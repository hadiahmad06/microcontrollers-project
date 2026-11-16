#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""Runner for the gesture.c suite (ticket 3.7T), written from docs/agent/hadi/briefs/3.7_spec.md only.

It defines the scenarios (op lists), generates scen.h for test_gesture.c, builds host / sim16 /
bring-up binaries, runs them, decodes the UART bytes with tools/c2_proto.py and compares everything
with the Python references: tools/trigger_ref.py (run + cut_windows: which windows exist and their
samples), tools/infer_ref.py (+ features_ref: class and confidence, k-NN), tools/c2_proto.py (frames).

Environment (set by the Makefile): HOST_CC HOST_CFLAGS AVR_CC AVR_CFLAGS SIM16_RUN SIM16_SRC MOD_SRC
TOOLS_DIR MLP_TEST_DIR. Prints PASS/FAIL lines and finally "gesture suite PASS" (exit 0) or exits 1.
"""
import argparse
import os
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.environ.get("TOOLS_DIR") or os.path.join(HERE, "..", "..", "..", "tools")
sys.path.insert(0, TOOLS)
import c2_proto  # noqa: E402
import features_ref  # noqa: E402
import infer_ref  # noqa: E402
import trigger_ref  # noqa: E402

# ----------------------------------------------------------------------------- ops (mirrored in scen.h)
OPS = ["BEGIN", "SENSOR", "CFG", "INIT", "SEG", "STALL", "POLL", "CLASSIFY", "LEARN", "REJECT",
       "STREAM", "EVENTS", "CLICK", "AUTO"]
K = {n: i for i, n in enumerate(OPS)}
QUIET = (0, 0, 0, 8)
GA, GB, GC, GD = (140, -90, 60, 16), (-120, 100, -80, 12), (90, 90, -120, 20), (160, -60, 100, 16)


def op(name, n=0, a=0, b=0, c=0, p=0):
    """One op tuple (kind, n, a, b, c, p); meaning of the fields per op is in test_gesture.c."""
    return (K[name], n, a, b, c, p)


def q(n):
    """n quiet steps."""
    return op("SEG", n, *QUIET)


def g(shape, n=40):
    """n steps of a gesture swing with the given (a, b, c, period)."""
    return op("SEG", n, *shape)


def stall(n):
    """n steps in which samples arrive but gesture_poll is not called."""
    return op("STALL", n, *QUIET)


def head(seed, cap=128, rate=64, polls=2, mode=0, ms0=0, addr=0x18, who=0x33, corrupt=0xFF, init=True):
    """Common scenario prefix: BEGIN, SENSOR, CFG and (optionally) a successful INIT."""
    h = [op("BEGIN", seed), op("SENSOR", addr, who, corrupt), op("CFG", cap, rate, polls, mode, ms0)]
    return h + ([op("INIT", 100, 4)] if init else [])


# ----------------------------------------------------------------------------- stream mirror
def gen_stream(ops, init_results):
    """Mirror of test_gesture.c's sample generator and of what the fake sensor delivers.

    Args: ops (op list); init_results (expected gesture_init returns, in order).
    Returns: (stream, step_of, step_total): stream = samples pushed while the FIFO was active (index =
    fake sensor seq), step_of[i] = step number (1-based) in which stream[i] was generated.
    """
    lcg, step, active = 0, 0, False
    stream, step_of = [], []
    inits = list(init_results)

    def noise():
        nonlocal lcg
        lcg = (lcg * 1664525 + 1013904223) & 0xFFFFFFFF
        return ((lcg >> 16) % 7) - 3

    def tri(j, per):
        u = j % per
        v = u if u < per // 2 else per - u
        return v - per // 4

    def clamp(v):
        return max(-2048, min(2047, v))

    for (k, n, a, b, c, p) in ops:
        if k == K["BEGIN"]:
            lcg = n & 0xFFFF
        elif k == K["SENSOR"]:
            active, stream, step_of = False, [], []
        elif k == K["INIT"]:
            if (inits.pop(0) if inits else 0) == 0:
                active = True
        elif k in (K["SEG"], K["STALL"]):
            for j in range(n):
                nx, ny, nz = noise(), noise(), noise()
                s = (clamp(a * tri(j, p) + nx), clamp(b * tri(j + 3, p) + ny), clamp(512 + c * tri(j + 5, p) + nz))
                step += 1
                if active:
                    stream.append(s)
                    step_of.append(step)
    return stream, step_of, step


def delivered(stream, gaps):
    """Samples that actually reached the driver: the stream minus the FIFO-discarded seq ranges."""
    lost = set()
    for first, cnt in gaps:
        lost.update(range(first, first + cnt))
    keep = [i for i in range(len(stream)) if i not in lost]
    return [stream[i] for i in keep], keep


# ----------------------------------------------------------------------------- output parsing
class Out:
    """Parsed output of one scenario."""

    def __init__(self, name):
        self.name = name
        self.R, self.P, self.X, self.G, self.V = [], [], [], [], []
        self.T = None
        self.frames, self.dec = [], None

    def init(self):
        return [r[1] for r in self.R if r[0] == "init"]

    def of(self, what):
        return [r[1:] for r in self.R if r[0] == what]

    def decode(self, accept_samples=False):
        """Decode every X byte through c2_proto.Decoder; frames = [(step, Frame)]."""
        self.dec = c2_proto.Decoder(accept_samples=accept_samples)
        self.frames = []
        for step, data in self.X:
            for f in self.dec.feed(data):
                self.frames.append((step, f))
        return self

    def typed(self, ftype):
        return [(s, f) for s, f in self.frames if f.ftype == ftype]


def parse_output(lines):
    """Split program output into (model tuple, {scenario name: Out}); also reports DONE."""
    model, outs, cur, done = None, {}, None, False
    for ln in lines:
        t = ln.split()
        if not t:
            continue
        if t[0] == "M":
            model = (int(t[1], 16), int(t[2]), int(t[3]))
        elif t[0] == "S":
            cur = Out(t[1])
            outs[t[1]] = cur
        elif t[0] == "DONE":
            done = True
        elif cur is None:
            continue
        elif t[0] == "R":
            cur.R.append((t[1],) + tuple(int(x) for x in t[2:]))
        elif t[0] == "P":
            cur.P.append(int(t[1]))
        elif t[0] == "X":
            cur.X.append((int(t[1]), bytes.fromhex(t[2])))
        elif t[0] == "G":
            cur.G.append((int(t[1]), int(t[2])))
        elif t[0] == "T":
            cur.T = tuple(int(x) for x in t[1:])
        elif t[0] == "V":
            cur.V.append(ln)
    return model, outs, done


# ----------------------------------------------------------------------------- reporting
class Rep:
    """Collects PASS/FAIL lines."""

    def __init__(self):
        self.fails, self.n = 0, 0

    def check(self, label, cond, detail=""):
        self.n += 1
        if cond:
            print("PASS %s" % label)
        else:
            self.fails += 1
            print("FAIL %s %s" % (label, detail))
        return bool(cond)


# ----------------------------------------------------------------------------- reference helpers
class Ref:
    """Reference model: infer_ref + features_ref + trigger_ref for the generated header."""

    def __init__(self, hdr):
        self.m = infer_ref.load_header(hdr)
        self.hash = self.m["GM_MODEL_HASH"]

    def classify(self, window, store, min_conf):
        """Returns ((id, conf), x8) for one window with the k-NN store {class: [x8, ...]}."""
        fw = infer_ref.forward(features_ref.features_extract(window), self.m)
        kn = infer_ref.knn_query(fw["x8"], store) if store else None
        return infer_ref.classify_decide(fw["top1"], fw["margin"], self.m["GM_CONF_SHIFT"], kn, min_conf), fw["x8"]


def ref_windows(deliv):
    """Windows trigger_ref would cut from the delivered stream: [(t, rows)]."""
    trigs, _ = trigger_ref.run(deliv)
    return trigger_ref.cut_windows(deliv, trigs)


def boot_line(o, ref, rep):
    """Check the ASCII boot line."""
    want = "GM_MODEL_HASH=0x%08X" % ref.hash
    rep.check("%s: boot text line" % o.name, want in o.dec.text_lines, "text lines %r, want %r" % (o.dec.text_lines[:3], want))


def clean_stream(o, rep, samples=False):
    """No CRC / header / sequence errors, no harness violation."""
    d = o.dec
    rep.check("%s: no CRC/header/seq errors" % o.name, d.crc_errors == 0 and d.bad_header == 0 and d.seq_gaps == 0,
              "crc %d bad_header %d seq_gaps %d" % (d.crc_errors, d.bad_header, d.seq_gaps))
    rep.check("%s: gesture.c never wrote more than port_tx_room" % o.name, not o.V, str(o.V))


def check_windows(o, rep, exp_wins, exp_cls, ref, overruns=None, events=None, label=None):
    """Compare WINDOW frames with the expected windows / class / conf (exp_cls = [(id, conf)])."""
    pw = [c2_proto.parse_window(f.payload) for _, f in o.typed(c2_proto.T_WINDOW)]
    lab = "%s: %s" % (o.name, label or "WINDOW frames")
    if not rep.check(lab + " count", len(pw) == len(exp_wins), "got %d expected %d" % (len(pw), len(exp_wins))):
        return pw
    for i, (w, (t, rows), (cid, conf)) in enumerate(zip(pw, exp_wins, exp_cls)):
        rep.check("%s window %d samples == trigger_ref cut" % (lab, i), w["samples"] == [tuple(r) for r in rows],
                  "first differing row %r" % next(((j, a, b) for j, (a, b) in enumerate(zip(w["samples"], rows)) if a != tuple(b)), None))
        rep.check("%s window %d metadata" % (lab, i),
                  (w["window_id"] == i and w["n_samples"] == 150 and w["trig_idx"] == 15 and w["model_hash"] == ref.hash
                   and w["flags"] == 1 and w["class_id"] == cid and w["conf"] == conf
                   and (overruns is None or w["overruns"] == overruns[i]) and (events is None or w["events"] == events[i])),
                  "got %r, expected id %d conf %d overruns %s events %s hash 0x%08X" % (
                      {k: v for k, v in w.items() if k != "samples"}, cid, conf,
                      None if overruns is None else overruns[i], None if events is None else events[i], ref.hash))
    return pw


def classify_results(o, rep, exp_cls, label="classify results", skip=0):
    got = [tuple(r) for r in o.of("classify")][skip:]
    rep.check("%s: %s" % (o.name, label), got == [tuple(c) for c in exp_cls], "got %r expected %r" % (got, exp_cls))


def hello_check(o, rep, ref, n=None):
    hs = o.typed(c2_proto.T_HELLO)
    if n is not None:
        rep.check("%s: HELLO count" % o.name, len(hs) == n, "got %d expected %d" % (len(hs), n))
    ok = all(c2_proto.parse_hello(f.payload) == {"proto_ver": 1, "odr_hz": 100, "range_g": 4, "n_samples": 150, "pre_trig": 15,
                                                 "feature_ver": ref.m["GM_FEATURE_VERSION"], "model_hash": ref.hash}
             for _, f in hs)
    rep.check("%s: HELLO fields" % o.name, ok and bool(hs), "frames %d" % len(hs))
    return [s for s, _ in hs]


# ----------------------------------------------------------------------------- scenarios
SCEN = []   # dicts: name, ops, init (expected init returns), kinds, check


def scenario(name, ops, init=(0,), kinds=("host",), fresh=False):
    """Decorator registering a scenario and its checker check(o, rep, ref, ctx)."""
    def deco(fn):
        SCEN.append(dict(name=name, ops=ops, init=list(init), kinds=kinds, check=fn, fresh=fresh))
        return fn
    return deco


def ctx_of(sc, o):
    """Stream/gap context of a scenario output: stream, delivered samples, delivered->step map, gaps."""
    stream, step_of, _ = gen_stream(sc["ops"], sc["init"])
    deliv, keep = delivered(stream, o.G)
    return dict(stream=stream, deliv=deliv, step_of=[step_of[i] for i in keep], gaps=o.G)


# 1: calls before init, then init, no window, set_reject before init survives ---------------------------
_ops = (head(1, init=False) + [op("POLL"), op("CLASSIFY"), op("CLASSIFY", 1), op("LEARN", 9), op("EVENTS"), op("STREAM", 1),
                                op("REJECT", 255), q(30), op("POLL"), op("INIT", 100, 4), op("LEARN", 9), q(5), op("AUTO", 1),
                                q(80), g(GA), q(160)])


@scenario("pre_init", _ops, init=(0,), fresh=True)
def chk_pre_init(o, rep, ref, cx):
    R = o.R
    rep.check("pre_init: poll before init is false", R[0] == ("poll", 0), str(R[:1]))
    rep.check("pre_init: classify before init is UNKNOWN (with and without pointer)",
              R[1][0] == "classify" and R[1][1] == -1 and R[2][0] == "classify" and R[2][1] == -1, str(R[1:3]))
    rep.check("pre_init: learn before init is -2 (ruling 3.7T-1)", R[3] == ("learn", -2), str(R[3]))
    rep.check("pre_init: events before init is 0", R[4] == ("events", 0), str(R[4]))
    rep.check("pre_init: second poll false, init returns 0", R[5] == ("poll", 0) and R[6] == ("init", 0), str(R[5:7]))
    rep.check("pre_init: learn with no window is -2", R[7] == ("learn", -2), str(R[7]))
    first_x = o.X[0][0] if o.X else None
    rep.check("pre_init: no UART byte before init (stream_raw before init does nothing)", first_x is not None and first_x > 30,
              "first TX step %r" % first_x)
    rep.check("pre_init: no frames (stream_raw(true) before init was ignored)", not o.frames, "%d frames" % len(o.frames))
    boot_line(o, ref, rep)
    clean_stream(o, rep)
    wins = ref_windows(cx["deliv"])
    exp = [ref.classify(w, {}, 255)[0] for _, w in wins]      # set_reject(255) before init must survive init
    classify_results(o, rep, exp, "reject set before init is kept", skip=2)


# 2: init return codes ------------------------------------------------------------------------------
_ops = (head(2, init=False) + [op("INIT", 50, 4), op("POLL"), op("EVENTS"), op("INIT", 100, 8), op("POLL"),
                                op("SENSOR", 0, 0x33, 0xFF), op("INIT", 100, 4), op("POLL"),
                                op("SENSOR", 0x18, 0x00, 0xFF), op("INIT", 100, 4), op("POLL"),
                                op("SENSOR", 0x18, 0x33, 0x20), op("INIT", 100, 4), op("POLL"), q(5),
                                op("SENSOR", 0x19, 0x33, 0xFF), op("INIT", 100, 4), q(20),
                                op("SENSOR", 0x18, 0x33, 0xFF), op("INIT", 100, 4), q(20)])


@scenario("init_codes", _ops, init=(-1, -1, -2, -2, -2, 0, 0))
def chk_init(o, rep, ref, cx):
    rep.check("init_codes: odr mismatch -1, range mismatch -1, no sensor -2, bad WHO_AM_I -2, bus/config error -2, ok at 0x19, ok at 0x18",
              o.init() == [-1, -1, -2, -2, -2, 0, 0], str(o.init()))
    rep.check("init_codes: poll false and events 0 after every failed init",
              all(r == ("poll", 0) or r == ("events", 0) or r[0] == "init" for r in o.R), str(o.R))
    boot_line(o, ref, rep)
    clean_stream(o, rep)


# 3: poll true until classify, classify twice, stream off releases at once --------------------------------
_ops = (head(3) + [op("REJECT", 0), op("STREAM", 0), q(80), g(GA), q(120), op("POLL"), op("POLL"), op("CLASSIFY"), op("POLL"), op("CLASSIFY"),
                    q(60), g(GB), q(120), op("CLASSIFY", 1), op("POLL")])


@scenario("poll_classify", _ops, kinds=("host", "sim"))
def chk_poll(o, rep, ref, cx):
    wins = ref_windows(cx["deliv"])
    exp = [ref.classify(w, {}, 0)[0] for _, w in wins]
    rep.check("poll_classify: reference sees two windows", len(wins) == 2, str(len(wins)))
    rep.check("poll_classify: poll went true once per READY window (2 transitions)", len(o.P) == 2, str(o.P))
    R = [r for r in o.R if r[0] in ("poll", "classify")]
    rep.check("poll_classify: poll stays true until classify, then false",
              R[0] == ("poll", 1) and R[1] == ("poll", 1) and R[3] == ("poll", 0), str(R[:4]))
    rep.check("poll_classify: second classify of the same window is UNKNOWN", R[4][0] == "classify" and R[4][1] == -1, str(R[4]))
    rep.check("poll_classify: first window class/conf == infer_ref; window B (NULL conf pointer) class == infer_ref",
              R[2][1:] == tuple(exp[0]) and R[5][1] == exp[1][0], "got %r %r, expected %r" % (R[2], R[5], exp))
    rep.check("poll_classify: poll false after classify", R[6] == ("poll", 0), str(R[6]))
    rep.check("poll_classify: stream off sends no frame", not o.frames, "%d frames" % len(o.frames))
    boot_line(o, ref, rep)
    clean_stream(o, rep)


# 4: learn -----------------------------------------------------------------------------------------------
_ops = (head(4) + [op("REJECT", 0), op("STREAM", 0), op("LEARN", 9), q(80), g(GA), q(120), op("CLASSIFY"), op("LEARN", 3), op("LEARN", 9), op("LEARN", 9),
                    q(60), g(GA), q(120), op("CLASSIFY"), op("LEARN", 9), q(60), g(GB), q(120), op("CLASSIFY"), op("LEARN", 10),
                    q(60), g(GA), q(120), op("CLASSIFY")])


@scenario("learn", _ops, kinds=("host", "sim"))
def chk_learn(o, rep, ref, cx):
    wins = ref_windows(cx["deliv"])
    rep.check("learn: reference sees four windows", len(wins) == 4, str(len(wins)))
    store, exp = {}, []
    # sequential: the k-NN store grows after each learn
    c, x = ref.classify(wins[0][1], store, 0)
    exp.append(c)
    store[9] = [x]
    c, x = ref.classify(wins[1][1], store, 0)
    exp.append(c)
    store[9].append(x)
    c, x = ref.classify(wins[2][1], store, 0)
    exp.append(c)
    store[10] = [x]
    c, x = ref.classify(wins[3][1], store, 0)
    exp.append(c)
    classify_results(o, rep, exp, "class/conf with learned k-NN templates")
    rep.check("learn: returns -2 (no window), -1 (bad id), 1, -2 (x8 cleared after a learn), 2 (second template), 1 (new class)",
              [r[0] for r in o.of("learn")] == [-2, -1, 1, -2, 2, 1], str(o.of("learn")))
    clean_stream(o, rep)


# 5: stream on: HELLO, WINDOW frames, default reject ---------------------------------------------------------
_ops = head(5) + [op("STREAM", 1), op("AUTO", 1), q(80), g(GA), q(160), g(GB), q(160), q(250)]


@scenario("stream_window", _ops, kinds=("host", "sim"))
def chk_stream(o, rep, ref, cx):
    o.decode()
    wins = ref_windows(cx["deliv"])
    rep.check("stream_window: reference sees two windows", len(wins) == 2, str(len(wins)))
    exp = [ref.classify(w, {}, ref.m["GM_DEFAULT_REJECT"])[0] for _, w in wins]
    classify_results(o, rep, exp, "default reject (GM_DEFAULT_REJECT) applied")
    check_windows(o, rep, wins, exp, ref, overruns=[0, 0], events=[0, 0])
    hs = hello_check(o, rep, ref, n=4)
    rep.check("stream_window: HELLO every 2000 ms (200 steps)", len(hs) >= 2 and all(198 <= b - a <= 202 for a, b in zip(hs, hs[1:])), str(hs))
    rep.check("stream_window: first HELLO right after stream on", bool(hs) and hs[0] <= 3, str(hs[:1]))
    boot_line(o, ref, rep)
    clean_stream(o, rep)
    rep.check("stream_window: boot line precedes the first frame", bool(o.frames) and o.X and o.X[0][1][:3] == b"GM_", "")


# 6: HELLO every 2000 ms across a millis wrap; stream off stops it; on again sends one at once -------------------
_ops = head(6, ms0=65000) + [op("STREAM", 1), q(250), op("STREAM", 0), q(300), op("STREAM", 1), q(260)]


@scenario("hello_wrap", _ops)
def chk_hello(o, rep, ref, cx):
    o.decode()
    hs = hello_check(o, rep, ref, n=4)
    ok = (len(hs) == 4 and hs[0] <= 3 and 198 <= hs[1] - hs[0] <= 202 and 551 <= hs[2] <= 556 and 198 <= hs[3] - hs[2] <= 202)
    rep.check("hello_wrap: HELLO at stream on and every 2000 ms across the 65536 ms wrap; none while off; one at once on re-enable",
              ok, str(hs))
    rep.check("hello_wrap: no WINDOW frame (nothing triggered)", not o.typed(c2_proto.T_WINDOW), "")
    rep.check("hello_wrap: backstop drain interval 50..60 ms across the millis wrap", o.T is not None and o.T[0] > 50 and 50 <= o.T[1] and o.T[2] <= 60,
              str(o.T))
    clean_stream(o, rep)


# 7: a gesture while SENDING is lost; buffer released only after the last byte --------------------------------------
_ops = head(7, rate=3) + [op("REJECT", 0), op("STREAM", 1), op("AUTO", 1), q(80), g(GA), q(130), g(GB), q(300), g(GC), q(330)]


@scenario("send_lock", _ops)
def chk_lock(o, rep, ref, cx):
    o.decode()
    allw = ref_windows(cx["deliv"])
    wins = [(t, w) for t, w in allw if not (250 <= t <= 295)]     # gesture B starts at step 251, during SENDING
    rep.check("send_lock: reference sees A, B, C", len(allw) == 3 and len(wins) == 2, str([t for t, _ in allw]))
    exp = [ref.classify(w, {}, 0)[0] for _, w in wins]
    classify_results(o, rep, exp, "only A and C classified (B lost while SENDING)")
    check_windows(o, rep, wins, exp, ref)
    boot_line(o, ref, rep)
    clean_stream(o, rep)


# 8: stream off: buffer is released at classify, a close second gesture is captured ----------------------------------
_ops = head(8) + [op("REJECT", 0), op("AUTO", 1), q(80), g(GA), q(142), g(GB), q(160)]


@scenario("tight_release", _ops)
def chk_tight(o, rep, ref, cx):
    wins = ref_windows(cx["deliv"])
    exp = [ref.classify(w, {}, 0)[0] for _, w in wins]
    rep.check("tight_release: reference sees two windows", len(wins) == 2, str(len(wins)))
    classify_results(o, rep, exp, "both windows classified (stream off releases immediately)")
    rep.check("tight_release: no frames", not o.frames, "")


# 9: events: latch per window, read-and-clear -----------------------------------------------------------------------
_ops = (head(9) + [op("REJECT", 0), op("STREAM", 1), op("AUTO", 1), q(80), g(GA), q(10), op("CLICK", 0), q(160), op("EVENTS"), op("EVENTS"),
                    q(40), op("AUTO", 0), g(GB), q(100), op("CLICK", 0), q(3), op("CLASSIFY"), op("AUTO", 1), q(100),
                    op("CLICK", 0), q(10), g(GC), q(160), g(GD), q(10), op("CLICK", 1), q(160), op("EVENTS"), op("EVENTS")])


@scenario("events", _ops, kinds=("host", "sim"))
def chk_events(o, rep, ref, cx):
    o.decode()
    wins = ref_windows(cx["deliv"])
    rep.check("events: reference sees four windows", len(wins) == 4, str(len(wins)))
    exp = [ref.classify(w, {}, 0)[0] for _, w in wins]
    check_windows(o, rep, wins, exp, ref, events=[1, 1, 0, 0], label="WINDOW events latch (tap while CAPTURING / READY; none; single click)")
    rep.check("events: gesture_events() is read-and-clear (1,0 then 1,0)", [r[0] for r in o.of("events")] == [1, 0, 1, 0], str(o.of("events")))
    clean_stream(o, rep)


# 10: overrun: windows straddling a gap are dropped; overrun count in WINDOW ------------------------------------------
_ops = (head(10) + [op("REJECT", 0), op("STREAM", 1), op("AUTO", 1), q(50), stall(40), q(60), g(GA), q(77), stall(45), q(250), g(GB), q(160)])


@scenario("overrun", _ops)
def chk_overrun(o, rep, ref, cx):
    o.decode()
    rep.check("overrun: the fake FIFO lost samples twice (stall 1 and stall 2)", len(o.G) == 2, str(o.G))
    gap2 = cx["gaps"][-1][0] if cx["gaps"] else 0       # delivered index of the first sample after gap 2
    gap2 -= cx["gaps"][0][1] if len(cx["gaps"]) > 1 else 0
    allw = ref_windows(cx["deliv"])
    wins = [(t, w) for t, w in allw if t >= gap2]
    rep.check("overrun: reference sees A (before gap 2) and B (after it)", len(allw) >= 2 and len(wins) == 1, str([t for t, _ in allw]))
    exp = [ref.classify(w, {}, 0)[0] for _, w in wins]
    classify_results(o, rep, exp, "window A (open when the overrun hit) is dropped, never classified")
    check_windows(o, rep, wins, exp, ref, overruns=[2], label="only window B, overruns == 2")
    clean_stream(o, rep)


# 11 / 12: drain triggers ---------------------------------------------------------------------------------------------
@scenario("backstop_drain", head(11, mode=1) + [op("REJECT", 0), op("AUTO", 1), q(80), g(GA), q(160)])
def chk_backstop(o, rep, ref, cx):
    wins = ref_windows(cx["deliv"])
    exp = [ref.classify(w, {}, 0)[0] for _, w in wins]
    classify_results(o, rep, exp, "no INT0 flag ever: the 50 ms backstop drain delivers every sample")
    rep.check("backstop_drain: drains 50..60 ms apart without any INT0 flag", o.T is not None and o.T[0] > 5 and o.T[1] >= 50 and o.T[2] <= 60, str(o.T))


@scenario("flag_drain", head(12, mode=2) + [op("REJECT", 0), op("AUTO", 1), q(80), g(GA), q(160)])
def chk_flag(o, rep, ref, cx):
    wins = ref_windows(cx["deliv"])
    exp = [ref.classify(w, {}, 0)[0] for _, w in wins]
    classify_results(o, rep, exp, "INT0 flag every step: each flag drains at once")
    rep.check("flag_drain: a drain on every flag (10 ms apart, not 50 ms)", o.T is not None and o.T[0] > 100 and o.T[2] <= 10, str(o.T))


# 13: one-byte TX room still completes frames ---------------------------------------------------------------------------
@scenario("tiny_tx", head(13, cap=1, rate=1, polls=8) + [op("REJECT", 0), op("STREAM", 1), op("AUTO", 1), q(80), g(GA), q(160), q(300)])
def chk_tiny(o, rep, ref, cx):
    o.decode()
    wins = ref_windows(cx["deliv"])
    exp = [ref.classify(w, {}, 0)[0] for _, w in wins]
    check_windows(o, rep, wins, exp, ref, overruns=[0], events=[0])
    hello_check(o, rep, ref)
    boot_line(o, ref, rep)
    clean_stream(o, rep)


# 14: set_reject after init ----------------------------------------------------------------------------------------------
_ops = head(14) + [op("REJECT", 0), op("STREAM", 0), op("AUTO", 1), q(80), g(GA), q(130), op("REJECT", 255), g(GB), q(130), op("REJECT", 128), g(GC), q(130)]


@scenario("reject", _ops, kinds=("host", "sim"))
def chk_reject(o, rep, ref, cx):
    wins = ref_windows(cx["deliv"])
    rep.check("reject: reference sees three windows", len(wins) == 3, str(len(wins)))
    exp = [ref.classify(w, {}, mc)[0] for (_, w), mc in zip(wins, (0, 255, 128))]
    classify_results(o, rep, exp, "reject threshold changes between windows")


# 15: bring-up build (-DGESTURE_BRINGUP_SAMPLES=1) -----------------------------------------------------------------------
BRING = []


def bring(name, ops):
    BRING.append(dict(name=name, ops=ops, init=[0], kinds=("bring",)))
    return BRING[-1]


bring("bu_basic", head(15) + [op("STREAM", 1), op("AUTO", 1), q(80), g(GA), q(100), q(7)])
bring("bu_overrun", head(16) + [op("STREAM", 1), q(60), stall(45), q(100), q(7)])


def chk_bring(sc, o, rep, ref):
    o.decode(accept_samples=True)
    cx = ctx_of(sc, o)
    sf = [c2_proto.parse_samples(f.payload) for _, f in o.typed(c2_proto.T_SAMPLES)]
    rows = [r for s in sf for r in s["samples"]]
    nm = "bring-up %s" % o.name
    rep.check("%s: SAMPLES chunks numbered 0,1,2.. with n=16" % nm,
              bool(sf) and [s["chunk"] for s in sf] == list(range(len(sf))) and all(s["n"] == 16 for s in sf), str([s["chunk"] for s in sf][:8]))
    rep.check("%s: no WINDOW frame and poll never true" % nm, not o.typed(c2_proto.T_WINDOW) and not o.P, "")
    rep.check("%s: HELLO present" % nm, bool(o.typed(c2_proto.T_HELLO)), "")
    if not o.G:
        n = len(cx["deliv"])
        rep.check("%s: every drained sample is sent, in order, in 16-row chunks" % nm,
                  rows == cx["deliv"][:len(rows)] and len(rows) % 16 == 0 and len(rows) >= (n - 20) // 16 * 16,
                  "rows %d delivered %d" % (len(rows), n))
    else:
        it = iter(cx["deliv"])
        rep.check("%s: sent rows are an in-order subsequence of the delivered samples, rows after the gap present" % nm,
                  all(any(r == s for s in it) for r in rows) and len(rows) >= 100, "rows %d" % len(rows))
        rep.check("%s: text line OVR 2 queued (ruling 3.7T-2: FIFO overrun + drain that lost rows)" % nm, "OVR 2" in o.dec.text_lines, str(o.dec.text_lines))
    rep.check("%s: no CRC/header errors, no TX overflow" % nm, o.dec.crc_errors == 0 and o.dec.bad_header == 0 and not o.V, str(o.V))


# ----------------------------------------------------------------------------- build and run
def scen_header(scens):
    """Text of scen.h for a scenario list."""
    s = ["/* generated by run_tests.py */", "#include <stdint.h>"]
    for n, i in K.items():
        s.append("#define OP_%s %d" % (n, i))
    s.append("typedef struct { uint8_t k; int16_t n, a, b, c, p; } op_t;")
    s.append("typedef struct { const char *name; const op_t *ops; uint16_t nops; } scen_t;")
    for i, sc in enumerate(scens):
        s.append("static const op_t S%d[] = {" % i)
        s += ["  {%d,%d,%d,%d,%d,%d}," % tuple(v - 65536 if v > 32767 else v for v in o) for o in sc["ops"]]   # p may be a uint16 (millis)
        s.append("};")
    s.append("static const scen_t SCEN[] = {")
    s += ['  {"%s", S%d, %d},' % (sc["name"], i, len(sc["ops"])) for i, sc in enumerate(scens)]
    s.append("};")
    s.append("#define N_SCEN %d" % len(scens))
    return "\n".join(s) + "\n"


def sh(cmd, timeout=600):
    """Run a command, return CompletedProcess (stdout/stderr text)."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def build(kind, scens, bdir, extra=(), tag=""):
    """Compile one binary. kind: host | avr. Returns (path, error text or None)."""
    kd = os.path.join(bdir, kind + tag)
    os.makedirs(kd, exist_ok=True)
    with open(os.path.join(kd, "scen.h"), "w") as f:
        f.write(scen_header(scens))
    mods = shlex.split(os.environ["MOD_SRC"])
    sim = os.environ["SIM16_SRC"]
    inc = ["-iquote", HERE, "-iquote", os.path.join(bdir, "model"), "-iquote", kd]
    if kind == "host":
        cc, flags, out = shlex.split(os.environ["HOST_CC"]), shlex.split(os.environ["HOST_CFLAGS"]), os.path.join(kd, "t.host")
    else:
        cc, flags, out = shlex.split(os.environ["AVR_CC"]), shlex.split(os.environ["AVR_CFLAGS"]), os.path.join(kd, "t.elf")
    cmd = cc + flags + inc + list(extra) + ["-o", out, os.path.join(HERE, "test_gesture.c"), os.path.join(HERE, "fake_sensor.c")] + mods + [sim]
    p = sh(cmd)
    return out, (None if p.returncode == 0 else (p.stderr or p.stdout)[-3000:])


def run_prog(kind, path, arg=None):
    """Run a binary; returns output lines or None on failure/timeout."""
    cmd = [path] + ([str(arg)] if arg is not None else []) if kind == "host" else [os.environ["SIM16_RUN"], path, "600"]
    try:
        p = sh(cmd, timeout=700)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    lines = [x.rstrip("\r") for x in p.stdout.split("\n") if x.strip() and not x.startswith("SIM16_EXIT")]
    return lines, (None if p.returncode == 0 else "exit %d: %s" % (p.returncode, p.stderr[-300:]))


def evaluate(sc, outs, ref, rep, model):
    """Run the checker of one scenario on its parsed output."""
    o = outs.get(sc["name"])
    if not rep.check("%s: scenario ran" % sc["name"], o is not None, "no output"):
        return
    rep.check("%s: model line == header" % sc["name"], model == (ref.hash, ref.m["GM_CONF_SHIFT"], ref.m["GM_DEFAULT_REJECT"]), str(model))
    cx = ctx_of(sc, o)
    if "check" in sc:
        o.decode()
        sc["check"](o, rep, ref, cx)
    else:
        chk_bring(sc, o, rep, ref)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", default="build")
    ap.add_argument("--model-seed", type=int, default=0)
    ap.add_argument("--no-sim16", action="store_true")
    a = ap.parse_args()
    bdir = os.path.abspath(a.build)
    os.makedirs(os.path.join(bdir, "model"), exist_ok=True)
    hdr = os.path.join(bdir, "model", "gesture_model.h")
    gm = os.path.join(os.environ.get("MLP_TEST_DIR", os.path.join(HERE, "..", "mlp")), "gen_model.py")
    p = sh([sys.executable, gm, str(a.model_seed), hdr])
    if p.returncode != 0:
        print("FAIL model generation: " + p.stderr[-500:])
        return 1
    ref = Ref(hdr)
    if (ref.m["GM_ODR_HZ"], ref.m["GM_RANGE_G"]) != (100, 4):
        print("FAIL model seed %d is not a 100 Hz / 4 g model; use MODEL_SEED % 3 == 0" % a.model_seed)
        return 1
    rep = Rep()
    # host: one process per scenario (gesture.c keeps state between scenarios, e.g. set_reject)
    for kind, scens, extra, label in (("host", SCEN, (), "host"), ("host", BRING, ("-DGESTURE_BRINGUP_SAMPLES=1",), "bring-up host")):
        path, err = build(kind, scens, bdir, extra, "_bring" if extra else "")
        if not rep.check("build %s" % label, err is None, err or ""):
            continue
        for i, sc in enumerate(scens):
            if "host" not in sc["kinds"] and "bring" not in sc["kinds"]:
                continue
            lines, err = run_prog("host", path, i)
            model, outs, done = parse_output(lines or [])
            if not rep.check("%s %s: program ran to DONE" % (label, sc["name"]), done and err is None, str(err)):
                continue
            evaluate(sc, outs, ref, rep, model)
    if not a.no_sim16:
        sims = [sc for sc in SCEN if "sim" in sc["kinds"]]
        sims.sort(key=lambda s: s["name"] != "stream_window")   # first: it needs the power-on default reject / stream off
        path, err = build("avr", sims, bdir, (), "_sim16")
        if rep.check("build sim16", err is None, err or ""):
            lines, err = run_prog("avr", path)
            model, outs, done = parse_output(lines or [])
            if rep.check("sim16: program ran to DONE", done and err is None, str(err)):
                for sc in sims:
                    print("-- sim16 %s" % sc["name"])
                    evaluate(sc, outs, ref, rep, model)
    print("%d checks, %d failed" % (rep.n, rep.fails))
    if rep.fails == 0:
        print("gesture suite PASS")
        return 0
    print("gesture suite FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
