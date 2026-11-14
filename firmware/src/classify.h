// [AI-GENERATED: Claude Code]
/**
 * @file classify.h
 * @brief MLP confidence, reject and MLP-vs-k-NN decision (ticket 3.5; contract C5.2).
 *
 * Pure functions; the caller runs knn_query() and passes the result (NULL if it returned false).
 * Confidence is a score, not a probability.
 */
#ifndef CLASSIFY_H
#define CLASSIFY_H

#include <stdint.h>
#include "knn.h"

/**
 * MLP confidence: min(255, margin >> conf_shift).
 * @param margin     top1 - top2 logit margin, >= 0 (a negative value is treated as 0)
 * @param conf_shift GM_CONF_SHIFT (shifts >= 32 give 0)
 * @return confidence 0..255
 */
uint8_t classify_mlp_conf(int32_t margin, uint8_t conf_shift);

/**
 * C5.2 gesture_classify steps 1-4.
 * @param top1       MLP argmax class index (0..8)
 * @param margin     MLP top1 - top2 logit margin (>= 0)
 * @param conf_shift GM_CONF_SHIFT
 * @param knn        result of knn_query(), or NULL if there are no templates
 * @param min_conf   reject threshold: reject iff confidence < min_conf (0 disables)
 * @param conf       if not NULL, receives the winner's confidence (also when rejected)
 * @return class id, or GESTURE_UNKNOWN if confidence < min_conf
 */
int8_t classify_decide(uint8_t top1, int32_t margin, uint8_t conf_shift, const knn_result_t *knn,
                       uint8_t min_conf, uint8_t *conf);

#endif /* CLASSIFY_H */
// [END AI-GENERATED]
