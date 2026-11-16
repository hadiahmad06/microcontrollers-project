<!-- [AI-GENERATED: Claude Code] -->
# Recording gesture data with a real wand

WORKING ASSUMPTION: open_questions Q1 (C2 as proposed), not decided. Needs the C2 firmware streaming build.
Python 3 and numpy only; pyserial is optional (a POSIX fallback is built in, Linux/macOS).

## 1. Check the link
Plug the wand into the PC (UART1, 115200 8N1) through its USB-serial adapter (install the adapter's driver first).
Linux: `/dev/ttyUSB0`. macOS: list the ports with `ls /dev/cu.*` and use `/dev/cu.usbserial-*` or `/dev/cu.usbmodem*`
(NOT `/dev/tty.*`: those block waiting for a carrier). pyserial is optional (`pip install pyserial`); without it a
built-in POSIX fallback is used. Only one program may hold a port: close any serial terminal first.
The wand sends HELLO beacons every 2 s, so a short test run shows whether the link works (the recorder prints
`waiting for HELLO` until one arrives; with `--count 1` it stops after one window and stores that window, delete the
test file afterwards; with no window recorded no output file is created):
`python3 tools/recorder.py --port /dev/ttyUSB0 --out /tmp/test.npz --label none --count 1`

## 2. Record a session (guided)
```
python3 tools/recorder.py --port /dev/ttyUSB0 --out data/s1.npz --subject 1 --session 0 \
    --plan "none:30,swipe_right:30,swipe_left:30,raise:30,push_down:30,circle_cw:30,circle_ccw:30,twist:30,thrust:30"
```
The recorder prints `NEXT: <GESTURE> xN (press Enter to start)`; press Enter, then perform the gesture N times
(each trigger sends one window). Windows that arrive while it waits for Enter are skipped. Ctrl-C stops cleanly; the
file is rewritten after every window, so nothing is lost. A raw copy of all bytes goes to `data/s1.bin`
(replay with `--input data/s1.bin`). The raw log is APPENDED to, never truncated: use a new `--out` name (or
`--raw-log`) per session, or the log will mix sessions.

Timing hazard: the first window of a step is stored as soon as it arrives after Enter, and the last window of a step ends
the step at once. A gesture you started before pressing Enter, or the one you make right after the last count, lands in
the wrong step; wait for the `[NAME i/N]` line before each gesture and do not start the next gesture before the next `NEXT:` line.

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
  ambiguous. Windows that straddle a gap or an OVR line are dropped on purpose (W2-6, deliberate: the samples on the two sides of a gap
  are not contiguous, so such a window would be a false gesture shape; reviewers: this is not a bug). An existing `--out` is
  overwritten (it is derived data you re-cut with other settings); `--out` equal to `--stream` is refused. It prints per label: marks, windows, marks with no window (missed
  gesture, e.g. performed too softly or too early) and marks with two or more windows.
- Test without a wand: `fake_wand.py --data ds.npz --samples --gap 60 --marks-lead 15 --marks-out m.json --out w.bin`, then
  `recorder.py --input w.bin --samples --marks-from m.json --no-pause --synthetic --label none --out st.npz` (`--marks-from`
  is test only: it takes the true marks from the fake wand instead of the wall clock; `--gap` puts rest samples between
  windows so the trigger can re-arm).
- Marks: each GO mark index is the number of samples received so far plus `MARK_LAG` = 16, because the PC receives a
  sample up to one 16-sample chunk after the wand took it, so the received count lags what the user sees at GO.
- Wand stalls: no `GO` and no mark is made until a HELLO has arrived and a chunk arrived within the last second. The
  recorder prints `waiting for wand` once per stall and resumes the step where it paused.
- Gaps and OVR: windows whose span contains a chunk gap are dropped, and windows whose span touches `[ovr-16, ovr]` (an
  `OVR n` line means up to one chunk may be missing before it) are dropped too. Deliberate, not a bug.
- `--marks-from` is test only: the recorder forces `synthetic=1` (with a warning) and `cut_stream.py` keeps it synthetic.
  `--append` is not available with `--samples`; record one stream file per session, cut each, then `dataset_tool.py merge`.
- Two label traps (defaults kept: `--window-after-mark 2.0`, `--none-gap 1.0`): (1) a gesture made late (more than 2 s
  after GO) is labelled `none` or dropped; (2) a hand movement that returns the hand to rest right after the gesture can
  trigger a second window, which is labelled with the same mark. Advice: keep still during the pause between GOs and
  return the hand slowly after each gesture.
<!-- [END AI-GENERATED] -->
