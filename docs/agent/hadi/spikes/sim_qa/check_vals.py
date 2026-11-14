# [AI-GENERATED: Claude Code]
"""Host-side oracle for vals.c. Reads run_sim.sh output on stdin, compares, exits non-zero on mismatch."""
import re
import sys


def s16(x):
    """Wrap to signed 16-bit. Args: x int. Returns: int."""
    x &= 0xFFFF
    return x - 0x10000 if x & 0x8000 else x


EXPECT = {
    "v_i16_neg": -12345, "v_i16_min": -32768,
    "v_i32_neg": -2000000000, "v_i32_min": -2147483648,
    "v_u32_max": 4294967295, "v_u32_big": 3000000000,
    "v_u16_max": 65535, "v_i8_neg": -5,
    "r_nocast": s16(300 * 300),          # 16-bit multiply truncates: 24464
    "r_cast": 300 * 300,                 # 90000
    "result_done": 1,
}
FEAT = [s16(s16(i) * 1111 - 30000) for i in range(60)]

got = {}
for line in sys.stdin:
    m = re.match(r"^(\w+)=(.*)$", line.strip())
    if m:
        got[m.group(1)] = m.group(2)
bad = 0
for k, v in EXPECT.items():
    if k in got and int(got[k]) != v:
        print(f"MISMATCH {k}: sim={got[k]} expected={v}")
        bad += 1
if "feat" in got:
    arr = [int(t) for t in got["feat"].strip("{}").split(",")]
    if arr != FEAT:
        print("MISMATCH feat")
        bad += 1
print("check_vals: FAIL" if bad else f"check_vals: PASS ({len(got)} symbols checked)")
sys.exit(1 if bad else 0)
# [END AI-GENERATED]
