<!-- [AI-GENERATED: Claude Code] -->
# C3 Feature definition: proposal (spike S1-2, fix round S1-2F)

Status: PROPOSAL, not locked. Prototype: `docs/agent/hadi/spikes/features/`. Review: `reviews/S1-2R.md`.

**Part of C3 (not only the algorithm):** window length 150 samples, ODR 100 Hz (so a 15-sample
segment is 0.15 s), range +/-4 g, 12-bit samples. The features, and any model trained on them, are
valid only at these settings; a different ODR or range changes what "segment" and "energy" mean
(see FRAMEWORK_REVIEW T4; C4 carries the model-side check).

**Pending contract C1 (input assumption):** window is `int16_t x[150][3]`, sample-major
(`x[i][0]=X, x[i][1]=Y, x[i][2]=Z`), every value a 12-bit signed sample in [-2048, 2047]
(LIS3DH high-res, +/-4 g, after arithmetic >>4). Behaviour outside this range is undefined.

**Change from the older wording:** PLAN section 1 C3 and INITIAL_OVERVIEW say "Energy = sum x^2".
This proposal defines energy about the segment mean, SS = sum (x - mean)^2 (with the truncated
integer mean, so it is variance-like times 15 plus 15*(mean error)^2, not exactly a variance). The
mean feature then carries the DC/orientation part and the energy feature does not repeat it.

**Out of scope:** feature normalization (per-feature offset/shift to int8) belongs to C4; see
`proposals/C4_model_header.md` D1. C3 ends at the raw int16 features.

## 1. Decisions needed

1. **Mean rounding.** Options: (a) truncate toward zero = C `/`; (b) floor (`>>` / Python `//`); (c) round half away from zero.
   (a) is what C does natively and compiles to one `div.sw`; (b) needs negative-safe shift emulation; (c) costs extra code.
   RECOMMENDATION (needs Hadi's decision): (a), Python emulates with `c_div_trunc`.
2. **Division implementation.** Plain `sum / 15` (XC16: `repeat; div.sw`) or multiply-shift `(|s|*34953)>>19`.
   Both proven identical for every s in [-30720, 30705] (C and Python, exhaustive).
   RECOMMENDATION (needs Hadi's decision): plain `/ 15`; mul-shift is a documented fallback.
3. **Energy definition.** (a) sum x^2 (old wording): dominated by gravity/DC, duplicates the mean feature. (b) SS = sum (x-mean)^2: independent of the mean, same cost. (c) mean of squares: needs another /15.
   RECOMMENDATION (needs Hadi's decision): (b), see "Change from the older wording" above.
4. **Energy scaling (D4, the important one).** The first spike used `min(SS >> 11, 32767)`. Measured on realistic sinusoids it wipes out small motions (table below). Options, all implemented and bit-exact in the spike (`FEAT_ENERGY_MODE`):
   - (a) `min(SS >> s, 32767)`, s = 6, 7, 8 (mode 0). Linear, cheapest (no extra code). Small motions survive at s <= 8 but large motions saturate (saturation is now reachable).
   - (b1) `isqrt(SS)` (mode 1): floor sqrt of SS, range 0..7912, no saturation, no divide. It is sqrt(15) times the RMS deviation.
   - (b2) `isqrt(SS / 15)` (mode 2): RMS deviation in LSB (SS/15 truncated), range 0..2042. Needs a uint32/15 division (`__udivsi3` library call on XC16).
   - Linear shifts keep one scale across the whole range, but no single shift serves both amplitude 10 and amplitude 2000 (shift 8: 87 % zeros at amp 10, 13 % saturated at amp 2000). A square root compresses the 4 decades of SS into 3 so one scale covers everything and it is a natural fit for the int8 input scaling in C4 D1.
   RECOMMENDATION (needs Hadi's decision): **(b1) `isqrt(SS)`, mode 1.** No zeros down to amp 10, never saturates, no divide, unit-less scale constant (sqrt 15) is absorbed by C4 normalization. Use (b2) only if energy in exact LSB-RMS is wanted for readability (costs a library division). Shift s = 8 with saturation is the fallback if the isqrt cycle cost is unacceptable (estimate below).
   **Default in the code is still mode 0 / shift 11**, solely because the independent QA oracle (`spikes/features_qa`, which this fix round may not change) encodes shift 11. After Hadi decides, flipping the default is a one-line change of `FEAT_ENERGY_MODE` in `features.h` plus updating the QA oracle's `segment_features`.
5. **Feature ordering.** Axis-major `idx = 20*axis + 2*seg + k` vs segment-major `6*seg + 2*axis + k`.
   RECOMMENDATION (needs Hadi's decision): axis-major, k=0 mean, k=1 energy.
6. **Input range handling.** Rely on C1 (no clamp), or clamp, or debug-only assert.
   RECOMMENDATION (needs Hadi's decision): rely on C1; the sensor driver guarantees [-2048, 2047]. A violation silently wraps the int16 sum.
7. **Prototype signature.** `void features_extract(int16_t (*x)[3], int16_t out[60])`. A `const int16_t (*x)[3]` parameter makes xc16-gcc 2.10 warn "incompatible pointer type" for every plain `int16_t[150][3]` caller (verified; C only allows the implicit conversion for non-array-of-const). The function does not write x; this is documented.
   RECOMMENDATION (needs Hadi's decision): non-const `(*x)[3]` as built (zero warnings, `call_check.c`); the alternative is a flat `const int16_t *` with `x[3*i+a]` indexing at the cost of callers passing `&buf[0][0]`.

### Energy option comparison

Method: `spikes/features/energy_study.py` (analysis only), 2500 windows x 30 segments per amplitude
(75,000 segments), per-axis sinusoid of 1..5 cycles/window, peak amp x U(0.3, 1), DC offset
U(-1000, 1000), +/-2 LSB noise, clipped to the 12-bit range. Values are the stored int16 energy.
"zero%" is the share of segments whose energy stores 0 (information lost); "sat%" the share clamped at 32767.

| amp (LSB) | option | zero % | median | p99 | max | sat % |
|---|---|---|---|---|---|---|
| 10 | shift 11 | 100.0 | 0 | 0 | 0 | 0.0 |
| 10 | shift 8 | 87.5 | 0 | 2 | 3 | 0.0 |
| 10 | shift 7 | 66.1 | 0 | 4 | 7 | 0.0 |
| 10 | shift 6 | 35.6 | 1 | 8 | 14 | 0.0 |
| 10 | isqrt(SS) | 0.0 | 9 | 23 | 30 | 0.0 |
| 10 | isqrt(SS/15) | 0.1 | 2 | 6 | 7 | 0.0 |
| 50 | shift 11 | 61.3 | 0 | 6 | 9 | 0.0 |
| 50 | shift 8 | 13.6 | 5 | 51 | 74 | 0.0 |
| 50 | shift 7 | 6.5 | 11 | 102 | 148 | 0.0 |
| 50 | shift 6 | 2.4 | 22 | 204 | 296 | 0.0 |
| 50 | isqrt(SS) | 0.0 | 37 | 114 | 137 | 0.0 |
| 50 | isqrt(SS/15) | 0.0 | 9 | 29 | 35 | 0.0 |
| 250 | shift 11 | 5.7 | 16 | 154 | 222 | 0.0 |
| 250 | shift 8 | 0.5 | 131 | 1237 | 1778 | 0.0 |
| 250 | shift 7 | 0.2 | 262 | 2474 | 3556 | 0.0 |
| 250 | shift 6 | 0.0 | 525 | 4949 | 7113 | 0.0 |
| 250 | isqrt(SS) | 0.0 | 183 | 562 | 674 | 0.0 |
| 250 | isqrt(SS/15) | 0.0 | 47 | 145 | 174 | 0.0 |
| 1000 | shift 11 | 0.2 | 265 | 2541 | 3474 | 0.0 |
| 1000 | shift 8 | 0.0 | 2120 | 20329 | 27799 | 0.0 |
| 1000 | shift 7 | 0.0 | 4241 | 32767 | 32767 | **2.8** |
| 1000 | shift 6 | 0.0 | 8482 | 32767 | 32767 | **13.7** |
| 1000 | isqrt(SS) | 0.0 | 736 | 2281 | 2667 | 0.0 |
| 1000 | isqrt(SS/15) | 0.0 | 190 | 589 | 688 | 0.0 |
| 2000 | shift 11 | 0.7 | 1016 | 9413 | 13411 | 0.0 |
| 2000 | shift 8 | 0.6 | 8134 | 32767 | 32767 | **13.0** |
| 2000 | shift 7 | 0.6 | 16269 | 32767 | 32767 | **29.9** |
| 2000 | shift 6 | 0.6 | 32539 | 32767 | 32767 | **49.8** |
| 2000 | isqrt(SS) | 0.6 | 1443 | 4390 | 5240 | 0.0 |
| 2000 | isqrt(SS/15) | 0.6 | 372 | 1133 | 1353 | 0.0 |

(The ~0.6 % zeros at amp 2000 are segments clipped flat at the 12-bit limit.)

Reading the table: shift 11 loses everything below amp ~50. Shifts 6-8 recover small motions but
saturate at amp 1000 (shift 7: 2.8 %, shift 6: 13.7 %) and amp 2000 (shift 8: 13.0 %, shift 7: 29.9 %, shift 6: 49.8 %).
`isqrt(SS)` keeps non-zero values from amp 10 and never saturates (max 7912 by construction).

Costs on XC16 2.10 (sizes measured, cycles are hand estimates, not measured on target; ticket 3.10 will measure):

| mode | flash -O1 / -O2 | extra over shift | notes |
|---|---|---|---|
| 0 shift | 240 B / 189 B | none | 0 library calls |
| 1 isqrt(SS) | 351 B / 321 B | `features_isqrt32`: 138 B at -O1 (159 B at -O2) | about 14 loop iterations x ~20 cycles, so roughly 150-300 cycles per segment, 5-9k cycles per window (about 1.3-2.2 ms at 4 MIPS); 0 library calls |
| 2 isqrt(SS/15) | 360 B / 318 B | isqrt plus `__udivsi3` (library, not counted) | adds one 32-bit divide per segment |

Both are negligible against the 1.5 s window, but an ISR-free budget should be re-checked in C7.

## 2. Normative spec

Types: exact integer arithmetic; "int16/int32/uint32" name the C storage width.
Input `x[i][a]`, i in 0..149, a in 0..2, each in [-2048, 2047].

```
trunc_div(a, b): q = floor(|a| / |b|); return q if sign(a)==sign(b) (or a==0) else -q   // C99 '/'
isqrt(n):  largest r with r*r <= n   (digit-by-digit: res=0; bit=1<<30; while bit>n: bit>>=2;
           while bit: if n >= res+bit: n -= res+bit; res = (res>>1)+bit  else res >>= 1; bit >>= 2)
for a in 0..2:            // X, Y, Z
  for s in 0..9:          // segment s covers samples 15*s .. 15*s+14
    sum    : int16  = x[15s][a] + ... + x[15s+14][a]
    mean   : int16  = trunc_div(sum, 15)
    SS     : uint32 = 0
    for j in 0..14:
        d : int16  = x[15s+j][a] - mean
        SS += (uint32)((int32)d * (int32)d)       // cast BEFORE multiply
    energy : int16 =                                  // by FEAT_ENERGY_MODE
        mode 0:  min(SS >> SHIFT, 32767)            // SS >= 0: plain shift
        mode 1:  isqrt(SS)                          // recommended
        mode 2:  isqrt(SS / 15)                     // uint32 division, truncating
    out[20*a + 2*s    ] = mean
    out[20*a + 2*s + 1] = energy
```
Index formula: `idx = 20*axis + 2*seg + k`, k=0 mean, k=1 energy. Output is 60 int16; mean in [-2048, 2047];
energy in [0, 32767] (mode 0), [0, 7912] (mode 1), [0, 2042] (mode 2).
Alternative mean (equivalent): `q = ((uint32)|sum| * 34953) >> 19; mean = sum<0 ? -q : q`.

## 3. Range proofs

| Step | Worst case | Fits |
|---|---|---|
| sample | [-2048, 2047] | int16 |
| sum (any partial sum of <= 15 values) | [-30720, 30705] | int16 (limit +/-32767) |
| mean = trunc(sum/15) | [-2048, 2047] (|mean| <= max |x|) | int16 |
| d = x - mean | [-4095, 4095] | int16 |
| d*d (computed in int32) | 4095^2 = 16,769,025 | int32 (int16 would overflow: cast first) |
| SS = sum of 15 d*d | loose bound 15*4095^2 = 251,535,375 < 2^31; true max 62,604,360 (7 or 8 of 15 at each extreme; enumerated over all vertices, SS is convex so the max is at a vertex, truncating the mean adds < 15) | uint32 |
| mode 0: SS >> 11 | max 30,568 (never saturates); at shift 8, saturation threshold 32768*256 = 8,388,608 is reachable | int16 after min |
| mode 1: isqrt(SS) | floor(sqrt(62,604,360)) = 7912 | int16; isqrt operand < 2^27 so the loop runs <= 15+14 iterations |
| mode 2: isqrt(SS/15) | SS/15 <= 4,173,624, result <= 2042 | int16 |
| mul-shift: |sum|*34953 | 30,720*34,953 = 1,073,756,160 < 2^31 | int32/uint32 |

Mul-shift equals trunc-division because 34953 = ceil(2^19/15), excess 7, so error < |s|*7/(15*2^19) < 1/15 for |s| < 74,898; also verified exhaustively.

## 4. Verification results

Branch `s1-2-fixes`. `make test` in `spikes/features` (host clang `-std=c99 -Wall -Wextra -Wconversion -Werror -O2`):
each of 6 energy variants (default, shift 8/7/6, isqrt, isqrt15) is built and compared bit-exactly against `features_ref.py` on 12,339 windows:
```
DIV15 PASS 61426 sums
ISQRT PASS 0..2^27 and top 100001 of uint32      (C isqrt exhaustive vs r*r<=n<(r+1)^2)
PY isqrt32 == math.isqrt PASS 102033 probes
PASS 12339/12339       (x 6 variants; "ALL VARIANTS PASS")
saturated (==32767) values seen: default 0, shift 8: 225533, shift 7: 248660, shift 6: 267947 of 370170
```
Vectors: edge cases, 4000 uniform, 4000 smooth, 2000 segments pinned to extremes, 2000 windows whose segments randomly mix -2048 and 2047 (half also perturbed by +/-3), a spike sweep (heights 0..4095 on both bases, crossing every shift-saturation threshold), and a boundary hunt (82 segments placed on or nearest to SS thresholds for shift 6/7/8 saturation and k^2-1, k^2, k^2+1 for isqrt; 14 land exactly, the rest within a few units).
`make test` in `spikes/features_qa` (default energy, unchanged oracle): OVERALL PASS, xc16 -O1/-O2 no warnings.

`make xc16` (xc16-gcc 2.10, `-mcpu=24FJ64GA002 -std=c99 -Wall -Wextra -Wconversion`): zero warnings at -O1 and -O2 for
`features.c` (all three energy modes) and for `call_check.c`, which calls `features_extract` with a plain non-const `int16_t[150][3]`. Sizes above (earlier -O1 number for the first spike, 228 B, excluded the separate scale step; the current default at -O1 is 240 B, at -O2 189 B). The free XC16 license may restrict some optimisation levels (-Os is reported as disabled in the QA output), not -O1/-O2.

Caveat (T2): host tests use 32-bit int. Every multiply is cast to int32_t first and the sum stays in int16 by the range proof, but the on-target vector run (gate G3) is still mandatory.

## 5. Open questions

- Is C1 confirmed: sample-major, [-2048, 2047], sign-extending `>>4`? Who guarantees the range?
- Decide D4: isqrt(SS) (recommended) vs shift 8; then flip the default and update the QA oracle.
- Real-data check: the table is synthetic; re-run with recorded data from WP2 before locking.
- Normalization of the 60 features (offset/shift to int8) is C4 D1.
- On-target cycle counts (ticket 3.10) replace the hand estimates.
- Should Markdown docs carry AI markers (this file carries an HTML-comment marker)?
<!-- [END AI-GENERATED] -->
