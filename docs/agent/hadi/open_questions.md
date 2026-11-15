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

**Data for Q2 from the integration spike S3-1 (synthetic, UNVERIFIED; `spikes/integration/`):** with the C1b defaults the
whole pipeline detects 92-96 % of gestures with a +40-sample hit window (99 % with +50: the few "false windows" are late
triggers 43-49 samples after the onset of a long gesture; idle, bumps, tremor and tilts produced zero windows; review S4-3R);
dead time after a trigger is ~1.7 s; slow-start gestures (circles, twist) trigger late, so their onset lands at window index 4-6
instead of ~15.
Possible refinement (not a recommendation yet): let samples seen while LOCKED count toward the 30-sample quiet re-arm.

### Q8. Data for C5 tuning (provisional constants; from S3-1 finding 6), FYI
With the exporter-chosen GM_CONF_SHIFT, typical MLP confidence on correct windows is ~80 (P90 ~140), so
`GESTURE_OVERRIDE_CONF = 192` makes the MLP count as "weak" almost always; with one template per class and the default
radius 1200, other-class windows sit at L1 ≈ 900-1000 from a template (tail down to ~380), so a learned id replaced the result on
78 of the 117 hits of classes without a template (72 of them had been correct); overall accuracy 140/154 → 74/154
(91 % → 48 %, synthetic; corrected by review S4-3R). Measured alternatives (S4-3R, numbers only): radius 600 → 133/154;
override conf 64 → 119/154; both → 135/154; override conf 255 → no change. C5 marks these constants "provisional, tune on data"; nothing changes
until real recordings exist. Options to consider then: derive GESTURE_OVERRIDE_CONF from the conf distribution, a smaller
default radius (e.g. 600), or require ≥ 2 templates before a class may override. Also (S3-1 finding 5): train on windows cut
by the real trigger from continuous recordings, not on fixed-onset windows (accuracy 82 % vs 99 % by onset position).

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

### Q6. Contract wording: which set is C4.3's "fixed held-out set"? (from review W2-2R M3)
C4.3 says the int16 fallback is judged "on a fixed held-out set of n ≥ 500 windows", and "every reported accuracy, model
selection and early-stopping decision uses the integer path ... on the held-out set". Using ONE set for checkpoint selection,
for choosing GM_CONF_SHIFT/GM_DEFAULT_REJECT and for reporting makes the reported numbers optimistic (measured: 78.7 %
reported vs a 77.8 % ceiling on a hard synthetic set). Agent recommendation, record as your decision (yes/no):
"Training uses a train/validation/test split (about 60/20/20, grouped by subject when the data has subjects). Validation
selects the checkpoint, GM_CONF_SHIFT and GM_DEFAULT_REJECT, and the C4.3 fallback is judged on validation (n ≥ 500).
The test set is scored once on the final header and gives every reported accuracy and rejection rate."
⚠️ This refines decided C4.3 (a top-level doc): options (1) overrule = adopt the wording above into C4.3, (2) discuss with the team.

### Q7. Contract wording FYI: drain bound per call (C1.4) (from PR-2R)
C1.4 says the drain loops "until FSS < 16 at the re-read". `lis3dh_drain` also stops after 4 bursts (64 samples) per
call and reports `more`, so the main loop calls it again (keeps each call bounded; no sample is lost: the FIFO keeps
them). Record as your decision (yes/no): "C1.4: the drain may stop after 4 bursts per call and resume on the next call."

## Hardware / bench (only you or the team can answer)
- CLICK_THS bit 7 (LIR_Click) read-back: `lis3dh_init` reads back every config write; if bit 7 of CLICK_THS (0xB0) does
  not read back as written on the real part (C-7), init fails with LIS3DH_ERR_BUS every time. Check this first at bring-up.
- S2-0b: rerun `make selftest` in `docs/agent/hadi/spikes/sim` on your Mac (XC16 + MDB).
- Gate G3 (PLAN 3.9): build `firmware/src/*.c` with XC16 and run the e2e vectors on the MPLAB simulator
  or the board. The cloud runs the same tests on a 16-bit-int AVR simulator (sim16) as a pre-check only.
- LIS3DH FIFO_SRC at 32 unread: does FSS read 31 (saturate) or 0 (5-bit wrap) with OVRN = 1? The driver handles both
  (WP1-bF), but the bench answer goes into C-7's 2-minute check.
- Datasheet check (anyone with the newest LIS3DH datasheet): the reserved-bit comments for CTRL_REG5 (bits 5:4) and
  CTRL_REG6 (bits 2, 0) in `firmware/src/lis3dh.c` were written from memory (WP1-bF2); the written values (0x40, 0x80) are
  from the reviewed proposals.
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
