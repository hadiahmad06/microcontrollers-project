#!/usr/bin/env python3
# [AI-GENERATED: Claude Code]
"""PC-side recorder: reads the C2 byte stream of a wand, stores labelled windows as a training .npz.

WORKING ASSUMPTION: open_questions Q1 (C2 as proposed), not decided.
Decoder and CRC come from tools/c2_proto.py (promoted from the spike docs/agent/hadi/spikes/uart/c2_ref.py).
Output format: tools/README.md "Dataset format" plus extra per-window arrays (see OUT_KEYS).

Usage:
  python3 tools/recorder.py (--port DEV [--baud 115200] | --input FILE|-) --out OUT.npz
        (--label L [--count N] | --plan "L:N,L:N,...") [--subject S] [--session K] [--append]
        [--no-pause] [--synthetic] [--raw-log PATH] [--quiet]
  python3 tools/recorder.py --selftest

Exit codes: 0 ok, 2 bad arguments / unreadable input / missing serial support / OUT exists, 3 HELLO mismatch.
"""
import argparse
import datetime
import json
import os
import queue
import select
import stat
import subprocess
import sys
import tempfile
import threading
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c2_proto  # noqa: E402
import features_ref  # noqa: E402
from gesture_labels import LABELS, parse_label  # noqa: E402

# per-window arrays of the output file: key -> dtype
OUT_KEYS = (("windows", np.int16), ("labels", np.uint8), ("subject", np.uint8), ("session", np.uint16),
            ("window_id", np.uint16), ("overruns", np.uint16), ("model_hash", np.uint32),
            ("dev_flags", np.uint8), ("dev_class", np.int8), ("dev_conf", np.uint8), ("events", np.uint8))
TOOL_VERSION = 1
IDLE_S = 0.05


class Fatal(Exception):
    """An error that ends the run with a given exit code."""

    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def peak_l1(w):
    """Peak L1 deviation of a window from its first sample.

    Args:
        w: array-like [150,3] of ints.
    Returns:
        int, max over samples of sum over axes of |s - s[0]| (counts).
    """
    a = np.asarray(w, dtype=np.int32)
    return int(np.abs(a - a[0]).sum(axis=1).max())


# ----------------------------------------------------------------------------- byte sources
def read_file(path):
    """Generator over a raw byte file ('-' = stdin) in chunks of 4096 B; ends at EOF.

    Args:
        path: file name or '-'.
    Yields:
        bytes chunks; for a pipe, FIFO or tty also None after 50 ms without data (like read_serial).
    """
    try:
        f = sys.stdin.buffer if path == "-" else open(path, "rb")
    except OSError as e:
        raise Fatal(2, "cannot read input %s: %s" % (path, e))
    try:
        try:
            streaming = not stat.S_ISREG(os.fstat(f.fileno()).st_mode)    # pipe, FIFO or tty
        except (OSError, ValueError, AttributeError):
            streaming = False
        while True:
            if streaming:
                # W2-6F3: like --port, wake every 50 ms so idle work (stall detection, flush_stale) runs while the pipe is quiet
                r, _, _ = select.select([f.fileno()], [], [], IDLE_S)
                if not r:
                    yield None
                    continue
                b = os.read(f.fileno(), 4096)
            else:
                b = f.read1(4096) if hasattr(f, "read1") else f.read(4096)
            if not b:
                return
            yield b
    finally:
        if path != "-":
            f.close()


def read_serial(port, baud):
    """Generator over a serial device (pyserial if importable, else POSIX termios); 8N1.

    Args:
        port: device path. baud: baud rate.
    Yields:
        bytes chunks, or None when no byte arrived for 50 ms. Ends at EOF/EIO (e.g. a closed pty).
    """
    try:
        import serial  # pyserial
    except ImportError:
        serial = None
    if serial is not None:
        try:
            s = serial.Serial(port, baud, timeout=IDLE_S)
        except (OSError, ValueError, serial.SerialException) as e:
            raise Fatal(2, "cannot open %s: %s" % (port, e))
        try:
            while True:
                b = s.read(max(1, s.in_waiting))
                yield b if b else None
        finally:
            s.close()
    try:
        import termios
    except ImportError:
        raise Fatal(2, "no serial support: install it with `pip install pyserial` (termios is not available)")
    bconst = getattr(termios, "B%d" % baud, None)
    if bconst is None:
        raise Fatal(2, "baud %d not supported by termios; install pyserial: pip install pyserial" % baud)
    try:
        fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    except OSError as e:
        raise Fatal(2, "cannot open %s: %s" % (port, e))
    try:
        attrs = termios.tcgetattr(fd)
        attrs[0] = 0                                    # iflag: no input processing (raw)
        attrs[1] = 0                                    # oflag: no output processing
        attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL   # cflag: 8 data bits, no parity, 1 stop, receiver on
        attrs[3] = 0                                    # lflag: no echo, no canonical mode, no signals
        attrs[4] = attrs[5] = bconst                    # input and output speed
        attrs[6][termios.VMIN] = 0                      # read returns what is there
        attrs[6][termios.VTIME] = 0                     # no read timeout (select does the waiting)
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        try:
            import fcntl
            fcntl.ioctl(fd, termios.TIOCEXCL)           # exclusive: a second program cannot open the port (F11)
        except (ImportError, AttributeError, OSError):
            pass
        termios.tcflush(fd, termios.TCIFLUSH)           # drop bytes buffered before we opened (F11)
        while True:
            r, _, _ = select.select([fd], [], [], IDLE_S)
            if not r:
                yield None
                continue
            try:
                b = os.read(fd, 4096)
            except BlockingIOError:
                continue
            except OSError:                             # EIO: the other end of a pty was closed
                return
            if not b:
                return
            yield b
    finally:
        os.close(fd)


class LazyLog:
    """Raw byte log that is created on the first byte written, so a failed run leaves no file behind (W2-4F F2)."""

    def __init__(self, path, enabled):
        """Args: path: log file; enabled: falsy = never write (input file is the log)."""
        self.path = path
        self.enabled = bool(enabled)
        self.f = None

    def write(self, b):
        """Append bytes (opens the file on first use, flushes every time); raises Fatal(2) if it cannot open."""
        if not self.enabled:
            return
        if self.f is None:
            try:
                self.f = open(self.path, "ab")
            except OSError as e:
                raise Fatal(2, "cannot open raw log %s: %s" % (self.path, e))
        self.f.write(b)
        self.f.flush()

    def close(self):
        """Close the file if it was opened."""
        if self.f:
            self.f.close()


def hello_hint(rec, hinted):
    """Print the waiting-for-HELLO hint once, after the first read that produced no HELLO (F7).

    Args:
        rec: recorder with a .hello attribute. hinted: list used as a once-flag.
    """
    if not hinted:
        hinted.append(1)
        if rec.hello is None:
            print("waiting for HELLO (the wand sends one every 2 s)", flush=True)


# ----------------------------------------------------------------------------- output file
def _load_existing(path):
    """Load an existing recorder file for --append; returns (dict of arrays, synthetic int, meta dict)."""
    try:
        z = np.load(path)
        arrs = {k: z[k] for k, _ in OUT_KEYS}
        syn = int(z["synthetic"])
        meta = json.loads(str(z["meta"]))
    except (OSError, ValueError, KeyError) as e:
        raise Fatal(2, "cannot append to %s: not a recorder file (%s)" % (path, e))
    if arrs["windows"].ndim != 3 or arrs["windows"].shape[1:] != (150, 3):
        raise Fatal(2, "cannot append to %s: windows is not [N,150,3]" % path)
    return arrs, syn, meta


def write_npz(path, arrays, synthetic, meta):
    """Write the output file through a temp file in the same directory and os.replace.

    Args:
        path: target. arrays: dict key -> ndarray. synthetic: int 0/1. meta: dict (JSON-able).
    """
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".rec_", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "wb") as f:
            np.savez(f, synthetic=np.uint8(synthetic), meta=np.array(json.dumps(meta)), **arrays)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class Recorder:
    """Decodes frames, applies the HELLO gate and the label plan, keeps the output file current."""

    def __init__(self, args, steps, live):
        """Args: args (argparse namespace); steps: list of (label_id, count; 0 = unbounded); live: serial source."""
        self.a = args
        self.steps = steps
        self.live = live
        self.dec = c2_proto.Decoder()
        self.hello = None
        self.stored = self.rejected = self.skipped = 0
        self.per_label = {}
        self.step_i = 0          # index of the current step
        self.in_step = 0         # windows stored in the current step
        self.waiting = False
        self.warned_range = False
        self.q = None
        self.cols = {k: [] for k, _ in OUT_KEYS}
        self.old = None
        self.old_syn = 0
        self.old_meta = {}
        self.started = datetime.datetime.now().isoformat(timespec="seconds")
        self.session = args.session
        self.session_given = args.session is not None

    @property
    def done(self):
        return self.step_i >= len(self.steps)

    def setup_append(self):
        """Load the existing file for --append and pick the default session number."""
        self.old, self.old_syn, self.old_meta = _load_existing(self.a.out)
        if not self.session_given:
            ses = self.old["session"]
            self.session = int(ses.max()) + 1 if len(ses) else 0
        elif self.session is None:
            self.session = 0
        if len(self.old["session"]) and bool(((self.old["session"] == self.session) &
                                              (self.old["subject"] == self.a.subject)).any()):
            print("warning: %s already holds subject %d session %d; dataset_tool merge refuses duplicates"
                  % (self.a.out, self.a.subject, self.session), file=sys.stderr)

    def start_plan(self):
        """Print the first NEXT line and begin waiting for Enter when pausing."""
        if self.a.plan:
            self.announce()
            if not self.a.no_pause:
                self.waiting = True
                if self.live:
                    self.q = queue.Queue()
                    threading.Thread(target=self._stdin_loop, daemon=True).start()

    def _stdin_loop(self):
        while True:
            line = sys.stdin.readline()
            self.q.put(line if line else None)
            if not line:
                return

    def announce(self):
        """Print the NEXT line of the plan for the current step."""
        label, n = self.steps[self.step_i]
        print("NEXT: %s x%d  (press Enter to start)" % (LABELS[label].upper(), n), flush=True)

    def poll_enter(self):
        """Live mode: end the waiting state if the user pressed Enter (non-blocking)."""
        if self.waiting and self.q is not None:
            try:
                line = self.q.get_nowait()
            except queue.Empty:
                return
            self._got_enter(line)

    def _got_enter(self, line):
        if line is None:                      # stdin closed while waiting: stop cleanly
            self.step_i = len(self.steps)
        self.waiting = False

    def _block_enter(self):
        """File mode: block for Enter on stdin."""
        line = sys.stdin.readline()
        self._got_enter(line if line else None)

    def on_frame(self, f):
        """Handle one decoded frame (HELLO gate, window storage)."""
        if f.ftype == c2_proto.T_HELLO:
            h = c2_proto.parse_hello(f.payload)
            for k, want in (("proto_ver", 1), ("odr_hz", 100), ("range_g", 4), ("n_samples", 150), ("pre_trig", 15)):
                if h[k] != want:
                    self.hello = h
                    raise Fatal(3, "HELLO mismatch: %s = %d, expected %d" % (k, h[k], want))
            if h["feature_ver"] != features_ref.FEATURES_VERSION:
                print("warning: wand feature_ver %d != tools/features_ref.FEATURES_VERSION %d (raw windows are unaffected)"
                      % (h["feature_ver"], features_ref.FEATURES_VERSION), file=sys.stderr)
            self.hello = h
        elif f.ftype == c2_proto.T_WINDOW:
            self.on_window(c2_proto.parse_window(f.payload))

    def on_window(self, p):
        """Store one WINDOW if the gate, the shape checks and the plan allow it."""
        if self.hello is None or p["n_samples"] != 150 or p["trig_idx"] != 15:
            self.rejected += 1
            return
        s = np.array(p["samples"], dtype=np.int16)
        if s.min() < -2048 or s.max() > 2047:             # outside the 12-bit range of the training format
            self.rejected += 1
            if not self.warned_range:
                self.warned_range = True
                print("warning: window rejected, samples outside the 12-bit range -2048..2047 (is the wand in +-4 g mode?)",
                      file=sys.stderr)
            return
        if self.waiting:
            if not self.live:
                self._block_enter()
            else:
                self.poll_enter()
            if self.waiting or self.done:
                self.skipped += 1
                return
        if self.done:
            return
        label, n = self.steps[self.step_i]
        c = self.cols
        c["windows"].append(s)
        c["labels"].append(label)
        c["subject"].append(self.a.subject)
        c["session"].append(self.session)
        c["window_id"].append(p["window_id"])
        c["overruns"].append(p["overruns"])
        c["model_hash"].append(p["model_hash"])
        c["dev_flags"].append(p["flags"])
        c["dev_class"].append(p["class_id"])
        c["dev_conf"].append(p["conf"])
        c["events"].append(p["events"])
        self.stored += 1
        self.in_step += 1
        self.per_label[label] = self.per_label.get(label, 0) + 1
        if not self.a.quiet:
            dev = "%d/%d" % (p["class_id"], p["conf"]) if p["flags"] & 1 else "-"
            if self.a.plan:
                print("[%s %d/%d]" % (LABELS[label].upper(), self.in_step, n))
            print("#%d %s id=%d peakL1=%d overruns=%d dev=%s" % (
                self.stored - 1, LABELS[label], p["window_id"], peak_l1(s), p["overruns"], dev), flush=True)
        self.write()
        if n and self.in_step >= n:
            self.step_i += 1
            self.in_step = 0
            if not self.done:
                self.announce_next()

    def drain_enter(self):
        """Throw away Enter presses already queued, so a stray Enter typed during a step cannot start the next one."""
        if self.q is not None:
            try:
                while True:
                    self.q.get_nowait()
            except queue.Empty:
                pass

    def announce_next(self):
        """After a finished step: print NEXT and wait for Enter unless --no-pause."""
        if self.a.plan:
            self.announce()
            if not self.a.no_pause:
                self.drain_enter()
                self.waiting = True

    def counters(self):
        """Decoder counters plus stored, rejected, skipped, as a dict."""
        d = self.dec
        return {"garbage": d.garbage, "bad_header": d.bad_header, "crc_errors": d.crc_errors, "frames": d.frames,
                "seq_gaps": d.seq_gaps, "stored": self.stored, "rejected": self.rejected, "skipped": self.skipped}

    def write(self):
        """Rewrite the output file atomically with everything stored so far."""
        arrays = {}
        for k, dt in OUT_KEYS:
            if k == "windows":
                new = np.array(self.cols[k], dtype=dt).reshape(-1, 150, 3)
            else:
                new = np.array(self.cols[k], dtype=dt)
            arrays[k] = np.concatenate([self.old[k], new]) if self.old is not None else new
        syn = max(self.old_syn, 1 if self.a.synthetic else 0)
        sess = list(self.old_meta.get("sessions", [])) if self.old is not None else []
        sess.append({"started": self.started, "source": self.a.port or self.a.input, "subject": self.a.subject,
                     "session": self.session, "stored": self.stored, "counters": self.counters()})
        meta = {"tool": "recorder.py", "version": TOOL_VERSION, "started": self.started,
                "source": self.a.port or self.a.input, "hello": self.hello, "counters": self.counters(),
                "label_names": list(LABELS), "sessions": sess}
        write_npz(self.a.out, arrays, syn, meta)

    def summary(self):
        """Print the end-of-run summary."""
        print("stored %d windows: %s" % (self.stored, ", ".join(
            "%s=%d" % (LABELS[k], v) for k, v in sorted(self.per_label.items())) or "-"))
        c = self.counters()
        print("rejected %d, skipped %d, frames %d, garbage bytes %d, bad_header %d, crc_errors %d, SEQ gaps %d" % (
            c["rejected"], c["skipped"], c["frames"], c["garbage"], c["bad_header"], c["crc_errors"], c["seq_gaps"]))
        if self.a.plan and not self.done:
            print("warning: plan not finished (step %d of %d)" % (self.step_i + 1, len(self.steps)))
        if self.dec.text_lines:
            print("device text: %s" % " | ".join(self.dec.text_lines[:5]))


def parse_plan(s):
    """Parse "label:count,label:count" into [(label_id, count)]; raises ValueError."""
    steps = []
    for part in s.split(","):
        name, _, n = part.strip().rpartition(":")
        if not name or not n.isdigit() or int(n) < 1:
            raise ValueError("bad plan step %r (expected LABEL:COUNT with COUNT >= 1)" % part)
        steps.append((parse_label(name), int(n)))
    if not steps:
        raise ValueError("empty plan")
    return steps


def build_parser():
    ap = argparse.ArgumentParser(description="Record labelled C2 windows into a training .npz")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--port")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--input", help="raw byte file, '-' = stdin")
    ap.add_argument("--out")
    ap.add_argument("--label")
    ap.add_argument("--count", type=int, default=0)
    ap.add_argument("--plan")
    ap.add_argument("--subject", type=int, default=0)
    ap.add_argument("--session", type=int, default=None)
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--no-pause", action="store_true")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--raw-log")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--samples", action="store_true", help="continuous SAMPLES recording (stream file, see RECORDING.md)")
    ap.add_argument("--every", type=float, default=2.5, help="--samples: seconds between GO marks")
    ap.add_argument("--marks-from", help="--samples, TEST ONLY: take the marks from a fake_wand --marks-out file")
    return ap


def run(args):
    """Run one recording session. Returns the exit code; raises Fatal for errors."""
    if bool(args.port) == bool(args.input):
        raise Fatal(2, "give exactly one of --port / --input")
    if not args.out:
        raise Fatal(2, "--out is required")
    if bool(args.label) == bool(args.plan):
        raise Fatal(2, "give exactly one of --label / --plan")
    if args.plan and args.count:
        raise Fatal(2, "--count is for --label; a plan has its own counts")
    if not (0 <= args.subject <= 255) or (args.session is not None and not 0 <= args.session <= 65535):
        raise Fatal(2, "--subject must be 0..255 and --session 0..65535")
    if args.input == "-" and args.plan and not args.no_pause:
        raise Fatal(2, "--input - needs --no-pause with --plan")
    try:
        steps = parse_plan(args.plan) if args.plan else [(parse_label(args.label), max(0, args.count))]
    except ValueError as e:
        raise Fatal(2, str(e))
    exists = os.path.exists(args.out)
    if exists and not args.append:
        raise Fatal(2, "%s exists; use --append or another --out" % args.out)
    if args.append and not exists:
        raise Fatal(2, "--append: %s does not exist" % args.out)
    rec = Recorder(args, steps, live=bool(args.port))
    if args.append:
        rec.setup_append()
    elif rec.session is None:
        rec.session = 0
    src = read_serial(args.port, args.baud) if args.port else read_file(args.input)
    logpath = args.raw_log or (os.path.splitext(args.out)[0] + ".bin")
    logger = LazyLog(logpath, None if (args.input and args.input != "-" and
                                       os.path.realpath(args.input) == os.path.realpath(logpath)) else True)
    code = 0
    hinted = []
    try:
        rec.start_plan()
        for chunk in src:
            if chunk is None:
                frames = rec.dec.flush_stale()
                rec.poll_enter()
            else:
                logger.write(chunk)
                frames = rec.dec.feed(chunk)
            for f in frames:
                rec.on_frame(f)
            rec.poll_enter()
            hello_hint(rec, hinted)
            if rec.done:
                break
    except KeyboardInterrupt:
        print("\ninterrupted; output so far is kept", file=sys.stderr)
    except OSError as e:
        if not args.port:
            raise Fatal(2, "read error: %s" % e)
        print("serial device lost (%s); keeping what was stored" % e, file=sys.stderr)
    except Fatal as e:
        code = e.code
        print("error: %s" % e, file=sys.stderr)
    finally:
        src.close()
        logger.close()
    if rec.stored > 0 or args.append:
        rec.write()
    rec.summary()
    return code


# ----------------------------------------------------------------------------- continuous recording (W2-6)
# WORKING ASSUMPTION: open_questions Q1, Q2, not decided (SAMPLES stream; offline trigger cut, briefs/W2-6_spec.md V1).
STREAM_VERSION = 1
MARK_LAG = 16                    # samples added to a wall-clock mark: the PC sees a sample up to one 16-sample chunk after the
                                 # wand took it, so the index of the last received sample lags what the user sees at GO
STALL_S = 1.0                    # no chunk for this long = the wand stalled; GO marks pause
STREAM_WRITE_EVERY = 16          # chunks between atomic rewrites of the stream file


def check_hello(h):
    """Check a parsed HELLO against the fixed C0/C1.5 values; raises Fatal(3) naming the first wrong field."""
    for k, want in (("proto_ver", 1), ("odr_hz", 100), ("range_g", 4), ("n_samples", 150), ("pre_trig", 15)):
        if h[k] != want:
            raise Fatal(3, "HELLO mismatch: %s = %d, expected %d" % (k, h[k], want))


class StreamRecorder:
    """Continuous SAMPLES recorder: keeps every sample, chunk gaps, OVR lines and time-based label marks."""

    def __init__(self, args, steps, live, marks_from=None):
        """Args: args (namespace); steps: [(label_id, count; 0 = unbounded)] or [];
        live: serial source; marks_from: list of [sample, label] replacing the wall-clock marks (tests)."""
        self.a = args
        self.steps = steps
        self.live = live
        self.marks_from = marks_from
        self.dec = c2_proto.Decoder(accept_samples=True)
        self.hello = None
        self.chunks = []         # list of int16 [16,3]
        self.m = 0               # samples stored
        self.last_chunk = None
        self.gaps = []           # [sample index, chunks lost]
        self.ovr = []            # sample index of each OVR line
        self.marks = []          # [sample index, label]
        self.rejected = 0
        self.nlines = 0
        self.nchunks = 0
        self.step_i = 0
        self.go_n = 0            # GOs given in the current step
        self.next_go = None      # monotonic time of the next GO
        self.last_chunk_t = None # monotonic time of the last stored chunk
        self.stalled = False
        self.stall_t = 0.0
        self.finish_at = None
        self.waiting = False
        self.q = None
        self.started = datetime.datetime.now().isoformat(timespec="seconds")

    @property
    def done(self):
        """True when the plan is finished and the last gesture had its time."""
        if self.marks_from is not None:
            return False
        return bool(self.steps) and self.step_i >= len(self.steps) and time.monotonic() >= (self.finish_at or 0)

    def start(self):
        """Begin the plan (print the first NEXT; wait for Enter unless --no-pause). With --marks-from: load marks."""
        if self.marks_from is not None:
            self.marks = [list(m) for m in self.marks_from]
            return
        self._begin_step()

    def _begin_step(self):
        label, n = self.steps[self.step_i]
        print("NEXT: %s x%s  (press Enter to start)" % (LABELS[label].upper(), n or "unlimited"), flush=True)
        self.go_n = 0
        if self.a.no_pause:
            self.next_go = time.monotonic() + self.a.every
        else:
            self.drain_enter()
            self.waiting = True
            self.next_go = None
            if self.live and self.q is None:
                self.q = queue.Queue()
                threading.Thread(target=self._stdin_loop, daemon=True).start()

    def _stdin_loop(self):
        while True:
            line = sys.stdin.readline()
            self.q.put(line if line else None)
            if not line:
                return

    def drain_enter(self):
        """Throw away queued Enter presses when entering an Enter-wait (F1)."""
        if self.q is not None:
            try:
                while True:
                    self.q.get_nowait()
            except queue.Empty:
                pass

    def tick(self):
        """Advance the wall-clock plan: handle Enter, emit GO marks. Call after every chunk and idle period."""
        if self.marks_from is not None or not self.steps or self.step_i >= len(self.steps):
            return
        now = time.monotonic()
        ready = self.hello is not None and self.last_chunk_t is not None and now - self.last_chunk_t <= STALL_S
        if not ready:                                           # no HELLO yet or the wand went quiet: pause the plan
            if not self.stalled:
                self.stalled = True
                self.stall_t = now
                print("waiting for wand", flush=True)
            return
        if self.stalled:                                        # resume the step where it paused
            self.stalled = False
            dt = now - self.stall_t
            if self.next_go is not None:
                self.next_go += dt
            if self.finish_at:
                self.finish_at += dt
        if self.waiting:
            if self.live:
                try:
                    line = self.q.get_nowait()
                except queue.Empty:
                    return
            else:
                line = sys.stdin.readline()
                line = line if line else None
            self.waiting = False
            if line is None:                                    # stdin closed: stop
                self.step_i = len(self.steps)
                self.finish_at = 0
                return
            self.next_go = time.monotonic() + self.a.every
        if self.next_go is not None and time.monotonic() >= self.next_go:
            label, n = self.steps[self.step_i]
            self.go_n += 1
            self.marks.append([self.m + MARK_LAG, label])
            print("GO %d/%s" % (self.go_n, n or "-"), flush=True)
            self.next_go += self.a.every
            if n and self.go_n >= n:
                self.step_i += 1
                self.finish_at = self.next_go                   # leave time for the last gesture
                if self.step_i < len(self.steps):
                    self._begin_step()

    def on_frame(self, f):
        """Handle one decoded frame: HELLO (checked) or SAMPLES chunk (gap detection)."""
        if f.ftype == c2_proto.T_HELLO:
            h = c2_proto.parse_hello(f.payload)
            self.hello = h
            check_hello(h)
            if h["feature_ver"] != features_ref.FEATURES_VERSION:
                print("warning: wand feature_ver %d != tools/features_ref.FEATURES_VERSION %d"
                      % (h["feature_ver"], features_ref.FEATURES_VERSION), file=sys.stderr)
        elif f.ftype == c2_proto.T_SAMPLES:
            p = c2_proto.parse_samples(f.payload)
            if self.hello is None or p["n"] != 16:
                self.rejected += 1
                return
            s = np.array(p["samples"], dtype=np.int16)
            if s.min() < -2048 or s.max() > 2047:
                self.rejected += 1
                return
            if self.last_chunk is not None:
                lost = (p["chunk"] - self.last_chunk - 1) & 0xFFFF
                if lost:
                    self.gaps.append([self.m, lost])
            self.last_chunk = p["chunk"]
            self.chunks.append(s)
            self.last_chunk_t = time.monotonic()
            self.m += 16
            self.nchunks += 1
            if self.nchunks % STREAM_WRITE_EVERY == 0:
                self.write()

    def feed(self, data):
        """Feed bytes one at a time so an OVR text line gets the exact sample index; handles the frames."""
        for b in data:
            for f in self.dec.feed(bytes((b,))):
                self.on_frame(f)
            self._lines()

    def idle(self):
        """No byte for 50 ms: apply the PC-side stale rule."""
        for f in self.dec.flush_stale():
            self.on_frame(f)
        self._lines()

    def _lines(self):
        tl = self.dec.text_lines
        while self.nlines < len(tl):
            t = tl[self.nlines].strip()
            self.nlines += 1
            if t.startswith("OVR ") or t == "OVR":
                self.ovr.append(self.m)

    def counters(self):
        """Decoder counters plus rejected and the sample count, as a dict."""
        d = self.dec
        return {"garbage": d.garbage, "bad_header": d.bad_header, "crc_errors": d.crc_errors, "frames": d.frames,
                "seq_gaps": d.seq_gaps, "rejected": self.rejected, "samples": self.m, "chunks": self.nchunks}

    def write(self):
        """Rewrite the stream file atomically."""
        smp = np.concatenate(self.chunks).astype(np.int16) if self.chunks else np.zeros((0, 3), np.int16)
        marks = [[min(mk[0], self.m), mk[1]] for mk in self.marks if self.marks_from is None or mk[0] <= self.m]   # a lagged mark past the stream end is clamped to it
        arrays = {"samples": smp,
                  "chunk_gaps": np.array(self.gaps, dtype=np.int32).reshape(-1, 2),
                  "ovr": np.array(self.ovr, dtype=np.int32),
                  "marks": np.array(marks, dtype=np.int32).reshape(-1, 2),
                  "subject": np.uint8(self.a.subject), "session": np.uint16(self.a.session or 0)}
        meta = {"tool": "recorder.py", "version": STREAM_VERSION, "mode": "samples", "started": self.started,
                "source": self.a.port or self.a.input, "hello": self.hello, "counters": self.counters(),
                "label_names": list(LABELS), "marks_from": self.a.marks_from}
        write_npz(self.a.out, arrays, 1 if self.a.synthetic else 0, meta)

    def summary(self):
        """Print the end-of-run summary."""
        c = self.counters()
        per = {}
        for _, lab in self.marks:
            per[lab] = per.get(lab, 0) + 1
        print("stream: %d samples (%d chunks), %d gaps, %d OVR lines, %d marks: %s" % (
            self.m, self.nchunks, len(self.gaps), len(self.ovr), len(self.marks),
            ", ".join("%s=%d" % (LABELS[k], v) for k, v in sorted(per.items())) or "-"))
        print("rejected %d, frames %d, garbage bytes %d, bad_header %d, crc_errors %d, SEQ gaps %d" % (
            c["rejected"], c["frames"], c["garbage"], c["bad_header"], c["crc_errors"], c["seq_gaps"]))


def run_samples(args):
    """Run one continuous (--samples) recording session.

    Args:
        args: argparse namespace of build_parser().
    Returns:
        exit code (0 ok, 3 HELLO mismatch); raises Fatal(2) for bad arguments.
    """
    if bool(args.port) == bool(args.input):
        raise Fatal(2, "give exactly one of --port / --input")
    if not args.out:
        raise Fatal(2, "--out is required")
    if args.append:
        raise Fatal(2, "--append cannot be used with --samples: a stream file is not appendable. Record each session to its "
                       "own stream file, cut each with cut_stream.py, then join the windows with dataset_tool.py merge")
    if args.every <= 0:
        raise Fatal(2, "--every must be > 0")
    if args.label and args.plan:
        raise Fatal(2, "give only one of --label / --plan")
    if args.count and args.plan:
        raise Fatal(2, "--count is for --label; a plan has its own counts")
    if not args.marks_from and not (args.label or args.plan):
        raise Fatal(2, "--samples needs --label or --plan (or --marks-from)")
    if not (0 <= args.subject <= 255) or (args.session is not None and not 0 <= args.session <= 65535):
        raise Fatal(2, "--subject must be 0..255 and --session 0..65535")
    if args.input == "-" and args.plan and not args.no_pause:
        raise Fatal(2, "--input - needs --no-pause with --plan")
    marks_from = None
    if args.marks_from:
        try:
            with open(args.marks_from) as f:
                marks_from = [[int(a), int(b)] for a, b in json.load(f)["marks"]]
        except (OSError, ValueError, KeyError, TypeError) as e:
            raise Fatal(2, "cannot read --marks-from %s: %s" % (args.marks_from, e))
        args.synthetic = True                                   # marks from a file are not real GO marks (W2-6F2 F1)
        print("warning: --marks-from is test only; the output is marked SYNTHETIC", file=sys.stderr)
    try:
        steps = ([] if marks_from is not None else
                 parse_plan(args.plan) if args.plan else [(parse_label(args.label), max(0, args.count))])
    except ValueError as e:
        raise Fatal(2, str(e))
    if os.path.exists(args.out):
        raise Fatal(2, "%s exists; use another --out" % args.out)
    rec = StreamRecorder(args, steps, live=bool(args.port), marks_from=marks_from)
    src = read_serial(args.port, args.baud) if args.port else read_file(args.input)
    logpath = args.raw_log or (os.path.splitext(args.out)[0] + ".bin")
    logger = LazyLog(logpath, None if (args.input and args.input != "-" and
                                       os.path.realpath(args.input) == os.path.realpath(logpath)) else True)
    code = 0
    hinted = []
    try:
        rec.start()
        for chunk in src:
            if chunk is None:
                rec.idle()
            else:
                logger.write(chunk)
                rec.feed(chunk)
            rec.tick()
            hello_hint(rec, hinted)
            if rec.done:
                break
    except KeyboardInterrupt:
        print("\ninterrupted; output so far is kept", file=sys.stderr)
    except OSError as e:
        if not args.port:
            raise Fatal(2, "read error: %s" % e)
        print("serial device lost (%s); keeping what was stored" % e, file=sys.stderr)
    except Fatal as e:
        code = e.code
        print("error: %s" % e, file=sys.stderr)
    finally:
        src.close()
        logger.close()
    if rec.nchunks > 0:
        rec.write()
    rec.summary()
    return code


# ----------------------------------------------------------------------------- selftest
def _selftest():
    """Record from synthetic streams in a temp dir and check the results; returns failure strings."""
    fails = []

    def check(c, msg):
        if not c:
            fails.append(msg)

    rng = np.random.default_rng(4)
    w = rng.integers(-2048, 2048, size=(6, 150, 3)).astype(np.int16)
    me = os.path.abspath(__file__)
    with tempfile.TemporaryDirectory() as t:
        def run_rec(*a):
            return subprocess.run([sys.executable, me] + list(a), capture_output=True, text=True)

        parts = [b"GM_MODEL_HASH=0\n", c2_proto.encode_hello(0)]
        for i in range(6):
            fb = c2_proto.encode_window(i + 1, 100 + i, w[i], flags=1, class_id=-1, conf=9)
            if i == 2:
                bad = bytearray(fb)
                bad[50] ^= 1
                fb = bytes(bad)
            parts.append(fb)
        pre = c2_proto.encode_window(0, 5, w[0])                # window before HELLO would be rejected
        stream = pre + b"".join(parts)
        sp = os.path.join(t, "s.bin")
        open(sp, "wb").write(stream)
        out = os.path.join(t, "o.npz")
        r = run_rec("--input", sp, "--out", out, "--plan", "swipe_left:2,none:3", "--no-pause", "--quiet")
        check(r.returncode == 0, "run 1 rc %d %s" % (r.returncode, r.stderr))
        z = np.load(out)
        check(z["windows"].dtype == np.int16 and z["windows"].shape == (5, 150, 3), "shape")
        keep = [0, 1, 3, 4, 5]
        check(np.array_equal(z["windows"], w[keep]), "windows equal")
        check(z["labels"].tolist() == [2, 2, 0, 0, 0], "labels %s" % z["labels"].tolist())
        check(z["window_id"].tolist() == [100, 101, 103, 104, 105], "window_id")
        check(z["dev_class"].dtype == np.int8 and int(z["dev_class"][0]) == -1, "dev_class")
        m = json.loads(str(z["meta"]))
        check(m["counters"]["crc_errors"] == 1 and m["counters"]["rejected"] == 1, "counters %s" % m["counters"])
        check(int(z["synthetic"]) == 0, "synthetic 0")
        check(os.path.exists(os.path.join(t, "o.bin")), "raw log")
        r = run_rec("--input", sp, "--out", out, "--label", "none")
        check(r.returncode == 2, "existing OUT must exit 2, got %d" % r.returncode)
        r = run_rec("--input", sp, "--out", out, "--label", "thrust", "--count", "1", "--append", "--synthetic", "--quiet")
        check(r.returncode == 0, "append rc %d %s" % (r.returncode, r.stderr))
        z = np.load(out)
        check(len(z["labels"]) == 6 and int(z["labels"][-1]) == 8 and int(z["session"][-1]) == 1, "append")
        check(int(z["synthetic"]) == 1, "append synthetic max")
        check(len(json.loads(str(z["meta"]))["sessions"]) == 2, "sessions list")
        # HELLO mismatch -> exit 3
        sp2 = os.path.join(t, "bad.bin")
        open(sp2, "wb").write(c2_proto.encode_hello(0, odr_hz=50) + c2_proto.encode_window(1, 0, w[0]))
        r = run_rec("--input", sp2, "--out", os.path.join(t, "b.npz"), "--label", "none")
        check(r.returncode == 3 and "odr_hz" in r.stderr, "hello mismatch rc %d" % r.returncode)
        r = run_rec("--input", sp2, "--out", os.path.join(t, "c.npz"), "--label", "bogus")
        check(r.returncode == 2, "bad label rc 2")
        r = run_rec("--out", os.path.join(t, "d.npz"), "--label", "none")
        check(r.returncode == 2, "no source rc 2")
        # --samples: gap, OVR line, marks-from
        sm = rng.integers(-2048, 2048, size=(16 * 20, 3)).astype(np.int16)
        parts = [c2_proto.encode_hello(0)]
        for c in range(20):
            if c == 8:
                parts.append(b"OVR 3\n")
            if c in (5, 6):
                continue                                     # two lost chunks
            parts.append(c2_proto.encode_samples(1 + c, c, sm[16 * c:16 * c + 16]))
        sp3 = os.path.join(t, "s3.bin")
        open(sp3, "wb").write(b"".join(parts))
        mj = os.path.join(t, "m.json")
        json.dump({"marks": [[10, 1], [100, 2], [100000, 3]]}, open(mj, "w"))
        o3 = os.path.join(t, "st.npz")
        r = run_rec("--input", sp3, "--out", o3, "--samples", "--marks-from", mj, "--synthetic")
        check(r.returncode == 0, "samples rc %d %s" % (r.returncode, r.stderr))
        if r.returncode == 0:
            z = np.load(o3)
            keep = [c for c in range(20) if c not in (5, 6)]
            check(np.array_equal(z["samples"], np.concatenate([sm[16 * c:16 * c + 16] for c in keep])), "stream samples")
            check(z["chunk_gaps"].tolist() == [[80, 2]], "chunk_gaps %s" % z["chunk_gaps"].tolist())
            check(z["ovr"].tolist() == [96], "ovr %s" % z["ovr"].tolist())
            check(z["marks"].tolist() == [[10, 1], [100, 2]] and int(z["synthetic"]) == 1, "marks")
        r = run_rec("--input", sp3, "--out", os.path.join(t, "x.npz"), "--samples")
        check(r.returncode == 2, "samples without label rc 2")
    return fails


def main(argv=None):
    """CLI entry point. Returns the exit code."""
    args = build_parser().parse_args(argv)
    if args.selftest:
        fails = _selftest()
        if fails:
            print("recorder selftest FAIL: " + "; ".join(fails))
            return 1
        print("recorder selftest PASS")
        return 0
    try:
        return run_samples(args) if args.samples else run(args)
    except Fatal as e:
        print("error: %s" % e, file=sys.stderr)
        return e.code


if __name__ == "__main__":
    sys.exit(main())
# [END AI-GENERATED]
