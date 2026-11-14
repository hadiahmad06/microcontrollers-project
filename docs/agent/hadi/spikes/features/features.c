// [AI-GENERATED: Claude Code]
#include "features.h"

/*
 * Implementation notes (see docs/agent/hadi/proposals/C3_features.md):
 *  - Segment sum of 15 values in [-2048,2047] lies in [-30720,30705]: fits int16.
 *  - Mean uses C '/' (truncation toward zero), identical on host and XC16.
 *  - Deviation d = x-mean is in [-4095,4095]; d*d is formed in int32_t
 *    (XC16 int is 16 bit, so the cast BEFORE the multiply is mandatory).
 *  - Sum of 15 squares <= 62,604,360 < 2^31; kept in uint32_t (always >= 0, so
 *    shifts are plain logical shifts, no implementation-defined case).
 */

#if FEAT_ENERGY_MODE != 0
uint16_t features_isqrt32(uint32_t n)
{
    uint32_t res = 0;
    uint32_t bit = (uint32_t)1 << 30;
    while (bit > n) {
        bit >>= 2;
    }
    while (bit != 0) {
        if (n >= res + bit) {
            n -= res + bit;
            res = (res >> 1) + bit;
        } else {
            res >>= 1;
        }
        bit >>= 2;
    }
    return (uint16_t)res;
}
#endif

/**
 * Scale the sum of squared deviations to the int16 energy feature.
 *
 * @param acc Sum of 15 squared deviations (0..62,604,360 for in-range input).
 * @return    Energy per FEAT_ENERGY_MODE, in 0..32767.
 */
static int16_t scale_energy(uint32_t acc)
{
#if FEAT_ENERGY_MODE == 0
    acc >>= FEAT_ENERGY_SHIFT;
    if (acc > 32767u) {
        acc = 32767u;
    }
    return (int16_t)acc;
#elif FEAT_ENERGY_MODE == 1
    return (int16_t)features_isqrt32(acc);
#elif FEAT_ENERGY_MODE == 2
    return (int16_t)features_isqrt32(acc / 15u);
#else
#error "FEAT_ENERGY_MODE must be 0, 1 or 2"
#endif
}

/**
 * Compute the (mean, energy) pair for one 15-sample segment of one axis.
 *
 * @param x       Window base pointer (sample-major, 3 axes).
 * @param first   Index of the first sample of the segment (0,15,...,135).
 * @param axis    Axis column, 0..2.
 * @param mean_o  Output: truncated mean of the segment.
 * @param energy_o Output: scaled sum of squared deviations.
 * @return        None.
 */
static void segment_features(int16_t (*x)[3], int16_t first, int16_t axis,
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
    *mean_o = mean;
    *energy_o = scale_energy(acc);
}

/* Doc comment for features_extract is in features.h. */
void features_extract(int16_t (*x)[3], int16_t out[60])
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
