# [AI-GENERATED: Claude Code]
"""Write test windows (raw little-endian int16, 450 values/window) to a file."""
import sys
import numpy as np

N_UNIFORM = 4000
N_SMOOTH = 4000
N_SEGEXT = 2000
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
    arr = np.concatenate([np.stack(wins), u, sm, se]).astype('<i2')
    arr.tofile(path)
    print("wrote %d windows to %s" % (arr.shape[0], path))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "vectors.bin")
# [END AI-GENERATED]
