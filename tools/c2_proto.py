#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""C2 UART protocol: CRC, frame encoders, streaming decoder (ticket W2-4).

WORKING ASSUMPTION: open_questions Q1 (C2 as proposed), not decided.
Promoted from the host spike docs/agent/hadi/spikes/uart/c2_ref.py (same author tool); the wire
format is the C2 contract text: [A5][5A][TYPE][LEN u16][SEQ][PAYLOAD][CRC16 u16], little-endian,
CRC-16/IBM-3740 (poly 0x1021, init 0xFFFF, check("123456789") = 0x29B1) over TYPE..PAYLOAD.
No numpy needed.

Usage: python3 tools/c2_proto.py --selftest
"""
import collections
import os
import random
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_ref  # noqa: E402  (FEATURES_VERSION default for encode_hello)

SYNC0, SYNC1 = 0xA5, 0x5A
T_HELLO, T_WINDOW, T_SAMPLES = 0x01, 0x02, 0x04
LEN_HELLO, LEN_WINDOW, LEN_SAMPLES = 10, 914, 99
HEADER_LEN, CRC_LEN = 6, 2
N_SAMPLES = 150

Frame = collections.namedtuple("Frame", "ftype seq payload")


def crc16(data, crc=0xFFFF):
    """CRC-16/IBM-3740, bitwise.

    Args:
        data: bytes-like to checksum.
        crc: running CRC (0xFFFF starts a message).
    Returns:
        The updated 16-bit CRC.
    """
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _frame(ftype, seq, payload):
    """Wrap a payload in sync bytes, header and CRC; returns bytes."""
    body = struct.pack("<BHB", ftype, len(payload), seq & 0xFF) + payload
    return bytes((SYNC0, SYNC1)) + body + struct.pack("<H", crc16(body))


def _flat(samples, nrows):
    """Check shape and int16 range of nrows x 3 samples; returns a flat list of ints."""
    rows = [tuple(int(v) for v in r) for r in samples]
    if len(rows) != nrows or any(len(r) != 3 for r in rows):
        raise ValueError("samples must be %d rows of 3 ints" % nrows)
    flat = [v for r in rows for v in r]
    if min(flat) < -32768 or max(flat) > 32767:
        raise ValueError("sample value outside int16 range")
    return flat


def encode_hello(seq, odr_hz=100, range_g=4, n_samples=150, pre_trig=15,
                 feature_ver=features_ref.FEATURES_VERSION, model_hash=0, proto_ver=1):
    """Encode a HELLO frame.

    Args:
        seq: frame counter (mod 256). odr_hz, range_g, n_samples, pre_trig, feature_ver,
        proto_ver: u8 payload fields. model_hash: u32 (mod 2^32).
    Returns:
        18 bytes.
    """
    p = struct.pack("<BBBBBBI", proto_ver, odr_hz, range_g, n_samples, pre_trig, feature_ver,
                    model_hash & 0xFFFFFFFF)
    return _frame(T_HELLO, seq, p)


def encode_window(seq, window_id, samples, trig_idx=15, overruns=0, model_hash=0, flags=0,
                  class_id=0, conf=0, events=0):
    """Encode a WINDOW frame.

    Args:
        seq: frame counter (mod 256). window_id: mod 65536. samples: 150 rows of 3 ints (list or
        numpy array), each within int16. trig_idx, overruns, model_hash, flags, class_id (i8),
        conf, events: payload metadata.
    Returns:
        922 bytes. Raises ValueError for a wrong shape or an out-of-range sample.
    """
    flat = _flat(samples, N_SAMPLES)
    p = struct.pack("<HBBHIBbBB", window_id & 0xFFFF, N_SAMPLES, trig_idx, overruns & 0xFFFF,
                    model_hash & 0xFFFFFFFF, flags, class_id, conf, events)
    p += struct.pack("<450h", *flat)
    return _frame(T_WINDOW, seq, p)


def encode_samples(seq, chunk, samples):
    """Encode a bring-up SAMPLES frame.

    Args:
        seq: frame counter (mod 256). chunk: chunk counter (mod 65536). samples: 16 rows of 3 ints.
    Returns:
        107 bytes.
    """
    flat = _flat(samples, 16)
    return _frame(T_SAMPLES, seq, struct.pack("<HB", chunk & 0xFFFF, 16) + struct.pack("<48h", *flat))


def parse_hello(payload):
    """Parse a HELLO payload into a dict (proto_ver, odr_hz, range_g, n_samples, pre_trig,
    feature_ver, model_hash)."""
    keys = ("proto_ver", "odr_hz", "range_g", "n_samples", "pre_trig", "feature_ver", "model_hash")
    return dict(zip(keys, struct.unpack("<BBBBBBI", payload)))


def parse_window(payload):
    """Parse a WINDOW payload into a dict (window_id, n_samples, trig_idx, overruns, model_hash,
    flags, class_id (signed), conf, events, samples = list of 150 (x, y, z) tuples)."""
    (wid, n, trig, ovr, mh, flags, cls, conf, ev) = struct.unpack_from("<HBBHIBbBB", payload)
    flat = struct.unpack_from("<450h", payload, 14)
    return {"window_id": wid, "n_samples": n, "trig_idx": trig, "overruns": ovr, "model_hash": mh,
            "flags": flags, "class_id": cls, "conf": conf, "events": ev,
            "samples": [tuple(flat[i:i + 3]) for i in range(0, 450, 3)]}


def parse_samples(payload):
    """Parse a SAMPLES payload into a dict (chunk, n, samples = 16 (x, y, z) tuples)."""
    chunk, n = struct.unpack_from("<HB", payload)
    flat = struct.unpack_from("<48h", payload, 3)
    return {"chunk": chunk, "n": n, "samples": [tuple(flat[i:i + 3]) for i in range(0, 48, 3)]}


class Decoder:
    """Streaming, byte-at-a-time C2 frame decoder with resynchronisation (proposal 3.2).

    Counters (public ints): garbage, bad_header, crc_errors, frames, seq_gaps.
    text_lines: ASCII lines found between frames (only bytes dropped while hunting for sync).
    """

    def __init__(self, accept_samples=False):
        """Args: accept_samples: also accept SAMPLES (type 0x04, LEN 99); False = v1 decoder."""
        self.known = {T_HELLO: LEN_HELLO, T_WINDOW: LEN_WINDOW}
        if accept_samples:
            self.known[T_SAMPLES] = LEN_SAMPLES
        self.buf = bytearray()
        self.garbage = self.bad_header = self.crc_errors = self.frames = self.seq_gaps = 0
        self.text_lines = []
        self._line = []
        self._last_seq = None

    def _hunt_drop(self):
        """Drop the front byte while hunting for sync: count garbage and collect ASCII text."""
        b = self.buf.pop(0)
        self.garbage += 1
        if b == 0x0A:
            if self._line:
                self.text_lines.append("".join(self._line))
            self._line = []
        elif b == 0x0D:
            pass
        elif 0x20 <= b <= 0x7E:
            self._line.append(chr(b))
        else:
            self._line = []

    def feed(self, data):
        """Feed bytes (any length).

        Args:
            data: bytes-like.
        Returns:
            List of Frame completed by these bytes, in order.
        """
        out = []
        for b in data:
            self.buf.append(b)
            out.extend(self._scan())
        return out

    def _scan(self):
        """Consume every complete frame the buffer holds; returns a list of Frame."""
        out = []
        buf = self.buf
        while buf:
            if buf[0] != SYNC0:
                self._hunt_drop()
                continue
            if len(buf) < 2:
                break
            if buf[1] != SYNC1:
                self._hunt_drop()
                continue
            if len(buf) < HEADER_LEN:
                break
            ftype, ln, seq = struct.unpack_from("<BHB", buf, 2)
            if self.known.get(ftype) != ln:
                del buf[0]
                self.bad_header += 1
                continue
            total = HEADER_LEN + ln + CRC_LEN
            if len(buf) < total:
                break
            (rx,) = struct.unpack_from("<H", buf, total - CRC_LEN)
            if crc16(buf[2:total - CRC_LEN]) != rx:
                del buf[0]
                self.crc_errors += 1
                continue
            payload = bytes(buf[HEADER_LEN:HEADER_LEN + ln])
            del buf[:total]
            if self._last_seq is not None:
                self.seq_gaps += (seq - self._last_seq - 1) & 0xFF
            self._last_seq = seq
            self.frames += 1
            out.append(Frame(ftype, seq, payload))
        return out

    def flush_stale(self):
        """PC-side idle rule (proposal 3.2): if an incomplete candidate is buffered, drop one byte
        (counted as bad_header) and rescan. Call when no byte arrived for >= 50 ms.

        Returns:
            List of Frame completed by the rescan (empty if the buffer was empty).
        """
        if not self.buf:
            return []
        del self.buf[0]
        self.bad_header += 1
        return self._scan()


def _selftest():
    """Run the built-in checks; returns a list of failure strings."""
    import importlib.util
    fails = []

    def check(c, msg):
        if not c:
            fails.append(msg)

    check(crc16(b"123456789") == 0x29B1, "crc check value")
    spike_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "agent",
                              "hadi", "spikes", "uart", "c2_ref.py")
    spike = None
    if os.path.exists(spike_path):
        spec = importlib.util.spec_from_file_location("c2_ref", spike_path)
        spike = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(spike)
    else:
        fails.append("spike c2_ref.py not found at %s" % spike_path)
    rng = random.Random(5)
    h = dict(proto_ver=1, odr_hz=100, range_g=4, n_samples=150, pre_trig=15,
             feature_ver=features_ref.FEATURES_VERSION, model_hash=0xDEADBEEF)
    hello = encode_hello(7, model_hash=0xDEADBEEF)
    check(len(hello) == 18, "hello length")
    if spike:
        check(hello == spike.encode_hello(7, h), "hello bytes vs spike")
    wins = []
    for i in range(20):
        if i == 0:
            s = [(-32768, 32767, -2048)] * 75 + [(2047, -1, 0)] * 75
        else:
            s = [tuple(rng.choice((-32768, 32767, -2048, 2047, rng.randint(-2048, 2047)))
                       for _ in range(3)) for _ in range(150)]
        meta = dict(window_id=i + 1000, trig_idx=15, overruns=i, model_hash=i * 77, flags=1,
                    class_id=-3, conf=200, events=5)
        fb = encode_window(i + 1, samples=s, **meta)
        check(len(fb) == 922, "window length")
        if spike:
            check(fb == spike.encode_window(i + 1, meta, s), "window bytes vs spike %d" % i)
        wins.append((fb, s, meta))
    sm = encode_samples(3, 70000, [(1, -2, 3)] * 16)
    check(len(sm) == 107, "samples length")
    for bad in ([(40000, 0, 0)] * 150, [(0, 0, 0)] * 149):
        try:
            encode_window(0, 0, bad)
            fails.append("encode_window accepted bad samples")
        except ValueError:
            pass
    # byte-at-a-time round trip: text, garbage, one corrupted frame
    badf = bytearray(wins[3][0])
    badf[100] ^= 0x40
    stream = (b"GM_MODEL_HASH=0\r\n" + hello + bytes([0, 1, 2, 0xA5, 0x77]) + wins[0][0] + wins[1][0]
              + bytes(badf) + wins[2][0] + b"hello\n" + hello)
    d = Decoder()
    got = []
    for b in stream:
        got += d.feed(bytes([b]))
    ids = [parse_window(f.payload)["window_id"] for f in got if f.ftype == T_WINDOW]
    check(ids == [1000, 1001, 1002], "round trip ids %s" % ids)
    check(parse_window(got[1].payload)["samples"] == [tuple(r) for r in wins[0][1]], "round trip samples")
    check(parse_window(got[1].payload)["class_id"] == -3, "signed class_id")
    check(parse_hello(got[0].payload) == h, "hello parse")
    check(d.crc_errors >= 1, "crc error counted")
    check("GM_MODEL_HASH=0" in d.text_lines and "hello" in d.text_lines, "text lines %s" % d.text_lines)
    check(d.frames == 5, "frames %d" % d.frames)
    d2 = Decoder(accept_samples=True)
    fr = d2.feed(sm)
    check(len(fr) == 1 and parse_samples(fr[0].payload)["chunk"] == 70000 & 0xFFFF, "samples decode")
    check(len(Decoder().feed(sm)) == 0, "v1 rejects SAMPLES")
    # flush_stale: false WINDOW header then a HELLO
    d3 = Decoder()
    fake = bytes((SYNC0, SYNC1, T_WINDOW, 0x92, 0x03, 9))
    fr = d3.feed(fake + hello)
    check(fr == [], "false header stalls")
    fr = d3.flush_stale()
    check(len(fr) == 1 and fr[0].ftype == T_HELLO, "flush_stale recovers hello")
    return fails


def main(argv):
    """CLI entry: --selftest. Returns the exit code."""
    if "--selftest" in argv:
        fails = _selftest()
        if fails:
            print("c2_proto selftest FAIL: " + "; ".join(fails))
            return 1
        print("c2_proto selftest PASS")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
# [END AI-GENERATED]
