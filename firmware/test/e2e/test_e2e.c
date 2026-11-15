// [AI-GENERATED: Claude Code]
/*
 * test_e2e.c - end-to-end driver (ticket 3.8): window -> features -> MLP -> k-NN -> decision, using
 * the real firmware modules, with every intermediate printed in short text lines (simavr splits
 * UART lines longer than 255 characters) for run_e2e.py to compare with the Python tools.
 *
 * Window generator and scenario plan are mirrored exactly in run_e2e.py (class Rng, gen_base,
 * SCENARIOS). Host: ./test_e2e SEED NPER. sim16: -DTEST_SEED=<n>u -DTEST_NPER=<n>u.
 * Output line formats (idx = running window number, hex fields are fixed width, two's complement):
 *   M <hash8> <conf_shift>            model identity
 *   W idx tag scn min_conf cs8        tag L (learn window) or Q (query window); cs8 = FNV-1a checksum
 *                                     of the 450 raw samples (3.8R F-08)
 *   F idx half 30x%04x                features 0..29 (half 0) and 30..59 (half 1)
 *   X idx 60x%02x                     x8
 *   G idx top1 margin8 9x%08x         top1, margin, logits
 *   K idx kid d1 d2 has c_k radius    k-NN result, or "K idx -" when no template / skipped
 *   R idx id conf                     final decision (Q windows only)
 *   RT scn ok|bad                     export/import round trip
 *   B scn crc4                        CRC-16 trailer of the exported blob (compared with Python's)
 *   DONE n                            end marker with window count
 *
 * Two parts: the random plan (7 scenarios, mirrored generator) and the DIRECTED plan (dplan.h,
 * written by run_e2e.py per model): a list of steps (reset, learn, query, round trip) whose windows
 * are described by (gen_base seed, optional noise, up to DPATCH single-sample patches). The directed
 * plan makes boundaries happen on purpose (3.8F); Python re-derives every expectation itself.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sim16.h"
#include "features.h"
#include "mlp.h"
#include "knn.h"
#include "classify.h"
#include "gesture_ids.h"

#define N_SCEN 7u
#define MAX_TPL (GESTURE_MAX_LEARNED * GESTURE_TEMPLATES_PER_CLASS)

/** Scenario table: learned classes and templates per class (mirrored in run_e2e.py SCENARIOS). */
static const uint8_t scen_ncls[N_SCEN] = {0u, 1u, 1u, 3u, 4u, 3u, 4u};
static const uint8_t scen_ntpl[N_SCEN] = {0u, 1u, 5u, 3u, 5u, 2u, 1u};
/** Scenario that runs the export -> reset -> import round trip mid-run. */
#define RT_SCEN 4u
/** Reject thresholds drawn per query window. */
static const uint8_t min_conf_tbl[4] = {0u, 64u, 192u, 255u};

/** Directed-plan step opcodes. */
#define DOP_RESET 0u
#define DOP_LEARN 1u
#define DOP_QUERY 2u
#define DOP_RT    3u
/** Patches per directed window. */
#define DPATCH 3u

/** One directed step: window = gen_base(base) [+ noise(nz_seed, nz)] [+ patches]. */
typedef struct {
    uint32_t base;           /**< gen_base() seed state, nonzero */
    uint32_t nz_seed;        /**< noise seed state, nonzero when nz != 0 */
    uint16_t pos[DPATCH];    /**< patch position: sample * 3 + axis */
    int16_t  delta[DPATCH];  /**< patch delta added to that sample value (then clamped) */
    uint8_t  op;             /**< DOP_* */
    uint8_t  scn;            /**< scenario number printed on the W line */
    uint8_t  cls;            /**< learned class index 0..3 (DOP_LEARN) */
    uint8_t  minc;           /**< min_conf (DOP_QUERY) */
    uint8_t  nz;             /**< noise amplitude, 0 = none */
    uint8_t  np;             /**< number of patches used (<= DPATCH) */
} dstep_t;

#include "dplan.h"   /* generated per model into build/mN/: DPLAN_N and dplan[] */

static int16_t win[FEAT_WINDOW_LEN][3];
static int16_t feat[FEAT_COUNT];
static int8_t  x8[FEAT_COUNT];
static int32_t logits[MLP_N_CLASSES];
static uint8_t blob[KNN_BLOB_SIZE];
static uint32_t saved[MAX_TPL];
static uint16_t fails;

/**
 * xorshift32 step (13, 17, 5).
 * xorshift32: G. Marsaglia, "Xorshift RNGs", J. Statistical Software 8(14), 2003; shifts 13/17/5.
 *
 * @param s State, must be nonzero; updated.
 * @return The new state, which is also the random value.
 */
static uint32_t rng_next(uint32_t *s)
{
    uint32_t x = *s;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *s = x;
    return x;
}

/**
 * Random integer in [0, n).
 *
 * @param s State, updated once.
 * @param n Range size, > 0.
 * @return next(s) % n.
 */
static int32_t rnd(uint32_t *s, uint32_t n)
{
    return (int32_t)(rng_next(s) % n);
}

/**
 * Clamp to the C1 sample range [-2048, 2047].
 *
 * @param v Value.
 * @return Clamped value as int16_t.
 */
static int16_t clamp12(int32_t v)
{
    if (v < -2048) {
        v = -2048;
    }
    if (v > 2047) {
        v = 2047;
    }
    return (int16_t)v;
}

/**
 * Pick a rest orientation: gravity of about 512 counts split over the three axes.
 *
 * @param s State, updated 6 times.
 * @param g Output per-axis offsets (int32_t[3]).
 * @return None.
 */
static void rest_orientation(uint32_t *s, int32_t g[3])
{
    int32_t w[3];
    int32_t sum = 0;
    uint8_t a;
    for (a = 0u; a < 3u; a++) {
        w[a] = rnd(s, 1025u);
        sum += w[a];
    }
    if (sum == 0) {
        w[0] = 1;
        sum = 1;
    }
    for (a = 0u; a < 3u; a++) {
        int32_t neg = rnd(s, 2u);
        int32_t m = (512 * w[a]) / sum;
        g[a] = (neg != 0) ? -m : m;
    }
}

/**
 * Generate one window of a randomly chosen base kind (rest x3, burst x2, extreme, uniform).
 *
 * @param s   State (updated); the first draw selects the kind.
 * @param out Window to fill, values in [-2048, 2047].
 * @return None.
 */
static void gen_base(uint32_t *s, int16_t out[FEAT_WINDOW_LEN][3])
{
    int32_t kind = rnd(s, 7u);
    int32_t g[3] = {0, 0, 0};
    int32_t na = 0, start = 0, len = 0, amp = 0, sub = 0;
    uint16_t i;
    uint8_t a;
    if (kind <= 4) {
        rest_orientation(s, g);
        na = 1 + rnd(s, 24u);
    }
    if (kind == 3 || kind == 4) {
        start = rnd(s, 100u);
        len = 10 + rnd(s, 40u);
        amp = 200 + rnd(s, 1500u);
    }
    if (kind == 5) {
        sub = rnd(s, 4u);
    }
    for (i = 0u; i < FEAT_WINDOW_LEN; i++) {
        for (a = 0u; a < 3u; a++) {
            int32_t v;
            if (kind <= 4) {
                v = g[a] + rnd(s, (uint32_t)(2 * na + 1)) - na;
                if (kind >= 3 && (int32_t)i >= start && (int32_t)i < start + len) {
                    v += rnd(s, (uint32_t)(2 * amp + 1)) - amp;
                }
            } else if (kind == 5) {
                if (sub == 0) {
                    v = -2048;
                } else if (sub == 1) {
                    v = 2047;
                } else if (sub == 2) {
                    v = ((i & 1u) != 0u) ? 2047 : -2048;
                } else {
                    v = ((((uint16_t)(i + a)) & 1u) != 0u) ? 2047 : -2048;
                }
            } else {
                v = rnd(s, 4096u) - 2048;
            }
            out[i][a] = clamp12(v);
        }
    }
}

/**
 * Add per-sample noise to the global window: v += rnd(2*nz+1) - nz, then clamp (mirror of apply_noise()).
 *
 * @param s  Noise state, updated 450 times.
 * @param nz Noise amplitude, > 0.
 * @return None.
 */
static void apply_noise(uint32_t *s, int32_t nz)
{
    uint16_t i;
    uint8_t a;
    for (i = 0u; i < FEAT_WINDOW_LEN; i++) {
        for (a = 0u; a < 3u; a++) {
            win[i][a] = clamp12((int32_t)win[i][a] + rnd(s, (uint32_t)(2 * nz + 1)) - nz);
        }
    }
}

/**
 * FNV-1a style checksum of the 450 raw samples of the global window (3.8R F-08).
 *
 * @return cs = fold of (cs ^ (uint16_t)v) * 16777619, start 2166136261, uint32_t arithmetic.
 */
static uint32_t win_checksum(void)
{
    uint32_t cs = 2166136261u;
    uint16_t i;
    uint8_t a;
    for (i = 0u; i < FEAT_WINDOW_LEN; i++) {
        for (a = 0u; a < 3u; a++) {
            cs = (cs ^ (uint32_t)(uint16_t)win[i][a]) * 16777619u;
        }
    }
    return cs;
}

/**
 * Build the global window of a directed step: gen_base(base), optional noise, then the patches.
 *
 * @param d Step (op LEARN or QUERY).
 * @return None.
 */
static void build_window(const dstep_t *d)
{
    uint32_t s = d->base;
    uint8_t p;
    gen_base(&s, win);
    if (d->nz != 0u) {
        uint32_t ns = d->nz_seed;
        apply_noise(&ns, (int32_t)d->nz);
    }
    for (p = 0u; p < d->np; p++) {
        uint16_t i = (uint16_t)(d->pos[p] / 3u);
        uint8_t a = (uint8_t)(d->pos[p] % 3u);
        win[i][a] = clamp12((int32_t)win[i][a] + (int32_t)d->delta[p]);
    }
}

/**
 * Features and MLP of the global window, then print the W/F/X/G lines.
 *
 * @param idx    Running window number.
 * @param is_q   1 for a query window (tag Q), 0 for a learn window (tag L).
 * @param scn    Scenario number.
 * @param minc   min_conf of the window (0 for learn windows).
 * @param margin Output: MLP margin.
 * @return MLP argmax (top1).
 */
static uint8_t stage_mlp(uint16_t idx, uint8_t is_q, uint8_t scn, uint8_t minc, int32_t *margin)
{
    uint8_t i, h, top1;
    features_extract(win, feat);
    top1 = mlp_forward(feat, x8, logits, margin);
    printf("W %u %s %u %u %08lx\n", (unsigned)idx, (is_q != 0u) ? "Q" : "L", (unsigned)scn, (unsigned)minc,
           (unsigned long)win_checksum());
    for (h = 0u; h < 2u; h++) {
        printf("F %u %u", (unsigned)idx, (unsigned)h);
        for (i = 0u; i < 30u; i++) {
            printf(" %04x", (unsigned)(uint16_t)feat[30u * h + i]);
        }
        printf("\n");
    }
    printf("X %u", (unsigned)idx);
    for (i = 0u; i < FEAT_COUNT; i++) {
        printf(" %02x", (unsigned)(uint8_t)x8[i]);
    }
    printf("\nG %u %u %08lx", (unsigned)idx, (unsigned)top1, (unsigned long)(uint32_t)*margin);
    for (i = 0u; i < MLP_N_CLASSES; i++) {
        printf(" %08lx", (unsigned long)(uint32_t)logits[i]);
    }
    printf("\n");
    return top1;
}

/**
 * k-NN query of the global x8 and the final decision; prints the K and R lines.
 *
 * @param idx        Running window number.
 * @param top1       MLP argmax of this window.
 * @param margin     MLP margin of this window.
 * @param minc       min_conf.
 * @param conf_shift GM_CONF_SHIFT.
 * @return None.
 */
static void stage_query(uint16_t idx, uint8_t top1, int32_t margin, uint8_t minc, uint8_t conf_shift)
{
    knn_result_t k;
    uint8_t conf = 0u;
    int8_t id;
    bool have = knn_query(x8, &k);
    if (have) {
        printf("K %u %u %u %u %u %u %u\n", (unsigned)idx, (unsigned)k.kid, (unsigned)k.d1,
               (unsigned)k.d2, (unsigned)k.has_other, (unsigned)k.c_k, (unsigned)k.radius);
    } else {
        printf("K %u -\n", (unsigned)idx);
    }
    id = classify_decide(top1, margin, conf_shift, have ? &k : NULL, minc, &conf);
    printf("R %u %d %u\n", (unsigned)idx, (int)id, (unsigned)conf);
}

/**
 * Export, print the blob's CRC trailer, reset, import and verify the store survives (counts, radii,
 * re-export identical).
 *
 * @param scn Scenario number (for the RT and B lines).
 * @return None; increments fails and prints "RT scn bad" on any difference.
 */
static void round_trip(uint8_t scn)
{
    uint8_t cnt[GESTURE_MAX_LEARNED];
    uint16_t rad[GESTURE_MAX_LEARNED];
    uint8_t crc_lo, crc_hi, c, ok = 1u;
    uint16_t n = knn_export(blob, (uint16_t)sizeof blob);
    int8_t r;
    for (c = 0u; c < GESTURE_MAX_LEARNED; c++) {
        cnt[c] = knn_count((uint8_t)(GESTURE_LEARNED_BASE + c));
        rad[c] = knn_radius((uint8_t)(GESTURE_LEARNED_BASE + c));
    }
    if (n != KNN_BLOB_SIZE) {
        ok = 0u;
    }
    crc_lo = blob[KNN_BLOB_SIZE - 2u];
    crc_hi = blob[KNN_BLOB_SIZE - 1u];
    printf("B %u %02x%02x\n", (unsigned)scn, (unsigned)crc_hi, (unsigned)crc_lo);
    knn_reset();
    if (knn_total() != 0u) {
        ok = 0u;
    }
    r = knn_import(blob, KNN_BLOB_SIZE);
    if (r != 0) {
        ok = 0u;
    }
    if (knn_export(blob, (uint16_t)sizeof blob) != KNN_BLOB_SIZE || blob[KNN_BLOB_SIZE - 2u] != crc_lo ||
        blob[KNN_BLOB_SIZE - 1u] != crc_hi) {
        ok = 0u;
    }
    for (c = 0u; c < GESTURE_MAX_LEARNED; c++) {
        if (cnt[c] != knn_count((uint8_t)(GESTURE_LEARNED_BASE + c)) ||
            rad[c] != knn_radius((uint8_t)(GESTURE_LEARNED_BASE + c))) {
            ok = 0u;
        }
    }
    printf("RT %u %s\n", (unsigned)scn, ok != 0u ? "ok" : "bad");
    if (ok == 0u) {
        fails++;
    }
}

/**
 * Run the directed plan (dplan.h) from window number idx on.
 *
 * @param idx        Running window number to continue from.
 * @param conf_shift GM_CONF_SHIFT.
 * @return The next running window number.
 */
static uint16_t run_directed(uint16_t idx, uint8_t conf_shift)
{
    uint8_t learned[GESTURE_MAX_LEARNED] = {0u, 0u, 0u, 0u};
    uint16_t n;
    for (n = 0u; n < DPLAN_N; n++) {
        const dstep_t *d = &dplan[n];
        int32_t margin;
        uint8_t top1;
        if (d->op == DOP_RESET) {
            knn_reset();
            memset(learned, 0, sizeof learned);
        } else if (d->op == DOP_LEARN) {
            build_window(d);
            (void)stage_mlp(idx, 0u, d->scn, 0u, &margin);
            learned[d->cls]++;
            if (knn_learn((uint8_t)(GESTURE_LEARNED_BASE + d->cls), x8) != (int8_t)learned[d->cls]) {
                printf("LEARNFAIL %u\n", (unsigned)idx);
                fails++;
            }
            idx++;
        } else if (d->op == DOP_QUERY) {
            build_window(d);
            top1 = stage_mlp(idx, 1u, d->scn, d->minc, &margin);
            stage_query(idx, top1, margin, d->minc, conf_shift);
            idx++;
        } else {
            round_trip(d->scn);
        }
    }
    return idx;
}

/**
 * Run the whole plan: 7 random scenarios, each learning its templates then answering nper queries,
 * then the directed plan.
 *
 * @param seed Window stream seed (0 is replaced by 1).
 * @param nper Query windows per random scenario.
 * @return 0 if all C-side checks passed, 1 otherwise.
 */
static int16_t run_all(uint32_t seed, uint16_t nper)
{
    uint32_t s = (seed != 0u) ? seed : 1u;
    uint16_t idx = 0u;
    uint8_t scn;
    mlp_model_info_t info;
    mlp_model_info(&info);
    printf("M %08lx %u\n", (unsigned long)info.model_hash, (unsigned)info.conf_shift);
    for (scn = 0u; scn < N_SCEN; scn++) {
        uint8_t ntpl = 0u, c, t;
        uint16_t q;
        knn_reset();
        for (c = 0u; c < scen_ncls[scn]; c++) {
            for (t = 0u; t < scen_ntpl[scn]; t++) {
                int32_t margin;
                saved[ntpl] = s;
                gen_base(&s, win);
                (void)stage_mlp(idx, 0u, scn, 0u, &margin);
                if (knn_learn((uint8_t)(GESTURE_LEARNED_BASE + c), x8) != (int8_t)(t + 1u)) {
                    printf("LEARNFAIL %u\n", (unsigned)idx);
                    fails++;
                }
                ntpl++;
                idx++;
            }
        }
        for (q = 0u; q < nper; q++) {
            int32_t margin;
            int32_t r = rnd(&s, 8u);
            uint8_t top1, minc;
            if (r >= 5 && ntpl > 0u) {
                uint32_t s2 = saved[rnd(&s, ntpl)];
                int32_t nz;
                gen_base(&s2, win);
                nz = 1 + rnd(&s, 8u);
                apply_noise(&s, nz);
            } else {
                gen_base(&s, win);
            }
            minc = min_conf_tbl[rnd(&s, 4u)];
            top1 = stage_mlp(idx, 1u, scn, minc, &margin);
            stage_query(idx, top1, margin, minc, info.conf_shift);
            idx++;
            if (scn == RT_SCEN && q == (uint16_t)(nper / 2u)) {
                round_trip(scn);
            }
        }
    }
    idx = run_directed(idx, info.conf_shift);
    printf("DONE %u\n", (unsigned)idx);
    return (fails == 0u) ? 0 : 1;
}

#ifdef __AVR__
/**
 * Entry point on sim16: runs the plan with the compile-time seed and count.
 *
 * @return Never returns (sim16_exit ends the simulation).
 */
int main(void)
{
    int16_t rc;
    sim16_init();
    rc = run_all(TEST_SEED, TEST_NPER);
    sim16_exit(rc);
    return 0;
}
#else
/**
 * Entry point on the host: ./test_e2e SEED NPER.
 *
 * @param argc Argument count (must be 3).
 * @param argv Program name, seed, query windows per scenario.
 * @return 2 on bad usage; otherwise exits through sim16_exit with 0 on success.
 */
int main(int argc, char **argv)
{
    int16_t rc;
    if (argc != 3) {
        fprintf(stderr, "usage: %s SEED NPER\n", argv[0]);
        return 2;
    }
    sim16_init();
    rc = run_all((uint32_t)strtoul(argv[1], NULL, 0), (uint16_t)strtoul(argv[2], NULL, 0));
    sim16_exit(rc);
    return 0;
}
#endif
// [END AI-GENERATED]
