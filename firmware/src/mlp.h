// [AI-GENERATED: Claude Code]
/**
 * @file mlp.h
 * @brief Integer-only MLP inference (60 -> 16 -> 9) per docs/agent/hadi/proposals/C4_model_header.md.
 *
 * int8 x int8 -> int32 dense layers, requantisation + ReLU, argmax. No float, no int64, no malloc.
 * The model constants come from the generated gesture_model.h, which only mlp.c includes.
 */
#ifndef MLP_H
#define MLP_H

#include <stdint.h>

#define MLP_N_FEATURES 60u
#define MLP_N_HIDDEN   16u
#define MLP_N_CLASSES   9u

/** Identity of the compiled-in model (copied from gesture_model.h). */
typedef struct {
    uint32_t model_hash;      /* GM_MODEL_HASH */
    uint8_t  format_version;  /* GM_FORMAT_VERSION */
    uint8_t  feature_version; /* GM_FEATURE_VERSION */
    uint8_t  odr_hz;          /* GM_ODR_HZ */
    uint8_t  range_g;         /* GM_RANGE_G */
    uint8_t  conf_shift;      /* GM_CONF_SHIFT */
    uint8_t  default_reject;  /* GM_DEFAULT_REJECT */
} mlp_model_info_t;

/**
 * @brief Report the compiled-in model's identity fields.
 * @param info Output; must not be NULL.
 */
void mlp_model_info(mlp_model_info_t *info);

/**
 * @brief Stage 0: x8[i] = SAT(RSHIFT_R(feat[i] - GM_IN_OFF[i], GM_IN_SH[i]), -127, 127).
 * @param feat Input feature vector (int16, C3 layout).
 * @param x8   Output normalised vector, values in [-127, 127].
 * @pre GM_IN_SH[i] <= 14 for every i (guaranteed by the model exporter); a larger shift would
 *      make the rounding term (1 << sh) >> 1 overflow the intended range.
 */
void mlp_normalize(const int16_t feat[MLP_N_FEATURES], int8_t x8[MLP_N_FEATURES]);

/**
 * @brief Layer 1: acc1 = B1 + W1*x8; h = ReLU(requant(acc1)) in [0, 127].
 * @param x8   Input from mlp_normalize.
 * @param acc1 Output int32 accumulators (before requant).
 * @param h    Output int8 hidden activations in [0, 127].
 */
void mlp_layer1(const int8_t x8[MLP_N_FEATURES], int32_t acc1[MLP_N_HIDDEN], int8_t h[MLP_N_HIDDEN]);

/**
 * @brief Layer 2: logits = B2 + W2*h (int32, no requant, no clamp).
 * @param h      Hidden activations from mlp_layer1.
 * @param logits Output class logits.
 */
void mlp_layer2(const int8_t h[MLP_N_HIDDEN], int32_t logits[MLP_N_CLASSES]);

/**
 * @brief Argmax with lowest-index tie-break, plus margin to the runner-up.
 * @param logits Class logits.
 * @param margin Output: logits[top1] - logits[top2] (>= 0); top2 is the largest among c != top1,
 *               lowest index on ties. May be NULL if not needed.
 * @return Index of the top class.
 */
uint8_t mlp_top2(const int32_t logits[MLP_N_CLASSES], int32_t *margin);

/**
 * @brief Requant + ReLU: SAT((acc*m + 2^(sh-1)) >> sh, 0, 127) without int64 (split multiply).
 * @param acc Layer-1 accumulator (full int32 range).
 * @param m   Multiplier, 2^14 <= m < 2^15.
 * @param sh  Shift, 16 <= sh <= 31.
 * @return Value in [0, 127].
 */
int8_t mlp_requant(int32_t acc, uint16_t m, uint8_t sh);

/**
 * @brief Full inference: normalise, layer 1, layer 2, argmax.
 * @param feat   Input features.
 * @param x8     Output normalised vector (kept for the k-NN stage).
 * @param logits Output class logits.
 * @param margin Output margin to the runner-up (see mlp_top2); may be NULL.
 * @return Index of the top class.
 */
uint8_t mlp_forward(const int16_t feat[MLP_N_FEATURES], int8_t x8[MLP_N_FEATURES],
                    int32_t logits[MLP_N_CLASSES], int32_t *margin);

#endif /* MLP_H */
// [END AI-GENERATED]
