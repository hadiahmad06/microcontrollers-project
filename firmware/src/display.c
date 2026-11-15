// [AI-GENERATED: Claude Code]
/**
 * @file display.c
 * @brief 8x8 framebuffer, cap, limiter, GRB serialisation. See display.h.
 *
 * Static RAM: 192 B framebuffer. Integer-only; no blocking, no malloc.
 */
#include "display.h"

/** Current units: 1 unit = 20 mA / 255, so the limit in units is mA * 255 / 20.
 *  The 20 mA per colour channel (60 mA per pixel at full white) figure is from the Adafruit NeoPixel Uberguide,
 *  "Powering NeoPixels", https://learn.adafruit.com/adafruit-neopixel-uberguide/powering-neopixels
 *  (no revision or date; page not confirmed as fetched, treat as UNVERIFIED). */
#define DISPLAY_LIMIT_UNITS ((uint32_t)DISPLAY_LIMIT_MA * 255u / 20u)

static uint8_t g_fb[DISPLAY_BYTES]; /* R,G,B per pixel, row-major, row 0 = top */

/**
 * Applies the compile-time brightness cap to one raw channel value: round(c * DISPLAY_CAP / 255),
 * computed in uint32_t so that 16-bit int targets cannot overflow.
 * @param c raw 8-bit channel value, 0..255.
 * @return capped value, 0..DISPLAY_CAP (rounded to nearest, ties up).
 */
static uint8_t cap_channel(uint8_t c)
{
    return (uint8_t)((((uint32_t)c * DISPLAY_CAP) + 127u) / 255u);
}

void display_clear(void)
{
    uint16_t i;
    for (i = 0u; i < DISPLAY_BYTES; i++) {
        g_fb[i] = 0u;
    }
}

void display_set(uint8_t row, uint8_t col, uint8_t r, uint8_t g, uint8_t b)
{
    uint16_t o;
    if (row >= DISPLAY_H || col >= DISPLAY_W) {
        return;
    }
    o = (uint16_t)(((uint16_t)row * DISPLAY_W + col) * 3u);
    g_fb[o] = r;
    g_fb[o + 1u] = g;
    g_fb[o + 2u] = b;
}

void display_get(uint8_t row, uint8_t col, uint8_t rgb[3])
{
    uint16_t o;
    if (row >= DISPLAY_H || col >= DISPLAY_W) {
        return;   /* out of range: rgb left unchanged (main-agent ruling, WP4-a/WP4-aT) */
    }
    o = (uint16_t)(((uint16_t)row * DISPLAY_W + col) * 3u);
    rgb[0] = g_fb[o];
    rgb[1] = g_fb[o + 1u];
    rgb[2] = g_fb[o + 2u];
}

void display_draw_bitmap(const uint8_t bits[8], uint8_t r, uint8_t g, uint8_t b)
{
    uint8_t row;
    uint8_t col;
    display_clear();
    for (row = 0u; row < DISPLAY_H; row++) {
        for (col = 0u; col < DISPLAY_W; col++) {
            if ((bits[row] & (uint8_t)(0x80u >> col)) != 0u) {
                display_set(row, col, r, g, b);
            }
        }
    }
}

uint32_t display_units(void)
{
    uint32_t sum = 0u;
    uint16_t i;
    for (i = 0u; i < DISPLAY_BYTES; i++) {
        sum += cap_channel(g_fb[i]);
    }
    return sum;
}

uint16_t display_render(uint8_t out[DISPLAY_BYTES])
{
    /*
     * Limiter: U = display_units() (sum of capped values). L = DISPLAY_LIMIT_UNITS.
     * Claim: the units written to the output after limiting (after) satisfy after <= L,
     * and the returned mA satisfies floor(after * 20 / 255) <= DISPLAY_LIMIT_MA.
     * Proof:
     *  - U <= L: nothing is scaled, so after = U <= L.
     *  - U > L: then U > 0, so the division is safe (L = 0 is also safe: every value becomes 0).
     *    Each capped value v becomes floor(v * L / U) <= v * L / U. The sum over all 192 channels
     *    is therefore <= (L / U) * (sum of v) = (L / U) * U = L. This uses sum of v == U exactly,
     *    which holds because display_units() and this loop apply the same cap_channel() to the
     *    same g_fb, and nothing modifies g_fb between them. The floor only ever lowers a value.
     *  - mA: after <= L = floor(DISPLAY_LIMIT_MA * 255 / 20) <= DISPLAY_LIMIT_MA * 255 / 20, so
     *    floor(after * 20 / 255) <= DISPLAY_LIMIT_MA.
     * Overflow: v * L is evaluated in uint32_t (v is uint32_t). v <= DISPLAY_CAP <= 255 and
     * L = floor(DISPLAY_LIMIT_MA * 255 / 20), so v * L < 2^32 whenever DISPLAY_LIMIT_MA < about
     * 16.8 million mA (255 * 255 * mA / 20 < 2^32); the default is 32 * 3825 = 122400.
     */
    uint32_t units = display_units();
    uint32_t after = 0u;
    uint8_t row;
    uint8_t col;
    uint8_t ch;

    for (row = 0u; row < DISPLAY_H; row++) {
        for (col = 0u; col < DISPLAY_W; col++) {
            /* Wire pixel position; serpentine reverses the columns of odd rows. */
            uint8_t wcol = col;
            uint16_t src = (uint16_t)(((uint16_t)row * DISPLAY_W + col) * 3u);
            uint16_t dst;
#if DISPLAY_SERPENTINE
            if ((row & 1u) != 0u) {
                wcol = (uint8_t)(DISPLAY_W - 1u - col);
            }
#endif
            dst = (uint16_t)(((uint16_t)row * DISPLAY_W + wcol) * 3u);
            for (ch = 0u; ch < 3u; ch++) {
                uint32_t v = cap_channel(g_fb[src + ch]);
                uint16_t d;
                if (units > DISPLAY_LIMIT_UNITS) {
                    v = (v * DISPLAY_LIMIT_UNITS) / units;
                }
                after += v;
                /* Wire order G,R,B from stored R,G,B: R(0)->1, G(1)->0, B(2)->2. */
                d = (uint16_t)(dst + ((ch == 0u) ? 1u : (ch == 1u) ? 0u : 2u));
                out[d] = (uint8_t)v;
            }
        }
    }
    return (uint16_t)(after * 20u / 255u);
}
// [END AI-GENERATED]
