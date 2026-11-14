// [AI-GENERATED: Claude Code]
/**
 * @file classify.c
 * @brief MLP-vs-k-NN decision (ticket 3.5), normative steps in docs/agent/CONTRACTS.md C5.2.
 * Mirror of classify_ref() in docs/agent/hadi/spikes/quant/quant_ref.py.
 */
#include <stddef.h>
#include "classify.h"

uint8_t classify_mlp_conf(int32_t margin, uint8_t conf_shift)
{
    uint32_t v;
    if (margin <= 0 || conf_shift >= 32u) {
        return 0u;
    }
    v = (uint32_t)margin >> conf_shift;   /* margin >= 0: shift is the exact floor division */
    return (v > 255u) ? 255u : (uint8_t)v;
}

int8_t classify_decide(uint8_t top1, int32_t margin, uint8_t conf_shift, const knn_result_t *knn,
                       uint8_t min_conf, uint8_t *conf)
{
    int8_t  id = (int8_t)top1;
    uint8_t c = classify_mlp_conf(margin, conf_shift);                       /* step 1 */

    if (knn != NULL) {                                                       /* step 2 */
        /* MLP is weak: class 0, rejected, or below the override threshold */
        bool weak = (id == GESTURE_NONE) || (c < min_conf) || (c < GESTURE_OVERRIDE_CONF);
        if (weak && knn->d1 <= knn->radius && knn->c_k >= min_conf) {
            id = (int8_t)knn->kid;
            c = knn->c_k;
        }
    }
    if (conf != NULL) {                                                      /* step 3 */
        *conf = c;
    }
    return (c < min_conf) ? (int8_t)GESTURE_UNKNOWN : id;                    /* step 4 */
}
// [END AI-GENERATED]
