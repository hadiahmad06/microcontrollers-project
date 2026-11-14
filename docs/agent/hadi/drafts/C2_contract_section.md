<!-- [AI-GENERATED: Claude Code] -->
<!-- Draft of the C2 section of docs/agent/CONTRACTS.md. Pasted in ONLY if Hadi accepts Q1 (open_questions.md). -->

## C2. UART raw stream (WP1 → WP2)
Source: `proposals/C2_uart_stream.md` (review S2-1R, fix round S2-1F). Spike: `docs/agent/hadi/spikes/uart/`.
- Decided: <date> by Hadi. Not contested.

1. **Link.** UART1, 115200 8N1 (C6.1). The wand only transmits in v1: **no PC → wand commands**
   (so the C6.3 "host does not transmit during show" rule is never needed; team question D-6 = "never").
2. **Encoding.** Binary frames, every multi-byte field little-endian (CRC too). CSV exists only as an
   export of the PC tool.
3. **What is sent.** Only completed 150-sample windows, sent from the locked C1 buffer after READY
   (one extra state READY → SENDING → release). The buffer is released when the last frame byte is
   queued (≈ 70 ms). Plus HELLO beacons.
4. **Frame.**
```
offset size field
0      1    SYNC0 0xA5
1      1    SYNC1 0x5A
2      1    TYPE  0x01 HELLO, 0x02 WINDOW (v1); reserved: 0x03 RESULT, 0x04 SAMPLES, 0x10 CMD, 0x11 VECTOR
3      2    LEN   payload length (10 for HELLO, 914 for WINDOW)
5      1    SEQ   frame counter, wraps at 256, restarts at 0 on reset
6      LEN  payload
6+LEN  2    CRC   CRC-16/IBM-3740 (poly 0x1021, init 0xFFFF, no reflection, xorout 0; check("123456789") = 0x29B1)
                  over bytes 2 .. 5+LEN, low byte first
```
   A decoder accepts a frame only if TYPE is one it knows, LEN is that type's single legal value and the CRC
   matches; on any failure it drops one byte and rescans.
5. **WINDOW payload (914 B; frame 922 B).** `window_id u16 | n_samples u8 (150) | trig_idx u8 (15) |
   overruns u16 | model_hash u32 | flags u8 (bit 0 = result valid) | class_id i8 | conf u8 | events u8 |
   450 × int16` (samples `buf[0][0], buf[0][1], buf[0][2], buf[1][0], …`, wand frame). `window_id` counts
   windows sent (overrun-dropped windows take no id); `events` = event bits latched during this window (never
   via `gesture_events()`); all metadata snapshotted at READY.
6. **HELLO payload (10 B; frame 18 B).** `proto_ver u8 (1) | odr_hz u8 | range_g u8 | n_samples u8 | pre_trig u8 |
   feature_ver u8 | model_hash u32`. Sent at boot and every 2 s while no frame is in flight.
7. **Label.** Attached by the PC recorder; nothing on the wire.
8. **TX pump rules.** One TX owner; frames are atomic (never aborted); bounded number of main-loop iterations per
   frame; no PC-side timeout (no flow control exists).
9. **Text.** ASCII (0x0A, 0x0D, 0x20..0x7E) only between frames (boot hash print, stack report).
10. **Bring-up.** A compile-time option streams type 0x04 SAMPLES chunks (`chunk u16 | n u8 = 16 | 16 × 3 × int16`,
    LEN 99, frame 107 B) with no trigger; never in the demo build.
11. **Test vectors** (PLAN 3.9) are deferred; the reserved types keep room for them.
<!-- [END AI-GENERATED] -->
