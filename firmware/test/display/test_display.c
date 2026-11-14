// [AI-GENERATED: Claude Code]
/*
 * test_display.c - replay driver for the display.c / icons.c suite (ticket WP4-aT).
 *
 * Written from the SPEC (docs/agent/CONTRACTS.md C6.3 and the main-agent rulings), never from the
 * implementation. The driver only CALLS the API and prints one text record per result; oracle.py
 * replays the identical frames from the spec and run_tests.py compares the text.
 * Directed frames first, then bitmap / out-of-range / clear cases, then N xorshift32 scenarios
 * (mirrored in oracle.py), then the icon section (checked by property in run_tests.py).
 *
 * Record per frame: "C <name> <ret_mA> <units_before_limit> <guard_ok> <get_ok>" followed by three
 * "D <128 hex>" lines (64 bytes each, the 192-byte wire image; lines stay < 255 chars for simavr).
 * Host: ./test_display_host SEED NSCEN.   AVR: SEED / NSCEN come from -DTEST_SEED / -DTEST_NSCEN.
 * The exit code is always 0; the verdict is the comparison done by run_tests.py.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sim16.h"
#include "display.h"
#include "icons.h"

#ifndef TEST_SEED
#define TEST_SEED 1u
#endif
#ifndef TEST_NSCEN
#define TEST_NSCEN 40u
#endif

/* Configuration under test (defaults are the spec defaults; -D overrides reach display.c too). */
#ifdef DISPLAY_CAP
#define T_CAP ((uint32_t)DISPLAY_CAP)
#else
#define T_CAP 32u
#endif
#ifdef DISPLAY_LIMIT_MA
#define T_LIMIT_MA ((uint32_t)DISPLAY_LIMIT_MA)
#else
#define T_LIMIT_MA 300u
#endif
#ifdef DISPLAY_SERPENTINE
#define T_SERP ((uint32_t)DISPLAY_SERPENTINE)
#else
#define T_SERP 0u
#endif

#define NBYTES 192u
#define GUARD 0xA5u

static uint32_t g_rng;

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
 * Spec cap formula c_cap = (c * cap + 127) / 255.
 *
 * @param c Channel value.
 * @return Capped value.
 */
static uint32_t cap_of(uint32_t c)
{
    return (c * T_CAP + 127u) / 255u;
}

/**
 * Write every channel of the framebuffer from a 192-byte R,G,B row-major array via display_set.
 *
 * @param fb 192 bytes, pixel p = row*8+col at fb[3p..3p+2] = R,G,B.
 * @return None.
 */
static void load(const uint8_t *fb)
{
    for (uint8_t p = 0u; p < 64u; p++) {
        display_set((uint8_t)(p / 8u), (uint8_t)(p % 8u), fb[3u * p], fb[3u * p + 1u], fb[3u * p + 2u]);
    }
}

/**
 * Fill the whole framebuffer with a constant noise colour (to prove later calls overwrite/clear).
 *
 * @return None.
 */
static void noise(void)
{
    for (uint8_t p = 0u; p < 64u; p++) {
        display_set((uint8_t)(p / 8u), (uint8_t)(p % 8u), 77u, 66u, 55u);
    }
}

/**
 * Print one frame record: render + units + guard check + display_get check against expect.
 *
 * @param name   Case name (no spaces).
 * @param expect 192-byte raw R,G,B framebuffer content the spec says display_get must return.
 * @return None.
 */
static void emit(const char *name, const uint8_t *expect)
{
    uint8_t out[NBYTES + 4u];
    memset(out, 0xEE, sizeof out);
    for (uint8_t i = 0u; i < 4u; i++) { out[NBYTES + i] = GUARD; }
    uint16_t ret = display_render(out);
    uint32_t units = display_units();
    uint8_t guard = 1u;
    for (uint8_t i = 0u; i < 4u; i++) { if (out[NBYTES + i] != GUARD) { guard = 0u; } }
    uint8_t getok = 1u;
    for (uint8_t p = 0u; p < 64u; p++) {
        uint8_t rgb[3] = {1u, 2u, 3u};
        display_get((uint8_t)(p / 8u), (uint8_t)(p % 8u), rgb);
        if (rgb[0] != expect[3u * p] || rgb[1] != expect[3u * p + 1u] || rgb[2] != expect[3u * p + 2u]) { getok = 0u; }
    }
    printf("C %s %u %lu %u %u\n", name, (unsigned)ret, (unsigned long)units, (unsigned)guard, (unsigned)getok);
    for (uint8_t line = 0u; line < 3u; line++) {
        printf("D ");
        for (uint8_t i = 0u; i < 64u; i++) { printf("%02X", (unsigned)out[line * 64u + i]); }
        printf("\n");
    }
}

/**
 * Build a frame whose capped sum is exactly `target` (as far as 192 channels allow): channels at
 * 255 (capped = cap) first, then one channel with the smallest input giving the remainder.
 *
 * @param fb     Output, 192 bytes.
 * @param target Wanted capped sum.
 * @return None.
 */
static void frame_target(uint8_t *fb, uint32_t target)
{
    memset(fb, 0, NBYTES);
    for (uint16_t i = 0u; i < NBYTES && target > 0u; i++) {
        if (target >= T_CAP) { fb[i] = 255u; target -= T_CAP; }
        else {
            for (uint16_t c = 0u; c < 256u; c++) {
                if (cap_of(c) == target) { fb[i] = (uint8_t)c; break; }
            }
            target = 0u;
        }
    }
}

#define NFRAME 13u
static const char *const FRAME_NAME[NFRAME] = {
    "zero", "all255", "one_r255", "one_white", "ramp_a", "ramp_c", "ramp_rev",
    "lim_m1", "lim_eq", "lim_p1", "lim_p2", "lim_x15", "half128"
};

/**
 * Build directed frame k (names in FRAME_NAME); mirrored in oracle.py.
 *
 * @param k  Directed case index 0..NFRAME-1.
 * @param fb Output, 192 bytes.
 * @return None.
 */
static void build_frame(uint8_t k, uint8_t *fb)
{
    uint32_t limit = T_LIMIT_MA * 255u / 20u;
    memset(fb, 0, NBYTES);
    switch (k) {
    case 1: memset(fb, 255, NBYTES); break;
    case 2: fb[0] = 255u; break;
    case 3: fb[3u * (3u * 8u + 4u)] = 255u; fb[3u * (3u * 8u + 4u) + 1u] = 255u; fb[3u * (3u * 8u + 4u) + 2u] = 255u; break;
    case 4: for (uint16_t i = 0u; i < NBYTES; i++) { fb[i] = (uint8_t)i; } break;
    case 5: for (uint16_t i = 0u; i < NBYTES; i++) { fb[i] = (uint8_t)(i + 64u); } break;
    case 6: for (uint16_t i = 0u; i < NBYTES; i++) { fb[i] = (uint8_t)(255u - i); } break;
    case 7: frame_target(fb, limit - 1u); break;
    case 8: frame_target(fb, limit); break;
    case 9: frame_target(fb, limit + 1u); break;
    case 10: frame_target(fb, limit + 2u); break;
    case 11: frame_target(fb, limit + limit / 2u); break;
    case 12: memset(fb, 128, NBYTES); break;
    default: break;
    }
}

/**
 * Directed bitmap cases: noise first (draw_bitmap must clear), draw, emit.
 *
 * @param name Case name.
 * @param bits 8 bitmap rows.
 * @param r    Red.
 * @param g    Green.
 * @param b    Blue.
 * @return None.
 */
static void bitmap_case(const char *name, const uint8_t *bits, uint8_t r, uint8_t g, uint8_t b)
{
    uint8_t exp[NBYTES];
    memset(exp, 0, sizeof exp);
    for (uint8_t row = 0u; row < 8u; row++) {
        for (uint8_t col = 0u; col < 8u; col++) {
            if ((bits[row] & (uint8_t)(0x80u >> col)) != 0u) {
                uint8_t p = (uint8_t)(row * 8u + col);
                exp[3u * p] = r; exp[3u * p + 1u] = g; exp[3u * p + 2u] = b;
            }
        }
    }
    noise();
    display_draw_bitmap(bits, r, g, b);
    emit(name, exp);
}

/**
 * Pseudo-random framebuffer for scenario i: mode i%4 = uniform / sparse 255 / small / mostly bright.
 *
 * @param i  Scenario index.
 * @param fb Output, 192 bytes.
 * @return None.
 */
static void scenario_frame(uint32_t i, uint8_t *fb)
{
    uint32_t mode = i % 4u;
    for (uint16_t k = 0u; k < NBYTES; k++) {
        uint32_t r = rnd();
        uint32_t v;
        if (mode == 0u) { v = (r >> 8) & 0xFFu; }
        else if (mode == 1u) { v = (((r >> 8) & 3u) == 0u) ? 255u : 0u; }
        else if (mode == 2u) { v = ((r >> 8) & 0xFFu) % 41u; }
        else { v = (((r >> 8) & 3u) == 0u) ? 0u : ((r >> 12) & 0xFFu); }
        fb[k] = (uint8_t)v;
    }
}

/**
 * Icon section: for each id print the bitmap/colour and the rendered icon_show result.
 *
 * @return None.
 */
static void icon_section(void)
{
    static const int8_t ids[] = {-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 50, 100, -2, 127, -128};
    printf("ICONS\n");
    for (uint8_t n = 0u; n < (uint8_t)(sizeof ids / sizeof ids[0]); n++) {
        int8_t id = ids[n];
        const uint8_t *bm = icon_bitmap(id);
        uint8_t rgb[3] = {9u, 9u, 9u};
        icon_color(id, rgb);
        printf("I %d ", (int)id);
        for (uint8_t i = 0u; i < 8u; i++) { printf("%02X", (unsigned)bm[i]); }
        printf(" %u %u %u\n", (unsigned)rgb[0], (unsigned)rgb[1], (unsigned)rgb[2]);
        uint8_t a[NBYTES], b[NBYTES];
        noise();
        icon_show(id);
        uint16_t ra = display_render(a);
        uint32_t ua = display_units();
        display_clear();
        display_draw_bitmap(bm, rgb[0], rgb[1], rgb[2]);
        uint16_t rb = display_render(b);
        uint8_t match = (ra == rb && memcmp(a, b, NBYTES) == 0) ? 1u : 0u;
        printf("S %d %u %u %lu\n", (int)id, (unsigned)match, (unsigned)ra, (unsigned long)ua);
        for (uint8_t line = 0u; line < 3u; line++) {
            printf("D ");
            for (uint8_t i = 0u; i < 64u; i++) { printf("%02X", (unsigned)a[line * 64u + i]); }
            printf("\n");
        }
    }
}

/**
 * Program entry: prints CFG, directed cases, scenarios, the icon section and END.
 *
 * @param argc Argument count (host only).
 * @param argv argv[1] = seed, argv[2] = scenario count (host only).
 * @return 0.
 */
int main(int argc, char **argv)
{
    uint32_t seed = TEST_SEED;
    uint32_t nscen = TEST_NSCEN;
#ifndef __AVR__
    if (argc > 1) { seed = (uint32_t)strtoul(argv[1], NULL, 0); }
    if (argc > 2) { nscen = (uint32_t)strtoul(argv[2], NULL, 0); }
#else
    (void)argc; (void)argv;
#endif
    sim16_init();
    g_rng = (seed == 0u) ? 1u : seed;
    printf("CFG %lu %lu %lu\n", (unsigned long)T_CAP, (unsigned long)T_LIMIT_MA, (unsigned long)T_SERP);

    uint8_t fb[NBYTES];
    for (uint8_t k = 0u; k < NFRAME; k++) {
        build_frame(k, fb);
        display_clear();
        load(fb);
        emit(FRAME_NAME[k], fb);
    }

    /* Orientation: one lit corner bit at each corner (byte 0 = top row, bit 7 = leftmost). */
    {
        uint8_t bm[8];
        static const char *const names[5] = {"bm_tl", "bm_tr", "bm_bl", "bm_br", "bm_mid"};
        for (uint8_t k = 0u; k < 5u; k++) {
            memset(bm, 0, sizeof bm);
            if (k == 0u) { bm[0] = 0x80u; }
            else if (k == 1u) { bm[0] = 0x01u; }
            else if (k == 2u) { bm[7] = 0x80u; }
            else if (k == 3u) { bm[7] = 0x01u; }
            else { bm[2] = 0x08u; }
            bitmap_case(names[k], bm, 200u, 100u, 50u);
        }
        memset(bm, 0xFF, sizeof bm);
        bitmap_case("bm_full", bm, 255u, 255u, 255u);
        for (uint8_t i = 0u; i < 8u; i++) { bm[i] = ((i & 1u) != 0u) ? 0x55u : 0xAAu; }
        bitmap_case("bm_checker", bm, 255u, 255u, 0u);
        for (uint8_t k = 0u; k < 3u; k++) {
            uint8_t cr, cg, cb;
            for (uint8_t i = 0u; i < 8u; i++) { bm[i] = (uint8_t)((rnd() >> 8) & 0xFFu); }
            cr = (uint8_t)((rnd() >> 8) & 0xFFu);
            cg = (uint8_t)((rnd() >> 8) & 0xFFu);
            cb = (uint8_t)((rnd() >> 8) & 0xFFu);
            bitmap_case((k == 0u) ? "bm_rnd0" : ((k == 1u) ? "bm_rnd1" : "bm_rnd2"), bm, cr, cg, cb);
        }
    }

    /* Out-of-range set/get: nothing may wrap into another pixel, get must not touch rgb. */
    {
        uint8_t exp[NBYTES];
        uint8_t rgb[3] = {7u, 8u, 9u};
        uint8_t ok = 1u;
        memset(exp, 0, sizeof exp);
        display_clear();
        display_set(8u, 0u, 200u, 200u, 200u);
        display_set(0u, 8u, 200u, 200u, 200u);
        display_set(8u, 8u, 200u, 200u, 200u);
        display_set(255u, 255u, 200u, 200u, 200u);
        display_set(7u, 255u, 200u, 200u, 200u);
        display_set(7u, 7u, 255u, 128u, 10u);
        exp[3u * 63u] = 255u; exp[3u * 63u + 1u] = 128u; exp[3u * 63u + 2u] = 10u;
        display_get(8u, 0u, rgb);
        display_get(0u, 8u, rgb);
        display_get(255u, 255u, rgb);
        display_get(7u, 200u, rgb);
        if (rgb[0] != 7u || rgb[1] != 8u || rgb[2] != 9u) { ok = 0u; }
        emit("out_of_range", exp);
        printf("O %u\n", (unsigned)ok);
    }

    /* display_clear after a random frame. */
    {
        uint8_t z[NBYTES];
        memset(z, 0, sizeof z);
        scenario_frame(0u, fb);
        load(fb);
        display_clear();
        emit("cleared", z);
    }

    for (uint32_t i = 0u; i < nscen; i++) {
        char nm[12];
        scenario_frame(i, fb);
        display_clear();
        load(fb);
        sprintf(nm, "s%lu", (unsigned long)i);
        emit(nm, fb);
    }

    icon_section();
    printf("END\n");
    sim16_exit(0);
    return 0;
}
// [END AI-GENERATED]
