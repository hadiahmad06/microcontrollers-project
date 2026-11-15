<!-- [AI-GENERATED: Claude Code] -->
# WP1-aR: review of capture.c and the WP1-aT suite

Reviewer: review-15 (Sonnet 5.5, medium). Working for: hadi. Reviewed at commit 0c51fb1 ("docs: AI_USAGE rows for WP1-a/WP1-aT").
Files: `firmware/src/capture.h`, `firmware/src/capture.c`, `firmware/test/capture/**`. Nothing was fixed.

## Verdict

**PASS WITH CHANGES.** `capture.c` conforms to C1 and to every main-agent ruling, including the new IDLE-push / disarm-keeps-ring ruling. I found no wrong behaviour (0 high). The suite is strong: 13 of 15 mutations are caught. The two it misses are exactly the new ruling: it is not pinned down by the suite (wildcards plus a guard that refuses to build the distinguishing scripts). The capture API also lacks what the trigger glue needs to tell an honoured trigger from an ignored one. Both are cheap to fix.

Counts: high 0, medium 5, low 5.

## Findings

| ID | file:line | finding | evidence | severity |
|----|-----------|---------|----------|----------|
| R-1 | `oracle.py:17-23, 143-145, 147-172, 196-201`; `test_capture.c:208` | The IDLE-push / disarm-keeps-ring ruling is not tested. The oracle still carries the pre-ruling "unknown ring" mechanism (`amb`): after an IDLE push or a disarm it reports the ring count as `*` and raises `ScriptError` for any script whose honour/early decision would depend on it. The random generator never emits an idle push or a mid-episode disarm. | Mutations m4 (disarm empties the ring) and m5 (IDLE push does not enter the ring) both SURVIVE (table below). Wildcard list in section 3. | medium |
| R-2 | `capture.h:60`, `capture.c:79` | `capture_push` returns `void`: the glue cannot tell an honoured trigger from an early or ignored one. C1b 3.3 / F-11 needs exactly that ("trigger_feed returned true and the capture cannot start a window: `trigger_release()` at once"). A workaround exists with the current API (state before == ARMED and state after == CAPTURING), but it is easy to get wrong, and `early_triggers` is only usable as a delta of a 6-byte struct copy. | Section 4. | medium |
| R-3 | `capture.h:50, 67`, `capture.c:71, 101` | `capture_disarm` and `capture_overrun` return `void`. When they drop an open window the trigger module is LOCKED and only `trigger_release()` unlocks it (C1.6, C1b 3.3). The glue must read `capture_state()` before the call to know that. Forgetting it leaves the wand deaf (LOCKED waits for a release that never comes). | C1b 3.3: "LOCKED: nothing happens until the capture code calls trigger_release() (buffer released, or window dropped for an overrun)". | medium |
| R-4 | `AI_USAGE.md` (rows 391-401), `capture.c:126` | `capture_buffer` has no row in AI_USAGE.md (every other capture.c function has one). Same for `standin/capture.c:108`. | `grep -n capture_buffer AI_USAGE.md` returns nothing. | medium (course rule 7) |
| R-5 | `oracle.py:40,52,99,111,147,204,213,231,237,274,282,321`; `run_tests.py:20,30,47,57` | Python doc comments are one-liners. They state the purpose and mostly the return value, but not each argument in a structured form (e.g. `ev(op)`, `episode(k)`, `compare(label, got, exp, fails)`, `check(label, cmd, seed, nep, timeout)`). The C test functions do have `@param`/`@return`. AGENTS.md 7 asks for purpose, each argument and return value. | AST scan: every function has a docstring, none lists its arguments. | medium (course rule 7) |
| R-6 | `capture.h:12-14, 25-27` | The header does not state the two decisive facts of the ruling: the ring is fed in every state including IDLE, and `arm`/`disarm`/`release` leave it alone. They are only in the `capture.c` file comment. The `CAPTURE_IDLE` doc says only "triggers ignored". | read | low |
| R-7 | `capture.c:41` | `(uint8_t)((s_head - s_count) & RING_MASK)` ANDs a negative `int` (both operands promote to 16-bit `int` on AVR/XC16). Correct on two's complement targets and passes sim16, but depends on negative-int bitwise behaviour. `(s_head + CAPTURE_RING - s_count) & RING_MASK` has no negative intermediate. | sim16 PASS; reading | low |
| R-8 | `capture.h:85` | `capture_buffer()` returns a writable, never-NULL pointer that is only meaningful in READY. `gesture_learn` (C1.12) cannot tell from the pointer whether the window is locked. Suggest a const row pointer, or NULL unless READY. | read | low |
| R-9 | `capture.c` (whole), C1.6 | C1.6 says "re-arm after a quiet period". capture.c has none: after a dropped window it goes straight to ARMED with an empty ring. Correct only because the trigger module's REARM (quiet >= 16, `trigger_init` raises `quiet` to 16) supplies the refractory time. The dependency is not written in `capture.h`. | C1b 3.3 | low |
| R-10 | `test_capture.c`, `run_tests.py` | Coverage limits: `uint16_t` counter wrap (65535) is never reached; sim16 runs only 40 episodes (29 134 events); NULL arguments (documented as not allowed) are untested (acceptable). | read | low |

## 1. Conformance (C1 and rulings), line by line

Checked against `capture.c` and by the suite (68 directed scripts, 1500 host episodes, all lines equal the oracle).

| Rule | Where | Result |
|------|-------|--------|
| C1.2 / C1.8 layout `int16_t buf[150][3]`, exactly 150, never padded | `capture.c:15, 92-97` | OK. Window = 15 pre + t + 134 (s_fill starts at 16, READY at 150). Checksum and full dumps in the oracle (m9, m15 caught). |
| C1.5 P = 15, ring 16 x 6 B | `capture.h` CAPTURE_*, `capture.c:16` | OK |
| Trigger honoured only in ARMED | `capture.c:82` | OK (trig_in_capturing, trig_in_ready, trig_in_idle) |
| Honoured only if >= 15 earlier samples since init / ring reset; the 16th pushed sample is the earliest; earlier ones count early_triggers | `capture.c:83-88` (push first, then `s_count >= 16`) | OK. early_15th, honoured_16th, pre_15..48; m6 caught |
| Overrun empties the ring in every state; READY keeps its buffer | `capture.c:101-111` | OK (ovr_ready*, m1, m7 caught) |
| Overrun in CAPTURING: drop window, ARMED, overruns++ | `capture.c:105-108` | OK |
| release only from READY, returns bool | `capture.c:113-120` | OK |
| arm only from IDLE | `capture.c:62-67` | OK (arm_noop, m10 caught) |
| disarm from any state except READY, no overrun counted | `capture.c:71-77` | OK; disarm in IDLE is a no-op. m12, m13 caught |
| `windows` counts transitions to READY | `capture.c:97` | OK (m2 caught) |
| IDLE pushes enter the ring; disarm does not empty it | `capture.c:81` (ring_push unconditional), `capture.c:71-77` | OK in the code. NOT pinned by the suite (R-1) |
| C1.7 in READY the ring keeps draining, triggers ignored | `capture.c:81-99` | OK |
| `init` zeroes stats, ring, state | `capture.c:50-58` | OK |

## 2. 16-bit int and AVR

- `RING_MASK` is `(uint8_t)15u`; `(s_head + 1u) & RING_MASK` is cast back to `uint8_t`. All index variables are `uint8_t`. `s_fill` reaches at most 150 (< 256) and `s_buf[s_fill]` is written only while `s_fill < 150` (the READY transition at 150 stops further writes); `s_count <= 16`.
- `window_start` copies `s_count` (= 16 by the guard at line 83) rows, then `s_fill = 16`: no overflow of `s_buf`.
- `capture_state_t` is int-sized on AVR (no -fshort-enums) and on XC16; nothing depends on the size. The `capture_stats` struct copy is a plain 6-byte copy.
- Built with `-std=c99 -Wall -Wextra -Wconversion -Werror -pedantic` on host and `avr-gcc -mmcu=atmega2560 ... -Werror`: no warnings. sim16 (16-bit int) matches the oracle on all 38 463 lines. Only R-7 (negative int AND).
- No float/double, no malloc, no delay in capture.c/capture.h (grep clean).

Commands and output:

```
$ cd firmware/test/capture && make clean && make test
PASS host: 68 directed scripts + 1500 random episodes, 433000 events, 477753 lines match the oracle
PASS sim16: 68 directed scripts + 40 random episodes, 29134 events, 38463 lines match the oracle
capture suite PASS
$ make test        (repo root)
sim16 harness PASS
ALL SUITES PASS (7 suites)
$ make test IMPL_DIR=standin      (harness proof, stand-in implementation)
capture suite PASS
```

## 3. Test quality

Independence: `oracle.py` is an independent Python model (own ring list, own honour test, own window assembly) driven through the same event executor as the C driver. Buffer content is verified by a checksum of all 450 values on every READY line, first/last three rows, and full 150-row dumps in selected places, with unique per-index samples. The directed scripts cover the ticket's mandatory list. Random episodes mix init/arm/overrun/release/trigger pushes. Good.

### Wildcards (what the `*` weakens)

`*` appears only in the **ring-count field** (field 4) of `E` lines, where the oracle considers the ring unknown: after an IDLE push or a `D`, until 16 pushes happened in a non-IDLE state (`oracle.py` `amb`, lines 17-23, 143-172, 196-201). Counts (seed 1):

| Scenario | E lines with `*` |
|----------|------------------|
| trig_in_idle | 20 |
| push_in_idle | 25 |
| disarm_idle | 18 |
| disarm_armed | 17 |
| disarm_capturing | 17 |
| directed total | 97 |
| random episodes ending in `D` (1 line each) | 8 of 40 (sim16); 369 of 1500 (host), total 466 on host with the directed ones |

State, overruns, windows, early_triggers, the buffer checksum and the buffer rows are still compared exactly on those lines. What is weakened: (a) `capture_ring_count()` after IDLE pushes and after `disarm` (kept vs emptied is not distinguished); (b) indirectly, the honour/early decision after IDLE pushes or a disarm, because `Model.push` raises `ScriptError` instead of building any script where the decision depends on the unknown ring (`oracle.py:158`). The existing scripts avoid it by always pushing >= 15 samples after re-arming (e.g. `disarm_armed`: `I A P20 D A P15 T P134 R`: the trigger at the 16th push is honoured even with an emptied ring). `test_capture.c:208` says the random generator never emits idle pushes or a mid-episode disarm.

Now that the main agent has ruled (IDLE pushes enter the ring; disarm keeps it), the unknown-ring mechanism can go: set the count exactly, delete `amb` and `ScriptError`, and add scripts that separate the two behaviours, for example:
- `I P20 A T P134` (honoured at the first armed sample: ring filled while IDLE),
- `I A P20 D P3 A T P134` (disarm keeps the ring; IDLE pushes enter it),
- `I A P20 T P5 D P20 A T P134` (disarm of an open window, then an immediate trigger),
- `I P5 A T P3 T` (5 idle pushes + 1: early, count 6 < 16),
- a random generator branch that emits `D` and idle `P`/`T`.

### Mutations (copies under the scratchpad, `make clean; make test IMPL_DIR=<copy>`)

| Mutation | Result | First failing scenario |
|----------|--------|------------------------|
| m1 ring not emptied on overrun in IDLE/ARMED/READY | caught | ovr_ready |
| m2 `windows` counted on trigger instead of READY | caught | early_15th |
| m3 release resets the ring | caught | early_15th |
| **m4 disarm empties the ring (new ruling)** | **SURVIVED** | none |
| **m5 IDLE push does not enter the ring (new ruling)** | **SURVIVED** | none |
| m6 honour threshold 15 ring entries instead of 16 | caught | early_15th |
| m7 overrun in READY drops the buffer | caught | ovr_ready |
| m8 overrun counted only when CAPTURING | caught | ovr_ready |
| m9 window of 149 samples | caught | early_15th |
| m10 arm allowed from READY | caught | arm_noop |
| m11 trigger in CAPTURING restarts the window | caught | trig_in_capturing |
| m12 disarm in READY unlocks the buffer | caught | disarm_ready |
| m13 disarm of an open window counts an overrun | caught | disarm_capturing (388 lines only) |
| m14 early trigger not counted | caught | early_15th |
| m15 window drops the trigger sample | caught | early_15th |

## 4. Integration risk (capture + trigger module + lis3dh_drain)

Intended glue per drained sample (C1b 3.3, C1.4):

```
t = trigger_feed(s);                 /* every drained sample, every capture state */
capture_push(s, t);
if (t && <capture did not start a window>) trigger_release();   /* F-11 */
if (capture_release()) trigger_release();                         /* buffer released */
on overrun: trigger_release() if a window was open (C1.6); idle-overrun resync is the Q5 change
```

When can `trigger_feed` return true without a window starting? (a) capture state IDLE (disarmed, or before arm); (b) ARMED but the ring has < 16 samples (after `capture_overrun`, if the trigger module was not resynced for that gap; the trigger's own first firing index is >= 32, so this happens only when resync is skipped). In READY / CAPTURING the trigger is LOCKED and cannot fire. In (a) and (b) the glue must call `trigger_release()` at once.

With the current API the glue can detect it only by `before = capture_state(); capture_push(s, t); started = (before == CAPTURE_ARMED && capture_state() == CAPTURE_CAPTURING);`. It works, but it is a convention hidden in the glue, and it is the most dangerous rule of the pair: a missed release deafens the wand (R-2, R-3).

**Proposal (additive, small):**

```c
/** @return true iff this call opened a window (trigger honoured, ARMED -> CAPTURING). */
bool capture_push(const int16_t s[3], bool trigger);
/** @return true iff an open window was dropped (CAPTURING -> ARMED); the glue then calls trigger_release(). */
bool capture_overrun(void);
/** @return true iff an open window was dropped (CAPTURING -> IDLE); the glue then calls trigger_release(). */
bool capture_disarm(void);
```
Glue: `started = capture_push(s, t); if (t && !started) trigger_release();`. Callers that ignore the return value stay valid. `capture_release()` already returns bool. The suite needs only the extra return value printed and compared (the oracle already knows when a window opens or is dropped). A cheaper alternative is to document the state-compare convention in `capture.h` and add a glue test, but I recommend the return values.

Other integration notes: the ring drains in all states (needed so t-15 exists in ARMED right after release), which holds in the code. `capture_overrun` empties the ring while the trigger module's baseline continues; the 16-sample refill plus the trigger's `quiet >= 16` make that consistent (R-9). The drain loop must call `capture_overrun()` before the first sample after a gap, since the ring is emptied at that call.

## 5. Course rules

- AI markers: all C files use the exact `// [AI-GENERATED: Claude Code]` ... `// [END AI-GENERATED]` form (capture.c, capture.h, test_capture.c, standin); Python and Makefile use `#` forms. OK.
- C doc comments (purpose, args, return): `capture.h` documents every public function; the static helpers `ring_push` and `window_start` have doc comments (no `@param`/`@return` where there are no arguments or return). Test C functions have `@param`/`@return`. Python: R-5.
- Register writes: none in this module.
- Fixed-width types everywhere; no float/double/malloc/delay. One `.c`/`.h` pair; C99 with -pedantic.
- AI_USAGE.md: rows present for all functions of capture.c except `capture_buffer` (R-4), all `test_capture.c` functions, all `oracle.py` functions/classes/methods and all `run_tests.py` functions; the stand-in also lacks `capture_buffer` (R-4).

## 6. Suggested follow-ups (not done, by instruction)

1. Update `oracle.py` for the final ring ruling (remove `amb` / `ScriptError`), add the scripts and the random branch from section 3, and re-run m4 and m5 (they must then be caught).
2. Decide R-2/R-3 (return values) before the glue ticket; change `capture.h`, `capture.c` and the suite output together.
3. Add the `capture_buffer` row to AI_USAGE.md; expand the Python doc comments with argument lists.
<!-- [END AI-GENERATED] -->
