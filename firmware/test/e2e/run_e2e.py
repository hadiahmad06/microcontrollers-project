#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""run_e2e.py - end-to-end bit-exact suite (ticket 3.8 and fix round 3.8F; PLAN gate G2 and a
16-bit pre-check of G3).

For each of N models (random float nets, exported by the REAL tools/export_model.py; the last one has
a deliberate logit tie) it builds test_e2e.c with the real firmware modules for host and sim16
(16-bit int), runs both, and compares every stage with the Python tools (features_ref, infer_ref):
window plan (tag, scenario, min_conf, checksum of the raw samples), model identity, feat, x8,
logits, top1, margin, knn, final (id, conf), export/import round trip (counts and CRC of the blob).

Two plans per model: the RANDOM plan (7 scenarios) and the DIRECTED plan (dplan.h, written here),
which makes each boundary happen on purpose: x8 saturation at +/-127, MLP logit tie, d1 == radius
and radius + 1, d2 == 0, MLP confidence 192 / 191, min_conf boundaries. A coverage counter per
boundary FAILS the suite if the boundary was never hit (on host or on sim16).
Prints PASS/FAIL per stage and target and finally `e2e suite PASS` (exit 0) or `e2e suite FAIL`
(exit 1). Compiler settings come from the environment (set by the Makefile from common.mk).
Python mirror of test_e2e.c: class Rng, gen_base, apply_noise, make_window, SCENARIOS,
MIN_CONF_TBL, expected(), expected_steps()."""
import argparse
import json
import os
import shlex
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get("TOOLS_DIR", os.path.join(HERE, "..", "..", "..", "tools")))
import features_ref  # noqa: E402
import infer_ref  # noqa: E402

M32 = 0xFFFFFFFF
SCENARIOS = [(0, 0), (1, 1), (1, 5), (3, 3), (4, 5), (3, 2), (4, 1)]   # (classes, templates each)
RT_SCEN = 4
MIN_CONF_TBL = [0, 64, 192, 255]
LEARNED_BASE = 9
T_OVR = infer_ref.GESTURE_OVERRIDE_CONF
STAGES = ["plan", "model", "feat", "x8", "logits", "top1", "margin", "knn", "final", "roundtrip", "count"]
DOP_RESET, DOP_LEARN, DOP_QUERY, DOP_RT = 0, 1, 2, 3
N_POOL = 2000                # windows in the per-model search pool (directed plan, balancing)
FAILS = []


def report(ok, name, detail=""):
    """Print one PASS/FAIL line and remember failures. Args: ok: bool; name: check name;
    detail: extra text. Returns: ok."""
    print("%s [%s]%s" % ("PASS" if ok else "FAIL", name, (" " + detail) if detail else ""))
    if not ok:
        FAILS.append(name)
    return ok


class Rng:
    """xorshift32 (13, 17, 5), identical to rng_next() in test_e2e.c."""

    def __init__(self, seed):
        """Args: seed: int; 0 is replaced by 1 (as in C). Returns: None."""
        self.s = (seed & M32) or 1

    def next(self):
        """Advance one step. Returns: the new state (uint32)."""
        x = self.s
        x ^= (x << 13) & M32
        x ^= x >> 17
        x ^= (x << 5) & M32
        self.s = x
        return x

    def rnd(self, n):
        """Args: n: int > 0. Returns: next() % n (as rnd() in C)."""
        return self.next() % n


def clamp12(v):
    """Clamp to [-2048, 2047]. Args: v: int. Returns: int."""
    return max(-2048, min(2047, v))


def rest_orientation(r):
    """Mirror of rest_orientation() in C. Args: r: Rng. Returns: list of 3 per-axis offsets."""
    w = [r.rnd(1025) for _ in range(3)]
    total = sum(w)
    if total == 0:
        w[0], total = 1, 1
    g = []
    for a in range(3):
        neg = r.rnd(2)
        m = (512 * w[a]) // total          # operands are non-negative: floor == C trunc
        g.append(-m if neg else m)
    return g


def gen_base(r):
    """Mirror of gen_base() in C (rest x3, burst x2, extreme, uniform). Args: r: Rng (advanced).
    Returns: window as 150 lists [x, y, z], values in [-2048, 2047]."""
    kind = r.rnd(7)
    g, na, start, ln, amp, sub = [0, 0, 0], 0, 0, 0, 0, 0
    if kind <= 4:
        g = rest_orientation(r)
        na = 1 + r.rnd(24)
    if kind in (3, 4):
        start = r.rnd(100)
        ln = 10 + r.rnd(40)
        amp = 200 + r.rnd(1500)
    if kind == 5:
        sub = r.rnd(4)
    out = []
    for i in range(150):
        row = []
        for a in range(3):
            if kind <= 4:
                v = g[a] + r.rnd(2 * na + 1) - na
                if kind >= 3 and start <= i < start + ln:
                    v += r.rnd(2 * amp + 1) - amp
            elif kind == 5:
                if sub == 0:
                    v = -2048
                elif sub == 1:
                    v = 2047
                elif sub == 2:
                    v = 2047 if (i & 1) else -2048
                else:
                    v = 2047 if ((i + a) & 1) else -2048
            else:
                v = r.rnd(4096) - 2048
            row.append(clamp12(v))
        out.append(row)
    return out


def apply_noise(win, nz, r):
    """Mirror of apply_noise() in C: v += rnd(2*nz+1) - nz per sample (sample-major), clamped.
    Args: win: window; nz: amplitude > 0; r: Rng (advanced 450 times). Returns: new window."""
    return [[clamp12(v + r.rnd(2 * nz + 1) - nz) for v in row] for row in win]


def window_checksum(win):
    """Mirror of win_checksum() in C (3.8R F-08). Args: win: window. Returns: uint32."""
    cs = 2166136261
    for row in win:
        for v in row:
            cs = ((cs ^ (v & 0xFFFF)) * 16777619) & M32
    return cs


def desc(base, nz=0, nzs=1, patches=()):
    """Window descriptor of a directed step. Args: base: nonzero uint32 gen_base() seed state;
    nz: noise amplitude (0 = none); nzs: nonzero noise seed state; patches: up to 3 pairs
    (sample * 3 + axis, delta). Returns: dict."""
    assert base != 0 and nzs != 0 and len(patches) <= 3
    return dict(base=base, nz=nz, nzs=nzs, patches=tuple(patches))


def make_window(d):
    """Mirror of build_window() in C. Args: d: descriptor from desc(). Returns: window."""
    win = gen_base(Rng(d["base"]))
    if d["nz"]:
        win = apply_noise(win, d["nz"], Rng(d["nzs"]))
    for pos, dl in d["patches"]:
        i, a = divmod(pos, 3)
        win[i][a] = clamp12(win[i][a] + dl)
    return win


def evaluate(win, m):
    """Run the Python tools on one window. Args: win: window; m: model dict. Returns: dict with
    cs, feat, x8, logits, top1, margin, conf (MLP confidence), unc (unclamped normalised values
    RSHIFT_R(feat - off, sh), before the +/-127 clamp) and tie (the maximum logit occurs twice)."""
    f = features_ref.features_extract(win)
    fw = infer_ref.forward(f, m)
    unc = [infer_ref.rshift_r(int(x) - int(o), int(s)) for x, o, s in zip(f, m["GM_IN_OFF"], m["GM_IN_SH"])]
    mx = max(fw["logits"])
    return dict(cs=window_checksum(win), feat=f, x8=fw["x8"], logits=fw["logits"], top1=fw["top1"],
                margin=fw["margin"], conf=fw["conf"], unc=unc, tie=fw["logits"].count(mx) > 1)


def query_result(ev, store, m, minc):
    """k-NN result and final decision of an evaluated window. Args: ev: evaluate() dict; store:
    {class id: [x8, ...]}; m: model dict; minc: min_conf. Returns: (knn dict or None, (id, conf))."""
    k = infer_ref.knn_query(ev["x8"], store) if store else None
    return k, infer_ref.classify_decide(ev["top1"], ev["margin"], m["GM_CONF_SHIFT"], k, minc)


def make_rec(tag, scn, minc, ev, k, fin):
    """Expected record of one window. Args: tag: 'L' or 'Q'; scn, minc; ev: evaluate() dict;
    k, fin: query_result() values (None for learn windows). Returns: dict."""
    rec = dict(ev)
    rec.update(tag=tag, scn=scn, minc=minc, knn=k, final=fin)
    return rec


def crc16_ibm3740(data):
    """CRC-16/IBM-3740 (poly 0x1021, init 0xFFFF, no reflection). Args: data: iterable of bytes.
    Returns: int."""
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def store_crc(store):
    """CRC trailer knn_export() must produce for a store (blob layout of knn.h: header, per class
    [count, next slot], templates class-major / slot-major, unused slots 0). Args: store: {class id:
    [x8, ...]} with at most 5 templates per class. Returns: int (low byte first on the wire)."""
    blob = [1, 4, 5, 60]
    for c in range(4):
        n = len(store.get(LEARNED_BASE + c, []))
        blob += [n, n % 5]
    for c in range(4):
        tpls = store.get(LEARNED_BASE + c, [])
        for s in range(5):
            blob += [v & 0xFF for v in (tpls[s] if s < len(tpls) else [0] * 60)]
    return crc16_ibm3740(blob)


def expected(m, seed, nper):
    """Run the random plan with the Python tools. Args: m: model dict (infer_ref.load_header);
    seed: window stream seed; nper: query windows per scenario. Returns: (window records, expected
    RT lines [(scn, 'ok')], expected B lines [(scn, crc)]). Record keys: see make_rec()."""
    r = Rng(seed)
    recs, rts, bs = [], [], []
    for scn, (ncls, ntpl_each) in enumerate(SCENARIOS):
        store = {}
        saved = []
        for c in range(ncls):
            for _ in range(ntpl_each):
                saved.append(r.s)
                ev = evaluate(gen_base(r), m)
                store.setdefault(LEARNED_BASE + c, []).append(ev["x8"])
                recs.append(make_rec("L", scn, 0, ev, None, None))
        for q in range(nper):
            sel = r.rnd(8)
            if sel >= 5 and saved:
                win = gen_base(Rng(saved[r.rnd(len(saved))]))
                win = apply_noise(win, 1 + r.rnd(8), r)
            else:
                win = gen_base(r)
            minc = MIN_CONF_TBL[r.rnd(4)]
            ev = evaluate(win, m)
            k, fin = query_result(ev, store, m, minc)
            recs.append(make_rec("Q", scn, minc, ev, k, fin))
            if scn == RT_SCEN and q == nper // 2:
                rts.append((scn, "ok"))
                bs.append((scn, store_crc(store)))
    return recs, rts, bs


def expected_steps(m, steps):
    """Run a directed plan with the Python tools (independent of C). Args: m: model dict; steps:
    list of dicts (op, scn, cls, minc, d). Returns: (window records, RT lines, B lines)."""
    recs, rts, bs = [], [], []
    store = {}
    for st in steps:
        if st["op"] == DOP_RESET:
            store = {}
        elif st["op"] == DOP_LEARN:
            ev = evaluate(make_window(st["d"]), m)
            store.setdefault(LEARNED_BASE + st["cls"], []).append(ev["x8"])
            recs.append(make_rec("L", st["scn"], 0, ev, None, None))
        elif st["op"] == DOP_QUERY:
            ev = evaluate(make_window(st["d"]), m)
            k, fin = query_result(ev, store, m, st["minc"])
            recs.append(make_rec("Q", st["scn"], st["minc"], ev, k, fin))
        else:
            rts.append((st["scn"], "ok"))
            bs.append((st["scn"], store_crc(store)))
    return recs, rts, bs


def write_dplan(path, steps):
    """Write dplan.h (DPLAN_N and the dplan[] initialiser of test_e2e.c). Args: path: output file;
    steps: directed steps. Returns: None."""
    rows = []
    for st in steps:
        d = st["d"]
        pat = list(d["patches"]) + [(0, 0)] * (3 - len(d["patches"]))
        rows.append("    {0x%08Xu, 0x%08Xu, {%s}, {%s}, %du, %du, %du, %du, %du, %du}" % (
            d["base"], d["nzs"], ", ".join("%du" % p[0] for p in pat), ", ".join("%d" % p[1] for p in pat),
            st["op"], st["scn"], st["cls"], st["minc"], d["nz"], len(d["patches"])))
    with open(path, "w") as f:
        f.write("/* generated by run_e2e.py, never committed */\n#define DPLAN_N %du\n"
                "static const dstep_t dplan[DPLAN_N] = {\n%s\n};\n" % (len(steps), ",\n".join(rows)))


# --------------------------------------------------------------------------- directed plan
def weak(ev, k, minc):
    """classify_decide's `weak` predicate. Args: ev: evaluate() dict; k: knn dict (unused, kept
    for symmetry); minc: min_conf. Returns: bool."""
    return ev["top1"] == 0 or ev["conf"] < minc or ev["conf"] < T_OVR


def gate_open(ev, k, minc):
    """True iff a weak MLP result would be overridden by the k-NN result. Args: as weak().
    Returns: bool."""
    return k is not None and weak(ev, k, minc) and k["d1"] <= k["radius"] and k["c_k"] >= minc


class Planner:
    """Builds the directed plan of one model. The pool (N_POOL random windows with all Python
    stages) is searched for windows that hit a boundary; descriptors with sparse patches nudge a
    near miss onto the exact value."""

    def __init__(self, m, pool, seed):
        """Args: m: model dict; pool: list of evaluate() dicts, each with key 'base'; seed: int for
        the patch search. Returns: None."""
        self.m, self.pool, self.rng = m, pool, Rng(seed)
        self.steps, self.scn, self.missing = [], len(SCENARIOS) - 1, []

    def start(self):
        """Begin a new directed scenario (RESET step). Returns: None."""
        self.scn += 1
        self.steps.append(dict(op=DOP_RESET, scn=self.scn, cls=0, minc=0, d=desc(1)))

    def add(self, op, d=None, cls=0, minc=0):
        """Append a step. Args: op: DOP_*; d: descriptor (LEARN/QUERY); cls: learned class index;
        minc: min_conf (QUERY). Returns: None."""
        self.steps.append(dict(op=op, scn=self.scn, cls=cls, minc=minc, d=d or desc(1)))

    def want(self, what, d):
        """Record a missing boundary window. Args: what: text; d: descriptor or None. Returns: d."""
        if d is None:
            self.missing.append(what)
        return d

    @staticmethod
    def of(e):
        """Descriptor of a pool entry. Args: e: pool entry. Returns: descriptor."""
        return desc(e["base"])

    def first(self, pred):
        """First pool entry satisfying pred. Args: pred: callable(entry) -> bool. Returns: entry or None."""
        return next((e for e in self.pool if pred(e)), None)

    def search(self, store, minc, score, pred, cands, ncand=40, ntrial=60):
        """Find a descriptor whose query result satisfies pred. Candidates are ranked by
        score(ev, k, fin) (lower is better, None skips), each tried as is and then with 1 or 2 random
        sample patches. Args: store: template store; minc: min_conf; score, pred: callables taking
        (ev, k, fin); cands: list from candidates(); ncand: candidates tried; ntrial: patch trials per
        candidate. Returns: descriptor or None."""
        shift = self.m["GM_CONF_SHIFT"]
        ranked = []
        for i, (d, e, k) in enumerate(cands):
            s = score(e, k, infer_ref.classify_decide(e["top1"], e["margin"], shift, k, minc))
            if s is not None:
                ranked.append((s, i))
        ranked.sort()
        for s0, i in ranked[:ncand]:
            d0, e, k = cands[i]
            if pred(e, k, infer_ref.classify_decide(e["top1"], e["margin"], shift, k, minc)):
                return d0
            cur, cur_s = d0, s0
            for _round in range(3 - len(d0["patches"])):     # greedy: add the best single patch, up to 3
                best = None
                for _t in range(ntrial):
                    dl = self.rng.rnd(801) - 400
                    d = desc(cur["base"], cur["nz"], cur["nzs"], cur["patches"] + ((self.rng.rnd(450), dl or 1),))
                    ev = evaluate(make_window(d), self.m)
                    k2, fin2 = query_result(ev, store, self.m, minc)
                    if k2 is None:
                        continue
                    if pred(ev, k2, fin2):
                        return d
                    s2 = score(ev, k2, fin2)
                    if s2 is not None and s2 < cur_s and (best is None or s2 < best[0]):
                        best = (s2, d)
                if best is None:
                    break
                cur_s, cur = best
        return None

    def candidates(self, store, tpl):
        """Search candidates for a store: every pool entry plus noisy copies (several amplitudes) of
        template windows, all with their k-NN result. Args: store: template store (not empty); tpl:
        template descriptors (without patches). Returns: list of (descriptor, evaluated window, k-NN dict)."""
        out = []
        for e in self.pool:
            out.append((self.of(e), e, infer_ref.knn_query(e["x8"], store)))
        for d0 in tpl:
            for nz in (2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 28, 32, 36, 40, 48, 56, 64, 80, 96, 128, 192, 250):
                for _ in range(2):
                    d = desc(d0["base"], nz, self.rng.next())
                    ev = evaluate(make_window(d), self.m)
                    out.append((d, ev, infer_ref.knn_query(ev["x8"], store)))
            for _ in range(16):     # a few large single-sample changes: distances between the noise steps
                pats = tuple((self.rng.rnd(450), self.rng.rnd(4001) - 2000 or 1) for _ in range(1 + self.rng.rnd(3)))
                d = desc(d0["base"], d0["nz"], d0["nzs"], pats)
                ev = evaluate(make_window(d), self.m)
                out.append((d, ev, infer_ref.knn_query(ev["x8"], store)))
        return out

    def build(self):
        """Create all directed scenarios. Returns: (steps, list of boundaries for which no window was found)."""
        self.plan_saturation()
        self.plan_minconf_mlp()
        self.plan_radius()
        self.plan_d2_zero()
        self.plan_conf_gate()
        self.plan_ck()
        return self.steps, self.missing

    def plan_saturation(self):
        """x8 clamp: windows whose unclamped value lands far beyond +/-127 and exactly on +/-128,
        learned as templates and queried. Returns: None."""
        top = max(self.pool, key=lambda e: max(e["unc"]))
        bot = min(self.pool, key=lambda e: min(e["unc"]))
        e128 = self.want("x8 unclamped == +128", self.first(lambda e: 128 in e["unc"]))
        em128 = self.want("x8 unclamped == -128", self.first(lambda e: -128 in e["unc"]))
        self.start()
        self.add(DOP_LEARN, self.of(top), cls=0)
        self.add(DOP_LEARN, self.of(bot), cls=1)
        for i, e in enumerate([top, bot, e128, em128]):
            if e is not None:
                self.add(DOP_QUERY, self.of(e), minc=(0, 64)[i % 2])

    def plan_minconf_mlp(self):
        """min_conf boundaries and the MLP tie with an empty store: queries with conf == min_conf
        (accepted), conf == min_conf - 1 (rejected), for min_conf 64, 192, 255; tie windows if the
        model has any. Returns: None."""
        self.start()
        for minc in (64, 192, 255):
            for conf in (minc, minc - 1):
                e = self.want("MLP conf %d with min_conf %d" % (conf, minc), self.first(lambda e: e["conf"] == conf))
                if e is not None:
                    self.add(DOP_QUERY, self.of(e), minc=minc)
        ties = [e for e in self.pool if e["tie"]][:3]
        for i, e in enumerate(ties):
            self.add(DOP_QUERY, self.of(e), minc=(0, 64, 192)[i])

    def far_templates(self, n, skip=()):
        """Pool entries that are far from each other in x8 space (greedy farthest-first), so the
        class radius is large. Args: n: how many; skip: base states to avoid. Returns: list of entries."""
        cand = [e for e in self.pool[:400] if e["base"] not in skip]
        chosen = [cand[0]]
        while len(chosen) < n:
            nxt = max(cand, key=lambda e: min(infer_ref.knn_l1(e["x8"], c["x8"]) for c in chosen))
            chosen.append(nxt)
        return chosen

    def plan_radius(self):
        """d1 == radius and d1 == radius + 1 with a weak MLP (so the override is decisive); a round
        trip between learning and querying. Returns: None."""
        base_e = self.pool[7]
        tpl = [self.of(base_e), desc(base_e["base"], nz=2, nzs=0x1234567), desc(base_e["base"], nz=3, nzs=0x7654321)]
        others = self.far_templates(2, skip=(base_e["base"],))
        self.start()
        store = {}
        for d in tpl:
            self.add(DOP_LEARN, d, cls=0)
            store.setdefault(LEARNED_BASE, []).append(evaluate(make_window(d), self.m)["x8"])
        for e in others:
            self.add(DOP_LEARN, self.of(e), cls=1)
            store.setdefault(LEARNED_BASE + 1, []).append(e["x8"])
        self.add(DOP_RT)
        kc = self.candidates(store, tpl)
        for off in (0, 1):
            def score(ev, k, fin, off=off):
                """Distance of d1 from radius + off, only for weak windows. Returns: int or None."""
                return abs(k["d1"] - k["radius"] - off) if weak(ev, k, 0) else None

            def pred(ev, k, fin, off=off):
                """d1 == radius + off with a weak MLP. Returns: bool."""
                return k["d1"] == k["radius"] + off and weak(ev, k, 0) and k["c_k"] >= 0
            d = self.want("d1 == radius + %d" % off, self.search(store, 0, score, pred, kc))
            if d is not None:
                self.add(DOP_QUERY, d, minc=0)

    def plan_d2_zero(self):
        """d2 == 0: the same window learned for two classes, queried with min_conf 0 and 64
        (c_k = 0 passes the first and fails the second). Returns: None."""
        x, y = self.pool[11], self.pool[23]
        self.start()
        self.add(DOP_LEARN, self.of(x), cls=0)
        self.add(DOP_LEARN, self.of(x), cls=1)
        self.add(DOP_LEARN, self.of(y), cls=2)
        self.add(DOP_QUERY, self.of(x), minc=0)
        self.add(DOP_QUERY, self.of(x), minc=64)
        self.add(DOP_QUERY, self.of(y), minc=0)

    def plan_conf_gate(self):
        """MLP confidence exactly 192 and 191 with an open k-NN gate (the override threshold).
        Two classes of far-apart templates (large radius); a round trip after learning. Returns: None."""
        tpl = self.far_templates(8)
        self.start()
        store = {}
        for i, e in enumerate(tpl):
            cls = i % 2
            self.add(DOP_LEARN, self.of(e), cls=cls)
            store.setdefault(LEARNED_BASE + cls, []).append(e["x8"])
        self.add(DOP_RT)
        kc = self.candidates(store, [self.of(e) for e in tpl])
        for conf in (T_OVR, T_OVR - 1):
            def score(ev, k, fin, conf=conf):
                """Distance of the MLP confidence from conf, big penalty for a closed gate. Returns: int or None."""
                if ev["top1"] == 0:
                    return None
                return abs(ev["conf"] - conf) + (0 if k["d1"] <= k["radius"] else 1000)

            def pred(ev, k, fin, conf=conf):
                """conf == target, top1 != 0, k-NN gate open for a weak MLP. Returns: bool."""
                return (ev["top1"] != 0 and ev["conf"] == conf and k["d1"] <= k["radius"]
                        and k["c_k"] >= 0 and (conf < T_OVR) == gate_open(ev, k, 0))
            d = self.want("MLP conf %d with open k-NN gate" % conf, self.search(store, 0, score, pred, kc))
            if d is not None:
                self.add(DOP_QUERY, d, minc=0)

    def plan_ck(self):
        """c_k == min_conf and min_conf - 1 for min_conf 64 and 192, with a weak MLP and d1 <= radius.
        Class 0 holds far-apart templates; class 1 holds noisy copies of them, so d2 is small enough
        for single-sample patches to tune c_k exactly. A round trip after learning. Returns: None."""
        tpl = self.far_templates(3, skip=(self.pool[7]["base"],))
        tpl_d = [self.of(e) for e in tpl]
        cop = [desc(d["base"], 40, 0x2468ACE + i) for i, d in enumerate(tpl_d)]
        self.start()
        store = {}
        for cls, ds in ((0, tpl_d), (1, cop)):
            for d in ds:
                self.add(DOP_LEARN, d, cls=cls)
                store.setdefault(LEARNED_BASE + cls, []).append(evaluate(make_window(d), self.m)["x8"])
        self.add(DOP_RT)
        cands = self.candidates(store, tpl_d)
        for minc in (64, 192):
            for ck in (minc, minc - 1):
                def score(ev, k, fin, ck=ck, minc=minc):
                    """Distance of c_k from ck, only for weak MLP windows inside the radius. Returns: int or None."""
                    if not weak(ev, k, minc) or k["d1"] > k["radius"]:
                        return None
                    return abs(k["c_k"] - ck)

                def pred(ev, k, fin, ck=ck, minc=minc):
                    """c_k == ck with a weak MLP and d1 <= radius. Returns: bool."""
                    return weak(ev, k, minc) and k["d1"] <= k["radius"] and k["c_k"] == ck
                d = self.want("c_k %d with min_conf %d" % (ck, minc), self.search(store, minc, score, pred, cands))
                if d is not None:
                    self.add(DOP_QUERY, d, minc=minc)


# --------------------------------------------------------------------------- coverage
def boundary_hits(recs):
    """Count how often each boundary was hit, from the expected records (queries only for the
    decision boundaries). Args: recs: expected records. Returns: dict name -> count."""
    h = {n: 0 for n, _ in BOUNDARIES}
    for r in recs:
        for name, fn in BOUNDARIES:
            if fn(r):
                h[name] += 1
    return h


def _q(r):
    """True for a query record with a k-NN result. Args: r: record. Returns: bool."""
    return r["tag"] == "Q" and r["knn"] is not None


def _decisive(r, off):
    """d1 == radius + off for a weak MLP and an open c_k gate, so the override depends on it.
    Args: r: record; off: 0 or 1. Returns: bool."""
    k = r["knn"]
    return _q(r) and k["d1"] == k["radius"] + off and weak(r, k, r["minc"]) and k["c_k"] >= r["minc"]


def _conf_edge(r, conf):
    """MLP conf == conf with top1 != 0, min_conf <= conf and an open k-NN gate (override differs
    between conf and conf-1 only through the T_OVR test). Args: r: record; conf: 192 or 191.
    Returns: bool."""
    k = r["knn"]
    return (_q(r) and r["conf"] == conf and r["top1"] != 0 and r["minc"] <= conf
            and k["d1"] <= k["radius"] and k["c_k"] >= r["minc"])


BOUNDARIES = [
    ("x8 saturates at +127 (unclamped >= 256)", lambda r: max(r["unc"]) >= 256),
    ("x8 saturates at -127 (unclamped <= -256)", lambda r: min(r["unc"]) <= -256),
    ("x8 clamp edge: unclamped == +128", lambda r: 128 in r["unc"]),
    ("x8 clamp edge: unclamped == -128", lambda r: -128 in r["unc"]),
    ("MLP logit tie for top1 (margin 0)", lambda r: r["tie"]),
    ("k-NN d1 == radius (override decisive)", lambda r: _decisive(r, 0)),
    ("k-NN d1 == radius + 1 (override denied)", lambda r: _decisive(r, 1)),
    ("k-NN d2 == 0 (has_other, c_k 0)", lambda r: _q(r) and r["knn"]["has_other"] and r["knn"]["d2"] == 0),
    ("MLP conf == 192 (not weak), gate open", lambda r: _conf_edge(r, T_OVR)),
    ("MLP conf == 191 (weak, overridden)", lambda r: _conf_edge(r, T_OVR - 1)),
    ("min_conf: MLP conf == min_conf accepted", lambda r: r["tag"] == "Q" and r["minc"] > 0 and r["final"][1] == r["minc"]
     and 0 <= r["final"][0] < LEARNED_BASE),
    ("min_conf: conf == min_conf - 1 rejected", lambda r: r["tag"] == "Q" and r["minc"] > 0
     and r["final"][1] == r["minc"] - 1 and r["final"][0] == -1),
    ("min_conf: k-NN c_k == min_conf overrides", lambda r: _q(r) and r["minc"] > 0 and r["knn"]["c_k"] == r["minc"]
     and r["final"][0] >= LEARNED_BASE),
    ("min_conf: k-NN c_k == min_conf - 1 denied", lambda r: _q(r) and r["minc"] > 0 and r["knn"]["c_k"] == r["minc"] - 1
     and weak(r, r["knn"], r["minc"]) and r["knn"]["d1"] <= r["knn"]["radius"] and r["final"][0] < LEARNED_BASE),
]


# --------------------------------------------------------------------------- C output
def s16(h):
    """Args: h: hex string of 16 bits. Returns: signed int."""
    v = int(h, 16)
    return v - 0x10000 if v & 0x8000 else v


def s8(h):
    """Args: h: hex string of 8 bits. Returns: signed int."""
    v = int(h, 16)
    return v - 0x100 if v & 0x80 else v


def s32(h):
    """Args: h: hex string of 32 bits. Returns: signed int."""
    v = int(h, 16)
    return v - (1 << 32) if v & 0x80000000 else v


def parse_c(text):
    """Parse the output of test_e2e.c. Args: text: program output. Returns: (dict idx -> record,
    list of RT tuples, list of B tuples, number from DONE or None, model line tokens or None,
    list of unparsed non-empty lines)."""
    win, rts, bs, done, minfo, junk = {}, [], [], None, None, []
    for line in text.splitlines():
        t = line.split()
        if not t:
            continue
        try:
            if t[0] == "M":
                minfo = t[1:]
            elif t[0] == "W":
                win.setdefault(int(t[1]), {}).update(tag=t[2], scn=int(t[3]), minc=int(t[4]), cs=int(t[5], 16))
            elif t[0] == "F":
                d = win.setdefault(int(t[1]), {}).setdefault("feat", {})
                d[int(t[2])] = [s16(v) for v in t[3:]]
            elif t[0] == "X":
                win.setdefault(int(t[1]), {})["x8"] = [s8(v) for v in t[2:]]
            elif t[0] == "G":
                w = win.setdefault(int(t[1]), {})
                w["top1"], w["margin"] = int(t[2]), s32(t[3])
                w["logits"] = [s32(v) for v in t[4:]]
            elif t[0] == "K":
                win.setdefault(int(t[1]), {})["knn"] = None if t[2] == "-" else tuple(int(v) for v in t[2:])
            elif t[0] == "R":
                win.setdefault(int(t[1]), {})["final"] = (int(t[2]), int(t[3]))
            elif t[0] == "RT":
                rts.append((int(t[1]), t[2]))
            elif t[0] == "B":
                bs.append((int(t[1]), int(t[2], 16)))
            elif t[0] == "DONE":
                done = int(t[1])
            elif t[0] == "SIM16_EXIT":
                pass    # printed by sim16_exit() on the host build
            else:
                junk.append(line)
        except (ValueError, IndexError):
            junk.append(line)
    for w in win.values():
        if "feat" in w and set(w["feat"]) == {0, 1}:
            w["feat"] = w["feat"][0] + w["feat"][1]
    return win, rts, bs, done, minfo, junk


def knn_tuple(k):
    """Args: k: dict from infer_ref.knn_query or None. Returns: tuple in the C print order
    (kid, d1, d2, has_other, c_k, radius) or None; d2 is 0 when absent, as C prints it."""
    if k is None:
        return None
    return (k["kid"], k["d1"], k["d2"] if k["has_other"] else 0, int(k["has_other"]), k["c_k"], k["radius"])


def compare(label, mod, exp, rts_exp, bs_exp, cout):
    """Compare one C run with the expected records and report every stage.
    Args: label: e.g. 'm1/host'; mod: model dict (header values); exp: records (random plan then
    directed plan); rts_exp, bs_exp: expected RT and B lines; cout: C program output text.
    Returns: None."""
    win, rts, bs, done, minfo, junk = parse_c(cout)
    first = {s: None for s in STAGES}
    want_m = ["%08x" % mod["GM_MODEL_HASH"], str(mod["GM_CONF_SHIFT"])]
    if minfo != want_m:
        first["model"] = "C M line %s, header says %s" % (minfo, want_m)
    for i, e in enumerate(exp):
        w = win.get(i)
        if w is None:
            first["count"] = first["count"] or "window %d missing" % i
            continue
        if (w.get("tag"), w.get("scn"), w.get("minc"), w.get("cs")) != (e["tag"], e["scn"], e["minc"], e["cs"]):
            first["plan"] = first["plan"] or "window %d C=%s py=%s" % (
                i, (w.get("tag"), w.get("scn"), w.get("minc"), w.get("cs")), (e["tag"], e["scn"], e["minc"], e["cs"]))
        for st in ("feat", "x8", "logits", "top1", "margin"):
            if w.get(st) != e[st]:
                first[st] = first[st] or "window %d C=%s py=%s" % (i, w.get(st), e[st])
        if e["tag"] == "Q":
            if w.get("knn") != knn_tuple(e["knn"]):
                first["knn"] = first["knn"] or "window %d C=%s py=%s" % (i, w.get("knn"), knn_tuple(e["knn"]))
            if w.get("final") != e["final"]:
                first["final"] = first["final"] or "window %d C=%s py=%s" % (i, w.get("final"), e["final"])
    if done != len(exp) or len(win) != len(exp) or junk:
        first["count"] = first["count"] or "DONE=%s windows_seen=%d expected=%d unparsed=%s" % (
            done, len(win), len(exp), junk[:2])
    if rts != rts_exp or bs != bs_exp:
        first["roundtrip"] = "C RT=%s B=%s expected RT=%s B=%s" % (rts, bs, rts_exp, bs_exp)
    for st in STAGES:
        report(first[st] is None, "%s %s" % (label, st), first[st] or "")


def run(cmd, timeout=900):
    """Run a command. Args: cmd: argv list; timeout: seconds. Returns: CompletedProcess with text."""
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)


def calib_windows(r, n):
    """Calibration windows: rest and burst kinds only (base kinds 0..4), like recorded data and unlike
    the full-scale extremes of the test mix, so the test windows really saturate x8 (3.8R F-01).
    Args: r: Rng (advanced); n: count. Returns: list of windows."""
    out = []
    while len(out) < n:
        if Rng(r.s).next() % 7 <= 4:
            out.append(gen_base(r))
        else:
            r.next()
    return out


def balance_bias(net, x8, tie, iters=300):
    """Adjust the float output biases so every class is the top1 equally often on x8 (3.8R F-03).
    Args: net: dict W1, b1, W2, b2, K (b2 modified); x8: float array [n, 60]; tie: if True classes 3
    and 5 share row and bias (a deliberate logit tie); iters: iterations. Returns: None."""
    h = np.maximum((x8 / net["K"]) @ net["W1"].T + net["b1"], 0.0)
    for it in range(iters):
        lg = h @ net["W2"].T + net["b2"]
        freq = np.bincount(lg.argmax(axis=1), minlength=9) / len(lg)
        net["b2"] += (1.0 / 9 - freq) * lg.std() * (1.5 if it < iters // 2 else 0.5)
        if tie:
            net["b2"][5] = net["b2"][3]


def histogram(tops):
    """Args: tops: list of top1 values. Returns: (classes seen, max share, {class: count})."""
    cnt = {}
    for t in tops:
        cnt[t] = cnt.get(t, 0) + 1
    return len(cnt), max(cnt.values()) / len(tops), dict(sorted(cnt.items()))


def export_model(m, mdir, tools, tie):
    """Create model m with the real exporter. Args: m: model number; mdir: output dir; tools: tools
    dir; tie: True for the model whose classes 3 and 5 always have equal logits. Returns: (path of
    gesture_model.h, reseeds, conf_shift, model dict, pool as a list of evaluated windows with keys
    base, feat, x8, logits, top1, margin, conf, tie, unc). A net the exporter refuses (exit 3), or whose int8 top1 histogram over
    the pool is not spread (>= 7 classes, no class above 40 %), is replaced by the next reseed; the
    best net is kept after 40 attempts."""
    os.makedirs(mdir, exist_ok=True)
    r = Rng(0xCA1B0000 + m)
    calib = np.array([features_ref.features_extract(w) for w in calib_windows(r, 400)], dtype=np.int16)
    np.save(os.path.join(mdir, "calib.npy"), calib)
    exp = os.path.join(tools, "export_model.py")
    norm = os.path.join(mdir, "norm.json")
    p = run([sys.executable, exp, "norm", "--features", os.path.join(mdir, "calib.npy"), "--out", norm])
    if p.returncode != 0:
        raise RuntimeError("export_model norm failed (%d): %s" % (p.returncode, p.stderr))
    with open(norm) as f:
        nj = json.load(f)
    nm = {"GM_IN_OFF": nj["off"], "GM_IN_SH": nj["sh"]}
    pr = Rng(0xD1C70000 + m)
    pool = []
    for _ in range(N_POOL):
        base = pr.s
        f = features_ref.features_extract(gen_base(pr))
        pool.append(dict(base=base, feat=f, x8=infer_ref.normalize(f, nm)))
    x8f = np.array([e["x8"] for e in pool], dtype=np.float64)
    hdr = os.path.join(mdir, "gesture_model.h")
    reseeds, best, shift = 0, None, 6
    for attempt in range(40):
        rng = np.random.default_rng(1000 * m + attempt)
        net = dict(W1=rng.normal(0, 0.6, (16, 60)), b1=rng.normal(0, 0.3, 16),
                   W2=rng.normal(0, 1.0, (9, 16)), b2=rng.normal(0, 0.3, 9), K=127.0)
        if tie:
            net["W2"][5] = net["W2"][3]
            net["b2"][5] = net["b2"][3]
        balance_bias(net, x8f, tie)
        np.savez(os.path.join(mdir, "net.npz"), **net)
        p = run([sys.executable, exp, "header", "--weights", os.path.join(mdir, "net.npz"), "--norm", norm,
                 "--calib", os.path.join(mdir, "calib.npy"), "--conf-shift", str(shift), "--out", hdr])
        if p.returncode == 3:
            reseeds += 1
            continue
        if p.returncode != 0:
            raise RuntimeError("export_model header failed (%d): %s" % (p.returncode, p.stderr))
        mod = infer_ref.load_header(hdr)
        fws = [infer_ref.forward(e["feat"], mod) for e in pool[:800]]
        ncls, share, _ = histogram([fw["top1"] for fw in fws])
        score = (min(ncls, 7), -max(share, 0.4))
        if best is None or score > best[0]:
            best = (score, attempt, net, ncls, share)
        if ncls >= 7 and share <= 0.4:
            break
        reseeds += 1
    _, attempt, net, ncls, share = best
    np.savez(os.path.join(mdir, "net.npz"), **net)
    p = run([sys.executable, exp, "header", "--weights", os.path.join(mdir, "net.npz"), "--norm", norm,
             "--calib", os.path.join(mdir, "calib.npy"), "--conf-shift", str(shift), "--out", hdr])
    if p.returncode != 0:
        raise RuntimeError("export_model header failed (%d): %s" % (p.returncode, p.stderr))
    mod = infer_ref.load_header(hdr)
    fws = [infer_ref.forward(e["feat"], mod) for e in pool]
    margins = [fw["margin"] for fw in fws]
    s0 = max(0, min(24, sorted(margins)[len(margins) // 2].bit_length() - 7))   # median confidence ~64..127
    bestk = None
    for s in range(max(0, s0 - 2), min(24, s0 + 2) + 1):    # shift near s0 that has windows at every edge value
        cnt = {}
        for mg in margins:
            c = min(255, mg >> s)
            cnt[c] = cnt.get(c, 0) + 1
        key = (min(cnt.get(v, 0) for v in (63, 64, 191, 192, 254, 255)), -abs(s - s0))
        if bestk is None or key > bestk[0]:
            bestk = (key, s)
    shift = bestk[1]
    p = run([sys.executable, exp, "header", "--weights", os.path.join(mdir, "net.npz"), "--norm", norm,
             "--calib", os.path.join(mdir, "calib.npy"), "--conf-shift", str(shift), "--out", hdr])
    if p.returncode != 0:
        raise RuntimeError("export_model header failed (%d): %s" % (p.returncode, p.stderr))
    mod = infer_ref.load_header(hdr)
    pev = []
    for e, fw in zip(pool, fws):    # margins do not depend on GM_CONF_SHIFT; the confidence does
        mx = max(fw["logits"])
        pev.append(dict(base=e["base"], feat=e["feat"], x8=fw["x8"], logits=fw["logits"], top1=fw["top1"],
                        margin=fw["margin"], conf=infer_ref.mlp_conf(fw["margin"], shift),
                        tie=fw["logits"].count(mx) > 1,
                        unc=[infer_ref.rshift_r(int(x) - int(o), int(s)) for x, o, s in
                             zip(e["feat"], mod["GM_IN_OFF"], mod["GM_IN_SH"])]))
    return hdr, reseeds, shift, mod, pev


def build(kind, mdir, out, seed, nper):
    """Compile test_e2e.c with the module sources for host or sim16.
    Args: kind: 'host' or 'avr'; mdir: dir holding gesture_model.h and dplan.h; out: output file;
    seed, nper: compile-time values (sim16 only). Returns: (ok, compiler messages)."""
    cc = os.environ["HOST_CC" if kind == "host" else "AVR_CC"]
    flags = shlex.split(os.environ["HOST_CFLAGS" if kind == "host" else "AVR_CFLAGS"])
    defs = [] if kind == "host" else ["-DTEST_SEED=%du" % seed, "-DTEST_NPER=%du" % nper]
    cmd = [cc, "-iquote", mdir] + flags + defs + ["-o", out, os.path.join(HERE, "test_e2e.c"),
                                                   os.environ["SIM16_SRC"]] + shlex.split(os.environ["MOD_SRC"])
    p = run(cmd)
    return p.returncode == 0, p.stdout + p.stderr


def main():
    """Entry point. Returns: process exit code (0 all pass, 1 any failure)."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--build", default="build")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--models", type=int, default=4)
    ap.add_argument("--nper-host", type=int, default=300)
    ap.add_argument("--nper-sim", type=int, default=60)
    a = ap.parse_args()
    tools = os.environ.get("TOOLS_DIR", os.path.join(HERE, "..", "..", "..", "tools"))
    hits = {"host": {n: [] for n, _ in BOUNDARIES}, "sim16": {n: [] for n, _ in BOUNDARIES}}
    tot = {"host": [0, 0], "sim16": [0, 0]}
    for m in range(1, a.models + 1):
        t_m = time.time()
        mdir = os.path.join(a.build, "m%d" % m)
        tie = (m == a.models)
        hdr, reseeds, shift, mod, pev = export_model(m, mdir, tools, tie)
        ncls, share, hist = histogram([e["top1"] for e in pev])
        steps, missing = Planner(mod, pev, 0xBEEF + m).build()
        write_dplan(os.path.join(mdir, "dplan.h"), steps)
        print("model m%d%s: exporter reseeds %d, GM_CONF_SHIFT %d, hash 0x%08X; pool top1 classes %d, "
              "max share %.0f%%, histogram %s; directed plan %d steps; setup %.1fs" % (
                  m, " (logit tie net)" if tie else "", reseeds, shift, mod["GM_MODEL_HASH"], ncls, 100 * share,
                  hist, len(steps), time.time() - t_m))
        report(ncls >= 7 and share <= 0.4, "m%d model spread (>= 7 top1 classes, no class > 40%%)" % m)
        report(not missing, "m%d directed windows found" % m, "missing: %s" % missing if missing else "")
        drecs, drts, dbs = expected_steps(mod, steps)
        for kind, nper in (("host", a.nper_host), ("avr", a.nper_sim)):
            tgt = "host" if kind == "host" else "sim16"
            label = "m%d/%s" % (m, tgt)
            seed = (0xC0FFEE if kind == "host" else 0x5151) + 97 * m + a.seed
            exe = os.path.join(mdir, "e2e_" + kind + (".elf" if kind == "avr" else ""))
            ok, msg = build(kind, mdir, exe, seed, nper)
            if not report(ok, "%s build" % label, "" if ok else "\n" + msg):
                continue
            rrecs, rrts, rbs = expected(mod, seed, nper)
            exp, rts_exp, bs_exp = rrecs + drecs, rrts + drts, rbs + dbs
            t0 = time.time()
            if kind == "host":
                p = run([exe, str(seed), str(nper)])
            else:
                p = run([os.environ["SIM16_RUN"], exe, "900"])
            dt = time.time() - t0
            if kind == "host" and p.returncode not in (0, 1):
                report(False, "%s run" % label, "exit %d %s" % (p.returncode, p.stderr))
                continue
            if kind == "avr" and p.returncode == 2:
                report(False, "%s run" % label, "simavr timeout/crash: " + p.stderr)
                continue
            compare(label, mod, exp, rts_exp, bs_exp, p.stdout)
            report(p.returncode == 0, "%s c-side checks" % label, "exit %d" % p.returncode)
            h = boundary_hits(exp)
            for n in h:
                hits[tgt][n].append(h[n])
            nq = sum(1 for e in exp if e["tag"] == "Q")
            tot[tgt][0] += len(exp)
            tot[tgt][1] += nq
            hd = boundary_hits(drecs)
            print("  %s: %d windows (%d queries, %d directed), %.1fs run; top1 classes seen %d; "
                  "overrides %d, rejects %d, plain MLP %d" % (
                      label, len(exp), nq, len(drecs), dt, len({e["top1"] for e in exp}),
                      sum(1 for e in exp if e["final"] and e["final"][0] >= LEARNED_BASE),
                      sum(1 for e in exp if e["final"] and e["final"][0] == -1),
                      sum(1 for e in exp if e["final"] and 0 <= e["final"][0] < LEARNED_BASE)))
            print("    directed-only hits: %s" % ", ".join("%d" % hd[n] for n, _ in BOUNDARIES))
    print("coverage of boundaries (hits per model m1..m%d; total must be > 0 on host and on sim16):" % a.models)
    print("  %-46s %-24s %-24s" % ("boundary", "host", "sim16"))
    for n, _ in BOUNDARIES:
        sh, ss = hits["host"][n], hits["sim16"][n]
        print("  %-46s %-24s %-24s" % (n, "%d = %s" % (sum(sh), "+".join(map(str, sh))),
                                        "%d = %s" % (sum(ss), "+".join(map(str, ss)))))
    for n, _ in BOUNDARIES:
        report(sum(hits["host"][n]) > 0 and sum(hits["sim16"][n]) > 0, "coverage: %s" % n,
               "host %d sim16 %d" % (sum(hits["host"][n]), sum(hits["sim16"][n])))
    print("windows: host %d (%d queries), sim16 %d (%d queries)" % (tot["host"][0], tot["host"][1],
                                                                    tot["sim16"][0], tot["sim16"][1]))
    print("e2e suite %s" % ("PASS" if not FAILS else "FAIL"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
