// [AI-GENERATED: Claude Code]
/* TEST STAND-IN ONLY (ticket 3.4T): not the product mlp.h. Same API, used to prove the suite
 * in firmware/test/mlp runs and detects bugs. Select with `make test IMPL_DIR=standin`. */
#ifndef MLP_H
#define MLP_H
#include <stdint.h>

#define MLP_N_FEATURES 60u
#define MLP_N_HIDDEN   16u
#define MLP_N_CLASSES   9u

typedef struct {
    uint32_t model_hash;
    uint8_t format_version;
    uint8_t feature_version;
    uint8_t odr_hz;
    uint8_t range_g;
    uint8_t conf_shift;
    uint8_t default_reject;
} mlp_model_info_t;

/** Fill info from the model header. @param info Output. @return None. */
void mlp_model_info(mlp_model_info_t *info);
/** Stage 0. @param feat int16 features. @param x8 Output int8 inputs. @return None. */
void mlp_normalize(const int16_t feat[MLP_N_FEATURES], int8_t x8[MLP_N_FEATURES]);
/** Layer 1. @param x8 Inputs. @param acc1 Output accumulators. @param h Output activations.
 *  @return None. */
void mlp_layer1(const int8_t x8[MLP_N_FEATURES], int32_t acc1[MLP_N_HIDDEN],
                int8_t h[MLP_N_HIDDEN]);
/** Layer 2. @param h Activations. @param logits Output. @return None. */
void mlp_layer2(const int8_t h[MLP_N_HIDDEN], int32_t logits[MLP_N_CLASSES]);
/** Argmax and margin. @param logits Input. @param margin Output top1-top2. @return top1. */
uint8_t mlp_top2(const int32_t logits[MLP_N_CLASSES], int32_t *margin);
/** Requantize. @param acc Accumulator. @param m Multiplier 2^14..2^15-1. @param sh 16..31.
 *  @return SAT(RSHIFT_R64(acc*m, sh), 0, 127). */
int8_t mlp_requant(int32_t acc, uint16_t m, uint8_t sh);
/** All stages. @param feat Input. @param x8 Output. @param logits Output. @param margin Output.
 *  @return top1. */
uint8_t mlp_forward(const int16_t feat[MLP_N_FEATURES], int8_t x8[MLP_N_FEATURES],
                    int32_t logits[MLP_N_CLASSES], int32_t *margin);
#endif
// [END AI-GENERATED]
