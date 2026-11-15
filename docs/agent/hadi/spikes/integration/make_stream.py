# [AI-GENERATED: Claude Code]
"""SPIKE S3-1: build CONTINUOUS synthetic recordings from tools/synth_dataset.py gesture windows.

THROWAWAY, SYNTHETIC, UNVERIFIED. Every shape, amplitude and gap length is an invented guess; the
numbers this stream produces say nothing about the real wand.

A stream is int16 wand-frame samples at 100 Hz: idle segments (hold, optional bump or tremor, slow
tilt to the next start pose) between synthetic gesture windows. Each gesture window comes from
synth_dataset.make_window (150 samples, onset near sample 15) and is placed unmodified (or, in
"tight" mode, rigidly rotated so its start pose equals the current pose). The true onset of each
gesture is re-derived by mirroring the first draws of make_window (gmag, noise, onset, dur); this
mirrors an internal of synth_dataset.py and is checked by an assertion on the draw order.

Outputs per stream NAME in the output directory:
  NAME.npy   int16 [N,3]
  NAME.json  ground truth: gestures [{onset,label,end,window_start}], events [{type,start,end}],
             learn plan [{onset,label,class_id}], stalls [{at,len}], classify_busy
  NAME.h     C header for glue.c (stream in PROGMEM on AVR, learn plan, stalls)
"""
import argparse
import copy
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "..", "..", "tools"))
sys.path.insert(0, os.path.join(HERE, "..", "trigger"))
import synth_dataset as S  # noqa: E402
import trigger_ref  # noqa: E402

LEARN_BASE = 9   # GESTURE_LEARNED_BASE


def _unit(v):
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def _rot_between(a, b):
    """Rotation matrix taking direction a to direction b. Args: a, b (3-vectors). Returns: 3x3."""
    a, b = _unit(a), _unit(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    s = float(np.linalg.norm(v))
    if s < 1e-9:
        return np.eye(3)
    k = v / s
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + s * K + (1 - c) * (K @ K)


def _tilt(p0, p1, span):
    """Smooth pose change p0 -> p1 over span samples (direction slerp, magnitude linear).

    Args: p0, p1 (3-vectors, counts); span (int samples). Returns: ndarray [span,3] (float).
    """
    u = (np.arange(span) + 1.0) / span
    sm = u * u * (3.0 - 2.0 * u)
    R = _rot_between(p0, p1)
    ang = math.acos(max(-1.0, min(1.0, float(np.dot(_unit(p0), _unit(p1))))))
    # full rotation R scaled by sm: rotate p0 about the axis by sm*ang
    axis = np.cross(p0, p1)
    axis = _unit(axis) if np.linalg.norm(axis) > 1e-9 else np.array([0.0, 0.0, 1.0])
    out = np.zeros((span, 3))
    m0, m1 = float(np.linalg.norm(p0)), float(np.linalg.norm(p1))
    d0 = _unit(p0)
    for i in range(span):
        a = sm[i] * ang
        c, s = math.cos(a), math.sin(a)
        d = d0 * c + np.cross(axis, d0) * s + axis * np.dot(axis, d0) * (1 - c)
        out[i] = d * (m0 + (m1 - m0) * sm[i])
    return out, ang, R


def _mirror(cls, rng):
    """Mirror the first draws of synth_dataset.make_window to learn onset and duration.

    Args: cls (int 1..8); rng (Generator, NOT advanced). Returns: (onset, dur, noise).
    """
    r = copy.deepcopy(rng)
    r.uniform(490.0, 530.0)             # gmag
    noise = float(r.uniform(2.0, 6.0))  # noise
    onset = 15 + int(r.integers(-3, 4))
    dur = int(r.integers(30, 101))
    return onset, dur, noise


def build(seed, classes, reps, hold_range, tight, n_extra_bumps=True, lead=250, tail=250):
    """Build one stream. Args: seed (int); classes (list of labels 1..8); reps (int per class);
    hold_range ((lo,hi) samples of idle hold); tight (bool, rotate instead of tilt);
    Returns: (samples int16 [N,3], gt dict)."""
    rng = np.random.default_rng(seed)
    order = [c for c in classes for _ in range(reps)]
    rng.shuffle(order)
    parts = []
    events, gestures = [], []
    pos = [0]

    def add(arr):
        parts.append(arr)
        pos[0] += len(arr)

    pose = None
    for gi, c in enumerate(order):
        # draw the window first (its draws define the start pose)
        onset_w, dur_w, noise_w = _mirror(c, rng)
        w = S.make_window(c, rng).astype(np.float64)
        ps = w[:10].mean(axis=0)
        pe = w[-10:].mean(axis=0)
        nz = noise_w
        if pose is None:
            pose = ps
            hold = lead
        else:
            hold = int(rng.integers(hold_range[0], hold_range[1] + 1))
        # hold with optional tremor or bump
        h = pose[None, :] + rng.normal(0.0, nz, (hold, 3))
        if gi > 0 and not tight and rng.uniform() < 0.2 and hold >= 100:
            tr = rng.uniform(5.0, 14.0)
            fq = rng.uniform(8.0, 12.0)
            ph = rng.uniform(0, 2 * math.pi, 3)
            t = np.arange(hold)
            h += (tr / 2.0) * np.sin(2 * math.pi * fq * t[:, None] / 100.0 + ph[None, :])
            events.append({"type": "tremor", "start": pos[0], "end": pos[0] + hold})
        elif gi > 0 and n_extra_bumps and hold >= 100 and rng.uniform() < 0.5:
            k = int(rng.integers(35, hold - 20))
            h[k, int(rng.integers(0, 3))] += rng.choice([-1, 1]) * rng.uniform(150, 400)
            events.append({"type": "bump", "start": pos[0] + k, "end": pos[0] + k + 1})
        add(h)
        if tight:
            if gi > 0:
                R = _rot_between(ps, pose)
                w = (w @ R.T) * (float(np.linalg.norm(pose)) / float(np.linalg.norm(ps)))
        else:
            ang = math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(_unit(pose), _unit(ps)))))))
            if ang > 3.0:
                span = int(min(500, max(150, ang * 4)))
                tl, _, _ = _tilt(pose, ps, span)
                tl += rng.normal(0.0, nz, tl.shape)
                if ang >= 20.0:
                    events.append({"type": "tilt", "start": pos[0], "end": pos[0] + span})
                add(tl)
        w0 = pos[0]
        add(w)
        gestures.append({"onset": w0 + onset_w, "label": int(c), "end": w0 + onset_w + dur_w,
                         "window_start": w0})
        pose = w[-10:].mean(axis=0)
    add(pose[None, :] + rng.normal(0.0, 3.0, (tail, 3)))
    x = np.clip(np.rint(np.concatenate(parts)), -2048, 2047).astype(np.int16)
    # learn plan: the first DETECTED occurrence (offline trigger, release 135 after t) of each of the first
    # two distinct labels of the stream, so a missed first gesture does not leave a class without template
    offs, _ = trigger_ref.run([tuple(int(v) for v in r) for r in x], None, 250, 135)
    learn, seen = [], []
    for g in gestures:
        det = any(g["onset"] - 5 <= t <= g["onset"] + 40 for t in offs)
        if g["label"] not in seen and len(seen) < 2 and det:
            seen.append(g["label"])
            learn.append({"onset": g["onset"], "label": g["label"], "class_id": LEARN_BASE + len(learn)})
    return x, {"gestures": gestures, "events": events, "learn": learn, "stalls": [], "classify_busy": 0,
               "n": int(len(x)), "seed": seed, "tight": tight}


def check_mirror(seed=7):
    """Assert that the mirrored onset equals the actual onset of the generated window.

    A window's first 10 samples must stay at rest and the motion must start near the mirrored
    onset; the check compares the mean absolute first difference before and after it.
    """
    rng = np.random.default_rng(seed)
    bad = 0
    for c in range(1, 9):
        for _ in range(20):
            on, du, nz = _mirror(c, rng)
            w = S.make_window(c, rng).astype(np.float64)
            pre = np.abs(np.diff(w[:max(on - 2, 5)], axis=0)).sum(axis=1).mean()
            post = np.abs(np.diff(w[on:on + 15], axis=0)).sum(axis=1).mean()
            if not (12 <= on <= 18) or post < pre * 0.9:
                bad += 1
    assert bad <= 8, "onset mirror of synth_dataset.make_window looks wrong (%d bad)" % bad


def write_header(path, name, x, gt):
    """Write the C header for glue.c. Args: path; name (str); x (int16 [N,3]); gt (dict)."""
    L = ["/* %s: SYNTHETIC, UNVERIFIED, generated by make_stream.py; do not edit. */" % name,
         "#ifdef __AVR__",
         "#include <avr/pgmspace.h>",
         "#define STREAM_PROGMEM PROGMEM",
         "#else",
         "#define STREAM_PROGMEM",
         "#endif",
         "#define STREAM_N %dUL" % len(x),
         "static const int16_t stream_data[STREAM_N][3] STREAM_PROGMEM = {"]
    row = []
    for i, r in enumerate(x):
        row.append("{%d,%d,%d}" % (r[0], r[1], r[2]))
        if len(row) == 10:
            L.append(",".join(row) + ",")
            row = []
    if row:
        L.append(",".join(row))
    L.append("};")
    ln = gt["learn"]
    L.append("#define LEARN_N %du" % len(ln))
    L.append("static const uint32_t learn_onset[%d] = {%s};" % (max(1, len(ln)), ",".join("%dUL" % g["onset"] for g in ln) or "0UL"))
    L.append("static const uint8_t learn_id[%d] = {%s};" % (max(1, len(ln)), ",".join("%du" % g["class_id"] for g in ln) or "0u"))
    st = gt["stalls"]
    L.append("#define STALL_N %du" % len(st))
    L.append("static const uint32_t stall_at[%d] = {%s};" % (max(1, len(st)), ",".join("%dUL" % s["at"] for s in st) or "0UL"))
    L.append("static const uint16_t stall_len[%d] = {%s};" % (max(1, len(st)), ",".join("%du" % s["len"] for s in st) or "0u"))
    L.append("#define CLASSIFY_BUSY %du" % gt["classify_busy"])
    open(path, "w").write("\n".join(L) + "\n")


def emit(outdir, name, x, gt):
    """Write NAME.npy, NAME.json, NAME.h. Args: outdir; name; x; gt. Returns: None."""
    np.save(os.path.join(outdir, name + ".npy"), x)
    json.dump(gt, open(os.path.join(outdir, name + ".json"), "w"), indent=1)
    write_header(os.path.join(outdir, name + ".h"), name, x, gt)
    print("stream %-6s N=%6d (%.0f s) gestures=%d events=%d learn=%s stalls=%d  SYNTHETIC, UNVERIFIED"
          % (name, len(x), len(x) / 100.0, len(gt["gestures"]), len(gt["events"]),
             [(g["label"], g["class_id"]) for g in gt["learn"]], len(gt["stalls"])))


def main(argv=None):
    """CLI: make_stream.py --out DIR. Writes the streams main, big, tight, stall, short."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    check_mirror()
    allc = list(range(1, 9))
    # main: 1-4 s idle holds, 8 classes x 6 reps
    x, gt = build(101, allc, 6, (100, 400), False)
    emit(a.out, "main", x, gt)
    # big: main-style, 8 classes x 20 reps, for per-class statistics (host only)
    x, gt = build(105, allc, 20, (100, 400), False)
    emit(a.out, "big", x, gt)
    # tight: 0.2-0.6 s holds, no tilts (windows rotated to the current pose): stresses the lock
    x, gt = build(103, allc, 4, (20, 60), True)
    emit(a.out, "tight", x, gt)
    # stall: main-style stream with the main loop stalled 45 samples at chosen places
    x, gt = build(104, allc, 3, (100, 400), False)
    g = gt["gestures"]
    gt["stalls"] = [{"at": g[1]["onset"] - 120, "len": 45},       # idle, before gesture 1
                    {"at": g[3]["onset"] + 50, "len": 45},        # inside an open window
                    {"at": g[5]["onset"] + 118, "len": 45}]       # near the end of a window
    gt["classify_busy"] = 40                                      # main loop busy 40 samples per classify
    emit(a.out, "stall", x, gt)
    # short: for sim16 (avr object limit 32 KB), 4 classes x 2 reps
    x, gt = build(102, [1, 2, 3, 4], 2, (100, 400), False)
    assert len(x) <= 5400, "avr-gcc objects are limited to 32 KB: shorten the sim16 stream"
    emit(a.out, "short", x, gt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
