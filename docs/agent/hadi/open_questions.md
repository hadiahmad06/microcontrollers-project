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

### Q2. Trigger rule (C1.9): accept proposal C1b? (fix round S2-2F running; ask after it lands)
Will be posted here with the final numbers once S2-2F is merged. Unblocks the capture state machine.

## Hardware / bench (only you or the team can answer)
- S2-0b: rerun `make selftest` in `docs/agent/hadi/spikes/sim` on your Mac (XC16 + MDB).
- Gate G3 (PLAN 3.9): build `firmware/src/*.c` with XC16 and run the e2e vectors on the MPLAB simulator
  or the board. The cloud runs the same tests on a 16-bit-int AVR simulator (sim16) as a pre-check only.
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
