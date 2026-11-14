# [AI-GENERATED: Claude Code]
"""C2 UART raw-stream reference: encoder and streaming decoder (host spike, ticket S2-1).

Wire format (little-endian):
    [0xA5][0x5A][TYPE u8][LEN u16][SEQ u8][PAYLOAD LEN bytes][CRC16 u16]
CRC-16/IBM-3740 (poly 0x1021, init 0xFFFF, refin/refout false, xorout 0, check 0x29B1) over
TYPE, LEN, SEQ and PAYLOAD. Catalogue: Greg Cook, "Catalogue of parametrised CRC algorithms",
https://reveng.sourceforge.io/crc-catalogue/16.htm (alias CRC-16/CCITT-FALSE; recalled from
memory, check value asserted by test_c2.py). The CRC below is the plain bitwise form.
"""
import struct

SYNC0, SYNC1 = 0xA5, 0x5A
HEADER_LEN = 6
CRC_LEN = 2
PROTO_VERSION = 1
TYPE_HELLO, TYPE_WINDOW = 0x01, 0x02          # the only types a v1 decoder accepts
TYPE_RESULT = 0x03     # reserved, wand -> PC: test-vector results (proposal 3.8)
TYPE_SAMPLES = 0x04    # reserved, wand -> PC: bring-up sample chunk (proposal 3.10); never in the demo build
TYPE_CMD, TYPE_VECTOR = 0x10, 0x11   # reserved, PC -> wand (proposal 3.7, 3.8)
N_SAMPLES, N_AXES = 150, 3
HELLO_PAYLOAD_LEN = 10
WINDOW_META_LEN = 14
WINDOW_PAYLOAD_LEN = WINDOW_META_LEN + 2 * N_SAMPLES * N_AXES   # 914
FLAG_RESULT_VALID = 0x01
SAMPLES_N = 16                                    # bring-up chunk: fixed 16 samples, so LEN is single-valued
SAMPLES_PAYLOAD_LEN = 2 + 1 + 2 * SAMPLES_N * N_AXES   # chunk u16, n u8, n x 3 x int16 = 99
# A v1 decoder knows ONLY these types, each with exactly one legal length. Any other TYPE
# (reserved, unknown, 0 or above 0x0F) or any other LEN is a bad header: drop one byte, rescan.
KNOWN_LEN = {TYPE_HELLO: HELLO_PAYLOAD_LEN, TYPE_WINDOW: WINDOW_PAYLOAD_LEN}


def crc16(data, crc=0xFFFF):
    """CRC-16/IBM-3740, bitwise.

    Args:
        data: bytes-like to checksum.
        crc: running CRC (0xFFFF to start a message).
    Returns:
        The updated 16-bit CRC.
    """
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _frame(ftype, seq, payload):
    """Wrap a payload in sync, header and CRC.

    Args:
        ftype: frame type byte.
        seq: sequence number (taken modulo 256).
        payload: payload bytes.
    Returns:
        The complete frame as bytes.
    """
    body = struct.pack("<BHB", ftype, len(payload), seq & 0xFF) + payload
    return bytes((SYNC0, SYNC1)) + body + struct.pack("<H", crc16(body))


def encode_window(seq, meta, samples):
    """Encode a WINDOW frame.

    Args:
        seq: sequence number.
        meta: dict with window_id, trig_idx, overruns, model_hash, flags, class_id, conf, events.
        samples: 150 rows of (x, y, z) int16 values.
    Returns:
        The frame bytes (922 bytes).
    """
    assert len(samples) == N_SAMPLES
    payload = struct.pack("<HBBHIBbBB", meta["window_id"], N_SAMPLES, meta["trig_idx"],
                          meta["overruns"], meta["model_hash"], meta["flags"],
                          meta["class_id"], meta["conf"], meta["events"])
    payload += struct.pack("<%dh" % (N_SAMPLES * N_AXES), *[v for row in samples for v in row])
    return _frame(TYPE_WINDOW, seq, payload)


def encode_hello(seq, h):
    """Encode a HELLO frame.

    Args:
        seq: sequence number.
        h: dict with proto_ver, odr_hz, range_g, n_samples, pre_trig, feature_ver, model_hash.
    Returns:
        The frame bytes (18 bytes).
    """
    payload = struct.pack("<BBBBBBI", h["proto_ver"], h["odr_hz"], h["range_g"], h["n_samples"],
                          h["pre_trig"], h["feature_ver"], h["model_hash"])
    return _frame(TYPE_HELLO, seq, payload)


def parse_payload(ftype, payload):
    """Decode a validated payload into a dict.

    Args:
        ftype: frame type.
        payload: payload bytes.
    Returns:
        dict of fields (WINDOW also has "samples": list of (x, y, z)), or None for unknown types.
    """
    if ftype == TYPE_WINDOW:
        (wid, n, trig, ovr, mh, flags, cls, conf, ev) = struct.unpack_from("<HBBHIBbBB", payload)
        flat = struct.unpack_from("<%dh" % (N_SAMPLES * N_AXES), payload, WINDOW_META_LEN)
        return {"window_id": wid, "n_samples": n, "trig_idx": trig, "overruns": ovr,
                "model_hash": mh, "flags": flags, "class_id": cls, "conf": conf, "events": ev,
                "samples": [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]}
    if ftype == TYPE_HELLO:
        keys = ("proto_ver", "odr_hz", "range_g", "n_samples", "pre_trig", "feature_ver", "model_hash")
        return dict(zip(keys, struct.unpack("<BBBBBBI", payload)))
    return None


class Decoder:
    """Streaming, byte-at-a-time frame parser with resynchronisation.

    Strategy: keep the unconsumed bytes. Look for the two sync bytes at the front; read the
    header; reject at once any TYPE that is not in the known table (v1: 0x01 HELLO, 0x02 WINDOW)
    and any LEN that is not the single legal value for that TYPE, which keeps false sync
    candidates from stalling the stream (a candidate with a known TYPE and a legal LEN waits for
    at most one frame's worth of bytes); wait for the whole frame; check the CRC. On any failure drop exactly ONE byte and rescan
    what is already buffered, so a fake sync inside garbage (or inside a damaged frame) can
    never swallow a good frame that follows it.

    Attributes (counters): garbage (bytes skipped outside a frame), bad_header, crc_errors,
    seq_gaps (frames missing according to the SEQ byte), frames (accepted).
    """

    def __init__(self, extra_types=None):
        """Create an empty decoder.

        Args:
            extra_types: optional dict {type: legal LEN} that extends the known table, for a
                bring-up tool that also reads SAMPLES chunks ({TYPE_SAMPLES: SAMPLES_PAYLOAD_LEN}).
                None (the default) is the v1 decoder: HELLO and WINDOW only.
        """
        self.known = dict(KNOWN_LEN)
        if extra_types:
            self.known.update(extra_types)
        self.buf = bytearray()
        self.garbage = self.bad_header = self.crc_errors = self.seq_gaps = self.frames = 0
        self._last_seq = None

    def feed(self, data):
        """Feed bytes; return the frames completed by them.

        Args:
            data: bytes-like, any length (including one byte at a time).
        Returns:
            List of (type, seq, payload_bytes) tuples, in arrival order.
        """
        out = []
        for b in data:
            self.buf.append(b)
            out.extend(self._scan())
        return out

    def _scan(self):
        """Consume as many complete frames as the buffer holds.

        Returns:
            List of (type, seq, payload_bytes) tuples.
        """
        out = []
        buf = self.buf
        while buf:
            if buf[0] != SYNC0:
                del buf[0]
                self.garbage += 1
                continue
            if len(buf) < 2:
                break
            if buf[1] != SYNC1:
                del buf[0]
                self.garbage += 1
                continue
            if len(buf) < HEADER_LEN:
                break
            ftype, ln, seq = struct.unpack_from("<BHB", buf, 2)
            if self.known.get(ftype) != ln:      # unknown TYPE (None) or wrong LEN for a known TYPE
                del buf[0]
                self.bad_header += 1
                continue
            total = HEADER_LEN + ln + CRC_LEN
            if len(buf) < total:
                break
            (rx_crc,) = struct.unpack_from("<H", buf, total - CRC_LEN)
            if crc16(buf[2:total - CRC_LEN]) != rx_crc:
                del buf[0]
                self.crc_errors += 1
                continue
            payload = bytes(buf[HEADER_LEN:HEADER_LEN + ln])
            del buf[:total]
            if self._last_seq is not None:
                self.seq_gaps += (seq - self._last_seq - 1) & 0xFF
            self._last_seq = seq
            self.frames += 1
            out.append((ftype, seq, payload))
        return out
# [END AI-GENERATED]
