# [AI-GENERATED: Claude Code]
"""Independent integer-only oracle for the product trigger module (ticket T-trigT).

Written from docs/agent/hadi/briefs/T-trig_spec.md (T0-T3). The two T4 points (first fire index follows
the spike's warm_n logic; the REARM->ARMED sample never counts toward run) follow the spike's behaviour.
WORKING ASSUMPTION: open_questions Q2, Q3, not decided.

Contents
  Model      the state machine (EMA-L1, S = 3), integers only
  apply()    one driver op -> output lines (the exact text test_trigger.c prints)
  build()    directed scenarios (ops are emitted as build/scripts.h for the C driver); hand-computed fire
             indices are asserted while building, so a wrong oracle is caught here
  episode()  random episode generator (mirrored in test_trigger.c, same xorshift32 and call order)
  expected() all lines the C driver must print for (seed, number of random episodes)
Usage: oracle.py --emit-header     prints scripts.h
"""
import sys

OP_INITNULL, OP_INIT, OP_SETTHR, OP_FEED, OP_RELEASE, OP_RESYNC, OP_MG2C, OP_SCEN, OP_NULLS = range(1, 10)
M32 = 0xFFFFFFFF
WARMUP, ARMED, LOCKED, REARM = 0, 1, 2, 3
THR_MAX = 12284


def mg_to_counts(mg):
    """Spec T2: counts = (mg + 1) >> 1 in uint32, clamped to 12284; 0 stays 0."""
    if mg == 0:
        return 0
    return min((mg + 1) >> 1, THR_MAX)


def clamp_axis(v):
    """Clamp one input axis to the C1.1 range [-2048, 2047]."""
    return max(-2048, min(2047, v))


class Model:
    """Bit-exact model of the spec state machine."""

    def __init__(self):
        self.cfg = (2, 30, 32)
        self.thr_mg = self.thr = self.lo = 0
        self.state = WARMUP
        self.seeded = self.warm_n = self.run = self.quiet_n = 0
        self.base = [0, 0, 0]
        self.stat = 0

    def init(self, cfg):
        """trigger_init: NULL cfg gives defaults; otherwise clamp debounce>=1, quiet>=16, warm>=16."""
        if cfg is None:
            self.cfg = (2, 30, 32)
        else:
            d, q, w = cfg
            self.cfg = (max(1, d), max(16, q), max(16, w))
        self.base = [0, 0, 0]
        self.resync()
        self.set_thr(250)

    def set_thr(self, mg):
        """trigger_set_threshold_mg: changes thr_mg, thr, lo only."""
        self.thr_mg = mg
        self.thr = mg_to_counts(mg)
        self.lo = (self.thr + 1) >> 1

    def resync(self):
        """trigger_resync: back to WARMUP, re-seed at the next sample."""
        self.state = WARMUP
        self.seeded = 0
        self.warm_n = self.run = self.quiet_n = 0
        self.stat = 0

    def release(self):
        """trigger_release: only LOCKED reacts."""
        if self.state == LOCKED:
            self.state = REARM
            self.quiet_n = 0

    def feed(self, s):
        """trigger_feed; returns True when the trigger fires."""
        x = [clamp_axis(v) for v in s]
        if not self.seeded:
            self.base = [v << 3 for v in x]
            self.seeded = 1
            self.warm_n = 1
            self.stat = 0
            return False
        st = 0
        for i in range(3):
            b = self.base[i] >> 3
            st += abs(x[i] - b)
            self.base[i] += x[i] - b
        self.stat = st
        d, q, w = self.cfg
        if self.state == WARMUP and self.warm_n >= w:
            self.state = ARMED
            self.run = 0
        fire = False
        if self.state == WARMUP:
            self.warm_n = min(255, self.warm_n + 1)
        elif self.state == ARMED:
            if self.thr != 0 and st > self.thr:
                self.run = min(255, self.run + 1)
            else:
                self.run = 0
            if self.run >= d:
                self.state = LOCKED
                self.run = 0
                fire = True
        elif self.state == REARM:
            if st < self.lo:
                self.quiet_n = min(255, self.quiet_n + 1)
            else:
                self.quiet_n = 0
            if self.quiet_n >= q:
                self.state = ARMED
                self.run = 0
        return fire


def snap(tag, m, ret):
    """The uniform state line printed after every state-changing op (last field = trigger_statistic)."""
    return "%s %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d" % (
        tag, ret, m.state, m.stat, m.run, m.quiet_n, m.warm_n, m.seeded, m.base[0], m.base[1], m.base[2],
        m.thr, m.lo, m.thr_mg, m.cfg[0], m.cfg[1], m.cfg[2], m.stat)


def apply(m, op, a=0, b=0, c=0):
    """Apply one driver op to model m; return the list of output lines."""
    if op == OP_INITNULL:
        m.init(None)
        return [snap("I", m, 0)]
    if op == OP_INIT:
        m.init((a, b, c))
        return [snap("I", m, 0)]
    if op == OP_SETTHR:
        m.set_thr(a & 0xFFFF)
        return [snap("T", m, 0)]
    if op == OP_FEED:
        r = m.feed((a, b, c))
        return [snap("F", m, 1 if r else 0)]
    if op == OP_RELEASE:
        m.release()
        return [snap("R", m, 0)]
    if op == OP_RESYNC:
        m.resync()
        return [snap("Y", m, 0)]
    if op == OP_MG2C:
        mg = a & 0xFFFF
        return ["M %d %d" % (mg, mg_to_counts(mg))]
    if op == OP_SCEN:
        return ["S %d" % a]
    if op == OP_NULLS:
        # Cases 1..8: feed(NULL,s), feed(t,NULL), statistic(NULL), init(NULL,cfg), set_threshold(NULL),
        # release(NULL), resync(NULL), init(NULL,NULL). Format: N <case> <return value> <t unchanged>.
        return ["N %d 0 1" % k for k in range(1, 9)]
    raise ValueError(op)


class B:
    """Records ops while tracking a model, so scenarios can ask for 'stat is exactly n' samples."""

    def __init__(self):
        self.ops = []
        self.names = []
        self.m = Model()
        self.lines_of = {}
        self.fires = {}
        self.cur = -1
        self.nfeed = 0
        self.altc = 0

    def _do(self, op, a=0, b=0, c=0):
        self.ops.append((op, a, b, c))
        lines = apply(self.m, op, a, b, c)
        self.lines_of.setdefault(self.cur, []).extend(lines)
        return lines

    def scen(self, name):
        self.names.append(name)
        self.cur = len(self.names) - 1
        self.nfeed = 0
        self.altc = 0
        self.fires[self.cur] = []
        self._do(OP_SCEN, self.cur)

    def init(self, cfg):
        if cfg is None:
            self._do(OP_INITNULL)
        else:
            self._do(OP_INIT, *cfg)

    def thr(self, mg):
        self._do(OP_SETTHR, mg if mg < 32768 else mg - 65536)

    def mg2c(self, mg):
        self._do(OP_MG2C, mg if mg < 32768 else mg - 65536)

    def release(self):
        self._do(OP_RELEASE)

    def resync(self):
        self._do(OP_RESYNC)
        self.nfeed = 0

    def nulls(self):
        self._do(OP_NULLS)

    def feed(self, x, y, z):
        lines = self._do(OP_FEED, x, y, z)
        fired = lines[0].split()[1] == "1"
        if fired:
            self.fires[self.cur].append(self.nfeed)
        self.nfeed += 1
        return fired

    def alt(self, n, amp=2000):
        """n samples that alternate between +amp and -amp (statistic stays about 3*amp)."""
        for _ in range(n):
            v = amp if self.altc % 2 == 0 else -amp
            self.altc += 1
            self.feed(v, -v, v)

    def base_sample(self):
        """Sample equal to the current baseline: stat is exactly 0."""
        return tuple(v >> 3 for v in self.m.base)

    def dev_sample(self, n):
        """Sample whose statistic against the current baseline is exactly n."""
        bs = [v >> 3 for v in self.m.base]
        s = list(bs)
        left = n
        for i in range(3):
            up, down = 2047 - bs[i], bs[i] + 2048
            if up >= down:
                d = min(left, up)
                s[i] = bs[i] + d
            else:
                d = min(left, down)
                s[i] = bs[i] - d
            left -= d
        assert left == 0, "dev_sample: no room for %d" % n
        return tuple(s)

    def far_sample(self):
        """Sample at the corner farthest from the baseline: stat >= 3*1024."""
        s = []
        for v in self.m.base:
            bs = v >> 3
            s.append(2047 if 2047 - bs >= bs + 2048 else -2048)
        return tuple(s)

    def feed_base(self):
        return self.feed(*self.base_sample())

    def feed_dev(self, n):
        return self.feed(*self.dev_sample(n))

    def feed_far(self):
        return self.feed(*self.far_sample())

    def expect(self, fires):
        """Assert hand-computed fire indices for the current scenario (guards the oracle itself)."""
        assert self.fires[self.cur] == fires, "oracle sanity %s: got %r expected %r" % (
            self.names[self.cur], self.fires[self.cur], fires)


def rearm_probe(b, cfg, q_eff, mg, tag, zeros, nbig):
    """Fire, release, then: q-1 quiet + a loud sample must NOT re-arm; q-1 quiet + stat==lo must not
    count as quiet; then q quiet samples re-arm exactly and the next nbig loud samples fire."""
    b.scen("rearm %s cfg=%s mg=%d" % (tag, cfg, mg))
    b.init(cfg)
    b.thr(mg)
    lo = (mg_to_counts(mg) + 1) >> 1
    for _ in range(zeros):
        b.feed(0, 0, 0)
    for _ in range(nbig):
        b.feed_far()
    f1 = zeros + nbig - 1
    b.release()
    for _ in range(q_eff - 1):
        b.feed_dev(lo - 1)
    b.feed_far()                       # too early and loud: must not fire, resets the quiet count
    for _ in range(q_eff - 1):
        b.feed_dev(lo - 1)
    b.feed_dev(lo)                     # stat == lo is NOT quiet: resets the count again
    for _ in range(q_eff):
        b.feed_dev(lo - 1)
    for _ in range(nbig):
        b.feed_far()
    b.expect([f1, f1 + 3 * q_eff + nbig])


def rng_stream(seed, n):
    """Synthetic REF stream (own xorshift32): quiet noise, orientation changes and motion bursts."""
    r = [((seed * 2654435761 + 977) & M32) or 1]

    def nxt(k):
        x = r[0]
        x ^= (x << 13) & M32
        x ^= x >> 17
        x ^= (x << 5) & M32
        r[0] = x
        return x % k

    o = [nxt(1001) - 500 for _ in range(3)]
    out = []
    left, amp = 0, 4
    for _ in range(n):
        if left == 0:
            left = 10 + nxt(60)
            amp = (4, 4, 4, 60, 600, 1200)[nxt(6)]
            if nxt(5) == 0:
                o = [nxt(1001) - 500 for _ in range(3)]
        left -= 1
        out.append(tuple(clamp_axis(o[j] + nxt(2 * amp + 1) - amp) for j in range(3)))
    return out


REFS = []       # (samples, thr_mg, rel_delay, resync_at, fire indices): compared with tools/trigger_ref.py
PAIRS = []      # (scenario index A, scenario index B) whose F lines must be identical (clamping)
SCEN_NAMES = []


def build():
    """Build every directed scenario; returns the builder (ops, names)."""
    b = B()
    b.scen("mg_to_counts")
    for mg in (0, 1, 2, 3, 4, 5, 250, 500, 1000, 24564, 24565, 24566, 24567, 24568, 24569, 24570, 24571, 32767, 32768, 65534, 65535):
        b.mg2c(mg)

    # seed / warm-up: first possible trigger index
    for warm in (None, 0, 15, 16, 17, 32, 50, 255):
        b.scen("warmup warm=%s" % (warm,))
        b.init(None if warm is None else (1, 30, warm))
        b.thr(2)
        b.alt(40 if warm is None or warm < 40 else warm + 8)
        b.expect([33] if warm is None else [max(16, warm)])   # default: warm 32 and debounce 2

    # debounce
    for n in (1, 2, 3, 4):
        b.scen("debounce N=%d broken run" % n)
        b.init((n, 30, 16))
        b.thr(500)
        for _ in range(20):
            b.feed(0, 0, 0)
        for _ in range(n - 1):
            b.feed(2000, 0, 0)
        b.feed(*b.base_sample())          # one sub-threshold sample breaks the run
        for _ in range(n):
            b.feed(2000, 0, 0)
        b.expect([19 + 2 * n])
    for n in (1, 2, 3):
        b.scen("debounce N=%d stat==thr no, thr+1 yes" % n)
        b.init((n, 30, 16))
        b.thr(500)                         # 250 counts
        for _ in range(20):
            b.feed(0, 0, 0)
        for _ in range(3):
            b.feed_dev(250)
        for _ in range(n):
            b.feed_dev(251)
        b.expect([22 + n])

    # LOCKED ignores everything; release elsewhere ignored
    b.scen("locked ignores")
    b.init((1, 16, 16))
    b.thr(500)
    b.release()
    for _ in range(20):
        b.feed(0, 0, 0)
    b.release()
    b.feed(2000, 2000, 2000)
    for i in range(40):
        b.feed(2000 if i % 3 == 0 else 0, -2000, 0)
    b.thr(2)
    b.thr(60000)
    b.thr(500)
    for _ in range(10):
        b.feed(2000, 2000, 2000)
    b.release()
    b.expect([20])
    b.scen("release ignored in warmup armed rearm")
    b.init(None)
    b.release()
    for _ in range(10):
        b.feed(0, 0, 0)
        b.release()
    for _ in range(40):
        b.feed(0, 0, 0)
        b.release()
    b.feed(2000, 0, 0)
    b.feed(2000, 0, 0)
    b.release()
    for _ in range(12):
        b.feed_base()
    b.release()
    for i in range(25):
        b.feed_base()
        if i == 3:
            b.release()
    b.feed(2000, 0, 0)
    b.feed(2000, 0, 0)
    b.expect([51, 90])

    # REARM quiet counting, lo rounding, stat == lo, quiet clamping
    for mg in (2, 4, 6, 250, 500, 4000):
        rearm_probe(b, (1, 16, 16), 16, mg, "q16", 18, 1)
    rearm_probe(b, (1, 30, 16), 30, 250, "q30", 18, 1)
    rearm_probe(b, None, 30, 250, "default", 34, 2)
    for q, qe in ((0, 16), (15, 16), (16, 16), (17, 17)):
        rearm_probe(b, (1, q, 16), qe, 250, "q=%d" % q, 18, 1)
    rearm_probe(b, (1, 255, 16), 255, 250, "q=255", 18, 1)

    # debounce clamping
    for d in (0, 1, 15, 255):
        b.scen("clamp debounce=%d" % d)
        b.init((d, 16, 16))
        b.thr(2)
        b.alt(16 + max(d, 1) + 4)
        b.expect([15 + max(d, 1)])

    # thr 0 never fires; thr 0 mid-run
    b.scen("thr0 never fires")
    b.init((1, 16, 16))
    b.thr(0)
    b.alt(100)
    b.thr(2)
    b.alt(3)
    b.expect([100])
    b.scen("thr0 mid-run resets run")
    b.init((3, 16, 16))
    b.thr(2)
    b.alt(18)
    b.thr(0)
    b.alt(10)
    b.thr(2)
    b.alt(4)
    b.expect([30])

    # threshold change mid-stream leaves state untouched
    b.scen("threshold change mid-stream")
    b.init((3, 16, 16))
    b.thr(500)
    b.alt(17)
    b.thr(65535)
    b.alt(3)
    b.thr(500)
    b.alt(5)
    b.expect([22])
    b.thr(4000)
    b.release()
    for _ in range(20):
        b.feed_base()
    b.thr(2)
    for _ in range(10):
        b.feed_dev(1)
    b.thr(500)
    for _ in range(5):
        b.feed_base()
    b.thr(0)
    b.feed_base()

    # resync re-seeds
    b.scen("resync re-seeds")
    b.init((1, 16, 16))
    b.thr(500)
    for _ in range(30):
        b.feed(0, 0, 0)
    b.resync()
    for _ in range(15):
        b.feed(500, -300, 200)
    b.feed(2000, -2000, 2000)           # still WARMUP (warm_n 15): no fire
    b.feed(-2000, 2000, -2000)          # first armed sample: fires at rel 16
    b.resync()                          # resync while LOCKED
    b.release()
    for _ in range(17):
        b.feed(-700, 100, 900)
    b.feed(2000, 2000, 2000)
    b.release()
    for _ in range(5):
        b.feed_base()
    b.resync()                          # resync while REARM
    for _ in range(17):
        b.feed(300, 300, -300)
    b.feed(-2000, 2000, 2000)
    b.expect([16, 17, 17])

    # top of the threshold range
    for mg in (24565, 24566, 24567, 24568, 24569, 24570, 65535):
        b.scen("top A stat 12284 mg=%d" % mg)
        b.init((1, 16, 16))
        b.thr(mg)
        for _ in range(20):
            b.feed(-2048, -2048, -2048)
        b.feed_dev(12284)
        b.expect([20] if mg <= 24566 else [])
        b.scen("top B full swing mg=%d" % mg)
        b.init((1, 16, 16))
        b.thr(mg)
        for _ in range(20):
            b.feed(-2048, -2048, -2048)
        b.feed(2047, 2047, 2047)
        b.expect([20])

    # out-of-range inputs: raw int16 extremes must equal their clamped twins
    vals = (-32768, -32767, -2049, -2048, -2047, 0, 2046, 2047, 2048, 32766, 32767)
    raw = [(vals[(i * 3) % 11], vals[(i * 5 + 1) % 11], vals[(i * 7 + 2) % 11]) for i in range(80)]
    ia = len(b.names)
    b.scen("oor raw")
    b.init((1, 16, 16))
    b.thr(500)
    for s in raw:
        b.feed(*s)
    ib = len(b.names)
    b.scen("oor clamped")
    b.init((1, 16, 16))
    b.thr(500)
    for s in raw:
        b.feed(*[clamp_axis(v) for v in s])
    PAIRS.append((ia, ib))

    b.scen("NULL pointers")
    b.init((1, 16, 16))
    b.thr(500)
    for _ in range(20):
        b.feed(10, 20, 30)
    b.nulls()
    b.feed(0, 0, 0)

    # offline reference streams (rel_delay 135): used for the trigger_ref cross-check
    for seed, mg, rs in ((11, 250, -1), (12, 100, 300), (13, 1000, -1)):
        samples = rng_stream(seed, 600)
        b.scen("ref seed=%d mg=%d resync_at=%d" % (seed, mg, rs))
        b.init(None)
        b.thr(mg)
        fires, due = [], None
        for i, s in enumerate(samples):
            if i == rs:
                b.resync()
            if b.feed(*s):
                fires.append(i)
                due = i + 135
            if due is not None and i == due:
                b.release()
                due = None
        REFS.append((samples, mg, 135, rs, fires))
    SCEN_NAMES[:] = b.names
    return b


# ---- random episodes (mirrored in test_trigger.c) -------------------------------------------------
DBS = (0, 1, 2, 3, 4, 7)
QQ = (0, 15, 16, 17, 30, 40, 255)
WW = (0, 15, 16, 20, 32, 50)
MGS = (0, 1, 2, 100, 250, 500, 1000, 3000, 24567, 65535)
AMPS = (3, 40, 300, 1200)


class Exec:
    """Executes ops on a model and collects lines (the Python twin of do_op in test_trigger.c)."""

    def __init__(self):
        self.m = Model()
        self.lines = []

    def do(self, op, a=0, b=0, c=0):
        out = apply(self.m, op, a, b, c)
        self.lines.extend(out)
        return len(out) > 0 and out[0][0] == "F" and out[0].split()[1] == "1"


def episode(ex, seed, k, nsamp):
    """Random episode k (mirror of episode() in test_trigger.c; the rnd call order must stay identical)."""
    rs = [(seed * 2654435761 + k * 40503 + 12345) & M32]
    if rs[0] == 0:
        rs[0] = 1

    def rnd(n):
        x = rs[0]
        x ^= (x << 13) & M32
        x ^= x >> 17
        x ^= (x << 5) & M32
        rs[0] = x
        return x % n

    def sgn(v):
        return v - 65536 if v >= 32768 else v

    def pick_mg():
        v = rnd(6)
        if v == 0:
            return rnd(5000)
        return MGS[rnd(10)]

    ex.do(OP_SCEN, 1000 + k)
    u = rnd(8)
    if u == 0:
        ex.do(OP_INITNULL)
    else:
        d = DBS[rnd(6)]
        q = QQ[rnd(7)]
        w = WW[rnd(6)]
        ex.do(OP_INIT, d, q, w)
    ex.do(OP_SETTHR, sgn(pick_mg()))
    o = [0, 0, 0]
    for j in range(3):
        o[j] = rnd(3001) - 1500
    phase = plen = rel_in = 0
    for _ in range(nsamp):
        u = rnd(64)
        if u == 0:
            ex.do(OP_RESYNC)
        elif u <= 2:
            ex.do(OP_SETTHR, sgn(pick_mg()))
        if plen == 0:
            phase = rnd(5)
            plen = 8 + rnd(50)
            v = rnd(4)
            if v == 0:
                for j in range(3):
                    o[j] = rnd(3001) - 1500
        plen -= 1
        s = [0, 0, 0]
        for j in range(3):
            if phase == 4:
                v = rnd(6)
                val = (-32768, 32767, -2048, 2047, 0, o[j])[v]
            else:
                amp = AMPS[phase]
                val = o[j] + rnd(2 * amp + 1) - amp
            s[j] = max(-32768, min(32767, val))
        ret = ex.do(OP_FEED, s[0], s[1], s[2])
        if ret:
            rel_in = 3 + rnd(30)
        elif rel_in > 0:
            rel_in -= 1
            if rel_in == 0:
                ex.do(OP_RELEASE)
        v = rnd(24)
        if v == 0:
            ex.do(OP_RELEASE)


NSAMP = 300
_B = None


def directed():
    """Return the (cached) directed-scenario builder."""
    global _B
    if _B is None:
        _B = build()
    return _B


def expected(seed, nep):
    """All lines the C driver must print: directed scenarios, then nep random episodes."""
    b = directed()
    ex = Exec()
    for op in b.ops:
        ex.do(*op)
    for k in range(nep):
        episode(ex, seed, k, NSAMP)
    return ex.lines


def emit_header():
    """Print scripts.h: the directed ops as tables of at most CH rows (an AVR object is limited to 32 KB)."""
    b = directed()
    n = len(b.ops)
    ch = 2000
    nch = (n + ch - 1) // ch
    assert nch <= 8, "directed table too large for AVR flash (%d rows)" % n
    out = ["/* generated by oracle.py --emit-header; do not edit */",
           "#ifdef __AVR__", "#include <avr/pgmspace.h>", "#define ROM PROGMEM",
           "#define LOAD(p) ((int16_t)pgm_read_word(p))", "#else", "#define ROM", "#define LOAD(p) (*(p))", "#endif",
           "#define NDIR %du" % n, "#define CHUNK %du" % ch]
    for k in range(nch):
        rows = b.ops[k * ch:(k + 1) * ch]
        out.append("static const int16_t DIR%d[%d][4] ROM = {" % (k, len(rows)))
        out.extend("{%d,%d,%d,%d}," % r for r in rows)
        out.append("};")
    out.append("/* element j of row i of the whole table */")
    out.append("static int16_t RD(uint16_t i, uint8_t j)")
    out.append("{")
    out.append("    uint16_t r = i % CHUNK;")
    for k in range(nch):
        out.append("    if (i < %du) { return LOAD(&DIR%d[r][j]); }" % ((k + 1) * ch, k))
    out.append("    return 0;")
    out.append("}")
    print("\n".join(out))


if __name__ == "__main__":
    if "--emit-header" in sys.argv:
        emit_header()
    else:
        d = directed()
        print("%d directed ops, %d scenarios, %d REF streams" % (len(d.ops), len(d.names), len(REFS)))
        for r in REFS:
            print("  ref mg=%d resync_at=%d fires=%r" % (r[1], r[3], r[4]))
# [END AI-GENERATED]
