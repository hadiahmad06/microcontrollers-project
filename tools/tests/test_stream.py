#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""W2-6T: spec-based tests for continuous recording (SAMPLES) and the offline trigger cut (ticket W2-6T, tester test-stream).

Written from docs/agent/hadi/briefs/W2-6_spec.md (V1-V3, building on W2-4_spec.md S1-S3) ONLY, without reading the
implementation (recorder.py --samples, cut_stream.py, fake_wand.py --marks-out).
WORKING ASSUMPTION: open_questions Q1, Q2, not decided.

Run:  python3 tools/tests/test_stream.py      (one PASS/FAIL line per test, then ALL PASS, exit 0 / 1)
Optional: pass test-name substrings as arguments to run a subset.

The ORACLE (CRC, frame builder, SAMPLES chunker, expected-trigger loop, labelling rule) is written here from the C2
layout (S6) and the V2 text. It uses tools/trigger_ref.py (already reviewed) as the trigger reference, never fake_wand.
Interpretations the spec leaves open are marked "AMBIGUITY" in comments; boundary cases that the text does not fix
(distance exactly equal to a --window-after-mark / --none-gap limit) are deliberately NOT tested.
"""
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import time
import traceback

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
REPO = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import trigger_ref  # noqa: E402  (reference, reviewed)

PY = sys.executable
RATE = 100  # Hz, C0 ODR: seconds -> samples


# --------------------------------------------------------------------------- oracle: C2 frames (spec S6)
def o_crc16(data, crc=0xFFFF):
    """CRC-16/IBM-3740 (poly 0x1021, init 0xFFFF, no reflection, xorout 0), bitwise."""
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def o_frame(ftype, seq, payload):
    """A5 5A TYPE LEN(le16) SEQ payload CRC(le16 over bytes 2..5+LEN)."""
    body = bytes([ftype]) + struct.pack("<H", len(payload)) + bytes([seq & 0xFF]) + payload
    return b"\xA5\x5A" + body + struct.pack("<H", o_crc16(body))


def o_hello(seq, odr=100, rng=4, n=150, pre=15, feat=None, mh=0, proto=1):
    """A HELLO frame (18 B)."""
    if feat is None:
        import features_ref
        feat = features_ref.FEATURES_VERSION
    return o_frame(0x01, seq, struct.pack("<BBBBBBI", proto, odr, rng, n, pre, feat, mh))


def o_samples(seq, chunk, rows):
    """A SAMPLES frame (107 B): chunk u16, n u8 = 16, 16 x 3 x int16."""
    flat = [int(v) for row in rows for v in row]
    return o_frame(0x04, seq, struct.pack("<HB", chunk & 0xFFFF, 16) + struct.pack("<48h", *flat))


def build_stream(samples, chunk0=0, drop=(), text_before=None, hello_every=0, pre=b"", hello_first=True):
    """Make the byte stream a bring-up wand would send for a continuous recording.

    Args:
        samples: int array [M,3], M a multiple of 16; chunk k holds samples[16k:16k+16].
        chunk0: chunk counter value of chunk 0 (mod 65536).
        drop: set of chunk indices k that are NOT sent (lost chunks).
        text_before: {k: "line"} ASCII line (plus LF) emitted just before chunk k.
        hello_every: emit an extra HELLO after every that many sent chunks (0 = never).
        pre: bytes emitted before everything.
        hello_first: emit a HELLO before the first chunk.
    Returns:
        (bytes, expect) with expect = dict(samples=int16 [M',3] received, gaps=[(idx, lost)], ovr=[idx]).
    """
    text_before = text_before or {}
    out, seq = bytes(pre), 0
    if hello_first:
        out += o_hello(seq)
        seq += 1
    got, gaps, ovr, sent, run = [], [], [], 0, 0
    for k in range(len(samples) // 16):
        if k in text_before:
            out += text_before[k].encode("ascii") + b"\n"
            if re.match(r"OVR\s+\d+$", text_before[k]):
                ovr.append(16 * sent)
        if k in drop:
            run += 1
            continue
        if run:
            gaps.append((16 * sent, run))
            run = 0
        rows = samples[16 * k:16 * k + 16]
        out += o_samples(seq, chunk0 + k, rows)
        seq += 1
        sent += 1
        got.append(np.asarray(rows))
        if hello_every and sent % hello_every == 0:
            out += o_hello(seq)
            seq += 1
    exp = dict(samples=np.concatenate(got).astype(np.int16) if got else np.zeros((0, 3), np.int16),
               gaps=gaps, ovr=ovr)
    return out, exp


# --------------------------------------------------------------------------- oracle: signals, trigger, labelling
def make_signal(M, bursts, seed=7):
    """Quiet baseline (0,0,512)+-3 noise plus step bursts.

    Args:
        M: number of samples (multiple of 16 recommended).
        bursts: list of (onset, length, (dx, dy, dz)); the burst adds the step on [onset, onset+length).
        seed: noise seed.
    Returns:
        int16 [M,3].
    """
    rng = np.random.default_rng(seed)
    s = rng.integers(-3, 4, size=(M, 3)) + np.array([0, 0, 512])
    for onset, length, d in bursts:
        s[onset:onset + length] += np.array(d)
    return s.astype(np.int16)


def ref_triggers(samples, resyncs=(), thr_mg=250, rel_delay=135):
    """Expected trigger indices: trigger_ref over the stream, resync before every index in `resyncs`, release after
    trig+rel_delay (same loop as trigger_ref.run, but with many resync points).

    Args:
        samples: int array [M,3]. resyncs: iterable of sample indices. thr_mg: threshold. rel_delay: release delay.
    Returns:
        list of trigger sample indices.
    """
    t = trigger_ref.Trigger()
    t.set_threshold_mg(thr_mg)
    rs = set(int(r) for r in resyncs)
    trigs, trig_at = [], -1
    for i, s in enumerate(np.asarray(samples).tolist()):
        if i in rs:
            t.resync()
            trig_at = -1
        if t.feed(s):
            trigs.append(i)
            trig_at = i
        if trig_at >= 0 and rel_delay >= 0 and i - trig_at >= rel_delay:
            t.release()
            trig_at = -1
    return trigs


def oracle_label(t, marks, w, g):
    """Label rule of V2. Returns the label, 0 (none) or None (dropped). `marks` = [(idx, label)]."""
    before = [m for m in marks if m[0] <= t]
    if before:
        latest = max(before, key=lambda m: m[0])
        if t - latest[0] <= w:
            return latest[1]
    if any(abs(m[0] - t) <= g for m in marks):
        return None
    return 0


def oracle_cut(samples, marks, resyncs, w_sec, g_sec, thr_mg=250):
    """Expected (trig_sample, labels, windows) of cut_stream. AMBIGUITY: kept windows keep trigger order."""
    samples = np.asarray(samples)
    trigs = ref_triggers(samples, resyncs, thr_mg)
    kept = trigger_ref.cut_windows(samples.tolist(), trigs)
    w, g = int(round(w_sec * RATE)), int(round(g_sec * RATE))
    ts, ls, ws = [], [], []
    for t, win in kept:
        lab = oracle_label(t, marks, w, g)
        if lab is None:
            continue
        ts.append(t)
        ls.append(lab)
        ws.append(win)
    return ts, ls, np.array(ws, dtype=np.int16).reshape(-1, 150, 3)


# --------------------------------------------------------------------------- helpers
def run(args, cwd=REPO, stdin=None, timeout=600):
    """Run a python script; returns (rc, stdout, stderr). Raises if the script file is missing."""
    p = subprocess.run([PY] + list(args), cwd=cwd, input=stdin, capture_output=True, timeout=timeout)
    err = p.stderr.decode("utf-8", "replace")
    if "can't open file" in err:  # tool missing: never let an "expects exit 2" test pass vacuously
        raise AssertionError("tool not present: " + err.strip()[-200:])
    return p.returncode, p.stdout.decode("utf-8", "replace"), err


def tool(name):
    """Absolute path of tools/<name>."""
    return os.path.join(TOOLS, name)


def wfile(path, data):
    """Write bytes to path; returns path."""
    with open(path, "wb") as f:
        f.write(data)
    return path


def eq(a, b, msg=""):
    """Assert a == b."""
    if a != b:
        raise AssertionError("%s: %r != %r" % (msg, a, b))


def need(c, msg):
    """Assert c."""
    if not c:
        raise AssertionError(msg)


def arr_eq(a, b, msg=""):
    """Assert two arrays have equal shape and content."""
    a, b = np.asarray(a), np.asarray(b)
    if a.shape != b.shape or not (a == b).all():
        raise AssertionError("%s: shape %s vs %s, content differs" % (msg, a.shape, b.shape))


class Tmp:
    """Context manager: a temp directory; P(name) gives a path inside it."""

    def __enter__(self):
        self.d = tempfile.TemporaryDirectory()
        return self

    def __exit__(self, *a):
        self.d.cleanup()

    def P(self, name):
        """Path of a file inside the temp directory."""
        return os.path.join(self.d.name, name)


def record(t, stream, extra=(), out="s.npz", name="in.bin", label="none"):
    """Run recorder.py --samples on a byte stream; returns (rc, stdout, stderr)."""
    inp = wfile(t.P(name), stream)
    args = [tool("recorder.py"), "--input", inp, "--out", t.P(out), "--no-pause", "--quiet", "--samples"]
    if label is not None:
        args += ["--label", label]
    return run(args + list(extra))


def load(path):
    """np.load without allow_pickle (the default)."""
    return np.load(path)


def write_stream_npz(path, samples, gaps=(), ovr=(), marks=(), synthetic=0, name="fake_source.bin"):
    """Hand-built STREAM file in the V1 layout (so V2 tests never depend on the recorder)."""
    np.savez(path, samples=np.asarray(samples, np.int16).reshape(-1, 3),
             chunk_gaps=np.asarray(gaps, np.int32).reshape(-1, 2),
             ovr=np.asarray(ovr, np.int32).reshape(-1),
             marks=np.asarray(marks, np.int32).reshape(-1, 2),
             synthetic=np.uint8(synthetic),
             meta=np.array(json.dumps({"tool": "test_stream", "version": 1, "source": name,
                                       "label_names": []})))
    return path


def cut(t, stream_npz, extra=(), out="ds.npz"):
    """Run cut_stream.py on a stream file; returns (rc, stdout, stderr)."""
    return run([tool("cut_stream.py"), "--stream", stream_npz, "--out", t.P(out)] + list(extra))


# --------------------------------------------------------------------------- V1: stream file
def test_v1_arrays_and_dtypes():
    sig = make_signal(16 * 40, [])
    data, exp = build_stream(sig, drop={20, 21, 22, 30}, text_before={10: "OVR 3", 25: "OVR 9"}, hello_every=7)
    with Tmp() as t:
        rc, o, e = record(t, data, ["--synthetic"], label="swipe_left")
        eq(rc, 0, e)
        d = load(t.P("s.npz"))
        for k in ("samples", "chunk_gaps", "ovr", "marks", "meta", "synthetic"):
            need(k in d.files, "missing array " + k)
        eq(d["samples"].dtype, np.int16, "samples dtype")
        eq(d["samples"].ndim, 2)
        eq(d["samples"].shape[1], 3)
        arr_eq(d["samples"], exp["samples"], "samples = all received samples in order")
        eq(d["chunk_gaps"].dtype, np.int32, "chunk_gaps dtype")
        eq(d["chunk_gaps"].shape[1:], (2,))
        eq(d["ovr"].dtype, np.int32, "ovr dtype")
        eq(d["ovr"].ndim, 1)
        eq(d["marks"].dtype, np.int32, "marks dtype")
        eq(d["marks"].shape[1:], (2,))
        need(all(int(r[1]) == 2 for r in d["marks"]), "--label swipe_left marks carry label 2")
        eq(int(d["synthetic"]), 1)
        eq(d["synthetic"].dtype, np.uint8)
        need(isinstance(json.loads(str(d["meta"])), dict), "meta is a JSON object")
        rc, o, e = record(t, data, [], out="s2.npz")
        eq(rc, 0, e)
        eq(int(load(t.P("s2.npz"))["synthetic"]), 0, "synthetic defaults to 0")


def test_v1_chunk_gaps_lost_chunks():
    sig = make_signal(16 * 60, [])
    data, exp = build_stream(sig, drop={10, 20, 21, 22, 23, 24, 25, 26, 40})  # 1, 7 and 1 lost chunks
    eq(exp["gaps"], [(16 * 10, 1), (16 * 19, 7), (16 * 32, 1)], "oracle sanity")
    with Tmp() as t:
        rc, o, e = record(t, data)
        eq(rc, 0, e)
        d = load(t.P("s.npz"))
        # AMBIGUITY: "sample index where a gap starts" is taken as the index in `samples` of the first sample
        # received after the lost chunk(s) (= number of samples received before the gap).
        arr_eq(d["chunk_gaps"], np.array(exp["gaps"], np.int32).reshape(-1, 2), "chunk_gaps")
        arr_eq(d["samples"], exp["samples"], "samples")


def test_v1_chunk_counter_wrap_no_gap():
    sig = make_signal(16 * 24, [])
    data, exp = build_stream(sig, chunk0=65536 - 6)  # counters 65530..65535, 0..17: wraps at k = 6
    with Tmp() as t:
        rc, o, e = record(t, data)
        eq(rc, 0, e)
        d = load(t.P("s.npz"))
        eq(d["chunk_gaps"].shape, (0, 2), "a wrap 65535 -> 0 is not a gap")
        arr_eq(d["samples"], exp["samples"])


def test_v1_chunk_counter_wrap_with_gaps():
    sig = make_signal(16 * 30, [])
    # counters: k=5 -> 65535 (lost, right before the wrap), k=12,13 -> 6,7 (two lost after the wrap)
    data, exp = build_stream(sig, chunk0=65536 - 6, drop={5, 12, 13})
    eq(exp["gaps"], [(16 * 5, 1), (16 * 11, 2)])
    with Tmp() as t:
        rc, o, e = record(t, data)
        eq(rc, 0, e)
        arr_eq(load(t.P("s.npz"))["chunk_gaps"], np.array(exp["gaps"], np.int32), "gaps across the 65536 wrap")
    # a lost run that spans the wrap itself (counters 0,1,2 lost)
    data, exp = build_stream(sig, chunk0=65536 - 6, drop={6, 7, 8})
    with Tmp() as t:
        rc, o, e = record(t, data)
        eq(rc, 0, e)
        arr_eq(load(t.P("s.npz"))["chunk_gaps"], np.array(exp["gaps"], np.int32), "run 0,1,2 lost")
    # lost chunk number 65535 and 0 together
    data, exp = build_stream(sig, chunk0=65536 - 6, drop={5, 6})
    with Tmp() as t:
        rc, o, e = record(t, data)
        eq(rc, 0, e)
        arr_eq(load(t.P("s.npz"))["chunk_gaps"], np.array(exp["gaps"], np.int32), "65535 and 0 lost")


def test_v1_ovr_text_line():
    sig = make_signal(16 * 30, [])
    text = {4: "OVR 1", 9: "GM_MODEL_HASH=0", 15: "OVR 12", 22: "OVR 100"}
    data, exp = build_stream(sig, text_before=text, pre=b"boot banner\n")
    eq(exp["ovr"], [16 * 4, 16 * 15, 16 * 22], "oracle sanity")
    with Tmp() as t:
        rc, o, e = record(t, data)
        eq(rc, 0, e)
        d = load(t.P("s.npz"))
        # AMBIGUITY: "sample index of every OVR line" = number of samples received before the line (the index the
        # next sample gets). Non-OVR text lines produce no entry.
        arr_eq(d["ovr"], np.array(exp["ovr"], np.int32), "ovr indices")
        eq(d["samples"].shape[0], 16 * 30)


def test_v1_hello_gate():
    sig = make_signal(16 * 20, [])
    d1, _ = build_stream(sig[:16 * 6], hello_first=False)  # 6 chunks before any HELLO
    d2, _ = build_stream(sig[16 * 6:], chunk0=6)           # HELLO, then 14 chunks
    with Tmp() as t:
        rc, o, e = record(t, d1 + d2)
        eq(rc, 0, e)
        arr_eq(load(t.P("s.npz"))["samples"], sig[16 * 6:], "no sample is stored before the first valid HELLO")
    with Tmp() as t:  # no HELLO at all: nothing stored (file absent or empty), no crash
        rc, o, e = record(t, d1)
        need(rc in (0, 2, 3), "exit code %d" % rc)
        if os.path.exists(t.P("s.npz")):
            eq(load(t.P("s.npz"))["samples"].shape[0], 0)


def test_v1_hello_mismatch_exit3():
    sig = make_signal(16 * 4, [])
    for kw in ({"odr": 200}, {"rng": 8}, {"proto": 2}, {"pre": 10}, {"n": 100}):
        data = o_hello(0, **kw) + b"".join(o_samples(1 + k, k, sig[16 * k:16 * k + 16]) for k in range(4))
        with Tmp() as t:
            rc, o, e = record(t, data)
            eq(rc, 3, "HELLO %s must exit 3 (%s)" % (kw, e[-200:]))


def test_v1_marks_plan_no_pause_pipe():
    """--plan with --no-pause: GO every --every SEC wall clock. Feed the bytes slowly through stdin so the whole
    plan elapses; test only what is deterministic: count, labels in plan order, non-decreasing sample indices."""
    sig = make_signal(16 * 120, [])
    data, _ = build_stream(sig)
    cut_at = np.linspace(0, len(data), 9, dtype=int)
    with Tmp() as t:
        p = subprocess.Popen([PY, tool("recorder.py"), "--input", "-", "--out", t.P("s.npz"), "--samples",
                              "--plan", "swipe_right:2,none:3", "--no-pause", "--every", "0.15", "--quiet"],
                             cwd=REPO, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for a, b in zip(cut_at[:-1], cut_at[1:]):
                p.stdin.write(data[a:b])
                p.stdin.flush()
                time.sleep(0.25)
            p.stdin.close()
        except BrokenPipeError:
            pass
        out, err = p.communicate(timeout=60)
        eq(p.returncode, 0, err.decode()[-300:])
        m = load(t.P("s.npz"))["marks"]
        eq(m.shape, (5, 2), "five GO lines in plan order -> five marks")
        eq([int(x) for x in m[:, 1]], [1, 1, 0, 0, 0], "labels in plan order")
        need(all(int(m[i, 0]) <= int(m[i + 1, 0]) for i in range(4)), "mark sample indices non-decreasing")
        need(0 <= int(m[0, 0]) and int(m[-1, 0]) <= load(t.P("s.npz"))["samples"].shape[0],
             "mark indices inside the stream")


def test_v1_marks_single_label_shape():
    data, _ = build_stream(make_signal(16 * 20, []))
    with Tmp() as t:
        rc, o, e = record(t, data, label="circle_cw")
        eq(rc, 0, e)
        m = load(t.P("s.npz"))["marks"]
        eq(m.shape[1:], (2,))
        need(all(int(r[1]) == 5 for r in m), "all marks carry label circle_cw = 5")


def test_v1_atomic_rewrite_every_16_chunks():
    """The file is rewritten while recording (every 16 chunks) and a reader never sees a broken file."""
    sig = make_signal(16 * 120, [])
    data, exp = build_stream(sig)
    hello, frames = data[:18], data[18:]
    fl = 107
    with Tmp() as t:
        p = subprocess.Popen([PY, tool("recorder.py"), "--input", "-", "--out", t.P("s.npz"), "--samples",
                              "--label", "none", "--no-pause", "--quiet"],
                             cwd=REPO, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        seen = set()
        try:
            p.stdin.write(hello + frames[:20 * fl])
            p.stdin.flush()
            deadline = time.time() + 15
            while time.time() < deadline and not os.path.exists(t.P("s.npz")):
                time.sleep(0.05)
            need(os.path.exists(t.P("s.npz")), "file appears after >= 16 chunks while stdin is still open")
            for k in range(20, 120):  # keep it busy and hammer the reader
                p.stdin.write(frames[k * fl:(k + 1) * fl])
                p.stdin.flush()
                time.sleep(0.004)
                z = np.load(t.P("s.npz"))  # must never fail (atomic os.replace)
                n = z["samples"].shape[0]
                seen.add(n)
                eq(n % 16, 0, "a rewrite holds whole chunks")
                arr_eq(z["samples"], exp["samples"][:n], "partial file is a prefix of the stream")
            p.stdin.close()
        except BrokenPipeError:
            pass
        out, err = p.communicate(timeout=60)
        eq(p.returncode, 0, err.decode()[-300:])
        need(len(seen) >= 2, "file grew while recording (saw %s)" % sorted(seen))
        arr_eq(load(t.P("s.npz"))["samples"], exp["samples"], "final file holds everything")
        left = [f for f in os.listdir(t.d.name) if f not in ("s.npz", "s.bin")]
        eq(left, [], "no temp files left behind")


# --------------------------------------------------------------------------- V2: cut_stream
# Mark offsets relative to the trigger sample t: [(offset, label)] per burst. Distances used are 0, 50, 99, 101, 150,
# 199, 201 only; never exactly 100 or 200 (boundary not fixed by the spec).
CASES = [
    [(0, 1)], [(-199, 2)], [(-201, 3)], [(99, 4)], [(101, 5)],
    [(-150, 1), (-50, 6)], [(-99, 7)], [(-150, 8)], [(-199, 3)],
]
GEST_AT = [400 + 600 * i for i in range(len(CASES))]
DOUBLE_AT = 400 + 600 * len(CASES)  # loud 60, quiet, loud again 200 samples later (second trigger after rearm)
M_LABEL = DOUBLE_AT + 1200


def labelling_stream():
    """Signal with 9 single bursts + a double burst; marks placed relative to the reference triggers.

    Returns:
        (samples, marks sorted by index, trigger indices).
    """
    bursts = [(o, 60, (500, -300, 0)) for o in GEST_AT]
    bursts += [(DOUBLE_AT, 60, (500, -300, 0)), (DOUBLE_AT + 200, 60, (-400, 300, 100))]
    sig = make_signal(M_LABEL, bursts, seed=11)
    trigs = ref_triggers(sig)
    need(len(trigs) == len(CASES) + 2, "construction: %d triggers %s" % (len(trigs), trigs))
    for tt, o in zip(trigs, GEST_AT + [DOUBLE_AT, DOUBLE_AT + 200]):
        need(o < tt <= o + 6, "trigger shortly after onset (%d vs %d)" % (tt, o))
    marks = []
    for tt, case in zip(trigs, CASES):
        marks += [(tt + off, lab) for off, lab in case]
    marks.append((trigs[len(CASES)], 5))  # double burst: mark at the first trigger
    marks.sort()
    return sig, marks, trigs


def check_cut(w_sec, g_sec, extra):
    """Run cut_stream on the labelling stream and compare with the oracle. Returns (dataset, trigs, labels)."""
    sig, marks, trigs = labelling_stream()
    with Tmp() as t:
        sp = write_stream_npz(t.P("S.npz"), sig, marks=marks)
        rc, o, e = cut(t, sp, extra)
        eq(rc, 0, e[-400:])
        d = load(t.P("ds.npz"))
        ts, ls, ws = oracle_cut(sig, marks, (), w_sec, g_sec)
        need(len(ts) >= 1, "construction: expected windows %d" % len(ts))
        for k in ("windows", "labels", "trig_sample"):
            need(k in d.files, "missing array " + k)
        eq(d["windows"].dtype, np.int16, "windows dtype")
        eq(d["labels"].dtype, np.uint8, "labels dtype")
        eq(d["trig_sample"].dtype, np.int32, "trig_sample dtype")
        arr_eq(d["trig_sample"], np.array(ts, np.int32), "trig_sample (kept triggers, trigger order)")
        arr_eq(d["labels"], np.array(ls, np.uint8), "labels")
        arr_eq(d["windows"], ws, "windows == samples[t-15:t+135]")
        for w, tt in zip(d["windows"], d["trig_sample"]):
            arr_eq(w, sig[int(tt) - 15:int(tt) + 135], "window of trigger %d" % tt)
        need("S.npz" in json.dumps(json.loads(str(d["meta"]))), "meta names the source stream file")
        return d, ts, ls


def test_v2_defaults_labelling():
    # defaults: --window-after-mark 2.0, --none-gap 1.0
    d, ts, ls = check_cut(2.0, 1.0, [])
    need(0 in ls and any(x > 0 for x in ls), "construction covers none and marked windows")
    need(len(ts) < len(CASES) + 2, "construction: at least one ambiguous window is dropped")


def test_v2_labelling_explicit_default_values():
    check_cut(2.0, 1.0, ["--thr-mg", "250", "--window-after-mark", "2.0", "--none-gap", "1.0"])


def test_v2_labelling_swapped_limits():
    # window-after-mark 1.0 < none-gap 2.0: a window 1..2 s after a mark is ambiguous and dropped
    check_cut(1.0, 2.0, ["--window-after-mark", "1.0", "--none-gap", "2.0"])


def test_v2_labelling_long_window():
    # 4.0 s: the second trigger of the double burst (about 205 samples after the first) takes the mark's label
    d, ts, ls = check_cut(4.0, 1.0, ["--window-after-mark", "4.0"])
    need(ls.count(5) >= 2, "both windows of the double burst carry the mark label 5: %s" % ls)


def test_v2_labelling_exact_boundaries():
    """One burst, one mark near the trigger. Never tests a distance equal to the limit."""
    sig = make_signal(1600, [(500, 60, (500, -300, 0))], seed=5)
    (tt,) = ref_triggers(sig)
    for (w, g, off, want) in [(2.0, 1.0, -199, 2), (2.0, 1.0, -201, 0), (2.0, 1.0, +99, "drop"),
                              (2.0, 1.0, +101, 0), (1.0, 2.0, -99, 2), (1.0, 2.0, -101, "drop"),
                              (1.0, 2.0, -199, "drop"), (1.0, 2.0, -201, 0), (1.0, 2.0, +199, "drop"),
                              (1.0, 2.0, +201, 0)]:
        with Tmp() as t:
            sp = write_stream_npz(t.P("S.npz"), sig, marks=[(tt + off, 2)])
            rc, o, e = cut(t, sp, ["--window-after-mark", str(w), "--none-gap", str(g)])
            eq(rc, 0, "W=%s G=%s off=%d: %s" % (w, g, off, e[-300:]))
            d = load(t.P("ds.npz"))
            if want == "drop":
                eq(d["windows"].shape[0], 0, "W=%s G=%s off=%d dropped" % (w, g, off))
            else:
                eq(d["windows"].shape[0], 1, "W=%s G=%s off=%d" % (w, g, off))
                eq(int(d["labels"][0]), want, "W=%s G=%s off=%d" % (w, g, off))


def test_v2_resync_at_gaps_and_ovr():
    """Gap / ovr indices re-seed the trigger; compared to trigger_ref with resync at those indices."""
    onsets = [400 + 500 * i for i in range(8)]
    sig = make_signal(4800, [(o, 60, (500, -300, 0)) for o in onsets], seed=3)
    gap_idx, ovr_idx = onsets[2] - 6, onsets[5] - 4  # burst begins right after the re-sync: absorbed in warm-up
    base = ref_triggers(sig)
    rs = ref_triggers(sig, (gap_idx, ovr_idx))
    need(base != rs, "construction: resync must remove two triggers (%s / %s)" % (base, rs))
    with Tmp() as t:
        sp = write_stream_npz(t.P("S.npz"), sig, gaps=[(gap_idx, 1)], ovr=[ovr_idx])
        rc, o, e = cut(t, sp)
        eq(rc, 0, e[-400:])
        d = load(t.P("ds.npz"))
        ts, ls, ws = oracle_cut(sig, [], [gap_idx, ovr_idx], 2.0, 1.0)
        arr_eq(d["trig_sample"], np.array(ts, np.int32), "triggers with resync at gap and ovr")
        arr_eq(d["windows"], ws)
        need(all(int(x) == 0 for x in d["labels"]), "no marks anywhere: every window is none (0)")
        for kw in (dict(gaps=[(gap_idx, 3)]), dict(ovr=[ovr_idx])):  # only a gap / only an ovr
            sp = write_stream_npz(t.P("S2.npz"), sig, **kw)
            rc, o, e = cut(t, sp, out="ds2.npz")
            eq(rc, 0, e[-400:])
            rsx = [g for g, _ in kw.get("gaps", [])] + list(kw.get("ovr", []))
            ts2, _, _ = oracle_cut(sig, [], rsx, 2.0, 1.0)
            arr_eq(load(t.P("ds2.npz"))["trig_sample"], np.array(ts2, np.int32), str(kw))


def test_v2_release_delay_135():
    """Second burst 200 samples after the first only triggers with release after +135 and a quiet re-arm."""
    sig = make_signal(2000, [(400, 60, (500, -300, 0)), (600, 60, (-400, 300, 100))], seed=9)
    exp = ref_triggers(sig)
    eq(len(exp), 2, "construction")
    need(ref_triggers(sig, rel_delay=-1) != exp, "construction: never-release differs")
    need(ref_triggers(sig, rel_delay=300) != exp, "construction: release at 300 differs")
    with Tmp() as t:
        sp = write_stream_npz(t.P("S.npz"), sig)
        rc, o, e = cut(t, sp)
        eq(rc, 0, e[-400:])
        arr_eq(load(t.P("ds.npz"))["trig_sample"], np.array(exp, np.int32))


def test_v2_thr_mg_option():
    sig = make_signal(3000, [(400 + 700 * i, 60, (200, 0, 0)) for i in range(3)], seed=13)
    lo, hi = ref_triggers(sig, thr_mg=250), ref_triggers(sig, thr_mg=700)
    need(len(lo) == 3 and len(hi) == 0, "construction: 200-count step fires at 250 mg, not at 700 mg (%s %s)" % (lo, hi))
    with Tmp() as t:
        sp = write_stream_npz(t.P("S.npz"), sig)
        rc, o, e = cut(t, sp, ["--thr-mg", "250"])
        eq(rc, 0, e[-300:])
        arr_eq(load(t.P("ds.npz"))["trig_sample"], np.array(lo, np.int32))
        rc, o, e = cut(t, sp, ["--thr-mg", "700"], out="ds2.npz")
        need(rc in (0, 2), "700 mg: empty result handled (exit %d)" % rc)
        if rc == 0 and os.path.exists(t.P("ds2.npz")):
            eq(load(t.P("ds2.npz"))["windows"].shape[0], 0)


def test_v2_synthetic_propagates():
    sig = make_signal(2000, [(400, 60, (500, -300, 0))], seed=2)
    with Tmp() as t:
        for flag in (1, 0):
            sp = write_stream_npz(t.P("S%d.npz" % flag), sig, synthetic=flag)
            rc, o, e = cut(t, sp, out="ds%d.npz" % flag)
            eq(rc, 0, e[-300:])
            d = load(t.P("ds%d.npz" % flag))
            need("synthetic" in d.files, "synthetic scalar present")
            eq(int(d["synthetic"]), flag, "synthetic propagates")
        data, _ = build_stream(sig)  # and through the real recorder chain
        rc, o, e = record(t, data, ["--synthetic"], out="r.npz")
        eq(rc, 0, e)
        rc, o, e = cut(t, t.P("r.npz"), out="dr.npz")
        eq(rc, 0, e[-300:])
        eq(int(load(t.P("dr.npz"))["synthetic"]), 1, "recorder --synthetic -> stream -> dataset")


def test_v2_output_loads_in_train():
    import train
    sig, marks, _ = labelling_stream()
    with Tmp() as t:
        sp = write_stream_npz(t.P("S.npz"), sig, marks=marks)
        rc, o, e = cut(t, sp)
        eq(rc, 0, e[-300:])
        ds = train.load_dataset(t.P("ds.npz"))
        d = load(t.P("ds.npz"))
        eq(ds["windows"].shape, d["windows"].shape)
        arr_eq(ds["labels"], d["labels"].astype(np.int64), "train sees the labels")


def _summary_numbers(out, name):
    """Integers on the first stdout line that mentions label `name`, after the name."""
    for line in out.splitlines():
        m = re.search(r"\b%s\b(.*)" % re.escape(name), line)
        if m:
            return [int(x) for x in re.findall(r"-?\d+", m.group(1))]
    raise AssertionError("no summary line for label %s in:\n%s" % (name, out))


def test_v2_summary_counts():
    """Per label: marks, windows, marks with no window, marks with two or more windows (AMBIGUITY: the printed
    format is unspecified; the test reads the last four integers on the line that names the label)."""
    bursts = [(400, 60, (500, -300, 0)), (1000, 60, (500, -300, 0)),
              (1600, 60, (500, -300, 0)), (1800, 60, (-400, 300, 100))]
    sig = make_signal(3600, bursts, seed=17)
    trigs = ref_triggers(sig)
    eq(len(trigs), 4, "construction")
    marks = [(trigs[0], 2), (trigs[1] - 10, 3), (trigs[2], 5), (3000, 1), (3100, 2)]
    with Tmp() as t:
        sp = write_stream_npz(t.P("S.npz"), sig, marks=marks)
        rc, o, e = cut(t, sp, ["--window-after-mark", "4.0", "--none-gap", "1.0"])
        eq(rc, 0, e[-300:])
        text = o + e
        eq(_summary_numbers(text, "swipe_right")[-4:], [1, 0, 1, 0], "swipe_right: marks/windows/missed/double")
        eq(_summary_numbers(text, "swipe_left")[-4:], [2, 1, 1, 0], "swipe_left")
        eq(_summary_numbers(text, "raise")[-4:], [1, 1, 0, 0], "raise")
        eq(_summary_numbers(text, "circle_cw")[-4:], [1, 2, 0, 1], "circle_cw (double burst)")
        eq(sorted(int(x) for x in load(t.P("ds.npz"))["labels"]), [2, 3, 5, 5], "labels of the four windows")


def test_v2_selftest():
    rc, o, e = run([tool("cut_stream.py"), "--selftest"])
    eq(rc, 0, o + e)


# --------------------------------------------------------------------------- V3: fake_wand --marks-out
def _read_marks_file(path):
    """Parse the --marks-out file: npz/npy (2-column integer array, key 'marks' preferred), else text with one
    `<sample> <label>` pair per line (any separator, non-numeric header lines ignored).
    AMBIGUITY: the file format is not specified; this reader accepts the obvious ones."""
    with open(path, "rb") as f:
        head = f.read(6)
    if head[:2] == b"PK" or head[:6] == b"\x93NUMPY":
        z = np.load(path)
        a = (z["marks"] if "marks" in z.files else z[z.files[0]]) if hasattr(z, "files") else z
        return [(int(r[0]), int(r[1])) for r in np.asarray(a).reshape(-1, 2)]
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            nums = re.findall(r"-?\d+", line)
            if len(nums) >= 2 and re.match(r"^\s*-?\d+", line):
                rows.append((int(nums[0]), int(nums[1])))
    return rows


def _wand_stream(t, per_class):
    """synth dataset -> fake_wand --samples --marks-out -> recorder --samples. Returns (src, marks, stream npz)."""
    rc, o, e = run([tool("synth_dataset.py"), "--out", t.P("ds.npz"), "--per-class", str(per_class), "--seed", "3"])
    eq(rc, 0, e[-300:])
    rc, o, e = run([tool("fake_wand.py"), "--data", t.P("ds.npz"), "--out", t.P("w.bin"), "--samples",
                    "--marks-out", t.P("marks.txt")])
    eq(rc, 0, e[-300:])
    need(os.path.exists(t.P("marks.txt")), "--marks-out file written")
    rc, o, e = run([tool("recorder.py"), "--input", t.P("w.bin"), "--out", t.P("s.npz"), "--samples",
                    "--label", "none", "--no-pause", "--quiet", "--synthetic"])
    eq(rc, 0, e[-300:])
    return load(t.P("ds.npz")), _read_marks_file(t.P("marks.txt")), load(t.P("s.npz"))


def test_v3_marks_out_matches_source_windows():
    with Tmp() as t:
        src, marks, s = _wand_stream(t, 2)
        n = src["windows"].shape[0]
        flat = src["windows"].reshape(-1, 3)
        arr_eq(s["samples"], flat[:s["samples"].shape[0]], "recorded stream = concatenated source windows")
        # AMBIGUITY: rows for all N windows, or only those that fit whole inside the stream
        need(len(marks) in (n, s["samples"].shape[0] // 150), "one mark per source window (got %d of %d)" % (len(marks), n))
        eq([m[1] for m in marks], [int(x) for x in src["labels"][:len(marks)]], "labels = source labels in order")
        idx = [m[0] for m in marks]
        need(all(a < b for a, b in zip(idx, idx[1:])), "onset samples strictly increasing")
        # AMBIGUITY: "true onset sample of each source window" is 150k (start) or 150k+15 (trigger index) or so;
        # only containment in window k is enforced.
        for k, i in enumerate(idx):
            need(150 * k <= i < 150 * (k + 1), "onset %d of window %d lies inside it" % (i, k))


def test_v3_marks_out_through_cut_matches_oracle():
    """End-to-end: wand stream -> recorder --samples -> cut_stream with the TRUE marks; the result equals the oracle."""
    with Tmp() as t:
        src, marks, s = _wand_stream(t, 3)
        rs = [int(x) for x in s["chunk_gaps"][:, 0]] + [int(x) for x in s["ovr"]]
        sp = write_stream_npz(t.P("S.npz"), s["samples"], gaps=s["chunk_gaps"], ovr=s["ovr"], marks=marks, synthetic=1)
        rc, o, e = cut(t, sp, out="cut.npz")
        eq(rc, 0, e[-300:])
        d = load(t.P("cut.npz"))
        ts, ls, ws = oracle_cut(s["samples"], marks, rs, 2.0, 1.0)
        arr_eq(d["trig_sample"], np.array(ts, np.int32), "cut_stream agrees with the oracle on the wand stream")
        arr_eq(d["labels"], np.array(ls, np.uint8))
        eq(int(d["synthetic"]), 1)


TESTS = [v for k, v in sorted(globals().items())
         if k.startswith("test_") and callable(v)]
TESTS.sort(key=lambda f: f.__code__.co_firstlineno)


# --------------------------------------------------------------------------- runner
def main(argv):
    """Run all tests (or those whose name contains an argument); returns the exit code."""
    sel = argv[1:]
    fails = 0
    for fn in TESTS:
        if sel and not any(s in fn.__name__ for s in sel):
            continue
        try:
            fn()
        except Exception as ex:  # noqa: BLE001 - report every failure kind
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
