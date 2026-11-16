<!-- [AI-GENERATED: Claude Code] -->
# Recording gesture data with a real wand

WORKING ASSUMPTION: open_questions Q1 (C2 as proposed), not decided. Needs the C2 firmware streaming build.
Python 3 and numpy only; pyserial is optional (a POSIX fallback is built in, Linux/macOS).

## 1. Check the link
Plug the wand into the PC (UART1, 115200 8N1, e.g. `/dev/ttyUSB0`). The wand sends HELLO beacons every 2 s, so a
dry run that records nothing but prints the decoder summary shows whether the link works:
`python3 tools/recorder.py --port /dev/ttyUSB0 --out /tmp/test.npz --label none --count 1`

## 2. Record a session (guided)
```
python3 tools/recorder.py --port /dev/ttyUSB0 --out data/s1.npz --subject 1 --session 0 \
    --plan "none:30,swipe_right:30,swipe_left:30,raise:30,push_down:30,circle_cw:30,circle_ccw:30,twist:30,thrust:30"
```
The recorder prints `NEXT: <GESTURE> xN (press Enter to start)`; press Enter, then perform the gesture N times
(each trigger sends one window). Windows that arrive while it waits for Enter are skipped. Ctrl-C stops cleanly; the
file is rewritten after every window, so nothing is lost. A raw copy of all bytes goes to `data/s1.bin`
(replay with `--input data/s1.bin`).

One label only: `--label swipe_right --count 20`. Add more later with `--append` (session number increments).
An existing OUT without `--append` is refused.

## 3. Check and clean
```
python3 tools/dataset_tool.py info data/s1.npz          # counts, median peak L1 per label, warnings
python3 tools/dataset_tool.py drop --out data/s1c.npz data/s1.npz --index 3,7
python3 tools/dataset_tool.py relabel --out data/s1c.npz data/s1.npz --index 12 --label swipe_left
```
A label whose median peak L1 is near that of `none` was probably not performed hard enough.

## 4. Merge sessions and train
```
python3 tools/dataset_tool.py merge --out data/all.npz data/s1.npz data/s2.npz
python3 tools/train.py --data data/all.npz --out-dir out/run1
```
Use a different `--subject`/`--session` per run: `merge` refuses duplicate (subject, session) pairs, and `train.py`
splits by session or subject. `dataset_tool.py csv` exports samples for a spreadsheet.

## 5. Try it without a wand
```
python3 tools/synth_dataset.py --out /tmp/ds.npz --per-class 30
python3 tools/fake_wand.py --data /tmp/ds.npz --pty --order grouped --print-plan   # prints the slave path
python3 tools/recorder.py --port <that path> --out /tmp/rec.npz --plan "<plan line>" --no-pause --synthetic
```
`fake_wand.py` output is synthetic; always record it with `--synthetic`.
<!-- [END AI-GENERATED] -->

<!-- [AI-GENERATED: Claude Code] -->
## 6. Continuous recording (bring-up firmware, SAMPLES)
WORKING ASSUMPTION: open_questions Q1, Q2, not decided. The bring-up firmware (`-DGESTURE_BRINGUP_SAMPLES=1`) sends
only SAMPLES frames. Record the whole stream, then cut windows offline (so the same recording can be re-cut with other
trigger settings):
```
python3 tools/recorder.py --port /dev/cu.usbserial-XXXX --samples --out data/stream1.npz --plan "swipe_right:20,none:20" [--every 2.5]
python3 tools/cut_stream.py --stream data/stream1.npz --out data/s1.npz [--thr-mg 250] [--window-after-mark 2.0] [--none-gap 1.0]
```
- The recorder prints `NEXT: <NAME> xN`, waits for Enter (unless `--no-pause`), then prints `GO i/N` every `--every`
  seconds; perform ONE gesture after each GO. Each GO stores a mark (sample index, label) in the stream file.
- The stream file holds `samples`, `chunk_gaps` (where chunks were lost), `ovr` (sample index of each `OVR n` line) and `marks`.
- `cut_stream.py` runs the reference trigger (re-synced at every gap and OVR), cuts 150-sample windows and labels each by
  the latest mark at most 2 s before the trigger; a trigger with no mark within 1 s is `none`; anything else is dropped as
  ambiguous. Windows that straddle a gap are dropped. It prints per label: marks, windows, marks with no window (missed
  gesture, e.g. performed too softly or too early) and marks with two or more windows.
- Test without a wand: `fake_wand.py --data ds.npz --samples --gap 60 --marks-lead 15 --marks-out m.json --out w.bin`, then
  `recorder.py --input w.bin --samples --marks-from m.json --no-pause --synthetic --label none --out st.npz` (`--marks-from`
  is test only: it takes the true marks from the fake wand instead of the wall clock; `--gap` puts rest samples between
  windows so the trigger can re-arm).
<!-- [END AI-GENERATED] -->
