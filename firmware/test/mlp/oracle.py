# [AI-GENERATED: Claude Code]
"""oracle.py - independent Python oracle for the MLP (contract C4 section 2), written from the
spec only. Python ints are unbounded, so there is no overflow anywhere: this is the "exact math"
the C code must reproduce. Also holds the xorshift32 PRNG that the C driver mirrors exactly."""

N_FEATURES, N_HIDDEN, N_CLASSES = 60, 16, 9
M32 = 0xFFFFFFFF


def to_s32(v):
    """Reinterpret an unsigned 32-bit value as signed (two's complement).

    Args: v: integer, taken modulo 2^32.
    Returns: the value in -2^31..2^31-1."""
    v &= M32
    return v - (1 << 32) if v >= (1 << 31) else v


def to_s16(v):
    """Reinterpret an unsigned 16-bit value as signed.

    Args: v: integer, taken modulo 2^16.
    Returns: the value in -32768..32767."""
    v &= 0xFFFF
    return v - 65536 if v >= 32768 else v


class XorShift32:
    """xorshift32 (13,17,5), identical to the C driver's rng()."""

    def __init__(self, seed):
        """Args: seed: non-zero 32-bit seed."""
        assert seed & M32
        self.s = seed & M32

    def next(self):
        """Advance the generator. Returns: next unsigned 32-bit value."""
        x = self.s
        x ^= (x << 13) & M32
        x ^= x >> 17
        x ^= (x << 5) & M32
        self.s = x
        return x


def rshift_r(v, s):
    """RSHIFT_R(v, s) = (v + ((1<<s)>>1)) >> s, flooring shift (s in 0..14; s==0 returns v).

    Args: v: integer; s: shift. Returns: rounded shifted value."""
    assert 0 <= s <= 14
    return (v + ((1 << s) >> 1)) >> s


def sat(v, lo, hi):
    """SAT(v, lo, hi) = min(max(v, lo), hi). Returns: clamped value."""
    return min(max(v, lo), hi)


def requant(acc, m, sh):
    """SAT(RSHIFT_R64(acc*m, sh), 0, 127) on the exact product, valid 2^14<=m<2^15, 16<=sh<=31.

    Args: acc: int32 accumulator; m: multiplier; sh: shift. Returns: int8 activation 0..127."""
    p = acc * m
    return sat((p + (1 << (sh - 1))) >> sh, 0, 127)


def normalize(model, feat):
    """Stage 0. Args: model: sidecar dict; feat: 60 int16. Returns: list of 60 x8 values."""
    return [sat(rshift_r(f - o, s), -127, 127)
            for f, o, s in zip(feat, model["in_off"], model["in_sh"])]


def layer1(model, x8):
    """Layer 1. Args: model, x8. Returns: (acc1[16], h[16])."""
    acc = [model["b1"][j] + sum(w * x for w, x in zip(model["w1"][j], x8))
           for j in range(N_HIDDEN)]
    h = [requant(a, model["m1"][j], model["sh1"][j]) for j, a in enumerate(acc)]
    return acc, h


def layer2(model, h):
    """Layer 2 (int32, no requant). Args: model, h. Returns: logits[9]."""
    return [model["b2"][c] + sum(w * x for w, x in zip(model["w2"][c], h))
            for c in range(N_CLASSES)]


def top2(logits):
    """Argmax with lowest-index ties; margin to best other class (lowest index ties).

    Args: logits. Returns: (top1, margin)."""
    t1 = 0
    for c in range(1, len(logits)):
        if logits[c] > logits[t1]:
            t1 = c
    t2 = None
    for c in range(len(logits)):
        if c != t1 and (t2 is None or logits[c] > logits[t2]):
            t2 = c
    return t1, logits[t1] - logits[t2]


def forward(model, feat):
    """Full forward pass. Args: model, feat. Returns: dict of every stage."""
    x8 = normalize(model, feat)
    acc1, h = layer1(model, x8)
    lg = layer2(model, h)
    t1, mg = top2(lg)
    return {"x8": x8, "acc1": acc1, "h": h, "logits": lg, "top1": t1, "margin": mg}


def random_features(model, seed, n):
    """Features of the C driver's random vectors (mirrors gen_feat() in driver.c).

    Per feature: r1=next; if r1&3==0 uniform int16 from r1>>16; else r2=next, a value near
    IN_OFF: t=(r2>>16)%321-160 in x8 units, frac = ((r1>>2)&0x3FFF)&(2^sh-1), d = t*2^sh +
    frac - 2^sh/2, x = clamp(off + d). Args: model: sidecar; seed; n: vector count.
    Returns: list of n feature lists."""
    g = XorShift32(seed)
    out = []
    for _ in range(n):
        f = []
        for i in range(N_FEATURES):
            r1 = g.next()
            if (r1 & 3) == 0:
                v = to_s16(r1 >> 16)
            else:
                r2 = g.next()
                sc = 1 << model["in_sh"][i]
                t = (r2 >> 16) % 321 - 160
                frac = ((r1 >> 2) & 0x3FFF) & (sc - 1)
                v = sat(model["in_off"][i] + t * sc + frac - (sc >> 1), -32768, 32767)
            f.append(v)
        out.append(f)
    return out


REQ_SEED = 0x9E3779B9
REQ_ACC_FIXED = [-(1 << 31), (1 << 31) - 1, 0, 1, -1, 65535, -65535, 65536, -65536, 65537, -65537]
REQ_M_FIXED = [16384, 16385, 32767]
REQ_SH_FIXED = [16, 17, 30, 31]


def requant_sweep():
    """The requant sweep the C driver prints (mirrors the loops in driver.c).

    acc: fixed list, 6 random int32, 6 random int32 >> (r%31); m: fixed + 2 random in
    16384..32767; sh: fixed + 2 random in 16..31. Returns: list of (acc, m, sh, expected)."""
    g = XorShift32(REQ_SEED)
    accs = list(REQ_ACC_FIXED)
    for _ in range(6):
        accs.append(to_s32(g.next()))
    for _ in range(6):
        a = to_s32(g.next())
        k = g.next() % 31
        accs.append(a >> k)
    ms = list(REQ_M_FIXED)
    for _ in range(2):
        ms.append(16384 + g.next() % 16384)
    shs = list(REQ_SH_FIXED)
    for _ in range(2):
        shs.append(16 + g.next() % 16)
    return [(a, m, s, requant(a, m, s)) for a in accs for m in ms for s in shs]
# [END AI-GENERATED]
