# Project plan: compartmentalized work packages

> Agent draft for `hadi`, 2026-11-14. Hadi hasn't approved it yet. Once Hadi says to use it,
> it moves to `docs/agent/PLAN.md` (AGENTS.md §5A).
> Sources: `docs/archive/proposal.pdf`, `docs/archive/INITIAL_OVERVIEW.md`, `docs/human/TEAM_PROCESS.md`.
> **Everyone owns everything.** The work packages below organize the *work*. They don't assign
> owners. Anyone, or anyone's agent, can pick up any ticket.

## 0. How the work is cut

The project splits into **5 work packages (WPs)**. The packages connect only through
**written interface contracts (C1–C7)**. A WP may assume nothing about another WP except
what a contract says. That is what lets four people (and their agents) work in parallel, and
what lets a Sonnet subagent get an unambiguous brief.

```
           C1 capture buffer        C3 features      C4 gesture_model.h
 WP1 Sensor ───────────────► WP3 Classifier ◄──────── WP2 Data & Training
    │  C2 UART stream ────────────────────────────────►  │
    │                              │ C5 result/event      │ C3 reference impl
    │                              ▼                      │
    └──────── C6 pins/timing ─► WP4 Display & Demo        │
                                   │                      │
                         WP5 Integration & Deliverables ◄─┘
```

`docs/archive/proposal.pdf` names a lead for each part. Under TEAM_PROCESS.md those names are a history
note, not ownership.

---

## 1. Interface contracts (must be agreed before any parallel coding)

A contract goes into `docs/agent/CONTRACTS.md` as soon as one person decides it explicitly
and it doesn't conflict with an existing top-level doc (AGENTS.md §5A). If someone later
changes it, that goes through §5B: overrule it, or discuss it with the team. Code built on a
contract that later changes has to be reworked.

| ID | Contract | Producer → Consumer | Must pin down |
|----|----------|---------------------|---------------|
| C1 | Capture buffer | WP1 → WP3 | `int16_t buf[150][3]`, axis order, sign convention (X tip, Y left, Z up). Units: raw left-justified LIS3DH or `>>4` to 12-bit (±4 g HR = 2 mg/LSB). Window alignment relative to the trigger (pre-trigger samples?). What happens when the FIFO overflows. |
| C2 | UART raw stream | WP1 → WP2 | Baud rate, binary vs CSV, frame header/sync byte, checksum, how a capture window is delimited, label field. |
| C3 | Feature definition | WP2 ⇄ WP3 | Exact integer algorithm: 150 / 10 = 15 samples per segment. Mean = sum / 15: **rounding mode** (C truncates toward 0, Python `//` floors). Energy = Σx²: int32 accumulator, then the shift/scale back to int16 and **saturation**. Normalization (subtract mean, scale) in fixed point. Feature ordering (axis-major or segment-major). **One reference implementation in Python, written with integer ops only.** |
| C4 | `gesture_model.h` | WP2 → WP3 | Array names and shapes, int8 weight layout (row/col-major), bias type (int32), per-layer requant (multiplier + shift), input normalization constants, class count, a **model version/hash** constant, and the ODR and range it was trained at. |
| C5 | Classifier output | WP3 → WP4 | Class ID table (0 none … 8 thrust), the value of `GESTURE_UNKNOWN`, the ID range for learned classes, how confidence is scaled (0–255 from the logit margin), and double-tap as a separate event. |
| C6 | Pins, peripherals, timing | all | I2C1 or I2C2, LIS3DH SA0 (0x18/0x19), UART pins, WS2812 pin, bulb control method (**unknown: IR? relay? Wi-Fi?**), interrupt priorities. The WS2812 bit-bang needs IRQs masked for about 2 ms per frame, and that interacts with I2C/UART. |
| C7 | Resource budget | all | RAM split of 8 KB (table in §4), flash split of 64 KB, worst-case CPU time per stage. |

---

## 2. Work packages

### WP1: Sensor driver
Output: `lis3dh.c/h`, the capture state machine, and the UART raw stream.
- I2C init and WHO_AM_I (0x33) check. 100 Hz, ±4 g, HR mode, FIFO stream mode.
- The FIFO is 32 deep. At 100 Hz it fills in 320 ms, so it must be drained in time during a
  1.5 s window.
- INT1 motion trigger opens a 150-sample window, then `gesture_poll()` returns true. Click
  detection on INT2 handles double-tap.
- `gesture_stream_raw()` follows C2.
- **Done when:** a logic-analyzer or UART dump shows 150 clean samples per trigger, with no
  dropped FIFO entries, at the specified axis signs.

### WP2: Data & training
Output: recorder tool, dataset, `features_ref.py` (C3 golden), training script, quantizer,
`export_model.py` → `gesture_model.h`, and `test_vectors/`.
- The recorder speaks C2 and stores labeled windows.
- `features_ref.py` uses **integer ops only** and mirrors C3 bit for bit. Training may use
  float features, but evaluation must use the quantized integer path.
- `infer_ref.py` is the integer reference inference: the same math as the C, bit for bit.
- Export test vectors as raw windows → expected features → expected logits → expected class.
- **Done when:** the quantized integer model hits target accuracy on a held-out set and the
  test vectors are generated.

### WP3: On-device classifier
Output: `gesture.c/h` (public API), `features.c`, `mlp.c`, `knn.c`, and a host test harness.
Detailed breakdown in §3.

### WP4: Display & demo
Output: `ws2812.c/h`, `icons.c`, `bulb.c/h`, `main.c` demo.
- WS2812 timing at Fcy = 16 MHz: about 0.4/0.85 µs per bit, which needs a cycle-counted asm loop.
- Icons for 9 classes plus unknown plus learn-mode feedback.
- **Done when:** each class ID maps to an icon, the bulb responds, and an animation doesn't
  block the sensor capture (C6).

### WP5: Integration & deliverables (shared)
- One MPLAB X project and the repo layout (proposed: `firmware/`, `tools/`, `docs/`).
- A library README with all ≥5 public functions documented.
- The combined `AI_USAGE.md`, the citations list, and the demo script.
- Measured cycles, RAM, and flash numbers in the report.

---

## 3. WP3 breakdown, sized for subagents (the other WPs get the same treatment when someone picks them up)

**Who does what.** "Main" means the main agent (Opus) working with the human, because the
task involves design or a contract. "Sonnet" means a Sonnet 5.5 subagent at medium effort,
following the brief template in §5.

**Every Sonnet implementation row also gets two more tickets:**
- a *test* ticket, written by a different subagent from the spec only;
- a *review* ticket, handled by a third subagent.

These are tracked in `BOARD.md` (AGENTS.md §6).

| # | Task | Who | Depends on | Acceptance |
|---|------|-----|------------|------------|
| 3.1 | Draft the C3 (features) and C5 (output) contracts | Main + human | – | A human decides explicitly, and the contract goes into `docs/agent/CONTRACTS.md` |
| 3.2 | Draft the C4 header-format contract. It must match what the WP2 exporter produces | Main + human | 3.1 | Same as 3.1 |
| 3.3 | `features.c`: integer feature extraction per C3 | Sonnet | C1, C3 locked | Host test: matches `features_ref.py` on all test vectors, bit for bit |
| 3.4 | `mlp.c`: int8×int8→int32 dense, requant, ReLU, argmax per C4 | Sonnet | C4 locked | Host test: logits match `infer_ref.py`, bit for bit |
| 3.5 | Reject logic: top1−top2 margin → uint8 confidence → `GESTURE_UNKNOWN` | Sonnet | 3.4, C5 | Unit tests at the boundary margins |
| 3.6 | `knn.c`: template store, L1 distance on template vectors (int8 normalized per the C5 proposal, pending Hadi's decision), learn and classify | Sonnet | 3.3 | Unit tests. Templates fit the RAM budget in §4 |
| 3.7 | `gesture.c`: public API wrapper, the 7 functions with doc comments | Sonnet | 3.3–3.6, WP1 API | Compiles with XC16 at `-Wall -Wconversion` with no warnings |
| 3.8 | Host harness: build C with host gcc, run vectors, diff against Python | Sonnet | 3.3, 3.4 | One command, `make test`, prints PASS/FAIL per vector |
| 3.9 | On-target verification: run the same vectors on the PIC24 (or the MPLAB simulator), stream results over UART, diff | Hadi + Main | 3.8, WP1 UART | 100% match on target, not just on host |
| 3.10 | Measure cycles (Timer1 or a pin toggle), RAM (map file), flash | Hadi | 3.9 | Numbers recorded in the report |

**Why 3.9 matters:** on host gcc `int` is 32 bits, but on XC16 it is 16 bits. Code can pass
3.8 and still overflow on the PIC24. 3.9 is the real gate.

---

## 4. RAM budget (first estimate, part of C7)

| Item | Bytes |
|------|------:|
| Capture buffer 150×3×int16 | 900 |
| Features 60×int16 | 120 |
| Hidden layer 16×int32 + logits 9×int32 | 100 |
| k-NN templates: 4 learned classes × 5 templates × 60 × int8 | 1200 |
| WS2812 framebuffer 64×3 | 192 |
| UART/I2C buffers | ~128 |
| Stack + globals headroom | ~2000 |
| **Total** | **~4.6 KB of 8 KB** |

Templates stored as int16 would double that line to 2400 B. Decide in C7. Templates live in
RAM, so they are **lost on power-off** unless written to flash (RTSP). That is a scope
question for the team.

---

## 5. Subagent brief template (copy this exactly)

```
Working for: hadi
You are: <name, e.g. impl-features>   Role: <implementer | tester | reviewer>
Ticket: <ID from docs/agent/hadi/BOARD.md>
Model: Sonnet 5.5, medium effort

TASK: <one sentence>

READ (do not modify): AGENTS.md, docs/agent/CONTRACTS.md, <input files>
WRITE ONLY: <exact file list, e.g. firmware/src/features.c, firmware/src/features.h>
            (tester: only tests/...; reviewer: writes nothing, reports findings)
NEVER WRITE: docs/human/**, docs/agent/*.md, docs/*/<anyone-but-hadi>/**, any file not listed above

SPEC:
<the relevant contract section pasted verbatim, not paraphrased>

CONSTRAINTS:
- C99, fixed-width types only (XC16 int is 16-bit), no float/double, no malloc, no blocking delays.
- Wrap every line you write in
  // [AI-GENERATED: Claude Code]  ...  // [END AI-GENERATED]
- Doc comment on every public function: purpose, args, return.
- Append one row per function to AI_USAGE.md (repo root): file | function | purpose | date | author: agent.

ACCEPTANCE: run `<command>`; it must print <expected>.

STOP AND REPORT (do not improvise) IF: the spec is ambiguous; a test cannot pass without
changing a file outside WRITE ONLY; you would need floating point; a contract value is missing.

REPORT FORMAT: files changed; functions added; test command + output; open questions.
```

---

## 6. Gates (order of operations)

1. **G0 Framework:** the shared git remote is added (FRAMEWORK_REVIEW F2), and the teammates have read AGENTS.md.
2. **G1 Contracts:** C1–C7 are written into `docs/agent/CONTRACTS.md`. *Parallel coding starts after this.*
3. **G2 Host bit-exact:** C and Python agree on every vector (3.8).
4. **G3 Target bit-exact:** the PIC24 agrees on every vector (3.9), and the sensor captures real data (WP1).
5. **G4 Integrated demo:** live gesture → icon → bulb, with numbers measured.

Deadlines: **unknown**. The milestone dates and the demo date need to come from the course schedule.
