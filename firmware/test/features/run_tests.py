#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""run_tests.py - runs the features test binaries and compares every output with oracle.py.

Checks: host binary (many windows), sim16 ELF (fewer windows, 16-bit int), the C self-checks
(isqrt sweep, FEAT_IS_NONNEG, FEATURES_VERSION) and tools/features_ref.py vs the oracle.
Prints PASS/FAIL/SKIP lines and a final "features suite PASS" (exit 0) or exit 1.
Usage: run_tests.py --host BIN --elf ELF --sim-run run_sim16.sh --tools DIR [--spike]
                    [--seed N] [--n-host N] [--n-sim N] [--sim-timeout S]
"""
import argparse
import subprocess
import sys

import oracle

FAILED = []


def report(name, ok, detail=""):
    """Print a PASS/FAIL line for one check and remember failures.

    Args:
        name: check name. ok: bool. detail: extra text shown on failure.
    Returns:
        ok.
    """
    print(("PASS " if ok else "FAIL ") + name + ((" -- " + detail) if (detail and not ok) else ""))
    if not ok:
        FAILED.append(name)
    return ok


def parse(text):
    """Parse driver output into windows, check lines and the DONE line.

    Args:
        text: stdout of the driver.
    Returns:
        (edges {e: [60]}, rands {w: [60]}, chk {name: [fields]}, done fields or None)
    """
    edges, rands, chk, done = {}, {}, {}, None
    for line in text.splitlines():
        f = line.split()
        if not f:
            continue
        if f[0] in ("E", "W") and len(f) == 23 and f[2] in ("0", "1", "2"):
            d = edges if f[0] == "E" else rands
            d.setdefault(int(f[1]), [None] * 60)[20 * int(f[2]):20 * int(f[2]) + 20] = \
                [int(v) for v in f[3:]]
        elif f[0] == "CHK" and len(f) >= 3:
            chk.setdefault(f[1], []).extend(f[2:])
        elif f[0] == "DONE":
            done = f[1:]
    return edges, rands, chk, done


def compare(label, edges, rands, seed, n):
    """Compare driver windows with the oracle and report one check.

    Args:
        label: "host" or "sim16". edges/rands: parsed output. seed, n: generator parameters.
    Returns:
        None.
    """
    bad = []
    for e in range(oracle.N_EDGE):
        want = oracle.expected(oracle.edge_window(e))
        if edges.get(e) != want:
            bad.append(("E", e, want, edges.get(e)))
    rng = oracle.Rng(seed)
    for w in range(n):
        want = oracle.expected(oracle.random_window(rng, w))
        if rands.get(w) != want:
            bad.append(("W", w, want, rands.get(w)))
    detail = ""
    for tag, k, want, got in bad[:3]:
        idx = [i for i in range(60) if got is None or got[i] != want[i]][:4]
        detail += "\n    %s %d idx %s want %s got %s" % (
            tag, k, idx, [want[i] for i in idx], None if got is None else [got[i] for i in idx])
    report("%s outputs match oracle (%d edge + %d random windows)" % (label, oracle.N_EDGE, n),
           not bad, "%d windows differ%s" % (len(bad), detail))
    return None


def checks(label, chk, spike):
    """Report the C self-checks printed by the driver.

    Args:
        label: "host" or "sim16". chk: parsed CHK lines. spike: True under SPIKE_STANDIN.
    Returns:
        None.
    """
    iq = chk.get("isqrt", [])
    report("%s features_isqrt32 sweep (%s cases)" % (label, iq[0] if iq else "?"),
           len(iq) == 2 and iq[1] == "0" and int(iq[0]) > 1000, "failures=%s" % (iq[1:] or "?"))
    for name in ("nonneg", "version", "dims"):
        v = chk.get(name)
        if spike:
            print("SKIP %s %s (spike stand-in)" % (label, name))
        else:
            report("%s %s check" % (label, name), v == ["0"], "got %s" % v)


def run_driver(label, cmd, timeout):
    """Run a driver command and return (exit code, stdout).

    Args:
        label: name for error messages. cmd: argv list. timeout: seconds.
    Returns:
        (returncode, stdout text); returncode -1 on timeout.
    """
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           universal_newlines=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return -1, ""
    if p.stderr.strip():
        print("  [%s stderr] %s" % (label, p.stderr.strip()[:300]))
    return p.returncode, p.stdout


def test_ref(tools, edges_ok_windows, n_random, seed):
    """Check tools/features_ref.py against the oracle and its ValueError behaviour.

    Args:
        tools: path of the tools directory. edges_ok_windows: unused marker.
        n_random: number of random windows. seed: generator seed.
    Returns:
        None.
    """
    sys.path.insert(0, tools)
    try:
        import features_ref as fr
    except Exception as ex:  # report, do not crash
        report("import tools/features_ref.py", False, repr(ex))
        return
    report("features_ref constants", getattr(fr, "FEATURES_VERSION", None) == 1 and
           getattr(fr, "FEAT_COUNT", None) == 60 and
           list(getattr(fr, "NONNEG", [])) == [(i % 2) == 1 for i in range(60)])
    bad = 0
    wins = [oracle.edge_window(e) for e in range(oracle.N_EDGE)]
    rng = oracle.Rng(seed)
    wins += [oracle.random_window(rng, w) for w in range(n_random)]
    for win in wins:
        if list(fr.features_extract(win)) != oracle.expected(win):
            bad += 1
    report("features_ref.features_extract matches oracle (%d windows)" % len(wins), bad == 0,
           "%d differ" % bad)
    div_bad = 0
    for a in (-30720, -30719, -31, -30, -29, -16, -15, -14, -1, 0, 1, 14, 15, 16, 29, 30, 30705):
        if fr.c_div_trunc(a, 15) != oracle.tdiv(a, 15):
            div_bad += 1
    for a in range(-100, 101):
        for b in (-7, -3, -1, 1, 2, 15):
            if fr.c_div_trunc(a, b) != oracle.tdiv(a, b):
                div_bad += 1
    report("features_ref.c_div_trunc matches oracle", div_bad == 0)
    sq_bad = 0
    vals = list(range(0, 3000)) + [2 ** 32 - 1, 2 ** 32 - 2, 2 ** 31, 62604360, 7912 ** 2, 7913 ** 2 - 1]
    for k in range(1, 65536, 97):
        vals += [k * k - 1, k * k, k * k + 1]
    vals += [65535 * 65535 - 1, 65535 * 65535]
    for n in vals:
        if fr.isqrt32(n) != oracle.math.isqrt(n):
            sq_bad += 1
    report("features_ref.isqrt32 matches math.isqrt (%d values)" % len(vals), sq_bad == 0)
    for badv in (2048, -2049):
        for pos in ((0, 0), (77, 1), (149, 2)):
            w = [[0, 0, 0] for _ in range(150)]
            w[pos[0]][pos[1]] = badv
            try:
                fr.features_extract(w)
                ok = False
            except ValueError:
                ok = True
            report("features_ref raises ValueError for %d at %s" % (badv, pos), ok)
    for edge in (-2048, 2047):
        w = [[edge] * 3 for _ in range(150)]
        try:
            ok = list(fr.features_extract(w)) == oracle.expected(w)
        except ValueError:
            ok = False
        report("features_ref accepts boundary value %d" % edge, ok)


def main():
    """Parse arguments, run everything and print the final verdict.

    Returns:
        None (calls sys.exit).
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--elf", required=True)
    ap.add_argument("--sim-run", required=True)
    ap.add_argument("--tools", required=True)
    ap.add_argument("--spike", action="store_true")
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--n-host", type=int, default=5000)
    ap.add_argument("--n-sim", type=int, default=300)
    ap.add_argument("--sim-timeout", type=int, default=600)
    a = ap.parse_args()

    rc, out = run_driver("host", [a.host, str(a.seed), str(a.n_host)], 600)
    edges, rands, chk, done = parse(out)
    report("host driver ran to completion", rc == 0 and done == [str(oracle.N_EDGE), str(a.n_host)],
           "rc=%s done=%s" % (rc, done))
    compare("host", edges, rands, a.seed, a.n_host)
    checks("host", chk, a.spike)

    rc, out = run_driver("sim16", [a.sim_run, a.elf, str(a.sim_timeout)], a.sim_timeout + 30)
    edges, rands, chk, done = parse(out)
    report("sim16 driver ran to completion", rc == 0 and done == [str(oracle.N_EDGE), str(a.n_sim)],
           "rc=%s done=%s" % (rc, done))
    compare("sim16", edges, rands, a.seed, a.n_sim)
    checks("sim16", chk, a.spike)

    if a.spike:
        print("SKIP tools/features_ref.py checks (spike stand-in)")
    else:
        test_ref(a.tools, None, min(a.n_host, 2000), a.seed)

    if FAILED:
        print("features suite FAIL (%d failed checks)" % len(FAILED))
        sys.exit(1)
    print("features suite PASS")
    sys.exit(0)


main()
# [END AI-GENERATED]
