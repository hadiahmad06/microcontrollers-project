<!-- [AI-GENERATED: Claude Code] -->
# SPEC W2-5: training on real recordings (`tools/train.py` extensions + `tools/evaluate_model.py`)

Context: `tools/README.md` section "train.py and synth_dataset.py" describes the current tool (read it; it is part of
this spec). Real data will come from `tools/recorder.py` (ticket W2-4) as one `.npz` per session in the same training
format, possibly with extra per-window arrays (`window_id`, `overruns`, `model_hash`, `dev_flags`, `dev_class`,
`dev_conf`, `events`) and a 0-d unicode `meta` string. Every existing behaviour, default and output stays unchanged
when the new flags are not used: `train.py --selftest` must still pass and a default run on a synthetic dataset must
produce a byte-identical `gesture_model.h` to the run before your change (check it: same data, same seed).

## R1. Several dataset files
`--data` accepts several paths (`--data a.npz --data b.npz`, or `--data a.npz,b.npz`). They are validated one by one
(current checks), then concatenated in order. Extra arrays are ignored by training. `subject` and `session` are kept
only if every file has them (else dropped with a warning). For grouping, the group of a window is the pair
(file index, value) when grouping by `session`, so equal session numbers in two files never merge; grouping by
`subject` uses the value alone (one person recorded on two days is one subject). `synthetic` = any file synthetic.
The report lists the files with their N.

## R2. `tools/evaluate_model.py`
```
python3 tools/evaluate_model.py --header gesture_model.h --data D.npz [--data E.npz ...] [--out-dir DIR] [--min-conf N]
python3 tools/evaluate_model.py --selftest      # prints "evaluate_model selftest PASS"
```
Scores an existing header on new data with the integer path only (`features_ref` → `infer_ref.forward` →
`infer_ref.mlp_conf`; reject when conf < min_conf, default the header's `GM_DEFAULT_REJECT`): accuracy with a Wilson
95 % interval, accuracy after rejection and the rejection rate (true gestures, label != 0), the 9×9 confusion matrix,
per-class recall, per-subject accuracy when `subject` exists, and for windows that carry `dev_flags` bit 0 the agreement
between the on-device `dev_class` and the host prediction (only when the window's `model_hash` equals the header's
`GM_MODEL_HASH`; else say "different model"). Writes `report.md` + `report.json` to `--out-dir` (default: print
markdown to stdout). Marks the report SYNTHETIC when any input is synthetic. Exit 0 ok, 2 bad input.

## R3. Opt-in augmentation (train set only)
`--augment roll=DEG,gain=PCT,copies=K` (default off; any subset of keys; defaults when the flag is given without a key:
roll=0, gain=0, copies=1). Each train window gets K extra copies; copy j: rotate every sample about the wand X axis
(the tip axis; models grip roll, C1.3 frame) by an angle uniform in [-DEG, +DEG], multiply by a gain uniform in
[1 - PCT/100, 1 + PCT/100], round half away from zero, clip to [-2048, 2047], store int16. Seeded by the run seed.
Validation and test sets are never augmented; the normalisation (`export_model.py norm`) is computed on the
un-augmented train set. The report states the augmentation used. Features of augmented windows are not cached.

## R4. Report additions
When `subject` exists: test-set accuracy per subject. Always: the list of input files with N, and the share of windows
per class in train / val / test.
<!-- [END AI-GENERATED] -->
