# [AI-GENERATED: Claude Code]
"""Score an existing gesture_model.h on new recordings with the integer path only (ticket W2-5, spec R2).

features_ref -> infer_ref.forward -> infer_ref.mlp_conf. A window is rejected when its MLP confidence is
below --min-conf (default: the header's GM_DEFAULT_REJECT). Reports accuracy with a Wilson 95 % interval,
accuracy after rejection and the rejection rate on true gestures (label != 0), the 9x9 confusion matrix,
per-class recall, per-subject accuracy when the data has `subject`, and, for windows whose `dev_flags`
bit 0 is set, the agreement between the on-device `dev_class` and the host prediction (only for windows
whose `model_hash` equals the header's GM_MODEL_HASH; the others are counted as "different model").
Reports are marked SYNTHETIC when any input is synthetic.

Dataset files are the train.py format (several --data files are concatenated); extra arrays written by
tools/recorder.py (window_id, overruns, model_hash, dev_flags, dev_class, dev_conf, events, meta) are
optional and only dev_flags / dev_class / model_hash are used here.

Usage:
  python3 tools/evaluate_model.py --header gesture_model.h --data D.npz [--data E.npz ...] [--out-dir DIR] [--min-conf N]
  python3 tools/evaluate_model.py --selftest      # prints "evaluate_model selftest PASS"
Exit codes: 0 ok, 2 bad input.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import infer_ref  # noqa: E402
import train  # noqa: E402  (dataset loading, feature cache, Wilson interval, confusion matrix)

N_CLASSES = train.N_CLASSES
CLASS_NAMES = train.CLASS_NAMES


def load_extras(paths, n_per_file):
    """Read the optional on-device arrays of every file and concatenate them.

    Args: paths (list of str); n_per_file (list of int, N of each file). Returns: dict with dev_flags,
    dev_class, model_hash (int64 arrays of the total length; windows of a file lacking an array get
    dev_flags 0, dev_class 0 and model_hash -1) and has_hash (bool, any file has model_hash).
    """
    fl, dc, mh = [], [], []
    for p, n in zip(paths, n_per_file):
        z = np.load(p)
        ok = lambda k: k in z.files and len(z[k]) == n   # noqa: E731
        fl.append(z["dev_flags"].astype(np.int64) if ok("dev_flags") and ok("dev_class") else np.zeros(n, np.int64))
        dc.append(z["dev_class"].astype(np.int64) if ok("dev_flags") and ok("dev_class") else np.zeros(n, np.int64))
        mh.append(z["model_hash"].astype(np.int64) if ok("model_hash") else np.full(n, -1, np.int64))
    return {"dev_flags": np.concatenate(fl), "dev_class": np.concatenate(dc), "model_hash": np.concatenate(mh),
            "has_hash": any(int(m[0]) != -1 for m in mh if len(m))}


def evaluate(model, paths, min_conf=None):
    """Score a parsed header on one or more dataset files (integer path only).

    Args: model (dict from infer_ref.load_header); paths (list of str); min_conf (int or None =
    GM_DEFAULT_REJECT; a window with MLP confidence below it is rejected).
    Returns: report dict (JSON-serialisable) with files, n, synthetic, min_conf, correct, acc, ci,
    gestures {n, rejected, reject_rate, accepted, accepted_correct, acc_after_reject}, confusion,
    recall (list, None where a class has no window), per_subject (dict or None), device (dict).
    Raises train.TrainError on unreadable or invalid data.
    """
    ds = train.load_datasets(paths)
    ex = load_extras(paths, [n for _, n in ds["files"]])
    y = ds["labels"]
    feats = train.compute_features(ds["windows"])
    res = train.integer_eval(model, feats, y)
    pred, margin = res["pred"], res["margin"]
    conf = np.array([infer_ref.mlp_conf(int(m), model["GM_CONF_SHIFT"]) for m in margin])
    thr = int(model["GM_DEFAULT_REJECT"] if min_conf is None else min_conf)
    rej = conf < thr
    gest = y != 0
    ng = int(gest.sum())
    acc_g = gest & ~rej
    n = len(y)
    cm = train._confusion(y, pred)
    recall = [(cm[i][i] / sum(cm[i])) if sum(cm[i]) else None for i in range(N_CLASSES)]
    per_subject = None
    if ds["subject"] is not None:
        per_subject = {str(int(s)): [int((ds["subject"] == s).sum()), int(((ds["subject"] == s) & (pred == y)).sum())]
                       for s in np.unique(ds["subject"])}
    on_dev = (ex["dev_flags"] & 1) != 0
    same = on_dev & (ex["model_hash"] == int(model["GM_MODEL_HASH"]))
    other = on_dev & ~same
    dev = {"n_with_device_result": int(on_dev.sum()), "n_same_model": int(same.sum()),
           "n_different_model": int(other.sum()) if ex["has_hash"] else 0,
           "n_no_model_hash": int(other.sum()) if not ex["has_hash"] else 0,
           "agree": int((ex["dev_class"][same] == pred[same]).sum())}
    ok = res["correct"]
    return {"files": ds["files"], "n": int(n), "synthetic": bool(ds["synthetic"]), "notes": ds["notes"],
            "model_hash": "0x%08X" % model["GM_MODEL_HASH"], "min_conf": thr,
            "correct": int(ok), "acc": ok / n, "ci": list(train.wilson_interval(int(ok), n)),
            "gestures": {"n": ng, "rejected": int((rej & gest).sum()), "reject_rate": float((rej & gest).sum() / max(ng, 1)),
                         "accepted": int(acc_g.sum()), "accepted_correct": int((acc_g & (pred == y)).sum()),
                         "acc_after_reject": float((acc_g & (pred == y)).sum() / max(int(acc_g.sum()), 1))},
            "confusion": cm, "recall": recall, "per_subject": per_subject, "device": dev,
            "class_counts": [int((y == c).sum()) for c in range(N_CLASSES)]}


def render_markdown(rep):
    """Format a report dict as markdown. Args: rep (dict from evaluate). Returns: str."""
    L = ["# Model evaluation", ""]
    if rep["synthetic"]:
        L += ["> SYNTHETIC data: pipeline test only, not an accuracy claim.", ""]
    L += ["Header model hash %s, rejection threshold (MLP confidence) %d. Input files: %s." % (
        rep["model_hash"], rep["min_conf"], "; ".join("`%s` (N = %d)" % f for f in rep["files"])), ""]
    L += ["- Accuracy (integer path, all %d windows): **%.2f %%** (%d / %d), Wilson 95 %% interval %.1f to %.1f %%" % (
        rep["n"], 100 * rep["acc"], rep["correct"], rep["n"], 100 * rep["ci"][0], 100 * rep["ci"][1])]
    g = rep["gestures"]
    L += ["- True gestures (label != 0): %d. Rejection rate %.2f %% (%d / %d); accuracy after rejection %.2f %% (%d / %d accepted)" % (
        g["n"], 100 * g["reject_rate"], g["rejected"], g["n"], 100 * g["acc_after_reject"], g["accepted_correct"], g["accepted"]), ""]
    L += ["## Confusion matrix (rows = true, columns = predicted)", "",
          "| true \\ pred | " + " | ".join(str(i) for i in range(N_CLASSES)) + " | recall |", "|---|" + "---|" * (N_CLASSES + 1)]
    for i, row in enumerate(rep["confusion"]):
        r = rep["recall"][i]
        L.append("| %d %s | %s | %s |" % (i, CLASS_NAMES[i], " | ".join(str(v) for v in row), "%.1f %%" % (100 * r) if r is not None else "n/a"))
    if rep["per_subject"]:
        L += ["", "## Accuracy per subject", ""]
        L += ["- subject %s: %.2f %% (%d / %d)" % (s, 100.0 * c / max(n, 1), c, n) for s, (n, c) in rep["per_subject"].items()]
    d = rep["device"]
    L += ["", "## On-device agreement", ""]
    if d["n_with_device_result"] == 0:
        L += ["- No window carries an on-device result (dev_flags bit 0)."]
    else:
        if d["n_same_model"]:
            L += ["- Same model (hash match): %d windows, device class equals host prediction in %d (%.2f %%)" % (
                d["n_same_model"], d["agree"], 100.0 * d["agree"] / d["n_same_model"])]
        if d["n_different_model"]:
            L += ["- different model: %d windows with a device result carry another GM_MODEL_HASH and are not compared" % d["n_different_model"]]
        if d["n_no_model_hash"]:
            L += ["- %d windows with a device result have no model_hash in the file: not compared" % d["n_no_model_hash"]]
    for nt in rep["notes"]:
        L += ["", "Note: %s" % nt]
    return "\n".join(L) + "\n"


def _selftest():
    """Train a tiny model on synthetic data, evaluate it on another set and check every report part.

    Asserts: accuracy and counts match a direct integer-path computation, rejection at min-conf 0 is 0
    and at 256 is 100 %, per-subject numbers sum to the total, the device agreement counts only windows
    with matching model_hash and bit 0, report.md / report.json are written and SYNTHETIC is marked,
    bad input exits 2. Prints "evaluate_model selftest PASS" and returns 0; returns 1 on failure.
    """
    import synth_dataset
    tmp = tempfile.mkdtemp(prefix="evalmodel_selftest_")
    try:
        tr_ds = os.path.join(tmp, "tr.npz")
        np.savez(tr_ds, **synth_dataset.make_dataset(30, 1))
        train.run_training(tr_ds, os.path.join(tmp, "m"), seed=1, epochs=10, eval_every=5, quiet=True)
        hdr = os.path.join(tmp, "m", "gesture_model.h")
        model = infer_ref.load_header(hdr)
        te = synth_dataset.make_dataset(20, 2)
        n = len(te["labels"])
        base = os.path.join(tmp, "base.npz")
        np.savez(base, **te)
        r0 = evaluate(model, [base])
        feats = train.compute_features(te["windows"])
        want = sum(infer_ref.forward([int(v) for v in f], model)["top1"] == int(t) for f, t in zip(feats, te["labels"]))
        if r0["correct"] != want or r0["n"] != n or not r0["synthetic"] or "SYNTHETIC" not in render_markdown(r0):
            print("FAIL accuracy does not match a direct integer-path computation, or SYNTHETIC not marked")
            return 1
        if sum(v[0] for v in r0["per_subject"].values()) != n or sum(v[1] for v in r0["per_subject"].values()) != want:
            print("FAIL per-subject numbers do not add up")
            return 1
        if sum(map(sum, r0["confusion"])) != n or evaluate(model, [base], 0)["gestures"]["rejected"] != 0 \
                or evaluate(model, [base], 256)["gestures"]["reject_rate"] != 1.0:
            print("FAIL confusion total or rejection extremes")
            return 1
        # device agreement: first 100 windows: bit 0 set; hash matches for the first 60 only; device class = host
        # prediction for the first 40 of those, wrong for the next 20
        host = np.array([infer_ref.forward([int(v) for v in f], model)["top1"] for f in feats])
        flags = np.zeros(n, np.uint8)
        flags[:100] = 1
        mh = np.full(n, 12345, np.int64)
        mh[:60] = int(model["GM_MODEL_HASH"])
        dcl = host.copy()
        dcl[40:60] = (host[40:60] + 1) % N_CLASSES
        dev = os.path.join(tmp, "dev.npz")
        np.savez(dev, **te, dev_flags=flags, dev_class=dcl.astype(np.uint8), model_hash=mh, meta=np.array("m"))
        d = evaluate(model, [dev])["device"]
        if (d["n_with_device_result"], d["n_same_model"], d["n_different_model"], d["agree"]) != (100, 60, 40, 40):
            print("FAIL device agreement counts: %s" % d)
            return 1
        if "different model" not in render_markdown(evaluate(model, [dev])):
            print("FAIL 'different model' not reported")
            return 1
        out = os.path.join(tmp, "out")
        if main(["--header", hdr, "--data", base, "--data", dev, "--out-dir", out]) != 0 \
                or not os.path.exists(os.path.join(out, "report.md")) or not os.path.exists(os.path.join(out, "report.json")):
            print("FAIL main did not write the report files")
            return 1
        with open(os.path.join(out, "report.json")) as f:
            if json.load(f)["n"] != 2 * n:
                print("FAIL two-file report N")
                return 1
        if main(["--header", hdr, "--data", os.path.join(tmp, "missing.npz")]) != 2 or main(["--header", os.path.join(tmp, "x.h"), "--data", base]) != 2:
            print("FAIL bad input must exit 2")
            return 1
        print("evaluate_model selftest PASS")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    """CLI entry. Args: argv (list of str or None). Returns: int exit code (0 ok, 2 bad input)."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--header", help="gesture_model.h to score")
    ap.add_argument("--data", action="append", help="dataset .npz; repeat the flag or give a comma list")
    ap.add_argument("--out-dir", help="write report.md and report.json here (default: print markdown)")
    ap.add_argument("--min-conf", type=int, help="reject below this MLP confidence (default: the header's GM_DEFAULT_REJECT)")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    if not a.header or not a.data:
        ap.error("--header and --data are required (or use --selftest)")
    try:
        paths = train.parse_data_args(a.data)
        model = train.load_model(a.header)
        rep = evaluate(model, paths, a.min_conf)
    except train.TrainError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    md = render_markdown(rep)
    if a.out_dir:
        os.makedirs(a.out_dir, exist_ok=True)
        with open(os.path.join(a.out_dir, "report.md"), "w") as f:
            f.write(md)
        with open(os.path.join(a.out_dir, "report.json"), "w") as f:
            json.dump(rep, f, indent=1)
        print("wrote %s and report.json" % os.path.join(a.out_dir, "report.md"))
    else:
        print(md, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
