#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""Runner for the classify.c / knn.c suite (tickets 3.5T / 3.6T).

Runs the host binary (thousands of scenarios) and the sim16 ELF (hundreds, 16-bit int, via
firmware/test/sim16/run_sim16.sh), compares every output line with oracle.py (built from the
spec only) and checks the C5 section 2 vectors against literal expected values.
Prints PASS/FAIL lines and finally "classify suite PASS" (exit 0) or exits 1.
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oracle  # noqa: E402

# C5 proposal section 2 table, as literal (id, conf). Independent of oracle.py.
C5_TABLE = {
    "c5_1": (3, 255),    # confident built-in within radius: MLP wins
    "c5_2": (9, 255),    # weak MLP (conf 100 < 192)
    "c5_3": (9, 255),    # MLP class 0, conf 255
    "c5_4": (9, 255),    # MLP rejected (30 < 64)
    "c5_5a": (-1, 30),   # outside radius, MLP conf 30
    "c5_5b": (3, 255),   # outside radius, MLP conf 255
    "c5_6a": (-1, 0),    # no templates, tied logits, min_conf 1
    "c5_6b": (0, 0),     # no templates, tied logits, min_conf 0
    "c5_7": (9, 229),    # two learned classes, d1=4, d2=40, margin 0
}

# Literal spot checks: (case name, expected Q line before it), (case name, id, conf).
LITERAL_Q = {
    "ex_p": "Q 1 9 0 15240 1 255 1200",
    "ex_m": "Q 1 9 1016 14224 1 236 1200",
    "dz_a": "Q 1 9 0 0 1 0 1200",
    "tie_cls": "Q 1 9 0 0 1 0 1200",
}
LITERAL_T = {"rmin_eq": (9, 255), "rmin_over": (-1, 0), "rdef_eq": (9, 255), "rdef_over": (-1, 0),
             "rmax_eq": (9, 255), "rmax_over": (-1, 0), "rmid_eq": (9, 255), "rmid_over": (-1, 0)}
# Metadata import cases: 3 directed io_tests calls x 4 classes x 8 cases (6 repaired-CRC -> -2, 2 unrepaired -> -3).
META_EXPECTED = 3 * 4 * 8
LITERAL_LINES = ["G 10673", "DX 15240", "DR 600", "DR 1200", "DR 4000", "DR 2000"]


def compare(label, got, exp, fails):
    """Compare line lists; report up to 5 mismatches with the scenario they occur in.

    Args:
        label: target name for messages.
        got: lines printed by the program.
        exp: lines expected by the oracle.
        fails: list that receives mismatch descriptions.

    Returns:
        Number of mismatching lines.
    """
    bad = 0
    scen = "directed"
    for i in range(max(len(got), len(exp))):
        g = got[i] if i < len(got) else "<missing>"
        e = exp[i] if i < len(exp) else "<extra>"
        if e.startswith("S "):
            scen = "scenario " + e[2:]
        if g != e:
            bad += 1
            if bad <= 5:
                fails.append("%s: line %d (%s)\n    got      %s\n    expected %s" % (label, i + 1, scen, g, e))
    return bad


def literal_checks(label, got, fails):
    """Check the C5 table and a few hand-computed values directly on the program output (independent of oracle.py).

    Args:
        label: target name for messages.
        got: lines printed by the program.
        fails: list that receives failure descriptions.

    Also checks the per-class metadata import cases (review 3.5R F1) against the spec, not the oracle: every
    "X meta_*" line must be -3 for a *_norepair case (CRC checked first) and -2 otherwise, with the store
    unchanged (same == 1), and there must be exactly META_EXPECTED of them.

    Returns:
        Number of metadata import lines checked.
    """
    lastq = None
    seen_t = set()
    nmeta = 0
    for ln in got:
        if ln.startswith("X meta_"):
            f = ln.split()
            want = -3 if "norepair" in f[1] else -2
            nmeta += 1
            if (int(f[2]), int(f[3])) != (want, 1):
                fails.append("%s: metadata case %s got rc %s same %s, expected rc %d same 1" % (label, f[1], f[2], f[3], want))
        if ln.startswith("Q "):
            lastq = ln
        elif ln.startswith("T "):
            f = ln.split()
            name = f[1]
            ret, conf = int(f[7]), int(f[8])
            seen_t.add(name)
            if name in C5_TABLE and (ret, conf) != C5_TABLE[name]:
                fails.append("%s: C5 vector %s got (%d,%d) expected %s" % (label, name, ret, conf, C5_TABLE[name]))
            if name in LITERAL_T and (ret, conf) != LITERAL_T[name]:
                fails.append("%s: case %s got (%d,%d) expected %s" % (label, name, ret, conf, LITERAL_T[name]))
            if name in LITERAL_Q and lastq != LITERAL_Q[name]:
                fails.append("%s: case %s query '%s' expected '%s'" % (label, name, lastq, LITERAL_Q[name]))
    for name in list(C5_TABLE) + list(LITERAL_T) + list(LITERAL_Q):
        if name not in seen_t:
            fails.append("%s: directed case %s missing from output" % (label, name))
    for lit in LITERAL_LINES:
        if lit not in got:
            fails.append("%s: expected line '%s' not found" % (label, lit))
    if nmeta != META_EXPECTED:
        fails.append("%s: %d metadata import lines, expected %d" % (label, nmeta, META_EXPECTED))
    return nmeta


def run(cmd, timeout):
    """Run a command with a timeout and keep its non-empty output lines (SIM16_EXIT markers dropped).

    Args:
        cmd: argument list.
        timeout: seconds.

    Returns:
        (exit code, stdout lines, stderr text), or (None, [], "") on timeout.
    """
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, [], ""
    return p.returncode, [x.rstrip("\r") for x in p.stdout.split("\n") if x.strip() != "" and not x.startswith("SIM16_EXIT")], p.stderr


def check(label, cmd, seed, nscen, timeout):
    """Run one target and compare its output with the oracle; print PASS or FAIL lines.

    Args:
        label: target name (host or sim16).
        cmd: argument list of the program.
        seed: run seed.
        nscen: scenarios the program replays.
        timeout: seconds.

    Returns:
        True on PASS.
    """
    exp = oracle.expected(seed, nscen)
    res = run(cmd, timeout)
    fails = []
    if res[0] is None:
        print("FAIL %s: timeout after %ds" % (label, timeout))
        return False
    rc, got, err = res
    if rc != 0:
        fails.append("%s: exit code %d %s" % (label, rc, err.strip()[:300]))
    nbad = compare(label, got, exp, fails)
    nmeta = literal_checks(label, got, fails)
    if fails:
        print("FAIL %s: %d mismatching lines of %d" % (label, nbad, len(exp)))
        for f in fails[:12]:
            print("  " + f)
        return False
    print("PASS %s: metadata import checks, %d cases (count > 5, next >= 5, count < 5 with next != count -> -2; "
          "flip without CRC repair -> -3; store unchanged)" % (label, nmeta))
    print("PASS %s: directed cases + %d scenarios, %d lines match the oracle" % (label, nscen, len(exp)))
    return True


def main():
    """Parse the command line, run the host and sim16 targets, print the verdict.

    Returns:
        Process exit code: 0 on "classify suite PASS", 1 otherwise.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--elf", required=True)
    ap.add_argument("--sim16", required=True, help="path of run_sim16.sh")
    ap.add_argument("--seed", type=lambda s: int(s, 0), default=1)
    ap.add_argument("--nhost", type=int, default=2000)
    ap.add_argument("--nsim", type=int, default=100)
    ap.add_argument("--sim-timeout", type=int, default=600)
    a = ap.parse_args()
    ok = check("host", [a.host, str(a.seed), str(a.nhost)], a.seed, a.nhost, 600)
    ok = check("sim16", [a.sim16, a.elf, str(a.sim_timeout)], a.seed, a.nsim, a.sim_timeout + 30) and ok
    if ok:
        print("classify suite PASS")
        return 0
    print("classify suite FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
