# C1 proposal: capture buffer (WP1 to WP3)

Author: research-sensor (ticket S1-1), 2026-11-14. **Status: PROPOSAL, not a decision.** Hadi decides.
Needs a fact-check pass (S1-1R). Nothing here was tested on hardware.

Source keys: **[DS]** = ST LIS3DH datasheet, DocID17530 **Rev 1** (May 2010), https://cdn-shop.adafruit.com/datasheets/LIS3DH.pdf (st.com was unreachable from this machine; the newest revision was NOT read).
**[AN]** = ST AN3308 (DocID18198) **Rev 3**, June 2017, https://core-electronics.com.au/attachments/uploads/lis3dh-application-note.pdf.
**[PLAN]** = docs/agent/hadi/PLAN.md.

## 1. Decisions needed

1. **Stored sample format.** (a) raw left-justified 16-bit register value; (b) arithmetic `>> 4` to 12-bit; (c) `>> 4` and also scale to mg.
   RECOMMENDATION (needs Hadi's decision): (b). int16 values in about -2048..+2047 (1 g is about 512), lossless in high-res mode, and the only option where an energy sum (sum of x^2 over 15 samples) fits int32. Raw 16-bit can overflow int32 (section 3.1).
2. **Layout.** (a) `int16_t buf[150][3]` sample-major; (b) `buf[3][150]` axis-major.
   RECOMMENDATION (needs Hadi's decision): (a), as already written in [PLAN] C1. Matches FIFO burst order, Python `(150,3)` arrays and the UART frame. Axis-major gains only a little loop speed (UNVERIFIED, not measured).
3. **Where the sensor-to-wand axis remap happens.** (a) driver, at unpack time; (b) feature code; (c) Python only.
   RECOMMENDATION (needs Hadi's decision): (a), one table of axis index + sign in a board header, verified by the tilt test in section 3.3. Everything downstream, including the UART stream, is then in wand frame.
4. **Trigger alignment and FIFO mode.** (a) Stream-to-FIFO (hardware freeze on motion interrupt); (b) FIFO mode (arm on motion); (c) Stream mode run continuously, MCU drains into a small software pre-trigger ring, window cut by sample index; (d) Bypass + data-ready polling.
   RECOMMENDATION (needs Hadi's decision): (c). Only (c) gives a gap-free 150-sample window with pre-trigger samples. (a) holds at most 32 samples in total.
5. **How many pre-trigger samples (P).** 0, 15 (0.15 s, one segment), or 30 (0.30 s, hardware maximum for 4a).
   RECOMMENDATION (needs Hadi's decision): P = 15. Costs 90 B of ring RAM and puts the motion onset at the start of segment 2, giving a consistent leading rest segment for training and runtime.
6. **Overflow policy.** (a) discard the window and re-arm; (b) keep the window, set a flag; (c) ignore.
   RECOMMENDATION (needs Hadi's decision): (a) while a window is being filled (return an overrun status, count it); OVRN while idle is only counted.
7. **Buffers.** (a) one 900 B buffer, locked until the consumer releases it, while a small ring keeps draining; (b) two 900 B buffers.
   RECOMMENDATION (needs Hadi's decision): (a). Keeps the RAM plan at about 4.7 KB of 8 KB [PLAN section 4]; (b) adds 900 B for little benefit while a gesture takes 1.5 s (classifier time is UNVERIFIED, WP3 to measure).
8. **Window length and early stop.** (a) always exactly 150 samples; (b) variable length with padding.
   RECOMMENDATION (needs Hadi's decision): (a). Never pad with zeros (zero is not "at rest": gravity reads about 512 on the vertical axis).

## 2. Facts

| Fact | Value | Source |
|---|---|---|
| High-res mode enable | CTRL_REG4 (0x23) HR = 1 and CTRL_REG1 (0x20) LPen = 0 | [AN] sec 3.4 (p.11); [DS] Tables 24, 32 |
| High-res data resolution | 12-bit, left-aligned, in OUT regs 0x28..0x2D | [AN] sec 3.4 |
| Register word | 16-bit two's complement, left-justified; OUT_x_L at the lower address (BLE = 0 default) | [AN] sec 4.2.1, 4.2.2 (p.16) |
| Example | at +-2 g HR, 1 g reads 0x4000 (L=0x00, H=0x40); -1 g reads 0xC000 | [AN] Table 9 (p.17) |
| Sensitivity +-4 g | 2 mg/digit typ. (12-bit HR digit) with FS bits 01 | [DS] Table 3 (p.10); [AN] Table 3 (+-2 g HR = 1 mg/digit) |
| Derived scale +-4 g | 1 g is about 512 digits (12-bit) = about 8192 raw (16-bit); full scale +-2048 digits. Nominal only. | Derived from the rows above, see 3.1 |
| FS select | CTRL_REG4 FS1:FS0 = 01 gives +-4 g | [DS] Table 33 (p.31) |
| ODR 100 Hz | CTRL_REG1 ODR3..0 = 0101 | [DS] Table 26 (p.30); [AN] Table 4 |
| FIFO depth | 32 sample sets of X,Y,Z; one set is 6 bytes | [AN] sec 9.1 (p.41); [DS] sec 5.1 |
| FIFO word width | **Sources disagree**: [DS] sec 5.1 says "10bit data" FIFO; [AN] sec 9.1 says 16-bit left-justified | both cited; bench test in open question 2 |
| FIFO enable | CTRL_REG5 (0x24) FIFO_EN (bit 6) | [AN] sec 9.2.1 (p.43); [DS] Table 35 |
| FIFO modes | FIFO_CTRL_REG (0x2E) FM1:FM0 = 00 Bypass, 01 FIFO, 10 Stream, 11 Stream-to-FIFO ([DS] Table 44 calls 11 "Trigger mode"); TR bit: 0 = trigger from INT1 source, 1 = INT2; FTH[4:0] watermark | [AN] sec 9.2.2 (p.44); [DS] Tables 42-44 |
| FIFO_SRC_REG (0x2F) | b7 WTM, b6 OVRN_FIFO, b5 EMPTY, b4..0 FSS (unread count) | [AN] sec 9.2.3 (p.44); [DS] Table 45 |
| OVRN_FIFO meaning | set when the FIFO holds 32 unread samples; at the next ODR a new set replaces the oldest; cleared when the first set is read | [AN] sec 9.2.3 |
| WTM meaning | set when unread count exceeds FTH (FTH = 15 sets it at 16 unread) | [AN] Table 40 (p.45), sec 9.4 |
| Stream mode full | oldest data discarded, new samples overwrite | [AN] sec 9.3.3 (p.47); [DS] sec 5.1.3 |
| Stream-to-FIFO | runs as Stream; on trigger (INT1_SRC IA bit) switches to FIFO mode. If already full at the trigger: 30 pre-trigger samples + the triggering sample + 1 post-trigger sample, then it stops | [AN] sec 9.3.4 (p.49-50) |
| FIFO read | OUT regs return the oldest sample set; a burst read with auto-increment wraps from 0x2D back to 0x28 | [AN] sec 9.5 (p.52) |
| Auto-increment | MSB of the sub-address byte = 1 (0x28 \| 0x80 = 0xA8) | [DS] sec 6.1.1 (p.21) |
| INT1 sources | CTRL_REG3 (0x22): I1_CLICK b7, I1_IA1 b6, I1_IA2 b5, I1_ZYXDA b4, I1_321DA b3, I1_WTM b2, I1_OVERRUN b1 | [AN] Tables 13-14 (p.20) |

## 3. Details

### 3.1 Sample format and headroom (decision 1)
In HR mode the 16-bit word carries 12-bit data left-aligned ([AN] sec 3.4), so the low 4 bits carry no data and `raw >> 4` loses nothing. Use an **arithmetic** shift. XC16 should shift signed values arithmetically but that is implementation-defined in C: **UNVERIFIED**, add a test with a negative input. Python `>>` is also arithmetic (floor), which matches.

Headroom with int32 accumulators (C3 energy = sum of x^2, 15 samples per segment):
- 12-bit, worst case |x| = 2048: x^2 = 2^22, times 15 is about 6.3e7 (26 bits). Fits int32 with 5 bits spare.
- raw 16-bit, worst case |x| = 32768: x^2 = 2^30, times 15 is about 1.6e10, which **overflows int32** (max about 2.1e9). A realistic 2 g swing (16384 raw) gives 2^28 per sample, so 8 samples already overflow.
- Mean sums: 15 x 2048 = 30720 (fits int16 barely, use int32 anyway); 15 x 32768 = 491520 does not fit int16.
- Option (c), scaling to mg, needs a non-power-of-two multiply (2 mg/digit is nominal, not exact). It adds cost and no accuracy. Skip: the model trains on the same units.

### 3.2 Layout (decision 2)
Burst order is X_L X_H Y_L Y_H Z_L Z_H per sample ([AN] Table 35), so one 6-byte read is exactly one row `buf[i][0..2]`. Sample-major stores each row at once; axis-major needs three strided stores. For the extractor (10 segments x 15 samples per axis) sample-major means a constant 6-byte stride per axis, which is simple index arithmetic; axis-major is a plain pointer walk. The difference is a few cycles per sample (UNVERIFIED, measure in WP3 task 3.9). C3 must still fix the feature order separately.
Axis index: `buf[i][0]` = wand X, `[1]` = wand Y, `[2]` = wand Z.

### 3.3 Axis mapping and verification (decision 3)
[DS] Figure 2 (p.8, pin connection) shows the +X/+Y/+Z directions relative to pin 1 of the package. How the board sits on the wand decides the mapping, so it cannot come from a datasheet. **UNVERIFIED until the board is built**; the course board may fix it (open question 1).
Proposal: `board_axes.h` with, for each wand axis, the source sensor axis index (0..2) and a sign (+1/-1). The driver applies it when it unpacks each sample, so consumers and the UART stream use wand frame only. A static accelerometer reads **+1 g on the axis pointing up** (standard MEMS convention; not stated in the two ST documents I read, so UNVERIFIED there).
Tilt test (UART raw stream or debugger watch, values after `>> 4`, 1 g about 512):
1. Wand flat, board face up, tip away: expect (X, Y, Z) about (0, 0, +512). If Z reads -512, flip the Z sign.
2. Tip pointing straight up: expect X about +512; tip straight down: about -512.
3. Left side raised (left edge to the ceiling): expect Y about +512; right side raised: about -512.
4. Adjust mapping and signs until all three pass. Then twist the wrist 90 degrees and check that Y and Z trade places as expected.
If the tests can only pass by swapping two axes and flipping an odd number of signs, suspect a mirrored mounting and re-check; X out, Y left, Z up is right-handed.

### 3.4 Trigger alignment and FIFO mode (decisions 4, 5)
- **Bypass**: no history; needs a read per data-ready (100 transactions per second, about 0.83 ms each at 100 kHz, [AN] sec 9.5). Pre-trigger only through a software ring.
- **FIFO mode**: fills 32 samples, then stops; restart needs Bypass, which clears the buffer ([AN] sec 9.3.1-9.3.2). No pre-trigger. Not suitable.
- **Stream-to-FIFO**: the only hardware pre-trigger: up to 30 samples before, the trigger, and 1 after ([AN] sec 9.3.4). Then the FIFO **freezes at 32 samples**, so a 150-sample window cannot be completed; reading it out and restarting via Bypass loses samples in between. The trigger is level-sensitive (IA bit), should be latched (LIR_INT1, CTRL_REG5) and takes 2/ODR to clear. Rejected for the 1.5 s window.
- **Stream mode + MCU ring (recommended)**: leave the FIFO in Stream mode, watermark FTH = 15 on INT1 (or poll FIFO_SRC), drain FSS samples per burst into a small circular buffer, convert and remap. At trigger index t the window starts at t - P and continues for 150 samples in total, appended straight into `buf`. P is limited by RAM (6 B per sample with int16 x 3). Interrupt-service latency does not matter because alignment uses sample index, not time. A software threshold trigger on the drained data is also possible and runs identically in the Python tool on recordings, which keeps training and device windows aligned the same way. Choosing hardware motion interrupt (IA1) versus software trigger is a sub-decision I did not make; pin cost is in C6a.

Pre-trigger samples possible: 30 in hardware (Stream-to-FIFO, window then limited to 32 samples); unlimited by hardware in the recommended mode (RAM bound; proposal 15).

### 3.5 FIFO depth, drain deadline, overflow (decision 6)
A full 32-sample FIFO is 320 ms at 100 Hz. With FTH = 15 the watermark fires at 16 unread, leaving 16 samples = 160 ms before the first overwrite. A 16-sample burst is 96 bytes: about 8.9 ms at 100 kHz, 2.2 ms at 400 kHz (C6a). The driver must start a burst within about 150 ms of the watermark.
OVRN_FIFO = 1 means 32 unread; a sample is lost only if none is read before the next ODR tick ([AN] sec 9.2.3). The flag alone cannot tell whether one was lost, so treat OVRN seen at drain start, or a missed deadline, during an open window as a fault. Policy: drop the window, increment `capture_overruns`, re-arm after a quiet period. While idle only count it. OVRN can also go to INT1 (I1_OVERRUN) to catch a stalled main loop ([AN] Table 41).

### 3.6 Buffers and window boundaries (decisions 7, 8)
One window is 150 x 3 x 2 = 900 B. [PLAN] section 4 totals about 4.6 KB; a second buffer gives about 5.5 KB of 8 KB, and templates stored as int16 would add 1200 B more, which leaves very little stack. Single buffer: IDLE -> ARMED -> CAPTURING (150 samples) -> READY (buffer locked) -> release -> ARMED. In READY the driver keeps draining into the small ring and ignores triggers until released plus a refractory time. A gesture made while classifying is lost (accepted).
Exactly 150 samples (1.5 s) from the first stored sample (P pre-trigger + trigger + rest). If motion stops early the remaining samples are real at-rest samples and are kept as they are, so on-device windows look like the training recordings. Early termination would need a length field in C3/C4; not recommended.

## 4. Open questions
1. How is the LIS3DH board mounted, and does the course lab board or breakout fix the orientation? (Sets the axis table.)
2. Does the FIFO keep 12-bit data or truncate to 10-bit ([DS] Rev 1 vs [AN] Rev 3)? Bench check: tilt slowly, read FIFO words, see whether bits 5..4 of the 16-bit word change (12-bit) or stay 0 (10-bit). If 10-bit, resolution is 8 mg/digit at +-4 g and C1 needs review.
3. Is +-4 g enough for hard swipes and thrusts? Check clipping on real recordings (WP2).
4. Is a software trigger acceptable, or must the hardware motion interrupt be used? (Affects INT pin use, C6a.)
5. Maximum classification time (WP3 measure), to confirm single buffering.
6. The newest datasheet revision (Rev 5/6) was not read; if it differs from Rev 1 on FIFO or HR output, re-check section 2.
7. [AN] Rev 3 sec 9.3.2 says the OVRN interrupt is enabled via CTRL_REG5; [AN] Table 41 and [DS] say CTRL_REG3 (I1_OVERRUN). I used CTRL_REG3 and treat the other as a typo (UNVERIFIED on hardware).
