// [AI-GENERATED: Claude Code]
/* TEST STAND-IN (spec only). Do not ship. */
#ifndef ICONS_H
#define ICONS_H
#include <stdint.h>
#define ICON_LEARN_OK 100
/** @param id Icon id. @return 8 row bytes (byte 0 top, bit 7 left); unknown ids give the "?" bitmap. */
const uint8_t *icon_bitmap(int8_t id);
/** @param id Icon id. @param rgb Output colour. @return None. */
void icon_color(int8_t id, uint8_t rgb[3]);
/** @param id Icon id. @return None. Draws the icon with its colour. */
void icon_show(int8_t id);
#endif
// [END AI-GENERATED]
