# [AI-GENERATED: Claude Code]
"""SYNTHETIC gesture dataset writer (pipeline testing only, NOT for accuracy claims).

Every shape, amplitude and noise level below is an invented guess, not a recording. Any accuracy
measured on this data says nothing about the real wand. Replace by real recordings (C2) before
claiming a number anywhere.

Dataset format (WP2 tools): one .npz with
  windows  int16 [N,150,3]  samples in the C1 wand frame (X out of the tip, Y left, Z up),
                            12-bit range [-2048, 2047], 100 Hz, 1 g about 512 counts
  labels   uint8 [N]        class id 0..8 (C5: 0 none, 1 swipe right, 2 swipe left, 3 raise,
                            4 push down, 5 circle CW, 6 circle CCW, 7 twist, 8 thrust)
  subject  uint8 [N]        optional, for grouped splits (here: pseudo-subjects, 4 groups)
  session  uint16 [N]       optional, for grouped splits (here: pseudo-sessions, 12 groups)
  synthetic uint8 scalar    optional marker, 1 = synthetic (train.py then stamps its report)

Class 0 ("none") starts in the same orientation distribution as the gestures (within 35 degrees of
up), so the start orientation alone does not reveal the class (review W2-2R S1; checked by --selftest).
Swipe signs follow the C1 wand frame, Y = left: a swipe to the RIGHT moves the tip toward -Y first
(W2-2R S2). Pseudo-subject and pseudo-session ids carry NO signal (W2-2R S3): grouped splits test the
splitting mechanics only.

Motion onset is near sample 15 (the trigger position, C1.5) with +-3 samples of jitter.
Option --onset-jitter LO,HI (default off, output byte-identical to before): each GESTURE onset is drawn
uniformly in [15+LO, 15+HI] instead (class 0 is unchanged). It approximates the trigger latency: the live
trigger fires a few to ~40 samples after the true onset, so the onset sits at window index ~-10..27 (negative = onset before the window start) rather
than 15 (integration spike S3-1 finding 5; e.g. --onset-jitter=-25,12). It is only an approximation;
real data should instead be cut by the real trigger from continuous recordings (C1b section 3.4).
Shapes are adapted from our own spike docs/agent/hadi/spikes/trigger/synth.py (not copied code).

Usage:  python3 tools/synth_dataset.py --out ds.npz --per-class 120 --seed 1
        python3 tools/synth_dataset.py --out ds.npz --onset-jitter=-25,12   # onset index -10..27
        python3 tools/synth_dataset.py --selftest
"""
import argparse
import math
import sys

import numpy as np

WINDOW_LEN = 150
N_CLASSES = 9
START_TILT_MAX_DEG = 35.0   # all classes start within this cone around up (Z)
CLASS_NAMES = ["none", "swipe_right", "swipe_left", "raise", "push_down",
               "circle_cw", "circle_ccw", "twist", "thrust"]


def _unit(rng):
    """Random unit vector, uniform on the sphere. Args: rng (numpy Generator). Returns: ndarray[3]."""
    z = rng.uniform(-1.0, 1.0)
    a = rng.uniform(0.0, 2.0 * math.pi)
    r = math.sqrt(1.0 - z * z)
    return np.array([r * math.cos(a), r * math.sin(a), z])


def _start_gravity(rng):
    """Draw the starting gravity direction shared by ALL classes (including class 0).

    Args: rng (numpy Generator, advanced in place: tilt first, then azimuth).
    Returns: ndarray[3] unit vector within START_TILT_MAX_DEG of up (+Z), tilt uniform in angle.
    """
    tilt = math.radians(rng.uniform(0.0, START_TILT_MAX_DEG))
    az = rng.uniform(0.0, 2.0 * math.pi)
    return np.array([math.sin(tilt) * math.cos(az), math.sin(tilt) * math.sin(az), math.cos(tilt)])


def _smooth(u):
    """Smoothstep clamped to 0..1. Args: u (ndarray). Returns: ndarray, same shape."""
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def _rot(v, axis, ang):
    """Rodrigues rotation of one vector by an angle per time step.

    Args: v (ndarray[3]); axis (ndarray[3] unit); ang (ndarray[T] radians).
    Returns: ndarray[T,3], v rotated about axis by each angle.
    """
    c = np.cos(ang)[:, None]
    s = np.sin(ang)[:, None]
    cr = np.cross(axis, v)
    return v[None, :] * c + cr[None, :] * s + axis[None, :] * np.dot(axis, v) * (1.0 - c)


def make_window(cls, rng, onset_jitter=None):
    """Generate one synthetic window.

    Args: cls (int 0..8 class id); rng (numpy Generator, advanced in place); onset_jitter (None for the
    default onset 15 + integers(-3, 3), or a (lo, hi) tuple of ints, lo <= hi: gesture onset
    15 + integers(lo, hi) inclusive; class 0 ignores it; the number of rng draws is the same either way).
    Returns: int16 ndarray [150,3], clipped to [-2048, 2047].
    """
    t = np.arange(WINDOW_LEN, dtype=np.float64)
    gmag = rng.uniform(490.0, 530.0)
    acc = np.zeros((WINDOW_LEN, 3))
    noise = rng.uniform(2.0, 6.0)
    if onset_jitter is None or cls == 0:
        onset = 15 + int(rng.integers(-3, 4))
    else:
        onset = 15 + int(rng.integers(onset_jitter[0], onset_jitter[1] + 1))
    dur = int(rng.integers(30, 101))
    amp = rng.uniform(200.0, 1400.0)
    u = (t - onset) / dur
    inside = ((u >= 0) & (u < 1)).astype(np.float64)
    uu = np.clip(u, 0.0, 1.0)
    if cls == 0:
        g0 = _start_gravity(rng)
        kind = int(rng.integers(0, 4))
        g = np.tile(g0, (WINDOW_LEN, 1))
        if kind == 1:        # tremor
            noise = rng.uniform(5.0, 14.0)
            fq = rng.uniform(8.0, 12.0)
            ph = rng.uniform(0, 2 * math.pi, 3)
            acc += (noise / 2.0) * np.sin(2 * math.pi * fq * t[:, None] / 100.0 + ph[None, :])
        elif kind == 2:      # one bump spike
            k = int(rng.integers(5, 140))
            acc[k, int(rng.integers(0, 3))] += rng.choice([-1, 1]) * rng.uniform(150, 400)
        elif kind == 3:      # slow tilt over 1..2 s
            ax = np.cross(g0, _unit(rng))
            ax /= (np.linalg.norm(ax) or 1.0)
            start = int(rng.integers(10, 60))
            span = int(rng.integers(100, 200))
            ang = math.radians(rng.uniform(40, 110)) * _smooth((t - start) / span)
            g = _rot(g0, ax, ang)
    else:
        g0 = _start_gravity(rng)
        g = np.tile(g0, (WINDOW_LEN, 1))
        s2 = np.sin(2 * math.pi * uu)
        c2 = np.cos(2 * math.pi * uu)
        hann = np.sin(math.pi * uu) ** 2
        if cls in (1, 2):    # swipe along Y, push then brake; Y = left (C1.3), so right = -Y first
            acc[:, 1] = (-1 if cls == 1 else 1) * amp * s2 * inside
        elif cls in (3, 4):  # pitch up / down about Y plus a Z pulse
            sg = 1 if cls == 3 else -1
            ang = sg * math.radians(rng.uniform(40, 80)) * _smooth(u)
            g = _rot(g0, np.array([0.0, 1.0, 0.0]), ang)
            acc[:, 2] = sg * 0.5 * amp * s2 * inside
        elif cls in (5, 6):  # circle in the XY plane, direction by sign
            sg = 1 if cls == 5 else -1
            acc[:, 0] = amp * s2 * hann * inside
            acc[:, 1] = sg * amp * c2 * hann * inside
        elif cls == 7:       # twist: roll about X plus weak Y wobble
            ang = math.radians(rng.uniform(60, 120)) * rng.choice([-1, 1]) * _smooth(u)
            g = _rot(g0, np.array([1.0, 0.0, 0.0]), ang)
            acc[:, 1] = 0.2 * amp * np.sin(2 * math.pi * 2.0 * uu) * inside
        elif cls == 8:       # thrust along X, then brake
            d3 = max(dur // 2, 15)
            u3 = (t - onset) / d3
            fwd = ((u3 >= 0) & (u3 < 1)).astype(np.float64)
            u4 = (t - onset - d3) / d3
            brk = ((u4 >= 0) & (u4 < 1)).astype(np.float64)
            acc[:, 0] = amp * np.sin(math.pi * np.clip(u3, 0, 1)) * fwd \
                - 0.5 * amp * np.sin(math.pi * np.clip(u4, 0, 1)) * brk
    sig = gmag * g + acc + rng.normal(0.0, noise, (WINDOW_LEN, 3))
    return np.clip(np.rint(sig), -2048, 2047).astype(np.int16)


def make_dataset(per_class, seed, onset_jitter=None):
    """Build a whole synthetic dataset.

    Args: per_class (int windows per class, >= 1); seed (int, deterministic output); onset_jitter (None or
    (lo, hi) as in make_window; None keeps the output byte-identical to the original generator).
    Returns: dict with windows int16 [N,150,3], labels uint8 [N], subject uint8 [N], session uint16 [N];
    rows are shuffled. Sessions are 12 pseudo-sessions, each inside one of 4 pseudo-subjects.
    """
    rng = np.random.default_rng(seed)
    n = per_class * N_CLASSES
    win = np.zeros((n, WINDOW_LEN, 3), dtype=np.int16)
    lab = np.zeros(n, dtype=np.uint8)
    i = 0
    for c in range(N_CLASSES):
        for _ in range(per_class):
            win[i] = make_window(c, rng, onset_jitter)
            lab[i] = c
            i += 1
    perm = rng.permutation(n)
    sess = rng.integers(0, 12, n)
    return {"windows": win[perm], "labels": lab[perm],
            "subject": (sess[perm] // 3).astype(np.uint8), "session": sess[perm].astype(np.uint16),
            "synthetic": np.array(1, dtype=np.uint8)}


def start_tilt_deg(windows):
    """Start tilt of each window, the angle between the median of its first 10 samples and +Z.

    Args: windows (int16 ndarray [N,150,3]). Returns: float ndarray [N] degrees (0 = upright).
    """
    v = np.median(windows[:, :10, :].astype(np.float64), axis=1)
    return np.degrees(np.arccos(np.clip(v[:, 2] / np.linalg.norm(v, axis=1), -1.0, 1.0)))


def start_tilt_separability(d):
    """Best a start-tilt-only rule can do for class 0 (review W2-2R S1).

    The rule "class 0 iff start tilt > t" uses the tightest t with ZERO false positives among the
    gesture windows (t = the largest gesture start tilt). Args: d (dict from make_dataset).
    Returns: float, the share of class-0 windows that rule recognises (0..1).
    """
    tilt = start_tilt_deg(d["windows"])
    lab = d["labels"]
    t = float(tilt[lab != 0].max())
    return float((tilt[lab == 0] > t).mean())


def _selftest():
    """Check shapes, determinism, the S1 orientation artefact and the S2 swipe signs.

    Returns: 0 and prints "synth_dataset selftest PASS" on success; 1 after printing the reason.
    """
    d = make_dataset(150, 4)
    d2 = make_dataset(150, 4)
    if d["windows"].shape != (150 * N_CLASSES, WINDOW_LEN, 3) or d["windows"].dtype != np.int16:
        print("FAIL windows shape or dtype")
        return 1
    if not (np.array_equal(d["windows"], d2["windows"]) and np.array_equal(d["labels"], d2["labels"])):
        print("FAIL not deterministic for a fixed seed")
        return 1
    if int(d["windows"].min()) < -2048 or int(d["windows"].max()) > 2047:
        print("FAIL values outside the 12-bit range")
        return 1
    rec = start_tilt_separability(d)
    print("start-tilt-only rule at 0 false positives recognises %.1f %% of class 0 (limit 60 %%)" % (100 * rec))
    if rec >= 0.60:
        print("FAIL class 0 separable by start orientation")
        return 1
    w = d["windows"].astype(np.float64)
    dy = w[:, 20:27, 1].mean(axis=1) - w[:, :10, 1].mean(axis=1)
    m1, m2 = float(dy[d["labels"] == 1].mean()), float(dy[d["labels"] == 2].mean())
    print("early Y change: swipe_right %+.1f, swipe_left %+.1f counts (expect - and +)" % (m1, m2))
    if not (m1 < -10.0 and m2 > 10.0):
        print("FAIL swipe signs not in the C1.3 wand frame")
        return 1
    j = (-25, 12)
    dj = make_dataset(60, 4, j)
    if not np.array_equal(make_dataset(60, 4, j)["windows"], dj["windows"]) or int(dj["windows"].min()) < -2048 \
            or int(dj["windows"].max()) > 2047:
        print("FAIL onset-jitter dataset not deterministic or out of range")
        return 1
    if not np.array_equal(make_dataset(60, 4)["windows"], make_dataset(60, 4, None)["windows"]):
        print("FAIL default dataset changed")
        return 1
    # onset of a swipe = first sample where |Y - start| leaves the noise: check the mean early/late motion
    wj = dj["windows"].astype(np.float64)
    sw = wj[dj["labels"] == 1][:, :, 1]
    early = np.abs(sw[:, 0:5] - sw[:, :1]).mean()
    print("onset-jitter -25,12: swipe windows with motion by sample 5: %.1f counts mean |dY| (default would be ~noise)" % early)
    print("synth_dataset selftest PASS")
    return 0


def main(argv=None):
    """CLI entry. Args: argv (list of str or None for sys.argv). Returns: int exit code (0 ok)."""
    ap = argparse.ArgumentParser(description="Write a SYNTHETIC gesture dataset (.npz); pipeline testing only.")
    ap.add_argument("--selftest", action="store_true", help="run the built-in checks and exit")
    ap.add_argument("--out", help="output .npz path")
    ap.add_argument("--per-class", type=int, default=120)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--onset-jitter", metavar="LO,HI", default=None,
                    help="gesture onset uniform in [15+LO, 15+HI] (e.g. --onset-jitter=-25,12); default off = onset 15 +- 3")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    if not a.out:
        ap.error("--out is required (or use --selftest)")
    if a.per_class < 1:
        print("error: --per-class must be >= 1", file=sys.stderr)
        return 2
    jit = None
    if a.onset_jitter is not None:
        try:
            lo, hi = (int(v) for v in a.onset_jitter.split(","))
        except ValueError:
            print("error: --onset-jitter needs LO,HI integers", file=sys.stderr)
            return 2
        if lo > hi or 15 + lo < -60 or 15 + hi > 120:
            print("error: --onset-jitter needs LO <= HI with onset in [-60, 120]", file=sys.stderr)
            return 2
        jit = (lo, hi)
    d = make_dataset(a.per_class, a.seed, jit)
    np.savez_compressed(a.out, **d)
    print("SYNTHETIC dataset (pipeline testing only, not for accuracy claims): %d windows -> %s"
          % (len(d["labels"]), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
