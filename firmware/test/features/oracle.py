# [AI-GENERATED: Claude Code]
"""oracle.py - independent oracle for contract C3 (features), written from the spec only.

Spec (energy mode = isqrt): for axis a in 0..2 and segment s in 0..9 (samples 15s..15s+14):
    sum = sum of x; mean = trunc_div(sum, 15); SS = sum((x - mean)^2); energy = isqrt(SS)
    out[20a + 2s] = mean; out[20a + 2s + 1] = energy.
Also holds the window generators (xorshift32 + fixed edge windows) that MUST match
test_features.c exactly. Uses Python's math.isqrt and its own truncating division.
"""
import math

from ss_table import SS_TABLE

SUMS = [-1, -14, -15, -16, -29, -30, -31, 1, 14, 15, 16, 29, 30, 31]
N_EDGE_FIXED = 7
N_EDGE = N_EDGE_FIXED + len(SS_TABLE) + len(SUMS)
LO, HI = -2048, 2047


def tdiv(a, b):
    """Division truncating toward zero (C99 '/').

    Args:
        a: dividend. b: non-zero divisor.
    Returns:
        q = floor(|a|/|b|), negated when the signs differ.
    """
    q = abs(a) // abs(b)
    return q if (a == 0 or (a < 0) == (b < 0)) else -q


def expected(window):
    """Compute the 60 features of one window.

    Args:
        window: 150 rows of 3 ints, each in [-2048, 2047].
    Returns:
        list of 60 ints, index 20*axis + 2*seg + k (k=0 mean, k=1 energy).
    """
    assert len(window) == 150
    out = [0] * 60
    for a in range(3):
        for s in range(10):
            seg = [window[15 * s + j][a] for j in range(15)]
            assert all(LO <= v <= HI for v in seg)
            mean = tdiv(sum(seg), 15)
            ss = sum((v - mean) * (v - mean) for v in seg)
            out[20 * a + 2 * s] = mean
            out[20 * a + 2 * s + 1] = math.isqrt(ss)
    return out


class Rng:
    """xorshift32 (shifts 13, 17, 5), identical to test_features.c."""

    def __init__(self, seed):
        """Args: seed - 32-bit seed (0 becomes 1)."""
        self.s = (seed & 0xFFFFFFFF) or 1

    def next(self):
        """Return the next 32-bit value."""
        x = self.s
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self.s = x
        return x


def edge_window(e):
    """Build fixed edge window number e (see test_features.c fill_edge).

    Args:
        e: 0 .. N_EDGE-1.
    Returns:
        150 x 3 list of ints.
    """
    nt = len(SS_TABLE)
    w = []
    for i in range(150):
        row = []
        for a in range(3):
            j, s = i % 15, i // 15
            if e == 0:
                v = -2048
            elif e == 1:
                v = 2047
            elif e == 2:
                v = 0
            elif e == 3:
                v = -2048 if j % 2 == 0 else 2047
            elif e == 4:
                v = 2047 if j % 2 == 0 else -2048
            elif e == 5:
                v = (-2048, 2047, 0)[a]
            elif e == 6:
                v = ((i * 37 + a * 101) % 4096) - 2048
            elif e < N_EDGE_FIXED + nt:
                v = SS_TABLE[((e - N_EDGE_FIXED) + 5 * a + s) % nt][j]
            else:
                t = e - N_EDGE_FIXED - nt
                v = SUMS[(t + a + s) % len(SUMS)] if j == 0 else 0
            row.append(v)
        w.append(row)
    return w


def random_window(rng, w):
    """Build pseudo-random window number w, drawing from rng (see test_features.c fill_random).

    Args:
        rng: Rng instance, advanced in place. w: window number (mode = w % 4).
    Returns:
        150 x 3 list of ints.
    """
    mode = w & 3
    c = 0
    if mode == 3:
        c = ((rng.next() >> 8) & 0x7FF) - 1024
    win = []
    for _ in range(150):
        row = []
        for _a in range(3):
            r = rng.next()
            if mode == 0:
                v = ((r >> 8) & 0xFFF) - 2048
            elif mode == 1:
                v = ((r >> 8) & 0x1F) - 16
            elif mode == 2:
                v = 2047 if (r >> 16) & 1 else -2048
            else:
                v = max(LO, min(HI, c + ((r >> 8) & 0x3FF) - 512))
            row.append(v)
        win.append(row)
    return win
# [END AI-GENERATED]
