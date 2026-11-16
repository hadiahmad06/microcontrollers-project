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
