// [AI-GENERATED: Claude Code]
/* driver.c - test driver for firmware/src/mlp.c (ticket 3.4T). Includes ONLY mlp.h.
 * Build flags: -DVEC_SEED=<nonzero u32> -DN_RAND=<count>. Per vector it prints short lines
 *   S <i> <stage> <first-index> v v ...   (stages x8, acc1, h, logits; <=12 values per line)
 *   T <i> top1 margin
 * for EDGE_N edge vectors (edge_vectors.h, from gen_model.py) then N_RAND PRNG vectors; an
 * "I ..." model-info line; "R acc m sh result" lines for the mlp_requant sweep; then SIM16_EXIT.
 * Python (run_tests.py + oracle.py) compares every field against its own oracle. */
#include <stdint.h>
#include <stdio.h>
#include "mlp.h"
#include "sim16.h"
#include "edge_vectors.h"

#ifndef VEC_SEED
#define VEC_SEED 1u
#endif
#ifndef N_RAND
#define N_RAND 10u
#endif

#define REQ_SEED 0x9E3779B9u

/* the API dimensions must be the real ones (compile-time check, no _Static_assert in C99) */
typedef char drv_sa_features[(MLP_N_FEATURES == 60u) ? 1 : -1];
typedef char drv_sa_hidden[(MLP_N_HIDDEN == 16u) ? 1 : -1];
typedef char drv_sa_classes[(MLP_N_CLASSES == 9u) ? 1 : -1];

static uint32_t g_xs;   /* xorshift32 state */

/**
 * xorshift32 (shifts 13, 17, 5): identical to oracle.py XorShift32.
 *
 * @return Next pseudo-random value.
 */
static uint32_t rng(void)
{
    uint32_t x = g_xs;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    g_xs = x;
    return x;
}

/**
 * Generate one random feature vector (mirrors oracle.random_features): per feature, one
 * quarter uniform over int16, the rest near VEC_OFF[i] in units of 2^VEC_SH[i] (so x8 spans
 * about -160..160 and rounding fractions are exercised).
 *
 * @param feat Output, MLP_N_FEATURES values.
 * @return None.
 */
static void gen_feat(int16_t feat[MLP_N_FEATURES])
{
    uint8_t i;
    for (i = 0u; i < MLP_N_FEATURES; i++) {
        uint32_t r1 = rng();
        int32_t v;
        if ((r1 & 3u) == 0u) {
            v = (int32_t)(int16_t)(uint16_t)(r1 >> 16);
        } else {
            uint32_t r2 = rng();
            int32_t sc = (int32_t)1 << VEC_SH[i];
            int32_t t = (int32_t)(r2 >> 16) % 321L - 160L;
            int32_t frac = (int32_t)((r1 >> 2) & 0x3FFFu) & (sc - 1L);
            v = (int32_t)VEC_OFF[i] + t * sc + frac - (sc >> 1);
            if (v > 32767L) {
                v = 32767L;
            }
            if (v < -32768L) {
                v = -32768L;
            }
        }
        feat[i] = (int16_t)v;
    }
}

/**
 * Print an int8 array as lines "S <idx> <name> <first> v v ..." of at most 12 values (the
 * simavr UART path breaks lines longer than 255 characters, so lines are kept short).
 *
 * @param idx  Vector index.
 * @param name Stage name.
 * @param v    Values.
 * @param n    Number of values.
 * @return None.
 */
static void print_i8(uint16_t idx, const char *name, const int8_t *v, uint8_t n)
{
    uint8_t i;
    for (i = 0u; i < n; i++) {
        if ((i % 12u) == 0u) {
            printf("%sS %u %s %u", (i == 0u) ? "" : "\n", (unsigned)idx, name, (unsigned)i);
        }
        printf(" %d", (int)v[i]);
    }
    printf("\n");
}

/**
 * Same as print_i8() for int32 values.
 *
 * @param idx  Vector index.
 * @param name Stage name.
 * @param v    Values.
 * @param n    Number of values.
 * @return None.
 */
static void print_i32(uint16_t idx, const char *name, const int32_t *v, uint8_t n)
{
    uint8_t i;
    for (i = 0u; i < n; i++) {
        if ((i % 8u) == 0u) {
            printf("%sS %u %s %u", (i == 0u) ? "" : "\n", (unsigned)idx, name, (unsigned)i);
        }
        printf(" %ld", (long)v[i]);
    }
    printf("\n");
}

/**
 * Run one feature vector through the staged API and mlp_forward(), print the V line, and
 * report whether mlp_forward() agrees with the staged calls.
 *
 * @param idx   Vector index printed on the line.
 * @param feat  Input features.
 * @return 0 if mlp_forward matched the staged result, 1 otherwise.
 */
static uint8_t run_vector(uint16_t idx, const int16_t feat[MLP_N_FEATURES])
{
    int8_t x8[MLP_N_FEATURES], h[MLP_N_HIDDEN], fx8[MLP_N_FEATURES];
    int32_t acc1[MLP_N_HIDDEN], lg[MLP_N_CLASSES], flg[MLP_N_CLASSES];
    int32_t margin = 0, fmargin = 0;
    uint8_t top1, ftop1, i, bad = 0u;

    mlp_normalize(feat, x8);
    mlp_layer1(x8, acc1, h);
    mlp_layer2(h, lg);
    top1 = mlp_top2(lg, &margin);

    print_i8(idx, "x8", x8, MLP_N_FEATURES);
    print_i32(idx, "acc1", acc1, MLP_N_HIDDEN);
    print_i8(idx, "h", h, MLP_N_HIDDEN);
    print_i32(idx, "logits", lg, MLP_N_CLASSES);
    printf("T %u %u %ld\n", (unsigned)idx, (unsigned)top1, (long)margin);

    ftop1 = mlp_forward(feat, fx8, flg, &fmargin);
    if (ftop1 != top1 || fmargin != margin) {
        bad = 1u;
    }
    for (i = 0u; i < MLP_N_FEATURES; i++) {
        if (fx8[i] != x8[i]) {
            bad = 1u;
        }
    }
    for (i = 0u; i < MLP_N_CLASSES; i++) {
        if (flg[i] != lg[i]) {
            bad = 1u;
        }
    }
    if (bad != 0u) {
        printf("FWDFAIL %u\n", (unsigned)idx);
    }
    return bad;
}

/**
 * Print the mlp_requant sweep: acc in a fixed list plus random values, m in {16384, 16385,
 * 32767, 2 random}, sh in {16, 17, 30, 31, 2 random}. Must mirror oracle.requant_sweep().
 *
 * @return None.
 */
static void requant_sweep(void)
{
    static const int32_t acc_fixed[11] = {
        (-2147483647L - 1L), 2147483647L, 0L, 1L, -1L, 65535L, -65535L, 65536L, -65536L,
        65537L, -65537L };
    static const uint16_t m_fixed[3] = { 16384u, 16385u, 32767u };
    static const uint8_t sh_fixed[4] = { 16u, 17u, 30u, 31u };
    int32_t accs[23];
    uint16_t ms[5];
    uint8_t shs[6];
    uint8_t a, b, c;
    g_xs = REQ_SEED;
    for (a = 0u; a < 11u; a++) {
        accs[a] = acc_fixed[a];
    }
    for (a = 11u; a < 17u; a++) {
        accs[a] = (int32_t)rng();
    }
    for (a = 17u; a < 23u; a++) {
        int32_t v = (int32_t)rng();
        uint32_t k = rng() % 31u;
        accs[a] = v >> k;
    }
    for (b = 0u; b < 3u; b++) {
        ms[b] = m_fixed[b];
    }
    for (b = 3u; b < 5u; b++) {
        ms[b] = (uint16_t)(16384u + rng() % 16384u);
    }
    for (c = 0u; c < 4u; c++) {
        shs[c] = sh_fixed[c];
    }
    for (c = 4u; c < 6u; c++) {
        shs[c] = (uint8_t)(16u + rng() % 16u);
    }
    for (a = 0u; a < 23u; a++) {
        for (b = 0u; b < 5u; b++) {
            for (c = 0u; c < 6u; c++) {
                printf("R %ld %u %u %d\n", (long)accs[a], (unsigned)ms[b], (unsigned)shs[c],
                       (int)mlp_requant(accs[a], ms[b], shs[c]));
            }
        }
    }
}

/**
 * Test program entry point.
 *
 * @return 0 on the host (never returns on AVR: sim16_exit stops the CPU). Exit code 1 if
 *         mlp_forward() disagreed with the staged API on any vector.
 */
int main(void)
{
    mlp_model_info_t info;
    int16_t feat[MLP_N_FEATURES];
    uint16_t i;
    uint8_t k, bad = 0u;

    sim16_init();
    mlp_model_info(&info);
    printf("I %lu %u %u %u %u %u %u\n", (unsigned long)info.model_hash,
           (unsigned)info.format_version, (unsigned)info.feature_version, (unsigned)info.odr_hz,
           (unsigned)info.range_g, (unsigned)info.conf_shift, (unsigned)info.default_reject);

    for (i = 0u; i < (uint16_t)EDGE_N; i++) {
        for (k = 0u; k < MLP_N_FEATURES; k++) {
            feat[k] = EDGE_VEC[i][k];
        }
        bad |= run_vector(i, feat);
    }
    g_xs = (uint32_t)VEC_SEED;
    for (i = 0u; i < (uint16_t)N_RAND; i++) {
        gen_feat(feat);
        bad |= run_vector((uint16_t)(EDGE_N + i), feat);
    }
    requant_sweep();
    sim16_exit((int16_t)bad);
    return (int)bad;
}
// [END AI-GENERATED]
