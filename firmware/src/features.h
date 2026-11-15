// [AI-GENERATED: Claude Code]
#ifndef FEATURES_H
#define FEATURES_H

/*
 * features: integer feature extraction per contract C3
 * (docs/agent/hadi/proposals/C3_features.md; decisions C3-D1..D7, B3, B8 by Hadi, 2026-11-14).
 * Promoted from our own spike docs/agent/hadi/spikes/features/features.{h,c}.
 * Only the decided energy mode is implemented: energy = floor(sqrt(SS)).
 */

#include <stdint.h>

#define FEATURES_VERSION  1u    /* C3 feature-definition version; must equal GM_FEATURE_VERSION (C4) */
#define FEAT_WINDOW_LEN   150   /* samples per window (1.5 s at 100 Hz)  */
#define FEAT_AXES         3     /* X, Y, Z                               */
#define FEAT_SEG_LEN      15    /* samples per segment                   */
#define FEAT_SEGMENTS     10    /* segments per window                   */
#define FEAT_COUNT        60    /* output features                       */

/**
 * @brief Non-negative flag of a feature (B3): odd index = energy (always >= 0), even = mean (signed).
 * @param i Feature index, 0..FEAT_COUNT-1; evaluated once, any integer expression.
 * @return Non-zero (true) if feature i is an energy and so never negative, 0 if it is a mean.
 */
#define FEAT_IS_NONNEG(i) ((((unsigned)(i)) & 1u) != 0u)

/**
 * Extract the 60 integer features from one capture window.
 *
 * For each axis a (0=X,1=Y,2=Z) and segment s (0..9, samples 15*s..15*s+14):
 *   out[20*a + 2*s]     = mean   = trunc_toward_zero(sum(x) / 15)     in [-2048, 2047]
 *   out[20*a + 2*s + 1] = energy = floor(sqrt(sum((x-mean)^2)))        in [0, 7912]
 *
 * @param x   Window, sample-major: x[i][0]=X, x[i][1]=Y, x[i][2]=Z, i in 0..149. Every
 *            value MUST be in [-2048, 2047] (contract C1, no clamp here); behaviour
 *            outside that range is undefined (the int16 sum may overflow). The
 *            parameter is deliberately NOT const-qualified (C3-D7): xc16-gcc 2.10 warns
 *            "incompatible pointer type" when a plain int16_t[150][3] is passed to a
 *            const int16_t (*)[3] parameter. The function never writes to x.
 * @param out Output array of 60 int16_t features, every element written.
 * @return    None.
 */
void features_extract(int16_t (*x)[3], int16_t out[60]);

/**
 * Exact integer square root, floor(sqrt(n)), digit-by-digit (no multiply, no divide).
 * Classic binary digit-by-digit square root; our own implementation from the C3 spec, exhaustively tested.
 *
 * @param n Any uint32_t value.
 * @return  The largest r with r*r <= n (0..65535).
 */
uint16_t features_isqrt32(uint32_t n);

#endif
// [END AI-GENERATED]
