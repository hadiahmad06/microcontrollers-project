// [AI-GENERATED: Claude Code]
/**
 * @file lis3dh.h
 * @brief LIS3DH accelerometer driver over an I2C HAL (ticket WP1-b; contracts C0, C1, C6.1).
 *
 * 100 Hz, +/-4 g, high resolution, FIFO in Stream mode (FTH = 15 on INT1), double click on INT2.
 * Register facts: ST LIS3DH datasheet DocID17530, and AN3308 Rev 3 (FIFO and click usage).
 * No float, no malloc, no blocking delays; the HAL (lis3dh_hal.h) is the only hardware access.
 */
#ifndef LIS3DH_H
#define LIS3DH_H

#include <stdint.h>
#include <stdbool.h>
#include "board_axes.h"

#define LIS3DH_OK          0
#define LIS3DH_ERR_SENSOR (-2)  /**< no WHO_AM_I = 0x33 at 0x18 or 0x19 (matches gesture_init's -2) */
#define LIS3DH_ERR_BUS    (-3)  /**< HAL error or config read-back mismatch */
#define LIS3DH_BURST_MAX  16u   /**< samples per burst read (C1.10: 96 B staging) */

/** Receives one sample in wand frame, int16 in [-2048, 2047] (C1.1). ctx is passed through. */
typedef void (*lis3dh_sample_cb)(const int16_t s[3], void *ctx);

/**
 * Probe, configure and start the sensor (C6.1, C1.4, C0).
 * @param axes sensor-to-wand axis table, kept by pointer (must outlive the driver);
 *             NULL selects the identity table
 * @return LIS3DH_OK, LIS3DH_ERR_SENSOR (no WHO_AM_I = 0x33 at 0x18/0x19) or
 *         LIS3DH_ERR_BUS (HAL error or a config register read back differently)
 */
int8_t lis3dh_init(const lis3dh_axes_t *axes);

/**
 * I2C address found by init.
 * @return 0x18 or 0x19 after a successful init, otherwise 0
 */
uint8_t lis3dh_address(void);

/**
 * Convert one 6-byte OUT_X_L..OUT_Z_H record to wand-frame samples (C1.1, C1.3).
 * @param raw  X_L, X_H, Y_L, Y_H, Z_L, Z_H as read from the sensor
 * @param axes axis table (NULL = identity)
 * @param out  receives wand X, Y, Z, each in [-2048, 2047]
 */
void lis3dh_unpack(const uint8_t raw[6], const lis3dh_axes_t *axes, int16_t out[3]);

/**
 * Drain the FIFO per C1.4: at most 4 bursts of <= 16 samples per call, samples delivered strictly in order.
 * @param cb       called once per sample, in order (must not be NULL)
 * @param ctx      passed to cb
 * @param overrun  set to 1 if FIFO_SRC had OVRN_FIFO at the first read of this call, else 0 (may be NULL)
 * @param more     set true if the call stopped at the 4-burst bound with FSS still >= 16 (may be NULL)
 * @return samples delivered (>= 0) or LIS3DH_ERR_BUS
 */
int16_t lis3dh_drain(lis3dh_sample_cb cb, void *ctx, uint8_t *overrun, bool *more);

/**
 * Read CLICK_SRC (this also clears a latched click interrupt, since CLICK_THS bit 7 latches).
 * @return 1 if IA and DCLICK are both set, 0 if not, LIS3DH_ERR_BUS on a bus error
 */
int8_t lis3dh_read_click(void);

#endif /* LIS3DH_H */
// [END AI-GENERATED]
