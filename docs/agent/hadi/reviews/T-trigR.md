<!-- [AI-GENERATED: Claude Code] -->
# T-trigR review (review-24): trigger.{h,c}, trigger_ref.py, firmware/test/trigger

Reviewed at 3f32dbc (includes d90c236 T-trig and ac7da77 T-trigT; the review worktree was fast-forwarded to it).

**Verdict: MERGE AFTER FIXES** (no correctness defect; two documentation gaps that W2-6 and gesture.c rely on).

## Runs
- `make -C firmware/test/trigger test`: `PASS host seed=1..3 (59 directed + 120 random, ~45.7k lines match oracle)`, `PASS trigger_ref cross-check: 3 reference streams`, `PASS sim16: 59 directed + 12 random, 9804 lines match`, `trigger suite PASS`.
- `... test IMPL_DIR=standin`: same lines, `trigger suite PASS` (build line confirmed to compile `standin/trigger.c`).
- `python3 tools/trigger_ref.py --selftest`: `selftest: 240 spike-equality streams` / `trigger_ref selftest PASS`.

## Spec check (T0-T4): conforms
API, constants, clamps (debounce>=1, quiet>=16, warm>=16), NULL handling, per-axis clamp before use, `(mg+1)>>1` in uint32 with clamp 12284, `lo=(thr+1)>>1`, first fire index 32 (warm_n logic), REARM->ARMED sets run=0 so that sample does not count, never-frozen baseline, state_hash field order: all match. `cut_windows` bound `t-15>=0 and t+135<=len` yields exactly samples t-15..t+134 (150 rows); selftest asserts 14 skipped, 15 and 265 kept, 266 skipped.

## Findings
1. **MEDIUM (doc), trigger.h:299-304 `trigger_resync` and `trigger_release`**: resync from LOCKED unlocks (state := WARMUP, run/quiet_n cleared); this is not stated. gesture.c inherits two duties that are only implicit: (a) when it calls resync with a window open, it must drop that window too; (b) it must never deliver a stale `trigger_release()` after a resync: release is ignored in WARMUP/ARMED, but if it arrives after warm-up and a new fire it releases the NEW lock early. Fix: add both sentences to the two doc comments. Release acts only from LOCKED (documented, correct).
2. **MEDIUM (doc), trigger_ref.py:173-201 `run`**: docstring too terse for W2-6 offline cutting. Add: (a) t = the Nth consecutive sample above threshold; (b) `release()` is called after the state hash of sample `t+rel_delay` is taken, so it takes effect for sample `t+rel_delay+1` and REARM quiet counting starts there (135 is one later than "window complete" at t+134; this is spike/spec behaviour, keep it, but say so); (c) `rel_delay<0` never releases, so only one trigger per stream; (d) `resync_at` calls `resync()` BEFORE feeding index `resync_at`, so that sample is the new seed (no fire before `resync_at+32`) and a pending release is discarded; (e) returned indices index into `samples` and feed `cut_windows` directly. In `cut_windows` say window[15] is sample t and rows are t-15..t+134 inclusive.
3. **LOW, trigger_ref.py:268-288**: spike-equality block is silently skipped when `docs/agent/hadi/spikes/trigger` is absent and the run still prints PASS (only `0 spike-equality streams` hints at it). Fix: print `SKIPPED (spike not found)` or make the PASS line conditional.
4. **LOW, trigger_ref.py:25-36,86**: `mg_to_counts`/`set_threshold_mg` accept values outside uint16 that C cannot represent. Fix: assert `0 <= mg <= 65535`. `Trigger(cfg)` raises KeyError if a key is missing; document "all three keys required".
5. **LOW (perf, optional), trigger.c:124-126**: `base[i] >> TRIG_SHIFT` is written twice per axis. XC16 -O1+ should CSE it, but a local `int32_t b = t->base[i] >> TRIG_SHIFT;` makes it certain. Cost: three axes x (two inline constant 32-bit asr, subtracts, abs, 32-bit add, clamp) is about 40-60 instructions per axis, roughly 200 cycles per sample, about 0.1% of the 160k-cycle sample period (16 MIPS, 100 Hz). Negligible. Constant 32-bit shifts are inline (no library call); `(int32_t)1 << TRIG_SHIFT` folds to 8 and shifts a positive constant (defined). No float, malloc, delay, or division.
6. **INFO, right shift of negative int32**: implementation-defined in C99 but arithmetic on gcc and XC16; documented in trigger.h:199-201, mirrored by Python floor `>>`, and bit-exactness is shown by the host and sim16 cross-checks. Acceptable. Optional hardening: a test-only check that `(-8 >> 1) == -4`.
7. **INFO, rules**: AI markers, doc comments on all public functions, fixed-width types, WORKING ASSUMPTION line, spike citation, AI_USAGE rows (AI_USAGE.md:654-655) present. No register writes. capture.h:20 integration contract (caller MUST call trigger_release()) is consistent with trigger.h.

## Tests (test-trigger)
Written against the oracle from the spec; the independent stand-in passes the same suite, so the harness is not tied to trigger.c. No test gap found that would hide findings 1-4 (documentation items). The equivalent run/warm saturation mutants are accepted: the 255 cap is unreachable with the configured thresholds.
<!-- [END AI-GENERATED] -->
