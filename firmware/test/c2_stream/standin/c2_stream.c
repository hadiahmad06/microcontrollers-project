// [AI-GENERATED: Claude Code]
/* c2_stream.c - STAND-IN for the suite harness (see c2_stream.h). Own bitwise CRC, own byte picker. */
#include <stddef.h>
#include "c2_stream.h"

#define T_IDLE 0u
#define T_TEXT 0xFFu

uint16_t c2_crc16_update(uint16_t crc, const uint8_t *p, uint16_t n)
{
    for (uint16_t i = 0; i < n; i++) {
        crc = (uint16_t)(crc ^ ((uint16_t)p[i] << 8));
        for (uint8_t b = 0; b < 8u; b++) {
            crc = (crc & 0x8000u) ? (uint16_t)((uint16_t)(crc << 1) ^ 0x1021u) : (uint16_t)(crc << 1);
        }
    }
    return crc;
}

void c2_tx_init(c2_tx_t *tx)
{
    tx->rows = NULL;
    tx->text = NULL;
    tx->pos = tx->len = 0u;
    tx->crc = 0xFFFFu;
    tx->wid = tx->chunk = 0u;
    tx->seq = 0u;
    tx->type = T_IDLE;
    tx->release = 0u;
}

bool c2_tx_busy(const c2_tx_t *tx)
{
    return tx->type != T_IDLE;
}

static void begin(c2_tx_t *tx, uint8_t type, uint16_t payload_len)
{
    tx->type = type;
    tx->len = (uint16_t)(payload_len + 8u);
    tx->pos = 0u;
    tx->crc = 0xFFFFu;
    tx->seq++; /* the frame's own SEQ is the old value: see byte_at */
}

bool c2_tx_start_hello(c2_tx_t *tx, const c2_hello_t *h)
{
    if (tx == NULL || h == NULL || tx->type != T_IDLE) {
        return false;
    }
    tx->pl[0] = 1u; tx->pl[1] = h->odr_hz; tx->pl[2] = h->range_g; tx->pl[3] = h->n_samples;
    tx->pl[4] = h->pre_trig; tx->pl[5] = h->feature_ver;
    for (uint8_t i = 0; i < 4u; i++) {
        tx->pl[6 + i] = (uint8_t)(h->model_hash >> (8u * i));
    }
    begin(tx, 1u, 10u);
    return true;
}

bool c2_tx_start_window(c2_tx_t *tx, const c2_window_meta_t *m, const int16_t (*buf)[3])
{
    if (tx == NULL || m == NULL || buf == NULL || tx->type != T_IDLE) {
        return false;
    }
    tx->pl[0] = (uint8_t)tx->wid; tx->pl[1] = (uint8_t)(tx->wid >> 8); tx->pl[2] = 150u; tx->pl[3] = m->trig_idx;
    tx->pl[4] = (uint8_t)m->overruns; tx->pl[5] = (uint8_t)(m->overruns >> 8);
    for (uint8_t i = 0; i < 4u; i++) {
        tx->pl[6 + i] = (uint8_t)(m->model_hash >> (8u * i));
    }
    tx->pl[10] = m->flags; tx->pl[11] = (uint8_t)m->class_id; tx->pl[12] = m->conf; tx->pl[13] = m->events;
    tx->rows = buf;
    tx->wid++;
    begin(tx, 2u, 914u);
    return true;
}

bool c2_tx_start_samples(c2_tx_t *tx, const int16_t (*s)[3])
{
    if (tx == NULL || s == NULL || tx->type != T_IDLE) {
        return false;
    }
    tx->pl[0] = (uint8_t)tx->chunk; tx->pl[1] = (uint8_t)(tx->chunk >> 8); tx->pl[2] = 16u;
    tx->rows = s;
    tx->chunk++;
    begin(tx, 4u, 99u);
    return true;
}

bool c2_tx_start_text(c2_tx_t *tx, const char *s)
{
    uint16_t n = 0u;
    if (tx == NULL || s == NULL || tx->type != T_IDLE) {
        return false;
    }
    for (; s[n] != '\0'; n++) {
        uint8_t c = (uint8_t)s[n];
        if (n >= 255u || !(c == 0x0Au || c == 0x0Du || (c >= 0x20u && c <= 0x7Eu))) {
            return false;
        }
    }
    if (n == 0u) {
        return false;
    }
    tx->text = s;
    tx->type = T_TEXT;
    tx->len = n;
    tx->pos = 0u;
    return true;
}

/* byte p of the frame in flight (frame bytes only; CRC bytes are handled by the caller) */
static uint8_t byte_at(const c2_tx_t *tx, uint16_t p)
{
    uint16_t plen = (uint16_t)(tx->len - 8u);
    switch (p) {
    case 0: return 0xA5u;
    case 1: return 0x5Au;
    case 2: return tx->type;
    case 3: return (uint8_t)plen;
    case 4: return (uint8_t)(plen >> 8);
    case 5: return (uint8_t)(tx->seq - 1u);
    default: break;
    }
    uint16_t q = (uint16_t)(p - 6u);
    uint8_t pre = tx->type == 1u ? 10u : (tx->type == 2u ? 14u : 3u);
    if (q < pre) {
        return tx->pl[q];
    }
    uint16_t s = (uint16_t)(q - pre);
    uint16_t idx = (uint16_t)(s / 2u);
    uint16_t v = (uint16_t)tx->rows[idx / 3u][idx % 3u];
    return (s & 1u) ? (uint8_t)(v >> 8) : (uint8_t)v;
}

uint8_t c2_tx_pump(c2_tx_t *tx, uint8_t *out, uint8_t room)
{
    uint8_t n = 0u;
    if (tx->type == T_IDLE || room == 0u) {
        return 0u;
    }
    while (n < room && n < C2_PUMP_MAX && tx->pos < tx->len) {
        uint8_t b;
        if (tx->type == T_TEXT) {
            b = (uint8_t)tx->text[tx->pos];
        } else if (tx->pos < (uint16_t)(tx->len - 2u)) {
            b = byte_at(tx, tx->pos);
            if (tx->pos >= 2u) {
                tx->crc = c2_crc16_update(tx->crc, &b, 1u);
            }
        } else {
            b = (tx->pos == (uint16_t)(tx->len - 2u)) ? (uint8_t)tx->crc : (uint8_t)(tx->crc >> 8);
        }
        out[n++] = b;
        tx->pos++;
    }
    if (tx->pos >= tx->len) {
        if (tx->type == 2u) {
            tx->release = 1u;
        }
        tx->type = T_IDLE;
    }
    return n;
}

bool c2_tx_take_release(c2_tx_t *tx)
{
    bool r = tx->release != 0u;
    tx->release = 0u;
    return r;
}

uint16_t c2_tx_window_id(const c2_tx_t *tx)
{
    return tx->wid;
}
// [END AI-GENERATED]
