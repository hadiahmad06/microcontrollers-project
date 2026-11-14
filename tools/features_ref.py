# [AI-GENERATED: Claude Code]
"""Integer-only reference for the C3 feature extraction (bit-exact with firmware/src/features.c).

Only the decided energy mode is implemented: energy = isqrt(sum of squared deviations).
Adapted from our own spike docs/agent/hadi/spikes/features/features_ref.py.
No floats; C semantics (truncating division) are emulated with explicit helpers.
"""

import sys

FEATURES_VERSION = 1   # must equal FEATURES_VERSION in features.h
FEAT_COUNT = 60
WINDOW_LEN = 150
AXES = 3
SEG_LEN = 15
SEGMENTS = 10
X_MIN, X_MAX = -2048, 2047
INT16_MIN, INT16_MAX = -32768, 32767

# Non-negative flag per feature index (B3): odd index = energy = True; even = mean = False.
NONNEG = [(i & 1) == 1 for i in range(FEAT_COUNT)]


def c_div_trunc(a, b):
    """C99 integer division: truncate toward zero.

    a: int dividend; b: int non-zero divisor. Returns the int quotient.
    """
    q = abs(a) // abs(b)  # operands non-negative here, so // is exact
    return q if (a >= 0) == (b > 0) else -q


def isqrt32(n):
    """Exact floor(sqrt(n)) by the same digit-by-digit loop as features.c.

    n: int in [0, 2**32). Returns int r with r*r <= n < (r+1)*(r+1).
    Raises ValueError if n is outside the uint32 range.
    """
    if not (0 <= n < 2 ** 32):
        raise ValueError("isqrt32 argument out of uint32 range")
    res = 0
    bit = 1 << 30
    while bit > n:
        bit >>= 2
    while bit != 0:
        if n >= res + bit:
            n -= res + bit
            res = (res >> 1) + bit   # res >= 0, so >> is a plain logical shift
        else:
            res >>= 1
        bit >>= 2
    return res


def _check_int16(v, what):
    """Assert v fits int16 (mirrors the C int16 intermediates). Returns v."""
    if not (INT16_MIN <= v <= INT16_MAX):
        raise OverflowError("%s=%d does not fit int16" % (what, v))
    return v


def features_extract(window):
    """Compute the 60 integer features of a window.

    window: sequence of 150 samples, each a sequence of 3 ints (X, Y, Z) in
    [-2048, 2047]. Returns a list of 60 ints, index = 20*axis + 2*seg + k with
    k=0 mean (trunc toward zero of sum/15) and k=1 energy = isqrt(sum((x-mean)^2)).
    Raises ValueError for a wrong window length, a bad sample row, or a value
    outside [-2048, 2047].
    """
    if len(window) != WINDOW_LEN:
        raise ValueError("window must have 150 samples")
    for row in window:
        if len(row) != AXES:
            raise ValueError("each sample must have 3 axes")
        for v in row:
            if not (X_MIN <= v <= X_MAX):
                raise ValueError("sample %d out of 12-bit range" % v)
    out = [0] * FEAT_COUNT
    for a in range(AXES):
        for s in range(SEGMENTS):
            seg = [int(window[SEG_LEN * s + j][a]) for j in range(SEG_LEN)]
            total = _check_int16(sum(seg), "sum")
            mean = _check_int16(c_div_trunc(total, 15), "mean")
            acc = 0
            for v in seg:
                d = _check_int16(v - mean, "dev")
                acc += d * d
            idx = 20 * a + 2 * s
            out[idx] = mean
            out[idx + 1] = isqrt32(acc)
    return out


def _selftest():
    """Check isqrt32 against math.isqrt on >= 100000 values; print PASS, return 0 (1 on failure)."""
    import math
    import random
    rng = random.Random(12345)
    vals = [0, 1, 2, 3, 2 ** 32 - 1, 2 ** 31, 2 ** 30]
    for k in range(0, 65536, 7):
        vals.extend([k * k, k * k + 1])
        if k > 0:
            vals.append(k * k - 1)
    vals.extend([65535 * 65535, 65535 * 65535 - 1, 65535 * 65535 + 1])
    vals.extend(rng.randrange(0, 2 ** 32) for _ in range(50000))
    vals.extend(rng.randrange(0, 62604361) for _ in range(30000))
    vals = [v for v in vals if 0 <= v < 2 ** 32]
    assert len(vals) >= 100000, len(vals)
    for v in vals:
        if isqrt32(v) != math.isqrt(v):
            print("FAIL isqrt32(%d)" % v)
            return 1
    assert c_div_trunc(-7, 2) == -3 and c_div_trunc(7, -2) == -3 and c_div_trunc(0, 5) == 0
    assert features_extract([[0, 0, 0]] * 150) == [0] * 60
    assert NONNEG[1] and not NONNEG[0] and len(NONNEG) == 60
    print("features_ref selftest PASS")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        sys.exit(_selftest())
    print("usage: features_ref.py --selftest")
    sys.exit(2)
# [END AI-GENERATED]
