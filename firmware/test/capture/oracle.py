#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""Independent oracle for the capture.c suite (ticket WP1-aT).

Written from the SPEC only (docs/agent/CONTRACTS.md C1 items 2, 4, 5, 6, 7, 8 plus the main-agent
rulings in the ticket), never from the implementation. It holds

  * Model   : the capture state machine as the spec describes it,
  * Replay  : an exact mirror of test_capture.c (same event executor, same xorshift32 episode
              generator, same output format), returning the expected output lines,
  * DIRECTED: the directed scripts. `--emit-header` writes them as build/scripts.h so the C
              driver and the oracle read ONE copy.

Script grammar (space separated tokens, op letter + optional decimal count, default 1):
  I init   A arm   D disarm   R release   O overrun   P plain push   T push with trigger flag

Unknown-ring rule ("amb"): the spec does not say whether a push while IDLE enters the ring, nor
whether disarm clears it. After such an event the oracle treats the ring count as unknown (the
expected line holds "*", a wildcard) until 16 pushes happened in a non-IDLE state, and it refuses
(ScriptError) to build a script that fires a trigger while the honour/early decision would depend
on that unknown. See the report for the open question.

Usage: python3 oracle.py --emit-header | python3 oracle.py SEED NEPISODES
"""
import sys

M32 = 0xFFFFFFFF
LEN, PRE, RING = 150, 15, 16
IDLE, ARMED, CAPT, READY = 0, 1, 2, 3

TRIG_TAB = [10, 30, 100, 400]   # per mille of events that are trigger pushes
OVR_TAB = [0, 2, 6, 20]         # per mille of events that are overruns
REL_TAB = [10, 30, 80]          # per mille of events that are releases


class ScriptError(Exception):
    """A script asks for a behaviour the spec leaves open."""


def sample(n):
    """Return the 3-axis sample for stream index n (unique per n below 2**24, axes differ)."""
    x = (n & 0xFFF) - 2048
    y = ((n >> 12) & 0xFFF) - 2048
    z = ((((n * 37) & M32) ^ (n >> 5)) & 0xFFF) - 2048
    return (x, y, z)


def _build_directed():
    """Build the list of (name, script, dump) directed scenarios from the ticket's mandatory list."""
    d = []

    def add(name, script, dump=1):
        """Append one directed scenario."""
        d.append((name, script, dump))

    # trigger at the 15th pushed sample is early, at the 16th it is honoured
    add("early_15th", "I A P14 T P1 T P133 P3 R")
    add("honoured_16th", "I A P15 T P133 P P3 R")
    add("early_trigs_then_ok", "I A T3 P12 T P134 P2 R")
    add("first_after_release", "I A P15 T P134 P20 R T P134 P2 R")
    add("trig_in_capturing", "I A P20 T P5 T P3 T P60 T P65 P3")
    add("trig_in_ready", "I A P15 T P134 T P3 T T R P2 T P134")
    add("trig_on_last_sample", "I A P15 T P133 T P2 R P1 T P134")
    add("trig_in_idle", "I T P3 A P20 T P134 R")
    add("push_in_idle", "I P5 T P3 A P20 T P134")
    # overruns
    add("ovr_capt_after_trigger", "I A P15 T O P14 T P1 T P134")
    add("ovr_capt_1", "I A P15 T P1 O P15 T P134 R")
    add("ovr_capt_149", "I A P15 T P133 O P15 T P134 R")
    add("ovr_capt_149_early", "I A P15 T P133 O P14 T P1 T P134 R")
    add("ovr_ready", "I A P15 T P134 O P5 R P10 T P134 R")
    add("ovr_ready_early", "I A P15 T P134 O P4 R P10 T P1 T P134")
    add("ovr_ready_many", "I A P15 T P134 O O P3 O R P15 T P134")
    add("ovr_idle", "I O O A P15 T P134 R")
    add("ovr_armed", "I A P5 O P14 T P1 T P134 R")
    add("ovr_double_capt", "I A P15 T P40 O O P15 T P134 R")
    # release / arm / disarm / init
    add("release_not_ready", "I R A R P15 R T R P50 R P84 R P1 R")
    add("arm_noop", "I A A P15 A T A P133 A P A R A P1 R")
    add("disarm_idle", "I D D A P15 T P134 R")
    add("disarm_armed", "I A P20 D A P15 T P134 R")
    add("disarm_capturing", "I A P15 T P30 D A P15 T P134 R")
    add("disarm_ready", "I A P15 T P134 D P3 A R P20 T P134")
    add("init_midstream", "I A P20 T P50 I A P15 T P134")
    add("init_in_ready", "I A P15 T P134 I A P15 T P133 P R")
    # long runs / wrap
    add("wrap5000", "I A P5000 T P134 R", 1)
    add("back_to_back", "I A P16 " + "T P134 R " * 12 + "T P134", 0)
    for k in range(15, 49):
        add("pre_%d" % k, "I A P%d T P134 R" % k, 1 if k in (15, 16, 17, 31, 32, 33, 47, 48) else 0)
    for k in (0, 1, 2, 7, 14):
        add("early_%d" % k, "I A %sT P3" % ("P%d " % k if k else ""), 0)
    return d


DIRECTED = _build_directed()


def parse(script):
    """Split a script into (op, count) pairs."""
    out = []
    for tok in script.split():
        cnt = int(tok[1:]) if len(tok) > 1 else 1
        out.append((tok[0], cnt))
    return out


class Rng:
    """xorshift32 (13, 17, 5), identical to test_capture.c."""

    def __init__(self, seed):
        """Seed the generator exactly like the C driver."""
        self.s = (seed ^ 0x9E3779B9) & M32
        if self.s == 0:
            self.s = 1

    def next(self):
        """Return the next 32-bit value."""
        x = self.s
        x ^= (x << 13) & M32
        x ^= x >> 17
        x ^= (x << 5) & M32
        self.s = x
        return x


class Model:
    """The capture state machine as written in the spec and the main-agent rulings."""

    def __init__(self):
        """Start in the post-init state."""
        self.init()

    def init(self):
        """capture_init: IDLE, ring empty, no window, statistics zero (assumption, see report)."""
        self.state = IDLE
        self.ring = []
        self.amb = 0
        self.buf = []
        self.ov = self.wi = self.et = 0
        self.cache = None

    def ring_count(self):
        """Ring fill count, or None when unknown (see module docstring)."""
        return None if self.amb > 0 else len(self.ring)

    def push(self, s, trig):
        """capture_push: ring push, trigger test (ARMED only), window append, strictly in order."""
        st = self.state
        since = RING - self.amb            # pushes since the unknown event (valid when amb > 0)
        before = len(self.ring)
        self.ring.append(s)
        del self.ring[:-RING]
        if st == IDLE:
            self.amb = RING
            return
        if st == ARMED and trig:
            if self.amb > 0 and since < PRE:
                raise ScriptError("trigger decision depends on the unspecified ring state")
            if before >= PRE:
                self.buf = list(self.ring)          # 15 before (oldest first) + the trigger sample
                self.state = CAPT
            else:
                self.et += 1
        elif st == CAPT:
            self.buf.append(s)
            if len(self.buf) == LEN:
                self.state = READY
                self.wi += 1
                self.cache = None
        if self.amb > 0:
            self.amb -= 1

    def overrun(self):
        """capture_overrun: count it, empty the ring, drop an open window (CAPTURING -> ARMED)."""
        self.ov += 1
        self.ring = []
        self.amb = 0
        if self.state == CAPT:
            self.state = ARMED
            self.buf = []

    def release(self):
        """capture_release: READY -> ARMED returning True, anything else False with no change."""
        if self.state == READY:
            self.state = ARMED
            self.buf = []
            return True
        return False

    def arm(self):
        """capture_arm: IDLE -> ARMED only."""
        if self.state == IDLE:
            self.state = ARMED

    def disarm(self):
        """capture_disarm: any state except READY -> IDLE, an open window is dropped, no count."""
        if self.state != READY:
            self.state = IDLE
            self.buf = []
            self.amb = RING


def _checksum(buf):
    """Order-sensitive 32-bit checksum of all 450 buffer values (mirror of the C driver)."""
    cs = 0
    for row in buf:
        for v in row:
            cs = (cs * 31 + (v & 0xFFFF)) & M32
    return cs


def _tri(rows):
    """Format up to three samples as 'x,y,z x,y,z x,y,z'."""
    return " ".join("%d,%d,%d" % r for r in rows)


class Replay:
    """Mirror of the event executor and reporter of test_capture.c; collects the output lines."""

    def __init__(self):
        """Create an empty replay."""
        self.out = []
        self.m = Model()
        self.n = 0
        self.prev = IDLE
        self.entries = 0
        self.dump = 0
        self.rng = None

    def begin(self, name, dump):
        """Start a scenario: print its header and reset the per-scenario state."""
        self.out.append("S %s" % name)
        self.dump = dump
        self.prev = IDLE

    def ev(self, op):
        """Execute one event on the model and append its report lines."""
        m = self.m
        ret = "-"
        if op == "I":
            m.init()
        elif op == "A":
            m.arm()
        elif op == "D":
            m.disarm()
        elif op == "R":
            ret = "1" if m.release() else "0"
        elif op == "O":
            m.overrun()
        else:
            m.push(sample(self.n), op == "T")
            self.n += 1
        rc = m.ring_count()
        self.out.append("E %s %s %d %s %d %d %d" % (op, ret, m.state, "*" if rc is None else rc,
                                                    m.ov, m.wi, m.et))
        if m.state == READY:
            entry = self.prev != READY
            if entry:
                self.entries += 1
            if m.cache is None:
                m.cache = (_checksum(m.buf), _tri(m.buf[:3]), _tri(m.buf[-3:]))
            self.out.append("W %d" % m.cache[0])
            if entry or op != "P":
                self.out.append("F " + m.cache[1])
                self.out.append("L " + m.cache[2])
            full = (self.dump == 1 and (entry or op != "P")) or \
                   (self.dump == 2 and entry and self.entries % 8 == 0)
            if full:
                for i, r in enumerate(m.buf):
                    self.out.append("B %d %d,%d,%d" % (i, r[0], r[1], r[2]))
        self.prev = m.state

    def script(self, name, text, dump):
        """Run one directed script."""
        self.begin(name, dump)
        self.n = 0
        for op, cnt in parse(text):
            for _ in range(cnt):
                self.ev(op)

    def episode(self, k):
        """Run random episode k, mirroring run_random() in test_capture.c exactly."""
        r = self.rng
        self.begin("rand%d" % k, 2)
        ptrig = TRIG_TAB[r.next() % 4]
        povr = OVR_TAB[r.next() % 4]
        prel = REL_TAB[r.next() % 3]
        nev = 150 + r.next() % 251
        self.ev("I")
        idle = True
        for _ in range(nev):
            x = r.next() % 1000
            if idle:
                if x < 500:
                    self.ev("A")
                    idle = False
                elif x < 700:
                    self.ev("O")
                elif x < 900:
                    self.ev("R")
                else:
                    self.ev("I")
            elif x < povr:
                self.ev("O")
            elif x < povr + prel:
                self.ev("R")
            elif x < povr + prel + 5:
                self.ev("A")
            elif x < povr + prel + 8:
                self.ev("I")
                idle = True
            elif x < povr + prel + 8 + ptrig:
                self.ev("T")
            else:
                self.ev("P")
        if r.next() % 4 == 0:
            self.ev("D")


def expected(seed, nep):
    """Expected program output for `seed` and `nep` random episodes (directed scripts first)."""
    rp = Replay()
    for name, text, dump in DIRECTED:
        rp.script(name, text, dump)
    rp.rng = Rng(seed)
    rp.n = 0
    rp.entries = 0
    for k in range(nep):
        rp.episode(k)
    return rp.out


def emit_header():
    """Print build/scripts.h: the directed scripts as C data (single source of truth)."""
    print("/* GENERATED by oracle.py --emit-header. Do not edit. */")
    print("#define N_DIRECTED %du" % len(DIRECTED))
    print("static const struct { const char *name; const char *script; uint8_t dump; } DIRECTED[N_DIRECTED] = {")
    for name, text, dump in DIRECTED:
        print('    {"%s", "%s", %du},' % (name, text, dump))
    print("};")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--emit-header":
        emit_header()
    else:
        print("\n".join(expected(int(sys.argv[1], 0), int(sys.argv[2]))))
# [END AI-GENERATED]
