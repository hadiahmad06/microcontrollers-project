// [AI-GENERATED: Claude Code]
/**
 * @file icons.c
 * @brief Icon bitmaps and colours. See icons.h. All tables are static const (flash).
 */
#include "icons.h"
#include "display.h"
#include "gesture_ids.h"

#define N_ICONS 15u /* index 0 = UNKNOWN(-1), 1..13 = ids 0..12, 14 = LEARN_OK */
#define IDX_UNKNOWN 0u
#define IDX_LEARN_OK 14u

static const uint8_t k_bitmap[N_ICONS][8] = {
    /* -1 UNKNOWN: question mark */
    {0x3C, 0x66, 0x06, 0x0C, 0x18, 0x18, 0x00, 0x18},
    /* 0 NONE: blank */
    {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00},
    /* 1 SWIPE_RIGHT: arrow right */
    {0x10, 0x18, 0xFE, 0xFF, 0xFE, 0x18, 0x10, 0x00},
    /* 2 SWIPE_LEFT: arrow left */
    {0x08, 0x18, 0x7F, 0xFF, 0x7F, 0x18, 0x08, 0x00},
    /* 3 RAISE: arrow up */
    {0x18, 0x3C, 0x7E, 0xFF, 0x18, 0x18, 0x18, 0x18},
    /* 4 PUSH_DOWN: arrow down */
    {0x18, 0x18, 0x18, 0x18, 0xFF, 0x7E, 0x3C, 0x18},
    /* 5 CIRCLE_CW: ring with head */
    {0x3C, 0x42, 0x87, 0x82, 0x81, 0x42, 0x3C, 0x00},
    /* 6 CIRCLE_CCW: mirrored ring with head */
    {0x3C, 0x42, 0xE1, 0x41, 0x81, 0x42, 0x3C, 0x00},
    /* 7 TWIST: hourglass */
    {0xFF, 0x7E, 0x3C, 0x18, 0x18, 0x3C, 0x7E, 0xFF},
    /* 8 THRUST: target */
    {0x3C, 0x42, 0x99, 0xA5, 0xA5, 0x99, 0x42, 0x3C},
    /* 9..12 learned slots: digits 1..4 */
    {0x18, 0x38, 0x18, 0x18, 0x18, 0x18, 0x7E, 0x00},
    {0x3C, 0x66, 0x06, 0x0C, 0x18, 0x30, 0x7E, 0x00},
    {0x3C, 0x66, 0x06, 0x1C, 0x06, 0x66, 0x3C, 0x00},
    {0x0C, 0x1C, 0x3C, 0x6C, 0x7E, 0x0C, 0x0C, 0x00},
    /* LEARN_OK: check mark */
    {0x00, 0x01, 0x03, 0x06, 0x8C, 0xD8, 0x70, 0x20}
};

static const uint8_t k_color[N_ICONS][3] = {
    {255, 128, 0},   /* UNKNOWN orange */
    {0, 0, 0},       /* NONE */
    {255, 0, 0},     /* SWIPE_RIGHT red */
    {0, 0, 255},     /* SWIPE_LEFT blue */
    {0, 255, 0},     /* RAISE green */
    {255, 255, 0},   /* PUSH_DOWN yellow */
    {0, 255, 255},   /* CIRCLE_CW cyan */
    {255, 0, 255},   /* CIRCLE_CCW magenta */
    {255, 255, 255}, /* TWIST white */
    {255, 64, 64},   /* THRUST salmon */
    {160, 0, 255},   /* learned 1..4 purple */
    {160, 0, 255},
    {160, 0, 255},
    {160, 0, 255},
    {0, 255, 0}      /* LEARN_OK green */
};

/** Maps an id to a table index; unsupported ids map to UNKNOWN. */
static uint8_t icon_index(int8_t id)
{
    if (id == (int8_t)ICON_LEARN_OK) {
        return (uint8_t)IDX_LEARN_OK;
    }
    if (id >= 0 && id <= (int8_t)(GESTURE_LEARNED_BASE + GESTURE_MAX_LEARNED - 1)) {
        return (uint8_t)((uint8_t)id + 1u);
    }
    return (uint8_t)IDX_UNKNOWN;
}

const uint8_t *icon_bitmap(int8_t id)
{
    return k_bitmap[icon_index(id)];
}

void icon_color(int8_t id, uint8_t rgb[3])
{
    uint8_t i = icon_index(id);
    rgb[0] = k_color[i][0];
    rgb[1] = k_color[i][1];
    rgb[2] = k_color[i][2];
}

void icon_show(int8_t id)
{
    uint8_t i = icon_index(id);
    display_draw_bitmap(k_bitmap[i], k_color[i][0], k_color[i][1], k_color[i][2]);
}
// [END AI-GENERATED]
