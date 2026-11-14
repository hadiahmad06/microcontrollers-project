#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""run_e2e.py - end-to-end bit-exact suite (ticket 3.8, PLAN gate G2 and a 16-bit pre-check of G3).

For each of N models (random float nets, exported by the REAL tools/export_model.py) it builds
test_e2e.c with the real firmware modules for host and sim16 (16-bit int), runs both, and compares
every stage with the Python tools (features_ref, infer_ref): feat, x8, logits, top1, margin, knn,
final (id, conf), plus the export/import round trip and the window plan. Prints PASS/FAIL per
stage and target and finally `e2e suite PASS` (exit 0) or `e2e suite FAIL` (exit 1).
Compiler settings come from the environment (set by the Makefile from common.mk).
Python mirror of test_e2e.c: class Rng, gen_base, SCENARIOS, MIN_CONF_TBL, expected()."""
import argparse
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
STAGES = ["plan", "feat", "x8", "logits", "top1", "margin", "knn", "final", "roundtrip", "count"]
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


def expected(m, seed, nper):
    """Run the whole plan with the Python tools. Args: m: model dict (infer_ref.load_header);
    seed: window stream seed; nper: query windows per scenario. Returns: (list of window records,
    expected RT lines). Record keys: tag, scn, minc, feat, x8, logits, top1, margin, knn (dict or
    None), final ((id, conf) or None for learn windows)."""
    r = Rng(seed)
    recs, rts = [], []
    for scn, (ncls, ntpl_each) in enumerate(SCENARIOS):
        store = {}
        saved = []

        def stages(win):
            """Features and MLP stages of one window. Args: win. Returns: (feat, forward dict)."""
            f = features_ref.features_extract(win)
            return f, infer_ref.forward(f, m)

        for c in range(ncls):
            for _ in range(ntpl_each):
                saved.append(r.s)
                f, fw = stages(gen_base(r))
                store.setdefault(LEARNED_BASE + c, []).append(fw["x8"])
                recs.append(dict(tag="L", scn=scn, minc=0, feat=f, x8=fw["x8"], logits=fw["logits"],
                                 top1=fw["top1"], margin=fw["margin"], knn=None, final=None))
        for q in range(nper):
            sel = r.rnd(8)
            if sel >= 5 and saved:
                r2 = Rng(saved[r.rnd(len(saved))])
                win = gen_base(r2)
                nz = 1 + r.rnd(8)
                win = [[clamp12(v + r.rnd(2 * nz + 1) - nz) for v in row] for row in win]
            else:
                win = gen_base(r)
            minc = MIN_CONF_TBL[r.rnd(4)]
            f, fw = stages(win)
            k = infer_ref.knn_query(fw["x8"], store) if saved else None
            fin = infer_ref.classify_decide(fw["top1"], fw["margin"], m["GM_CONF_SHIFT"], k, minc)
            recs.append(dict(tag="Q", scn=scn, minc=minc, feat=f, x8=fw["x8"], logits=fw["logits"],
                             top1=fw["top1"], margin=fw["margin"], knn=k, final=fin))
            if scn == RT_SCEN and q == nper // 2:
                rts.append((scn, "ok"))
    return recs, rts


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
    list of RT tuples, number from DONE or None, model line tokens or None, list of unparsed
    non-empty lines)."""
    win, rts, done, minfo, junk = {}, [], None, None, []
    for line in text.splitlines():
        t = line.split()
        if not t:
            continue
        try:
            if t[0] == "M":
                minfo = t[1:]
            elif t[0] == "W":
                win.setdefault(int(t[1]), {}).update(tag=t[2], scn=int(t[3]), minc=int(t[4]))
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
    return win, rts, done, minfo, junk


def knn_tuple(k):
    """Args: k: dict from infer_ref.knn_query or None. Returns: tuple in the C print order
    (kid, d1, d2, has_other, c_k, radius) or None; d2 is 0 when absent, as C prints it."""
    if k is None:
        return None
    return (k["kid"], k["d1"], k["d2"] if k["has_other"] else 0, int(k["has_other"]), k["c_k"], k["radius"])


def compare(label, exp, rts_exp, cout):
    """Compare one C run with the expected records and report every stage.
    Args: label: e.g. 'm1/host'; exp: records from expected(); rts_exp: expected RT lines;
    cout: C program output text. Returns: dict with coverage counters."""
    win, rts, done, minfo, junk = parse_c(cout)
    first = {s: None for s in STAGES}
    for i, e in enumerate(exp):
        w = win.get(i)
        if w is None:
            first["count"] = first["count"] or "window %d missing" % i
            continue
        if (w.get("tag"), w.get("scn"), w.get("minc")) != (e["tag"], e["scn"], e["minc"]):
            first["plan"] = first["plan"] or "window %d C=%s py=%s" % (
                i, (w.get("tag"), w.get("scn"), w.get("minc")), (e["tag"], e["scn"], e["minc"]))
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
    if rts != rts_exp:
        first["roundtrip"] = "C=%s expected=%s" % (rts, rts_exp)
    for st in STAGES:
        report(first[st] is None, "%s %s" % (label, st), first[st] or "")
    nq = sum(1 for e in exp if e["tag"] == "Q")
    return dict(nq=nq, nwin=len(exp),
                top1=len({e["top1"] for e in exp}),
                knn=sum(1 for e in exp if e["knn"] is not None),
                override=sum(1 for e in exp if e["final"] and e["final"][0] >= LEARNED_BASE),
                reject=sum(1 for e in exp if e["final"] and e["final"][0] == -1),
                mlp_ok=sum(1 for e in exp if e["final"] and 0 <= e["final"][0] < LEARNED_BASE))


def run(cmd, timeout=900):
    """Run a command. Args: cmd: argv list; timeout: seconds. Returns: CompletedProcess with text."""
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)


def export_model(m, mdir, tools):
    """Create model m with the real exporter. Args: m: model number; mdir: output dir; tools: tools dir.
    Returns: (path of gesture_model.h, reseeds, conf_shift). A net the exporter refuses (exit 3)
    is replaced by the next reseed; any other failure raises."""
    os.makedirs(mdir, exist_ok=True)
    r = Rng(0xCA1B0000 + m)
    calib = np.array([features_ref.features_extract(gen_base(r)) for _ in range(400)], dtype=np.int16)
    np.save(os.path.join(mdir, "calib.npy"), calib)
    exp = os.path.join(tools, "export_model.py")
    p = run([sys.executable, exp, "norm", "--features", os.path.join(mdir, "calib.npy"),
             "--out", os.path.join(mdir, "norm.json")])
    if p.returncode != 0:
        raise RuntimeError("export_model norm failed (%d): %s" % (p.returncode, p.stderr))
    reseeds, attempt, shift = 0, 0, 6
    while True:
        rng = np.random.default_rng(1000 * m + attempt)
        # a net "trained on x8 / K": x8 in [-127, 127], K = 127
        net = dict(W1=rng.normal(0, 0.6, (16, 60)), b1=rng.normal(0, 0.3, 16),
                   W2=rng.normal(0, 1.0, (9, 16)), b2=rng.normal(0, 0.3, 9), K=127.0)
        np.savez(os.path.join(mdir, "net.npz"), **net)
        hdr = os.path.join(mdir, "gesture_model.h")
        for pass_no in (0, 1):
            p = run([sys.executable, exp, "header", "--weights", os.path.join(mdir, "net.npz"),
                     "--norm", os.path.join(mdir, "norm.json"), "--calib", os.path.join(mdir, "calib.npy"),
                     "--conf-shift", str(shift), "--out", hdr])
            if p.returncode != 0:
                break
            if pass_no == 0:    # choose GM_CONF_SHIFT so the median calibration confidence is ~64..127
                mod = infer_ref.load_header(hdr)
                marg = sorted(infer_ref.forward(list(map(int, f)), mod)["margin"] for f in calib)
                shift = max(0, min(24, marg[len(marg) // 2].bit_length() - 7))
        if p.returncode == 0:
            return hdr, reseeds, shift
        if p.returncode != 3:
            raise RuntimeError("export_model header failed (%d): %s" % (p.returncode, p.stderr))
        reseeds += 1
        attempt += 1
        if attempt > 50:
            raise RuntimeError("exporter refused 50 random nets in a row: " + p.stderr)


def build(kind, mdir, out, seed, nper):
    """Compile test_e2e.c with the module sources for host or sim16.
    Args: kind: 'host' or 'avr'; mdir: dir holding gesture_model.h; out: output file; seed, nper:
    compile-time values (sim16 only). Returns: (ok, compiler messages)."""
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
    ap.add_argument("--models", type=int, default=3)
    ap.add_argument("--nper-host", type=int, default=300)
    ap.add_argument("--nper-sim", type=int, default=15)
    a = ap.parse_args()
    tools = os.environ.get("TOOLS_DIR", os.path.join(HERE, "..", "..", "..", "tools"))
    cov = dict(nq=0, nwin=0, knn=0, override=0, reject=0, mlp_ok=0)
    total_reseeds = 0
    for m in range(1, a.models + 1):
        mdir = os.path.join(a.build, "m%d" % m)
        hdr, reseeds, shift = export_model(m, mdir, tools)
        total_reseeds += reseeds
        mod = infer_ref.load_header(hdr)
        print("model m%d: exporter reseeds %d, GM_CONF_SHIFT %d, hash 0x%08X" % (
            m, reseeds, shift, mod["GM_MODEL_HASH"]))
        for kind, nper in (("host", a.nper_host), ("avr", a.nper_sim)):
            label = "m%d/%s" % (m, "host" if kind == "host" else "sim16")
            seed = (0xC0FFEE if kind == "host" else 0x5151) + 97 * m + a.seed
            exe = os.path.join(mdir, "e2e_" + kind + (".elf" if kind == "avr" else ""))
            ok, msg = build(kind, mdir, exe, seed, nper)
            if not report(ok, "%s build" % label, "" if ok else "\n" + msg):
                continue
            exp, rts_exp = expected(mod, seed, nper)
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
            c = compare(label, exp, rts_exp, p.stdout)
            report(p.returncode == 0, "%s c-side checks" % label, "exit %d" % p.returncode)
            print("  %s: %d windows (%d queries), %.1fs, top1 classes seen %d, knn results %d, "
                  "overrides %d, rejects %d" % (label, c["nwin"], c["nq"], dt, c["top1"], c["knn"],
                                                c["override"], c["reject"]))
            for k in cov:
                cov[k] += c[k]
    print("coverage: %s; exporter reseeds %d" % (cov, total_reseeds))
    report(cov["override"] > 0 and cov["reject"] > 0 and cov["mlp_ok"] > 0 and cov["knn"] > 0,
           "coverage non-vacuous (k-NN overrides, rejects and plain MLP results all occur)")
    print("e2e suite %s" % ("PASS" if not FAILS else "FAIL"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
