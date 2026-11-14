<!-- [AI-GENERATED: Claude Code] -->
# C2 proposal: UART raw stream (WP1 to WP2)

Author: research-uart (ticket S2-1), 2026-11-14. **Status: Reviewed (S2-1R), fix round applied 2026-11-14. Hadi decides.**
Spike: `docs/agent/hadi/spikes/uart/` (`make test` prints ALL PASS: C and Python encoders give identical bytes, decoder resyncs). Nothing here ran on the PIC24 or on XC16.

Source keys: **[PLAN]** = docs/agent/PLAN.md. **[OV]** = docs/archive/INITIAL_OVERVIEW.md. **[C1]**, **[C4]**, **[C5]**, **[C6a]**, **[C6b]**, **[C7]** = the proposals of the same name in this folder. **[SHEET]** = DECISION_SHEET.md (B5, D-6 as quoted in the ticket brief). **[CRC]** = Greg Cook, "Catalogue of parametrised CRC algorithms", https://reveng.sourceforge.io/crc-catalogue/16.htm (entry CRC-16/IBM-3740, recalled from memory; the page was not re-read, the check value is asserted by the spike test).

## 1. Decisions needed

1. **Baud.** Not re-decided here. C6a D5 owns it: (a) 115200, BRGH = 1, U1BRG = 34 (114286 actual, -0.79%); (b) 230400; (c) 250000. This proposal is written and costed at (a) and works unchanged at (b) or (c); only the time figures scale. Dependency: the frame is 922 B, so the baud sets how long the capture buffer stays locked (decision 3).
   RECOMMENDATION (needs Hadi's decision): follow C6a D5 (a). Nothing in C2 needs more.

2. **Binary, text, or hybrid; byte order.** (a) Binary frames; (b) CSV text lines (`x,y,z\n`, about 15 B per sample, worst 18 B) with a header line; (c) hybrid: binary frames plus a PC tool that can dump CSV.
   RECOMMENDATION (needs Hadi's decision): (c), i.e. **binary on the wire**, CSV only as an export in the Python tool. A window is 922 B binary (80 ms at 115200) versus about 2.3 KB CSV (about 200 ms, worst 237 ms), and a CSV line has no integrity check, so a flipped digit is silently a wrong sample in the training set. **All multi-byte fields little-endian** (the PIC24 is little-endian, so the samples can go out straight from `int16_t buf[150][3]` with no byte shuffling: UNVERIFIED, XC16 manual not re-read; the spike encodes byte by byte and does not rely on it). The CRC is also sent low byte first, so there is exactly one rule.

3. **What is streamed, and how it meets C1's single buffer and C7's TX ring.** (i) every drained sample continuously; (ii) only completed 150-sample windows; (iii) both.
   RECOMMENDATION (needs Hadi's decision): **(ii) windows only for v1**, sent from the capture buffer after the window is READY. Reasons: the recorder needs exactly what the classifier will see (same trigger, same P = 15 alignment, same wand frame); a window is self-contained, so one CRC protects all 150 samples and a lost window is one clean gap; and it needs no TX ring growth: the sender reads the locked buffer straight into the existing 128 B TX ring, which resolves C7 §3.4's "or stream from the capture buffer after the window" (C7 line "UART buffers 160 B" stays valid, plus about 30 to 32 B of sender state, see 3.6). Buffer rule: in recorder mode the C1 buffer is released only after (classification, if any) **and** the last frame byte has been queued, about 70 ms after the frame starts at 115200 (80 ms is the transmit time; the 128 B ring and the 4 B FIFO still hold the tail when the last byte is queued, 3.5). C1 keeps draining into the ring meanwhile, so the 160 ms FIFO deadline is not touched. For the first bring-up (the tilt test of C1 §3.3, before the trigger rule of ticket S2-2 exists) there is a compile-time BRING-UP option that streams type 0x04 SAMPLES chunks continuously with no trigger (16 samples, 107 B per 160 ms, about 669 B/s, 5.8% of the link; defined in 3.10). It is never in the demo build.

4. **Frame format, checksum, resynchronisation.**
   - 4a Framing: (a) two sync bytes `A5 5A` + type + 16-bit length + sequence + payload + CRC, resync by scanning; (b) COBS or SLIP byte-stuffing with a 0x00/0xC0 delimiter; (c) fixed-size frames with one sync byte.
   - 4b Checksum: (a) CRC-16/IBM-3740; (b) CRC-8; (c) Fletcher-16 or a plain sum; (d) CRC-32 (same polynomial family C4 uses for `GM_MODEL_HASH`).
   RECOMMENDATION (needs Hadi's decision): **4a (a), 4b (a).** Format in 3.1. CRC-16/IBM-3740: width 16, poly 0x1021, init 0xFFFF, refin false, refout false, xorout 0x0000, **check("123456789") = 0x29B1** [CRC] (asserted in C and Python by the spike). Why: a 922 B frame is far too long for CRC-8 (the 8-bit check lets about 1 in 256 corrupted frames through); Fletcher-16 and sums are blind to some swaps and to 0x00/0xFF substitution; CRC-32 costs 2 more bytes per frame and a 1 KB table or a slow bitwise loop for no gain at this frame length and error rate. CRC-16 catches every single-bit and every burst up to 16 bits and all odd-bit errors (the poly has the factor x+1); random corruption slips through about 1 in 65536 (standard CRC property, not measured here). Cost on the PIC24: a 16-entry nibble table is 32 B of data (about 48 B of flash with the PSV 3/2 convention of C7), two lookups per byte; the nibble technique is our own derivation from the bitwise definition (no source is cited), verified against the bitwise CRC by the spike test; cycles per byte not measured (**UNVERIFIED**; an estimate of 20 to 30 cycles gives 18k to 28k cycles for 918 bytes, about 1.1 to 1.7 ms of CPU, spread over the 80 ms send). COBS would add a 0.4% overhead and an encode pass over 900 B for little benefit, and it still needs a CRC. **Resync (3.2):** the decoder looks for `A5 5A`; a frame is accepted only if TYPE is one the decoder knows (v1: **only 0x01 HELLO and 0x02 WINDOW**), LEN is exactly the single legal value for that type (10 and 914), and the CRC matches. Any other TYPE (reserved, unknown, 0, above 0x0F) is a bad header: drop one byte and rescan. On any failure it drops exactly one byte and rescans what it already holds, so a fake sync inside garbage or inside a damaged frame cannot swallow a good frame behind it (except by a CRC collision, about 2^-16 per false candidate). The spike shows this with garbage, a fake header, a flipped bit, a dropped byte, a damaged LEN (WINDOW and HELLO), a truncated frame, reserved and out-of-range TYPEs, LEN 1024 and 1025, ASCII text between frames, and 40 fuzzed streams (no false accept, every intact frame recovered).

5. **Window delimiting and metadata.** (a) The frame **is** the delimiter (one window per frame) with metadata inside it; (b) start and end marker frames around sample chunks; (c) no metadata, samples only.
   RECOMMENDATION (needs Hadi's decision): (a), with these payload fields (3.1): `window_id` u16 (windows SENT since reset; a window dropped by an overrun takes no id and shows only in `overruns`, so a gap in `window_id` means a window lost on the wire, never an overrun; it survives SEQ wraps), `n_samples` u8 (= 150, C1 D8), `trig_idx` u8 (index of the trigger sample inside the window = P = 15, C1 D5, so a different P is visible to the recorder), `overruns` u16 (cumulative `capture_overruns`, C1 D6), `model_hash` u32 (`GM_MODEL_HASH`, C4, 0 if no model is linked), `flags` u8 (bit 0 = on-device result valid), and the optional on-device result `class_id` i8 (C5, -1 = `GESTURE_UNKNOWN`), `conf` u8 (C5), `events` u8 (the event bits latched while THIS window was captured: an internal per-window latch that the click ISR sets next to the public pending bit and that is cleared when a new capture starts; C2 never calls `gesture_events()`, which is the application's read-and-clear function (C5 D6)). **Snapshot rule:** `window_id`, `trig_idx`, `overruns`, `class_id`, `conf`, `flags` and `events` are all copied into the 14 B metadata scratch when the window becomes READY and sent unchanged. **Reset rule:** SEQ and `window_id` restart at 0 on reset; the first frame after reset is a HELLO with SEQ 0, which is the recorder's reboot cue (a `window_id` that goes backwards is the second cue). The result lets the recorder log what the wand decided next to the raw data, which is exactly the comparison PLAN WP2 and task 3.9 need; when no model is built in (data collection firmware) `flags` bit 0 is 0 and the three bytes are ignored. C1 D6 drops an overrun window, so a sent window is never a damaged one; `overruns` only tells the recorder how many were dropped.

6. **Label field.** (a) The wand attaches a label (button or learn mode); (b) the PC attaches the label; (c) both, with a reserved byte.
   RECOMMENDATION (needs Hadi's decision): **(b) the PC attaches it.** The recorder prompts "do gesture N now", receives the next window frame, and stores it with N. The wand has no UI for 9+ classes, and a label sent from the wand would still have to be checked by the PC. No label byte is on the wire in v1. A later version can add one only as a new frame type or after a HELLO `proto_ver` bump: a v1 reader checks LEN per type, so it would reject a WINDOW with an extra field. Open question 3 covers learn mode (`gesture_learn(class_id)` already knows its class).

7. **PC-to-wand commands.** (a) None in v1: the wand is transmit-only, stream on/off comes from `gesture_stream_raw(bool)` called by the firmware (compile flag or boot state of a recorder build), the RX pin stays unused; (b) a minimal command set (PING, STREAM on/off) with a rule; (c) a full command set (set label, set trigger threshold, and so on).
   RECOMMENDATION (needs Hadi's decision): **(a) for v1**, because it removes the UART RX overrun problem of C6a 3.4 and C6b 4.3 at the root (no RX traffic, so nothing to overrun while `ws2812_show()` masks interrupts) and answers team question D-6 ("does the PC ever transmit while the matrix refreshes") with "never". The HELLO frame is repeated as a beacon (decision 8) so a PC that opens the port late still learns the wand's settings without asking. **If D-6 is answered yes**, adopt (b) as defined in 3.7: one frame type, 0x10 CMD, 10 bytes on the wire (868 us), PING and STREAM only, reply = a HELLO. It is safe with the C6b mitigations already recommended there (RX ISR loops `while (URXDA)`, 4-LED chunks of at most 138 us against a worst-case 260 us overrun window): any byte that does overrun merely fails the CRC and the host resends after a timeout, provided the RX ISR also clears OERR (on the PIC24 the receiver stops after an overrun until the bit is cleared in software: recalled from the family datasheet, UNVERIFIED, check before relying on it). The extra rule "host does not transmit during show" ([SHEET] B5) is then not required; keep it only if the team drops chunking. (c) is not needed for anything in PLAN WP1 to WP3.

8. **Version and handshake.** (a) A HELLO frame at boot and repeated every 2 s while idle; (b) HELLO only on request (needs RX); (c) a version byte in every header; (d) none.
   RECOMMENDATION (needs Hadi's decision): (a). HELLO carries `proto_ver` (= 1), `odr_hz` (100), `range_g` (4), `n_samples` (150), `pre_trig` (15), `feature_ver` (C4 `GM_FEATURE_VERSION`) and `model_hash` (C4 `GM_MODEL_HASH`, matching C4 D6 "print `GM_MODEL_HASH` at boot"); 18 bytes on the wire, 1.6 ms. Beacon rule: send it at boot when streaming is on, then every 2 s while no window is in flight (about 9 B/s, 0.08% of the link). The recorder refuses to store windows until it has seen a HELLO whose `proto_ver` it knows, and it can store `model_hash` and the HELLO settings in the dataset manifest, so a dataset records what produced it. A version byte per frame (c) costs one more byte per frame, 1000 bytes per 1000 frames (about 0.11% of a 922 B frame), and gives nothing a beacon does not.

9. **Test vectors for PLAN 3.9 (on-target verification).** (a) Propose the framing now; (b) explicitly defer, reserving type IDs; (c) use the same framing, no new types.
   RECOMMENDATION (needs Hadi's decision): **(b) defer**, because it needs PC to wand traffic (decision 7) and a firmware RX parser that is outside what any ticket has costed. Feasibility of the same framing, so nothing in v1 blocks it (3.8): PC to wand type 0x11 VECTOR reuses the WINDOW payload layout; wand to PC type 0x03 RESULT carries `window_id`, class, conf, the 60 features (`int16`) and the 9 logits (`int32`) for the diff in PLAN 3.9, 170 bytes. Two real obstacles to cost then: the 900 B vector must be received **straight into the capture buffer** (a 32 B RX ring cannot stage it), and the test build must have no WS2812 activity or must use the chunked masking. **Type map:** wand to PC: 0x01 HELLO and 0x02 WINDOW (v1), **0x03 RESULT** (test-vector results, 3.8), **0x04 SAMPLES** (bring-up chunk, 3.10), 0x05..0x0F reserved; PC to wand: **0x10 CMD** (3.7), **0x11 VECTOR** (3.8), 0x12..0x1F reserved. A v1 decoder accepts ONLY 0x01 and 0x02, each with its exact LEN; every other TYPE is a bad header (drop one byte, rescan). A recorder that must read 0x03 or 0x04 extends its known-type table (the spike's `Decoder(extra_types=...)`), tied to a build flag or a `proto_ver` bump. The wand-side decoder for PC-to-wand frames has its own type range (0x10..0x1F).

## 2. Facts

| Fact | Value | Source |
|---|---|---|
| Wand-side API | `void gesture_stream_raw(bool on);` | [OV] Planned public API |
| C2 must pin down | baud, binary vs CSV, header/sync byte, checksum, window delimiting, label field | [PLAN] §1 table, row C2 |
| WP2 use | the recorder speaks C2 and stores labeled windows; test vectors = raw windows, features, logits, class | [PLAN] WP2 |
| UART baud options | 115200 BRGH=1 U1BRG=34 (114286, -0.79%); 230400 U1BRG=16 (+2.12%); 250000 U1BRG=15 (0.00%) | [C6a] D5, §3.4 |
| Baud formula | BRGH=1: Baud = FCY / (4 (U1BRG + 1)), FCY = 16 MHz | [C6a] §2 facts (PIC DS39881E Eq. 17-2) |
| Raw stream load per C6a | about 600 B/s of samples plus framing against 11.5 KB/s capacity | [C6a] D5 |
| UART RX FIFO | 4 deep; at 115200 one byte is about 87 us; interrupts masked for the 2 ms WS2812 frame can overrun RX; TX only pauses | [C6a] §3.4; [C6b] §4.3 (DS39881E p.1) |
| RX overrun window | worst case 260 to 347 us with one byte already pending; a 4-LED chunk masks at most 138 us | [C6b] §4.3 |
| UART TX FIFO | 4 deep | [C6b] §3 (Reg 17-2, DS39881E) |
| Host must not transmit during show | listed as team question D-6 (sheet row B5); show only from the main loop, BUSY while a drain is pending, no priority-7 ISR, gaps total at most 40 us | [SHEET] B5, D-6; [C6b] §4.4 |
| Stored sample | int16 after arithmetic `>>4`, 12-bit, about -2048..+2047, 1 g about 512 | [C1] D1 |
| Layout | `int16_t buf[150][3]`, sample-major, X tip, Y left, Z up | [C1] D2, §3.2 |
| Wand frame | axis remap done in the driver, so the UART stream is in wand frame | [C1] D3 |
| Pre-trigger | recommended P = 15 (0.15 s), window starts at t - P | [C1] D5, §3.4 |
| Window length | always exactly 150 samples (1.5 s at 100 Hz) | [C1] D8 |
| Overrun | window dropped and `capture_overruns` counted | [C1] D6, §3.5 |
| Buffer lifecycle | IDLE, ARMED, CAPTURING, READY (locked), release; ring keeps draining; FIFO deadline 160 ms | [C1] §3.4, §3.6 |
| RAM line | "UART buffers: TX ring 128 + RX ring 32 = 160 B, [C2] pending" | [C7] RAM table |
| Raw stream sizing in C7 | 600 B/s binary or about 2 KB/s CSV against 11.5 KB/s; CSV in 16-sample bursts needs a bigger TX ring "or stream from the capture buffer after the window" | [C7] §3.4 |
| UART code size | about 1,500 B for driver plus raw stream | [C7] flash table |
| Class IDs | built-ins 0..8, `GESTURE_UNKNOWN = -1` (`int8_t`), learned 9..12 | [C5] D2 |
| Confidence | `uint8_t` 0..255 | [C5] D3 |
| Events | `uint8_t gesture_events()` read-and-clear, `GESTURE_EVT_DOUBLE_TAP = 0x01`; C2 does not call it (decision 5) | [C5] D6 |
| Model identity | `GM_MODEL_HASH` (u32, CRC-32 IEEE over the header arrays), `GM_FEATURE_VERSION`, printed at boot | [C4] header, D6 |
| CRC-16/IBM-3740 | poly 0x1021, init 0xFFFF, refin false, refout false, xorout 0x0000, check("123456789") = 0x29B1 (alias CRC-16/CCITT-FALSE) | [CRC]; asserted by `make test` |
| `int` width | XC16 `int` is 16 bits; C99, fixed-width types required | AGENTS.md §7; [C1] §3.1 |

## 3. Details

### 3.1 Wire format (v1)

```
offset  size  field
0       1     SYNC0   0xA5
1       1     SYNC1   0x5A
2       1     TYPE    0x01 HELLO, 0x02 WINDOW  (v1 decoders accept only these two; 0x03 RESULT, 0x04 SAMPLES, 0x10 CMD, 0x11 VECTOR are reserved, see decision 9)
3       2     LEN     payload length, little-endian (914 for WINDOW, 10 for HELLO)
5       1     SEQ     frame counter, wraps at 256, counts every frame the wand sends, restarts at 0 on reset
6       LEN   payload
6+LEN   2     CRC16   CRC-16/IBM-3740 over bytes 2 .. 5+LEN (TYPE, LEN, SEQ, payload), low byte first
```

WINDOW payload (914 bytes): `window_id u16 | n_samples u8 (150) | trig_idx u8 | overruns u16 | model_hash u32 | flags u8 | class_id i8 | conf u8 | events u8 | 450 x int16` (14 bytes of metadata, then `buf[0][0], buf[0][1], buf[0][2], buf[1][0], ...` sample-major, X Y Z in wand frame, signed two's complement little-endian). Frame = 6 + 914 + 2 = **922 bytes**.

HELLO payload (10 bytes): `proto_ver u8 (1) | odr_hz u8 | range_g u8 | n_samples u8 | pre_trig u8 | feature_ver u8 | model_hash u32`. Frame = 18 bytes.

Why SEQ and `window_id` both: SEQ is per frame (so a lost HELLO or a lost window both show as a gap), `window_id` counts windows sent and survives SEQ wraps (an overrun-dropped window consumes neither); the decoder counts SEQ gaps and the recorder uses `window_id` to name the file.

### 3.2 Decoder (PC side, spike `c2_ref.py`)
Byte-at-a-time, buffer of unconsumed bytes. Steps: front byte must be 0xA5 and the next 0x5A (else drop one byte, count garbage); read TYPE, LEN, SEQ; the TYPE must be in the known table (v1: 0x01 with LEN 10, 0x02 with LEN 914) and LEN must equal its single legal value, otherwise drop one byte and count a bad header (this covers reserved types, TYPE 0, TYPE above 0x0F, LEN 1024 and 1025, and a damaged LEN of either known type); wait for the whole frame; check the CRC (on mismatch drop one byte, count CRC error); on success consume the frame.

**Worst-case stall.** A false header can only have a known TYPE and its legal LEN, so it waits at most until 6 + LEN + 2 bytes are buffered: 916 more bytes after the 6 header bytes for WINDOW (922 buffered), 12 more for HELLO. Measured by the spike test with a false WINDOW header (`A5 5A 02 92 03 00`):
- Continuous windows: a real WINDOW that follows the false header is delivered on its own last byte, with no delay at all, because the false candidate ends before the real frame does. Only a HELLO beacon between two windows can wait, until the next window's bytes complete the candidate: about one capture interval, 1.6 to 3 s of wall time (the data are 80 ms of line time).
- Beacon-only traffic (one 18 B HELLO every 2 s): the candidate needs 916 more bytes, which is 51 beacons, so the first real HELLO is delivered about 100 s late (at the 51st beacon). The recorder refuses to store windows until it has a HELLO, so the case can stall a recording start. It needs `A5 5A 02 92 03 00` or a similar legal header to appear in noise, which is rare, and no frame is lost.
- Optional PC-side rule, not in the spike: if no byte arrives for 50 ms while the buffer holds an incomplete candidate, drop one byte and rescan. A real frame has no such gap if the TX pump rules in 3.5 hold, and this cuts the beacon-only stall to the idle gap.
A real receiver also needs a read timeout so the tool can say "no data"; the beacon (decision 8) keeps data flowing.

### 3.3 Bandwidth at 115200 8N1 (recommended format)
One byte is 10 bits. At the nominal 115200: 11,520 B/s. At the real BRG 114286: 11,429 B/s (C6a D5 (a)).

| Item | Bytes | Time at 115200 | Time at 114286 | Share of link |
|---|---:|---:|---:|---|
| WINDOW frame | 922 | 80.0 ms | 80.7 ms | 100% for 80 ms |
| HELLO frame | 18 | 1.56 ms | 1.57 ms | beacon every 2 s: 9 B/s, 0.08% |
| Windows back to back (1.5 s capture + 80 ms send, about 1.58 s) | 922 per 1.58 s | | | 583 B/s, 5.1% |
| One gesture every 3 s (recorder use) | 922 per 3 s | | | 307 B/s, 2.7% |
| CSV window (comparison, about 15 B/sample + header) | about 2,255 | about 196 ms | | 2.4x the binary; worst case 2,730 B, 237 ms |
| Same frame at 230400 / 250000 baud | 922 | about 40 ms / 37 ms | | halves the lock time |

The 922 B binary window is 6.1 B per sample against the 6 B of raw data (2.4% overhead); the "600 B/s binary" of C7 §3.4 is the continuous-stream rate, which windows-only replaces with about 307 to 583 B/s.

### 3.4 Interaction with C1 (single locked buffer)
Recorder mode adds one state: READY -> (optional classify) -> SENDING -> release. In SENDING the buffer is read-only and the capture ring keeps draining. The buffer is released when the last frame byte has been queued into the TX ring, about 70 ms after the frame starts (the transmit time is 80 ms; the ring and FIFO still hold about 130 B). A gesture made in that time is lost, the same trade C1 §3.6 already accepts for a gesture made while classifying. There is no PC-stall case: the wand has no flow control (TX only, no RTS/CTS pin in C6a), the UART drains the ring at line rate whether or not anyone reads, and a closed port loses bytes at the adapter without ever back-pressuring the wand. The only real stall is a firmware one (TX ISR masked or starved, main loop blocked), covered by the bounded-iterations rule in 3.5. The wand never blocks on the PC: when the TX ring is full the pump simply does not advance that iteration.

### 3.5 TX pump (design for WP1, not in the spike)
Main-loop function called each iteration: if the ring has room, queue up to 32 bytes from the frame source and return. The source is a small state machine: HEADER (6 B built in a scratch array), META (14 B scratch), SAMPLES (bytes read directly from `buf`, one `int16_t` as low then high byte), CRC (2 B). The CRC is updated per chunk with `c2_crc16_update`, so no 922 B copy exists. This is non-blocking and bounded per call, as C1 requires. `c2_encode_window` in the spike (whole frame into a caller buffer) is the reference and the PC-side test oracle; firmware uses the incremental API. Rules for WP1:
1. **One TX owner, frames are atomic.** A frame, once started, is always finished; there is no abort and no truncated frame on the wire, so SEQ never skips because of a drop. HELLO beacons are inserted between frames only.
2. **Bounded completion.** The pump must finish a frame within a bounded number of main-loop iterations (WP1 picks the number; at 32 B per iteration a WINDOW needs at least 29). Exceeding it is a firmware fault (TX ISR masked or starved, loop blocked) to count and assert in a debug build, not a protocol feature; there is no PC-side timeout.
3. **Release.** The capture buffer is released when the last byte is queued.
4. **Snapshot.** All metadata is copied into the 14 B scratch when the window becomes READY (decision 5); SEQ is assigned when the frame starts.
5. **Text** only between frames (3.11).

### 3.6 RAM and flash
RAM: C7's 160 B for the UART rings stays. Add about 30 to 32 B of sender state (scratch for header and metadata 20 B, position 2 B, running CRC 2 B, SEQ 1 B, `window_id` 2 B, state 1 B, beacon timer 2 to 4 B): UNVERIFIED estimate, a few bytes either way. Flash: nibble table 32 B of data (about 48 B with the PSV 3/2 convention of C7) plus encoder; C7 budgets 1,500 B for "UART driver + raw stream", assumed to cover it (not measured).

### 3.7 Commands, only if D-6 is answered yes
`TYPE 0x10 CMD`, payload 2 bytes `cmd u8, arg u8`, frame 10 bytes (868 us at 115200). `cmd 1 PING` (reply: a HELLO frame), `cmd 2 STREAM` (`arg 0` off, `arg 1` on; reply: a HELLO). The wand's RX ISR loops `while (U1STAbits.URXDA)` into the 32 B RX ring and clears OERR (UNVERIFIED, see decision 7), the main loop feeds a decoder of the same style (3.2) with its own known-type range (0x10..0x1F) and ignores a bad CRC. A command is a single burst; the host waits for the HELLO (timeout 100 ms) before resending. The wand sets no rule about show(): C6b D2 (ii) plus 4-LED chunking already keeps a continuous 115200 stream below the overrun window. Without the chunking, fall back to [SHEET] B5's rule "host does not transmit during show", which then needs a way for the host to know a show is running (not designed here).

### 3.8 Test vectors, reserved layout (decision 9)
`0x11 VECTOR` (PC to wand): same payload layout as WINDOW, wand ignores metadata fields except `window_id`. `0x03 RESULT` (wand to PC; a v1 recorder rejects it, so a test-vector build needs the extended known-type table of decision 9): `window_id u16 | class_id i8 | conf u8 | events u8 | n_feat u8 (60) | features 60 x int16 | logits 9 x int32`, payload 2+1+1+1+1+120+36 = 162, frame 170 B (15 ms). The PC compares features, logits and class to PLAN WP2's exported test vectors. Costs not counted by any ticket: the RX parser writing into the capture buffer, a test-build mode, and an answer to whether the 80 ms receive time interacts with FIFO draining (it does not if the sensor is idle in test mode).

### 3.9 Spike results and limits
`make test` (host `cc`, `-std=c99 -Wall -Wextra -Wconversion -Werror -pedantic`): CRC check value 0x29B1 in C and Python; nibble-table C CRC equals bitwise Python CRC on 43 random strings; C and Python produce identical bytes for 1 HELLO and 40 WINDOW frames, including all samples -2048, all 2047 and full-range int16 (so negative values and the sign byte are exercised); the decoder round-trips 41 frames one byte at a time; directed damage and 40 fuzzed streams: no false accept, every intact frame recovered; fix round: 58 header-rejection cases (reserved and unknown TYPE, TYPE above 0x0F, LEN 1024, 1025 and 913, every single-bit hit in a HELLO LEN), ASCII lines between frames, and the measured stall of 3.2. `c2_frame.c` also builds clean with `avr-gcc -mmcu=atmega2560 -std=c99 -Wall -Wextra -Wconversion -Werror -O1` (16-bit `int`, compile only, not run). Not tested: XC16 (16-bit `int`; the code uses only `uint16_t`/`uint32_t` arithmetic and explicit casts, but that is unverified on target), real UART timing, the TX pump, framing errors from a real adapter.

### 3.10 Bring-up sample stream (compile-time option, never in the demo build)
Windows need a trigger, and the trigger rule is ticket S2-2, so the first bring-up (the tilt test of C1 §3.3) has no window source. A compile-time BRING-UP flag (name is WP1's) therefore streams **type 0x04 SAMPLES** chunks continuously with no trigger and no WINDOW frames. Payload, defined minimally with a fixed n so LEN is single-valued: `chunk u16 (counter, wraps) | n u8 (= 16) | 16 x 3 x int16`, LEN 2 + 1 + 96 = 99, frame 6 + 99 + 2 = **107 B** (9.4 ms at 115200). At 100 Hz one chunk per 160 ms: 669 B/s, 5.8% of 11,520 B/s. Sample i of chunk c is global sample 16c + i; a gap in `chunk` is a lost chunk. HELLO beacons still go out between chunks. The bring-up tool uses `Decoder(extra_types={0x04: 99})`; a v1 recorder rejects 0x04. Defined, not built: the spike has no encoder for it, only the decoder-table test. A timed capture (one WINDOW every N s regardless of motion) is an alternative bring-up trigger for the WINDOW path; WP1's choice.

### 3.11 Text on the same UART
Plain ASCII text (bytes 0x0A, 0x0D, 0x20..0x7E) may be sent only BETWEEN frames, never inside one: the C4 D6 boot print of `GM_MODEL_HASH` and the C7 stack high-water report share UART1 TX with the frame pump, so text goes through the same single TX owner and is queued only while the pump is idle between frames (or between SAMPLES chunks). ASCII is below 0x80, so it can never contain the sync byte 0xA5; the decoder counts text bytes as garbage and loses nothing (tested with interleaved lines). The recorder may show them as log lines.

## 4. Open questions
1. **D-6 (team):** does the PC ever transmit while the matrix refreshes? Decision 7 recommends "never" for v1; a yes needs 3.7.
2. Does the course lab board expose UART1 over a USB-serial adapter, and which adapter and driver does the recorder machine use? (Decides 115200 vs 230400 and 250000 with C6a D5; some adapters do not support 250000.)
3. Learn mode: should the recorder see which class the wand is teaching during `gesture_learn`? v1 says no (no label on the wire). If yes, add a type or a label byte with a `proto_ver` bump.
4. (Withdrawn in the fix round, S2-1R F-05: no PC-stall case exists, see 3.4.)
5. Is the recorder firmware a separate build (stream on at boot, no matrix animations) or the demo firmware with `gesture_stream_raw(true)`? Affects whether C6b's show rules and D-6 matter at all for C2.
6. Should the on-device result (class, confidence, events) be sent when a model exists but the user is collecting training data? It is cheap (3 bytes), but the recorder must not treat it as a label. Proposal: recorder logs it separately as `device_pred`.
7. XC16 behaviour of the nibble CRC and of the byte-per-iteration sender is UNVERIFIED; measure cycles per byte in WP3 task 3.10 style (pin toggle) before relying on the 1.1 to 1.7 ms estimate.
8. Time stamps: none on the wire (100 Hz fixed, sample i is at i/100 s from the window start, trigger at index `trig_idx`). Is wall-clock time from the PC enough for the recorder's manifest? Assumed yes.
9. Firmware details WP1 must settle: the TX ISR priority (not in the C6b B9 list), and `trig_idx` for a trigger within the first 150 ms after boot, when the pre-trigger ring holds fewer than P samples (C1 does not say).

## 5. Fix round (S2-1R)
- F-01: decision 8 now says one more byte per frame, 1000 bytes per 1000 frames (0.11%).
- F-02: 0x03 = RESULT, 0x04 = SAMPLES (bring-up), 0x10 CMD, 0x11 VECTOR; decision 3, the 3.1 table and decision 9 agree.
- F-03: 3.2 restates the stall (at most 922 buffered bytes for a false WINDOW header) and measures it: continuous windows no delay for windows, beacons up to one capture interval; beacon-only 51 beacons, about 100 s; test added.
- F-04: v1 decoder accepts only 0x01 (LEN 10) and 0x02 (LEN 914), any other TYPE is a bad header; the LEN-up-to-1024 path is removed from `c2_ref.py`; tests for reserved and unknown TYPE, TYPE above 0x0F, LEN 1024 and 1025, and a damaged HELLO LEN.
- F-05: PC-stall timeout dropped (3.4); firmware bounded-iterations rule and release-at-last-byte in 3.5; open question 4 withdrawn.
- F-06: new 3.11, ASCII only between frames; test with interleaved lines.
- F-07: `events` is a per-window latch, C2 never calls `gesture_events()` (decision 5).
- F-08: `window_id` counts windows sent, reset restarts SEQ and `window_id` at 0, all metadata snapshotted at READY (decision 5, 3.1, 3.5).
- F-09: not in this round (AI_USAGE rows are the main agent's).
- F-10: new 3.10, compile-time bring-up SAMPLES stream (0x04, n = 16, LEN 99, defined, not built).
- F-11: 2.3% corrected to 2.4%.
- F-12: chunk figure replaced by the defined 107 B chunk, 669 B/s, 5.8%.
- F-13: lock time stated as about 70 ms (queued), 80 ms is the transmit time.
- F-14: nibble table 32 B data, about 48 B flash (C7 PSV 3/2); sender state 30 to 32 B.
- F-15: the label wording now says a new type or a `proto_ver` bump is needed.
- F-16: OERR clearing added to decision 7 and 3.7 (UNVERIFIED on target); wand-side decoder has its own type range.
- F-17: D7 naming slip removed (D-6, sheet row B5).
- F-18: nibble-table CRC stated as our own derivation, verified by the test; no source cited (comment in `c2_frame.c`, README).
- F-19: `c2_cli.c` switched to fixed-width types (only `char` and `int main` remain, noted in the header).
- F-20: `c2_encode_window` takes non-const `int16_t (*samples)[3]` (CONTRACTS C3); the cast in `c2_cli.c` is gone.
- F-21: docstring added to the nested `frame` test helper.
- Also: "can never swallow a good frame" now says "except by a CRC collision" (review checklist 4).
<!-- [END AI-GENERATED] -->
