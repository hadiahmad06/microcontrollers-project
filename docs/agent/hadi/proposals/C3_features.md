# C3 Feature definition: proposal (spike S1-2)

Status: PROPOSAL, not locked. Prototype: `docs/agent/hadi/spikes/features/`.

**Pending contract C1 (input assumption):** window is `int16_t x[150][3]`, sample-major
(`x[i][0]=X, x[i][1]=Y, x[i][2]=Z`), every value a 12-bit signed sample in [-2048, 2047]
(LIS3DH high-res, +/-4 g, after arithmetic >>4). Behaviour outside this range is undefined.

## 1. Decisions needed

1. **Mean rounding.** Options: (a) truncate toward zero = C `/`; (b) floor (`>>`/Python `//`); (c) round half away from zero.
   (a) is what C does natively, and compiles to one `div.sw`; (b) needs a negative-safe shift emulation; (c) costs extra code.
   RECOMMENDATION (needs Hadi's decision): (a) truncate toward zero, Python emulates with `c_div_trunc`.
2. **Division implementation.** Options: plain `sum / 15` (XC16: `repeat #17; div.sw`, ~18 cycles) or
   multiply-shift `(|s|*34953)>>19` with sign restore (needs int32 multiply). Both proven identical for every s in [-30720, 30705].
   RECOMMENDATION (needs Hadi's decision): plain `/ 15` (simplest, hardware divide); keep mul-shift as documented fallback.
3. **Energy definition.** Options: (a) sum(x^2); (b) sum((x-mean)^2), variance-like; (c) mean of squares (needs another /15).
   (a) is dominated by DC/gravity and duplicates the mean feature (max 15*2048^2 = 6.3e7, same range as (b)); (b) is orthogonal to mean, same cost (one extra pass).
   RECOMMENDATION (needs Hadi's decision): (b), deviation taken from the already-truncated integer mean.
4. **Energy scaling and saturation.** Right shift of the int32/uint32 sum, then saturate to 32767. Shift 11 makes the
   true worst case 30568 so saturation never fires; shift 8-10 gives more resolution for small motions but saturates on large ones.
   RECOMMENDATION (needs Hadi's decision): shift 11, keep the saturation as a safety net. Revisit after real data
   (if typical energies are small, a smaller shift plus saturation, or a later normalization step, may train better).
5. **Feature ordering.** Options: axis-major `20*a + 2*s + k`, or segment-major (time-major) `6*s + 2*a + k`, or grouped by feature type.
   RECOMMENDATION (needs Hadi's decision): axis-major `idx = 20*axis + 2*seg + k` (k=0 mean, k=1 energy).
6. **Input range handling.** Spec relies on C1 (no clamping in features code). Alternative: clamp inputs, costing cycles for no benefit if the sensor driver guarantees range.
   RECOMMENDATION (needs Hadi's decision): rely on C1; the sensor driver must guarantee [-2048, 2047].

## 2. Normative spec

Types: all arithmetic is exact integer arithmetic; "int16"/"int32"/"uint32" name the C storage width.
Input `x[i][a]`, i in 0..149, a in 0..2, each in [-2048, 2047].

```
trunc_div(a, b): q = floor(|a| / |b|); return q if sign(a)==sign(b) (or a==0) else -q   // C99 '/'
for a in 0..2:            // X, Y, Z
  for s in 0..9:          // segment s covers samples 15*s .. 15*s+14
    sum    : int16  = x[15s][a] + ... + x[15s+14][a]
    mean   : int16  = trunc_div(sum, 15)
    acc    : uint32 = 0
    for j in 0..14:
        d : int16  = x[15s+j][a] - mean
        acc += (uint32)((int32)d * (int32)d)      // cast BEFORE multiply
    e      : uint32 = acc >> 11                   // acc >= 0: plain shift, no sign issue
    energy : int16  = min(e, 32767)
    out[20*a + 2*s    ] = mean
    out[20*a + 2*s + 1] = energy
```
Index formula: `idx = 20*axis + 2*seg + k`, k=0 mean, k=1 energy. Output is 60 int16, mean in [-2048,2047], energy in [0,32767].
Alternative mean (equivalent): `q = ((uint32)|sum| * 34953) >> 19; mean = sum<0 ? -q : q`.

## 3. Range proofs

| Step | Worst case | Fits |
|---|---|---|
| sample | [-2048, 2047] | int16 |
| partial sums and sum (<=15 values) | [-30720, 30705] (15*-2048, 15*2047) | int16 (limit +/-32767) |
| mean = trunc(sum/15) | [-2048, 2047] (|mean| <= max |x|) | int16 |
| d = x - mean | [-4095, 4095] (x and mean both in range) | int16 |
| d*d (in int32) | 4095^2 = 16,769,025 | int32 (int16 would overflow: cast first) |
| acc = sum of 15 d*d | loose bound 15*16,769,025 = 251,535,375 < 2^31; true max 62,604,360 (7 or 8 of the 15 at each extreme, found by enumerating all vertices; Sum(x-m)^2 is convex so its maximum is at a vertex, and truncating the mean adds under 15) | uint32/int32 |
| e = acc >> 11 | true max 30,568; saturation threshold 32,768*2048 = 67,108,864 is never reached | int16 |
| mul-shift: |sum|*34953 | 30,720*34,953 = 1,073,756,160 < 2^31 | int32/uint32 |

Mul-shift equals trunc-division because 34953 = ceil(2^19/15), excess 7, so error < |s|*7/(15*2^19) < 1/15 for |s| < 74,898;
also verified exhaustively for all 61,426 sums (Python `compare.py` and C `div15_check.c`).

## 4. Verification results

`make test` (host clang, `-std=c99 -Wall -Wextra -Wconversion -Werror`):
```
DIV15 PASS 61426 sums
PY mulshift==trunc-div PASS 61426 sums
max energy feature seen: 30568
PASS 10062/10062
```
Vectors: edge cases (all -2048, all 2047, alternating, zeros, +/-1, spikes at each axis/position, worst-case energy splits, ramps), 4000 uniform random, 4000 smooth sinusoid+noise, 2000 random with random segments pinned to extremes.

`make xc16` (xc16-gcc v2.10, `-mcpu=24FJ64GA002 -O1 -std=c99 -Wall -Wextra -Wconversion`): zero warnings.
`.text` 0x98 address units = 76 instructions = 228 bytes of program flash (features_extract + static segment_features); 0 bytes data/bss; /15 compiles to `repeat #17; div.sw`, no library calls.

Caveat (T2): host tests use 32-bit int. The code casts to int32_t before every multiply and keeps the sum in int16 by the range proof, but the on-target vector run (gate G3) is still mandatory.

## 5. Open questions

- Is C1 (12-bit range after >>4, sample-major layout) confirmed by the sensor-driver owner? Is the >>4 arithmetic (sign-extending)?
- Real-data energy distribution: is shift 11 too coarse (most energies in the low hundreds)? Needs recorded data from WP2.
- Does the model want normalization of the 60 features (C4)? Not included here; this spec ends at raw int16 features.
- Cycle count on target not measured (ticket 3.10).
