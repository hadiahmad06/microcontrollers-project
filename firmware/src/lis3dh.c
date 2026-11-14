// [AI-GENERATED: Claude Code]
/**
 * @file lis3dh.c
 * @brief LIS3DH driver: probe, register config, FIFO drain, unpack + axis remap, click read.
 *
 * Register facts: ST LIS3DH datasheet DocID17530 (register map, FIFO, click) and AN3308 Rev 3.
 * Spec: docs/agent/CONTRACTS.md C0, C1.1, C1.3, C1.4, C1.6, C1.10, C6.1.
 */
#include "lis3dh.h"
#include "lis3dh_hal.h"

/* Register addresses (DocID17530 table 17) */
#define REG_WHO_AM_I      0x0Fu
#define REG_CTRL1         0x20u
#define REG_CTRL3         0x22u
#define REG_CTRL4         0x23u
#define REG_CTRL5         0x24u
#define REG_CTRL6         0x25u
#define REG_OUT_X_L       0x28u
#define REG_FIFO_CTRL     0x2Eu
#define REG_FIFO_SRC      0x2Fu
#define REG_CLICK_CFG     0x38u
#define REG_CLICK_SRC     0x39u
#define REG_CLICK_THS     0x3Au
#define REG_TIME_LIMIT    0x3Bu
#define REG_TIME_LATENCY  0x3Cu
#define REG_TIME_WINDOW   0x3Du

#define WHO_AM_I_VALUE    0x33u
#define AUTO_INC          0x80u  /* sub-address MSB: auto-increment on multi-byte reads */
#define FSS_MASK          0x1Fu  /* FIFO_SRC bits 4:0, unread samples */
#define FIFO_SRC_OVRN     0x40u  /* FIFO_SRC bit 6 OVRN_FIFO */
#define CLICK_SRC_IA      0x40u  /* CLICK_SRC bit 6 */
#define CLICK_SRC_DCLICK  0x20u  /* CLICK_SRC bit 5 */
#define MAX_BURSTS        4u     /* bursts per lis3dh_drain call (main-agent ruling: 64 samples) */
#define BYTES_PER_SAMPLE  6u

static const lis3dh_axes_t s_identity = { {0u, 1u, 2u}, {1, 1, 1} };

static const lis3dh_axes_t *s_axes = &s_identity;
static uint8_t s_addr;                                   /* 0 until init succeeds */
static uint8_t s_stage[LIS3DH_BURST_MAX * BYTES_PER_SAMPLE]; /* drain staging, 96 B (C1.10) */

/** Write a config register and read it back (main-agent ruling: every config write is verified). */
static int8_t write_verify(uint8_t reg, uint8_t val)
{
    uint8_t rb = 0u;
    if (lis3dh_hal_write(s_addr, reg, val) < 0) {
        return LIS3DH_ERR_BUS;
    }
    if (lis3dh_hal_read(s_addr, reg, &rb, 1u) < 0) {
        return LIS3DH_ERR_BUS;
    }
    return (rb == val) ? LIS3DH_OK : LIS3DH_ERR_BUS;
}

int8_t lis3dh_init(const lis3dh_axes_t *axes)
{
    static const uint8_t cand[2] = { 0x18u, 0x19u };
    uint8_t i;
    uint8_t who;

    s_axes = (axes != 0) ? axes : &s_identity;
    s_addr = 0u;

    /* Probe 0x18 then 0x19 (C6.1); the first that answers WHO_AM_I = 0x33 wins. */
    for (i = 0u; i < 2u; i++) {
        who = 0u;
        if (lis3dh_hal_read(cand[i], REG_WHO_AM_I, &who, 1u) < 0) {  /* NACK = nobody here */
            continue;
        }
        if (who == WHO_AM_I_VALUE) {
            s_addr = cand[i];
            break;
        }
    }
    if (s_addr == 0u) {
        return LIS3DH_ERR_SENSOR;
    }

    /* Write order is a main-agent ruling; BDU (CTRL_REG4 bit 7) stays 0, UNVERIFIED, bench check. */

    /* CTRL_REG1 = 0x00: ODR3..0 (7:4) = 0000 power-down, LPen (3) = 0, Zen/Yen/Xen (2:0) = 0.
     * Configure with the sensor stopped. */
    if (write_verify(REG_CTRL1, 0x00u) != LIS3DH_OK) { return LIS3DH_ERR_BUS; }

    /* CTRL_REG4 = 0x18: BDU (7) = 0, BLE (6) = 0, FS1:FS0 (5:4) = 01 (+/-4 g), HR (3) = 1
     * (high resolution, 12-bit), ST1:ST0 (2:1) = 00 self-test off, SIM (0) = 0. */
    if (write_verify(REG_CTRL4, 0x18u) != LIS3DH_OK) { return LIS3DH_ERR_BUS; }

    /* CTRL_REG3 = 0x06: I1_CLICK (7) = 0, I1_IA1 (6) = 0, I1_IA2 (5) = 0, I1_ZYXDA (4) = 0,
     * I1_321DA (3) = 0, I1_WTM (2) = 1 FIFO watermark on INT1, I1_OVERRUN (1) = 1 overrun on INT1
     * (C1.6), bit 0 unused = 0. */
    if (write_verify(REG_CTRL3, 0x06u) != LIS3DH_OK) { return LIS3DH_ERR_BUS; }

    /* CTRL_REG6 = 0x80: I2_CLICK (7) = 1 click on INT2, I2_IA1 (6) = 0, I2_IA2 (5) = 0,
     * I2_BOOT (4) = 0, I2_ACT (3) = 0, bit 2 = 0, INT_POLARITY (1) = 0 active high (rising edge). */
    if (write_verify(REG_CTRL6, 0x80u) != LIS3DH_OK) { return LIS3DH_ERR_BUS; }

    /* CLICK_CFG = 0x2A: ZD (5) = 1, ZS (4) = 0, YD (3) = 1, YS (2) = 0, XD (1) = 1, XS (0) = 0
     * (double click on X, Y, Z); bits 7:6 = 0 (LIR reserved / unused). */
    if (write_verify(REG_CLICK_CFG, 0x2Au) != LIS3DH_OK) { return LIS3DH_ERR_BUS; }

    /* CLICK_THS = 0xB0: bit 7 = 1 (latch interrupt until CLICK_SRC is read), bits 6:0 = 0x30
     * = 48 counts (1.5 g at +/-4 g). Bench question C-7: does bit 7 read back as written? */
    if (write_verify(REG_CLICK_THS, 0xB0u) != LIS3DH_OK) { return LIS3DH_ERR_BUS; }

    /* TIME_LIMIT = 0x04: bits 6:0 = max click duration, 4 ODR periods (40 ms). */
    if (write_verify(REG_TIME_LIMIT, 0x04u) != LIS3DH_OK) { return LIS3DH_ERR_BUS; }

    /* TIME_LATENCY = 0x10: dead time after a click, 16 ODR periods (160 ms). */
    if (write_verify(REG_TIME_LATENCY, 0x10u) != LIS3DH_OK) { return LIS3DH_ERR_BUS; }

    /* TIME_WINDOW = 0x30: window for the second click, 48 ODR periods (480 ms). */
    if (write_verify(REG_TIME_WINDOW, 0x30u) != LIS3DH_OK) { return LIS3DH_ERR_BUS; }

    /* CTRL_REG5 = 0x40: BOOT (7) = 0, FIFO_EN (6) = 1, LIR_INT1 (3) = 0, D4D_INT1 (2) = 0,
     * LIR_INT2 (1) = 0, D4D_INT2 (0) = 0. */
    if (write_verify(REG_CTRL5, 0x40u) != LIS3DH_OK) { return LIS3DH_ERR_BUS; }

    /* FIFO_CTRL_REG = 0x00: FM1:FM0 (7:6) = 00 Bypass (this clears the FIFO), TR (5) = 0,
     * FTH4:0 (4:0) = 0. */
    if (write_verify(REG_FIFO_CTRL, 0x00u) != LIS3DH_OK) { return LIS3DH_ERR_BUS; }

    /* FIFO_CTRL_REG = 0x8F: FM1:FM0 (7:6) = 10 Stream mode, TR (5) = 0 (trigger on INT1),
     * FTH4:0 (4:0) = 01111 = 15 (watermark, C1.4). */
    if (write_verify(REG_FIFO_CTRL, 0x8Fu) != LIS3DH_OK) { return LIS3DH_ERR_BUS; }

    /* CTRL_REG1 = 0x57 (last: starts sampling): ODR3..0 (7:4) = 0101 (100 Hz), LPen (3) = 0
     * (with HR = 1: high resolution), Zen (2) = 1, Yen (1) = 1, Xen (0) = 1. */
    if (write_verify(REG_CTRL1, 0x57u) != LIS3DH_OK) { return LIS3DH_ERR_BUS; }

    return LIS3DH_OK;
}

uint8_t lis3dh_address(void)
{
    return s_addr;
}

void lis3dh_unpack(const uint8_t raw[6], const lis3dh_axes_t *axes, int16_t out[3])
{
    int16_t sv[3];
    uint8_t k;
    uint8_t s;
    const lis3dh_axes_t *a = (axes != 0) ? axes : &s_identity;

    for (k = 0u; k < 3u; k++) {
        /* C1.1: left-justified 16-bit word, arithmetic shift right by 4 -> [-2048, 2047]. */
        int16_t w = (int16_t)(((uint16_t)raw[2u * k + 1u] << 8) | raw[2u * k]);
        sv[k] = (int16_t)(w >> 4);
    }
    for (k = 0u; k < 3u; k++) {
        s = a->src[k];
        if (s > 2u) {
            s = 0u;  /* defensive: a bad table must not index out of range */
        }
        /* C1.3: wand axis k = sign * sensor axis src. -(-2048) = 2048 does not fit in the
         * contract range, so clamp it to 2047 (cannot occur with a +/-1 sign on a 12-bit value
         * except for the one value -2048). */
        if (a->sign[k] < 0) {
            out[k] = (sv[s] == -2048) ? (int16_t)2047 : (int16_t)(-sv[s]);
        } else {
            out[k] = sv[s];
        }
    }
}

int16_t lis3dh_drain(lis3dh_sample_cb cb, void *ctx, uint8_t *overrun, bool *more)
{
    uint8_t src = 0u;
    uint8_t n;
    uint8_t k;
    uint8_t j;
    uint8_t bursts = 0u;
    bool    first = true;
    int16_t total = 0;
    int16_t sample[3];

    if (overrun != 0) { *overrun = 0u; }
    if (more != 0)    { *more = false; }

    for (;;) {
        if (lis3dh_hal_read(s_addr, REG_FIFO_SRC, &src, 1u) < 0) {
            return LIS3DH_ERR_BUS;
        }
        if (first && (overrun != 0) && ((src & FIFO_SRC_OVRN) != 0u)) {
            *overrun = 1u;  /* OVRN_FIFO seen at drain start (C1.6); caller decides */
        }
        n = (uint8_t)(src & FSS_MASK);
        /* First read: stop when empty. Re-reads: stop when FSS < 16 (C1.4). */
        if (first ? (n == 0u) : (n < LIS3DH_BURST_MAX)) {
            break;
        }
        if (bursts >= MAX_BURSTS) {
            if (more != 0) { *more = true; }
            break;
        }
        first = false;
        k = (n < LIS3DH_BURST_MAX) ? n : (uint8_t)LIS3DH_BURST_MAX;

        /* One burst of 6*k bytes from OUT_X_L with the auto-increment bit set. */
        if (lis3dh_hal_read(s_addr, (uint8_t)(REG_OUT_X_L | AUTO_INC), s_stage,
                            (uint8_t)(k * BYTES_PER_SAMPLE)) < 0) {
            return LIS3DH_ERR_BUS;
        }
        for (j = 0u; j < k; j++) {
            lis3dh_unpack(&s_stage[(uint8_t)(j * BYTES_PER_SAMPLE)], s_axes, sample);
            cb(sample, ctx);
        }
        total = (int16_t)(total + k);
        bursts++;
    }
    return total;
}

int8_t lis3dh_read_click(void)
{
    uint8_t v = 0u;
    if (lis3dh_hal_read(s_addr, REG_CLICK_SRC, &v, 1u) < 0) {
        return LIS3DH_ERR_BUS;
    }
    /* CLICK_SRC bit 6 IA (interrupt active) and bit 5 DCLICK (double click detected). */
    return (int8_t)(((v & (CLICK_SRC_IA | CLICK_SRC_DCLICK)) == (CLICK_SRC_IA | CLICK_SRC_DCLICK)) ? 1 : 0);
}
// [END AI-GENERATED]
