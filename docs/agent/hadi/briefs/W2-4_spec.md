<!-- [AI-GENERATED: Claude Code] -->
# SPEC W2-4: PC-side recording tools (C2 decoder, recorder, fake wand, dataset tool)

WORKING ASSUMPTION: open_questions Q1 (C2 as proposed), not decided. Goal: Hadi can plug the wand into a PC, record
labelled gesture windows, merge sessions, and feed `tools/train.py` directly.

## S0. Label names (C5.1, decided)
`tools/gesture_labels.py`: `LABELS = ("none", "swipe_right", "swipe_left", "raise", "push_down", "circle_cw",
"circle_ccw", "twist", "thrust")` (index = class id 0..8). `parse_label(s) -> int` accepts a decimal id 0..8 or a name
(case-insensitive, `-` and `_` equivalent); anything else raises `ValueError` naming the valid labels.

## S1. `tools/c2_proto.py` (no numpy; promoted from the spike `docs/agent/hadi/spikes/uart/c2_ref.py`, cite it)
- `crc16(data: bytes, crc=0xFFFF) -> int`: CRC-16/IBM-3740 per C2 §4 below. `crc16(b"123456789") == 0x29B1`.
- Constants: `SYNC0=0xA5, SYNC1=0x5A, T_HELLO=0x01, T_WINDOW=0x02, T_SAMPLES=0x04, LEN_HELLO=10, LEN_WINDOW=914,
  LEN_SAMPLES=99`.
- `encode_hello(seq, odr_hz=100, range_g=4, n_samples=150, pre_trig=15, feature_ver=<features_ref.FEATURES_VERSION>,
  model_hash=0, proto_ver=1) -> bytes` (18 B).
- `encode_window(seq, window_id, samples, trig_idx=15, overruns=0, model_hash=0, flags=0, class_id=0, conf=0, events=0)
  -> bytes` (922 B). `samples`: 150 rows of 3 ints (any sequence, or a numpy array); every value must be in int16 range
  (else `ValueError`).
- `encode_samples(seq, chunk, samples) -> bytes` (107 B), `samples` 16 rows of 3 ints.
- `seq` is taken modulo 256; `window_id`/`chunk` modulo 65536; `model_hash` modulo 2^32.
- `class Decoder(accept_samples=False)`: byte-at-a-time state machine exactly as C2 §4 and proposal §3.2 (below).
  Known types: HELLO (LEN 10) and WINDOW (LEN 914); SAMPLES (LEN 99) only when `accept_samples=True`.
  - `feed(data: bytes) -> list[Frame]`: returns the frames completed by these bytes, in order.
  - `Frame`: a namedtuple `(ftype, seq, payload)` (payload = bytes).
  - Counters (ints, public): `garbage` (bytes dropped while hunting for sync, including ASCII text), `bad_header`,
    `crc_errors`, `frames`, `seq_gaps` (sum over frames of `(seq - prev_seq - 1) mod 256`, first frame not counted).
  - `text_lines`: list of str. ASCII text (0x20..0x7E) dropped between frames is collected; a line ends at 0x0A
    (0x0D is ignored). Only bytes dropped while hunting for sync count as text; a byte that is not 0x0A, 0x0D or
    0x20..0x7E discards the partial line.
  - `flush_stale() -> list[Frame]`: the optional PC-side idle rule of proposal §3.2: if the buffer holds an
    incomplete candidate, drop one byte (counted as `bad_header`) and rescan the rest; returns frames that complete.
    The recorder calls it when no byte arrived for >= 50 ms.
- `parse_hello(payload) -> dict` with keys `proto_ver, odr_hz, range_g, n_samples, pre_trig, feature_ver, model_hash`.
- `parse_window(payload) -> dict` with keys `window_id, n_samples, trig_idx, overruns, model_hash, flags, class_id
  (signed), conf, events, samples` (`samples` = list of 150 `(x, y, z)` int tuples).
- `parse_samples(payload) -> dict` with keys `chunk, n, samples` (16 tuples).
- `--selftest` prints `c2_proto selftest PASS` and exits 0, else prints what failed and exits 1. It must check: the CRC
  check value; byte equality with the spike's `encode_hello`/`encode_window` (import the spike module by path) for at
  least 1 HELLO and 20 random WINDOWs incl. -32768/32767/-2048/2047; a byte-at-a-time round trip with ASCII text,
  garbage and one corrupted frame in between; `flush_stale` on a false WINDOW header followed by a HELLO.

## S2. `tools/recorder.py`
```
python3 tools/recorder.py (--port DEV [--baud 115200] | --input FILE|-) --out OUT.npz
        (--label L [--count N] | --plan "L:N,L:N,...") [--subject S] [--session K] [--append]
        [--no-pause] [--synthetic] [--raw-log PATH] [--quiet]
python3 tools/recorder.py --selftest     # prints "recorder selftest PASS"
```
- **Input.** `--port`: a serial device at `--baud` 8N1. Use pyserial if it imports; otherwise a POSIX fallback
  (`os.open` + `termios` raw mode, 8N1, the baud constant from `termios`, `select` with a 50 ms timeout). If neither
  works, exit 2 with a message that names `pip install pyserial`. `--input FILE` reads a raw byte file (`-` = stdin)
  in chunks of 4096 B and ends at EOF (used for tests and replays). Exactly one of `--port`/`--input`.
- **Raw log.** Every byte read is appended to `--raw-log` (default: OUT with the suffix replaced by `.bin`) and the
  file is flushed after each read, so a session can always be decoded again with `--input`.
- **HELLO gate.** No window is stored before a valid HELLO has arrived. Every HELLO is checked: `proto_ver == 1`,
  `odr_hz == 100`, `range_g == 4`, `n_samples == 150`, `pre_trig == 15` (C0, C1.5); any mismatch exits 3 with the field
  name. `feature_ver != tools/features_ref.FEATURES_VERSION` only prints a warning (raw windows do not depend on it).
  WINDOW frames with `n_samples != 150` or `trig_idx != 15` are counted as `rejected` and not stored.
- **Labels.** `--label L` labels every stored window L (S0 `parse_label`); `--count N` stops after N stored windows
  (default 0 = until EOF / Ctrl-C). `--plan "swipe_right:20,none:30"` = guided session: steps in order; before each step
  print `NEXT: <NAME> x<N>  (press Enter to start)` and wait for a line on stdin unless `--no-pause` (required with
  `--input -`); the next N stored windows get that label; while a step runs print `[<NAME> i/N]` per window; after
  the last step stop. Windows that arrive while waiting for Enter are counted as `skipped` and not stored.
- **Per-window line** (unless `--quiet`): stored index, label name, window_id, peak L1 deviation from the window's first
  sample in counts (max over samples of sum over axes of |s - s[0]|), overruns, and the on-device result
  (`class_id/conf` if flags bit 0 set, else `-`).
- **Ctrl-C** stops cleanly: the output written so far stays valid.
- **Output** `--out OUT.npz` (the training format of `tools/README.md`, below) plus extra arrays:
  `windows` int16 [N,150,3], `labels` uint8 [N], `subject` uint8 [N] (`--subject`, default 0), `session` uint16 [N]
  (`--session`; default: 0 for a new file, max(existing)+1 with `--append`), `window_id` uint16 [N], `overruns`
  uint16 [N], `model_hash` uint32 [N], `dev_flags` uint8 [N], `dev_class` int8 [N], `dev_conf` uint8 [N], `events`
  uint8 [N], `synthetic` scalar uint8 (1 with `--synthetic`, else 0), `meta` = a 0-d numpy unicode string holding a
  JSON object (`tool`, `version`, `started`, `source` (port or file name), `hello` (last HELLO dict), `counters`
  (decoder counters + `stored`, `rejected`, `skipped`), `label_names`). The file is rewritten after EVERY stored window
  through a temp file in the same directory and `os.replace`, so a crash never leaves a truncated file. `np.savez`
  (not compressed); `np.load(OUT)` must work without `allow_pickle`.
- **`--append`**: OUT must exist and have the same format; new windows are appended; `synthetic` becomes the max of old
  and new; `meta` keeps a list of sessions (`sessions`: one entry per run). Without `--append` an existing OUT is an
  error (exit 2), never silently overwritten.
- **Summary** at the end (stdout): stored per label, rejected, skipped, decoder counters, SEQ gaps.
- Exit codes: 0 ok, 2 bad arguments / unreadable input / missing serial support / OUT exists, 3 HELLO mismatch.

## S3. `tools/fake_wand.py` (test and demo source, never real data)
```
python3 tools/fake_wand.py --data DS.npz (--out FILE | --pty) [--order as-is|grouped] [--hello-every K]
        [--text "LINE"] [--corrupt P] [--seed S] [--print-plan] [--rate BPS] [--samples]
python3 tools/fake_wand.py --selftest     # prints "fake_wand selftest PASS"
```
- Reads a training-format dataset (e.g. from `tools/synth_dataset.py`) and emits the C2 byte stream a wand would send:
  optional ASCII text line(s) `--text` first (each followed by `\n`), a HELLO, then one WINDOW per dataset window
  (`window_id` 0,1,2,...; SEQ counts every frame from 0, wrapping), with a HELLO inserted after every `--hello-every`
  windows (default 2). `model_hash` 0, flags 0.
- `--order grouped` emits windows sorted by label (stable); `--print-plan` prints to stderr the `--plan` string that
  labels that stream correctly (e.g. `none:120,swipe_right:120,...`, labels with zero windows omitted).
- `--corrupt P` (0..1, default 0, seeded by `--seed`, default 1): each WINDOW frame is independently, with probability
  P, emitted with one byte flipped at a random payload position (so the decoder must reject it with a CRC error). Print
  to stderr how many were corrupted.
- `--out FILE` writes the bytes at once. `--pty` opens a pseudo-terminal pair (`os.openpty`, raw mode), prints the slave
  path on stdout (one line, flushed), waits up to 30 s for the reader to open it (or a short fixed 1 s delay), then
  writes at `--rate` bytes per second (default 11520) in chunks of at most 256 B, and exits when done (after a 1 s
  drain delay). `--samples` (bring-up mode): instead of WINDOW frames, concatenate the windows into one continuous
  stream and emit SAMPLES chunks of 16 samples (chunk counter from 0; a trailing partial chunk is dropped).
- Always print to stderr: `SYNTHETIC: fake_wand output, never real data`.

## S4. `tools/dataset_tool.py`
```
python3 tools/dataset_tool.py info DS.npz [DS2.npz ...]
python3 tools/dataset_tool.py merge --out OUT.npz DS1.npz DS2.npz [...] [--allow-dup-session]
python3 tools/dataset_tool.py drop --out OUT.npz DS.npz --index 3,7,12
python3 tools/dataset_tool.py relabel --out OUT.npz DS.npz --index 3,7 --label swipe_left
python3 tools/dataset_tool.py csv --out OUT.csv DS.npz
python3 tools/dataset_tool.py --selftest     # prints "dataset_tool selftest PASS"
```
- **Validation (every command):** `windows` int16 [N,150,3] with every value in [-2048, 2047]; `labels` uint8 [N] in
  0..8; optional `subject`/`session` of length N; any other array of length N is a per-window extra. Violations exit 2
  with the file name and the check.
- **info:** per file and in total: N, per-label counts by name, subjects, sessions, `synthetic` flag (print
  `SYNTHETIC` in capitals when 1), per-label median peak L1 deviation (as in S2), and a warning line for every label
  with fewer than 20 windows.
- **merge:** concatenates in argument order. Keeps `subject`, `session` and extras present in all inputs; drops (with a
  warning naming them) arrays present in only some. `synthetic` = max. `meta` = JSON with `merged_from` (file names and
  their N). Refuses (exit 2) if the same (subject, session) pair occurs in two different input files, unless
  `--allow-dup-session`. Output dtypes equal the inputs'.
- **drop / relabel:** indices refer to the input file (0-based); out-of-range index exits 2; output keeps all arrays.
- **csv:** header `window,label,label_name,subject,session,t,x,y,z`, one row per sample (t = 0..149).
- Writes via temp file + `os.replace`; never overwrites an input file (exit 2 if `--out` equals an input).

## S5. Pipeline acceptance (both implementer and tester run it)
```
python3 tools/synth_dataset.py --out $T/ds.npz --per-class 30 --seed 3
python3 tools/fake_wand.py --data $T/ds.npz --out $T/stream.bin --order grouped --print-plan --text "GM_MODEL_HASH=0" 2>$T/plan.txt
python3 tools/recorder.py --input $T/stream.bin --out $T/rec.npz --plan "$(grep -v '^SYNTHETIC' $T/plan.txt | tail -1)" --no-pause --synthetic --quiet
python3 tools/dataset_tool.py info $T/rec.npz
python3 tools/train.py --data $T/rec.npz --out-dir $T/train --epochs 5
```
`rec.npz` windows and labels equal the source dataset's windows and labels after the grouped (stable) sort, exactly;
`train.py` exits 0. With `--corrupt 0.1` the recorder stores exactly the uncorrupted windows (count = N - corrupted)
and its CRC error counter equals the number corrupted.
Live check on Linux: `fake_wand.py --pty` in the background and `recorder.py --port <slave path>` (POSIX fallback,
pyserial is not installed) records the same windows.

## S6. Verbatim: C2 working-assumption contract text (`docs/agent/hadi/drafts/C2_contract_section.md`)

1. **Link.** UART1, 115200 8N1 (C6.1). The wand only transmits in v1: **no PC → wand commands**
   (so the C6.3 "host does not transmit during show" rule is never needed; team question D-6 = "never").
2. **Encoding.** Binary frames, every multi-byte field little-endian (CRC too). CSV exists only as an
   export of the PC tool.
3. **What is sent.** Only completed 150-sample windows, sent from the locked C1 buffer after READY
   (one extra state READY → SENDING → release). The buffer is released when the last frame byte is
   queued (≈ 70 ms). Plus HELLO beacons.
4. **Frame.**
```
offset size field
0      1    SYNC0 0xA5
1      1    SYNC1 0x5A
2      1    TYPE  0x01 HELLO, 0x02 WINDOW (v1); reserved: 0x03 RESULT, 0x04 SAMPLES, 0x10 CMD, 0x11 VECTOR
3      2    LEN   payload length (10 for HELLO, 914 for WINDOW)
5      1    SEQ   frame counter, wraps at 256, restarts at 0 on reset
6      LEN  payload
6+LEN  2    CRC   CRC-16/IBM-3740 (poly 0x1021, init 0xFFFF, no reflection, xorout 0; check("123456789") = 0x29B1)
                  over bytes 2 .. 5+LEN, low byte first
```
   A decoder accepts a frame only if TYPE is one it knows, LEN is that type's single legal value and the CRC
   matches; on any failure it drops one byte and rescans.
5. **WINDOW payload (914 B; frame 922 B).** `window_id u16 | n_samples u8 (150) | trig_idx u8 (15) |
   overruns u16 | model_hash u32 | flags u8 (bit 0 = result valid) | class_id i8 | conf u8 | events u8 |
   450 × int16` (samples `buf[0][0], buf[0][1], buf[0][2], buf[1][0], …`, wand frame). `window_id` counts
   windows sent (overrun-dropped windows take no id); `events` = event bits latched during this window (never
   via `gesture_events()`); all metadata snapshotted at READY.
6. **HELLO payload (10 B; frame 18 B).** `proto_ver u8 (1) | odr_hz u8 | range_g u8 | n_samples u8 | pre_trig u8 |
   feature_ver u8 | model_hash u32`. Sent at boot and every 2 s while no frame is in flight.
7. **Label.** Attached by the PC recorder; nothing on the wire.
8. **TX pump rules.** One TX owner; frames are atomic (never aborted); bounded number of main-loop iterations per
   frame; no PC-side timeout (no flow control exists).
9. **Text.** ASCII (0x0A, 0x0D, 0x20..0x7E) only between frames (boot hash print, stack report).
10. **Bring-up.** A compile-time option streams type 0x04 SAMPLES chunks (`chunk u16 | n u8 = 16 | 16 × 3 × int16`,
    LEN 99, frame 107 B) with no trigger; never in the demo build.
11. **Test vectors** (PLAN 3.9) are deferred; the reserved types keep room for them.

## S7. Verbatim: proposal §3.2 decoder (`docs/agent/hadi/proposals/C2_uart_stream.md`)

Byte-at-a-time, buffer of unconsumed bytes. Steps: front byte must be 0xA5 and the next 0x5A (else drop one byte, count garbage); read TYPE, LEN, SEQ; the TYPE must be in the known table (v1: 0x01 with LEN 10, 0x02 with LEN 914) and LEN must equal its single legal value, otherwise drop one byte and count a bad header (this covers reserved types, TYPE 0, TYPE above 0x0F, LEN 1024 and 1025, and a damaged LEN of either known type); wait for the whole frame; check the CRC (on mismatch drop one byte, count CRC error); on success consume the frame.

Optional PC-side rule, not in the spike: if no byte arrives for 50 ms while the buffer holds an incomplete candidate, drop one byte and rescan. A real frame has no such gap if the TX pump rules in 3.5 hold, and this cuts the beacon-only stall to the idle gap.

§3.10 (SAMPLES): Sample i of chunk c is global sample 16c + i; a gap in `chunk` is a lost chunk. HELLO beacons still go out between chunks. The bring-up tool uses `Decoder(extra_types={0x04: 99})`; a v1 recorder rejects 0x04.

## S8. Verbatim: training dataset format (`tools/README.md`)

Dataset format (WP2 tools): one `.npz` with `windows` int16 `[N,150,3]` (C1 wand frame, values in
[-2048, 2047]), `labels` uint8 `[N]` (0..8, C5), optional `subject` uint8 `[N]` and `session` uint16
`[N]` for grouped splits, optional scalar `synthetic` (1 stamps the report as synthetic). The recorder
(C2, undecided) will write this format.
<!-- [END AI-GENERATED] -->
