// [AI-GENERATED: Claude Code]
/* fake_lis3dh.c - see fake_lis3dh.h. Test-only code (the "no blocking / no malloc" rules apply to
 * library code; this file uses static storage only and no delays). */
#include <string.h>
#include "fake_lis3dh.h"
#include "lis3dh_hal.h"

/* Register addresses used by the model (LIS3DH datasheet register map). */
#define R_WHO      0x0Fu
#define R_CTRL5    0x24u
#define R_OUT_XL   0x28u
#define R_OUT_ZH   0x2Du
#define R_FIFOCTRL 0x2Eu
#define R_FIFOSRC  0x2Fu
#define R_CLICKSRC 0x39u
#define FIFO_DEPTH 32u

static struct {
    uint8_t  present;
    uint8_t  who;
    uint8_t  regs[0x40];
    uint16_t fifo[FIFO_DEPTH][3];
    uint8_t  head;             /* index of the oldest unread sample */
    uint8_t  count;            /* unread samples, 0..32 */
    uint16_t latch[3];         /* output registers: the last popped sample */
    uint8_t  click_src;
    fake_fss32_t fss32;
    fake_txn_t log[FAKE_LOG_MAX];
    uint16_t nlog;
    uint16_t txn;              /* transactions since clear */
    uint16_t nack_txn;
    uint8_t  n_fsrc, nack_fsrc;
    uint8_t  n_burst, nack_burst;
    uint8_t  corrupt;
    uint8_t  arr_k;
    uint16_t arr_left;
    uint16_t next_seq;
    uint16_t lost;
} F;

void fake_reset(uint8_t present_addr)
{
    memset(&F, 0, sizeof F);
    F.present = present_addr;
    F.who = 0x33u;
    F.corrupt = 0xFFu;
    F.regs[0x20] = 0x07u;   /* CTRL_REG1 power-on value: ODR off (bits 7:4 = 0), axes enabled (bits 2:0) */
    F.fss32 = FAKE_FSS32_SATURATE;
}

void fake_set_who(uint8_t who) { F.who = who; }
void fake_set_fss32(fake_fss32_t m) { F.fss32 = m; }
void fake_set_click_src(uint8_t v) { F.click_src = v; }
void fake_set_arrivals(uint8_t k, uint16_t total_cap) { F.arr_k = k; F.arr_left = total_cap; }
uint16_t fake_next_seq(void) { return F.next_seq; }
uint8_t fake_fifo_level(void) { return F.count; }
uint16_t fake_lost(void) { return F.lost; }
uint8_t fake_reg(uint8_t reg) { return F.regs[reg & 0x3Fu]; }
uint16_t fake_log_count(void) { return F.nlog; }
const fake_txn_t *fake_log_get(uint16_t i) { return &F.log[i]; }
void fake_nack_txn(uint16_t n) { F.nack_txn = n; }
void fake_nack_fifo_src(uint8_t n) { F.nack_fsrc = n; }
void fake_nack_burst(uint8_t n) { F.nack_burst = n; }
void fake_corrupt_readback(uint8_t reg) { F.corrupt = reg; }

void fake_clear_log(void)
{
    F.nlog = 0u;
    F.txn = 0u;
    F.n_fsrc = 0u;
    F.n_burst = 0u;
}

uint8_t fake_fifo_active(void)
{
    /* CTRL_REG5 bit 6 = FIFO_EN; FIFO_CTRL_REG bits 7:6 = FM, 10 = Stream */
    return (uint8_t)(((F.regs[R_CTRL5] & 0x40u) != 0u) && ((F.regs[R_FIFOCTRL] >> 6) == 2u));
}

uint16_t fake_sample_word(uint16_t seq, uint8_t axis)
{
    uint32_t m = ((uint32_t)seq * 97u + (uint32_t)axis * 1031u + 13u) % 4096u;
    int32_t  v = (int32_t)m - 2048;
    uint32_t u12;
    if (v == -2048) {
        v = -2047;   /* keep -2048 out of the stream so sign flips cannot reach +2048 */
    }
    u12 = (uint32_t)(v & 0xFFF);                        /* 12-bit two's complement */
    return (uint16_t)((u12 << 4) | (((uint32_t)seq + axis) & 0xFu));   /* low nibble = garbage */
}

/** Push one sample (raw words) into the FIFO; discard the oldest when full (Stream mode). */
static void push_one(void)
{
    uint8_t slot, a;
    if (!fake_fifo_active()) {
        return;
    }
    if (F.count == FIFO_DEPTH) {
        F.head = (uint8_t)((F.head + 1u) % FIFO_DEPTH);
        F.count--;
        F.lost++;
    }
    slot = (uint8_t)(((uint16_t)F.head + (uint16_t)F.count) % (uint16_t)FIFO_DEPTH);
    for (a = 0u; a < 3u; a++) {
        F.fifo[slot][a] = fake_sample_word(F.next_seq, a);
    }
    F.next_seq++;
    F.count++;
}

void fake_push_next(uint16_t count)
{
    uint16_t i;
    for (i = 0u; i < count; i++) {
        push_one();
    }
}

/** Pop the oldest sample into the output-register latch (no-op when empty: old data stays). */
static void pop_one(void)
{
    uint8_t a;
    if (F.count == 0u) {
        return;
    }
    for (a = 0u; a < 3u; a++) {
        F.latch[a] = F.fifo[F.head][a];
    }
    F.head = (uint8_t)((F.head + 1u) % FIFO_DEPTH);
    F.count--;
}

/** FIFO_SRC_REG: b7 WTM (unread > FTH), b6 OVRN (32 unread), b5 EMPTY, b4:0 FSS. */
static uint8_t fifo_src_value(void)
{
    uint8_t u = F.count, fth = (uint8_t)(F.regs[R_FIFOCTRL] & 0x1Fu), v = 0u, fss;
    if (u > fth) { v |= 0x80u; }
    if (u == FIFO_DEPTH) { v |= 0x40u; }
    if (u == 0u) { v |= 0x20u; }
    if (u == FIFO_DEPTH) {
        fss = (F.fss32 == FAKE_FSS32_WRAP) ? 0u : 31u;
    } else {
        fss = u;
    }
    return (uint8_t)(v | fss);
}

/** Append a log entry (counted but dropped when the log is full). */
static fake_txn_t *log_add(uint8_t is_read, uint8_t addr, uint8_t reg, uint8_t n, uint8_t val)
{
    fake_txn_t *t;
    if (F.nlog >= FAKE_LOG_MAX) {
        return NULL;
    }
    t = &F.log[F.nlog++];
    t->is_read = is_read;
    t->addr = addr;
    t->reg = (uint8_t)(reg & 0x7Fu);
    t->n = n;
    t->val = val;
    t->flags = (uint8_t)(((reg & 0x80u) != 0u) ? FAKE_F_MSB : 0u);
    return t;
}

/** Common NACK decision: wrong address, n-th transaction, n-th FIFO_SRC read, n-th burst. */
static uint8_t should_nack(uint8_t is_read, uint8_t addr, uint8_t reg)
{
    uint8_t r = (uint8_t)(reg & 0x7Fu), nack = 0u;
    F.txn++;
    if (addr != F.present || addr == 0u) { nack = 1u; }
    if (F.nack_txn != 0u && F.txn == F.nack_txn) { nack = 1u; }
    if (is_read && r == R_FIFOSRC) {
        F.n_fsrc++;
        if (F.nack_fsrc != 0u && F.n_fsrc == F.nack_fsrc) { nack = 1u; }
    }
    if (is_read && r == R_OUT_XL) {
        F.n_burst++;
        if (F.nack_burst != 0u && F.n_burst == F.nack_burst) { nack = 1u; }
    }
    return nack;
}

int8_t lis3dh_hal_write(uint8_t addr7, uint8_t reg, uint8_t val)
{
    uint8_t r = (uint8_t)(reg & 0x3Fu);
    fake_txn_t *t = log_add(0u, addr7, reg, 1u, val);
    if (should_nack(0u, addr7, reg)) {
        if (t != NULL) { t->flags |= FAKE_F_NACK; }
        return -1;
    }
    /* read-only registers: WHO_AM_I, OUT_X_L..OUT_Z_H, FIFO_SRC, CLICK_SRC ignore writes */
    if (r == R_WHO || (r >= R_OUT_XL && r <= R_OUT_ZH) || r == R_FIFOSRC || r == R_CLICKSRC) {
        return 0;
    }
    F.regs[r] = val;
    if (r == R_FIFOCTRL && (val >> 6) == 0u) {
        F.count = 0u;      /* FM = 00 Bypass clears the FIFO */
        F.head = 0u;
    }
    return 0;
}

int8_t lis3dh_hal_read(uint8_t addr7, uint8_t reg, uint8_t *buf, uint8_t n)
{
    uint8_t i, cur = (uint8_t)(reg & 0x7Fu), popped = 0u, fifo_mode;
    fake_txn_t *t = log_add(1u, addr7, reg, n, 0u);
    if (should_nack(1u, addr7, reg)) {
        if (t != NULL) { t->flags |= FAKE_F_NACK; }
        return -1;
    }
    fifo_mode = (uint8_t)((F.regs[R_FIFOCTRL] >> 6) != 0u && (F.regs[R_CTRL5] & 0x40u) != 0u);
    for (i = 0u; i < n; i++) {
        uint8_t b;
        if (cur == R_WHO) {
            b = F.who;
        } else if (cur == R_FIFOSRC) {
            b = fifo_src_value();
        } else if (cur == R_CLICKSRC) {
            b = F.click_src;
            F.click_src = 0u;                       /* cleared on read */
        } else if (cur >= R_OUT_XL && cur <= R_OUT_ZH) {
            uint8_t k = (uint8_t)(cur - R_OUT_XL);  /* 0..5: XL XH YL YH ZL ZH */
            if (k == 0u && fifo_mode) {
                pop_one();                          /* each 6-byte group pops one sample */
                popped++;
            }
            b = ((k & 1u) == 0u) ? (uint8_t)(F.latch[k / 2u] & 0xFFu) : (uint8_t)(F.latch[k / 2u] >> 8);
        } else {
            b = F.regs[cur & 0x3Fu];
        }
        if (i == 0u && cur == F.corrupt) {
            b ^= 0x01u;                             /* read-back mismatch injection */
        }
        if (i == 0u && t != NULL) { t->val = b; }
        buf[i] = b;
        /* auto-increment (always applied for n > 1); in FIFO mode 0x2D wraps back to 0x28 */
        cur = (uint8_t)((cur == R_OUT_ZH && fifo_mode) ? R_OUT_XL : cur + 1u);
    }
    if (popped != 0u && F.arr_k != 0u && F.arr_left != 0u) {
        uint16_t k = (F.arr_left < F.arr_k) ? F.arr_left : F.arr_k;
        F.arr_left = (uint16_t)(F.arr_left - k);
        fake_push_next(k);                          /* samples that arrive between bursts */
    }
    return 0;
}
// [END AI-GENERATED]
