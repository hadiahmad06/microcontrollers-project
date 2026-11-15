<!-- [AI-GENERATED: Claude Code] -->
# C1b proposal: software trigger rule (CONTRACTS C1.9, decision B2)

Author: research-trigger (ticket S2-2), 2026-11-14. **Status: Reviewed (S2-2R), fix round applied 2026-11-14. Hadi decides.**
Spike: `docs/agent/hadi/spikes/trigger/` (`make test` ends with ALL PASS). **Everything below was measured on SYNTHETIC data I generated (UNVERIFIED) and nothing ran on hardware.** Every rate, latency and default must be re-checked on real recordings (WP2) before it is trusted. Every number quoted below is printed by a committed command of the spike (`make test`: rate table, per-gesture lines, margins, re-arm table, fresh-seed check); section 4 reproduces that output.

Source keys: **[C]** = docs/agent/CONTRACTS.md (C0, C1, API), **[C1p]** = proposals/C1_capture_buffer.md, **[C6a]** = proposals/C6a_sensor_io.md, **[C2p]** = proposals/C2_uart_stream.md, **[SPIKE]** = the spike in this folder.

## 1. Decisions needed

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

## 2. Facts

| Fact | Value | Source |
|---|---|---|
| Operating point | LIS3DH 100 Hz, ±4 g, high-res 12 bit; window 150 samples; segment 15 | [C] C0 |
| Sample range | int16 in [−2048, 2047], 1 g ≈ 500..512 counts (nominal 512) | [C] C1.1 |
| Frame | X out of the tip, Y left, Z up; a resting axis pointing up reads +1 g | [C] C1.3 |
| Per-sample order | ring push, trigger test, window append, each sample strictly in order | [C] C1.4 |
| Window around t | samples t−15 … t+134 (150), ring 16 entries × 6 B | [C] C1.5 |
| Trigger locked | in READY the driver ignores triggers until release plus refractory | [C] C1.7 |
| Trigger source | software threshold on drained samples, same rule in firmware and Python; hardware IA1 only an optional wake-up; rule, units, default, refractory OPEN | [C] C1.9 |
| Double tap | during an open window does not invalidate it | [C] C1.11 |
| Class 0 | trained on idle, noise and bumps; false triggers tolerated but each locks the buffer for one window | [C] C5 class 0 |
| API | `void gesture_set_trigger(uint16_t threshold_mg)` | [C] API |
| Sensitivity ±4 g HR | 2 mg/digit typical | [C1p] §2 (datasheet Table 3) |
| WINDOW metadata | `trig_idx` u8 = P = 15 | [C2p] WINDOW payload (§3.1) |
| Click is separate | double tap comes from the LIS3DH click engine on INT2, not from this trigger | [C6a] §3.5 |
| avr-gcc / int width | XC16 and avr-gcc `int` is 16 bit; the spike compiles clean with `-mmcu=atmega2560 -Wconversion -Werror` | [SPIKE] |

## 3. Details

### 3.1 The statistics compared (decision 1)

Notation: x = (x, y, z) sample, b = baseline, S = shift, counts, 100 Hz.

| | EMA-L1 (rec.) | EMA-MAX | JERK-L1 | MAG2 |
|---|---|---|---|---|
| Rule | Σ\|x_i − b_i\| | max\|x_i − b_i\| | Σ\|x_i[n] − x_i[n−1]\| | \|Σx_i² − 512²\| |
| Per-sample integer work | per axis: 1 asr (32-bit base), 1 sub, 1 abs, 1 add, 1 add32 (`base += dev`, reuses dev); 0 multiplies | same, `max` instead of add | per axis: 1 sub, 1 abs, 1 add; 0 multiplies; no baseline | 3 multiplies 16×16→32, 2 adds, 1 sub, 1 abs |
| State | 3 × int32 base (+ int16 prev in the spike) | same | 3 × int16 prev | none (spike still updates base for a uniform state hash) |
| Max values | dev in ±4095, stat ≤ 12285 (fits int16); base in −2048·2^S .. 2047·2^S (S = 3: −16384..16383 fits int16; S = 4 touches −32768 exactly, so any S above 3 or an added offset overflows int16; the spike uses int32 and clamps S to 1..8) | stat ≤ 4095 | stat ≤ 12285 | Σx² ≤ 3·2048² = 12 582 912 (24 bits, fits int32); stat ≤ 12.58e6 |
| Orientation | independent (gravity is in the baseline); L1 reads 1.0..1.73 × the Euclidean size depending on the direction of the motion | independent; 0.58..1.0 × Euclidean | independent for gravity; sees only changes | **dependent**: dynamic acceleration a changes \|g+a\|² by 2g·a_∥ + a², so motion across gravity (about 0 in the first-order term) is nearly invisible; pure rotation (twist) keeps \|x\| constant, so it is invisible; gain error 2.4 % alone shifts Σx² by about 12 000 |
| Slow tilt (my synthetic 60..120° in 2 s) | tracked with a lag of slope·2^S per axis; S = 3 gives peak 98..216 mg, below the 250 mg default (thin margin, section 4 Q1) | peak lower | sees about 2 counts/sample per axis: tiny | 0 % false (no change in \|x\|) |
| Hand tremor ±5..15 | peak 34..122 mg | lower | high: differencing doubles noise; fires on 77 % of tremor streams at 60 mg | 0 % false |
| Cost estimate on a 16-bit MCU | about 12 to 20 simple instructions, UNVERIFIED (cycles not measured; the 32-bit shift of `base` dominates) | similar | about 8 | about 15 plus 3 multiplies, UNVERIFIED |

Cost note: `dev = x − (base >> S)`; `base += dev`. With S a compile-time constant the shift is a fixed number of 32-bit `asr`. With S = 3 the exact value of `base` stays within −16384..16383 and would fit int16, but the spike keeps int32 and any narrowing must be re-verified against the mirror.

Why S = 3 and 250 mg, not S = 4 and 300 mg (the two candidates; the code defaults are the first, `grep DEFAULT trigger.h trigger_ref.py`). Criteria and evidence rows (section 4, synthetic, UNVERIFIED):

| Criterion | S = 3, 250 mg (RECOMMENDED) | S = 4, 300 mg | S = 4, 450 mg (what S = 4 needs for 0 tilt) |
|---|---|---|---|
| Rest / tremor false triggers | 0 % / 0 % | 0 % / 0 % | 0 % / 0 % |
| Slow tilt false triggers (60 seeds; fresh: 1000 seeds 5000..5999) | **0 %** (fresh 0 / 1000) | **47 %** (fresh 444 / 1000) | 0 % (fresh not run) |
| Bump (one sample, N = 2) | 0 % | 0 % | 0 % |
| Detection of gesture bursts | **100 %** | 100 % | 97 % |
| Latency median / P90 / share later than 15 samples | 4 / 14 / 8 % | 4 / 14 / 6 % | 7 / 26 / 22 % |
| Re-arm reachable against tremor (section 4, 1000 seeds) | 0 / 1000 fail | not run for S = 4 | not run for S = 4 |

S = 3 at 250 mg is clean on every criterion; S = 4 either false-triggers on slow tilts (73 % at 250 mg, 47 % at 300 mg, 100 % at 150 mg) or, at 450 mg, loses detection (97 %) and delays 22 % of the detections past the 15-sample pre-trigger. S = 2 is the other side: it fires on 82 % of one-sample bumps at 150 mg and detects only 87 % at 300 mg with 20 % late (rows `S2 N2 150/300`). S = 3 is therefore the choice, and the code defaults are S = 3, 250 mg.

### 3.2 Units (decision 3)
`counts = (mg + 1) >> 1` computed in `uint32_t` (65535 + 1 would wrap a 16-bit `int`), clamped to **12284**. Values: 0→0, 1→1, 2→1, 3→2, 250→125, 500→250, 24566→12283, 24567 and above (up to 65535)→12284. Round half up, so 1 mg is already 1 count (never silently 0). **At and near the top of the range:** 12285 counts (the largest possible statistic) can never fire because the test is `stat > thr`, so the clamp stops one count lower; at 12284 only a full-scale swing on all three axes (−2048 to +2047 on each) fires. Treating "too large" as "disabled" was rejected: a caller who asks for the least sensitive setting should still get the hardest shake, and 0 is already the explicit disable. For MAG2 the spike scales the threshold by 1024 (= 2·512, first-order conversion of a count change into Σx²); this is a spike-only detail. `gesture_set_trigger(m)` may be called at any time; it takes effect at the next sample, keeps the state machine untouched, and recomputes `lo`.

**Recommended valid range to document: 0 (off) or 200..400 mg**, the range my evaluation covers. The limit at the low end is hand tremor, not rest noise (rest peaks at 16 mg): re-arm needs 30 consecutive samples with `stat < thr/2`, and tremor (peak 122 mg on the tuning seeds, 132 mg on 1000 fresh seeds) blocks it when `thr/2` is low. Streams that never re-armed in 460 samples (tremor, 1000 seeds, S = 3, quiet 30; section 4 table): 100 mg 564 / 1000 (56 %), 150 mg 34 / 1000 (3 %), 175 mg to 300 mg 0 / 1000. Slow tilt also false-triggers 53 % of streams at 150 mg and 7 % (fresh seeds 5 %) at 200 mg. So below 200 mg the trigger either re-arms unreliably or fires on a wrist turn. 175 mg also re-armed 0 / 1000 but its tilt false rate was not measured, so the range starts at 200 mg. At the default 250 mg `lo` = 126 mg is only 4 to 10 mg above the tremor peak (122 to 132 mg); re-arm still never failed because it needs 30 consecutive quiet samples, but that margin is thin and real tremor decides it. Above 400 mg: 400 mg detects 94 % with 25 % late (section 4), so the upper end is limited by missed gestures; values up to the clamp are accepted but not recommended. The real LIS3DH noise at HR 100 Hz is UNVERIFIED.

### 3.3 State machine (decisions 2, 4, 5, 6, 7)
States: `WARMUP → ARMED → LOCKED → (release) REARM → ARMED`. Call `trigger_feed(s)` for every drained sample in every state. In `ARMED`: `run = (stat > thr) ? run+1 : 0`; when `run >= N` the sample is the trigger t, state = `LOCKED`. In `LOCKED` nothing happens until the capture code calls `trigger_release()` (buffer released, or window dropped for an overrun, C1.6; this is the overrun call, `trigger_resync()` is not used there). In `REARM`: `quiet = (stat < lo) ? quiet+1 : 0`; at `quiet >= 30` state = `ARMED`. `trigger_resync()` returns to `WARMUP` with a re-seed (for a stream gap that no open window covers; see decision 7 and Q5; with `quiet >= 16` enforced, release alone is also safe). The baseline update never stops. `thr == 0` never fires. All counters are uint8.

The first sample after init/resync seeds `base = x << S`, so the statistic starts at 0 even when the wand is not level. The first sample allowed to fire has index 32 (index 0 is the seed), so the window start t−15 ≥ 17 is real data. If the wand is moving at boot, 32 samples (4 time constants of S = 3) make the baseline error shrink to about 2 %.

Interaction with the capture state machine of C1.7: the trigger's `LOCKED` state is the "ignore triggers in CAPTURING/READY" rule, and `REARM` is the "refractory time". The capture code needs no second gate; it only calls `trigger_release()` when it releases the buffer. **One rule is needed on the capture side:** if `trigger_feed()` returns true while the capture state machine (C1.7) is not in a state that starts a window (for example IDLE), the capture code must call `trigger_release()` at once; otherwise the trigger stays LOCKED with nobody to release it and the wand goes deaf. Call `trigger_init` once at boot, feed every drained sample from then on, and treat a true return as "start a window if ARMED, else release". If a gesture is made during READY it is lost (accepted, C1.7).

### 3.4 Offline labelling (decision 8)
`trigger_ref.run(samples, cfg, thr_mg, rel_delay, resync_at)` returns trigger indices and the state hash. For a continuous recording (the C2 raw stream) call it with `rel_delay = 135` ("window complete, buffer released at once"); real firmware holds the buffer longer, so the offline labels are the most optimistic set. An isolated 150-sample WINDOW cannot be re-labelled because it starts only 15 samples before t (warm-up needs ≥ 16); there use the metadata `trig_idx = 15`.

### 3.5 Synthetic data (UNVERIFIED)
Shapes are documented at the top of `synth.py`: rest at random orientation, slow tilt 60..120° in 2 s, tremor ±5..15 + 8..12 Hz, one-sample 300-count bump, and six gesture shapes of 0.3..1.0 s with amplitude 200..1500 counts. They are my guesses. The trigger rates in the table depend entirely on these guesses.

## 4. Results (host spike, synthetic data, UNVERIFIED, C code)

`make test` output (60 streams per scenario, seeds 1000..1059, 500 samples each). **Synthetic, UNVERIFIED: do not paste this table without this caption.**

```
rule             thr |  rest  tilt tremor  bump | detect latMed latP90   >15   pre twice
EMA-L1 S2 N2     150 |   0%   0%     0%  82% |  99%     3    11   5%   0%   0%
EMA-L1 S2 N2     300 |   0%   0%     0%   0% |  87%     5    31  20%   0%   0%
EMA-L1 S3 N2     150 |   0%  53%     0%   0% | 100%     3     9   1%   0%   0%
EMA-L1 S3 N2     200 |   0%   7%     0%   0% | 100%     3    11   5%   0%   0%
EMA-L1 S3 N2     250 |   0%   0%     0%   0% | 100%     4    14   8%   0%   0%   <- recommended
EMA-L1 S3 N2     300 |   0%   0%     0%   0% |  99%     5    18  12%   0%   0%
EMA-L1 S3 N2     400 |   0%   0%     0%   0% |  94%     7    33  25%   0%   0%
EMA-L1 S3 N1     250 |   0%   0%     0% 100% | 100%     3    13   6%   0%   0%
EMA-L1 S3 N3     250 |   0%   0%     0%   0% | 100%     5    15   9%   0%   0%
EMA-L1 S4 N2     150 |   0% 100%     0%   0% | 100%     3     8   1%   0%   0%
EMA-L1 S4 N2     250 |   0%  73%     0%   0% | 100%     4    12   5%   0%   0%
EMA-L1 S4 N2     300 |   0%  47%     0%   0% | 100%     4    14   6%   0%   0%
EMA-L1 S4 N2     450 |   0%   0%     0%   0% |  97%     7    26  22%   0%   0%
EMA-MAX S3 N2    150 |   0%   0%     0%   0% | 100%     3    12   4%   0%   0%
EMA-MAX S3 N2    250 |   0%   0%     0%   0% |  97%     4    16  10%   0%   0%
JERK-L1 N2        60 |   0%   0%    77% 100% |  99%     2    12   6%   0%   0%
JERK-L1 N2       120 |   0%   0%     0% 100% |  76%     2    26  22%   0%   0%
JERK-L1 N2       240 |   0%   0%     0% 100% |  29%     2    30  22%   0%   0%
MAG2 N2          150 |   0%   0%     0%   0% |  93%     6    25  21%   0%   0%
MAG2 N2          300 |   0%   0%     0%   0% |  82%     7    32  27%   0%   0%
MAG2 N2          600 |   0%   0%     0%   0% |  64%     8    24  23%   0%   0%
```
Columns: rest/tilt/tremor/bump = share of streams with at least one trigger (false triggers); detect = first trigger within onset .. onset+duration+20; latMed/latP90 = trigger sample minus motion onset, in samples; `>15` = share of detections later than 15 samples (the onset is then cut off the window start, P = 15); `pre` = trigger before the onset; `twice` = a second trigger after the first one (release at t+135).

Margin of the recommended statistic (synthetic, UNVERIFIED; mg, peak over each scenario, seeds 1000..1099, 100 streams): rest max 16; tremor max 122; tilt max 216; bump (single sample) 598..612 but removed by N = 2; weakest gesture peaks 220 (swipe_r), 270 (twist), 276 (swipe_l), 280 (raise), 284 (thrust), 308 (circle). So 250 mg sits between the largest tilt (216) and the weakest gestures (220..308): usable but **thin on both sides** in my synthetic world. On 1000 fresh seeds (5000..5999, not used to choose the threshold; printed by `make test`) the tilt maximum is 228 mg and the tremor maximum 132 mg, still below 250 mg, margin 22 mg. Tilt false triggers on those fresh seeds: S = 3 at 200 mg 54 / 1000, at 220 mg 2 / 1000, at 250 mg 0 / 1000; S = 4 at 250 mg 692 / 1000, at 300 mg 444 / 1000.

Re-arm after a release against tremor (1000 fresh tremor streams, S = 3, N = 2, quiet 30, release forced at sample 40, 460 samples to re-arm; synthetic, UNVERIFIED; peak tremor statistic 132 mg):

```
thr  100 mg (lo   50 mg): never re-armed  564 / 1000  (56%)
thr  150 mg (lo   76 mg): never re-armed   34 / 1000  (3%)
thr  175 mg (lo   88 mg): never re-armed    0 / 1000  (0%)
thr  200 mg (lo  100 mg): never re-armed    0 / 1000  (0%)
thr  225 mg (lo  114 mg): never re-armed    0 / 1000  (0%)
thr  250 mg (lo  126 mg): never re-armed    0 / 1000  (0%)
thr  300 mg (lo  150 mg): never re-armed    0 / 1000  (0%)
```

Per gesture at 250 mg (S = 3, N = 2, 60 streams each): swipe_r 98 %, all others 100 %; median latency 2 (thrust) .. 10 (circle) samples.

Spike self-checks (Python mirror = C): the recommended rule equals the code defaults in `trigger.h` and `trigger_ref.py`; the warm-up gate holds (alternating 1500-count jolts from sample 1 never fire before sample 33, the first armed sample plus N = 2); `thr = 0` never fires; two separated pulses fire twice (t = 103 and 303); every trigger index ≥ 15; `warm < 16` is raised to 16, `quiet < 16` to 16, shift clamped to 1..8; a full-scale swing fires at every threshold from 24566 mg to 65535 mg (clamped to 12284 counts) in both C and Python.

## 5. Fix round (S2-2R)

- F-01 → code defaults changed to S = 3, 250 mg (`TRIG_DEFAULT_SHIFT 3u`, `TRIG_DEFAULT_MG 250u`, `DEFAULT_CFG shift=3`, `DEFAULT_MG = 250`); choice and evidence table in section 3.1; `selfcheck` asserts that the header and mirror defaults equal the recommendation.
- F-02 → section 3.2 redone with tremor as the limiting signal; new re-arm table (never re-armed: 100 mg 56 %, 150 mg 3 %, 175 mg and up 0 %); recommended range 0 or 200..400 mg.
- F-03 → done by the main agent (AI_USAGE.md), not touched here; the new functions of this round (`rearm`, `fresh`, `header_defaults`) still need rows.
- F-04 → `evaluate.py` rows added (S2 N2 150/300, S3 N2 150/300, S4 N2 150/250), plus the re-arm and fresh-seed outputs and the margin seed range; every number in the proposal now comes from section 4; S = 3 versus 4 is decided on several criteria, not tilt alone.
- F-05 → thresholds clamp to 12284 counts (`threshold_mg >= 24567`), which still fires on a full-scale swing; 12285 could never fire; stated in decision 3 and 3.2, implemented in C and Python, tested in `compare` (5 swing streams) and `selfcheck`.
- F-06 → decision 7 and 3.3: overrun with an open window calls `trigger_release()` (C1.6); resync is for other gaps; the idle-overrun resync is marked as a change to C1.6 (Q5); `trigger_init` raises `quiet` to 16.
- F-07 → example now "512 counts read 1024 mg".
- F-08 → base range corrected to −16384..16383 (S = 3); the S = 4 edge (−32768) stated.
- F-09 → `trigger_init` and `Trigger.__init__` clamp stat (unknown to EMA-L1), shift 1..8, quiet >= 16.
- F-10 → decision 1 and `trigger.h` state that firmware must hard-code S.
- F-11 → section 3.3 adds the rule "if feed() returns true and the capture cannot start a window, release at once", also in the `trigger_feed` doc comment.
- F-12 → table and margin text carry "synthetic, UNVERIFIED"; fresh-seed numbers added from the committed output.
- F-13 → doc comments completed on `pct` and `cfg_tuple`; new functions have them.
- F-14 → "D1, D2, ..." replaced by "decision N" in `trigger.h`.
- F-15 → `BOARD.md` is outside this ticket's write paths; main agent to update.

## 6. Open questions for Hadi

1. Tilt margin: the largest synthetic tilt (216 mg) is close to the 250 mg default. A real quick wrist turn will exceed it; is a false trigger on a wrist turn acceptable (it classifies as 0 but locks the buffer for a window)? If not, raise the default towards 300..400 mg and accept weaker gestures being missed (300 mg: 99 % detect, 12 % late; 400 mg: 94 % detect, 25 % late). Real recordings (WP2) must set this number.
2. Do real table bumps ring for several samples at ±4 g, 100 Hz? If yes N = 2 will not reject them; this does not matter for correctness (class 0) but costs window time.
3. Should `gesture_set_trigger` expose the statistic in "L1 mg" (as proposed) or a single-axis g-equivalent? L1 is up to 1.73 times a "total acceleration" for the same motion.
4. Is a 0.32 s warm-up after boot and after every overrun acceptable (LED feedback "ready" only after it)?
5. Should `capture_overruns` while idle also call `trigger_resync()` (proposed: yes, a gap invalidates the baseline and the ring)? This would CHANGE decided C1.6 ("OVRN while idle: count only"); without it the baseline keeps following the wand and later samples refill the ring, which is also safe with `quiet >= 16`.
6. The Python recording tool must label continuous streams, so the raw-stream mode (C2) needs to be usable for long recordings; is that already planned (WP2)?
7. Which hardware wake-up (IA1) threshold, if any, accompanies this rule? Not part of this proposal; it only needs to be lower than `threshold_mg` so it never masks a software trigger.
<!-- [END AI-GENERATED] -->
