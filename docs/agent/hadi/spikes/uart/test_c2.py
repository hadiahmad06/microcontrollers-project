# [AI-GENERATED: Claude Code]
"""Test for the C2 framing spike: CRC check value, C vs Python byte-exact encoding, decoder resync.

Usage: python3 test_c2.py <path to build/c2_cli>
Prints PASS/FAIL lines and a final "ALL PASS" (exit code 0), else exits 1.
"""
import random
import subprocess
import sys

import c2_ref as c2

FAILS = []


def check(name, ok, detail=""):
    """Print one PASS/FAIL line and remember failures.

    Args:
        name: test name.
        ok: truthy if the test passed.
        detail: extra text shown on failure.
    """
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else "  " + detail))
    if not ok:
        FAILS.append(name)


def rand_meta(rng, wid):
    """Random window metadata covering the full range of every field.

    Args:
        rng: random.Random instance.
        wid: window id to use.
    Returns:
        dict of metadata fields.
    """
    return {"window_id": wid, "trig_idx": rng.choice([0, 15, 30, 149, 255]),
            "overruns": rng.randrange(65536), "model_hash": rng.choice([0, 0xFFFFFFFF, rng.getrandbits(32)]),
            "flags": rng.choice([0, 1]), "class_id": rng.randrange(-1, 13),
            "conf": rng.randrange(256), "events": rng.choice([0, 1, 0xFF])}


def rand_samples(rng, mode):
    """150x3 int16 samples.

    Args:
        rng: random.Random instance.
        mode: "rand" (12-bit range), "min", "max", or "full" (whole int16 range).
    Returns:
        list of 150 (x, y, z) tuples.
    """
    if mode == "min":
        return [(-2048, -2048, -2048)] * c2.N_SAMPLES
    if mode == "max":
        return [(2047, 2047, 2047)] * c2.N_SAMPLES
    lo, hi = (-32768, 32767) if mode == "full" else (-2048, 2047)
    return [tuple(rng.randint(lo, hi) for _ in range(3)) for _ in range(c2.N_SAMPLES)]


def c_record(seq, meta, samples):
    """Text record for the C driver (see c2_cli.c).

    Args:
        seq: sequence number.
        meta: metadata dict.
        samples: sample rows.
    Returns:
        One text line.
    """
    head = "W %d %d %d %d %d %d %d %d %d" % (seq, meta["window_id"], meta["trig_idx"], meta["overruns"],
                                            meta["model_hash"], meta["flags"], meta["class_id"],
                                            meta["conf"], meta["events"])
    return head + " " + " ".join(str(v) for row in samples for v in row) + "\n"


def main():
    """Run all tests.

    Returns:
        Process exit code.
    """
    cli = sys.argv[1]
    rng = random.Random(2361)

    # 1. CRC check value, Python and C, plus nibble-table C vs bitwise Python on random strings.
    check("crc16 python check value 0x29B1", c2.crc16(b"123456789") == 0x29B1)
    r = subprocess.run([cli, "crc", "123456789"], capture_output=True, text=True)
    check("crc16 C check value 0x29B1 (and split update equal)", r.returncode == 0 and r.stdout.strip() == "29B1",
          repr((r.returncode, r.stdout)))
    bad = 0
    for n in list(range(0, 40)) + [127, 255, 300]:
        s = "".join(chr(rng.randrange(33, 127)) for _ in range(n))
        r = subprocess.run([cli, "crc", s], capture_output=True, text=True)
        if r.returncode != 0 or int(r.stdout.strip(), 16) != c2.crc16(s.encode("ascii")):
            bad += 1
    check("crc16 C (nibble table) == Python (bitwise) on 43 random strings", bad == 0, "%d mismatches" % bad)

    # 2. C and Python encoders give identical bytes.
    hello = {"proto_ver": 1, "odr_hz": 100, "range_g": 4, "n_samples": 150, "pre_trig": 15,
             "feature_ver": 1, "model_hash": 0x1A2B3C4D}
    seqs, recs, py_frames, metas, smps = [], [], [], [], []
    recs.append("H 249 1 100 4 150 15 1 %d\n" % hello["model_hash"])
    py_frames.append(c2.encode_hello(249, hello))
    modes = ["min", "max", "full"] + ["rand"] * 37
    for i, mode in enumerate(modes):
        meta, smp = rand_meta(rng, i), rand_samples(rng, mode)
        seq = (250 + i) & 0xFF            # crosses the 255 -> 0 wrap
        recs.append(c_record(seq, meta, smp))
        py_frames.append(c2.encode_window(seq, meta, smp))
        metas.append(meta)
        smps.append(smp)
    r = subprocess.run([cli, "encode"], input="".join(recs).encode(), capture_output=True)
    c_bytes = r.stdout
    py_bytes = b"".join(py_frames)
    check("C encoder exit code 0", r.returncode == 0, repr(r.stderr))
    check("frame sizes: HELLO 18 B, WINDOW 922 B", len(py_frames[0]) == 18 and all(len(f) == 922 for f in py_frames[1:]))
    check("C bytes == Python bytes (1 HELLO + 40 WINDOW frames incl. min/max/full-int16)", c_bytes == py_bytes,
          "len C=%d py=%d" % (len(c_bytes), len(py_bytes)))

    # 3. Clean decode round trip, fed one byte at a time.
    dec = c2.Decoder()
    got = []
    for b in py_bytes:
        got.extend(dec.feed(bytes([b])))
    ok = len(got) == 41 and dec.crc_errors == 0 and dec.garbage == 0 and dec.seq_gaps == 0
    for (ftype, seq, payload), meta, smp in zip(got[1:], metas, smps):
        p = c2.parse_payload(ftype, payload)
        ok = ok and p["samples"] == smp and all(p[k] == meta[k] for k in meta) and p["n_samples"] == 150
    ok = ok and c2.parse_payload(got[0][0], got[0][2]) == hello
    check("decoder: 41 clean frames round-trip bit-exactly, no errors (one byte at a time)", ok,
          "frames=%d crc=%d garbage=%d gaps=%d" % (dec.frames, dec.crc_errors, dec.garbage, dec.seq_gaps))

    # 4. Directed damage. Frames: A..F; expected survivors are marked.
    def frame(i):
        return c2.encode_window(i, rand_meta(rng, i), rand_samples(rng, "rand"))
    F = [frame(i) for i in range(8)]
    fake_sync = bytes([0xA5, 0x5A, 0x02, 0x92, 0x03, 0x00])           # plausible WINDOW header, no real frame
    flipped = bytearray(F[3]); flipped[400] ^= 0x10                    # one flipped bit in the samples
    dropped = bytearray(F[4]); del dropped[500]                        # one byte lost
    hdr_hit = bytearray(F[5]); hdr_hit[3] ^= 0x01                      # LEN damaged (914 -> 915)
    trunc = F[6][:300]                                                 # transmitter reset mid-frame
    stream = (bytes([0x00, 0xFF, 0xA5, 0xA5, 0x5A, 0x13]) + F[0]       # garbage incl. a lone sync lookalike
              + fake_sync + bytes(rng.randrange(256) for _ in range(40)) + F[1]
              + F[2] + bytes(flipped) + bytes(dropped) + bytes(hdr_hit) + trunc + F[7])
    dec = c2.Decoder()
    got = dec.feed(stream)
    want = [F[0], F[1], F[2], F[7]]
    rebuilt = [c2._frame(t, s, p) for (t, s, p) in got]
    check("decoder resync: directed damage keeps exactly the 4 intact frames, in order", rebuilt == want,
          "got seqs %s" % [s for (_, s, _) in got])
    check("decoder rejects: flipped bit and dropped byte counted as CRC errors, LEN hit as bad header",
          dec.crc_errors >= 2 and dec.bad_header >= 1,
          "crc=%d bad_header=%d" % (dec.crc_errors, dec.bad_header))
    check("decoder: SEQ gap counter sees the 4 lost frames (seq 3,4,5,6)",
          dec.seq_gaps == 4, "seq_gaps=%d" % dec.seq_gaps)

    # 5. Fuzz: random damage over many streams. No false accepts; every intact frame recovered.
    false_accepts = missed = streams = 0
    for seed in range(40):
        r2 = random.Random(1000 + seed)
        pieces, expect = [], []
        for i in range(12):
            f = bytes(c2.encode_window(i, rand_meta(r2, i), rand_samples(r2, "rand"))) if r2.random() < 0.7 \
                else c2.encode_hello(i, hello)
            kind = r2.choice(["ok", "ok", "flip", "drop", "garbage_before", "dup_sync"])
            fb = bytearray(f)
            if kind == "flip":
                fb[r2.randrange(2, len(fb))] ^= 1 << r2.randrange(8)
            elif kind == "drop":
                del fb[r2.randrange(len(fb))]
            elif kind == "garbage_before":
                pieces.append(bytes(r2.randrange(256) for _ in range(r2.randrange(1, 60))))
            elif kind == "dup_sync":
                pieces.append(bytes([0xA5, 0x5A]) * r2.randrange(1, 4))
            pieces.append(bytes(fb))
            if kind in ("ok", "garbage_before", "dup_sync"):
                expect.append(f)
        trailer = c2.encode_window(99, rand_meta(r2, 99), rand_samples(r2, "rand")) * 2
        pieces.append(trailer)       # longer than any false candidate can wait for, so it flushes one
        expect.extend([trailer[:922], trailer[922:]])
        d = c2.Decoder()
        out = [c2._frame(t, s, p) for (t, s, p) in d.feed(b"".join(pieces))]
        streams += 1
        if any(o not in expect for o in out):
            false_accepts += 1
        if out != expect:
            missed += 1
    check("fuzz: 40 damaged streams, no false accept", false_accepts == 0, "%d streams" % false_accepts)
    check("fuzz: 40 damaged streams, every intact frame recovered in order", missed == 0, "%d streams differ" % missed)

    print("ALL PASS" if not FAILS else "FAILED: " + ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
