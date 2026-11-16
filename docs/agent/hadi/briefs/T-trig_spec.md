<!-- [AI-GENERATED: Claude Code] -->
# SPEC T-trig: product trigger module `firmware/src/trigger.{h,c}` + `tools/trigger_ref.py`

WORKING ASSUMPTION: open_questions Q2 (trigger C1b as proposed, fixed by S2-2F) and Q3 (keep C1.6), not decided.
Promoted from the spike `docs/agent/hadi/spikes/trigger/` (trigger.c, trigger.h, trigger_ref.py): cite it.

## T0. Product API (differences from the spike are deliberate)
- Statistic: **EMA-L1 only** (the other spike statistics are removed). Shift **S = 3 is a compile-time constant**
  `TRIG_SHIFT 3` (no runtime shift field; S2-2R F-10).
- Keep: `TRIG_WARMUP/ARMED/LOCKED/REARM`, `TRIG_STAT_MAX_COUNTS 12285`, `TRIG_THR_MAX_COUNTS 12284`, `TRIG_MIN_QUIET 16`,
  `TRIG_DEFAULT_DEBOUNCE 2`, `TRIG_DEFAULT_QUIET 30`, `TRIG_DEFAULT_WARM 32`, `TRIG_DEFAULT_MG 250`.
- `trigger_cfg_t { uint8_t debounce; uint8_t quiet; uint8_t warm; }` (init clamps debounce >= 1, quiet >= 16,
  warm >= 16; NULL = defaults).
- `trigger_t` fields public (for tests): `cfg`, `thr_mg` (uint16), `thr` and `lo` (uint16 counts), `state`, `seeded`,
  `warm_n` (saturates at 255), `run`, `quiet_n` (uint8 counters, saturating at 255), `base[3]` (int32), `stat` (uint16).
- Functions: `uint16_t trigger_mg_to_counts(uint16_t mg)`, `void trigger_init(trigger_t *t, const trigger_cfg_t *cfg)`,
  `void trigger_set_threshold_mg(trigger_t *t, uint16_t mg)`, `bool trigger_feed(trigger_t *t, const int16_t s[3])`,
  `void trigger_release(trigger_t *t)`, `void trigger_resync(trigger_t *t)`,
  `uint16_t trigger_statistic(const trigger_t *t)` (the statistic of the last sample fed; debug).
  NULL `t` or `s`: functions return (false / 0) without touching memory.
- Input samples are C1.1 counts in [-2048, 2047]. Values outside that range must still behave identically in C and
  Python: clamp each axis to [-2048, 2047] before use, so no int16/int32 overflow is possible.
- `trigger_set_threshold_mg` may be called at any time; it changes `thr`, `lo`, `thr_mg` only (state machine untouched).
- `tools/trigger_ref.py`: class `Trigger` mirroring the C API and field names one to one, with `state_hash()` over
  (stat, state, base x3, run, quiet_n, warm_n, seeded); plus
  `run(samples, cfg=None, thr_mg=250, rel_delay=135, resync_at=-1) -> (trigger_indices, hash)` for offline labelling of a
  continuous recording (proposal §3.4: the trigger is released `rel_delay` samples after it fired); plus
  `cut_windows(samples, trigger_indices) -> list of (t, window)` where window = samples[t-15 : t+135] (150 rows; a trigger
  whose window would start before 0 or run past the end of the stream is skipped).
  `python3 tools/trigger_ref.py --selftest` prints `trigger_ref selftest PASS`.

## T1. Verbatim: proposal C1b §1 decisions 1-8 (`docs/agent/hadi/proposals/C1b_trigger.md`)

1. **The motion statistic.** (a) deviation from a slow integer baseline, L1 over 3 axes (EMA-L1); (b) same baseline, max-abs over 3 axes (EMA-MAX); (c) sample-to-sample difference, L1 (JERK-L1); (d) |x²+y²+z² − 512²| (MAG2); (e) a plain magnitude threshold on raw samples is impossible (gravity is about 512 counts on whatever axis points up).
   RECOMMENDATION (needs Hadi's decision): (a) EMA-L1 with baseline shift S = 3 (time constant 8 samples = 80 ms). `stat = Σ_axes |x − (base >> 3)|`, then `base += x − (base >> 3)`. In firmware S must be a compile-time constant (a runtime 32-bit shift is a library call on a 16-bit core); the spike keeps it a runtime field only for its tests. No multiplies, orientation independent, ignores gravity because gravity is in the baseline. JERK-L1 cannot separate tremor from slow gestures; MAG2 misses motion across the gravity direction and pure rotations (section 3.1, table).
2. **Debounce.** (a) 1 sample above threshold; (b) N consecutive samples; (c) k of the last M.
   RECOMMENDATION (needs Hadi's decision): (b) with N = 2. N = 1 fires on every single-sample spike (100 % of my synthetic bumps), N = 2 rejects them (0 %) and costs 1 sample of latency; N = 3 costs another sample for no extra rejection in my data (rows `S3 N1/N2/N3 250` in section 4). Real bumps ring for several samples (UNVERIFIED), so they may still trigger; that is accepted (class 0, C5).
3. **Units of `threshold_mg`.** (a) 2 mg per count: `counts = (mg + 1) >> 1`; (b) 1000/512 mg per count: `counts = (mg·512 + 500) / 1000`; (c) the datasheet sensitivity only as a comment.
   RECOMMENDATION (needs Hadi's decision): (a). Meaning: **the L1 deviation, summed over the 3 axes, in mg** (a nominal 1 g jolt of 512 counts on one axis reads 1024 mg). 0 = triggering disabled (the baseline keeps running). **Default 250 mg = 125 counts.** **Top of the range: the statistic can reach at most 12285 counts (3·4095) and the test is `stat > thr`, so a threshold of 12285 counts could never fire. Recommendation: clamp, do not disable: any `threshold_mg >= 24567` becomes 12284 counts**, the largest threshold that can still fire (only a full-scale swing on all three axes does; tested in C and Python). Only 0 disables. 24566 mg is 12283 counts, 24567 and above are 12284. (a) is exact in 16 bit shifts and equals the datasheet's 2 mg/digit at ±4 g [C1p §2 Facts]; it differs from the nominal 512 counts/g of [C] C1.1 by 2.4 % (512 counts read 1024 mg, not 1000), which is far below the sensor-to-sensor spread of 500..512 that C1.1 already allows.
4. **Baseline behaviour.** (a) seed from the first sample, then a warm-up of 32 samples without triggers; (b) start at 0 and settle; (c) freeze the baseline in CAPTURING/READY/refractory.
   RECOMMENDATION (needs Hadi's decision): (a), and **never freeze** (not even in CAPTURING or READY). The trigger is fed every drained sample in every state. Reason: after a "raise" or "twist" the wand rests in a new orientation; a frozen baseline would keep the statistic high forever and the trigger would never re-arm.
5. **Refractory and hysteresis.** (a) fixed dead time after release; (b) re-arm only when the statistic is low (hysteresis); (c) both.
   RECOMMENDATION (needs Hadi's decision): (c) in one rule: after `trigger_release()` re-arm only after **30 consecutive samples (0.3 s) with `stat < thr/2`** (`lo = (thr + 1) >> 1`); `trigger_init` raises a configured quiet count below 16 to 16 so REARM always outlasts the 16-entry ring. A wand that is still moving never re-arms; 0.3 s is about 4 baseline time constants, so the baseline has caught up with the final orientation. While the buffer is LOCKED or READY the trigger cannot fire at all (C1.7).
6. **Where t is.** (a) the sample that completes the debounce (the Nth consecutive sample above threshold); (b) back-dated to the first sample of the run.
   RECOMMENDATION (needs Hadi's decision): (a). Then `trig_idx = 15` in C2's WINDOW frame is exact and the window is samples t−15 … t+134 as in C1.5. Back-dating needs a 17-entry ring (the 16-entry ring of C1.5 only holds t and 15 earlier samples), so (b) would change C1's RAM budget.
7. **Pre-trigger ring.** (a) trigger may not fire until at least 16 samples were drained since boot/resync; (b) fire and pad.
   RECOMMENDATION (needs Hadi's decision): (a), enforced by the warm-up (default 32, never below 16: `trigger_init` raises smaller values). After a release the ring keeps draining (C1.7), so it is always full. **Overrun while a window is open: the capture code calls `trigger_release()` (window dropped, C1.6); REARM then needs 30 quiet samples, so the next window starts after the gap.** `trigger_resync()` (re-seed, warm up again, 32 samples) is for gaps that C1.6 does not cover (see Q5; using it for an overrun while idle would CHANGE C1.6, which says "count only"). Never pad (C1.8).
8. **Python mirror.** (a) a bit-exact integer mirror (`trigger_ref.py`), run on the continuous raw stream; (b) a separate float-based rule.
   RECOMMENDATION (needs Hadi's decision): (a). The spike proves bit-exactness: trigger indices and a per-sample hash of the internal state (statistic, state, baseline ×3, run, quiet and warm counters) are identical on 405 streams (400 synthetic, 5 full-scale swings at the top of the threshold range) including different configs, thresholds, release delays and resync points.

## T2. Verbatim: proposal C1b §3.2 units and §3.3 state machine

`counts = (mg + 1) >> 1` computed in `uint32_t` (65535 + 1 would wrap a 16-bit `int`), clamped to **12284**. Values: 0→0, 1→1, 2→1, 3→2, 250→125, 500→250, 24566→12283, 24567 and above (up to 65535)→12284. Round half up, so 1 mg is already 1 count (never silently 0). **At and near the top of the range:** 12285 counts (the largest possible statistic) can never fire because the test is `stat > thr`, so the clamp stops one count lower; at 12284 only a full-scale swing on all three axes (−2048 to +2047 on each) fires. Treating "too large" as "disabled" was rejected: a caller who asks for the least sensitive setting should still get the hardest shake, and 0 is already the explicit disable. `gesture_set_trigger(m)` may be called at any time; it takes effect at the next sample, keeps the state machine untouched, and recomputes `lo`.

States: `WARMUP → ARMED → LOCKED → (release) REARM → ARMED`. Call `trigger_feed(s)` for every drained sample in every state. In `ARMED`: `run = (stat > thr) ? run+1 : 0`; when `run >= N` the sample is the trigger t, state = `LOCKED`. In `LOCKED` nothing happens until the capture code calls `trigger_release()` (buffer released, or window dropped for an overrun, C1.6; this is the overrun call, `trigger_resync()` is not used there). In `REARM`: `quiet = (stat < lo) ? quiet+1 : 0`; at `quiet >= 30` state = `ARMED`. `trigger_resync()` returns to `WARMUP` with a re-seed (for a stream gap that no open window covers; see decision 7 and Q5; with `quiet >= 16` enforced, release alone is also safe). The baseline update never stops. `thr == 0` never fires. All counters are uint8.

The first sample after init/resync seeds `base = x << S`, so the statistic starts at 0 even when the wand is not level. The first sample allowed to fire has index 32 (index 0 is the seed), so the window start t−15 ≥ 17 is real data. If the wand is moving at boot, 32 samples (4 time constants of S = 3) make the baseline error shrink to about 2 %.

Interaction with the capture state machine of C1.7: the trigger's `LOCKED` state is the "ignore triggers in CAPTURING/READY" rule, and `REARM` is the "refractory time". The capture code needs no second gate; it only calls `trigger_release()` when it releases the buffer. **One rule is needed on the capture side:** if `trigger_feed()` returns true while the capture state machine (C1.7) is not in a state that starts a window (for example IDLE), the capture code must call `trigger_release()` at once; otherwise the trigger stays LOCKED with nobody to release it and the wand goes deaf. Call `trigger_init` once at boot, feed every drained sample from then on, and treat a true return as "start a window if ARMED, else release". If a gesture is made during READY it is lost (accepted, C1.7).

## T3. Verbatim: proposal C1b §3.4 offline labelling

`trigger_ref.run(samples, cfg, thr_mg, rel_delay, resync_at)` returns trigger indices and the state hash. For a continuous recording (the C2 raw stream) call it with `rel_delay = 135` ("window complete, buffer released at once"); real firmware holds the buffer longer, so the offline labels are the most optimistic set. An isolated 150-sample WINDOW cannot be re-labelled because it starts only 15 samples before t (warm-up needs ≥ 16); there use the metadata `trig_idx = 15`.

## T4. Open points the spec leaves to the spike (follow the spike exactly; report if unclear)
- Exact meaning of "first sample allowed to fire has index 32": follow the spike's `warm_n` logic.
- Whether the sample on which REARM → ARMED happens can itself count toward `run`: follow the spike.
<!-- [END AI-GENERATED] -->
