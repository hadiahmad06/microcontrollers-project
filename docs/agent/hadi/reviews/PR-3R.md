<!-- [AI-GENERATED: Claude Code] -->
# PR-3R: pre-merge review of PR hadiahmad06/microcontrollers-project#2 (Sprints 3-4)

Reviewer: review-21 (Sonnet 5.5, medium), working for hadi, 2026-11-15. I wrote none of the reviewed work.
Reviewed: `git diff origin/main...HEAD` at `fd8f751` (17 commits, 36 files) on branch `pr3-review`
(= `origin/claude/optimistic-meitner-67qdon`). Read: AGENTS.md, `docs/agent/CONTRACTS.md`, the diff, REPORT_DRAFT.md,
CITATIONS.md, S4-3R.md, the spike sources.

## Verdict: MERGE AFTER FIXES

No product behaviour change (checklist 1 holds for every file), no governance breach, clean run passes on both
suites. The only issues are documentation that is stale or slightly inaccurate after the SW-3 comment sweep. None
touches code or a top-level doc, so the fixes are small and can go in this PR.

## Findings

| ID | Where | Finding | Evidence | Severity |
|---|---|---|---|---|
| F-01 | `CITATIONS.md` Gaps 1, 2, 3, 5, 6, 7 and the "Cited at" columns | CITATIONS.md was written before SW-3 and not updated after it. BOARD says SW-3 "closed gaps 1-3, 5-7", but CITATIONS.md still says (Gap 1) "The code comment does not carry the UNVERIFIED tag", (Gap 2) "product code names the algorithm with no source and no tag", (Gap 3) reserved-bit comments "carry no tag", (Gap 5) lis3dh.c/h give no DocID/Rev, (Gap 6) xorshift32 "cited nowhere" and isqrt "no source", (Gap 7) display.c/h have no pointer. All are now false; the code has the tags/citations. A reader of the report would chase closed gaps. | `knn.h` now says "cited from memory, UNVERIFIED"; `knn.c:11-13` names G. Cook; `lis3dh.c` CTRL_REG5/6 comments say "written from memory, UNVERIFIED"; `lis3dh.h` gives "DocID17530 Rev 1 (May 2010)" and "DocID18198 Rev 3"; `display.c:11-14`, `display.h` cite the Uberguide and WS2812B; `features.c`/`features.h`/`tools/features_ref.py` say "our own implementation". | major |
| F-02 | `CITATIONS.md` (no entry) vs 11 new code comments | Marsaglia, "Xorshift RNGs", J. Statistical Software 8(14), 2003, is now cited in 10 test files (`firmware/test/*/oracle.py`, `test_*.c`, `mlp/driver.c`, `e2e/*`) but has no row in section (b) and is not tagged "FROM MEMORY" in either place. Volume/issue/year were evidently written from memory (CITATIONS.md says the repo had no source for it). Per the checklist the comment citations must match CITATIONS.md; this one is absent. | `grep -n Marsaglia docs/agent/hadi/CITATIONS.md` returns nothing; the only mention is Gap 6 "xorshift32 ... published generator (Marsaglia) but cited nowhere". | minor |
| F-03 | `CITATIONS.md` file:line references | Several line references no longer point at the cited text after SW-3 (file says it will drift). Spot check: `knn.c:10` (now inside the new header comment, not the CRC line; the CRC text moved to 11-13, 93-94, 116-117), `knn.c:89,110` (now `}`), `lis3dh.c:12` (now blank; "table 17" is at line 13), `lis3dh.c:129-130,151-152` (comment lines moved), `test_classify.c:77` (now `/**`). Unaffected and correct: `lis3dh_hal.h:28` ("section 5.1.1"), `mlp.c:7-8,11` (Jacob 2018, DS-50002071M section 23), `display.c:11` (20 mA), `run_e2e.py:196` (CRC), `tools/train.py:28` (Adam). | `sed -n` of each cited line at HEAD. | minor |
| F-04 | `REPORT_DRAFT.md` section 6 | "19 review reports in `docs/agent/hadi/reviews/`". The directory holds 20 files at HEAD (`S4-3R.md` is the 20th); with this review it is 21. | `ls docs/agent/hadi/reviews | wc -l` = 20. | minor |
| F-05 | `REPORT_DRAFT.md` section 2 diagram and section 3 | Says "watermark 16" / "watermark at 16". CONTRACTS C1.4 (decided) says "watermark **FTH = 15**". The two are the same event in LIS3DH terms (WTM sets when unread > FTH, i.e. at 16 samples), but a reader comparing with the contract sees two numbers. | CONTRACTS.md:46; fake_lis3dh.c comment "b7 WTM (unread > FTH)". | minor |
| F-06 | `REPORT_DRAFT.md` section 5 results table | Lists `stall0` (96 %, gap 1, gap-windows 2) as a result without saying it is the superseded overrun order kept as a bug demonstration. The spike output labels it "overrun order 0 (SUPERSEDED, bug demo)"; the corrected default is `stall1`/`stall2`. The table shows both and the prose does not tell a reader which is the design. | Spike output footer line; S4-3R R-03. | minor |
| F-07 | `AI_USAGE.md` (spike rows) | Spike `fake_lis3dh.c` has one new function (`fake_push_sample`) plus a refactor (`push_one_w`, `push_one` wrapper) in the copied file. Only `fake_push_sample` has a row (the row mentions "+ copy of firmware/test/lis3dh fake"). All other functions of the copy are covered by the existing `firmware/test/lis3dh/fake_lis3dh.c` rows, so this is acceptable; noted only because `push_one_w` has no row of its own. | `AI_USAGE.md:647` | minor |

Not findings (checked and fine): AI_USAGE has a row for every function in `glue.c` (8/8), `make_stream.py` (10/10) and
`evaluate.py` (8/8). Markers are balanced in all 36 changed files that exist (script check, no output).

## Checklist results

### 1. No product behaviour change: PASS
Objects built from `origin/main` and `HEAD` with `cc -std=c99 -O2 -c` and `avr-gcc -mmcu=atmega2560 -std=c99 -O1 -c`
(`-iquote` for the project include dirs, because `-I firmware/src` makes the system `<features.h>` resolve to
`firmware/src/features.h`; that is a build-flag hazard of mine, not a repo problem), `cmp` result:

```
display host IDENTICAL   display avr IDENTICAL
features host IDENTICAL  features avr IDENTICAL
knn host IDENTICAL       knn avr IDENTICAL
lis3dh host IDENTICAL    lis3dh avr IDENTICAL
mlp host IDENTICAL       mlp avr IDENTICAL   (mlp.c is not in the diff; built as a control, header from
                                              python3 firmware/test/mlp/gen_model.py 1 <dir>/gesture_model.h)
```
`ast.dump` of base vs head: `tools/features_ref.py`, `firmware/test/{capture,classify,display,features,mlp}/oracle.py`,
`firmware/test/e2e/run_e2e.py`: all 7 IDENTICAL. `cc -fpreprocessed -dD -E -P` of base vs head: `test_capture.c`,
`classify/standin/knn.c`, `test_classify.c`, `test_display.c`, `test_e2e.c`, `test_features.c`, `mlp/driver.c`: all 7
IDENTICAL. Files changed under `firmware/src` and `tools` are only the 4 `.c`, 4 `.h` and `features_ref.py` listed;
no header changed in a way that affects objects (the four objects are byte-identical).

### 2. Governance: PASS
`git diff origin/main...HEAD --stat -- docs/human docs/archive 'docs/agent/*.md'` prints nothing. Changed docs are
all under `docs/agent/hadi/` (BOARD.md, CITATIONS.md, REPORT_DRAFT.md, open_questions.md, proposals/API_glue.md,
reviews/S4-3R.md, spikes/integration/*) plus root `AI_USAGE.md`. No other person's folder, no archive, no top-level doc.
CITATIONS.md itself notes (Gap 11) that moving its content into a top-level doc needs the section 5 process and was not done.

### 3. Clean run: PASS
`git clean -xdf firmware tools && make test` ends:
```
sim16 harness PASS
ALL SUITES PASS (8 suites)
```
`cd docs/agent/hadi/spikes/integration && git clean -xdf . && make test` ends:
```
host == sim16 and Python == C: PASS
INTEGRATION SPIKE DONE
```
The printed SUMMARY rows (main 48/46, big 160/154, tight 32/25, stall0 24/23, stall1 24/22, stall2, stallw, short 8/7)
equal the table in REPORT_DRAFT.md section 5 (the draft omits `stall2` and `stallw`). After the run `git status` is clean
(build dir is ignored).

### 4. Docs accuracy: PASS with the findings above
REPORT_DRAFT numbers checked against their sources (10 of 10 correct, 1 imprecise = F-05):
1. static RAM 2512 B vs C7 2500 B, and the per-module table (402/548/1007 ... total 6150/1603/2512): equal to `measurements.md`.
2. 3660 B (44.7 %), 512 B stack: CONTRACTS C7 line 297 / 285.
3. isqrt range max 7912: CONTRACTS C3 line 97.
4. k-NN templates 4 x 5 x 60 B = 1200 B: CONTRACTS C7.
5. I2C1BRG 394 kHz: CONTRACTS line 232. 6. WS2812 mask about 138 us, 300 mA: CONTRACTS lines 263, 269.
7. 5-9 k cycles, 0.3-0.56 ms at 16 MIPS: CONTRACTS C3 line 108 (5k/16 MIPS = 0.31 ms, 9k = 0.56 ms).
8. Capture RAM 900 + 96 + 96 = 1092: C7 budget (capture 900, ring 96, staging 96).
9. AI_USAGE "about 640 rows: ~57 product, ~380 test, ~100 tools, ~100 spikes": counted 57 / 382 / 101 / 97 (+3 other), 645 total.
10. Spike table and "dead time about 1.7 s" (re-trigger 167-194 samples) and "91 % -> 48 %": spike output and Q8 (140/154 -> 74/154).
11. (imprecise) "watermark 16": F-05. (stale) "19 review reports": F-04.

CITATIONS.md spot check of 5 citations: `lis3dh_hal.h:28` ok; `mlp.c:7-8,11` ok; `display.c:11` ok; `run_e2e.py:196` ok;
`knn.c:10/89/110` and `lis3dh.c:12` drifted (F-03). The new CRC comments in `knn.c`, `knn.h`, `classify/standin/knn.c`,
`test_classify.c`, `classify/oracle.py`, `e2e/run_e2e.py` all name "G. Cook, Catalogue of parametrised CRC algorithms"
and the URL with "recalled from memory, not re-read": this matches CITATIONS.md C1. No "R. Williams" anywhere
(`grep -rn Williams firmware tools docs/agent/hadi/CITATIONS.md` returns nothing). Lowe, A1, A2, A10 and C2 comments match the
CITATIONS.md entries (title, DocID, revision, URL, UNVERIFIED tags). Marsaglia is the exception (F-02).

### 5. Course rules: PASS
Start/end marker counts equal in every changed file. The spike files, report and scripts: no `float`/absolute machine paths in
the diff added lines other than the S4-3R review prose naming repo-relative paths. No build products tracked
(`.o`, `.elf`, `.pyc`, `build/` absent from the file list; the spike `.gitignore` covers its build dir). AI_USAGE rows: see above.

## Commands
```
git fetch origin main claude/optimistic-meitner-67qdon
git checkout -B pr3-review origin/claude/optimistic-meitner-67qdon
git diff origin/main...HEAD --stat           # 36 files, 2037 insertions, 18 deletions
git diff origin/main...HEAD --stat -- docs/human docs/archive 'docs/agent/*.md'     # empty
git clean -xdf firmware tools && make test    # ALL SUITES PASS (8 suites)
make -C docs/agent/hadi/spikes/integration test    # INTEGRATION SPIKE DONE
```

## Suggested fixes before merge (all docs, in this PR)
1. Update CITATIONS.md: mark Gaps 1, 2, 3, 5, 6, 7 as closed by SW-3 (keep the "from memory, UNVERIFIED" caveats where the
   comments carry them), add Marsaglia to section (b), refresh the file:line columns (re-grep).
2. REPORT_DRAFT.md: "20 (21 with PR-3R)" review reports; "watermark FTH = 15 (fires at 16 unread)"; one line saying stall0
   is the superseded overrun order shown only as a bug demonstration.
<!-- [END AI-GENERATED] -->
