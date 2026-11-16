#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""Runner for the trigger suite (ticket T-trigT).

Runs the host binary (directed scripts + many random episodes) and the sim16 ELF (16-bit int, a few
episodes, via firmware/test/sim16/run_sim16.sh) and compares every output line exactly with oracle.py.
Extra checks on the host output:
  * scenarios 'oor raw' and 'oor clamped' must give identical lines (out-of-range clamping),
  * if tools/trigger_ref.py exists, its run() trigger indices (and cut_windows) must equal the C
    trigger indices on the offline reference streams; otherwise a SKIP line is printed.
Prints "trigger suite PASS" (exit 0) or "trigger suite FAIL" (exit 1).
"""
import argparse
import importlib.util
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oracle  # noqa: E402


def compare(label, got, exp, fails):
    """Compare two line lists exactly; record up to 5 mismatches with their scenario.

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
    names = oracle.SCEN_NAMES
    for i in range(max(len(got), len(exp))):
        g = got[i] if i < len(got) else "<missing>"
        e = exp[i] if i < len(exp) else "<extra>"
        if e.startswith("S "):
            n = int(e[2:])
            scen = names[n] if n < len(names) else "random episode %d" % (n - 1000)
        if g != e:
            bad += 1
            if bad <= 5:
                fails.append("%s: line %d (scenario %s)\n    got      %s\n    expected %s"
                             % (label, i + 1, scen, g, e))
    return bad


def run(cmd, timeout):
    """Run a command and collect its output lines.

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


def segment(lines, idx):
    """Return the lines of scenario idx (after its 'S idx' line, up to the next 'S' line)."""
    out, on = [], False
    for ln in lines:
        if ln.startswith("S "):
            on = (ln == "S %d" % idx)
            continue
        if on:
            out.append(ln)
    return out


def check_pairs(lines):
    """Clamping check: paired scenarios must print identical lines. Returns a list of failure texts."""
    fails = []
    for a, b in oracle.PAIRS:
        sa, sb = segment(lines, a), segment(lines, b)
        if not sa or sa != sb:
            fails.append("scenarios %r and %r differ (out-of-range inputs not clamped identically)"
                         % (oracle.SCEN_NAMES[a], oracle.SCEN_NAMES[b]))
    return fails


def fire_indices_from_c(lines, name_prefix):
    """Indices (within the scenario's feed count, resyncs do not reset) of 'F 1' lines of one REF scenario."""
    n = [i for i, nm in enumerate(oracle.SCEN_NAMES) if nm.startswith(name_prefix)][0]
    seg = segment(lines, n)
    idx, out = 0, []
    for ln in seg:
        if ln.startswith("F "):
            if ln.split()[1] == "1":
                out.append(idx)
            idx += 1
    return out


def check_ref(lines, ref_path):
    """Compare C trigger indices with tools/trigger_ref.py.

    Args:
        lines: host output lines.
        ref_path: path of trigger_ref.py.

    Returns:
        (ok, message).
    """
    if not os.path.exists(ref_path):
        return True, "SKIP trigger_ref cross-check: %s not found" % ref_path
    try:
        spec = importlib.util.spec_from_file_location("trigger_ref", ref_path)
        ref = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ref)
        for (samples, mg, rel, rs, fires), name in zip(
                oracle.REFS, [n for n in oracle.SCEN_NAMES if n.startswith("ref ")]):
            c_fires = fire_indices_from_c(lines, name)
            py_fires, _h = ref.run(samples, None, mg, rel, rs)
            py_fires = [int(v) for v in py_fires]
            if c_fires != py_fires or c_fires != fires:
                return False, "FAIL trigger_ref %s: C %r, trigger_ref %r, oracle %r" % (name, c_fires, py_fires, fires)
            wins = ref.cut_windows(samples, py_fires)
            exp = [t for t in py_fires if t - 15 >= 0 and t + 135 <= len(samples)]
            if [int(t) for (t, _w) in wins] != exp:
                return False, "FAIL trigger_ref cut_windows indices %s: %r vs %r" % (name, [t for (t, _w) in wins], exp)
            for (t, w) in wins:
                rows = [tuple(int(v) for v in r) for r in w]
                if rows != [tuple(r) for r in samples[t - 15:t + 135]]:
                    return False, "FAIL trigger_ref cut_windows content %s t=%d" % (name, t)
        return True, "PASS trigger_ref cross-check: %d reference streams, trigger indices and windows identical" % len(oracle.REFS)
    except Exception as exc:  # noqa: BLE001
        return False, "FAIL trigger_ref cross-check raised %s: %s" % (type(exc).__name__, exc)


def check(label, cmd, seed, nep, timeout, extra):
    """Run one target and compare it with the oracle.

    Args:
        label: target name (host or sim16).
        cmd: command that runs the target.
        seed: random-episode seed.
        nep: number of random episodes.
        timeout: time limit in seconds.
        extra: callable(lines) -> list of failure texts, run on the output (or None).

    Returns:
        (True on PASS, output lines).
    """
    exp = oracle.expected(seed, nep)
    res = run(cmd, timeout)
    if res[0] is None:
        print("FAIL %s: timeout after %ds" % (label, timeout))
        return False, []
    rc, got, err = res
    fails = []
    if rc != 0:
        fails.append("%s: exit code %d %s" % (label, rc, err.strip()[:300]))
    nbad = compare(label, got, exp, fails)
    if extra is not None:
        fails.extend(extra(got))
    if fails:
        print("FAIL %s: %d mismatching lines of %d" % (label, nbad, len(exp)))
        for f in fails[:12]:
            print("  " + f)
        return False, got
    print("PASS %s: %d directed scenarios + %d random episodes, %d lines match the oracle"
          % (label, len(oracle.directed().names), nep, len(exp)))
    return True, got


def main():
    """Parse arguments, run the host and sim16 targets, print the final verdict.

    Returns:
        Process exit code: 0 on PASS, 1 on FAIL.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--elf", required=True)
    ap.add_argument("--sim16", required=True, help="path of run_sim16.sh")
    ap.add_argument("--ref", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                                                  "tools", "trigger_ref.py"))
    ap.add_argument("--seeds", default="1,2,3", help="host seeds, comma separated")
    ap.add_argument("--nhost", type=int, default=120)
    ap.add_argument("--seed-sim", type=int, default=1)
    ap.add_argument("--nsim", type=int, default=3)
    ap.add_argument("--sim-timeout", type=int, default=900)
    a = ap.parse_args()
    ok = True
    first = True
    for sd in [int(x, 0) for x in a.seeds.split(",")]:
        good, got = check("host seed=%d" % sd, [a.host, str(sd), str(a.nhost)], sd, a.nhost, 900,
                          check_pairs if first else None)
        ok = good and ok
        if first and got:
            rok, msg = check_ref(got, a.ref)
            print(msg)
            ok = rok and ok
        first = False
    good, _ = check("sim16", [a.sim16, a.elf, str(a.sim_timeout)], a.seed_sim, a.nsim, a.sim_timeout + 30, None)
    ok = good and ok
    if ok:
        print("trigger suite PASS")
        return 0
    print("trigger suite FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
