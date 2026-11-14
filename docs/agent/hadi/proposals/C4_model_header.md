# C4 proposal: `gesture_model.h` format and quantization scheme

> Agent draft (research-quant) for `hadi`, ticket S1-3, 2026-11-14. **Not a decision.** Hadi decides; then it can go to `docs/agent/CONTRACTS.md` (AGENTS.md §5).
> Companion: `C5_classifier_output.md`. Numeric spike: `docs/agent/hadi/spikes/quant/quant_ref.py` (run with `/usr/local/bin/python3.12`; the other python3.12 on this Mac lacks numpy).
> Facts are tagged **VERIFIED** (compiled/ran here with XC16 v2.10 or numpy, or read in the local XC16 guide DS-50002071M) or **UNVERIFIED**.

## 1. Decisions needed

**D1. Network input representation.** Features are 60 int16 (C3).
- (a) *Per-feature offset + power-of-two shift -> int8*: `x8 = sat127(rshift_r(x - off_i, s_i))`. Cheap (add, shift, clamp), exact in Python, fixes the mean-vs-energy scale gap. Costs 60 int16 offsets + 60 uint8 shifts = 180 B flash.
- (b) Per-feature fixed-point multiplier: finer scale than 2^k steps, but needs a 16x16 multiply plus a shift per feature (60 more MULs), and 120 B more flash. Gain is small (at most 1 bit of range per feature).
- (c) None: feed raw int16 to layer 1 with per-tensor int8 weights. Rejected: energy features (up to ~10^7 before C3's shift) and means differ by orders of magnitude, so one weight scale crushes the small-scale features. Worst-case acc is 60*32767*127 = 2.5e8 < 2^31, so it would fit, but it trains badly.
- (d) Same as (a) but output int16 (e.g. +-2047) instead of int8. MUL cost is identical on PIC24 (MUL.SS is 16x16), flash for W1 is unchanged, precision is better. k-NN templates would then cost 120 B each rather than 60 B.
RECOMMENDATION (needs Hadi's decision): **(a) int8 inputs**, matching the "int8" in the overview and the 60 B/template RAM budget (PLAN §4). Fall back to (d) only if the integer-path accuracy loss vs float exceeds ~1 pt on the held-out set.

**D2. Weight quantization granularity.**
- (a) Per-tensor symmetric int8 for both layers. Simplest header.
- (b) Per-output-channel for layer 1 (16 multipliers `M1[j], SH1[j]`), per-tensor for layer 2.
- (c) Per-output-channel for layer 2. **Not allowed**: logits would have different scales per class, which breaks argmax and the margin.
RECOMMENDATION (needs Hadi's decision): **(b) as the *format*** (arrays `GM_M1[GM_N_HIDDEN]`, `GM_SH1[GM_N_HIDDEN]`), with the exporter free to emit identical entries (= per-tensor). Cost: 16*3 B = 48 B and zero extra cycles (requant is per-neuron anyway). Layer 2 is per-tensor; its single scale is exported as `GM_LOGIT_SCALE_Q16` for information only. Weights use the symmetric range **[-127, 127]** (never -128), zero point 0 (Jacob et al. 2018 §2.2 recommend this restricted range to keep products within int16 and allow simple kernels; our MAC is 8x8 so the range is a convention, not a necessity).

**D3. Requantization arithmetic (int32 acc -> int8 activation).**
- (a) `int64` expression `(int64_t)acc*M`. Compiler emits a call to `___muldi3` (**VERIFIED**: even for int32*int16 at -O1 XC16 v2.10 sign-extends to 64 bit and does `rcall ___muldi3`; cycle cost of that routine **UNVERIFIED**, assume 100-200). 16 calls/inference = ~2-3k cycles, still small beside ~10k cycles of MACs.
- (b) **int64-free split multiply**: `acc = hi*2^16 + lo` (hi int16, lo uint16); two 16x16 multiplies, shift >= 16. Proven bit-identical to (a) over 2*10^5 random cases (`quant_ref.py`, **VERIFIED**). Requires `16 <= SH <= 31`, `2^14 <= M < 2^15`.
- (c) Pre-shift `acc` to int16 first, then one 16x16 multiply. Loses low bits, differs from any clean integer reference. Rejected.
RECOMMENDATION (needs Hadi's decision): the **normative definition is (a)'s math** (Python big-int); the firmware may implement it either way because (b) is proven equal. Start with (a) on host, ship (b) on target if profiling shows requant matters. Exporter must assert `16 <= SH <= 31` (else the (b) path is unusable and the exporter must fail loudly).

**D4. Activation range after ReLU.** (a) int8 `[0,127]` (recommended; keeps the signed-int8 MAC path), (b) uint8 `[0,255]` (one more bit of precision; needs a uint8 pointer, MUL.SU/zero-extend, no measurable cost). RECOMMENDATION (needs Hadi's decision): (a) for simplicity.

**D5. Where the header's arrays live.** (a) `static const` arrays inside `gesture_model.h`, included by exactly one translation unit (`mlp.c`); (b) declarations in the header + generated `gesture_model.c`. RECOMMENDATION (needs Hadi's decision): (a), one generated file the exporter owns, metadata as macros so other .c files may include it safely (**VERIFIED** that an unreferenced `static const` array is discarded by XC16 at -O1, so a stray include costs no flash).

**D6. Consistency checks the firmware performs.** RECOMMENDATION (needs Hadi's decision): compile-time (`GM_STATIC_ASSERT`) checks of `sizeof(int)==2`-independent layout constants, and a **runtime refusal** in `gesture_init(odr_hz, range_g)`: if `odr_hz != GM_ODR_HZ || range_g != GM_RANGE_G` return an error / set a sticky `GESTURE_ERR_MODEL_MISMATCH` (FRAMEWORK_REVIEW T4). Print `GM_MODEL_HASH` over UART at boot.

## 2. Normative spec of the recommended option

Notation: all values are mathematical integers; `>>` is an arithmetic (flooring) right shift, which is what Python `>>` does and what XC16 does (**VERIFIED** in DS-50002071M §23 "result of a right shift of a negative-valued signed integral type: the sign is retained"; still, firmware must not rely on it for unsigned operands of a signed value, so cast first).

```
RSHIFT_R(v, s) = (v + ((1 << s) >> 1)) >> s     # round half up (toward +inf); s==0 -> v
SAT(v, lo, hi) = min(max(v, lo), hi)
```
Rounding is always *round-half-up via add-then-floor-shift*. Never use C `/` on negatives.

**Stage 0, input normalization** (feature i in 0..59, `x` int16 from C3):
`d = (int32)x - (int32)GM_IN_OFF[i]` (int32 needed: the difference of two int16 can overflow int16);
`x8[i] = SAT(RSHIFT_R(d, GM_IN_SH[i]), -127, 127)`. `GM_IN_SH[i]` in 0..15.

**Layer 1:** for j in 0..15: `acc1[j] = GM_B1[j] + sum_i (int32)GM_W1[j][i] * x8[i]` (int32; |acc1| < 60*127*127 + |bias|, exporter asserts `|acc1| <= 2^30` over all training vectors with margin and also by worst-case bound).
`h[j] = SAT(RSHIFT_R64(acc1[j] * GM_M1[j], GM_SH1[j]), 0, 127)` where `RSHIFT_R64(p, s) = (p + (1 << (s-1))) >> s` on a 48-bit-safe product. **ReLU is the lower clamp 0** (fused, no separate pass). `GM_M1[j]` is `uint16` in `[16384, 32767]`, `GM_SH1[j]` in `[16, 31]`.

**Layer 2:** for c in 0..8: `logit[c] = GM_B2[c] + sum_j (int32)GM_W2[c][j] * h[j]` (int32, no requant, no clamp; |logit| <= 16*127*127 + |bias| < 2^19 + |bias|).

**Argmax:** `top1 = smallest index c with logit[c] == max(logit)` (scan with strict `>`; **lowest index wins ties**). `top2 = index of the largest logit among c != top1`, again lowest index on ties. `margin = logit[top1] - logit[top2] >= 0` (C5 consumes this).

**Exporter (float -> integer) recipe** (informative but normative for the exporter's outputs):
1. `GM_IN_OFF[i] = round(mean_i)` of training features; `GM_IN_SH[i] = smallest s>=0 with max|x_i - off_i| >> s <= 127` (percentile 99.9 optional, then saturation applies).
2. Fold the per-feature input scale `2^s_i` into W1 (`W1' = W1 * 2^s_i`), and fold the offset into the float bias (`b1' = b1 - sum_i W1_i*off_i`) so the integer network sees `x8` only.
3. `s_w1 = max|W1'| / 127`, `W1q = round_half_even(W1'/s_w1)`; `s_h = P99.9(h_float)/127` (calibration set); `B1 = round(b1' / s_w1)` (int32, accumulator scale = `s_w1`, since the input scale is folded to 1).
4. `real = s_w1 / s_h`; `SH1 = smallest sh>=15 with real*2^sh >= 2^14`, `M1 = round(real*2^sh)` (if it rounds to 2^15, halve M and decrement sh). Same for each channel if per-channel.
5. `s_w2 = max|W2|/127`; `B2 = round(b2 / (s_h*s_w2))`; `GM_LOGIT_SCALE = s_h*s_w2` is the real value of one logit LSB.
`quant_ref.py::demo` follows this recipe end to end on a random network (**VERIFIED** to run; the 187/200 argmax agreement there is for random untrained weights and is informational only).

**Header layout (complete example with dummy values; real model has 60/16/9).**

```c
/* gesture_model.h : GENERATED by tools/export_model.py. DO NOT EDIT.
 * [AI-GENERATED: Claude Code]  (example only; exporter must emit the marker if AI-written) */
#ifndef GESTURE_MODEL_H
#define GESTURE_MODEL_H
#include <stdint.h>

#define GM_FORMAT_VERSION   1u            /* layout of this file; bump on any change below   */
#define GM_N_FEATURES       4u            /* real: 60                                        */
#define GM_N_HIDDEN         3u            /* real: 16                                        */
#define GM_N_CLASSES        2u            /* real: 9 (ids 0..8, see C5)                      */
#define GM_ODR_HZ           100u          /* sensor config the model was trained at          */
#define GM_RANGE_G          4u
#define GM_N_SAMPLES        150u          /* capture window length (C1)                      */
#define GM_FEATURE_VERSION  1u            /* C3 feature-definition version                   */
#define GM_MODEL_HASH       0x1A2B3C4Du   /* uint32: CRC-32 of all arrays below, big-endian  */
#define GM_CONF_SHIFT       6u            /* C5: conf = min(255, margin >> GM_CONF_SHIFT)    */
#define GM_DEFAULT_REJECT   64u           /* C5: default min_conf                            */
#define GM_LOGIT_SCALE_Q16  1234u         /* info: real logit LSB * 2^16                     */

/* Compile-time checks (XC16 v2.10 is GCC 4.5-based: _Static_assert is NOT supported,
 * VERIFIED by compile error; use the negative-array typedef). */
#define GM_STATIC_ASSERT(c, name) typedef char gm_sa_##name[(c) ? 1 : -1]
GM_STATIC_ASSERT(GM_N_CLASSES <= 16u, classes);

/* Input normalization, one entry per feature */
static const int16_t GM_IN_OFF[GM_N_FEATURES] = { 12, -3, 0, 100 };
static const uint8_t GM_IN_SH [GM_N_FEATURES] = {  4,  2, 0,   6 };

/* Layer 1: W1[hidden][feature] row-major (one row = one neuron), int8 in [-127,127] */
static const int8_t   GM_W1 [GM_N_HIDDEN][GM_N_FEATURES] = { {1,2,3,4}, {-5,6,-7,8}, {0,0,1,-1} };
static const int32_t  GM_B1 [GM_N_HIDDEN] = { 100, -250, 0 };
static const uint16_t GM_M1 [GM_N_HIDDEN] = { 29100u, 29100u, 29100u };  /* Q15-normalized */
static const uint8_t  GM_SH1[GM_N_HIDDEN] = { 22u, 22u, 22u };

/* Layer 2: W2[class][hidden] row-major, int32 logits out */
static const int8_t   GM_W2[GM_N_CLASSES][GM_N_HIDDEN] = { {5,-6,7}, {-1,2,-3} };
static const int32_t  GM_B2[GM_N_CLASSES] = { 10, -10 };

#endif
```
Layout rules: row-major, one row = one output neuron (so the inner loop walks consecutive bytes); no padding; arrays are `static const` so XC16 places them in program memory (below). `GM_MODEL_HASH` = CRC-32 (IEEE) over the little-endian bytes of the constants, in the file order, computed by the exporter. Python and C each can recompute it; the firmware does not need to (it prints the constant), but a host test should.

## 3. Details and rationale

**Where const arrays land (item 6).**
- XC16's default memory model is **const-in-code**: `const`-qualified initialized objects go to program memory (the `auto_psv` section, a compiler-managed PSV window), read with ordinary C (DS-50002071M §8.7.1 "Memory Models and Address Spaces", §12.3.1.1 "String and Const Objects", option `-mconst-in-code`, default). **VERIFIED here**: compiling a file with `static const int8_t W[960]`, an int32 array, and a `space(auto_psv)` array with `xc16-gcc -mcpu=24FJ64GA002 -O1` puts all in section `.const` (flags `READONLY, PSV, PAGE`, 0x49a = 1178 B) and the linked image reports **0 bytes of "data" memory** (`-Wl,--report-mem`). Same result with explicit `-mconst-in-code`, i.e. RAM holds no weights. Flag to avoid: `-mconst-in-data` copies constants to RAM (§12.3.1.1).
- The attribute `__attribute__((space(auto_psv)))` is redundant for `const` objects but harmless.
- Limits: one PSV page of 32 KB shared by all constants and string literals (§8.7.1, §10.10 `auto_psv`: "maximum of 32K"); our ~1.5 KB fits trivially. Gotcha: ISRs re-assert the PSV page; mark ISRs that do not read constants `__attribute__((no_auto_psv))` (§8.7.2). Do not mix the `-mconst-in-code` model with manual `__prog__` access without reading §12.3.2.
- Flash cost per byte: only 2 of each 3 instruction-word bytes hold data in a PSV read. **VERIFIED by linking**: 1178 data bytes show as 1767 bytes of "program" memory, i.e. x1.5.
- Pointers to the arrays are ordinary 16-bit generic pointers into the PSV window (compiled `mac(const int8_t*, ...)` loop uses plain `se [w4++]`, no table reads).

**Memory cost (item 7), real model 60/16/9.** Data bytes: W1 960 + W2 144 + B1 64 + B2 36 + IN_OFF 120 + IN_SH 60 + M1 32 + SH1 16 + scalars ~32 = ~1464 B; x1.5 -> **~2.2 KB of program memory (~3 % of 64 KB)**. RAM: 0 for weights; working RAM = x8[60] + h[16] (int8) + logit[9] int32 = 60+16+36 = 112 B (PLAN §4 budgeted 100 B for hidden int32; int8 h is smaller).

**Cycle estimate for one inference (item 7).** 1104 MACs. **VERIFIED asm** at -O1 for the inner loop `a += (int16)w[i]*x[i]` on XC16 v2.10: `se, mul.ss, asr, add, addc, inc, sub, bra` = 8 instructions, the taken branch is 2 cycles -> ~9 cycles/MAC (branch timing from the PIC24 programmer's reference, **UNVERIFIED** here). So ~10 k cycles, plus a possible per-access PSV penalty (PIC24F PSV reads may cost extra cycle(s): **UNVERIFIED**, assume +1/MAC -> ~11 k). A 4x-unrolled hand/-O3 loop can approach ~6 cycles/MAC (~6.6 k). Requant: 16x (b) path ~40 cycles each ~700, or (a) 16x 100-200 (UNVERIFIED) ~2-3 k. Normalization 60x ~15 = ~900. **Total ~8k-15k cycles = 0.5-0.95 ms at 16 MIPS**, i.e. negligible against the 1.5 s window. Task 3.10 must measure it (do not quote these as measurements).

**Why int8 weights with int32 accumulate is safe on a 16-bit `int`.** Every product is cast explicitly: `(int32_t)w * x` or `(int16_t)w * (int16_t)x` assigned to int32 (the PIC24 MUL.SS yields 32 bits in a register pair). Without the cast the product of two int16 stays 16-bit `int` in C and overflows only on target (FRAMEWORK_REVIEW T2). The host harness cannot catch a missing cast (host `int` is 32-bit), so rely on gate G3 (on-target vectors) and code review of every multiply. An `-Wconversion` warning-free build is acceptance 3.7.

**Python evaluation rule (item 8).** Training uses float. Every reported accuracy, every model-selection decision, and the early-stopping/early-export criterion must come from `infer_ref.py` running the integer path above (normalize -> int8 dense -> requant -> int32 dense -> argmax) on the held-out set; float accuracy is diagnostic only. Report float-vs-int argmax agreement as a sanity metric. Test vectors export raw window -> features -> `x8` -> `acc1` -> `h` -> logits -> class so the C test can localize a mismatch to a stage. Optionally do quantization-aware fine-tuning (Jacob et al. 2018 §3) if post-training quantization loses >1 pt.

**Sources.** Jacob et al., "Quantization and Training of Neural Networks for Efficient Integer-Arithmetic-Only Inference", CVPR 2018 (affine scheme; fixed-point multiplier M0 in [0.5,1) with right shift; bias int32 at scale s_x*s_w; restricted weight range -127..127 -- from memory of the paper, **UNVERIFIED** section numbers). XC16 C Compiler User's Guide DS-50002071M (local copy `/Applications/microchip/xc16/v2.10/docs/MPLAB_XC16_C_Compiler_Users_Guide.pdf`), sections cited inline. PIC24 FRM (DS39… family reference) for MUL.SS/MUL.SU/instruction timing: **not consulted offline; UNVERIFIED**; MUL.SS/MUL.SU/MUL.UU appear in the compiler output here, which confirms the multiplier instructions exist.

## 4. Open questions
1. Does C3 deliver feature magnitudes that fit int16 without further saturation? (Affects `GM_IN_SH` range 0..15.)
2. Per-channel L1 multipliers: worth the exporter complexity, or all-equal? (Decide after first accuracy numbers.)
3. Is `sizeof(int)`-dependent code avoided entirely? (Use only `int16_t/int32_t` in mlp.c.)
4. Who owns the CRC-32 definition (exporter + host test) and is a boot-time print enough, or should `gesture_init` also compare against an expected hash from the app?
5. Measured cost of `___muldi3` and PSV access on target (task 3.10); decides D3 (a) vs (b).
6. Should the header also carry `GM_N_SAMPLES` / C3 feature version so firmware can refuse a mismatched capture length? (Proposed yes, included above.)
