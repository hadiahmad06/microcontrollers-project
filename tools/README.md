<!-- [AI-GENERATED: Claude Code] -->
# tools/

Host-side Python tools (Python 3, numpy needed for `export_model.py` only).

## infer_ref.py: integer reference inference (C4/C5)

Bit-exact model of the firmware path, integers only. Stages are separate functions so a test
vector can localise a mismatch: `normalize` -> `layer1` (acc1, h) -> `layer2` (logits) -> `top2`
(top1, margin) -> `mlp_conf`; `forward(feat, m)` returns all of them. C5: `knn_l1`,
`class_radius`, `knn_query`, `classify_decide`.

```
python3 tools/infer_ref.py --selftest          # prints "infer_ref selftest PASS"
python3 -c "import sys; sys.path.insert(0,'tools'); import infer_ref as I; \
  m=I.load_header('gesture_model.h'); print(I.forward([0]*60, m))"
```
`load_header` also checks `GM_MODEL_HASH` against the arrays.

## export_model.py: float network to `gesture_model.h` (C4)

Train the float net on `x8 = normalize(features)` (optionally `x8 / K`), so compute the
normalisation first (odd feature index = non-negative energy, C3):

```
python3 tools/export_model.py norm   --features calib.npy --out norm.json
python3 tools/export_model.py header --weights net.npz --norm norm.json --calib calib.npy \
        [--val val.npy --val-labels y.npy] [--k K] [--conf-shift N] [--default-reject N] \
        --out gesture_model.h
```
`net.npz`: `W1 [16,60]`, `b1 [16]`, `W2 [9,16]`, `b2 [9]` (optional scalar `K`). `K` convention: the
net was trained on `x8 / K`, so the exporter uses `W1 / K` (the net then acts on `x8` directly;
CONTRACTS C4.3 words this as "multiplies W1 by that constant back", the same thing seen from the
other side).

The exporter reads `NONNEG` (which features are non-negative energies) and `FEATURES_VERSION` from
`tools/features_ref.py` (C3); `--feature-version` must equal it, and `len(NONNEG) == 60` is checked.

With `--val` / `--val-labels` (held-out raw features and integer class labels, class 0 = no gesture):
- `GM_CONF_SHIFT`: C5 rule, the smallest shift s with `P95 >> s <= 255`, where P95 is the nearest-rank
  value `sorted[ceil(0.95 n) - 1]` of the margins of correctly classified windows.
- `GM_DEFAULT_REJECT` (C5.2): let `conf = min(255, margin >> GM_CONF_SHIFT)` of every held-out window
  with label != 0 (true gestures; a window the MLP misclassifies still counts), sorted ascending as
  `c[0..n-1]`, and `k = floor(2 n / 100)`. Then `GM_DEFAULT_REJECT = c[k]`. Reject means `conf < min_conf`,
  so at most `k` windows (<= 2 %) are rejected and `c[k] + 1` would reject more than `k`. (The
  contract says "smallest value ... <= ~2 % rejected"; taken literally that is 0, so it is
  implemented as the tightest threshold within the 2 % budget.) The chosen value and the actual
  rejected share are printed. `--default-reject N` overrides it.
- The C4.3 fallback criterion (agreement < 97 %, or accuracy drop with a Wilson bound) is evaluated when
  n >= 500 and printed as a warning if met; with n < 500 a warning says it cannot be assessed.

Without validation data `--conf-shift` (default 6) and `--default-reject` (default 64) are used,
a warning goes to stderr, and the header marks both macros with `/* PROVISIONAL: no validation data */`.

Exit codes: 0 ok, 2 unusable input (missing file, bad shapes, bad K), 3 bound violation (message on
stderr names the bound, e.g. `scale in [2^-17, 0.5)`, `|B| < 2^29`, `|B| + 127*sum|W| < 2^30`,
`GM_IN_SH <= 14`, `GM_IN_OFF in int16`, `len(GM_IN_OFF) == len(GM_IN_SH) == GM_N_FEATURES`); never a
traceback, and independent of `python -O` (all checks are explicit, none is an `assert`). A bad
`norm.json` is checked before it is used. Nothing is ever clamped, except that the info-only
`GM_LOGIT_SCALE_Q32` saturates to 0xFFFFFFFF with a warning (it is not a C4 bound). An all-zero W1 row
(dead neuron) only prints a warning.

`infer_ref.parse_header` / `load_header` enforce the same C4 bounds on a header (weights in [-127,127],
`2^14 <= M1 < 2^15`, `16 <= SH1 <= 31`, `GM_IN_SH <= 14`, `|B| < 2^29`, per-row worst case `< 2^30`), the full array
shape (ragged arrays are refused), literal-only `GM_*` macros and the hash, raising `ValueError`.

Quantization scheme: Jacob et al. 2018, arXiv:1712.05877; reference spec
`docs/agent/hadi/spikes/quant/quant_ref.py` (our own spike).
<!-- [END AI-GENERATED] -->

<!-- [AI-GENERATED: Claude Code] -->
## train.py and synth_dataset.py: dataset to trained header (W2-2)

Dataset format (WP2 tools): one `.npz` with `windows` int16 `[N,150,3]` (C1 wand frame, values in
[-2048, 2047]), `labels` uint8 `[N]` (0..8, C5), optional `subject` uint8 `[N]` and `session` uint16
`[N]` for grouped splits, optional scalar `synthetic` (1 stamps the report as synthetic). The recorder
(C2, undecided) will write this format.

```
python3 tools/synth_dataset.py --out ds.npz --per-class 120 --seed 1   # SYNTHETIC, pipeline test only
python3 tools/synth_dataset.py --selftest                              # "synth_dataset selftest PASS"
python3 tools/train.py --data ds.npz --out-dir DIR [--seed S | --seeds 1,2,3] [--epochs 60] \
        [--val-frac 0.2] [--test-frac 0.2] [--group subject|session|none] [--fallback-set val|test] \
        [--lr 3e-3] [--batch 32] [--weight-decay 1e-4] [--k 64] [--eval-every 5] [--split-seed S]
python3 tools/train.py --selftest        # prints "train selftest PASS"
```

Real recordings (W2-5). `--data` may be repeated or a comma list (`--data a.npz --data b.npz`, or `a.npz,b.npz`):
each file is validated, then they are concatenated in order. Extra arrays from `recorder.py` (`window_id`,
`overruns`, `model_hash`, `dev_*`, `events`, `meta`) are ignored by training. `subject` and `session` are kept
only if every file has them (else dropped with a warning). With `--group session` the group is (file index,
session number), so equal session numbers in two files never merge; `--group subject` uses the subject value
alone (one person on two days is one subject). The report lists the files with their N, the share of each class
in train / validation / test, and (when `subject` exists) the test accuracy per subject.
`--augment roll=DEG,gain=PCT,copies=K` (default off, any subset of keys, defaults roll=0 gain=0 copies=1) adds K
copies of every TRAIN window: rotated about the wand X axis by a uniform angle in +-DEG degrees (grip roll,
C1.3 frame), multiplied by a uniform gain in 1 +- PCT/100, rounded half away from zero, clipped to
[-2048, 2047], int16. It uses its own generator seeded from the run seed (the training stream is untouched).
Validation and test are never augmented, the normalisation (`export_model.py norm`) is computed on the
un-augmented train features, augmented features are not cached, and the report states the augmentation.
Without the new flags a run is unchanged (checked: same `gesture_model.h` hash as before the change).
Warnings (W2-5F2, in the report banner and on stderr): when `subject` has at least 2 values but the split is not
grouped by subject, "subjects appear in both train and test; per-person generalisation is NOT measured"; an
automatic fallback to a stratified split puts its message in the warnings too. In automatic mode with several
input files and no usable subject / session array, the split is grouped by input file index (`grouping: by input
file`) before the stratified fallback. Two input files with byte-identical `windows`, or windows that appear in
two files, produce a warning (duplicates leak between sets). Per-subject lines with N < 30 carry "(small N)".
Onset-jitter augmentation (W2-3, SYNTHETIC): `synth_dataset.py --onset-jitter=LO,HI` (use the `=` form, the
value starts with a minus sign) draws each gesture's onset uniformly in `[15+LO, 15+HI]` instead of `15 +- 3`
(class 0 and the default output are unchanged: the default `.npz` is byte-identical to before, checked by hash). It
approximates trigger latency: the live trigger fires a few to ~40 samples after the true onset, so the onset
lands at window index ~-10..27 (negative = onset before the window start) (`--onset-jitter=-25,12`), as seen in the integration spike (S3-1 finding 5). It is
only an approximation; real data should instead be cut by the real trigger from continuous recordings (C1b
section 3.4). `train.py` needs no flag, it just trains on the resulting `.npz`.

Pipeline: features (`features_ref`, cached in `DIR/features.npy`; the cache key hashes the windows and
`FEATURES_VERSION`) -> split into train / validation / test (seeded) -> `export_model.py norm` on TRAIN
features only -> `x8 = infer_ref.normalize` -> float 60-16-9 MLP in numpy (ReLU, softmax cross-entropy,
Adam, trained on `x8 / K`, default K = 64; typical `|x8/K|` is about 0.2, extremes about 2) -> every
`--eval-every` epochs a candidate header is exported with `export_model.py header --val ...` and scored
with `infer_ref.forward` on the VALIDATION set; the best integer accuracy wins (patience 6 candidates).
`--hidden` is accepted only as 16 (C4.2: `mlp.c` static-asserts `GM_N_HIDDEN == 16`); anything else is
refused with exit 2.

**Three sets (review W2-2R M1/M2).** Train fits weights and normalisation. Validation selects the
checkpoint and, through the exporter's `--val`, `GM_CONF_SHIFT` and `GM_DEFAULT_REJECT`. The TEST set is
scored once, on the final header with the integer path, and gives every reported accuracy (with a Wilson
95 % interval), confusion matrix and rejection rate in `report.md` / `report.json`; float accuracy and
float-vs-int agreement are diagnostics. Validation numbers are reported too, labelled "selection set
(optimistic)": the best of up to 12 candidates and an in-sample threshold, so they are biased upward (the
rejection rate there is at most 2 % by construction). `--val-frac` and `--test-frac` default to 0.2 each.
`--test-frac 0` gives a two-way split; the report then says all its numbers are optimistic.

**Grouping (M4).** If the dataset has `subject` (else `session`) and `--group` is not given, the split
is grouped by it automatically (whole groups per set, shuffled by the split seed) and the choice is
printed and written to the report; with fewer than 3 groups (2 without a test set) it falls back to a
stratified split and says so. `--group none` forces the stratified split (every class in every set where
the class has at least 3 windows). After any split a warning (stderr and report) lists each class missing
from train, validation or test. Pseudo-groups in the synthetic data carry no signal (S3: ids are drawn
independently of class, with no per-subject offset or gain), so a grouped synthetic run tests only the
splitting mechanics, not the generalisation across people.

**C4.3 fallback (M3, open question Q6).** `--fallback-set val|test` (default `val`, the agent's
recommendation pending Hadi's decision) picks the set that judges the int16 fallback. `test` makes the
test set part of a design decision, so it is then no longer untouched (the report says so). The report
names the set and n, and prints "CANNOT be assessed" when n < 500.

**Other flags.** `--lr`, `--batch`, `--weight-decay` (defaults 3e-3, 32, 1e-4). `--seeds 1,2,3` runs one
training per seed in `DIR/seed_N/` and writes `DIR/seeds.md` / `seeds.json` with the mean and min/max of
the reported integer accuracy; the split follows each seed unless `--split-seed` fixes it (then the
test set is the same for all seeds). When `GM_DEFAULT_REJECT` is 0 the report says "rejection disabled
(GM_DEFAULT_REJECT = 0)" instead of a bare 0.00 % rate.

Outputs in `DIR`: `gesture_model.h`, `norm.json`, `net.npz` (with `K`), `report.json`, `report.md`,
plus `split.npz` (train, val, test indices), `features.npy` and a `work/` scratch folder. Exit codes:
0 ok, 2 bad input (including an exporter exit 2), 3 exporter refusal (decided by the exporter's exit
code 3, message names the bound).

`synth_dataset.py`: class 0 ("none") starts in the same cone around up (35 degrees) as the gestures, so
the start orientation alone does not reveal it; `--selftest` checks that the best start-tilt-only rule
at zero false positives recognises under 60 % of class 0 (it prints the number, about 0 %). Swipes
follow the C1.3 wand frame (Y = left): a swipe to the right moves the tip toward -Y first. The circle
classes still have a small nonzero mean Y (cos x Hann window), a mild artefact.

`synth_dataset.py` shapes are adapted from our own spike `docs/agent/hadi/spikes/trigger/synth.py`;
the data is invented and must never be quoted as an accuracy result. Adam: Kingma and Ba 2015,
arXiv:1412.6980 (textbook algorithm, no code borrowed).

## evaluate_model.py: score an existing header on new data (W2-5)

```
python3 tools/evaluate_model.py --header gesture_model.h --data D.npz [--data E.npz ...] [--out-dir DIR] [--min-conf N]
python3 tools/evaluate_model.py --selftest      # prints "evaluate_model selftest PASS"
```
Integer path only (`features_ref` -> `infer_ref.forward` -> `infer_ref.mlp_conf`); a window is rejected when its
confidence is below `--min-conf` (default the header's `GM_DEFAULT_REJECT`). The report gives accuracy with a
Wilson 95 % interval, accuracy after rejection (correct / accepted over all accepted windows, every label; plus a second line for true gestures only), the rejection rate on true gestures (label != 0), the 9x9
confusion matrix with per-class recall, per-subject accuracy when `subject` exists, and, for windows with
`dev_flags` bit 0, the agreement of the on-device `dev_class` with the host prediction, counted only where
`model_hash` equals the header's `GM_MODEL_HASH` (others are listed as "different model"). `--out-dir` writes
`report.md` and `report.json`, otherwise the markdown is printed. Rejection is MLP-confidence only ("MLP-only, no k-NN
gate"; firmware `classify_decide` may overturn a weak MLP result), and this is stated in report.md. Windows whose
`dev_class` is GESTURE_UNKNOWN (-1, the recorder stores int8) are reported separately as "device rejected" and are
not counted as disagreements; per-subject lines with N < 30 carry "(small N)". Marked SYNTHETIC when any input is. Exit 0 ok,
2 bad input.
<!-- [END AI-GENERATED] -->
