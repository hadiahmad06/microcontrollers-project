# Sprint board for hadi's agent team

> The main agent is the scrum master (AGENTS.md §6). Update this file every time a subagent
> is assigned work, reports back, or gets blocked. It has to make sense to a fresh session
> with no chat history.

## Environment
**Cloud session (2026-11-14, Linux, branch `claude/optimistic-meitner-67qdon`):** gcc/clang, python3 + numpy 2.5.3, make.
**No XC16 and no MDB simulator** (both are only on Hadi's Mac; the proxy blocks microchip.com). Simulator and XC16 checks are queued for the Mac.
Git name for agent commits: `Hadi Ahmad (Claude)` (Hadi, 2026-11-14). Agents may push, open PRs and merge after review (Hadi, 2026-11-14).

**Hadi's Mac (verified 2026-11-14):**
- XC16 v2.10: `/Applications/microchip/xc16/v2.10/bin/xc16-gcc -mcpu=24FJ64GA002`. Compiles and links. ✅
- MPLAB X v6.35 simulator: `/Applications/microchip/mplabx/v6.35/mplab_platform/bin/mdb.sh`. Headless use not yet proven (S1-4).
- Host tools: Apple clang 16, python 3.12 + numpy 1.26, make. arm64 macOS.
- Git: branch `main` on GitHub. Superseded: agents may now push, open PRs and merge after review (Hadi's decision, 2026-11-14).

## Working rules (Hadi's decisions, 2026-11-14)
- New subagents run in **git worktrees** (`isolation: worktree`), each committing on its own branch.
- The main agent merges a branch only after the ticket is done: tests it ran itself pass, and review findings are resolved.
- Work that predates worktree mode, and has not been reviewed yet, stays uncommitted in the main checkout until its review passes. Then the main agent commits it on `master`.

## Roster
_Agent IDs only work inside the session that started them. After a handoff, start new subagents and give them the ticket and its files._

| Name | Model | Role | Ticket | Status |
|------|-------|------|--------|--------|
| research-sensor | Sonnet 5.5 / medium | researcher | S1-1 | done |
| review-3 | Sonnet 5.5 / medium (worktree) | fact-checker | S1-1R | done |
| spike-features | Sonnet 5.5 / medium | implementer | S1-2 | done |
| test-features (S1) | Sonnet 5.5 / medium (worktree) | tester | S1-2T | done |
| review-1 | Sonnet 5.5 / medium (worktree) | reviewer | S1-2R | done |
| research-quant | Sonnet 5.5 / medium | researcher | S1-3 | done |
| review-2 | Sonnet 5.5 / medium (worktree) | fact-checker | S1-3R | done |
| spike-sim | Sonnet 5.5 / medium | implementer | S1-4 | done |
| review-4 | Sonnet 5.5 / medium (worktree) | reviewer / tester | S1-4R | done |
| research-display | Sonnet 5.5 / medium | researcher | S1-5 | done |
| review-5 | Sonnet 5.5 / medium (worktree) | fact-checker | S1-5R | done |
| sheet-writer | Sonnet 5.5 / medium (worktree) | integrator | S1-8 | done |
| impl-guard, qa-guard | - | - | S1-6 | retired (scrapped) |
| review-6 | Sonnet 5.5 / medium (worktree) | fact-checker | S2-0R | done |
| research-uart (2 instances) | Sonnet 5.5 / medium (worktree) | researcher / spike | S2-1, S2-1F | done |
| review-7 | Sonnet 5.5 / medium (worktree) | reviewer | S2-1R | done |
| research-trigger (2 instances) | Sonnet 5.5 / medium (worktree) | researcher / spike | S2-2, S2-2F | done |
| review-12 | Sonnet 5.5 / medium (worktree) | reviewer | S2-2R | done |
| impl-features | Sonnet 5.5 / medium (worktree) | implementer | 3.3 | done |
| test-features | Sonnet 5.5 / medium (worktree) | tester | 3.3T | done |
| review-8 | Sonnet 5.5 / medium (worktree) | reviewer | 3.3R | done |
| impl-mlp | Sonnet 5.5 / medium (worktree) | implementer | 3.4 | done |
| test-mlp | Sonnet 5.5 / medium (worktree) | tester | 3.4T | done |
| review-9 | Sonnet 5.5 / medium (worktree) | reviewer | 3.4R | done |
| impl-classify | Sonnet 5.5 / medium (worktree) | implementer | 3.5, 3.6 | done |
| test-classify (2 instances) | Sonnet 5.5 / medium (worktree) | tester | 3.5T/3.6T, SW-2b | SW-2b in progress |
| review-10 | Sonnet 5.5 / medium (worktree) | reviewer | 3.5R | done |
| fix-classify | Sonnet 5.5 / medium (worktree) | fix round | 3.5F | done |
| impl-wp2 (2 instances) | Sonnet 5.5 / medium (worktree) | implementer | W2-1, W2-1F | done |
| review-11 | Sonnet 5.5 / medium (worktree) | reviewer | W2-1R | done |
| impl-e2e (2 instances) | Sonnet 5.5 / medium (worktree) | implementer | 3.8, 3.8F | 3.8F in progress (resumed after API limit) |
| review-13 | Sonnet 5.5 / medium (worktree) | reviewer | 3.8R | done |
| impl-capture | Sonnet 5.5 / medium (worktree) | implementer | WP1-a | done |
| test-capture (2 instances) | Sonnet 5.5 / medium (worktree) | tester | WP1-aT, WP1-aT2 | done |
| review-15 | Sonnet 5.5 / medium (worktree) | reviewer | WP1-aR | done |
| fix-capture | Sonnet 5.5 / medium (worktree) | fix round | WP1-aF | done |
| impl-lis3dh | Sonnet 5.5 / medium (worktree) | implementer | WP1-b | done |
| test-lis3dh (3 instances) | Sonnet 5.5 / medium (worktree) | tester | WP1-bT, -bT2, -bT3 | WP1-bT3 in progress |
| fix-lis3dh (2 instances) | Sonnet 5.5 / medium (worktree) | fix round | WP1-bF, -bF2 | WP1-bF2 in progress |
| review-18 | Sonnet 5.5 / medium (worktree) | reviewer | WP1-bR | done |
| impl-display | Sonnet 5.5 / medium (worktree) | implementer | WP4-a | done |
| test-display | Sonnet 5.5 / medium (worktree) | tester | WP4-aT | done |
| review-14 | Sonnet 5.5 / medium (worktree) | reviewer | WP4-aR | done |
| fix-display | Sonnet 5.5 / medium (worktree) | fix round | WP4-aF | done |
| impl-train (2 instances) | Sonnet 5.5 / medium (worktree) | implementer | W2-2, W2-2F | done |
| review-16 | Sonnet 5.5 / medium (worktree) | reviewer | W2-2R | done |
| sweep-1 | Sonnet 5.5 / medium (worktree) | fix round | SW-1 | done |
| fix-knn | Sonnet 5.5 / medium (worktree) | fix round | SW-2a | done (branch, waits for SW-2b) |
| review-17 | Sonnet 5.5 / medium (worktree) | pre-merge reviewer | PR-2R | done: MERGE AFTER FIXES |

## Sprint 0: Framework (carried over)
| ID | Title | Assignee | Status | Notes |
|----|-------|----------|--------|-------|
| S0-1 | Add shared git remote | Hadi | done | Don't interact with the remote yet |
| S0-4 | Fill in the unknowns (pins, I2C bus and address, bulb method, deadlines) | Hadi | backlog | XC16 version is now known: v2.10. The S1 proposals will narrow the rest down to concrete questions |

## Sprint 1: Contract proposals and verification setup (started 2026-11-14)
**Goal:** every contract C1–C7 is written up so Hadi can decide it quickly (options plus a
recommendation), the PIC24 simulator can run tests headlessly, and the write guard is in place.
**Out of scope:** product code. Spikes are throwaway prototypes in `docs/agent/hadi/spikes/`.

| ID | Title | Assignee | Status | Writes to | Follow-up tickets |
|----|-------|----------|--------|-----------|-------------------|
| S1-1 | Proposals C1 (capture buffer) and C6a (sensor and I/O pins) | research-sensor | **done**, merged `9b4a6a5`. Adds the drain-loop rule, a capture-path RAM total of 1188 B, the required config-word list, and the WS2812 pin conflict flagged for Hadi | `proposals/C1_*.md`, `proposals/C6a_*.md` | S1-1R: fact-check against the datasheets |
| S1-2 | Spike: bit-exact integer features in Python and C, plus the C3 proposal | spike-features | **done**, merged `9c8a414`. Main agent reran: all 6 energy variants PASS, QA OVERALL PASS, XC16 clean. Recommends isqrt energy; the default stays at shift 11 until Hadi decides (D4) | `spikes/features/**`, `proposals/C3_*.md` | S1-2T: independent tests written from the spec · S1-2R: review |
| S1-3 | Proposals C4 (model header and quantization) and C5 (classifier output) | research-quant | **done**: all 15 review findings fixed and merged. Main agent reran: ALL PASS, with float-vs-int agreement at 99.3% when training on x8 directly. Ready for Hadi's decisions | `proposals/C4_*.md`, `proposals/C5_*.md`, `spikes/quant/**` | S1-3R: review |
| S1-4 | Spike: run the MDB simulator headlessly, read results back, count cycles | spike-sim | **done**: checks breakpoint order (exit code 7), uses a temp dir per run, `make demo` asserts 1130 cycles, `make selftest` passes. Main agent did NOT rerun the selftest | `spikes/sim/**` | S1-4R: reproduce from the README |
| S1-5 | Proposals C6b (display and bulb) and C7 (resource budget) | research-display | **done**, merged `d822a43`. RAM is 3,660 B (44.7%). Flash is 21.9 KB (33.5%) without persistence, or 28.0 KB with 4-block persistence | `proposals/C6b_*.md`, `proposals/C7_*.md` | S1-5R: fact-check |
| S1-6 | ~~Write-guard hook~~ | - | **scrapped** by Hadi (git history is the accountability). A no-op stub stays in local `.claude/hooks/` (git-excluded) until this session ends; delete it afterwards | `.claude/**`, `.gitignore` | S1-6T: test suite · S1-6R: review |
| S1-8 | Compile one decision sheet from all 7 proposals and 5 reviews | sheet-writer | **done**: `DECISION_SHEET.md`; checked by the main agent and by review-6 (S2-0R: accurate with errata) | `DECISION_SHEET.md` | S2-0R |
| S1-7 | Hadi decides C1–C7, and the decisions go into `docs/agent/CONTRACTS.md` | main + Hadi | **done** 2026-11-14 (Part A + B1-B11 accepted; see Sprint 2) | top-level docs | – |

Paths are relative to `docs/agent/hadi/` unless they start with `.`.
**AI_USAGE.md:** subagents don't write to it, to avoid several of them writing at once.
The main agent adds rows from their reports.

## Sprint 2: verified decision round, C2, first product code (started 2026-11-14, cloud session)
**Goal:** the decision sheet is verified, Hadi's decisions are in `docs/agent/CONTRACTS.md`, C2 is proposed, and
host-tested product code exists for every module the locked contracts allow (3.3-3.6, 3.8, WP2 references).
**Out of scope:** anything that needs XC16, the simulator or hardware (queued for Hadi's Mac / bench).
**Merge flow:** subagent worktree branch → main agent reruns tests, reads diff → merge into session branch → push.
At the sprint boundary: PR session branch → `main`, reviewed by a Sonnet reviewer that wrote none of it, then merged.

| ID | Title | Assignee | Status | Writes to | Follow-up tickets |
|----|-------|----------|--------|-----------|-------------------|
| S2-0a | Rerun all host test suites | main | **done**: all PASS | – | – |
| S2-0b | Rerun `make selftest` (spikes/sim) | Hadi (Mac) | **blocked**: needs XC16 + MDB | – | – |
| S2-0c | Main agent checks DECISION_SHEET | main | **done**: accurate; C3 4-MIPS erratum | – | S2-0R |
| S2-0R | Independent fact-check of DECISION_SHEET | review-6 | **done**, merged: ACCURATE WITH ERRATA (0 high, 7 medium); none changes Hadi's answers | `reviews/S2-0R.md` | – |
| S1-7 | Hadi decides C1-C7 | main + Hadi | **done**: Part A + B1-B11 accepted; `docs/agent/CONTRACTS.md` written; PLAN adopted; repo layout decided | top-level docs | – |
| S2-1 | C2 UART proposal + framing spike | research-uart | **done**, merged; `make test` ALL PASS (main reran) | `proposals/C2_*.md`, `spikes/uart/**` | S2-1R, S2-1F |
| S2-1R | Review C2 | review-7 | **done**, merged: APPROVE WITH NITS (0 high, 10 medium) | `reviews/S2-1R.md` | – |
| S2-1F | C2 fix round (main-agent rulings on F-02..F-10) | research-uart (2nd instance) | **done**, merged; ALL PASS (main reran). **Waiting for Hadi (open_questions Q1)** | same as S2-1 | – |
| S2-2 | Trigger rule proposal C1b + spike | research-trigger | **done**, merged; ALL PASS (main reran) | `proposals/C1b_trigger.md`, `spikes/trigger/**` | S2-2R, S2-2F |
| S2-2R | Review trigger proposal | review-12 | **done**, merged: REQUEST CHANGES (code defaults S4/300 mg ≠ proposal S3/250 mg; tremor re-arm; unsourced numbers; saturation) | `reviews/S2-2R.md` | – |
| S2-2F | Trigger fix round | research-trigger (2nd instance) | **done**, merged; ALL PASS (main reran); defaults = proposal (S3, 250 mg). **Waiting for Hadi (Q2, Q3)** | same as S2-2 | – |
| S2-3 | Repo skeleton + sim16 16-bit-int harness (avr-gcc + simavr) | main | **done**; `common.mk` now searches IMPL_DIR first (3.3R L1) | `Makefile`, `firmware/test/{common.mk,sim16}` | – |
| 3.3 / 3.3T | `features.c` + `tools/features_ref.py` / features suite | impl-features / test-features | **done**, merged | `firmware/src/features.*`, `tools/features_ref.py`, `firmware/test/features/**` | – |
| 3.3R | Review 3.3 + 3.3T | review-8 | **done**, merged: APPROVE WITH NITS (0 high, 0 medium, 5 low); 9/9 logic mutations caught | `reviews/3.3R.md` | low items in backlog |
| 3.4 / 3.4T | `mlp.c` / mlp suite | impl-mlp / test-mlp | **done**, merged; main fixed `-I`→`-iquote` in run_tests.py | `firmware/src/mlp.*`, `firmware/test/mlp/**` | – |
| 3.4R | Review 3.4 + 3.4T | review-9 | **done**, merged: APPROVE WITH NITS; F1 (marker form) fixed by main; F4 (GM_FEATURE_VERSION == FEATURES_VERSION assert) goes to 3.7 | `reviews/3.4R.md` | – |
| 3.5/3.6 + T | `classify.c`, `knn.c`, `gesture_ids.h` / classify suite | impl-classify / test-classify | **done**, merged; knn RAM 1216 B (= C7 budget) | `firmware/src/{knn,classify,gesture_ids}.*`, `firmware/test/classify/**` | – |
| 3.5R | Review classify/knn | review-10 | **done**, merged: APPROVE WITH NITS (untested -2 import path, missing docstrings) | `reviews/3.5R.md` | 3.5F |
| 3.5F | classify/knn fix round (docs + -2 tests) | fix-classify | **done**, merged (96 metadata import cases; firmware/src object code byte-identical). F4 (knn_import ignores non-zero unused slots / NULL) → backlog | `firmware/test/classify/**`, doc comments | – |
| W2-1 | `tools/infer_ref.py` + `tools/export_model.py` | impl-wp2 | **done**, merged; selftest PASS | `tools/**` | W2-1R, W2-1F |
| W2-1R | Review tools | review-11 | **done**, merged: APPROVE WITH NITS; **0 mismatches / 3000** C mlp vs infer_ref | `reviews/W2-1R.md` | – |
| W2-1F | Tools fix round | impl-wp2 (2nd instance) | **done**, merged; selftest PASS also under -O; e2e PASS. Raised Q4, Q5 (contract wording) | `tools/**` | – |
| 3.8 | End-to-end bit-exact harness (C vs tools, host + sim16) | impl-e2e | **done**, merged: **gate G2 met** (every stage, 3 exporter models, host + sim16); all 5 suites PASS (main reran) | `firmware/test/e2e/**` | 3.8R |
| 3.8R | Review e2e harness | review-13 | **done**, merged: APPROVE WITH NITS (4 medium: boundary coverage incidental, skewed models, few sim16 windows) | `reviews/3.8R.md` | 3.8F |
| W2-2 | `tools/train.py` + `tools/synth_dataset.py` | impl-train | **done**, merged; main reran selftest + full run (seed 7): integer path 100 % on synthetic, header compiles for sim16 | `tools/{train,synth_dataset}.py` | W2-2R |
| W2-2R | Review training pipeline | review-16 | **done**, merged: 0 high, 5 medium (val set both selects and reports; class-0 separable by orientation). Raised Q6 | `reviews/W2-2R.md` | W2-2F |
| W2-2F | 3-way split, auto grouping, synth fixes | impl-train (2nd instance) | **done**, merged; `--fallback-set val` default pending Q6 | `tools/{train,synth_dataset}.py` | – |
| SW-1 | Low findings of 3.3R/3.4R | sweep-1 | **done**, merged (found + fixed a test-generator corner bug) | tests, comments | – |
| PR-2R2 | Delta pre-merge review (22 commits since PR-2R) | review-19 | **done**: MERGE (0 blockers, 0 majors; minors d-1, d-3, d-4, d-5 fixed) | `reviews/PR-2R2.md` | merge if MERGE |
| PR-2 | Sprint-2 PR to `main` (hadiahmad06/microcontrollers-project#1) + pre-merge review | main + review-17 | PR open. PR-2R: MERGE AFTER FIXES (2 majors: 3.8F not landed; code-vs-CONTRACTS wording differences not disclosed → now disclosed in the PR body; minors fixed) | `reviews/PR-2R.md` | merge when 3.8F, WP1-bF2/bT3, SW-2 land and all suites PASS |
| WP1-bR | Review lis3dh driver (missing review ticket found by main) | review-18 | **done**, merged: APPROVE WITH NITS (0 high, 4 medium); all 256 FIFO_SRC values bounded | `reviews/WP1-bR.md` | WP1-bF2, WP1-bT3 |
| WP1-bF2 | lis3dh: address reset on failure, pre-init guards, power-down on failure, comments; main-agent ruling: only sign == -1 negates (WP1-bT3) | fix-lis3dh (2nd instance) | **done**, merged; main fixed sign check to == -1 (ruling) | `firmware/src/lis3dh.*` | – |
| WP1-bT3 | lis3dh tests: stop at first fault, guards, NULL tables, R5 both ways | test-lis3dh (3rd instance) | **done**, merged; lis3dh suite PASS on the real driver | `firmware/test/lis3dh/**` | – |
| SW-2a | knn_import: reject non-zero unused slots, NULL buffers (ruling, 3.5R F4) | fix-knn | **done**, merged | `firmware/src/knn.*` | SW-2b |
| SW-2b | classify suite: F4 ruling, -128 inputs, conf edges (3.5R F4-F6) | test-classify (2nd instance) | **done**, merged; classify suite PASS on host + sim16 | `firmware/test/classify/**` | – |
| 3.8F | e2e directed boundary coverage | impl-e2e (2nd instance) | **done**, merged: every boundary hit on purpose on host + sim16; 4 models incl. a tie model; 5/5 mutations caught | `firmware/test/e2e/**` | – |
| 3.7 | `gesture.c` public API (8 functions); design note `proposals/API_glue.md` | – | backlog: needs WP1 driver (`lis3dh.c`, capture state machine), the trigger decision (Q2) and C2 (Q1) for `gesture_stream_raw` | `firmware/src/gesture.*` | – |
| WP1-a | `capture.c`: ring, window cut, overrun policy, buffer lock | impl-capture | **done**, merged; ruling: IDLE pushes enter the ring, disarm keeps it | `firmware/src/capture.*` | WP1-aR |
| WP1-aT | Capture suite (host + sim16) | test-capture | **done**, merged: real capture.c matches 477,753 host + 38,463 sim16 lines | `firmware/test/capture/**` | – |
| WP1-aR | Review capture | review-15 | **done**, merged: 0 high, 5 medium (ring ruling not pinned; glue needs bool returns R-2/R-3, adopted as rulings) | `reviews/WP1-aR.md` | WP1-aF, WP1-aT2 |
| WP1-aF | capture: bool returns (R-2, R-3) + docs | fix-capture | **done**, merged | `firmware/src/capture.*` | – |
| WP1-aT2 | capture suite: pin ring ruling, assert returns | test-capture (2nd instance) | **done**, merged: 603k host + 208k sim16 lines; m4/m5 now caught | `firmware/test/capture/**` | – |
| WP4-a | `display.c` + `icons.c` (no asm) | impl-display | **done**, merged; main applied ruling: out-of-range `display_get` leaves rgb unchanged (briefs had disagreed) | `firmware/src/{display,icons}.*` | WP4-aR |
| WP4-aT | Display suite (host + sim16) | test-display | **done**, merged; display suite PASS (6 suites total) | `firmware/test/display/**` | – |
| WP4-aR | Review display | review-14 | **done**, merged: 0 high, 2 medium (icon identity untested, doc comments) | `reviews/WP4-aR.md` | WP4-aF |
| WP4-aF | display docs + icon identity snapshot test | fix-display | **done**, merged (objects byte-identical) | `firmware/src/{display,icons}.*` (docs), `firmware/test/display/**` | – |
| WP1-b | `lis3dh.c` over an I2C HAL | impl-lis3dh | **done**, merged; suite PASS | `firmware/src/{lis3dh,lis3dh_hal,board_axes}.*` | WP1-bF, review |
| WP1-bT | Fake LIS3DH + driver suite | test-lis3dh | **done**, merged; found a stall: full FIFO reported as FSS=0+OVRN | `firmware/test/lis3dh/**` | – |
| WP1-bF | Driver: FSS=0+OVRN+!EMPTY means 32 unread (ruling R1) | fix-lis3dh | **done**, merged; stall gone | `firmware/src/lis3dh.c` | – |
| WP1-bT2 | Assert rulings R1-R5 | test-lis3dh (2nd instance) | **done**, merged; real driver 0 failures | `firmware/test/lis3dh/**` | WP1-bR (backlog) |
| WP4-b | WS2812 asm bit-bang + chunked masking | – | blocked: needs XC16 (Mac) and a scope | – | – |

**Lessons (this sprint):** keep a subagent's worktree until its fix round is done (removing it made research-uart unresumable).
Two container restarts (2026-11-14) killed pending question dialogs and made running agents unresumable: decisions now also go to `open_questions.md`; fix rounds start fresh instances that work from the review file.
simavr splits UART lines longer than 255 characters: test drivers print short lines.

## Backlog (later sprints)
Each implementation ticket gets its own test (T) and review (R) ticket, assigned to
different subagents from the implementer.

| ID | Title | Type | Depends on |
|----|-------|------|------------|
| C2 | UART raw-stream protocol proposal | research | C1 |
| 3.3 / 3.3T / 3.3R | `features.c` (promoted from the S1-2 spike) | impl / test / review | C1, C3 |
| 3.4 / 3.4T / 3.4R | `mlp.c` | impl / test / review | C4 |
| 3.5 / 3.5T / 3.5R | Reject logic | impl / test / review | 3.4, C5 |
| 3.6 / 3.6T / 3.6R | `knn.c` | impl / test / review | 3.3, C7 |
| 3.7 / 3.7R | `gesture.c` API | impl / review | 3.3–3.6 |
| 3.8 / 3.8R | Bit-exact harness (host and simulator) | impl / review | 3.3, 3.4, S1-4 |
| 3.9 | On-target verification on real hardware | Hadi + main | 3.8 |
| 3.10 | Cycles / RAM / flash measurement | Hadi | 3.9 |

## HANDOFF NOTES FOR THE NEXT SESSION (kept current by the main agent; newest state, 2026-11-15)
1. **Where things are:** all work is on `claude/optimistic-meitner-67qdon`; PR hadiahmad06/microcontrollers-project#1 → `main`
   (merge only after the pre-merge review PR-2R says MERGE). `make test` at the repo root runs 8 suites (host + sim16).
2. **Hadi's open decisions:** `docs/agent/hadi/open_questions.md` Q1 (C2), Q2 (trigger C1b), Q3 (C1.6 conflict), Q4/Q5
   (C5.2 / C4.3 wording), Q6 (train/val/test split wording). Do not code `gesture.c`, the trigger module or the C2 TX
   pump into `firmware/src` before Q1/Q2 are answered; design is ready in `proposals/API_glue.md`.
3. **After Q1/Q2:** tickets T-trig (promote `spikes/trigger` → `firmware/src/trigger.*`), T-c2tx (C2 TX pump),
   3.7 (`gesture.c`), each with T and R tickets; then paste `drafts/C2_contract_section.md` into CONTRACTS.md (C2).
4. **Mac-only:** S2-0b `make selftest` (spikes/sim), gate G3 (XC16 build + MDB/on-target vectors), the WS2812 asm
   driver (WP4-b), the PIC24 HAL (I2C1/UART1/INT0/INT1/PPS/config words), measurements 3.10.
5. **Environment:** sim16 needs `apt-get install -y simavr gcc-avr avr-libc` in a fresh cloud container (not saved
   as a setup script; Hadi has not been asked yet because he signed off).
6. **Process lessons:** keep a subagent's worktree until its fix round is merged; a container restart or API limit
   kills running agents and pending question dialogs, so commit early, record decisions in open_questions.md, and
   resume agents with SendMessage when they are still resumable (else start a fresh instance from the review file).
   Firmware headers are on the `-iquote` path only (features.h vs glibc). simavr splits UART lines > 255 chars.

## Standup log
_(newest first: done · next · blocked)_
- 2026-11-15 (w): **Done:** 3.8F, WP1-bF2/bT3, SW-2a/b; all 8 suites PASS. **Next:** delta review PR-2R2, then merge PR #1. **Waiting for Hadi:** Q1-Q7.
- 2026-11-15 (v): Hadi signed off ("continue running, don't ask questions, leave notes in the chat"). The API spend limit stopped 3.8F mid-task; resumed after reset. PR #1 opened; pre-merge review running.
- 2026-11-15 (u): **Done:** all fix rounds except 3.8F; 8 suites PASS; e2e soak (3 extra seeds × 4 models) PASS; proxy RAM 2512 B vs C7 2500 B; glue design note for 3.7. **Next:** PR-2 (session branch → main) with a full-diff review. **Waiting for Hadi:** Q1-Q6.
- 2026-11-15 (t): **Done:** WP1-bF + bT2 (lis3dh stall fixed, rulings asserted), WP1-aR, WP4-aR, W2-2R; 8 suites PASS. **Next:** 5 fix rounds running (3.8F, W2-2F, WP4-aF, WP1-aF, WP1-aT2), then the sprint PR to `main`. **Waiting for Hadi:** Q1-Q6.
- 2026-11-15 (s): **Done:** WP1-a + T (merged), WP1-b + T (merged), W2-2 (merged); 7 suites PASS. **Next:** WP1-bF/WP1-bT2, 3.8F, reviews WP1-aR, WP4-aR, W2-2R running. **Waiting for Hadi:** Q1-Q5. **Then:** sprint-boundary PR to `main` with a full-diff review.
- 2026-11-14 (r): **Done:** S2-2F, W2-1F, 3.5F, 3.8R, WP4-a + T (6 suites PASS), WP1-a and WP1-b code. **Next:** WP1-aT, WP1-bT, 3.8F, W2-2, WP4-aR running. **Waiting for Hadi:** Q1-Q5 in open_questions.md. **Blocked:** G3, S2-0b (Mac).
- 2026-11-14 (q): **Done:** 3.3R, 3.4R, 3.5/3.6 (+T, R), W2-1 (+R), S2-2 (+R), 3.8 → **gate G2 met on host and sim16**; 5 suites PASS. Two container restarts survived (work was committed). **Next:** S2-2F, W2-1F, 3.5F, 3.8R running. **Waiting for Hadi:** Q1 (C2), then Q2 (trigger). **Blocked:** S2-0b, G3 (Mac/hardware).
- 2026-11-14 (p): **Done:** S1-7 (Hadi accepted everything; CONTRACTS.md, PLAN adopted, repo layout), S2-0R, S2-1 + S2-1R, sim16 harness, 3.3 + 3.3T (suite PASS on host and sim16, nothing skipped). **Next:** 3.3R, 3.4T, 3.5/3.6 (+T), W2-1, S2-1F all running. **Blocked:** S2-0b (Mac). C2 waits for its fix round, then Hadi.
- 2026-11-14 (o), **SPRINT 2 START (cloud session)**. **Done:** host suites rerun (all PASS), sheet checked by main agent, Hadi's push/PR/merge and git-name decisions recorded. **Next:** review-6 (S2-0R) and research-uart (S2-1) running; decision round S1-7 once S2-0R reports. **Blocked:** S2-0b `make selftest` needs Hadi's Mac (no XC16/MDB here).
- 2026-11-14 (n), **SPRINT 1 STOPPING POINT / HANDOFF**
  - **Done:** S1-1 to S1-5 and S1-8 are merged on main. S1-6 was scrapped.
  - **Next session:**
    1. Check DECISION_SHEET.md against the proposals. The sheet-writer flagged 8 inconsistencies, now in Part B: B1 pin wording, B2 trigger source, B3 nonneg flag, B7 staging size, B8–B10 have no recommendation, and B11 is API deltas. C3 also quotes ms at 4 MIPS rather than 16.
    2. Rerun `make selftest` in spikes/sim.
    3. Hadi works through the sheet (S1-7). Write the agreed contracts to `docs/agent/CONTRACTS.md`.
    4. Sprint 2: C2 proposal, then 3.3–3.8.
  - **Housekeeping:** about 14 stale `run_sim.*` dirs in `$TMPDIR`. Delete the no-op stub `.claude/hooks/guard_docs.py` once this session ends.
  - **Remote:** not used yet, on Hadi's instruction.
- 2026-11-14 (m): **Done:** S1-5 fix round merged. All 7 proposals are final on main. **Next:** S1-8 decision sheet (sheet-writer), S1-4 fix round (spike-sim). **Then:** the sprint stopping point; Hadi plans a handoff to a cloud session.
- 2026-11-14 (l): **Done:** S1-4R merged. **Next:** the S1-4 and S1-5 fix rounds are running in parallel. When both are merged, a Sonnet agent compiles the decision sheet (S1-7 prep). **Env note:** the zoxide banner from `~/.zshrc` appears in every shell output. It's harmless; setting `_ZO_DOCTOR=0` silences it.
- 2026-11-14 (k): **Done:** S1-5R merged with verdict REQUEST CHANGES. Its reconciliation table covers all 7 proposals. **Next:** the S1-5 fix round, and S1-4R (still running). Then the decision sheet.
- 2026-11-14 (j): **Done:** S1-1 fix round merged. S1-1, S1-2 and S1-3 are complete. **Next:** S1-4R and S1-5R; then the decision sheet (S1-7 prep).
- 2026-11-14 (i): **Done:** S1-2 fixes merged; S1-1R merged (APPROVE WITH NITS). **Next:** S1-1 fix round; S1-4R and S1-5R are still running. After that, the decision sheet. **Note:** review-3's worktree had also started from a stale commit; it fast-forwarded to `main` itself.
- 2026-11-14 (h): **Done:** S1-3 fix round merged (`154a01e`). The demo is now a self-guarding acceptance test: the wrong-sign fold scores 83% and fails the 97% threshold. **Next:** S1-1R, S1-4R, S1-5R and the S1-2 fix round.
- 2026-11-14 (g): **Done:** S1-3R merged, verdict REQUEST CHANGES; research-quant is now fixing in its worktree. **Issue:** review-5's worktree was created from a stale commit (`1150592`), so it was told to read the proposals from the main checkout. **Lesson:** check each worktree's base commit right after the agent starts.
- 2026-11-14 (f): **Done:** S1-6 scrapped on Hadi's decision. S1-1, S1-3 and S1-4 delivered and committed. S1-2T and S1-2R merged, and their worktrees removed. **Next:** S1-2 fix round, reviews S1-1R, S1-3R and S1-4R, and S1-5 delivery. Then a sprint review with Hadi (S1-7 decisions) and the handoff to a cloud session. **Blocked:** none.
- 2026-11-14 (e): **Done:** S1-3 delivered. It confirmed `ug.txt` was its file: a failed `cd` made `pdftotext` write to the project root. The file has been moved out. Added `.claude/worktrees/` to `.gitignore`. Fixed the PLAN 3.6 int16/int8 inconsistency that research-quant flagged. **Next:** review-2 is checking S1-3. **Lesson for future briefs:** tell agents to `cd` with quoted absolute paths and to check that the `cd` succeeded before writing output files.
- 2026-11-14 (d): **Done:** base commit `ea537f2` on master, so worktree mode is on. S1-2 implemented. Main agent's review: the code matches its spec. Open concern: the `>>11` energy scale may be too coarse for small motions. `ug.txt` is gone. **Next:** S1-2T and S1-2R are running in worktrees. Once qa-guard reports, fix the hook's worktree bypass: paths under `.claude/worktrees/<name>/docs/...` are not checked. **Note:** the guard's Bash heuristic blocked the main agent's own commit because the commit message mentioned the archive folder. That is the documented false positive; the workaround is to put the message in a file (`git commit -F`).
- 2026-11-14 (c): **Done:** S1-6 implemented. Main agent read the diff and found one small issue: the shebang, module docstring and `__main__` guard sit outside the AI markers. **Next:** qa-guard is writing independent tests and reviewing it. One test plus review agent was used because the ticket is small. **Issue:** a 985 KB XC16 user-guide text dump (`ug.txt`) appeared in the project root, outside every subagent's allowed paths. research-quant is the likely source; it has been asked to confirm and remove it. Don't commit it.
- 2026-11-14 (b): **Done:** verified the toolchain; XC16 and the MDB simulator are present. Sprint 1 planned. **Next:** six Sonnet subagents start on S1-1 to S1-6. **Blocked:** S1-7 needs their proposals.
- 2026-11-14 (a): **Done:** docs framework, AGENTS.md, TEAM_PROCESS.md, plan draft. Moved the original files to `docs/archive/`. **Next:** S0-3 contracts. **Blocked:** S0-1, the remote, which Hadi is adding.
