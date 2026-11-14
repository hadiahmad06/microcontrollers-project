// [AI-GENERATED: Claude Code]
/* STAND-IN (test harness proof only; the real file is firmware/src/lis3dh.h). */
#ifndef LIS3DH_H
#define LIS3DH_H
#include <stdint.h>
#include <stdbool.h>
#include "board_axes.h"

#define LIS3DH_OK 0
#define LIS3DH_ERR_SENSOR (-2)
#define LIS3DH_ERR_BUS (-3)
#define LIS3DH_BURST_MAX 16u

typedef void (*lis3dh_sample_cb)(const int16_t s[3], void *ctx);

/**
 * Probe 0x18 then 0x19, verify WHO_AM_I, configure FIFO (Stream, FTH 15), click and ODR.
 *
 * @param axes Sensor-to-wand axis table, copied.
 * @return LIS3DH_OK, LIS3DH_ERR_SENSOR (no/wrong sensor) or LIS3DH_ERR_BUS.
 */
int8_t lis3dh_init(const lis3dh_axes_t *axes);

/**
 * Address found by lis3dh_init.
 *
 * @return 7-bit address.
 */
uint8_t lis3dh_address(void);

/**
 * Convert one 6-byte burst group (X_L X_H Y_L Y_H Z_L Z_H) to wand-frame counts.
 *
 * @param raw 6 bytes as read from OUT_X_L.
 * @param axes Remap table.
 * @param out Three int16 results.
 * @return None.
 */
void lis3dh_unpack(const uint8_t raw[6], const lis3dh_axes_t *axes, int16_t out[3]);

/**
 * Drain the FIFO per C1.4 (at most 4 bursts of at most 16 samples).
 *
 * @param cb Called once per sample, oldest first.
 * @param ctx Passed to cb.
 * @param overrun OVRN_FIFO seen at the first FIFO_SRC read of this call.
 * @param more Set when stopped by the burst bound while FSS >= 16.
 * @return Samples delivered, or LIS3DH_ERR_BUS.
 */
int16_t lis3dh_drain(lis3dh_sample_cb cb, void *ctx, uint8_t *overrun, bool *more);

/**
 * Read (and clear) CLICK_SRC.
 *
 * @return CLICK_SRC value, or LIS3DH_ERR_BUS.
 */
int8_t lis3dh_read_click(void);

#endif
// [END AI-GENERATED]
