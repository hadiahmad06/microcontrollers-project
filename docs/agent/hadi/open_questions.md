<!-- [AI-GENERATED: Claude Code] -->
# Open questions for Hadi

Kept by Hadi's main agent. Two container restarts killed pending question dialogs, so every
decision waiting on Hadi is listed here as well. Answer in chat at any time ("Q1 yes", "Q2 override ...").
Newest at the top of each section. When answered, the entry moves to `docs/human/hadi/DECISIONS.md`.

## Decisions waiting on Hadi

### Q1. C2 UART stream: accept the proposal? (ready, reviewed + fixed)
Record as your decision: "Accept every recommendation in docs/agent/hadi/proposals/C2_uart_stream.md
(decisions 1-9, as fixed after review S2-1R)."
- Binary little-endian frames; CSV only as a PC export. Only completed 150-sample windows are sent,
  after READY; the buffer is released when the last byte is queued (~70 ms).
- Frame `A5 5A | TYPE | LEN | SEQ | payload | CRC-16/IBM-3740`; decoders accept only known types.
- WINDOW (922 B) carries window_id, trig_idx, overruns, model hash and the on-device result.
- The PC attaches the label. **No PC → wand commands in v1** (wand is TX-only; this answers team
  question D-6 with "never" and removes the UART-RX-vs-LED-matrix overrun problem).
- HELLO at boot and every 2 s; test-vector frame types reserved; compile-time bring-up stream for
  the tilt test; ASCII text only between frames.
- Conflicts with CONTRACTS.md or other top-level docs: none.
Unblocks: UART driver + TX pump (WP1), PC recorder tool (WP2).

### Q2. Trigger rule (CONTRACTS C1.9): accept proposal C1b? (ready: reviewed S2-2R, fix round S2-2F applied)
Record as your decision: "Accept every recommendation in docs/agent/hadi/proposals/C1b_trigger.md (decisions 1-8, as fixed after review S2-2R)."
- Statistic EMA-L1: sum over 3 axes of |x − (base >> 3)| (baseline time constant 80 ms, gravity cancels in any orientation), debounce N = 2 consecutive samples.
- `gesture_set_trigger(threshold_mg)`: L1 mg at 2 mg/count; **default 250 mg**; 0 disables; recommended range 200..400 mg; >= 24567 clamps to a value that can still fire.
- t = the sample that completes the debounce (trig_idx = 15, window t−15 … t+134, no RAM change).
- Re-arm after release: 30 consecutive samples below thr/2; warm-up 32 samples after boot; baseline never frozen.
- Bit-exact C/Python (405 streams). Synthetic, UNVERIFIED: 0 % false triggers on rest/tilt/tremor, 100 % detection,
  0 % tilt false triggers on 1000 fresh seeds (vs 47 % for S=4/300 mg).
- **Risks to know:** slow-tilt peak 216 mg is close to 250 mg; tremor peak (122-132 mg) is close to the re-arm level (126 mg). Real recordings decide.
Unblocks: capture integration and the `gesture.c` API (3.7).

### Q3. ⚠️ Conflicts with a top-level doc (the proposal's sub-question Q5 in C1b §6)
You would be asked to say: "On a FIFO overrun while idle, also call trigger_resync()."
`docs/agent/CONTRACTS.md` C1.6 says: "OVRN while idle: count only." (decided 2026-11-14 by Hadi)
Options: **(1) Overrule** (C1.6 becomes "count, empty the ring and resync the trigger"), or **(2) Keep C1.6**: the trigger proposal works
either way (with `quiet >= 16` a later release is safe). Agent recommendation: (2), keep C1.6 as is; capture.c already empties the ring on any overrun.

### Q4. Contract wording: GM_DEFAULT_REJECT rule (CONTRACTS C5.2)
C5.2 says: "exporter rule: smallest value with ≤ ~2 % of held-out true gestures rejected". Read literally that is always 0.
The exporter (W2-1F) implements the evident intent: the **largest** min_conf that still rejects ≤ 2 % of held-out windows with
label ≠ 0. Record as your decision: "GM_DEFAULT_REJECT = the largest min_conf that rejects at most 2 % of held-out true gestures (label ≠ 0)." (yes/no)

### Q5. Contract wording erratum: conditioning constant K (CONTRACTS C4.3)
C4.3 says the float net is trained on x8 "optionally divided by a constant for conditioning, multiplied back into W1 by the exporter".
A net trained on x8/K has effective weights W1/K on x8, so the exporter must **divide** W1 by K (the tool does; e2e passes).
Record as your decision: "C4.3: the exporter divides W1 by K." (yes/no)

## Hardware / bench (only you or the team can answer)
- S2-0b: rerun `make selftest` in `docs/agent/hadi/spikes/sim` on your Mac (XC16 + MDB).
- Gate G3 (PLAN 3.9): build `firmware/src/*.c` with XC16 and run the e2e vectors on the MPLAB simulator
  or the board. The cloud runs the same tests on a 16-bit-int AVR simulator (sim16) as a pre-check only.
- LIS3DH FIFO_SRC at 32 unread: does FSS read 31 (saturate) or 0 (5-bit wrap) with OVRN = 1? The driver handles both
  (WP1-bF), but the bench answer goes into C-7's 2-minute check.
- Part C of `DECISION_SHEET.md` (C-1 .. C-15): lab-board pins, ICSP set, SA0, pull-ups, oscillator,
  WS2812 revision, USB-serial adapter, bulb hardware.

## Team questions (Part D of DECISION_SHEET.md)
D-1/D-2 bulb method (C6.4 is OPEN), D-3 who records training data, D-4 held-out set size, D-5 should
learned gestures persist, D-7 target false-reject/accept rates, D-8 learn only after MLP reject?,
D-9 UNKNOWN icon, D-10 CRC-32 owner, D-11 course schedule. (D-6 is answered by Q1 if accepted.)

## Cloud environment (optional)
The sim16 harness needs `simavr gcc-avr avr-libc`, installed by hand in this container. A future cloud
session will not have them unless the environment gets a setup script
(`apt-get install -y simavr gcc-avr avr-libc`). Say "save the setup script" and I will propose it.
<!-- [END AI-GENERATED] -->
