// [AI-GENERATED: Claude Code]
/*
 * c2_stream.c - incremental C2 UART frame sender (TX pump), ticket T-c2tx.
 *
 * WORKING ASSUMPTION: open_questions Q1, not decided.
 * Promoted from our own spike docs/agent/hadi/spikes/uart/c2_frame.c (nibble CRC table,
 * header and payload layout) and checked against spikes/uart/c2_ref.py. See c2_stream.h.
 * SW-4 (review T-c2txR F3): the 6 header bytes live in head[], samples are indexed flat (no
 * divide per byte) and each pump call CRCs its run of bytes once instead of byte by byte.
 */
#include "c2_stream.h"

#define K_IDLE    0u
#define K_HELLO   1u
#define K_WINDOW  2u
#define K_SAMPLES 3u
#define K_TEXT    4u

#define HDR_LEN        6u    /* A5 5A TYPE LEN(2) SEQ */
#define CRC_LEN        2u
#define N_SAMPLES      150u
#define SAMPLES_ROWS   16u
#define HELLO_HEAD     10u   /* whole HELLO payload */
#define WINDOW_HEAD    14u   /* WINDOW metadata before the samples */
#define SAMPLES_HEAD   3u    /* chunk u16, n u8 */
#define HELLO_LEN      10u
#define WINDOW_LEN     914u
#define SAMPLES_LEN    99u
#define TEXT_MAX       255u

/*
 * Nibble-wise CRC-16 table for poly 0x1021, copied from the spike c2_frame.c: entry n is
 * the carry-less product n * 0x1021 (32 B const).
 */
static const uint16_t c2_crc_nibble[16] = {
    0x0000u, 0x1021u, 0x2042u, 0x3063u, 0x4084u, 0x50A5u, 0x60C6u, 0x70E7u,
    0x8108u, 0x9129u, 0xA14Au, 0xB16Bu, 0xC18Cu, 0xD1ADu, 0xE1CEu, 0xF1EFu
};

uint16_t c2_crc16_update(uint16_t crc, const uint8_t *p, uint16_t n)
{
    uint16_t i;
    for (i = 0u; i < n; i++) {
        uint16_t b = (uint16_t)p[i];
        /* High nibble first, then the low nibble (spike c2_frame.c). */
        crc = (uint16_t)((uint16_t)(crc << 4) ^ c2_crc_nibble[((uint16_t)(crc >> 12) ^ (uint16_t)(b >> 4)) & 0x0Fu]);
        crc = (uint16_t)((uint16_t)(crc << 4) ^ c2_crc_nibble[((uint16_t)(crc >> 12) ^ (uint16_t)(b & 0x0Fu)) & 0x0Fu]);
    }
    return crc;
}

void c2_tx_init(c2_tx_t *tx)
{
    uint8_t i;
    if (tx == NULL) {
        return;
    }
    tx->crc = 0xFFFFu;
    tx->pos = 0u;
    tx->window_id = 0u;
    tx->chunk = 0u;
    tx->body_end = 0u;
    tx->head_n = 0u;
    tx->src = NULL;
    tx->kind = K_IDLE;
    tx->seq = 0u;
    tx->release = 0u;
    for (i = 0u; i < (uint8_t)sizeof(tx->head); i++) {
        tx->head[i] = 0u;
    }
}

bool c2_tx_busy(const c2_tx_t *tx)
{
    return (tx != NULL) && (tx->kind != K_IDLE);
}

/**
 * Store a uint16_t little-endian.
 * @param p destination, 2 bytes
 * @param v value
 */
static void put_u16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
}

/**
 * Store a uint32_t little-endian (shifts act on uint32_t, never on a 16-bit int).
 * @param p destination, 4 bytes
 * @param v value
 */
static void put_u32(uint8_t *p, uint32_t v)
{
    put_u16(p, (uint16_t)(v & 0xFFFFu));
    put_u16(p + 2, (uint16_t)((v >> 16) & 0xFFFFu));
}

/**
 * Begin a frame: write the 6 header bytes into head[], assign SEQ, reset CRC and position.
 * The caller has already stored the leading payload bytes at head[HDR_LEN..].
 * @param tx   sender state
 * @param kind K_HELLO, K_WINDOW or K_SAMPLES
 * @param type TYPE byte on the wire (0x01 HELLO, 0x02 WINDOW, 0x04 SAMPLES)
 * @param len  payload length LEN
 * @param hl   leading payload bytes held in head[] (the rest is read from src)
 */
static void begin_frame(c2_tx_t *tx, uint8_t kind, uint8_t type, uint16_t len, uint8_t hl)
{
    tx->head[0] = 0xA5u;                 /* SYNC0 */
    tx->head[1] = 0x5Au;                 /* SYNC1 */
    tx->head[2] = type;
    put_u16(&tx->head[3], len);
    tx->head[5] = tx->seq;               /* SEQ assigned at frame start */
    tx->seq = (uint8_t)(tx->seq + 1u);
    tx->head_n = (uint8_t)(HDR_LEN + hl);
    tx->body_end = (uint16_t)(HDR_LEN + len);
    tx->kind = kind;
    tx->pos = 0u;
    tx->crc = 0xFFFFu;
}

bool c2_tx_start_hello(c2_tx_t *tx, const c2_hello_t *h)
{
    uint8_t *p;
    if ((tx == NULL) || (h == NULL) || (tx->kind != K_IDLE)) {
        return false;
    }
    p = &tx->head[HDR_LEN];
    p[0] = 1u;                           /* proto_ver */
    p[1] = h->odr_hz;
    p[2] = h->range_g;
    p[3] = h->n_samples;
    p[4] = h->pre_trig;
    p[5] = h->feature_ver;
    put_u32(&p[6], h->model_hash);
    tx->src = NULL;
    begin_frame(tx, K_HELLO, 0x01u, (uint16_t)HELLO_LEN, (uint8_t)HELLO_HEAD);
    return true;
}

bool c2_tx_start_window(c2_tx_t *tx, const c2_window_meta_t *m, const int16_t (*buf)[3])
{
    uint8_t *p;
    if ((tx == NULL) || (m == NULL) || (buf == NULL) || (tx->kind != K_IDLE)) {
        return false;
    }
    p = &tx->head[HDR_LEN];
    put_u16(&p[0], tx->window_id);
    p[2] = (uint8_t)N_SAMPLES;
    p[3] = m->trig_idx;
    put_u16(&p[4], m->overruns);
    put_u32(&p[6], m->model_hash);
    p[10] = m->flags;
    p[11] = (uint8_t)m->class_id;        /* two's complement byte */
    p[12] = m->conf;
    p[13] = m->events;
    tx->window_id = (uint16_t)(tx->window_id + 1u);
    tx->src = buf;
    begin_frame(tx, K_WINDOW, 0x02u, (uint16_t)WINDOW_LEN, (uint8_t)WINDOW_HEAD);
    return true;
}

bool c2_tx_start_samples(c2_tx_t *tx, const int16_t (*s)[3])
{
    uint8_t *p;
    if ((tx == NULL) || (s == NULL) || (tx->kind != K_IDLE)) {
        return false;
    }
    p = &tx->head[HDR_LEN];
    put_u16(&p[0], tx->chunk);
    p[2] = (uint8_t)SAMPLES_ROWS;
    tx->chunk = (uint16_t)(tx->chunk + 1u);
    tx->src = s;
    begin_frame(tx, K_SAMPLES, 0x04u, (uint16_t)SAMPLES_LEN, (uint8_t)SAMPLES_HEAD);
    return true;
}

bool c2_tx_start_text(c2_tx_t *tx, const char *s)
{
    uint16_t n = 0u;
    if ((tx == NULL) || (s == NULL) || (tx->kind != K_IDLE)) {
        return false;
    }
    while (s[n] != '\0') {
        uint8_t c = (uint8_t)s[n];
        if ((n >= TEXT_MAX) || !((c == 0x0Au) || (c == 0x0Du) || ((c >= 0x20u) && (c <= 0x7Eu)))) {
            return false;
        }
        n++;
    }
    if (n == 0u) {
        return true;                     /* nothing to send; stay idle */
    }
    tx->src = s;
    tx->pos = 0u;
    tx->kind = K_TEXT;
    return true;
}

uint8_t c2_tx_pump(c2_tx_t *tx, uint8_t *out, uint8_t room)
{
    uint8_t n = 0u;
    uint8_t cap;
    uint16_t pos;
    uint16_t body_end;
    if ((tx == NULL) || (out == NULL) || (room == 0u) || (tx->kind == K_IDLE)) {
        return 0u;
    }
    cap = (room < (uint8_t)C2_PUMP_MAX) ? room : (uint8_t)C2_PUMP_MAX;
    pos = tx->pos;

    if (tx->kind == K_TEXT) {
        const char *s = (const char *)tx->src;
        while ((n < cap) && (s[pos] != '\0')) {
            out[n] = (uint8_t)s[pos];
            n = (uint8_t)(n + 1u);
            pos = (uint16_t)(pos + 1u);
        }
        tx->pos = pos;
        if (s[pos] == '\0') {
            tx->kind = K_IDLE;
        }
        return n;
    }

    body_end = tx->body_end;

    /* 1. Header and leading payload bytes, snapshotted in head[] at frame start. */
    while ((n < cap) && (pos < (uint16_t)tx->head_n)) {
        out[n] = tx->head[pos];
        n = (uint8_t)(n + 1u);
        pos = (uint16_t)(pos + 1u);
    }

    /* 2. Samples, read from the caller's buffer as a flat row-major int16 array (x0 y0 z0 x1 ...),
     *    low byte first. A HELLO has head_n == body_end, so this part is skipped and src stays unread. */
    if ((n < cap) && (pos < body_end)) {
        const int16_t *flat = (const int16_t *)tx->src;
        uint16_t idx = (uint16_t)(pos - (uint16_t)tx->head_n);   /* byte index within the samples */
        while ((n < cap) && (pos < body_end)) {
            /* int16_t -> uint16_t is modulo 2^16, the two's complement bits. */
            uint16_t v = (uint16_t)flat[idx >> 1];
            out[n] = ((idx & 1u) == 0u) ? (uint8_t)(v & 0xFFu) : (uint8_t)((v >> 8) & 0xFFu);
            n = (uint8_t)(n + 1u);
            pos = (uint16_t)(pos + 1u);
            idx = (uint16_t)(idx + 1u);
        }
    }

    /* 3. CRC the run just written in one call. It covers TYPE..payload, not the two sync bytes. */
    if (n != 0u) {
        uint8_t skip = 0u;
        if (tx->pos < 2u) {
            skip = (uint8_t)(2u - tx->pos);
            if (skip > n) {
                skip = n;
            }
        }
        tx->crc = c2_crc16_update(tx->crc, out + skip, (uint16_t)(n - skip));
    }

    /* 4. The two CRC bytes, low byte first. */
    while ((n < cap) && (pos < (uint16_t)(body_end + CRC_LEN))) {
        out[n] = (pos == body_end) ? (uint8_t)(tx->crc & 0xFFu) : (uint8_t)((tx->crc >> 8) & 0xFFu);
        n = (uint8_t)(n + 1u);
        pos = (uint16_t)(pos + 1u);
    }

    tx->pos = pos;
    if (pos >= (uint16_t)(body_end + CRC_LEN)) {
        if (tx->kind == K_WINDOW) {
            tx->release = 1u;
        }
        tx->kind = K_IDLE;
    }
    return n;
}

bool c2_tx_take_release(c2_tx_t *tx)
{
    if ((tx == NULL) || (tx->release == 0u)) {
        return false;
    }
    tx->release = 0u;
    return true;
}

uint16_t c2_tx_window_id(const c2_tx_t *tx)
{
    return (tx != NULL) ? tx->window_id : 0u;
}
// [END AI-GENERATED]
