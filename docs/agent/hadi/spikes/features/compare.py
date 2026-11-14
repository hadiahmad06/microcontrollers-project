# [AI-GENERATED: Claude Code]
"""Compare C host-runner features to the Python reference, exactly.

usage: compare.py windows.bin c_features.bin expected_count [mode [shift]]
Fails (exit 1) on an empty input or if the window count differs from
expected_count. Checks mean_mulshift == c_div_trunc exhaustively, reports how
many energy values saturated (32767) and how many were not.
"""
import sys
import numpy as np
import features_ref as fr


def main(win_path, feat_path, expected, mode=None, shift=None):
    """Run the comparison. expected: required window count. Returns exit code (0 pass, 1 fail)."""
    for s in range(-30720, 30706):
        if fr.mean_mulshift(s) != fr.c_div_trunc(s, 15):
            print("MULSHIFT MISMATCH s=%d" % s)
            return 1
    print("PY mulshift==trunc-div PASS 61426 sums")
    import math
    import random
    rnd = random.Random(5)
    probes = [0, 1, 2, 3, 4, 2 ** 32 - 1] + [k * k + d for k in range(0, 65536, 97) for d in (-1, 0, 1) if 0 <= k * k + d < 2 ** 32]
    probes += [rnd.randrange(0, 2 ** 27) for _ in range(100000)]
    for p in probes:
        if fr.isqrt32(p) != math.isqrt(p):
            print("PY ISQRT MISMATCH n=%d" % p)
            return 1
    print("PY isqrt32 == math.isqrt PASS %d probes" % len(probes))
    wins = np.fromfile(win_path, dtype='<i2')
    if wins.size % 450 != 0:
        print("FAIL window file size not a multiple of 450 values")
        return 1
    wins = wins.reshape(-1, 150, 3)
    cf = np.fromfile(feat_path, dtype='<i2')
    if cf.size % 60 != 0:
        print("FAIL feature file size not a multiple of 60 values")
        return 1
    cf = cf.reshape(-1, 60)
    n = wins.shape[0]
    if n == 0 or n != expected or cf.shape[0] != n:
        print("FAIL count: windows=%d c_features=%d expected=%d" % (n, cf.shape[0], expected))
        return 1
    bad = 0
    max_e = 0
    sat = 0
    total_e = 0
    for i in range(n):
        ref = fr.extract(wins[i].tolist(), mode, shift)
        en = ref[1::2]
        max_e = max(max_e, max(en))
        sat += sum(1 for e in en if e == 32767)
        total_e += len(en)
        got = cf[i].tolist()
        if ref != got:
            bad += 1
            if bad <= 5:
                idx = [k for k in range(60) if ref[k] != got[k]]
                print("MISMATCH window %d features %s: ref=%s c=%s" % (
                    i, idx[:5], [ref[k] for k in idx[:5]], [got[k] for k in idx[:5]]))
    print("max energy feature seen: %d; saturated (==32767): %d of %d" % (max_e, sat, total_e))
    if bad:
        print("FAIL %d/%d windows mismatched" % (bad, n))
        return 1
    print("PASS %d/%d" % (n, n))
    return 0


if __name__ == "__main__":
    a = sys.argv
    sys.exit(main(a[1], a[2], int(a[3]),
                  int(a[4]) if len(a) > 4 else None, int(a[5]) if len(a) > 5 else None))
# [END AI-GENERATED]
