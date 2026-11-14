# [AI-GENERATED: Claude Code]
"""Exporter: float network -> gesture_model.h (contract C4 section 2 "Exporter recipe", steps 1-6).

Two subcommands:
  export_model.py norm   --features calib.npy --out norm.json
      Per-feature input normalisation (C4 D1b): GM_IN_OFF / GM_IN_SH from raw int16 calibration
      features.  Run this FIRST: training must use exactly these offsets/shifts (the float net is
      trained on x8 = normalize(features), optionally divided by a conditioning constant K).
  export_model.py header --weights net.npz --norm norm.json --calib calib.npy
                         [--val val.npy --val-labels y.npy] [--k K] [--conf-shift N]
                         [--default-reject N] --out gesture_model.h
      net.npz holds W1 [16,60], b1 [16], W2 [9,16], b2 [9] (and optionally scalar K).  The
      exporter does NO offset fold: the net was trained on x8 (/K), so W1_x8 = W1 / K.

Every value written is produced by the recipe and checked against the C4 bounds; a violation
exits non-zero (code 3) with a message naming the bound.  Nothing is ever clamped.

Sources: our own executable spec docs/agent/hadi/spikes/quant/quant_ref.py (mshift, choose_norm,
export_quant, assert_bounds are promoted from it); quantization scheme of Jacob et al., 2018,
arXiv:1712.05877 (int8 weights in [-127,127], int32 bias, fixed-point multiplier M * 2^-SH).
"""
import argparse
import json
import math
import os
import sys
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_ref  # noqa: E402  (C3: NONNEG, FEATURES_VERSION; B3 says the exporter reads them)
import infer_ref  # noqa: E402  (integer reference path, used to pick GM_CONF_SHIFT)


class BoundError(Exception):
    """Raised when a C4 exporter bound is violated; the message names the bound."""


def _need(cond, bound, detail):
    """Raise BoundError naming `bound` unless cond (explicit raise, so it also holds under python -O).

    Args: cond (bool); bound (str, the named C4 bound); detail (str). Returns: None."""
    if not cond:
        raise BoundError("%s violated: %s" % (bound, detail))


def feature_defs():
    """C3 feature definitions the exporter depends on (read from tools/features_ref.py, never
    hard-coded).

    Args: none. Returns: (nonneg, version): nonneg is a list of 60 bools (True = non-negative
    energy feature, offset 0), version is features_ref.FEATURES_VERSION. Raises BoundError if
    len(NONNEG) != 60.
    """
    _need(len(features_ref.NONNEG) == 60, "len(NONNEG) == 60", "len(NONNEG) = %d" % len(features_ref.NONNEG))
    return list(features_ref.NONNEG), features_ref.FEATURES_VERSION


def check_norm(off, sh, n_features):
    """Validate a norm.json pair (C4: GM_IN_OFF int16, GM_IN_SH in 0..14, one entry per feature).

    Args: off, sh (lists from norm.json); n_features (int, columns of the net). Returns: None.
    Raises BoundError naming the bound (explicit checks, independent of assert / python -O).
    """
    _need(isinstance(off, list) and isinstance(sh, list) and len(off) == n_features and len(sh) == n_features,
          "len(GM_IN_OFF) == len(GM_IN_SH) == GM_N_FEATURES",
          "norm.json has %s offsets and %s shifts, net has %d features"
          % (len(off) if isinstance(off, list) else "?", len(sh) if isinstance(sh, list) else "?", n_features))
    for i, (o, s_) in enumerate(zip(off, sh)):
        _need(isinstance(o, int) and not isinstance(o, bool) and isinstance(s_, int) and not isinstance(s_, bool),
              "GM_IN_OFF / GM_IN_SH are integers", "feature %d: off=%r sh=%r" % (i, o, s_))
        _need(-32768 <= o <= 32767, "GM_IN_OFF in int16", "feature %d off=%d" % (i, o))
        _need(0 <= s_ <= 14, "GM_IN_SH <= 14", "feature %d sh=%d" % (i, s_))


# --------------------------------------------------------------------------- recipe pieces
def mshift(scale):
    """Real requant scale -> (M, SH) with 2^14 <= M < 2^15, 16 <= SH <= 31, M * 2^-SH ~= scale.

    Args: scale (float > 0). Returns: (M, SH) ints. Raises BoundError unless the scale is in
    [2^-17, 0.5) (also after rounding M up to 2^15 at SH == 16).
    """
    _need(math.isfinite(scale) and scale > 0, "scale in [2^-17, 0.5)", "scale %r is not a positive number" % (scale,))
    sh = 16
    while sh <= 31 and scale * (1 << sh) < (1 << 14):
        sh += 1
    _need(sh <= 31, "scale in [2^-17, 0.5)", "scale %g < 2^-17 (SH would exceed 31)" % scale)
    m = int(round(scale * (1 << sh)))
    if m >= (1 << 15):
        _need(sh > 16, "scale in [2^-17, 0.5)", "scale %g >= 0.5 (SH would be < 16)" % scale)
        m, sh = m >> 1, sh - 1  # only reachable via rounding up to exactly 2^15
        _need(m == (1 << 14), "2^14 <= M < 2^15", "M=%d after halving" % m)
    _need((1 << 14) <= m < (1 << 15), "2^14 <= M < 2^15", "M=%d" % m)
    _need(16 <= sh <= 31, "16 <= SH <= 31", "SH=%d" % sh)
    return m, sh


def choose_norm(X, nonneg, pct=99.9):
    """Per-feature (off, sh) from calibration features (C4 D1b).

    Args: X (n x F integer array of raw int16 features); nonneg (bool per feature; True gives
    off = 0, False gives off = round(median)); pct (percentile of |x - off| that must map to
    <= 127; larger values saturate). Returns: (off list, sh list); sh_i is the smallest s in 0..14
    with RSHIFT_R(ceil(P(|x-off|)), s) <= 127. Raises BoundError if no s <= 14 works.
    """
    off, sh = [], []
    for i in range(X.shape[1]):
        o = 0 if nonneg[i] else int(round(float(np.median(X[:, i]))))
        _need(-32768 <= o <= 32767, "GM_IN_OFF in int16", "feature %d offset %d" % (i, o))
        p = int(math.ceil(np.percentile(np.abs(X[:, i].astype(np.int64) - o), pct)))
        s = next((s for s in range(15) if infer_ref.rshift_r(p, s) <= 127), None)
        _need(s is not None, "GM_IN_SH <= 14", "feature %d needs a shift above 14" % i)
        off.append(o)
        sh.append(s)
    return off, sh


def _as_int_features(a, name):
    """Validate a calibration/validation feature array. Args: a (ndarray); name (str).
    Returns: int64 ndarray [n, F] of int16-range values. Raises ValueError otherwise."""
    a = np.asarray(a)
    if a.ndim != 2:
        raise ValueError("%s must be 2-D [windows, features]" % name)
    if not np.issubdtype(a.dtype, np.integer):
        if not np.all(np.isfinite(a)) or not np.array_equal(a, np.rint(a)):
            raise ValueError("%s must hold integers (C3 int16 features)" % name)
    a = a.astype(np.int64)
    if a.min() < -32768 or a.max() > 32767:
        raise ValueError("%s has values outside int16" % name)
    return a


def quantize(W1, b1, W2, b2, K, off, sh, x8_calib):
    """C4 exporter recipe steps 2-6 on a float net defined on the training input x8 / K.

    Args: W1 [H,F], b1 [H], W2 [C,H], b2 [C] (float arrays); K (float > 0, W1 is multiplied
    by 1/K so the net acts on x8: W1_x8 = W1 / K); off, sh (lists from choose_norm); x8_calib
    (n x F int array: normalized calibration windows, for s_h). Returns: dict with GM_* arrays as
    nested int lists, plus logit_scale (float, real value of one logit LSB). Raises BoundError.
    """
    W1 = np.asarray(W1, dtype=np.float64) / K
    b1 = np.asarray(b1, dtype=np.float64)
    W2 = np.asarray(W2, dtype=np.float64)
    b2 = np.asarray(b2, dtype=np.float64)
    for n, a in (("W1", W1), ("b1", b1), ("W2", W2), ("b2", b2)):
        _need(np.all(np.isfinite(a)), "finite weights", "%s has NaN/inf" % n)
    _need(np.abs(W1).max() > 0 and np.abs(W2).max() > 0, "non-zero weights", "W1 or W2 is all zero")
    _need(all(0 <= s <= 14 for s in sh), "GM_IN_SH <= 14", "sh=%s" % sh)
    # step 2
    s_w1 = np.abs(W1).max() / 127.0
    W1q = np.rint(W1 / s_w1)
    b1r = np.rint(b1 / s_w1)
    # step 3
    H = np.maximum(W1 @ np.asarray(x8_calib, dtype=np.float64).T + b1[:, None], 0.0)
    p_h = np.percentile(H, 99.9)
    _need(p_h > 0, "s_h > 0", "calibration hidden activations are all zero")
    s_h = p_h / 127.0
    # step 4: per-channel (M1, SH1); the recipe's scale is common, so entries are equal
    M, S = mshift(s_w1 / s_h)
    # step 5
    s_w2 = np.abs(W2).max() / 127.0
    W2q = np.rint(W2 / s_w2)
    b2r = np.rint(b2 / (s_h * s_w2))
    for lname, br in (("layer 1", b1r), ("layer 2", b2r)):
        _need(np.all(np.abs(br) < (1 << 29)), "|B| < 2^29", "%s max |bias| = %.6g" % (lname, float(np.abs(br).max())))
    for j in np.flatnonzero(~np.any(W1q != 0, axis=1)):  # I1: dead neuron (scale is per tensor, no bound applies)
        print("warning: W1 row %d is all zero after quantization (dead hidden neuron)" % j, file=sys.stderr)
    q = {"GM_IN_OFF": [int(v) for v in off], "GM_IN_SH": [int(v) for v in sh],
         "GM_W1": W1q.astype(np.int64).tolist(), "GM_B1": b1r.astype(np.int64).tolist(),
         "GM_M1": [M] * W1q.shape[0], "GM_SH1": [S] * W1q.shape[0],
         "GM_W2": W2q.astype(np.int64).tolist(), "GM_B2": b2r.astype(np.int64).tolist(),
         "logit_scale": float(s_h * s_w2)}
    check_bounds(q)
    return q


def check_bounds(q):
    """C4 step 6 bounds on a quantized model dict. Args: q (dict with GM_* lists). Returns: None.
    Raises BoundError naming the violated bound."""
    for name in ("GM_W1", "GM_W2"):
        for row in q[name]:
            for w in row:
                _need(-127 <= w <= 127, "weights in [-127, 127]", "%s element %d" % (name, w))
    for name, W, B in (("layer 1", q["GM_W1"], q["GM_B1"]), ("layer 2", q["GM_W2"], q["GM_B2"])):
        for j, (row, b) in enumerate(zip(W, B)):
            _need(abs(b) < (1 << 29), "|B| < 2^29", "%s bias[%d] = %d" % (name, j, b))
            worst = abs(b) + 127 * sum(abs(w) for w in row)
            _need(worst < (1 << 30), "|B| + 127*sum|W| < 2^30", "%s row %d worst case %d" % (name, j, worst))
    for m_, s_ in zip(q["GM_M1"], q["GM_SH1"]):
        _need((1 << 14) <= m_ < (1 << 15), "2^14 <= M < 2^15", "M=%d" % m_)
        _need(16 <= s_ <= 31, "16 <= SH <= 31", "SH=%d" % s_)
    for s_ in q["GM_IN_SH"]:
        _need(0 <= s_ <= 14, "GM_IN_SH <= 14", "SH_in=%d" % s_)
    for o in q["GM_IN_OFF"]:
        _need(-32768 <= o <= 32767, "GM_IN_OFF in int16", "off=%d" % o)


def model_hash(q):
    """CRC-32 IEEE over the little-endian bytes of all arrays in file order (C4.3).
    Args: q (dict with GM_* lists). Returns: int uint32."""
    return infer_ref.model_hash(q)


def choose_conf_shift(margins):
    """C5 rule: smallest shift s with P95(margins of correct validation windows) >> s <= 255.

    Args: margins (non-empty list of int margins of correctly classified windows). Returns: int.
    P95 is the nearest-rank value sorted[ceil(0.95*n)-1] (integers only). Raises BoundError if the
    shift would exceed 24.
    """
    _need(len(margins) > 0, "validation windows", "no correctly classified validation window")
    srt = sorted(margins)
    p95 = srt[(95 * len(srt) + 99) // 100 - 1]
    s = next(s for s in range(0, 64) if (p95 >> s) <= 255)
    _need(s <= 24, "GM_CONF_SHIFT <= 24", "needed shift %d (P95 margin %d)" % (s, p95))
    return s


def choose_default_reject(confs, max_share_pct=2):
    """C5.2 rule for GM_DEFAULT_REJECT: the threshold min_conf (reject iff conf < min_conf) that
    rejects at most `max_share_pct` % of the held-out true gestures.

    Exact definition: with the n confidences sorted ascending as c[0..n-1] and
    k = floor(n * max_share_pct / 100), min_conf = c[k]. Then #{conf < min_conf} <= k, so the
    rejected share is <= max_share_pct %, and min_conf + 1 would reject at least k + 1 windows
    (so this is the tightest such threshold; the literal "smallest" value would be 0, which rejects
    nothing, so the rule is read as the largest threshold within the budget).

    Args: confs (non-empty list of int MLP confidences 0..255 of held-out true-gesture windows,
    label != 0); max_share_pct (int percent budget, default 2). Returns: (min_conf, rejected)
    with rejected the number of windows with conf < min_conf. Raises BoundError if confs is empty.
    """
    _need(len(confs) > 0, "validation windows", "no held-out true-gesture window (label != 0)")
    srt = sorted(confs)
    k = len(srt) * max_share_pct // 100
    mc = srt[k]
    return mc, sum(1 for c in srt if c < mc)


def fallback_needed(n, correct_float, correct_int, agree, z=1.645):
    """C4.3 criterion (ported from quant_ref.py): fall back to int16 inputs iff agreement < 97 % or
    (accuracy drop > 1 pt and the one-sided 95 % Wilson upper bound of the int accuracy < float accuracy).

    Args: n (held-out windows, >= 500); correct_float, correct_int (counts of correct predictions);
    agree (count where float and int argmax agree); z (1.645 for one-sided 95 %).
    Returns: bool.
    """
    p = correct_int / n
    up = (p + z * z / (2 * n) + z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)
    return agree / n < 0.97 or ((correct_float - correct_int) / n > 0.01 and up < correct_float / n)


# --------------------------------------------------------------------------- header text
def _c32(v):
    """int32 C literal portable to 16-bit int. Args: v (int). Returns: str."""
    if v == -(1 << 31):
        return "(-2147483647L - 1L)"
    return "%dL" % v


def _c16(v):
    """int16 C literal (INT16_MIN-safe). Args: v (int). Returns: str."""
    return "(-32767 - 1)" if v == -32768 else "%d" % v


def _fmt_1d(vals, conv, indent="    ", width=100):
    """Wrap a 1-D initializer. Args: vals (ints), conv (int -> str), indent, width. Returns: str."""
    lines, cur = [], indent
    for k, v in enumerate(vals):
        tok = conv(v) + ("," if k < len(vals) - 1 else "")
        if len(cur) + len(tok) + 1 > width and cur.strip():
            lines.append(cur.rstrip())
            cur = indent
        cur += tok + " "
    lines.append(cur.rstrip())
    return "\n".join(lines)


def _fmt_2d(rows, conv):
    """Initializer with one braced row per line. Args: rows (list of lists), conv. Returns: str."""
    return "\n".join("    { %s }%s" % (", ".join(conv(v) for v in r), "," if i < len(rows) - 1 else "")
                     for i, r in enumerate(rows))


def render_header(q, conf_shift, default_reject, logit_q32, odr_hz=100, range_g=4,
                  n_samples=150, feature_version=None, provisional=False):
    """Render gesture_model.h text per the C4 header layout.

    Args: q (checked model dict); conf_shift (0..24); default_reject (0..255); logit_q32 (int,
    round(real logit LSB * 2^32)); odr_hz, range_g, n_samples (macros); feature_version (macro;
    None = features_ref.FEATURES_VERSION); provisional (bool: True marks GM_CONF_SHIFT and
    GM_DEFAULT_REJECT with the comment `PROVISIONAL: no validation data`).
    Returns: str (the full file).
    """
    if feature_version is None:
        feature_version = features_ref.FEATURES_VERSION
    prov = " /* PROVISIONAL: no validation data */" if provisional else ""
    nh, nf = len(q["GM_W1"]), len(q["GM_W1"][0])
    nc = len(q["GM_W2"])
    h = model_hash(q)
    u = lambda n, v, c: "#define %-19s %-16s /* %s */" % (n, "%du" % v, c)  # noqa: E731
    L = [
        "/* gesture_model.h : GENERATED by tools/export_model.py. DO NOT EDIT. */",
        "// [AI-GENERATED: Claude Code]",
        "#ifndef GESTURE_MODEL_H",
        "#define GESTURE_MODEL_H",
        "#include <stdint.h>",
        "",
        u("GM_FORMAT_VERSION", 1, "layout of this file; bump on any change"),
        u("GM_N_FEATURES", nf, "C3 feature vector length"),
        u("GM_N_HIDDEN", nh, "hidden neurons"),
        u("GM_N_CLASSES", nc, "ids 0..8 (see C5)"),
        u("GM_ODR_HZ", odr_hz, "sensor config the model was trained at"),
        u("GM_RANGE_G", range_g, "full scale in g"),
        u("GM_N_SAMPLES", n_samples, "capture window length (C1)"),
        u("GM_FEATURE_VERSION", feature_version, "C3 feature-definition version"),
        "#define GM_MODEL_HASH       0x%08XUL       /* CRC-32 (IEEE) over the little-endian bytes of all arrays below, in file order */" % h,
        u("GM_CONF_SHIFT", conf_shift, "C5: conf = min(255, margin >> GM_CONF_SHIFT)") + prov,
        u("GM_DEFAULT_REJECT", default_reject, "C5: default min_conf") + prov,
        "#define GM_LOGIT_SCALE_Q32  %dUL       /* info: real logit LSB * 2^32 */" % logit_q32,
        "",
        "/* XC16 v2.10 is GCC 4.5-based: _Static_assert is NOT supported; use this. */",
        "#define GM_STATIC_ASSERT(c, name) typedef char gm_sa_##name[(c) ? 1 : -1]",
        "GM_STATIC_ASSERT(GM_N_CLASSES <= 16u, classes);",
        "GM_STATIC_ASSERT(GM_CONF_SHIFT <= 24u, conf_shift);",
        "",
        "/* x8 = SAT(RSHIFT_R(x - GM_IN_OFF[i], GM_IN_SH[i]), -127, 127); energies (odd index): offset 0 */",
        "static const int16_t GM_IN_OFF[GM_N_FEATURES] = {",
        _fmt_1d(q["GM_IN_OFF"], _c16),
        "};",
        "static const uint8_t GM_IN_SH [GM_N_FEATURES] = {",
        _fmt_1d(q["GM_IN_SH"], lambda v: "%du" % v),
        "};",
        "",
        "/* W1[hidden][feature], row-major, one row = one neuron, int8 in [-127,127] */",
        "static const int8_t   GM_W1 [GM_N_HIDDEN][GM_N_FEATURES] = {",
        _fmt_2d(q["GM_W1"], lambda v: "%d" % v),
        "};",
        "static const int32_t  GM_B1 [GM_N_HIDDEN] = {",
        _fmt_1d(q["GM_B1"], _c32),
        "};",
        "static const uint16_t GM_M1 [GM_N_HIDDEN] = {   /* 2^14 <= M < 2^15 */",
        _fmt_1d(q["GM_M1"], lambda v: "%du" % v),
        "};",
        "static const uint8_t  GM_SH1[GM_N_HIDDEN] = {   /* 16 <= SH <= 31 */",
        _fmt_1d(q["GM_SH1"], lambda v: "%du" % v),
        "};",
        "",
        "static const int8_t   GM_W2[GM_N_CLASSES][GM_N_HIDDEN] = {",
        _fmt_2d(q["GM_W2"], lambda v: "%d" % v),
        "};",
        "static const int32_t  GM_B2[GM_N_CLASSES] = {",
        _fmt_1d(q["GM_B2"], _c32),
        "};",
        "",
        "#endif",
        "// [END AI-GENERATED]",
        "",
    ]
    return "\n".join(L)


# --------------------------------------------------------------------------- commands
def cmd_norm(args):
    """`norm` subcommand: write norm.json from calibration features.

    Args: args (Namespace with features, out, percentile). Returns: None. Raises BoundError /
    ValueError (mapped to exit 3 / 2 by main)."""
    nonneg, version = feature_defs()
    X = _as_int_features(np.load(args.features), "--features")
    if X.shape[1] != len(nonneg):
        raise ValueError("--features has %d columns, features_ref.NONNEG has %d" % (X.shape[1], len(nonneg)))
    off, sh = choose_norm(X, nonneg, args.percentile)
    with open(args.out, "w") as f:
        json.dump({"n_features": X.shape[1], "percentile": args.percentile, "nonneg": nonneg,
                   "feature_version": version, "off": off, "sh": sh}, f)
    print("norm: %d features, %d windows -> %s (max shift %d)" % (X.shape[1], X.shape[0], args.out, max(sh)))


def cmd_header(args):
    """`header` subcommand: quantize, check bounds, write gesture_model.h.

    Args: args (Namespace of the header options). Returns: None. Raises BoundError (exit 3) on any
    bound violation and ValueError / KeyError / OSError (exit 2) on unusable input."""
    _nonneg, fversion = feature_defs()
    if args.feature_version is not None:
        _need(args.feature_version == fversion, "GM_FEATURE_VERSION == features_ref.FEATURES_VERSION",
              "--feature-version %d, features_ref says %d" % (args.feature_version, fversion))
    net = np.load(args.weights)
    K = float(net["K"]) if "K" in net.files else 1.0
    if args.k is not None:
        if "K" in net.files and abs(K - args.k) > 0:
            raise ValueError("--k %g conflicts with K=%g in the npz" % (args.k, K))
        K = args.k
    if not (math.isfinite(K) and K > 0):
        raise ValueError("K must be a positive number")
    with open(args.norm) as f:
        nj = json.load(f)
    off, sh = nj["off"], nj["sh"]
    if "feature_version" in nj:
        _need(nj["feature_version"] == fversion, "GM_FEATURE_VERSION == features_ref.FEATURES_VERSION",
              "norm.json was made for feature version %r, features_ref says %d" % (nj["feature_version"], fversion))
    W1, b1, W2, b2 = (net[k] for k in ("W1", "b1", "W2", "b2"))
    H, F, C = W1.shape[0], W1.shape[1], W2.shape[0]
    if not (W1.shape == (H, F) and b1.shape == (H,) and W2.shape == (C, H) and b2.shape == (C,)):
        raise ValueError("inconsistent weight shapes W1%s b1%s W2%s b2%s" % (W1.shape, b1.shape, W2.shape, b2.shape))
    check_norm(off, sh, F)  # BEFORE any normalize(): a bad norm must be exit 3, not a traceback
    _need(C <= 16, "GM_N_CLASSES <= 16", "%d classes" % C)
    calib = _as_int_features(np.load(args.calib), "--calib")
    if calib.shape[1] != F:
        raise ValueError("--calib has %d features, net has %d" % (calib.shape[1], F))
    nm = {"GM_IN_OFF": off, "GM_IN_SH": sh}
    x8c = np.array([infer_ref.normalize(r, nm) for r in calib])
    q = quantize(W1, b1, W2, b2, K, off, sh, x8c)
    logit_q32 = int(round(q["logit_scale"] * 2.0 ** 32))
    if logit_q32 >= 2 ** 32:  # info-only macro, not a C4 bound: saturate it and say so
        print("warning: GM_LOGIT_SCALE_Q32 saturated to 0xFFFFFFFF (logit LSB >= 1.0 real unit; info-only macro)",
              file=sys.stderr)
        logit_q32 = 2 ** 32 - 1
    default_reject = 64 if args.default_reject is None else args.default_reject
    _need(0 <= default_reject <= 255, "GM_DEFAULT_REJECT in 0..255", "value %d" % default_reject)
    conf_shift = args.conf_shift
    provisional = args.val is None
    if args.val is not None:
        if args.val_labels is None:
            raise ValueError("--val needs --val-labels")
        V = _as_int_features(np.load(args.val), "--val")
        y = np.load(args.val_labels).astype(np.int64)
        if V.shape[0] != y.shape[0] or V.shape[1] != F:
            raise ValueError("--val/--val-labels shape mismatch")
        # integer path on the quantized model (hash/CLI fields are not needed for the stages)
        mm = dict(q, GM_CONF_SHIFT=0)
        ok, ok_f, agree, margins, rows = 0, 0, 0, [], []
        for r, lab in zip(V, y):
            res = infer_ref.forward(r, mm)
            x8 = np.array(res["x8"], dtype=np.float64)
            lf = (W2 @ np.maximum((W1 / K) @ x8 + b1, 0.0)) + b2
            agree += int(np.argmax(lf)) == res["top1"]
            ok_f += int(np.argmax(lf)) == lab
            rows.append((int(lab), res["margin"]))
            if res["top1"] == lab:
                ok += 1
                margins.append(res["margin"])
        conf_shift = choose_conf_shift(margins)
        print("val: %d windows, int accuracy %.1f%%, float-vs-int argmax agreement %.1f%%, GM_CONF_SHIFT=%d"
              % (len(y), 100.0 * ok / len(y), 100.0 * agree / len(y), conf_shift))
        if len(y) < 500:
            print("warning: only %d validation windows (< 500): the C4.3 int8-vs-int16 fallback criterion cannot be assessed"
                  % len(y), file=sys.stderr)
        elif fallback_needed(len(y), ok_f, ok, agree):
            print("warning: C4.3 fallback criterion is MET (agreement < 97 %% or significant accuracy drop): "
                  "consider int16 inputs (option d)", file=sys.stderr)
        if args.default_reject is None:
            confs = [infer_ref.mlp_conf(mg, conf_shift) for lab, mg in rows if lab != 0]
            default_reject, nrej = choose_default_reject(confs)
            print("val: GM_DEFAULT_REJECT=%d chosen by the C5.2 rule: rejects %d of %d held-out true gestures "
                  "(%.2f %%, budget 2 %%)" % (default_reject, nrej, len(confs), 100.0 * nrej / len(confs)))
    else:
        print("warning: no validation data; GM_CONF_SHIFT=%d and GM_DEFAULT_REJECT=%d are PROVISIONAL defaults"
              % (conf_shift, default_reject), file=sys.stderr)
    _need(0 <= conf_shift <= 24, "GM_CONF_SHIFT <= 24", "value %d" % conf_shift)
    _need(0 <= default_reject <= 255, "GM_DEFAULT_REJECT in 0..255", "value %d" % default_reject)
    text = render_header(q, conf_shift, default_reject, logit_q32, args.odr_hz, args.range_g,
                         args.n_samples, fversion, provisional)
    infer_ref.parse_header(text)  # round-trip: shapes, ranges and GM_MODEL_HASH must parse back
    with open(args.out, "w") as f:
        f.write(text)
    print("header: %s written (GM_MODEL_HASH 0x%08X, hidden %d, classes %d)" % (args.out, model_hash(q), H, C))


def main(argv=None):
    """CLI entry. Args: argv (list or None). Returns: process exit code (0 ok, 2 bad input, 3 bound violation).
    A violation of any C4 bound prints a message naming the bound to stderr and never a traceback."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("norm", help="compute GM_IN_OFF / GM_IN_SH from calibration features")
    n.add_argument("--features", required=True, help=".npy [n,60] raw int16 features")
    n.add_argument("--out", required=True, help="norm.json")
    n.add_argument("--percentile", type=float, default=99.9)
    h = sub.add_parser("header", help="quantize a float net and write gesture_model.h")
    h.add_argument("--weights", required=True, help=".npz with W1,b1,W2,b2 (optional K)")
    h.add_argument("--norm", required=True, help="norm.json from the norm subcommand")
    h.add_argument("--calib", required=True, help=".npy raw features used to set the hidden scale")
    h.add_argument("--val", help=".npy raw validation features")
    h.add_argument("--val-labels", help=".npy integer class labels for --val")
    h.add_argument("--k", type=float, help="conditioning constant: net trained on x8 / K")
    h.add_argument("--conf-shift", type=int, default=6, help="used only without --val (provisional)")
    h.add_argument("--default-reject", type=int, default=None,
                   help="GM_DEFAULT_REJECT; default: chosen by the C5.2 rule with --val, else provisional 64")
    h.add_argument("--odr-hz", type=int, default=100)
    h.add_argument("--range-g", type=int, default=4)
    h.add_argument("--n-samples", type=int, default=150)
    h.add_argument("--feature-version", type=int, default=None,
                   help="must equal features_ref.FEATURES_VERSION (default)")
    h.add_argument("--out", required=True, help="gesture_model.h")
    args = ap.parse_args(argv)
    try:
        (cmd_norm if args.cmd == "norm" else cmd_header)(args)
    except BoundError as e:
        print("export_model: BOUND VIOLATION: %s" % e, file=sys.stderr)
        return 3
    except (ValueError, KeyError, OSError) as e:
        print("export_model: error: %s" % e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
