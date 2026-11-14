# [AI-GENERATED: Claude Code]
"""Energy-scaling study for C3 decision D4 (analysis only, not a bit-exact reference).

Synthetic motion: per axis a sinusoid of 1..5 cycles/window, peak amplitude amp*U(0.3,1),
DC offset U(-1000,1000), +-2 LSB uniform noise, clipped to [-2048, 2047] (same recipe as
the independent QA generator). For each amplitude prints, per energy option, the share
of segments that store 0, the median, the 99th percentile, the max, and the share that
saturate at 32767. isqrt options use numpy float sqrt, exact here since SS < 2**26.
usage: energy_study.py [windows_per_amplitude]
"""
import sys
import numpy as np

AMPS = (10, 50, 250, 1000, 2000)


def segments_ss(rng, n, amp):
    """Return int64 array of n*30 per-segment sums of squared deviations.

    rng: numpy Generator; n: windows; amp: peak amplitude in LSB.
    """
    i = np.arange(150)[None, :, None]
    cyc = rng.uniform(1, 5, size=(n, 1, 3))
    ph = rng.uniform(0, 2 * np.pi, size=(n, 1, 3))
    off = rng.integers(-1000, 1001, size=(n, 1, 3))
    a = amp * rng.uniform(0.3, 1.0, size=(n, 1, 3))
    x = np.rint(off + a * np.sin(2 * np.pi * cyc * i / 150 + ph)).astype(np.int64)
    x += rng.integers(-2, 3, size=(n, 150, 3))
    x = np.clip(x, -2048, 2047).reshape(n, 10, 15, 3)
    tot = x.sum(axis=2, keepdims=True)
    mean = np.sign(tot) * (np.abs(tot) // 15)  # C truncation
    return ((x - mean) ** 2).sum(axis=2).reshape(-1)


def options(ss):
    """Map option name -> stored int16 energy array for sums of squares ss."""
    o = {}
    for s in (11, 8, 7, 6):
        o["shift %d" % s] = np.minimum(ss >> s, 32767)
    o["isqrt(SS)"] = np.floor(np.sqrt(ss.astype(np.float64))).astype(np.int64)
    o["isqrt(SS/15)"] = np.floor(np.sqrt((ss // 15).astype(np.float64))).astype(np.int64)
    return o


def main(n):
    """Print the comparison table. n: windows per amplitude. Returns None."""
    rng = np.random.default_rng(2361)
    print("amp   option          zero%   median   p99      max    sat%")
    for amp in AMPS:
        ss = segments_ss(rng, n, amp)
        for name, e in options(ss).items():
            print("%-5d %-14s %6.1f  %7d %7d %8d %6.1f" % (
                amp, name, 100.0 * np.mean(e == 0), np.median(e),
                np.percentile(e, 99), e.max(), 100.0 * np.mean(e == 32767)))
        print()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2500)
# [END AI-GENERATED]
