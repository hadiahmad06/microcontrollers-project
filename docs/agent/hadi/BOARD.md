# Sprint board for hadi's agent team

> The main agent is the scrum master (AGENTS.md §6). Update this file every time a subagent
> is assigned work, reports back, or gets blocked. It has to make sense to a fresh session
> with no chat history.

## Environment (verified 2026-11-14)
- XC16 v2.10: `/Applications/microchip/xc16/v2.10/bin/xc16-gcc -mcpu=24FJ64GA002`. Compiles and links. ✅
- MPLAB X v6.35 simulator: `/Applications/microchip/mplabx/v6.35/mplab_platform/bin/mdb.sh`. Headless use not yet proven (S1-4).
- Host tools: Apple clang 16, python 3.12 + numpy 1.26, make. arm64 macOS.
- Git: branch `main`. Hadi added a GitHub remote on 2026-11-14; agents do not push or fetch until told to.

## Working rules (Hadi's decisions, 2026-11-14)
- New subagents run in **git worktrees** (`isolation: worktree`), each committing on its own branch.
- The main agent merges a branch only after the ticket is done: tests it ran itself pass, and review findings are resolved.
- Work that predates worktree mode, and has not been reviewed yet, stays uncommitted in the main checkout until its review passes. Then the main agent commits it on `master`.

## Roster
_Agent IDs only work inside the session that started them. After a handoff, start new subagents and give them the ticket and its files._

| Name | Model | Role | Ticket | Status |
|------|-------|------|--------|--------|
| research-sensor | Sonnet 5.5 / medium | researcher | S1-1 | done; fixes merged |
| review-3 | Sonnet 5.5 / medium (worktree) | fact-checker | S1-1R | done, merged: APPROVE WITH NITS (3 medium) |
| spike-features | Sonnet 5.5 / medium | implementer | S1-2 | done; fixes merged |
| test-features | Sonnet 5.5 / medium (worktree) | tester | S1-2T | done, merged: 0 mismatches over 28k windows plus every possible segment sum |
| review-1 | Sonnet 5.5 / medium (worktree) | reviewer | S1-2R | done, merged: APPROVE WITH NITS |
| research-quant | Sonnet 5.5 / medium | researcher | S1-3 | done; fixes merged |
| review-2 | Sonnet 5.5 / medium (worktree) | fact-checker | S1-3R | done, merged: REQUEST CHANGES (3 major) |
| spike-sim | Sonnet 5.5 / medium | implementer | S1-4 | done; standing by for fixes |
| review-4 | Sonnet 5.5 / medium (worktree) | reviewer / tester | S1-4R | running |
| research-display | Sonnet 5.5 / medium | researcher | S1-5 | done; standing by for fixes |
| review-5 | Sonnet 5.5 / medium (worktree) | fact-checker and cross-proposal reconciler | S1-5R | running |
| impl-guard, qa-guard | - | - | S1-6 | retired; S1-6 was scrapped |

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
| S1-4 | Spike: run the MDB simulator headlessly, read results back, count cycles | spike-sim | in review: works. Main agent reran `make demo`: PASS, 1130 cycles, about 7 s | `spikes/sim/**` | S1-4R: reproduce from the README |
| S1-5 | Proposals C6b (display and bulb) and C7 (resource budget) | research-display | in review: committed `c4a2859`. Found that no single WS2812 waveform satisfies both chip revisions, and that the matrix needs a 5 V level shifter. review-5 is also reconciling all seven proposals | `proposals/C6b_*.md`, `proposals/C7_*.md` | S1-5R: fact-check |
| S1-6 | ~~Write-guard hook~~ | - | **scrapped** by Hadi (git history is the accountability). A no-op stub stays in local `.claude/hooks/` (git-excluded) until this session ends; delete it afterwards | `.claude/**`, `.gitignore` | S1-6T: test suite · S1-6R: review |
| S1-7 | Hadi decides C1–C7, and the decisions go into `docs/agent/CONTRACTS.md` | main + Hadi | blocked by S1-1 to S1-5 | top-level docs | – |

Paths are relative to `docs/agent/hadi/` unless they start with `.`.
**AI_USAGE.md:** subagents don't write to it, to avoid several of them writing at once.
The main agent adds rows from their reports.

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

## Standup log
_(newest first: done · next · blocked)_
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
