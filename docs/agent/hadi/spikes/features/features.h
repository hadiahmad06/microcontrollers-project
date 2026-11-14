// [AI-GENERATED: Claude Code]
#ifndef FEATURES_H
#define FEATURES_H

#include <stdint.h>

#define FEAT_WINDOW_LEN 150  /* samples per window            */
#define FEAT_AXES       3    /* X, Y, Z                       */
#define FEAT_SEG_LEN    15   /* samples per segment           */
#define FEAT_SEGMENTS   10   /* segments per window           */
#define FEAT_COUNT      60   /* output features               */
#define FEAT_ENERGY_SHIFT 11 /* right shift applied to energy */

/**
 * Extract the 60 integer features from one capture window.
 *
 * For each axis a (0=X,1=Y,2=Z) and segment s (0..9, samples 15*s..15*s+14):
 *   out[20*a + 2*s]     = mean   = trunc_toward_zero(sum(x) / 15)
 *   out[20*a + 2*s + 1] = energy = min(32767, sum((x-mean)^2) >> 11)
 *
 * @param x   Window, sample-major: x[i][0]=X, x[i][1]=Y, x[i][2]=Z. Every
 *            value MUST be in [-2048, 2047] (pending contract C1); behaviour
 *            outside that range is undefined (int16 sum may overflow).
 * @param out Output array of 60 int16_t features, written completely.
 * @return    None.
 */
void features_extract(const int16_t x[150][3], int16_t out[60]);

#endif
// [END AI-GENERATED]
