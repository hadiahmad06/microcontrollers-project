<!-- [AI-GENERATED: Claude Code] -->
# WP4-aR: review of display.c, icons.c and the WP4-aT suite

Reviewer: review-14 (wrote none of the code). Working for: hadi. Reviewed commit a12fc73
("fix: display_get leaves rgb unchanged out of range ...") on branch `claude/optimistic-meitner-67qdon`
(fast-forwarded into this worktree first). Nothing was fixed; only this file was written.

## Verdict

**PASS WITH FINDINGS.** 0 high, 2 medium, 8 low. `display.c` and `icons.c` match the rulings line by line, there is no
16-bit hazard, and the limiter bound holds on every path. Both suites pass. The tests catch every non-equivalent
mutation I tried in `display.c`. The two medium findings are (M1) the icon tests do not pin which icon is which, and
(M2) incomplete doc comments.

| Severity | Count |
|----------|-------|
| high | 0 |
| medium | 2 |
| low | 8 |

## Findings

| ID | file:line | finding | evidence | severity |
|----|-----------|---------|----------|----------|
| M1 | firmware/test/display/run_tests.py:110-150 (`check_icons`) | Icon shapes and colours are checked only by properties (blank NONE, >= 6 lit pixels, pairwise distinct, unknown ids give the `?` bitmap, `icon_show` equals draw_bitmap of the icon's own colour). Nothing pins which gesture owns which bitmap or colour. A wrong icon assignment is invisible: CW and CCW swapped, or red and blue swapped, still passes. Mirror relations that hold today (id 2 = mirror of 1, id 4 = flip of 3, id 6 = mirror of 5) are not asserted either. | Mutations i1 (CW/CCW bitmaps swapped) and i2 (SWIPE_RIGHT colour set to blue) both ended "display suite PASS". | medium |
| M2 | firmware/src/icons.h:14-24; firmware/src/display.c:15; firmware/src/icons.c:62 | Doc comments are incomplete against the AGENTS.md section 7 rule (purpose, each argument, return). `icon_bitmap` and `icon_color` have `@param`/`@return` but no purpose sentence. The static helpers `cap_channel` and `icon_index` have no `@param`. Test-side: `cap_of` in `standin/display.c:36` has no doc comment at all, and the AI_USAGE row says "doc in its header" although it is a static helper that is not in the header. | `icons.h` comments start at "@param id ..."; `display.c:15` is one line with only `@return`. | medium |
| L1 | firmware/src/display.c:106-107 | The limiter is a uniform floor, so a frame just over the limit loses a visible step. 1 unit over the limit drops the estimate from 300 mA to 290 mA. All-white at cap 32 reads 286 mA, 14 mA under the limit. This is within the ruling and the bound is safe. It is a design observation only. | Host log: `lim_eq 300 3825`, `lim_p1 290 3826`, `all255 286 6144`. | low |
| L2 | firmware/src/display.h:20-24, display.c:16 | There is no `#error` guard on `DISPLAY_CAP`. `cap_channel` returns `uint8_t`, and a cap above 255 would give results above 255 that are silently truncated. The proof comment assumes v <= 255. The default (32) and the tested alt (64) are fine. | Code read; the alt build only exercises cap 64. | low |
| L3 | firmware/src/display.c:79-85 | The limiter proof is correct but terse. It does not state the U <= L case (after = U <= L, trivially). It does not say why the mA return is <= DISPLAY_LIMIT_MA: after*20/255 <= L*20/255 <= mA, since L = floor(mA*255/20). "L small" is vague (the actual condition is v*L < 2^32). | See section "Limiter proof" below. | low |
| L4 | firmware/src/icons.c:28-31 (ids 5, 6) | CW and CCW are exact mirror images (0xE1 vs 0x87, 0x41 vs 0x82), so they are distinct, but legibility is weak. Each is a plain ring with a 3-pixel horizontal tick at the upper right (CW) or upper left (CCW), not an arrowhead. The only cue is which side the tick is on. Cyan vs magenta helps, but at 8x8 on a real matrix this is likely to be hard to tell apart. The ring also resembles the THRUST target (id 8). Needs a bench look. | ASCII dump in "Icon review". | low |
| L5 | firmware/src/icons.c:34, 49 | The TWIST icon (white hourglass, 40 lit pixels) is the only icon that engages the limiter: 40*3*32 = 3840 units against a limit of 3825, so it renders at (31,31,31) and about 291 mA. It also draws about 4x the current of the other icons, so it is the brightest on the matrix. | Computed with oracle.py: `twist 40 3840 291 LIMITED max wire 31`. | low |
| L6 | firmware/src/icons.c:15 vs 60 | The `?` bitmap and learned digit "2" share their first four rows (3C 66 06 0C). Only colour (orange vs purple) and the last 3 rows tell them apart. Fine for MVP, noted for legibility. | Bitmaps in source. | low |
| L7 | firmware/test/display/run_tests.py:125 and :202 | `check_icons` returns early on `if fails:` where `fails` is shared with the frame checks, so any earlier frame mismatch silently skips all icon checks in the same run. Harmless when everything passes. It hides icon results while debugging. | Code read. | low |
| L8 | firmware/test/display/Makefile:13-15 | Serpentine is tested only with cap 32 / limit 300. Serpentine combined with a non-default cap or limit is not built. The serpentine code path is independent of cap, so the risk is small. | CFGS list: default, serp, alt. | low |

## 1. Spec conformance (line by line)

| Ruling | Where | Result |
|--------|-------|--------|
| Framebuffer 64x3 R,G,B, pixel = row*8 + col, row 0 top | display.c:13, 31, 43 | OK (`(row * DISPLAY_W + col) * 3`) |
| cap `(c * DISPLAY_CAP + 127) / 255`, DISPLAY_CAP 32 | display.h:19-21, display.c:15-18 | OK, evaluated in uint32 |
| units = sum of the 192 capped values | display.c:67-75 | OK |
| limit = DISPLAY_LIMIT_MA * 255 / 20 (300 mA gives 3825) | display.c:11 | OK, cast to uint32 before the multiply |
| if units > limit then v = (v * limit) / units, floor, uint32 | display.c:106-108 | OK, strict `>` |
| render writes G,R,B per pixel 0..63 | display.c:110-112 | OK (R(0) to +1, G(1) to +0, B(2) to +2) |
| render returns floor(units_after * 20 / 255) mA | display.c:116 | OK, `after` is uint32 |
| DISPLAY_SERPENTINE=1 reverses odd rows | display.c:97-101 | OK (`row & 1`, wcol = 7 - col) |
| set out of range ignored | display.c:32-34 | OK (both row and col checked) |
| get out of range leaves rgb unchanged (last commit) | display.c:46-48 | OK. The early `return` is before any write to `rgb`. The comment cites the ruling. The suite checks it (`O 1` and the preloaded `{7,8,9}` array); mutation m7 (zeroing rgb) is caught. |
| bitmap: byte 0 top row, bit 7 leftmost | display.c:60 (`0x80 >> col`) | OK; also clears first |
| icons for -1, 0, 1..8, 9..12, 100; unknown gives the -1 bitmap | icons.c:63-72 | OK. 13..15, 50, -2, 127, -128 all give index 0 (checked in the suite's UNKNOWN_IDS). |

Static RAM is 192 B (`g_fb`), matching the C7 budget line for the WS2812 framebuffer. The icon tables are `static const`.

### Limiter proof (display.c:79-85)

- If U <= L the code does not scale, so units_after = U <= L.
- If U > L then U > 0, so there is no division by zero (L = 0 is also safe, giving all zeros).
- Each scaled value is floor(v*L/U) <= v*L/U, so the sum is <= (L/U)*sum(v) = (L/U)*U = L. This needs sum(v) = U exactly. It holds because `display_units()` and the render loop both use the same `cap_channel` on the same `g_fb`.
- **units_after <= limit is always true.** I found no rounding path where it is not. The per-channel floor only lowers values.
- mA return: `after <= L = floor(mA*255/20)`, so `floor(after*20/255) <= mA`. Verified in the logs: `lim_eq` returns 300, `lim_p1` returns 290, no frame exceeds the limit, and `run_tests.py` asserts `ret <= limit_ma` for every icon.

## 2. 16-bit int audit

Every expression, with XC16 `int` = 16 bits:

| Expression | Worst case | Result |
|------------|-----------|--------|
| `(uint32_t)c * DISPLAY_CAP + 127u` | 255*32 = 8160 (64: 16320); computed in uint32 anyway | OK |
| `(uint32_t)DISPLAY_LIMIT_MA * 255u / 20u` | 300*255 = 76500 > 65535, but the cast makes it uint32 | OK (see mutation m9: without the cast sim16 fails) |
| `v * DISPLAY_LIMIT_UNITS`, v uint32 | 32*3825 = 122400 > 16 bits; uint32 | OK |
| `sum` in `display_units` (uint32) | 192*32 = 6144 (192*255 = 48960 for a cap of 255) | OK |
| `after * 20u` (uint32) | 3825*20 = 76500 | OK |
| `(uint16_t)row * DISPLAY_W + col`, then `* 3u` | 63, then 189; DISPLAY_W is `8u` | OK |
| loop counters `uint8_t`/`uint16_t` up to 192 | fits | OK |
| `0x80u >> col` | col 0..7 | OK |

No overflow, signed-overflow or int-width hazard. The sim16 (avr-gcc, `int` = 16 bits) build confirms this for all three configs.

## 3. Test quality

- **Oracle independence: good.** `oracle.py` is written from the spec only, in Python, and replays the same frames from a mirrored xorshift32. It compares the full 192-byte wire image, the mA return, the pre-limit `display_units`, a guard-byte check (4 bytes past the buffer; the buffer is pre-filled with 0xEE so every output byte must be written) and a display_get read-back of all 64 pixels.
- **Cap rounding over all 256 inputs:** `ramp_a` (0..191) and `ramp_c` (64..255) together cover every raw value for cap 32 and cap 64. The check goes through the `units` sum (and the wire bytes when the limiter is off), not per input. Mutation m11 (one input value, 77, wrong by +1) is caught by 600+ lines.
- **Limit boundary:** `lim_m1`, `lim_eq`, `lim_p1`, `lim_p2` land on exactly limit-1 / limit / limit+1 / limit+2 (verified in the host log: units 3824, 3825, 3826, 3827 for default; 1911..1914 for alt). `lim_x15` is 1.5x the limit.
- **Serpentine:** covered by the `serp` config on every frame. **Non-default cap/limit:** `alt` (64 / 150 mA). **Out of range:** set (8,0), (0,8), (8,8), (255,255), (7,255) and get. **Bitmap orientation:** four corners plus mid, full, checker, 3 random.
- **Host vs sim16:** the same oracle is applied to both builds (1000 random frames on host, 40 on sim16).
- Gaps: M1 (icon identity, above), L7, L8.

### Mutation table

Mutations were applied to copies in the scratchpad (`.../scratchpad/mut/<name>/`) and run with `make test IMPL_DIR=...`.

| ID | Mutation | Result | What caught it |
|----|----------|--------|----------------|
| m1 | serpentine applied on even rows instead of odd | caught | serp/host 3034 of 4102 lines, serp/sim16 154 of 262; default and alt pass (correct, serp off) |
| m2 | limiter `>=` instead of `>` | survives, **equivalent mutant** | at units == limit the scaling is v*L/L = v, so output is identical. Not a gap. |
| m3 | cap rounding `+128` instead of `+127` | caught | all 6 targets, 365..528 lines on host |
| m4 | limit in units + 1 (3826) | caught | 3 lines in default/serp (the boundary frames `lim_p1`/`lim_p2`), 221 in alt |
| m5 | mA return rounded up (+254) | caught | all 6 targets (62..989 lines) |
| m6 | bitmap bit order reversed (`0x01 << col`) | caught | all 6 targets, 26 lines each (bitmap cases) |
| m7 | `display_get` zeroes rgb out of range | caught | 1 line per target (the `out_of_range` getok / `O` check) |
| m8 | wire order R,G,B instead of G,R,B | caught | all 6 targets, 3025 lines on host |
| m9 | `(uint16_t)` instead of `(uint32_t)` on the limit macro | caught by sim16 only | default/sim16 and serp/sim16 fail (172 lines); host passes, as expected. In alt, 150*255 = 38250 fits in 16 bits, so alt does not catch it. This is why the sim16 build matters. |
| m10 | `v` declared `uint16_t` in render | not run | does not compile under `-Wconversion -Werror` (the compiler already guards it) |
| m11 | cap result +1 for raw input 77 only | caught | all 6 targets (24..602 lines) |
| m12 | limiter rounds to nearest instead of floor | caught | all 6 targets |
| m13 | serpentine column mapping off by one at col 7 | caught | serp/host 3025, serp/sim16 146; other configs pass |
| i1 | CW and CCW bitmaps swapped | **survives** | nothing (finding M1) |
| i2 | SWIPE_RIGHT colour changed to blue | **survives** | nothing (finding M1) |
| i3 | id 13 maps to a learned slot (off-by-one in the id range) | caught | UNKNOWN_IDS check |
| i4 | SWIPE_LEFT bitmap replaced by SWIPE_RIGHT's | caught | pairwise-distinct check |

## 4. Icons

ASCII from the suite log (`#` = lit, byte 0 on top):

```
id -1 (?)    id 1 (right)  id 2 (left)   id 3 (up)     id 4 (down)
..####..     ...#....      ....#...      ...##...      ...##...
.##..##.     ...##...      ...##...      ..####..      ...##...
.....##.     #######.      .#######      .######.      ...##...
....##..     ########      ########      ########      ...##...
...##...     #######.      .#######      ...##...      ########
...##...     ...##...      ...##...      ...##...      .######.
........     ...#....      ....#...      ...##...      ..####..
...##...     ........      ........      ...##...      ...##...

id 5 (CW)    id 6 (CCW)    id 7 (twist)  id 8 (thrust) id 100 (OK)
..####..     ..####..      ########      ..####..      ........
.#....#.     .#....#.      .######.      .#....#.      .......#
#....###     ###....#      ..####..      #..##..#      ......##
#.....#.     .#.....#      ...##...      #.#..#.#      .....##.
#......#     #......#      ...##...      #.#..#.#      #...##..
.#....#.     .#....#.      ..####..      #..##..#      ##.##...
..####..     ..####..      .######.      .#....#.      .###....
........     ........      ########      ..####..      ..#.....
```

- **Arrows (1..4):** recognisable and distinct. Left is the exact mirror of right, down the exact flip of up. Right/left have a 5-wide wedge head with a 3-row shaft; up/down have a triangular head. The two pairs differ slightly in style, which is cosmetic.
- **CW vs CCW:** see L4. They are exact mirrors, so they are distinct, but the only cue is a 3-pixel tick on the upper right versus upper left. I would not rely on it without a bench look.
- **Twist (hourglass) and thrust (target):** distinct from everything else. The metaphors are weak but acceptable.
- **Learned digits 1..4 and the check mark:** clear. `?` and "2" share their top rows (L6).
- **Colour vs limit** (cap 32, limit 300 mA = 3825 units; units and estimated mA from oracle.py):

| icon | lit px | units | mA | limited |
|------|--------|-------|----|---------|
| ? (orange) | 18 | 864 | 67 | no |
| right / left / up (one channel at 255) | 28 | 896 | 70 | no |
| down (yellow) | 28 | 1792 | 140 | no |
| CW / CCW (cyan / magenta) | 20 | 1280 | 100 | no |
| twist (white) | 40 | 3840 | 291 | **yes, slightly** (3840 > 3825; renders 31/31/31) |
| thrust (salmon) | 28 | 1344 | 105 | no |
| digits 1 / 2 / 3 / 4 (purple) | 19 / 22 / 23 / 23 | 988 / 1144 / 1196 / 1196 | 77 / 89 / 93 / 93 | no |
| check (green) | 16 | 512 | 40 | no |

  Every icon stays within 300 mA. The suite also asserts `ret <= limit` for each icon (trivially true given the limiter). Note L5.

## 5. Course rules

- **AI markers:** exact `// [AI-GENERATED: Claude Code]` ... `// [END AI-GENERATED]` in `display.h`, `display.c`, `icons.h`, `icons.c`, `test_display.c` and the stand-in sources. `#` form in the Makefile, `oracle.py` and `run_tests.py`. OK.
- **Doc comments:** see M2 (icons.h purpose lines, `cap_channel`/`icon_index` `@param`, standin `cap_of`). Every Python function and class in `oracle.py` and `run_tests.py` has a docstring with purpose, params and return; every static helper in `test_display.c` has a doc comment with `@param`/`@return`. `display.h` documents all public functions fully.
- **Fixed-width types:** all firmware types are `uint8_t`/`uint16_t`/`uint32_t`/`int8_t`. Only `#define` constants are plain (unsigned-suffixed). The test driver uses `char`/`unsigned` only in `printf` formatting.
- **No float/double/malloc/blocking in firmware/src display and icons:** grep finds only the comment "no malloc". No delays.
- **No register writes** in these modules, so the bit-field comment rule does not apply.
- **AI_USAGE.md:** one row per function present at lines 335-387: all 7 `display.c` functions (`cap_channel` included), all 4 `icons.c` functions (`icon_index` included), all test C helpers, `main`, all `oracle.py` functions (incl. `Rng`, `__init__`, `next`), all `run_tests.py` functions, and the stand-in functions. No missing rows found.
- **C99 and `-pedantic -Wconversion -Werror`:** compiles clean on host and avr-gcc.

## Commands and outputs

```
git merge --ff-only claude/optimistic-meitner-67qdon
git log --oneline -1
a12fc73 fix: display_get leaves rgb unchanged out of range (ruling WP4-a/WP4-aT); AI_USAGE rows

cd firmware/test/display && make test
PASS default/host: cap=32 limit=300mA serp=0, 24 directed + 1000 random frames and 22 icons match the spec
PASS default/sim16: cap=32 limit=300mA serp=0, 24 directed + 40 random frames and 22 icons match the spec
PASS serp/host:  ... serp=1 ...   PASS serp/sim16: ...
PASS alt/host:   cap=64 limit=150mA ...   PASS alt/sim16: ...
display suite PASS                      (about 4.5 s)

make test   (repo root)
sim16 harness PASS
ALL SUITES PASS (6 suites)              (about 61 s)
```

The mutation runner is `scratchpad/mut/run.sh`; scratch copies were not committed.
<!-- [END AI-GENERATED] -->
