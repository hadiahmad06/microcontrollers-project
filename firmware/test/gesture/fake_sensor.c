// [AI-GENERATED: Claude Code]
/* fake_sensor.c - see fake_sensor.h. Adapted from firmware/test/lis3dh/fake_lis3dh.c (our own test code). */
#include <string.h>
#include "fake_sensor.h"
#include "lis3dh_hal.h"

#define R_WHO      0x0Fu
#define R_CTRL5    0x24u
#define R_OUT_XL   0x28u
#define R_OUT_ZH   0x2Du
#define R_FIFOCTRL 0x2Eu
#define R_FIFOSRC  0x2Fu
#define R_CLICKSRC 0x39u
#define DEPTH 32u

static struct {
    uint8_t  present, who, corrupt;
    uint8_t  regs[0x40];
    uint16_t fifo[DEPTH][3];
    uint16_t fseq[DEPTH];
    uint8_t  head, count;
    uint16_t latch[3];
    uint8_t  click;
    uint16_t next_seq;
    uint16_t gfirst[4], gcnt[4];
    uint8_t  ngap;
} F;

void fs_reset(uint8_t present_addr, uint8_t who, uint8_t corrupt_reg)
{
    memset(&F, 0, sizeof F);
    F.present = present_addr;
    F.who = who;
    F.corrupt = corrupt_reg;
    F.regs[0x20] = 0x07u;   /* CTRL_REG1 power-on: ODR off, axes enabled */
}

uint8_t fs_level(void) { return F.count; }
void fs_set_click(uint8_t v) { F.click = v; }
uint16_t fs_next_seq(void) { return F.next_seq; }
uint8_t fs_gap_count(void) { return F.ngap; }
void fs_gap(uint8_t i, uint16_t *first, uint16_t *cnt) { *first = F.gfirst[i]; *cnt = F.gcnt[i]; }

/** Record that sample number seq was discarded; merge with the previous range when contiguous. */
static void note_lost(uint16_t seq)
{
    if (F.ngap > 0u && (uint16_t)(F.gfirst[F.ngap - 1u] + F.gcnt[F.ngap - 1u]) == seq) {
        F.gcnt[F.ngap - 1u]++;
    } else if (F.ngap < 4u) {
        F.gfirst[F.ngap] = seq;
        F.gcnt[F.ngap] = 1u;
        F.ngap++;
    }
}

void fs_push(const int16_t s[3])
{
    uint8_t a, slot;
    /* active = CTRL_REG5 FIFO_EN (bit 6) and FIFO_CTRL FM = Stream (10) */
    if (!(((F.regs[R_CTRL5] & 0x40u) != 0u) && ((F.regs[R_FIFOCTRL] >> 6) == 2u))) {
        return;
    }
    if (F.count == DEPTH) {                 /* Stream mode: discard the oldest */
        note_lost(F.fseq[F.head]);
        F.head = (uint8_t)((F.head + 1u) % DEPTH);
        F.count--;
    }
    slot = (uint8_t)(((uint16_t)F.head + F.count) % DEPTH);
    for (a = 0u; a < 3u; a++) {
        /* 12-bit two's complement, left-justified in the 16-bit output word */
        F.fifo[slot][a] = (uint16_t)(((uint16_t)s[a] & 0x0FFFu) << 4);
    }
    F.fseq[slot] = F.next_seq++;
    F.count++;
}

/** FIFO_SRC: b7 WTM (unread > FTH), b6 OVRN (32 unread), b5 EMPTY, b4:0 FSS (saturates at 31). */
static uint8_t fifo_src(void)
{
    uint8_t u = F.count, fth = (uint8_t)(F.regs[R_FIFOCTRL] & 0x1Fu), v = 0u;
    if (u > fth) { v |= 0x80u; }
    if (u == DEPTH) { v |= 0x40u; }
    if (u == 0u) { v |= 0x20u; }
    return (uint8_t)(v | (u == DEPTH ? 31u : u));
}

int8_t lis3dh_hal_write(uint8_t addr7, uint8_t reg, uint8_t val)
{
    uint8_t r = (uint8_t)(reg & 0x3Fu);
    if (addr7 != F.present || addr7 == 0u) { return -1; }
    if (r == R_WHO || (r >= R_OUT_XL && r <= R_OUT_ZH) || r == R_FIFOSRC || r == R_CLICKSRC) { return 0; }
    F.regs[r] = val;
    if (r == R_FIFOCTRL && (val >> 6) == 0u) { F.count = 0u; F.head = 0u; }   /* Bypass clears */
    return 0;
}

int8_t lis3dh_hal_read(uint8_t addr7, uint8_t reg, uint8_t *buf, uint8_t n)
{
    uint8_t i, cur = (uint8_t)(reg & 0x7Fu), fifo_mode, a;
    if (addr7 != F.present || addr7 == 0u) { return -1; }
    fifo_mode = (uint8_t)((F.regs[R_FIFOCTRL] >> 6) != 0u && (F.regs[R_CTRL5] & 0x40u) != 0u);
    for (i = 0u; i < n; i++) {
        uint8_t b;
        if (cur == R_WHO) {
            b = F.who;
        } else if (cur == R_FIFOSRC) {
            b = fifo_src();
        } else if (cur == R_CLICKSRC) {
            b = F.click;
            F.click = 0u;
        } else if (cur >= R_OUT_XL && cur <= R_OUT_ZH) {
            uint8_t k = (uint8_t)(cur - R_OUT_XL);
            if (k == 0u && fifo_mode && F.count != 0u) {      /* each 6-byte group pops one sample */
                for (a = 0u; a < 3u; a++) { F.latch[a] = F.fifo[F.head][a]; }
                F.head = (uint8_t)((F.head + 1u) % DEPTH);
                F.count--;
            }
            b = ((k & 1u) == 0u) ? (uint8_t)(F.latch[k / 2u] & 0xFFu) : (uint8_t)(F.latch[k / 2u] >> 8);
        } else {
            b = F.regs[cur & 0x3Fu];
        }
        if (cur == F.corrupt) { b ^= 0x01u; }
        buf[i] = b;
        cur = (uint8_t)((cur == R_OUT_ZH && fifo_mode) ? R_OUT_XL : cur + 1u);
    }
    return 0;
}
// [END AI-GENERATED]
