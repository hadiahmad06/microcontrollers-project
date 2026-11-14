// [AI-GENERATED: Claude Code]
/* TEST STAND-IN written from the C5 spec only. Real header: firmware/src/classify.h. */
#ifndef CLASSIFY_H
#define CLASSIFY_H
#include <stdint.h>
#include "knn.h"

uint8_t classify_mlp_conf(int32_t margin, uint8_t conf_shift);
int8_t  classify_decide(uint8_t top1, int32_t margin, uint8_t conf_shift, const knn_result_t *knn,
                        uint8_t min_conf, uint8_t *conf);
#endif
// [END AI-GENERATED]
