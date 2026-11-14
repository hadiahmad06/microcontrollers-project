<!-- [AI-GENERATED: Claude Code] -->
# Decision sheet for contracts C1 to C7 (ticket S1-8, prep for S1-7)

> Compiled by sheet-writer on 2026-11-14 from the 7 proposals, reviews S1-1R..S1-5R, PLAN, FRAMEWORK_REVIEW, INITIAL_OVERVIEW. The sheet makes **no decisions**; every recommendation is the proposal's own post-fix-round text, shortened. Source keys: `C1`..`C7` = `proposals/C*_*.md` (section = §), `R1`..`R5` = `reviews/S1-nR.md`, `PLAN`, `FR` = FRAMEWORK_REVIEW, `OV` = `docs/archive/INITIAL_OVERVIEW.md`. **C2 (UART raw-stream protocol): not yet proposed, Sprint 2.**

## 1. How to use this sheet
- Fastest path: reply "accept all recommendations in Part A", then list overrides by ID (e.g. "C3-D4 shift 8, C5-D2b void").
- Then work Parts B (cross-contract), C (bench/team facts) and D (team/TA); each row names what it blocks.
- ⚠ marks a change from INITIAL_OVERVIEW (footnotes at the end of Part A). Nothing here is tested on hardware.

## 2. Part A: software and design decisions Hadi can make now (46)

### C1 capture buffer (8)
| ID | Decision | Recommendation | Main alternative | Source |
|---|---|---|---|---|
| C1-D1 | Stored sample format | (b) arithmetic `>>4` to 12-bit int16, 1 g about 512 | (a) raw left-justified 16-bit | C1 §1.1, §3.1 |
| C1-D2 | Buffer layout | (a) `int16_t buf[150][3]`, sample-major | (b) `buf[3][150]` axis-major | C1 §1.2 |
| C1-D3 | Where axis remap happens | (a) driver at unpack time, table in `board_axes.h`, tilt test | (b) feature code; (c) Python only | C1 §1.3, §3.3 |
| C1-D4 ⚠1 | Trigger alignment and FIFO mode | (c) Stream mode + MCU pre-trigger ring; drain loop with FIFO_SRC poll backstop | (a) Stream-to-FIFO (32 samples max) | C1 §1.4, §3.4 |
| C1-D5 ⚠1 | Pre-trigger samples P | P = 15 (90 B ring, 16 entries) | P = 0 or 30 | C1 §1.5 |
| C1-D6 | Overflow policy | (a) drop window, count overrun, re-arm; idle: only count | (b) keep window, set flag | C1 §1.6, §3.5 |
| C1-D7 ⚠2 | Number of buffers | (a) one 900 B buffer, locked until released; ring keeps draining | (b) two 900 B buffers | C1 §1.7, §3.6 |
| C1-D8 | Window length | (a) always exactly 150 samples; never zero-pad | (b) variable length with padding | C1 §1.8 |

### C3 features (7)
| ID | Decision | Recommendation | Main alternative | Source |
|---|---|---|---|---|
| C3-D1 | Mean rounding | (a) truncate toward zero (C `/`); Python `c_div_trunc` | (b) floor; (c) round half away | C3 §1.1 |
| C3-D2 | Division implementation | plain `/ 15`; mul-shift is documented fallback | `(\|s\|*34953)>>19` | C3 §1.2 |
| C3-D3 ⚠3 | Energy definition | (b) SS = sum (x - mean)^2 | (a) sum x^2 (old wording) | C3 §1.3, header |
| C3-D4 ⚠3 | Energy scaling | (b1) `isqrt(SS)`, mode 1 (range 0..7912, no divide) | shift 8 with saturation; (b2) `isqrt(SS/15)` | C3 §1.4 + table |
| C3-D5 | Feature ordering | axis-major `20*axis+2*seg+k`, k=0 mean, k=1 energy | segment-major | C3 §1.5 |
| C3-D6 | Input range handling | rely on C1 (no clamp) | clamp, or debug-only assert | C3 §1.6 |
| C3-D7 | `features_extract` signature | non-const `int16_t (*x)[3]` as built (0 warnings on XC16) | flat `const int16_t *` | C3 §1.7 |

C3-D4 note: code default is still mode 0 / shift 11 (the QA oracle encodes it). After the decision, flipping needs `FEAT_ENERGY_MODE` plus the oracle's `segment_features` (C3 §1.4).

### C4 model header and quantization (7)
| ID | Decision | Recommendation | Main alternative | Source |
|---|---|---|---|---|
| C4-D1 | NN input representation | (a) per-feature offset + pow2 shift to int8; train float net on x8. Fall back to (d) iff held-out n >= 500 shows agreement < 97 % | (d) same, int16 output | C4 §1 D1 |
| C4-D1b | Energy normalization | per-feature `nonneg` flag: off = 0, shift from P99.9, saturate | ask C3 for compressed energy | C4 §1 D1b |
| C4-D2 | Weight quantization granularity | (b) per-channel layer-1 multipliers, per-tensor layer 2; weights in [-127,127] | (a) per-tensor both | C4 §1 D2 |
| C4-D3 | Requant arithmetic | normative = int64 math; firmware may use split multiply; exporter fails loudly | (c) pre-shift to int16 (rejected) | C4 §1 D3 |
| C4-D4 | Activation range after ReLU | int8 [0,127] | uint8 [0,255] | C4 §1 D4 |
| C4-D5 | Where arrays live | `static const` in `gesture_model.h`, one includer | generated `.c` with externs | C4 §1 D5 |
| C4-D6 ⚠4 | Consistency checks | static assert; `gesture_init` refuses ODR/range mismatch; print `GM_MODEL_HASH` | drop the parameters (FR T4) | C4 §1 D6 |

C4-D6 gap: the proposal does not say what `gesture_init` returns when it refuses (the overview has `void`). See B11.

### C5 classifier output (7)
| ID | Decision | Recommendation | Main alternative | Source |
|---|---|---|---|---|
| C5-D1 | Is class 0 "none" trained | (a) yes, 9 outputs; a confident 0 is ID 0 | (b) 8 outputs, none = rejected | C5 §1 D1 |
| C5-D2 | `GESTURE_UNKNOWN` and ID space | (a) -1 (`int8_t`); built-ins 0..8, learned 9..15; `GESTURE_MAX_LEARNED = 4` | -128 or 0x7F | C5 §1 D2 |
| C5-D2b ⚠5 | `gesture_learn` return type | `int8_t`: >=1 templates stored, -1 bad id, -2 no window | `void` as in overview | C5 §1 D2b |
| C5-D3 | Confidence mapping | (a) `min(255, margin >> GM_CONF_SHIFT)`; a score, not a probability | (c) 256-entry LUT, "% sure" | C5 §1 D3 |
| C5-D4 ⚠6 | k-NN vs MLP precedence | (c) learned overrides only if gates pass and MLP weak (class 0, rejected, or conf < 192); per-class radius | (b) MLP-first only | C5 §1 D4 |
| C5-D5 | `gesture_set_reject` | reject iff `confidence < min_conf`; 0 disables; default 64, provisional | no alternative given | C5 §1 D5 |
| C5-D6 ⚠7 | Double-tap representation | (c) `uint8_t gesture_events()` read-and-clear, `GESTURE_EVT_DOUBLE_TAP = 0x01` | (b) latched flag; (a) pseudo class | C5 §1 D6 |

### C6a sensor and I/O (7 here; D7 pin map and D8 trigger are in Part B)
| ID | Decision | Recommendation | Main alternative | Source |
|---|---|---|---|---|
| C6a-D1 | I2C module and pins | (a) I2C1 on pins 17/18, `JTAGEN = OFF` | (c) I2C2 on pins 7/6 | C6a §1.1 |
| C6a-D2 | LIS3DH address | compile-time constant; probe both, verify WHO_AM_I = 0x33 | fixed 0x18 or 0x19 | C6a §1.2 |
| C6a-D3 | I2C speed | (c) 400 kHz with I2CBRG = 38 (394 kHz); fall back to 100 kHz if wiring is poor | (a) 100 kHz, BRG 157 | C6a §1.3 |
| C6a-D4 | LIS3DH interrupt routing | (a) INT1 to PIC INT0 (RB7); INT2 to PIC INT1 via PPS | (c) one wire only | C6a §1.4 |
| C6a-D5 | UART1 raw-stream baud | (a) 115200, BRGH = 1, U1BRG = 34 | (c) 250000 (check adapter) | C6a §1.5 |
| C6a-D6 | Click (double tap) start config | double-click on all axes at first, narrow after bench tests | Z only | C6a §1.6, §3.5 |
| C6a-D7b | Required config words | list in §3.8 (JTAG off, ICS, FRCPLL ...); "adopt after the lab-board check" | per lab board | C6a §1.7, §3.8 |

### C6b display (5 here; D5 bulb is in Part D, D7 pin layout in Part B)
| ID | Decision | Recommendation | Main alternative | Source |
|---|---|---|---|---|
| C6b-D1 | WS2812 driver method | (a) cycle-counted asm bit-bang, 4-LED chunks | (b) SPI encoding (fallback) | C6b §1 D1 |
| C6b-D2 | Show vs sensor/UART/I2C rule | (ii) show from main loop only, chunked, BUSY while drain pending or IR in flight | (i) never during capture | C6b §1 D2, §4.4 |
| C6b-D3 | Brightness cap | per-channel cap 32 plus software limiter, sum(R+G+B) for <= 300 mA | no cap; 25 % | C6b §1 D3 |
| C6b-D4 | Data-line level shifting | 74AHCT125-class shifter, about 330 ohm series, 500 to 1000 uF across supply | direct connection | C6b §1 D4 |
| C6b-D6 | WS2812 part variant | compile-time `WS2812_T1L_CYCLES` (9 old, 10 V5); use 9 and >= 300 us reset until known | one fixed timing | C6b §1 D6 |

### C7 budget (5 here; D4 persistence is in Part B)
| ID | Decision | Recommendation | Main alternative | Source |
|---|---|---|---|---|
| C7-D1 | Stack size | 512 B with `--stack=512` plus a paint test; no `printf` | 256 or 1024 B | C7 §1 D1 |
| C7-D2 | k-NN template element | int8 `x8`, as C4/C5 define | int16 (hypothetical) | C7 §1 D2 |
| C7-D3 | Template geometry | keep 4 x 5 int8 = 1200 B; constants compile-time | 7 x 5 (2100 B) | C7 §1 D3 |
| C7-D5 | Headroom policy | keep >= 25 % RAM (2 KB) and 30 % flash free | none stated | C7 §1 D5 |
| C7-D6 | Build rules | `-mconst-in-code`, `--heap=0`, no float/`printf`, always link with device `.gld` | none stated | C7 §1 D6 |

**Footnotes (changes from INITIAL_OVERVIEW)**
1. OV: "motion interrupt starts a 1.5 s capture window". Now: FIFO Stream mode, 15 pre-trigger samples, window cut by sample index (C1-D4/D5); trigger source is B2.
2. OV: capture buffer about 900 B. Capture path is 1188 B (900 + 96 ring + 192 staging), or 1092 B with staging capped (C1 §3.4; see B7).
3. OV/PLAN C3: "Energy = sum x^2". Now energy about the segment mean, then `isqrt` (about 15^0.5 times RMS deviation); mean carries gravity/orientation (C3 header). The 60-feature shape is unchanged.
4. OV: `void gesture_init(odr, range)` accepts anything. Now it refuses a mismatch with `GM_ODR_HZ` / `GM_RANGE_G` (100 Hz, +-4 g).
5. OV: `void gesture_learn(class_id)`. Now `int8_t` status. PLAN 3.6 "int16 features" also becomes int8 `x8` templates (C5 D4; R3 ruled it sound; PLAN line 113 already says "pending Hadi").
6. New behaviour not in OV: learned IDs 9..12 (reserve to 15), override rule, per-class radius, provisional constants 192 / 600 / 1200 / 4000.
7. New API function `gesture_events()` (OV lists 7 functions; PLAN 3.7 says "the 7 functions").

## 3. Part B: cross-contract choices (11)
| ID | Choice | Options | Recommendation | Affects |
|---|---|---|---|---|
| B1 | Pin layout (= C6a-D7 = C6b-D7) | (a) WS2812 RB15, UART TX/RX RB13/RB14, debug RB4. (b) WS2812 RB13, UART TX RB15, RX RB4, debug RA4 | C6b D7: (a) after lab-board check, (b) only if board forces RB13. C6a D7: "adopt after the lab-board check; if C6b's RB13/RB14 stands, use (b)" (wording predates C6b rev 2; both now point to (a)) | C6a map, C6b §7, bulb pins, C-1, C-2 |
| B2 | Trigger source, and meaning of `gesture_set_trigger(threshold_mg)` | hardware motion IA1 (on INT2, shared with click) vs software threshold on drained samples | C6a-D8: "software threshold first (frees an interrupt route, same rule runs in Python), keep IA1 as an optional wake-up". C1: sub-decision not made. **No proposal defines the threshold rule, default or units** | C1-D4/D5, C6a-D4, `gesture.h`, Python tool |
| B3 | Energy mode (C3-D4) vs normalization (C4-D1b) | isqrt vs shift 8 vs isqrt(SS/15); exporter needs a per-feature `nonneg` flag that C3 does not define or export | C3: isqrt(SS). C4-D1b: generic rule works for any mode; "if real small-motion energies sit at x8 of 0-2, ask C3 for a compressed energy". Decide C3-D4 first; no owner named for the `nonneg` flag | `features.c`, exporter, QA oracle, k-NN distances |
| B4 | Learned-template format and data path | int8 `x8` 60 B (C4/C5/C7) vs int16 (hypothetical, 120 B) | C5-D4 + C7-D2: int8 `x8`. `gesture_learn` stores `x8` of the most recent READY window, so it must run before the C1 buffer is released; fallback (d) in C4-D1 is only allowed if k-NN stays int8 | C1-D7, C4-D1, C5-D2b, C7-D3 |
| B5 | FIFO drain / `show()` / UART RX interaction | one 2 ms mask; chunked 4-LED; never during capture | C6b-D2 (ii) plus: drain from main loop only, RX ISR loops `while (URXDA)`, show BUSY while drain pending, no show during IR frame, gaps total <= 40 us, no priority-7 ISR. Host does not transmit during show: team question D7 | C1 §3.4, C6a-D3/D5, C6b §4, C2 |
| B6 | Persistence of learned templates (C7-D4 P1..P4) vs k-NN design (C5) | (a) RAM only; (b) flash: P1 3 B/word 2 blocks 3072 B; P2 four blocks 6144 B; P3 4 x 4 templates (changes C5); P4 no A/B; (c) dump over UART | C7-D4: "(a) for the MVP, with `knn_export()`/`knn_import()` (flat blob: version + count + data + CRC16). If persistence is wanted later, use P2." C5 §3: IDs 9..12 have no fixed meaning across resets | C5, `knn.c`, flash, D5 |
| B7 | Drain staging size | C1: 192 B (full 32-sample drain), total 1188 B. C7 table: 96 B (bursts capped at 16), total 1092 B | C1: staging "192 B (96 B if bursts are capped at 16 samples, which the loop above allows)"; C7 uses 96 and lists it as open question 1. **No single recommendation** | C1-D7, C7 RAM table (not binding: 3660 to 3972 B of 8192) |
| B8 | Lock the operating point 100 Hz, +-4 g, 12-bit, 150 samples | lock now vs revisit after real recordings | no recommendation. C3 header and C4-D6 treat it as fixed; C6a-D6 says raise ODR to 200/400 Hz if taps are missed, which changes C1, C3, C4 and FIFO seconds; C1 Q3 asks about +-4 g clipping | C1, C3, C4, C6a |
| B9 | Interrupt priorities | not specified | no recommendation (C6a §3.6 "Not decided here"). Constraint from C6b: no priority-7 ISR; UART RX does not tolerate masking, LIS3DH INT1/INT2 tolerate 2 ms | C6a, C6b |
| B10 | Double tap during an open capture window | invalidate window or ignore | no recommendation (C5 Q5, open) | C1 state machine, C5-D6 |
| B11 | API deltas vs overview | `gesture_init` return type on refusal (C4-D6); `gesture_learn` int8 (C5); `gesture_events` (C5); trigger setter (B2) | no recommendation for the `gesture_init` return type; others per Part A. PLAN 3.7 wrapper brief must list the final API | PLAN 3.7, library README |

## 4. Part C: hardware facts only the team or the bench can answer (15)
| ID | Question | Who / how | Blocks |
|---|---|---|---|
| C-1 | Does the lab board fix any pins (I2C bus, programmer header, LEDs, UART/USB bridge)? Is I2C wired to pins 17/18 or 6/7? Are both INT1 and INT2 broken out? | TA / board schematic | C6a-D1, D4, D7b; B1 |
| C-2 | Which ICSP set does the programmer header use (1, 2 or 3)? | board / TA | C6a-D7b `ICS`; B1; bulb option b pins |
| C-3 | How is LIS3DH SA0 wired (0x18 or 0x19)? | breakout schematic / bench | C6a-D2 (probe covers either) |
| C-4 | Pull-up value on the breakout; regulator or level shifter on it? | breakout schematic | C6a-D1, D3 (2.2 to 4.7 kOhm advised) |
| C-5 | Main oscillator: FRC+PLL or a crystal? Is FCY really 16 MHz (RCDIV)? | board / scope | C6a-D7b; every cycle/ms figure in C3-C7 (C3 quotes 4 MIPS) |
| C-6 | Is pin 19 DISVREG tied to VSS, with a VCAP capacitor? | board | C6a pin map |
| C-7 | LIS3DH 2-minute bench check: Stream FIFO, tilt, bits 15..4 vary and 3..0 stay 0; write 0xB0 to CLICK_THS and read it back (bit 7 latches); INT1 idles low | bench | C1-D1, C6a-D6 |
| C-8 | LIS3DH mounting on the wand (axis table); does +-4 g clip on hard swipes? Tilt test per C1 §3.3 | bench / WP2 recordings | C1-D3, B8 |
| C-9 | First I2C bring-up: scope SCL, about 100 kHz at BRG 157, about 394 kHz at BRG 38 | bench | C6a-D3 |
| C-10 | Which USB-serial adapter; does it run 115200 within +-1 % (250000 if wanted)? | team | C6a-D5, C2 |
| C-11 | WS2812B revision of the matrix (old, reset > 50 us, or V5, > 280 us); scope the T1L 9 vs 10 cycles | bench / logic analyzer | C6b-D6 |
| C-12 | Is a 5 V rail and a 74AHCT125 available in the lab kit? | team | C6b-D4 |
| C-13 | Wand power source (USB bridge, 5 V adapter, battery) | team | C6b-D3 cap |
| C-14 | Bulb or strip chosen, and its remote protocol (NEC?); IR receiver and logic analyzer available to capture codes? | team | C6b D5 (D1 in Part D), bulb pins |
| C-15 | Programmer: can it preserve a reserved flash range across downloads? Someone to read the newest LIS3DH datasheet (FIFO §5.1, CLICK_THS, CTRL_REG3) from st.com | bench / any teammate | B6 (only if persistence); C1, C6a UNVERIFIED items |

## 5. Part D: team or TA questions (11)
| ID | Question | Source |
|---|---|---|
| D-1 | May a WS2812 ring (or the matrix) count as the "bulb", or is a separate lamp mandatory? C6b recommends IR to an RGB bulb with a ring as day-one fallback ("D5") | C6b D5, Q6; R5 Q5 |
| D-2 | Is mains in a lamp socket acceptable to the instructor, or must it be the 12 V strip? (Relay option c "not recommended") | C6b §6.3, Q6 |
| D-3 | Who records training data and the 5-template spread data for the k-NN constants? | C5 Q2 |
| D-4 | Is a held-out set of >= 500 windows realistic for 9 classes? | C4 Q5, D1 |
| D-5 | Should learned gestures persist across power cycles at all? (If no, drop persistence from the flash budget.) | C7 D4, Q5; R5 Q2 |
| D-6 | Does the PC ever transmit to the wand while the matrix refreshes (recorder commands during animations)? | C6b Q8; R5 Q3 |
| D-7 | Target false-reject and false-accept rates; final `GM_DEFAULT_REJECT` (64 is a placeholder) | C5 Q4 |
| D-8 | Should learning require the MLP to say none/reject first (avoid relabeling a built-in)? | C5 Q3 (no recommendation) |
| D-9 | Distinct display icon for UNKNOWN vs 0? (WP4 assumes yes) | C5 Q1 |
| D-10 | Who owns the CRC-32 definition (exporter and host test)? Is the boot-time print enough? | C4 Q4 |
| D-11 | Course schedule: milestone and demo dates are unknown (PLAN §6) | PLAN §6, FR T9 |

## 6. Part E: what is unblocked once Part A is accepted
Gate note: PLAN §6 G1 asks for C1 to C7 in `CONTRACTS.md`; C2 is not yet proposed, so G1 is formally open until the C2 ticket (BOARD backlog, depends on C1) is done.

| Ticket | Status after Part A | Still blocked by |
|---|---|---|
| C2 UART protocol proposal | can start (needs C1) | C6a-D5 baud, C-10, B5/D-6 |
| 3.3 `features.c` (+T, +R) | can start (C1, C3) | B3 energy mode only if not taken from C3-D4 |
| 3.4 `mlp.c` (+T, +R) | can start (C4) | none (normalization is generic) |
| 3.5 reject logic | can start after 3.4 (C5) | constants stay provisional (D-7) |
| 3.6 `knn.c` | can start after 3.3 (C5, C7-D2/D3) | B4 data path, B6 only for export/import hooks |
| 3.8 bit-exact harness | can start after 3.3, 3.4 and the S1-4 simulator fix round (F1 breakpoint order, F2 parallel runs, per R4) | none |
| WP2: `export_model.py`, `infer_ref.py` (spec in C4, `quant_ref.py`) | can start | B3, D-3 (data) |
| `icons.c` (C5 IDs) | can start | D-9 |
| 3.7 `gesture.c` API | blocked | B2, B10, B11, 3.3 to 3.6 |
| WP1 `lis3dh.c`, capture state machine | host-side logic can start (C1, C6a-D2..D4) | B1, B2, B7, C-1, C-2, C-5, C-7 |
| `ws2812.c` | partly (driver logic, C6b-D1..D4) | C-11, C-12, B1, B5 |
| `bulb.c` | blocked | D-1, D-2, C-14, B1 |
| 3.9 on-target, 3.10 measurements | blocked | hardware (Part C), 3.8 |

## 7. Still UNVERIFIED (deduplicated; source in brackets)
- Newest LIS3DH datasheet revision never read; Rev 1 and AN3308 Rev 3 only [C1 Q6, C6a Q9, R1].
- FIFO keeps 12-bit data (AN says yes, datasheet §5.1 says "10bit"): bench check [C1 Q2, R1].
- `CLICK_THS` bit 7 (LIR_Click) latches; click values in C6a §3.5 are guesses; 10 ms timing units may be too coarse [C6a D6, R1].
- 1 g about 500 to 512 counts; +-4 g clipping on hard swipes [C1 Q3, Q7, R1].
- Axis-major vs sample-major speed difference unmeasured [C1 D2].
- Classification time (about 5 ms) unmeasured; single buffering depends on it [C1 Q5, C7 §6].
- I2C pull-up range 2.2 to 4.7 kOhm (I2C spec not read); SCL speed at FRC+PLL ("PLL disabled" table footnote); RCDIV requirement [C6a §3.1, §3.2, §3.8, R1].
- UART baud tolerance rule of about 3 % [C6a §3.4]; MPLAB X GUI default for JTAGEN [R1].
- All cycle counts are hand estimates (features, MLP about 16k cycles, requant, isqrt) and C3 quotes 4 MIPS vs 16 MIPS elsewhere [C3 §1, C4 §3, C7 §6, R2].
- Cost of `___muldi3` on target [C4 D3, R3]; taken-branch timing was confirmed by R5, not by C4.
- On-target (16-bit `int`) behaviour of everything: only host, QA and XC16 compile checks so far; gate G3 is mandatory [C3 §4, FR T2].
- C3 energy table is synthetic sinusoids; needs real WP2 recordings [C3 §5].
- Quantization agreement (99.3 %) is on random weights, not gesture accuracy [C4 §2].
- Provisional constants: `GESTURE_OVERRIDE_CONF` 192, radius 600/1200/4000, `GM_DEFAULT_REJECT` 64 [C5 §1, §4].
- k-NN accuracy int8 vs int16 on real data [R5]; Lowe 2004 citation detail [C5 §3, R3].
- Real C runtime RAM (64 B guess), stack high-water, `printf` flash/stack cost [C7 §2, §3.1].
- Flash: block erase time, whether the simulator models NVMCON, whether a download erases a NEVER_LOAD region, the 4096 B reservation form (2048 B form was tested), P1 3 B/word path [C7 §4, R5].
- WS2812: 20-cycle loop feasible by cycle count only; V5 parts "forgiving"; SPI inter-word gap; ISR entry/exit 10 to 20 cycles; old-part quiescent current; gap tolerance is empirical; original non-B timing [C6b §2, §3, R5].
- LIS3DH has no SCL-low timeout [C6b §4.2, R5].
- USB 100/500 mA supply; cheap RGB remotes being NEC; strip current, prices, campus Wi-Fi [C6b §5, §6, R5]; NEC numbers not re-fetched [R5].
- XC16 free licence may disable some optimisation levels (-Os) [C3 §4].
<!-- [END AI-GENERATED] -->
