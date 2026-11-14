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
`net.npz`: `W1 [16,60]`, `b1 [16]`, `W2 [9,16]`, `b2 [9]` (optional scalar `K`). With `--val`, the
exporter picks `GM_CONF_SHIFT` by the C5 rule from the integer path (P95 of correct margins
<= 255, nearest-rank); without it `--conf-shift` (default 6, provisional) is used and a warning is
printed. `--default-reject` defaults to the provisional 64. `K` convention: the net was trained
on `x8 / K`, so the exporter uses `W1 / K` (the net then acts on `x8` directly).

Exit codes: 0 ok, 2 bad input, 3 bound violation (message names the bound, e.g.
`scale in [2^-17, 0.5)`, `|B| < 2^29`, `|B| + 127*sum|W| < 2^30`); nothing is ever clamped.

Quantization scheme: Jacob et al. 2018, arXiv:1712.05877; reference spec
`docs/agent/hadi/spikes/quant/quant_ref.py` (our own spike).
<!-- [END AI-GENERATED] -->
