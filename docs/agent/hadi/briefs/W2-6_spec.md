<!-- [AI-GENERATED: Claude Code] -->
# SPEC W2-6: continuous recording (SAMPLES) and offline trigger cut

WORKING ASSUMPTION: open_questions Q1, Q2, not decided. Why: windows cut offline from a continuous stream let training
re-cut the same recording with other trigger settings and with real trigger latency (S3-1 finding 5, C1b §3.4), and the
bring-up firmware (`-DGESTURE_BRINGUP_SAMPLES=1`, `briefs/3.7_spec.md` G2) sends only SAMPLES frames.
Builds on `tools/c2_proto.py`, `tools/recorder.py` (W2-4, `briefs/W2-4_spec.md`) and `tools/trigger_ref.py` (T-trig).

## V1. `recorder.py --samples` (stream capture)
With `--samples` the decoder accepts SAMPLES (accept_samples=True) and the recorder writes a STREAM file instead of a
window dataset: `samples` int16 [M,3] (all received samples in order), `chunk_gaps` int32 [G,2] (sample index where a
gap starts, number of lost chunks, from the chunk counter incl. wrap), `ovr` int32 [K] (sample index of every
`OVR <n>` text line received), `marks` int32 [L,2] (sample index, label) and the scalars/`meta` as in W2-4.
Labelling: `--plan` works as in W2-4 but a step is time-based: `NEXT: <NAME> x<N>` then, after Enter (or at once with
`--no-pause`), the recorder prints `GO <i>/<N>` every `--every SEC` seconds (default 2.5) and appends a mark
(current sample index, label) at each GO; the user performs one gesture after each GO. `--label L` without a plan
marks a single step of unlimited length. Rewritten atomically every 16 chunks. HELLO gate and checks as in W2-4.

## V2. `tools/cut_stream.py`
```
python3 tools/cut_stream.py --stream S.npz --out DS.npz [--thr-mg 250] [--window-after-mark SEC] [--none-gap SEC]
python3 tools/cut_stream.py --selftest
```
Runs `trigger_ref` over the stream (re-sync at every chunk gap and every `ovr` index; release `rel_delay = 135`),
cuts every trigger with `cut_windows`, and labels each window: the label of the latest mark at or before the trigger
sample if the trigger is within `--window-after-mark` seconds (default 2.0) after that mark, else 0 (none) if no mark
lies within `--none-gap` seconds (default 1.0) before or after it, else dropped (ambiguous). Output: the W2-4
training format plus `trig_sample` int32 [N] and `source` (stream file name in meta). Prints per label: marks, windows,
marks with no window (missed gesture), marks with two or more windows. SYNTHETIC propagates.

## V3. Fake wand support
`tools/fake_wand.py --samples` (W2-4 S3) already emits SAMPLES; add `--marks-out FILE` writing the true onset sample
of each source window and its label so tests can check V2's labelling against the truth.
<!-- [END AI-GENERATED] -->
