// [AI-GENERATED: Claude Code]
/* TEST STAND-IN written from the spec only (CONTRACTS.md C6.3 + main-agent rulings) to prove the
 * display test harness. The real implementation is firmware/src/display.h. Do not ship this file. */
#ifndef DISPLAY_MODULE_H
#define DISPLAY_MODULE_H
#include <stdint.h>

#define DISPLAY_W 8u
#define DISPLAY_H 8u
#define DISPLAY_BYTES 192u
#ifndef DISPLAY_CAP
#define DISPLAY_CAP 32
#endif
#ifndef DISPLAY_LIMIT_MA
#define DISPLAY_LIMIT_MA 300
#endif
#ifndef DISPLAY_SERPENTINE
#define DISPLAY_SERPENTINE 0
#endif

/** Set every pixel to black. @return None. */
void display_clear(void);
/**
 * Set one pixel (stored uncapped). Out-of-range row/col are ignored.
 * @param row Row 0..7 (0 = top). @param col Column 0..7. @param r,g,b Colour. @return None.
 */
void display_set(uint8_t row, uint8_t col, uint8_t r, uint8_t g, uint8_t b);
/**
 * Read one pixel. Out-of-range row/col leave rgb unchanged.
 * @param row Row. @param col Column. @param rgb Output R,G,B. @return None.
 */
void display_get(uint8_t row, uint8_t col, uint8_t rgb[3]);
/**
 * Clear, then set every pixel whose bit is 1 (byte 0 = top row, bit 7 = left) to the colour.
 * @param bits 8 row bytes. @param r,g,b Colour. @return None.
 */
void display_draw_bitmap(const uint8_t bits[8], uint8_t r, uint8_t g, uint8_t b);
/** @return Sum of the capped values of the framebuffer, before limiting. */
uint32_t display_units(void);
/**
 * Write the wire image (G,R,B per pixel, capped and limited).
 * @param out DISPLAY_BYTES bytes. @return Estimated mA after limiting.
 */
uint16_t display_render(uint8_t out[DISPLAY_BYTES]);
#endif
// [END AI-GENERATED]
