# [AI-GENERATED: Claude Code]
"""SPIKE S3-1 evaluator. SYNTHETIC, UNVERIFIED: every number below comes from invented data.

Reads the output of glue.c (host runs and the sim16 run), the ground truth of make_stream.py and the
model header, then:
  1. FAILS if the host and sim16 outputs of the short stream differ;
  2. FAILS if any window's C result (top1, margin, k-NN result, id, conf) differs from the Python
     reference (tools/features_ref.py + tools/infer_ref.py), replaying the learn events;
  3. prints per-class detection, latency, onset position, accuracy, false windows and lost gestures.
There is no pass/fail threshold on accuracy (spike).
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "..", "..", "..", "..", "tools")
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(HERE, "..", "trigger"))
import features_ref  # noqa: E402
import infer_ref  # noqa: E402
import trigger_ref  # noqa: E402

NAMES = ["none", "swipe_r", "swipe_l", "raise", "push_dn", "circ_cw", "circ_ccw", "twist", "thrust"]
STREAM_OF = {"main": "main", "big": "big", "stallw": "stall", "tight": "tight", "stall0": "stall", "stall1": "stall", "stall2": "stall",
             "short": "short"}


def parse(path):
    """Parse a glue output file. Args: path. Returns: list of passes, each dict(W=[...], ev=[...], S=str)."""
    passes = []
    cur = None
    for line in open(path):
        f = line.split()
        if not f:
            continue
        if f[0] == "R":
            cur = {"W": [], "ev": [], "S": None}
            passes.append(cur)
        elif f[0] == "W":
            v = [int(x) for x in f[1:]]
            w = dict(zip("start trig ready rel top1 margin id conf kid d1 d2 ck rad".split(), v))
            cur["W"].append(w)
            cur["ev"].append(("W", w))
        elif f[0] in ("A", "E", "G", "O", "L"):
            cur["ev"].append((f[0], [int(x) for x in f[1:]]))
        elif f[0] == "S":
            cur["S"] = {f[i]: int(f[i + 1]) for i in range(1, len(f) - 1, 2)}
    return passes


def python_check(passes, x, model):
    """Replay every window through the Python reference. Args: passes; x (int16 [N,3]); model.
    Returns: (n_windows, n_mismatch, n_contaminated, first_mismatch_text)."""
    n = bad = contaminated = bad_gap = 0
    first = ""
    for ps in passes:
        store = {}
        last_x8 = None
        gaps = [e[1][0] for e in ps["ev"] if e[0] == "G"]
        for kind, v in ps["ev"]:
            if kind == "L":
                store.setdefault(v[1], []).append(list(last_x8))
                continue
            if kind != "W":
                continue
            w = v
            n += 1
            win = x[w["start"]:w["start"] + 150]
            spans = any(w["start"] < g <= w["start"] + 149 for g in gaps)
            if spans:
                contaminated += 1
            feat = features_ref.features_extract([[int(a) for a in r] for r in win])
            r = infer_ref.forward(feat, model)
            last_x8 = r["x8"]
            kn = infer_ref.knn_query(r["x8"], store)
            gid, conf = infer_ref.classify_decide(r["top1"], r["margin"], model["GM_CONF_SHIFT"], kn,
                                                  model["GM_DEFAULT_REJECT"])
            if kn is None:
                kt = (-1, 0, 0, 0, 0)
            else:
                kt = (kn["kid"], kn["d1"], kn["d2"] or 0, kn["c_k"], kn["radius"])
            ct = (w["top1"], w["margin"], w["id"], w["conf"], w["kid"], w["d1"], w["d2"], w["ck"], w["rad"])
            pt = (r["top1"], r["margin"], gid, conf) + kt
            if ct != pt and spans:
                bad_gap += 1      # expected: the C window holds a gap that the contiguous Python window does not
            elif ct != pt:
                bad += 1
                if not first:
                    first = "window@%d C=%s Py=%s" % (w["start"], ct, pt)
    return n, bad, contaminated, first, bad_gap


def match(passes_p, gt):
    """Match the windows of one pass to the ground truth.

    Returns: dict with per-gesture result list (hit window or None, status) and false windows list.
    """
    ws = passes_p["W"]
    arms = sorted(e[1][0] for e in passes_p["ev"] if e[0] == "A")
    g_res = []
    used = set()
    lost = [(e[1][0] - e[1][1], e[1][0] - 1) for e in passes_p["ev"] if e[0] == "G"]
    for g in gt["gestures"]:
        hit = None
        for i, w in enumerate(ws):
            if i in used:
                continue
            if g["onset"] - 5 <= w["trig"] <= g["onset"] + 40:
                hit = i
                used.add(i)
                break
        status = "hit"
        if hit is None:
            status = "missed"
            if any(a <= g["onset"] + 135 and b >= g["onset"] - 15 for a, b in lost):
                status = "gap"       # samples of its window were lost in a FIFO overrun
            for w in ws:
                if status == "gap":
                    break   # onset inside a lock interval: trigger .. next re-arm (or end of stream)
                nxt = [a for a in arms if a > w["trig"]]
                end = nxt[0] if nxt else gt["n"]
                if w["trig"] < g["onset"] <= end:
                    status = "locked"
                    break
        g_res.append((g, hit, status))
    false = []
    for i, w in enumerate(ws):
        if i in used:
            continue
        cat = "idle"
        for e in gt["events"]:
            if e["start"] - 2 <= w["trig"] <= e["end"] + 40:
                cat = e["type"]
                break
        for g in gt["gestures"]:
            if g["onset"] + 41 <= w["trig"] <= g["onset"] + 200:
                cat = "post-gesture"
                break
        false.append((w, cat))
    return g_res, false


def pct(a, b):
    """Percentage string. Args: a, b ints. Returns: str."""
    return "%3d%%" % (round(100.0 * a / b) if b else 0)


def med(v, q=50):
    """Percentile of a list. Args: v; q. Returns: int or None."""
    return int(np.percentile(v, q)) if v else None


def report_run(name, passes, gt):
    """Print the per-class table of pass 0 and the k-NN delta of pass 1 for one run. Returns: dict summary."""
    print("\n--- run %s  (stream %s, N=%d samples = %.0f s; SYNTHETIC, UNVERIFIED) ---"
          % (name, STREAM_OF[name], gt["n"], gt["n"] / 100.0))
    g0, f0 = match(passes[0], gt)
    S0 = passes[0]["S"]
    print("pass 0 (no templates): windows=%d  early=%d  overruns=%d dropped=%d gaps=%d unflagged=%d  "
          "drains=%d more=%d maxdrain=%d fifolost=%d"
          % (S0["windows"], S0["early"], S0["overruns"], S0["dropped"], S0["gaps"], S0["unflagged"],
             S0["drains"], S0["more"], S0["maxdrain"], S0["fifolost"]))
    print("%-9s %4s %4s %5s | %5s %5s %5s | %6s %5s | %4s %4s %4s" %
          ("class", "n", "hit", "det", "latMd", "latP90", "latMx", "onsPos", "acc", "lock", "gap", "miss"))
    tot = dict(n=0, hit=0, ok=0, lock=0, miss=0, gap=0)
    for c in range(1, 9):
        rows = [r for r in g0 if r[0]["label"] == c]
        if not rows:
            continue
        hits = [r for r in rows if r[2] == "hit"]
        lat = [passes[0]["W"][r[1]]["trig"] - r[0]["onset"] for r in hits]
        pos = [r[0]["onset"] - passes[0]["W"][r[1]]["start"] for r in hits]
        ok = sum(1 for r in hits if passes[0]["W"][r[1]]["id"] == c)
        lock = sum(1 for r in rows if r[2] == "locked")
        miss = sum(1 for r in rows if r[2] == "missed")
        gap = sum(1 for r in rows if r[2] == "gap")
        print("%-9s %4d %4d %s | %5s %6s %5s | %6s %s | %4d %4d %4d" %
              (NAMES[c], len(rows), len(hits), pct(len(hits), len(rows)), med(lat), med(lat, 90),
               max(lat) if lat else None, med(pos), pct(ok, len(hits)), lock, gap, miss))
        tot["n"] += len(rows); tot["hit"] += len(hits); tot["ok"] += ok; tot["lock"] += lock; tot["miss"] += miss
        tot["gap"] += gap
    print("%-9s %4d %4d %s | %5s %6s %5s | %6s %s | %4d %4d %4d" %
          ("ALL", tot["n"], tot["hit"], pct(tot["hit"], tot["n"]), "", "", "", "", pct(tot["ok"], tot["hit"]),
           tot["lock"], tot["gap"], tot["miss"]))
    hw = [passes[0]["W"][r[1]] for r in g0 if r[2] == "hit"]
    if hw:
        cf = [w["conf"] for w in hw]
        print("MLP conf of hit windows: median %d, P90 %d, max %d; share >= GESTURE_OVERRIDE_CONF (192): %s; "
              "share < default reject: %s" % (med(cf), med(cf, 90), max(cf), pct(sum(1 for c in cf if c >= 192), len(cf)),
                                              pct(sum(1 for c in cf if c < 7), len(cf))))
    cats = {}
    ids = {"id0": 0, "reject": 0, "gest": 0}
    for w, cat in f0:
        cats[cat] = cats.get(cat, 0) + 1
        ids["id0" if w["id"] == 0 else ("reject" if w["id"] < 0 else "gest")] += 1
    idle_s = (gt["n"] - sum(150 for _ in gt["gestures"])) / 100.0
    print("false windows (pass 0): %d total  by place %s  by decision %s  (%.1f per idle minute)"
          % (len(f0), dict(sorted(cats.items())), ids, 60.0 * len(f0) / max(idle_s, 1.0)))
    # accuracy of hit windows versus where the onset lands in the window
    hits_all = [(r[0]["onset"] - passes[0]["W"][r[1]]["start"], passes[0]["W"][r[1]]["id"] == r[0]["label"])
                for r in g0 if r[2] == "hit"]
    if len(hits_all) >= 40 and not gt["tight"]:
        parts = []
        for lo, hi, nm in ((-99, 4, "<5"), (5, 9, "5-9"), (10, 14, "10-14"), (15, 99, ">=15")):
            b = [ok for pos, ok in hits_all if lo <= pos <= hi]
            parts.append("onset at %s: %d windows acc %s" % (nm, len(b), pct(sum(b), len(b))))
        print("accuracy by onset position in the window (training windows have it at 12..18): " + "; ".join(parts))
    # integer-path confusion of hit windows
    wrong = {}
    for r in g0:
        if r[2] == "hit":
            w = passes[0]["W"][r[1]]
            if w["id"] != r[0]["label"]:
                k = "%s->%s" % (NAMES[r[0]["label"]], NAMES[w["id"]] if w["id"] >= 0 else "REJECT")
                wrong[k] = wrong.get(k, 0) + 1
    if wrong:
        print("misclassified hit windows: %s" % dict(sorted(wrong.items())))
    # pass 1: k-NN
    out = {"hit": tot["hit"], "n": tot["n"], "ok0": tot["ok"], "lock": tot["lock"], "miss": tot["miss"],
           "false": len(f0), "windows": S0["windows"], "gap": tot["gap"],
           "corrupt": 0}
    if len(passes) > 1:
        g1, f1 = match(passes[1], gt)
        L = {}
        for kind, v in passes[1]["ev"]:
            if kind == "L":
                L[v[1]] = v[0]       # class id -> trigger index of the template window
        cid_of = {p["label"]: p["class_id"] for p in gt["learn"]}
        ok1 = hit1 = 0
        lines = []
        for p in gt["learn"]:
            rows = [r for r in g1 if r[0]["label"] == p["label"] and r[2] == "hit"
                    and passes[1]["W"][r[1]]["trig"] != L.get(p["class_id"], -1)]
            own = sum(1 for r in rows if passes[1]["W"][r[1]]["id"] == p["class_id"])
            mlp = sum(1 for r in rows if passes[1]["W"][r[1]]["id"] == p["label"])
            r0 = [r for r in g0 if r[0]["label"] == p["label"] and r[2] == "hit"
                 ]
            ok0 = sum(1 for r in r0 if passes[0]["W"][r[1]]["id"] == p["label"])
            lines.append("class %d (%s) -> learned id %d: later hit windows %d: id=%d %d, id=%d(MLP) %d, other %d; "
                         "pass 0 MLP accuracy on all its hits %d/%d (template=%s)"
                         % (p["label"], NAMES[p["label"]], p["class_id"], len(rows), p["class_id"], own,
                            p["label"], mlp, len(rows) - own - mlp, ok0, len(r0),
                            "yes" if p["class_id"] in L else "NO (not learned)"))
        for r in g1:
            if r[2] == "hit":
                w = passes[1]["W"][r[1]]
                hit1 += 1
                if w["id"] == r[0]["label"] or w["id"] == cid_of.get(r[0]["label"], -99):
                    ok1 += 1
        fo = sum(1 for r in g1 if r[2] == "hit" and r[0]["label"] not in cid_of
                 and passes[1]["W"][r[1]]["id"] >= 9)
        ff = sum(1 for w, _ in f1 if w["id"] >= 9)
        print("pass 1 (k-NN, %d templates learned from the first occurrence of 2 classes): hit accuracy %s (%d/%d), "
              "false override on other classes' hits %d, false windows classified as learned %d / %d"
              % (len(L), pct(ok1, hit1), ok1, hit1, fo, ff, len(f1)))
        for ln in lines:
            print("   " + ln)
        same, other = [], []
        for r in g1:
            if r[2] == "hit":
                w = passes[1]["W"][r[1]]
                if w["kid"] < 0 or w["trig"] in L.values():
                    continue
                (same if r[0]["label"] == next((p["label"] for p in gt["learn"] if p["class_id"] == w["kid"]), -1)
                 else other).append(w["d1"])
        if same or other:
            print("   k-NN d1 to nearest template (L1 over x8): nearest is the SAME class %d windows: median %s max %s; "
                  "nearest is another class %d windows: median %s min %s; default radius 1200" %
                  (len(same), med(same), max(same) if same else None, len(other), med(other),
                   min(other) if other else None))
        out["ok1"] = ok1
        out["hit1"] = hit1
    return out


def main(argv=None):
    """CLI. Args: --build DIR --runs "a b c" --sim NAME. Returns: exit code (1 on host/sim16 or Python mismatch)."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True)
    ap.add_argument("--runs", required=True)
    ap.add_argument("--sim", required=True)
    a = ap.parse_args(argv)
    fail = False
    model = infer_ref.load_header(os.path.join(a.build, "model", "gesture_model.h"))
    print("INTEGRATION SPIKE evaluation. ALL NUMBERS SYNTHETIC, UNVERIFIED (invented data, no real wand).")
    print("model %s: hash 0x%08X" % (os.path.join(a.build, "model"), model["GM_MODEL_HASH"]))
    # 1. host == sim16
    def clean(p):
        """Read an output file without the SIM16_EXIT line (run_sim16.sh strips it, the host build prints it)."""
        return "".join(l for l in open(p) if not l.startswith("SIM16_EXIT"))
    h = clean(os.path.join(a.build, "out_%s_host.txt" % a.sim))
    s = clean(os.path.join(a.build, "out_%s_sim16.txt" % a.sim))
    if h.strip() == s.strip() and "DONE" in h:
        print("host == sim16: IDENTICAL (%d lines, stream '%s')" % (len(h.strip().splitlines()), a.sim))
    else:
        fail = True
        hl, sl = h.strip().splitlines(), s.strip().splitlines()
        for i in range(max(len(hl), len(sl))):
            if i >= len(hl) or i >= len(sl) or hl[i] != sl[i]:
                print("FAIL host/sim16 differ at line %d: host=%r sim16=%r" % (i + 1, hl[i] if i < len(hl) else None,
                                                                              sl[i] if i < len(sl) else None))
                break
    # 2. Python vs C, and metrics
    summ = {}
    for name in a.runs.split():
        gt = json.load(open(os.path.join(a.build, STREAM_OF[name] + ".json")))
        x = np.load(os.path.join(a.build, STREAM_OF[name] + ".npy"))
        passes = parse(os.path.join(a.build, "out_%s_host.txt" % name))
        if len(passes) != 2 or any(p["S"] is None for p in passes):
            print("FAIL run %s: incomplete output" % name)
            fail = True
            continue
        n, bad, cont, first, bad_gap = python_check(passes, x, model)
        print("python == C, run %-6s: %d windows, %d mismatches, %d windows spanning a gap (of which %d differ, "
              "expected: corrupt window)  %s" % (name, n, bad, cont, bad_gap, first))
        if bad or (cont and name != "stall0"):
            fail = True      # a window spanning a gap is a known defect only of the API_glue.md overrun order (stall0)
        summ[name] = (report_run(name, passes, gt), passes, gt, cont)
        summ[name][0]["corrupt"] = cont
    if "stallw" in summ and "stall1" in summ:
        same = open(os.path.join(a.build, "out_stallw_host.txt")).read() == \
            open(os.path.join(a.build, "out_stall1_host.txt")).read()
        print("FIFO_SRC full-FIFO encoding WRAP (FSS = 0 + OVRN) vs SATURATE (FSS = 31): output %s"
              % ("IDENTICAL" if same else "DIFFERENT"))
        if not same:
            fail = True
    # offline trigger comparison on main
    if "main" in summ:
        gt = summ["main"][2]
        x = np.load(os.path.join(a.build, "main.npy"))
        offs, _ = trigger_ref.run([tuple(int(v) for v in r) for r in x], None, 250, 135)
        ws = [w["trig"] for w in summ["main"][1][0]["W"]]
        print("\noffline trigger_ref.run(rel_delay=135) on main: %d triggers; integrated glue: %d windows; "
              "identical trigger indices: %d" % (len(offs), len(ws), len(set(offs) & set(ws))))
    # release latency
    for name in ("main", "big", "tight"):
        if name in summ:
            ws = summ[name][1][0]["W"]
            d = [w["rel"] - w["ready"] for w in ws]
            arms = sorted(e[1][0] for e in summ[name][1][0]["ev"] if e[0] == "A")
            dead = []
            for w in ws:
                nx = [t for t in arms if t > w["rel"]]
                if nx:
                    dead.append(nx[0] - w["trig"])
            print("run %-5s: READY -> release delay (samples) median %s max %s; trigger -> re-armed (deaf) median %s max %s"
                  % (name, med(d), max(d) if d else None, med(dead), max(dead) if dead else None))
    # summary table
    print("\n=== SUMMARY (SYNTHETIC, UNVERIFIED; no thresholds, spike) ===")
    print("%-7s %5s %5s %5s %6s %5s %5s %5s %6s %8s %s" %
          ("run", "gest", "hit", "det", "accC", "lock", "gap", "miss", "false", "windows", "gap-windows"))
    for name, (o, _, _, _) in summ.items():
        print("%-7s %5d %5d %s %s %5d %5d %5d %6d %8d %6d" % (name, o["n"], o["hit"], pct(o["hit"], o["n"]),
                                                              pct(o["ok0"], o["hit"]), o["lock"], o["gap"], o["miss"],
                                                              o["false"], o["windows"], o["corrupt"]))
    print("run: main = 1-4 s idle, tight = 0.2-0.6 s idle + rotated windows (accC unreliable), stall0/1/2 = main-style "
          "stream with 3 stalls of 45 samples and 40-sample busy classify, overrun order 0 (API_glue.md), "
          "1 (at the first delivered sample), 2 (1 + trigger_resync); short = the sim16 stream")
    if fail:
        print("FAIL: host/sim16 or Python mismatch (see above)")
        return 1
    print("host == sim16 and Python == C: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
