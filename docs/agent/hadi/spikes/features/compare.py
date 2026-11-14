# [AI-GENERATED: Claude Code]
"""Compare C host-runner features to the Python reference, exactly.

usage: compare.py windows.bin c_features.bin
Also checks mean_mulshift == c_div_trunc exhaustively and prints worst cases.
Exit status 0 only if every feature of every window matches.
"""
import sys
import numpy as np
import features_ref as fr


def main(win_path, feat_path):
    """Run the comparison. Returns process exit code (0 pass, 1 fail)."""
    for s in range(-30720, 30706):
        if fr.mean_mulshift(s) != fr.c_div_trunc(s, 15):
            print("MULSHIFT MISMATCH s=%d" % s)
            return 1
    print("PY mulshift==trunc-div PASS 61426 sums")
    wins = np.fromfile(win_path, dtype='<i2').reshape(-1, 150, 3)
    cf = np.fromfile(feat_path, dtype='<i2').reshape(-1, 60)
    n = wins.shape[0]
    if cf.shape[0] != n:
        print("count mismatch: windows=%d c_features=%d" % (n, cf.shape[0]))
        return 1
    bad = 0
    max_e = 0
    for i in range(n):
        ref = fr.extract(wins[i].tolist())
        max_e = max(max_e, max(ref[1::2]))
        got = cf[i].tolist()
        if ref != got:
            bad += 1
            if bad <= 5:
                idx = [k for k in range(60) if ref[k] != got[k]]
                print("MISMATCH window %d features %s: ref=%s c=%s" % (
                    i, idx[:5], [ref[k] for k in idx[:5]], [got[k] for k in idx[:5]]))
    print("max energy feature seen: %d" % max_e)
    if bad:
        print("FAIL %d/%d windows mismatched" % (bad, n))
        return 1
    print("PASS %d/%d" % (n, n))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
# [END AI-GENERATED]
