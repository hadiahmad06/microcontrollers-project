// [AI-GENERATED: Claude Code]
/**
 * @file lis3dh_hal.h
 * @brief The only hardware dependency of lis3dh.c: a synchronous I2C master (ticket WP1-b, C6.1).
 *
 * The board implements these two functions on I2C1 (400 kHz, C6.1); the host/sim16 tests implement
 * them with a fake sensor. Both calls block until the transfer is complete or failed and are called
 * from the main loop only (allowed by C1.4), never from an ISR.
 */
#ifndef LIS3DH_HAL_H
#define LIS3DH_HAL_H

#include <stdint.h>

/**
 * Write one register of a 7-bit-addressed I2C device.
 * @param addr7 7-bit device address (0x18 or 0x19 for the LIS3DH)
 * @param reg   register sub-address
 * @param val   byte to write
 * @return 0 on success, < 0 on bus error or NACK
 */
int8_t lis3dh_hal_write(uint8_t addr7, uint8_t reg, uint8_t val);

/**
 * Read n bytes starting at a register.
 * @param addr7 7-bit device address
 * @param reg   first register sub-address; the caller sets bit 7 (reg | 0x80) when n > 1 so the
 *              LIS3DH auto-increments (DocID17530 section 5.1.1)
 * @param buf   destination, at least n bytes
 * @param n     number of bytes to read (>= 1)
 * @return 0 on success, < 0 on bus error or NACK
 */
int8_t lis3dh_hal_read(uint8_t addr7, uint8_t reg, uint8_t *buf, uint8_t n);

#endif /* LIS3DH_HAL_H */
// [END AI-GENERATED]
