// [AI-GENERATED: Claude Code]
/**
 * @file knn.h
 * @brief k-NN template store for learned gestures (ticket 3.6; contracts C5.2, C7).
 *
 * Templates are int8 x8 vectors of KNN_DIM (60) values, GESTURE_TEMPLATES_PER_CLASS per learned
 * class, GESTURE_MAX_LEARNED classes (4 x 5 x 60 B = 1200 B). RAM only; knn_export()/knn_import()
 * move the store as a flat blob. Distance is L1. No float, no malloc, no blocking.
 *
 * Confidence idea: Lowe, "Distinctive Image Features from Scale-Invariant Keypoints", IJCV 2004
 * (nearest-neighbour distance ratio), used here in "1 - d1/d2" form (C5 section 3).
 */
#ifndef KNN_H
#define KNN_H

#include <stdint.h>
#include <stdbool.h>
#include "gesture_ids.h"

#define KNN_DIM 60u
#define KNN_BLOB_VERSION 1u
#define KNN_BLOB_SIZE (4u + (GESTURE_MAX_LEARNED * 2u) + \
                       (GESTURE_MAX_LEARNED * GESTURE_TEMPLATES_PER_CLASS * KNN_DIM) + 2u)

/** Result of a nearest-template search. */
typedef struct {
    uint8_t  kid;        /**< class id (GESTURE_LEARNED_BASE..) of the nearest template */
    uint16_t d1;         /**< L1 distance to the nearest template */
    uint16_t d2;         /**< nearest L1 distance among templates of other classes (0 if !has_other) */
    bool     has_other;  /**< true if some template of a class != kid exists */
    uint8_t  c_k;        /**< k-NN confidence 0..255 (C5.2) */
    uint16_t radius;     /**< acceptance radius R_c of class kid */
} knn_result_t;

/** Erase all templates (counts, round-robin indices, radii and template bytes). */
void knn_reset(void);

/**
 * Store one template for a learned class (round-robin overwrite when the class holds 5).
 * @param class_id learned class id, must be in [GESTURE_LEARNED_BASE, GESTURE_LEARNED_BASE + GESTURE_MAX_LEARNED - 1]
 * @param x8       KNN_DIM int8 feature values to copy
 * @return templates now stored for the class (1..GESTURE_TEMPLATES_PER_CLASS), or GESTURE_LEARN_ERR_ID
 */
int8_t knn_learn(uint8_t class_id, const int8_t x8[KNN_DIM]);

/**
 * Templates stored for a learned class.
 * @param class_id learned class id
 * @return count 0..GESTURE_TEMPLATES_PER_CLASS, 0 for an invalid id
 */
uint8_t knn_count(uint8_t class_id);

/** @return templates stored over all classes. */
uint8_t knn_total(void);

/**
 * Current acceptance radius R_c of a class.
 * @param class_id learned class id
 * @return clamp(2 * lower_median(pairwise L1), MIN, MAX); GESTURE_KNN_RADIUS_DEFAULT if the class has
 *         fewer than 2 templates; 0 for an invalid id
 */
uint16_t knn_radius(uint8_t class_id);

/**
 * L1 distance of two int8 vectors of KNN_DIM values (max 60*254 = 15240, fits uint16_t).
 * @param a first vector
 * @param b second vector
 * @return sum of |a[i] - b[i]|
 */
uint16_t knn_l1(const int8_t a[KNN_DIM], const int8_t b[KNN_DIM]);

/**
 * Find the nearest template and the k-NN confidence (C5.2). Nearest ties: lowest class, then lowest slot.
 * d2 is the nearest distance among templates whose class != kid (ruling of the main agent).
 * @param x8  KNN_DIM int8 query vector
 * @param out receives the result (written only when true is returned)
 * @return false iff knn_total() == 0
 */
bool knn_query(const int8_t x8[KNN_DIM], knn_result_t *out);

/**
 * Serialise the store: [version, MAX_LEARNED, TEMPLATES_PER_CLASS, KNN_DIM], per class [count, next slot],
 * all template bytes class-major/slot-major (unused slots 0), CRC-16/IBM-3740 (poly 0x1021, init 0xFFFF,
 * no reflection, xorout 0) low byte first.
 * @param buf output buffer
 * @param cap capacity of buf in bytes
 * @return KNN_BLOB_SIZE bytes written, or 0 if cap is too small or buf is NULL (store untouched)
 */
uint16_t knn_export(uint8_t *buf, uint16_t cap);

/**
 * Replace the store from a blob made by knn_export(). The store is unchanged on error.
 * @param buf blob
 * @param len length of blob in bytes
 * @return 0 ok; -1 bad length or NULL buf; -2 bad version/shape (header, count/next-slot values out of
 *         range, or any template byte of an unused slot (slot index >= class count) non-zero); -3 bad CRC.
 *         Checks run in that order (length, header, CRC, per-class shape, unused-slot zeros).
 */
int8_t knn_import(const uint8_t *buf, uint16_t len);

#endif /* KNN_H */
// [END AI-GENERATED]
