<!-- [AI-GENERATED: Claude Code] -->
# Interface contracts

Top-level agent doc (AGENTS.md §2, §5). Every work package codes against this file and nothing else
from another package. Changes follow AGENTS.md §5B (overrule, or discuss with the team).

**Status (2026-11-14):** C1, C3, C4, C5, C6, C7 and the public API are **decided**. C2 is **proposed only**
(`docs/agent/hadi/proposals/C2_uart_stream.md`). The bulb control method (C6.4) and the trigger rule (C1.9) are **open**.

**Provenance for everything marked decided below:**
Hadi accepted every Part A recommendation of `docs/agent/hadi/DECISION_SHEET.md` and every Part B
recommendation of `docs/agent/hadi/S1-7_DECISION_ROUND.md` (`docs/human/hadi/DECISIONS.md`, 2026-11-14).
The text here is each proposal's own recommended option. Full rationale, facts and sources stay in
`docs/agent/hadi/proposals/C*.md` and their reviews; where this file and a proposal differ, **this file wins**.
- Decided: 2026-11-14 by Hadi. Not contested.

**Changes from `docs/archive/INITIAL_OVERVIEW.md` (FYI, not a conflict with a top-level doc):** energy is measured
about the segment mean, then isqrt (C3); the window has 15 pre-trigger samples cut from a FIFO stream (C1);
`gesture_init` and `gesture_learn` return a status; `gesture_events()` is new (API); a confident class 0 is
returned as 0, not UNKNOWN (C5).

Nothing here has run on the PIC24 yet. Items marked **BENCH** must be confirmed on hardware
(`docs/agent/hadi/DECISION_SHEET.md` Part C).

---

## C0. Operating point (locked for v1)
- LIS3DH at **100 Hz ODR, ±4 g, high-resolution (12-bit)**; window **150 samples (1.5 s)**; segment = 15 samples.
- MCU PIC24FJ64GA002 at **FCY = 16 MHz** (FRC + PLL assumed; BENCH C-5). Every cycle and ms figure uses 16 MIPS.
- Revisit only through §5B, and only if bench tests show missed taps (C6.1 click) or ±4 g clipping.
- Decided: 2026-11-14 by Hadi (B8). Not contested.

---

## C1. Capture buffer (WP1 → WP3)
Source: `proposals/C1_capture_buffer.md`. Decided: 2026-11-14 by Hadi. Not contested.

1. **Sample format.** Each stored value is the left-justified 16-bit register word shifted right by 4 with an
   **arithmetic** shift: int16 in [-2048, 2047], 1 g ≈ 500 to 512 counts (nominal 512). Byte assembly must be
   `int16_t raw = (int16_t)(((uint16_t)H << 8) | L); int16_t v = raw >> 4;` (XC16 `int` is 16 bits).
2. **Layout.** `int16_t buf[150][3]`, sample-major. `buf[i][0]` = wand X, `[1]` = wand Y, `[2]` = wand Z.
3. **Axis frame.** The driver remaps sensor axes to the wand frame at unpack time, from one table (axis index
   + sign) in `board_axes.h`. Wand frame: **X out of the tip, Y to the left, Z up** (board face-up, held like a TV
   remote), right-handed. A resting axis pointing up reads **+1 g**. Everything downstream, including the UART
   stream, is in wand frame. Verified by the tilt test of C1 §3.3 (BENCH C-8).
4. **FIFO mode.** LIS3DH FIFO in **Stream mode**, watermark **FTH = 15** routed to INT1. The MCU drains bursts
   into a software pre-trigger ring and cuts the window by sample index (latency-independent).
   **Drain loop (required):** the INT0 ISR only sets a flag. The drain task:
   `loop { read FIFO_SRC; n = FSS; if n == 0 break; read min(n, 16) samples in one burst; process each sample
   strictly in order (ring push, trigger test, window append) } until FSS < 16 at the re-read`, then re-arm INT0
   (clear IF, enable). **Backstop:** the main loop polls FIFO_SRC (or reads the RB7 pin level) at least every
   50 ms. Drain runs from the main loop or a non-blocking state machine, never as one long ISR.
5. **Pre-trigger.** **P = 15** samples. For trigger sample index t the window is samples t−15 … t+134
   (150 in total). Ring: 16 entries × 6 B = 96 B.
6. **Overflow.** OVRN_FIFO seen at drain start, or a missed drain deadline, **while a window is open**: drop the
   window, increment `capture_overruns`, re-arm after a quiet period. OVRN while idle: count only. I1_OVERRUN is
   enabled in **CTRL_REG3**.
7. **Buffers.** One 900 B buffer. States `IDLE → ARMED → CAPTURING (150 samples) → READY (locked) → release
   → ARMED`. In READY the driver keeps draining into the ring and ignores triggers until release plus a
   refractory time. A gesture made while the buffer is locked is lost (accepted).
8. **Window length.** Always exactly 150 samples; never zero-padded (zero is not "at rest").
9. **Trigger source.** A **software threshold** on drained samples, the same rule in firmware and in the Python
   tool. Hardware IA1 is only an optional wake-up. **OPEN:** the exact rule, its units (`threshold_mg`), default
   and refractory time come from ticket S2-2 (proposal) and need a decision before the capture state machine is
   coded. (B2)
10. **Drain staging.** Bursts are capped at 16 samples: staging buffer **96 B**; capture path total
    900 + 96 + 96 = **1092 B**. (B7)
11. **Double tap during an open window** does not invalidate the window; the event is still reported by
    `gesture_events()`. (B10)
12. **Learning uses the locked window.** `gesture_learn` stores the `x8` vector of the most recent READY window,
    so it must be called before that buffer is released. (B4)

---

## C2. UART raw stream (WP1 → WP2): **PROPOSED, NOT DECIDED**
Proposal: `docs/agent/hadi/proposals/C2_uart_stream.md` (ticket S2-1, review S2-1R).
Fixed already by other contracts: UART1 at 115200 baud (C6.1), sample format and wand frame (C1).

---

## C3. Features (WP2 ⇄ WP3)
Source: `proposals/C3_features.md` (energy option b1). Decided: 2026-11-14 by Hadi. Not contested.

Valid only at the C0 operating point. Input: a C1 window, every value in [-2048, 2047]; outside that range the
behaviour is undefined (no clamp: C1 guarantees the range). Output: 60 int16.
```
trunc_div(a, b): C99 '/' (truncate toward zero); in Python c_div_trunc
isqrt(n):        largest r with r*r <= n (digit-by-digit, no multiply, no divide)
for a in 0..2:            // X, Y, Z
  for s in 0..9:          // segment s covers samples 15*s .. 15*s+14
    sum    : int16  = x[15s][a] + ... + x[15s+14][a]          // in [-30720, 30705]
    mean   : int16  = trunc_div(sum, 15)                       // plain '/ 15'
    SS     : uint32 = 0
    for j in 0..14:
        d : int16  = x[15s+j][a] - mean
        SS += (uint32)((int32)d * (int32)d)                    // cast BEFORE multiply
    energy : int16 = isqrt(SS)                                  // in [0, 7912]
    out[20*a + 2*s    ] = mean
    out[20*a + 2*s + 1] = energy
```
- **Ordering:** `idx = 20*axis + 2*segment + k`, k = 0 mean, k = 1 energy (axis-major).
- **Non-negative flag (B3):** odd index (energy) = non-negative, even index (mean) = signed. C3 owns it: it ships
  as `FEAT_IS_NONNEG(i)` in `features.h` and `NONNEG` in `tools/features_ref.py`; the exporter reads it there.
- **Version:** `FEATURES_VERSION = 1` (must equal `GM_FEATURE_VERSION`, C4).
- **C signature:** `void features_extract(int16_t (*x)[3], int16_t out[60]);` (non-const on purpose: xc16-gcc 2.10
  warns on a `const int16_t (*)[3]` parameter for plain array callers; the function never writes `x`).
- **Python reference:** `tools/features_ref.py`, integer-only, bit-exact with the C.
- Cost (estimate): about 5 to 9 k cycles per window, about 0.3 to 0.56 ms at 16 MIPS.

---

## C4. Model header `gesture_model.h` and quantization (WP2 → WP3)
Source: `proposals/C4_model_header.md`, executable spec `docs/agent/hadi/spikes/quant/quant_ref.py`.
Decided: 2026-11-14 by Hadi. Not contested.

### C4.1 Integer inference (normative)
`>>` is an arithmetic flooring shift. Never use C `/` on negatives.
```
RSHIFT_R(v, s) = (v + (((int32_t)1 << s) >> 1)) >> s      # s in 0..14 only; s == 0 -> v
SAT(v, lo, hi) = min(max(v, lo), hi)
Stage 0:  d = (int32_t)x - (int32_t)GM_IN_OFF[i];  x8[i] = SAT(RSHIFT_R(d, GM_IN_SH[i]), -127, 127)
Layer 1:  acc1[j] = GM_B1[j] + sum_i (int32_t)GM_W1[j][i] * x8[i]
          h[j]    = SAT(RSHIFT_R64(acc1[j] * GM_M1[j], GM_SH1[j]), 0, 127),  RSHIFT_R64(p, s) = (p + 2^(s-1)) >> s
                    on the exact product (ReLU = the lower clamp)
Layer 2:  logit[c] = GM_B2[c] + sum_j (int32_t)GM_W2[c][j] * h[j]          (int32, no requant, no clamp)
Argmax:   lowest index with the maximum logit; top2 = largest among c != top1, lowest index on ties;
          margin = logit[top1] - logit[top2] >= 0
```
- Requant may be computed with int64 or with the int64-free **split multiply** of C4 §2 (proven identical for
  `2^14 <= M < 2^15`, `16 <= SH <= 31`); firmware uses the split multiply.
- Activations after ReLU are int8 in [0, 127].

### C4.2 Header format
Generated by `tools/export_model.py`; `static const` arrays (program memory via PSV), **one includer: `mlp.c`**.
Row-major, no padding. Macros: `GM_FORMAT_VERSION` (1), `GM_N_FEATURES` (60), `GM_N_HIDDEN` (16),
`GM_N_CLASSES` (9), `GM_ODR_HZ` (100), `GM_RANGE_G` (4), `GM_N_SAMPLES` (150), `GM_FEATURE_VERSION` (1),
`GM_MODEL_HASH` (CRC-32 IEEE over the little-endian bytes of all arrays, in file order), `GM_CONF_SHIFT`,
`GM_DEFAULT_REJECT`, `GM_LOGIT_SCALE_Q32`, `GM_STATIC_ASSERT(c, name)` (typedef trick; XC16 v2.10 has no
`_Static_assert`). Arrays: `int16_t GM_IN_OFF[60]`, `uint8_t GM_IN_SH[60]`, `int8_t GM_W1[16][60]`,
`int32_t GM_B1[16]`, `uint16_t GM_M1[16]`, `uint8_t GM_SH1[16]`, `int8_t GM_W2[9][16]`, `int32_t GM_B2[9]`.
Layout example: C4 §2 "Header layout".

### C4.3 Training and export
- **Input representation (D1):** per-feature offset + power-of-two shift to int8 `x8`; the float model is trained
  directly on `x8` (optionally divided by a constant for conditioning, multiplied back into W1 by the exporter),
  so the exporter does no offset fold.
- **Fallback to int16 inputs (option d)** on a fixed held-out set of **n ≥ 500 windows** iff float-vs-int argmax
  agreement < 97 %, **or** (float accuracy − int accuracy > 1 pt **and** the one-sided 95 % Wilson upper bound of
  the int accuracy is below the float accuracy) (`fallback_needed()` in `quant_ref.py`). k-NN stays int8 either way.
- **Normalization (D1b):** non-negative feature (C3 flag): `off = 0`; signed: `off = round(median)`.
  `s_i` = smallest s in 0..14 with `RSHIFT_R(P99.9(|x − off|), s) <= 127`; values above saturate.
- **Weights (D2):** symmetric int8 in [-127, 127], zero point 0; **per-channel** M1/SH1 for layer 1, per-tensor
  layer 2 (per-channel layer 2 is forbidden).
- **Exporter recipe and bounds:** C4 §2 steps 1 to 6. It fails loudly (never clamps) unless every scale is in
  [2^-17, 0.5), `2^14 <= M < 2^15`, `16 <= SH <= 31`, `GM_IN_SH <= 14`, `|B| < 2^29`, and the weight-only worst
  cases `|B| + 127·Σ|W| < 2^30` for both layers.
- **Evaluation rule:** every reported accuracy, model selection and early-stopping decision uses the integer path
  (`tools/infer_ref.py`) on the held-out set; float accuracy is diagnostic only. Test vectors export
  window → features → x8 → acc1 → h → logits → class.
- **Consistency checks (D6):** `GM_STATIC_ASSERT` at compile time; `gesture_init(odr_hz, range_g)` refuses a
  mismatch with `GM_ODR_HZ` / `GM_RANGE_G` (API); `GM_MODEL_HASH` printed at boot.

---

## C5. Classifier output (WP3 → WP4)
Source: `proposals/C5_classifier_output.md`. Decided: 2026-11-14 by Hadi. Not contested.

### C5.1 IDs and constants
```c
#define GESTURE_UNKNOWN        (-1)   /* int8_t: rejected / ambiguous */
#define GESTURE_NONE            0     /* trained class: idle, noise, bumps; "show nothing" */
#define GESTURE_SWIPE_RIGHT     1
#define GESTURE_SWIPE_LEFT      2
#define GESTURE_RAISE           3
#define GESTURE_PUSH_DOWN       4
#define GESTURE_CIRCLE_CW       5
#define GESTURE_CIRCLE_CCW      6
#define GESTURE_TWIST           7
#define GESTURE_THRUST          8
#define GESTURE_LEARNED_BASE    9     /* == GM_N_CLASSES (static-assert) */
#define GESTURE_MAX_LEARNED     4     /* ids 9..12; 13..15 reserved */
#define GESTURE_TEMPLATES_PER_CLASS 5
#define GESTURE_EVT_DOUBLE_TAP  0x01u
#define GESTURE_LEARN_ERR_ID        (-1)
#define GESTURE_LEARN_ERR_NO_WINDOW (-2)
#define GESTURE_OVERRIDE_CONF       192   /* provisional */
#define GESTURE_KNN_RADIUS_MIN      600   /* provisional */
#define GESTURE_KNN_RADIUS_DEFAULT  1200  /* provisional */
#define GESTURE_KNN_RADIUS_MAX      4000  /* provisional */
```
- IDs 0..8 equal the MLP output index. The MLP never emits 9..15. Learned IDs have no meaning across resets.

### C5.2 Confidence and classification
- **MLP confidence:** `c = min(255, margin >> GM_CONF_SHIFT)`. A score, **not** a probability. The exporter picks
  `GM_CONF_SHIFT` as the smallest shift for which the 95th percentile of margins of correctly classified
  validation windows is ≤ 255 (asserts ≤ 24).
- **k-NN:** L1 distance over the int8 `x8` vector. `d1` = nearest template (class `kid`, lowest slot on ties);
  `d2` = nearest template of any other class; `c_k = 255` if no other-class template, else
  `0 if d2 == 0 else ((uint32_t)(d2 − d1) * 255) / d2`.
- **Per-class radius:** `R_c = clamp(2 · lower_median(pairwise L1 of class c's templates), MIN, MAX)`, where
  `lower_median` of the sorted `n(n−1)/2` distances is element `(k−1)//2`; fewer than 2 templates → `DEFAULT`.
- `gesture_classify` (normative):
```
1. MLP:   id = top1;  c = min(255, margin >> GM_CONF_SHIFT)
2. if n_learned_templates > 0:
       k, kid, d1, d2, c_k as above
       weak = (id == 0) or (c < min_conf) or (c < GESTURE_OVERRIDE_CONF)
       if weak and d1 <= R[kid] and c_k >= min_conf:  id, c = kid, c_k
3. if conf != NULL: *conf = c        # written also when rejected
4. return (c < min_conf) ? GESTURE_UNKNOWN : id
```
  All divisions are floor divisions of non-negative operands. `(d2 − d1) * 255` needs `uint32_t`.
  Required test vectors: C5 §2 table (asserted by `selftest_c5` in `quant_ref.py`).
- **Reject (`gesture_set_reject`):** reject iff `confidence < min_conf` (strict, unsigned); 0 disables; applies to
  MLP, k-NN and class 0. Default `GM_DEFAULT_REJECT` (provisional 64; exporter rule: smallest value with ≤ ~2 %
  of held-out true gestures rejected). Callable before or after `gesture_init`; persists until reset.
- **Learning (`gesture_learn`):** stores one `x8` template per call (C1.12), round-robin overwrite when the class
  has 5. Returns ≥ 1 = templates now stored for the class, `GESTURE_LEARN_ERR_ID` for an id outside
  `[9, 9 + GESTURE_MAX_LEARNED − 1]`, `GESTURE_LEARN_ERR_NO_WINDOW` if no window is available. Never touches the MLP.
- **Events (`gesture_events`):** read-and-clear bitmask; the click ISR sets `GESTURE_EVT_DOUBLE_TAP` when
  LIS3DH `CLICK_SRC` (0x39) shows IA (bit 6) and DCLICK (bit 5). Never a class ID, not subject to `min_conf`;
  repeated taps coalesce.

---

## C6. Pins, peripherals and timing
Sources: `proposals/C6a_sensor_io.md`, `proposals/C6b_display_bulb.md`. Decided: 2026-11-14 by Hadi. Not contested,
except C6.4 (open).

### C6.1 Sensor and I/O (C6a)
- **I2C:** I2C1 on pins 17/18 (SCL1 RB8, SDA1 RB9), config `JTAGEN = OFF`; external pull-ups 2.2 to 4.7 kΩ
  (BENCH C-4). **400 kHz with I2C1BRG = 38** (394 kHz); fall back to 100 kHz (BRG 157) if wiring is poor (BENCH C-9).
- **LIS3DH address:** compile-time constant; `init` probes 0x18 and 0x19 and verifies WHO_AM_I (0x0F) = 0x33.
- **Interrupts:** LIS3DH INT1 → PIC INT0 (RB7, pin 16, fixed); LIS3DH INT2 → PIC INT1 via PPS from RB12 (pin 23).
  INT1 = FIFO watermark (+ overrun); INT2 = click. Rising edge (LIS3DH active high).
- **UART1:** 115200 baud, BRGH = 1, U1BRG = 34 (114286, −0.79 %). RX ISR loops `while (U1STAbits.URXDA)`.
- **Click (double tap) start values** (tune on the bench): CLICK_CFG = 0x2A (double click X, Y, Z),
  CLICK_THS = 0xB0 (latch + 48 counts = 1.5 g), TIME_LIMIT = 0x04, TIME_LATENCY = 0x10, TIME_WINDOW = 0x30,
  CTRL_REG6 = 0x80 (click on INT2). Narrow the axes after bench tests.
- **Config words:** C6a §3.8 (JTAGEN off, ICS = PGx1, I2C1SEL = 1, IOL1WAY off during development, FNOSC = FRCPLL,
  POSCMD = 11, FWDTEN off). Adopt after the lab-board check (BENCH C-1, C-2, C-5). `AD1PCFG = 0xFFFF` in
  `board_init`. DISVREG (pin 19) tied to VSS with a VCAP capacitor (BENCH C-6).
- **Pin layout (a), provisional until the lab-board check (B1):**

| Pin | Use |
|---|---|
| 4, 5 (RB0, RB1) | ICSP PGED1/PGEC1 (assumes set 1) |
| 11 (RB4) | debug / timing pin |
| 16 (RB7, INT0) | LIS3DH INT1 |
| 17, 18 (RB8, RB9) | I2C1 SCL, SDA |
| 23 (RB12, RP12) | LIS3DH INT2 → INT1 |
| 24 (RB13, RP13) | UART1 TX |
| 25 (RB14, RP14) | UART1 RX |
| 26 (RB15) | WS2812 data |
| 2, 3, 6, 7, 9, 10, 12, 14, 15, 21, 22 | spare (see C6a §3.7 and C6b §7 for bulb candidates) |

### C6.2 Interrupt priorities (B9)
UART1 RX = 6, INT0 (FIFO watermark) = 5, INT1 (click) = 4, timers = 3, everything else ≤ 2. **Nothing at 7.**
Every ISR only sets flags or moves bytes, budget ≈ 15 µs each, 40 µs total for all ISRs pending at once.

### C6.3 Display (C6b)
- **Driver:** cycle-counted asm bit-bang, interrupts masked (`SRbits.IPL = 7`) for at most one **4-LED chunk**
  (≈ 138 µs), then restore IPL and run ≥ 10 NOPs. `DISI` is not used. SPI encoding is the fallback.
- **Rules (C6b §4.4):** (1) `ws2812_show()` runs only from the main loop and returns BUSY while a FIFO drain is
  pending or running, or an IR frame is in flight. (2) mask one chunk at a time as above. (3) gap budget 40 µs
  total. (4) chunk-boundary low time is empirical (scope-verify). (5) no show while an IR frame is in flight.
  (6) no flash write during a show, an IR frame or a capture window. (7) ≥ 300 µs low after the last chunk.
- **Brightness:** compile-time per-channel cap 32 plus a software limiter on Σ(R+G+B) so the estimated draw stays
  ≤ 300 mA.
- **Hardware:** 74AHCT125-class level shifter, ≈ 330 Ω series resistor, 500 to 1000 µF across the matrix supply;
  prefer a separate 5 V supply with common ground (BENCH C-12, C-13).
- **Part variant:** compile-time `WS2812_T1L_CYCLES` = 9 (old WS2812B) or 10 (V5); use 9 and a ≥ 300 µs reset
  until the part is known (BENCH C-11).
- **Show vs UART (B5):** the RX-loop plus 4-LED chunking above. A "host does not transmit during show" rule is
  added only if C2 needs PC → wand traffic during animations (team question D-6).

### C6.4 Bulb control: **OPEN**
Team questions D-1, D-2, BENCH C-14. C6b recommends IR (NEC) to an RGB bulb with a WS2812 ring as the day-one
fallback, but this was not decided.

---

## C7. Resource budget
Source: `proposals/C7_budget.md`. Decided: 2026-11-14 by Hadi. Not contested.
- **Stack:** 512 B (`--stack=512`, default 16 B guard) plus a paint test reporting the high-water mark; raise to
  768 B only if more than 300 B is used. No `printf`/`sprintf` in the product build.
- **k-NN templates:** int8 `x8`, 4 classes × 5 templates × 60 B = **1200 B**; `GESTURE_MAX_LEARNED` and
  `GESTURE_TEMPLATES_PER_CLASS` are compile-time constants.
- **Persistence (B6):** RAM only for the MVP, with `knn_export()` / `knn_import()` (flat blob: version + count +
  data + CRC16). If persistence is wanted later: design P2 of C7 §4 (adds `gesture_save`). Team question D-5.
- **Headroom:** keep ≥ 25 % RAM (2 KB) and ≥ 30 % flash free at every milestone.
- **Build rules:** `-mconst-in-code` (default), `--heap=0`, no float/double/printf, always link with the device
  linker script `p24FJ64GA002.gld` (or build in MPLAB X), check the `.map` file at every milestone; all `const`
  data in one 32 KB PSV page.
- **RAM budget (with C1.10's 96 B staging):** capture 900, ring 96, staging 96, features 120, feature scratch 32,
  MLP working set 112, k-NN templates 1200, k-NN metadata 16, WS2812 framebuffer 192, UART rings 160
  (C2 pending), I2C 32, app globals 96, bulb/IR 32, C runtime 64 (UNVERIFIED), stack 512 = **3660 B (44.7 %)**.

---

## API: public library functions (`gesture.h`)
Decided: 2026-11-14 by Hadi (B11, C4 D6, C5 D2b/D6). Not contested. Eight functions:
```c
int8_t  gesture_init(uint8_t odr_hz, uint8_t range_g);   /* 0 ok; -1 odr/range != model (GM_ODR_HZ/GM_RANGE_G);
                                                             -2 sensor not found (WHO_AM_I) */
void    gesture_set_trigger(uint16_t threshold_mg);       /* meaning: C1.9, OPEN (S2-2) */
bool    gesture_poll(void);                               /* true when a capture window is READY */
int8_t  gesture_classify(uint8_t *confidence);            /* class id or GESTURE_UNKNOWN (C5.2); conf may be NULL */
int8_t  gesture_learn(uint8_t class_id);                  /* C5.2 learning */
void    gesture_set_reject(uint8_t min_conf);             /* C5.2 reject */
void    gesture_stream_raw(bool on);                      /* C2, PROPOSED */
uint8_t gesture_events(void);                             /* read-and-clear event bits (C5.2) */
```
Suggested names for the init codes: `GESTURE_INIT_OK 0`, `GESTURE_INIT_ERR_CONFIG (-1)`, `GESTURE_INIT_ERR_SENSOR (-2)`.
Internal module APIs (`features.h`, `mlp.h`, `knn.h`, ...) are defined by their tickets in `docs/agent/hadi/BOARD.md`
and must not contradict this file.
<!-- [END AI-GENERATED] -->
