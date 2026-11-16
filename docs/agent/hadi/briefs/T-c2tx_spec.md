<!-- [AI-GENERATED: Claude Code] -->
# SPEC T-c2tx: C2 frame sender `firmware/src/c2_stream.{h,c}` (incremental TX pump)

WORKING ASSUMPTION: open_questions Q1 (C2 as proposed, fixed by S2-1F), not decided.
Promoted from the spike `docs/agent/hadi/spikes/uart/c2_frame.{h,c}` (CRC nibble table, encoders): cite it.
The wire format is `docs/agent/hadi/briefs/W2-4_spec.md` §S6 (verbatim C2 text) — read §S6 and §S7 there; they are
part of this spec. This module only produces bytes; it never touches a UART register (the PIC24 UART driver is a
separate, later ticket). It must be host-testable and pure: no globals except `const` tables.

## X1. API (`c2_stream.h`)
```c
#define C2_PUMP_MAX 32u          /* most bytes one c2_tx_pump call emits */
typedef struct { uint8_t odr_hz, range_g, n_samples, pre_trig, feature_ver; uint32_t model_hash; } c2_hello_t;
typedef struct { uint8_t trig_idx; uint16_t overruns; uint32_t model_hash; uint8_t flags; int8_t class_id;
                 uint8_t conf; uint8_t events; } c2_window_meta_t;     /* window_id and n_samples are added by the sender */
typedef struct { ...private but visible for tests... } c2_tx_t;
uint16_t c2_crc16_update(uint16_t crc, const uint8_t *p, uint16_t n);   /* CRC-16/IBM-3740 step; start 0xFFFF */
void     c2_tx_init(c2_tx_t *tx);                                       /* seq 0, window_id 0, chunk 0, idle */
bool     c2_tx_busy(const c2_tx_t *tx);                                 /* a frame or text is in flight */
bool     c2_tx_start_hello(c2_tx_t *tx, const c2_hello_t *h);           /* false (nothing changes) if busy or NULL */
bool     c2_tx_start_window(c2_tx_t *tx, const c2_window_meta_t *m, const int16_t (*buf)[3]); /* 150 rows */
bool     c2_tx_start_samples(c2_tx_t *tx, const int16_t (*s)[3]);      /* 16 rows, bring-up SAMPLES frame */
bool     c2_tx_start_text(c2_tx_t *tx, const char *s);                  /* ASCII text between frames */
uint8_t  c2_tx_pump(c2_tx_t *tx, uint8_t *out, uint8_t room);           /* returns n <= min(room, C2_PUMP_MAX) */
bool     c2_tx_take_release(c2_tx_t *tx);                               /* true once per WINDOW, after its last byte */
uint16_t c2_tx_window_id(const c2_tx_t *tx);                            /* id the NEXT window will get */
```
## X2. Behaviour
- `c2_tx_start_*` return false and change nothing when busy or when any pointer is NULL. On success the frame is
  "in flight": SEQ is assigned now (C2 §8 / proposal §3.5 rule 4: SEQ at frame start), `proto_ver` = 1 in HELLO, LEN is
  the type's single legal value (10 / 914 / 99), all WINDOW metadata is copied into the sender at start (snapshot),
  `window_id` = the current counter, then the counter increments (wraps at 65536); `n_samples` = 150. SAMPLES uses the
  internal `chunk` counter the same way (wraps at 65536), `n` = 16.
- The WINDOW samples and SAMPLES rows are read from the caller's buffer **while pumping** (no 922 B copy). The caller
  must not change the buffer until `c2_tx_take_release` returned true (WINDOW) or `c2_tx_busy` is false (SAMPLES).
- Each int16 is sent low byte then high byte, two's complement; rows `buf[0][0], buf[0][1], buf[0][2], buf[1][0], ...`.
- The CRC is computed incrementally over TYPE, LEN, SEQ and payload as bytes are produced; CRC low byte first.
- `c2_tx_pump` with `room == 0` or when idle returns 0. Otherwise it writes up to `min(room, C2_PUMP_MAX)` bytes of the
  frame in flight to `out` and returns the count. When the last byte of a frame is written the sender becomes idle in
  the same call (so `c2_tx_busy` is false right after) and, for a WINDOW, the release flag is set; a pump call never
  writes bytes of two different frames. A WINDOW therefore needs at least ceil(922/32) = 29 calls.
- `c2_tx_take_release` returns true exactly once after each WINDOW's last byte, then false until the next WINDOW ends.
- Text (C2 §9): `c2_tx_start_text` accepts a NUL-terminated string of at most 255 characters, each 0x0A, 0x0D or
  0x20..0x7E; otherwise it returns false and nothing is sent. Text bytes are pumped like a frame (no SEQ, no CRC,
  never interleaved with a frame). The caller's string must stay valid until `c2_tx_busy` is false.
- Fixed-width types, C99, no float, no malloc, no blocking; builds with the repo's host flags and avr-gcc sim16 flags
  (`firmware/test/common.mk`: `-Wall -Wextra -Wconversion -Werror -pedantic`). `sizeof(c2_tx_t)` <= 40 B on avr
  (proposal §3.6: about 30 to 32 B of sender state). CRC table: the spike's 16-entry nibble table (32 B, `const`).
- Every public function has a doc comment (purpose, each argument, return value).
<!-- [END AI-GENERATED] -->
