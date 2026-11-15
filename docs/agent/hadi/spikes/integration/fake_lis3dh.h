// [AI-GENERATED: Claude Code]
/*
 * fake_lis3dh.h - register-file model of a LIS3DH on I2C, used to test lis3dh.c on the host and
 * under sim16. Written from the spec (C1.4, C6.1, the LIS3DH FIFO facts in the C1/C6a proposals),
 * not from lis3dh.c. It implements lis3dh_hal_write / lis3dh_hal_read (lis3dh_hal.h).
 *
 * Modelled: probe address (0x18 / 0x19 / none), configurable WHO_AM_I, a 32-deep Stream FIFO,
 * FIFO_SRC computed from the fill level, OVRN at 32 unread, discard-oldest on a push into a full
 * FIFO, Bypass clearing the FIFO, burst reads that pop one sample per 6-byte group with the
 * 0x2D -> 0x28 wrap, CLICK_SRC cleared on read, fault injection and a transaction log.
 *
 * FSS ambiguity (known): FSS is 5 bits, so 32 unread cannot be written as 32. Two models:
 *   FAKE_FSS32_SATURATE  FSS = min(unread, 31), OVRN = 1 at 32 unread (default, the brief's model)
 *   FAKE_FSS32_WRAP      FSS = unread & 0x1F, i.e. 0 at 32 unread, OVRN = 1
 */
#ifndef FAKE_LIS3DH_H
#define FAKE_LIS3DH_H

#include <stdint.h>

#define FAKE_LOG_MAX 16u     /* SPIKE: was 128; the log is unused here and RAM is tight on sim16 */
#define FAKE_F_MSB   0x01u   /* log flag: the sub-address had bit 7 (auto-increment) set */
#define FAKE_F_NACK  0x02u   /* log flag: the transaction was NACKed (no effect, HAL returned -1) */

/** One logged I2C transaction. */
typedef struct {
    uint8_t is_read;  /**< 1 = read, 0 = write */
    uint8_t addr;     /**< 7-bit address used */
    uint8_t reg;      /**< register, bit 7 stripped */
    uint8_t n;        /**< bytes read (1 for a write) */
    uint8_t val;      /**< write: value written; read: first byte returned (0 if NACKed) */
    uint8_t flags;    /**< FAKE_F_* */
} fake_txn_t;

/** How FIFO_SRC reports a completely full FIFO (32 unread). */
typedef enum { FAKE_FSS32_SATURATE = 0, FAKE_FSS32_WRAP = 1 } fake_fss32_t;

/**
 * Reset the whole fake: registers to power-on, FIFO empty, log cleared, all faults off,
 * WHO_AM_I = 0x33, sample sequence counter = 0.
 *
 * @param present_addr 7-bit address the sensor answers on (0x18 or 0x19), or 0 for no sensor.
 * @return None.
 */
void fake_reset(uint8_t present_addr);

/**
 * Set the WHO_AM_I value the sensor returns.
 *
 * @param who Value of register 0x0F.
 * @return None.
 */
void fake_set_who(uint8_t who);

/**
 * Choose how FIFO_SRC reports 32 unread samples.
 *
 * @param m FAKE_FSS32_SATURATE or FAKE_FSS32_WRAP.
 * @return None.
 */
void fake_set_fss32(fake_fss32_t m);

/**
 * Set the value the next CLICK_SRC (0x39) read returns; the register then clears to 0.
 *
 * @param v CLICK_SRC value (bit 6 IA, bit 5 DCLICK, bit 4 SCLICK ...).
 * @return None.
 */
void fake_set_click_src(uint8_t v);

/**
 * Deterministic raw 16-bit register word (left-justified 12-bit value, low nibble holds garbage)
 * for sample number seq on sensor axis 0..2. The 12-bit value is never -2048.
 *
 * @param seq Sample sequence number (0 = first sample ever pushed after fake_reset).
 * @param axis Sensor axis, 0 = X, 1 = Y, 2 = Z.
 * @return The word the sensor reports (OUT_x_H:OUT_x_L).
 */
uint16_t fake_sample_word(uint16_t seq, uint8_t axis);

/**
 * Push count new samples (sequence numbers continue from fake_next_seq) into the FIFO as the
 * sensor would at its output data rate. Ignored (counted as rejected) unless the FIFO is
 * enabled (CTRL_REG5 bit 6) and in Stream mode. A push into a full FIFO discards the oldest.
 *
 * @param count Number of samples to push.
 * @return None.
 */
void fake_push_next(uint16_t count);

/**
 * SPIKE ADDITION. Push one given wand/sensor-frame sample (identity axis table assumed) as the next FIFO
 * entry, with the same Stream-mode rules as fake_push_next (ignored unless the FIFO is active; a push
 * into a full FIFO discards the oldest).
 *
 * @param s Three values in [-2048, 2047].
 * @return None.
 */
void fake_push_sample(const int16_t s[3]);

/**
 * Make k more samples arrive after every read that popped at least one sample ("samples arriving
 * between bursts").
 *
 * @param k Samples per burst (0 = off).
 * @param total_cap Maximum samples to add this way in total.
 * @return None.
 */
void fake_set_arrivals(uint8_t k, uint16_t total_cap);

/**
 * Sequence number the next pushed sample will get (= total samples pushed so far).
 *
 * @return Next sequence number.
 */
uint16_t fake_next_seq(void);

/**
 * Unread samples currently in the FIFO.
 *
 * @return 0..32.
 */
uint8_t fake_fifo_level(void);

/**
 * Number of samples lost to Stream-mode overflow since fake_reset.
 *
 * @return Lost sample count.
 */
uint16_t fake_lost(void);

/**
 * True when the FIFO is accepting samples (CTRL_REG5 FIFO_EN and FIFO_CTRL FM = Stream).
 *
 * @return 1 if active, else 0.
 */
uint8_t fake_fifo_active(void);

/**
 * Current content of a register as stored (read without side effects, no log entry).
 *
 * @param reg Register address 0x00..0x3F.
 * @return Stored value.
 */
uint8_t fake_reg(uint8_t reg);

/**
 * Empty the transaction log and restart the transaction / FIFO_SRC-read / burst counters used by
 * the fault injectors below.
 *
 * @return None.
 */
void fake_clear_log(void);

/**
 * Number of logged transactions (capped at FAKE_LOG_MAX).
 *
 * @return Entries available.
 */
uint16_t fake_log_count(void);

/**
 * Access one logged transaction.
 *
 * @param i Index 0 .. fake_log_count() - 1, oldest first.
 * @return Pointer to the entry (valid until the next fake_clear_log / fake_reset).
 */
const fake_txn_t *fake_log_get(uint16_t i);

/**
 * Fault: NACK the n-th transaction counted since fake_clear_log, on any address and register.
 *
 * @param n 1-based transaction number; 0 disables.
 * @return None.
 */
void fake_nack_txn(uint16_t n);

/**
 * Fault: NACK the n-th read of FIFO_SRC (0x2F) since fake_clear_log.
 *
 * @param n 1-based; 0 disables.
 * @return None.
 */
void fake_nack_fifo_src(uint8_t n);

/**
 * Fault: NACK the n-th FIFO burst read (a read starting at OUT_X_L 0x28) since fake_clear_log.
 *
 * @param n 1-based; 0 disables.
 * @return None.
 */
void fake_nack_burst(uint8_t n);

/**
 * Fault: reads of this register return the stored value with bit 0 flipped (read-back mismatch).
 *
 * @param reg Register address, or 0xFF to disable.
 * @return None.
 */
void fake_corrupt_readback(uint8_t reg);

#endif
// [END AI-GENERATED]
