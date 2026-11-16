#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""Independent oracle for the c2_stream suite (ticket T-c2txT).

Written from the SPEC only (docs/agent/hadi/briefs/T-c2tx_spec.md X1-X2 plus the verbatim C2 text
W2-4_spec.md S6 and the S7 decoder). It imports nothing from tools/ or from the spike. It holds

  * crc16()  : its own bitwise CRC-16/IBM-3740 (poly 0x1021, init 0xFFFF, check 0x29B1),
  * frame()  : the S6 byte layout (HELLO 18 B, WINDOW 922 B, SAMPLES 107 B),
  * decode() : its own byte-at-a-time decoder (S7 rules: sync, known TYPE with its single LEN, CRC),
  * Replay   : the model of the sender plus the mirror of test_c2_stream.c (same op executor, same
               output format); it returns the expected output lines per scenario,
  * SCENARIOS: the directed scripts. `--emit-header` writes them as build/scripts.h so the C driver
               and the oracle read ONE copy.

Op grammar (op letter, a, b); the C driver is the mirror of Replay.run:
  I init        h k load hello k      m k load meta k       f k fill window buffer kind k
  g k fill samples buffer kind k      H W S start hello / window / samples    T k start text k
  n k NULL start (0 hello,1 meta,2 window buf,3 samples buf,4 text)
  P room pump once       D room flag drain until idle (flag 1: poll take_release after every pump)
  E take_release        B busy        X window id           C kind arg: CRC checks
  Z sizeof              Q kind n-1: n frames silently (kind H, W or S), hashed and CRC checked
Fill kinds: k >= 0 xorshift32 seeded (k+1)*0x9E3779B1; -1 int16 extremes; -2 zeros; -3 byte patterns;
-4 ramp i*7-400.  D room: >0 fixed, -1 cycle 32,1,31,33,255,5,0,17,2, -2 random 0..69 seeded by flag>>1.

Usage: python3 oracle.py --emit-header
"""
import sys

M32 = 0xFFFFFFFF
PUMP_MAX = 32
KNOWN = {0x01: 10, 0x02: 914, 0x04: 99}
EXT = [0x8000, 0x7FFF, 0xFFFF, 0x0000, 0x0001, 0x00FF, 0x0100, 0xFF00, 0x7F80, 0x8080, 0x0080, 0xFF7F]
PAT = [0x0080, 0x8000, 0x00FF, 0xFF00, 0x7F00, 0x0001, 0xFFFF, 0x0180]
CYCLE = [32, 1, 31, 33, 255, 5, 0, 17, 2]
CHECK = b"123456789"


def crc16(data, crc=0xFFFF):
    """CRC-16/IBM-3740 (aka CCITT-FALSE), bitwise, no reflection, xorout 0.

    Args:
        data: bytes to add.
        crc: running value (start 0xFFFF).

    Returns:
        The updated 16-bit value.
    """
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


assert crc16(CHECK) == 0x29B1


class Rng:
    """xorshift32 (13, 17, 5), mirrored bit for bit in test_c2_stream.c (G. Marsaglia, 2003)."""

    def __init__(self, seed):
        self.x = seed & M32

    def next(self):
        x = self.x
        x ^= (x << 13) & M32
        x ^= x >> 17
        x ^= (x << 5) & M32
        self.x = x
        return x


def s16(v):
    """Wrap an int to signed 16 bits."""
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def fill(k, rows):
    """Window/sample buffer content for a fill kind (see module doc); flat list of int16."""
    n = rows * 3
    if k >= 0:
        r = Rng(((k + 1) * 0x9E3779B1) & M32)
        return [s16(r.next() >> 8) for _ in range(n)]
    if k == -1:
        return [s16(EXT[i % len(EXT)]) for i in range(n)]
    if k == -2:
        return [0] * n
    if k == -3:
        return [s16(PAT[i % len(PAT)]) for i in range(n)]
    return [s16(i * 7 - 400) for i in range(n)]


def frame(ftype, seq, payload):
    """Build a complete C2 frame (S6 item 4): SYNC, TYPE, LEN, SEQ, payload, CRC low byte first."""
    ln = len(payload)
    body = bytes([ftype, ln & 255, ln >> 8, seq & 255]) + bytes(payload)
    c = crc16(body)
    return bytes([0xA5, 0x5A]) + body + bytes([c & 255, c >> 8])


def le(v, n):
    """Little-endian bytes of v in n bytes (two's complement for negatives)."""
    return (v & ((1 << (8 * n)) - 1)).to_bytes(n, "little")


def samples_bytes(flat):
    """int16 list to wire bytes, low byte first."""
    return b"".join(le(v, 2) for v in flat)


def decode(stream):
    """Byte-at-a-time decoder per S7 (own implementation).

    Args:
        stream: bytes received.

    Returns:
        (frames, garbage, badhdr, crcerr); frames is a list of (type, seq, payload bytes).
    """
    buf = bytearray()
    frames, garbage, badhdr, crcerr = [], 0, 0, 0
    for b in stream:
        buf.append(b)
        while buf:
            if buf[0] != 0xA5:
                del buf[0]
                garbage += 1
                continue
            if len(buf) < 2:
                break
            if buf[1] != 0x5A:
                del buf[0]
                garbage += 1
                continue
            if len(buf) < 6:
                break
            ln = buf[3] | (buf[4] << 8)
            if KNOWN.get(buf[2]) != ln:
                del buf[0]
                badhdr += 1
                continue
            total = 6 + ln + 2
            if len(buf) < total:
                break
            if crc16(bytes(buf[2:6 + ln])) != (buf[6 + ln] | (buf[7 + ln] << 8)):
                del buf[0]
                crcerr += 1
                continue
            frames.append((buf[2], buf[5], bytes(buf[6:6 + ln])))
            del buf[:total]
    return frames, garbage, badhdr, crcerr


# ---------------------------------------------------------------- tables shared with the C driver
def _tables():
    """Return (hello table, meta table, text table). Deterministic."""
    r = Rng(0xC2C2C2C2)
    hello = [dict(odr=100, rng=4, n=150, pre=15, fv=1, h=0xDEADBEEF),
             dict(odr=255, rng=255, n=255, pre=255, fv=255, h=0xFFFFFFFF),
             dict(odr=0, rng=0, n=0, pre=0, fv=0, h=0),
             dict(odr=50, rng=2, n=150, pre=15, fv=7, h=0x01020304)]
    for _ in range(3):
        v = r.next()
        hello.append(dict(odr=v & 255, rng=(v >> 8) & 255, n=(v >> 16) & 255, pre=(v >> 24) & 255,
                          fv=r.next() & 255, h=r.next()))
    meta = [dict(t=15, o=0, h=0x11223344, fl=0, c=0, cf=0, ev=0),
            dict(t=255, o=65535, h=0xFFFFFFFF, fl=255, c=-128, cf=255, ev=255),
            dict(t=15, o=1, h=0x12345678, fl=1, c=127, cf=200, ev=3),
            dict(t=0, o=256, h=0x80000001, fl=0x80, c=-1, cf=0, ev=0x80),
            dict(t=1, o=0x0102, h=0xA5A5A5A5, fl=1, c=5, cf=0xA5, ev=0x5A)]
    for _ in range(6):
        v = r.next()
        w = r.next()
        meta.append(dict(t=v & 255, o=(v >> 8) & 0xFFFF, h=r.next(), fl=(w >> 8) & 255,
                         c=(w & 255) - (256 if w & 128 else 0), cf=(w >> 16) & 255, ev=(w >> 24) & 255))
    allp = bytes(range(0x20, 0x7F))
    texts = [b"hello\n", b"\r\n", allp, b"A" * 255, b"B" * 256, b"bad\x7f", b"bad\x80", b"tab\t", b"\x1f",
             b"line1\nline2\r\n", (b"C" * 254) + b"\x7f", b"\x0b", b"x", b"\xff",
             (allp * 3)[:254] + b"\n", b"ok\x00hidden"]
    return hello, meta, texts


HELLO, META, TEXTS = _tables()


def text_ok(t):
    """Spec X2 text validity: NUL-terminated string of 0..255 chars, each 0x0A, 0x0D or 0x20..0x7E."""
    t = t.split(b"\x00")[0]
    return len(t) <= 255 and all(c in (0x0A, 0x0D) or 0x20 <= c <= 0x7E for c in t)


def hello_payload(h):
    """HELLO payload (S6 item 6): proto_ver 1, odr, range, n_samples, pre_trig, feature_ver, hash."""
    return bytes([1, h["odr"], h["rng"], h["n"], h["pre"], h["fv"]]) + le(h["h"], 4)


def window_payload(wid, m, flat):
    """WINDOW payload (S6 item 5): 14 metadata bytes then 450 int16."""
    return (le(wid, 2) + bytes([150, m["t"]]) + le(m["o"], 2) + le(m["h"], 4)
            + bytes([m["fl"], m["c"] & 255, m["cf"], m["ev"]]) + samples_bytes(flat))


def samples_payload(chunk, flat):
    """SAMPLES payload (S6 item 10): chunk u16, n = 16, 16 x 3 int16."""
    return le(chunk, 2) + bytes([16]) + samples_bytes(flat)


FNV = 0x811C9DC5


def fnv_update(h, data):
    """FNV-1a 32 bit."""
    for b in data:
        h = ((h ^ b) * 0x01000193) & M32
    return h


class Replay:
    """Model of the sender and mirror of the C driver op executor."""

    def __init__(self, avr):
        self.avr = avr
        self.lines = []
        self.streams = {}    # scenario -> (stream bytes, expected frames, text byte count)
        self.cur = None

    def reset(self):
        self.seq = self.wid = self.chunk = 0
        self.q = b""
        self.pos = 0
        self.kind = None
        self.rel = False
        self.hello = HELLO[0]
        self.meta = META[0]
        self.win = fill(-2, 150)
        self.smp = fill(-2, 16)

    @property
    def busy(self):
        return self.pos < len(self.q)

    def out(self, s):
        self.lines.append(s)

    def start(self, kind, data, hdrtype=None, payload=None):
        """Begin a frame (bytes built now = snapshot) or text."""
        self.q = data
        self.pos = 0
        self.kind = kind

    def pump_once(self, room, poll):
        """Spec X2 pump: n = min(room, 32, remaining); frame end idles the sender in the same call."""
        n = min(room, PUMP_MAX, len(self.q) - self.pos) if self.busy else 0
        chunk = self.q[self.pos:self.pos + n]
        self.pos += n
        if n and not self.busy:
            if self.kind == "W":
                self.rel = True
            if self.kind != "T":
                self.cur[1].append(self.q)   # completed frame bytes; compared through decode()
        self.cur[0].extend(chunk)
        if self.kind == "T":
            self.cur[3] += n
        s = "P room=%d n=%d busy=%d g=1" % (room, n, 1 if self.busy else 0)
        if poll:
            s += " rel=%d" % self.take()
        self.out(s)
        for i in range(0, n, 32):
            self.out("x " + chunk[i:i + 32].hex())
        return n

    def take(self):
        r = 1 if self.rel else 0
        self.rel = False
        return r

    def mk_hello(self):
        f = frame(1, self.seq, hello_payload(self.hello))
        self.seq = (self.seq + 1) & 255
        return f

    def mk_window(self):
        f = frame(2, self.seq, window_payload(self.wid, self.meta, self.win))
        self.seq = (self.seq + 1) & 255
        self.wid = (self.wid + 1) & 0xFFFF
        return f

    def mk_samples(self):
        f = frame(4, self.seq, samples_payload(self.chunk, self.smp))
        self.seq = (self.seq + 1) & 255
        self.chunk = (self.chunk + 1) & 0xFFFF
        return f

    def room_list(self, a, flag):
        """Generator of rooms for a drain."""
        if a > 0:
            while True:
                yield a
        elif a == -1:
            i = 0
            while True:
                yield CYCLE[i % len(CYCLE)]
                i += 1
        else:
            r = Rng(((flag >> 1) * 2654435761 + 7) & M32)
            while True:
                yield r.next() % 70

    def crc_op(self, a, b):
        if a == 0:
            self.out("C0 %04x" % crc16(CHECK))
        elif a == 1:
            for k in range(10):
                self.out("C1 k=%d %04x" % (k, crc16(CHECK[k:], crc16(CHECK[:k]))))
        elif a == 2:
            self.out("C2 %04x %04x" % (crc16(CHECK, 0x1234), crc16(b"", 0xBEEF)))
        else:
            r = Rng(b + 1)
            d = bytes((r.next() >> 9) & 255 for _ in range(b))
            c = 0xFFFF
            for x in d:
                c = crc16(bytes([x]), c)
            sp = crc16(d[2 * b // 3:], crc16(d[b // 3:2 * b // 3], crc16(d[:b // 3])))
            self.out("C3 len=%d whole=%04x split=%04x bytewise=%04x" % (b, crc16(d), sp, c))

    def bulk(self, kind, n):
        """Q op: n silent frames; hash of header bytes 0..7, byte count, release count."""
        h, total = FNV, 0
        w0, c0 = self.wid, self.chunk
        for i in range(n):
            if kind == "H":
                hdr = bytes([0xA5, 0x5A, 1, 10, 0, (self.seq + i) & 255, 1, self.hello["odr"]])
                ln = 18
            elif kind == "W":
                hdr = bytes([0xA5, 0x5A, 2, 0x92, 3, (self.seq + i) & 255]) + le(w0 + i, 2)
                ln = 922
            else:
                hdr = bytes([0xA5, 0x5A, 4, 99, 0, (self.seq + i) & 255]) + le(c0 + i, 2)
                ln = 107
            h = fnv_update(h, hdr)
            total += ln
        self.seq = (self.seq + n) & 255
        if kind == "W":
            self.wid = (self.wid + n) & 0xFFFF
        if kind == "S":
            self.chunk = (self.chunk + n) & 0xFFFF
        self.out("Q kind=%s n=%d rel=%d bytes=%d hash=%08x diff=0 badcrc=0 badlen=0 startfail=0"
                 % (kind, n, n if kind == "W" else 0, total, h))

    def run(self, name, ops):
        self.cur = [bytearray(), [], 0, 0]   # stream, completed frames bytes, unused, text bytes
        self.out("== " + name)
        for op, a, b in ops:
            self.exec(op, a, b)
        self.streams[name] = (bytes(self.cur[0]), b"".join(self.cur[1]), self.cur[3])

    def exec(self, op, a, b):
        if op == "I":
            self.reset()
            self.out("I")
        elif op == "h":
            self.hello = HELLO[a]
        elif op == "m":
            self.meta = META[a]
        elif op == "f":
            self.win = fill(a, 150)
        elif op == "g":
            self.smp = fill(a, 16)
        elif op in "HWS":
            r = 0
            if not self.busy:
                r = 1
                self.start(op, {"H": self.mk_hello, "W": self.mk_window, "S": self.mk_samples}[op]())
            self.out("S%s r=%d busy=%d" % (op, r, 1 if self.busy else 0))
        elif op == "T":
            r = 0
            if not self.busy and text_ok(TEXTS[a]):
                t = TEXTS[a].split(b"\x00")[0]
                if len(t) > 0:
                    r = 1
                    self.start("T", t)
            self.out("ST r=%d busy=%d" % (r, 1 if self.busy else 0))
        elif op == "n":
            self.out("n %d r=0 busy=%d" % (a, 1 if self.busy else 0))
        elif op == "P":
            self.pump_once(a, False)
        elif op == "D":
            gen = self.room_list(a, b)
            calls = 0
            while self.busy and calls < 3000:
                self.pump_once(next(gen), b & 1)
                calls += 1
            self.pump_once(7, b & 1)
            self.out("D calls=%d busy=%d" % (calls, 1 if self.busy else 0))
        elif op == "E":
            self.out("E r=%d" % self.take())
        elif op == "B":
            self.out("B busy=%d" % (1 if self.busy else 0))
        elif op == "X":
            self.out("X wid=%d" % self.wid)
        elif op == "C":
            self.crc_op(a, b)
        elif op == "Z":
            self.out("# sizeof(c2_tx_t) is printed by the target")
            if self.avr:
                self.out("Z le40=1")
        elif op == "Q":
            self.bulk(chr(a), b + 1)
        else:
            raise ValueError(op)


# ---------------------------------------------------------------- scenarios
SCENARIOS = []   # (name, ops, host_only)


def add(name, ops, host_only=False):
    SCENARIOS.append((name, [(o[0], o[1] if len(o) > 1 else 0, o[2] if len(o) > 2 else 0) for o in ops], host_only))


def _build():
    add("crc", [("C", 0), ("C", 1), ("C", 2)] + [("C", 3, n) for n in (0, 1, 2, 3, 17, 64, 255, 300)])
    add("init", [("I",), ("B",), ("X",), ("E",), ("P", 32), ("P", 0), ("Z",)])
    add("hello_basic", [("I",), ("h", 0), ("H",), ("D", 32), ("h", 1), ("H",), ("D", 1),
                        ("h", 2), ("H",), ("D", 255), ("h", 3), ("H",), ("D", 18), ("h", 4), ("H",),
                        ("D", 17), ("h", 5), ("H",), ("D", 19), ("h", 6), ("H",), ("D", -2, 2)])
    ops = [("I",), ("m", 0), ("f", 0)]
    for room in (1, 2, 3, 17, 18, 31, 32, 33, 64, 255):
        ops += [("H",), ("D", room)]
    add("hello_rooms", ops)
    for room in (1, 31, 32, 33, 255):
        add("win_room_%d" % room, [("I",), ("m", 0), ("f", 0), ("W",), ("D", room, 1)])
    add("win_cycle", [("I",), ("m", 2), ("f", 3), ("W",), ("D", -1, 1)])
    for s in (1, 2, 3, 4, 5):
        add("win_random_%d" % s, [("I",), ("m", 5 + s), ("f", 10 + s), ("W",), ("D", -2, (s << 1) | 1)])
    ops = [("I",)]
    for k in range(len(META)):
        ops += [("m", k), ("f", k + 20), ("W",), ("D", 32, 1)]
    add("win_all_metas", ops)
    add("win_calls_room32", [("I",), ("m", 1), ("f", 1), ("W",), ("D", 32), ("E",), ("E",)])
    # frame end: busy false in the same call, next call returns 0, never two frames in one call
    add("frame_end", [("I",), ("h", 0), ("H",), ("P", 18), ("P", 255), ("H",), ("P", 255), ("P", 255),
                      ("h", 1), ("H",), ("P", 17), ("B",), ("P", 1), ("B",), ("P", 1),
                      ("m", 0), ("W",)] + [("P", 32)] * 28 + [("P", 26), ("B",), ("P", 32), ("E",),
                      ("S",)] + [("P", 32)] * 3 + [("P", 11), ("B",), ("P", 32), ("T", 0), ("P", 255), ("P", 255),
                      ("H",), ("P", 255), ("T", 12), ("P", 255), ("W",), ("P", 255), ("D", 255)])
    add("never_two_frames", [("I",), ("H",), ("P", 255), ("H",), ("P", 255), ("W",), ("P", 255), ("D", 255), ("E",),
                             ("S",), ("P", 255), ("T", 0), ("P", 255), ("H",), ("P", 255)])
    add("release", [("I",), ("m", 0), ("f", 0), ("E",), ("W",), ("D", 32, 1), ("E",), ("E",), ("H",), ("D", 32, 1),
                    ("E",), ("S",), ("D", 32, 1), ("E",), ("T", 0), ("D", 32, 1), ("E",), ("W",), ("P", 32),
                    ("E",), ("P", 255), ("E",), ("D", 255, 1), ("E",), ("W",), ("D", 255, 1), ("E",), ("W",),
                    ("D", 7, 1), ("E",), ("E",), ("W",), ("P", 255), ("T", 0), ("H",), ("E",), ("D", 255, 1)])
    add("busy_null", [("I",), ("n", 0), ("n", 1), ("n", 2), ("n", 3), ("n", 4), ("B",), ("X",),
                      ("m", 3), ("f", 4), ("W",), ("P", 40), ("H",), ("W",), ("S",), ("T", 0), ("n", 0),
                      ("n", 1), ("n", 2), ("n", 3), ("n", 4), ("P", 10), ("T", 3), ("H",), ("D", 32), ("E",), ("X",),
                      ("H",), ("D", 32), ("S",), ("P", 10), ("W",), ("H",), ("T", 12), ("n", 3), ("D", 32),
                      ("T", 12), ("P", 0), ("H",), ("S",), ("W",), ("D", 255), ("E",), ("h", 0), ("H",), ("D", 32), ("X",)])
    add("snapshot", [("I",), ("m", 1), ("f", 1), ("W",), ("P", 5), ("m", 2), ("P", 5), ("m", 3), ("D", 32), ("E",),
                     ("W",), ("D", 32), ("E",), ("h", 1), ("H",), ("P", 3), ("h", 3), ("D", 32)])
    add("buf_change", [("I",), ("m", 0), ("f", 1), ("W",), ("D", 32), ("E",), ("f", 2), ("W",), ("D", 32), ("E",),
                       ("g", 1), ("S",), ("D", 32), ("g", 2), ("S",), ("D", 32), ("g", -1), ("S",), ("D", 7),
                       ("f", -1), ("g", -3), ("W",), ("D", 32), ("E",), ("S",), ("D", 32)])
    add("extremes", [("I",), ("m", 0), ("f", -1), ("W",), ("D", 32), ("E",), ("f", -3), ("W",), ("D", 32), ("E",),
                     ("f", -4), ("W",), ("D", 32), ("E",), ("f", -2), ("W",), ("D", 32), ("E",),
                     ("g", -1), ("S",), ("D", 32), ("g", -3), ("S",), ("D", 32), ("g", -4), ("S",), ("D", 32)])
    add("samples", [("I",), ("g", 5), ("S",), ("D", 32), ("S",), ("D", 1), ("S",), ("D", 31), ("S",), ("D", 255),
                    ("S",), ("D", -1), ("S",), ("D", -2, 9), ("X",)])
    ops = [("I",)]
    for k in (0, 1, 2, 12, 3, 9, 10, 14, 15):
        ops += [("T", k), ("D", 32 if k != 14 else 1)]
    ops += [("T", 4), ("D", 32), ("T", 5), ("T", 6), ("T", 7), ("T", 8), ("T", 11), ("T", 13), ("T", 10), ("B",),
            ("P", 32), ("h", 0), ("H",), ("D", 32), ("T", 3), ("D", -1), ("T", 2), ("D", 255), ("T", 2),
            ("D", -2, 4)]
    add("text", ops)
    add("text_busy", [("I",), ("T", 1), ("P", 1), ("H",), ("W",), ("S",), ("T", 0), ("n", 0), ("n", 4), ("D", 32),
                      ("H",), ("D", 32), ("m", 0), ("f", 0), ("W",), ("P", 20), ("T", 0), ("T", 5), ("D", 32), ("E",)])
    add("mixed_seq", [("I",), ("h", 0), ("m", 0), ("f", 7), ("g", 7), ("H",), ("D", 32, 1), ("W",), ("D", 32, 1),
                      ("S",), ("D", 32), ("T", 0), ("D", 32), ("W",), ("D", 32, 1), ("S",), ("D", 32), ("H",),
                      ("D", 32), ("X",), ("W",), ("D", 255, 1), ("S",), ("D", 255), ("X",), ("H",), ("D", 255)])
    add("reinit", [("I",), ("m", 0), ("W",), ("D", 32), ("E",), ("W",), ("D", 32), ("E",), ("W",), ("P", 32), ("I",), ("B",), ("X",),
                   ("E",), ("H",), ("D", 32), ("W",), ("D", 32), ("S",), ("D", 32)])
    add("seq_wrap", [("I",), ("h", 0), ("Q", ord("H"), 299), ("H",), ("D", 32), ("Q", ord("S"), 299), ("S",),
                     ("D", 32), ("Q", ord("W"), 2), ("W",), ("D", 32, 1), ("X",)])
    add("seq_wrap_window", [("I",), ("m", 1), ("f", 1), ("Q", ord("W"), 257), ("W",), ("D", 32), ("X",)], True)
    add("wid_wrap", [("I",), ("m", 1), ("f", 1), ("Q", ord("W"), 65534), ("X",), ("W",), ("D", 32), ("E",), ("X",), ("W",),
                     ("D", 32), ("E",), ("X",), ("S",), ("D", 32), ("Q", ord("W"), 65535), ("X",), ("W",), ("D", 32)], True)
    add("chunk_wrap", [("I",), ("g", 3), ("Q", ord("S"), 65534), ("S",), ("D", 32), ("S",), ("D", 32), ("S",),
                       ("D", 32), ("X",), ("W",), ("D", 32), ("E",), ("Q", ord("S"), 65535), ("S",), ("D", 32)], True)


_build()


def emit_header():
    """Write build/scripts.h on stdout."""
    o = ["/* generated by oracle.py --emit-header; do not edit */"]
    o.append("static const c2_hello_t g_hello_tab[] = {")
    for h in HELLO:
        o.append("  {.odr_hz = %d, .range_g = %d, .n_samples = %d, .pre_trig = %d, .feature_ver = %d, "
                 ".model_hash = 0x%08Xu}," % (h["odr"], h["rng"], h["n"], h["pre"], h["fv"], h["h"]))
    o.append("};")
    o.append("static const c2_window_meta_t g_meta_tab[] = {")
    for m in META:
        o.append("  {.trig_idx = %d, .overruns = %d, .model_hash = 0x%08Xu, .flags = %d, .class_id = %d, "
                 ".conf = %d, .events = %d}," % (m["t"], m["o"], m["h"], m["fl"], m["c"], m["cf"], m["ev"]))
    o.append("};")
    names = []
    for i, t in enumerate(TEXTS):
        lit = ""
        for c in t:
            if 0x20 <= c <= 0x7E and chr(c) not in '"\\?':
                lit += chr(c)
            else:
                lit += "\\%03o" % c
        o.append('static const char g_t%d[] = "%s";' % (i, lit))
        names.append("g_t%d" % i)
    o.append("static const char *const g_text[] = {%s};" % ", ".join(names))
    o.append("#define N_OPS %d" % sum(len(s[1]) for s in SCENARIOS))
    o.append("static const op_t g_ops[N_OPS] ROMDATA = {")
    first, scen = 0, []
    for name, ops, host in SCENARIOS:
        row = []
        for op, a, b in ops:
            row.append("{'%s', %d, %du}" % (op, a, b))
        o.append("  " + ", ".join(row) + ",")
        scen.append('  {"%s", %d, %d, %d}' % (name, first, len(ops), 1 if host else 0))
        first += len(ops)
    o.append("};")
    o.append("#define N_SCEN %d" % len(SCENARIOS))
    o.append("static const scen_t g_scen[N_SCEN] = {")
    o.append(",\n".join(scen))
    o.append("};")
    print("\n".join(o))


def expected(avr):
    """Expected output lines and per-scenario streams for the avr or host target.

    Returns:
        (lines, streams) where streams maps scenario name to (stream, completed frames bytes, text bytes).
    """
    rp = Replay(avr)
    rp.reset()
    for name, ops, host in SCENARIOS:
        if host and avr:
            continue
        rp.run(name, ops)
    return rp.lines, rp.streams


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--emit-header":
        emit_header()
    else:
        sys.exit("usage: oracle.py --emit-header")
# [END AI-GENERATED]
