# [AI-GENERATED: Claude Code]
"""Window generators for the features QA (independent of the implementer's generator).

A window is a list of 150 [x, y, z] rows. Groups are lists of (label, window).
"""
import math
import random

LO, HI = -2048, 2047


def clamp(v):
    """Clamp v to the legal sample range. Args: v (int). Returns: int in [-2048, 2047]."""
    return LO if v < LO else HI if v > HI else v


def from_axes(cols):
    """Interleave three 150-long axis lists into a window.

    Args: cols: 3 lists of 150 ints. Returns: list of 150 [x,y,z] rows.
    """
    return [[cols[0][i], cols[1][i], cols[2][i]] for i in range(150)]


def segment_with_sum(rng, total):
    """Random 15-sample segment, all in range, summing exactly to total.

    Args: rng (random.Random), total (int in [-30720, 30705]).
    Returns: list of 15 ints.
    """
    seg = [LO] * 15
    rem = total - 15 * LO  # distribute 0..30705+30720 on top of -2048
    order = list(range(15))
    rng.shuffle(order)
    mode = rng.randrange(3)
    if mode == 0:  # greedy in random order (extreme, spiky)
        for i in order:
            add = min(rem, HI - LO)
            seg[i] += add
            rem -= add
    else:  # random-weighted spread, then greedy fix-up
        while rem > 0:
            i = rng.randrange(15)
            room = HI - seg[i]
            if room == 0:
                continue
            add = min(rem, room, rng.randint(1, 600) if mode == 1 else room)
            seg[i] += add
            rem -= add
    assert sum(seg) == total and all(LO <= v <= HI for v in seg)
    return seg


def window_from_segments(segs):
    """Assemble a window from 30 segments.

    Args: segs: 30 lists of 15 ints, index 10*axis+seg. Returns: window.
    """
    cols = []
    for a in range(3):
        col = []
        for s in range(10):
            col.extend(segs[10 * a + s])
        cols.append(col)
    return from_axes(cols)


def g_uniform(rng, n):
    """Uniform random full-range windows. Args: rng, n. Returns: [(label, window)]."""
    return [("uniform", [[rng.randint(LO, HI) for _ in range(3)] for _ in range(150)])
            for _ in range(n)]


def g_boundary(rng, n):
    """Values within a few LSB of +/-2048 limits, mixed. Args: rng, n."""
    pool = [LO, LO + 1, LO + 2, LO + 5, HI, HI - 1, HI - 2, HI - 5, 0, -1, 1]
    out = []
    for _ in range(n):
        p = rng.choice([0.5, 0.9, 1.0])
        w = [[rng.choice(pool) if rng.random() < p else rng.randint(LO, HI)
              for _ in range(3)] for _ in range(150)]
        out.append(("boundary", w))
    return out


def g_constant(rng, n):
    """Constant segments (energy 0), random or extreme levels. Args: rng, n."""
    out = []
    for _ in range(n):
        segs = []
        for _ in range(30):
            c = rng.choice([LO, HI, 0, -1, 1, rng.randint(LO, HI)])
            segs.append([c] * 15)
        out.append(("constant", window_from_segments(segs)))
    return out


def g_spike(rng, n):
    """Single-sample spike at every position of a segment, all segments/axes.

    Args: rng, n (windows; position cycles through 0..14). Returns list.
    """
    out = []
    for k in range(n):
        segs = []
        for si in range(30):
            base = rng.choice([0, LO, HI, rng.randint(LO, HI)])
            seg = [base] * 15
            pos = (k + si) % 15 if k < 15 else rng.randrange(15)
            seg[pos] = rng.choice([LO, HI, clamp(base + rng.choice([-1, 1]))])
            segs.append(seg)
        out.append(("spike", window_from_segments(segs)))
    return out


def g_sum_multiples(rng, n):
    """Segments whose sum is 15k, 15k+/-1 (pos/neg), 15k+14 etc. Args: rng, n."""
    out = []
    for _ in range(n):
        segs = []
        for _ in range(30):
            k = rng.randint(-2048, 2047)
            t = 15 * k + rng.choice([0, 1, -1, 14, -14, 7, -7])
            t = max(-30720, min(30705, t))
            segs.append(segment_with_sum(rng, t))
        out.append(("summult", window_from_segments(segs)))
    return out


def g_sum_extremes(rng, n):
    """Segments with sum -30720, +30705 and neighbours. Args: rng, n."""
    vals = [-30720, -30719, -30706, -30705, 30705, 30704, 30691, 30690, 0, 1, -1]
    out = []
    for _ in range(n):
        segs = [segment_with_sum(rng, rng.choice(vals)) for _ in range(30)]
        out.append(("sumext", window_from_segments(segs)))
    return out


def g_alternating(rng, n):
    """Maximal-variance patterns: +/- extremes at various splits/phases. Args: rng, n."""
    out = []
    for _ in range(n):
        segs = []
        for _ in range(30):
            style = rng.randrange(4)
            if style == 0:  # strict alternation
                ph = rng.randrange(2)
                seg = [HI if (j + ph) % 2 else LO for j in range(15)]
            elif style == 1:  # k high, rest low, shuffled
                k = rng.randint(0, 15)
                seg = [HI] * k + [LO] * (15 - k)
                rng.shuffle(seg)
            elif style == 2:  # 7/8 split (max variance region)
                seg = [HI] * 7 + [LO] * 8
                if rng.random() < 0.5:
                    seg = [HI] * 8 + [LO] * 7
                rng.shuffle(seg)
            else:  # near-extremes alternating with jitter
                seg = [clamp((HI if j % 2 else LO) + rng.randint(-3, 3)) for j in range(15)]
            segs.append(seg)
        out.append(("alternate", window_from_segments(segs)))
    return out


def sinusoid_window(rng, amp, noise=2):
    """Realistic smooth motion: per-axis sinusoid (1..5 cycles/window) + offset + noise.

    Args: rng, amp (peak LSB), noise (peak LSB noise). Returns: window.
    """
    cols = []
    for _ in range(3):
        cyc = rng.uniform(1.0, 5.0)
        ph = rng.uniform(0, 2 * math.pi)
        off = rng.randint(-1000, 1000)
        a = amp * rng.uniform(0.3, 1.0)
        cols.append([clamp(int(round(off + a * math.sin(2 * math.pi * cyc * i / 150 + ph)))
                           + rng.randint(-noise, noise)) for i in range(150)])
    return from_axes(cols)


def g_sinusoid(rng, n, amp):
    """n sinusoid windows at amplitude amp. Args: rng, n, amp."""
    return [("sin%d" % amp, sinusoid_window(rng, amp)) for _ in range(n)]


def g_exhaustive_sums():
    """Windows covering every 15-sample sum -30720..30705 (30 per window).

    Returns: (windows, expected_sums) where expected_sums[w] lists 30 sums
    in segment order 10*axis+seg.
    """
    rng = random.Random(7771)
    sums = list(range(-30720, 30706))
    while len(sums) % 30:
        sums.append(rng.randint(-30720, 30705))
    wins, exp = [], []
    for i in range(0, len(sums), 30):
        chunk = sums[i:i + 30]
        wins.append(window_from_segments([segment_with_sum(rng, t) for t in chunk]))
        exp.append(chunk)
    return wins, exp
# [END AI-GENERATED]
