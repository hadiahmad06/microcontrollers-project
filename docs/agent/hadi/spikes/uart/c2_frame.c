// [AI-GENERATED: Claude Code]
/*
 * c2_frame.c - C2 UART raw-stream encoder and CRC (host spike, ticket S2-1).
 * See c2_frame.h for the wire format and the CRC catalogue citation.
 */
#include "c2_frame.h"

/*
 * Nibble-wise CRC-16 table for poly 0x1021: entry n is the carry-less product n * 0x1021
 * (n < 16, so no reduction is needed). 32 bytes of data (about 48 B of flash with the
 * PSV 3/2 convention of C7) instead of the 512 bytes of a byte-wise table. No source is
 * cited: this is our own derivation from the bitwise definition (four bits per step instead
 * of one), verified against the bitwise Python CRC by `make test`. No code was borrowed.
 */
static const uint16_t c2_crc_nibble[16] = {
    0x0000u, 0x1021u, 0x2042u, 0x3063u, 0x4084u, 0x50A5u, 0x60C6u, 0x70E7u,
    0x8108u, 0x9129u, 0xA14Au, 0xB16Bu, 0xC18Cu, 0xD1ADu, 0xE1CEu, 0xF1EFu
};

/**
 * Store a uint16_t little-endian.
 * @param p destination, 2 bytes
 * @param v value
 * @return pointer just past the written bytes
 */
static uint8_t *c2_put_u16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
    return p + 2;
}

/**
 * Store a uint32_t little-endian. Shifts act on uint32_t, never on a 16-bit int.
 * @param p destination, 4 bytes
 * @param v value
 * @return pointer just past the written bytes
 */
static uint8_t *c2_put_u32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
    p[2] = (uint8_t)((v >> 16) & 0xFFu);
    p[3] = (uint8_t)((v >> 24) & 0xFFu);
    return p + 4;
}

/**
 * Write the 6-byte header (sync, type, length, sequence).
 * @param out  destination, at least C2_HEADER_LEN bytes
 * @param type frame type
 * @param len  payload length in bytes
 * @param seq  sequence number
 */
static void c2_put_header(uint8_t *out, uint8_t type, uint16_t len, uint8_t seq)
{
    out[0] = (uint8_t)C2_SYNC0;
    out[1] = (uint8_t)C2_SYNC1;
    out[2] = type;
    (void)c2_put_u16(&out[3], len);
    out[5] = seq;
}

uint16_t c2_crc16_update(uint16_t crc, const uint8_t *data, uint16_t len)
{
    uint16_t i;
    for (i = 0u; i < len; i++) {
        uint16_t b = (uint16_t)data[i];
        /* High nibble first: fold the top nibble of the CRC with the byte's high nibble. */
        crc = (uint16_t)((uint16_t)(crc << 4) ^ c2_crc_nibble[((uint16_t)(crc >> 12) ^ (uint16_t)(b >> 4)) & 0x0Fu]);
        /* Then the low nibble. */
        crc = (uint16_t)((uint16_t)(crc << 4) ^ c2_crc_nibble[((uint16_t)(crc >> 12) ^ (uint16_t)(b & 0x0Fu)) & 0x0Fu]);
    }
    return crc;
}

uint16_t c2_crc16(const uint8_t *data, uint16_t len)
{
    return c2_crc16_update(0xFFFFu, data, len);
}

uint16_t c2_encode_window(uint8_t *out, uint16_t out_cap, uint8_t seq,
                          const c2_window_meta_t *meta, int16_t (*samples)[C2_N_AXES])
{
    uint8_t *p;
    uint16_t i;
    uint16_t k;
    uint16_t crc;

    if ((out == NULL) || (meta == NULL) || (samples == NULL) || (out_cap < C2_WINDOW_FRAME_LEN)) {
        return 0u;
    }
    c2_put_header(out, (uint8_t)C2_TYPE_WINDOW, (uint16_t)C2_WINDOW_PAYLOAD_LEN, seq);
    p = &out[C2_HEADER_LEN];
    p = c2_put_u16(p, meta->window_id);
    *p++ = (uint8_t)C2_N_SAMPLES;
    *p++ = meta->trig_idx;
    p = c2_put_u16(p, meta->overruns);
    p = c2_put_u32(p, meta->model_hash);
    *p++ = meta->flags;
    *p++ = (uint8_t)meta->class_id;   /* two's complement byte, -1 -> 0xFF */
    *p++ = meta->conf;
    *p++ = meta->events;
    for (i = 0u; i < C2_N_SAMPLES; i++) {
        for (k = 0u; k < C2_N_AXES; k++) {
            /* int16_t -> uint16_t is modulo 2^16 (C99 6.3.1.3): the two's complement bits. */
            p = c2_put_u16(p, (uint16_t)samples[i][k]);
        }
    }
    /* CRC over TYPE, LEN, SEQ and payload: everything after the two sync bytes. */
    crc = c2_crc16(&out[2], (uint16_t)(C2_HEADER_LEN - 2u + C2_WINDOW_PAYLOAD_LEN));
    (void)c2_put_u16(p, crc);
    return (uint16_t)C2_WINDOW_FRAME_LEN;
}

uint16_t c2_encode_hello(uint8_t *out, uint16_t out_cap, uint8_t seq, const c2_hello_t *hello)
{
    uint8_t *p;
    uint16_t crc;

    if ((out == NULL) || (hello == NULL) || (out_cap < C2_HELLO_FRAME_LEN)) {
        return 0u;
    }
    c2_put_header(out, (uint8_t)C2_TYPE_HELLO, (uint16_t)C2_HELLO_PAYLOAD_LEN, seq);
    p = &out[C2_HEADER_LEN];
    *p++ = hello->proto_ver;
    *p++ = hello->odr_hz;
    *p++ = hello->range_g;
    *p++ = hello->n_samples;
    *p++ = hello->pre_trig;
    *p++ = hello->feature_ver;
    p = c2_put_u32(p, hello->model_hash);
    crc = c2_crc16(&out[2], (uint16_t)(C2_HEADER_LEN - 2u + C2_HELLO_PAYLOAD_LEN));
    (void)c2_put_u16(p, crc);
    return (uint16_t)C2_HELLO_FRAME_LEN;
}
// [END AI-GENERATED]
