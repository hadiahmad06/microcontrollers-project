<!-- [AI-GENERATED: Claude Code] -->
# Gesture-recognition magic wand: project report (DRAFT)

> Draft for the team, written by Hadi's agents on 2026-11-15 from what is in the repo. Every number below names
> its source file. Anything **SYNTHETIC** comes from generated data, not recordings. Edit freely; nothing here is a decision.

## Status at a glance
**Done (host + 16-bit-int simulator):** integer feature extraction, int8 MLP inference, k-NN learning and the
decision/reject logic, the capture state machine, the LIS3DH driver (against a fake sensor), display logic and icons,
the Python reference tools, export and training pipeline, and gate **G2** (C equals Python, bit-exact, end to end).
**Not done:** gate **G3** on the PIC24 (XC16 + MDB are only on Hadi's Mac); `gesture.c` (the 8-function public API,
waiting on decisions Q1/Q2); the trigger module and C2 UART TX pump in `firmware/src`; the PIC24 HAL; the WS2812 asm
driver; the bulb (method undecided, CONTRACTS C6.4); real recordings and real accuracy; on-target cycle and flash
measurements; the demo (G4).

## 1. Goal and hardware
A handheld wand with an LIS3DH accelerometer; a PIC24FJ64GA002 (16 MIPS, 64 KB flash, 8 KB RAM, no FPU, no DMA)
classifies the motion as one of 8 gestures, shows an icon on an 8×8 WS2812 matrix and controls a light
(`docs/archive/INITIAL_OVERVIEW.md`, `docs/archive/proposal.pdf`). Toolchain: XC16 v2.10, MPLAB X v6.35.
Operating point (CONTRACTS C0): 100 Hz, ±4 g, 12-bit high resolution, FIFO stream mode; one window = 150 samples
(1.5 s), split into 10 segments of 15.
Class IDs (C5.1): 0 none, 1 swipe right, 2 swipe left, 3 raise, 4 push down, 5 circle CW, 6 circle CCW, 7 twist,
8 thrust; learned classes 9..12; `GESTURE_UNKNOWN` = −1. Double tap is a hardware click event, not a class.
Changes from the original overview are listed at the top of `docs/agent/CONTRACTS.md` (energy about the segment mean,
then isqrt; 15 pre-trigger samples; status return codes; `gesture_events()`; a confident class 0 is returned as 0).

## 2. Architecture
```
LIS3DH FIFO (stream mode, watermark 16 -> INT1 -> PIC INT0 flag)
  -> lis3dh_drain   (main loop; bursts <= 16; byte assembly, >>4, axis remap to wand frame)
  -> trigger        (software threshold, proposal C1b; not yet in firmware/src)
  -> capture        (16-entry pre-trigger ring, window = samples t-15 .. t+134, single locked buffer)
  -> features_extract (60 int16: truncated mean + isqrt energy per axis x segment)
  -> mlp_forward    (x8 normalisation -> 60-16-9 int8 MLP -> logits, top1, margin)
  -> knn_query      (L1 over x8 against up to 4 x 5 learned templates)
  -> classify_decide (class id + confidence 0..255, or GESTURE_UNKNOWN)
  -> icon_show / display_render -> WS2812 (asm driver not written) ; bulb (method open)
```
Public API (CONTRACTS "API"): `gesture_init`, `gesture_set_trigger`, `gesture_poll`, `gesture_classify`,
`gesture_learn`, `gesture_set_reject`, `gesture_stream_raw`, `gesture_events`. The glue design is in
`docs/agent/hadi/proposals/API_glue.md` (corrected after the integration spike, §5). Module status: `firmware/README.md`.

## 3. Design decisions (decided 2026-11-14 by Hadi; full text in CONTRACTS.md)
- **Capture (C1).** The FIFO is 32 deep (320 ms at 100 Hz), so it runs in stream mode with a watermark at 16; the
  interrupt only sets a flag and the main loop drains. The window is cut by sample index, which makes it independent
  of interrupt latency; 15 pre-trigger samples; always exactly 150 samples, never zero-padded; an overrun during an
  open window drops the window. Capture-path RAM: 900 + 96 + 96 = 1092 B.
- **Features (C3).** Mean by C99 truncating division (the Python reference emulates it: Python `//` floors). Energy
  is the sum of squared deviations about the segment mean, then an integer square root: removing the mean keeps
  gravity/orientation out of the energy, and isqrt compresses four decades of dynamic range into a fixed int16 range
  (max 7912) with no data-dependent shift. Every product is cast to int32 before the multiply.
- **Quantisation (C4).** Each feature is offset and shifted to an int8 `x8`; the float net is trained directly on
  `x8`, so the exporter does no offset fold. Symmetric int8 weights, per-channel requantisation for layer 1,
  per-tensor layer 2, following Jacob et al. 2018. Requantisation uses a split 16×16 multiply that avoids int64 and
  is proven identical to the exact product for the allowed multiplier/shift range. The exporter fails loudly instead
  of clamping; `GM_MODEL_HASH` (CRC-32) identifies the model, and `gesture_init` refuses a sensor configuration the
  model was not trained for.
- **Output (C5).** Confidence = `min(255, margin >> GM_CONF_SHIFT)`: a score, not a probability; strict reject
  `confidence < min_conf`. Learned gestures use L1 nearest-template matching on `x8` (4 classes × 5 templates ×
  60 B = 1200 B) with a per-class radius; a learned class may override the MLP only when the MLP is weak. The
  thresholds are provisional until real data exists (open question Q8).
- **Pins, interrupts, display (C6).** I2C1 at 394 kHz; LIS3DH INT1 → INT0 (FIFO), INT2 → INT1 (click); UART1 at
  115200; priorities UART 6 > FIFO 5 > click 4 > timers 3, nothing at 7. The WS2812 bit-bang masks interrupts for at
  most one 4-LED chunk (~138 µs) and runs only from the main loop; brightness cap 32 plus a 300 mA limiter. The pin
  layout is provisional until the lab-board check.
- **Budget (C7).** 512 B stack, no printf, ≥ 25 % RAM and ≥ 30 % flash free; estimated RAM 3660 B (44.7 %);
  learned templates live in RAM only.

## 4. Verification method
1. **Separation of duties.** Every module was implemented by one agent, tested by a second agent that wrote an
   independent oracle from the contract text (never reading the implementation), and reviewed by a third.
2. **Bit-exactness.** Each stage of the C pipeline is compared value by value with the Python references
   (`tools/features_ref.py`, `tools/infer_ref.py`). Example: review W2-1R found 0 mismatches over 3000 vectors
   between the C MLP and `infer_ref`.
3. **16-bit integers without the PIC24.** XC16's `int` is 16 bits; a host compiler's is 32, so a missing cast can pass
   every host test. Every suite is therefore also built with avr-gcc for an ATmega2560 (16-bit `int`, 8 KB RAM) and
   run under simavr ("sim16"). Evidence from deliberately injected bugs:

   | Injected bug | Host | sim16 | Source |
   |---|---|---|---|
   | features: `(int32_t)(d*d)` (cast after the multiply) | PASS | FAIL (282 windows) | `reviews/3.3R.md` |
   | mlp: requant `(int32_t)(hi*(int16_t)m)` | PASS | FAIL | `reviews/3.4R.md` |
   | k-NN: `(d2-d1)*255` without the `uint32_t` cast | PASS | FAIL | `reviews/3.5R.md` |
   | lis3dh: byte assembly without the `(uint16_t)` cast | PASS | PASS | invisible to tests: checked by review (`reviews/WP1-bR.md`) |

   sim16 is not the PIC24: gate G3 (XC16 build + MPLAB simulator or board) is still required.
4. **Mutation testing.** Reviewers broke copies of the code on purpose; every suite caught every behaviour-changing
   mutation, or the gap was closed in a fix round (details per review in `docs/agent/hadi/reviews/`).
5. **Gate G2.** The end-to-end suite (`firmware/test/e2e`) runs raw windows through the whole C path and the Python
   tools, with models produced by the real exporter, on host and sim16, and forces every decision boundary (int8
   saturation, logit ties, radius edges, confidence gates) to occur on purpose.

## 5. Results
- `make test` at the repo root: **ALL SUITES PASS (8 suites)** (sim16 self-test, features, mlp, classify, capture,
  lis3dh, display, e2e).
- **Integration spike** (`docs/agent/hadi/spikes/integration/`), the whole stream pipeline with a fake sensor;
  **SYNTHETIC, UNVERIFIED**:
  ```
  run      gest   hit   det   accC  lock   gap  miss  false  windows gap-windows
  main       48    46  96%  87%     0     0     2      1       47      0
  big       160   154  96%  91%     0     0     6      5      159      0
  tight      32    25  78%  48%     6     0     1      1       26      0
  stall0     24    23  96%  91%     0     1     0      0       23      2
  stall1     24    22  92%  91%     0     2     0      0       22      0
  short       8     7  88% 100%     0     0     1      0        7      0
  ```
  Host and sim16 outputs are identical, and the Python replay matches the C output. Observations: dead time after a
  trigger ≈ 1.7 s; slow-start gestures trigger 10–40 samples late; learned templates override too eagerly with the
  provisional C5 constants (Q8); training on fixed-onset windows scores 99 % but 82 % on trigger-cut windows.
- **Proxy memory** (avr-gcc, `docs/agent/hadi/measurements.md`; not the PIC24): static RAM of the finished modules
  2512 B against 2500 B in the C7 budget for the same items.

  | Module | code (AVR) | const data (flash on PIC24) | static RAM |
  |---|---:|---:|---:|
  | features | 402 | 0 | 0 |
  | capture | 548 | 0 | 1007 |
  | knn | 1912 | 0 | 1216 |
  | classify | 192 | 0 | 0 |
  | mlp | 1278 | 1432 | 0 |
  | display | 736 | 0 | 192 |
  | icons | 146 | 165 | 0 |
  | lis3dh | 936 | 6 | 97 |
  | **Total** | 6150 | 1603 | **2512** |
- **Cycles:** not measured. The only figure is the C3 estimate of 5–9 k cycles per window (0.3–0.56 ms at 16 MIPS).
- **Accuracy on real gestures:** unknown; no recordings exist yet.

## 6. Process and AI usage
The work ran as sprints on a board (`docs/agent/hadi/BOARD.md`): 19 review reports in `docs/agent/hadi/reviews/`,
every implementation with its own tester and reviewer, two pre-merge reviews before Sprint 2 was merged into `main`
(PR hadiahmad06/microcontrollers-project#1). Top-level decisions were made only by Hadi and are logged with
provenance in `docs/human/hadi/DECISIONS.md` and the top-level docs.
Course rule on AI-written code: every AI-written block is wrapped in `// [AI-GENERATED: Claude Code]` …
`// [END AI-GENERATED]` and every AI-written function has a row in `AI_USAGE.md` (about 640 rows: ~57 product
firmware, ~380 test, ~100 tools, ~100 spikes). Agent commits are made under the name `Hadi Ahmad (Claude)` with a
co-author trailer.
Problems met: container restarts and an API limit interrupted running agents (all work was already committed);
one worktree started from a stale commit; one review ticket (the LIS3DH driver) was initially missing.

## 7. Open items
- Decisions (`docs/agent/hadi/open_questions.md`): Q1 C2 UART stream; Q2 trigger rule; Q3 C1.6 conflict;
  Q4–Q7 contract wording; Q8 provisional C5 constants.
- Bench: S2-0b simulator self-test; DECISION_SHEET Part C (C-1..C-15); CLICK_THS bit-7 read-back; FIFO_SRC at 32
  unread; LIS3DH reserved-bit comments; click threshold tuning.
- Engineering: trigger module → C2 TX pump → `gesture.c`; PIC24 HAL; WS2812 asm driver; bulb (C6.4); recorder,
  real data, training; G3 and on-target measurements; the G4 demo.
- Team questions D-1..D-11 (DECISION_SHEET Part D) and the course schedule.
- Known limits: learned gestures are lost at power-off; a gesture made while the buffer is locked is lost.

## 8. References
See `docs/agent/hadi/CITATIONS.md` (datasheets, application notes, papers, catalogues and internal provenance, with
the gaps that still need a check before the final report).
<!-- [END AI-GENERATED] -->
