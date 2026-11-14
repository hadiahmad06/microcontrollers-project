# [AI-GENERATED: Claude Code]
"""Integer-only reference for the C3 feature extraction (bit-exact with features.c).

No floats, no Python // or >> on possibly-negative values: C semantics are
emulated with explicit helpers.
"""

WINDOW_LEN = 150
AXES = 3
SEG_LEN = 15
SEGMENTS = 10
ENERGY_SHIFT = 11   # default shift for ENERGY_MODE 0
ENERGY_MODE = 0     # 0 shift+saturate, 1 isqrt(SS), 2 isqrt(SS/15); must match FEAT_ENERGY_MODE in features.h
X_MIN, X_MAX = -2048, 2047
INT16_MIN, INT16_MAX = -32768, 32767


def c_div_trunc(a, b):
    """C99 integer division: truncate toward zero.

    a: int dividend; b: int non-zero divisor. Returns the int quotient.
    """
    q = abs(a) // abs(b)  # operands non-negative here, so // is exact
    return q if (a >= 0) == (b > 0) else -q


def shr_nonneg(v, n):
    """Right shift of a NON-NEGATIVE value (the only case the spec uses).

    v: int >= 0; n: int shift count. Returns v >> n. Raises on negative v.
    """
    if v < 0:
        raise ValueError("shr_nonneg called with negative value")
    return v >> n


def check_int16(v, what):
    """Assert v fits int16 (mirrors the C int16 intermediates). Returns v."""
    if not (INT16_MIN <= v <= INT16_MAX):
        raise OverflowError("%s=%d does not fit int16" % (what, v))
    return v


def mean_mulshift(s):
    """Alternative mean: (|s|*34953)>>19 with sign restored. Returns int.

    s: int segment sum in [-30720, 30705]. Equivalent to c_div_trunc(s, 15).
    """
    a = abs(s)
    q = shr_nonneg(a * 34953, 19)
    return -q if s < 0 else q


def isqrt32(n):
    """Exact floor(sqrt(n)) by the same digit-by-digit loop as features.c.

    n: int in [0, 2**32). Returns int r with r*r <= n < (r+1)*(r+1).
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
            res = shr_nonneg(res, 1) + bit
        else:
            res = shr_nonneg(res, 1)
        bit >>= 2
    return res


def scale_energy(acc, mode=None, shift=None):
    """Scale the sum of squared deviations to the int16 energy feature.

    acc: int >= 0 (< 2**32). mode: 0 shift+saturate, 1 isqrt(acc), 2 isqrt(acc/15
    truncated); None selects ENERGY_MODE. shift: used by mode 0, None selects
    ENERGY_SHIFT. Returns int in [0, 32767].
    """
    mode = ENERGY_MODE if mode is None else mode
    shift = ENERGY_SHIFT if shift is None else shift
    if mode == 0:
        return min(shr_nonneg(acc, shift), 32767)
    if mode == 1:
        return isqrt32(acc)
    if mode == 2:
        return isqrt32(acc // 15)  # acc >= 0, so // equals C truncation
    raise ValueError("bad energy mode")


def extract(window, mode=None, shift=None):
    """Compute the 60 integer features of a window.

    window: sequence of 150 samples, each a sequence of 3 ints (X, Y, Z) in
    [-2048, 2047]. mode/shift: energy scaling, see scale_energy (None = module
    defaults). Returns list of 60 ints, index = 20*axis + 2*seg + k with
    k=0 mean (trunc toward zero of sum/15) and k=1 energy = scale_energy of
    sum((x-mean)^2).
    """
    if len(window) != WINDOW_LEN:
        raise ValueError("window must have 150 samples")
    out = [0] * (AXES * SEGMENTS * 2)
    for a in range(AXES):
        for s in range(SEGMENTS):
            seg = [int(window[SEG_LEN * s + j][a]) for j in range(SEG_LEN)]
            for v in seg:
                if not (X_MIN <= v <= X_MAX):
                    raise ValueError("sample %d out of 12-bit range" % v)
            total = check_int16(sum(seg), "sum")
            mean = check_int16(c_div_trunc(total, 15), "mean")
            acc = 0
            for v in seg:
                d = check_int16(v - mean, "dev")
                acc += d * d
            if acc >= 2 ** 32:
                raise OverflowError("acc overflow")
            e = scale_energy(acc, mode, shift)
            idx = 20 * a + 2 * s
            out[idx] = mean
            out[idx + 1] = e
    return out
# [END AI-GENERATED]
