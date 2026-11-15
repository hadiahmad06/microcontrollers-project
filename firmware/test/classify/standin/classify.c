// [AI-GENERATED: Claude Code]
/* TEST STAND-IN written from CONTRACTS.md C5.2 only, to prove the classify test harness.
 * The real implementation is firmware/src/classify.c. Do not ship this file. */
#include <stddef.h>
#include "classify.h"

/**
 * MLP confidence score: min(255, margin >> conf_shift).
 *
 * @param margin     Non-negative top1-top2 logit margin.
 * @param conf_shift Right shift (0..24).
 * @return Confidence 0..255.
 */
uint8_t classify_mlp_conf(int32_t margin, uint8_t conf_shift)
{
    uint32_t v = (uint32_t)margin >> conf_shift;
    return (v > 255u) ? 255u : (uint8_t)v;
}

/**
 * Combine the MLP result with an optional k-NN result (C5.2 steps 1-4).
 *
 * @param top1       MLP argmax class.
 * @param margin     MLP logit margin.
 * @param conf_shift GM_CONF_SHIFT.
 * @param knn        k-NN result, or NULL when no templates are stored.
 * @param min_conf   Reject threshold.
 * @param conf       Receives the final confidence (may be NULL).
 * @return Class id or GESTURE_UNKNOWN.
 */
int8_t classify_decide(uint8_t top1, int32_t margin, uint8_t conf_shift, const knn_result_t *knn,
                       uint8_t min_conf, uint8_t *conf)
{
    uint8_t id = top1;
    uint8_t c = classify_mlp_conf(margin, conf_shift);
    if (knn != NULL) {
        bool weak = (id == 0u) || (c < min_conf) || (c < GESTURE_OVERRIDE_CONF);
        if (weak && knn->d1 <= knn->radius && knn->c_k >= min_conf) {
            id = knn->kid;
            c = knn->c_k;
        }
    }
    if (conf != NULL) { *conf = c; }
    return (c < min_conf) ? (int8_t)GESTURE_UNKNOWN : (int8_t)id;
}
// [END AI-GENERATED]
