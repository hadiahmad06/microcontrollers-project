#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""Offline trigger cut: turns a continuous recorder stream (recorder.py --samples) into a labelled window dataset.

WORKING ASSUMPTION: open_questions Q1, Q2, not decided (briefs/W2-6_spec.md V2).
Runs tools/trigger_ref.Trigger over the stream, cuts samples[t-15 : t+135] per trigger (trigger_ref.cut_windows
geometry) and labels each window from the time-based marks.

Trigger driving mirrors trigger_ref.run() exactly (run() takes only one resync_at, we need many):
  - before feeding sample i: if i is a resync index (a chunk gap start or an OVR index) -> trigger.resync() and
    forget the pending release;
  - feed sample i; if it fires, record i and remember it as the pending trigger;
  - after sample i: if a trigger is pending and i - trig_at >= rel_delay (135) -> trigger.release() (effective at
    t + rel_delay + 1) and clear the pending trigger.
A window whose span (t-15 .. t+134) contains a resync index strictly inside it is dropped (discontinuous data).

Usage:
  python3 tools/cut_stream.py --stream S.npz --out DS.npz [--thr-mg 250] [--window-after-mark SEC] [--none-gap SEC]
  python3 tools/cut_stream.py --selftest
"""
import argparse
import json
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trigger_ref  # noqa: E402
from gesture_labels import LABELS  # noqa: E402
import recorder  # noqa: E402

ODR = 100            # samples per second (C0)
REL_DELAY = 135


def find_triggers(samples, resync_idx, thr_mg=trigger_ref.DEFAULT_MG, rel_delay=REL_DELAY):
    """Run the reference trigger over a stream with any number of re-sync points.

    Args:
        samples: int array [M,3]. resync_idx: iterable of sample indices before which resync() is called.
        thr_mg: threshold in mg. rel_delay: release() after sample (trigger + rel_delay).
    Returns:
        list of trigger sample indices.
    """
    t = trigger_ref.Trigger(None)
    t.set_threshold_mg(thr_mg)
    rs = set(int(i) for i in resync_idx)
    trigs, trig_at = [], -1
    for i, s in enumerate(np.asarray(samples, dtype=np.int64).tolist()):
        if i in rs:
            t.resync()
            trig_at = -1
        if t.feed(s):
            trigs.append(i)
            trig_at = i
        if trig_at >= 0 and rel_delay >= 0 and i - trig_at >= rel_delay:
            t.release()
            trig_at = -1
    return trigs


def label_window(t, marks, after, none_gap):
    """Label a trigger sample from the marks.

    Args:
        t: trigger sample index. marks: sorted list of (sample, label). after: samples after a mark in which a
        trigger belongs to it. none_gap: samples around a trigger that must hold no mark for it to be 'none'.
    Returns:
        (label, mark index or -1); label None = ambiguous (drop).
    """
    best = -1
    for k, (ms, _) in enumerate(marks):
        if ms <= t:
            best = k
        else:
            break
    if best >= 0 and t - marks[best][0] <= after:
        return int(marks[best][1]), best
    if all(abs(ms - t) > none_gap for ms, _ in marks):
        return 0, -1
    return None, -1


def cut(stream, thr_mg=250, after_s=2.0, none_gap_s=1.0):
    """Cut and label the windows of a stream.

    Args:
        stream: dict with samples [M,3], chunk_gaps [G,2], ovr [K], marks [L,2].
        thr_mg: trigger threshold. after_s: --window-after-mark. none_gap_s: --none-gap.
    Returns:
        dict: windows, labels, trig_sample, and report numbers (per_mark window counts, n_trig, dropped_gap,
        dropped_ambiguous, dropped_edge).
    """
    smp = np.asarray(stream["samples"])
    resync = sorted(set([int(g[0]) for g in np.asarray(stream["chunk_gaps"]).reshape(-1, 2)] +
                        [int(o) for o in np.asarray(stream["ovr"]).reshape(-1)]))
    marks = sorted((int(a), int(b)) for a, b in np.asarray(stream["marks"]).reshape(-1, 2))
    trigs = find_triggers(smp, resync, thr_mg)
    wins, labs, ts = [], [], []
    per_mark = [0] * len(marks)
    dropped_gap = dropped_amb = dropped_edge = 0
    for t in trigs:
        if t - trigger_ref.PRE < 0 or t + trigger_ref.POST > len(smp):
            dropped_edge += 1
            continue
        if any(t - trigger_ref.PRE < g < t + trigger_ref.POST for g in resync):
            dropped_gap += 1
            continue
        lab, k = label_window(t, marks, int(round(after_s * ODR)), int(round(none_gap_s * ODR)))
        if lab is None:
            dropped_amb += 1
            continue
        if k >= 0:
            per_mark[k] += 1
        wins.append(smp[t - trigger_ref.PRE:t + trigger_ref.POST])
        labs.append(lab)
        ts.append(t)
    return {"windows": np.array(wins, dtype=np.int16).reshape(-1, 150, 3), "labels": np.array(labs, dtype=np.uint8),
            "trig_sample": np.array(ts, dtype=np.int32), "marks": marks, "per_mark": per_mark, "n_trig": len(trigs),
            "dropped_gap": dropped_gap, "dropped_ambiguous": dropped_amb, "dropped_edge": dropped_edge}


def report(res):
    """Print the per-label table (marks, windows, marks with no window, marks with two or more) and drops."""
    print("%-12s %6s %8s %12s %12s" % ("label", "marks", "windows", "missed", "multi(>=2)"))
    for lab in range(len(LABELS)):
        idx = [k for k, (_, l) in enumerate(res["marks"]) if l == lab]
        nw = int((res["labels"] == lab).sum())
        if not idx and not nw:
            continue
        miss = sum(1 for k in idx if res["per_mark"][k] == 0)
        multi = sum(1 for k in idx if res["per_mark"][k] >= 2)
        print("%-12s %6d %8d %12d %12d" % (LABELS[lab], len(idx), nw, miss, multi))
    print("triggers %d, windows %d; dropped: %d across a gap/OVR, %d ambiguous, %d at the stream edges" % (
        res["n_trig"], len(res["labels"]), res["dropped_gap"], res["dropped_ambiguous"], res["dropped_edge"]))


def save(path, stream, res, src_name):
    """Write the training-format dataset plus trig_sample (atomic, via recorder.write_npz).

    Args:
        path: output .npz. stream: loaded stream dict. res: result of cut(). src_name: stream file name for meta.
    """
    n = len(res["labels"])
    arrays = {"windows": res["windows"], "labels": res["labels"],
              "subject": np.full(n, int(stream["subject"]), np.uint8),
              "session": np.full(n, int(stream["session"]), np.uint16),
              "window_id": (np.arange(n) & 0xFFFF).astype(np.uint16), "overruns": np.zeros(n, np.uint16),
              "model_hash": np.zeros(n, np.uint32), "dev_flags": np.zeros(n, np.uint8),
              "dev_class": np.full(n, -1, np.int8), "dev_conf": np.zeros(n, np.uint8), "events": np.zeros(n, np.uint8),
              "trig_sample": res["trig_sample"]}
    meta = {"tool": "cut_stream.py", "version": 1, "source": src_name, "windows": n,
            "dropped": {"gap": res["dropped_gap"], "ambiguous": res["dropped_ambiguous"], "edge": res["dropped_edge"]},
            "label_names": list(LABELS)}
    recorder.write_npz(path, arrays, int(stream["synthetic"]), meta)


def load_stream(path):
    """Load a recorder stream file; raises SystemExit(2) with a message if it is not one."""
    try:
        z = np.load(path)
        st = {k: z[k] for k in ("samples", "chunk_gaps", "ovr", "marks")}
        st["synthetic"] = int(z["synthetic"])
        st["subject"] = int(z["subject"]) if "subject" in z.files else 0
        st["session"] = int(z["session"]) if "session" in z.files else 0
    except (OSError, ValueError, KeyError) as e:
        print("error: cannot read stream %s: %s" % (path, e), file=sys.stderr)
        sys.exit(2)
    if st["samples"].ndim != 2 or st["samples"].shape[1] != 3:
        print("error: %s: samples must be [M,3]" % path, file=sys.stderr)
        sys.exit(2)
    return st


def _selftest():
    """Check the cut on a synthetic stream with bursts, a chunk gap and an OVR index; returns failure strings."""
    fails = []

    def check(c, msg):
        if not c:
            fails.append(msg)

    rng = np.random.default_rng(3)
    M = 3000
    smp = np.zeros((M, 3), np.int32)
    smp[:, 2] = 512                                           # 1 g on Z at +-4 g (C0: 512 counts/g... resting)
    smp += rng.integers(-2, 3, size=smp.shape)
    bursts = [300, 700, 1100, 1700, 2300]
    for b in bursts:                                          # a 60-sample shake
        smp[b:b + 60, 0] += (400 * np.sin(np.arange(60) * 0.5)).astype(np.int32)
    smp = smp.astype(np.int16)
    marks = [[290, 1], [690, 2], [1090, 3], [1690, 4], [2290, 5]]
    base = {"samples": smp, "chunk_gaps": np.zeros((0, 2), np.int32), "ovr": np.zeros(0, np.int32),
            "marks": np.array(marks, np.int32), "synthetic": 1, "subject": 0, "session": 0}
    r = cut(base)
    check(r["labels"].tolist() == [1, 2, 3, 4, 5], "labels %s" % r["labels"].tolist())
    check(all(0 <= t - b <= 40 for t, b in zip(r["trig_sample"].tolist(), bursts)), "trigger offsets")
    check(all(np.array_equal(w, smp[t - 15:t + 135]) for w, t in zip(r["windows"], r["trig_sample"].tolist())), "window cut")
    check(r["per_mark"] == [1] * 5, "per_mark %s" % r["per_mark"])
    # equals trigger_ref.run with one resync point
    tr, _ = trigger_ref.run([tuple(x) for x in smp.astype(int).tolist()], thr_mg=250, resync_at=1000)
    me = find_triggers(smp, [1000])
    check(tr == me, "find_triggers != trigger_ref.run: %s vs %s" % (me, tr))
    # a gap inside the window of burst 1700 drops it; the other bursts survive
    g = dict(base, chunk_gaps=np.array([[1760, 2]], np.int32))
    r = cut(g)
    check(4 not in r["labels"].tolist() and r["dropped_gap"] >= 1, "gap drop %s" % r["labels"].tolist())
    check(r["labels"].tolist()[:3] == [1, 2, 3], "labels after gap")
    # OVR resync before the first sample of a burst: trigger needs a new warm-up (32 samples) but still fires later
    o = dict(base, ovr=np.array([2200], np.int32))
    r = cut(o)
    check(5 in r["labels"].tolist(), "ovr burst still detected")
    # ambiguous: no mark near but a mark 1.5 s before -> dropped; far from every mark -> none
    a = dict(base, marks=np.array([[700 - 250, 1]], np.int32))
    r = cut(a)
    check(0 in r["labels"].tolist() and 1 not in r["labels"].tolist(), "none far from marks %s" % r["labels"].tolist())
    a = dict(base, marks=np.array([[300 + 80, 1]], np.int32))   # mark just after the trigger of burst 1: ambiguous
    r = cut(a)
    check(r["dropped_ambiguous"] >= 1, "ambiguous dropped")
    # CLI round trip
    with tempfile.TemporaryDirectory() as t:
        sp, op = os.path.join(t, "s.npz"), os.path.join(t, "d.npz")
        np.savez(sp, samples=smp, chunk_gaps=base["chunk_gaps"], ovr=base["ovr"], marks=base["marks"],
                 synthetic=np.uint8(1), subject=np.uint8(2), session=np.uint16(3))
        rc = main(["--stream", sp, "--out", op])
        z = np.load(op)
        check(rc == 0 and z["labels"].tolist() == [1, 2, 3, 4, 5] and int(z["synthetic"]) == 1 and
              z["trig_sample"].dtype == np.int32 and int(z["subject"][0]) == 2 and int(z["session"][0]) == 3,
              "cli")
        check(json.loads(str(z["meta"]))["source"] == "s.npz", "meta source")
        check(main(["--stream", sp, "--out", op]) == 0, "existing out overwritten")
        check(main(["--stream", sp, "--out", sp]) == 2 and os.path.getsize(sp) > 0, "out == stream refused")
    return fails


def main(argv=None):
    """CLI entry point. Returns the exit code (0 ok, 2 bad arguments or files)."""
    ap = argparse.ArgumentParser(description="Cut a continuous recorder stream into labelled windows")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--stream")
    ap.add_argument("--out")
    ap.add_argument("--thr-mg", type=int, default=250)
    ap.add_argument("--window-after-mark", type=float, default=2.0, help="seconds after a mark a trigger belongs to it")
    ap.add_argument("--none-gap", type=float, default=1.0, help="seconds around a trigger that must hold no mark for 'none'")
    a = ap.parse_args(argv)
    if a.selftest:
        fails = _selftest()
        if fails:
            print("cut_stream selftest FAIL: " + "; ".join(fails))
            return 1
        print("cut_stream selftest PASS")
        return 0
    if not a.stream or not a.out:
        print("error: need --stream and --out", file=sys.stderr)
        return 2
    if not 0 < a.thr_mg <= 65535 or a.window_after_mark <= 0 or a.none_gap < 0:
        print("error: bad --thr-mg / --window-after-mark / --none-gap", file=sys.stderr)
        return 2
    if os.path.exists(a.out) and os.path.samefile(a.out, a.stream):
        print("error: --out must not be the --stream input", file=sys.stderr)
        return 2                               # an existing different --out is overwritten (derived data; temp + os.replace)
    st = load_stream(a.stream)
    res = cut(st, a.thr_mg, a.window_after_mark, a.none_gap)
    report(res)
    save(a.out, st, res, os.path.basename(a.stream))
    if st["synthetic"]:
        print("SYNTHETIC: output is marked synthetic", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
