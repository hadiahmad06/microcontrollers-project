#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""Dataset tool: inspect, merge, prune, relabel and export training .npz files (ticket W2-4).

WORKING ASSUMPTION: open_questions Q1 (C2 as proposed), not decided.
Format: tools/README.md "Dataset format" (windows int16 [N,150,3], labels uint8 [N], optional subject/session,
optional scalar synthetic) plus the recorder's extra per-window arrays.

Usage:
  python3 tools/dataset_tool.py info DS.npz [DS2.npz ...]
  python3 tools/dataset_tool.py merge --out OUT.npz DS1.npz DS2.npz [...] [--allow-dup-session]
  python3 tools/dataset_tool.py drop --out OUT.npz DS.npz --index 3,7,12
  python3 tools/dataset_tool.py relabel --out OUT.npz DS.npz --index 3,7 --label swipe_left
  python3 tools/dataset_tool.py csv --out OUT.csv DS.npz
  python3 tools/dataset_tool.py --selftest
Exit codes: 0 ok, 1 selftest failure, 2 bad arguments or invalid file.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gesture_labels import LABELS, parse_label  # noqa: E402

N_CLASSES = len(LABELS)
MIN_PER_LABEL = 20


class Fatal(Exception):
    """Error that exits with code 2."""


def peak_l1(w):
    """Peak L1 deviation of a window [150,3] from its first sample (max over samples of sum over axes of |s - s[0]|)."""
    a = np.asarray(w, dtype=np.int32)
    return int(np.abs(a - a[0]).sum(axis=1).max())


def load(path):
    """Load and validate a dataset file.

    Args:
        path: .npz path.
    Returns:
        dict name -> ndarray (all arrays of the file).
    Raises:
        Fatal: naming the file and the failed check.
    """
    try:
        z = np.load(path)
        d = {k: z[k] for k in z.files}
    except (OSError, ValueError) as e:
        raise Fatal("%s: cannot read: %s" % (path, e))
    for k in ("windows", "labels"):
        if k not in d:
            raise Fatal("%s: missing array '%s'" % (path, k))
    w, y = d["windows"], d["labels"]
    if w.dtype != np.int16 or w.ndim != 3 or w.shape[1:] != (150, 3):
        raise Fatal("%s: windows must be int16 [N,150,3], got %s %s" % (path, w.dtype, w.shape))
    n = len(w)
    if y.ndim != 1 or len(y) != n or y.dtype.kind not in "iu":
        raise Fatal("%s: labels must be an integer vector of length N=%d" % (path, n))
    if n and (int(w.min()) < -2048 or int(w.max()) > 2047):
        raise Fatal("%s: windows has values outside [-2048, 2047]" % path)
    if n and (int(y.min()) < 0 or int(y.max()) >= N_CLASSES):
        raise Fatal("%s: labels must be in 0..%d" % (path, N_CLASSES - 1))
    for k in ("subject", "session"):
        if k in d and (d[k].ndim != 1 or len(d[k]) != n):
            raise Fatal("%s: %s must have length N=%d" % (path, k, n))
    return d


def per_window_keys(d):
    """Names of the arrays that have one entry per window (first axis N, ndim >= 1)."""
    n = len(d["windows"])
    return [k for k, v in d.items() if v.ndim >= 1 and len(v) == n]


def save(path, d):
    """Write a dataset through a temp file in the same directory and os.replace; keeps array dtypes."""
    dirn = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".ds_", suffix=".tmp", dir=dirn)
    try:
        with os.fdopen(fd, "wb") as f:
            np.savez(f, **d)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def check_out(out, inputs):
    """Refuse an output path that is one of the inputs. Raises Fatal."""
    if any(os.path.realpath(out) == os.path.realpath(i) for i in inputs):
        raise Fatal("--out %s is an input file; refusing to overwrite it" % out)


def _describe(name, w, y, d):
    """Print the info block of one dataset (or the total); returns the list of warning lines."""
    n = len(y)
    counts = np.bincount(y.astype(np.int64), minlength=N_CLASSES) if n else np.zeros(N_CLASSES, int)
    print("%s: N=%d%s" % (name, n, "  SYNTHETIC" if d.get("synthetic") else ""))
    print("  labels: " + ", ".join("%s=%d" % (LABELS[i], counts[i]) for i in range(N_CLASSES)))
    if "subject" in d:
        print("  subjects: %s" % sorted(set(int(v) for v in d["subject"])))
    if "session" in d:
        print("  sessions: %s" % sorted(set(int(v) for v in d["session"])))
    med = []
    for i in range(N_CLASSES):
        sel = w[y == i]
        if len(sel):
            med.append("%s=%d" % (LABELS[i], int(np.median([peak_l1(s) for s in sel]))))
    print("  median peak L1 deviation: " + (", ".join(med) or "-"))
    for i in range(N_CLASSES):
        if counts[i] < MIN_PER_LABEL:
            print("  WARNING: label %s has only %d windows (< %d)" % (LABELS[i], counts[i], MIN_PER_LABEL))


def cmd_info(a):
    """info: print per-file and total statistics."""
    ws, ys = [], []
    syn = 0
    for p in a.files:
        d = load(p)
        d["synthetic"] = int(d["synthetic"]) if "synthetic" in d else 0
        syn = max(syn, d["synthetic"])
        _describe(p, d["windows"], d["labels"], d)
        ws.append(d["windows"])
        ys.append(d["labels"])
    if len(a.files) > 1:
        _describe("TOTAL", np.concatenate(ws), np.concatenate(ys), {"synthetic": syn})
    return 0


def cmd_merge(a):
    """merge: concatenate datasets in argument order."""
    if len(a.files) < 2:
        raise Fatal("merge needs at least two input files")
    check_out(a.out, a.files)
    ds = [load(p) for p in a.files]
    seen = {}
    for p, d in zip(a.files, ds):
        if "subject" in d and "session" in d:
            for pair in set(zip(d["subject"].tolist(), d["session"].tolist())):
                if pair in seen and seen[pair] != p and not a.allow_dup_session:
                    raise Fatal("(subject, session) = %s occurs in both %s and %s; use --allow-dup-session to merge anyway"
                                % (pair, seen[pair], p))
                seen.setdefault(pair, p)
    keys = [k for k in per_window_keys(ds[0]) if all(k in d and k in per_window_keys(d) for d in ds)]
    for k in sorted(set(sum((per_window_keys(d) for d in ds), [])) - set(keys)):
        print("warning: dropping array '%s' (not present in all inputs)" % k, file=sys.stderr)
    out = {k: np.concatenate([d[k] for d in ds]) for k in keys}
    out["synthetic"] = np.uint8(max(int(d["synthetic"]) if "synthetic" in d else 0 for d in ds))
    out["meta"] = np.array(json.dumps({"tool": "dataset_tool.py", "merged_from": [
        {"file": os.path.basename(p), "n": len(d["windows"])} for p, d in zip(a.files, ds)]}))
    save(a.out, out)
    print("merged %d files -> %s (N=%d)" % (len(ds), a.out, len(out["windows"])))
    return 0


def parse_index(s, n):
    """Parse a comma list of window indices; raises Fatal if malformed or outside 0..n-1."""
    try:
        idx = [int(t) for t in s.split(",") if t.strip() != ""]
    except ValueError:
        raise Fatal("--index must be a comma list of integers, got %r" % s)
    if not idx:
        raise Fatal("--index is empty")
    bad = [i for i in idx if i < 0 or i >= n]
    if bad:
        raise Fatal("--index out of range (N=%d): %s" % (n, bad))
    return sorted(set(idx))


def cmd_drop(a):
    """drop: remove the given windows."""
    check_out(a.out, [a.file])
    d = load(a.file)
    n = len(d["windows"])
    idx = parse_index(a.index, n)
    keep = np.ones(n, bool)
    keep[idx] = False
    keys = set(per_window_keys(d))
    save(a.out, {k: (v[keep] if k in keys else v) for k, v in d.items()})
    print("dropped %d windows -> %s (N=%d)" % (len(idx), a.out, int(keep.sum())))
    return 0


def cmd_relabel(a):
    """relabel: set the label of the given windows."""
    check_out(a.out, [a.file])
    try:
        lab = parse_label(a.label)
    except ValueError as e:
        raise Fatal(str(e))
    d = load(a.file)
    idx = parse_index(a.index, len(d["windows"]))
    y = d["labels"].copy()
    y[idx] = lab
    d["labels"] = y
    save(a.out, d)
    print("relabelled %d windows to %s -> %s" % (len(idx), LABELS[lab], a.out))
    return 0


def cmd_csv(a):
    """csv: export one row per sample (window,label,label_name,subject,session,t,x,y,z)."""
    check_out(a.out, [a.file])
    d = load(a.file)
    n = len(d["windows"])
    sub = d["subject"] if "subject" in d else np.zeros(n, int)
    ses = d["session"] if "session" in d else np.zeros(n, int)
    dirn = os.path.dirname(os.path.abspath(a.out))
    fd, tmp = tempfile.mkstemp(prefix=".csv_", suffix=".tmp", dir=dirn)
    try:
        with os.fdopen(fd, "w", newline="") as f:
            f.write("window,label,label_name,subject,session,t,x,y,z\n")
            for i in range(n):
                lab = int(d["labels"][i])
                head = "%d,%d,%s,%d,%d" % (i, lab, LABELS[lab], sub[i], ses[i])
                for t, (x, y, z) in enumerate(d["windows"][i].tolist()):
                    f.write("%s,%d,%d,%d,%d\n" % (head, t, x, y, z))
        os.replace(tmp, a.out)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    print("wrote %s (%d rows)" % (a.out, n * 150))
    return 0


def _selftest():
    """Exercise every command on small files in a temp dir; returns failure strings."""
    fails = []

    def check(c, msg):
        if not c:
            fails.append(msg)

    me = os.path.abspath(__file__)
    rng = np.random.default_rng(3)
    with tempfile.TemporaryDirectory() as t:
        def P(n):
            return os.path.join(t, n)

        def run(*args):
            return subprocess.run([sys.executable, me] + list(args), capture_output=True, text=True)

        def mk(name, n, sub, ses, extra=True, syn=0):
            d = {"windows": rng.integers(-2048, 2048, size=(n, 150, 3)).astype(np.int16),
                 "labels": (np.arange(n) % 9).astype(np.uint8), "subject": np.full(n, sub, np.uint8),
                 "session": np.full(n, ses, np.uint16), "synthetic": np.uint8(syn)}
            if extra:
                d["window_id"] = np.arange(n, dtype=np.uint16)
            np.savez(P(name), **d)
            return d
        a = mk("a.npz", 18, 0, 0)
        b = mk("b.npz", 9, 0, 1, extra=False, syn=1)
        r = run("info", P("a.npz"), P("b.npz"))
        check(r.returncode == 0 and "SYNTHETIC" in r.stdout and "WARNING" in r.stdout and "TOTAL" in r.stdout, "info")
        r = run("merge", "--out", P("m.npz"), P("a.npz"), P("b.npz"))
        check(r.returncode == 0 and "window_id" in r.stderr, "merge rc/warn %s" % r.stderr)
        m = np.load(P("m.npz"))
        check(m["windows"].shape == (27, 150, 3) and m["windows"].dtype == np.int16 and int(m["synthetic"]) == 1
              and "window_id" not in m.files and m["session"].dtype == np.uint16, "merge content")
        check(json.loads(str(m["meta"]))["merged_from"][1]["n"] == 9, "merge meta")
        mk("c.npz", 9, 0, 1)
        check(run("merge", "--out", P("x.npz"), P("b.npz"), P("c.npz")).returncode == 2, "dup session refused")
        check(run("merge", "--out", P("x.npz"), "--allow-dup-session", P("b.npz"), P("c.npz")).returncode == 0, "dup allowed")
        check(run("merge", "--out", P("a.npz"), P("a.npz"), P("b.npz")).returncode == 2, "out == input")
        r = run("drop", "--out", P("d.npz"), P("a.npz"), "--index", "3,7,12")
        dd = np.load(P("d.npz"))
        check(r.returncode == 0 and len(dd["labels"]) == 15 and np.array_equal(dd["windows"], np.delete(a["windows"], [3, 7, 12], 0))
              and len(dd["window_id"]) == 15, "drop")
        check(run("drop", "--out", P("e.npz"), P("a.npz"), "--index", "18").returncode == 2, "drop range")
        r = run("relabel", "--out", P("r.npz"), P("a.npz"), "--index", "3,7", "--label", "swipe-left")
        rr = np.load(P("r.npz"))
        check(r.returncode == 0 and rr["labels"][3] == 2 and rr["labels"][7] == 2 and rr["labels"][4] == a["labels"][4], "relabel")
        r = run("csv", "--out", P("o.csv"), P("b.npz"))
        lines = open(P("o.csv")).read().splitlines()
        check(r.returncode == 0 and len(lines) == 1 + 9 * 150 and lines[0] == "window,label,label_name,subject,session,t,x,y,z"
              and lines[1].startswith("0,0,none,0,1,0,"), "csv")
        bad = dict(windows=np.full((2, 150, 3), 3000, np.int16), labels=np.zeros(2, np.uint8))
        np.savez(P("bad.npz"), **bad)
        r = run("info", P("bad.npz"))
        check(r.returncode == 2 and "bad.npz" in r.stderr, "validation")
    return fails


def main(argv=None):
    """CLI entry point. Returns the exit code."""
    ap = argparse.ArgumentParser(description="Inspect and edit training datasets")
    ap.add_argument("--selftest", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("info")
    s.add_argument("files", nargs="+")
    s = sub.add_parser("merge")
    s.add_argument("--out", required=True)
    s.add_argument("--allow-dup-session", action="store_true")
    s.add_argument("files", nargs="+")
    s = sub.add_parser("drop")
    s.add_argument("--out", required=True)
    s.add_argument("--index", required=True)
    s.add_argument("file")
    s = sub.add_parser("relabel")
    s.add_argument("--out", required=True)
    s.add_argument("--index", required=True)
    s.add_argument("--label", required=True)
    s.add_argument("file")
    s = sub.add_parser("csv")
    s.add_argument("--out", required=True)
    s.add_argument("file")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if a.selftest:
        fails = _selftest()
        if fails:
            print("dataset_tool selftest FAIL: " + "; ".join(fails))
            return 1
        print("dataset_tool selftest PASS")
        return 0
    if not a.cmd:
        print("error: give a command (info, merge, drop, relabel, csv) or --selftest", file=sys.stderr)
        return 2
    try:
        return {"info": cmd_info, "merge": cmd_merge, "drop": cmd_drop, "relabel": cmd_relabel, "csv": cmd_csv}[a.cmd](a)
    except Fatal as e:
        print("error: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
