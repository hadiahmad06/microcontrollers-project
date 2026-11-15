<!-- [AI-GENERATED: Claude Code] -->
# PR-2R2: delta pre-merge review of PR #1 since PR-2R (`1cdceaa`)

Reviewer: review-19 (Sonnet 5.5, medium), working for hadi. I wrote none of the code.
Reviewed head: `84cb145` (22 commits after `1cdceaa`, 20 files, +1818/-239). The remote branch tip is `d8225f1`, one commit later
("docs(board): batch w, PR-2R2 running", board only, no code), so the code reviewed equals the PR head.

## Verdict: MERGE

No blocker, no major. Both PR-2R majors are closed. The five minors below are bookkeeping and can be fixed after the merge.

## Findings

| ID | Where | Finding | Evidence | Severity |
|----|-------|---------|----------|----------|
| d-1 | `firmware/src/lis3dh.c:~188` (`lis3dh_unpack`), `BOARD.md` | `sign[k] < 0` became `sign[k] == -1` (only -1 negates, any other value acts as +1). Commit 653f6b5 calls it the WP1-bT3 "ruling" and `lis3dh.h` documents it, but the BOARD WP1-bT3 / WP1-bF2 rows do not record the ruling text, and CONTRACTS C1.3 only defines signs of +-1. Behaviour for non-+-1 signs is outside the contract, so no contract conflict. | `git show 653f6b5`; `grep -n "sign" BOARD.md` finds no ruling line | minor |
| d-2 | `lis3dh.c` `init_fail` | A failed config write before CTRL_REG1 = 0x57 is attempted does no power-down (`sampling == false`). If the part was already sampling from an earlier successful init and the first CTRL_REG1 = 0x00 write fails, the sensor keeps sampling while `lis3dh_address()` returns 0. Harmless (driver refuses to run; a later init restarts from 0x00 and Bypass) and the header says "if CTRL_REG1 may have been written non-zero". | read | minor |
| d-3 | `AI_USAGE.md` | Missing rows for helpers in `firmware/test/e2e/run_e2e.py`: module-level `_q`, `_decisive`, `_conf_edge`; plan-class methods `start`, `add`, `want`, `of`, `first`; nested closures `score`/`pred`. All 61 function definitions added in the delta were scripted against the log; every `firmware/src` function (`init_fail`) and every C test function has a row. PR text says every function in `firmware/src` and `tools` has a row: still true. | script output below | minor |
| d-4 | PR #1 description | Stale: says "clean build takes 73 s" (now 97 s on this container) and lists 3.8F, WP1-bF2/bT3, SW-2a/b as "landing before merge" with "if it cannot land, it is deferred". They have landed. | PR body read via GitHub | minor |
| d-5 | `firmware/test/e2e/Makefile:5` | Comment `make test IMPL_DIR=/tmp/broken` is still there (PR-2R m-10). Harmless example path; no other absolute machine path in the delta. | grep | minor |
| d-6 | `firmware/test/lis3dh/standin/lis3dh.c`, `firmware/test/classify/standin/knn.c` | Test stand-ins duplicate the product logic (the knn stand-in got the same 15-line change). They are by design the independent oracle; their drift from `firmware/src` is caught by running both. Noted only. | read | minor (info) |

Count: 0 blocker, 0 major, 6 minor.

## Checklist results

### 1. M-1 (3.8F landed, closes 3.8R F-01..F-04): CLOSED
3.8F is on the branch (b693a04, merge 7172056) and BOARD says done. The coverage section of the e2e run:
```
coverage of boundaries (hits per model m1..m4; total must be > 0 on host and on sim16):
  x8 saturates at +127 (unclamped >= 256)   host 1605  sim16 326
  x8 saturates at -127 (unclamped <= -256)  host 392   sim16 63
  x8 clamp edge +128 / -128                 host 477 / 31   sim16 104 / 9
  MLP logit tie for top1 (margin 0)         host 184   sim16 71
  k-NN d1 == radius / radius+1              4 / 4      sim16 4 / 4
  k-NN d2 == 0                              host 14    sim16 12
  MLP conf == 192 / 191                     host 23 / 7  sim16 8 / 4
  min_conf: MLP conf == min_conf / -1 ; k-NN c_k == min_conf / -1   all > 0 on host and sim16
PASS [coverage: ...] for every line
```
- F-01 (saturation never exercised): closed, +-127 and +-128 edges hit on host and sim16 for every counted case.
- F-02 (boundary ties incidental): closed, directed plan (14 to 57 steps per model) hits tie, d1 == radius (+1), d2 == 0, conf 191/192, min_conf edges, and the run fails if any total is 0 on host or sim16.
- F-03 (skewed models): closed, "model spread (>= 7 top1 classes, no class > 40%)" is now a PASS line; e.g. m4 has 8 classes, max share 15% (was 64 to 79%).
- F-04 (thin sim16 sample): closed, sim16 now runs 370+ windows per model (was 150), 45 to 48 of them directed.
- The tie coverage per model is uneven (0+1+1+182); the total over the four models is what is asserted, which is what F-02 asked for.

### 2. M-2 (code vs CONTRACTS wording disclosed): CLOSED
- `docs/agent/hadi/open_questions.md` Q4, Q5, Q6, Q7 each quote the CONTRACTS sentence, the code behaviour and the proposed record; Q6 carries the AGENTS 5B conflict marker.
- The PR body (read through the GitHub API, read only) has the section "Known differences between code and CONTRACTS wording (PR-2R M-2)" with Q4 to Q7, and says CONTRACTS is unchanged.
- Code comments: `tools/export_model.py:227` (literal "smallest" would be 0), `tools/train.py:19,505,778` (Q6), `lis3dh.c` `MAX_BURSTS` comment and `lis3dh.h` (`more`, 4-burst bound). Q5 (divide by K) is documented in the exporter and Q5; the Q4/Q5/Q7 comments do not carry the question number, which is fine.

### 3. Delta correctness (firmware/src, line by line)
- `knn.c` / `knn.h` (SW-2a, ruling 3.5R F4): `buf == NULL` returns 0 from `knn_export` and -1 from `knn_import`; `knn_import` rejects any non-zero byte of an unused slot (slot index >= count) with -2. Order is length, header, CRC, per-class shape, unused slots, then the store is written, so the store stays unchanged on every error (the new loop sits before the first write to `s_count`). Index arithmetic is `uint16_t`, max 1216, fits a 16-bit int. Header text matches. A blob made by `knn_export` always passes (unused slots are zero). Covered by ruling SW-2a.
- `lis3dh.c` / `lis3dh.h` (WP1-bF2, review WP1-bR F1, F3, F5 to F9): `init_fail` clears `s_addr` and does a best-effort CTRL_REG1 = 0x00 once CTRL_REG1 = 0x57 has been attempted (F1, F9); `lis3dh_drain` and `lis3dh_read_click` return `LIS3DH_ERR_BUS` with no HAL call when `s_addr == 0` (F8); in `lis3dh_drain` the guard comes after `*overrun = 0` and `*more = false`, so outputs are defined; comments for CLICK_CFG (no LIR bit), CTRL_REG5 bits 5:4 and CTRL_REG6 bit 0 added (F6, F7); `write_verify` has full @param/@return (F5). Init still stops at the first fault (F2, now tested). No register value, order or burst/drain logic changed (the diff of the register-write lines shows only the `return init_fail(sampling)` substitution and comment text).
- The only behaviour change not stated in a review row is `sign == -1` (d-1): main-agent ruling in the commit message, documented in `lis3dh.h`, matched by the odd-table tests, does not change any value for +-1 signs (the only values CONTRACTS C1.3 and `board_axes.h` use). Not a blocker.
- No other `firmware/src` file changed in the delta.

### 4. Clean run: PASS
```
git clean -xdf firmware tools            (nothing left to remove on the checkout)
make test                                -> rc=0, wall 97 s, last line "ALL SUITES PASS (8 suites)"; "warning" count in the log: 0
python3 tools/infer_ref.py --selftest    -> infer_ref selftest PASS
python3 tools/train.py --selftest        -> train selftest PASS
git status after the build               -> clean
```

### 5. Course rules on the delta: PASS with d-3
- AI markers: all 14 changed code files (`firmware/src/{knn.c,knn.h,lis3dh.c,lis3dh.h}`, `firmware/test/**` changed files incl. the e2e Makefile) have exactly 1 begin and 1 end marker.
- AI_USAGE: scripted check of the 61 function definitions added in `git diff 1cdceaa..HEAD -- firmware tools` against `AI_USAGE.md` rows (file and name): all present except the 10 names in d-3. `init_fail` has its row.
- `grep -nwE 'float|double|malloc|calloc|realloc' firmware/src`: only comment text ("no float, no malloc", "double click"). No blocking delays added.

### 6. Hygiene: PASS
- No tracked build product, `.pyc`, object or `build/` in the delta; `git status` clean after a full build.
- Absolute machine paths: only the `/tmp/broken` usage comment (d-5).
- Delta docs touch only `docs/agent/hadi/**` (own folder) and `AI_USAGE.md`; no `docs/human/**`, top-level doc or other person's folder changed, no archive change.
<!-- [END AI-GENERATED] -->
