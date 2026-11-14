// [AI-GENERATED: Claude Code]
/*
 * c2_frame.h - C2 UART raw-stream framing, host spike (ticket S2-1).
 *
 * PROPOSAL ONLY (docs/agent/hadi/proposals/C2_uart_stream.md). C99, fixed-width types,
 * no float, no malloc, no blocking. XC16 has a 16-bit int, so every shift and sum below
 * is done on an explicitly sized unsigned type.
 *
 * Wire format (all multi-byte fields little-endian, which is PIC24 native order):
 *   [0xA5][0x5A][TYPE u8][LEN u16][SEQ u8][PAYLOAD LEN bytes][CRC16 u16]
 * CRC covers TYPE, LEN, SEQ and PAYLOAD (not the sync bytes), sent low byte first.
 * CRC-16/IBM-3740: poly 0x1021, init 0xFFFF, refin false, refout false, xorout 0x0000,
 * check("123456789") = 0x29B1. Catalogue: Greg Cook, "Catalogue of parametrised CRC
 * algorithms", https://reveng.sourceforge.io/crc-catalogue/16.htm (alias CRC-16/CCITT-FALSE;
 * entry recalled from memory and the check value is asserted by `make test`; the page
 * itself was not re-read in this session).
 */
#ifndef C2_FRAME_H
#define C2_FRAME_H

#include <stdint.h>
#include <stddef.h>

#define C2_SYNC0            0xA5u   /* first sync byte  */
#define C2_SYNC1            0x5Au   /* second sync byte */
#define C2_HEADER_LEN       6u      /* SYNC0 SYNC1 TYPE LEN(2) SEQ */
#define C2_CRC_LEN          2u
#define C2_PROTO_VERSION    1u

#define C2_TYPE_HELLO       0x01u   /* wand -> PC: capabilities and model hash   */
#define C2_TYPE_WINDOW      0x02u   /* wand -> PC: one 150-sample capture window */

#define C2_N_SAMPLES        150u
#define C2_N_AXES           3u

#define C2_HELLO_PAYLOAD_LEN   10u
#define C2_HELLO_FRAME_LEN     (C2_HEADER_LEN + C2_HELLO_PAYLOAD_LEN + C2_CRC_LEN)   /* 18  */
#define C2_WINDOW_META_LEN     14u
#define C2_WINDOW_PAYLOAD_LEN  (C2_WINDOW_META_LEN + 2u * C2_N_SAMPLES * C2_N_AXES)  /* 914 */
#define C2_WINDOW_FRAME_LEN    (C2_HEADER_LEN + C2_WINDOW_PAYLOAD_LEN + C2_CRC_LEN)  /* 922 */

#define C2_FLAG_RESULT_VALID   0x01u   /* class_id/conf/events carry an on-device result */

/* Window metadata (the first 14 payload bytes). */
typedef struct {
    uint16_t window_id;    /* windows since boot, wraps at 65536                        */
    uint8_t  trig_idx;     /* index of the trigger sample in the window (= P, C1 D5)    */
    uint16_t overruns;     /* cumulative capture_overruns counter (C1 D6)               */
    uint32_t model_hash;   /* GM_MODEL_HASH (C4), 0 if no model is built in             */
    uint8_t  flags;        /* C2_FLAG_*                                                 */
    int8_t   class_id;     /* C5 class id, -1 = GESTURE_UNKNOWN; valid iff RESULT_VALID */
    uint8_t  conf;         /* C5 confidence 0..255; valid iff RESULT_VALID              */
    uint8_t  events;       /* C5 gesture_events() bits; valid iff RESULT_VALID          */
} c2_window_meta_t;

/* HELLO payload fields. */
typedef struct {
    uint8_t  proto_ver;    /* C2_PROTO_VERSION                */
    uint8_t  odr_hz;       /* 100 (C1)                        */
    uint8_t  range_g;      /* 4 (C1)                          */
    uint8_t  n_samples;    /* 150 (C1 D8)                     */
    uint8_t  pre_trig;     /* P, 15 (C1 D5)                   */
    uint8_t  feature_ver;  /* GM_FEATURE_VERSION (C4)         */
    uint32_t model_hash;   /* GM_MODEL_HASH (C4)              */
} c2_hello_t;

/**
 * Continue a CRC-16/IBM-3740 over a byte range.
 * @param crc  running CRC (start a new message with 0xFFFF)
 * @param data bytes to add; may be NULL only if len == 0
 * @param len  number of bytes
 * @return the updated running CRC (there is no final xor, xorout = 0)
 */
uint16_t c2_crc16_update(uint16_t crc, const uint8_t *data, uint16_t len);

/**
 * CRC-16/IBM-3740 of a whole buffer (init 0xFFFF).
 * @param data bytes to checksum
 * @param len  number of bytes
 * @return the CRC; for "123456789" this is 0x29B1
 */
uint16_t c2_crc16(const uint8_t *data, uint16_t len);

/**
 * Encode one WINDOW frame into a caller-provided buffer.
 * @param out     destination buffer
 * @param out_cap size of out in bytes; must be at least C2_WINDOW_FRAME_LEN
 * @param seq     frame sequence number (wraps at 256)
 * @param meta    window metadata, must not be NULL
 * @param samples C2_N_SAMPLES rows of {x, y, z} in wand frame (C1), sample-major, must not be NULL
 * @return number of bytes written (C2_WINDOW_FRAME_LEN), or 0 on a NULL argument or short buffer
 */
uint16_t c2_encode_window(uint8_t *out, uint16_t out_cap, uint8_t seq,
                          const c2_window_meta_t *meta, const int16_t samples[][C2_N_AXES]);

/**
 * Encode one HELLO frame into a caller-provided buffer.
 * @param out     destination buffer
 * @param out_cap size of out in bytes; must be at least C2_HELLO_FRAME_LEN
 * @param seq     frame sequence number (wraps at 256)
 * @param hello   HELLO fields, must not be NULL
 * @return number of bytes written (C2_HELLO_FRAME_LEN), or 0 on a NULL argument or short buffer
 */
uint16_t c2_encode_hello(uint8_t *out, uint16_t out_cap, uint8_t seq, const c2_hello_t *hello);

#endif /* C2_FRAME_H */
// [END AI-GENERATED]
