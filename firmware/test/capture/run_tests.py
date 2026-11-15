#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""Runner for the capture.c suite (ticket WP1-aT).

Runs the host binary (hundreds of random episodes, thousands of events) and the sim16 ELF (a few
episodes, 16-bit int, via firmware/test/sim16/run_sim16.sh), both after the same directed scripts,
and compares every output line exactly with oracle.py (built from the spec only).
Prints PASS/FAIL lines and finally "capture suite PASS" (exit 0) or exits 1.
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oracle  # noqa: E402


def compare(label, got, exp, fails):
    """Compare two line lists exactly; record up to 5 mismatches with the scenario they occur in.

    Args:
        label: target name used in the failure text.
        got: lines printed by the program.
        exp: lines expected by the oracle.
        fails: list that receives the formatted mismatch descriptions.

    Returns:
        The number of mismatching lines.
    """
    bad = 0
    scen = "?"
    for i in range(max(len(got), len(exp))):
        g = got[i] if i < len(got) else "<missing>"
        e = exp[i] if i < len(exp) else "<extra>"
        if e.startswith("S "):
            scen = e[2:]
        if g != e:
            bad += 1
            if bad <= 5:
                fails.append("%s: line %d (scenario %s)\n    got      %s\n    expected %s"
                             % (label, i + 1, scen, g, e))
    return bad


def run(cmd, timeout):
    """Run a command and collect its output.

    Args:
        cmd: argument list.
        timeout: time limit in seconds.

    Returns:
        (exit code, stdout lines, stderr), or (None, [], "") on timeout.
    """
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, [], ""
    lines = [x.rstrip("\r") for x in p.stdout.split("\n") if x.strip() != "" and not x.startswith("SIM16_EXIT")]
    return p.returncode, lines, p.stderr


def check(label, cmd, seed, nep, timeout):
    """Run one target and compare it with the oracle.

    Args:
        label: target name (host or sim16).
        cmd: command that runs the target.
        seed: random-episode seed.
        nep: number of random episodes.
        timeout: time limit in seconds.

    Returns:
        True on PASS, False on FAIL.
    """
    exp = oracle.expected(seed, nep)
    res = run(cmd, timeout)
    if res[0] is None:
        print("FAIL %s: timeout after %ds" % (label, timeout))
        return False
    rc, got, err = res
    fails = []
    if rc != 0:
        fails.append("%s: exit code %d %s" % (label, rc, err.strip()[:300]))
    nbad = compare(label, got, exp, fails)
    if fails:
        print("FAIL %s: %d mismatching lines of %d" % (label, nbad, len(exp)))
        for f in fails[:12]:
            print("  " + f)
        return False
    nev = sum(1 for x in exp if x.startswith("E "))
    print("PASS %s: %d directed scripts + %d random episodes, %d events, %d lines match the oracle"
          % (label, len(oracle.DIRECTED), nep, nev, len(exp)))
    return True


def main():
    """Parse arguments, run the host and sim16 targets, print the final verdict.

    Returns:
        Process exit code: 0 on PASS, 1 on FAIL.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--elf", required=True)
    ap.add_argument("--sim16", required=True, help="path of run_sim16.sh")
    ap.add_argument("--seed", type=lambda s: int(s, 0), default=1)
    ap.add_argument("--nhost", type=int, default=1500)
    ap.add_argument("--nsim", type=int, default=150)
    ap.add_argument("--sim-timeout", type=int, default=900)
    a = ap.parse_args()
    ok = check("host", [a.host, str(a.seed), str(a.nhost)], a.seed, a.nhost, 900)
    ok = check("sim16", [a.sim16, a.elf, str(a.sim_timeout)], a.seed, a.nsim, a.sim_timeout + 30) and ok
    if ok:
        print("capture suite PASS")
        return 0
    print("capture suite FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
