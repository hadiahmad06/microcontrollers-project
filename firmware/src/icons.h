// [AI-GENERATED: Claude Code]
/**
 * @file icons.h
 * @brief 8x8 monochrome icons (flash) with one colour each, one per gesture class (C5.1).
 *        Bitmap: 8 bytes, byte 0 = top row, bit 7 = leftmost column.
 */
#ifndef ICONS_H
#define ICONS_H

#include <stdint.h>

#define ICON_LEARN_OK 100 /* pseudo id for the learn-mode check mark */

/**
 * @param id -1 (unknown), 0..8 gestures, 9..12 learned slots (digit 1..4), ICON_LEARN_OK.
 *           Any other id gives the UNKNOWN bitmap.
 * @return pointer to 8 bitmap bytes in flash.
 */
const uint8_t *icon_bitmap(int8_t id);

/**
 * @param id as icon_bitmap(). @param rgb output R,G,B (raw colour, before display cap).
 */
void icon_color(int8_t id, uint8_t rgb[3]);

/**
 * Draws the icon for id onto the framebuffer (display_draw_bitmap with its colour).
 * @param id as icon_bitmap().
 */
void icon_show(int8_t id);

#endif /* ICONS_H */
// [END AI-GENERATED]
