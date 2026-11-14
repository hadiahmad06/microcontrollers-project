// [AI-GENERATED: Claude Code]
/**
 * @file board_axes.h
 * @brief The one table that maps LIS3DH sensor axes to the wand frame (contract C1.3).
 *
 * Wand frame: X out of the tip, Y to the left, Z up, right-handed; a resting axis pointing up
 * reads +1 g. Wand axis k = sign[k] * sensor axis src[k] (src: 0 = X, 1 = Y, 2 = Z; sign: +1 or -1).
 * Identity until the tilt test of C1 section 3.3 (BENCH C-8) fixes the real mounting.
 */
#ifndef BOARD_AXES_H
#define BOARD_AXES_H

#include <stdint.h>

/** Axis permutation and signs from sensor frame to wand frame. */
typedef struct {
    uint8_t src[3];   /**< sensor axis index (0..2) feeding wand axis k */
    int8_t  sign[3];  /**< +1 or -1 applied to that sensor axis */
} lis3dh_axes_t;

/** Initialiser for the board's axis table (BENCH C-8: identity for now). */
#define LIS3DH_BOARD_AXES { {0u, 1u, 2u}, {1, 1, 1} }

#endif /* BOARD_AXES_H */
// [END AI-GENERATED]
