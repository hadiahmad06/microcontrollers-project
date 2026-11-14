# [AI-GENERATED: Claude Code]
"""Host tests and rate table for the trigger spike (ticket S2-2). UNVERIFIED: synthetic data.

  python3 evaluate.py compare   C (./trigger_cli) versus Python mirror, bit for bit
  python3 evaluate.py table     rate table, computed with the C code
"""
import math
import re
import statistics
import subprocess
import sys

import synth
import trigger_ref as tr

CLI = "./trigger_cli"
REL = 135  # window complete (t+134) then released at once; see proposal D5


def cfg_tuple(c):
    """Config dict to the tuple order of the CLI header.

    Args:
        c: trigger config dict with keys stat, shift, debounce, quiet, warm.
    Returns:
        tuple (stat, shift, debounce, quiet, warm).
    """
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
                       quiet=(16, 30, 40)[k % 3], warm=(16, 32, 40)[(k // 5) % 3])
            jobs.append(dict(samples=samples, cfg=cfg, thr_mg=(60, 150, 300, 600, 1200, 0, 65535)[k % 7],
                             rel=(135, 0, 300, -1)[(k // 2) % 4],
                             resync=(-1, -1, -1, 320)[(k // 7) % 4]))
            k += 1
    # extreme full-scale streams for the top of the threshold range (S2-2R F-05): a swing from
    # -2048 to +2047 on all axes gives the largest possible statistic, 12285 counts.
    swing = [(-2048, -2048, -2048)] * 20 + [(2047, 2047, 2047)] + [(-2048, -2048, -2048)] * 60
    for thr in (24566, 24567, 24568, 24569, 65535):
        jobs.append(dict(samples=swing, cfg=dict(stat=0, shift=3, debounce=1, quiet=30, warm=16),
                         thr_mg=thr, rel=-1, resync=-1))
    got = run_c(jobs)
    for thr, (ct, _) in zip((24566, 24567, 24568, 24569, 65535), got[-5:]):
        assert ct == [20], (thr, ct)  # clamped thresholds still fire on the full-scale swing
    ntrig = 0
    for idx, (j, (ct, ch)) in enumerate(zip(jobs, got)):
        pt, ph = tr.run(j["samples"], j["cfg"], j["thr_mg"], j["rel"], j["resync"])
        if pt != ct or ph != ch:
            print("MISMATCH stream %d cfg %s thr %d: C %s %d  PY %s %d" % (idx, j["cfg"], j["thr_mg"], ct, ch, pt, ph))
            sys.exit(1)
        ntrig += len(pt)
    print("compare: %d streams, %d triggers, trigger indices and per-sample state hash identical (C vs Python)" % (len(jobs), ntrig))


def pct(v, n):
    """Format v out of n as a right-aligned whole-number percentage.

    Args:
        v: count of hits.
        n: total count (0 gives a placeholder).
    Returns:
        string such as " 47%", or "  - " when n is 0.
    """
    return "%3d%%" % round(100.0 * v / n) if n else "  - "


# The recommended rule (proposal section 1, decisions 1..5); equals the code defaults (selfcheck).
REC_CFG = dict(stat=tr.STAT_EMA_L1, shift=3, debounce=2, quiet=30, warm=32)
REC_MG = 250

RULES = [
    ("EMA-L1 S2 N2", dict(stat=tr.STAT_EMA_L1, shift=2, debounce=2, quiet=30, warm=32), (150, 300)),
    ("EMA-L1 S3 N2", dict(stat=tr.STAT_EMA_L1, shift=3, debounce=2, quiet=30, warm=32), (150, 200, 250, 300, 400)),
    ("EMA-L1 S3 N1", dict(stat=tr.STAT_EMA_L1, shift=3, debounce=1, quiet=30, warm=32), (250,)),
    ("EMA-L1 S3 N3", dict(stat=tr.STAT_EMA_L1, shift=3, debounce=3, quiet=30, warm=32), (250,)),
    ("EMA-L1 S4 N2", dict(stat=tr.STAT_EMA_L1, shift=4, debounce=2, quiet=30, warm=32), (150, 250, 300, 450)),
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


def margins(nseed=100, seed0=1000, kinds=None):
    """Print the largest statistic seen on non-event streams versus the weakest gesture peak.

    Uses the Python mirror (identical to C) on the recommended rule. Values in mg (2 per count).

    Args:
        nseed: streams per scenario; seed0: first seed; kinds: list of scenarios, None = all.
    Returns:
        None
    """
    cfg = REC_CFG
    print("Statistic margin, EMA-L1 S3 (mg of L1 deviation, 2 mg per count), seeds %d..%d, %d streams each:"
          % (seed0, seed0 + nseed - 1, nseed))
    for kind in (kinds or synth.KINDS):
        peaks = []
        for s in range(seed0, seed0 + nseed):
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


def rearm(nseed=1000):
    """Re-arm failure rate versus threshold on tremor streams (S2-2R F-02).

    After a forced LOCKED and release at sample 40 (the wand just finished a window), count the
    tremor streams that never get back to ARMED in the remaining 460 samples. Re-arm needs 30
    consecutive samples with stat < lo = thr/2, so the tremor peak limits the lowest usable
    threshold. Uses the Python mirror (equal to C). Synthetic, UNVERIFIED.

    Args:
        nseed: number of tremor streams (seeds 5000 ...).
    Returns:
        None
    """
    print("Re-arm after release on %d tremor streams (seeds 5000..%d), EMA-L1 S3 N2, quiet 30. UNVERIFIED: synthetic." %
          (nseed, 4999 + nseed))
    streams = [synth.make_stream("tremor", s)[0] for s in range(5000, 5000 + nseed)]
    peak = 0
    for smp in streams:
        t = tr.Trigger(REC_CFG)
        t.set_threshold_mg(0)
        for i, x in enumerate(smp):
            t.feed(x)
            if i >= 32:
                peak = max(peak, 2 * t.stat)
    print("  tremor peak statistic over these streams: %d mg" % peak)
    for thr in (100, 150, 175, 200, 225, 250, 300):
        never = 0
        for smp in streams:
            t = tr.Trigger(REC_CFG)
            t.set_threshold_mg(thr)
            for i, x in enumerate(smp):
                t.feed(x)
                if i == 40:
                    t.state = tr.LOCKED  # test hook: pretend a window just fired
                    t.release()
            if t.state != tr.ARMED:
                never += 1
        print("  thr %4d mg (lo %4d mg): never re-armed %4d / %d  (%s)" %
              (thr, 2 * t.lo, never, nseed, pct(never, nseed).strip()))


def fresh(nseed=1000):
    """False-trigger rates on fresh seeds (5000 ...), not the seeds the thresholds were tuned on.

    Args:
        nseed: streams per scenario.
    Returns:
        None
    """
    print("Fresh seeds 5000..%d (tuning used 1000..1059), %d tilt streams each, UNVERIFIED: synthetic:" % (4999 + nseed, nseed))
    streams = [synth.make_stream("tilt", s)[0] for s in range(5000, 5000 + nseed)]
    for name, cfg, thrs in (("EMA-L1 S3 N2", REC_CFG, (200, 220, 250)),
                            ("EMA-L1 S4 N2", dict(REC_CFG, shift=4), (250, 300))):
        for thr in thrs:
            jobs = [dict(samples=s, cfg=cfg, thr_mg=thr, rel=REL, resync=-1) for s in streams]
            fp = sum(1 for trigs, _ in run_c(jobs) if trigs)
            print("  %-13s thr %d mg: tilt false triggers %d / %d (%s)" % (name, thr, fp, nseed, pct(fp, nseed).strip()))
    margins(nseed, 5000, ["tilt", "tremor"])


def header_defaults():
    """Read the TRIG_DEFAULT_* values out of trigger.h.

    Returns:
        dict name -> int (for example {"SHIFT": 3, "MG": 250}).
    """
    out = {}
    with open("trigger.h") as f:
        for ln in f:
            m = re.match(r"#define TRIG_DEFAULT_(\w+)\s+(\d+)u", ln)
            if m:
                out[m.group(1)] = int(m.group(2))
    return out


def selfcheck():
    """Assert the rule properties claimed in the proposal (Python mirror, equal to C).

    Returns:
        None; raises AssertionError on failure.
    """
    assert [tr.mg_to_counts(m) for m in (0, 1, 2, 3, 500, 24566, 24567, 24568, 24569, 65535)] == \
        [0, 1, 1, 2, 250, 12283, 12284, 12284, 12284, 12284]
    # the recommended rule is the code default, in the C header and in the mirror (S2-2R F-01)
    hd = header_defaults()
    assert (hd["SHIFT"], hd["DEBOUNCE"], hd["QUIET"], hd["WARM"], hd["MG"]) == (3, 2, 30, 32, REC_MG)
    assert tr.DEFAULT_CFG == REC_CFG and tr.DEFAULT_MG == REC_MG
    # top of the range: a threshold above the largest statistic can fire (clamped), 12285 could not
    t = tr.Trigger(dict(REC_CFG, debounce=1, warm=16))
    t.set_threshold_mg(65535)
    assert t.thr == 12284
    got = [t.feed(s) for s in [(-2048,) * 3] * 20 + [(2047,) * 3]]
    assert got.index(True) == 20 and t.stat == 12285
    # init clamps: shift 1..8, quiet >= 16, unknown stat -> EMA-L1
    c = tr.Trigger(dict(stat=9, shift=40, debounce=0, quiet=1, warm=1)).cfg
    assert (c["stat"], c["shift"], c["debounce"], c["quiet"], c["warm"]) == (0, 8, 1, 16, 16)
    rest = (0, 0, 512)
    # warm-up: huge motion in the first 32 samples never fires; first allowed index is 32
    t = tr.Trigger()
    t.set_threshold_mg(250)
    fired = [i for i in range(60) if t.feed((0, 0, 512) if i == 0 else (1500 * (-1) ** i, -1500, 1500))]
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
    print("selfcheck: defaults == recommendation, mg_to_counts and top clamp, init clamps, warm-up gate, "
          "disable, re-arm, trigger index >= 15: OK; two pulses fired at", trigs)


if __name__ == "__main__":
    if sys.argv[1] == "compare":
        compare()
    else:
        table()
        print()
        per_gesture("EMA-L1 S3 N2", REC_CFG, REC_MG)
        print()
        margins()
        print()
        rearm()
        print()
        fresh()
        print()
        selfcheck()
# [END AI-GENERATED]
