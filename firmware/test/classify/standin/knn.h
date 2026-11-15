// [AI-GENERATED: Claude Code]
/* TEST STAND-IN written from the C5/C7 spec only, to prove the classify test harness.
 * The real header is firmware/src/knn.h. Do not ship this file. */
#ifndef KNN_H
#define KNN_H
#include <stdint.h>
#include <stdbool.h>
#include "gesture_ids.h"

#define KNN_DIM 60u
#define KNN_BLOB_VERSION 1u
#define KNN_BLOB_SIZE (4u + (GESTURE_MAX_LEARNED * 2u) + (GESTURE_MAX_LEARNED * GESTURE_TEMPLATES_PER_CLASS * KNN_DIM) + 2u)

typedef struct { uint8_t kid; uint16_t d1; uint16_t d2; bool has_other; uint8_t c_k; uint16_t radius; } knn_result_t;

void     knn_reset(void);
int8_t   knn_learn(uint8_t class_id, const int8_t x8[KNN_DIM]);
uint8_t  knn_count(uint8_t class_id);
uint8_t  knn_total(void);
uint16_t knn_radius(uint8_t class_id);
uint16_t knn_l1(const int8_t a[KNN_DIM], const int8_t b[KNN_DIM]);
bool     knn_query(const int8_t x8[KNN_DIM], knn_result_t *out);
uint16_t knn_export(uint8_t *buf, uint16_t cap);
int8_t   knn_import(const uint8_t *buf, uint16_t len);
#endif
// [END AI-GENERATED]
