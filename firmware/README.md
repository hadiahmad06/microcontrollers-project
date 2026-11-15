<!-- [AI-GENERATED: Claude Code] -->
# firmware/: gesture-wand library (PIC24FJ64GA002)

Layout (docs/human/REPO_LAYOUT.md): product code in `src/` (one `.c`/`.h` pair per module), host tests in
`test/<module>/`, Python tools in `../tools/`. Every module follows `docs/agent/CONTRACTS.md`; that file wins
over anything written here.

## Modules

| Module | Contract | What it does | Status |
|---|---|---|---|
| `lis3dh.c/.h` (+ `lis3dh_hal.h`, `board_axes.h`) | C1, C6.1 | Probe 0x18/0x19, register config with read-back, FIFO drain loop (bursts ≤ 16), byte assembly + axis remap, click read | host + sim16 tested on a fake sensor; needs the board's I2C1 HAL |
| `capture.c/.h` | C1 | Pre-trigger ring (P = 15), 150-sample window cut by index, overrun policy, single locked buffer | host + sim16 tested |
| `features.c/.h` | C3 | 60 int16 features: truncated mean + isqrt energy per axis × segment | bit-exact vs `tools/features_ref.py` |
| `mlp.c/.h` | C4 | int8 MLP 60-16-9: normalise to x8, split-multiply requant, argmax/margin; reads `gesture_model.h` | bit-exact vs `tools/infer_ref.py` |
| `knn.c/.h` | C5, C7 | Learned templates (4 × 5 × 60 B), L1 query, per-class radius, export/import blob with CRC-16 | bit-exact vs `tools/infer_ref.py` |
| `classify.c/.h` | C5 | MLP confidence, k-NN override rule, reject | bit-exact vs `tools/infer_ref.py` |
| `gesture_ids.h` | C5.1 | Class IDs and constants | – |
| `display.c/.h`, `icons.c/.h` | C6.3 | 8×8 framebuffer, icons for every class ID, brightness cap 32 + 300 mA limiter, GRB wire bytes | host + sim16 tested; the WS2812 asm bit-bang is not written yet (needs XC16 + scope) |
| `gesture.c/.h` (public API, 8 functions) | API | Glue: init, trigger, poll, classify, learn, reject, stream, events | **not written**: waits for the trigger rule (C1.9) and C2 decisions |

## Public library API (to be implemented in `gesture.c`, CONTRACTS "API")
```c
int8_t  gesture_init(uint8_t odr_hz, uint8_t range_g);   /* 0 ok; -1 odr/range != model; -2 sensor not found */
void    gesture_set_trigger(uint16_t threshold_mg);
bool    gesture_poll(void);                               /* true when a capture window is READY */
int8_t  gesture_classify(uint8_t *confidence);            /* class id or GESTURE_UNKNOWN */
int8_t  gesture_learn(uint8_t class_id);                  /* >= 1 templates stored, < 0 error */
void    gesture_set_reject(uint8_t min_conf);
void    gesture_stream_raw(bool on);
uint8_t gesture_events(void);                             /* read-and-clear, GESTURE_EVT_DOUBLE_TAP */
```

## Data path
```
LIS3DH FIFO --lis3dh_drain--> sample (wand frame) --capture_push--> 150x3 window (READY)
   --features_extract--> 60 int16 --mlp_forward--> x8[60], logits[9], top1, margin
   --knn_query--> nearest template --classify_decide--> class id + confidence --> icon_show / bulb
```

## Tests
`make test` at the repo root runs every suite. Each suite builds its tests twice:
- **host**: `cc`, 32-bit `int`, large vector sets.
- **sim16**: `avr-gcc` for an ATmega2560 run under `simavr`. It has a 16-bit `int` like XC16 and
  8 KB RAM like the PIC24FJ64GA002, so missing casts and int-promotion overflows show up
  (FRAMEWORK_REVIEW T2). It is **not** the PIC24: gate G3 (MPLAB simulator / hardware) is still required.

| Suite | Checks |
|---|---|
| `test/sim16` | the harness itself really has a 16-bit `int` |
| `test/features` | C vs an independent oracle and vs `tools/features_ref.py` (incl. its `--selftest` and ValueError cases) |
| `test/mlp` | every stage vs an independent oracle, 10 generated models (each of the 5 variants twice) incl. corner cases |
| `test/classify` | knn + decision vs an independent oracle, C5 vector table, blob import errors |
| `test/capture` | state machine vs an independent model (directed + random event streams) |
| `test/lis3dh` | driver vs a fake LIS3DH register model with fault injection |
| `test/display` | cap/limiter/serialisation vs an oracle, icon properties |
| `test/e2e` | whole path (window → class) C vs Python tools, models made by `tools/export_model.py` (gate G2) |

Each suite also has a hand-written spec stand-in (`standin/`) and was shown to fail on deliberately broken
copies; see the reviews in `docs/agent/hadi/reviews/`. Swap the implementation under test with
`make test IMPL_DIR=dir` (run `make clean` first).

Needs: `cc`, `python3` (+ numpy for the tools), and for sim16 `apt-get install simavr gcc-avr avr-libc`.
Firmware headers must be included with quotes: `-iquote` keeps `features.h` from shadowing glibc's `<features.h>`.

## Course rules (EE 2361) in this code
AI-written code is wrapped in `// [AI-GENERATED: Claude Code]` … `// [END AI-GENERATED]` and listed per
function in `/AI_USAGE.md`. C99, fixed-width types, no float/double, no malloc, no blocking delays in library
code; register writes are commented bit by bit.
<!-- [END AI-GENERATED] -->
