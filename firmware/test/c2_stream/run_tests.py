#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""Runner for the c2_stream suite (ticket T-c2txT).

Runs the host binary and the sim16 ELF (16-bit int, firmware/test/sim16/run_sim16.sh), compares every
output line exactly with oracle.py (built from the spec only), and additionally decodes the bytes the
target pumped (per scenario) with the oracle's own S7 decoder: every completed frame must decode with
a good CRC, the decoded frame list must equal what the oracle's model started, and the only garbage
bytes must be the text bytes. Lines starting with "# " are informational and not compared.
Prints PASS/FAIL lines and finally "c2_stream suite PASS" (exit 0) or exits 1.
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oracle  # noqa: E402


def run(cmd, timeout):
    """Run a command; return (exit code, stdout lines, stderr) or (None, [], "") on timeout."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, [], ""
    lines = [x.rstrip("\r") for x in p.stdout.split("\n") if x.strip() != "" and not x.startswith("SIM16_EXIT")]
    return p.returncode, lines, p.stderr


def compare(got, exp, fails):
    """Compare line lists exactly; record up to 6 mismatches with their scenario. Returns mismatch count."""
    bad, scen = 0, "?"
    for i in range(max(len(got), len(exp))):
        g = got[i] if i < len(got) else "<missing>"
        e = exp[i] if i < len(exp) else "<extra>"
        if e.startswith("== "):
            scen = e[3:]
        if g != e:
            bad += 1
            if bad <= 6:
                fails.append("line %d (scenario %s)\n    got      %s\n    expected %s" % (i + 1, scen, g, e))
    return bad


def streams_of(lines):
    """Split output lines into {scenario: pumped bytes} using the x lines."""
    out, cur = {}, None
    for ln in lines:
        if ln.startswith("== "):
            cur = ln[3:]
            out[cur] = bytearray()
        elif ln.startswith("x ") and cur is not None:
            try:
                out[cur].extend(bytes.fromhex(ln[2:]))
            except ValueError:
                pass
    return out


def check_decode(got_lines, exp_streams, fails):
    """Decode the target's pumped bytes with the oracle decoder and compare with the model's frames."""
    got = streams_of(got_lines)
    nfr = 0
    for name, (_, frames_bytes, ntext) in exp_streams.items():
        if name == "reinit":   # abandons a half-sent frame on purpose; line compare only
            continue
        if name not in got:
            fails.append("decode: scenario %s missing" % name)
            continue
        frames, garbage, badhdr, crcerr = oracle.decode(bytes(got[name]))
        exp_frames, eg, eh, ec = oracle.decode(frames_bytes)
        nfr += len(frames)
        if frames != exp_frames or badhdr or crcerr or garbage != ntext:
            fails.append("decode: scenario %s: %d frames (expected %d), garbage %d (text bytes %d), "
                         "badhdr %d, crcerr %d" % (name, len(frames), len(exp_frames), garbage, ntext, badhdr, crcerr))
    return nfr


def check(label, cmd, avr, timeout):
    """Run one target and compare with the oracle. Returns True on PASS."""
    exp, streams = oracle.expected(avr)
    res = run(cmd, timeout)
    if res[0] is None:
        print("FAIL %s: timeout after %ds" % (label, timeout))
        return False
    rc, got, err = res
    for ln in got:
        if ln.startswith("# "):
            print("  %s %s" % (label, ln))
    got = [x for x in got if not x.startswith("# ")]
    exp = [x for x in exp if not x.startswith("# ")]
    fails = []
    if rc != 0:
        fails.append("exit code %d %s" % (rc, err.strip()[:300]))
    nbad = compare(got, exp, fails)
    nfr = check_decode(got, streams, fails)
    # spec X2: a WINDOW needs at least ceil(922/32) = 29 pump calls when room >= 32 (direct check)
    for i, ln in enumerate(got):
        if ln == "== win_room_32":
            j = i
            while not got[j].startswith("D calls="):
                j += 1
            if int(got[j].split("=")[1].split()[0]) < 29:
                fails.append("fewer than 29 pump calls for a WINDOW at room 32")
    if fails:
        print("FAIL %s: %d mismatching lines of %d" % (label, nbad, len(exp)))
        for f in fails[:12]:
            print("  " + f)
        return False
    nsc = sum(1 for x in exp if x.startswith("== "))
    print("PASS %s: %d scenarios, %d lines match the oracle, %d frames decode cleanly" % (label, nsc, len(exp), nfr))
    return True


def main():
    """Run host and sim16 targets; print the verdict. Returns the exit code."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--elf", required=True)
    ap.add_argument("--sim16", required=True, help="path of run_sim16.sh")
    ap.add_argument("--sim-timeout", type=int, default=900)
    a = ap.parse_args()
    ok = check("host", [a.host], False, 900)
    ok = check("sim16", [a.sim16, a.elf, str(a.sim_timeout)], True, a.sim_timeout + 30) and ok
    print("c2_stream suite PASS" if ok else "c2_stream suite FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
