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
