# [AI-GENERATED: Claude Code]
"""Train the 60-16-9 gesture MLP on a windows dataset and export it (tickets W2-2, W2-2F; contracts C0/C3/C4/C5).

Pipeline: dataset .npz -> features (tools/features_ref.py) -> train / validation / test split ->
per-feature normalisation from TRAIN features only (export_model.py norm) -> x8 =
infer_ref.normalize -> float MLP trained in numpy on x8 / K (no torch, no sklearn) -> candidate
headers exported every few epochs (export_model.py header --val) and scored with the INTEGER path
(infer_ref.forward) on the VALIDATION set -> best integer accuracy wins -> gesture_model.h,
norm.json, net.npz, report.json, report.md in --out-dir.

Three sets (review W2-2R M1/M2): train fits the weights and the normalisation; validation selects
the checkpoint and (through the exporter) GM_CONF_SHIFT and GM_DEFAULT_REJECT; the TEST set is
scored once, on the final header, with the integer path, and gives every reported accuracy,
confusion matrix and rejection rate. Validation numbers are reported too, labelled "selection set
(optimistic)". With --test-frac 0 the split is two-way and the report says its numbers are optimistic.

Evaluation rule (CONTRACTS C4.3): every reported accuracy, the model selection and the early
stopping use the integer path; float accuracy is diagnostic only. Which set judges the C4.3 int16
fallback is --fallback-set (default val; open question Q6).

Grouping (W2-2R M4): when the dataset has `subject` (else `session`) and --group is not given, the
split is grouped by it automatically and the choice is printed; --group none forces a stratified
split. Classes missing from train, validation or test after the split are warned about.

Dataset format (see tools/README.md): .npz with windows int16 [N,150,3], labels uint8 [N],
optional subject uint8 [N] and session uint16 [N] (used by --group).

Adam and softmax cross-entropy are the textbook algorithms (Kingma and Ba 2015, arXiv:1412.6980);
no code was borrowed. The Wilson interval is the standard formula (Wilson 1927).

Usage:
  python3 tools/train.py --data ds.npz --out-dir DIR [--seed S | --seeds a,b,c] [--epochs E]
        [--val-frac 0.2] [--test-frac 0.2] [--group subject|session|none]
        [--fallback-set val|test] [--lr 3e-3] [--batch 32] [--weight-decay 1e-4] [--k K]
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
N_HIDDEN = 16             # C4.2: mlp.c static-asserts GM_N_HIDDEN == 16
CLASS_NAMES = ["none", "swipe_right", "swipe_left", "raise", "push_down",
               "circle_cw", "circle_ccw", "twist", "thrust"]
DEFAULT_K = 64.0          # x8 / K brings the typical input to about +-0.3 (extremes about +-2)
EXPORTER = os.path.join(_HERE, "export_model.py")
MIN_FALLBACK_N = 500      # C4.3: the fallback criterion needs a set of at least this many windows


class TrainError(Exception):
    """Unusable input or an exporter refusal. Carries a message printed once by main() and the
    process exit code to use (attribute `code`: 2 bad input, 3 exporter refusal)."""

    def __init__(self, msg, code=2):
        super().__init__(msg)
        self.code = code


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
    .sha1 file holding the hash of the windows AND features_ref.FEATURES_VERSION (W2-2R L1), reused
    only if the hash matches.
    Returns: int32 ndarray [N,60].
    """
    h = hashlib.sha1(np.ascontiguousarray(windows).tobytes())
    h.update(b"|FEATURES_VERSION=%d" % features_ref.FEATURES_VERSION)
    digest = h.hexdigest()
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


def min_groups(test_frac):
    """Fewest groups a grouped split can use. Args: test_frac (float). Returns: int (2 without a test set, else 3)."""
    return 3 if test_frac > 0 else 2


def resolve_group(ds, group, test_frac):
    """Decide the grouping of the split (W2-2R M4).

    Args: ds (dict from load_dataset); group (None = automatic, or 'subject', 'session', 'none');
    test_frac (float, decides how many groups are needed). Returns: (name, message) with name in
    'subject', 'session', 'none' and message a one-line description to print and put in the report.
    Automatic mode takes subject, else session, provided it has enough groups; otherwise it falls
    back to a stratified split and says why. Raises TrainError for an explicitly requested array
    the dataset lacks.
    """
    need = min_groups(test_frac)
    if group == "none":
        return "none", "grouping: none (forced by --group none): stratified split"
    if group in ("subject", "session"):
        if ds[group] is None:
            raise TrainError("--group %s requested but the dataset has no '%s' array" % (group, group))
        return group, "grouping: by %s (requested by --group)" % group
    why = []
    for cand in ("subject", "session"):
        if ds[cand] is None:
            continue
        n = len(np.unique(ds[cand]))
        if n >= need:
            return cand, "grouping: by %s (automatic: the dataset has it, %d groups)" % (cand, n)
        why.append("%s has only %d groups (need %d)" % (cand, n, need))
    msg = "grouping: none (automatic: %s): stratified split, siblings from one session may land on both sides and inflate the numbers" % (
        "; ".join(why) if why else "the dataset has no subject or session array")
    return "none", msg


def split_indices(labels, group_ids, val_frac, test_frac, seed):
    """Deterministic three-way (or two-way) split into train / validation / test.

    Args: labels (int [N]); group_ids (int [N] or None: whole groups go to one set; groups are shuffled
    with the seed, then whole groups move to test until >= test_frac of the windows, then to
    validation until >= val_frac, the rest is train; None gives a stratified split, test_frac and
    val_frac of every class, at least 1 per class with >= 3 windows, train keeps at least 1);
    val_frac (float in (0,1)); test_frac (float in [0,1), 0 means no test set); seed (int).
    Returns: (train_idx, val_idx, test_idx) sorted int arrays (test_idx empty if test_frac is 0).
    Raises TrainError if a set would be empty or too few groups exist.
    """
    rng = np.random.default_rng(seed)
    n = len(labels)
    part = np.zeros(n, dtype=np.int8)       # 0 train, 1 validation, 2 test
    if group_ids is not None:
        groups = np.unique(group_ids)
        need = min_groups(test_frac)
        if len(groups) < need:
            raise TrainError("grouped split needs at least %d groups (train, validation%s), found %d" % (
                need, ", test" if test_frac > 0 else "", len(groups)))
        rng.shuffle(groups)
        gi, cnt = 0, 0
        while test_frac > 0 and len(groups) - gi > 2 and (cnt == 0 or cnt < test_frac * n):
            m = group_ids == groups[gi]
            part[m] = 2
            cnt += int(m.sum())
            gi += 1
        cnt = 0
        while len(groups) - gi > 1 and (cnt == 0 or cnt < val_frac * n):
            m = group_ids == groups[gi]
            part[m] = 1
            cnt += int(m.sum())
            gi += 1
    else:
        for c in np.unique(labels):
            idx = np.flatnonzero(labels == c)
            rng.shuffle(idx)
            m = len(idx)
            k_te, k_va = int(round(test_frac * m)), int(round(val_frac * m))
            if m >= 3:
                k_te = max(k_te, 1) if test_frac > 0 else 0
                k_va = max(k_va, 1)
            elif m == 2:
                k_te, k_va = 0, 1
            else:
                k_te = k_va = 0
            while k_te + k_va > m - 1:
                if k_te >= k_va and k_te > 0:
                    k_te -= 1
                else:
                    k_va -= 1
            part[idx[:k_te]] = 2
            part[idx[k_te:k_te + k_va]] = 1
    tr, va, te = np.flatnonzero(part == 0), np.flatnonzero(part == 1), np.flatnonzero(part == 2)
    if len(tr) == 0 or len(va) == 0 or (test_frac > 0 and len(te) == 0):
        raise TrainError("split produced an empty train, validation or test set")
    return tr, va, te


def missing_class_warnings(labels, parts):
    """List the classes present in the dataset but absent from a set (W2-2R M4).

    Args: labels (int [N]); parts (dict name -> index array, e.g. train/validation/test; empty
    arrays are skipped, a test set that does not exist is not a warning). Returns: list of str.
    """
    present = set(int(c) for c in np.unique(labels))
    out = []
    for name, idx in parts.items():
        if len(idx) == 0:
            continue
        miss = sorted(present - set(int(c) for c in np.unique(labels[idx])))
        if miss:
            out.append("%s set has no window of class %s (%s): its recall there cannot be measured" % (
                name, ", ".join(str(c) for c in miss), ", ".join(CLASS_NAMES[c] for c in miss)))
    return out


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
    Returns: stdout (str). Raises TrainError carrying the exporter's stderr and exit code when it
    fails; the TrainError exit code is 3 when the exporter exited 3 (bound violation), else 2.
    """
    r = subprocess.run([sys.executable, EXPORTER] + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise TrainError("export_model.py %s failed (exit %d): %s" % (what, r.returncode, r.stderr.strip()),
                         code=3 if r.returncode == 3 else 2)
    return r.stdout


def load_model(path):
    """Parse a header with infer_ref.load_header. Args: path (str). Returns: model dict.
    Raises TrainError (exit 3) if the reference parser rejects the header."""
    try:
        return infer_ref.load_header(path)
    except (ValueError, OSError) as e:
        raise TrainError("infer_ref rejected %s: %s" % (path, e), code=3)


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
    model = load_model(hdr)
    return hdr, integer_eval(model, val_feats, val_labels), model


# ----------------------------------------------------------------------------- metrics + report
def wilson_interval(correct, n, z=1.96):
    """Two-sided Wilson score interval for a proportion (host-side reporting only).

    Args: correct (int successes); n (int trials, >= 1); z (float, 1.96 for 95 %).
    Returns: (low, high) floats in [0, 1].
    """
    p = correct / n
    d = 1.0 + z * z / n
    c = (p + z * z / (2.0 * n)) / d
    h = z * np.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / d
    return float(max(c - h, 0.0)), float(min(c + h, 1.0))


def _confusion(labels, pred):
    """9x9 confusion matrix, rows = true, columns = predicted. Args: two int arrays. Returns: list of lists."""
    cm = np.zeros((N_CLASSES, N_CLASSES), dtype=np.int64)
    for t, p in zip(labels, pred):
        cm[int(t), int(p)] += 1
    return cm.tolist()


def evaluate_set(model, net, k, nm, feats, labels):
    """Score one set with the final header (integer path) plus float diagnostics.

    Args: model (dict from load_model); net (dict, float weights of the same checkpoint); k (float,
    the K the net was trained with); nm (dict GM_IN_OFF / GM_IN_SH from norm.json); feats (int [n,60]
    raw features); labels (int [n]). Returns: dict of counts and rates (JSON-serialisable): n,
    int_correct, int_acc, int_ci (Wilson 95 %), float_correct, float_acc, agree_count, agreement,
    n_gestures, reject_count_gestures, reject_rate_gestures, n_class0, class0_below,
    class0_below_rate, reject_rate_all, confusion.
    """
    n = len(labels)
    res = integer_eval(model, feats, labels)
    x8 = np.array([infer_ref.normalize([int(v) for v in r], nm) for r in feats], dtype=np.float64)
    pf = np.argmax(float_logits(net, x8 / k), axis=1)
    ok_i, ok_f = int(res["correct"]), int((pf == labels).sum())
    agree = int((pf == res["pred"]).sum())
    confs = np.array([infer_ref.mlp_conf(int(m), model["GM_CONF_SHIFT"]) for m in res["margin"]])
    gest = labels != 0
    rej = confs < model["GM_DEFAULT_REJECT"]
    n0 = int((~gest).sum())
    return {"n": int(n), "int_correct": ok_i, "int_acc": ok_i / n, "int_ci": list(wilson_interval(ok_i, n)),
            "float_correct": ok_f, "float_acc": ok_f / n, "agree_count": agree, "agreement": agree / n,
            "n_gestures": int(gest.sum()), "reject_count_gestures": int((rej & gest).sum()),
            "reject_rate_gestures": float((rej & gest).sum() / max(int(gest.sum()), 1)),
            "n_class0": n0, "class0_below": int((rej & ~gest).sum()),
            "class0_below_rate": float((rej & ~gest).sum() / max(n0, 1)),
            "reject_rate_all": float(rej.sum() / n), "confusion": _confusion(labels, res["pred"])}


def _accuracy_lines(m):
    """Markdown bullet lines for one metrics dict. Args: m (dict from evaluate_set). Returns: list of str."""
    return ["- Integer-path accuracy: **%.2f %%** (%d / %d), Wilson 95 %% interval %.1f to %.1f %%" % (
                100 * m["int_acc"], m["int_correct"], m["n"], 100 * m["int_ci"][0], 100 * m["int_ci"][1]),
            "- Float accuracy (diagnostic only): %.2f %% (%d / %d)" % (100 * m["float_acc"], m["float_correct"], m["n"]),
            "- Float-vs-int argmax agreement: %.2f %% (%d / %d)" % (100 * m["agreement"], m["agree_count"], m["n"])]


def _reject_lines(rep, m):
    """Markdown bullet lines on the C5 confidence parameters, measured on one set.

    Args: rep (dict, the report); m (dict from evaluate_set, the set the rates come from).
    Returns: list of str. States "rejection disabled" when GM_DEFAULT_REJECT is 0 (W2-2R L6).
    """
    L = ["- GM_CONF_SHIFT = %d and GM_DEFAULT_REJECT = %d, both chosen on the VALIDATION set by the exporter" % (
        rep["conf_shift"], rep["default_reject"])]
    if rep["default_reject"] == 0:
        L.append("- **rejection disabled (GM_DEFAULT_REJECT = 0)**: no window is rejected at the default, "
                 "so the rates below are 0 by construction. Low-confidence windows exist; see the C5.2 note in tools/README.md.")
    L += ["- Rejection rate at that default on true gestures (label != 0) of this set: %.2f %% (%d / %d)" % (
              100 * m["reject_rate_gestures"], m["reject_count_gestures"], m["n_gestures"]),
          "- Class-0 (no gesture) windows with confidence below the default: %.2f %% (%d / %d)" % (
              100 * m["class0_below_rate"], m["class0_below"], m["n_class0"]),
          "- Share of all windows of this set with MLP confidence below the default: %.2f %%" % (100 * m["reject_rate_all"])]
    return L


def _write_report_md(path, rep):
    """Write the human-readable report. Args: path (str); rep (dict as written to report.json)."""
    te, va = rep["test"], rep["val"]
    prim = te if te is not None else va
    L = ["# Training report", "",
         "Data: `%s` (%d windows: %d train / %d validation / %d test), %s, seed %d, split seed %d." % (
             rep["data"], rep["n_total"], rep["n_train"], rep["n_val"], rep["n_test"], rep["split_note"],
             rep["seed"], rep["split_seed"]),
         "Network 60-%d-9, K = %g, lr %g, batch %d, weight decay %g, best candidate at epoch %d (of %d run)." % (
             rep["hidden"], rep["k"], rep["lr"], rep["batch"], rep["weight_decay"], rep["best_epoch"], rep["epochs_run"]), ""]
    if rep.get("synthetic_note"):
        L += ["> %s" % rep["synthetic_note"], ""]
    if rep["warnings"]:
        L += ["## Warnings", ""] + ["- %s" % w for w in rep["warnings"]] + [""]
    if te is not None:
        L += ["## Accuracy: TEST set (n = %d), scored once on the final header; C4.3: the integer path is the reported number" % te["n"], ""]
    else:
        L += ["## Accuracy: VALIDATION set (n = %d), OPTIMISTIC" % va["n"], "",
              "- **No test set (--test-frac 0):** this set also selected the checkpoint, GM_CONF_SHIFT and GM_DEFAULT_REJECT, "
              "so every number below is optimistic. Do not quote it as an accuracy."]
    L += _accuracy_lines(prim)
    L += ["", "## Confidence parameters (C5), measured on the %s set" % ("test" if te is not None else "validation (optimistic)"), ""]
    L += _reject_lines(rep, prim)
    if te is not None:
        L += ["", "## Selection set: validation (optimistic, n = %d)" % va["n"], "",
              "These numbers come from the set that chose the checkpoint and the C5 constants; they are biased upward and are NOT the result.", ""]
        L += _accuracy_lines(va)
        L += ["- Rejection rate on validation true gestures: %.2f %% (%d / %d); this is at most the 2 %% budget by construction, not a measurement" % (
            100 * va["reject_rate_gestures"], va["reject_count_gestures"], va["n_gestures"])]
    L += ["", "## C4.3 fallback verdict (int16 inputs, option d)", "", rep["fallback_verdict"], "",
          "## Confusion matrix (%s set, integer path, rows = true, columns = predicted)" % ("test" if te is not None else "validation, optimistic"), "",
          "| true \\ pred | " + " | ".join(str(i) for i in range(N_CLASSES)) + " | recall |",
          "|---|" + "---|" * (N_CLASSES + 1)]
    for i, row in enumerate(prim["confusion"]):
        tot = sum(row)
        L.append("| %d %s | %s | %s |" % (i, CLASS_NAMES[i], " | ".join(str(v) for v in row),
                                          "%.1f %%" % (100.0 * row[i] / tot) if tot else "n/a"))
    L += ["", "## Selection history (integer validation accuracy per candidate)", ""]
    L += ["- epoch %d: %s" % (e, ("%.2f %%" % (100 * a)) if a is not None else "exporter refused") for e, a in rep["history"]]
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")


def _fallback_verdict(which, m):
    """Text of the C4.3 fallback verdict.

    Args: which ('val' or 'test', the set that was used); m (dict from evaluate_set for that set).
    Returns: str. Says which set and n, and "CANNOT be assessed" when n < 500.
    """
    n = m["n"]
    where = "the %s set (n = %d)" % ("validation" if which == "val" else "TEST", n)
    extra = " Using the test set for this decision means it is no longer untouched." if which == "test" else ""
    diff = 100.0 * (m["float_correct"] - m["int_correct"]) / n
    if n >= MIN_FALLBACK_N:
        need = export_model.fallback_needed(n, m["float_correct"], m["int_correct"], m["agree_count"])
        return ("Judged on %s: fallback criterion %s (agreement %.2f %% vs 97 %% limit; float - int accuracy = %.2f pt).%s"
                % (where, "MET, consider int16 inputs (option d)" if need else "NOT met, int8 inputs stay",
                   100.0 * m["agree_count"] / n, diff, extra))
    return ("Judged on %s: n = %d < %d, so the C4.3 fallback criterion CANNOT be assessed (needs a set of at least %d windows). "
            "Informational only: agreement %.2f %%, float - int accuracy %.2f pt.%s"
            % (where, n, MIN_FALLBACK_N, MIN_FALLBACK_N, 100.0 * m["agree_count"] / n, diff, extra))


def run_training(data, out_dir, seed=1, hidden=N_HIDDEN, epochs=60, val_frac=0.2, test_frac=0.2, group=None,
                 k=DEFAULT_K, eval_every=5, patience=6, fallback_set="val", lr=3e-3, batch=32,
                 weight_decay=1e-4, split_seed=None, synthetic_note=None, quiet=False):
    """Run the whole pipeline and write the output files.

    Args: data (str path of the dataset .npz); out_dir (str, created); seed (int, weights init and
    batches); hidden (int, must be 16); epochs (int maximum); val_frac (float in (0,1)); test_frac
    (float in [0,1), 0 = no test set, the report then says its numbers are optimistic); group (None =
    automatic, 'subject', 'session' or 'none'); k (float, the net is trained on x8 / k); eval_every
    (int epochs between integer-path candidates); patience (int candidates without improvement
    before stopping); fallback_set ('val' or 'test', the set that judges the C4.3 fallback; Q6);
    lr, batch, weight_decay (Adam learning rate, minibatch size, L2 on the weights); split_seed (int
    or None = seed); synthetic_note (str or None, copied to the report); quiet (bool, suppress
    progress prints and warnings). Returns: the report dict. Raises TrainError on unusable input or
    if the exporter refuses every candidate.
    """
    def say(msg):
        """Print a progress line unless quiet. Args: msg (str). Returns: None."""
        if not quiet:
            print(msg, flush=True)

    def warn(msg):
        """Print a warning on stderr unless quiet. Args: msg (str). Returns: None."""
        if not quiet:
            print("warning: %s" % msg, file=sys.stderr, flush=True)

    if hidden != N_HIDDEN:
        raise TrainError("--hidden %d refused: C4.2 fixes GM_N_HIDDEN at %d and firmware/src/mlp.c static-asserts it" % (hidden, N_HIDDEN))
    if not (k > 0 and epochs >= 1 and 0 < val_frac < 1 and 0 <= test_frac < 1 and val_frac + test_frac < 1
            and eval_every >= 1 and lr > 0 and batch >= 1 and weight_decay >= 0):
        raise TrainError("need k > 0, epochs >= 1, 0 < val-frac < 1, 0 <= test-frac < 1, val-frac + test-frac < 1, "
                         "eval-every >= 1, lr > 0, batch >= 1, weight-decay >= 0")
    if fallback_set not in ("val", "test"):
        raise TrainError("--fallback-set must be val or test")
    if fallback_set == "test" and test_frac == 0:
        raise TrainError("--fallback-set test needs a test set (--test-frac > 0)")
    split_seed = seed if split_seed is None else split_seed
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.join(out_dir, "work")
    os.makedirs(work, exist_ok=True)
    ds = load_dataset(data)
    gname, gmsg = resolve_group(ds, group, test_frac)
    say(gmsg)
    gid = ds[gname] if gname != "none" else None
    if ds["synthetic"] and not synthetic_note:
        synthetic_note = "SYNTHETIC data: pipeline test only, not an accuracy claim."
    t0 = time.time()
    feats = compute_features(ds["windows"], os.path.join(out_dir, "features.npy"))
    say("features: %d windows in %.1f s" % (len(feats), time.time() - t0))
    y = ds["labels"]
    tr, va, te = split_indices(y, gid, val_frac, test_frac, split_seed)
    np.savez(os.path.join(out_dir, "split.npz"), train=tr, val=va, test=te)
    warnings = missing_class_warnings(y, {"train": tr, "validation": va, "test": te})
    for w in warnings:
        warn(w)
    if te.size == 0:
        warnings.append("no test set (--test-frac 0): every reported number comes from the selection set and is optimistic")
        warn(warnings[-1])
    say("split: %d train / %d validation / %d test" % (len(tr), len(va), len(te)))
    ftr, fva, ytr, yva = feats[tr], feats[va], y[tr], y[va]
    fte, yte = feats[te], y[te]
    # normalisation from TRAIN features only; validation features only for scoring and the C5 constants
    np.save(os.path.join(work, "calib.npy"), ftr)
    np.save(os.path.join(work, "val.npy"), fva)
    np.save(os.path.join(work, "val_labels.npy"), yva)
    run_exporter(["norm", "--features", os.path.join(work, "calib.npy"), "--out", os.path.join(work, "norm.json")], "norm")
    with open(os.path.join(work, "norm.json")) as f:
        nj = json.load(f)
    nm = {"GM_IN_OFF": nj["off"], "GM_IN_SH": nj["sh"]}
    x8_tr = np.array([infer_ref.normalize([int(v) for v in r], nm) for r in ftr], dtype=np.float64)
    Xtr = x8_tr / k
    # train; candidates scored on the integer path on VALIDATION
    rng = np.random.default_rng(seed)
    net = init_net(hidden, rng)
    opt = {}
    best, history, stale, last_err = None, [], 0, None
    ep_run = 0
    for ep in range(1, epochs + 1):
        loss = train_epoch(net, opt, Xtr, ytr, rng, lr=lr, batch=batch, wd=weight_decay)
        ep_run = ep
        if ep % eval_every == 0 or ep == epochs:
            try:
                hdr, res, model = export_candidate(net, k, work, fva, yva, "cand")
            except TrainError as e:
                last_err = str(e)
                if e.code != 3:
                    raise
                history.append((ep, None))
                say("epoch %d loss %.4f  candidate refused by exporter" % (ep, loss))
                continue
            history.append((ep, res["acc"]))
            say("epoch %d loss %.4f  integer val acc %.2f %%" % (ep, loss, 100 * res["acc"]))
            if best is None or res["acc"] > best["acc"]:
                shutil.copyfile(hdr, os.path.join(work, "best.h"))
                best = {"acc": res["acc"], "epoch": ep, "net": {a: b.copy() for a, b in net.items()}}
                stale = 0
            else:
                stale += 1
                if stale >= patience:
                    say("early stop: no integer-accuracy gain for %d candidates" % patience)
                    break
    if best is None:
        raise TrainError("the exporter refused every candidate; last error: %s" % last_err, code=3)
    # final outputs
    hdr_out = os.path.join(out_dir, "gesture_model.h")
    shutil.copyfile(os.path.join(work, "best.h"), hdr_out)
    shutil.copyfile(os.path.join(work, "norm.json"), os.path.join(out_dir, "norm.json"))
    bn = best["net"]
    np.savez(os.path.join(out_dir, "net.npz"), W1=bn["W1"], b1=bn["b1"], W2=bn["W2"], b2=bn["b2"], K=np.float64(k))
    model = load_model(hdr_out)
    m_val = evaluate_set(model, bn, k, nm, fva, yva)
    m_test = evaluate_set(model, bn, k, nm, fte, yte) if te.size else None   # the ONE scoring of the test set
    fb = m_test if fallback_set == "test" else m_val
    verdict = _fallback_verdict(fallback_set, fb)
    prim = m_test if m_test is not None else m_val
    rep = {"data": os.path.basename(data), "seed": seed, "split_seed": split_seed, "split_note": gmsg,
           "group": gname, "n_total": int(len(y)), "n_train": int(len(tr)), "n_val": int(len(va)),
           "n_test": int(len(te)), "hidden": hidden, "k": k, "lr": lr, "batch": batch,
           "weight_decay": weight_decay, "best_epoch": best["epoch"], "epochs_run": ep_run,
           "primary_set": "test" if m_test is not None else "val (optimistic)",
           "test": m_test, "val": m_val, "fallback_set": fallback_set, "fallback_verdict": verdict,
           "fallback_assessable": bool(fb["n"] >= MIN_FALLBACK_N),
           "conf_shift": int(model["GM_CONF_SHIFT"]), "default_reject": int(model["GM_DEFAULT_REJECT"]),
           "warnings": warnings, "history": history, "synthetic_note": synthetic_note,
           "model_hash": "0x%08X" % model["GM_MODEL_HASH"]}
    with open(os.path.join(out_dir, "report.json"), "w") as f:
        json.dump(rep, f, indent=1)
    _write_report_md(os.path.join(out_dir, "report.md"), rep)
    say("%s integer accuracy %.2f %% (n = %d), float %.2f %%, agreement %.2f %%; outputs in %s"
        % ("TEST" if m_test is not None else "validation (optimistic)", 100 * prim["int_acc"], prim["n"],
           100 * prim["float_acc"], 100 * prim["agreement"], out_dir))
    return rep


def summarize_seeds(reps):
    """Mean and spread of the reported integer accuracy over several runs.

    Args: reps (list of report dicts from run_training, one per seed). Returns: dict with seeds,
    accs (list of float), set ('test' or 'val (optimistic)'), mean, min, max.
    """
    accs = [float((r["test"] if r["test"] is not None else r["val"])["int_acc"]) for r in reps]
    return {"seeds": [r["seed"] for r in reps], "accs": accs, "set": reps[0]["primary_set"],
            "mean": float(np.mean(accs)), "min": float(np.min(accs)), "max": float(np.max(accs))}


def _write_seeds_summary(out_dir, summ):
    """Write seeds.json and seeds.md. Args: out_dir (str); summ (dict from summarize_seeds). Returns: None."""
    with open(os.path.join(out_dir, "seeds.json"), "w") as f:
        json.dump(summ, f, indent=1)
    L = ["# Multi-seed summary", "", "Integer-path accuracy on the **%s** set, one run per seed (run directories seed_N)." % summ["set"], ""]
    L += ["- seed %d: %.2f %%" % (s, 100 * a) for s, a in zip(summ["seeds"], summ["accs"])]
    L += ["", "- mean %.2f %%, min %.2f %%, max %.2f %% (%d seeds)" % (
        100 * summ["mean"], 100 * summ["min"], 100 * summ["max"], len(summ["seeds"]))]
    if summ["set"] != "test":
        L += ["- **Optimistic:** no test set was used."]
    with open(os.path.join(out_dir, "seeds.md"), "w") as f:
        f.write("\n".join(L) + "\n")


def _selftest():
    """Check the split, grouping, the single scoring of the test set and a full small run.

    Asserts: three-way splits are disjoint and cover everything, groups are disjoint across all three
    sets (subject and session), the splits are deterministic, a stratified split has every class in
    every set, class-missing warnings fire, --hidden 8 is refused, a full run writes every output,
    chooses grouping automatically, scores the test set exactly once with the integer path and
    reaches > 60 % test accuracy (chance 11 %; synthetic data), and --test-frac 0 gives the
    optimistic two-way report.
    Prints "train selftest PASS" and returns 0; returns 1 after printing the reason on failure.
    """
    import synth_dataset
    tmp = tempfile.mkdtemp(prefix="train_selftest_")
    try:
        ds = os.path.join(tmp, "ds.npz")
        np.savez_compressed(ds, **synth_dataset.make_dataset(40, 7))
        d = load_dataset(ds)
        y = d["labels"]
        for gname in ("session", "subject"):
            tr, va, te = split_indices(y, d[gname], 0.2, 0.2, 3)
            gs = [set(d[gname][i]) for i in (tr, va, te)]
            if gs[0] & gs[1] or gs[0] & gs[2] or gs[1] & gs[2] or min(len(tr), len(va), len(te)) == 0:
                print("FAIL grouped (%s) split leaks groups or has an empty set" % gname)
                return 1
            if len(set(tr) | set(va) | set(te)) != len(y) or len(tr) + len(va) + len(te) != len(y):
                print("FAIL grouped split is not a partition")
                return 1
        a = split_indices(y, None, 0.2, 0.2, 5)
        b = split_indices(y, None, 0.2, 0.2, 5)
        if any(not np.array_equal(p, q) for p, q in zip(a, b)):
            print("FAIL split not deterministic")
            return 1
        if any(len(set(y[i])) != N_CLASSES for i in a) or len(set(a[0]) & set(a[1])) or len(set(a[0]) & set(a[2])) or len(set(a[1]) & set(a[2])):
            print("FAIL stratified split: a class is missing or sets overlap")
            return 1
        tr2, va2, te2 = split_indices(y, None, 0.25, 0.0, 5)
        if len(te2) != 0 or len(tr2) + len(va2) != len(y):
            print("FAIL two-way split")
            return 1
        if not missing_class_warnings(y, {"train": np.flatnonzero(y != 3)}) or missing_class_warnings(y, {"train": a[0]}):
            print("FAIL missing-class warning")
            return 1
        if resolve_group(d, None, 0.2)[0] != "subject" or resolve_group(d, "none", 0.2)[0] != "none":
            print("FAIL automatic grouping choice")
            return 1
        try:
            run_training(ds, os.path.join(tmp, "bad"), hidden=8, quiet=True)
            print("FAIL --hidden 8 was not refused")
            return 1
        except TrainError as e:
            if e.code != 2 or "16" not in str(e):
                print("FAIL --hidden refusal wrong: %s" % e)
                return 1
        if abs(summarize_seeds([{"seed": 1, "primary_set": "test", "test": {"int_acc": 0.5}, "val": None},
                                {"seed": 2, "primary_set": "test", "test": {"int_acc": 0.7}, "val": None}])["mean"] - 0.6) > 1e-12:
            print("FAIL seed summary")
            return 1
        # full run; wrap integer_eval to count scorings of the test features
        global integer_eval
        orig = integer_eval
        seen = []
        sp = split_indices(y, d["subject"], 0.2, 0.2, 3)
        test_feats = compute_features(d["windows"])[sp[2]]
        want = hashlib.sha1(np.ascontiguousarray(test_feats).tobytes()).hexdigest()

        def counting(model, feats, labels):
            """Record a hash of the scored features, then call the real integer_eval. Returns its result."""
            seen.append(hashlib.sha1(np.ascontiguousarray(feats).tobytes()).hexdigest())
            return orig(model, feats, labels)
        integer_eval = counting
        try:
            out = os.path.join(tmp, "run")
            rep = run_training(ds, out, seed=3, epochs=40, eval_every=10, patience=4, quiet=True)
        finally:
            integer_eval = orig
        if seen.count(want) != 1:
            print("FAIL test set scored %d times (want exactly 1)" % seen.count(want))
            return 1
        if rep["group"] != "subject" or rep["test"] is None or rep["n_test"] == 0:
            print("FAIL automatic subject grouping or missing test metrics")
            return 1
        for f in ("gesture_model.h", "norm.json", "net.npz", "report.json", "report.md", "split.npz"):
            if not os.path.exists(os.path.join(out, f)):
                print("FAIL missing output %s" % f)
                return 1
        m = infer_ref.load_header(os.path.join(out, "gesture_model.h"))
        if m["GM_N_CLASSES"] != N_CLASSES or m["GM_N_FEATURES"] != N_FEATURES:
            print("FAIL header shape")
            return 1
        if rep["test"]["int_acc"] <= 0.60:
            print("FAIL integer test accuracy %.3f <= 0.60 on synthetic data" % rep["test"]["int_acc"])
            return 1
        with open(os.path.join(out, "report.md")) as f:
            txt = f.read()
        if "TEST set" not in txt or "selection set" not in txt.lower() or "optimistic" not in txt:
            print("FAIL report.md lacks the test / selection-set labels")
            return 1
        rep2 = run_training(ds, os.path.join(tmp, "run2"), seed=3, epochs=20, eval_every=10, patience=4,
                            test_frac=0.0, group="none", quiet=True)
        if rep2["test"] is not None or "OPTIMISTIC" not in open(os.path.join(tmp, "run2", "report.md")).read():
            print("FAIL two-way run is not labelled optimistic")
            return 1
        print("train selftest PASS")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    """CLI entry. Args: argv (list of str or None). Returns: int exit code (0 ok, 2 bad input, 3 exporter refusal by its exit code)."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--data", help="dataset .npz (windows, labels, optional subject, session)")
    ap.add_argument("--out-dir", help="output directory")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--seeds", help="comma list of seeds, e.g. 1,2,3: one run each in OUT_DIR/seed_N plus seeds.md with mean and min/max")
    ap.add_argument("--split-seed", type=int, help="seed of the split (default: the run seed)")
    ap.add_argument("--hidden", type=int, default=N_HIDDEN, help="must be 16 (C4.2, mlp.c static-asserts it)")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--val-frac", type=float, default=0.2)
    ap.add_argument("--test-frac", type=float, default=0.2, help="0 = two-way split, the report is then optimistic")
    ap.add_argument("--group", choices=["subject", "session", "none"], default=None,
                    help="default: automatic (subject, else session, if the dataset has it); none forces a stratified split")
    ap.add_argument("--fallback-set", choices=["val", "test"], default="val",
                    help="set that judges the C4.3 int16 fallback (default val, pending open question Q6)")
    ap.add_argument("--lr", type=float, default=3e-3)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--weight-decay", type=float, default=1e-4)
    ap.add_argument("--k", type=float, default=DEFAULT_K, help="net is trained on x8 / K (default 64)")
    ap.add_argument("--eval-every", type=int, default=5, help="epochs between integer-path candidates")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    if not a.data or not a.out_dir:
        ap.error("--data and --out-dir are required (or use --selftest)")
    common = dict(epochs=a.epochs, val_frac=a.val_frac, test_frac=a.test_frac, group=a.group, k=a.k,
                  eval_every=a.eval_every, fallback_set=a.fallback_set, lr=a.lr, batch=a.batch,
                  weight_decay=a.weight_decay, split_seed=a.split_seed, hidden=a.hidden)
    try:
        if a.seeds:
            try:
                seeds = [int(s) for s in a.seeds.split(",") if s.strip() != ""]
            except ValueError:
                raise TrainError("--seeds must be a comma list of integers, got %r" % a.seeds)
            if not seeds:
                raise TrainError("--seeds is empty")
            reps = [run_training(a.data, os.path.join(a.out_dir, "seed_%d" % s), seed=s, **common) for s in seeds]
            summ = summarize_seeds(reps)
            _write_seeds_summary(a.out_dir, summ)
            print("%d seeds, %s integer accuracy: mean %.2f %%, min %.2f %%, max %.2f %%" % (
                len(seeds), summ["set"], 100 * summ["mean"], 100 * summ["min"], 100 * summ["max"]))
        else:
            run_training(a.data, a.out_dir, seed=a.seed, **common)
    except TrainError as e:
        print("error: %s" % e, file=sys.stderr)
        return e.code
    return 0


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
