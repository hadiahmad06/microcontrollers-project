# C4 proposal: `gesture_model.h` format and quantization scheme

> Agent draft (research-quant) for `hadi`, ticket S1-3, revised 2026-11-14 after review S1-3R (`docs/agent/hadi/reviews/S1-3R.md`). **Not a decision.** Hadi decides; then it can go to `docs/agent/CONTRACTS.md` (AGENTS.md §5).
> Companion: `C5_classifier_output.md`. Executable spec and acceptance tests: `docs/agent/hadi/spikes/quant/quant_ref.py` (`/usr/local/bin/python3.12 quant_ref.py` prints `ALL PASS`; the other python3.12 on this Mac lacks numpy).
> Tags: **VERIFIED** = compiled/ran here (XC16 v2.10, numpy) or read in the local XC16 guide DS-50002071M; **UNVERIFIED** = not checked.

## 1. Decisions needed

**D1. Network input representation and training domain.** Features are 60 int16 (C3: even index = mean, signed; odd index = energy, non-negative).
- (a) *Per-feature offset + power-of-two shift -> int8*: `x8 = sat127(rshift_r(x - off_i, s_i))`. Cheap, exact in Python. 180 B flash (60 int16 + 60 uint8).
- (b) Per-feature fixed-point multiplier: 60 extra multiplies, 120 B more flash, at most 1 bit more range. Rejected.
- (c) Raw int16 into layer 1: scale gap between features crushes a per-tensor weight scale. Rejected.
- (d) As (a) but int16 output (+-2047). Same MUL cost, better precision, but k-NN must stay on int8 (otherwise 120 B/template breaks the PLAN §4 budget), and the layer-1 MAC must cast to int32 (127*2047 overflows int16).
RECOMMENDATION (needs Hadi's decision): **(a), and train the float model directly on x8** (Python: compute features with the C3 integer reference, apply the integer `normalize`, feed the resulting integers, optionally divided by a constant like 64 for conditioning, to the float net; the exporter multiplies W1 by that constant back). Then the exporter performs *no offset fold*, so the fold-sign bug class (review finding 1) cannot occur, `W1` is never inflated by `2^s_i`, and QAT/PTQ sees exactly what the firmware sees. Folding the normalization into W1/b1 (training on raw x) still works and is tested in `quant_ref.py::demo` (B, correct sign: `b1' = b1 + sum_i W1_i*off_i`, `W1' = W1*2^s_i`, because `x = off + 2^s*x8`), but it is worse: the per-tensor W1 scale spans up to `2^s` between features and the float model no longer matches the integer inputs (rounding of x8).
**Fallback to (d)** (decision rule, review finding 8): evaluate on a fixed held-out set of **n >= 500 windows**; fall back iff float-vs-int argmax **agreement < 97 %**, or (float accuracy - int accuracy > 1 pt **and** the one-sided 95 % Wilson upper bound of the int accuracy is below the float accuracy). Implemented as `fallback_needed()` in `quant_ref.py`.

**D1b. Energy normalization (works for whatever C3 picks).** C3's energy scaling is still moving (shift 6/7/8 vs an isqrt RMS feature, spike S1-2), so the rule is generic: the exporter gets a per-feature `nonneg` flag from C3 (energies true, means false).
- Non-negative feature: `off = 0` (x8 in 0..127; one bit unused, but low-energy resolution is kept). Signed feature: `off = round(median)`.
- Shift: `s_i = smallest s in 0..14 with rshift_r(P99.9(|x - off|), s) <= 127`. Values above the percentile saturate at 127 (not max-based: a single outlier must not set the scale, review finding 7).
- Open: if real small-motion energies sit at x8 of 0-2, ask C3 for a compressed (isqrt/log) energy; C4 needs no change (only the `nonneg` flag and the range matter).

**D2. Weight quantization granularity.** (a) per-tensor both layers; (b) per-output-channel multipliers for layer 1 (`GM_M1[16]`, `GM_SH1[16]`) and per-tensor layer 2; (c) per-channel layer 2 is **forbidden** (class logits would have different scales; argmax and margin would break).
RECOMMENDATION (needs Hadi's decision): **(b) as the format** (+48 B, no extra cycles); the exporter may emit equal entries. Weights symmetric int8 in **[-127,127]**, zero point 0. (The [-127,127] restriction is from Jacob et al. 2018 §3, training with simulated quantization; their stated reason is a "substantial optimization opportunity" for ARM NEON kernels, Appendix B, not an int16-product guarantee. For our 8x8 MAC it is just a convention that keeps the grid symmetric.)

**D3. Requantization arithmetic (int32 acc -> int8 activation).** (a) `(int64_t)acc*M`: XC16 emits `rcall ___muldi3` (**VERIFIED**; its cycle cost **UNVERIFIED**, assume 100-200, i.e. 2-3 k cycles for 16 neurons). (b) int64-free split multiply (below): **VERIFIED** bit-identical to (a) on 960 corner cases plus 200 k random in `quant_ref.py` (reviewer: 2 M random, no counterexample), XC16 `-O1 -Wall -Wconversion` compiles it warning-free to four `mul.*` and no library call, and the same C run on a host matches Python on 200 k vectors. (c) pre-shift to int16: lossy, rejected.
RECOMMENDATION (needs Hadi's decision): normative definition = (a)'s math; firmware may use (a) or (b) (proven equal). Ship (b) on target if profiling says requant matters. Exporter must **fail loudly** (never clamp) unless `2^14 <= M < 2^15` and `16 <= SH <= 31`, i.e. the real scale is in [2^-17, 0.5).

**D4. Activation range after ReLU:** int8 [0,127] (recommended) or uint8 [0,255].

**D5. Where arrays live:** `static const` in `gesture_model.h`, one includer (`mlp.c`); unreferenced `static const` is discarded (**VERIFIED**). Alternative: generated `.c` with extern declarations. RECOMMENDATION: static const header.

**D6. Consistency checks:** `GM_STATIC_ASSERT` at compile time; `gesture_init(odr_hz, range_g)` refuses on `odr_hz != GM_ODR_HZ || range_g != GM_RANGE_G` (FRAMEWORK_REVIEW T4); print `GM_MODEL_HASH` at boot.

## 2. Normative spec of the recommended option

`>>` is an arithmetic flooring shift (Python `>>`; XC16 `asr`, **VERIFIED**, DS-50002071M §23 "The sign is retained"). Never use C `/` on negatives.
```
RSHIFT_R(v, s) = (v + (((int32_t)1 << s) >> 1)) >> s      # s in 0..14 ONLY; s==0 -> v
SAT(v, lo, hi) = min(max(v, lo), hi)
```
Write the constant as `((int32_t)1 << s)`: with 16-bit `int`, `(1 << 15)` is negative (**VERIFIED** on XC16; review finding 5). The exporter asserts `GM_IN_SH[i] <= 14` (14 is never limiting: |x-off| <= 65535 needs s <= 9).

**Stage 0:** `d = (int32_t)x - (int32_t)GM_IN_OFF[i]` (a difference of int16 can exceed int16); `x8[i] = SAT(RSHIFT_R(d, GM_IN_SH[i]), -127, 127)`.

**Layer 1:** `acc1[j] = GM_B1[j] + sum_i (int32_t)GM_W1[j][i] * x8[i]` (cast both operands: `(int32_t)w * (int32_t)x`, or `(int16_t)w * (int16_t)x` stored to int32, safe because |w*x| <= 16129).
`h[j] = SAT(RSHIFT_R64(acc1[j]*GM_M1[j], GM_SH1[j]), 0, 127)` with `RSHIFT_R64(p, s) = (p + 2^(s-1)) >> s` on the exact product. ReLU = the lower clamp 0 after the floor shift (negative acc gives <= 0, clamped to 0).
**Split multiply, exact C** (valid for `2^14 <= m < 2^15`, `16 <= sh <= 31`):
```c
// [AI-GENERATED: Claude Code]
static int8_t gm_requant(int32_t acc, uint16_t m, uint8_t sh)
{
    int16_t  hi = (int16_t)(acc >> 16);                       /* arithmetic shift          */
    uint16_t lo = (uint16_t)acc;
    int32_t  a  = (int32_t)hi * (int32_t)m;                   /* |a| <= 2^30               */
    uint32_t c  = (uint32_t)lo * (uint32_t)m + ((uint32_t)1 << (sh - 1u));  /* < 2^32      */
    int32_t  r  = (a + (int32_t)(c >> 16)) >> (sh - 16u);
    return (int8_t)(r < 0 ? 0 : (r > 127 ? 127 : r));
}
// [END AI-GENERATED]
```
Without the casts, `hi*m` and `lo*m` are 16-bit multiplications that overflow on target only (review finding 6): a G3 on-target vector must include `|acc1| > 2^16` and `acc1 < 0` cases.

**Layer 2:** `logit[c] = GM_B2[c] + sum_j (int32_t)GM_W2[c][j] * h[j]` (int32, no requant, no clamp).
**Argmax:** smallest index with the maximum logit (strict `>` scan: lowest index wins). `top2`: largest among `c != top1`, lowest index on ties. `margin = logit[top1] - logit[top2] >= 0`.

**Exporter recipe (after training on x8):**
1. `off`, `sh` per D1b. 2. `s_w1 = max|W1|/127`; `W1q = rint(W1/s_w1)` (round-half-even); `B1 = rint(b1/s_w1)` (input scale is 1). 3. `s_h = P99.9(relu(W1 x8 + b1))/127` on calibration data. 4. `scale = s_w1/s_h`; `(M1,SH1) = mshift(scale)` per channel; **raise if scale not in [2^-17, 0.5)** or if rounding leaves `M == 2^15` at `SH == 16` (`mshift` in `quant_ref.py` does: search starts at SH=16; `M == 2^15` is halved and SH decremented only if it stays >= 16). 5. `s_w2 = max|W2|/127`; `W2q = rint(W2/s_w2)`; `B2 = rint(b2/(s_h*s_w2))`; `logit_scale = s_h*s_w2` (real value of one logit LSB).
6. **Bounds (assert, review finding 11):** `|B1[j]|,|B2[c]| < 2^29`; weight-only worst cases `|B1[j]| + 127*sum_i|W1[j][i]| < 2^30` and `|B2[c]| + 127*sum_j|W2[c][j]| < 2^30` (so no `acc` or `margin` can overflow int32 for any input); all weights in [-127,127]. `assert_bounds()` in `quant_ref.py`.

**Acceptance test (executable):** `quant_ref.py::demo`: 1500 calibration + 1000 test synthetic windows with non-zero per-feature means (+-1500) and heavy-tailed energies; random 60-16-9 net; **asserts float-vs-int argmax agreement >= 97 %** for both (A) float net on x8 and (B) raw-x net with the correct-sign fold, and asserts that the *wrong-sign* fold falls below 97 %. Measured here: **A 99.3 % (993/1000), B 98.8 %, wrong sign 83.0 %**. This is a random-weights stress test of the quantization path, not a measure of gesture accuracy.

**Header layout (dummy values; real model 60/16/9).**
```c
/* gesture_model.h : GENERATED by tools/export_model.py. DO NOT EDIT. */
// [AI-GENERATED: Claude Code]
#ifndef GESTURE_MODEL_H
#define GESTURE_MODEL_H
#include <stdint.h>

#define GM_FORMAT_VERSION   1u            /* layout of this file; bump on any change         */
#define GM_N_FEATURES       4u            /* real: 60                                        */
#define GM_N_HIDDEN         3u            /* real: 16                                        */
#define GM_N_CLASSES        2u            /* real: 9 (ids 0..8, see C5)                      */
#define GM_ODR_HZ           100u          /* sensor config the model was trained at          */
#define GM_RANGE_G          4u
#define GM_N_SAMPLES        150u          /* capture window length (C1)                      */
#define GM_FEATURE_VERSION  1u            /* C3 feature-definition version                   */
#define GM_MODEL_HASH       0x1A2B3C4Du   /* CRC-32 (IEEE) over the little-endian bytes of
                                             all arrays below, in file order                 */
#define GM_CONF_SHIFT       6u            /* C5: conf = min(255, margin >> GM_CONF_SHIFT)    */
#define GM_DEFAULT_REJECT   64u           /* C5: default min_conf                            */
#define GM_LOGIT_SCALE_Q32  429497u       /* info: real logit LSB * 2^32 (1e-4 -> 429497)    */

/* XC16 v2.10 is GCC 4.5-based: _Static_assert is NOT supported (VERIFIED); use this. */
#define GM_STATIC_ASSERT(c, name) typedef char gm_sa_##name[(c) ? 1 : -1]
GM_STATIC_ASSERT(GM_N_CLASSES <= 16u, classes);

static const int16_t GM_IN_OFF[GM_N_FEATURES] = { 12, -3, 0, 100 };   /* energies: 0       */
static const uint8_t GM_IN_SH [GM_N_FEATURES] = {  4,  2, 0,   6 };   /* each <= 14        */

/* W1[hidden][feature], row-major, one row = one neuron, int8 in [-127,127] */
static const int8_t   GM_W1 [GM_N_HIDDEN][GM_N_FEATURES] = { {1,2,3,4}, {-5,6,-7,8}, {0,0,1,-1} };
static const int32_t  GM_B1 [GM_N_HIDDEN] = { 100, -250, 0 };
static const uint16_t GM_M1 [GM_N_HIDDEN] = { 29100u, 29100u, 29100u };  /* 2^14 <= M < 2^15 */
static const uint8_t  GM_SH1[GM_N_HIDDEN] = { 22u, 22u, 22u };          /* 16 <= SH <= 31    */

static const int8_t   GM_W2[GM_N_CLASSES][GM_N_HIDDEN] = { {5,-6,7}, {-1,2,-3} };
static const int32_t  GM_B2[GM_N_CLASSES] = { 10, -10 };

#endif
// [END AI-GENERATED]
```
Layout: row-major, no padding, `static const` (program memory). The exporter writes the real marker pair itself (it is an AI-written generator only if an agent wrote it; generated output still carries the markers per AGENTS.md §7).

## 3. Details and rationale

**Where const arrays land.** XC16's default is **const-in-code**: initialized `const` objects go to `.const`/`auto_psv` and are read with ordinary C (DS-50002071M §8.7.1, §12.3.1.1, option `-mconst-in-code`, default). **VERIFIED**: sections `.const` flags `READONLY, PSV, PAGE`; `-Wl,--report-mem` shows 0 B of data RAM for the weights. Avoid `-mconst-in-data` (copies to RAM). Limits: one 32 KB PSV page for all constants/strings (§8.7.1, §10.10 `auto_psv`); our ~1.5 KB fits. Mark ISRs that read no constants `__attribute__((no_auto_psv))` (§8.7.2). Flash cost x1.5 (2 of 3 bytes per word are data): **VERIFIED**, 1178 data B = 1767 B program memory.

**Memory.** ~1464 data B (W1 960, W2 144, B1 64, B2 36, off 120, sh 60, M1 32, SH1 16, scalars ~32) -> **~2.2 KB of program memory (~3 %)**; RAM for weights 0; working set x8[60] + h[16] + logit[9]*4 = 112 B.

**Cycles per inference (1104 MACs).** **VERIFIED** asm of the inner loop: `se, mul.ss, asr, add, addc, inc, sub, bra` = 8 instructions, ~9 cycles (taken branch = 2 cycles, **UNVERIFIED** here). PSV access: per the PIC24FJ64GA004-family datasheet DS39881E (cited by review S1-3R; I did not read it) a PSV read adds +1 cycle for MOV/MOV.D and **+2 for other instructions** outside REPEAT; `se [w4++]` is the latter, so **~11 cycles/MAC, ~12 k cycles for the MACs**. Normalization ~0.9 k, requant 0.7 k (split) to 2-3 k (int64), loop and argmax ~0.3 k: **total ~14-17 k, call it ~16 k cycles = ~1 ms at 16 MIPS** (still < 0.1 % of the 1.5 s window). An unrolled loop may be ~30 % faster. Task 3.10 measures; these are estimates.

**int16 traps.** Every product is cast to int32 explicitly; host `int` is 32-bit, so the host harness cannot catch a missing cast (FRAMEWORK_REVIEW T2); gate G3 on-target vectors and a review of every multiply do. Use only fixed-width types in `mlp.c`.

**Python evaluation rule.** Training uses float, but every reported accuracy, model selection and early-stopping decision comes from `infer_ref.py` running the integer path above on the held-out set; float accuracy is diagnostic. Report float-vs-int agreement. Test vectors export window -> features -> `x8` -> `acc1` -> `h` -> logits -> class so C failures localize to a stage. QAT (Jacob et al. 2018 §3) only if PTQ misses the D1 criterion.

**Sources.** Jacob et al., "Quantization and Training of Neural Networks for Efficient Integer-Arithmetic-Only Inference", CVPR 2018, arXiv:1712.05877: fixed-point multiplier `M = 2^-n * M0`, `M0` in [0.5,1) (§2.2, Eq. 6, confirmed by review); int32 bias (§2.1, §2.4); weight range [-127,127] (§3, Appendix B). XC16 C Compiler User's Guide DS-50002071M (local PDF), sections inline. PIC24FJ64GA004-family datasheet DS39881E for PSV timing (via review, UNVERIFIED by me). The PIC24 programmer's reference manual was not consulted (UNVERIFIED instruction timing).

## 4. Open questions
1. Energy scaling (C3 shift 6/7/8 vs isqrt): after real data, are typical x8 energies > ~10? If not, compress in C3.
2. Per-channel L1 multipliers: keep or all-equal? (decide with first real accuracy numbers.)
3. Cycle cost of `___muldi3` and of PSV loads on target (ticket 3.10) decides D3 (a) vs (b).
4. Who owns the CRC-32 definition (exporter + host test)? Boot-time print enough?
5. Held-out set size for D1's criterion: is n >= 500 windows realistic for the 9 classes?
