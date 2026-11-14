// [AI-GENERATED: Claude Code]
/*
 * test_classify.c - replay driver for the classify.c / knn.c suite (tickets 3.5T / 3.6T).
 *
 * Written from the SPEC (docs/agent/CONTRACTS.md C5.2, C7; proposals/C5_classifier_output.md §2),
 * never from the implementation. The driver only CALLS the API and prints one line per result;
 * oracle.py replays the identical scenarios from the spec and run_tests.py compares the text.
 * Directed cases first, then N pseudo-random scenarios (xorshift32, mirrored in oracle.py).
 *
 * Host: ./test_classify_host SEED NSCEN.   AVR: SEED / NSCEN come from -DTEST_SEED / -DTEST_NSCEN.
 * The exit code is always 0; the verdict is the comparison done by run_tests.py.
 */
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sim16.h"
#include "gesture_ids.h"
#include "knn.h"
#include "classify.h"

#ifndef TEST_SEED
#define TEST_SEED 1u
#endif
#ifndef TEST_NSCEN
#define TEST_NSCEN 100u
#endif

#define L(x) ((long)(x))

static uint32_t g_rng;
static int8_t   g_base[GESTURE_MAX_LEARNED][KNN_DIM];
static int8_t   g_cur[KNN_DIM];
static int8_t   g_last[KNN_DIM];
static int8_t   g_win[KNN_DIM];
static int8_t   g_a[KNN_DIM];
static int8_t   g_b[KNN_DIM];
static uint8_t  g_blob1[KNN_BLOB_SIZE + 2u];
static uint8_t  g_blob2[KNN_BLOB_SIZE + 2u];

static const uint8_t AMP_TAB[6] = {0u, 1u, 3u, 8u, 20u, 60u};
static const uint8_t BAD_TAB[7] = {0u, 8u, 13u, 255u, 14u, 15u, 100u};
static const uint8_t MC_TAB[7] = {0u, 1u, 64u, 191u, 192u, 193u, 255u};

/**
 * xorshift32 PRNG (13, 17, 5); mirrored bit for bit in oracle.py.
 *
 * @return Next 32-bit pseudo-random value.
 */
static uint32_t rnd(void)
{
    uint32_t x = g_rng;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    g_rng = x;
    return x;
}

/**
 * Seed the PRNG for scenario s: state = seed + (s + 1) * 0x9E3779B9 (0 becomes 1), then 3 draws dropped.
 *
 * @param seed Run seed.
 * @param s    Scenario index.
 * @return None.
 */
static void rng_seed(uint32_t seed, uint32_t s)
{
    g_rng = seed + (s + 1u) * 0x9E3779B9u;
    if (g_rng == 0u) { g_rng = 1u; }
    (void)rnd(); (void)rnd(); (void)rnd();
}

/**
 * CRC-16/IBM-3740 (poly 0x1021, init 0xFFFF, no reflection, xorout 0), the C7 blob checksum.
 *
 * @param p Data.
 * @param n Number of bytes.
 * @return CRC-16 of the data.
 */
static uint16_t crc16(const uint8_t *p, uint16_t n)
{
    uint16_t crc = 0xFFFFu;
    for (uint16_t i = 0u; i < n; i++) {
        crc = (uint16_t)(crc ^ (uint16_t)((uint16_t)p[i] << 8));
        for (uint8_t b = 0u; b < 8u; b++) {
            if ((crc & 0x8000u) != 0u) { crc = (uint16_t)((uint16_t)(crc << 1) ^ 0x1021u); }
            else { crc = (uint16_t)(crc << 1); }
        }
    }
    return crc;
}

/**
 * Fill a vector with a random "base" pattern: style 0 uniform [-127,127], 1 extremes +-127, 2 small [-20,20].
 *
 * @param v Output vector (KNN_DIM entries).
 * @return None.
 */
static void v_base(int8_t *v)
{
    uint32_t style = rnd() % 3u;
    for (uint8_t i = 0u; i < KNN_DIM; i++) {
        if (style == 0u) { v[i] = (int8_t)((int32_t)(rnd() % 255u) - 127); }
        else if (style == 1u) { v[i] = ((rnd() & 1u) != 0u) ? (int8_t)127 : (int8_t)-127; }
        else { v[i] = (int8_t)((int32_t)(rnd() % 41u) - 20); }
    }
}

/**
 * out = clamp(base + uniform noise in [-amp, amp], -127, 127). No PRNG draws when amp == 0.
 *
 * @param out  Output vector.
 * @param base Base vector.
 * @param amp  Noise amplitude.
 * @return None.
 */
static void v_noisy(int8_t *out, const int8_t *base, uint8_t amp)
{
    for (uint8_t i = 0u; i < KNN_DIM; i++) {
        int32_t x = base[i];
        if (amp > 0u) { x += (int32_t)(rnd() % (2u * (uint32_t)amp + 1u)) - (int32_t)amp; }
        if (x > 127) { x = 127; }
        if (x < -127) { x = -127; }
        out[i] = (int8_t)x;
    }
}

/**
 * Vector with L1 distance d (<= 7620) from the zero vector: entries of sign*127 filled first, remainder next.
 *
 * @param v    Output vector.
 * @param d    Total absolute value.
 * @param sign +1 or -1.
 * @return None.
 */
static void v_dist(int8_t *v, uint16_t d, int8_t sign)
{
    for (uint8_t i = 0u; i < KNN_DIM; i++) {
        uint16_t e = (d > 127u) ? 127u : d;
        v[i] = (int8_t)(sign * (int16_t)e);
        d = (uint16_t)(d - e);
    }
}

/**
 * Vector of `fill` with the first n entries set to val.
 *
 * @param v    Output vector.
 * @param fill Value of all entries.
 * @param n    Number of leading entries to override.
 * @param val  Override value.
 * @return None.
 */
static void v_mk(int8_t *v, int8_t fill, uint8_t n, int8_t val)
{
    for (uint8_t i = 0u; i < KNN_DIM; i++) { v[i] = (i < n) ? val : fill; }
}

/**
 * Print N (counts), R (radii) and E (export size / crc / self-check / short-cap / zero-cap) lines.
 * Leaves the exported blob in g_blob1.
 *
 * @param pfx Line prefix ("" for the first report, other text for later ones).
 * @return None.
 */
static void report_state(const char *pfx)
{
    uint16_t sz, crc_field = 0u, ok = 0u, sh, zr;
    printf("%sN %ld %ld %ld %ld %ld %ld %ld %ld\n", pfx, L(knn_count(9)), L(knn_count(10)),
           L(knn_count(11)), L(knn_count(12)), L(knn_total()), L(knn_count(0)), L(knn_count(13)),
           L(knn_count(255)));
    printf("%sR %ld %ld %ld %ld %ld %ld %ld %ld\n", pfx, L(knn_radius(9)), L(knn_radius(10)),
           L(knn_radius(11)), L(knn_radius(12)), L(knn_radius(0)), L(knn_radius(8)),
           L(knn_radius(13)), L(knn_radius(255)));
    sz = knn_export(g_blob1, KNN_BLOB_SIZE);
    if (sz >= 3u) {
        crc_field = (uint16_t)((uint16_t)g_blob1[sz - 2u] | (uint16_t)((uint16_t)g_blob1[sz - 1u] << 8));
        ok = (crc16(g_blob1, (uint16_t)(sz - 2u)) == crc_field) ? 1u : 0u;
    }
    sh = knn_export(g_blob2, (uint16_t)(KNN_BLOB_SIZE - 1u));
    zr = knn_export(g_blob2, 0u);
    printf("%sE %ld %ld %ld %ld %ld\n", pfx, L(sz), L(crc_field), L(ok), L(sh), L(zr));
}

/**
 * Print one "Q" line for a knn_query result.
 *
 * @param win Query window.
 * @param r   Result buffer.
 * @return true if the query returned a result (templates exist).
 */
static bool emit_query(const int8_t *win, knn_result_t *r)
{
    bool ok = knn_query(win, r);
    if (!ok) { printf("Q 0\n"); return false; }
    printf("Q 1 %ld %ld %ld %ld %ld %ld\n", L(r->kid), L(r->d1), L(r->has_other ? r->d2 : 0u),
           L(r->has_other ? 1 : 0), L(r->c_k), L(r->radius));
    return true;
}

/**
 * Run classify_decide with a conf pointer and with NULL, print one line "<tag> ...".
 *
 * @param tag   Line tag (e.g. "D" or "T name").
 * @param top1  MLP argmax.
 * @param margin MLP margin.
 * @param sh    conf_shift.
 * @param mc    min_conf.
 * @param knn   k-NN result or NULL.
 * @return None.
 */
static void emit_decide(const char *tag, uint8_t top1, int32_t margin, uint8_t sh, uint8_t mc,
                        const knn_result_t *knn)
{
    uint8_t c = 77u;
    int8_t r = classify_decide(top1, margin, sh, knn, mc, &c);
    int8_t rn = classify_decide(top1, margin, sh, knn, mc, NULL);
    uint8_t m = classify_mlp_conf(margin, sh);
    printf("%s %ld %ld %ld %ld %ld %ld %ld %ld %ld\n", tag, L(top1), L(margin), L(sh), L(mc),
           L(knn != NULL ? 1 : 0), L(r), L(c), L(rn), L(m));
}

/**
 * Directed case: print the Q line for the window and one T line with the decision.
 *
 * @param name   Case name.
 * @param win    Window vector.
 * @param top1   MLP argmax.
 * @param margin MLP margin.
 * @param sh     conf_shift.
 * @param mc     min_conf.
 * @return None.
 */
static void T_case(const char *name, const int8_t *win, uint8_t top1, int32_t margin, uint8_t sh, uint8_t mc)
{
    knn_result_t r;
    bool have = emit_query(win, &r);
    char tag[24];
    (void)snprintf(tag, sizeof tag, "T %s", name);
    emit_decide(tag, top1, margin, sh, mc, have ? &r : NULL);
}

/**
 * Error-path and round-trip tests of knn_export / knn_import on the current store.
 * Prints "X name rc same" lines (same = 1 if the store re-exports identically afterwards) and finally
 * the round trip: reset, junk learn, import, then N/R/E again and one more learn.
 *
 * @param amp Noise amplitude used for the learn after the import (draws nothing when 0).
 * @return None.
 */
static void io_tests(uint8_t amp)
{
    uint16_t size = knn_export(g_blob1, KNN_BLOB_SIZE);
    uint16_t idx;
    uint8_t bit;
    int8_t rc;
    uint16_t n;
    uint16_t same;
    uint8_t k;
    if (size != KNN_BLOB_SIZE) { printf("X nosize %ld\n", L(size)); return; }
    /* each case: name, mutation index/value, whether the CRC is repaired afterwards */
    for (k = 0u; k < 14u; k++) {
        const char *name = "";
        uint16_t len = size;
        memcpy(g_blob2, g_blob1, size);
        g_blob2[size] = 0u; g_blob2[size + 1u] = 0u;
        switch (k) {
        case 0: name = "len_short"; len = (uint16_t)(size - 1u); break;
        case 1: name = "len_long"; len = (uint16_t)(size + 1u); break;
        case 2: name = "len_zero"; len = 0u; break;
        case 3: name = "ver0"; g_blob2[0] = 0u; break;
        case 4: name = "ver2"; g_blob2[0] = 2u; break;
        case 5: name = "ver255"; g_blob2[0] = 255u; break;
        case 6: name = "shape_classes"; g_blob2[1] = (uint8_t)(GESTURE_MAX_LEARNED + 1u); break;
        case 7: name = "shape_tpc"; g_blob2[2] = (uint8_t)(GESTURE_TEMPLATES_PER_CLASS - 1u); break;
        case 8: name = "shape_dim"; g_blob2[3] = (uint8_t)(KNN_DIM + 1u); break;
        case 9: name = "flip_first"; g_blob2[12] ^= 1u; break;
        case 10: idx = (uint16_t)(12u + rnd() % (uint32_t)(size - 14u)); bit = (uint8_t)(rnd() % 8u);
                 name = "flip_rand"; g_blob2[idx] ^= (uint8_t)(1u << bit); break;
        case 11: name = "flip_last"; g_blob2[size - 3u] ^= 0x80u; break;
        case 12: name = "crc_lo"; g_blob2[size - 2u] ^= 0x01u; break;
        default: name = "crc_hi"; g_blob2[size - 1u] ^= 0x10u; break;
        }
        if (k >= 3u && k <= 8u) {
            /* repair the CRC so only the version / shape byte is wrong */
            uint16_t c = crc16(g_blob2, (uint16_t)(size - 2u));
            g_blob2[size - 2u] = (uint8_t)(c & 0xFFu);
            g_blob2[size - 1u] = (uint8_t)(c >> 8);
        }
        rc = knn_import(g_blob2, len);
        n = knn_export(g_blob2, KNN_BLOB_SIZE);
        same = (n == size && memcmp(g_blob2, g_blob1, size) == 0) ? 1u : 0u;
        printf("X %s %ld %ld\n", name, L(rc), L(same));
    }
    /* round trip: other content first, so import must replace everything including next-slot */
    knn_reset();
    v_mk(g_a, 3, 7, -9);
    (void)knn_learn(11, g_a);
    rc = knn_import(g_blob1, size);
    n = knn_export(g_blob2, KNN_BLOB_SIZE);
    same = (n == size && memcmp(g_blob2, g_blob1, size) == 0) ? 1u : 0u;
    printf("I %ld %ld\n", L(rc), L(same));
    report_state("p");
    {
        uint8_t id = (uint8_t)(9u + rnd() % 4u);
        v_noisy(g_cur, g_base[id - 9u], amp);
        printf("pL %ld %ld\n", L(id), L(knn_learn(id, g_cur)));
    }
    report_state("q");
}

/**
 * One pseudo-random scenario: learns (some with bad ids), state report, queries, decisions, I/O tests.
 *
 * @param seed Run seed.
 * @param s    Scenario index.
 * @return None.
 */
static void scenario(uint32_t seed, uint32_t s)
{
    uint8_t amp, nl, nq;
    knn_result_t r;
    rng_seed(seed, s);
    printf("S %lu\n", (unsigned long)s);
    amp = AMP_TAB[rnd() % 6u];
    for (uint8_t c = 0u; c < GESTURE_MAX_LEARNED; c++) { v_base(g_base[c]); }
    memcpy(g_last, g_base[0], KNN_DIM);
    knn_reset();
    nl = (uint8_t)(rnd() % 24u);
    for (uint8_t i = 0u; i < nl; i++) {
        uint32_t sel = rnd() % 16u;
        uint8_t id, cls;
        if (sel < 13u) { id = (uint8_t)(9u + rnd() % 4u); }
        else { id = BAD_TAB[rnd() % 7u]; }
        cls = (id >= 9u && id <= 12u) ? (uint8_t)(id - 9u) : 0u;
        v_noisy(g_cur, g_base[cls], amp);
        memcpy(g_last, g_cur, KNN_DIM);
        printf("L %ld %ld\n", L(id), L(knn_learn(id, g_cur)));
    }
    report_state("");
    nq = 8u;
    for (uint8_t qi = 0u; qi < nq; qi++) {
        uint32_t mode = rnd() % 4u;
        uint8_t cls = (uint8_t)(rnd() % 4u);
        bool have;
        if (mode == 0u) { v_noisy(g_win, g_base[cls], amp); }
        else if (mode == 1u) { v_noisy(g_win, g_base[cls], AMP_TAB[rnd() % 6u]); }
        else if (mode == 2u) { v_base(g_win); }
        else { memcpy(g_win, g_last, KNN_DIM); }
        have = emit_query(g_win, &r);
        for (uint8_t j = 0u; j < 3u; j++) {
            uint8_t top1 = (uint8_t)(rnd() % 9u);
            uint32_t shsel = rnd() % 4u;
            uint8_t sh;
            uint32_t mm, mcs, fl;
            int32_t margin;
            uint8_t mc;
            if (shsel == 0u) { sh = 0u; }
            else if (shsel == 1u) { sh = 24u; }
            else { sh = (uint8_t)(rnd() % 25u); }
            mm = rnd() % 6u;
            if (mm == 0u) { margin = 0; }
            else if (mm == 1u) { margin = (int32_t)(rnd() % 8u); }
            else if (mm == 2u) { margin = (int32_t)1 << 30; }
            else if (mm == 3u) { margin = (int32_t)(rnd() & 0xFFFFFu); }
            else if (mm == 4u) {
                uint32_t tgt = rnd() % 256u;
                uint32_t off = rnd() % 3u;
                uint32_t v = tgt << sh;
                if (off == 0u && v > 0u) { v -= 1u; }
                else if (off == 2u) { v += 1u; }
                if (v > 0x7FFFFFFFu) { v = 0x7FFFFFFFu; }
                margin = (int32_t)v;
            } else { margin = (int32_t)(rnd() & 0x3FFFFFFFu); }
            mcs = rnd() % 9u;
            if (mcs < 7u) { mc = MC_TAB[mcs]; }
            else { mc = (uint8_t)(rnd() % 256u); }
            fl = rnd() % 8u;
            emit_decide("D", top1, margin, sh, mc, (have && fl != 0u) ? &r : NULL);
        }
    }
    io_tests(amp);
}

/**
 * Directed cases: C5 §2 table, min_conf sweeps, d2 == 0, radius boundaries and clamps, template growth and
 * overwrite, cross-class tie rule, x8 extremes, learn ids, classify_mlp_conf table, blob I/O.
 *
 * @return None.
 */
static void directed(void)
{
    static const int32_t MARG[6] = {0, 1, 255, 256, 0x7FFFFFFF, 0x40000000};
    static const uint8_t SHS[4] = {0u, 1u, 8u, 24u};
    static const int32_t BM[10] = {63, 64, 65, 191, 192, 193, 254, 255, 256, 10000};
    static const int32_t SM[4] = {0, 5, 255, 0x40000000};
    static const uint16_t GROW[7] = {0u, 300u, 700u, 1500u, 2100u, 3000u, 5000u};
    uint8_t i, j, k;
    printf("G %lu\n", (unsigned long)crc16((const uint8_t *)"123456789", 9u));
    g_rng = 12345u;
    /* learn ids 0..20 and 255 on an empty store */
    knn_reset();
    v_mk(g_a, 0, 0, 0);
    for (i = 0u; i < 21u; i++) { printf("DL %ld %ld\n", L(i), L(knn_learn(i, g_a))); }
    printf("DL 255 %ld\n", L(knn_learn(255u, g_a)));
    report_state("d");
    /* classify_mlp_conf table */
    for (i = 0u; i < 6u; i++) {
        for (j = 0u; j < 4u; j++) {
            printf("DM %ld %ld %ld\n", L(MARG[i]), L(SHS[j]), L(classify_mlp_conf(MARG[i], SHS[j])));
        }
    }
    /* C5 section 2 test vectors: one learned class 9, single template at L1 distance 4 */
    knn_reset();
    v_mk(g_a, 0, 0, 0); (void)knn_learn(9, g_a);
    v_mk(g_win, 0, 4, 1);
    T_case("c5_1", g_win, 3u, 255, 0u, 64u);
    T_case("c5_2", g_win, 3u, 100, 0u, 64u);
    T_case("c5_3", g_win, 0u, 255, 0u, 64u);
    T_case("c5_4", g_win, 3u, 30, 0u, 64u);
    v_mk(g_b, 0, 10, 127);                       /* L1 distance 1270 > default radius 1200 */
    T_case("c5_5a", g_b, 3u, 30, 0u, 64u);
    T_case("c5_5b", g_b, 3u, 255, 0u, 64u);
    knn_reset();
    T_case("c5_6a", g_win, 0u, 0, 0u, 1u);
    T_case("c5_6b", g_win, 0u, 0, 0u, 0u);
    knn_reset();
    v_mk(g_a, 0, 0, 0); (void)knn_learn(9, g_a);
    v_mk(g_b, 0, 44, 1); (void)knn_learn(10, g_b);   /* distance 40 from the window */
    T_case("c5_7", g_win, 3u, 0, 0u, 64u);
    /* min_conf sweeps, with one template (d=4, c_k=255) and with none */
    for (k = 0u; k < 2u; k++) {
        knn_reset();
        if (k == 0u) { v_mk(g_a, 0, 0, 0); (void)knn_learn(9, g_a); }
        for (i = 0u; i < 2u; i++) {
            for (j = 0u; j < 4u; j++) {
                for (uint8_t s = 0u; s < 2u; s++) {
                    for (uint8_t m = 0u; m < 7u; m++) {
                        T_case("sw", g_win, (uint8_t)(i * 3u), SM[j], (uint8_t)(s * 24u), MC_TAB[m]);
                    }
                }
            }
        }
        for (j = 0u; j < 10u; j++) {
            for (uint8_t m = 0u; m < 7u; m++) { T_case("bd", g_win, 3u, BM[j], 0u, MC_TAB[m]); }
        }
    }
    /* d2 == 0: two classes with identical templates */
    knn_reset();
    v_mk(g_a, 0, 0, 0);
    (void)knn_learn(9, g_a); (void)knn_learn(10, g_a);
    T_case("dz_a", g_a, 3u, 0, 0u, 0u);
    T_case("dz_b", g_a, 3u, 0, 0u, 1u);
    T_case("dz_c", g_win, 3u, 0, 0u, 0u);
    /* radius: MIN clamp (two identical templates) and boundary */
    knn_reset();
    v_mk(g_a, 0, 0, 0);
    (void)knn_learn(9, g_a); (void)knn_learn(9, g_a);
    printf("DR %ld\n", L(knn_radius(9)));
    v_dist(g_win, 600u, 1); T_case("rmin_eq", g_win, 3u, 0, 0u, 1u);
    v_dist(g_win, 601u, 1); T_case("rmin_over", g_win, 3u, 0, 0u, 1u);
    /* radius: DEFAULT with one template and boundary */
    knn_reset();
    (void)knn_learn(9, g_a);
    printf("DR %ld\n", L(knn_radius(9)));
    v_dist(g_win, 1200u, 1); T_case("rdef_eq", g_win, 3u, 0, 0u, 1u);
    v_dist(g_win, 1201u, 1); T_case("rdef_over", g_win, 3u, 0, 0u, 1u);
    /* radius: MAX clamp (pairwise distance 3000 -> 2*3000 > 4000) and boundary */
    knn_reset();
    (void)knn_learn(9, g_a);
    v_dist(g_b, 3000u, -1); (void)knn_learn(9, g_b);
    printf("DR %ld\n", L(knn_radius(9)));
    v_dist(g_win, 4000u, 1); T_case("rmax_eq", g_win, 3u, 0, 0u, 1u);
    v_dist(g_win, 4001u, 1); T_case("rmax_over", g_win, 3u, 0, 0u, 1u);
    /* radius: in range (2 * 1000 = 2000) and boundary */
    knn_reset();
    (void)knn_learn(9, g_a);
    v_dist(g_b, 1000u, 1); (void)knn_learn(9, g_b);
    printf("DR %ld\n", L(knn_radius(9)));
    v_dist(g_win, 2000u, -1); T_case("rmid_eq", g_win, 3u, 0, 0u, 1u);
    v_dist(g_win, 2001u, -1); T_case("rmid_over", g_win, 3u, 0, 0u, 1u);
    /* growth 0..5 templates and the 6th and 7th overwrite (round robin) */
    knn_reset();
    printf("DG 0 0 %ld %ld\n", L(knn_count(9)), L(knn_radius(9)));
    for (i = 0u; i < 7u; i++) {
        v_dist(g_cur, GROW[i], 1);
        int8_t lr = knn_learn(9, g_cur);   /* separate statement: printf argument order is unspecified */
        printf("DG %ld %ld %ld %ld\n", L(i + 1u), L(lr), L(knn_count(9)), L(knn_radius(9)));
    }
    for (i = 0u; i < 7u; i++) {
        v_dist(g_win, GROW[i], 1);
        T_case("gr", g_win, 3u, 0, 0u, 1u);
    }
    io_tests(3u);
    /* cross-class tie: identical templates in class 10 (learned first) and class 9 -> kid 9 */
    knn_reset();
    v_mk(g_a, 5, 20, -33);
    (void)knn_learn(10, g_a); (void)knn_learn(9, g_a);
    T_case("tie_cls", g_a, 3u, 0, 0u, 0u);
    /* tie where the radii differ: class 9 R=600, class 10 R=4000; kid must be 9 -> rejected */
    knn_reset();
    v_mk(g_a, 0, 0, 0);
    (void)knn_learn(9, g_a); (void)knn_learn(9, g_a);
    (void)knn_learn(10, g_a);
    v_dist(g_b, 3000u, -1); (void)knn_learn(10, g_b);
    v_dist(g_win, 700u, 1);
    T_case("tie_rad", g_win, 3u, 0, 0u, 0u);
    /* x8 extremes: max L1 15240, products above 16 bits */
    knn_reset();
    v_mk(g_a, 127, 0, 0); (void)knn_learn(9, g_a);
    v_mk(g_b, -127, 0, 0); (void)knn_learn(10, g_b);
    printf("DX %ld\n", L(knn_l1(g_a, g_b)));
    T_case("ex_p", g_a, 3u, 0, 0u, 64u);
    T_case("ex_n", g_b, 3u, 0, 0u, 64u);
    v_mk(g_win, 0, 0, 0);
    T_case("ex_z", g_win, 3u, 0, 0u, 64u);
    v_mk(g_win, 127, 4, -127);
    T_case("ex_m", g_win, 3u, 0, 0u, 64u);
    v_mk(g_win, 127, 20, -127);
    T_case("ex_far", g_win, 3u, 0, 0u, 0u);
    io_tests(60u);
    for (i = 0u; i < GESTURE_MAX_LEARNED; i++) { v_base(g_base[i]); }
    /* all four classes full and wrapped, then I/O */
    knn_reset();
    for (j = 0u; j < 7u; j++) {
        for (i = 0u; i < 4u; i++) {
            v_noisy(g_cur, g_base[i], 8u);
            (void)knn_learn((uint8_t)(9u + i), g_cur);
        }
    }
    report_state("w");
    io_tests(8u);
}

/**
 * Entry point: print the directed section, then TEST_NSCEN scenarios, then "DONE".
 *
 * @param argc Host only: argument count.
 * @param argv Host only: argv[1] = seed, argv[2] = number of scenarios.
 * @return 0 on the host; never returns on AVR (sim16_exit).
 */
#ifdef __AVR__
int main(void)
{
    uint32_t seed = TEST_SEED, nscen = TEST_NSCEN;
#else
int main(int argc, char **argv)
{
    uint32_t seed = TEST_SEED, nscen = TEST_NSCEN;
    if (argc > 1) { seed = (uint32_t)strtoul(argv[1], NULL, 0); }
    if (argc > 2) { nscen = (uint32_t)strtoul(argv[2], NULL, 0); }
#endif
    sim16_init();
    directed();
    for (uint32_t s = 0u; s < nscen; s++) { scenario(seed, s); }
    printf("DONE\n");
    sim16_exit(0);
    return 0;
}
// [END AI-GENERATED]
