// [AI-GENERATED: Claude Code]
/**
 * @file mlp.c
 * @brief Integer MLP inference, normative spec: docs/agent/hadi/proposals/C4_model_header.md §2.
 *
 * Requantisation scheme (fixed-point multiplier + shift, ReLU folded into the clamp) follows
 * Jacob et al. 2018, "Quantization and Training of Neural Networks for Efficient Integer-
 * Arithmetic-Only Inference", arXiv:1712.05877. The int64-free split multiply is from C4 §2 and
 * is checked against docs/agent/hadi/spikes/quant/quant_ref.py.
 *
 * `>>` on negative values is an arithmetic flooring shift on XC16 (asr, DS-50002071M §23).
 */
#include "mlp.h"
#include "gesture_model.h"

GM_STATIC_ASSERT(GM_N_FEATURES == MLP_N_FEATURES, mlp_nfeat);
GM_STATIC_ASSERT(GM_N_HIDDEN == MLP_N_HIDDEN, mlp_nhidden);
GM_STATIC_ASSERT(GM_N_CLASSES == MLP_N_CLASSES, mlp_nclasses);
GM_STATIC_ASSERT(GM_FORMAT_VERSION == 1, mlp_fmtver);

void mlp_model_info(mlp_model_info_t *info)
{
    info->model_hash      = (uint32_t)GM_MODEL_HASH;
    info->format_version  = (uint8_t)GM_FORMAT_VERSION;
    info->feature_version = (uint8_t)GM_FEATURE_VERSION;
    info->odr_hz          = (uint8_t)GM_ODR_HZ;
    info->range_g         = (uint8_t)GM_RANGE_G;
    info->conf_shift      = (uint8_t)GM_CONF_SHIFT;
    info->default_reject  = (uint8_t)GM_DEFAULT_REJECT;
}

void mlp_normalize(const int16_t feat[MLP_N_FEATURES], int8_t x8[MLP_N_FEATURES])
{
    uint8_t i;
    for (i = 0u; i < MLP_N_FEATURES; i++) {
        int32_t d = (int32_t)feat[i] - (int32_t)GM_IN_OFF[i];   /* int16 difference can exceed int16 */
        uint8_t s = GM_IN_SH[i];                                /* 0..14 */
        int32_t v = (d + (((int32_t)1 << s) >> 1)) >> s;        /* RSHIFT_R, floor shift */
        if (v < -127) { v = -127; }
        if (v > 127)  { v = 127; }
        x8[i] = (int8_t)v;
    }
}

int8_t mlp_requant(int32_t acc, uint16_t m, uint8_t sh)
{
    int16_t  hi = (int16_t)(acc >> 16);                         /* arithmetic shift: signed high half */
    uint16_t lo = (uint16_t)acc;                                /* unsigned low half */
    int32_t  a  = (int32_t)hi * (int32_t)m;                     /* |a| <= 2^30 */
    uint32_t c  = (uint32_t)lo * (uint32_t)m + ((uint32_t)1 << (sh - 1u)); /* < 2^32, adds rounding term */
    int32_t  r  = (a + (int32_t)(c >> 16)) >> (sh - 16u);
    return (int8_t)(r < 0 ? 0 : (r > 127 ? 127 : r));           /* ReLU = lower clamp */
}

void mlp_layer1(const int8_t x8[MLP_N_FEATURES], int32_t acc1[MLP_N_HIDDEN], int8_t h[MLP_N_HIDDEN])
{
    uint8_t i, j;
    for (j = 0u; j < MLP_N_HIDDEN; j++) {
        int32_t acc = GM_B1[j];
        for (i = 0u; i < MLP_N_FEATURES; i++) {
            acc += (int32_t)GM_W1[j][i] * (int32_t)x8[i];
        }
        acc1[j] = acc;
        h[j] = mlp_requant(acc, GM_M1[j], GM_SH1[j]);
    }
}

void mlp_layer2(const int8_t h[MLP_N_HIDDEN], int32_t logits[MLP_N_CLASSES])
{
    uint8_t c, j;
    for (c = 0u; c < MLP_N_CLASSES; c++) {
        int32_t acc = GM_B2[c];
        for (j = 0u; j < MLP_N_HIDDEN; j++) {
            acc += (int32_t)GM_W2[c][j] * (int32_t)h[j];
        }
        logits[c] = acc;
    }
}

uint8_t mlp_top2(const int32_t logits[MLP_N_CLASSES], int32_t *margin)
{
    uint8_t i1 = 0u;
    uint8_t i2;
    uint8_t c;
    for (c = 1u; c < MLP_N_CLASSES; c++) {
        if (logits[c] > logits[i1]) { i1 = c; }                 /* strict >: lowest index wins ties */
    }
    i2 = (i1 == 0u) ? 1u : 0u;
    for (c = 0u; c < MLP_N_CLASSES; c++) {
        if (c != i1 && logits[c] > logits[i2]) { i2 = c; }
    }
    if (margin != 0) { *margin = logits[i1] - logits[i2]; }
    return i1;
}

uint8_t mlp_forward(const int16_t feat[MLP_N_FEATURES], int8_t x8[MLP_N_FEATURES],
                    int32_t logits[MLP_N_CLASSES], int32_t *margin)
{
    int32_t acc1[MLP_N_HIDDEN];
    int8_t  h[MLP_N_HIDDEN];
    mlp_normalize(feat, x8);
    mlp_layer1(x8, acc1, h);
    mlp_layer2(h, logits);
    return mlp_top2(logits, margin);
}
// [END AI-GENERATED]
