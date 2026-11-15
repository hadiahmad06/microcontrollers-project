<!-- [AI-GENERATED: Claude Code] -->
# Draft brief: T-trig (use ONLY after Hadi accepts Q2 in open_questions.md)

Pattern: three agents, as for 3.3: impl-trigger (firmware/src/trigger.{h,c} + tools/trigger_ref.py), test-trigger
(firmware/test/trigger/**, oracle written from CONTRACTS C1.9 only), review-trigger. Before launching:
1. Paste the accepted C1b recommendations into CONTRACTS.md as C1.9 (replace "OPEN"), with a provenance line, and
   record Hadi's decision in docs/human/hadi/DECISIONS.md (§5A). If Q3 is decided "overrule", update C1.6 too.
2. Spec to paste verbatim into both briefs: the new CONTRACTS C1.9 text, plus C1b §3.3 (state machine
   WARMUP → ARMED → LOCKED → REARM → ARMED, `trigger_feed` every drained sample in every state, `trigger_release`
   on buffer release or dropped window, `trigger_resync` for stream gaps, counters uint8, thr == 0 never fires,
   top clamp 12284 counts, quiet >= 16, warm-up >= 16).
3. Required API (from the spike's trigger.h, minus host-only parts): `trigger_init`, `trigger_set_threshold_mg`,
   `trigger_feed(const int16_t s[3])` → bool, `trigger_release`, `trigger_resync`, `trigger_statistic` (debug),
   plus the TRIG_DEFAULT_* constants; S hard-coded at 3 (C1b F-10). No float, no malloc.
4. Acceptance: host + sim16 suite bit-exact against the oracle AND against tools/trigger_ref.py on synthetic streams
   from tools/synth_dataset.py (continuous concatenations), mutation-proofed; repo-root `make test` all PASS.
5. Then 3.7 `gesture.c` per proposals/API_glue.md, tested with the fake LIS3DH (firmware/test/lis3dh/fake_lis3dh.*)
   feeding synthetic gesture streams end to end into the e2e models.
<!-- [END AI-GENERATED] -->
