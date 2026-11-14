#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""run_tests.py - runner of the mlp suite (ticket 3.4T). For every seed: generate a random model
(gen_model.py), build driver.c + sim16.c + <impl>/mlp.c for host and for sim16 (AVR, 16-bit int),
run both, and compare every printed stage with the independent oracle (oracle.py).
Prints PASS/FAIL per check and finally `mlp suite PASS` (exit 0) or `mlp suite FAIL` (exit 1).
Compiler settings come from the environment (set by the Makefile from common.mk)."""
import argparse
import json
import os
import shlex
import subprocess
import sys
import time

import oracle

HERE = os.path.dirname(os.path.abspath(__file__))
FAILS = []
STAGES = ["x8", "acc1", "h", "logits", "top1", "margin"]


def report(ok, name, detail=""):
    """Print one PASS/FAIL line and remember failures. Args: ok: bool; name: check name;
    detail: extra text. Returns: ok."""
    print("%s [%s]%s" % ("PASS" if ok else "FAIL", name, (" " + detail) if detail else ""))
    if not ok:
        FAILS.append(name)
    return ok


def run(cmd, timeout=600):
    """Run a command, capturing output. Args: cmd: argv list; timeout: seconds.
    Returns: CompletedProcess (stdout/stderr text)."""
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                          timeout=timeout)


def build(kind, impl, mdir, out, seed_vec, n_rand):
    """Compile the driver for host or sim16. Args: kind: 'host' or 'avr'; impl: dir with
    mlp.c/mlp.h; mdir: dir with gesture_model.h and edge_vectors.h; out: output file;
    seed_vec: PRNG seed; n_rand: random vector count. Returns: (ok, compiler messages)."""
    cc = os.environ["HOST_CC" if kind == "host" else "AVR_CC"]
    flags = shlex.split(os.environ["HOST_CFLAGS" if kind == "host" else "AVR_CFLAGS"])
    cmd = ([cc, "-iquote", mdir, "-iquote", impl] + flags +
           ["-DVEC_SEED=%du" % seed_vec, "-DN_RAND=%du" % n_rand, "-o", out,
            os.path.join(HERE, "driver.c"), os.environ["SIM16_SRC"], os.path.join(impl, "mlp.c")])
    p = run(cmd)
    return p.returncode == 0, p.stdout + p.stderr


def execute(kind, elf):
    """Run a built image. Args: kind: 'host' or 'avr'; elf: path. Returns: (exit code, stdout)."""
    if kind == "host":
        p = run([elf])
    else:
        p = run([os.environ["SIM16_RUN"], elf, "600"])
    return p.returncode, p.stdout


def parse(text):
    """Parse driver output. Args: text. Returns: dict with 'info', 'vec' (index -> record),
    'req' (list of tuples), 'fwdfail' (list), or raises ValueError on malformed lines."""
    res = {"info": None, "vec": {}, "req": [], "fwdfail": []}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("S "):
            t = line.split()
            rec = res["vec"].setdefault(int(t[1]), {"x8": [], "acc1": [], "h": [], "logits": []})
            vals = [int(v) for v in t[4:]]
            if int(t[3]) != len(rec[t[2]]):
                raise ValueError("stage %s of vector %s out of order" % (t[2], t[1]))
            rec[t[2]].extend(vals)
        elif line.startswith("T "):
            t = line.split()
            rec = res["vec"].setdefault(int(t[1]), {"x8": [], "acc1": [], "h": [], "logits": []})
            rec["top1"], rec["margin"] = int(t[2]), int(t[3])
        elif line.startswith("I "):
            res["info"] = [int(t) for t in line.split()[1:]]
        elif line.startswith("R "):
            res["req"].append(tuple(int(t) for t in line.split()[1:]))
        elif line.startswith("FWDFAIL"):
            res["fwdfail"].append(int(line.split()[1]))
    return res


def check_output(tag, model, features, res, exit_code):
    """Compare parsed driver output with the oracle. Args: tag: label; model: sidecar dict;
    features: list of feature vectors (edge + random); res: parse() result; exit_code: of the run.
    Returns: None (reports PASS/FAIL per check)."""
    info = model["info"]
    exp_info = [model["hash"], info["format_version"], info["feature_version"], info["odr_hz"],
                info["range_g"], info["conf_shift"], info["default_reject"]]
    report(res["info"] == exp_info, tag + " model_info",
           "" if res["info"] == exp_info else "got %s want %s" % (res["info"], exp_info))
    n = len(features)
    report(sorted(res["vec"]) == list(range(n)), tag + " vector count", "(%d vectors)" % n)
    bad = {s: [] for s in STAGES}
    for i, f in enumerate(features):
        got = res["vec"].get(i)
        if got is None:
            for s in STAGES:
                bad[s].append((i, None, None))
            continue
        exp = oracle.forward(model, f)
        for s in STAGES:
            if got[s] != exp[s]:
                bad[s].append((i, got[s], exp[s]))
    for s in STAGES:
        if bad[s]:
            i, g, e = bad[s][0]
            report(False, "%s %s" % (tag, s), "%d/%d vectors differ; first #%d got %s want %s"
                   % (len(bad[s]), n, i, g, e))
        else:
            report(True, "%s %s" % (tag, s), "(%d vectors)" % n)
    report(not res["fwdfail"], tag + " mlp_forward == staged calls",
           "" if not res["fwdfail"] else "differs on vectors %s" % res["fwdfail"][:5])
    exp_req = oracle.requant_sweep()
    got_req = res["req"]
    nbad = sum(1 for g, e in zip(got_req, exp_req) if g != e)
    ok = len(got_req) == len(exp_req) and nbad == 0
    first = next(((g, e) for g, e in zip(got_req, exp_req) if g != e), None)
    report(ok, tag + " mlp_requant sweep",
           "(%d cases)" % len(exp_req) if ok else
           "%d/%d differ (got %d lines); first (acc,m,sh,got) %s want %s"
           % (nbad, len(exp_req), len(got_req), first[0] if first else None,
              first[1] if first else None))
    report(exit_code == 0, tag + " driver exit code", "(%d)" % exit_code)


def coverage(models_feats):
    """Check the generated test data really exercises the interesting cases (guards against a
    vacuous suite). Args: models_feats: list of (model, features). Returns: None."""
    seen = {"x8=+127": 0, "x8=-127": 0, "x8=0 all": 0, "d=+65535": 0, "d=-65535": 0,
            "tie ge2 with margin 0 and top1>0": 0, "all acc1<0 and h==0": 0, "h mid 1..126": 0,
            "h=127": 0, "h=0": 0, "|acc1|>65536": 0, "acc1<-65536": 0, "round tie d=+-2^(s-1)": 0}
    for model, feats in models_feats:
        for f in feats:
            r = oracle.forward(model, f)
            seen["x8=+127"] += 127 in r["x8"]
            seen["x8=-127"] += -127 in r["x8"]
            seen["x8=0 all"] += all(v == 0 for v in r["x8"])
            ds = [x - o for x, o in zip(f, model["in_off"])]
            seen["d=+65535"] += 65535 in ds
            seen["d=-65535"] += -65535 in ds
            seen["tie ge2 with margin 0 and top1>0"] += (r["margin"] == 0 and r["top1"] > 0)
            seen["all acc1<0 and h==0"] += (all(a < 0 for a in r["acc1"]) and not any(r["h"]))
            seen["h mid 1..126"] += any(0 < v < 127 for v in r["h"])
            seen["h=127"] += 127 in r["h"]
            seen["h=0"] += 0 in r["h"]
            seen["|acc1|>65536"] += any(abs(a) > 65536 for a in r["acc1"])
            seen["acc1<-65536"] += any(a < -65536 for a in r["acc1"])
            seen["round tie d=+-2^(s-1)"] += any(
                s > 0 and abs(d) == (1 << (s - 1)) for d, s in zip(ds, model["in_sh"]))
    for k, v in seen.items():
        report(v > 0, "coverage: " + k, "(%d vectors)" % v)


def main():
    """Entry point. Returns: process exit code."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--impl", required=True, help="directory holding mlp.c and mlp.h")
    ap.add_argument("--build", default="build")
    ap.add_argument("--seeds", default="1,2,3,4,5")
    ap.add_argument("--host-n", type=int, default=3000)
    ap.add_argument("--sim-n", type=int, default=150)
    ap.add_argument("--skip-sim", action="store_true")
    a = ap.parse_args()
    impl, bdir = os.path.abspath(a.impl), os.path.abspath(a.build)
    os.makedirs(bdir, exist_ok=True)
    seeds = [int(s) for s in a.seeds.split(",")]
    assert len(seeds) >= 4
    cov = []
    for seed in seeds:
        mdir = os.path.join(bdir, "m%d" % seed)
        os.makedirs(mdir, exist_ok=True)
        p = run([sys.executable, os.path.join(HERE, "gen_model.py"), str(seed),
                 os.path.join(mdir, "gesture_model.h")])
        if not report(p.returncode == 0, "model %d generate" % seed, p.stderr.strip()):
            continue
        with open(os.path.join(mdir, "gesture_model.json")) as f:
            model = json.load(f)
        edge = model["edge"]
        vseed = 0xC0FFEE00 + seed
        for kind, n in [("host", a.host_n)] + ([] if a.skip_sim else [("avr", a.sim_n)]):
            tag = "model %d (%s) %s" % (seed, model["variant"], "host" if kind == "host" else "sim16")
            out = os.path.join(mdir, "driver_" + ("host" if kind == "host" else "avr.elf"))
            ok, msg = build(kind, impl, mdir, out, vseed, n)
            if not report(ok, tag + " build", "" if ok else "\n" + msg):
                continue
            t0 = time.time()
            try:
                code, text = execute(kind, out)
            except subprocess.TimeoutExpired:
                report(False, tag + " run", "timeout")
                continue
            dt = time.time() - t0
            print("     (%s run: %.1f s)" % (kind, dt))
            try:
                res = parse(text)
            except (ValueError, IndexError) as e:
                report(False, tag + " parse output", repr(e))
                continue
            feats = edge + oracle.random_features(model, vseed, n)
            check_output(tag, model, feats, res, code)
            if kind == "host":
                cov.append((model, feats))
    if cov:
        coverage(cov)
    if FAILS:
        print("mlp suite FAIL (%d failed checks)" % len(FAILS))
        return 1
    print("mlp suite PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
