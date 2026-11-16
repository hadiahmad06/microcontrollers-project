// [AI-GENERATED: Claude Code]
/**
 * @file gesture.h
 * @brief Public gesture API (CONTRACTS "API", ticket 3.7): eight functions that glue the sensor driver,
 *        capture, trigger, features, MLP, k-NN, classifier and the C2 UART sender into one service.
 *
 * WORKING ASSUMPTION: open_questions Q1 (C2), Q2 (trigger C1b), Q3 (keep C1.6), not decided.
 *
 * Usage: gesture_init() once, then call gesture_poll() every main-loop iteration; when it returns true call
 * gesture_classify() (and optionally gesture_learn()). All functions are non-blocking. Interrupt handlers only
 * set the flags read through gesture_port.h; nothing here is called from an ISR.
 * Design: docs/agent/hadi/proposals/API_glue.md, docs/agent/hadi/briefs/3.7_spec.md.
 * C99, fixed-width types, no float, no malloc.
 */
#ifndef GESTURE_H
#define GESTURE_H

#include <stdbool.h>
#include <stdint.h>
#include "gesture_ids.h"

/**
 * Initialise the whole stack and arm the capture. Queues the ASCII boot line GM_MODEL_HASH=0x........ on the
 * C2 transmitter.
 * @param odr_hz  output data rate the application expects; must equal the model's GM_ODR_HZ
 * @param range_g full-scale range in g the application expects; must equal the model's GM_RANGE_G
 * @return 0 ok; -1 odr_hz or range_g differs from the model; -2 sensor not usable (no LIS3DH found, or an I2C
 *         bus error / configuration read-back mismatch)
 */
int8_t gesture_init(uint8_t odr_hz, uint8_t range_g);

/**
 * Set the motion-trigger threshold (trigger C1b). Does nothing before a successful gesture_init().
 * @param threshold_mg threshold in mg of L1 deviation summed over three axes; 0 disables triggering
 */
void gesture_set_trigger(uint16_t threshold_mg);

/**
 * One non-blocking service step: drain the sensor FIFO when its watermark flag is set or 50 ms passed, run the
 * trigger and capture, handle a double-tap click, and pump the C2 transmitter. Call every main-loop iteration.
 * @return true iff a capture window is READY and has not been classified yet. Always false before a
 *         successful init and in the bring-up build (GESTURE_BRINGUP_SAMPLES).
 */
bool gesture_poll(void);

/**
 * Classify the READY window (features, MLP, optional k-NN override, reject rule; C5.2).
 * @param confidence if not NULL, receives the confidence 0..255 (also when the result is rejected; 0 when no
 *                   window was available)
 * @return class id 0..8 (MLP) or 9..12 (learned), or GESTURE_UNKNOWN when rejected, when no unclassified
 *         window is READY (including a second call for the same window), or before init
 */
int8_t gesture_classify(uint8_t *confidence);

/**
 * Store the most recently classified window as a template of a learned class (C5.2, C1.12).
 * @param class_id learned class id in [GESTURE_LEARNED_BASE, GESTURE_LEARNED_BASE + GESTURE_MAX_LEARNED - 1]
 * @return templates now stored for the class (>= 1), GESTURE_LEARN_ERR_ID for a bad id, or
 *         GESTURE_LEARN_ERR_NO_WINDOW when no classified window is available (also before init, and for a
 *         window that was already learned)
 */
int8_t gesture_learn(uint8_t class_id);

/**
 * Set the reject threshold: results with confidence < min_conf become GESTURE_UNKNOWN (0 disables). Works before
 * or after gesture_init() and persists until reset (C5.2).
 * @param min_conf reject threshold
 */
void gesture_set_reject(uint8_t min_conf);

/**
 * Switch the C2 raw stream (WINDOW frames after every classify, HELLO beacon every 2 s) on or off. A frame that
 * is pending or in flight when it is switched off still completes. Does nothing before init.
 * @param on true to stream, false to stop
 */
void gesture_stream_raw(bool on);

/**
 * Read and clear the event bits.
 * @return bit mask of GESTURE_EVT_* seen since the last call (0 before init)
 */
uint8_t gesture_events(void);

#endif /* GESTURE_H */
// [END AI-GENERATED]
