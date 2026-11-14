# [AI-GENERATED: Claude Code]
"""Independent oracle for the S1-2 feature extractor, written only from the spec.

Pure Python ints; C semantics (truncating division, 16/32-bit storage) are emulated
explicitly. No floor division or right shift is applied to a negative value.
"""

N_SAMPLES = 150
N_AXES = 3
SEG_LEN = 15
N_SEG = 10
N_FEAT = 60


def trunc_div(a, b):
    """C99 '/' on integers: quotient truncated toward zero.

    Args: a (int) dividend, b (int, nonzero) divisor.
    Returns: int quotient. Uses only non-negative floor division.
    """
    if b == 0:
        raise ZeroDivisionError
    q = abs(a) // abs(b)  # both operands are non-negative here
    if a == 0 or (a < 0) == (b < 0):
        return q
    return -q


def mean_alt(total):
    """Spec's alternative mean: ((uint32)|sum| * 34953) >> 19, sign restored.

    Args: total (int) 15-sample sum. Returns: int mean (truncated toward zero).
    """
    q = ((abs(total) * 34953) & 0xFFFFFFFF) >> 19  # operand is non-negative
    return -q if total < 0 else q


def check_int16(v, what):
    """Assert v fits int16 (emulating the declared storage width).

    Args: v (int), what (str) label. Returns: v. Raises AssertionError on overflow.
    """
    assert -32768 <= v <= 32767, "int16 overflow in %s: %d" % (what, v)
    return v


def segment_features(seg):
    """Mean and energy of one 15-sample segment per the spec.

    Args: seg (sequence of 15 ints in [-2048, 2047]).
    Returns: (mean, energy) as Python ints.
    """
    assert len(seg) == SEG_LEN
    total = check_int16(sum(seg), "sum")
    mean = check_int16(trunc_div(total, 15), "mean")
    acc = 0
    for v in seg:
        d = check_int16(v - mean, "d")
        acc += d * d
        assert acc <= 0xFFFFFFFF, "uint32 overflow"
    e = acc >> 11  # acc >= 0
    energy = e if e < 32767 else 32767
    return mean, energy


def features(window):
    """Compute the 60 features of one window.

    Args: window: 150 rows of 3 ints, window[i][a].
    Returns: list of 60 ints, idx = 20*axis + 2*seg + k (k=0 mean, k=1 energy).
    """
    assert len(window) == N_SAMPLES
    out = [0] * N_FEAT
    for a in range(N_AXES):
        for s in range(N_SEG):
            seg = [window[SEG_LEN * s + j][a] for j in range(SEG_LEN)]
            m, e = segment_features(seg)
            out[20 * a + 2 * s] = m
            out[20 * a + 2 * s + 1] = e
    return out
# [END AI-GENERATED]
