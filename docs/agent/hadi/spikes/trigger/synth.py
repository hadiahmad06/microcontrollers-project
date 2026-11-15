# [AI-GENERATED: Claude Code]
"""Synthetic accelerometer streams for the trigger spike (ticket S2-2).

UNVERIFIED: every shape and amplitude below is a guess of mine, NOT a real recording.
Replace by real WP2 recordings before trusting any rate in the proposal table.

Units: int counts, 100 Hz, wand frame (X out of the tip, Y left, Z up), 1 g about 500..512.
Floats are used to generate, every sample is rounded to int and clipped to [-2048, 2047]
before anything else sees it. All streams are N = 500 samples (5 s). Event onset is at a
random sample in 150..250 (so the 32-sample warm-up has long passed).

Scenarios (kind -> shape):
  rest    : gravity along a random direction (|g| = 500..512) + uniform noise +-2.
  tilt    : rest, then the gravity vector rotates by 60..120 deg about a random axis over
            200 samples (2 s, smoothstep) = wrist turning over slowly; noise +-3.
  tremor  : rest + uniform noise +-A (A = 5..15) + a 8..12 Hz sine of amplitude A/2 per axis.
  bump    : rest + ONE sample spike of +-300 counts on one random axis (table bump).
  swipe_r : accel on Y = +A sin(2 pi u), u = t/D (push then brake), D = 30..100 samples,
  swipe_l : same with the sign flipped.                    A = 200..1500 counts
  raise   : tip pitches up by 40..80 deg (gravity rotates about Y, smoothstep over D) plus
            a Z accel pulse 0.5 A sin(2 pi u).
  circle  : ax = A sin(2 pi u) h(u), ay = A cos(2 pi u) h(u), h = sin^2(pi u) (Hann envelope).
  twist   : wrist rolls 60..120 deg about X (smoothstep over D), accel = 0.2 A noise-like
            sine on Y so it is not perfectly clean.
  thrust  : ax = +A sin(pi u3) for the first third (u3 = 3u), then -0.5 A sin(pi u3') braking
            for the rest; D = 30..60.
Gesture streams start from a wand held roughly level (gravity tilted <= 30 deg from +Z),
with uniform noise +-5 (tremor level) added all the time.
"""
import math
import random

N = 500
G_KINDS = ["swipe_r", "swipe_l", "raise", "circle", "twist", "thrust"]
NG_KINDS = ["rest", "tilt", "tremor", "bump"]
KINDS = NG_KINDS + G_KINDS


def _clip(v):
    """Round to int and clip to the 12-bit range [-2048, 2047]."""
    return max(-2048, min(2047, int(round(v))))


def _unit(rng):
    """Random unit vector (uniform on the sphere)."""
    z = rng.uniform(-1.0, 1.0)
    a = rng.uniform(0.0, 2.0 * math.pi)
    r = math.sqrt(1.0 - z * z)
    return [r * math.cos(a), r * math.sin(a), z]


def _rot(v, axis, ang):
    """Rotate vector v about unit axis by ang radians (Rodrigues)."""
    c, s = math.cos(ang), math.sin(ang)
    d = sum(a * b for a, b in zip(axis, v))
    cr = [axis[1] * v[2] - axis[2] * v[1], axis[2] * v[0] - axis[0] * v[2],
          axis[0] * v[1] - axis[1] * v[0]]
    return [v[i] * c + cr[i] * s + axis[i] * d * (1.0 - c) for i in range(3)]


def _smooth(u):
    """Smoothstep 0..1."""
    u = max(0.0, min(1.0, u))
    return u * u * (3.0 - 2.0 * u)


def make_stream(kind, seed):
    """Generate one synthetic stream.

    Args:
        kind: one of KINDS.
        seed: integer seed (deterministic output).
    Returns:
        (samples, meta): samples = list of N (x, y, z) int tuples; meta = dict with keys
        kind, onset (first sample of the event, or None), dur (event length, or None).
    """
    rng = random.Random(seed * 7919 + KINDS.index(kind))
    gmag = rng.uniform(500.0, 512.0)
    onset = rng.randint(150, 250)
    dur = None
    amp = 0.0
    noise = 2.0
    if kind in G_KINDS:
        tilt = math.radians(rng.uniform(0.0, 30.0))
        az = rng.uniform(0.0, 2.0 * math.pi)
        g0 = [math.sin(tilt) * math.cos(az), math.sin(tilt) * math.sin(az), math.cos(tilt)]
        noise = 5.0
        amp = rng.uniform(200.0, 1500.0)
        dur = rng.randint(30, 100)
        if kind == "thrust":
            dur = rng.randint(30, 60)
    else:
        g0 = _unit(rng)
    if kind == "tilt":
        noise = 3.0
        tilt_axis = _unit(rng)
        # make the axis perpendicular to gravity
        d = sum(a * b for a, b in zip(tilt_axis, g0))
        tilt_axis = [tilt_axis[i] - d * g0[i] for i in range(3)]
        n = math.sqrt(sum(a * a for a in tilt_axis)) or 1.0
        tilt_axis = [a / n for a in tilt_axis]
        tilt_ang = math.radians(rng.uniform(60.0, 120.0))
        onset = rng.randint(100, 200)
        dur = 200
    if kind == "tremor":
        noise = rng.uniform(5.0, 15.0)
        fq = rng.uniform(8.0, 12.0)
        ph = [rng.uniform(0, 2 * math.pi) for _ in range(3)]
    if kind == "bump":
        bump_axis = rng.randint(0, 2)
        bump_sign = rng.choice([-1, 1])
    roll = math.radians(rng.uniform(60.0, 120.0))
    pitch = math.radians(rng.uniform(40.0, 80.0))
    out = []
    for n_i in range(N):
        g = list(g0)
        acc = [0.0, 0.0, 0.0]
        u = (n_i - onset) / dur if dur else 0.0
        inside = dur is not None and 0 <= n_i - onset < dur
        if kind == "tilt":
            g = _rot(g0, tilt_axis, tilt_ang * _smooth((n_i - onset) / dur))
        elif kind == "swipe_r" and inside:
            acc[1] = amp * math.sin(2 * math.pi * u)
        elif kind == "swipe_l" and inside:
            acc[1] = -amp * math.sin(2 * math.pi * u)
        elif kind == "raise":
            g = _rot(g0, [0.0, 1.0, 0.0], -pitch * _smooth(u))
            if inside:
                acc[2] = 0.5 * amp * math.sin(2 * math.pi * u)
        elif kind == "circle" and inside:
            h = math.sin(math.pi * u) ** 2
            acc[0] = amp * math.sin(2 * math.pi * u) * h
            acc[1] = amp * math.cos(2 * math.pi * u) * h
        elif kind == "twist":
            g = _rot(g0, [1.0, 0.0, 0.0], roll * _smooth(u))
            if inside:
                acc[1] = 0.2 * amp * math.sin(6 * math.pi * u)
        elif kind == "thrust" and inside:
            u3 = 3.0 * u
            if u3 < 1.0:
                acc[0] = amp * math.sin(math.pi * u3)
            else:
                acc[0] = -0.5 * amp * math.sin(math.pi * (u3 - 1.0) / 2.0)
        v = [gmag * g[i] + acc[i] + rng.uniform(-noise, noise) for i in range(3)]
        if kind == "tremor":
            for i in range(3):
                v[i] += 0.5 * noise * math.sin(2 * math.pi * fq * n_i / 100.0 + ph[i])
        if kind == "bump" and n_i == 200:
            v[bump_axis] += 300.0 * bump_sign
        out.append(tuple(_clip(c) for c in v))
    meta = {"kind": kind,
            "onset": onset if kind in G_KINDS + ["tilt", "bump"] else None,
            "dur": dur}
    if kind == "bump":
        meta["onset"] = 200
    return out, meta
# [END AI-GENERATED]
