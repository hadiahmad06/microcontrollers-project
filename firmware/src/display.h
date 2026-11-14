// [AI-GENERATED: Claude Code]
/**
 * @file display.h
 * @brief 8x8 WS2812 framebuffer, brightness cap, current limiter and GRB serialisation
 *        (docs/agent/CONTRACTS.md C6.3, C7; docs/agent/hadi/proposals/C6b_display_bulb.md 2.1, 5).
 *
 * Hardware independent: the cycle-counted bit-bang and interrupt masking live elsewhere
 * (XC16 asm, later ticket). This module only prepares the 192 wire bytes.
 *
 * Framebuffer: 64 pixels x R,G,B, row-major, index = row*8 + col, row 0 = top, col 0 = left.
 * Stored values are the raw 8-bit colours; cap and limiter are applied in display_render().
 */
#ifndef DISPLAY_MODULE_H
#define DISPLAY_MODULE_H

#include <stdint.h>

/** Per-channel brightness cap (compile-time). Each channel c becomes (c*CAP+127)/255, 0..CAP. */
#ifndef DISPLAY_CAP
#define DISPLAY_CAP 32u
#endif
/** Estimated current limit in mA for the whole matrix (20 mA per channel at 255). */
#ifndef DISPLAY_LIMIT_MA
#define DISPLAY_LIMIT_MA 300u
#endif
/**
 * Set to 1 if the matrix is wired as a serpentine (odd rows run right-to-left): the column
 * order of odd rows is then reversed in the wire data. BENCH-dependent: the physical wiring
 * is not yet known, so the default is 0 (all rows left-to-right).
 */
#ifndef DISPLAY_SERPENTINE
#define DISPLAY_SERPENTINE 0
#endif

#define DISPLAY_W 8u
#define DISPLAY_H 8u
#define DISPLAY_BYTES 192u

/** Sets every pixel to black. */
void display_clear(void);

/**
 * Sets one pixel. Out-of-range row/col is ignored.
 * @param row 0..7, 0 = top. @param col 0..7, 0 = left.
 * @param r,g,b raw 8-bit colour (0..255), capped later in display_render().
 */
void display_set(uint8_t row, uint8_t col, uint8_t r, uint8_t g, uint8_t b);

/**
 * Reads back the raw stored colour of one pixel.
 * @param row 0..7. @param col 0..7.
 * @param rgb output, 3 bytes R,G,B. Out-of-range row/col yields {0,0,0}.
 */
void display_get(uint8_t row, uint8_t col, uint8_t rgb[3]);

/**
 * Clears the framebuffer, then sets every lit bitmap pixel to one colour.
 * @param bits 8 bytes, byte 0 = top row, bit 7 = leftmost column.
 * @param r,g,b colour for lit pixels.
 */
void display_draw_bitmap(const uint8_t bits[8], uint8_t r, uint8_t g, uint8_t b);

/**
 * Current estimate before limiting.
 * @return sum over all 192 capped channel values (1 unit = 20 mA / 255).
 */
uint32_t display_units(void);

/**
 * Serialises the frame in WS2812 wire order (per pixel G, R, B; pixels 0..63; MSB-first bit
 * order is the bit-banger's job) after applying the cap and the current limiter.
 * @param out 192 bytes of output.
 * @return estimated current in mA after limiting, rounded down; always <= DISPLAY_LIMIT_MA.
 */
uint16_t display_render(uint8_t out[DISPLAY_BYTES]);

#endif /* DISPLAY_MODULE_H */
// [END AI-GENERATED]
