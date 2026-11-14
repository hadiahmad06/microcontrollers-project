# [AI-GENERATED: Claude Code]
"""Spike for C4/C5: integer-only reference path + quantization math (numpy only for the demo).
Run: python3.12 quant_ref.py   -> prints PASS lines.  Not production code."""
import numpy as np

def rshift_r(v, s):
    """Round-half-up arithmetic right shift: (v + (1<<s>>1)) >> s. Python >> floors == XC16 asr."""
    return (v + ((1 << s) >> 1)) >> s

def sat(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

def normalize(x16, off, sh):
    """x16: 60 int16 -> 60 int8.  (x-off) computed in int32 (can exceed int16)."""
    return [sat(rshift_r(int(x) - int(o), int(s)), -127, 127) for x, o, s in zip(x16, off, sh)]

def requant_big(acc, m, sh):
    """Normative definition: ReLU fused, result in [0,127]. Unbounded ints (== int64 in C)."""
    return sat((acc * m + (1 << (sh - 1))) >> sh, 0, 127)

def requant_split(acc, m, sh):
    """int64-free version for XC16. Needs 16<=sh<=31, 0<m<2^15, acc int32."""
    assert 16 <= sh <= 31 and 0 < m < (1 << 15) and -(1 << 31) <= acc < (1 << 31)
    hi = acc >> 16                 # int16 (arithmetic)
    lo = acc & 0xFFFF              # uint16
    a = hi * m                     # int32:  |a| <= 2^30
    b = lo * m                     # uint32 < 2^31
    c = b + (1 << (sh - 1))        # uint32 (<= 2^31 + 2^30)
    assert c < (1 << 32) and -(1 << 31) <= a + (c >> 16) < (1 << 31)
    r = (a + (c >> 16)) >> (sh - 16)
    return sat(r, 0, 127)

def dense(x, W, b):
    return [int(bj) + sum(int(w) * int(xi) for w, xi in zip(row, x)) for row, bj in zip(W, b)]

def infer(x16, q):
    x = normalize(x16, q['off'], q['sh_in'])
    a1 = dense(x, q['W1'], q['b1'])
    h = [requant_split(a, m, s) for a, m, s in zip(a1, q['M1'], q['SH1'])]
    return dense(h, q['W2'], q['b2'])          # int32 logits

def top2(l):
    i1 = 0
    for i in range(1, len(l)):
        if l[i] > l[i1]: i1 = i                 # strict > : lowest index wins ties
    i2 = 1 if i1 == 0 else 0
    for i in range(len(l)):
        if i != i1 and l[i] > l[i2]: i2 = i
    return i1, i2

def confidence(l, conf_shift):
    i1, i2 = top2(l)
    return i1, min(255, (l[i1] - l[i2]) >> conf_shift)   # margin >= 0 so >> is exact floor

def mshift(scale):
    """real multiplier -> (M in [2^14,2^15), SH) with M*2^-SH ~= scale."""
    sh = 15
    while scale * (1 << sh) < (1 << 14): sh += 1
    m = int(round(scale * (1 << sh)))
    if m == (1 << 15): m >>= 1; sh -= 1
    return m, sh

def selftest_requant(n=200000, seed=1):
    rng = np.random.default_rng(seed)
    for _ in range(n):
        acc = int(rng.integers(-(1 << 31), 1 << 31)) if rng.random() < .5 else int(rng.integers(-(1 << 28), 1 << 28))
        m = int(rng.integers(1 << 14, 1 << 15)); sh = int(rng.integers(16, 32))
        big = (acc * m + (1 << (sh - 1))) >> sh
        a = (acc >> 16) * m; c = (acc & 0xFFFF) * m + (1 << (sh - 1))
        assert (a + (c >> 16)) >> (sh - 16) == big, (acc, m, sh)   # unclamped equality
        assert requant_big(acc, m, sh) == requant_split(acc, m, sh)
    print("PASS requant split == bigint (%d cases)" % n)

def demo(seed=0):
    rng = np.random.default_rng(seed)
    NF, NH, NC = 60, 16, 9
    X = (rng.standard_normal((500, NF)) * rng.uniform(50, 4000, NF)).astype(np.int32).clip(-32768, 32767)
    W1f = rng.standard_normal((NH, NF)) * 0.3; b1f = rng.standard_normal(NH) * .1
    W2f = rng.standard_normal((NC, NH)) * 0.5; b2f = rng.standard_normal(NC) * .1
    off = np.round(X.mean(0)).astype(int)
    amax = np.abs(X - off).max(0)
    sh_in = np.array([max(0, int(np.ceil(np.log2(a / 127.0 + 1e-9)))) for a in amax])
    xin = np.array([[sat(rshift_r(int(x) - int(o), int(s)), -127, 127) for x, o, s in zip(r, off, sh_in)] for r in X])
    s_x = 2.0 ** sh_in                                # real x ~= x8 * 2^sh (centered)
    # fold per-feature input scale into W1 so int8 inputs are the layer input
    W1e = W1f * s_x
    sw1 = np.abs(W1e).max() / 127; W1 = np.round(W1e / sw1).astype(int)
    b1 = np.round((b1f - (W1f * off).sum(1)) / sw1).astype(np.int64)   # bias in acc scale (s_in==1 after folding)
    h_real = np.maximum(W1e @ xin.T + (b1f - (W1f * off).sum(1))[:, None], 0)
    sh_h = np.percentile(h_real, 99.9) / 127.0
    M1, SH1 = zip(*[mshift(sw1 / sh_h)] * NH)
    sw2 = np.abs(W2f).max() / 127; W2 = np.round(W2f / sw2).astype(int)
    b2 = np.round(b2f / (sh_h * sw2)).astype(np.int64)
    q = dict(off=off, sh_in=sh_in, W1=W1, b1=b1, M1=M1, SH1=SH1, W2=W2, b2=b2)
    agree = 0
    for r in X[:200]:
        l = infer(r, q)
        xf = (r - off) ; hf = np.maximum(W1f @ r + b1f, 0); lf = W2f @ hf + b2f
        agree += int(np.argmax(lf)) == top2(l)[0]
    print("demo: int vs float argmax agreement %d/200 (random net, informational)" % agree)
    print("demo: M1=%d SH1=%d  max|acc1|<2^31 ok" % (M1[0], SH1[0]))

if __name__ == "__main__":
    selftest_requant()
    assert top2([5, 5, 3])[0] == 0 and top2([1, 5, 5])[0] == 1          # tie -> lowest index
    assert confidence([0, 300, 100], 1) == (1, 100) and confidence([0, 900, 0], 1) == (1, 255)
    print("PASS argmax tie-break / confidence saturation")
    demo()
# [END AI-GENERATED]
