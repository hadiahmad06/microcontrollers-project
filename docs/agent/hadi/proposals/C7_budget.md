# C7: Resource budget (RAM, flash, CPU time) and k-NN template persistence

> Proposal by `research-display` (ticket S1-5) for `hadi`, 2026-11-14. **Not a decision.** Companion: `C6b_display_bulb.md`.
> Sources: `DS39881E` = Microchip PIC24FJ64GA004 Family datasheet (covers the 28-pin PIC24FJ64GA002),
> `ww1.microchip.com/downloads/en/DeviceDoc/39881e.pdf`, printed page numbers. `XC16-UG` = MPLAB XC16 C Compiler User's Guide
> (local, `/Applications/microchip/xc16/v2.10/docs/MPLAB_XC16_C_Compiler_Users_Guide.pdf`). `GLD` = XC16 linker script
> `/Applications/microchip/xc16/v2.10/support/PIC24F/gld/p24FJ64GA002.gld`.
> **Assumptions that depend on pending contracts** are marked **[C1]**, **[C3]**, **[C4]**, **[C2]**.
> All code-size and cycle numbers are **estimates** (UNVERIFIED until measured with the map file and the simulator, ticket 3.10).

## 1. Decisions needed

**D1. Stack size.**
- Options: 256 B (tight, risky with nested ISRs), 512 B, 1024 B.
- **RECOMMENDATION (needs Hadi's decision): 512 B reserved** with `--stack=512` and the default 16 B stack guard, plus a test that paints the stack and reports the high-water mark (§3.1). Raise to 768 B only if the paint test shows over 300 B used. No `printf`/`sprintf` in the product build.

**D2. k-NN template element type: int8 or int16.**
- int8: 60 B per template. **Needs the template vector to be the C4-normalized int8 MLP input** (assumption [C4]). Cheapest, and distance sums fit in `uint16` (60 x 255 = 15300).
- int16: 120 B per template; keeps the raw C3 features (60 x int16) at full resolution, but needs 32-bit or saturating distance sums.
- **RECOMMENDATION (needs Hadi's decision): int8, matching the MLP input vector.** Re-evaluate with a quick offline accuracy check (is k-NN on int8 as accurate as on int16 for the recorded gestures? **UNVERIFIED**, a WP2 spike). Fall back to int16 if accuracy drops noticeably.

**D3. Template geometry (learned classes x templates per class).**
- Options (bytes of RAM): 2x3 = 360 (int8) / 720 (int16); 4x3 = 720 / 1440; **4x5 = 1200 / 2400 (PLAN.md)**; 8x5 = 2400 / 4800 (does not fit with int16, §2.3).
- **RECOMMENDATION (needs Hadi's decision): 4 learned classes x 5 templates, int8 (1200 B)**, as compile-time constants `KNN_CLASSES` and `KNN_TPL`, with a ceiling of 2400 B total for templates.

**D4. k-NN persistence.**
- (a) RAM only: templates are lost at reset or power-off. (b) Save to program flash with RTSP, using two reserved erase blocks. (c) Dump to the PC over UART and restore from the PC at boot.
- **RECOMMENDATION (needs Hadi's decision): (a) for the MVP, but write `knn.c` with `knn_export()`/`knn_import()` that serialize to one flat blob (version + count + data + CRC16), so (b) is a small later add-on. Do (b) only as a stretch goal**, using the two reserved blocks in §4. It adds a public function (`gesture_save`), which is an API change.

**D5. Headroom policy.**
- **RECOMMENDATION (needs Hadi's decision): keep at least 25% of RAM (2 KB) and 30% of flash free** at every milestone. A change that takes more needs re-approval. A single capture buffer (no double buffering) unless C1 requires otherwise.

**D6. Build rules that protect the budget.**
- **RECOMMENDATION (needs Hadi's decision):** `-mconst-in-code` (the XC16 default, XC16-UG "-mconst-in-code ... This is the default") for all weights, icons and tables, so they stay out of RAM. `--heap=0` (no malloc). No `float`, `double` or `printf` in the product build. Check the `.map` file at every milestone (this is part of ticket 3.10). Large `const` data in one PSV window must stay inside one 32 KB program page (§5).

## 2. RAM budget (8 KB)

### 2.1 Facts

| Fact | Value | Source |
|------|-------|--------|
| Data RAM | 8 KB implemented at 0x0800 to 0x27FF (SFRs at 0x0000 to 0x07FF are separate) | DS39881E Fig 4-3 and §4.2 (p.31) |
| Linker data region | `data (a!xr) : ORIGIN = 0x800, LENGTH = 0x2000` | GLD line 60 |
| Stack grows up; limit register | W15 stack pointer with SPLIM; a stack error trap fires on overflow | DS39881E §4.2.5 (p.43), Table 7-1 (Stack Error trap) |
| Stack guard and minimum size | default stack guard 16 B (configurable); minimum stack with `--stack` linker option; stack guidance report in the linker output | XC16-UG §8.8.3 "Using the Guidance", §12.2.3.1 "Software Stack" |
| Heap | none unless `--heap=N` is given | XC16-UG linker options table ("Heap size ... --heap") |
| `const` placement | const objects go in flash (PSV window) by default; `-mconst-in-data` would put them in RAM | XC16-UG "-mconst-in-code ... (This is the default)" |
| C runtime RAM | **UNVERIFIED**. Expected to be tens of bytes of library statics if no stdio/malloc is linked. Budgeted at 64 B. Check the map file. | n/a |

### 2.2 Proposed budget (lean, recommended)

| Item | Bytes | Depends on | Notes |
|------|------:|------------|-------|
| Capture buffer `int16_t[150][3]` | 900 | [C1] | If C1 adds pre-trigger samples, add 6 B per sample (20 samples = 120 B). If C1 chooses a double buffer, +900. |
| I2C/FIFO burst staging | 0 | [C1] | LIS3DH output order (XL, XH, YL, YH, ZL, ZH, little-endian) matches `int16_t[3]` on a little-endian PIC24, so bursts can be read straight into the capture buffer. If C1 needs a separate staging area: 192 B (32 samples x 6). |
| Features `int16_t[60]` | 120 | [C3] | C3 may change the count or width. |
| Feature accumulators/scratch (3 axes x int32 sum + int32 energy, indices) | 32 | [C3] | |
| MLP input `int8_t[60]` | 60 | [C4] | Also the k-NN vector (D2). |
| MLP activations: hidden `int32 acc[16]` 64 + `int8 hidden[16]` 16 + `int32 logits[9]` 36 | 116 | [C4] | PLAN.md said about 100. |
| k-NN templates: 4 classes x 5 x 60 B (int8) | 1200 | D2, D3 | |
| k-NN metadata: counts, labels, version/CRC | 16 | | |
| WS2812 framebuffer 64 x 3 | 192 | C6b | A palette-index framebuffer (64 B + palette) could save about 100 B. Not recommended yet: complicates brightness scaling. |
| UART buffers: TX ring 128 + RX ring 32 | 160 | [C2] | If C2 streams CSV live in 16-sample bursts (about 20 B per sample = 320 B), the ring must grow, or stream from the capture buffer after the window ends (no ring needed). |
| I2C driver state | 32 | | |
| Application globals (state machine, config, thresholds, timers, learn state) | 96 | | |
| Bulb/IR state (NEC frame, timing queue) | 32 | C6b | |
| C runtime and library statics | 64 | | UNVERIFIED (§2.1) |
| **Stack** | 512 | D1 | |
| **Total used** | **3532** | | **43% of 8192** |
| **Free** | **4660** | | 57% |


### 2.3 Scenarios and what fits

Base without template data = 3532 - 1200 = **2332 B** (includes the 16 B metadata). With the 25% free policy (D5), 2048 B must stay free, so templates plus any extras may use at most 8192 - 2332 - 2048 = **3812 B**.

| Scenario | Template bytes | Extra | Total used | Free | Meets D5? |
|----------|---------------:|-------|-----------:|-----:|-----------|
| Lean: 4x5 int8 (recommended) | 1200 | none | 3532 | 4660 | yes |
| 4x5 int16 | 2400 | none | 4732 | 3460 | yes |
| 8x5 int8 | 2400 | none | 4732 | 3460 | yes |
| 8x5 int8 + double capture buffer | 2400 | +900 | 5632 | 2560 | yes (barely) |
| 8x5 int16 | 4800 | none | 7132 | 1060 | **no** |
| 4x5 int16 + double buffer + 192 B staging | 2400 | +1092 | 5824 | 2368 | yes |
| 8x5 int16 + double buffer | 4800 | +900 | 8032 | 160 | **no** (nearly out of RAM) |

Conclusion: RAM is not the binding constraint unless the team picks both int16 and 8 classes. int8 with 4 to 8 classes is comfortable.

### 2.4 Mitigations if RAM gets tight (in order)
1. Stream raw samples straight from the FIFO to UART instead of buffering (recorder mode only).
2. Reuse the capture buffer as scratch for features after the window closes.
3. Drop the UART ring and send directly from the capture buffer.
4. Use a palette-index framebuffer (64 B).
5. Reduce `KNN_TPL`.

## 3. Details: RAM items

### 3.1 Stack
- No dynamic allocation, no recursion, big arrays are `static` (not locals).
- Rough worst case (estimate only): main (about 30 B) + `gesture_classify` + `mlp_forward` + dense layer helper (about 30 to 40 B each, locals only) = about 150 B; plus up to three nested ISRs. Each ISR frame is the PC (4 bytes with the SR/IPL word, DS39881E §4.2.5) plus saved W registers (about 16 to 32 B). That is about 100 B. Total about 250 to 300 B, so 512 B has about 2x margin.
- Verification: link with `--stack=512`, read the stack guidance in the linker output, and run a paint-and-check test at the end of every integration run (fill the unused region with 0xA5 at boot, report the high-water mark over UART).
- Danger zone: any `printf`-family call. It may pull in 100+ B of stack and kilobytes of flash (**UNVERIFIED**).

### 3.2 Capture buffer
- 150 samples x 3 axes x 2 bytes = 900 B. At 100 Hz that is 1.5 s. The classification (about 5 ms, §6) is far shorter than any re-arm delay, so one buffer suffices **unless C1 wants to capture the next window while classifying**, which the 320 ms FIFO slack also allows (the FIFO is the second buffer).

### 3.3 k-NN templates
- Per template: int8 = 60 B, int16 = 120 B (60 features). The feature count follows C3 [C3].
- Distance: L1 on int8 gives at most 60 x 255 = 15300, so a `uint16_t` accumulator is enough and cheap on a 16-bit CPU. L1 on int16 needs `uint32_t` (or saturation).
- If templates are stored as the C4-normalized MLP input, there is no extra normalization code for learning mode. If C4 does not define an int8 input quantization, this needs revisiting [C4].

### 3.4 UART and I2C
- Raw stream rate: 100 Hz x 6 B = 600 B/s binary, or about 2 KB/s CSV. 115200 baud carries about 11.5 KB/s, so the link is 5% to 17% loaded. [C2]
- UART hardware FIFOs are 4 deep (RX and TX; DS39881E p.1), so the software rings are only for burst smoothing.

## 4. k-NN persistence: flash facts and design

### 4.1 Facts

| Fact | Value | Source |
|------|-------|--------|
| Program memory size (this part) | 22 K instructions (22016) at 24 bits each = **66,048 B** nominal ("64 KB") | DS39881E Table 4-1 (p.30) |
| Linker user program region | `ORIGIN = 0x200, LENGTH = 0xA9FC` (ends at 0xABFC); config words at 0xABFC and 0xABFE | GLD lines 65 to 67, 70 to 71 |
| Usable code space | (0xABFC - 0x200) / 2 = 21,758 instructions = **65,274 B** at 3 B each | computed from GLD |
| Config words | **Yes: the top two words of program memory (0xABFC and 0xABFE) hold the Flash Configuration Words**; they are reloaded on every reset | DS39881E §4.1.3 and Table 4-1 (p.30); §24.1, Table 24-1 (p.209) |
| Danger | "Performing a page erase operation on the last page of program memory clears these values and enables code protection. ... avoid performing page erase operations on the last page" | DS39881E §5.5 (p.48, "Programming Operations") |
| RTSP erase block | 8 rows = **512 instructions = 1536 B**, aligned on 1536 B boundaries. In address terms that is 0x400 per block | DS39881E §5 intro and §5.2 (p.47 to 48) |
| RTSP write row | **64 instructions = 192 B**, programmed one row at a time; word writes also possible; 64 `TBLWT` for a full row; unused latches must be 0xFFFFFF | DS39881E §5.2 (p.48) |
| Last erase block | 0xA800 to 0xABFF (0xAC00 is 43 x 0x400) contains the config words | computed from the above |
| Endurance | **10,000 erase/write cycles minimum** (-40 to +125 C), retention 20 years | DS39881E p.1; Table 27-9 D130, D134 (p.242) |
| Write time | self-timed write cycle about **3 ms typical** (D133A); erase time is **UNVERIFIED** (not listed separately in Table 27-9) | DS39881E Table 27-9 (p.242) |
| Supply for write | VDDCORE 2.25 to 2.75 V self-timed write; flash is erasable/writable when VDD is over 2.25 V | Table 27-9 D132B; §5 intro (p.47) |
| CPU during write | the processor **stalls** until the operation completes (about 3 ms per row) | DS39881E §5.5 (p.48) |
| Key sequence | write 0x55 then 0xAA to NVMKEY, then set WR; the datasheet example wraps it in `DISI #5` | DS39881E §5.5.1 (p.49) and example |
| Program space as data | a 24-bit word has a "phantom" upper byte that PSV reads cannot see. PSV only reads the least significant 16 bits; table reads (`TBLRDL`/`TBLRDH`, 2 cycles each) reach all 24 | DS39881E Fig 4-2 (p.30), §4.3 (p.43) |
| FRM (not fetched here) | PIC24F Family Reference Manual "Program Memory" DS39715 and "Flash Programming" | cited by DS39881E §5 intro. **Not read for this proposal.** |

### 4.2 Options

| Option | Cost | Risk |
|--------|------|------|
| (a) RAM only | 0 flash, 0 code | learned gestures vanish at reset and on every re-flash. Fine for a single live demo |
| (b) RTSP save/restore | 2 erase blocks (3 KB reserved), about 0.7 KB code, `gesture_save()`/`gesture_load()` | an erase of the wrong block can wipe code or the config words (device unusable/code-protected). A write during a UART burst or capture window stalls the CPU about 3 ms per row. Brown-out mid-write corrupts a block (mitigate with CRC and A/B blocks). Re-flashing from MPLAB X overwrites the reserved region unless "preserve program memory" is set |
| (c) Dump over UART, restore from PC | about 0.3 KB code, PC tool work | needs the PC at boot, so it is not standalone |

### 4.3 If (b) is chosen: design
- Reserve two **erase blocks well away from the config words**: A = 0xA000 to 0xA3FF, B = 0xA400 to 0xA7FF. Block C (0xA800 to 0xABFF) is never touched. A hard check in the erase routine: refuse any address at or above 0xA800.
- Reserve them from the linker by declaring a `const` array with `__attribute__((space(prog), address(0xA000)))`, initialized to all 0xFF (`fillupper` attribute) so no code lands there (syntax **UNVERIFIED**; see XC16-UG §12.3 "Variables in Program Space" and the `address` attribute).
- Two blocks give 2 x 512 x 2 B = 2048 B usable (reading through PSV, which sees 16 bits per word). One block gives only 1024 B, which is less than 1200 B + header. Writing 24 bits per word needs table reads and is more code. So **two blocks, used as A/B alternates**: write the new copy (sequence number + CRC16) to the other block, then erase the old one, and at boot take the valid copy with the highest sequence.
- Per save: about 1216 B / 128 B per row (16-bit data) = 10 rows x about 3 ms + 1 erase = about 35 ms of CPU stall. Do it only on an explicit save command while idle, never during capture, never during a WS2812 show or IR frame, and with UART RX quiet (350 us overrun window at 115200, see C6b §4.3).
- Wear: 10,000 cycles per block; a handful of saves per session, so under 1% of endurance in the whole project.
- Not tested in the MPLAB simulator: **UNVERIFIED** whether the simulator models NVMCON writes. Hadi-with-board only. This adds a hardware test session.

### 4.4 Recommendation reasoning
For a class demo the learned gestures are shown live in one session, so RAM-only is sufficient and has no way to brick the chip. Persistence is the one feature that can damage the target, and it cannot be verified in the simulator. The `knn_export`/`knn_import` hooks keep the door open at near-zero cost.

## 5. Flash budget (64 KB)

### 5.1 Facts and rules

| Fact | Value | Source |
|------|-------|--------|
| Total usable program space | 65,274 B (21,758 instructions) | §4.1 |
| `const` data costs 1.5x | A 24-bit program word holds only 16 bits visible to PSV, so 1 byte of `const` data costs about 1.5 B of flash | DS39881E §4.3, Fig 4-2 (phantom byte); XC16-UG (PSV and `auto_psv`) |
| PSV window | 15-bit window (32 KB). `space(auto_psv)` data "will use a single memory page by default", so all `const` tables must fit within one 32 KB page | DS39881E §4.2 (p.31); XC16-UG ("The space(auto_psv) or space(psv) attribute will use a single memory page by default") |
| Hardware multiply/divide | `MUL.SS` 1 cycle; 17x17 single-cycle multiplier; `DIV.SW` 18 cycles; taken `BRA` 2 cycles; `TBLRDL` 2 cycles | DS39881E p.1; Table 26-2 (p.226) |
| Reset/IVT | vectors occupy 0x000 to 0x1FF | DS39881E §4.1.2 (p.30) |

### 5.2 Estimate (all numbers are guesses to be replaced by map-file data)

| Item | Flash (B) | Notes |
|------|----------:|-------|
| Startup, clock/PPS init, vectors, main loop | 1,200 | |
| LIS3DH driver + I2C + FIFO drain | 2,000 | |
| Capture state machine, trigger, double-tap handling | 1,200 | |
| UART driver + raw stream (C2) | 1,500 | |
| `features.c` (includes 32-bit divide helpers) | 1,800 | |
| `mlp.c` | 1,200 | |
| `knn.c` + learn + export/import | 1,800 | |
| `gesture.c` API + reject logic | 1,000 | |
| `ws2812.c` (asm loop) + framebuffer + brightness limit | 1,200 | |
| Icons + animations | 4,000 | 9 to 12 icons; an 8x8 icon as 64 palette-index bytes costs about 96 B flash; 8 frames x 12 icons = 9 KB if full, so use 1-bit bitmaps + color (12 B per frame) for animations |
| `bulb.c` (NEC / PWM) | 1,200 | |
| libc/runtime helpers (`memcpy`, `__mulsi3`, `__divsi3`, ...) | 2,000 | |
| Debug/test hooks, version string, paint test | 1,000 | |
| **Code total** | **about 20,100** | |
| MLP weights: 960 + 144 = 1,104 B int8 x 1.5 | 1,656 | [C4] |
| Biases 25 x int32 = 100 B x 1.5; requant constants | about 300 | [C4] |
| Normalization constants, model hash/version | about 100 | [C4] |
| RTSP template blocks (only if D4 option b) | 3,072 | reserved, never code |
| **Total (with RTSP blocks)** | **about 25,300** | **39% of 65,274 B** |
| **Free** | **about 40,000** | 61% |

Even if every estimate is off by a factor of 2, total use stays under 51 KB (78%). A `printf` with float support would be the one thing that could blow the budget (**UNVERIFIED**; avoid, D6). Flash is not a binding constraint.

## 6. CPU time per gesture

### 6.1 Assumptions
Fcy = 16 MHz: 62.5 ns per cycle, 16,000 cycles per ms. XC16 `-Os`, no DSP/MAC engine (PIC24F has none). The C compiler generates about 10 to 20 cycles per C-level inner-loop step with 32-bit accumulation. The estimates below use those ranges.

### 6.2 Timeline

| Stage | Estimate | How derived |
|-------|----------|-------------|
| Capture window | 1.5 s (150 samples at 100 Hz) | fixed by design |
| FIFO drain over I2C, 400 kHz | about 21 ms total over the window = **1.4% of the window** | 9 clocks per byte at 2.5 us per clock = 22.5 us per byte; 6 B per sample = 135 us per sample; 150 samples = 20.3 ms, plus about 10 bursts of about 90 us overhead each. At 100 kHz, about 4x: about 85 ms, 5.7% |
| Drain per burst | 16 samples = about 2.25 ms | 96 B x 22.5 us + 90 us. At most 4.5 ms for a 32-sample worst case |
| Feature extraction | about 0.7 to 2 ms (11k to 32k cycles) | 450 sample-axis steps x 12 to 16 cycles (load, 32-bit add, `MUL.SS`, 32-bit accumulate) = 5.4k to 7.2k; 30 segment finalizations (divide by 15: `DIV.SW` 18 cycles, saturate) about 2.4k; normalize and quantize 60 features about 1k to 2k. Budget 3 ms |
| MLP, 1104 MACs | about 0.7 to 1.5 ms (11k to 24k cycles) | 10 to 20 cycles per int8 MAC with 32-bit accumulation; plus requant (25 outputs, about 40 cycles each, about 1k). PSV/table reads for weights add cycles, **UNVERIFIED** |
| Reject logic (top-2 margin) | under 0.05 ms | trivial |
| k-NN, 20 templates x 60 | about 0.5 ms (8.4k cycles) | about 7 cycles per element (two loads, subtract, abs, 16-bit add); 8 classes x 5 = 40 templates is about 1.1 ms |
| Icon render to framebuffer | about 0.05 ms | 64 pixels x about 12 cycles |
| WS2812 show | **about 2.0 ms (old) / 2.2 ms (V5)** | 1536 bits x 1.25 us + reset (C6b) |
| IR bulb frame | about 68 ms, mostly waiting | timer-ISR driven, under 1% CPU (about 70 events x about 100 cycles) |
| **Compute after capture ends** | **about 4 to 7 ms** (without the IR wait) | sum of features, MLP, k-NN, render, show |
| End-to-end gesture to bulb | about 1.5 s + 7 ms + 68 ms = **about 1.6 s** | dominated by the capture window |

### 6.3 Does it fit?
- **During capture:** the CPU is about 97% idle (drain 1.4% blocking; much less if ISR-driven).
- **After capture:** 4 to 7 ms of compute against a 320 ms FIFO slack. Even a 10x underestimate (70 ms) fits. The FIFO keeps filling while classification runs, so a new trigger right after a gesture is not lost.
- **Interaction rule:** the WS2812 chunking and drain-first rule in C6b §4.4 apply. Animations at 30 fps would cost 2.2 ms of 33 ms = 7% CPU.
- **Learn gesture:** one feature extraction plus a store, about 1 to 2 ms. Optional flash save about 35 ms (D4 b) in idle.
- **Verdict:** time is not a constraint. The latency users feel is the 1.5 s window itself, which may be worth shortening later (a C1 matter, not a budget one).

## 7. Open questions
1. [C1] Does the capture buffer include pre-trigger samples? Is there a staging buffer or a double buffer? Does the FIFO drain read directly into `buf[n][3]`?
2. [C3] Final feature count and width; is there per-axis scratch that must persist (accumulators)?
3. [C4] Is the MLP input int8 after a defined normalization? Is the k-NN allowed to reuse it? How are the biases stored (int32)?
4. [C2] Live CSV streaming in bursts (needs a ring of 300+ B) or post-window dump (no ring)?
5. Is the persistence of learned gestures wanted at all (D4)? A scope decision for the team.
6. Which debugger/programmer is used, and can it preserve the reserved flash blocks across downloads?
7. What is the real C runtime RAM overhead and stack high-water mark? Needs the first map file (ticket 3.10).
8. How long does a block erase take? (Table 27-9 gives only the 3 ms write; check the PIC24F FRM DS39715 or measure.)
