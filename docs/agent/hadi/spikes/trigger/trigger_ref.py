# [AI-GENERATED: Claude Code]
"""Integer-only Python mirror of trigger.c (ticket S2-2). UNVERIFIED on real data.

Bit-exact with trigger.c: same statistics, same state machine, same order of operations.
Python's >> on negative ints is arithmetic (floor), which matches the C rule (C1.1).
Used by the recording tool (offline labelling) and by the host tests.
"""

STAT_EMA_L1, STAT_EMA_MAX, STAT_JERK_L1, STAT_MAG2 = 0, 1, 2, 3
WARMUP, ARMED, LOCKED, REARM = 0, 1, 2, 3
STAT_MAX_COUNTS = 12285
G_COUNTS = 512
MAG2_SCALE = 10
DEFAULT_CFG = dict(stat=STAT_EMA_L1, shift=4, debounce=2, quiet=30, warm=32)
DEFAULT_MG = 300


def mg_to_counts(mg):
    """Convert threshold_mg to counts: (mg + 1) >> 1, clamped to 12285; 0 stays 0.

    Args:
        mg: integer threshold in mg, 0..65535.
    Returns:
        integer threshold in counts.
    """
    if mg == 0:
        return 0
    return min((mg + 1) >> 1, STAT_MAX_COUNTS)


class Trigger:
    """Mirror of trigger_t. Fields have the same names and meaning as in trigger.h."""

    def __init__(self, cfg=None):
        """Initialise like trigger_init().

        Args:
            cfg: dict with keys stat, shift, debounce, quiet, warm; None = defaults.
        Returns:
            None
        """
        self.cfg = dict(DEFAULT_CFG if cfg is None else cfg)
        self.cfg["debounce"] = max(self.cfg["debounce"], 1)
        self.cfg["warm"] = max(self.cfg["warm"], 16)
        self.base = [0, 0, 0]
        self.prev = [0, 0, 0]
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
        c = mg_to_counts(mg)
        self.thr_mg = mg
        if self.cfg["stat"] == STAT_MAG2:
            c = c << MAG2_SCALE
        self.thr = c
        self.lo = (c + 1) >> 1

    def _statistic(self, s):
        """Compute the statistic and update baseline/previous sample (trigger_statistic)."""
        stat = 0
        m2 = 0
        sh = self.cfg["shift"]
        mode = self.cfg["stat"]
        for i in range(3):
            x = s[i]
            dev = x - (self.base[i] >> sh)
            jerk = x - self.prev[i]
            if mode == STAT_EMA_L1:
                stat += abs(dev)
            elif mode == STAT_EMA_MAX:
                stat = max(stat, abs(dev))
            elif mode == STAT_JERK_L1:
                stat += abs(jerk)
            else:
                m2 += x * x
            self.base[i] += x - (self.base[i] >> sh)
            self.prev[i] = x
        if mode == STAT_MAG2:
            stat = abs(m2 - G_COUNTS * G_COUNTS)
        return stat

    def feed(self, s):
        """Feed one drained sample (trigger_feed).

        Args:
            s: sequence of three ints (x, y, z) in [-2048, 2047].
        Returns:
            True if this sample is the trigger sample t, else False.
        """
        if not self.seeded:
            for i in range(3):
                self.base[i] = s[i] << self.cfg["shift"]
                self.prev[i] = s[i]
            self.seeded = 1
            self.warm_n = 1
            self.stat = 0
            return False
        stat = self._statistic(s)
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
                self.run += 1
            else:
                self.run = 0
            if self.run >= self.cfg["debounce"]:
                self.state = LOCKED
                self.run = 0
                fire = True
        elif self.state == REARM:
            if stat < self.lo:
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

    def hash_words(self):
        """State words hashed after every sample (same order as trigger_cli.c).

        Returns:
            list of ints (unsigned 32-bit).
        """
        m = 0xFFFFFFFF
        return [self.stat & m, self.state, self.base[0] & m, self.base[1] & m,
                self.base[2] & m, self.run, self.quiet_n, self.warm_n]


def run(samples, cfg=None, thr_mg=DEFAULT_MG, rel_delay=0, resync_at=-1):
    """Run the trigger over a whole stream like trigger_cli.c does.

    Args:
        samples: list of (x, y, z) int tuples.
        cfg: trigger config dict or None for defaults.
        thr_mg: threshold in mg.
        rel_delay: release is called after sample (trigger index + rel_delay); < 0 never.
            Use 135 to mimic "window is complete, buffer released at once" (C1.5).
        resync_at: call resync() before this sample index; < 0 never.
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
        for w in t.hash_words():
            h = ((h ^ w) * 16777619) & 0xFFFFFFFF
        if trig_at >= 0 and rel_delay >= 0 and i - trig_at >= rel_delay:
            t.release()
            trig_at = -1
    return trigs, h
# [END AI-GENERATED]
