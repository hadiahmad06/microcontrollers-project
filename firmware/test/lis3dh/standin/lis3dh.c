// [AI-GENERATED: Claude Code]
/* STAND-IN lis3dh.c: written from the spec by test-lis3dh ONLY to prove the test suite in
 * ../test_lis3dh.c. It is NOT the product driver (that is firmware/src/lis3dh.c by impl-lis3dh). */
#include "lis3dh.h"
#include "lis3dh_hal.h"

static uint8_t s_addr = 0u;                 /* 0 until a full init succeeds (guards, lis3dh_address) */
static const lis3dh_axes_t *s_axes = 0;     /* NULL = identity */

/**
 * Write a register and read it back; any HAL error or mismatch is LIS3DH_ERR_BUS.
 * @param a   7-bit device address
 * @param reg register sub-address
 * @param val value to write and expect back
 * @return LIS3DH_OK or LIS3DH_ERR_BUS
 */
static int8_t cfg(uint8_t a, uint8_t reg, uint8_t val)
{
    uint8_t rb = 0u;
    if (lis3dh_hal_write(a, reg, val) != 0) { return LIS3DH_ERR_BUS; }
    if (lis3dh_hal_read(a, reg, &rb, 1u) != 0) { return LIS3DH_ERR_BUS; }
    return (rb == val) ? LIS3DH_OK : LIS3DH_ERR_BUS;
}

/** Probe one address: 1 = WHO_AM_I ok, 0 = no answer or wrong value. */
static uint8_t probe(uint8_t a)
{
    uint8_t who = 0u;
    if (lis3dh_hal_read(a, 0x0Fu, &who, 1u) != 0) { return 0u; }
    return (uint8_t)(who == 0x33u);
}

int8_t lis3dh_init(const lis3dh_axes_t *axes)
{
    static const uint8_t seq[][2] = {
        {0x20u, 0x00u},  /* CTRL_REG1: ODR = 0 power-down while configuring */
        {0x23u, 0x18u},  /* CTRL_REG4 */
        {0x22u, 0x06u},  /* CTRL_REG3 */
        {0x25u, 0x80u},  /* CTRL_REG6 */
        {0x38u, 0x2Au},  /* CLICK_CFG */
        {0x3Au, 0xB0u},  /* CLICK_THS */
        {0x3Bu, 0x04u},  /* TIME_LIMIT */
        {0x3Cu, 0x10u},  /* TIME_LATENCY */
        {0x3Du, 0x30u},  /* TIME_WINDOW */
        {0x24u, 0x40u},  /* CTRL_REG5: FIFO_EN */
        {0x2Eu, 0x00u},  /* FIFO_CTRL: Bypass (clears) */
        {0x2Eu, 0x8Fu},  /* FIFO_CTRL: Stream, FTH = 15 */
        {0x20u, 0x57u}   /* CTRL_REG1: 100 Hz, XYZ on */
    };
    uint8_t i, a;
    s_axes = axes;
    s_addr = 0u;
    if (probe(0x18u)) {
        a = 0x18u;
    } else if (probe(0x19u)) {
        a = 0x19u;
    } else {
        return LIS3DH_ERR_SENSOR;
    }
    for (i = 0u; i < (uint8_t)(sizeof seq / sizeof seq[0]); i++) {
        int8_t r = cfg(a, seq[i][0], seq[i][1]);
        if (r != LIS3DH_OK) {
            if (i == (uint8_t)(sizeof seq / sizeof seq[0] - 1u)) {
                (void)lis3dh_hal_write(a, 0x20u, 0x00u);   /* best-effort power-down, then stop */
            }
            return r;                                       /* stop at the first fault */
        }
    }
    s_addr = a;
    return LIS3DH_OK;
}

uint8_t lis3dh_address(void) { return s_addr; }

void lis3dh_unpack(const uint8_t raw[6], const lis3dh_axes_t *axes, int16_t out[3])
{
    int16_t v[3];
    uint8_t i;
    static const lis3dh_axes_t ident = {{0u, 1u, 2u}, {1, 1, 1}};
    if (axes == 0) { axes = &ident; }
    for (i = 0u; i < 3u; i++) {
        int16_t w = (int16_t)(((uint16_t)raw[2u * i + 1u] << 8) | raw[2u * i]);
        v[i] = (int16_t)(w >> 4);                       /* arithmetic shift (C1.1) */
    }
    for (i = 0u; i < 3u; i++) {
        uint8_t src = (axes->src[i] > 2u) ? 0u : axes->src[i];            /* out of range -> 0 */
        int32_t sg = (axes->sign[i] == -1) ? -1L : 1L;                    /* anything but -1 is +1 */
        int32_t r = sg * (int32_t)v[src];                                 /* R4 */
        out[i] = (int16_t)((r > 2047L) ? 2047L : r);                      /* R2: -(-2048) -> 2047 */
    }
}

/** R1: unread count from a FIFO_SRC byte; FSS = 0 with OVRN = 1 and EMPTY = 0 means 32. */
static uint8_t unread(uint8_t src)
{
    uint8_t fss = (uint8_t)(src & 0x1Fu);
    if (fss == 0u && (src & 0x40u) != 0u && (src & 0x20u) == 0u) { return 32u; }
    return fss;
}

int16_t lis3dh_drain(lis3dh_sample_cb cb, void *ctx, uint8_t *overrun, bool *more)
{
    uint8_t src = 0u, raw[6u * LIS3DH_BURST_MAX], bursts = 0u, n, i;
    int16_t total = 0, s[3];
    *overrun = 0u;
    *more = false;
    if (s_addr == 0u) { return LIS3DH_ERR_BUS; }        /* pre-init guard: no HAL traffic */
    if (lis3dh_hal_read(s_addr, 0x2Fu, &src, 1u) != 0) { return LIS3DH_ERR_BUS; }
    *overrun = (uint8_t)((src & 0x40u) != 0u);          /* OVRN_FIFO at the first read only */
    for (;;) {
        n = unread(src);
        if (n == 0u) { break; }
        if (n > LIS3DH_BURST_MAX) { n = (uint8_t)LIS3DH_BURST_MAX; }
        if (lis3dh_hal_read(s_addr, 0x28u | 0x80u, raw, (uint8_t)(6u * n)) != 0) { return LIS3DH_ERR_BUS; }
        for (i = 0u; i < n; i++) {
            lis3dh_unpack(&raw[6u * i], s_axes, s);
            cb(s, ctx);
        }
        total = (int16_t)(total + n);
        bursts++;
        if (lis3dh_hal_read(s_addr, 0x2Fu, &src, 1u) != 0) { return LIS3DH_ERR_BUS; }
        if (unread(src) < 16u) { break; }
        if (bursts >= 4u) { *more = true; break; }
    }
    return total;
}

int8_t lis3dh_read_click(void)
{
    uint8_t v = 0u;
    if (s_addr == 0u) { return LIS3DH_ERR_BUS; }
    if (lis3dh_hal_read(s_addr, 0x39u, &v, 1u) != 0) { return LIS3DH_ERR_BUS; }
    return (int8_t)(((v & 0x60u) == 0x60u) ? 1 : 0);    /* R3: IA and DCLICK */
}
// [END AI-GENERATED]
