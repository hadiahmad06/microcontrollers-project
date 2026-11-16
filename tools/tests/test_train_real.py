#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""Tests for W2-5 (train.py on real recordings, evaluate_model.py), written from the spec only.

Run: python3 tools/tests/test_train_real.py [name-substring ...]
Prints PASS/FAIL per test, then ALL PASS (exit 0) or a failure count (exit 1).
Environment: ORIG_REF (git ref holding the pre-change tools/, default HEAD) for the byte-identity test;
TEST_TRACE=1 prints tracebacks.
Uses small SYNTHETIC data (tools/synth_dataset.py) and few epochs.
WORKING ASSUMPTION: the report.json / report.md layout of evaluate_model.py is unspecified, so numbers are
searched for anywhere in the report (as a fraction or a percent), not by key.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import features_ref  # noqa: E402
import infer_ref  # noqa: E402
import synth_dataset  # noqa: E402

TMP = tempfile.mkdtemp(prefix="test_train_real_")
PER_CLASS = 8
FAST = ["--epochs", "4", "--eval-every", "2"]
_cache = {}


class Skip(Exception):
    """Soft check that could not be exercised (reported as PASS with a note)."""


def sh(args, cwd=None):
    """Run a command. Args: argv list, cwd. Returns (rc, stdout, stderr)."""
    p = subprocess.run(args, capture_output=True, text=True, cwd=cwd)
    return p.returncode, p.stdout, p.stderr


def make_ds(name, seed, per_class=PER_CLASS, drop=(), sess_mod=None, subj_mod=None, extra=None, synthetic=True,
            windows=None):
    """Write a synthetic dataset .npz in TMP and return its path.

    Args: name (file stem); seed; per_class; drop (keys to remove); sess_mod / subj_mod (modulus applied to
    session / subject); extra (dict of arrays added); synthetic (keep the marker); windows (replacement array).
    """
    d = synth_dataset.make_dataset(per_class, seed)
    if sess_mod:
        d["session"] = (d["session"] % sess_mod).astype(np.uint16)
    if subj_mod:
        d["subject"] = (d["subject"] % subj_mod).astype(np.uint8)
    if windows is not None:
        d["windows"] = windows
    if not synthetic:
        d.pop("synthetic")
    for k in drop:
        d.pop(k, None)
    d.update(extra or {})
    p = os.path.join(TMP, name + ".npz")
    np.savez(p, **d)
    return p


def train(tag, data, flags=(), seed=1, script=None, expect=0):
    """Run train.py into TMP/out_<tag> (cached per tag). Args: tag, data (list of --data args), flags, seed,
    script (alternative train.py), expect (exit code). Returns (out_dir, stdout, stderr)."""
    if tag in _cache:
        return _cache[tag]
    out = os.path.join(TMP, "out_" + tag)
    cmd = [sys.executable, script or os.path.join(TOOLS, "train.py")] + list(data) + [
        "--out-dir", out, "--seed", str(seed)] + FAST + list(flags)
    rc, so, se = sh(cmd)
    if rc != expect:
        raise AssertionError("train.py %s exited %d (want %d): %s" % (tag, rc, expect, (se or so)[-400:]))
    _cache[tag] = (out, so, se)
    return _cache[tag]


def D(*paths):
    """Format paths as repeated --data arguments."""
    r = []
    for p in paths:
        r += ["--data", p]
    return r


def rj(out):
    """Load DIR/report.json."""
    with open(os.path.join(out, "report.json")) as f:
        return json.load(f)


def rmd(out):
    """Read DIR/report.md."""
    with open(os.path.join(out, "report.md")) as f:
        return f.read()


def fileb(out, name):
    """Bytes of DIR/name."""
    with open(os.path.join(out, name), "rb") as f:
        return f.read()


def host_eval(header, windows):
    """Independent integer-path recomputation (features_ref + infer_ref). Returns (model, preds, confs)."""
    m = infer_ref.load_header(header)
    pr, cf = [], []
    for w in windows:
        r = infer_ref.forward(features_ref.features_extract(w.tolist()), m)
        pr.append(int(r["top1"]))
        cf.append(int(r["conf"]))
    return m, np.array(pr), np.array(cf)


def json_leaves(o):
    """All numeric leaves of a JSON object."""
    if isinstance(o, bool):
        return []
    if isinstance(o, (int, float)):
        return [float(o)]
    if isinstance(o, dict):
        return [x for v in o.values() for x in json_leaves(v)]
    if isinstance(o, list):
        return [x for v in o for x in json_leaves(v)]
    return []


def has_number(blob, v):
    """True when blob (markdown and/or JSON text) holds v as a fraction (+-0.0006) or a percent (+-0.006)."""
    nums = [float(t) for t in re.findall(r"-?\d+(?:\.\d+)?", blob)]
    try:
        nums += json_leaves(json.loads(blob))
    except ValueError:
        pass
    return any(abs(n - v) <= 0.0006 or abs(n - 100 * v) <= 0.006 for n in nums)


def find_matrices(o):
    """All 9x9 nested lists inside a JSON object, as numpy arrays."""
    r = []
    if isinstance(o, list):
        if len(o) == 9 and all(isinstance(x, list) and len(x) == 9 for x in o):
            r.append(np.array(o))
        for x in o:
            r += find_matrices(x)
    elif isinstance(o, dict):
        for x in o.values():
            r += find_matrices(x)
    return r


def wilson(k, n, z=1.96):
    """Wilson score interval (lo, hi) for k of n."""
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return c - h, c + h


# ------------------------------------------------------------------------------------------ R1
def t_multi_data_forms():
    """R1: repeated --data and comma list give the same result; report lists files with N."""
    a, b = make_ds("a1", 1), make_ds("b1", 2)
    o1, _, _ = train("rep", D(a, b))
    o2, _, _ = train("comma", ["--data", a + "," + b])
    n = 9 * PER_CLASS * 2
    assert rj(o1)["n_total"] == n and rj(o2)["n_total"] == n, "n_total"
    assert fileb(o1, "gesture_model.h") == fileb(o2, "gesture_model.h"), "repeat vs comma headers differ"
    md = rmd(o1)
    assert "a1.npz" in md and "b1.npz" in md, "report lists input files"
    assert str(9 * PER_CLASS) in md, "report lists N per file"


def t_validate_each_file():
    """R1: every file is validated, in any position; missing file exits 2."""
    a = make_ds("a2", 1)
    z = np.load(a)
    bad_shape = os.path.join(TMP, "badshape.npz")
    np.savez(bad_shape, windows=z["windows"][:, :100], labels=z["labels"])
    bad_lab = os.path.join(TMP, "badlab.npz")
    np.savez(bad_lab, windows=z["windows"], labels=z["labels"] + 20)
    nokey = os.path.join(TMP, "nokey.npz")
    np.savez(nokey, labels=z["labels"])
    big = os.path.join(TMP, "bigval.npz")
    w = z["windows"].copy()
    w[0, 0, 0] = 3000
    np.savez(big, windows=w, labels=z["labels"])
    for i, bad in enumerate([bad_shape, bad_lab, nokey, big]):
        for pos, order in enumerate(([a, bad], [bad, a])):
            rc, so, se = sh([sys.executable, os.path.join(TOOLS, "train.py")] + D(*order) +
                            ["--out-dir", os.path.join(TMP, "v%d" % i)] + FAST)
            assert rc == 2, "bad file %s at position %d: exit %d" % (os.path.basename(bad), pos, rc)
    rc, _, _ = sh([sys.executable, os.path.join(TOOLS, "train.py"), "--data", a + ",/nonexistent/x.npz",
                   "--out-dir", os.path.join(TMP, "vmiss")] + FAST)
    assert rc == 2, "missing file in comma list: exit %d" % rc


def t_drop_subject_session():
    """R1: subject/session dropped with a warning when one file lacks them."""
    a = make_ds("a3", 1)
    b = make_ds("b3", 2, drop=("subject", "session"))
    out, so, se = train("drop", D(a, b))
    assert "warn" in (se + so).lower(), "no warning about dropped subject/session"
    assert rj(out)["group"] not in ("subject", "session"), "grouping must not use dropped keys: %r" % rj(out)["group"]
    assert rj(out)["n_total"] == 2 * 9 * PER_CLASS
    c = make_ds("c3", 3, drop=("session",))
    out2, _, se2 = train("drop2", D(a, c))
    assert "warn" in se2.lower(), "no warning when one file lacks session"
    assert rj(out2)["group"] == "subject", "subject must survive when both files have it"


def t_session_grouping_by_file_and_value():
    """R1: session group = (file, value); colliding numbers across files never merge (forced construction)."""
    a = make_ds("a4", 1, per_class=10, sess_mod=2, drop=("subject",))
    b = make_ds("b4", 2, per_class=10, sess_mod=2, drop=("subject",))
    out, _, _ = train("sess", D(a, b), ["--group", "session", "--val-frac", "0.25", "--test-frac", "0.25"])
    na = len(np.load(a)["labels"])
    sess = np.concatenate([np.load(a)["session"], np.load(b)["session"]]).astype(int)
    fid = (np.arange(len(sess)) >= na).astype(int)
    sp = np.load(os.path.join(out, "split.npz"))
    grp = {k: set(zip(fid[sp[k]].tolist(), sess[sp[k]].tolist())) for k in ("train", "val", "test")}
    assert len(sp["test"]) > 0 and len(sp["train"]) > 0 and len(sp["val"]) > 0, "empty split"
    assert not (grp["test"] & grp["train"]), "test shares a (file, session) group with train"
    assert not (grp["val"] & grp["train"]), "val shares a (file, session) group with train"
    assert not (grp["test"] & grp["val"]), "test shares a group with val"
    assert rj(out)["group"] == "session", "group %r" % rj(out)["group"]
    # 4 (file, value) groups in 3 sets over only 2 session values: by pigeonhole a value lands in two sets
    vals = {k: set(v for _, v in g) for k, g in grp.items()}
    assert (vals["test"] & vals["train"]) or (vals["val"] & vals["train"]) or (vals["test"] & vals["val"]), \
        "no session value shared across sets: groups were merged by value alone"


def t_subject_grouping_by_value():
    """R1: subject grouping uses the value alone across files."""
    a = make_ds("a5", 1, per_class=10, subj_mod=4, drop=("session",))
    b = make_ds("b5", 2, per_class=10, subj_mod=4, drop=("session",))
    out, _, _ = train("subj", D(a, b), ["--group", "subject", "--val-frac", "0.25", "--test-frac", "0.25"])
    sub = np.concatenate([np.load(a)["subject"], np.load(b)["subject"]]).astype(int)
    sp = np.load(os.path.join(out, "split.npz"))
    g = {k: set(sub[sp[k]].tolist()) for k in ("train", "val", "test")}
    assert not (g["test"] & g["train"]) and not (g["val"] & g["train"]) and not (g["test"] & g["val"]), \
        "a subject value appears in two sets across files: %r" % g
    assert rj(out)["group"] == "subject"


def t_synthetic_flag_propagation():
    """R1: synthetic = any file synthetic."""
    a = make_ds("a6", 1, synthetic=True)
    b = make_ds("b6", 2, synthetic=False)
    out, _, _ = train("synth_any", D(a, b))
    assert "SYNTHETIC" in rmd(out), "any synthetic input must mark the report SYNTHETIC"
    out, _, _ = train("synth_any_rev", D(b, a))
    assert "SYNTHETIC" in rmd(out), "synthetic as second file must mark SYNTHETIC"
    c, d = make_ds("c6", 3, synthetic=False), make_ds("d6", 4, synthetic=False)
    out, _, _ = train("synth_none", D(c, d))
    assert "SYNTHETIC" not in rmd(out), "no synthetic input: report must not say SYNTHETIC"


def t_extra_arrays_and_meta():
    """R1: extra per-window arrays and a 0-d unicode meta are accepted and ignored."""
    n = 9 * PER_CLASS
    extra = {"window_id": np.arange(n, dtype=np.uint32), "overruns": np.zeros(n, np.uint16),
             "model_hash": np.full(n, 0xDEADBEEF, np.uint32), "dev_flags": np.ones(n, np.uint8),
             "dev_class": np.zeros(n, np.uint8), "dev_conf": np.zeros(n, np.uint8),
             "events": np.zeros((n, 2), np.int32), "meta": np.array('{"who": "x", "note": "café"}')}
    a = make_ds("a7", 1, extra=extra)
    assert np.load(a)["meta"].shape == ()
    b = make_ds("b7", 2)
    out, _, _ = train("extra", D(a, b))
    assert rj(out)["n_total"] == 2 * n, "n_total %r" % rj(out)["n_total"]
    out1, _, _ = train("extra_single", D(a))
    assert rj(out1)["n_total"] == n


def orig_tools():
    """Copy the pre-change tools/*.py (git show REF:tools/...) into a temp dir. Returns the dir."""
    ref = os.environ.get("ORIG_REF", "HEAD")
    d = os.path.join(TMP, "orig_tools")
    if os.path.isdir(d):
        return d
    os.makedirs(d)
    rc, so, se = sh(["git", "ls-tree", "--name-only", ref, "."], cwd=TOOLS)
    assert rc == 0, "git ls-tree failed: " + se
    for f in so.split():
        if f.endswith(".py"):
            rc, src, se = sh(["git", "show", "%s:./%s" % (ref, f)], cwd=TOOLS)
            assert rc == 0, se
            with open(os.path.join(d, os.path.basename(f)), "w") as fh:
                fh.write(src)
    return d


def t_default_output_byte_identical():
    """Spec preamble: default run is byte-identical to the original train.py (header, norm, split, features)."""
    a = make_ds("a8", 5, per_class=10)
    d = orig_tools()
    for seed in (1, 3):
        o_new, _, _ = train("id_new%d" % seed, D(a), seed=seed)
        o_old, _, _ = train("id_old%d" % seed, D(a), seed=seed, script=os.path.join(d, "train.py"))
        for f in ("gesture_model.h", "norm.json", "features.npy"):
            assert fileb(o_new, f) == fileb(o_old, f), "%s differs from original train.py (seed %d)" % (f, seed)
        sn, so_ = np.load(os.path.join(o_new, "split.npz")), np.load(os.path.join(o_old, "split.npz"))
        for k in ("train", "val", "test"):
            assert np.array_equal(sn[k], so_[k]), "split %s differs" % k
    # a stratified (--group none) run too
    o_new, _, _ = train("id_new_none", D(a), ["--group", "none"])
    o_old, _, _ = train("id_old_none", D(a), ["--group", "none"], script=os.path.join(d, "train.py"))
    assert fileb(o_new, "gesture_model.h") == fileb(o_old, "gesture_model.h"), "--group none header differs"


def t_selftest_still_passes():
    """Spec preamble: train.py --selftest still passes."""
    rc, so, se = sh([sys.executable, os.path.join(TOOLS, "train.py"), "--selftest"])
    assert rc == 0 and "train selftest PASS" in so, "train --selftest: rc %d %s" % (rc, (so + se)[-200:])


# ------------------------------------------------------------------------------------------ R2
def eval_setup():
    """Train one model for the evaluate tests. Returns the header path."""
    assert os.path.exists(os.path.join(TOOLS, "evaluate_model.py")), "tools/evaluate_model.py does not exist"
    a = make_ds("ev_train", 11, per_class=12)
    out, _, _ = train("ev_model", D(a), seed=2)
    return os.path.join(out, "gesture_model.h")


def run_eval(header, datas, tag, extra=()):
    """Run evaluate_model.py with --out-dir. Returns (rc, stdout, stderr, out_dir)."""
    out = os.path.join(TMP, "ev_" + tag)
    rc, so, se = sh([sys.executable, os.path.join(TOOLS, "evaluate_model.py"), "--header", header] + D(*datas)
                    + ["--out-dir", out] + list(extra))
    return rc, so, se, out


def report_blob(out):
    """Returns (report.md text, report.json text)."""
    with open(os.path.join(out, "report.md")) as f:
        md = f.read()
    with open(os.path.join(out, "report.json")) as f:
        js = f.read()
    return md, js


def t_eval_selftest():
    """R2: --selftest prints 'evaluate_model selftest PASS'."""
    rc, so, se = sh([sys.executable, os.path.join(TOOLS, "evaluate_model.py"), "--selftest"])
    assert rc == 0 and "evaluate_model selftest PASS" in so, "rc %d: %s" % (rc, (so + se)[-200:])


def t_eval_accuracy_and_confusion():
    """R2: accuracy, Wilson interval, confusion matrix, per-class recall, default rejection rate."""
    h = eval_setup()
    e = make_ds("ev1", 21, per_class=10)
    rc, so, se, out = run_eval(h, [e], "acc")
    assert rc == 0, "rc %d %s" % (rc, se[-300:])
    z = np.load(e)
    y = z["labels"].astype(int)
    m, pred, conf = host_eval(h, z["windows"])
    acc = float((pred == y).mean())
    md, js = report_blob(out)
    blob = md + "\n" + js
    assert has_number(blob, acc), "accuracy %.4f not in report" % acc
    lo, hi = wilson(int((pred == y).sum()), len(y))
    assert has_number(blob, float(lo)) and has_number(blob, float(hi)), "Wilson interval (%.4f, %.4f) missing" % (lo, hi)
    cm = np.zeros((9, 9), int)
    for t, p in zip(y, pred):
        cm[t, p] += 1
    mats = find_matrices(json.loads(js))
    assert mats, "no 9x9 confusion matrix in report.json"
    assert any(int(x.sum()) == len(y) for x in mats), "confusion matrix does not sum to N"
    assert any(np.array_equal(x, cm) or np.array_equal(x, cm.T) for x in mats), "confusion matrix differs from recomputation"
    assert "recall" in md.lower(), "per-class recall missing"
    for c in range(9):
        if (y == c).any():
            assert has_number(blob, float((pred[y == c] == c).mean())), "recall of class %d" % c
    g = y != 0
    rej = float(((conf < m["GM_DEFAULT_REJECT"]) & g).sum() / g.sum())
    assert has_number(blob, rej), "rejection rate %.4f (default min_conf %d) missing" % (rej, m["GM_DEFAULT_REJECT"])


def t_eval_min_conf_and_rejection_definition():
    """R2: --min-conf override; rejection rate counts label != 0 only; accuracy after rejection."""
    h = eval_setup()
    e = make_ds("ev2", 22, per_class=10)
    z = np.load(e)
    y = z["labels"].astype(int)
    m, pred, conf = host_eval(h, z["windows"])
    g = y != 0
    mc = max(1, int(np.median(conf)))
    rate_gest = float(((conf < mc) & g).sum() / g.sum())
    rc, so, se, out = run_eval(h, [e], "mc", ["--min-conf", str(mc)])
    assert rc == 0, se[-300:]
    md, js = report_blob(out)
    assert has_number(md + js, rate_gest), "rejection rate on label != 0 (%.4f) missing for min_conf %d" % (rate_gest, mc)
    acc_acc = (conf >= mc)
    if acc_acc.any():
        a1 = float((pred[acc_acc] == y[acc_acc]).mean())              # ruling R2-a: correct / ALL accepted (all labels)
        assert has_number(md + js, a1), "accuracy after rejection (correct/accepted, all labels) %.4f missing" % a1
    rc, so, se, out0 = run_eval(h, [e], "mc0", ["--min-conf", "0"])
    assert rc == 0
    md0, js0 = report_blob(out0)
    assert has_number(md0 + js0, 0.0), "min_conf 0 must give rejection rate 0"
    rc, so, se, out255 = run_eval(h, [e], "mc255", ["--min-conf", "255"])
    assert rc == 0
    rate255 = float(((conf < 255) & g).sum() / g.sum())
    md2, js2 = report_blob(out255)
    assert has_number(md2 + js2, rate255), "min_conf 255 rejection rate %.4f" % rate255


def t_eval_stdout_and_multi_data():
    """R2: without --out-dir markdown goes to stdout; several --data are pooled."""
    h = eval_setup()
    e1, e2 = make_ds("ev3a", 23, per_class=6), make_ds("ev3b", 24, per_class=6)
    rc, so, se = sh([sys.executable, os.path.join(TOOLS, "evaluate_model.py"), "--header", h] + D(e1, e2))
    assert rc == 0, se[-300:]
    assert "accuracy" in so.lower(), "markdown on stdout when no --out-dir"
    y = np.concatenate([np.load(e1)["labels"], np.load(e2)["labels"]]).astype(int)
    w = np.concatenate([np.load(e1)["windows"], np.load(e2)["windows"]])
    _, pred, _ = host_eval(h, w)
    assert has_number(so, float((pred == y).mean())), "combined accuracy of two --data files"
    assert str(len(y)) in so, "N of combined data"


def t_eval_per_subject():
    """R2: per-subject section present iff subject exists."""
    h = eval_setup()
    e = make_ds("ev4", 25, per_class=10)
    rc, so, se, out = run_eval(h, [e], "subj")
    assert rc == 0, se[-300:]
    md, js = report_blob(out)
    z = np.load(e)
    y, s = z["labels"].astype(int), z["subject"].astype(int)
    _, pred, _ = host_eval(h, z["windows"])
    assert "accuracy per subject" in md.lower(), "per-subject section missing"
    for v in np.unique(s):
        assert has_number(md + js, float((pred[s == v] == y[s == v]).mean())), "subject %d accuracy" % v
    e2 = make_ds("ev4n", 25, per_class=10, drop=("subject", "session"))
    rc, so, se, out2 = run_eval(h, [e2], "nosubj")
    assert rc == 0, se[-300:]
    md2, js2 = report_blob(out2)
    assert "accuracy per subject" not in md2.lower(), "per-subject section present without subject"
    assert not json.loads(js2).get("per_subject"), "per_subject values present without subject"
    assert json.loads(js).get("per_subject"), "per_subject missing in report.json with subject"


def t_eval_device_agreement():
    """R2: dev_class agreement only for dev_flags bit 0 and equal model_hash; else 'different model'."""
    h = eval_setup()
    m = infer_ref.load_header(h)
    z = synth_dataset.make_dataset(10, 26)
    _, pred, _ = host_eval(h, z["windows"])
    n = len(pred)
    flags = np.zeros(n, np.uint8)
    flags[: n // 2] = 1
    dev_class = pred.astype(np.uint8).copy()
    dev_class[n // 2:] = (dev_class[n // 2:] + 1) % 9      # windows without bit 0 must be ignored
    same = {"dev_flags": flags, "dev_class": dev_class, "dev_conf": np.full(n, 100, np.uint8),
            "model_hash": np.full(n, m["GM_MODEL_HASH"], np.uint32)}
    e = make_ds("ev5", 26, per_class=10, extra=same)
    rc, so, se, out = run_eval(h, [e], "dev_same")
    assert rc == 0, se[-300:]
    md, js = report_blob(out)
    assert "different model" not in md.lower(), "same model_hash must not say 'different model'"
    assert "agree" in md.lower(), "device agreement missing"
    assert has_number(md + js, 1.0), "agreement should be 100 %"
    diff = dict(same, model_hash=np.full(n, (m["GM_MODEL_HASH"] ^ 0x1) & 0xFFFFFFFF, np.uint32))
    e2 = make_ds("ev5d", 26, per_class=10, extra=diff)
    rc, so, se, out2 = run_eval(h, [e2], "dev_diff")
    assert rc == 0, se[-300:]
    md2, _ = report_blob(out2)
    assert "different model" in md2.lower(), "'different model' expected when model_hash differs"


def t_eval_synthetic_marking():
    """R2: report marked SYNTHETIC iff any input is synthetic."""
    h = eval_setup()
    e = make_ds("ev6", 27, per_class=5, synthetic=True)
    e2 = make_ds("ev6n", 27, per_class=5, synthetic=False)
    rc, so, se, out = run_eval(h, [e2, e], "syn")
    assert rc == 0 and "SYNTHETIC" in report_blob(out)[0], "SYNTHETIC when any input is synthetic"
    rc, so, se, out = run_eval(h, [e2], "nosyn")
    assert rc == 0 and "SYNTHETIC" not in report_blob(out)[0], "no SYNTHETIC without synthetic input"


def t_eval_bad_input_exit2():
    """R2: exit 2 on bad header / bad data / missing files."""
    h = eval_setup()
    e = make_ds("ev7", 28, per_class=4)
    py = [sys.executable, os.path.join(TOOLS, "evaluate_model.py")]
    z = np.load(e)
    nokey = os.path.join(TMP, "ev7_nokey.npz")
    np.savez(nokey, labels=z["labels"])
    badshape = os.path.join(TMP, "ev7_shape.npz")
    np.savez(badshape, windows=z["windows"][:, :50], labels=z["labels"])
    corrupt = os.path.join(TMP, "corrupt.h")
    with open(h) as f:
        txt = f.read()
    with open(corrupt, "w") as f:
        f.write(re.sub(r"GM_MODEL_HASH\s+0x[0-9A-Fa-f]+", "GM_MODEL_HASH 0x00000001", txt))
    cases = {"missing header": py + ["--header", os.path.join(TMP, "nope.h")] + D(e),
             "bad header hash": py + ["--header", corrupt] + D(e),
             "missing data file": py + ["--header", h] + D(os.path.join(TMP, "nope.npz")),
             "no windows key": py + ["--header", h] + D(nokey),
             "bad shape": py + ["--header", h] + D(badshape),
             "one bad of two": py + ["--header", h] + D(e, nokey),
             "no --data": py + ["--header", h]}
    for name, cmd in cases.items():
        rc, so, se = sh(cmd)
        assert rc == 2, "%s: exit %d (want 2)" % (name, rc)


# ------------------------------------------------------------------------------------------ R3
def t_aug_off_by_default():
    """R3: no --augment gives the same output twice and the report does not claim augmentation."""
    a = make_ds("a9", 6, per_class=10)
    base, _, _ = train("aug_base", D(a))
    o, _, _ = train("aug_none_again", D(a))
    assert fileb(base, "gesture_model.h") == fileb(o, "gesture_model.h")
    md = rmd(base).lower()
    assert "augment" not in md or "none" in md or "off" in md or "no augment" in md, \
        "report must not claim augmentation when it is off"


def t_aug_deterministic_and_effective():
    """R3: deterministic per seed, has an effect, report states roll/gain/copies."""
    a = make_ds("a10", 6, per_class=10)
    fl = ["--augment", "roll=25,gain=15,copies=2"]
    o1, _, _ = train("aug1", D(a), fl, seed=1)
    o2, _, _ = train("aug1b", D(a), fl, seed=1)
    assert fileb(o1, "gesture_model.h") == fileb(o2, "gesture_model.h"), "same seed must give the same header"
    base, _, _ = train("aug_base", D(a))
    assert fileb(o1, "gesture_model.h") != fileb(base, "gesture_model.h"), "augmentation had no effect on the header"
    o3, _, _ = train("aug_s2", D(a), fl, seed=2)
    o4, _, _ = train("aug_s2_noaug", D(a), seed=2)
    assert fileb(o3, "gesture_model.h") != fileb(o4, "gesture_model.h")
    md = rmd(o1).lower()
    assert "augment" in md and "25" in md and "15" in md, "report must state the augmentation used (roll 25, gain 15)"
    assert "roll" in md and "gain" in md and "cop" in md, "report names roll, gain, copies"


def t_aug_val_test_untouched():
    """R3: val/test never augmented; norm from the un-augmented train set; features.npy un-augmented."""
    a = make_ds("a10", 6, per_class=10)
    base, _, _ = train("aug_base", D(a))
    aug, _, _ = train("aug1", D(a), ["--augment", "roll=25,gain=15,copies=2"], seed=1)
    sb, sa = np.load(os.path.join(base, "split.npz")), np.load(os.path.join(aug, "split.npz"))
    n = len(np.load(a)["labels"])
    assert np.array_equal(sb["val"], sa["val"]) and np.array_equal(sb["test"], sa["test"]), "val/test indices changed"
    tr = sa["train"]
    assert set(tr[tr < n].tolist()) == set(sb["train"].tolist()), "original train indices changed"
    assert not ((set(sa["val"].tolist()) | set(sa["test"].tolist())) & set(tr.tolist())), "val/test windows in train"
    fb, fa = np.load(os.path.join(base, "features.npy")), np.load(os.path.join(aug, "features.npy"))
    assert fb.shape == fa.shape == (n, 60), "features.npy must cover only un-augmented windows: %s" % (fa.shape,)
    idx = np.concatenate([sa["val"], sa["test"]])
    assert np.array_equal(fb[idx], fa[idx]), "val/test feature rows changed by augmentation"
    w = np.load(a)["windows"]
    for i in idx[:6]:
        assert fa[i].tolist() == features_ref.features_extract(w[i].tolist()), "val/test features not from raw windows"
    assert fileb(base, "norm.json") == fileb(aug, "norm.json"), "normalisation must come from the un-augmented train set"
    jb, ja = rj(base), rj(aug)
    assert jb["n_val"] == ja["n_val"] and jb["n_test"] == ja["n_test"]


def t_aug_zero_roll_zero_gain():
    """R3: roll=0,gain=0 copies change nothing but the train count; key subsets accepted."""
    a = make_ds("a12", 6, per_class=10)
    base, _, _ = train("aug_base12", D(a))
    z, _, _ = train("aug_zero", D(a), ["--augment", "roll=0,gain=0,copies=2"])
    sb, sz = np.load(os.path.join(base, "split.npz")), np.load(os.path.join(z, "split.npz"))
    assert np.array_equal(sb["val"], sz["val"]) and np.array_equal(sb["test"], sz["test"])
    assert fileb(base, "norm.json") == fileb(z, "norm.json"), "norm must not change with identity copies"
    assert fileb(base, "features.npy") == fileb(z, "features.npy")
    nb, nz = rj(base)["n_train"], rj(z)["n_train"]
    assert nz in (nb, 3 * nb), "n_train %d should be %d (originals) or %d (with copies)" % (nz, nb, 3 * nb)
    assert rj(z)["n_val"] == rj(base)["n_val"] and rj(z)["n_test"] == rj(base)["n_test"]
    for i, fl in enumerate(["roll=10", "gain=10", "copies=3", "roll=5,copies=1", "gain=5,roll=5,copies=1"]):
        train("aug_sub%d" % i, D(a), ["--augment", fl])


def t_aug_clipping_and_extremes():
    """R3: augmented values are clipped to [-2048, 2047] (else features_ref would reject them and train would fail)."""
    rng = np.random.default_rng(5)
    w = rng.choice(np.array([-2048, 2047], dtype=np.int16), size=(9 * 6, 150, 3)).astype(np.int16)
    a = make_ds("a13", 7, per_class=6, windows=w)
    out, _, _ = train("aug_clip", D(a), ["--augment", "roll=45,gain=50,copies=2"])
    infer_ref.load_header(os.path.join(out, "gesture_model.h"))
    train("aug_clip2", D(a), ["--augment", "roll=180,gain=99,copies=1"])


def t_aug_bad_values():
    """R3 (spec silent): malformed --augment must not be accepted silently (exit 1 or 2)."""
    a = make_ds("a14", 7, per_class=6)
    train("aug_ok", D(a), ["--augment", "roll=5"])      # a valid flag must work, else the exits below prove nothing
    for fl in ["roll=abc", "frob=1", "copies=-1", "gain=-5", "gain=100"]:
        rc, so, se = sh([sys.executable, os.path.join(TOOLS, "train.py")] + D(a) +
                        ["--out-dir", os.path.join(TMP, "augbad"), "--augment", fl] + FAST)
        assert rc == 2, "--augment %s: exit %d (spec silent, expected 2)" % (fl, rc)


# ------------------------------------------------------------------------------------------ R4
def t_report_contents():
    """R4: input files with N, class shares per set, per-subject test accuracy."""
    a = make_ds("a15", 9, per_class=10)
    b = make_ds("b15", 10, per_class=7)
    out, _, _ = train("rep4", D(a, b))
    md, js = rmd(out), json.dumps(rj(out))
    assert "a15.npz" in md and "b15.npz" in md and "90" in md and "63" in md, "input files with N"
    y = np.concatenate([np.load(a)["labels"], np.load(b)["labels"]]).astype(int)
    sp = np.load(os.path.join(out, "split.npz"))
    blob = md + "\n" + js
    for k in ("train", "val", "test"):
        idx = sp[k]
        if len(idx) == 0:
            continue
        for c in range(9):
            share = float((y[idx] == c).mean())
            assert has_number(blob, share), "class %d share in %s: %.4f" % (c, k, share)
    sub = np.concatenate([np.load(a)["subject"], np.load(b)["subject"]]).astype(int)
    w = np.concatenate([np.load(a)["windows"], np.load(b)["windows"]])
    te = sp["test"]
    _, pred, _ = host_eval(os.path.join(out, "gesture_model.h"), w[te])
    assert "subject" in md.lower(), "per-subject test accuracy section"
    for v in np.unique(sub[te]):
        sel = sub[te] == v
        assert has_number(blob, float((pred[sel] == y[te][sel]).mean())), "test accuracy of subject %d" % v
    c = make_ds("c15", 12, per_class=10, drop=("subject", "session"))
    out2, _, _ = train("rep4n", D(c))
    assert "c15.npz" in rmd(out2), "input file listed even for a single file"


# ------------------------------------------------------------------------------------------ W2-5TF2
def t_aug_geometry():
    """R3: roll about X (X unchanged, |(Y,Z)| preserved, angle within +-roll), via train.augment_windows."""
    import train as tr
    w = np.zeros((4, 150, 3), np.int16)
    w[:, :] = (100, 500, -300)
    aug = {"roll": 60, "gain": 0, "copies": 3}
    out, src = tr.augment_windows(w, aug, 7)
    assert out.shape == (12, 150, 3) and out.dtype == np.int16 and len(src) == 12
    assert (out[:, :, 0] == 100).all(), "X (tip axis) must be unchanged"
    r0 = np.hypot(500.0, -300.0)
    r = np.hypot(out[:, :, 1].astype(float), out[:, :, 2].astype(float))
    assert np.abs(r - r0).max() <= 1.0, "|(Y,Z)| not preserved: %.3f" % np.abs(r - r0).max()
    d = np.degrees(np.arctan2(out[:, :, 2].astype(float), out[:, :, 1].astype(float)) - np.arctan2(-300.0, 500.0))
    d = (d + 180) % 360 - 180
    assert np.abs(d).max() <= 60.0 + 0.2, "angle %.2f outside +-60" % np.abs(d).max()
    assert np.abs(d).max() > 20, "copies are not rotated (max angle %.2f)" % np.abs(d).max()
    assert out[0, 0].tolist() != out[1, 0].tolist() or out[1, 0].tolist() != out[2, 0].tolist(), "all copies identical"
    o2, _ = tr.augment_windows(w, aug, 7)
    assert np.array_equal(out, o2), "not deterministic"


def t_aug_rounding_half_away():
    """R3: exact .5 results round half away from zero (random draws stubbed to the upper bound)."""
    import train as tr

    class Stub:
        def uniform(self, lo, hi, size):
            return np.full(size, float(hi))

    w = np.zeros((1, 150, 3), np.int16)
    w[0, 0] = (1, -1, 3)
    w[0, 1] = (-3, 2047, -2048)
    w[0, 2] = (0, 1, 1)
    orig = tr.np.random.default_rng
    tr.np.random.default_rng = lambda *a, **k: Stub()
    try:
        out, _ = tr.augment_windows(w, {"roll": 0, "gain": 50, "copies": 1}, 1)   # gain = 1.5 exactly, angle 0
    finally:
        tr.np.random.default_rng = orig
    assert out[0, 0].tolist() == [2, -2, 5], "half away from zero (positive): %s" % out[0, 0]
    assert out[0, 1].tolist() == [-5, 2047, -2048], "negative .5 / clipping: %s" % out[0, 1]
    assert out[0, 2].tolist() == [0, 2, 2], "got %s" % out[0, 2]


def t_warn_subject_not_grouping():
    """W2-5F2: warn 'both train and test' when 2 subjects exist but grouping is by session."""
    a = make_ds("a20", 3, per_class=10, subj_mod=2)
    out, so, se = train("w_subj", D(a), ["--group", "session"])
    txt = (se + so + rmd(out)).lower()
    assert "both train and test" in txt, "no 'both train and test' warning"


def t_warn_duplicate_file():
    """W2-5F2: warn when the same file is given twice."""
    a = make_ds("a21", 3, per_class=8)
    out, so, se = train("w_dup", D(a, a))
    txt = (se + so + rmd(out)).lower()
    assert "duplicate" in txt or "identical" in txt, "no duplicate-file warning"
    b = make_ds("b21", 4, per_class=8)
    out2, so2, se2 = train("w_nodup", D(a, b))
    assert "duplicate" not in (se2 + so2).lower(), "spurious duplicate warning for different files"


def t_eval_rejected_device_windows():
    """W2-5F2: dev_class -1 (device rejected) is not counted as a disagreement."""
    h = eval_setup()
    m = infer_ref.load_header(h)
    z = synth_dataset.make_dataset(10, 31)
    _, pred, _ = host_eval(h, z["windows"])
    n = len(pred)
    dc = pred.astype(np.int8).copy()
    dc[:12] = -1
    extra = {"dev_flags": np.ones(n, np.uint8), "dev_class": dc, "dev_conf": np.full(n, 100, np.uint8),
             "model_hash": np.full(n, m["GM_MODEL_HASH"], np.uint32)}
    e = make_ds("ev8", 31, per_class=10, extra=extra)
    rc, so, se, out = run_eval(h, [e], "dev_rej")
    assert rc == 0, se[-300:]
    md, js = report_blob(out)
    naive = (n - 12) / n
    assert not has_number(md + js, naive), "rejected windows counted as disagreements (%.4f)" % naive
    assert "100" in md or has_number(js, 1.0), "agreement should be 100 % over non-rejected windows"


TESTS = [t_multi_data_forms, t_validate_each_file, t_drop_subject_session, t_session_grouping_by_file_and_value,
         t_subject_grouping_by_value, t_synthetic_flag_propagation, t_extra_arrays_and_meta,
         t_default_output_byte_identical, t_selftest_still_passes,
         t_eval_selftest, t_eval_accuracy_and_confusion, t_eval_min_conf_and_rejection_definition,
         t_eval_stdout_and_multi_data, t_eval_per_subject, t_eval_device_agreement, t_eval_synthetic_marking,
         t_eval_bad_input_exit2,
         t_aug_off_by_default, t_aug_deterministic_and_effective, t_aug_val_test_untouched,
         t_aug_zero_roll_zero_gain, t_aug_clipping_and_extremes, t_aug_bad_values, t_report_contents,
         t_aug_geometry, t_aug_rounding_half_away, t_warn_subject_not_grouping, t_warn_duplicate_file,
         t_eval_rejected_device_windows]


def main():
    """Run every test (or those whose name contains a CLI argument). Returns 0 when all pass, else 1."""
    fails = 0
    only = sys.argv[1:]
    for t in TESTS:
        if only and not any(o in t.__name__ for o in only):
            continue
        try:
            t()
            print("PASS %s" % t.__name__)
        except Skip as s:
            print("PASS %s (soft check skipped: %s)" % (t.__name__, s))
        except Exception as e:  # noqa: BLE001
            fails += 1
            msg = str(e).splitlines()[0] if str(e) else type(e).__name__
            print("FAIL %s: %s" % (t.__name__, msg[:300]))
            if os.environ.get("TEST_TRACE"):
                traceback.print_exc()
    shutil.rmtree(TMP, ignore_errors=True)
    if fails:
        print("%d FAILED" % fails)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
