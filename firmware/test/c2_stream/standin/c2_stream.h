// [AI-GENERATED: Claude Code]
/*
 * c2_stream.h - STAND-IN written by the tester from the spec (T-c2tx_spec.md X1-X2) only, to prove
 * the c2_stream suite harness. It is not the firmware implementation.
 */
#ifndef C2_STREAM_H
#define C2_STREAM_H

#include <stdbool.h>
#include <stdint.h>

#define C2_PUMP_MAX 32u /* most bytes one c2_tx_pump call emits */

typedef struct { uint8_t odr_hz, range_g, n_samples, pre_trig, feature_ver; uint32_t model_hash; } c2_hello_t;
typedef struct { uint8_t trig_idx; uint16_t overruns; uint32_t model_hash; uint8_t flags; int8_t class_id;
                 uint8_t conf; uint8_t events; } c2_window_meta_t;

typedef struct {
    const int16_t (*rows)[3];  /* caller's samples, read while pumping */
    const char *text;          /* caller's text */
    uint16_t pos, len, crc;    /* byte position, total bytes, running CRC */
    uint16_t wid, chunk;       /* counters for the NEXT WINDOW / SAMPLES */
    uint8_t seq, type, release;
    uint8_t pl[14];            /* payload prefix (metadata snapshot) */
} c2_tx_t;

/** CRC-16/IBM-3740 step. @param crc Running value (start 0xFFFF). @param p Bytes. @param n Count.
 * @return Updated CRC. */
uint16_t c2_crc16_update(uint16_t crc, const uint8_t *p, uint16_t n);
/** Reset the sender (seq 0, ids 0, idle). @param tx Sender. @return None. */
void c2_tx_init(c2_tx_t *tx);
/** @param tx Sender. @return true while a frame or text is in flight. */
bool c2_tx_busy(const c2_tx_t *tx);
/** Start a HELLO. @param tx Sender. @param h Fields. @return false if busy or NULL. */
bool c2_tx_start_hello(c2_tx_t *tx, const c2_hello_t *h);
/** Start a WINDOW. @param tx Sender. @param m Metadata. @param buf 150 rows. @return false if busy or NULL. */
bool c2_tx_start_window(c2_tx_t *tx, const c2_window_meta_t *m, const int16_t (*buf)[3]);
/** Start a SAMPLES. @param tx Sender. @param s 16 rows. @return false if busy or NULL. */
bool c2_tx_start_samples(c2_tx_t *tx, const int16_t (*s)[3]);
/** Start text. @param tx Sender. @param s NUL-terminated string. @return false if busy, NULL or invalid. */
bool c2_tx_start_text(c2_tx_t *tx, const char *s);
/** Emit bytes. @param tx Sender. @param out Buffer. @param room Its size. @return Bytes written. */
uint8_t c2_tx_pump(c2_tx_t *tx, uint8_t *out, uint8_t room);
/** @param tx Sender. @return true once per WINDOW after its last byte. */
bool c2_tx_take_release(c2_tx_t *tx);
/** @param tx Sender. @return The id the next WINDOW gets. */
uint16_t c2_tx_window_id(const c2_tx_t *tx);

#endif
// [END AI-GENERATED]
