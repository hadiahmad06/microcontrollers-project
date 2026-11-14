# [AI-GENERATED: Claude Code]
"""Spike for C4/C5: integer-only reference path, exporter recipe, and acceptance tests.

Run:  /usr/local/bin/python3.12 quant_ref.py     (needs numpy; exits non-zero on any failure)
Not production code; the production infer_ref.py / exporter should copy these definitions.
"""
import math
import numpy as np

# ----------------------------------------------------------------------------- primitives
def rshift_r(v, s):
    """Round-half-up arithmetic right shift: (v + ((int32)1 << s >> 1)) >> s.

    Args: v (int) value; s (int) shift, 0..14 (firmware limit, see C4 §2). Python >> floors,
    matching XC16 asr. Returns: int.
    """
    assert 0 <= s <= 14
    return (v + ((1 << s) >> 1)) >> s

def sat(v, lo, hi):
    """Clamp v to [lo, hi]. Returns int."""
    return lo if v < lo else hi if v > hi else v

def normalize(x16, off, sh):
    """C4 stage 0. Args: x16 (60 int16), off (int16 per feature), sh (0..14 per feature).
    d = x - off is formed in int32. Returns list of int8 values in [-127,127]."""
    return [sat(rshift_r(int(x) - int(o), int(s)), -127, 127) for x, o, s in zip(x16, off, sh)]

def requant_big(acc, m, sh):
    """Normative requant+ReLU: sat((acc*m + 2^(sh-1)) >> sh, 0, 127). Args: acc int32, m, sh. Returns 0..127."""
    return sat((acc * m + (1 << (sh - 1))) >> sh, 0, 127)

def requant_split(acc, m, sh):
    """int64-free requant mirroring the C in C4 §2 (casts: int32 hi*m, uint32 lo*m).
    Domain: 16<=sh<=31, 2^14<=m<2^15, acc int32. Args/return as requant_big."""
    assert 16 <= sh <= 31 and (1 << 14) <= m < (1 << 15) and -(1 << 31) <= acc < (1 << 31)
    hi = acc >> 16                       # (int16_t)(acc >> 16)
    lo = acc & 0xFFFF                    # (uint16_t)acc
    a = hi * m                           # (int32_t)hi * (int32_t)m
    c = lo * m + (1 << (sh - 1))         # (uint32_t)lo * (uint32_t)m + (1UL << (sh-1))
    assert -(1 << 31) <= a < (1 << 31) and 0 <= c < (1 << 32)
    t = a + (c >> 16)
    assert -(1 << 31) <= t < (1 << 31)
    return sat(t >> (sh - 16), 0, 127)

def dense(x, W, b):
    """int8 dense layer. Args: x (list of ints), W (rows = output neurons), b (int32 biases).
    Returns list of int32 accumulators b[j] + sum_i W[j][i]*x[i] (asserted to fit int32)."""
    out = [int(bj) + sum(int(w) * int(xi) for w, xi in zip(row, x)) for row, bj in zip(W, b)]
    assert all(-(1 << 31) <= v < (1 << 31) for v in out)
    return out

def infer(x16, q):
    """Full integer reference path. Args: x16 (60 int16 features), q (dict from export_quant).
    Returns (x8, logits) with logits int32 list."""
    x8 = normalize(x16, q['off'], q['sh_in'])
    h = [requant_split(a, m, s) for a, m, s in zip(dense(x8, q['W1'], q['b1']), q['M1'], q['SH1'])]
    return x8, dense(h, q['W2'], q['b2'])

def top2(l):
    """Argmax with lowest-index tie-break, and runner-up (also lowest index on ties).
    Args: l (logit list, >=2 entries). Returns (i1, i2); l[i1] >= l[i2]."""
    i1 = 0
    for i in range(1, len(l)):
        if l[i] > l[i1]: i1 = i
    i2 = 1 if i1 == 0 else 0
    for i in range(len(l)):
        if i != i1 and l[i] > l[i2]: i2 = i
    return i1, i2

def confidence(l, conf_shift):
    """C5 D3. Args: l (logits), conf_shift (GM_CONF_SHIFT). Returns (top1 index, uint8 conf)
    with conf = min(255, (l[i1]-l[i2]) >> conf_shift); margin >= 0 so the shift is exact floor."""
    i1, i2 = top2(l)
    return i1, min(255, (l[i1] - l[i2]) >> conf_shift)

# ----------------------------------------------------------------------------- exporter recipe
def mshift(scale):
    """Real requant scale -> (M, SH) with 2^14<=M<2^15, 16<=SH<=31, M*2^-SH ~= scale.
    Args: scale (float > 0). Returns (M, SH). Raises ValueError if the scale is outside
    [2^-17, 0.5) after rounding (exporter must then fail loudly, not clamp)."""
    if not scale > 0:
        raise ValueError("scale must be > 0")
    sh = 16
    while sh <= 31 and scale * (1 << sh) < (1 << 14):
        sh += 1
    if sh > 31:
        raise ValueError("scale %g too small (< 2^-17): SH would exceed 31" % scale)
    m = int(round(scale * (1 << sh)))
    if m >= (1 << 15):
        if sh == 16:
            raise ValueError("scale %g too large (>= ~0.5): SH would be < 16" % scale)
        m, sh = m >> 1, sh - 1                    # only reachable via rounding up to exactly 2^15
        assert m == (1 << 14)
    assert (1 << 14) <= m < (1 << 15) and 16 <= sh <= 31
    return m, sh

def choose_norm(X, nonneg, pct=99.9):
    """Per-feature (off, sh) from training features. Args: X (n x 60 int array), nonneg (bool per
    feature, True for energies: off=0 and range [0,127]), pct (percentile of |x-off| mapped to <=127,
    larger values saturate). off = round(median) for signed features. sh = smallest 0..14 s.t.
    rshift_r(P(|x-off|), s) <= 127. Returns (off list, sh list)."""
    off, sh = [], []
    for i in range(X.shape[1]):
        o = 0 if nonneg[i] else int(round(float(np.median(X[:, i]))))
        p = int(math.ceil(np.percentile(np.abs(X[:, i] - o), pct)))
        s = next((s for s in range(15) if rshift_r(p, s) <= 127), None)
        if s is None:
            raise ValueError("feature %d needs shift > 14" % i)
        off.append(o); sh.append(s)
    return off, sh

def export_quant(W1f, b1f, W2f, b2f, off, sh_in, H_calib, pct=99.9):
    """Quantize a float net defined on the *int8 input domain* x8 (recommended: train on x8).
    Args: W1f/b1f/W2f/b2f float arrays (W1f: 16x60 in x8 units), off/sh_in from choose_norm,
    H_calib (float hidden activations relu(W1f x8 + b1f) on calibration data, for s_h).
    Returns dict q (W1,b1,M1,SH1,W2,b2,off,sh_in,logit_scale); asserts exporter bounds."""
    s_w1 = np.abs(W1f).max() / 127.0
    W1 = np.rint(W1f / s_w1).astype(int)
    b1 = np.rint(b1f / s_w1).astype(np.int64)
    s_h = np.percentile(H_calib, pct) / 127.0
    M, S = mshift(s_w1 / s_h)
    s_w2 = np.abs(W2f).max() / 127.0
    W2 = np.rint(W2f / s_w2).astype(int)
    b2 = np.rint(b2f / (s_h * s_w2)).astype(np.int64)
    q = dict(off=off, sh_in=sh_in, W1=W1.tolist(), b1=b1.tolist(), M1=[M] * len(b1), SH1=[S] * len(b1),
             W2=W2.tolist(), b2=b2.tolist(), logit_scale=s_h * s_w2)
    assert_bounds(q)
    return q

def assert_bounds(q):
    """Exporter checks (C4 §2): |B1|,|B2| < 2^29; worst-case |acc1| and |logit| < 2^30 from the
    weights alone (no data needed), so margins cannot overflow int32. Raises AssertionError."""
    assert all(abs(b) < (1 << 29) for b in q['b1'] + q['b2'])
    for row, b in zip(q['W1'], q['b1']):
        assert abs(b) + 127 * sum(abs(w) for w in row) < (1 << 30)
    for row, b in zip(q['W2'], q['b2']):
        assert abs(b) + 127 * sum(abs(w) for w in row) < (1 << 30)
    assert all(abs(w) <= 127 for r in q['W1'] + q['W2'] for w in r)
    assert all(0 <= s <= 14 for s in q['sh_in'])

# ----------------------------------------------------------------------------- C5 reference
def l1(a, b):
    """L1 distance of two int8 vectors (max 60*254 = 15240, fits uint16). Returns int."""
    return sum(abs(int(x) - int(y)) for x, y in zip(a, b))

def class_radius(vecs, rmin=600, rdef=1200, rmax=4000):
    """C5 D4 per-class acceptance radius. Args: vecs (the class's template x8 vectors).
    <2 templates: rdef. Else clamp(2 * lower-median pairwise L1, rmin, rmax). Constants provisional."""
    if len(vecs) < 2:
        return rdef
    d = sorted(l1(vecs[i], vecs[j]) for i in range(len(vecs)) for j in range(i + 1, len(vecs)))
    return sat(2 * d[(len(d) - 1) // 2], rmin, rmax)

def classify_ref(x8, logits, templates, min_conf, conf_shift, t_ovr=192):
    """C5 normative classify. Args: x8 (60 int8), logits (9 int32), templates (list of (class_id,
    x8vec) in slot order), min_conf (0..255), conf_shift, t_ovr (GESTURE_OVERRIDE_CONF).
    Returns (id, conf): id -1 = GESTURE_UNKNOWN; conf always the winner's score."""
    i1, c = confidence(logits, conf_shift)
    gid = i1
    if templates:
        d = [l1(x8, v) for _, v in templates]
        k = min(range(len(d)), key=lambda i: (d[i], i))          # nearest, lowest slot on ties
        kid, d1 = templates[k][0], d[k]
        others = [d[i] for i in range(len(d)) if templates[i][0] != kid]
        d2 = min(others) if others else None
        ck = 255 if d2 is None else (0 if d2 == 0 else ((d2 - d1) * 255) // d2)
        rad = class_radius([v for cid, v in templates if cid == kid])
        mlp_weak = (i1 == 0) or (c < min_conf) or (c < t_ovr)
        if d1 <= rad and ck >= min_conf and mlp_weak:
            gid, c = kid, ck
    return (gid if c >= min_conf else -1), c

def fallback_needed(n, correct_float, correct_int, agree, z=1.645):
    """C4 D1 criterion. Args: n held-out windows (>=500), counts of correct float / correct int
    predictions, count where float and int argmax agree. Returns True if fall back to int16
    inputs: agreement < 97 % OR (acc drop > 1 pt AND one-sided 95 % Wilson upper bound of int
    accuracy < float accuracy)."""
    assert n >= 500
    p = correct_int / n
    up = (p + z * z / (2 * n) + z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)
    return agree / n < 0.97 or ((correct_float - correct_int) / n > 0.01 and up < correct_float / n)

# ----------------------------------------------------------------------------- tests
def selftest_requant(n=200000, seed=1):
    """Check requant_split == requant_big on n random cases (plus unclamped identity) and
    corner values. Args: n, seed. Raises AssertionError on mismatch."""
    rng = np.random.default_rng(seed)
    corners = [0, 1, -1, 65535, 65536, 65537, -65535, -65536, -65537, 2**31 - 1, -2**31, 2**30, -2**30]
    for acc in corners:
        for m in (1 << 14, (1 << 14) + 1, (1 << 15) - 1, 29100):
            for sh in range(16, 32):
                assert requant_big(acc, m, sh) == requant_split(acc, m, sh), (acc, m, sh)
    for _ in range(n):
        acc = int(rng.integers(-(1 << 31), 1 << 31)) if rng.random() < .5 else int(rng.integers(-(1 << 28), 1 << 28))
        m = int(rng.integers(1 << 14, 1 << 15)); sh = int(rng.integers(16, 32))
        a = (acc >> 16) * m; c = (acc & 0xFFFF) * m + (1 << (sh - 1))
        assert (a + (c >> 16)) >> (sh - 16) == (acc * m + (1 << (sh - 1))) >> sh, (acc, m, sh)
        assert requant_big(acc, m, sh) == requant_split(acc, m, sh)
    print("PASS requant split == bigint (%d random + corners)" % n)

def selftest_mshift(seed=2):
    """Domain tests for mshift: out-of-range scales must raise; in-range must satisfy
    2^14<=M<2^15, 16<=SH<=31, relative error <= 2^-14; rounding-to-2^15 edge handled."""
    for bad in (0.6, 0.99999, 1.5, 3.8e-6, 0.0, -1.0, 0.49999999):
        try:
            mshift(bad); raise SystemExit("mshift(%g) should have raised" % bad)
        except ValueError:
            pass
    for good in (0.4999, 0.25, 1e-4, 7.7e-6, 2.0 ** -17 * 1.0001, 0.5 - 2.0 ** -14):
        m, s = mshift(good)
        assert (1 << 14) <= m < (1 << 15) and 16 <= s <= 31 and abs(m * 2.0 ** -s / good - 1) < 2.0 ** -13, good
    # edge: scale whose M rounds to exactly 2^15 at SH=17 -> M=2^14, SH=16
    m, s = mshift((2 ** 15 - 0.4) / 2 ** 17)
    assert (m, s) == (1 << 14, 16), (m, s)
    rng = np.random.default_rng(seed)
    for sc in np.exp(rng.uniform(math.log(2.0 ** -17 * 1.001), math.log(0.4999), 20000)):
        m, s = mshift(float(sc))
        assert (1 << 14) <= m < (1 << 15) and 16 <= s <= 31 and abs(m * 2.0 ** -s / sc - 1) < 2.0 ** -13
    print("PASS mshift domain (0.6, 0.99999, 1.5, 3.8e-6 rejected; 20000 random in-range)")

def selftest_rshift():
    """rshift_r for s in 0..14 on edge values equals floor((v + 2^(s-1)) / 2^s) via Python //."""
    for s in range(15):
        for v in (-2**17, -65535, -1, 0, 1, 255, 65535, 2**17):
            assert rshift_r(v, s) == (v + ((1 << s) >> 1)) // (1 << s)
    print("PASS rshift_r 0..14")

def selftest_c5():
    """C5 vectors incl. one-learned-class/no-other-class case, override rule, tie-break, reject."""
    x8 = [10] * 60; far = [-100] * 60
    def lg(margin): return [0, 0, 0, margin, 0, 0, 0, 0, 0]   # class 3 wins by `margin`
    T = [(9, [10] * 59 + [14])]                                   # one learned class, d1 = 4
    assert top2([5, 5, 3]) == (0, 1) and top2([1, 5, 5]) == (1, 2)
    assert confidence(lg(900), 1) == (3, 255) and confidence(lg(300), 1) == (3, 150)
    # (a) confident built-in (conf 255) within radius of learned template: MLP must win
    assert classify_ref(x8, lg(900), T, 64, 1) == (3, 255)
    # (b) weak MLP (conf 100 < 192): learned class overrides, c_k = 255 (no other-class template)
    assert classify_ref(x8, lg(200), T, 64, 1) == (9, 255)
    # (c) MLP says class 0 confidently: learned overrides
    assert classify_ref(x8, [900] + [0] * 8, T, 64, 1) == (9, 255)
    # (d) MLP rejected (conf 30 < min_conf 64): learned overrides; with min_conf 0 and conf 30<192 also
    assert classify_ref(x8, lg(60), T, 64, 1) == (9, 255)
    # (e) outside radius: MLP result retained; rejected -> UNKNOWN
    assert classify_ref(far, lg(60), T, 64, 1) == (-1, 30) and classify_ref(far, lg(900), T, 64, 1) == (3, 255)
    # (f) no templates, tie -> margin 0 -> UNKNOWN (min_conf>=1), conf 0
    assert classify_ref(x8, [7] * 9, [], 1, 0) == (-1, 0) and classify_ref(x8, [7] * 9, [], 0, 0) == (0, 0)
    # (g) two learned classes: ratio (d2-d1)*255//d2 ; d1=4, d2=40 -> 229
    T2 = T + [(10, [10] * 56 + [20] * 4)]                        # d = 40 from x8
    assert classify_ref(x8, lg(0), T2, 64, 1) == (9, (36 * 255) // 40)
    # (h) radius rule: <2 templates -> default; tight cluster floors at rmin
    assert class_radius([x8]) == 1200 and class_radius([x8, x8, x8]) == 600
    assert class_radius([x8, [10] * 59 + [200]]) == 600            # 2*190 = 380 -> floored to rmin
    assert class_radius([x8, [10] * 56 + [110] * 4]) == 800        # 2*400
    # (i) fallback criterion
    assert not fallback_needed(600, 540, 540, 600) and fallback_needed(600, 540, 500, 570)
    print("PASS C5 classify/override/radius/fallback vectors")

def synth(n, rng, nonneg):
    """Synthetic C3-like features (60 int16): signed means with non-zero per-feature mean, and
    heavy-tailed non-negative energies. Args: n windows, rng, nonneg mask. Returns n x 60 int array."""
    mu = rng.uniform(-1500, 1500, 60); sd = rng.uniform(100, 500, 60)
    X = mu + sd * rng.standard_normal((n, 60))
    E = np.exp(rng.normal(6.0, 1.2, (n, 60))) * rng.uniform(0.3, 3, 60)
    X = np.where(nonneg, E, X)
    return np.clip(np.rint(X), -32768, 32767).astype(np.int64)

def demo(n_cal=1500, n_test=1000, seed=0, min_agree=0.97):
    """Acceptance test (finding 1/15). Non-zero-mean synthetic features -> int8 x8 (choose_norm) ->
    random float net trained-on-x8 stand-in -> export_quant -> integer path. Prints and asserts
    float-vs-int argmax agreement >= min_agree over n_test windows, for (A) the recommended
    float net defined on x8 and (B) the fold alternative: a float net on raw x folded with
    b1' = b1 + sum_i W1_i*off_i and W1' = W1*2^s_i (correct sign). Returns (agreeA, agreeB)."""
    rng = np.random.default_rng(seed)
    nonneg = np.array([i % 2 == 1 for i in range(60)])              # C3: odd = energy, even = mean
    X = synth(n_cal + n_test, rng, nonneg); Xc, Xt = X[:n_cal], X[n_cal:]
    off, sh = choose_norm(Xc, nonneg)
    x8c = np.array([normalize(r, off, sh) for r in Xc]); x8t = np.array([normalize(r, off, sh) for r in Xt])
    NH, NC = 16, 9
    res = []
    for name in ("A: float net on x8", "B: raw-x net, folded"):
        if name[0] == "A":
            W1 = rng.standard_normal((NH, 60)) * (1.0 / 64) * 0.8; b1 = rng.standard_normal(NH) * .3
            W1e, b1e = W1, b1
        else:
            W1r = rng.standard_normal((NH, 60)) * (0.8 / 64) / (2.0 ** np.array(sh)); b1 = rng.standard_normal(NH) * .3
            W1e = W1r * 2.0 ** np.array(sh)                          # x = off + 2^s*x8
            b1e = b1 + W1r @ np.array(off)                           # PLUS sign (review finding 1)
        W2 = rng.standard_normal((NC, NH)) * 1.5; b2 = rng.standard_normal(NC) * .3
        Hc = np.maximum(W1e @ x8c.T + b1e[:, None], 0)
        q = export_quant(W1e, b1e, W2, b2, off, sh, Hc)
        agree = 0
        for r, x8 in zip(Xt, x8t):
            if name[0] == "A":
                lf = W2 @ np.maximum(W1e @ x8 + b1e, 0) + b2
            else:
                lf = W2 @ np.maximum(W1r @ r + b1, 0) + b2           # genuinely the raw-x float net
            agree += top2(list(lf))[0] == top2(infer(r, q)[1])[0]
        res.append(agree / n_test)
        print("demo %-22s float-vs-int argmax agreement %d/%d = %.1f%%" % (name, agree, n_test, 100 * agree / n_test))
    assert min(res) >= min_agree, res
    # sanity: the WRONG fold sign must fail the same test (guards the acceptance test itself)
    W1r = rng.standard_normal((NH, 60)) * (0.8 / 64) / (2.0 ** np.array(sh)); b1 = rng.standard_normal(NH) * .3
    W1e = W1r * 2.0 ** np.array(sh); bad = b1 - W1r @ np.array(off)
    Hc = np.maximum(W1e @ x8c.T + bad[:, None], 0); W2 = rng.standard_normal((NC, NH)) * 1.5; b2 = rng.standard_normal(NC) * .3
    qb = export_quant(W1e, bad, W2, b2, off, sh, Hc)
    ag = sum(top2(list(W2 @ np.maximum(W1r @ r + b1, 0) + b2))[0] == top2(infer(r, qb)[1])[0] for r in Xt[:300]) / 300
    print("demo wrong-sign fold agreement %.1f%% (must be < threshold)" % (100 * ag))
    assert ag < min_agree
    return res

if __name__ == "__main__":
    selftest_requant(); selftest_mshift(); selftest_rshift(); selftest_c5()
    demo()
    print("ALL PASS")
# [END AI-GENERATED]
