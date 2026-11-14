# [AI-GENERATED: Claude Code]
"""Integer reference inference, bit-exact with the firmware (contracts C4 and C5).

Pipeline: normalize -> layer1 (acc1, h) -> layer2 (logits) -> top2 (top1, margin) -> MLP
confidence, then the C5 k-NN gates and decision.  Every stage is a separate public function so
a test vector can localise a mismatch to one stage.

INTEGERS ONLY: no float or true division anywhere in the inference path (selftest enforces it
for the model arithmetic by construction; only `//` and shifts on ints are used).

Sources: our own executable spec docs/agent/hadi/spikes/quant/quant_ref.py (rshift_r, sat,
requant_big/requant_split, top2, classify_ref, class_radius, l1 are promoted from it), the
C4/C5 text in docs/agent/CONTRACTS.md, and the quantization scheme of Jacob et al., 2018,
"Quantization and Training of Neural Networks for Efficient Integer-Arithmetic-Only
Inference", arXiv:1712.05877 (int8 weights in [-127,127], int32 bias, fixed-point multiplier
M = M0 * 2^-n).

Usage:  python3 tools/infer_ref.py --selftest
"""
import ast
import re
import struct
import sys
import zlib

# C5 provisional constants (docs/agent/CONTRACTS.md C5.1; mirrored from firmware gesture.h)
GESTURE_OVERRIDE_CONF = 192
GESTURE_KNN_RADIUS_MIN = 600
GESTURE_KNN_RADIUS_DEFAULT = 1200
GESTURE_KNN_RADIUS_MAX = 4000
GESTURE_UNKNOWN = -1

_I32_MIN = -(1 << 31)
_I32_MAX = (1 << 31) - 1

# header array name -> (C type, signed bytes struct code, lo, hi); file order is the hash order
ARRAY_ORDER = [
    ("GM_IN_OFF", "<h", -(1 << 15), (1 << 15) - 1),
    ("GM_IN_SH", "<B", 0, 255),
    ("GM_W1", "<b", -128, 127),
    ("GM_B1", "<i", _I32_MIN, _I32_MAX),
    ("GM_M1", "<H", 0, 65535),
    ("GM_SH1", "<B", 0, 255),
    ("GM_W2", "<b", -128, 127),
    ("GM_B2", "<i", _I32_MIN, _I32_MAX),
]


# --------------------------------------------------------------------------- primitives
def rshift_r(v, s):
    """Round-half-up arithmetic right shift, RSHIFT_R(v, s) = (v + (1 << s >> 1)) >> s.

    Args: v (int) value; s (int) shift in 0..14 (firmware limit). Python >> floors like XC16 asr.
    Returns: int.
    """
    assert 0 <= s <= 14, "shift out of 0..14: %r" % (s,)
    return (v + ((1 << s) >> 1)) >> s


def rshift_r64(p, s):
    """Rounding shift on the exact (unbounded) product: (p + 2^(s-1)) >> s.

    Args: p (int) exact product acc*M; s (int) shift, >= 1. Returns: int.
    """
    assert s >= 1
    return (p + (1 << (s - 1))) >> s


def sat(v, lo, hi):
    """Clamp v to [lo, hi]. Args: v, lo, hi (ints). Returns: int."""
    return lo if v < lo else hi if v > hi else v


def requant_split(acc, m, sh):
    """int64-free requantisation mirroring the firmware C `gm_requant` (C4 section 2).

    Args: acc (int32), m (uint16, 2^14..2^15-1), sh (16..31). Returns: int in 0..127. Used by the
    selftest to prove it equals the normative layer-1 math; layer1() itself uses the exact form.
    """
    assert 16 <= sh <= 31 and (1 << 14) <= m < (1 << 15) and _I32_MIN <= acc <= _I32_MAX
    hi = acc >> 16
    lo = acc & 0xFFFF
    a = hi * m
    c = lo * m + (1 << (sh - 1))
    assert _I32_MIN <= a <= _I32_MAX and 0 <= c < (1 << 32)
    t = a + (c >> 16)
    assert _I32_MIN <= t <= _I32_MAX
    return sat(t >> (sh - 16), 0, 127)


# --------------------------------------------------------------------------- header parsing
_SUFFIX = re.compile(r"([0-9A-Fa-f])[uUlL]+(?![A-Za-z0-9_])")
_SAFE_EXPR = re.compile(r"^[0-9A-Fa-fxX+\-*() \t,\[\]]*$")


def _c_int_expr(text):
    """Evaluate a C integer constant expression made of literals, + - * and parentheses.

    Args: text (str) such as '0x1A2Bu', '(-2147483647L - 1L)'. Returns: int. Raises ValueError.
    """
    t = _SUFFIX.sub(r"\1", text.strip())
    if not t or not _SAFE_EXPR.match(t):
        raise ValueError("unsupported constant expression: %r" % text)
    return eval(t, {"__builtins__": {}}, {})  # restricted charset checked above


def _strip_comments(src):
    """Remove /* */ and // comments. Args: src (str). Returns: str."""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def _flatten(x):
    """Row-major flatten of a nested list of ints. Args: x (list). Returns: list[int]."""
    out = []
    for e in x:
        out.extend(_flatten(e) if isinstance(e, list) else [e])
    return out


def model_hash(m):
    """CRC-32 (IEEE) over the little-endian bytes of all arrays in file order (C4.3).

    Args: m (dict as returned by load_header; only the GM_* arrays are used).
    Returns: int uint32.
    """
    crc = 0
    for name, code, _lo, _hi in ARRAY_ORDER:
        crc = zlib.crc32(b"".join(struct.pack(code, v) for v in _flatten(m[name])), crc)
    return crc & 0xFFFFFFFF


def parse_header(text):
    """Parse the text of a generated gesture_model.h into a dict.

    Args: text (str) header source. Returns: dict with every numeric `#define GM_*` macro
    (key = macro name, value = int) and every `static const` array (key = array name, value =
    nested list of ints, shape checked against its declared dimensions and element range).
    Raises ValueError on a malformed file, out-of-range element, shape mismatch or when
    GM_MODEL_HASH does not match the arrays.
    """
    src = _strip_comments(text)
    m = {}
    for name, val in re.findall(r"^[ \t]*#[ \t]*define[ \t]+(\w+)[ \t]+([^\n]+)$", src, flags=re.M):
        try:
            m[name] = _c_int_expr(val)
        except (ValueError, SyntaxError):
            pass  # non-numeric macro (e.g. GM_STATIC_ASSERT body); not needed
    ranges = {n: (lo, hi) for n, _c, lo, hi in ARRAY_ORDER}
    decl = re.compile(r"static\s+const\s+\w+\s+(GM_\w+)\s*((?:\[[^\]]*\]\s*)+)=\s*(\{.*?\})\s*;", re.S)
    for name, dims, body in decl.findall(src):
        shape = [_c_int_expr(re.sub(r"\b(GM_\w+)\b", lambda g: str(m[g.group(1)]), d))
                 for d in re.findall(r"\[([^\]]*)\]", dims)]
        val = ast.literal_eval(_SUFFIX.sub(r"\1", _expand_exprs(body)).replace("{", "[").replace("}", "]"))
        sh = []
        x = val
        while isinstance(x, list):
            sh.append(len(x))
            x = x[0] if x else None
        if sh != shape:
            raise ValueError("%s: shape %s != declared %s" % (name, sh, shape))
        lo, hi = ranges.get(name, (_I32_MIN, _I32_MAX))
        for v in _flatten(val):
            if not lo <= v <= hi:
                raise ValueError("%s: element %d outside [%d, %d]" % (name, v, lo, hi))
        m[name] = val
    for name, _c, _lo, _hi in ARRAY_ORDER:
        if name not in m:
            raise ValueError("array %s missing" % name)
    if "GM_MODEL_HASH" not in m:
        raise ValueError("GM_MODEL_HASH missing")
    if model_hash(m) != m["GM_MODEL_HASH"]:
        raise ValueError("GM_MODEL_HASH 0x%08X does not match arrays (CRC 0x%08X)"
                         % (m["GM_MODEL_HASH"], model_hash(m)))
    return m


def _expand_exprs(body):
    """Replace parenthesised constant expressions like (-2147483647L - 1L) inside an array body
    by their integer value so ast.literal_eval can read the body. Args: body (str). Returns: str."""
    def one(g):
        return str(_c_int_expr(_SUFFIX.sub(r"\1", g.group(0))))
    return re.sub(r"\([^()]*\)", one, body)


def load_header(path):
    """Parse a generated gesture_model.h file (macros and arrays).

    Args: path (str) file path. Returns: dict as parse_header (macros and arrays keyed by their C
    names, e.g. m['GM_W1'][j][i], m['GM_CONF_SHIFT']). Raises ValueError on a bad file.
    """
    with open(path, "r") as f:
        return parse_header(f.read())


# --------------------------------------------------------------------------- stages
def normalize(feat, m):
    """C4 stage 0: x8[i] = SAT(RSHIFT_R((int32)x - GM_IN_OFF[i], GM_IN_SH[i]), -127, 127).

    Args: feat (sequence of GM_N_FEATURES int16 features); m (model dict). Returns: list[int]
    of int8 values in [-127, 127].
    """
    off, sh = m["GM_IN_OFF"], m["GM_IN_SH"]
    if len(feat) != len(off):
        raise ValueError("feature length %d != %d" % (len(feat), len(off)))
    out = []
    for x, o, s in zip(feat, off, sh):
        x = int(x)
        if not -32768 <= x <= 32767:
            raise ValueError("feature %d is not int16" % x)
        out.append(sat(rshift_r(x - int(o), int(s)), -127, 127))
    return out


def layer1(x8, m):
    """C4 layer 1: acc1[j] = B1[j] + sum_i W1[j][i]*x8[i]; h[j] = SAT(RSHIFT_R64(acc1*M1, SH1), 0, 127).

    Args: x8 (list[int] int8 inputs); m (model dict). Returns: (acc1, h), two lists of ints
    (acc1 int32, h in 0..127). Raises OverflowError if an accumulator leaves int32.
    """
    acc1, h = [], []
    for row, b, mm, s in zip(m["GM_W1"], m["GM_B1"], m["GM_M1"], m["GM_SH1"]):
        a = int(b) + sum(int(w) * int(x) for w, x in zip(row, x8))
        if not _I32_MIN <= a <= _I32_MAX:
            raise OverflowError("acc1 %d leaves int32" % a)
        acc1.append(a)
        h.append(sat(rshift_r64(a * int(mm), int(s)), 0, 127))
    return acc1, h


def layer2(h, m):
    """C4 layer 2: logit[c] = B2[c] + sum_j W2[c][j]*h[j] (int32, no requant, no clamp).

    Args: h (list[int] hidden activations 0..127); m (model dict). Returns: list[int] logits.
    Raises OverflowError if a logit leaves int32.
    """
    out = []
    for row, b in zip(m["GM_W2"], m["GM_B2"]):
        a = int(b) + sum(int(w) * int(x) for w, x in zip(row, h))
        if not _I32_MIN <= a <= _I32_MAX:
            raise OverflowError("logit %d leaves int32" % a)
        out.append(a)
    return out


def top2_idx(logits):
    """Argmax (lowest index on ties) and runner-up index (largest among c != top1, lowest index on ties).

    Args: logits (list[int], >= 2 entries). Returns: (i1, i2).
    """
    i1 = 0
    for i in range(1, len(logits)):
        if logits[i] > logits[i1]:
            i1 = i
    i2 = 1 if i1 == 0 else 0
    for i in range(len(logits)):
        if i != i1 and logits[i] > logits[i2]:
            i2 = i
    return i1, i2


def top2(logits):
    """C4 argmax and margin.

    Args: logits (list[int], >= 2 entries). Returns: (top1, margin) with top1 the lowest index of
    the maximum logit and margin = logit[top1] - logit[top2] >= 0.
    """
    i1, i2 = top2_idx(logits)
    return i1, logits[i1] - logits[i2]


def mlp_conf(margin, conf_shift):
    """C5 MLP confidence: min(255, margin >> GM_CONF_SHIFT).

    Args: margin (int >= 0); conf_shift (int, GM_CONF_SHIFT). Returns: int in 0..255.
    """
    assert margin >= 0 and 0 <= conf_shift <= 24
    return min(255, margin >> conf_shift)


def forward(feat, m):
    """Run every stage and keep every intermediate.

    Args: feat (GM_N_FEATURES int16 features); m (model dict from load_header).
    Returns: dict with keys x8, acc1, h, logits, top1, margin, conf.
    """
    x8 = normalize(feat, m)
    acc1, h = layer1(x8, m)
    logits = layer2(h, m)
    t1, margin = top2(logits)
    return {"x8": x8, "acc1": acc1, "h": h, "logits": logits, "top1": t1,
            "margin": margin, "conf": mlp_conf(margin, m["GM_CONF_SHIFT"])}


# --------------------------------------------------------------------------- C5
def knn_l1(a, b):
    """L1 distance of two int8 vectors (max 60*254 = 15240). Args: a, b (equal-length lists). Returns: int."""
    assert len(a) == len(b)
    return sum(abs(int(x) - int(y)) for x, y in zip(a, b))


def class_radius(templates, rmin=GESTURE_KNN_RADIUS_MIN, rdef=GESTURE_KNN_RADIUS_DEFAULT,
                 rmax=GESTURE_KNN_RADIUS_MAX):
    """C5 per-class acceptance radius: clamp(2 * lower_median(pairwise L1), rmin, rmax).

    Args: templates (list of x8 vectors of ONE class); rmin, rdef, rmax (provisional constants).
    Returns: int; rdef when fewer than 2 templates. lower_median of the sorted n(n-1)/2 pairwise
    distances is element (k-1)//2.
    """
    if len(templates) < 2:
        return rdef
    d = sorted(knn_l1(templates[i], templates[j])
               for i in range(len(templates)) for j in range(i + 1, len(templates)))
    return sat(2 * d[(len(d) - 1) // 2], rmin, rmax)


def knn_query(x8, store):
    """C5 k-NN gate inputs.

    Args: x8 (list[int] window vector); store ({class_id: [template, ...]}; slot order within a
    class is preserved; classes are scanned in ascending class id, so an exact distance tie goes to
    the lowest class id then lowest slot).
    Returns: None when the store holds no template; else dict with kid (class of the nearest
    template), d1 (its L1 distance), d2 (nearest distance among templates of other classes, or
    None), has_other (bool), c_k (0..255: 255 if no other-class template, 0 if d2 == 0, else
    (d2-d1)*255 // d2), radius (class_radius of class kid).
    """
    best = None
    flat = []
    for cid in sorted(store):
        for t in store[cid]:
            d = knn_l1(x8, t)
            flat.append((cid, d))
            if best is None or d < best[1]:
                best = (cid, d)
    if best is None:
        return None
    kid, d1 = best
    others = [d for cid, d in flat if cid != kid]
    d2 = min(others) if others else None
    c_k = 255 if d2 is None else (0 if d2 == 0 else ((d2 - d1) * 255) // d2)
    return {"kid": kid, "d1": d1, "d2": d2, "has_other": d2 is not None, "c_k": c_k,
            "radius": class_radius(store[kid])}


def classify_decide(top1, margin, conf_shift, knn, min_conf, t_ovr=GESTURE_OVERRIDE_CONF):
    """C5 normative decision (steps 1, 2, 4).

    Args: top1 (int MLP class); margin (int >= 0); conf_shift (GM_CONF_SHIFT); knn (dict from
    knn_query or None); min_conf (0..255, reject iff conf < min_conf); t_ovr (override threshold,
    GESTURE_OVERRIDE_CONF). Returns: (id, conf); id is GESTURE_UNKNOWN (-1) when rejected, conf is
    always the winning score (also when rejected).
    """
    gid, c = top1, mlp_conf(margin, conf_shift)
    if knn is not None:
        weak = (gid == 0) or (c < min_conf) or (c < t_ovr)
        if weak and knn["d1"] <= knn["radius"] and knn["c_k"] >= min_conf:
            gid, c = knn["kid"], knn["c_k"]
    return (gid if c >= min_conf else GESTURE_UNKNOWN), c


# --------------------------------------------------------------------------- selftest
def _tiny_model():
    """Hand-built 2-feature, 2-hidden, 3-class model for stage checks. Returns: model dict."""
    return {"GM_IN_OFF": [10, 0], "GM_IN_SH": [2, 0],
            "GM_W1": [[1, 2], [-1, 0]], "GM_B1": [5, 0],
            "GM_M1": [16384, 16384], "GM_SH1": [16, 16],
            "GM_W2": [[1, 1], [2, 0], [0, 3]], "GM_B2": [0, 0, 0], "GM_CONF_SHIFT": 0}


def selftest():
    """Run the C5 section 2 vector table, stage checks and requant checks. Raises AssertionError on
    any failure; prints 'infer_ref selftest PASS' on success. Returns: None."""
    import random

    # rshift_r edge values against floor division
    for s in range(15):
        for v in (-(1 << 17), -65535, -1, 0, 1, 255, 65535, 1 << 17):
            assert rshift_r(v, s) == (v + ((1 << s) >> 1)) // (1 << s)
    assert rshift_r(-5, 0) == -5 and rshift_r(2, 2) == 1 and rshift_r(-2, 2) == 0

    # requant: split (firmware C form) == exact bigint form, corners then random
    rnd = random.Random(1)
    corners = [0, 1, -1, 65535, 65536, 65537, -65535, -65536, -65537, 2**31 - 1, -2**31, 2**30, -2**30]
    for acc in corners:
        for mm in (1 << 14, (1 << 14) + 1, (1 << 15) - 1, 29100):
            for sh in range(16, 32):
                assert requant_split(acc, mm, sh) == sat(rshift_r64(acc * mm, sh), 0, 127), (acc, mm, sh)
    for _ in range(50000):
        acc = rnd.randrange(-(1 << 31), 1 << 31) if rnd.random() < 0.5 else rnd.randrange(-(1 << 28), 1 << 28)
        mm = rnd.randrange(1 << 14, 1 << 15)
        sh = rnd.randrange(16, 32)
        assert requant_split(acc, mm, sh) == sat(rshift_r64(acc * mm, sh), 0, 127), (acc, mm, sh)

    # stage checks on a tiny model (hand computed)
    m = _tiny_model()
    assert normalize([50, 200], m) == [10, 127] and normalize([-1000, -200], m) == [-127, -127]
    acc1, h = layer1([10, 127], m)
    assert acc1 == [269, -10] and h == [67, 0], (acc1, h)
    assert layer2(h, m) == [67, 134, 0]
    assert top2([67, 134, 0]) == (1, 67) and top2([5, 5, 3]) == (0, 0) and top2([1, 5, 5]) == (1, 0)
    assert top2_idx([5, 5, 3]) == (0, 1) and top2_idx([1, 5, 5]) == (1, 2)
    f = forward([50, 200], m)
    assert (f["x8"], f["acc1"], f["h"], f["logits"], f["top1"], f["margin"], f["conf"]) == \
        ([10, 127], [269, -10], [67, 0], [67, 134, 0], 1, 67, 67)
    assert mlp_conf(900, 1) == 255 and mlp_conf(300, 1) == 150 and mlp_conf(0, 24) == 0

    # C5 section 2 vector table
    x8 = [10] * 60
    far = [-100] * 60

    def lg(margin):
        return [0, 0, 0, margin, 0, 0, 0, 0, 0]

    def run(x, logits, store, min_conf, shift):
        t1, mg = top2(logits)
        return classify_decide(t1, mg, shift, knn_query(x, store), min_conf)

    S = {9: [[10] * 59 + [14]]}                                    # one learned class, d1 = 4
    q = knn_query(x8, S)
    assert q == {"kid": 9, "d1": 4, "d2": None, "has_other": False, "c_k": 255, "radius": 1200}
    assert run(x8, lg(900), S, 64, 1) == (3, 255)                  # confident built-in: MLP wins
    assert run(x8, lg(200), S, 64, 1) == (9, 255)                  # weak MLP (100 < 192)
    assert run(x8, [900] + [0] * 8, S, 64, 1) == (9, 255)          # MLP class 0
    assert run(x8, lg(60), S, 64, 1) == (9, 255)                   # MLP rejected (30 < 64)
    assert run(far, lg(60), S, 64, 1) == (-1, 30)                  # outside radius, rejected
    assert run(far, lg(900), S, 64, 1) == (3, 255)                 # outside radius, confident
    assert run(x8, [7] * 9, {}, 1, 0) == (-1, 0)                   # tie -> margin 0 -> UNKNOWN
    assert run(x8, [7] * 9, {}, 0, 0) == (0, 0)                    # min_conf 0 disables reject
    S2 = {9: [[10] * 59 + [14]], 10: [[10] * 56 + [20] * 4]}       # d1 = 4, d2 = 40
    assert knn_query(x8, S2)["d2"] == 40
    assert run(x8, lg(0), S2, 64, 1) == (9, (36 * 255) // 40) == (9, 229)
    # boundaries for min_conf in {0, default, 255}
    assert run(x8, lg(900), S, 0, 1) == (3, 255) and run(x8, lg(900), S, 255, 1) == (3, 255)
    assert run(x8, lg(500), S, 255, 1) == (9, 255)                 # conf 250 < 255 -> weak, kNN 255 >= 255
    assert run(far, lg(500), S, 255, 1) == (-1, 250)               # rejected at the boundary
    assert classify_decide(3, 130, 1, None, 65) == (3, 65) and classify_decide(3, 128, 1, None, 65) == (-1, 64)
    # radius rule and exact-tie order (lowest class id, then slot)
    assert class_radius([x8]) == 1200 and class_radius([x8, x8, x8]) == 600
    assert class_radius([x8, [10] * 59 + [200]]) == 600
    assert class_radius([x8, [10] * 56 + [110] * 4]) == 800
    assert class_radius([x8, x8, [10] * 56 + [110] * 4]) == 800     # lower median (idx 1) of {0, 400, 400}
    assert knn_query(x8, {12: [x8], 9: [x8]})["kid"] == 9
    assert knn_query(x8, {9: []}) is None
    # d2 == 0 -> c_k 0
    assert knn_query(x8, {9: [x8], 10: [x8]})["c_k"] == 0
    print("infer_ref selftest PASS")


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        selftest()
    else:
        print(__doc__)
        sys.exit(2)
# [END AI-GENERATED]
