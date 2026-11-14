// [AI-GENERATED: Claude Code]
/* TEST STAND-IN ONLY (ticket 3.4T): a deliberately minimal mlp.c written from the C4 spec, used
 * to prove the suite in firmware/test/mlp works. It is NOT the product code (firmware/src/mlp.c).
 * Requant is the split multiply from docs/agent/hadi/proposals/C4_model_header.md section 2. */
#include "mlp.h"
#include "gesture_model.h"

/**
 * RSHIFT_R(v, s) of the spec, s in 0..14.
 *
 * @param v Value.
 * @param s Shift.
 * @return Rounded, flooring-shifted value.
 */
static int32_t rshift_r(int32_t v, uint8_t s)
{
    return (v + (((int32_t)1 << s) >> 1)) >> s;
}

void mlp_model_info(mlp_model_info_t *info)
{
    info->model_hash = GM_MODEL_HASH;
    info->format_version = (uint8_t)GM_FORMAT_VERSION;
    info->feature_version = (uint8_t)GM_FEATURE_VERSION;
    info->odr_hz = (uint8_t)GM_ODR_HZ;
    info->range_g = (uint8_t)GM_RANGE_G;
    info->conf_shift = (uint8_t)GM_CONF_SHIFT;
    info->default_reject = (uint8_t)GM_DEFAULT_REJECT;
}

void mlp_normalize(const int16_t feat[MLP_N_FEATURES], int8_t x8[MLP_N_FEATURES])
{
    uint8_t i;
    for (i = 0u; i < MLP_N_FEATURES; i++) {
        int32_t d = (int32_t)feat[i] - (int32_t)GM_IN_OFF[i];
        int32_t v = rshift_r(d, GM_IN_SH[i]);
        x8[i] = (int8_t)(v < -127 ? -127 : (v > 127 ? 127 : v));
    }
}

int8_t mlp_requant(int32_t acc, uint16_t m, uint8_t sh)
{
    int16_t  hi = (int16_t)(acc >> 16);
    uint16_t lo = (uint16_t)acc;
    int32_t  a  = (int32_t)hi * (int32_t)m;
    uint32_t c  = (uint32_t)lo * (uint32_t)m + ((uint32_t)1 << (sh - 1u));
    int32_t  r  = (a + (int32_t)(c >> 16)) >> (sh - 16u);
    return (int8_t)(r < 0 ? 0 : (r > 127 ? 127 : r));
}

void mlp_layer1(const int8_t x8[MLP_N_FEATURES], int32_t acc1[MLP_N_HIDDEN],
                int8_t h[MLP_N_HIDDEN])
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
    uint8_t c, t1 = 0u, t2 = 0xFFu;
    for (c = 1u; c < MLP_N_CLASSES; c++) {
        if (logits[c] > logits[t1]) {
            t1 = c;
        }
    }
    for (c = 0u; c < MLP_N_CLASSES; c++) {
        if (c != t1 && (t2 == 0xFFu || logits[c] > logits[t2])) {
            t2 = c;
        }
    }
    *margin = logits[t1] - logits[t2];
    return t1;
}

uint8_t mlp_forward(const int16_t feat[MLP_N_FEATURES], int8_t x8[MLP_N_FEATURES],
                    int32_t logits[MLP_N_CLASSES], int32_t *margin)
{
    int32_t acc1[MLP_N_HIDDEN];
    int8_t h[MLP_N_HIDDEN];
    mlp_normalize(feat, x8);
    mlp_layer1(x8, acc1, h);
    mlp_layer2(h, logits);
    return mlp_top2(logits, margin);
}
// [END AI-GENERATED]
