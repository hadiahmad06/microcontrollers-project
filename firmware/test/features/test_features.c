// [AI-GENERATED: Claude Code]
/*
 * test_features.c - test driver for firmware/src/features.c (ticket 3.3T).
 *
 * It generates windows (fixed edge windows, then pseudo-random ones from xorshift32), runs
 * features_extract on each and prints one line per window. run_tests.py compares every line
 * with an independent Python oracle (oracle.py) that implements the same generators.
 * It also self-checks features_isqrt32, FEAT_IS_NONNEG and FEATURES_VERSION.
 *
 * Output lines:
 *   E <e> <axis> <20 ints>   edge window number e, features 20*axis .. 20*axis+19
 *   W <w> <axis> <20 ints>   random window number w
 *   CHK isqrt <cases> <failures>
 *   CHK nonneg <failures> | CHK version <failures>   (or "SKIP" under SPIKE_STANDIN)
 * then "SIM16_EXIT 0" via sim16_exit.
 *
 * Seed and window count: argv[1], argv[2] on the host; -DTEST_SEED / -DTEST_N on the AVR build.
 * Window generators MUST stay identical to oracle.py (xorshift32; same draw order).
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "features.h"
#include "sim16.h"
#include "ss_table.h"

#ifndef TEST_SEED
#define TEST_SEED 12345u
#endif
#ifndef TEST_N
#define TEST_N 300
#endif
#ifndef TEST_KSTEP
#define TEST_KSTEP 1   /* stride over k in the k*k-1, k*k, k*k+1 isqrt sweep */
#endif
#ifndef TEST_NRAND_ISQRT
#define TEST_NRAND_ISQRT 2000
#endif

#define N_EDGE_FIXED 7      /* edges 0..6 are hand-written; then SS_NT table windows; then sums */
#define N_SUMS 14
#define N_EDGE (N_EDGE_FIXED + SS_NT + N_SUMS)

static const int16_t sum_cases[N_SUMS] = {
    -1, -14, -15, -16, -29, -30, -31, 1, 14, 15, 16, 29, 30, 31
};

static uint32_t rng_state;

/**
 * Seed the xorshift32 generator (a zero seed is replaced by 1).
 *
 * @param seed Seed value.
 * @return None.
 */
static void rng_seed(uint32_t seed)
{
    rng_state = (seed == 0u) ? 1u : seed;
}

/**
 * Advance the xorshift32 generator (shifts 13, 17, 5) and return the new state.
 * xorshift32: G. Marsaglia, "Xorshift RNGs", J. Statistical Software 8(14), 2003; shifts 13/17/5.
 *
 * @return Next 32-bit pseudo-random value.
 */
static uint32_t rng_next(void)
{
    uint32_t x = rng_state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    rng_state = x;
    return x;
}

/**
 * Fill one fixed edge window; see oracle.py edge_window() for the identical definition.
 *
 * @param e Edge window number, 0 .. N_EDGE-1.
 * @param x Window to fill (150 samples x 3 axes).
 * @return None.
 */
static void fill_edge(int16_t e, int16_t (*x)[3])
{
    int16_t i, a;
    for (i = 0; i < FEAT_WINDOW_LEN; i++) {
        for (a = 0; a < FEAT_AXES; a++) {
            int32_t v = 0;
            int16_t j = (int16_t)(i % FEAT_SEG_LEN);
            int16_t s = (int16_t)(i / FEAT_SEG_LEN);
            if (e == 0) {
                v = -2048;
            } else if (e == 1) {
                v = 2047;
            } else if (e == 2) {
                v = 0;
            } else if (e == 3) {
                v = ((j & 1) == 0) ? -2048 : 2047;      /* 8 low, 7 high per segment */
            } else if (e == 4) {
                v = ((j & 1) == 0) ? 2047 : -2048;      /* 8 high, 7 low per segment */
            } else if (e == 5) {
                v = (a == 0) ? -2048 : ((a == 1) ? 2047 : 0);
            } else if (e == 6) {
                v = (((int32_t)i * 37 + (int32_t)a * 101) % 4096) - 2048;
            } else if (e < N_EDGE_FIXED + SS_NT) {
                int16_t t = (int16_t)(e - N_EDGE_FIXED);
                v = ss_table[(t + 5 * a + s) % SS_NT][j];
            } else {
                int16_t t = (int16_t)(e - N_EDGE_FIXED - SS_NT);
                v = (j == 0) ? sum_cases[(t + a + s) % N_SUMS] : 0;
            }
            x[i][a] = (int16_t)v;
        }
    }
}

/**
 * Fill one pseudo-random window; see oracle.py random_window() for the identical definition.
 * Mode is w % 4: 0 full range, 1 small amplitude, 2 extremes only, 3 offset cluster (clamped).
 *
 * @param w Random window number (also selects the mode).
 * @param x Window to fill.
 * @return None.
 */
static void fill_random(int32_t w, int16_t (*x)[3])
{
    int16_t i, a;
    int32_t c = 0;
    int16_t mode = (int16_t)(w & 3);
    if (mode == 3) {
        c = (int32_t)((rng_next() >> 8) & 0x7FFu) - 1024;
    }
    for (i = 0; i < FEAT_WINDOW_LEN; i++) {
        for (a = 0; a < FEAT_AXES; a++) {
            uint32_t r = rng_next();
            int32_t v;
            if (mode == 0) {
                v = (int32_t)((r >> 8) & 0xFFFu) - 2048;
            } else if (mode == 1) {
                v = (int32_t)((r >> 8) & 0x1Fu) - 16;
            } else if (mode == 2) {
                v = (((r >> 16) & 1u) != 0u) ? 2047 : -2048;
            } else {
                v = c + (int32_t)((r >> 8) & 0x3FFu) - 512;
                if (v < -2048) {
                    v = -2048;
                }
                if (v > 2047) {
                    v = 2047;
                }
            }
            x[i][a] = (int16_t)v;
        }
    }
}

/**
 * Print one window as three lines (one per axis, 20 features each): the simavr UART path
 * breaks lines longer than 255 characters, so a 60-value line would be split.
 *
 * @param tag 'E' or 'W'.
 * @param n   Window number.
 * @param out The 60 features.
 * @return None.
 */
static void print_line(char tag, int32_t n, const int16_t *out)
{
    int16_t k, a;
    for (a = 0; a < FEAT_AXES; a++) {
        printf("%c %ld %d", tag, (long)n, (int)a);
        for (k = 0; k < 20; k++) {
            printf(" %d", (int)out[20 * a + k]);
        }
        printf("\n");
    }
}

/**
 * Check features_isqrt32(n) against its defining property r*r <= n < (r+1)*(r+1)
 * (the upper bound is vacuous for r == 65535 because (r+1)^2 == 2^32 exceeds uint32).
 *
 * @param n Input value.
 * @return 1 if the result is correct, else 0.
 */
static int16_t isqrt_ok(uint32_t n)
{
    uint32_t r = (uint32_t)features_isqrt32(n);
    uint32_t r1;
    if (r * r > n) {
        return 0;
    }
    if (r < 65535u) {
        r1 = r + 1u;
        if (r1 * r1 <= n) {
            return 0;
        }
    }
    return 1;
}

/**
 * Run the features_isqrt32 sweep and print the "CHK isqrt" summary (first failures are listed).
 *
 * @return Number of failures.
 */
static int32_t check_isqrt(void)
{
    int32_t cases = 0, fails = 0;
    uint32_t n, k;
    int16_t shown = 0;
    uint32_t list[8];
    int16_t li;
    list[0] = 0xFFFFFFFFu; list[1] = 0xFFFFFFFEu; list[2] = 0x80000000u;
    list[3] = 0x7FFFFFFFu; list[4] = 0xFFFE0001u; list[5] = 0xFFFE0000u;
    list[6] = 0xFFFC0000u; list[7] = 0x00010000u;
    for (li = 0; li < 8; li++) {
        n = list[li];
        cases++;
        if (!isqrt_ok(n)) {
            fails++;
            if (shown < 5) { printf("CHK isqrt BAD n=%lu\n", (unsigned long)n); shown++; }
        }
    }
    for (n = 0u; n <= 1000u; n++) {
        cases++;
        if (!isqrt_ok(n)) {
            fails++;
            if (shown < 5) { printf("CHK isqrt BAD n=%lu\n", (unsigned long)n); shown++; }
        }
    }
    for (k = 1u; k <= 65535u; k += (uint32_t)TEST_KSTEP) {
        uint32_t sq = k * k;
        uint32_t d;
        for (d = 0u; d <= 2u; d++) {
            n = sq - 1u + d;   /* k*k-1, k*k, k*k+1 */
            cases++;
            if (!isqrt_ok(n)) {
                fails++;
                if (shown < 5) { printf("CHK isqrt BAD n=%lu\n", (unsigned long)n); shown++; }
            }
        }
    }
    /* the last k values (including 65535, whose square is the largest perfect square) */
    for (k = 65500u; k <= 65535u; k++) {
        uint32_t sq = k * k;
        uint32_t d;
        for (d = 0u; d <= 2u; d++) {
            n = sq - 1u + d;   /* k*k-1, k*k, k*k+1 */
            cases++;
            if (!isqrt_ok(n)) {
                fails++;
                if (shown < 5) { printf("CHK isqrt BAD n=%lu\n", (unsigned long)n); shown++; }
            }
        }
    }
    rng_seed(0xC0FFEEu);
    for (li = 0; li < TEST_NRAND_ISQRT; li++) {
        n = rng_next();
        cases++;
        if (!isqrt_ok(n)) {
            fails++;
            if (shown < 5) { printf("CHK isqrt BAD n=%lu\n", (unsigned long)n); shown++; }
        }
    }
    printf("CHK isqrt %ld %ld\n", (long)cases, (long)fails);
    return fails;
}

/**
 * Test entry point: prints isqrt/macro checks, edge windows, then random windows.
 *
 * @param argc Argument count (host only).
 * @param argv argv[1] = seed, argv[2] = number of random windows (host only).
 * @return 0 on the host (exit code via sim16_exit); never returns on AVR.
 */
#ifdef __AVR__
int main(void)
#else
int main(int argc, char **argv)
#endif
{
    static int16_t x[FEAT_WINDOW_LEN][3];
    static int16_t out[FEAT_COUNT];
    uint32_t seed = (uint32_t)TEST_SEED;
    int32_t n = TEST_N, w;
    int16_t e;
    int32_t fails = 0;
#ifndef __AVR__
    if (argc > 1) {
        seed = (uint32_t)strtoul(argv[1], NULL, 10);
    }
    if (argc > 2) {
        n = (int32_t)strtol(argv[2], NULL, 10);
    }
#endif
    sim16_init();
    fails += check_isqrt();
#ifndef SPIKE_STANDIN
    {
        int16_t k, bad = 0;
        for (k = 0; k < FEAT_COUNT; k++) {
            int16_t want = (int16_t)(k & 1);
            int16_t got = FEAT_IS_NONNEG(k) ? 1 : 0;
            if (want != got) {
                bad++;
            }
        }
        printf("CHK nonneg %d\n", (int)bad);
        fails += bad;
        printf("CHK version %d\n", (FEATURES_VERSION == 1u) ? 0 : 1);
        if (FEATURES_VERSION != 1u) {
            fails++;
        }
        if (FEAT_WINDOW_LEN != 150 || FEAT_AXES != 3 || FEAT_SEG_LEN != 15 ||
            FEAT_SEGMENTS != 10 || FEAT_COUNT != 60) {
            printf("CHK dims 1\n");
            fails++;
        } else {
            printf("CHK dims 0\n");
        }
    }
#else
    printf("CHK nonneg SKIP\nCHK version SKIP\nCHK dims SKIP\n");
#endif
    for (e = 0; e < N_EDGE; e++) {
        fill_edge(e, x);
        features_extract(x, out);
        print_line('E', (int32_t)e, out);
    }
    rng_seed(seed);
    for (w = 0; w < n; w++) {
        fill_random(w, x);
        features_extract(x, out);
        print_line('W', w, out);
    }
    printf("DONE %ld %ld\n", (long)N_EDGE, (long)n);
    sim16_exit((fails == 0) ? 0 : 1);
    return 0;
}
// [END AI-GENERATED]
