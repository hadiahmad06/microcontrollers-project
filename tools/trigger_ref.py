# [AI-GENERATED: Claude Code]
"""Integer-only Python mirror of firmware/src/trigger.c (ticket T-trig).

WORKING ASSUMPTION: open_questions Q2, Q3, not decided.
Promoted from our own spike docs/agent/hadi/spikes/trigger/trigger_ref.py (S2-2); EMA-L1 only,
shift S = 3 fixed. Bit-exact with trigger.c: same state machine, same order of operations.
Python >> on negative ints is arithmetic (floor), matching the C rule (C1.1).

Usage: python3 tools/trigger_ref.py --selftest
"""
import os
import random
import sys

SHIFT = 3
WARMUP, ARMED, LOCKED, REARM = 0, 1, 2, 3
STAT_MAX_COUNTS = 12285
THR_MAX_COUNTS = 12284
MIN_QUIET = 16
DEFAULT_DEBOUNCE, DEFAULT_QUIET, DEFAULT_WARM, DEFAULT_MG = 2, 30, 32, 250
AXIS_MIN, AXIS_MAX = -2048, 2047
PRE, POST = 15, 135  # window = samples[t-15 : t+135]


def mg_to_counts(mg):
    """Convert threshold_mg to counts: (mg + 1) >> 1, clamped to 12284; 0 stays 0.

    Args:
        mg: integer threshold in mg, 0..65535.
    Returns:
        integer threshold in counts.
    """
    if not 0 <= mg <= 65535:
        raise ValueError("mg must be in 0..65535, got %r" % (mg,))
    if mg == 0:
        return 0
    return min((mg + 1) >> 1, THR_MAX_COUNTS)


def _clamp(v):
    """Clamp one axis to [-2048, 2047]."""
    return AXIS_MIN if v < AXIS_MIN else (AXIS_MAX if v > AXIS_MAX else v)


class Trigger:
    """Mirror of trigger_t. Field names and meaning match trigger.h."""

    def __init__(self, cfg=None):
        """Initialise like trigger_init().

        Args:
            cfg: dict with ALL three keys debounce, quiet, warm required (extra keys ignored; a
                missing key raises KeyError); None = defaults.
        Returns:
            None
        """
        c = {"debounce": DEFAULT_DEBOUNCE, "quiet": DEFAULT_QUIET, "warm": DEFAULT_WARM}
        if cfg is not None:
            c = {k: cfg[k] for k in ("debounce", "quiet", "warm")}
        c["debounce"] = max(c["debounce"], 1)
        c["quiet"] = max(c["quiet"], MIN_QUIET)
        c["warm"] = max(c["warm"], 16)
        self.cfg = c
        self.base = [0, 0, 0]
        self.resync()
        self.set_threshold_mg(DEFAULT_MG)

    def resync(self):
        """Restart after a gap (trigger_resync): re-seed from the next sample, warm up again.

        Returns:
            None
        """
        self.state = WARMUP
        self.seeded = 0
        self.warm_n = 0
        self.run = 0
        self.quiet_n = 0
        self.stat = 0

    def set_threshold_mg(self, mg):
        """Set the threshold (trigger_set_threshold_mg); 0 disables triggering.

        Args:
            mg: integer threshold in mg of L1 deviation, 0..65535.
        Returns:
            None
        """
        self.thr = mg_to_counts(mg)  # raises ValueError outside 0..65535
        self.thr_mg = mg
        self.lo = (self.thr + 1) >> 1

    def statistic(self):
        """Statistic of the last sample fed (trigger_statistic).

        Returns:
            int, counts.
        """
        return self.stat

    def feed(self, s):
        """Feed one drained sample (trigger_feed).

        Args:
            s: sequence of three ints (x, y, z); each axis is clamped to [-2048, 2047].
        Returns:
            True if this sample is the trigger sample t, else False.
        """
        if not self.seeded:
            for i in range(3):
                self.base[i] = _clamp(s[i]) << SHIFT
            self.seeded = 1
            self.warm_n = 1
            self.stat = 0
            return False
        stat = 0
        for i in range(3):
            x = _clamp(s[i])
            stat += abs(x - (self.base[i] >> SHIFT))
            self.base[i] += x - (self.base[i] >> SHIFT)
        self.stat = stat
        fire = False
        if self.state == WARMUP and self.warm_n >= self.cfg["warm"]:
            self.state = ARMED
            self.run = 0
        if self.state == WARMUP:
            if self.warm_n < 255:
                self.warm_n += 1
        elif self.state == ARMED:
            if self.thr != 0 and stat > self.thr:
                if self.run < 255:
                    self.run += 1
            else:
                self.run = 0
            if self.run >= self.cfg["debounce"]:
                self.state = LOCKED
                self.run = 0
                fire = True
        elif self.state == REARM:
            if stat < self.lo:
                if self.quiet_n < 255:
                    self.quiet_n += 1
            else:
                self.quiet_n = 0
            if self.quiet_n >= self.cfg["quiet"]:
                self.state = ARMED
                self.run = 0
        return fire

    def release(self):
        """Buffer released or window dropped (trigger_release): LOCKED -> REARM.

        Returns:
            None
        """
        if self.state == LOCKED:
            self.state = REARM
            self.quiet_n = 0

    def state_hash(self, h=2166136261):
        """FNV-1a update with (stat, state, base x3, run, quiet_n, warm_n, seeded).

        Args:
            h: running 32-bit hash value (FNV offset basis to start).
        Returns:
            the updated 32-bit hash.
        """
        m = 0xFFFFFFFF
        words = [self.stat & m, self.state, self.base[0] & m, self.base[1] & m,
                 self.base[2] & m, self.run, self.quiet_n, self.warm_n, self.seeded]
        for w in words:
            h = ((h ^ w) * 16777619) & m
        return h


def run(samples, cfg=None, thr_mg=DEFAULT_MG, rel_delay=135, resync_at=-1):
    """Run the trigger over a continuous recording (offline labelling, proposal 3.4).

    A trigger index t is the Nth consecutive sample above threshold (N = debounce). release() is
    called after the state hash of sample t + rel_delay has been taken, so it takes effect for
    sample t + rel_delay + 1 and REARM quiet counting starts there (135 is one later than "window
    complete" at t + 134; this is spike/spec behaviour). rel_delay < 0 never releases, so at most
    one trigger fires per stream. resync_at >= 0 calls resync() BEFORE feeding sample resync_at,
    so that sample is the new seed (no fire before resync_at + 32 with default warm) and a pending
    release is discarded. The returned indices index into samples and feed cut_windows directly.

    Args:
        samples: list of (x, y, z) int tuples.
        cfg: dict with all keys debounce, quiet, warm, or None for defaults.
        thr_mg: threshold in mg, 0..65535 (ValueError otherwise).
        rel_delay: see above; < 0 never releases.
        resync_at: sample index before which resync() is called; < 0 never.
    Returns:
        (list of trigger indices, FNV-1a hash of the state after every sample).
    """
    t = Trigger(cfg)
    t.set_threshold_mg(thr_mg)
    trigs = []
    trig_at = -1
    h = 2166136261
    for i, s in enumerate(samples):
        if i == resync_at:
            t.resync()
            trig_at = -1
        if t.feed(s):
            trigs.append(i)
            trig_at = i
        h = t.state_hash(h)
        if trig_at >= 0 and rel_delay >= 0 and i - trig_at >= rel_delay:
            t.release()
            trig_at = -1
    return trigs, h


def cut_windows(samples, trigger_indices):
    """Cut 150-row windows samples[t-15 : t+135] around trigger indices.

    Triggers whose window starts before 0 or runs past the end are skipped. Each window holds
    samples t-15 .. t+134 inclusive, so window[15] is sample t.

    Args:
        samples: list of (x, y, z) rows.
        trigger_indices: iterable of trigger sample indices t.
    Returns:
        list of (t, window) with window a list of 150 rows.
    """
    out = []
    for t in trigger_indices:
        if t - PRE >= 0 and t + POST <= len(samples):
            out.append((t, [tuple(r) for r in samples[t - PRE:t + POST]]))
    return out


def _load_spike():
    """Import the spike's trigger_ref and synth modules; return (ref, synth) or None."""
    here = os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(here, "..", "docs", "agent", "hadi", "spikes", "trigger")
    if not os.path.isdir(d):
        return None
    sys.path.insert(0, d)
    try:
        import trigger_ref as spike_ref  # the spike's module of the same name
        import synth
    finally:
        sys.path.pop(0)
    return spike_ref, synth


def selftest():
    """Run the self checks. Returns None, raises AssertionError on failure."""
    # T2 table of mg_to_counts
    table = {0: 0, 1: 1, 2: 1, 3: 2, 250: 125, 500: 250, 24566: 12283,
             24567: 12284, 24568: 12284, 30000: 12284, 65535: 12284}
    for mg, c in table.items():
        assert mg_to_counts(mg) == c, (mg, mg_to_counts(mg), c)
    # cut_windows bounds
    st = [(i, 0, 0) for i in range(400)]
    got = cut_windows(st, [14, 15, 100, 264, 265, 266, 399])
    assert [t for t, _ in got] == [15, 100, 264, 265], [t for t, _ in got]
    assert all(len(w) == 150 and w[15][0] == t for t, w in got)
    assert cut_windows(st, [15])[0][1][0][0] == 0
    # clamp: out of range input behaves like the clamped input
    a = Trigger()
    b = Trigger()
    for s in [(0, 0, 0)] * 40 + [(30000, -30000, 5000)] * 3:
        a.feed(s)
        b.feed((_clamp(s[0]), _clamp(s[1]), _clamp(s[2])))
    assert a.state_hash() == b.state_hash()
    # top of the range: only a full-scale swing fires at 12284
    t = Trigger(dict(debounce=1, quiet=30, warm=32))
    t.set_threshold_mg(65535)
    assert t.thr == 12284
    fired = [t.feed(s) for s in [(-2048,) * 3] * 40 + [(2047,) * 3]]
    assert fired[-1] and not any(fired[:-1]) and t.stat == 12285
    t = Trigger(dict(debounce=1, quiet=30, warm=32))
    t.set_threshold_mg(65535)
    fired = [t.feed(s) for s in [(-2048,) * 3] * 40 + [(2047, 2047, 2046)]]
    assert not any(fired)  # stat 12284 is not > 12284
    # equality with the spike (EMA-L1, S = 3)
    sp = _load_spike()
    n = 0
    if sp is not None:
        spike_ref, synth = sp
        rng = random.Random(2361)
        for k in range(240):
            kind = synth.KINDS[k % len(synth.KINDS)]
            x = synth.make_stream(kind, 1000 + k)
            samples = x[0] if isinstance(x, tuple) else x
            samples = [tuple(r) for r in samples]
            thr = rng.choice([0, 100, 250, 400, 800, 2000, 24567])
            rel = rng.choice([-1, 0, 20, 135])
            rs = rng.choice([-1, -1, 100, 300])
            cfg = dict(debounce=rng.choice([1, 2, 3]), quiet=rng.choice([10, 30, 60]),
                       warm=rng.choice([8, 32, 40]))
            scfg = dict(cfg, stat=0, shift=3)
            ti, _ = run(samples, cfg, thr, rel, rs)
            si, _ = spike_ref.run(samples, scfg, thr, rel, rs)
            assert ti == si, (k, kind, ti, si)
            n += 1
    if sp is None:
        print("selftest: spike-equality SKIPPED (spike not found)")
    else:
        print("selftest: %d spike-equality streams" % n)
    print("trigger_ref selftest PASS")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        print(__doc__)
# [END AI-GENERATED]
