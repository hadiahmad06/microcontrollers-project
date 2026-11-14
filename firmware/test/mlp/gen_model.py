#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""gen_model.py SEED OUT.h - write a random VALID gesture_model.h (C4 section 2 layout, real dims
60/16/9), a JSON sidecar OUT.json with the arrays for the oracle, and edge_vectors.h (next to
OUT.h) with the model-dependent edge feature vectors for the C driver. Standard library only.
SEED % 5 picks the variant: 0 general, 1 tie (logits tie), 2 negb1 (every B1 < 0),
3 corners (M1/SH1/weights at their limits, huge biases), 4 mid (h mostly in the interior)."""
import json
import os
import random
import struct
import sys
import zlib

NF, NH, NC = 60, 16, 9
VARIANTS = ["general", "tie", "negb1", "corners", "mid"]
LIM29, LIM30 = 1 << 29, 1 << 30


def check_bounds(m):
    """Assert the exporter bounds of C4 section 2. Args: m: model dict. Returns: None."""
    assert all(abs(b) < LIM29 for b in m["b1"]) and all(abs(b) < LIM29 for b in m["b2"])
    for j in range(NH):
        assert abs(m["b1"][j]) + 127 * sum(abs(w) for w in m["w1"][j]) < LIM30
    for c in range(NC):
        assert abs(m["b2"][c]) + 127 * sum(abs(w) for w in m["w2"][c]) < LIM30
    assert all(-127 <= w <= 127 for r in m["w1"] + m["w2"] for w in r)
    assert all(16384 <= v < 32768 for v in m["m1"])
    assert all(16 <= v <= 31 for v in m["sh1"])
    assert all(0 <= v <= 14 for v in m["in_sh"])
    assert all(-32768 <= v <= 32767 for v in m["in_off"])


def rnd_weight(r):
    """Random int8 weight in [-127,127] with extra mass on 0 and +-127. Args: r: Random."""
    p = r.random()
    if p < 0.08:
        return r.choice([-127, 127])
    if p < 0.18:
        return 0
    return r.randint(-127, 127)


def make_model(seed):
    """Build a random valid model dict. Args: seed: int. Returns: model dict."""
    r = random.Random(seed * 7919 + 13)
    var = VARIANTS[seed % 5]
    in_off = [-32768, 32767, 0] + [r.randint(-32768, 32767) for _ in range(NF - 3)]
    for i in range(3, NF, 7):
        in_off[i] = r.randint(-300, 300)
    sh = [i % 15 for i in range(NF)]
    r.shuffle(sh)
    sh[0], sh[1] = 14, 0   # feature 0: off=-32768, sh 14; feature 1: off=32767, sh 0
    sh[2], sh[3] = 0, 14   # and both extremes again, with a random offset feature
    w1 = [[rnd_weight(r) for _ in range(NF)] for _ in range(NH)]
    w2 = [[rnd_weight(r) for _ in range(NH)] for _ in range(NC)]
    b1, b2, m1, sh1 = [], [], [], []
    for j in range(NH):
        kind = r.choice([0, 0, 1, 2]) if var in ("general", "negb1") else 0
        if var == "corners":
            w1[j] = [r.choice([-127, 127]) for _ in range(NF)]
            kind = 2 if j % 4 == 0 else 0
        v = r.randint(-5000, 5000) if kind == 0 else r.randint(-(1 << 20), 1 << 20)
        if kind == 2:
            v = r.choice([-1, 1]) * (LIM29 - 1 - r.randint(0, 3))
        if var == "negb1":
            v = -abs(v) - 1
        b1.append(v)
        if var == "corners":
            m1.append([16384, 32767][j % 2])
            sh1.append([16, 31, 17, 30][(j // 2) % 4])
        else:
            m1.append(r.choice([16384, 32767, r.randint(16384, 32767)]))
            if var == "tie":
                sh1.append(r.randint(16, 28))
            elif var == "mid":
                sh1.append(r.randint(22, 29))
            else:
                sh1.append(r.choice([16, 31, r.randint(16, 31)]))
    for c in range(NC):
        if var == "corners":
            b2.append((1 if c % 2 == 0 else -1) * (LIM29 - 1 - c))
        elif var == "mid":
            b2.append(r.randint(-300, 300))
        else:
            b2.append(r.randint(-5000, 5000) if r.random() < 0.8 else r.randint(-(1 << 25), 1 << 25))
    if var == "tie":
        # Classes 2 and 5 identical; every other row < row 2 elementwise with the same bias, so
        # with h >= 0 the maximum logit is shared by 2 and 5 (or by all, when h == 0).
        base = [r.randint(-100, 127) for _ in range(NH)]
        bias = r.randint(-5000, 5000)
        for c in range(NC):
            w2[c] = list(base) if c in (2, 5) else [w - r.randint(1, 27) for w in base]
            b2[c] = bias
    m = {"variant": var, "seed": seed, "in_off": in_off, "in_sh": sh, "w1": w1, "b1": b1,
         "m1": m1, "sh1": sh1, "w2": w2, "b2": b2}
    check_bounds(m)
    m["info"] = {"format_version": 1, "feature_version": 1 + seed % 3,
                 "odr_hz": [100, 50, 200][seed % 3], "range_g": [4, 2, 8][seed % 3],
                 "conf_shift": 4 + seed % 5, "default_reject": 32 + 7 * (seed % 9),
                 "n_samples": 150, "logit_scale_q32": 429497}
    return m


def model_bytes(m):
    """Little-endian bytes of all arrays in header file order. Args: m. Returns: bytes."""
    out = b"".join(struct.pack("<h", v) for v in m["in_off"])
    out += bytes(m["in_sh"])
    out += b"".join(struct.pack("<b", w) for row in m["w1"] for w in row)
    out += b"".join(struct.pack("<i", v) for v in m["b1"])
    out += b"".join(struct.pack("<H", v) for v in m["m1"])
    out += bytes(m["sh1"])
    out += b"".join(struct.pack("<b", w) for row in m["w2"] for w in row)
    out += b"".join(struct.pack("<i", v) for v in m["b2"])
    return out


def lit32(v):
    """Portable int32 literal for a 16-bit-int compiler. Args: v: int. Returns: C text."""
    return "(-2147483647L-1L)" if v == -(1 << 31) else "%dL" % v


def lit16(v):
    """int16 literal (avoids a bare -32768). Args: v: int. Returns: C text."""
    return "(-32767-1)" if v == -32768 else "%d" % v


def arr1(name, typ, dim, vals, fmt):
    """One 1-D const array definition. Args: name, typ: C type, dim: size macro, vals, fmt."""
    return "static const %s %s[%s] = { %s };\n" % (typ, name, dim, ", ".join(fmt(v) for v in vals))


def arr2(name, typ, d1, d2, rows):
    """One 2-D const int8 array definition. Args: name, typ, d1, d2: size macros, rows."""
    body = ",\n".join("  { " + ", ".join(str(w) for w in row) + " }" for row in rows)
    return "static const %s %s[%s][%s] = {\n%s\n};\n" % (typ, name, d1, d2, body)


def write_header(m, path):
    """Write gesture_model.h. Args: m: model dict with m['hash']; path: output file."""
    i = m["info"]
    s = "/* gesture_model.h : GENERATED by gen_model.py (test model). DO NOT EDIT. */\n"
    s += "// [AI-GENERATED: Claude Code]\n#ifndef GESTURE_MODEL_H\n#define GESTURE_MODEL_H\n"
    s += "#include <stdint.h>\n\n"
    s += "#define GM_FORMAT_VERSION   %du\n#define GM_N_FEATURES       60u\n" % i["format_version"]
    s += "#define GM_N_HIDDEN         16u\n#define GM_N_CLASSES        9u\n"
    s += "#define GM_ODR_HZ           %du\n#define GM_RANGE_G          %du\n" % (i["odr_hz"], i["range_g"])
    s += "#define GM_N_SAMPLES        %du\n#define GM_FEATURE_VERSION  %du\n" % (i["n_samples"], i["feature_version"])
    s += "#define GM_MODEL_HASH       0x%08Xu\n" % m["hash"]
    s += "#define GM_CONF_SHIFT       %du\n#define GM_DEFAULT_REJECT   %du\n" % (i["conf_shift"], i["default_reject"])
    s += "#define GM_LOGIT_SCALE_Q32  %du\n\n" % i["logit_scale_q32"]
    s += "#define GM_STATIC_ASSERT(c, name) typedef char gm_sa_##name[(c) ? 1 : -1]\n"
    s += "GM_STATIC_ASSERT(GM_N_CLASSES <= 16u, classes);\n\n"
    s += arr1("GM_IN_OFF", "int16_t", "GM_N_FEATURES", m["in_off"], lit16)
    s += arr1("GM_IN_SH", "uint8_t", "GM_N_FEATURES", m["in_sh"], str)
    s += arr2("GM_W1", "int8_t", "GM_N_HIDDEN", "GM_N_FEATURES", m["w1"])
    s += arr1("GM_B1", "int32_t", "GM_N_HIDDEN", m["b1"], lit32)
    s += arr1("GM_M1", "uint16_t", "GM_N_HIDDEN", m["m1"], lambda v: "%du" % v)
    s += arr1("GM_SH1", "uint8_t", "GM_N_HIDDEN", m["sh1"], str)
    s += arr2("GM_W2", "int8_t", "GM_N_CLASSES", "GM_N_HIDDEN", m["w2"])
    s += arr1("GM_B2", "int32_t", "GM_N_CLASSES", m["b2"], lit32)
    s += "\n#endif\n// [END AI-GENERATED]\n"
    with open(path, "w") as f:
        f.write(s)


def edge_vectors(m):
    """Model-dependent edge feature vectors (all int16). Args: m. Returns: list of 60-lists.

    Covers: extremes, x==off (x8=0), maximal |d| both signs (d=+-65535 on features 0/1),
    RSHIFT_R ties and neighbours (d = +-2^(s-1) +-1), and x8 saturation boundaries."""
    off, shv = m["in_off"], m["in_sh"]

    def build(dfun):
        return [max(-32768, min(32767, off[i] + dfun(shv[i], (1 << shv[i]) >> 1)))
                for i in range(NF)]
    v = [[32767] * NF, [-32768] * NF, list(off), [0] * NF,
         [32767 if k % 2 == 0 else -32768 for k in range(NF)],
         [32767 if o < 0 else -32768 for o in off],
         [-32768 if o < 0 else 32767 for o in off]]
    for k in (1, -1):
        v.append(build(lambda s, h, k=k: k * (h if s else 1)))              # tie d = +-2^(s-1)
        v.append(build(lambda s, h, k=k: k * (h if s else 1) - 1))
        v.append(build(lambda s, h, k=k: k * (h if s else 1) + 1))
        v.append(build(lambda s, h, k=k: k * ((127 << s) - 1)))
        v.append(build(lambda s, h, k=k: k * (127 << s)))
        v.append(build(lambda s, h, k=k: k * ((127 << s) + h)))             # 127.5 -> 128 -> sat
        v.append(build(lambda s, h, k=k: k * ((127 << s) + h - 1)))
        v.append(build(lambda s, h, k=k: k * (128 << s)))
    return v


def write_edge(m, path):
    """Write edge_vectors.h for driver.c. Args: m: model dict; path: output file.
    Returns: the edge vectors."""
    ev = edge_vectors(m)
    s = "// [AI-GENERATED: Claude Code]\n#ifndef EDGE_VECTORS_H\n#define EDGE_VECTORS_H\n#include <stdint.h>\n"
    s += "#define EDGE_N %du\n" % len(ev)
    s += "static const int16_t VEC_OFF[60] = { %s };\n" % ", ".join(lit16(v) for v in m["in_off"])
    s += "static const uint8_t VEC_SH[60] = { %s };\n" % ", ".join(str(v) for v in m["in_sh"])
    s += "static const int16_t EDGE_VEC[EDGE_N][60] = {\n"
    s += ",\n".join("  { " + ", ".join(lit16(x) for x in row) + " }" for row in ev) + "\n};\n"
    s += "#endif\n// [END AI-GENERATED]\n"
    with open(path, "w") as f:
        f.write(s)
    return ev


def main(argv):
    """CLI: gen_model.py SEED OUT.h. Returns: process exit code."""
    if len(argv) != 3:
        print(__doc__)
        return 2
    seed, out = int(argv[1]), argv[2]
    m = make_model(seed)
    m["hash"] = zlib.crc32(model_bytes(m)) & 0xFFFFFFFF
    write_header(m, out)
    d = os.path.dirname(out) or "."
    m["edge"] = write_edge(m, os.path.join(d, "edge_vectors.h"))
    with open(os.path.splitext(out)[0] + ".json", "w") as f:
        json.dump(m, f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
# [END AI-GENERATED]
