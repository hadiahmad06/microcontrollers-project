// [AI-GENERATED: Claude Code]
/**
 * @file ws2812_pic24.h
 * @brief WS2812 output on RB15 (pin 26) for the 8x8 matrix. DEBUG version (docs/agent/hadi/TODO.md T-2):
 *        masks interrupts for the whole frame (~2 ms for 192 bytes) instead of the C6.3 4-LED chunks.
 */
#ifndef WS2812_PIC24_H
#define WS2812_PIC24_H

#include <stdbool.h>
#include <stdint.h>

/**
 * Make RB15 a low output (idle level of the WS2812 data line).
 * Call once after board_init().
 */
void ws2812_init(void);

/**
 * Send a frame in wire order (G, R, B per pixel) with interrupts masked (CPU IPL 7) for its duration.
 * Refuses to send if the previous frame ended less than ~1 ms ago (WS2812 reset/latch gap >= 300 us).
 * @param bytes wire bytes, e.g. from display_render()
 * @param n     number of bytes (192 for the 8x8 matrix)
 * @return true if the frame was sent, false if it was too soon after the previous one (try again later)
 */
bool ws2812_show(const uint8_t *bytes, uint16_t n);

#endif /* WS2812_PIC24_H */
// [END AI-GENERATED]
