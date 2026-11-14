// [AI-GENERATED: Claude Code]
#ifndef FEATURES_H
#define FEATURES_H

#include <stdint.h>

#define FEAT_WINDOW_LEN 150  /* samples per window (1.5 s at 100 Hz)  */
#define FEAT_AXES       3    /* X, Y, Z                               */
#define FEAT_SEG_LEN    15   /* samples per segment                   */
#define FEAT_SEGMENTS   10   /* segments per window                   */
#define FEAT_COUNT      60   /* output features                       */

/*
 * Energy scaling mode (compile-time, see docs/agent/hadi/proposals/C3_features.md D4):
 *   0 = shift:   min(32767, SS >> FEAT_ENERGY_SHIFT)       (SS = sum of squared deviations)
 *   1 = isqrt:   floor(sqrt(SS))                           range 0..7912, no saturation
 *   2 = isqrt15: floor(sqrt(SS / 15)), SS/15 truncated     RMS deviation in LSB, range 0..2043
 * The DEFAULT stays mode 0 / shift 11 (the originally reviewed spec, which the independent
 * QA oracle in spikes/features_qa checks) until Hadi decides D4; the proposal recommends mode 1.
 */
#ifndef FEAT_ENERGY_MODE
#define FEAT_ENERGY_MODE 0
#endif
#ifndef FEAT_ENERGY_SHIFT
#define FEAT_ENERGY_SHIFT 11
#endif

/**
 * Extract the 60 integer features from one capture window.
 *
 * For each axis a (0=X,1=Y,2=Z) and segment s (0..9, samples 15*s..15*s+14):
 *   out[20*a + 2*s]     = mean   = trunc_toward_zero(sum(x) / 15)
 *   out[20*a + 2*s + 1] = energy = f(sum((x-mean)^2)), f chosen by FEAT_ENERGY_MODE
 *
 * @param x   Window, sample-major: x[i][0]=X, x[i][1]=Y, x[i][2]=Z. Every
 *            value MUST be in [-2048, 2047] (contract C1); behaviour outside that
 *            range is undefined (the int16 sum may overflow). The parameter is
 *            deliberately NOT const-qualified: xc16-gcc 2.10 warns "incompatible
 *            pointer type" when a plain int16_t[150][3] is passed to a
 *            const int16_t (*)[3] parameter. The function never writes to x.
 * @param out Output array of 60 int16_t features, written completely.
 * @return    None.
 */
void features_extract(int16_t (*x)[3], int16_t out[60]);

#if FEAT_ENERGY_MODE != 0
/**
 * Exact integer square root (only built when FEAT_ENERGY_MODE is 1 or 2), floor(sqrt(n)), digit-by-digit (no multiply, no divide).
 *
 * @param n Any uint32_t value.
 * @return  The largest r with r*r <= n (0..65535).
 */
uint16_t features_isqrt32(uint32_t n);
#endif

#endif
// [END AI-GENERATED]
