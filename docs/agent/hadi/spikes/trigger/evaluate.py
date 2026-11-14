# [AI-GENERATED: Claude Code]
"""Host tests and rate table for the trigger spike (ticket S2-2). UNVERIFIED: synthetic data.

  python3 evaluate.py compare   C (./trigger_cli) versus Python mirror, bit for bit
  python3 evaluate.py table     rate table, computed with the C code
"""
import math
import statistics
import subprocess
import sys

import synth
import trigger_ref as tr

CLI = "./trigger_cli"
REL = 135  # window complete (t+134) then released at once; see proposal D5


def cfg_tuple(c):
    """Config dict to the tuple order of the CLI header (stat shift debounce quiet warm)."""
    return (c["stat"], c["shift"], c["debounce"], c["quiet"], c["warm"])


def run_c(jobs):
    """Run many streams through the C harness.

    Args:
        jobs: list of dicts with keys samples, cfg, thr_mg, rel, resync.
    Returns:
        list of (trigger index list, hash) in job order.
    """
    lines = [str(len(jobs))]
    for j in jobs:
        n = len(j["samples"])
        lines.append("%d %d %d %d %d %d %d %d %d" % (cfg_tuple(j["cfg"]) + (j["thr_mg"], j["rel"], j["resync"], n)))
        lines.append(" ".join("%d %d %d" % s for s in j["samples"]))
    res = subprocess.run([CLI], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True)
    out = []
    for ln in res.stdout.strip().split("\n"):
        f = [int(v) for v in ln.split()]
        out.append((f[1:1 + f[0]], f[-1]))
    return out


def compare():
    """Check C and Python agree on trigger indices and per-sample internal state.

    Returns:
        None; exits non-zero on the first mismatch.
    """
    jobs = []
    k = 0
    for seed in range(1, 41):
        for kind in synth.KINDS:
            samples, _ = synth.make_stream(kind, seed)
            cfg = dict(stat=k % 4, shift=3 + (k // 4) % 3, debounce=1 + (k // 3) % 3,
                       quiet=(10, 30, 40)[k % 3], warm=(16, 32, 40)[(k // 5) % 3])
            jobs.append(dict(samples=samples, cfg=cfg, thr_mg=(60, 150, 300, 600, 1200, 0)[k % 6],
                             rel=(135, 0, 300, -1)[(k // 2) % 4],
                             resync=(-1, -1, -1, 320)[(k // 7) % 4]))
            k += 1
    got = run_c(jobs)
    ntrig = 0
    for idx, (j, (ct, ch)) in enumerate(zip(jobs, got)):
        pt, ph = tr.run(j["samples"], j["cfg"], j["thr_mg"], j["rel"], j["resync"])
        if pt != ct or ph != ch:
            print("MISMATCH stream %d cfg %s thr %d: C %s %d  PY %s %d" % (idx, j["cfg"], j["thr_mg"], ct, ch, pt, ph))
            sys.exit(1)
        ntrig += len(pt)
    print("compare: %d streams, %d triggers, trigger indices and per-sample state hash identical (C vs Python)" % (len(jobs), ntrig))


def pct(v, n):
    """Percentage string."""
    return "%3d%%" % round(100.0 * v / n) if n else "  - "


RULES = [
    ("EMA-L1 S3 N2", dict(stat=tr.STAT_EMA_L1, shift=3, debounce=2, quiet=30, warm=32), (200, 250, 400)),
    ("EMA-L1 S3 N1", dict(stat=tr.STAT_EMA_L1, shift=3, debounce=1, quiet=30, warm=32), (250,)),
    ("EMA-L1 S3 N3", dict(stat=tr.STAT_EMA_L1, shift=3, debounce=3, quiet=30, warm=32), (250,)),
    ("EMA-L1 S4 N2", dict(stat=tr.STAT_EMA_L1, shift=4, debounce=2, quiet=30, warm=32), (300, 450)),
    ("EMA-MAX S3 N2", dict(stat=tr.STAT_EMA_MAX, shift=3, debounce=2, quiet=30, warm=32), (150, 250)),
    ("JERK-L1 N2", dict(stat=tr.STAT_JERK_L1, shift=3, debounce=2, quiet=30, warm=32), (60, 120, 240)),
    ("MAG2 N2", dict(stat=tr.STAT_MAG2, shift=3, debounce=2, quiet=30, warm=32), (150, 300, 600)),
]


def table(nseed=60):
    """Print the rate table (computed with the C code) for the rules in RULES.

    Args:
        nseed: streams per scenario.
    Returns:
        None
    """
    streams = {k: [synth.make_stream(k, s) for s in range(1000, 1000 + nseed)] for k in synth.KINDS}
    print("Rates over %d streams per scenario, 500 samples each, 100 Hz. UNVERIFIED: synthetic data." % nseed)
    print("FP = streams with >= 1 trigger. detect = first trigger within [onset, onset+dur+20].")
    print("lat = trigger sample minus onset (samples); >15 means the onset is cut off the window start (P = 15).")
    print("%-14s %5s | %5s %5s %6s %5s | %6s %5s %5s %5s %5s %5s" %
          ("rule", "thr", "rest", "tilt", "tremor", "bump", "detect", "latMed", "latP90", ">15", "pre", "twice"))
    for name, cfg, thrs in RULES:
        for thr in thrs:
            jobs, tags = [], []
            for kind in synth.KINDS:
                for samples, meta in streams[kind]:
                    jobs.append(dict(samples=samples, cfg=cfg, thr_mg=thr, rel=REL, resync=-1))
                    tags.append(meta)
            res = run_c(jobs)
            fp = {k: 0 for k in synth.NG_KINDS}
            det = pre = twice = ng = 0
            lats = []
            for meta, (trigs, _) in zip(tags, res):
                kind = meta["kind"]
                if kind in synth.NG_KINDS:
                    fp[kind] += 1 if trigs else 0
                    continue
                ng += 1
                on, du = meta["onset"], meta["dur"]
                hits = [t for t in trigs if on <= t <= on + du + 20]
                if any(t < on for t in trigs):
                    pre += 1
                if hits:
                    det += 1
                    lats.append(hits[0] - on)
                if len([t for t in trigs if t >= on]) > 1:
                    twice += 1
            lats.sort()
            med = lats[len(lats) // 2] if lats else -1
            p90 = lats[int(len(lats) * 0.9)] if lats else -1
            late = sum(1 for v in lats if v > 15)
            print("%-14s %5d | %s %s %s %s | %s %5d %5d %s %s %s" %
                  (name, thr, pct(fp["rest"], nseed), pct(fp["tilt"], nseed), "  " + pct(fp["tremor"], nseed),
                   pct(fp["bump"], nseed), pct(det, ng), med, p90, pct(late, max(len(lats), 1)), pct(pre, ng), pct(twice, ng)))


def per_gesture(name, cfg, thr, nseed=60):
    """Print per-gesture detection rate and latency for one rule.

    Args:
        name: label; cfg: trigger config dict; thr: threshold_mg; nseed: streams per gesture.
    Returns:
        None
    """
    print("Per gesture, %s thr %d mg:" % (name, thr))
    for kind in synth.G_KINDS:
        jobs, metas = [], []
        for s in range(1000, 1000 + nseed):
            samples, meta = synth.make_stream(kind, s)
            jobs.append(dict(samples=samples, cfg=cfg, thr_mg=thr, rel=REL, resync=-1))
            metas.append(meta)
        res = run_c(jobs)
        lats, det = [], 0
        for meta, (trigs, _) in zip(metas, res):
            hits = [t for t in trigs if meta["onset"] <= t <= meta["onset"] + meta["dur"] + 20]
            if hits:
                det += 1
                lats.append(hits[0] - meta["onset"])
        print("  %-8s detect %s  latency median %s samples" %
              (kind, pct(det, nseed), statistics.median(lats) if lats else "-"))


def margins(nseed=100):
    """Print the largest statistic seen on non-event streams versus the weakest gesture peak.

    Uses the Python mirror (identical to C) on the recommended rule. Values in mg (2 per count).

    Args:
        nseed: streams per scenario.
    Returns:
        None
    """
    cfg = RULES[0][1]
    print("Statistic margin, EMA-L1 S3 (mg of L1 deviation, 2 mg per count), %d streams each:" % nseed)
    for kind in synth.KINDS:
        peaks = []
        for s in range(1000, 1000 + nseed):
            samples, meta = synth.make_stream(kind, s)
            t = tr.Trigger(cfg)
            lo = meta["onset"] if kind in synth.G_KINDS else 0
            hi = meta["onset"] + meta["dur"] + 20 if kind in synth.G_KINDS else len(samples)
            pk = 0
            for i, x in enumerate(samples):
                t.feed(x)
                if i >= 32 and lo <= i <= hi:
                    pk = max(pk, t.stat)
            peaks.append(2 * pk)
        peaks.sort()
        print("  %-8s peak stat: min %5d  median %5d  max %5d" % (kind, peaks[0], peaks[len(peaks) // 2], peaks[-1]))


def selfcheck():
    """Assert the rule properties claimed in the proposal (Python mirror, equal to C).

    Returns:
        None; raises AssertionError on failure.
    """
    assert [tr.mg_to_counts(m) for m in (0, 1, 2, 3, 500, 65535)] == [0, 1, 1, 2, 250, 12285]
    rest = (0, 0, 512)
    # warm-up: huge motion in the first 32 samples never fires; first allowed index is 32
    t = tr.Trigger()
    t.set_threshold_mg(250)
    fired = [i for i in range(60) if t.feed((0, 0, 512) if i == 0 else (1500, -1500, 1500))]
    assert fired == [33], fired  # sample 32 is the first armed one (run=1), N=2 fires at 33
    # disabled
    t = tr.Trigger()
    t.set_threshold_mg(0)
    assert not any(t.feed((0, 0, 512) if i < 50 else (1500, 0, 0)) for i in range(200))
    # two pulses, release at window end, re-arm after 30 quiet samples
    stream = [rest] * 100 + [(0, int(600 * math.sin(2 * 3.14159 * k / 40)), 512) for k in range(40)]
    stream += [rest] * 160 + [(0, int(600 * math.sin(2 * 3.14159 * k / 40)), 512) for k in range(40)] + [rest] * 100
    trigs, _ = tr.run(stream, None, 250, 135)
    assert len(trigs) == 2 and trigs[0] >= 100 and trigs[1] >= 300, trigs
    assert all(i >= 15 for i in trigs)  # ring always holds 15 samples before t
    # rest, tremor never fire; and the ring condition: warm >= 16 is enforced
    assert tr.Trigger(dict(stat=0, shift=3, debounce=1, quiet=1, warm=1)).cfg["warm"] == 16
    print("selfcheck: mg_to_counts, warm-up gate, disable, re-arm, trigger index >= 15: OK; two pulses fired at", trigs)


if __name__ == "__main__":
    if sys.argv[1] == "compare":
        compare()
    else:
        table()
        print()
        per_gesture(RULES[0][0], RULES[0][1], 250)
        print()
        margins()
        print()
        selfcheck()
# [END AI-GENERATED]
