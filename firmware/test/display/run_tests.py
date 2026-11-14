#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""Runner for the display.c / icons.c suite (ticket WP4-aT).

For each configuration (default, serpentine, non-default cap/limit) it runs the host binary and
the sim16 ELF (16-bit int, via firmware/test/sim16/run_sim16.sh), compares every frame record with
oracle.py (built from the spec only) and checks the icon properties. Prints PASS/FAIL lines and
finally "display suite PASS" (exit 0) or "display suite FAIL" (exit 1).
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oracle  # noqa: E402

UNKNOWN_IDS = [-2, 13, 14, 15, 50, 127, -128]


def run(cmd, timeout):
    """Run a command and return its non-empty output lines.

    :param cmd: argv list.
    :param timeout: seconds.
    :return: (exit code or None on timeout, list of lines, stderr text).
    """
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, [], ""
    lines = [x.rstrip("\r") for x in p.stdout.split("\n") if x.strip() != "" and not x.startswith("SIM16_EXIT")]
    return p.returncode, lines, p.stderr


def bitmap_ascii(bm):
    """Render an 8-byte bitmap as 8 strings of '#' and '.'.

    :param bm: list of 8 ints.
    :return: list of 8 strings.
    """
    return ["".join("#" if b & (0x80 >> c) else "." for c in range(8)) for b in bm]


def check_frames(label, got, exp, fails):
    """Compare the frame section of the output (up to the ICONS marker) with the oracle.

    :param label: target label for messages.
    :param got: output lines.
    :param exp: oracle lines.
    :param fails: list that receives failure messages.
    :return: number of mismatching lines.
    """
    idx = got.index("ICONS") if "ICONS" in got else len(got)
    g = got[:idx]
    bad = 0
    case = "CFG"
    for i in range(max(len(g), len(exp))):
        gl = g[i] if i < len(g) else "<missing>"
        el = exp[i] if i < len(exp) else "<extra>"
        if el.startswith("C "):
            case = el.split()[1]
        if gl != el:
            bad += 1
            if bad <= 4:
                fails.append("%s: line %d (case %s)\n    got      %s\n    expected %s" % (label, i + 1, case, gl[:150], el[:150]))
    if not got or got[-1] != "END":
        fails.append("%s: output does not end with END (truncated?)" % label)
    return bad


def parse_icons(got, fails, label):
    """Parse the ICONS section.

    :param got: output lines.
    :param label: target label.
    :param fails: failure list.
    :return: dict id -> {bm, rgb, match, ret, units, wire}.
    """
    icons = {}
    if "ICONS" not in got:
        fails.append("%s: no ICONS section" % label)
        return icons
    i = got.index("ICONS") + 1
    while i < len(got) and got[i] != "END":
        f = got[i].split()
        if f[0] == "I" and i + 4 < len(got):
            ident = int(f[1])
            bm = [int(f[2][2 * k:2 * k + 2], 16) for k in range(8)]
            s = got[i + 1].split()
            wire = "".join(got[i + 2 + k].split()[1] for k in range(3))
            icons[ident] = {"bm": bm, "rgb": tuple(int(x) for x in f[3:6]), "match": int(s[2]),
                            "ret": int(s[3]), "units": int(s[4]), "wire": wire}
            i += 5
        else:
            fails.append("%s: unexpected icon line '%s'" % (label, got[i][:80]))
            i += 1
    return icons


def lit(bm):
    """Number of lit pixels of a bitmap.

    :param bm: 8 row bytes.
    :return: popcount.
    """
    return sum(bin(b).count("1") for b in bm)


def check_icons(label, icons, cap, limit_ma, serp, fails):
    """Check the icon properties (not exact shapes) and that icon_show matches the spec render.

    :param label: target label.
    :param icons: parsed icon dict.
    :param cap: DISPLAY_CAP.
    :param limit_ma: DISPLAY_LIMIT_MA.
    :param serp: DISPLAY_SERPENTINE.
    :param fails: failure list.
    :return: None.
    """
    need = [-1, 0] + list(range(1, 13)) + [100] + UNKNOWN_IDS
    for n in need:
        if n not in icons:
            fails.append("%s: icon id %d missing" % (label, n))
    if fails:
        return
    bm = {k: tuple(v["bm"]) for k, v in icons.items()}
    if any(bm[0]):
        fails.append("%s: icon NONE (0) is not all zero: %s" % (label, bm[0]))
    for k in list(range(1, 9)) + [-1]:
        if lit(bm[k]) < 6:
            fails.append("%s: icon %d has only %d lit pixels (>= 6 needed)" % (label, k, lit(bm[k])))
    for a in range(1, 9):
        for b in range(a + 1, 9):
            if bm[a] == bm[b]:
                fails.append("%s: icons %d and %d have the same bitmap" % (label, a, b))
    for a in range(9, 13):
        if not any(bm[a]):
            fails.append("%s: learned icon %d is blank" % (label, a))
        for b in range(1, 13):
            if a != b and bm[a] == bm[b]:
                fails.append("%s: learned icon %d equals icon %d" % (label, a, b))
    for u in UNKNOWN_IDS:
        if bm[u] != bm[-1]:
            fails.append("%s: unknown id %d does not give the UNKNOWN (-1) bitmap" % (label, u))
    if not any(bm[100]) or bm[100] == bm[-1]:
        fails.append("%s: ICON_LEARN_OK (100) is blank or equals the '?' bitmap" % label)
    for k, v in sorted(icons.items()):
        if v["match"] != 1:
            fails.append("%s: icon_show(%d) differs from display_draw_bitmap(icon_bitmap, icon_color)" % (label, k))
        fb = oracle.bitmap_frame(v["bm"], v["rgb"])
        out, ret, units = oracle.render(fb, cap, limit_ma, serp)
        if v["wire"] != "".join("%02X" % b for b in out) or v["ret"] != ret or v["units"] != units:
            fails.append("%s: icon_show(%d) wire image/ret/units differs from the spec render (ret %d vs %d)"
                         % (label, k, v["ret"], ret))
        if v["ret"] > limit_ma:
            fails.append("%s: icon %d draws an estimated %d mA > limit %d" % (label, k, v["ret"], limit_ma))


def print_art(icons):
    """Print every icon as ASCII art into the log.

    :param icons: parsed icon dict.
    :return: None.
    """
    order = [-1, 0] + list(range(1, 13)) + [100]
    print("icons (8x8, '#' lit):")
    for grp in (order[:5], order[5:10], order[10:]):
        rows = [bitmap_ascii(icons[k]["bm"]) for k in grp if k in icons]
        print("  " + "  ".join("id %-4d " % k for k in grp if k in icons))
        for r in range(8):
            print("  " + "  ".join("%-8s " % rr[r] for rr in rows))


def check(label, cmd, cfg, seed, nscen, timeout, art):
    """Run one target and verify frames + icons. Returns True on PASS.

    :param label: label such as "default/host".
    :param cmd: argv to run.
    :param cfg: (cap, limit_ma, serp).
    :param seed: run seed.
    :param nscen: number of scenarios.
    :param timeout: seconds.
    :param art: print the icon ASCII art when True.
    :return: True when everything matches.
    """
    cap, lim, serp = cfg
    res = run(cmd, timeout)
    if res[0] is None:
        print("FAIL %s: timeout after %ds" % (label, timeout))
        return False
    rc, got, err = res
    fails = []
    if rc != 0:
        fails.append("%s: exit code %d %s" % (label, rc, err.strip()[:300]))
    exp = oracle.expected(seed, nscen, cap, lim, serp)
    nbad = check_frames(label, got, exp, fails)
    icons = parse_icons(got, fails, label)
    check_icons(label, icons, cap, lim, serp, fails)
    if art and icons:
        print_art(icons)
    if fails:
        print("FAIL %s: %d mismatching frame lines of %d" % (label, nbad, len(exp)))
        for f in fails[:14]:
            print("  " + f)
        return False
    print("PASS %s: cap=%d limit=%dmA serp=%d, %d directed + %d random frames and %d icons match the spec"
          % (label, cap, lim, serp, len(oracle.FRAME_NAMES) + 11, nscen, len(icons)))
    return True


def main():
    """Parse arguments and run all configurations on host and sim16.

    :return: process exit code.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", default="build")
    ap.add_argument("--sim16", required=True, help="path of run_sim16.sh")
    ap.add_argument("--cfg", action="append", required=True, help="name:cap:limit_ma:serp")
    ap.add_argument("--seed", type=lambda s: int(s, 0), default=1)
    ap.add_argument("--nhost", type=int, default=1000)
    ap.add_argument("--nsim", type=int, default=40)
    ap.add_argument("--sim-timeout", type=int, default=600)
    a = ap.parse_args()
    ok = True
    first = True
    for c in a.cfg:
        name, cap, lim, serp = c.split(":")
        cfg = (int(cap), int(lim), int(serp))
        host = os.path.join(a.build, "test_display_%s_host" % name)
        elf = os.path.join(a.build, "test_display_%s_avr.elf" % name)
        ok = check(name + "/host", [host, str(a.seed), str(a.nhost)], cfg, a.seed, a.nhost, 600, first) and ok
        first = False
        ok = check(name + "/sim16", [a.sim16, elf, str(a.sim_timeout)], cfg, a.seed, a.nsim,
                   a.sim_timeout + 30, False) and ok
    if ok:
        print("display suite PASS")
        return 0
    print("display suite FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
