// [AI-GENERATED: Claude Code]
/*
 * c2_stream.h - incremental C2 UART frame sender (TX pump), ticket T-c2tx.
 *
 * WORKING ASSUMPTION: open_questions Q1, not decided (C2 as proposed, fixed by S2-1F).
 *
 * Promoted from our own host spike docs/agent/hadi/spikes/uart/c2_frame.{h,c} (CRC nibble
 * table and the frame encoders) and docs/agent/hadi/spikes/uart/c2_ref.py (reference wire
 * format). Wire format: docs/agent/hadi/briefs/W2-4_spec.md S6. No code was borrowed from
 * outside the project.
 *
 * Frame: A5 5A | TYPE u8 | LEN u16 | SEQ u8 | payload | CRC16 u16, little-endian, CRC-16/IBM-3740
 * over TYPE..payload, low byte first. HELLO LEN 10, WINDOW LEN 914, SAMPLES LEN 99.
 *
 * This module only produces bytes; it never touches a UART register. It is pure: no globals
 * except const tables, no malloc, no float, no blocking. The caller owns a c2_tx_t, starts a
 * frame, then calls c2_tx_pump from the main loop with the room its UART queue has.
 */
#ifndef C2_STREAM_H
#define C2_STREAM_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/** Most bytes one c2_tx_pump call emits. */
#define C2_PUMP_MAX 32u

/** HELLO beacon contents (proto_ver is always 1 and is added by the sender). */
typedef struct {
    uint8_t  odr_hz;
    uint8_t  range_g;
    uint8_t  n_samples;
    uint8_t  pre_trig;
    uint8_t  feature_ver;
    uint32_t model_hash;
} c2_hello_t;

/** WINDOW metadata; window_id and n_samples (150) are added by the sender. */
typedef struct {
    uint8_t  trig_idx;
    uint16_t overruns;
    uint32_t model_hash;
    uint8_t  flags;
    int8_t   class_id;
    uint8_t  conf;
    uint8_t  events;
} c2_window_meta_t;

/** Sender state. Fields are private; they are visible only so tests can size it. */
typedef struct {
    uint16_t    crc;        /* running CRC of the frame in flight */
    uint16_t    pos;        /* next byte index within the frame (or text) */
    uint16_t    window_id;  /* id the NEXT window will get */
    uint16_t    chunk;      /* chunk counter the NEXT SAMPLES frame will get */
    const void *src;        /* caller buffer (rows) or text, read while pumping */
    uint8_t     kind;       /* 0 idle, 1 hello, 2 window, 3 samples, 4 text */
    uint8_t     seq;        /* SEQ the NEXT frame will get */
    uint8_t     release;    /* WINDOW finished and not yet taken */
    uint8_t     head[14];   /* snapshot of the leading payload bytes of the frame */
} c2_tx_t;

/**
 * CRC-16/IBM-3740 step (poly 0x1021, no reflection, xorout 0). Nibble table from the spike.
 * @param crc running CRC, start with 0xFFFF
 * @param p   bytes to add
 * @param n   number of bytes
 * @return the updated CRC
 */
uint16_t c2_crc16_update(uint16_t crc, const uint8_t *p, uint16_t n);

/**
 * Reset the sender: SEQ 0, window_id 0, chunk 0, idle, no release pending.
 * @param tx sender state (must not be NULL)
 */
void c2_tx_init(c2_tx_t *tx);

/**
 * Tell whether a frame or text is in flight.
 * @param tx sender state
 * @return true if c2_tx_pump still has bytes to produce
 */
bool c2_tx_busy(const c2_tx_t *tx);

/**
 * Start a HELLO frame (proto_ver 1, LEN 10). SEQ is assigned now.
 * @param tx sender state
 * @param h  HELLO fields, copied at once
 * @return true if started; false (nothing changes) if busy or a pointer is NULL
 */
bool c2_tx_start_hello(c2_tx_t *tx, const c2_hello_t *h);

/**
 * Start a WINDOW frame (LEN 914, n_samples 150). SEQ and window_id are assigned now, then
 * the window_id counter increments. Metadata is copied at once; the 150 rows are read
 * while pumping, so the caller must not change buf until c2_tx_take_release returns true.
 * @param tx  sender state
 * @param m   window metadata snapshot
 * @param buf 150 rows of (x, y, z) int16 samples
 * @return true if started; false (nothing changes) if busy or a pointer is NULL
 */
bool c2_tx_start_window(c2_tx_t *tx, const c2_window_meta_t *m, const int16_t (*buf)[3]);

/**
 * Start a bring-up SAMPLES frame (type 0x04, LEN 99): chunk u16, n u8 = 16, 16 rows.
 * The chunk counter increments. buf must stay unchanged until c2_tx_busy is false.
 * @param tx sender state
 * @param s  16 rows of (x, y, z) int16 samples
 * @return true if started; false (nothing changes) if busy or a pointer is NULL
 */
bool c2_tx_start_samples(c2_tx_t *tx, const int16_t (*s)[3]);

/**
 * Start ASCII text (C2 section 9), sent as raw bytes: no SEQ, no CRC. At most 255
 * characters, each 0x0A, 0x0D or 0x20..0x7E. An empty string is accepted and sends nothing.
 * The string must stay valid until c2_tx_busy is false.
 * @param tx sender state
 * @param s  NUL-terminated text
 * @return true if accepted; false (nothing changes) if busy, NULL, too long or has a bad character
 */
bool c2_tx_start_text(c2_tx_t *tx, const char *s);

/**
 * Produce the next bytes of the frame (or text) in flight. Never mixes two frames in one call.
 * When the last byte is written the sender is idle at once (and a WINDOW sets its release flag).
 * @param tx   sender state
 * @param out  destination
 * @param room free bytes in out; 0 returns 0
 * @return number of bytes written, at most min(room, C2_PUMP_MAX); 0 when idle
 */
uint8_t c2_tx_pump(c2_tx_t *tx, uint8_t *out, uint8_t room);

/**
 * Take the release flag: true exactly once after each WINDOW's last byte was pumped.
 * @param tx sender state
 * @return true if a WINDOW just finished (the caller may now reuse its buffer)
 */
bool c2_tx_take_release(c2_tx_t *tx);

/**
 * Peek the id the next WINDOW will get.
 * @param tx sender state
 * @return the window_id counter
 */
uint16_t c2_tx_window_id(const c2_tx_t *tx);

#endif /* C2_STREAM_H */
// [END AI-GENERATED]
