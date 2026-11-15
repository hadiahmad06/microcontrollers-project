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

Ring rulings (main agent, final): every pushed sample enters the 16-entry ring in EVERY state
(IDLE included); arm, disarm and release never touch the ring; overrun empties it in every state.
Return values: push is True iff the call opened a window (ARMED -> CAPTURING); disarm and overrun
are True iff the call dropped an open window; release is True iff READY -> ARMED.

Script grammar additions: "(body)N" repeats body N times (no nesting). Dump mode 3 is "sparse": an E
line is printed only for every 4096th event of the script and while a counter is within 2 of the
uint16_t wrap point (used by the counter-wrap scripts).

Usage: python3 oracle.py --emit-header | python3 oracle.py SEED NEPISODES
"""
import sys

M32 = 0xFFFFFFFF
LEN, PRE, RING = 150, 15, 16
IDLE, ARMED, CAPT, READY = 0, 1, 2, 3

TRIG_TAB = [10, 30, 100, 400]   # per mille of events that are trigger pushes
OVR_TAB = [0, 2, 6, 20]         # per mille of events that are overruns
REL_TAB = [10, 30, 80]          # per mille of events that are releases


def sample(n):
    """Return the 3-axis sample for a stream index.

    Args:
        n: stream index (unique samples below 2**24; the three axes differ).

    Returns:
        A tuple (x, y, z), every value in [-2048, 2047].
    """
    x = (n & 0xFFF) - 2048
    y = ((n >> 12) & 0xFFF) - 2048
    z = ((((n * 37) & M32) ^ (n >> 5)) & 0xFFF) - 2048
    return (x, y, z)


def _build_directed():
    """Build the directed scenarios.

    Returns:
        A list of (name, script, dump) tuples; dump is 0 none, 1 full dumps, 3 sparse output.
    """
    d = []

    def add(name, script, dump=1):
        """Append one directed scenario.

        Args:
            name: scenario name (printed in the S line).
            script: script text, grammar in the module docstring.
            dump: dump mode (0 none, 1 full buffer dumps, 3 sparse).

        Returns:
            None.
        """
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
    # ring rulings: IDLE pushes enter the ring; disarm/arm/release leave it alone; overrun empties it
    add("idle_ring_honoured", "I P20 A T P134 R")
    add("idle_ring_exact15", "I P15 A T P134 R")
    add("idle_ring_14_early", "I P14 A T P1 T P134 R")
    add("idle_ring_5_early", "I P5 A T")
    add("idle_ring_5_early_more", "I P5 A T P3 T P10 T P134")
    add("disarm_keeps_ring", "I A P20 D P3 A T P134 R")
    add("disarm_keeps_ring_idle_fill", "I A P3 D P12 A T P134 R")
    add("disarm_short_ring_early", "I A P5 D A T P3 T P134")
    add("disarm_open_window_ring", "I A P20 T P5 D P20 A T P134 R")
    add("disarm_open_window_early", "I A P20 T P5 D O P5 A T P3 T P134")
    add("idle_after_overrun_early", "I A P20 D O P10 A T P3 T P134")
    add("idle_after_overrun_honoured", "I A P20 D O P15 A T P134 R")
    add("idle_overrun_idle_push", "I P20 O P3 A T P5")
    add("overrun_empties_idle_ring", "I P20 O A T P20 T P134")
    add("arm_keeps_ring", "I P3 A P12 T P134 R")
    add("arm_keeps_ring_early", "I P3 A P11 T P3 T P134 R")
    add("release_keeps_ring", "I A P15 T P134 P3 R T P134 R")
    add("disarm_ready_ring", "I A P15 T P134 D D P5 R P20 T P134 R")
    add("disarm_ready_ring_keep", "I A P15 T P134 D P3 R D P3 A T P134")
    add("disarm_capt_then_trig", "I A P20 T P5 D A T P134 R")
    add("disarm_capt_149", "I A P20 T P133 D A T P134 R")
    add("ovr_after_disarm_ready", "I A P15 T P134 D O R P5 T P1 T P134")
    # NOTE: the windows counter (uint16_t) is NOT wrap-tested: 65536 windows need 9.8 M pushes, and the
    # Python oracle needs well over 5 s for that (about 1-2 us per event), so the check is not cheap.
    # counter wrap (uint16_t): 65536 overruns, 65536 early triggers (O empties the ring so the next T is early)
    add("wrap_overruns", "I O65535 A P20 O T P2 O65536 P3 T", 3)
    add("wrap_early_triggers", "I A (O T)65538 P20 T P134 R", 3)
    # long runs / wrap
    add("wrap5000", "I A P5000 T P134 R", 1)
    add("back_to_back", "I A P16 " + "T P134 R " * 12 + "T P134", 0)
    for k in range(15, 49):
        add("pre_%d" % k, "I A P%d T P134 R" % k, 1 if k in (15, 16, 17, 31, 32, 33, 47, 48) else 0)
    for k in (0, 1, 2, 7, 14):
        add("early_%d" % k, "I A %sT P3" % ("P%d " % k if k else ""), 0)
    return d


DIRECTED = _build_directed()


def expand(script):
    """Expand a script into the flat sequence of event letters.

    Args:
        script: script text; tokens are an op letter with an optional decimal repeat count, or a
            group "(ops)N" (no nesting) that repeats its ops N times.

    Returns:
        A list of single-character op letters.
    """
    out = []
    i = 0
    n = len(script)

    def count(j):
        """Parse an optional decimal repeat count.

        Args:
            j: index of the first possible digit.

        Returns:
            (count, next_index); count is 1 when there are no digits.
        """
        k = j
        while k < n and script[k].isdigit():
            k += 1
        return (int(script[j:k]) if k > j else 1), k

    while i < n:
        c = script[i]
        if c == " ":
            i += 1
        elif c == "(":
            e = script.index(")", i)
            body = expand(script[i + 1:e])
            cnt, i = count(e + 1)
            out.extend(body * cnt)
        else:
            cnt, i = count(i + 1)
            out.extend([c] * cnt)
    return out


# xorshift32: G. Marsaglia, "Xorshift RNGs", J. Statistical Software 8(14), 2003; shifts 13/17/5.
class Rng:
    """xorshift32 (13, 17, 5), identical to test_capture.c."""

    def __init__(self, seed):
        """Seed the generator exactly like the C driver.

        Args:
            seed: test seed (any integer; masked to 32 bits).

        Returns:
            None.
        """
        self.s = (seed ^ 0x9E3779B9) & M32
        if self.s == 0:
            self.s = 1

    def next(self):
        """Advance the generator.

        Returns:
            The next 32-bit value.
        """
        x = self.s
        x ^= (x << 13) & M32
        x ^= x >> 17
        x ^= (x << 5) & M32
        self.s = x
        return x


class Model:
    """The capture state machine as written in the spec and the main-agent rulings."""

    def __init__(self):
        """Start in the post-init state.

        Returns:
            None.
        """
        self.init()

    def init(self):
        """capture_init: IDLE, ring empty, no window, statistics zero.

        Returns:
            None.
        """
        self.state = IDLE
        self.ring = []
        self.buf = []
        self.ov = self.wi = self.et = 0
        self.cache = None

    def ring_count(self):
        """Report the ring fill.

        Returns:
            Number of samples in the ring, 0..16.
        """
        return len(self.ring)

    def push(self, s, trig):
        """capture_push: ring push (every state), trigger test (ARMED only), window append.

        Args:
            s: the (x, y, z) sample.
            trig: True when the trigger flag is set on this sample.

        Returns:
            True iff this call opened a window (ARMED -> CAPTURING); False otherwise.
        """
        st = self.state
        before = len(self.ring)
        self.ring.append(s)
        del self.ring[:-RING]
        if st == ARMED and trig:
            if before >= PRE:
                self.buf = list(self.ring)          # 15 before (oldest first) + the trigger sample
                self.state = CAPT
                return True
            self.et = (self.et + 1) & 0xFFFF
        elif st == CAPT:
            self.buf.append(s)
            if len(self.buf) == LEN:
                self.state = READY
                self.wi = (self.wi + 1) & 0xFFFF
                self.cache = None
        return False

    def overrun(self):
        """capture_overrun: count it, empty the ring (all states), drop an open window.

        Returns:
            True iff an open window was dropped (CAPTURING -> ARMED); False otherwise.
        """
        self.ov = (self.ov + 1) & 0xFFFF
        self.ring = []
        if self.state == CAPT:
            self.state = ARMED
            self.buf = []
            return True
        return False

    def release(self):
        """capture_release: READY -> ARMED; the ring is not touched.

        Returns:
            True when the state was READY, else False with no change.
        """
        if self.state == READY:
            self.state = ARMED
            self.buf = []
            return True
        return False

    def arm(self):
        """capture_arm: IDLE -> ARMED only; the ring is not touched.

        Returns:
            None.
        """
        if self.state == IDLE:
            self.state = ARMED

    def disarm(self):
        """capture_disarm: any state except READY -> IDLE; the ring is not touched, no count.

        Returns:
            True iff an open window was dropped (CAPTURING -> IDLE); False otherwise.
        """
        if self.state == READY:
            return False
        dropped = self.state == CAPT
        self.state = IDLE
        self.buf = []
        return dropped


def _checksum(buf):
    """Order-sensitive 32-bit checksum of all 450 buffer values (mirror of the C driver).

    Args:
        buf: list of (x, y, z) rows.

    Returns:
        The checksum as an unsigned 32-bit integer.
    """
    cs = 0
    for row in buf:
        for v in row:
            cs = (cs * 31 + (v & 0xFFFF)) & M32
    return cs


def _tri(rows):
    """Format up to three samples as 'x,y,z x,y,z x,y,z'.

    Args:
        rows: list of (x, y, z) tuples.

    Returns:
        The formatted string.
    """
    return " ".join("%d,%d,%d" % r for r in rows)


class Replay:
    """Mirror of the event executor and reporter of test_capture.c; collects the output lines."""

    def __init__(self):
        """Create an empty replay.

        Returns:
            None.
        """
        self.out = []
        self.m = Model()
        self.n = 0
        self.prev = IDLE
        self.entries = 0
        self.dump = 0
        self.idx = 0
        self.rng = None

    def begin(self, name, dump):
        """Start a scenario: print its header and reset the per-scenario state.

        Args:
            name: scenario name.
            dump: dump mode (0 none, 1 directed full dumps, 2 random, 3 sparse).

        Returns:
            None.
        """
        self.out.append("S %s" % name)
        self.dump = dump
        self.prev = IDLE
        self.idx = 0

    def ev(self, op):
        """Execute one event on the model and append its report lines.

        E line: E op ret state ring overruns windows early_triggers. ret is "-" for I and A and
        the 0/1 return value of capture_push / disarm / overrun / release for the other ops.

        Args:
            op: one of I A D R O P T.

        Returns:
            None.
        """
        m = self.m
        ret = "-"
        if op == "I":
            m.init()
        elif op == "A":
            m.arm()
        elif op == "D":
            ret = "1" if m.disarm() else "0"
        elif op == "R":
            ret = "1" if m.release() else "0"
        elif op == "O":
            ret = "1" if m.overrun() else "0"
        else:
            ret = "1" if m.push(sample(self.n), op == "T") else "0"
            self.n += 1
        self.idx += 1
        if self.dump == 3 and not (self.idx % 4096 == 0 or m.ov <= 1 or m.ov >= 65534
                                   or m.et <= 1 or m.et >= 65534):
            self.prev = m.state
            return
        self.out.append("E %s %s %d %d %d %d %d" % (op, ret, m.state, m.ring_count(),
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
        """Run one directed script.

        Args:
            name: scenario name.
            text: script text.
            dump: dump mode.

        Returns:
            None.
        """
        self.begin(name, dump)
        self.n = 0
        for op in expand(text):
            self.ev(op)

    def episode(self, k):
        """Run random episode k, mirroring run_random() in test_capture.c exactly.

        Idle pushes (plain and with trigger flag) and mid-episode disarms are generated.

        Args:
            k: episode number.

        Returns:
            None.
        """
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
                if x < 400:
                    self.ev("A")
                    idle = False
                elif x < 500:
                    self.ev("O")
                elif x < 600:
                    self.ev("R")
                elif x < 650:
                    self.ev("I")
                elif x < 900:
                    self.ev("P")
                else:
                    self.ev("T")
            elif x < povr:
                self.ev("O")
            elif x < povr + prel:
                self.ev("R")
            elif x < povr + prel + 5:
                self.ev("A")
            elif x < povr + prel + 8:
                self.ev("I")
                idle = True
            elif x < povr + prel + 12:
                self.ev("D")
                idle = True
            elif x < povr + prel + 12 + ptrig:
                self.ev("T")
            else:
                self.ev("P")
        if r.next() % 4 == 0:
            self.ev("D")


def expected(seed, nep):
    """Compute the expected program output.

    Args:
        seed: random-episode seed.
        nep: number of random episodes (directed scripts always come first).

    Returns:
        The list of expected output lines.
    """
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
    """Print build/scripts.h: the directed scripts as C data (single source of truth).

    Returns:
        None.
    """
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
