<!-- [AI-GENERATED: Claude Code] -->
# Model headers for firmware builds

- `synthetic_bootstrap_model.h`: **SYNTHETIC**. Trained on invented data only so the recording firmware can be built
  before any real data exists (`make -C firmware/build record.hex MODEL=../models/synthetic_bootstrap_model.h`).
  The wand's on-device class/confidence with this model mean nothing; `tools/recorder.py` stores the raw windows and
  your label, which is what training uses. Regenerate:
  `python3 tools/synth_dataset.py --out ds.npz --per-class 120 --seed 1 --onset-jitter=-25,12` then
  `python3 tools/train.py --data ds.npz --out-dir out --epochs 30 --seed 1` (GM_MODEL_HASH 0x96CC9410).
- After the first real recordings: `python3 tools/train.py --data s1.npz --data s2.npz ... --out-dir real1` and build
  with `MODEL=<path>/real1/gesture_model.h`. See `tools/RECORDING.md`.
<!-- [END AI-GENERATED] -->
