# [AI-GENERATED: Claude Code]
"""Train the 60-H-9 gesture MLP on a windows dataset and export it (ticket W2-2, contracts C0/C3/C4/C5).

Pipeline: dataset .npz -> features (tools/features_ref.py) -> train/val split -> per-feature
normalisation from TRAIN features only (export_model.py norm) -> x8 = infer_ref.normalize ->
float MLP trained in numpy on x8 / K (no torch, no sklearn) -> candidate headers exported
every few epochs (export_model.py header) and scored with the INTEGER path (infer_ref.forward)
on the validation set -> best integer accuracy wins -> gesture_model.h, norm.json, net.npz,
report.json, report.md in --out-dir.

Evaluation rule (CONTRACTS C4.3): every reported accuracy, the model selection and the early
stopping use the integer path on the held-out set; float accuracy is diagnostic only. Because the
same held-out set drives the selection, its integer accuracy is slightly optimistic; a final
untouched test set is the recorder's job later.

Dataset format (see tools/README.md): .npz with windows int16 [N,150,3], labels uint8 [N],
optional subject uint8 [N] and session uint16 [N] (used by --group).

Adam and softmax cross-entropy are the textbook algorithms (Kingma and Ba 2015, arXiv:1412.6980);
no code was borrowed.

Usage:
  python3 tools/train.py --data ds.npz --out-dir DIR [--seed S] [--hidden 16] [--epochs E]
                         [--val-frac 0.2] [--group subject|session|none] [--k K]
  python3 tools/train.py --selftest
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import export_model  # noqa: E402  (fallback_needed; the exporter CLI is run as a subprocess)
import features_ref  # noqa: E402
import infer_ref  # noqa: E402

N_CLASSES = 9
N_FEATURES = features_ref.FEAT_COUNT
CLASS_NAMES = ["none", "swipe_right", "swipe_left", "raise", "push_down",
               "circle_cw", "circle_ccw", "twist", "thrust"]
DEFAULT_K = 64.0          # x8 / K brings the inputs to about +-2 for conditioning
EXPORTER = os.path.join(_HERE, "export_model.py")


class TrainError(Exception):
    """Unusable input or an exporter refusal. Carries a message printed once by main()."""


# ----------------------------------------------------------------------------- data
def load_dataset(path):
    """Load and validate a dataset .npz.

    Args: path (str). Returns: dict with windows int16 [N,150,3], labels int64 [N], and subject /
    session (int64 [N] or None), synthetic (bool, from the optional marker). Raises TrainError on a missing key, wrong shape or label range.
    """
    try:
        z = np.load(path)
    except (OSError, ValueError) as e:
        raise TrainError("cannot read dataset %s: %s" % (path, e))
    for k in ("windows", "labels"):
        if k not in z.files:
            raise TrainError("dataset lacks key '%s'" % k)
    w, y = z["windows"], z["labels"].astype(np.int64)
    if w.ndim != 3 or w.shape[1:] != (features_ref.WINDOW_LEN, features_ref.AXES) or len(w) != len(y):
        raise TrainError("windows must be [N,150,3] with N labels, got %s and %s" % (w.shape, y.shape))
    if y.min() < 0 or y.max() >= N_CLASSES:
        raise TrainError("labels must be in 0..%d" % (N_CLASSES - 1))
    if w.min() < features_ref.X_MIN or w.max() > features_ref.X_MAX:
        raise TrainError("window values outside the 12-bit range [-2048, 2047]")
    out = {"windows": w.astype(np.int16), "labels": y, "subject": None, "session": None,
           "synthetic": bool("synthetic" in z.files and int(z["synthetic"]) != 0)}
    for k in ("subject", "session"):
        if k in z.files:
            if len(z[k]) != len(y):
                raise TrainError("%s has %d entries, labels %d" % (k, len(z[k]), len(y)))
            out[k] = z[k].astype(np.int64)
    return out


def compute_features(windows, cache_path=None):
    """Compute the 60 C3 features of every window with features_ref, with an on-disk cache.

    Args: windows (int16 [N,150,3]); cache_path (str or None). The cache is a .npy next to a
    .sha1 file holding the hash of the windows, reused only if the hash matches.
    Returns: int32 ndarray [N,60].
    """
    digest = hashlib.sha1(np.ascontiguousarray(windows).tobytes()).hexdigest()
    if cache_path and os.path.exists(cache_path) and os.path.exists(cache_path + ".sha1"):
        with open(cache_path + ".sha1") as f:
            if f.read().strip() == digest:
                return np.load(cache_path)
    feats = np.array([features_ref.features_extract(w.tolist()) for w in windows], dtype=np.int32)
    if cache_path:
        np.save(cache_path, feats)
        with open(cache_path + ".sha1", "w") as f:
            f.write(digest + "\n")
    return feats


def split_indices(labels, group_ids, val_frac, seed):
    """Deterministic train/validation split.

    Args: labels (int [N]); group_ids (int [N] or None: whole groups go to one side, groups are
    shuffled with the seed and moved to validation until >= val_frac of the windows; None gives a
    stratified split, val_frac of every class, at least 1 per class with >= 2 windows); val_frac
    (float in (0,1)); seed (int). Returns: (train_idx, val_idx) sorted int arrays.
    Raises TrainError if a side would be empty or fewer than 2 groups exist.
    """
    rng = np.random.default_rng(seed)
    n = len(labels)
    if group_ids is not None:
        groups = np.unique(group_ids)
        if len(groups) < 2:
            raise TrainError("grouped split needs at least 2 groups, found %d" % len(groups))
        rng.shuffle(groups)
        val_mask = np.zeros(n, dtype=bool)
        for g in groups[:-1]:
            if val_mask.sum() >= val_frac * n:
                break
            val_mask |= group_ids == g
    else:
        val_mask = np.zeros(n, dtype=bool)
        for c in np.unique(labels):
            idx = np.flatnonzero(labels == c)
            rng.shuffle(idx)
            k = int(round(val_frac * len(idx)))
            if len(idx) >= 2:
                k = min(max(k, 1), len(idx) - 1)
            val_mask[idx[:k]] = True
    tr, va = np.flatnonzero(~val_mask), np.flatnonzero(val_mask)
    if len(tr) == 0 or len(va) == 0:
        raise TrainError("split produced an empty train or validation set")
    return tr, va


# ----------------------------------------------------------------------------- float MLP
def init_net(hidden, rng):
    """He-initialised 60-hidden-9 net. Args: hidden (int); rng (numpy Generator).
    Returns: dict W1 [hidden,60], b1, W2 [9,hidden], b2 (float64)."""
    return {"W1": rng.normal(0, np.sqrt(2.0 / N_FEATURES), (hidden, N_FEATURES)),
            "b1": np.zeros(hidden),
            "W2": rng.normal(0, np.sqrt(2.0 / hidden), (N_CLASSES, hidden)),
            "b2": np.zeros(N_CLASSES)}


def float_logits(net, X):
    """Float forward pass. Args: net (dict W1,b1,W2,b2); X (float [n,60], i.e. x8 / K).
    Returns: float [n,9] logits."""
    return np.maximum(X @ net["W1"].T + net["b1"], 0.0) @ net["W2"].T + net["b2"]


def train_epoch(net, opt, X, y, rng, lr, batch=32, wd=1e-4):
    """One epoch of minibatch Adam on softmax cross-entropy (in place).

    Args: net (dict, updated); opt (dict of Adam moments, updated; start with {});
    X (float [n,60]); y (int [n]); rng (Generator, shuffles); lr (float); batch (int); wd (float L2
    on the weights). Returns: mean training loss (float).
    """
    n = len(y)
    perm = rng.permutation(n)
    tot = 0.0
    for s in range(0, n, batch):
        ib = perm[s:s + batch]
        xb, yb = X[ib], y[ib]
        z1 = xb @ net["W1"].T + net["b1"]
        h = np.maximum(z1, 0.0)
        lg = h @ net["W2"].T + net["b2"]
        lg -= lg.max(axis=1, keepdims=True)
        p = np.exp(lg)
        p /= p.sum(axis=1, keepdims=True)
        tot += float(-np.log(p[np.arange(len(ib)), yb] + 1e-12).sum())
        d2 = p
        d2[np.arange(len(ib)), yb] -= 1.0
        d2 /= len(ib)
        g = {"W2": d2.T @ h + wd * net["W2"], "b2": d2.sum(axis=0)}
        d1 = (d2 @ net["W2"]) * (z1 > 0)
        g["W1"] = d1.T @ xb + wd * net["W1"]
        g["b1"] = d1.sum(axis=0)
        opt["t"] = opt.get("t", 0) + 1
        t = opt["t"]
        for k, gr in g.items():
            m = opt.setdefault("m" + k, np.zeros_like(gr))
            v = opt.setdefault("v" + k, np.zeros_like(gr))
            m *= 0.9
            m += 0.1 * gr
            v *= 0.999
            v += 0.001 * gr * gr
            net[k] -= lr * (m / (1 - 0.9 ** t)) / (np.sqrt(v / (1 - 0.999 ** t)) + 1e-8)
    return tot / n


# ----------------------------------------------------------------------------- export + integer eval
def run_exporter(args, what):
    """Run tools/export_model.py as a subprocess.

    Args: args (list of str, the exporter's arguments); what (str, used in the error message).
    Returns: stdout (str). Raises TrainError carrying the exporter's stderr and exit code when it fails.
    """
    r = subprocess.run([sys.executable, EXPORTER] + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise TrainError("export_model.py %s failed (exit %d): %s" % (what, r.returncode, r.stderr.strip()))
    return r.stdout


def integer_eval(model, feats, labels):
    """Score a parsed header model on raw features with infer_ref.forward (the integer path).

    Args: model (dict from infer_ref.load_header); feats (int [n,60]); labels (int [n]).
    Returns: dict with pred (int ndarray), margin (int ndarray), acc (float), correct (int).
    """
    pred, margin = [], []
    for r in feats:
        res = infer_ref.forward([int(v) for v in r], model)
        pred.append(res["top1"])
        margin.append(res["margin"])
    pred, margin = np.array(pred), np.array(margin)
    ok = int((pred == labels).sum())
    return {"pred": pred, "margin": margin, "correct": ok, "acc": ok / len(labels)}


def export_candidate(net, K, work, val_feats, val_labels, tag):
    """Write net.npz, export a header with validation data, and score it on the integer path.

    Args: net (dict W1,b1,W2,b2); K (float); work (str dir holding norm.json, calib.npy, val.npy,
    val_labels.npy); val_feats, val_labels (arrays for scoring); tag (str file stem).
    Returns: (header_path, int_result dict from integer_eval, model dict). Raises TrainError if the
    exporter refuses (message includes the violated bound).
    """
    npz = os.path.join(work, tag + ".npz")
    hdr = os.path.join(work, tag + ".h")
    np.savez(npz, W1=net["W1"], b1=net["b1"], W2=net["W2"], b2=net["b2"], K=np.float64(K))
    run_exporter(["header", "--weights", npz, "--norm", os.path.join(work, "norm.json"),
                  "--calib", os.path.join(work, "calib.npy"), "--val", os.path.join(work, "val.npy"),
                  "--val-labels", os.path.join(work, "val_labels.npy"), "--out", hdr], "header")
    model = infer_ref.load_header(hdr)
    return hdr, integer_eval(model, val_feats, val_labels), model


# ----------------------------------------------------------------------------- main run
def _confusion(labels, pred):
    """9x9 confusion matrix, rows = true, columns = predicted. Args: two int arrays. Returns: list of lists."""
    cm = np.zeros((N_CLASSES, N_CLASSES), dtype=np.int64)
    for t, p in zip(labels, pred):
        cm[int(t), int(p)] += 1
    return cm.tolist()


def _write_report_md(path, rep):
    """Write the human-readable report. Args: path (str); rep (dict as written to report.json)."""
    L = ["# Training report", "",
         "Data: `%s` (%d windows, %d train / %d validation), split `%s`, seed %d." % (
             rep["data"], rep["n_total"], rep["n_train"], rep["n_val"], rep["split"], rep["seed"]),
         "Network 60-%d-9, K = %g, best candidate at epoch %d (of %d run)." % (
             rep["hidden"], rep["k"], rep["best_epoch"], rep["epochs_run"]), ""]
    if rep.get("synthetic_note"):
        L += ["> %s" % rep["synthetic_note"], ""]
    L += ["## Accuracy (validation set; C4.3: the integer path is the reported number)", "",
          "- Integer-path accuracy: **%.2f %%** (%d / %d)" % (100 * rep["int_acc"], rep["int_correct"], rep["n_val"]),
          "- Float accuracy (diagnostic only): %.2f %% (%d / %d)" % (100 * rep["float_acc"], rep["float_correct"], rep["n_val"]),
          "- Float-vs-int argmax agreement: %.2f %% (%d / %d)" % (100 * rep["agreement"], rep["agree_count"], rep["n_val"]),
          "- Caveat: the validation set also selected the checkpoint (early stopping on integer accuracy), so the figure is slightly optimistic.",
          "", "## C4.3 fallback verdict (int16 inputs, option d)", "", rep["fallback_verdict"], "",
          "## Confidence parameters (C5)", "",
          "- GM_CONF_SHIFT = %d" % rep["conf_shift"],
          "- GM_DEFAULT_REJECT = %d" % rep["default_reject"],
          "- Rejection rate at that default on validation true gestures (label != 0): %.2f %% (%d / %d)" % (
              100 * rep["reject_rate_gestures"], rep["reject_count_gestures"], rep["n_gestures_val"]),
          "- Share of all validation windows with MLP confidence below it: %.2f %%" % (100 * rep["reject_rate_all"]),
          "", "## Confusion matrix (integer path, rows = true, columns = predicted)", "",
          "| true \\ pred | " + " | ".join(str(i) for i in range(N_CLASSES)) + " | recall |",
          "|---|" + "---|" * (N_CLASSES + 1)]
    for i, row in enumerate(rep["confusion"]):
        tot = sum(row)
        L.append("| %d %s | %s | %s |" % (i, CLASS_NAMES[i], " | ".join(str(v) for v in row),
                                          "%.1f %%" % (100.0 * row[i] / tot) if tot else "n/a"))
    L += ["", "## Selection history (integer validation accuracy per candidate)", ""]
    L += ["- epoch %d: %s" % (e, ("%.2f %%" % (100 * a)) if a is not None else "exporter refused") for e, a in rep["history"]]
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")


def run_training(data, out_dir, seed=1, hidden=16, epochs=60, val_frac=0.2, group="none",
                 k=DEFAULT_K, eval_every=5, patience=6, synthetic_note=None, quiet=False):
    """Run the whole pipeline and write the output files.

    Args: data (str path of the dataset .npz); out_dir (str, created); seed (int); hidden (int);
    epochs (int maximum); val_frac (float); group ('none', 'subject' or 'session'); k (float, the
    net is trained on x8 / k); eval_every (int epochs between integer-path candidates); patience
    (int candidates without improvement before stopping); synthetic_note (str or None, copied to
    the report); quiet (bool, suppress progress prints). Returns: the report dict. Raises TrainError
    on unusable input or if the exporter refuses every candidate.
    """
    def say(msg):
        if not quiet:
            print(msg, flush=True)
    if not (k > 0 and hidden >= 1 and epochs >= 1 and 0 < val_frac < 1 and eval_every >= 1):
        raise TrainError("need k > 0, hidden >= 1, epochs >= 1, 0 < val-frac < 1, eval-every >= 1")
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.join(out_dir, "work")
    os.makedirs(work, exist_ok=True)
    ds = load_dataset(data)
    gid = None
    if group != "none":
        gid = ds[group]
        if gid is None:
            raise TrainError("--group %s requested but the dataset has no '%s' array" % (group, group))
    if ds["synthetic"] and not synthetic_note:
        synthetic_note = "SYNTHETIC data: pipeline test only, not an accuracy claim."
    t0 = time.time()
    feats = compute_features(ds["windows"], os.path.join(out_dir, "features.npy"))
    say("features: %d windows in %.1f s" % (len(feats), time.time() - t0))
    y = ds["labels"]
    tr, va = split_indices(y, gid, val_frac, seed)
    np.savez(os.path.join(out_dir, "split.npz"), train=tr, val=va)
    ftr, fva, ytr, yva = feats[tr], feats[va], y[tr], y[va]
    # b. normalisation from TRAIN features only
    np.save(os.path.join(work, "calib.npy"), ftr)
    np.save(os.path.join(work, "val.npy"), fva)
    np.save(os.path.join(work, "val_labels.npy"), yva)
    run_exporter(["norm", "--features", os.path.join(work, "calib.npy"), "--out", os.path.join(work, "norm.json")], "norm")
    with open(os.path.join(work, "norm.json")) as f:
        nj = json.load(f)
    nm = {"GM_IN_OFF": nj["off"], "GM_IN_SH": nj["sh"]}
    x8_tr = np.array([infer_ref.normalize([int(v) for v in r], nm) for r in ftr], dtype=np.float64)
    x8_va = np.array([infer_ref.normalize([int(v) for v in r], nm) for r in fva], dtype=np.float64)
    Xtr, Xva = x8_tr / k, x8_va / k
    # c. train; candidates scored on the integer path
    rng = np.random.default_rng(seed)
    net = init_net(hidden, rng)
    opt = {}
    best, history, stale, last_err = None, [], 0, None
    ep_run = 0
    for ep in range(1, epochs + 1):
        loss = train_epoch(net, opt, Xtr, ytr, rng, lr=3e-3)
        ep_run = ep
        if ep % eval_every == 0 or ep == epochs:
            try:
                hdr, res, model = export_candidate(net, k, work, fva, yva, "cand")
            except TrainError as e:
                last_err = str(e)
                history.append((ep, None))
                say("epoch %d loss %.4f  candidate refused by exporter" % (ep, loss))
                continue
            history.append((ep, res["acc"]))
            say("epoch %d loss %.4f  integer val acc %.2f %%" % (ep, loss, 100 * res["acc"]))
            if best is None or res["acc"] > best["acc"]:
                shutil.copyfile(hdr, os.path.join(work, "best.h"))
                best = {"acc": res["acc"], "epoch": ep, "net": {a: b.copy() for a, b in net.items()}, "res": res}
                stale = 0
            else:
                stale += 1
                if stale >= patience:
                    say("early stop: no integer-accuracy gain for %d candidates" % patience)
                    break
    if best is None:
        raise TrainError("the exporter refused every candidate; last error: %s" % last_err)
    # d. final outputs
    hdr_out = os.path.join(out_dir, "gesture_model.h")
    shutil.copyfile(os.path.join(work, "best.h"), hdr_out)
    shutil.copyfile(os.path.join(work, "norm.json"), os.path.join(out_dir, "norm.json"))
    bn = best["net"]
    np.savez(os.path.join(out_dir, "net.npz"), W1=bn["W1"], b1=bn["b1"], W2=bn["W2"], b2=bn["b2"], K=np.float64(k))
    model = infer_ref.load_header(hdr_out)
    res = integer_eval(model, fva, yva)
    pf = np.argmax(float_logits(bn, Xva), axis=1)
    n = len(yva)
    ok_i, ok_f = int((res["pred"] == yva).sum()), int((pf == yva).sum())
    agree = int((pf == res["pred"]).sum())
    confs = np.array([infer_ref.mlp_conf(int(m), model["GM_CONF_SHIFT"]) for m in res["margin"]])
    gest = yva != 0
    rej = confs < model["GM_DEFAULT_REJECT"]
    if n >= 500:
        need = export_model.fallback_needed(n, ok_f, ok_i, agree)
        verdict = ("n = %d >= 500: fallback criterion %s (agreement %.2f %% vs 97 %% limit; float - int accuracy = %.2f pt)."
                   % (n, "MET, consider int16 inputs (option d)" if need else "NOT met, int8 inputs stay",
                      100.0 * agree / n, 100.0 * (ok_f - ok_i) / n))
    else:
        verdict = ("n = %d < 500: the C4.3 fallback criterion CANNOT be assessed (needs a held-out set of at least 500 windows). "
                   "Informational only: agreement %.2f %%, float - int accuracy %.2f pt." % (n, 100.0 * agree / n, 100.0 * (ok_f - ok_i) / n))
    rep = {"data": os.path.basename(data), "seed": seed, "split": group if group != "none" else "stratified",
           "n_total": int(len(y)), "n_train": int(len(tr)), "n_val": int(n), "hidden": hidden, "k": k,
           "best_epoch": best["epoch"], "epochs_run": ep_run, "int_acc": ok_i / n, "int_correct": ok_i,
           "float_acc": ok_f / n, "float_correct": ok_f, "agreement": agree / n, "agree_count": agree,
           "fallback_verdict": verdict, "fallback_assessable": bool(n >= 500),
           "conf_shift": int(model["GM_CONF_SHIFT"]), "default_reject": int(model["GM_DEFAULT_REJECT"]),
           "n_gestures_val": int(gest.sum()), "reject_count_gestures": int((rej & gest).sum()),
           "reject_rate_gestures": float((rej & gest).sum() / max(int(gest.sum()), 1)),
           "reject_rate_all": float(rej.sum() / n), "confusion": _confusion(yva, res["pred"]),
           "history": history, "synthetic_note": synthetic_note,
           "model_hash": "0x%08X" % model["GM_MODEL_HASH"]}
    with open(os.path.join(out_dir, "report.json"), "w") as f:
        json.dump(rep, f, indent=1)
    _write_report_md(os.path.join(out_dir, "report.md"), rep)
    say("integer accuracy %.2f %%, float %.2f %%, agreement %.2f %%; outputs in %s"
        % (100 * rep["int_acc"], 100 * rep["float_acc"], 100 * rep["agreement"], out_dir))
    return rep


def _selftest():
    """Train on a tiny synthetic dataset in a temp dir and check the outputs.

    Asserts: all output files exist, the header loads with infer_ref.load_header, integer accuracy
    > 60 % (chance is 11 %; synthetic data only), and a grouped split keeps groups disjoint.
    Prints "train selftest PASS" and returns 0; returns 1 after printing the reason on failure.
    """
    import synth_dataset
    tmp = tempfile.mkdtemp(prefix="train_selftest_")
    try:
        ds = os.path.join(tmp, "ds.npz")
        np.savez_compressed(ds, **synth_dataset.make_dataset(40, 7))
        d = load_dataset(ds)
        tr, va = split_indices(d["labels"], d["session"], 0.25, 3)
        if set(d["session"][tr]) & set(d["session"][va]) or len(va) == 0:
            print("FAIL grouped split leaks groups")
            return 1
        out = os.path.join(tmp, "run")
        rep = run_training(ds, out, seed=3, epochs=40, eval_every=10, patience=4, quiet=True)
        for f in ("gesture_model.h", "norm.json", "net.npz", "report.json", "report.md"):
            if not os.path.exists(os.path.join(out, f)):
                print("FAIL missing output %s" % f)
                return 1
        m = infer_ref.load_header(os.path.join(out, "gesture_model.h"))
        if m["GM_N_CLASSES"] != N_CLASSES or m["GM_N_FEATURES"] != N_FEATURES:
            print("FAIL header shape")
            return 1
        if rep["int_acc"] <= 0.60:
            print("FAIL integer accuracy %.3f <= 0.60 on synthetic data" % rep["int_acc"])
            return 1
        print("train selftest PASS")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    """CLI entry. Args: argv (list of str or None). Returns: int exit code (0 ok, 2 bad input, 3 exporter refusal)."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--data", help="dataset .npz (windows, labels, optional subject, session)")
    ap.add_argument("--out-dir", help="output directory")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--hidden", type=int, default=16)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--val-frac", type=float, default=0.2)
    ap.add_argument("--group", choices=["subject", "session", "none"], default="none")
    ap.add_argument("--k", type=float, default=DEFAULT_K, help="net is trained on x8 / K (default 64)")
    ap.add_argument("--eval-every", type=int, default=5, help="epochs between integer-path candidates")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    if not a.data or not a.out_dir:
        ap.error("--data and --out-dir are required (or use --selftest)")
    try:
        run_training(a.data, a.out_dir, a.seed, a.hidden, a.epochs, a.val_frac, a.group, a.k, a.eval_every)
    except TrainError as e:
        print("error: %s" % e, file=sys.stderr)
        return 3 if "export_model" in str(e) or "exporter" in str(e) else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
