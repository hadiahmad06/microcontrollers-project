// [AI-GENERATED: Claude Code]
/*
 * c2_stream.c - incremental C2 UART frame sender (TX pump), ticket T-c2tx.
 *
 * WORKING ASSUMPTION: open_questions Q1, not decided.
 * Promoted from our own spike docs/agent/hadi/spikes/uart/c2_frame.c (nibble CRC table,
 * header and payload layout) and checked against spikes/uart/c2_ref.py. See c2_stream.h.
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
 * Begin a frame of the given kind: assign SEQ, reset CRC and position.
 * @param tx   sender state
 * @param kind K_HELLO, K_WINDOW or K_SAMPLES
 */
static void begin_frame(c2_tx_t *tx, uint8_t kind)
{
    tx->kind = kind;
    tx->pos = 0u;
    tx->crc = 0xFFFFu;
    tx->seq = (uint8_t)(tx->seq + 1u);   /* this frame's SEQ is seq - 1 (assigned now) */
}

bool c2_tx_start_hello(c2_tx_t *tx, const c2_hello_t *h)
{
    if ((tx == NULL) || (h == NULL) || (tx->kind != K_IDLE)) {
        return false;
    }
    tx->head[0] = 1u;                    /* proto_ver */
    tx->head[1] = h->odr_hz;
    tx->head[2] = h->range_g;
    tx->head[3] = h->n_samples;
    tx->head[4] = h->pre_trig;
    tx->head[5] = h->feature_ver;
    put_u32(&tx->head[6], h->model_hash);
    tx->src = NULL;
    begin_frame(tx, K_HELLO);
    return true;
}

bool c2_tx_start_window(c2_tx_t *tx, const c2_window_meta_t *m, const int16_t (*buf)[3])
{
    if ((tx == NULL) || (m == NULL) || (buf == NULL) || (tx->kind != K_IDLE)) {
        return false;
    }
    put_u16(&tx->head[0], tx->window_id);
    tx->head[2] = (uint8_t)N_SAMPLES;
    tx->head[3] = m->trig_idx;
    put_u16(&tx->head[4], m->overruns);
    put_u32(&tx->head[6], m->model_hash);
    tx->head[10] = m->flags;
    tx->head[11] = (uint8_t)m->class_id;  /* two's complement byte */
    tx->head[12] = m->conf;
    tx->head[13] = m->events;
    tx->window_id = (uint16_t)(tx->window_id + 1u);
    tx->src = buf;
    begin_frame(tx, K_WINDOW);
    return true;
}

bool c2_tx_start_samples(c2_tx_t *tx, const int16_t (*s)[3])
{
    if ((tx == NULL) || (s == NULL) || (tx->kind != K_IDLE)) {
        return false;
    }
    put_u16(&tx->head[0], tx->chunk);
    tx->head[2] = (uint8_t)SAMPLES_ROWS;
    tx->chunk = (uint16_t)(tx->chunk + 1u);
    tx->src = s;
    begin_frame(tx, K_SAMPLES);
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

/**
 * Number of leading payload bytes held in head[] for a frame kind.
 * @param kind frame kind
 * @return head length
 */
static uint8_t head_len(uint8_t kind)
{
    if (kind == K_HELLO) {
        return (uint8_t)HELLO_HEAD;
    }
    return (kind == K_WINDOW) ? (uint8_t)WINDOW_HEAD : (uint8_t)SAMPLES_HEAD;
}

/**
 * Payload length LEN of a frame kind.
 * @param kind frame kind
 * @return LEN
 */
static uint16_t payload_len(uint8_t kind)
{
    if (kind == K_HELLO) {
        return (uint16_t)HELLO_LEN;
    }
    return (kind == K_WINDOW) ? (uint16_t)WINDOW_LEN : (uint16_t)SAMPLES_LEN;
}

/**
 * Produce frame byte number tx->pos (CRC bytes are produced by the caller).
 * @param tx sender state, frame in flight, pos < HDR_LEN + LEN
 * @return the byte
 */
static uint8_t frame_byte(const c2_tx_t *tx)
{
    uint16_t pos = tx->pos;
    uint16_t len = payload_len(tx->kind);
    uint16_t hl;
    uint16_t idx;
    uint16_t e;
    uint16_t row;
    uint16_t col;
    int16_t v;
    if (pos < HDR_LEN) {
        switch (pos) {
        case 0u: return 0xA5u;           /* SYNC0 */
        case 1u: return 0x5Au;           /* SYNC1 */
        case 2u: return (tx->kind == K_HELLO) ? 0x01u : ((tx->kind == K_WINDOW) ? 0x02u : 0x04u);
        case 3u: return (uint8_t)(len & 0xFFu);
        case 4u: return (uint8_t)((len >> 8) & 0xFFu);
        default: return (uint8_t)(tx->seq - 1u);   /* SEQ assigned at frame start */
        }
    }
    hl = head_len(tx->kind);
    idx = (uint16_t)(pos - HDR_LEN);
    if (idx < hl) {
        return tx->head[idx];
    }
    idx = (uint16_t)(idx - hl);
    e = (uint16_t)(idx >> 1);            /* int16 element index */
    row = (uint16_t)(e / 3u);
    col = (uint16_t)(e - (uint16_t)(row * 3u));
    v = ((const int16_t (*)[3])tx->src)[row][col];
    /* Low byte first; int16_t -> uint16_t is modulo 2^16, the two's complement bits. */
    return ((idx & 1u) == 0u) ? (uint8_t)((uint16_t)v & 0xFFu) : (uint8_t)(((uint16_t)v >> 8) & 0xFFu);
}

uint8_t c2_tx_pump(c2_tx_t *tx, uint8_t *out, uint8_t room)
{
    uint8_t n = 0u;
    uint8_t cap;
    if ((tx == NULL) || (out == NULL) || (room == 0u) || (tx->kind == K_IDLE)) {
        return 0u;
    }
    cap = (room < (uint8_t)C2_PUMP_MAX) ? room : (uint8_t)C2_PUMP_MAX;

    if (tx->kind == K_TEXT) {
        const char *s = (const char *)tx->src;
        while ((n < cap) && (s[tx->pos] != '\0')) {
            out[n] = (uint8_t)s[tx->pos];
            n++;
            tx->pos = (uint16_t)(tx->pos + 1u);
        }
        if (s[tx->pos] == '\0') {
            tx->kind = K_IDLE;
        }
        return n;
    }

    {
        uint16_t body_end = (uint16_t)(HDR_LEN + payload_len(tx->kind));
        uint16_t total = (uint16_t)(body_end + CRC_LEN);
        while ((n < cap) && (tx->pos < total)) {
            uint8_t b;
            if (tx->pos < body_end) {
                b = frame_byte(tx);
                if (tx->pos >= 2u) {     /* CRC covers TYPE..payload, not the sync bytes */
                    tx->crc = c2_crc16_update(tx->crc, &b, 1u);
                }
            } else if (tx->pos == body_end) {
                b = (uint8_t)(tx->crc & 0xFFu);          /* CRC low byte first */
            } else {
                b = (uint8_t)((tx->crc >> 8) & 0xFFu);
            }
            out[n] = b;
            n++;
            tx->pos = (uint16_t)(tx->pos + 1u);
        }
        if (tx->pos >= total) {
            if (tx->kind == K_WINDOW) {
                tx->release = 1u;
            }
            tx->kind = K_IDLE;
        }
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
