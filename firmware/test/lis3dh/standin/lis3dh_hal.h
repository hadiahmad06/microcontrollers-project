// [AI-GENERATED: Claude Code]
/* STAND-IN (test harness proof only; the real file is firmware/src/lis3dh_hal.h). */
#ifndef LIS3DH_HAL_H
#define LIS3DH_HAL_H
#include <stdint.h>

/**
 * Write one register over I2C.
 *
 * @param addr7 7-bit device address.
 * @param reg Register address.
 * @param val Value to write.
 * @return 0 on success, negative on a bus error (NACK, timeout).
 */
int8_t lis3dh_hal_write(uint8_t addr7, uint8_t reg, uint8_t val);

/**
 * Read n bytes starting at a register.
 *
 * @param addr7 7-bit device address.
 * @param reg Start register (bit 7 set = auto-increment).
 * @param buf Destination.
 * @param n Number of bytes.
 * @return 0 on success, negative on a bus error.
 */
int8_t lis3dh_hal_read(uint8_t addr7, uint8_t reg, uint8_t *buf, uint8_t n);

#endif
// [END AI-GENERATED]
