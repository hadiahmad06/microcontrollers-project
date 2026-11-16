#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""Fake wand: turns a training dataset into the C2 byte stream a wand would send (test and demo source).

WORKING ASSUMPTION: open_questions Q1 (C2 as proposed), not decided.
SYNTHETIC output, never real data. Encoders come from tools/c2_proto.py (promoted from the spike
docs/agent/hadi/spikes/uart/c2_ref.py).

Usage:
  python3 tools/fake_wand.py --data DS.npz (--out FILE | --pty) [--order as-is|grouped] [--hello-every K]
        [--text "LINE"] [--corrupt P] [--seed S] [--print-plan] [--rate BPS] [--samples]
  python3 tools/fake_wand.py --selftest
"""
import argparse
import os
import random
import sys
import tempfile
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c2_proto  # noqa: E402
from gesture_labels import LABELS  # noqa: E402


def plan_string(labels):
    """Run-length encode a label sequence as a recorder --plan string.

    Args:
        labels: sequence of int class ids in stream order.
    Returns:
        e.g. "none:30,swipe_right:30" (consecutive equal labels merged).
    """
    runs = []
    for lab in labels:
        if runs and runs[-1][0] == int(lab):
            runs[-1][1] += 1
        else:
            runs.append([int(lab), 1])
    return ",".join("%s:%d" % (LABELS[a], n) for a, n in runs)


def build_stream(windows, labels, order="as-is", hello_every=2, text=(), corrupt=0.0, seed=1, samples=False):
    """Build the byte stream of a wand that sends the given windows.

    Args:
        windows: int array [N,150,3]. labels: int array [N]. order: "as-is" or "grouped" (stable sort by label).
        hello_every: a HELLO after every K windows (SAMPLES chunks in bring-up mode); 0 = only the first.
        text: iterable of ASCII lines sent first. corrupt: probability that a WINDOW frame has one bit flipped.
        seed: RNG seed for the corruption. samples: bring-up mode (SAMPLES chunks of 16 instead of WINDOWs).
    Returns:
        (bytes, info) where info has n, corrupted, order_labels (list) and plan (str).
    """
    labels = np.asarray(labels)
    idx = np.argsort(labels, kind="stable") if order == "grouped" else np.arange(len(labels))
    rng = random.Random(seed)
    out = bytearray()
    for line in text:
        out += line.encode("ascii") + b"\n"
    seq = [0]

    def nxt():
        s = seq[0]
        seq[0] += 1
        return s

    out += c2_proto.encode_hello(nxt())
    corrupted = 0
    if samples:
        stream = np.concatenate([np.asarray(windows[i]) for i in idx]) if len(idx) else np.zeros((0, 3), np.int16)
        for c in range(len(stream) // 16):
            out += c2_proto.encode_samples(nxt(), c, stream[c * 16:(c + 1) * 16])
            if hello_every and (c + 1) % hello_every == 0:
                out += c2_proto.encode_hello(nxt())
    else:
        for k, i in enumerate(idx):
            fb = bytearray(c2_proto.encode_window(nxt(), k, windows[i]))
            if corrupt > 0 and rng.random() < corrupt:
                fb[6 + rng.randrange(c2_proto.LEN_WINDOW)] ^= 1 << rng.randrange(8)   # one flipped payload bit
                corrupted += 1
            out += fb
            if hello_every and (k + 1) % hello_every == 0:
                out += c2_proto.encode_hello(nxt())
    order_labels = [int(labels[i]) for i in idx]
    return bytes(out), {"n": len(idx), "corrupted": corrupted, "order_labels": order_labels,
                        "plan": plan_string(order_labels)}


def load(path):
    """Load a training-format dataset; returns (windows int16 [N,150,3], labels). Raises SystemExit(2) on error."""
    try:
        z = np.load(path)
        w, y = z["windows"], z["labels"]
    except (OSError, ValueError, KeyError) as e:
        print("error: cannot read dataset %s: %s" % (path, e), file=sys.stderr)
        sys.exit(2)
    if w.ndim != 3 or w.shape[1:] != (150, 3) or len(w) != len(y):
        print("error: %s: windows must be [N,150,3] with N labels" % path, file=sys.stderr)
        sys.exit(2)
    return w, y


def pty_send(data, rate):
    """Serve data on a new pseudo-terminal: print the slave path, wait 1 s, write at rate B/s, drain 1 s.

    Args:
        data: bytes. rate: bytes per second (chunks of at most 256 B).
    """
    import tty
    master, slave = os.openpty()
    tty.setraw(slave)                      # raw: no echo, no CR/LF translation, 8 bits
    print(os.ttyname(slave), flush=True)
    time.sleep(1.0)                        # fixed delay for the reader to open the slave
    t0 = time.monotonic()
    sent = 0
    while sent < len(data):
        chunk = data[sent:sent + 256]
        os.write(master, chunk)
        sent += len(chunk)
        wait = t0 + sent / float(rate) - time.monotonic()
        if wait > 0:
            time.sleep(wait)
    time.sleep(1.0)                        # let the reader drain
    os.close(master)
    os.close(slave)


def _selftest():
    """Check the generated stream with the decoder; returns failure strings."""
    fails = []

    def check(c, msg):
        if not c:
            fails.append(msg)

    rng = np.random.default_rng(2)
    n = 40
    w = rng.integers(-2048, 2048, size=(n, 150, 3)).astype(np.int16)
    y = (rng.integers(0, 3, size=n)).astype(np.uint8)
    data, info = build_stream(w, y, order="grouped", text=["GM_MODEL_HASH=0"])
    d = c2_proto.Decoder()
    fr = d.feed(data)
    wf = [c2_proto.parse_window(f.payload) for f in fr if f.ftype == c2_proto.T_WINDOW]
    srt = np.argsort(y, kind="stable")
    check(len(wf) == n and all(p["window_id"] == k for k, p in enumerate(wf)), "window ids")
    check(all(np.array_equal(np.array(p["samples"]), w[srt[k]]) for k, p in enumerate(wf)), "grouped windows")
    nh = sum(1 for f in fr if f.ftype == c2_proto.T_HELLO)
    check(nh == 1 + n // 2, "hello count %d" % nh)
    check(d.text_lines == ["GM_MODEL_HASH=0"] and d.seq_gaps == 0 and d.crc_errors == 0, "text/seq/crc")
    check(info["plan"] == plan_string(np.sort(y)) and info["plan"].startswith("none:"), "plan %s" % info["plan"])
    check(plan_string([1, 1, 0]) == "swipe_right:2,none:1", "plan rle")
    data, info = build_stream(w, y, corrupt=0.25, seed=7)
    d = c2_proto.Decoder()
    fr = d.feed(data)
    nw = sum(1 for f in fr if f.ftype == c2_proto.T_WINDOW)
    check(0 < info["corrupted"] < n and nw == n - info["corrupted"] and d.crc_errors == info["corrupted"],
          "corrupt %d windows %d crc %d" % (info["corrupted"], nw, d.crc_errors))
    data, info = build_stream(w, y, samples=True, hello_every=4)
    d = c2_proto.Decoder(accept_samples=True)
    fr = d.feed(data)
    ch = [c2_proto.parse_samples(f.payload) for f in fr if f.ftype == c2_proto.T_SAMPLES]
    flat = w.reshape(-1, 3)
    check(len(ch) == len(flat) // 16 and [c["chunk"] for c in ch] == list(range(len(ch))), "chunks")
    check(all(np.array_equal(np.array(c["samples"]), flat[16 * k:16 * k + 16]) for k, c in enumerate(ch)), "chunk data")
    # CLI: --out
    with tempfile.TemporaryDirectory() as t:
        ds, op = os.path.join(t, "d.npz"), os.path.join(t, "s.bin")
        np.savez(ds, windows=w, labels=y)
        rc = main(["--data", ds, "--out", op, "--order", "grouped"])
        check(rc == 0 and open(op, "rb").read(), "cli --out")
    return fails


def main(argv=None):
    """CLI entry point. Returns the exit code."""
    ap = argparse.ArgumentParser(description="Emit the C2 stream of a fake wand from a dataset")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--data")
    ap.add_argument("--out")
    ap.add_argument("--pty", action="store_true")
    ap.add_argument("--order", choices=("as-is", "grouped"), default="as-is")
    ap.add_argument("--hello-every", type=int, default=2)
    ap.add_argument("--text", action="append", default=[])
    ap.add_argument("--corrupt", type=float, default=None)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--print-plan", action="store_true")
    ap.add_argument("--rate", type=int, default=11520)
    ap.add_argument("--samples", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        fails = _selftest()
        if fails:
            print("fake_wand selftest FAIL: " + "; ".join(fails))
            return 1
        print("fake_wand selftest PASS")
        return 0
    if not a.data or bool(a.out) == bool(a.pty):
        print("error: need --data and exactly one of --out / --pty", file=sys.stderr)
        return 2
    corrupt_given = a.corrupt is not None
    if a.corrupt is None:
        a.corrupt = 0.0
    if not 0.0 <= a.corrupt <= 1.0 or a.rate < 1 or a.hello_every < 0:
        print("error: --corrupt must be 0..1, --rate >= 1, --hello-every >= 0", file=sys.stderr)
        return 2
    w, y = load(a.data)
    data, info = build_stream(w, y, a.order, a.hello_every, a.text, a.corrupt, a.seed, a.samples)
    print("SYNTHETIC: fake_wand output, never real data", file=sys.stderr)
    if corrupt_given:  # spec S3: report the count whenever --corrupt is given (W2-4T fw_corrupt)
        print("corrupted %d of %d WINDOW frames" % (info["corrupted"], info["n"]), file=sys.stderr)
    if a.print_plan:                       # last stderr line, so `tail -1` yields the plan
        print(info["plan"], file=sys.stderr)
    if a.out:
        with open(a.out, "wb") as f:
            f.write(data)
    else:
        pty_send(data, a.rate)
    return 0


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
