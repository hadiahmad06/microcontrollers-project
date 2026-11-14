// [AI-GENERATED: Claude Code]
/* TEST STAND-IN written from CONTRACTS.md C5.2/C7 and the main-agent rulings only, to prove
 * the classify test harness. The real implementation is firmware/src/knn.c. Do not ship this file. */
#include <string.h>
#include "knn.h"

#define NC GESTURE_MAX_LEARNED
#define NS GESTURE_TEMPLATES_PER_CLASS

static int8_t  s_t[NC][NS][KNN_DIM];
static uint8_t s_cnt[NC];
static uint8_t s_next[NC];

/** Clear all templates. @return None. */
void knn_reset(void)
{
    memset(s_t, 0, sizeof s_t);
    memset(s_cnt, 0, sizeof s_cnt);
    memset(s_next, 0, sizeof s_next);
}

/**
 * L1 distance of two x8 vectors.
 *
 * @param a First vector.
 * @param b Second vector.
 * @return Sum of absolute differences (max 15240).
 */
uint16_t knn_l1(const int8_t a[KNN_DIM], const int8_t b[KNN_DIM])
{
    uint16_t acc = 0u;
    for (uint8_t i = 0u; i < KNN_DIM; i++) {
        int16_t d = (int16_t)((int16_t)a[i] - (int16_t)b[i]);
        acc = (uint16_t)(acc + (uint16_t)((d < 0) ? -d : d));
    }
    return acc;
}

/**
 * Store one template (round-robin overwrite when full).
 *
 * @param class_id Class 9..12.
 * @param x8       Template vector.
 * @return Templates now stored for the class, or GESTURE_LEARN_ERR_ID.
 */
int8_t knn_learn(uint8_t class_id, const int8_t x8[KNN_DIM])
{
    if (class_id < GESTURE_LEARNED_BASE || class_id >= GESTURE_LEARNED_BASE + GESTURE_MAX_LEARNED) {
        return (int8_t)GESTURE_LEARN_ERR_ID;
    }
    uint8_t c = (uint8_t)(class_id - GESTURE_LEARNED_BASE);
    memcpy(s_t[c][s_next[c]], x8, KNN_DIM);
    s_next[c] = (uint8_t)((s_next[c] + 1u) % NS);
    if (s_cnt[c] < NS) { s_cnt[c]++; }
    return (int8_t)s_cnt[c];
}

/** @param class_id Class id. @return Template count, 0 for a bad id. */
uint8_t knn_count(uint8_t class_id)
{
    if (class_id < GESTURE_LEARNED_BASE || class_id >= GESTURE_LEARNED_BASE + GESTURE_MAX_LEARNED) { return 0u; }
    return s_cnt[class_id - GESTURE_LEARNED_BASE];
}

/** @return Total templates stored. */
uint8_t knn_total(void)
{
    uint8_t t = 0u;
    for (uint8_t c = 0u; c < NC; c++) { t = (uint8_t)(t + s_cnt[c]); }
    return t;
}

/**
 * Acceptance radius of a class.
 *
 * @param class_id Class id.
 * @return Radius, DEFAULT with < 2 templates, 0 for a bad id.
 */
uint16_t knn_radius(uint8_t class_id)
{
    uint16_t d[NS * (NS - 1u) / 2u];
    uint8_t k = 0u;
    if (class_id < GESTURE_LEARNED_BASE || class_id >= GESTURE_LEARNED_BASE + GESTURE_MAX_LEARNED) { return 0u; }
    uint8_t c = (uint8_t)(class_id - GESTURE_LEARNED_BASE);
    uint8_t n = s_cnt[c];
    if (n < 2u) { return GESTURE_KNN_RADIUS_DEFAULT; }
    for (uint8_t i = 0u; i < n; i++) {
        for (uint8_t j = (uint8_t)(i + 1u); j < n; j++) { d[k++] = knn_l1(s_t[c][i], s_t[c][j]); }
    }
    for (uint8_t i = 1u; i < k; i++) {
        uint16_t v = d[i];
        uint8_t j = i;
        while (j > 0u && d[j - 1u] > v) { d[j] = d[j - 1u]; j--; }
        d[j] = v;
    }
    uint32_t r = 2u * (uint32_t)d[(k - 1u) / 2u];
    if (r < GESTURE_KNN_RADIUS_MIN) { r = GESTURE_KNN_RADIUS_MIN; }
    if (r > GESTURE_KNN_RADIUS_MAX) { r = GESTURE_KNN_RADIUS_MAX; }
    return (uint16_t)r;
}

/**
 * Nearest-template query (class-major, slot-major scan; lowest slot wins ties).
 *
 * @param x8  Query vector.
 * @param out Result.
 * @return false iff no templates are stored.
 */
bool knn_query(const int8_t x8[KNN_DIM], knn_result_t *out)
{
    uint16_t best = 0xFFFFu;
    uint8_t kc = 0u;
    bool found = false;
    for (uint8_t c = 0u; c < NC; c++) {
        for (uint8_t s = 0u; s < s_cnt[c]; s++) {
            uint16_t d = knn_l1(x8, s_t[c][s]);
            if (!found || d < best) { best = d; kc = c; found = true; }
        }
    }
    if (!found) { return false; }
    bool other = false;
    uint16_t d2 = 0xFFFFu;
    for (uint8_t c = 0u; c < NC; c++) {
        if (c == kc) { continue; }
        for (uint8_t s = 0u; s < s_cnt[c]; s++) {
            uint16_t d = knn_l1(x8, s_t[c][s]);
            if (!other || d < d2) { d2 = d; other = true; }
        }
    }
    out->kid = (uint8_t)(GESTURE_LEARNED_BASE + kc);
    out->d1 = best;
    out->has_other = other;
    out->d2 = other ? d2 : 0u;
    if (!other) { out->c_k = 255u; }
    else if (d2 == 0u) { out->c_k = 0u; }
    else { out->c_k = (uint8_t)(((uint32_t)(d2 - best) * 255u) / d2); }
    out->radius = knn_radius(out->kid);
    return true;
}

static uint16_t crc16(const uint8_t *p, uint16_t n)
{
    uint16_t crc = 0xFFFFu;
    for (uint16_t i = 0u; i < n; i++) {
        crc = (uint16_t)(crc ^ (uint16_t)((uint16_t)p[i] << 8));
        for (uint8_t b = 0u; b < 8u; b++) {
            crc = (crc & 0x8000u) ? (uint16_t)((uint16_t)(crc << 1) ^ 0x1021u) : (uint16_t)(crc << 1);
        }
    }
    return crc;
}

/**
 * Serialise the store to a flat blob.
 *
 * @param buf Output buffer.
 * @param cap Capacity of buf.
 * @return KNN_BLOB_SIZE, or 0 if cap is too small.
 */
uint16_t knn_export(uint8_t *buf, uint16_t cap)
{
    uint16_t p = 0u;
    if (cap < KNN_BLOB_SIZE) { return 0u; }
    buf[p++] = KNN_BLOB_VERSION; buf[p++] = GESTURE_MAX_LEARNED;
    buf[p++] = GESTURE_TEMPLATES_PER_CLASS; buf[p++] = KNN_DIM;
    for (uint8_t c = 0u; c < NC; c++) { buf[p++] = s_cnt[c]; buf[p++] = s_next[c]; }
    for (uint8_t c = 0u; c < NC; c++) {
        for (uint8_t s = 0u; s < NS; s++) {
            for (uint8_t i = 0u; i < KNN_DIM; i++) { buf[p++] = (uint8_t)s_t[c][s][i]; }
        }
    }
    uint16_t crc = crc16(buf, p);
    buf[p++] = (uint8_t)(crc & 0xFFu);
    buf[p++] = (uint8_t)(crc >> 8);
    return p;
}

/**
 * Load a blob made by knn_export.
 *
 * @param buf Blob.
 * @param len Blob length.
 * @return 0 ok; -1 bad length; -2 bad version/shape; -3 bad CRC. Store unchanged on error.
 */
int8_t knn_import(const uint8_t *buf, uint16_t len)
{
    if (len != KNN_BLOB_SIZE) { return -1; }
    if (buf[0] != KNN_BLOB_VERSION || buf[1] != GESTURE_MAX_LEARNED ||
        buf[2] != GESTURE_TEMPLATES_PER_CLASS || buf[3] != KNN_DIM) { return -2; }
    uint16_t crc = crc16(buf, (uint16_t)(len - 2u));
    if (buf[len - 2u] != (uint8_t)(crc & 0xFFu) || buf[len - 1u] != (uint8_t)(crc >> 8)) { return -3; }
    /* metadata (valid CRC only): count <= NS, next < NS, and next == count while count < NS (3.5R F1) */
    for (uint8_t c = 0u; c < NC; c++) {
        uint8_t cn = buf[4u + 2u * c], nx = buf[5u + 2u * c];
        if (cn > NS || nx >= NS || (cn < NS && nx != cn)) { return -2; }
    }
    uint16_t p = 4u;
    for (uint8_t c = 0u; c < NC; c++) { s_cnt[c] = buf[p++]; s_next[c] = buf[p++]; }
    for (uint8_t c = 0u; c < NC; c++) {
        for (uint8_t s = 0u; s < NS; s++) {
            for (uint8_t i = 0u; i < KNN_DIM; i++) { s_t[c][s][i] = (int8_t)buf[p++]; }
        }
    }
    return 0;
}
// [END AI-GENERATED]
