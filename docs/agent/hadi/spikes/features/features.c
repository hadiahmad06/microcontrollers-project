// [AI-GENERATED: Claude Code]
#include "features.h"

/*
 * Implementation notes (see docs/agent/hadi/proposals/C3_features.md):
 *  - Segment sum of 15 values in [-2048,2047] lies in [-30720,30705]: fits int16.
 *  - Mean uses C '/' (truncation toward zero), identical on host and XC16.
 *  - Deviation d = x-mean is in [-4095,4095]; d*d is formed in int32_t
 *    (XC16 int is 16 bit, so the cast BEFORE the multiply is mandatory).
 *  - Sum of 15 squares <= ~6.3e7 < 2^31; kept in uint32_t (always >= 0, so
 *    the right shift is a plain logical shift, no implementation-defined case).
 */

/**
 * Compute the (mean, energy) pair for one 15-sample segment of one axis.
 *
 * @param x       Window base pointer (sample-major, 3 axes).
 * @param first   Index of the first sample of the segment (0,15,...,135).
 * @param axis    Axis column, 0..2.
 * @param mean_o  Output: truncated mean of the segment.
 * @param energy_o Output: saturated, shifted sum of squared deviations.
 * @return        None.
 */
static void segment_features(const int16_t x[150][3], int16_t first, int16_t axis,
                             int16_t *mean_o, int16_t *energy_o)
{
    int16_t sum = 0;
    int16_t j;
    for (j = 0; j < FEAT_SEG_LEN; j++) {
        sum = (int16_t)(sum + x[first + j][axis]);
    }
    int16_t mean = (int16_t)(sum / 15);

    uint32_t acc = 0;
    for (j = 0; j < FEAT_SEG_LEN; j++) {
        int16_t d = (int16_t)(x[first + j][axis] - mean);
        int32_t dd = (int32_t)d * (int32_t)d;
        acc += (uint32_t)dd;
    }
    acc >>= FEAT_ENERGY_SHIFT;
    if (acc > 32767u) {
        acc = 32767u;
    }
    *mean_o = mean;
    *energy_o = (int16_t)acc;
}

void features_extract(const int16_t x[150][3], int16_t out[60])
{
    int16_t a, s;
    for (a = 0; a < FEAT_AXES; a++) {
        for (s = 0; s < FEAT_SEGMENTS; s++) {
            int16_t idx = (int16_t)(20 * a + 2 * s);
            segment_features(x, (int16_t)(FEAT_SEG_LEN * s), a, &out[idx], &out[idx + 1]);
        }
    }
}
// [END AI-GENERATED]
