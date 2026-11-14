# [AI-GENERATED: Claude Code]
"""Test runner: oracle self-checks, differential tests vs the C code, sinusoid stats.

Usage: run_tests.py <path to host_runner binary> <build dir>
Prints PASS/FAIL per group; exit status 1 if any group fails.
"""
import math
import os
import random
import struct
import subprocess
import sys
from fractions import Fraction

import gen
import oracle


def pack(windows):
    """Serialize windows to the runner format (LE int16, sample-major).

    Args: windows: list of windows. Returns: bytes.
    """
    flat = [v for w in windows for row in w for v in row]
    return struct.pack("<%dh" % len(flat), *flat)


def run_c(binary, build, windows, tag):
    """Run the C implementation on windows. Args: binary, build dir, windows, tag.

    Returns: list of 60-int lists, one per window.
    """
    inp = os.path.join(build, tag + ".win")
    outp = os.path.join(build, tag + ".feat")
    with open(inp, "wb") as f:
        f.write(pack(windows))
    subprocess.run([binary, inp, outp], check=True)
    with open(outp, "rb") as f:
        data = f.read()
    assert len(data) == 120 * len(windows), "short output"
    vals = struct.unpack("<%dh" % (60 * len(windows)), data)
    return [list(vals[60 * i:60 * i + 60]) for i in range(len(windows))]


def report(name, ok, total, fails):
    """Print one group result. Args: name, ok count, total, fail list. Returns: bool."""
    status = "PASS" if not fails and ok == total else "FAIL"
    print("%s %-28s %d/%d" % (status, name, ok, total))
    for f in fails[:5]:
        print("   mismatch:", f)
    return status == "PASS"


def diff_group(binary, build, name, items):
    """Differential test of items [(label, window)] vs the oracle.

    Args: binary, build, name, items. Returns: bool pass.
    """
    wins = [w for _, w in items]
    got = run_c(binary, build, wins, name)
    fails = []
    for i, w in enumerate(wins):
        exp = oracle.features(w)
        if exp != got[i]:
            idx = next(k for k in range(60) if exp[k] != got[i][k])
            fails.append({"label": items[i][0], "win": i, "idx": idx,
                          "expected": exp[idx], "got": got[i][idx]})
    return report(name, len(wins) - len(fails), len(wins), fails)


def sanity():
    """Oracle self-checks independent of the C code. Returns: bool pass."""
    bad = 0
    for s in range(-30720, 30706):
        ref = (1 if s >= 0 else -1) * math.floor(Fraction(abs(s), 15))
        if oracle.trunc_div(s, 15) != ref or oracle.mean_alt(s) != ref:
            bad += 1
    # hand-computed cases
    cases = [([0] * 15, (0, 0)), ([5] * 15, (5, 0)),
             ([-1] + [0] * 14, (0, 0)),  # sum -1 -> mean 0 (trunc), acc 1 -> 0
             ([-2048] * 15, (-2048, 0))]
    for seg, exp in cases:
        if oracle.segment_features(seg) != exp:
            bad += 1
    # [2047]*8 + [-2048]*7: sum=16376-14336=2040 -> mean 136; computed by hand below
    seg = [2047] * 8 + [-2048] * 7
    mean = 2040 // 15  # positive operands, so floor == trunc
    acc = 8 * (2047 - mean) ** 2 + 7 * (-2048 - mean) ** 2
    if oracle.segment_features(seg) != (mean, min(acc // 2048, 32767)):
        bad += 1
    # negative-sum truncation: sum -16 -> -1 (floor would give -2)
    if oracle.trunc_div(-16, 15) != -1 or oracle.trunc_div(-15, 15) != -1 \
            or oracle.trunc_div(-14, 15) != 0:
        bad += 1
    return report("oracle-sanity", 1 if bad == 0 else 0, 1, [] if bad == 0 else ["bad=%d" % bad])


def exhaustive_mean(binary, build):
    """Check C mean for every 15-sample sum. Args: binary, build. Returns: bool pass."""
    wins, exp = gen.g_exhaustive_sums()
    got = run_c(binary, build, wins, "exh")
    fails, n = [], 0
    seen = set()
    for w, (win, sums) in enumerate(zip(wins, exp)):
        for a in range(3):
            for s in range(10):
                t = sums[10 * a + s]
                m = got[w][20 * a + 2 * s]
                n += 1
                seen.add(t)
                if m != oracle.trunc_div(t, 15):
                    fails.append({"sum": t, "expected": oracle.trunc_div(t, 15), "got": m})
                # also cross-check the generated segment really has that sum
                assert sum(win[15 * s + j][a] for j in range(15)) == t
    ok = report("exhaustive-mean (%d sums)" % len(seen), n - len(fails), n, fails)
    return ok and len(seen) == 61426


def sin_stats(binary, build):
    """Energy distribution of sinusoid windows per amplitude (C output).

    Args: binary, build. Returns: bool pass (differential check) ; prints table.
    """
    ok = True
    rows = []
    for amp in (10, 50, 250, 1000):
        rng = random.Random(9000 + amp)
        items = gen.g_sinusoid(rng, 2500, amp)
        ok &= diff_group(binary, build, "sinusoid-amp%d" % amp, items)
        got = run_c(binary, build, [w for _, w in items], "sin%d" % amp)
        en = sorted(f[20 * a + 2 * s + 1] for f in got for a in range(3) for s in range(10))
        zero = sum(1 for e in en if e == 0) / len(en)
        rows.append((amp, en[0], en[len(en) // 2], en[-1], zero))
    print("\nEnergy (after >>11) over all segments, per sinusoid amplitude (noise +/-2 LSB):")
    print("amp   min  median  max   frac_zero")
    for r in rows:
        print("%-5d %-4d %-7d %-5d %.3f" % r)
    print()
    return ok


def main():
    """Entry point. Returns: process exit code."""
    binary, build = sys.argv[1], sys.argv[2]
    ok = sanity()
    ok &= exhaustive_mean(binary, build)
    r = random.Random(20261114)
    groups = [
        ("uniform", gen.g_uniform(r, 4000)),
        ("boundary", gen.g_boundary(r, 3000)),
        ("constant", gen.g_constant(r, 1500)),
        ("spikes", gen.g_spike(r, 2000)),
        ("sum-multiples-of-15", gen.g_sum_multiples(r, 3000)),
        ("sum-extremes", gen.g_sum_extremes(r, 1500)),
        ("alternating-maxvar", gen.g_alternating(r, 3000)),
    ]
    total = 0
    for name, items in groups:
        ok &= diff_group(binary, build, name, items)
        total += len(items)
    ok &= sin_stats(binary, build)
    total += 4 * 2500
    print("total differential windows (excl. exhaustive): %d" % total)
    print("OVERALL", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
