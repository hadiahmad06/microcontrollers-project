// [AI-GENERATED: Claude Code]
/* TEST STAND-IN (spec only), see display.h. Do not ship. */
#include "display.h"

static uint8_t s_fb[64][3];

void display_clear(void)
{
    for (uint8_t i = 0u; i < 64u; i++) { s_fb[i][0] = 0u; s_fb[i][1] = 0u; s_fb[i][2] = 0u; }
}

void display_set(uint8_t row, uint8_t col, uint8_t r, uint8_t g, uint8_t b)
{
    if (row >= 8u || col >= 8u) { return; }
    uint8_t p = (uint8_t)(row * 8u + col);
    s_fb[p][0] = r; s_fb[p][1] = g; s_fb[p][2] = b;
}

void display_get(uint8_t row, uint8_t col, uint8_t rgb[3])
{
    if (row >= 8u || col >= 8u) { return; }
    uint8_t p = (uint8_t)(row * 8u + col);
    rgb[0] = s_fb[p][0]; rgb[1] = s_fb[p][1]; rgb[2] = s_fb[p][2];
}

void display_draw_bitmap(const uint8_t bits[8], uint8_t r, uint8_t g, uint8_t b)
{
    display_clear();
    for (uint8_t row = 0u; row < 8u; row++) {
        for (uint8_t col = 0u; col < 8u; col++) {
            if ((bits[row] & (uint8_t)(0x80u >> col)) != 0u) { display_set(row, col, r, g, b); }
        }
    }
}

static uint32_t cap_of(uint8_t c)
{
    return ((uint32_t)c * (uint32_t)DISPLAY_CAP + 127u) / 255u;
}

uint32_t display_units(void)
{
    uint32_t u = 0u;
    for (uint8_t i = 0u; i < 64u; i++) { for (uint8_t k = 0u; k < 3u; k++) { u += cap_of(s_fb[i][k]); } }
    return u;
}

uint16_t display_render(uint8_t out[DISPLAY_BYTES])
{
    uint32_t units = display_units();
    uint32_t limit = (uint32_t)DISPLAY_LIMIT_MA * 255u / 20u;
    uint32_t after = 0u;
    for (uint8_t row = 0u; row < 8u; row++) {
        for (uint8_t k = 0u; k < 8u; k++) {
            uint8_t col = (DISPLAY_SERPENTINE && (row & 1u) != 0u) ? (uint8_t)(7u - k) : k;
            uint8_t p = (uint8_t)(row * 8u + col);
            uint32_t v[3];
            for (uint8_t c = 0u; c < 3u; c++) {
                v[c] = cap_of(s_fb[p][c]);
                if (units > limit) { v[c] = (v[c] * limit) / units; }
                after += v[c];
            }
            uint8_t o = (uint8_t)((row * 8u + k) * 3u);
            out[o] = (uint8_t)v[1]; out[o + 1u] = (uint8_t)v[0]; out[o + 2u] = (uint8_t)v[2];
        }
    }
    return (uint16_t)(after * 20u / 255u);
}
// [END AI-GENERATED]
