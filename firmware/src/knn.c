// [AI-GENERATED: Claude Code]
/**
 * @file knn.c
 * @brief k-NN template store (ticket 3.6). See knn.h and docs/agent/CONTRACTS.md C5.2, C7.
 *
 * Rulings applied (main agent): d2 is the nearest template among those whose class != kid;
 * radii fit uint16_t; a class's radius is recomputed whenever its templates change (learn/import),
 * never at query time; the pairwise list has <= 10 entries and is sorted by insertion sort.
 * Nearest-neighbour ratio idea: Lowe, "Distinctive Image Features from Scale-Invariant Keypoints",
 * IJCV 2004 (cited from memory, UNVERIFIED; see knn.h). Sort: textbook insertion sort.
 * Bitwise form of the standard algorithm. CRC-16/IBM-3740 (alias CRC-16/CCITT-FALSE): poly 0x1021, init 0xFFFF, refin/refout false, xorout 0, check("123456789") = 0x29B1.
 * Parameters per G. Cook, "Catalogue of parametrised CRC algorithms", https://reveng.sourceforge.io/crc-catalogue/16.htm
 * (entry recalled from memory, not re-read; check value verified by test).
 */
#include <stddef.h>   /* NULL */
#include "knn.h"

#define NCLS  ((uint8_t)GESTURE_MAX_LEARNED)
#define NSLOT ((uint8_t)GESTURE_TEMPLATES_PER_CLASS)
#define NPAIR ((GESTURE_TEMPLATES_PER_CLASS * (GESTURE_TEMPLATES_PER_CLASS - 1)) / 2)

/* Statics: 1200 B templates + 4 B count + 4 B next + 8 B radius = 1216 B. */
static int8_t   s_tpl[GESTURE_MAX_LEARNED][GESTURE_TEMPLATES_PER_CLASS][KNN_DIM];
static uint8_t  s_count[GESTURE_MAX_LEARNED];   /* templates stored per class */
static uint8_t  s_next[GESTURE_MAX_LEARNED];    /* round-robin slot to write next */
static uint16_t s_radius[GESTURE_MAX_LEARNED];  /* valid when s_count >= 2 */

/**
 * Map a class id to its index in the per-class arrays.
 *
 * @param class_id Class id; valid learned ids are GESTURE_LEARNED_BASE .. GESTURE_LEARNED_BASE + NCLS - 1.
 * @return Index 0..NCLS-1, or NCLS if class_id is not a learned class id.
 */
static uint8_t cls_index(uint8_t class_id)
{
    if (class_id < GESTURE_LEARNED_BASE) {
        return NCLS;
    }
    if ((uint8_t)(class_id - GESTURE_LEARNED_BASE) >= NCLS) {
        return NCLS;
    }
    return (uint8_t)(class_id - GESTURE_LEARNED_BASE);
}

/**
 * Recompute the acceptance radius R_c of one class from its stored templates (C5.2 per-class radius):
 * clamp(2 * lower median of the pairwise L1 distances, MIN, MAX), or the default for fewer than 2 templates.
 * Writes s_radius[c]; called whenever the templates of the class change (learn, import).
 *
 * @param c Class index 0..NCLS-1 (not a class id; the caller has validated it).
 * @return None.
 */
static void recompute_radius(uint8_t c)
{
    uint16_t d[NPAIR];
    uint8_t  n = s_count[c];
    uint8_t  k = 0u;
    uint8_t  i, j;
    uint32_t r;

    if (n < 2u) {
        s_radius[c] = GESTURE_KNN_RADIUS_DEFAULT;
        return;
    }
    for (i = 0u; i < n; i++) {
        for (j = (uint8_t)(i + 1u); j < n; j++) {
            d[k] = knn_l1(s_tpl[c][i], s_tpl[c][j]);
            k++;
        }
    }
    /* insertion sort ascending (k <= 10); textbook insertion sort */
    for (i = 1u; i < k; i++) {
        uint16_t v = d[i];
        uint8_t  p = i;
        while (p > 0u && d[p - 1u] > v) {
            d[p] = d[p - 1u];
            p--;
        }
        d[p] = v;
    }
    r = 2u * (uint32_t)d[(uint8_t)((k - 1u) / 2u)];   /* lower median, element (k-1)//2 */
    if (r < GESTURE_KNN_RADIUS_MIN) {
        r = GESTURE_KNN_RADIUS_MIN;
    }
    if (r > GESTURE_KNN_RADIUS_MAX) {
        r = GESTURE_KNN_RADIUS_MAX;
    }
    s_radius[c] = (uint16_t)r;
}

/**
 * CRC-16/IBM-3740 update with one byte (poly 0x1021, MSB first, no reflection).
 * CRC-16/IBM-3740 (alias CRC-16/CCITT-FALSE): poly 0x1021, init 0xFFFF, refin/refout false, xorout 0, check("123456789") = 0x29B1.
 * Parameters per G. Cook, "Catalogue of parametrised CRC algorithms", https://reveng.sourceforge.io/crc-catalogue/16.htm
 * (entry recalled from memory, not re-read; check value verified by test).
 *
 * @param crc Running CRC so far (0xFFFF to start a new one).
 * @param b   Next data byte.
 * @return CRC after folding b in.
 */
static uint16_t crc16_byte(uint16_t crc, uint8_t b)
{
    uint8_t i;
    crc = (uint16_t)(crc ^ (uint16_t)((uint16_t)b << 8));   /* bring byte into the high half */
    for (i = 0u; i < 8u; i++) {
        if ((crc & 0x8000u) != 0u) {                         /* MSB set: shift and xor the polynomial */
            crc = (uint16_t)((uint16_t)(crc << 1) ^ 0x1021u);
        } else {
            crc = (uint16_t)(crc << 1);
        }
    }
    return crc;
}

/**
 * CRC-16/IBM-3740 of a byte range (init 0xFFFF, xorout 0); check("123456789") = 0x29B1.
 * Parameters per G. Cook, "Catalogue of parametrised CRC algorithms", https://reveng.sourceforge.io/crc-catalogue/16.htm
 * (entry recalled from memory, not re-read; check value verified by test).
 *
 * @param p   First byte (must not be NULL when len > 0).
 * @param len Number of bytes.
 * @return CRC-16 of the len bytes.
 */
static uint16_t crc16(const uint8_t *p, uint16_t len)
{
    uint16_t crc = 0xFFFFu;
    uint16_t i;
    for (i = 0u; i < len; i++) {
        crc = crc16_byte(crc, p[i]);
    }
    return crc;
}

/* Documented in knn.h. */
void knn_reset(void)
{
    uint8_t c, s, i;
    for (c = 0u; c < NCLS; c++) {
        for (s = 0u; s < NSLOT; s++) {
            for (i = 0u; i < KNN_DIM; i++) {
                s_tpl[c][s][i] = 0;
            }
        }
        s_count[c] = 0u;
        s_next[c] = 0u;
        s_radius[c] = GESTURE_KNN_RADIUS_DEFAULT;
    }
}

/* Documented in knn.h. */
int8_t knn_learn(uint8_t class_id, const int8_t x8[KNN_DIM])
{
    uint8_t c = cls_index(class_id);
    uint8_t slot, i;

    if (c >= NCLS) {
        return GESTURE_LEARN_ERR_ID;
    }
    slot = s_next[c];                                 /* == count while filling, then oldest slot */
    for (i = 0u; i < KNN_DIM; i++) {
        s_tpl[c][slot][i] = x8[i];
    }
    s_next[c] = (uint8_t)((slot + 1u) % NSLOT);
    if (s_count[c] < NSLOT) {
        s_count[c]++;
    }
    recompute_radius(c);
    return (int8_t)s_count[c];
}

/* Documented in knn.h. */
uint8_t knn_count(uint8_t class_id)
{
    uint8_t c = cls_index(class_id);
    return (c >= NCLS) ? 0u : s_count[c];
}

/* Documented in knn.h. */
uint8_t knn_total(void)
{
    uint8_t c, t = 0u;
    for (c = 0u; c < NCLS; c++) {
        t = (uint8_t)(t + s_count[c]);
    }
    return t;
}

/* Documented in knn.h. */
uint16_t knn_radius(uint8_t class_id)
{
    uint8_t c = cls_index(class_id);
    if (c >= NCLS) {
        return 0u;
    }
    return (s_count[c] < 2u) ? (uint16_t)GESTURE_KNN_RADIUS_DEFAULT : s_radius[c];
}

/* Documented in knn.h. */
uint16_t knn_l1(const int8_t a[KNN_DIM], const int8_t b[KNN_DIM])
{
    uint16_t sum = 0u;
    uint8_t  i;
    for (i = 0u; i < KNN_DIM; i++) {
        int16_t df = (int16_t)((int16_t)a[i] - (int16_t)b[i]);
        if (df < 0) {
            df = (int16_t)-df;
        }
        sum = (uint16_t)(sum + (uint16_t)df);
    }
    return sum;
}

/* Documented in knn.h. */
bool knn_query(const int8_t x8[KNN_DIM], knn_result_t *out)
{
    uint16_t best[GESTURE_MAX_LEARNED];   /* nearest distance per class (valid when count > 0) */
    uint8_t  c, s;
    uint8_t  kc = NCLS;                   /* class index of nearest template */
    uint16_t d1 = 0u, d2 = 0u;
    bool     has_other = false;

    if (knn_total() == 0u) {
        return false;
    }
    for (c = 0u; c < NCLS; c++) {
        if (s_count[c] == 0u) {
            continue;
        }
        best[c] = 0xFFFFu;
        for (s = 0u; s < s_count[c]; s++) {
            uint16_t d = knn_l1(x8, s_tpl[c][s]);
            if (d < best[c]) {
                best[c] = d;
            }
        }
        if (kc == NCLS || best[c] < d1) {   /* strict: lowest class, then lowest slot, wins ties */
            kc = c;
            d1 = best[c];
        }
    }
    for (c = 0u; c < NCLS; c++) {
        if (c != kc && s_count[c] != 0u) {
            if (!has_other || best[c] < d2) {
                d2 = best[c];
                has_other = true;
            }
        }
    }
    out->kid = (uint8_t)(GESTURE_LEARNED_BASE + kc);
    out->d1 = d1;
    out->d2 = d2;
    out->has_other = has_other;
    if (!has_other) {
        out->c_k = 255u;
    } else if (d2 == 0u) {
        out->c_k = 0u;
    } else {
        /* (d2 - d1) * 255 up to ~3.9e6: needs uint32_t on a 16-bit int target; floor division */
        out->c_k = (uint8_t)(((uint32_t)(uint16_t)(d2 - d1) * 255u) / d2);
    }
    out->radius = knn_radius(out->kid);
    return true;
}

/* Documented in knn.h. */
uint16_t knn_export(uint8_t *buf, uint16_t cap)
{
    uint16_t n = 0u;
    uint16_t crc;
    uint8_t  c, s, i;

    if (buf == NULL || cap < KNN_BLOB_SIZE) {
        return 0u;
    }
    buf[n++] = (uint8_t)KNN_BLOB_VERSION;
    buf[n++] = (uint8_t)GESTURE_MAX_LEARNED;
    buf[n++] = (uint8_t)GESTURE_TEMPLATES_PER_CLASS;
    buf[n++] = (uint8_t)KNN_DIM;
    for (c = 0u; c < NCLS; c++) {
        buf[n++] = s_count[c];
        buf[n++] = s_next[c];
    }
    for (c = 0u; c < NCLS; c++) {
        for (s = 0u; s < NSLOT; s++) {
            for (i = 0u; i < KNN_DIM; i++) {
                buf[n++] = (uint8_t)s_tpl[c][s][i];
            }
        }
    }
    crc = crc16(buf, n);
    buf[n++] = (uint8_t)(crc & 0xFFu);          /* low byte first */
    buf[n++] = (uint8_t)(crc >> 8);
    return n;
}

/* Documented in knn.h. */
int8_t knn_import(const uint8_t *buf, uint16_t len)
{
    uint16_t crc, n;
    uint8_t  c, s, i;

    if (buf == NULL || len != KNN_BLOB_SIZE) {
        return -1;
    }
    if (buf[0] != KNN_BLOB_VERSION || buf[1] != GESTURE_MAX_LEARNED ||
        buf[2] != GESTURE_TEMPLATES_PER_CLASS || buf[3] != KNN_DIM) {
        return -2;
    }
    crc = crc16(buf, (uint16_t)(KNN_BLOB_SIZE - 2u));
    if (buf[KNN_BLOB_SIZE - 2u] != (uint8_t)(crc & 0xFFu) ||
        buf[KNN_BLOB_SIZE - 1u] != (uint8_t)(crc >> 8)) {
        return -3;
    }
    for (c = 0u; c < NCLS; c++) {                 /* shape of the per-class metadata */
        uint8_t cnt = buf[4u + 2u * c];
        uint8_t nxt = buf[5u + 2u * c];
        if (cnt > NSLOT || nxt >= NSLOT || (cnt < NSLOT && nxt != cnt)) {
            return -2;
        }
    }
    n = 4u + 2u * NCLS;
    for (c = 0u; c < NCLS; c++) {                 /* every byte of an unused slot (index >= count) must be 0 */
        uint8_t cnt = buf[4u + 2u * c];
        for (s = cnt; s < NSLOT; s++) {
            for (i = 0u; i < KNN_DIM; i++) {
                if (buf[n + ((uint16_t)((uint16_t)c * NSLOT + s) * KNN_DIM) + i] != 0u) {
                    return -2;
                }
            }
        }
    }
    for (c = 0u; c < NCLS; c++) {
        s_count[c] = buf[4u + 2u * c];
        s_next[c] = buf[5u + 2u * c];
    }
    for (c = 0u; c < NCLS; c++) {
        for (s = 0u; s < NSLOT; s++) {
            for (i = 0u; i < KNN_DIM; i++) {
                s_tpl[c][s][i] = (int8_t)buf[n++];
            }
        }
        recompute_radius(c);
    }
    return 0;
}
// [END AI-GENERATED]
