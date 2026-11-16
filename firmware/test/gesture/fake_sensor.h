// [AI-GENERATED: Claude Code]
/*
 * fake_sensor.h - LIS3DH register-file fake with EXPLICIT samples (test-only), for the gesture suite.
 * Derived from firmware/test/lis3dh/fake_lis3dh.c (same register model: 32-deep Stream FIFO, FIFO_SRC
 * from the fill level, burst reads pop one sample per 6-byte group with the 0x2D -> 0x28 wrap,
 * CLICK_SRC cleared on read), but the pushed samples are given by the caller instead of a formula,
 * and discarded samples are reported as seq ranges. Implements lis3dh_hal_write / lis3dh_hal_read.
 */
#ifndef FAKE_SENSOR_H
#define FAKE_SENSOR_H

#include <stdint.h>

/**
 * Reset the fake to power-on state.
 * @param present_addr 7-bit address the sensor answers on (0x18 / 0x19) or 0 for no sensor
 * @param who          WHO_AM_I value returned
 * @param corrupt_reg  register whose first read-back has bit 0 flipped, or 0xFF for none
 */
void fs_reset(uint8_t present_addr, uint8_t who, uint8_t corrupt_reg);
/** Push one wand-frame sample (12-bit range) as a sensor sample; dropped unless the FIFO is active.
 *  @param s x, y, z in [-2048, 2047] (the board axes table is assumed to be the identity) */
void fs_push(const int16_t s[3]);
/** @return unread samples in the FIFO (0..32) */
uint8_t fs_level(void);
/** Set the value the next CLICK_SRC read returns (cleared on read). @param v CLICK_SRC byte */
void fs_set_click(uint8_t v);
/** Bus-error injection: every I2C call NACKs after n more samples were popped (n = 0: from now on). @param n pops */
void fs_bus_fail_after(uint8_t n);
/** Clear the bus-error injection. */
void fs_bus_ok(void);
/** @return number of samples pushed so far (sequence number of the next one) */
uint16_t fs_next_seq(void);
/** @return number of discarded-sample seq ranges recorded (max 4) */
uint8_t fs_gap_count(void);
/** Read one discarded range. @param i index @param first first lost seq @param cnt samples lost */
void fs_gap(uint8_t i, uint16_t *first, uint16_t *cnt);

#endif /* FAKE_SENSOR_H */
// [END AI-GENERATED]
