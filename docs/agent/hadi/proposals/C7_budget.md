# C7: Resource budget (RAM, flash, CPU time) and k-NN template persistence

> Proposal by `research-display` (ticket S1-5) for `hadi`, 2026-11-14, **revision 2** (fix round after `reviews/S1-5R.md`). **Not a decision.** Companion: `C6b_display_bulb.md`.
> Reconciled with the final C1, C3, C4, C5 and C6a proposals. Sources: `DS39881E` = Microchip PIC24FJ64GA004 Family datasheet (covers the 28-pin PIC24FJ64GA002),
> `ww1.microchip.com/downloads/en/DeviceDoc/39881e.pdf`, printed page numbers. `XC16-UG` = MPLAB XC16 C Compiler User's Guide (local,
> `/Applications/microchip/xc16/v2.10/docs/MPLAB_XC16_C_Compiler_Users_Guide.pdf`). `GLD` = XC16 linker script
> `/Applications/microchip/xc16/v2.10/support/PIC24F/gld/p24FJ64GA002.gld`. `S1-5R` = the review of the first revision.
> Sibling numbers used here: **[C1]** capture path 1188 B, **[C3]** `features.c` measured 240 B (-O1) / 189 B (-O2), about 350 B in isqrt mode, **[C4]** MLP constants about 1464 data B = about 2196 B of flash, working set 112 B, **[C5]** `GESTURE_MAX_LEARNED = 4` (IDs 9..12), 5 templates each, int8 `x8` vectors.
> Cycle counts and code sizes other than `features.c` are **estimates** (UNVERIFIED until a map file and the simulator exist, ticket 3.10).

## 1. Decisions needed

**D1. Stack size.**
- Options: 256 B (tight), 512 B, 1024 B.
- **RECOMMENDATION (needs Hadi's decision): 512 B reserved** with `--stack=512` and the default 16 B stack guard, plus a paint test that reports the high-water mark (§3.1). Raise to 768 B only if the test shows over 300 B used. No `printf`/`sprintf` in the product build.

**D2. k-NN template element type.** C4 (D1) and C5 (D4) now define an int8 `x8` input vector and an L1 distance over it (max 60 x 254 = 15240, fits `uint16_t`). int16 would double the template size and need a 32-bit sum.
- **RECOMMENDATION (needs Hadi's decision): int8 `x8`, as C4/C5 already specify.** int16 appears below only as a hypothetical.

**D3. Template geometry.** C5 fixes the default at 4 learned classes (IDs 9..12) x 5 templates = 1200 B, raisable to 7 classes (2100 B) at compile time.
- **RECOMMENDATION (needs Hadi's decision): keep 4 x 5 int8 = 1200 B** with `GESTURE_MAX_LEARNED` and `GESTURE_TEMPLATES_PER_CLASS` as compile-time constants. Scenarios above 4 classes are marked hypothetical (§2.3).

**D4. Persistence of learned templates.**
- (a) RAM only (lost at reset or re-flash). (b) Save to program flash with RTSP. (c) Dump to the PC over UART.
- If (b), the design choice (§4.3): **P1** 3 B per word via table reads (2 blocks, 3072 B reserved, more code); **P2** 2 B per word, **four** blocks (two A/B copies of two blocks each, 6144 B reserved); **P3** a smaller blob that fits one 1024 B block (e.g. 4 classes x 4 templates = 976 B), 2 blocks reserved, but it changes C5's 5 templates per class; **P4** no A/B (one copy, no power-loss safety).
- **RECOMMENDATION (needs Hadi's decision): (a) for the MVP, with `knn_export()`/`knn_import()` (flat blob: version + count + data + CRC16). If persistence is wanted later, use P2.** Reason: P2 needs no contract change, plain 16-bit word writes and PSV reads like the other tables, and flash is two thirds free. It adds a public function (`gesture_save`).

**D5. Headroom policy.**
- **RECOMMENDATION (needs Hadi's decision): keep at least 25% of RAM (2 KB) and 30% of flash free** at every milestone. A single capture buffer (C1 decision 7a) unless C1 changes.

**D6. Build rules that protect the budget.**
- **RECOMMENDATION (needs Hadi's decision):** `-mconst-in-code` (the XC16 default) so weights, icons and tables stay out of RAM; `--heap=0`; no `float`, `double` or `printf`; check the `.map` file at every milestone. **Always link with the device script** (`-Wl,-T,.../p24FJ64GA002.gld`, or build in MPLAB X): S1-5R found that a command-line link without `-T` uses a generic map (program origin 0x100 length 0x3FF00, data 0xF800) and so hides the 8 KB / 64 KB limits. Check the "Loading file" line of the build log. All `const` data must sit in one 32 KB PSV page (§5.1).

## 2. RAM budget (8 KB)

### 2.1 Facts

| Fact | Value | Source |
|------|-------|--------|
| Data RAM | 8 KB implemented at 0x0800 to 0x27FF (SFRs 0x0000 to 0x07FF are separate) | DS39881E Fig 4-3, §4.2 (p.31) |
| Linker data region | `data (a!xr) : ORIGIN = 0x800, LENGTH = 0x2000` | GLD line 60 |
| Stack | grows up; SPLIM; stack error trap on overflow | DS39881E §4.2.5 (p.43) |
| Stack guard and minimum | default guard 16 B; minimum with `--stack`; linker stack guidance report | XC16-UG §8.8.3, §12.2.3.1 |
| Heap | none unless `--heap=N` | XC16-UG linker options |
| `const` placement | flash via PSV by default; `-mconst-in-data` puts it in RAM | XC16-UG "-mconst-in-code ... default"; C4 verified 0 B of data RAM for weights |
| Capture path | 900 B buffer + 96 B ring + 192 B staging = 1188 B (1092 B with staging capped at 16 samples) | C1 §3.4 |
| MLP working set | x8[60] + h[16] + logits[9] x 4 = 112 B (**includes x8**) | C4 §3 |
| k-NN | templates are the C4 `x8` vector, 60 B each; optional 1 to 2 class-0 "anti-templates" +120 B | C5 §3, D4 |
| C runtime RAM | **UNVERIFIED**; budgeted 64 B; check the map file | n/a |

### 2.2 Recommended budget

| Item | Bytes | Source / depends on |
|------|------:|---------------------|
| Capture buffer `int16_t[150][3]` | 900 | [C1] |
| Pre-trigger ring, 16 entries x 6 B (P = 15) | 96 | [C1] decision 5 |
| Drain staging buffer, bursts capped at 16 samples (192 if a full 32-sample drain is allowed) | 96 | [C1] §3.4, C6a §3.2 |
| Features `int16_t[60]` | 120 | [C3] |
| Feature scratch (accumulators, indices) | 32 | [C3] |
| MLP working set x8 + h + logits | 112 | [C4] (x8 counted here once) |
| k-NN templates 4 x 5 x 60 B | 1200 | [C5] |
| k-NN metadata (counts, labels, per-class radius) | 16 | [C5] |
| WS2812 framebuffer 64 x 3 | 192 | C6b |
| UART buffers: TX ring 128 + RX ring 32 | 160 | [C2] pending |
| I2C driver state | 32 | |
| Application globals (state machine, thresholds, timers, learn state) | 96 | |
| Bulb/IR state | 32 | C6b |
| C runtime and library statics | 64 | UNVERIFIED |
| **Stack** | 512 | D1 |
| **Total used** | **3660** | **44.7% of 8192** |
| **Free** | **4532** | 55.3% |

Difference from S1-5R's 3,714 B: the review added the ring at 90 B (this file uses C1's 16 entries = 96 B, +6) but kept both the old x8 line (60 B) and C4's 112 B working set, which already contains x8, so it counted x8 twice (-60). Net 3,660 B.

Options on top of the lean total: staging of 192 B instead of 96 B (+96); two class-0 anti-templates (+120). **Worst case with all options: 3,972 B (48.5%), 4,220 B free.**

### 2.3 Scenarios

Base without template data = 3,660 - 1,200 = **2,460 B**. With the 2 KB free policy, templates plus extras may use at most 8,192 - 2,460 - 2,048 = **3,684 B**. Rows above the default cap of 4 learned classes, or with int16, are **hypothetical**: C5 fixes int8 and 4 classes by default.

| Scenario | Templates | Extra | Total used | Free | Policy ok? |
|----------|----------:|-------|-----------:|-----:|------------|
| Lean: 4 x 5 int8 (default) | 1200 | none | 3660 | 4532 | yes |
| Lean + 192 B staging + anti-templates | 1200 | +216 | 3876 | 4316 | yes |
| (hyp.) 7 x 5 int8 (C5 maximum) | 2100 | none | 4560 | 3632 | yes |
| (hyp.) 7 x 5 int8 + 192 B staging + anti-templates | 2100 | +216 | 4776 | 3416 | yes |
| (hyp.) 4 x 5 int16 | 2400 | none | 4860 | 3332 | yes |
| (hyp.) 7 x 5 int8 + second capture buffer | 2100 | +900 | 5460 | 2732 | yes |
| (hyp.) 7 x 5 int16 | 4200 | none | 6660 | 1532 | **no** |

Conclusion: RAM is not binding. The only configuration that breaks the policy is int16 together with 7 classes.

### 2.4 Mitigations if RAM gets tight (in order)
1. Cap staging at 16 samples (already assumed) and the ring at P = 15.
2. Reuse the capture buffer as scratch for features after the window closes (it is locked until released, so only if C1 allows).
3. Drop the UART ring and send straight from the capture buffer.
4. Palette-index framebuffer (64 B plus palette).
5. Reduce `GESTURE_TEMPLATES_PER_CLASS`.

## 3. Details: RAM items

### 3.1 Stack
- No dynamic allocation, no recursion, big arrays `static`. Rough worst case (estimate): main about 30 B + `gesture_classify` + `mlp_forward` + dense helper (30 to 40 B each) = about 150 B, plus up to three nested ISRs at about 30 to 50 B each (PC + SR word + saved W registers). Total about 250 to 300 B, so 512 B has about 2x margin.
- Verify with `--stack=512`, the linker stack guidance, and a paint-and-check test (fill with 0xA5 at boot; report the high-water mark over UART).
- Danger: any `printf`-family call (stack and flash cost **UNVERIFIED**).

### 3.2 Capture path (C1)
- 900 B buffer, 96 B pre-trigger ring (the ring is a real RAM item: C1 converts and remaps samples at unpack time, so the FIFO cannot be read straight into the capture buffer, contrary to revision 1), 96 B staging. C1 keeps draining into the ring while the buffer is locked in READY, so classification time (about 5 to 7 ms) never threatens the 160 ms drain deadline.

### 3.3 k-NN templates
- 60 B each (int8 `x8`). L1 distance sum fits `uint16_t`; the confidence formula `(d2 - d1) * 255` needs `uint32_t` on XC16 (16-bit `int`, C5 §4).
- Learned IDs 9..12 mean nothing across resets (C5 §3), so RAM-only persistence is consistent with the API.

### 3.4 UART and I2C
- Raw stream: 600 B/s binary or about 2 KB/s CSV, against 11.5 KB/s at 115200 (5% to 17%). [C2]
- UART hardware FIFOs are 4 deep (DS39881E p.1). If C2 streams CSV live in 16-sample bursts (about 320 B) the TX ring must grow, or stream from the capture buffer after the window.

## 4. k-NN persistence: flash facts and design

### 4.1 Facts

| Fact | Value | Source |
|------|-------|--------|
| Program memory | 22 K instructions (22016) at 24 bits = **66,048 B** nominal | DS39881E Table 4-1 (p.30) |
| Linker user program region | `ORIGIN = 0x200, LENGTH = 0xA9FC` (ends at 0xABFC); `CONFIG2` at 0xABFC, `CONFIG1` at 0xABFE | GLD lines 65 to 71 (confirmed by S1-5R) |
| Usable code space | (0xABFC - 0x200) / 2 = 21,758 instructions = **65,274 B** at 3 B each | computed from GLD |
| Config words | top two words (0xABFC, 0xABFE), reloaded on every reset | DS39881E §4.1.3 (p.30); Table 24-1 (p.209) |
| Danger | "Performing a page erase operation on the last page of program memory clears these values and enables code protection" | DS39881E §5.5 (p.48) |
| Erase block | 8 rows = **512 instructions = 1536 B**, aligned from address 0, i.e. every 0x400 address units | DS39881E §5.2 (p.48) |
| Write row | **64 instructions = 192 B**; 64 `TBLWT` per row; unused latches must be 0xFFFFFF | DS39881E §5.2 (p.48) |
| Last erase block | 0xA800 to 0xABFF (0xAC00 = 43 x 0x400): holds the config words **and may hold code** | computed; S1-5R observed the linker placing `main` at 0xA800 once A/B were reserved |
| Endurance, retention | **10,000 E/W minimum**, 20 years | DS39881E p.1; Table 27-9 D130, D134 (p.242) |
| Write time | self-timed write about **3 ms typical** (D133A), not stated per row or per block. **Erase time UNVERIFIED** | DS39881E Table 27-9 (p.242) |
| CPU during write | the processor **stalls** until done | DS39881E §5.5 (p.48) |
| Key sequence | 0x55 then 0xAA to NVMKEY then set WR; the datasheet example uses `DISI #5` (a priority-7 ISR can still break it) | DS39881E §5.5.1 (p.49) |
| Data per word | 16 bits visible to PSV and `TBLWTL`; `TBLRDH`/`TBLWTH` reach the other 8; table reads take 2 cycles | DS39881E Fig 4-2, §4.3 (p.30, 43); Table 26-2 |
| PSV windows | PSVPAG selects 32 KB pages (16K words). 0x9800 to 0xA7FF is in **page 1** (0x8000 to 0xFFFF), while default `.const` is in page 0, so reading needs PSVPAG = 1 or a `__prog__` pointer with `TBLRDL` | DS39881E §4.3; S1-5R |
| Linker reservation form (tested) | `__attribute__((space(prog), address(0xA000), aligned(2), noload)) const uint8_t rsv[2048];` emits a 0x800-byte NEVER_LOAD section at 0xA000. `fillupper` is not needed. 2048 B of array = 1024 words (2 B/word). A reservation reaching 0xA800 and beyond fails ("crosses the boundary") | S1-5R (xc16-gcc v2.10, real `.gld`) |
| Reserved region and code placement | By default the allocator places code from the bottom (0x200 up); at about 25 KB use it never reaches 0x9800. The attribute turns that into a guarantee | S1-5R |
| Whether a download erases a NEVER_LOAD region | **UNVERIFIED**; check the programmer's "preserve program memory range" option | n/a |

### 4.2 Options

| Option | Cost | Risk |
|--------|------|------|
| (a) RAM only | 0 flash, 0 code | learned gestures vanish at reset or re-flash. Fine for a live demo |
| (b) RTSP save/restore | reserved blocks (3 to 6 KB), about 0.7 KB code, `gesture_save()`/`gesture_load()` | wrong erase wipes code or the config words; a write stalls the CPU about 3 ms per row (UART RX overflows, §4.3); brown-out mid-write corrupts a block (CRC + A/B); not testable in the simulator (**UNVERIFIED**) |
| (c) Dump to PC over UART | about 0.3 KB code and PC tool work | needs the PC at boot |

### 4.3 Design of (b): the blob does not fit one 2 B/word block
- Revision 1 proposed two A/B blocks, each holding one copy. **That does not work:** at 2 B per word one 512-instruction block holds 1024 B, and the blob is 4 x 5 x 60 + 16 = **1216 B**. (The "2048 B usable" figure was for both blocks together.)

| Variant | Reserved | Each copy | Code impact | Contract impact |
|---------|---------:|-----------|-------------|-----------------|
| **P1** 3 B/word via `TBLWTL`+`TBLWTH`, `TBLRDL`+`TBLRDH` | 2 blocks = 3,072 B | 1 block (1536 B >= 1216 B) | +about 300 B and a second read path (no PSV) | none |
| **P2 (recommended if (b))** 2 B/word, four blocks | 4 blocks = **6,144 B** at 0x9800 to 0xA7FF | 2 blocks (2048 B >= 1216 B) | smallest: 16-bit words, PSV reads, 2 erases per save | none |
| **P3** smaller blob, 2 B/word, 2 blocks | 2,048 B | 1 block (1024 B): 4 x 4 x 60 + 16 = 976 B | smallest flash | changes C5 (4 templates per class) |
| **P4** single copy | 2 blocks | no power-loss safety | smallest code | none |

- Reservation for P2 (same form as the tested 2048 B case, extended; the 4096 B variant itself is untested): `__attribute__((space(prog), address(0x9800), aligned(2), noload)) const uint8_t tpl_rsv[4096];`. Copies A = 0x9800 to 0x9FFF, B = 0xA000 to 0xA7FF.
- **Block C (0xA800 to 0xABFF) is not empty**: it holds the config words and the linker may place code there. "Never touched" therefore means **never erased**. The erase routine must reject any address outside 0x9800 to 0xA7FF (hard check).
- A/B: write the new copy (sequence number + CRC16) into the other pair, then erase the old pair; at boot take the valid copy with the highest sequence.
- Save cost: 1216 B / 128 B per row = 10 rows x about 3 ms + 2 erases (erase time **UNVERIFIED**; if about 3 ms each) = about 36 to 45 ms of CPU stall. Do it only on an explicit command, idle, with no capture, no WS2812 show, no IR frame and the **host not transmitting** (a 3 ms stall exceeds the 260 to 347 µs UART RX overflow window, see C6b §4.3).
- Wear: 10,000 cycles per block, a handful of saves per session: well under 1%.
- Needs a board session (the simulator may not model NVMCON writes, **UNVERIFIED**).

### 4.4 Recommendation reasoning
For a class demo, learned gestures are shown live, so RAM-only suffices and cannot brick the chip. Persistence is the one feature that can damage the target and cannot be verified in the simulator. `knn_export`/`knn_import` keep the door open at near-zero cost.

## 5. Flash budget (64 KB)

### 5.1 Facts and rules

| Fact | Value | Source |
|------|-------|--------|
| Usable program space | 65,274 B (21,758 instructions) | §4.1 |
| `const` data costs 1.5x | one byte of `const` costs about 1.5 B of flash (2 of 3 bytes per word visible); C4 measured 1178 data B = 1767 B | DS39881E §4.3, Fig 4-2; C4 §3 |
| PSV window | one 32 KB page for `auto_psv` data | DS39881E §4.2; XC16-UG |
| PSV access cost | +1 cycle for MOV/MOV.D, +2 cycles for other instructions outside REPEAT | DS39881E §4.3 (per S1-5R) |
| CPU instruction timing | `MUL.SS` 1 cycle, `DIV.SW` 18, taken `BRA` 2, `TBLRDL` 2 | DS39881E Table 26-2 (p.226) |
| Vectors | 0x000 to 0x1FF | DS39881E §4.1.2 (p.30) |

### 5.2 Estimate (code lines are guesses except `features.c`)

| Item | Flash (B) | Notes |
|------|----------:|-------|
| Startup, clock/PPS init, vectors, main loop | 1,200 | |
| LIS3DH driver + I2C + FIFO drain | 2,000 | |
| Capture state machine, ring, trigger, double tap | 1,200 | |
| UART driver + raw stream (C2) | 1,500 | |
| `features.c` | **400** | C3 measured 240 B (-O1) / 189 B (-O2), about 350 B in isqrt mode; `/15` is `repeat #17; div.sw`, no library calls |
| `mlp.c` | 1,200 | requant may call `___muldi3` (C4 D3, cost UNVERIFIED), see libc line |
| `knn.c` + learn + export/import | 1,800 | |
| `gesture.c` API + reject | 1,000 | |
| `ws2812.c` (asm loop, chunking, variant switch, brightness limit) | 1,200 | |
| Icons + animations | 4,000 | 1-bit bitmaps + color for animations |
| `bulb.c` (NEC / PWM) | 1,200 | |
| libc/runtime helpers | 2,000 | |
| Debug/test hooks, version string, paint test | 1,000 | |
| **Code subtotal** | **19,700** | |
| MLP constants (W1 960, W2 144, B1 64, B2 36, off 120, sh 60, M1 32, SH1 16, scalars about 32 = about 1,464 B) x 1.5 | 2,196 | C4 §3 |
| **Total without persistence** | **21,896** | **33.5% of 65,274 B**; 43,378 B free |
| + P2 reservation (four blocks) | 6,144 | only if D4 (b) |
| **Total with P2** | **28,040** | 43.0%; 37,234 B free |
| (alt.) with P1 (2 blocks + about 300 B code) | 25,268 | 38.7% |

Note on S1-5R's flash totals: the review quoted a code subtotal of 18,700 B. The line items in revision 1 actually summed to 21,100 B (revision 1 printed 20,100, an addition error carried into the review), so the corrected subtotal after the `features.c` change is 19,700 B, not 18,700 B. Review totals shift by +1,000 B: 21,896 / 28,040 (P2) instead of 20,896 / 27,040. The conclusion is unchanged. Even doubling every estimate stays under 50 KB. A `printf` with float support is the one thing that could blow the budget (**UNVERIFIED**; avoid, D6).

## 6. CPU time per gesture

### 6.1 Assumptions
Fcy = 16 MHz: 62.5 ns per cycle, 16,000 cycles per ms. XC16 `-Os`, no DSP engine. About 10 to 20 cycles per C-level inner-loop step with 32-bit accumulation. I2C at 394 kHz (C6a BRG 38; 2.54 µs per clock).

### 6.2 Timeline

| Stage | Estimate | How derived |
|-------|----------|-------------|
| Capture window | 150 samples at 100 Hz, which includes 15 pre-trigger samples, so about 1.35 s after the trigger | C1 §3.6 |
| FIFO drain over I2C | about 21 ms total over the window = **1.4%** at 394 kHz; about 85 ms (5.6%) at 100 kHz | 54 clocks per sample x 150 + 10 bursts x 29 clocks = about 8,400 clocks x 2.54 µs |
| Drain per burst | 16 samples = 893 clocks = **2.27 ms** (394 kHz) or 8.93 ms (100 kHz) | C6a §3.2; deadline 160 ms after the watermark (FTH = 15) |
| Feature extraction | about 0.7 to 2 ms (11k to 32k cycles) | 450 sample-axis steps x 12 to 16 cycles, 30 segment finalizations (`DIV.SW` 18 cycles), normalize to x8. isqrt mode adds 5k to 9k cycles (0.3 to 0.6 ms at 16 MIPS; C3 quotes its ms at 4 MIPS) |
| MLP, 1104 MACs | about 0.8 to 1.7 ms | 12 to 22 cycles per int8 MAC including about +2 for PSV access, plus requant |
| Reject logic | under 0.05 ms | |
| k-NN, 20 templates x 60 | about 0.5 ms (8.4k cycles) | about 7 cycles per element; 7 x 5 hypothetical = about 0.9 ms |
| Icon render | about 0.05 ms | |
| WS2812 show | **about 1.8 to 2.2 ms** + at least 0.3 ms reset | C6b §3.1 |
| IR bulb frame | about 68 ms, interrupt driven, under 1% CPU | C6b |
| **Compute after capture ends** | **about 4 to 7 ms** (without the IR wait) | sum of the above |
| Gesture start to bulb | about 1.35 s + 7 ms + 68 ms = **about 1.45 s** | dominated by the capture window |

### 6.3 Does it fit?
- During capture the CPU is about 97% idle. After capture, 4 to 7 ms of compute against the **160 ms** drain deadline (C1/C6a), a factor of 20 to 40; even a 10x underestimate (70 ms) fits. C1 keeps draining into the ring in READY, so nothing is lost.
- The C6b rules apply: `ws2812_show()` returns BUSY while a drain is pending, in 4-LED chunks. Animations at 30 fps cost 2.2 ms of 33 ms = 7%.
- Learn gesture: one feature extraction plus a store, about 1 to 2 ms. Optional flash save about 36 to 45 ms in idle.
- **Verdict:** time is not a constraint. The latency users feel is the capture window itself.

## 7. Open questions
1. [C1] Is staging capped at 16 samples (96 B) or a full 32-sample drain (192 B)? Is the ring 16 entries (96 B)?
2. [C3] Final energy mode (shift or isqrt) changes only `features.c` flash (about 240 to 360 B) and cycles. Any change to the 60 x int16 shape resizes the features line.
3. [C4] Is `x8` stable at 60 B and the working set at 112 B? Does `___muldi3` get linked for requant (flash cost)?
4. [C2] Live CSV streaming (needs a TX ring of 300+ B) or post-window dump?
5. Is persistence of learned gestures wanted at all (D4)? If yes, P2 (four blocks), P1 or P3?
6. Which programmer is used, and can it preserve the reserved flash across downloads (and does a NEVER_LOAD region get erased)?
7. Real C runtime RAM and stack high-water mark (first map file, ticket 3.10); confirm builds link with the device `.gld`.
8. Block erase time (Table 27-9 gives only the 3 ms write; check DS39715 or measure).
9. Anti-templates (+120 B) and `GESTURE_MAX_LEARNED` above 4: needed? (C5 D4, D2)
