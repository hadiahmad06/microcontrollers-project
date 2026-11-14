# [AI-GENERATED: Claude Code]
"""Write test windows (raw little-endian int16, 450 values/window) to a file."""
import sys
import numpy as np

N_UNIFORM = 4000
N_SMOOTH = 4000
N_SEGEXT = 2000
N_MIXED = 2000
SEED = 2361


def edge_cases():
    """Return a list of (150,3) int16 arrays covering hand-picked extremes."""
    w = []
    full = lambda v: np.full((150, 3), v, dtype=np.int16)
    w += [full(-2048), full(2047), full(0), full(-1), full(1)]
    alt = np.zeros((150, 3), dtype=np.int16)
    alt[0::2] = -2048
    alt[1::2] = 2047
    w.append(alt)
    w.append((-alt - 1).astype(np.int16))
    # spikes: one sample at each extreme at several positions/axes
    for v in (-2048, 2047):
        for pos in (0, 14, 15, 74, 75, 149):
            for ax in range(3):
                z = np.zeros((150, 3), dtype=np.int16)
                z[pos, ax] = v
                w.append(z)
    # worst-case energy: 7/8 extremes split in every segment
    for lo_n in (7, 8):
        seg = np.array([-2048] * lo_n + [2047] * (15 - lo_n), dtype=np.int16)
        z = np.tile(seg, 10)[:, None].repeat(3, axis=1)
        w.append(z.astype(np.int16))
    # every sum residue mod 15 around zero: ramps
    for k in range(-8, 9):
        z = np.zeros((150, 3), dtype=np.int16)
        z[:, 0] = k
        z[:, 1] = -k
        z[:, 2] = np.tile(np.arange(15) - 7 + k, 10)
        w.append(z)
    return w


def spike_sweep():
    """Windows whose segments are one spike of height h (0..4095) above a base of
    -2048 or below a base of 2047; sweeping h crosses every energy scaling boundary
    (shift 6/7/8 saturation, isqrt steps). Returns a list of (150,3) int16 arrays."""
    segs = []
    for h in range(4096):
        a = np.full(15, -2048, dtype=np.int16)
        a[7] = -2048 + h
        b = np.full(15, 2047, dtype=np.int16)
        b[3] = 2047 - h
        segs += [a, b]
    while len(segs) % 30:
        segs.append(np.zeros(15, dtype=np.int16))
    return [np.concatenate(segs[i:i + 30]).reshape(3, 150).T.astype(np.int16)
            for i in range(0, len(segs), 30)]


def boundary_hunt():
    """Segments whose sum of squared deviations (SS) lands exactly on, or nearest to,
    each boundary: acc>>s crossing 32767 for s in 6,7,8, and k^2-1, k^2 for several k
    (isqrt step edges). Family: base -2048 with two samples raised by h1, h2.
    Returns a list of (150,3) int16 arrays (30 hit segments per window)."""
    targets = []
    for sh in (6, 7, 8):
        targets += [(32767 << sh), (32768 << sh) - 1, (32768 << sh), (32768 << sh) + 1]
    for k in (100, 511, 512, 1000, 1023, 1024, 1500, 2000, 2043, 2044, 3000, 4000, 6000, 7000):
        targets += [k * k - 1, k * k, k * k + 1, 15 * k * k - 1, 15 * k * k]
    best = {t: (1 << 60, None) for t in targets}
    h2 = np.arange(4096, dtype=np.int64)
    for h1 in range(4096):
        tot = 15 * -2048 + h1 + h2
        m = np.sign(tot) * (np.abs(tot) // 15)
        d0 = -2048 - m
        acc = 13 * d0 * d0 + (d0 + h1) ** 2 + (d0 + h2) ** 2
        for t in targets:
            i = int(np.argmin(np.abs(acc - t)))
            e = abs(int(acc[i]) - t)
            if e < best[t][0]:
                best[t] = (e, (h1, i))
    segs = []
    for t in targets:
        h1, h2v = best[t][1]
        a = np.full(15, -2048, dtype=np.int16)
        a[2] += h1
        a[11] += h2v
        segs.append(a)
    while len(segs) % 30:
        segs.append(np.full(15, 2047, dtype=np.int16))
    print("boundary hunt exact hits: %d of %d targets" % (sum(1 for t in targets if best[t][0] == 0), len(targets)))
    return [np.concatenate(segs[i:i + 30]).reshape(3, 150).T.astype(np.int16)
            for i in range(0, len(segs), 30)]


def mixed_extremes(rng, n):
    """n windows whose segments are random mixes of -2048 and 2047 (per-segment random
    probability), half of them with +-0..3 LSB perturbation (clipped). Returns int16 array."""
    p = rng.uniform(0, 1, size=(n, 10, 3))
    pr = np.repeat(p, 15, axis=1)
    hi = rng.uniform(0, 1, size=(n, 150, 3)) < pr
    w = np.where(hi, 2047, -2048).astype(np.int64)
    pert = rng.integers(-3, 4, size=(n, 150, 3))
    pert[: n // 2] = 0
    return np.clip(w + pert, -2048, 2047).astype(np.int16)


def main(path):
    """Generate vectors into `path`. Returns None; prints the window count."""
    rng = np.random.default_rng(SEED)
    wins = edge_cases()
    # uniform full range
    u = rng.integers(-2048, 2048, size=(N_UNIFORM, 150, 3), dtype=np.int16)
    # smooth motion-like: sum of 1-3 sinusoids + drift + noise, per axis
    t = np.arange(150)[None, :, None] / 100.0
    amp = rng.uniform(50, 2000, size=(N_SMOOTH, 1, 3))
    f1 = rng.uniform(0.3, 6.0, size=(N_SMOOTH, 1, 3))
    f2 = rng.uniform(0.3, 12.0, size=(N_SMOOTH, 1, 3))
    ph = rng.uniform(0, 2 * np.pi, size=(N_SMOOTH, 2, 3))
    off = rng.uniform(-1200, 1200, size=(N_SMOOTH, 1, 3))
    sig = (amp * np.sin(2 * np.pi * f1 * t + ph[:, :1]) +
           0.5 * amp * np.sin(2 * np.pi * f2 * t + ph[:, 1:]) + off +
           rng.normal(0, 20, size=(N_SMOOTH, 150, 3)))
    sm = np.clip(np.rint(sig), -2048, 2047).astype(np.int16)
    # per-segment random extremes to push mean/energy boundaries
    se = rng.integers(-2048, 2048, size=(N_SEGEXT, 150, 3), dtype=np.int16)
    pick = rng.integers(0, 3, size=(N_SEGEXT, 10, 3))
    for k, v in enumerate((None, -2048, 2047)):
        if v is None:
            continue
        m = np.repeat(pick == k, 15, axis=1)
        se[m] = v
    mx = mixed_extremes(rng, N_MIXED)
    arr = np.concatenate([np.stack(wins), u, sm, se, mx, np.stack(spike_sweep()), np.stack(boundary_hunt())]).astype('<i2')
    arr.tofile(path)
    with open(path + ".count", "w") as f:
        f.write("%d\n" % arr.shape[0])
    print("wrote %d windows to %s" % (arr.shape[0], path))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "vectors.bin")
# [END AI-GENERATED]
