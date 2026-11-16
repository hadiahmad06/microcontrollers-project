#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""W2-4T: spec-based tests for the PC-side recording tools (ticket W2-4T, tester test-rec).

Written from docs/agent/hadi/briefs/W2-4_spec.md (S0-S8) ONLY, without reading the implementation.
WORKING ASSUMPTION: open_questions Q1 (C2 as proposed), not decided.

Run:  python3 tools/tests/test_recording.py      (one PASS/FAIL line per test, then ALL PASS, exit 0 / 1)
Optional: pass test-name substrings as arguments to run a subset.

The ORACLE below (crc16, frame builder, payload layouts, tiny stream walker) is written from the C2 byte
layout of spec S6 and never imports c2_proto, so the implementation cannot grade itself.
"""
import csv
import io
import json
import os
import random
import re
import struct
import subprocess
import sys
import tempfile
import traceback

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
REPO = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

PY = sys.executable
LABELS = ("none", "swipe_right", "swipe_left", "raise", "push_down", "circle_cw",
          "circle_ccw", "twist", "thrust")


# --------------------------------------------------------------------------- oracle (spec S6, own code)
def o_crc16(data, crc=0xFFFF):
    """CRC-16/IBM-3740: poly 0x1021, init 0xFFFF, no reflection, xorout 0 (bitwise)."""
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def o_frame(ftype, seq, payload):
    """A5 5A TYPE LEN(le16) SEQ payload CRC(le16 over bytes 2..5+LEN)."""
    body = bytes([ftype]) + struct.pack("<H", len(payload)) + bytes([seq & 0xFF]) + payload
    return b"\xA5\x5A" + body + struct.pack("<H", o_crc16(body))


def o_feature_ver():
    import features_ref
    return features_ref.FEATURES_VERSION


def o_hello(seq, odr=100, rng=4, n=150, pre=15, feat=None, mh=0, proto=1):
    feat = o_feature_ver() if feat is None else feat
    return o_frame(0x01, seq, struct.pack("<BBBBBBI", proto, odr, rng, n, pre, feat, mh & 0xFFFFFFFF))


def o_window(seq, wid, samples, trig=15, over=0, mh=0, flags=0, cls=0, conf=0, ev=0, n=150):
    flat = [int(v) for row in samples for v in row]
    pl = struct.pack("<HBBHIBbBB", wid & 0xFFFF, n, trig, over, mh & 0xFFFFFFFF, flags, cls, conf, ev)
    pl += struct.pack("<450h", *flat)
    return o_frame(0x02, seq, pl)


def o_samples(seq, chunk, samples):
    flat = [int(v) for row in samples for v in row]
    return o_frame(0x04, seq, struct.pack("<HB", chunk & 0xFFFF, 16) + struct.pack("<48h", *flat))


def o_walk(buf):
    """Tiny independent stream walker: returns (text_prefix_bytes, [(type, seq, payload, raw_frame)])."""
    i = buf.find(b"\xA5\x5A")
    prefix = buf[:i] if i >= 0 else buf
    frames = []
    while i >= 0 and i + 6 <= len(buf):
        assert buf[i:i + 2] == b"\xA5\x5A", "stream not contiguous frames at %d" % i
        t, ln, seq = buf[i + 2], struct.unpack("<H", buf[i + 3:i + 5])[0], buf[i + 5]
        raw = buf[i:i + 8 + ln]
        frames.append((t, seq, raw[6:6 + ln], raw))
        i += 8 + ln
    return prefix, frames


def rnd_samples(rng, n=150):
    return rng.integers(-2048, 2048, size=(n, 3)).astype(np.int64)


def make_stream(n_windows, seed=0, hello_first=True, text=b""):
    """HELLO + n windows; returns (bytes, samples list)."""
    rng = np.random.default_rng(seed)
    out, seq, ws = text, 0, []
    if hello_first:
        out += o_hello(seq)
        seq += 1
    for k in range(n_windows):
        s = rnd_samples(rng)
        ws.append(s)
        out += o_window(seq, k, s)
        seq += 1
    return out, ws


# --------------------------------------------------------------------------- helpers
def run(args, cwd=REPO, stdin=None, timeout=600):
    p = subprocess.run([PY] + list(args), cwd=cwd, input=stdin, capture_output=True, timeout=timeout)
    err = p.stderr.decode("utf-8", "replace")
    if "can't open file" in err:   # tool missing: never let an "expects exit 2" test pass vacuously
        raise AssertionError("tool not present: " + err.strip()[-200:])
    return p.returncode, p.stdout.decode("utf-8", "replace"), err


def tool(name):
    return os.path.join(TOOLS, name)


def wfile(path, data):
    with open(path, "wb") as f:
        f.write(data)
    return path


def rfile(path):
    with open(path, "rb") as f:
        return f.read()


def rec(tmp, stream, extra, out="rec.npz", name="in.bin", quiet=True):
    inp = wfile(os.path.join(tmp, name), stream)
    args = [tool("recorder.py"), "--input", inp, "--out", os.path.join(tmp, out)] + list(extra)
    if quiet:
        args.append("--quiet")
    return run(args)


def ds_save(path, windows, labels, **extra):
    np.savez(path, windows=np.asarray(windows, dtype=np.int16), labels=np.asarray(labels, dtype=np.uint8), **extra)
    return path


def step_ds(n_per_label_list, peak_by_label=None):
    """Dataset: windows are constant 0 then a step of (peak,0,0) from sample 10 => peak L1 = peak."""
    ws, ls = [], []
    for lab, cnt in enumerate(n_per_label_list):
        for _ in range(cnt):
            w = np.zeros((150, 3), np.int16)
            pk = (peak_by_label or {}).get(lab, 100 + lab)
            w[10:, 0] = pk
            ws.append(w)
            ls.append(lab)
    return np.stack(ws), np.array(ls, np.uint8)


def need(cond, msg=""):
    if not cond:
        raise AssertionError(msg or "assertion failed")


def eq(a, b, msg=""):
    if not (a == b):
        raise AssertionError("%s: got %r, expected %r" % (msg, a, b))


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


# --------------------------------------------------------------------------- oracle sanity
@test
def oracle_selfcheck():
    eq(o_crc16(b"123456789"), 0x29B1, "oracle CRC check value")
    eq(len(o_hello(0)), 18)
    eq(len(o_window(0, 0, np.zeros((150, 3)))), 922)
    eq(len(o_samples(0, 0, np.zeros((16, 3)))), 107)
    h = o_hello(3)
    eq(h[:6], bytes([0xA5, 0x5A, 1, 10, 0, 3]))


# --------------------------------------------------------------------------- S0 labels
@test
def labels_module():
    import gesture_labels as g
    eq(tuple(g.LABELS), LABELS, "LABELS")
    for i, n in enumerate(LABELS):
        eq(g.parse_label(str(i)), i, "id " + str(i))
        eq(g.parse_label(n), i, n)
        eq(g.parse_label(n.upper()), i, n.upper())
        eq(g.parse_label(n.replace("_", "-")), i, n + " dashed")
    eq(g.parse_label("Swipe-Right"), 1)
    for bad in ("9", "-1", "", "wave", "swipe right", "1.5", "x"):
        try:
            g.parse_label(bad)
        except ValueError as e:
            need("swipe_right" in str(e), "ValueError must name the valid labels: %r" % str(e))
        else:
            raise AssertionError("parse_label(%r) should raise ValueError" % bad)


# --------------------------------------------------------------------------- S1 c2_proto encoders
@test
def proto_crc_check_value():
    import c2_proto as c
    eq(c.crc16(b"123456789"), 0x29B1)
    need(c.crc16(b"abc") == o_crc16(b"abc"), "crc16 vs oracle")
    eq(c.crc16(b"6789", c.crc16(b"12345")), 0x29B1, "crc16 chaining via crc argument")
    eq(c.crc16(b""), 0xFFFF)


@test
def proto_constants():
    import c2_proto as c
    eq((c.SYNC0, c.SYNC1, c.T_HELLO, c.T_WINDOW, c.T_SAMPLES), (0xA5, 0x5A, 1, 2, 4))
    eq((c.LEN_HELLO, c.LEN_WINDOW, c.LEN_SAMPLES), (10, 914, 99))


@test
def proto_encode_hello_bytes():
    import c2_proto as c
    eq(c.encode_hello(0), o_hello(0), "defaults")
    eq(c.encode_hello(7, 100, 4, 150, 15, 9, 0xDEADBEEF, 1), o_hello(7, feat=9, mh=0xDEADBEEF))
    eq(c.encode_hello(256 + 3), o_hello(3), "seq modulo 256")
    eq(c.encode_hello(255), o_hello(255))
    eq(c.encode_hello(1, model_hash=2 ** 32 + 5), o_hello(1, mh=5), "model_hash modulo 2^32")
    eq(c.encode_hello(1, odr_hz=50, range_g=8, n_samples=100, pre_trig=10, proto_ver=2),
       o_hello(1, odr=50, rng=8, n=100, pre=10, proto=2))
    eq(len(c.encode_hello(0)), 18)


@test
def proto_encode_window_bytes():
    import c2_proto as c
    rng = np.random.default_rng(1)
    s = rnd_samples(rng)
    s[0] = (-32768, 32767, 0)
    s[1] = (-2048, 2047, -1)
    eq(c.encode_window(4, 9, s.tolist()), o_window(4, 9, s), "defaults, list input")
    eq(c.encode_window(4, 9, s), o_window(4, 9, s), "numpy input")
    eq(c.encode_window(4, 9, [tuple(r) for r in s.tolist()]), o_window(4, 9, s), "tuple rows")
    eq(c.encode_window(5, 1000, s, trig_idx=15, overruns=3, model_hash=0x12345678, flags=1, class_id=-3, conf=200,
                       events=0x81),
       o_window(5, 1000, s, over=3, mh=0x12345678, flags=1, cls=-3, conf=200, ev=0x81), "all fields")
    eq(c.encode_window(256 + 9, 65536 + 2, s), o_window(9, 2, s), "seq/window_id wrap")
    eq(c.encode_window(0, 65535, s), o_window(0, 65535, s))
    eq(c.encode_window(0, 0, s, model_hash=2 ** 32 + 7), o_window(0, 0, s, mh=7), "model_hash modulo")
    eq(len(c.encode_window(0, 0, s)), 922)


@test
def proto_encode_samples_bytes():
    import c2_proto as c
    rng = np.random.default_rng(2)
    s = rnd_samples(rng, 16)
    s[0] = (-32768, 32767, -1)
    eq(c.encode_samples(3, 5, s.tolist()), o_samples(3, 5, s))
    eq(c.encode_samples(256 + 3, 65536 + 5, s), o_samples(3, 5, s), "wrap")
    eq(len(c.encode_samples(0, 0, s)), 107)


@test
def proto_encode_range_errors():
    import c2_proto as c
    for bad in (32768, -32769, 100000):
        for pos in (0, 77, 149):
            s = np.zeros((150, 3), np.int64)
            s[pos, pos % 3] = bad
            try:
                c.encode_window(0, 0, s)
            except ValueError:
                pass
            else:
                raise AssertionError("encode_window accepted %d" % bad)
        s16 = [[0, 0, 0]] * 15 + [[0, bad, 0]]
        try:
            c.encode_samples(0, 0, s16)
        except ValueError:
            pass
        else:
            raise AssertionError("encode_samples accepted %d" % bad)


@test
def proto_parsers():
    import c2_proto as c
    rng = np.random.default_rng(3)
    s = rnd_samples(rng)
    fr = o_window(1, 4242, s, over=5, mh=0xCAFEBABE, flags=1, cls=-2, conf=77, ev=3)
    d = c.parse_window(fr[6:-2])
    for k in ("window_id", "n_samples", "trig_idx", "overruns", "model_hash", "flags", "class_id", "conf", "events",
              "samples"):
        need(k in d, "parse_window key " + k)
    eq((d["window_id"], d["n_samples"], d["trig_idx"], d["overruns"], d["model_hash"], d["flags"], d["class_id"],
        d["conf"], d["events"]), (4242, 150, 15, 5, 0xCAFEBABE, 1, -2, 77, 3))
    eq(len(d["samples"]), 150)
    eq([tuple(r) for r in d["samples"]], [tuple(int(v) for v in r) for r in s], "samples as int tuples")
    h = c.parse_hello(o_hello(0, feat=6, mh=99)[6:-2])
    eq(h, {"proto_ver": 1, "odr_hz": 100, "range_g": 4, "n_samples": 150, "pre_trig": 15, "feature_ver": 6,
           "model_hash": 99})
    s16 = rnd_samples(rng, 16)
    sm = c.parse_samples(o_samples(0, 321, s16)[6:-2])
    eq((sm["chunk"], sm["n"]), (321, 16))
    eq([tuple(r) for r in sm["samples"]], [tuple(int(v) for v in r) for r in s16])


# --------------------------------------------------------------------------- S1 decoder
def feed_all(dec, data, chunks=None):
    out = []
    if chunks is None:
        for b in data:
            out += dec.feed(bytes([b]))
    else:
        i = 0
        for n in chunks:
            out += dec.feed(data[i:i + n])
            i += n
        out += dec.feed(data[i:])
    return out


def counters(dec):
    return (dec.garbage, dec.bad_header, dec.crc_errors, dec.frames, dec.seq_gaps)


@test
def decoder_clean_stream_byte_at_a_time():
    import c2_proto as c
    rng = np.random.default_rng(4)
    ws = [rnd_samples(rng) for _ in range(3)]
    data = o_hello(0) + o_window(1, 0, ws[0]) + o_window(2, 1, ws[1]) + o_hello(3) + o_window(4, 2, ws[2])
    d = c.Decoder()
    fr = feed_all(d, data)
    eq([(f.ftype, f.seq) for f in fr], [(1, 0), (2, 1), (2, 2), (1, 3), (2, 4)])
    eq(fr[1].payload, o_window(1, 0, ws[0])[6:-2], "payload bytes")
    eq(counters(d), (0, 0, 0, 5, 0), "counters")
    eq(d.text_lines, [])


@test
def decoder_random_chunking_equals_bytewise():
    import c2_proto as c
    rng = np.random.default_rng(5)
    r = random.Random(5)
    junk = bytes([0x00, 0xFF, 0x13, 0x80])
    data = (b"boot\r\n" + o_hello(0) + junk + o_window(1, 0, rnd_samples(rng)) + b"x\n"
            + o_window(2, 1, rnd_samples(rng)) + o_hello(3))
    bad = bytearray(o_window(4, 2, rnd_samples(rng)))
    bad[100] ^= 0x40
    data += bytes(bad) + o_window(5, 3, rnd_samples(rng))
    ref = c.Decoder()
    ref_fr = feed_all(ref, data)
    for trial in range(10):
        chunks = [r.randint(1, 700) for _ in range(40)]
        d = c.Decoder()
        fr = feed_all(d, data, chunks)
        eq([(f.ftype, f.seq, f.payload) for f in fr], [(f.ftype, f.seq, f.payload) for f in ref_fr], "frames")
        eq(counters(d), counters(ref), "counters trial %d" % trial)
        eq(d.text_lines, ref.text_lines)
    eq(ref.crc_errors, 1)
    eq(ref.frames, 5)


@test
def decoder_garbage_and_text():
    import c2_proto as c
    d = c.Decoder()
    fr = feed_all(d, b"Hello\r\n" + o_hello(0))
    eq(len(fr), 1)
    eq(d.text_lines, ["Hello"])
    eq(d.garbage, 7, "ASCII text bytes count as garbage")
    d = c.Decoder()
    feed_all(d, b"\x00\xFF\x13")
    eq((d.garbage, d.text_lines), (3, []))
    d = c.Decoder()
    feed_all(d, b"a\rb\n  x \nGM_MODEL_HASH=0\n")
    eq(d.text_lines, ["ab", "  x ", "GM_MODEL_HASH=0"], "CR ignored, line ends at LF")
    d = c.Decoder()
    feed_all(d, b"abc\xFFdef\n")
    eq(d.text_lines, ["def"], "non-ASCII byte discards the partial line")
    d = c.Decoder()
    feed_all(d, b"abc\x00def\n" + b"ghi\x1Fjkl\n")
    eq(d.text_lines, ["def", "jkl"])
    d = c.Decoder()
    fr = feed_all(d, o_hello(0) + b"stack 12\n" + o_hello(1))
    eq(len(fr), 2)
    eq(d.text_lines, ["stack 12"])


@test
def decoder_reserved_type_and_bad_len():
    import c2_proto as c
    for t in (0x03, 0x00, 0x05, 0x10, 0x11, 0x7F):
        d = c.Decoder()
        fr = feed_all(d, o_frame(t, 0, bytes(10)) + o_hello(1))
        eq([f.ftype for f in fr], [1], "type %#x" % t)
        eq(d.bad_header, 1, "type %#x" % t)
    for t, ln in ((0x01, 11), (0x01, 9), (0x02, 913), (0x02, 915), (0x02, 1024), (0x02, 1025), (0x01, 0)):
        d = c.Decoder()
        fr = feed_all(d, o_frame(t, 0, bytes(ln)) + o_hello(1))
        eq([f.ftype for f in fr], [1], "type %d len %d" % (t, ln))
        eq(d.bad_header, 1, "type %d len %d" % (t, ln))
        eq(d.crc_errors, 0)


@test
def decoder_crc_error():
    import c2_proto as c
    rng = np.random.default_rng(6)
    bad = bytearray(o_window(0, 0, rnd_samples(rng)))
    bad[300] ^= 0x01
    d = c.Decoder()
    fr = feed_all(d, bytes(bad) + o_hello(1))
    eq([f.ftype for f in fr], [1])
    eq((d.crc_errors, d.bad_header, d.frames), (1, 0, 1))
    bad = bytearray(o_hello(0))
    bad[-1] ^= 0xFF
    d = c.Decoder()
    fr = feed_all(d, bytes(bad) + o_hello(1))
    eq((len(fr), d.crc_errors), (1, 1))


@test
def decoder_crc_garbage_accounting():
    # AMBIGUITY probe: the dropped byte is a CRC error; the other 921 bytes are hunted past as garbage
    import c2_proto as c
    rng = np.random.default_rng(7)
    bad = bytearray(o_window(0, 0, rnd_samples(rng)))
    bad[300] ^= 0x01
    d = c.Decoder()
    feed_all(d, bytes(bad) + o_hello(1))
    eq(d.garbage, 921, "garbage after one CRC error")


@test
def decoder_truncated_frame():
    import c2_proto as c
    full = o_window(0, 0, np.zeros((150, 3)))
    d = c.Decoder()
    fr = feed_all(d, full[:500])
    eq((fr, d.frames, d.crc_errors, d.bad_header), ([], 0, 0, 0))
    fr = d.feed(full[500:])
    eq(len(fr), 1)


@test
def decoder_samples_rejected_unless_accepted():
    import c2_proto as c
    rng = np.random.default_rng(8)
    s16 = rnd_samples(rng, 16)
    data = o_samples(0, 0, s16) + o_hello(1)
    d = c.Decoder()
    fr = feed_all(d, data)
    eq([f.ftype for f in fr], [1], "default decoder rejects SAMPLES")
    eq(d.bad_header, 1)
    d = c.Decoder(accept_samples=True)
    fr = feed_all(d, data)
    eq([f.ftype for f in fr], [4, 1])
    eq(c.parse_samples(fr[0].payload)["chunk"], 0)
    eq(counters(d), (0, 0, 0, 2, 0))
    d = c.Decoder(accept_samples=True)
    fr = feed_all(d, o_frame(4, 0, bytes(98)) + o_hello(1))
    eq([f.ftype for f in fr], [1])
    eq(d.bad_header, 1)


@test
def decoder_seq_gaps():
    import c2_proto as c
    d = c.Decoder()
    feed_all(d, o_hello(5) + o_hello(6) + o_hello(9))
    eq((d.frames, d.seq_gaps), (3, 2), "first frame not counted; 6->9 loses 2")
    d = c.Decoder()
    feed_all(d, o_hello(254) + o_hello(255) + o_hello(0) + o_hello(2))
    eq(d.seq_gaps, 1, "wrap then a gap of 1")
    d = c.Decoder()
    feed_all(d, o_hello(255) + o_hello(1))
    eq(d.seq_gaps, 1)
    d = c.Decoder()
    feed_all(d, o_hello(0) + o_hello(0))
    eq(d.seq_gaps, 255, "repeat of the same seq = (0-0-1) mod 256")
    d = c.Decoder()
    feed_all(d, o_hello(200))
    eq(d.seq_gaps, 0)


@test
def decoder_flush_stale():
    import c2_proto as c
    false_hdr = bytes([0xA5, 0x5A, 0x02, 0x92, 0x03, 0x00])   # WINDOW header, LEN 914, SEQ 0
    d = c.Decoder()
    fr = d.feed(false_hdr + o_hello(1))
    eq(fr, [], "false WINDOW header stalls the decoder")
    fr = d.flush_stale()
    eq([f.ftype for f in fr], [1], "flush_stale rescans and completes the HELLO")
    eq(d.bad_header, 1, "dropped byte counted as bad_header")
    eq(d.frames, 1)
    eq(d.garbage, 5, "remaining header bytes hunted past")
    eq(d.flush_stale(), [], "nothing stale any more")
    eq(d.bad_header, 1, "empty buffer: no counter change")
    d = c.Decoder()
    eq(d.flush_stale(), [])
    eq(counters(d), (0, 0, 0, 0, 0))


@test
def selftests_cli():
    for mod, line in (("c2_proto.py", "c2_proto selftest PASS"), ("recorder.py", "recorder selftest PASS"),
                      ("fake_wand.py", "fake_wand selftest PASS"), ("dataset_tool.py", "dataset_tool selftest PASS")):
        rc, out, err = run([tool(mod), "--selftest"])
        eq(rc, 0, mod + " --selftest exit; stderr=" + err[-300:])
        need(line in out, "%s: expected %r in %r" % (mod, line, out))


# --------------------------------------------------------------------------- S2 recorder
@test
def rec_no_window_before_hello():
    rng = np.random.default_rng(10)
    pre = [rnd_samples(rng) for _ in range(2)]
    post = [rnd_samples(rng) for _ in range(2)]
    stream = (o_window(0, 0, pre[0]) + o_window(1, 1, pre[1]) + o_hello(2)
              + o_window(3, 2, post[0]) + o_window(4, 3, post[1]))
    with tempfile.TemporaryDirectory() as t:
        rc, out, err = rec(t, stream, ["--label", "none"])
        eq(rc, 0, err)
        d = np.load(os.path.join(t, "rec.npz"))
        eq(d["windows"].shape, (2, 150, 3))
        eq(d["window_id"].tolist(), [2, 3], "only post-HELLO windows stored")
        need((d["windows"][0] == post[0]).all() and (d["windows"][1] == post[1]).all())


@test
def rec_never_hello_stores_nothing():
    rng = np.random.default_rng(11)
    stream = o_window(0, 0, rnd_samples(rng)) + o_window(1, 1, rnd_samples(rng))
    with tempfile.TemporaryDirectory() as t:
        rc, out, err = rec(t, stream, ["--label", "none"])
        need(rc in (0, 2), "exit %d" % rc)
        if os.path.exists(os.path.join(t, "rec.npz")):
            eq(np.load(os.path.join(t, "rec.npz"))["windows"].shape[0], 0)


@test
def rec_hello_mismatch_per_field():
    tail, _ = make_stream(2, hello_first=False)
    cases = {"proto_ver": dict(proto=2), "odr_hz": dict(odr=50), "range_g": dict(rng=8),
             "n_samples": dict(n=100), "pre_trig": dict(pre=10)}
    for field, kw in cases.items():
        with tempfile.TemporaryDirectory() as t:
            rc, out, err = rec(t, o_hello(0, **kw) + tail, ["--label", "none"])
            eq(rc, 3, "%s mismatch exit code (out=%r err=%r)" % (field, out[-200:], err[-200:]))
            need(field in out + err, "message must name the field %s: %r" % (field, out + err))
    with tempfile.TemporaryDirectory() as t:
        rng = np.random.default_rng(12)
        stream = o_hello(0) + o_window(1, 0, rnd_samples(rng)) + o_hello(2, odr=50) + o_window(3, 1, rnd_samples(rng))
        rc, out, err = rec(t, stream, ["--label", "none"])
        eq(rc, 3, "mismatching later HELLO")


@test
def rec_feature_ver_only_warns():
    tail, _ = make_stream(2, hello_first=False)
    with tempfile.TemporaryDirectory() as t:
        rc, out, err = rec(t, o_hello(0, feat=o_feature_ver() + 5) + tail, ["--label", "none"])
        eq(rc, 0, err)
        need("warn" in (out + err).lower(), "feature_ver mismatch should print a warning")
        eq(np.load(os.path.join(t, "rec.npz"))["windows"].shape[0], 2)


@test
def rec_rejects_wrong_geometry_windows():
    rng = np.random.default_rng(13)
    good = [rnd_samples(rng) for _ in range(2)]
    stream = (o_hello(0) + o_window(1, 0, good[0]) + o_window(2, 1, rnd_samples(rng), n=100)
              + o_window(3, 2, rnd_samples(rng), trig=7) + o_window(4, 3, good[1]))
    with tempfile.TemporaryDirectory() as t:
        rc, out, err = rec(t, stream, ["--label", "raise"])
        eq(rc, 0, err)
        d = np.load(os.path.join(t, "rec.npz"))
        eq(d["window_id"].tolist(), [0, 3])
        meta = json.loads(str(d["meta"]))
        eq(meta["counters"]["rejected"], 2)
        eq(meta["counters"]["stored"], 2)


@test
def rec_label_and_count():
    stream, ws = make_stream(6, seed=14)
    with tempfile.TemporaryDirectory() as t:
        rc, out, err = rec(t, stream, ["--label", "Swipe-Right", "--count", "4"])
        eq(rc, 0, err)
        d = np.load(os.path.join(t, "rec.npz"))
        eq(d["labels"].tolist(), [1, 1, 1, 1], "count stops after 4")
        eq(d["window_id"].tolist(), [0, 1, 2, 3])
    with tempfile.TemporaryDirectory() as t:
        rc, out, err = rec(t, stream, ["--label", "5"])
        eq(rc, 0, err)
        eq(np.load(os.path.join(t, "rec.npz"))["labels"].tolist(), [5] * 6, "count default 0 = until EOF")
    with tempfile.TemporaryDirectory() as t:
        rc, out, err = rec(t, stream, ["--label", "wave"])
        eq(rc, 2, "bad label exit code")
    with tempfile.TemporaryDirectory() as t:
        rc, out, err = rec(t, stream, [])
        eq(rc, 2, "neither --label nor --plan")


@test
def rec_plan_no_pause():
    stream, ws = make_stream(8, seed=15)
    with tempfile.TemporaryDirectory() as t:
        rc, out, err = rec(t, stream, ["--plan", "swipe_right:2,none:3,thrust:1", "--no-pause"], quiet=False)
        eq(rc, 0, err)
        d = np.load(os.path.join(t, "rec.npz"))
        eq(d["labels"].tolist(), [1, 1, 0, 0, 0, 8], "stops after the last step")
        eq(d["window_id"].tolist(), [0, 1, 2, 3, 4, 5])
        low = out.lower()
        need("next: swipe_right x2" in low, "NEXT line missing: %r" % out[:400])
        need("next: none x3" in low and "next: thrust x1" in low)
        need("[swipe_right 1/2]" in low and "[none 3/3]" in low, "per-window [NAME i/N] lines")
    with tempfile.TemporaryDirectory() as t:
        rc, out, err = rec(t, stream, ["--plan", "bogus:2", "--no-pause"])
        eq(rc, 2)
    with tempfile.TemporaryDirectory() as t:
        p = subprocess.run([PY, tool("recorder.py"), "--input", "-", "--out", os.path.join(t, "r.npz"),
                            "--plan", "none:2", "--no-pause", "--quiet"], cwd=REPO, input=stream, capture_output=True)
        eq(p.returncode, 0, p.stderr.decode()[-300:])
        eq(np.load(os.path.join(t, "r.npz"))["labels"].tolist(), [0, 0])


@test
def rec_output_arrays_and_meta():
    rng = np.random.default_rng(16)
    s0, s1 = rnd_samples(rng), rnd_samples(rng)
    stream = (o_hello(0, feat=o_feature_ver(), mh=0xABCD)
              + o_window(1, 65535, s0, over=4, mh=0x01020304, flags=1, cls=-3, conf=201, ev=0x85)
              + o_window(2, 0, s1))
    with tempfile.TemporaryDirectory() as t:
        rc, out, err = rec(t, stream, ["--label", "circle_cw", "--subject", "4", "--session", "3"])
        eq(rc, 0, err)
        d = np.load(os.path.join(t, "rec.npz"))   # must work without allow_pickle
        exp = {"windows": ("int16", (2, 150, 3)), "labels": ("uint8", (2,)), "subject": ("uint8", (2,)),
               "session": ("uint16", (2,)), "window_id": ("uint16", (2,)), "overruns": ("uint16", (2,)),
               "model_hash": ("uint32", (2,)), "dev_flags": ("uint8", (2,)), "dev_class": ("int8", (2,)),
               "dev_conf": ("uint8", (2,)), "events": ("uint8", (2,)), "synthetic": ("uint8", ())}
        for k, (dt, sh) in exp.items():
            need(k in d.files, "missing array " + k)
            eq((str(d[k].dtype), d[k].shape), (dt, sh), k)
        need("meta" in d.files)
        eq((d["meta"].ndim, d["meta"].dtype.kind), (0, "U"), "meta is a 0-d unicode string")
        need((d["windows"][0] == s0).all() and (d["windows"][1] == s1).all(), "window contents")
        eq(d["labels"].tolist(), [5, 5])
        eq(d["subject"].tolist(), [4, 4])
        eq(d["session"].tolist(), [3, 3])
        eq(d["window_id"].tolist(), [65535, 0])
        eq(d["overruns"].tolist(), [4, 0])
        eq(d["model_hash"].tolist(), [0x01020304, 0])
        eq(d["dev_flags"].tolist(), [1, 0])
        eq(d["dev_class"].tolist(), [-3, 0])
        eq(d["dev_conf"].tolist(), [201, 0])
        eq(d["events"].tolist(), [0x85, 0])
        eq(int(d["synthetic"]), 0)
        meta = json.loads(str(d["meta"]))
        for k in ("tool", "version", "started", "source", "hello", "counters", "label_names"):
            need(k in meta, "meta key " + k)
        eq(meta["label_names"], list(LABELS))
        for k in ("garbage", "bad_header", "crc_errors", "frames", "seq_gaps", "stored", "rejected", "skipped"):
            need(k in meta["counters"], "counters key " + k)
        eq((meta["counters"]["stored"], meta["counters"]["rejected"], meta["counters"]["skipped"]), (2, 0, 0))
        eq(meta["counters"]["frames"], 3)
        eq(meta["hello"]["model_hash"], 0xABCD)
        eq(meta["hello"]["odr_hz"], 100)
        need("in.bin" in str(meta["source"]), "source names the input file")
    with tempfile.TemporaryDirectory() as t:
        rc, out, err = rec(t, stream, ["--label", "none", "--synthetic"])
        d = np.load(os.path.join(t, "rec.npz"))
        eq((d["subject"].tolist(), d["session"].tolist(), int(d["synthetic"])), ([0, 0], [0, 0], 1))
        eq(d["synthetic"].ndim, 0)


@test
def rec_per_window_line():
    w = np.zeros((150, 3), np.int64)
    w[3] = (10, -20, 30)      # peak L1 deviation from sample 0 = 60
    stream = o_hello(0) + o_window(1, 77, w, over=2, flags=1, cls=5, conf=90) + o_window(2, 78, np.zeros((150, 3)))
    with tempfile.TemporaryDirectory() as t:
        rc, out, err = rec(t, stream, ["--label", "twist"], quiet=False)
        eq(rc, 0, err)
        need("77" in out and "78" in out, "window ids in per-window lines")
        need("twist" in out.lower())
        need("60" in out, "peak L1 deviation 60 printed")
        need("5/90" in out, "on-device result class/conf printed when flags bit 0 set")


@test
def rec_raw_log_equals_input():
    stream = b"boot\n" + make_stream(3, seed=17)[0] + bytes(range(0, 40)) + b"tail"
    with tempfile.TemporaryDirectory() as t:
        rc, out, err = rec(t, stream, ["--label", "none"])
        eq(rc, 0, err)
        eq(rfile(os.path.join(t, "rec.bin")), stream, "default raw log = OUT with .bin suffix")
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, "sub_raw.log")
        rc, out, err = rec(t, stream, ["--label", "none", "--raw-log", p])
        eq(rc, 0, err)
        eq(rfile(p), stream)
    with tempfile.TemporaryDirectory() as t:
        big = make_stream(12, seed=18)[0]
        need(len(big) > 8192)
        rc, out, err = rec(t, big, ["--label", "none"])
        eq(rfile(os.path.join(t, "rec.bin")), big)
        eq(np.load(os.path.join(t, "rec.npz"))["windows"].shape[0], 12)


@test
def rec_append():
    sA, wA = make_stream(2, seed=19)
    sB, wB = make_stream(3, seed=20)
    with tempfile.TemporaryDirectory() as t:
        rc, o, e = rec(t, sA, ["--label", "none", "--session", "5", "--subject", "2", "--synthetic",
                               "--raw-log", os.path.join(t, "a.bin")])
        eq(rc, 0, e)
        rc, o, e = rec(t, sB, ["--label", "raise", "--append", "--subject", "2", "--raw-log", os.path.join(t, "b.bin")],
                       name="in2.bin")
        eq(rc, 0, e)
        d = np.load(os.path.join(t, "rec.npz"))
        eq(d["windows"].shape, (5, 150, 3))
        eq(d["labels"].tolist(), [0, 0, 3, 3, 3])
        eq(d["session"].tolist(), [5, 5, 6, 6, 6], "default session = max+1")
        eq(int(d["synthetic"]), 1, "synthetic = max(old,new)")
        need((d["windows"][2] == wB[0]).all() and (d["windows"][0] == wA[0]).all())
        eq(str(d["session"].dtype), "uint16")
        meta = json.loads(str(d["meta"]))
        need(isinstance(meta.get("sessions"), list) and len(meta["sessions"]) == 2, "meta.sessions one per run")
    with tempfile.TemporaryDirectory() as t:
        rc, o, e = rec(t, sA, ["--label", "none", "--raw-log", os.path.join(t, "a.bin")])
        rc, o, e = rec(t, sB, ["--label", "none", "--append", "--session", "9", "--raw-log", os.path.join(t, "b.bin")],
                       name="in2.bin")
        eq(rc, 0, e)
        d = np.load(os.path.join(t, "rec.npz"))
        eq(d["session"].tolist(), [0, 0, 9, 9, 9])
        eq(int(d["synthetic"]), 0)
        rc, o, e = rec(t, sB, ["--label", "none", "--append", "--synthetic", "--raw-log", os.path.join(t, "c.bin")],
                       name="in3.bin")
        eq(rc, 0, e)
        d = np.load(os.path.join(t, "rec.npz"))
        eq(int(d["synthetic"]), 1, "new synthetic run makes the file synthetic")
        eq(d["session"].tolist()[-3:], [10, 10, 10])
    with tempfile.TemporaryDirectory() as t:
        rc, o, e = rec(t, sA, ["--label", "none", "--append"])
        eq(rc, 2, "--append with missing OUT")


@test
def rec_existing_out_without_append():
    sA, _ = make_stream(2, seed=21)
    with tempfile.TemporaryDirectory() as t:
        rc, o, e = rec(t, sA, ["--label", "none"])
        eq(rc, 0, e)
        before = rfile(os.path.join(t, "rec.npz"))
        rc, o, e = rec(t, make_stream(4, seed=22)[0], ["--label", "none", "--raw-log", os.path.join(t, "x.bin")],
                       name="in2.bin")
        eq(rc, 2, "existing OUT without --append")
        eq(rfile(os.path.join(t, "rec.npz")), before, "existing OUT untouched")


@test
def rec_argument_errors():
    sA, _ = make_stream(1, seed=23)
    with tempfile.TemporaryDirectory() as t:
        inp = wfile(os.path.join(t, "in.bin"), sA)
        out = os.path.join(t, "o.npz")
        rc, o, e = run([tool("recorder.py"), "--out", out, "--label", "none"])
        eq(rc, 2, "neither --port nor --input")
        rc, o, e = run([tool("recorder.py"), "--port", "/dev/null", "--input", inp, "--out", out, "--label", "none"])
        eq(rc, 2, "both --port and --input")
        rc, o, e = run([tool("recorder.py"), "--input", os.path.join(t, "missing.bin"), "--out", out,
                        "--label", "none"])
        eq(rc, 2, "unreadable input")


@test
def rec_garbage_and_text_tolerated():
    rng = np.random.default_rng(24)
    s = [rnd_samples(rng) for _ in range(3)]
    stream = (b"GM_MODEL_HASH=0\n" + bytes([0, 1, 2, 255]) + o_hello(0) + b"noise\x00\xFF" + o_window(1, 0, s[0])
              + o_hello(2) + o_window(3, 1, s[1]) + o_window(4, 2, s[2]))
    with tempfile.TemporaryDirectory() as t:
        rc, o, e = rec(t, stream, ["--label", "push_down"])
        eq(rc, 0, e)
        d = np.load(os.path.join(t, "rec.npz"))
        eq(d["window_id"].tolist(), [0, 1, 2])
        need(all((d["windows"][i] == s[i]).all() for i in range(3)))


@test
def rec_truncated_tail_leaves_valid_file():
    stream, _ = make_stream(4, seed=25)
    with tempfile.TemporaryDirectory() as t:
        rc, o, e = rec(t, stream[:-300], ["--label", "none"])   # last frame truncated
        eq(rc, 0, e)
        eq(np.load(os.path.join(t, "rec.npz"))["windows"].shape[0], 3)
        eq([f for f in os.listdir(t) if ".tmp" in f], [], "no stray temp files")


# --------------------------------------------------------------------------- S4 dataset_tool
@test
def ds_validation_failures():
    w, l = step_ds([2, 2])
    with tempfile.TemporaryDirectory() as t:
        cases = {}
        wb = w.copy()
        wb[0, 0, 0] = 2048
        cases["hi.npz"] = dict(windows=wb, labels=l)
        wb = w.copy()
        wb[1, 5, 2] = -2049
        cases["lo.npz"] = dict(windows=wb, labels=l)
        cases["badlabel.npz"] = dict(windows=w, labels=np.array([0, 0, 9, 1], np.uint8))
        cases["shape.npz"] = dict(windows=w[:, :149, :], labels=l)
        cases["dtype.npz"] = dict(windows=w.astype(np.float32), labels=l)
        cases["labdtype.npz"] = dict(windows=w, labels=l.astype(np.float64))
        cases["subjlen.npz"] = dict(windows=w, labels=l, subject=np.zeros(3, np.uint8))
        cases["sesslen.npz"] = dict(windows=w, labels=l, session=np.zeros(5, np.uint16))
        cases["nowin.npz"] = dict(labels=l)
        for name, arrs in cases.items():
            p = os.path.join(t, name)
            np.savez(p, **arrs)
            rc, o, e = run([tool("dataset_tool.py"), "info", p])
            eq(rc, 2, name + " should fail validation")
            need(name in o + e, "message must name the file " + name)
        p = os.path.join(t, "hi.npz")
        for cmd in (["drop", "--out", os.path.join(t, "x.npz"), p, "--index", "0"],
                    ["relabel", "--out", os.path.join(t, "x.npz"), p, "--index", "0", "--label", "none"],
                    ["csv", "--out", os.path.join(t, "x.csv"), p],
                    ["merge", "--out", os.path.join(t, "x.npz"), p, p]):
            rc, o, e = run([tool("dataset_tool.py")] + cmd)
            eq(rc, 2, cmd[0] + " on invalid input")
        wb = w.copy()
        wb[0, 0, 0], wb[0, 0, 1] = 2047, -2048
        p = ds_save(os.path.join(t, "edge.npz"), wb, l)
        rc, o, e = run([tool("dataset_tool.py"), "info", p])
        eq(rc, 0, e)


@test
def ds_info_output():
    w, l = step_ds([25, 25, 25, 25, 25, 25, 25, 25, 5], peak_by_label={2: 777})
    with tempfile.TemporaryDirectory() as t:
        p = ds_save(os.path.join(t, "a.npz"), w, l, subject=np.full(len(l), 3, np.uint8),
                    session=np.full(len(l), 7, np.uint16), synthetic=np.uint8(1))
        rc, o, e = run([tool("dataset_tool.py"), "info", p])
        eq(rc, 0, e)
        need("SYNTHETIC" in o, "SYNTHETIC in capitals when synthetic=1")
        for name in LABELS:
            need(name in o, "label name " + name)
        m = re.search(r"swipe_left\D*(\d+)", o)
        need(m and m.group(1) == "25", "swipe_left count 25: %r" % o)
        m = re.search(r"thrust\D*(\d+)", o)
        need(m and m.group(1) == "5", "thrust count 5")
        need("777" in o, "median peak L1 for swipe_left")
        low = o.lower()
        need(re.search(r"warn[^\n]*thrust|thrust[^\n]*warn", low) is not None, "warning line names thrust")
        need("a.npz" in o)
        p2 = ds_save(os.path.join(t, "b.npz"), w, l)
        rc, o2, e2 = run([tool("dataset_tool.py"), "info", p2])
        eq(rc, 0, e2)
        need("SYNTHETIC" not in o2, "no SYNTHETIC without the flag")
        rc, o3, e3 = run([tool("dataset_tool.py"), "info", p, p2])
        eq(rc, 0, e3)
        need("a.npz" in o3 and "b.npz" in o3 and "SYNTHETIC" in o3)
        need("410" in o3 or "total" in o3.lower(), "total over files (205+205=410)")


@test
def ds_merge():
    wA, lA = step_ds([2, 1, 0, 0, 0, 0, 0, 0, 0])
    wB, lB = step_ds([0, 0, 2, 0, 0, 0, 0, 0, 1], peak_by_label={2: 300, 8: 400})
    nA, nB = len(lA), len(lB)
    with tempfile.TemporaryDirectory() as t:
        a = ds_save(os.path.join(t, "a.npz"), wA, lA, subject=np.full(nA, 1, np.uint8),
                    session=np.full(nA, 0, np.uint16), overruns=np.arange(nA, dtype=np.uint16),
                    onlyA=np.arange(nA, dtype=np.int32), synthetic=np.uint8(0))
        b = ds_save(os.path.join(t, "b.npz"), wB, lB, subject=np.full(nB, 2, np.uint8),
                    session=np.full(nB, 0, np.uint16), overruns=np.arange(nB, dtype=np.uint16) + 100,
                    synthetic=np.uint8(1))
        out = os.path.join(t, "m.npz")
        rc, o, e = run([tool("dataset_tool.py"), "merge", "--out", out, a, b])
        eq(rc, 0, e)
        d = np.load(out)
        eq(d["windows"].shape, (nA + nB, 150, 3))
        need((d["windows"][:nA] == wA).all() and (d["windows"][nA:] == wB).all(), "argument order")
        eq(d["labels"].tolist(), lA.tolist() + lB.tolist())
        eq(d["subject"].tolist(), [1] * nA + [2] * nB)
        eq(d["overruns"].tolist(), list(range(nA)) + [100 + i for i in range(nB)], "extra in all inputs kept")
        need("onlyA" not in d.files, "array present in only some inputs is dropped")
        need("onlyA" in o + e, "warning names the dropped array")
        eq(int(d["synthetic"]), 1, "synthetic = max")
        for k, dt in (("windows", "int16"), ("labels", "uint8"), ("subject", "uint8"), ("session", "uint16"),
                      ("overruns", "uint16")):
            eq(str(d[k].dtype), dt, "dtype " + k)
        meta = json.loads(str(d["meta"]))
        need("merged_from" in meta)
        dump = json.dumps(meta["merged_from"])
        need("a.npz" in dump and "b.npz" in dump, "merged_from names files")
        need(str(nA) in dump and str(nB) in dump, "merged_from has N")
        c = ds_save(os.path.join(t, "c.npz"), wB, lB, subject=np.full(nB, 1, np.uint8),
                    session=np.full(nB, 0, np.uint16), overruns=np.zeros(nB, np.uint16))
        out2 = os.path.join(t, "m2.npz")
        rc, o, e = run([tool("dataset_tool.py"), "merge", "--out", out2, a, c])
        eq(rc, 2, "dup (subject,session) refused")
        need(not os.path.exists(out2), "no output on refusal")
        rc, o, e = run([tool("dataset_tool.py"), "merge", "--out", out2, a, c, "--allow-dup-session"])
        eq(rc, 0, e)
        eq(np.load(out2)["windows"].shape[0], nA + nB)


@test
def ds_drop_relabel():
    w, l = step_ds([2, 2, 2, 2, 2])
    n = len(l)
    with tempfile.TemporaryDirectory() as t:
        p = ds_save(os.path.join(t, "a.npz"), w, l, subject=np.arange(n, dtype=np.uint8),
                    extra=np.arange(n, dtype=np.int32) * 10, synthetic=np.uint8(1))
        out = os.path.join(t, "o.npz")
        rc, o, e = run([tool("dataset_tool.py"), "drop", "--out", out, p, "--index", "1,3,7"])
        eq(rc, 0, e)
        d = np.load(out)
        keep = [i for i in range(n) if i not in (1, 3, 7)]
        eq(d["labels"].tolist(), [int(l[i]) for i in keep])
        eq(d["subject"].tolist(), keep, "per-window arrays dropped consistently")
        eq(d["extra"].tolist(), [i * 10 for i in keep])
        need((d["windows"] == w[keep]).all())
        eq(int(d["synthetic"]), 1, "output keeps all arrays")
        eq(str(d["windows"].dtype), "int16")
        for bad in (str(n), "1,%d" % (n + 5)):
            o2 = os.path.join(t, "bad.npz")
            rc, oo, ee = run([tool("dataset_tool.py"), "drop", "--out", o2, p, "--index", bad])
            eq(rc, 2, "drop out-of-range index " + bad)
            need(not os.path.exists(o2))
        out = os.path.join(t, "r.npz")
        rc, o, e = run([tool("dataset_tool.py"), "relabel", "--out", out, p, "--index", "3,7", "--label", "swipe_left"])
        eq(rc, 0, e)
        d = np.load(out)
        exp = l.copy()
        exp[[3, 7]] = 2
        eq(d["labels"].tolist(), exp.tolist())
        eq(str(d["labels"].dtype), "uint8")
        eq(d["extra"].tolist(), [i * 10 for i in range(n)])
        need((d["windows"] == w).all())
        rc, oo, ee = run([tool("dataset_tool.py"), "relabel", "--out", os.path.join(t, "bad2.npz"), p, "--index",
                          str(n), "--label", "none"])
        eq(rc, 2, "relabel out-of-range index")
        rc, oo, ee = run([tool("dataset_tool.py"), "relabel", "--out", os.path.join(t, "bad3.npz"), p, "--index",
                          "0", "--label", "nonsense"])
        eq(rc, 2, "relabel unknown label")
        rc, oo, ee = run([tool("dataset_tool.py"), "relabel", "--out", os.path.join(t, "ok4.npz"), p, "--index",
                          "0", "--label", "7"])
        eq(rc, 0, ee)
        eq(int(np.load(os.path.join(t, "ok4.npz"))["labels"][0]), 7)


@test
def ds_csv():
    rng = np.random.default_rng(30)
    w = rng.integers(-2048, 2048, size=(3, 150, 3)).astype(np.int16)
    l = np.array([4, 0, 8], np.uint8)
    with tempfile.TemporaryDirectory() as t:
        p = ds_save(os.path.join(t, "a.npz"), w, l, subject=np.array([5, 6, 7], np.uint8),
                    session=np.array([1, 2, 3], np.uint16))
        out = os.path.join(t, "o.csv")
        rc, o, e = run([tool("dataset_tool.py"), "csv", "--out", out, p])
        eq(rc, 0, e)
        rows = list(csv.reader(io.StringIO(rfile(out).decode())))
        eq(rows[0], ["window", "label", "label_name", "subject", "session", "t", "x", "y", "z"])
        eq(len(rows) - 1, 3 * 150, "one row per sample")
        r = rows[1]
        eq((r[0], r[1], r[2], r[3], r[4], r[5]), ("0", "4", "push_down", "5", "1", "0"))
        eq(tuple(int(v) for v in r[6:9]), tuple(int(v) for v in w[0, 0]))
        r = rows[1 + 2 * 150 + 149]
        eq((r[0], r[1], r[2], r[3], r[4], r[5]), ("2", "8", "thrust", "7", "3", "149"))
        eq(tuple(int(v) for v in r[6:9]), tuple(int(v) for v in w[2, 149]))


@test
def ds_out_equals_input_refused():
    w, l = step_ds([2, 2])
    with tempfile.TemporaryDirectory() as t:
        a = ds_save(os.path.join(t, "a.npz"), w, l)
        b = ds_save(os.path.join(t, "b.npz"), w, l, subject=np.array([1, 1, 1, 1], np.uint8))
        before = rfile(a)
        for cmd in (["merge", "--out", a, a, b, "--allow-dup-session"],
                    ["merge", "--out", a, b, a, "--allow-dup-session"],
                    ["drop", "--out", a, a, "--index", "0"],
                    ["relabel", "--out", a, a, "--index", "0", "--label", "none"]):
            rc, o, e = run([tool("dataset_tool.py")] + cmd)
            eq(rc, 2, cmd[0] + " with --out == input")
            eq(rfile(a), before, "input untouched")
        rc, o, e = run([tool("dataset_tool.py"), "drop", "--out", os.path.join(t, ".", "a.npz"), a, "--index", "0"])
        eq(rc, 2, "equivalent path spelling")


# --------------------------------------------------------------------------- S3 fake_wand
def fw_dataset(path, n=7, seed=40):
    rng = np.random.default_rng(seed)
    w = rng.integers(-2048, 2048, size=(n, 150, 3)).astype(np.int16)
    l = np.array([3, 0, 3, 8, 0, 1, 3][:n], np.uint8)
    ds_save(path, w, l)
    return w, l


def fw(t, extra, ds="ds.npz", out="s.bin"):
    return run([tool("fake_wand.py"), "--data", os.path.join(t, ds), "--out", os.path.join(t, out)] + list(extra))


@test
def fw_stream_structure_and_determinism():
    with tempfile.TemporaryDirectory() as t:
        w, l = fw_dataset(os.path.join(t, "ds.npz"))
        rc, o, e = fw(t, ["--text", "GM_MODEL_HASH=0"])
        eq(rc, 0, e)
        need("SYNTHETIC: fake_wand output, never real data" in e, "stderr banner")
        b1 = rfile(os.path.join(t, "s.bin"))
        rc, o, e = fw(t, ["--text", "GM_MODEL_HASH=0"], out="s2.bin")
        eq(rfile(os.path.join(t, "s2.bin")), b1, "deterministic")
        prefix, frames = o_walk(b1)
        eq(prefix, b"GM_MODEL_HASH=0\n", "text line first, followed by LF")
        types = [f[0] for f in frames]
        eq(types[:7], [1, 2, 2, 1, 2, 2, 1], "HELLO, then HELLO after every 2 windows")
        eq(types.count(2), 7)
        eq([f[1] for f in frames], [i % 256 for i in range(len(frames))], "SEQ counts every frame from 0")
        wid = 0
        for ftype, seq, pl, raw in frames:
            if ftype == 2:
                eq(raw, o_window(seq, wid, w[wid]), "window %d bytes" % wid)
                wid += 1
            else:
                eq(raw, o_hello(seq), "HELLO bytes seq %d" % seq)
        rc, o, e = fw(t, ["--hello-every", "3"], out="s3.bin")
        eq(rc, 0, e)
        _, fr3 = o_walk(rfile(os.path.join(t, "s3.bin")))
        eq([f[0] for f in fr3][:8], [1, 2, 2, 2, 1, 2, 2, 2])
        ds_save(os.path.join(t, "big.npz"), np.zeros((300, 150, 3), np.int16), np.zeros(300, np.uint8))
        rc, o, e = fw(t, [], ds="big.npz", out="big.bin")
        _, frb = o_walk(rfile(os.path.join(t, "big.bin")))
        eq([f[1] for f in frb], [i % 256 for i in range(len(frb))])
        eq(frb[256][1], 0)
        fw(t, ["--corrupt", "0.5", "--seed", "5"], out="c1.bin")
        fw(t, ["--corrupt", "0.5", "--seed", "5"], out="c2.bin")
        eq(rfile(os.path.join(t, "c1.bin")), rfile(os.path.join(t, "c2.bin")), "seeded corruption deterministic")


@test
def fw_order_grouped_and_plan():
    with tempfile.TemporaryDirectory() as t:
        w, l = fw_dataset(os.path.join(t, "ds.npz"))
        rc, o, e = fw(t, ["--order", "grouped", "--print-plan"])
        eq(rc, 0, e)
        order = np.argsort(l, kind="stable")
        _, frames = o_walk(rfile(os.path.join(t, "s.bin")))
        wins = [f for f in frames if f[0] == 2]
        eq(len(wins), 7)
        for k, f in enumerate(wins):
            eq(f[2][14:], o_window(0, 0, w[order[k]])[6 + 14:-2], "grouped (stable) order")
            eq(struct.unpack("<H", f[2][:2])[0], k, "window_id counts 0.. in emitted order")
        lines = [x.strip() for x in e.splitlines() if x.strip() and not x.startswith("SYNTHETIC")]
        need("none:2,swipe_right:1,raise:3,thrust:1" in lines, "plan string on stderr; got %r" % lines)
        rc, o, e = fw(t, [], out="asis.bin")
        _, fa = o_walk(rfile(os.path.join(t, "asis.bin")))
        wa = [f for f in fa if f[0] == 2]
        for k, f in enumerate(wa):
            eq(f[2][14:], o_window(0, 0, w[k])[6 + 14:-2], "as-is order")


@test
def fw_corrupt():
    with tempfile.TemporaryDirectory() as t:
        w, l = fw_dataset(os.path.join(t, "ds.npz"))
        fw(t, [], out="clean.bin")
        clean = rfile(os.path.join(t, "clean.bin"))
        for P, seed in (("0", "1"), ("0.5", "3"), ("1", "1")):
            rc, o, e = fw(t, ["--corrupt", P, "--seed", seed], out="c.bin")
            eq(rc, 0, e)
            bad = rfile(os.path.join(t, "c.bin"))
            eq(len(bad), len(clean), "corruption flips a byte, never changes length")
            _, fc = o_walk(clean)
            _, fb = o_walk(bad)
            ndiff = 0
            for a, b in zip(fc, fb):
                if a[3] != b[3]:
                    ndiff += 1
                    diffs = [i for i in range(len(a[3])) if a[3][i] != b[3][i]]
                    eq(len(diffs), 1, "exactly one byte flipped")
                    need(6 <= diffs[0] < 6 + 914, "flip inside the payload")
                    eq(a[0], 2, "only WINDOW frames corrupted")
            if P == "0":
                eq(ndiff, 0)
            if P == "1":
                eq(ndiff, 7)
            lines = [x for x in e.splitlines() if "corrupt" in x.lower()]
            need(lines, "stderr must report the corrupted count: %r" % e)
            nums = re.findall(r"(?<![\d.])\d+(?![\d.])", " ".join(lines))
            need(str(ndiff) in nums, "reported count %r should contain %d" % (lines, ndiff))


@test
def fw_samples_mode():
    with tempfile.TemporaryDirectory() as t:
        w, l = fw_dataset(os.path.join(t, "ds.npz"))
        rc, o, e = fw(t, ["--samples"])
        eq(rc, 0, e)
        _, frames = o_walk(rfile(os.path.join(t, "s.bin")))
        sm = [f for f in frames if f[0] == 4]
        eq(len(sm), (7 * 150) // 16, "trailing partial chunk dropped")
        need(not any(f[0] == 2 for f in frames), "no WINDOW frames in samples mode")
        flat = w.reshape(-1, 3).astype(np.int64)
        for k, f in enumerate(sm):
            eq(f[3], o_samples(f[1], k, flat[16 * k:16 * k + 16]), "chunk %d" % k)


@test
def fw_arg_errors():
    with tempfile.TemporaryDirectory() as t:
        fw_dataset(os.path.join(t, "ds.npz"))
        rc, o, e = run([tool("fake_wand.py"), "--data", os.path.join(t, "ds.npz")])
        need(rc != 0, "neither --out nor --pty must fail")
        rc, o, e = run([tool("fake_wand.py"), "--data", os.path.join(t, "nope.npz"), "--out", os.path.join(t, "x")])
        need(rc != 0, "missing data must fail")


# --------------------------------------------------------------------------- S5 pipeline
def _plan_line(stderr):
    cand = [x.strip() for x in stderr.splitlines() if re.fullmatch(r"\w+:\d+(,\w+:\d+)*", x.strip())]
    need(cand, "no plan line on stderr: %r" % stderr)
    return cand[-1]


@test
def pipeline_end_to_end():
    with tempfile.TemporaryDirectory() as t:
        P = lambda n: os.path.join(t, n)
        rc, o, e = run([tool("synth_dataset.py"), "--out", P("ds.npz"), "--per-class", "30", "--seed", "3"])
        eq(rc, 0, e)
        rc, o, e = run([tool("fake_wand.py"), "--data", P("ds.npz"), "--out", P("stream.bin"), "--order", "grouped",
                        "--print-plan", "--text", "GM_MODEL_HASH=0"])
        eq(rc, 0, e)
        plan = [x for x in e.splitlines() if not x.startswith("SYNTHETIC")][-1]   # S5: grep -v '^SYNTHETIC' | tail -1
        eq(plan, _plan_line(e), "plan is the last non-SYNTHETIC stderr line")
        rc, o, e = run([tool("recorder.py"), "--input", P("stream.bin"), "--out", P("rec.npz"), "--plan", plan,
                        "--no-pause", "--synthetic", "--quiet"])
        eq(rc, 0, e)
        src = np.load(P("ds.npz"))
        order = np.argsort(src["labels"], kind="stable")
        d = np.load(P("rec.npz"))
        eq(d["windows"].shape, (270, 150, 3))
        need((d["windows"] == src["windows"][order]).all(), "windows equal grouped source")
        need((d["labels"] == src["labels"][order]).all(), "labels equal grouped source")
        eq(int(d["synthetic"]), 1)
        eq(d["window_id"].tolist(), list(range(270)))
        meta = json.loads(str(d["meta"]))
        eq(meta["counters"]["crc_errors"], 0)
        eq(meta["counters"]["stored"], 270)
        eq(rfile(P("rec.bin")), rfile(P("stream.bin")), "raw log == stream")
        rc, o, e = run([tool("dataset_tool.py"), "info", P("rec.npz")])
        eq(rc, 0, e)
        need("SYNTHETIC" in o)
        rc, o, e = run([tool("train.py"), "--data", P("rec.npz"), "--out-dir", P("train"), "--epochs", "5"])
        eq(rc, 0, "train.py exit; stderr tail=" + e[-400:])
        rc, o, e = run([tool("recorder.py"), "--input", P("rec.bin"), "--out", P("rec2.npz"), "--plan", plan,
                        "--no-pause", "--synthetic", "--quiet", "--raw-log", P("rec2.bin")])
        eq(rc, 0, e)
        need((np.load(P("rec2.npz"))["windows"] == d["windows"]).all(), "replay of the raw log")


@test
def pipeline_corrupt_variant():
    with tempfile.TemporaryDirectory() as t:
        P = lambda n: os.path.join(t, n)
        rc, o, e = run([tool("synth_dataset.py"), "--out", P("ds.npz"), "--per-class", "30", "--seed", "3"])
        eq(rc, 0, e)
        rc, o, e = run([tool("fake_wand.py"), "--data", P("ds.npz"), "--out", P("clean.bin"), "--order", "grouped"])
        eq(rc, 0, e)
        rc, o, e = run([tool("fake_wand.py"), "--data", P("ds.npz"), "--out", P("bad.bin"), "--order", "grouped",
                        "--print-plan", "--corrupt", "0.1", "--seed", "1"])
        eq(rc, 0, e)
        plan = _plan_line(e)
        _, fc = o_walk(rfile(P("clean.bin")))
        _, fb = o_walk(rfile(P("bad.bin")))
        pairs = [(x, y) for x, y in zip(fc, fb) if x[0] == 2]
        good_idx = [k for k, (a, b) in enumerate(pairs) if a[3] == b[3]]
        n_bad = 270 - len(good_idx)
        need(n_bad > 0, "seed 1 / P 0.1 should corrupt at least one frame")
        rc, o, e = run([tool("recorder.py"), "--input", P("bad.bin"), "--out", P("rec.npz"), "--plan", plan,
                        "--no-pause", "--synthetic", "--quiet"])
        eq(rc, 0, e)
        src = np.load(P("ds.npz"))
        order = np.argsort(src["labels"], kind="stable")
        d = np.load(P("rec.npz"))
        eq(d["windows"].shape[0], 270 - n_bad, "stores exactly the uncorrupted windows")
        need((d["windows"] == src["windows"][order][good_idx]).all(), "stored windows are the uncorrupted ones")
        meta = json.loads(str(d["meta"]))
        eq(meta["counters"]["crc_errors"], n_bad, "CRC error counter equals the number corrupted")
        eq(meta["counters"]["stored"], 270 - n_bad)


# --------------------------------------------------------------------------- runner
def main(argv):
    sel = argv[1:]
    fails = 0
    for fn in TESTS:
        if sel and not any(s in fn.__name__ for s in sel):
            continue
        try:
            fn()
        except Exception as ex:   # noqa: BLE001 - report every failure kind
            fails += 1
            tb = traceback.extract_tb(ex.__traceback__)[-1]
            msg = ("%s: %s" % (type(ex).__name__, ex)).replace("\n", " ")[:600]
            print("FAIL %s  [%s:%d] %s" % (fn.__name__, os.path.basename(tb.filename), tb.lineno, msg))
        else:
            print("PASS %s" % fn.__name__)
    if fails:
        print("%d FAILED" % fails)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
# [END AI-GENERATED]
