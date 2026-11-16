<!-- [AI-GENERATED: Claude Code] -->
# PR-4R: pre-merge review of PR #4 (review-30, for hadi)

Verdict: **MERGE** (no blockers, no majors; 4 minors/nits, none gate the merge).

## Checks
1. Marker scan (`git diff -U0` added lines vs. marker blocks, all changed files): every .c/.h/.py/Makefile/.md code file is covered.
   Reported hits are all benign: `tools/recorder.py` has nested markers (open L2, L169, L553; END L207, L853, L962), so L210-552 and L856-961
   look unmarked to a flat scanner but sit inside the outer block L2-L962; `firmware/build/.gitignore` and
   `firmware/test/gesture/.gitignore` carry no marker (data files); L1 shebangs by design; `AI_USAGE.md`, `BOARD.md` (agent doc), `DECISIONS.md` (human statements) are logs, not code.
2. AI_USAGE.md: rows present for all new code files. Missing: `firmware/models/synthetic_bootstrap_model.h` (F1).
3. AGENTS.md section 3: `docs/human/**` touched only `docs/human/hadi/DECISIONS.md` (+10 lines, 0 deletions, append-only); top-level docs: only `docs/agent/WORKING_ASSUMPTIONS.md` (new). No other person's folder. No deleted files.
4. No binaries (numstat shows none), no .npz/.elf/.hex/ug.txt, no secret patterns. `!firmware/build/` only un-ignores that dir (its own .gitignore ignores obj/, gesture_model.h, elf/hex/map); `git check-ignore` confirms firmware/test/*/build and trigger build outputs stay ignored.
5. Consistency: C2 layout matches (SYNC A5 5A, TYPE 1/2/4, LEN LE, SEQ, HELLO 10 B `<BBBBBBI`, WINDOW head 14 B `<HBBHIBbBB`, SAMPLES `<HB`+48h LEN 99, CRC-16 0x1021 init FFFF).
   Trigger defaults equal everywhere (debounce 2, quiet 30, warm 32, 250 mg; PRE 15/POST 135; cut_stream uses trigger_ref constants, `--thr-mg` default 250).
   HELLO fields from gesture.c come from CAPTURE_LEN/CAPTURE_PRE and model info; recorder checks proto 1, odr 100, range 4, n 150, pre 15 (hard) and feature_ver (warning only, F2). Makefile uses wildcard globs for src, hal and app, so new files are included. Spot-checked CLI flags in README/RECORDING against `--help` for recorder, cut_stream, dataset_tool (info/merge/drop/relabel), train, evaluate_model, fake_wand: all match.
6. Test runs: `make test` last line `ALL SUITES PASS (11 suites)`; test_recording `ALL PASS`; test_stream `ALL PASS`; `ORIG_REF=e8a4291 test_train_real.py` `ALL PASS`.

## Findings
- F1 (minor): `AI_USAGE.md` lacks a row for `firmware/models/synthetic_bootstrap_model.h` (generated AI file). Add one.
- F2 (minor): recorder `check_hello` (tools/recorder.py:564) hard-checks 5 fields; feature_ver mismatch is only a warning (L336, L697). Acceptable; confirm intent.
- F3 (nit): nested/duplicate AI markers in `tools/recorder.py` (L169/L553 inside L2-L962) and `firmware/models/synthetic_bootstrap_model.h` (L1 and L7 openers, one END at L89). Flatten for tidiness.
- F4 (nit): `firmware/build/.gitignore`, `firmware/test/gesture/.gitignore` and the one-line edit in `docs/agent/hadi/proposals/C6a_sensor_io.md:162` (own folder, allowed) have no marker.
<!-- [END AI-GENERATED] -->
