// [AI-GENERATED: Claude Code]
/**
 * @file main.c
 * @brief Firmware entry point with a compile-time mode switch for bench bring-up.
 *
 * APP_MODE (set below, or -DAPP_MODE=n in MPLAB X: Project Properties > xc16-gcc > Preprocessing):
 *   0: regular function: gesture library, classify each window, show its icon on the matrix
 *   1: DEBUG 8x8 RGB LED: colour fills, then one pixel walking 0..63 (checks wiring, order, colour)
 *   2: DEBUG accelerometer: drain the LIS3DH, print "x,y,z" per sample on UART1 (115200), "TAP" on a
 *      double tap; RB4 (pin 11) is high during each I2C drain, for the logic analyser
 *   3: DEBUG LED + accelerometer: tilt "bubble level" dot on the matrix (green; red for 300 ms on a double tap)
 *
 * Debug pin RB4 (pin 11): toggles on every frame in modes 1 and 3; see board_error_blink codes in board.h
 * (2 blinks = LIS3DH not found).
 */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "board.h"
#include "p24_regs.h"
#include "ws2812_pic24.h"
#include "display.h"

#ifndef APP_MODE
#define APP_MODE 1
#endif

#if (APP_MODE == 2) || (APP_MODE == 3)
#include "board_axes.h"
#include "gesture_port.h"
#include "lis3dh.h"
#endif
#if APP_MODE == 0
#include "gesture.h"
#include "icons.h"
#endif

/** WS2812 wire bytes for one frame (display_render output). */
static uint8_t s_wire[DISPLAY_BYTES];
/** Debug pin level, toggled once per shown frame. */
static bool s_dbg;

/**
 * Render the framebuffer and send it to the matrix; toggles RB4 when a frame goes out.
 * @return true if the frame was sent, false if too soon after the previous frame
 */
static bool show_frame(void)
{
    (void)display_render(s_wire);
    if (ws2812_show(s_wire, DISPLAY_BYTES)) {
        s_dbg = !s_dbg;
        board_debug_pin(s_dbg);
        return true;
    }
    return false;
}

#if (APP_MODE == 1) || (APP_MODE == 3)
/**
 * Fill every pixel with one colour.
 * @param r red 0..255 (capped to DISPLAY_CAP by display_set)
 * @param g green 0..255
 * @param b blue 0..255
 */
static void fill(uint8_t r, uint8_t g, uint8_t b)
{
    uint8_t row;
    uint8_t col;
    for (row = 0U; row < DISPLAY_H; row++) {
        for (col = 0U; col < DISPLAY_W; col++) {
            display_set(row, col, r, g, b);
        }
    }
}
#endif

#if (APP_MODE == 2) || (APP_MODE == 3)
/** Sensor-to-wand axis table (identity until BENCH C-8). */
static const lis3dh_axes_t s_axes = LIS3DH_BOARD_AXES;
/** Latest sample seen by the drain callback, wand frame, 2 mg/LSB at +-4 g. */
static int16_t s_last[3];

#if APP_MODE == 2
/**
 * Write a signed decimal number into buf (no printf on the target, C7).
 * @param v   value to format
 * @param buf at least 6 bytes
 * @return number of bytes written
 */
static uint8_t fmt_i16(int16_t v, uint8_t *buf)
{
    uint8_t tmp[5];
    uint8_t n = 0U;
    uint8_t k = 0U;
    uint16_t u;

    if (v < 0) {
        buf[n++] = (uint8_t)'-';
        u = (uint16_t)(-(int32_t)v);
    } else {
        u = (uint16_t)v;
    }
    do {
        tmp[k++] = (uint8_t)('0' + (u % 10U));
        u /= 10U;
    } while (u != 0U);
    while (k != 0U) {
        buf[n++] = tmp[--k];
    }
    return n;
}
#endif

/**
 * lis3dh_drain callback: keeps the latest sample; in mode 2 also prints it as "x,y,z\r\n" if the TX ring has room.
 * @param s   one sample, wand frame
 * @param ctx unused
 */
static void on_sample(const int16_t s[3], void *ctx)
{
    (void)ctx;
    s_last[0] = s[0];
    s_last[1] = s[1];
    s_last[2] = s[2];
#if APP_MODE == 2
    {
        uint8_t line[24];
        uint8_t n = 0U;
        n = (uint8_t)(n + fmt_i16(s[0], &line[n]));
        line[n++] = (uint8_t)',';
        n = (uint8_t)(n + fmt_i16(s[1], &line[n]));
        line[n++] = (uint8_t)',';
        n = (uint8_t)(n + fmt_i16(s[2], &line[n]));
        line[n++] = (uint8_t)'\r';
        line[n++] = (uint8_t)'\n';
        if (port_tx_room() >= n) {
            port_tx_write(line, n);
        }
    }
#endif
}

/**
 * Drain the sensor when INT1 fired or every 50 ms (backstop), and poll the latched click (no INT2, TODO T-1).
 * @return true if a double tap was seen on this call
 */
static bool sensor_service(void)
{
    static uint16_t last_ms;
    bool more = true;
    bool tap = false;
    uint16_t now = board_millis();

    if (!port_take_fifo_flag() && (uint16_t)(now - last_ms) < 50U) {
        return false;
    }
    last_ms = now;
    board_debug_pin(true);             /* RB4 high: I2C drain in progress (logic analyser marker) */
    while (more) {
        if (lis3dh_drain(on_sample, NULL, NULL, &more) < 0) {
            more = false;
        }
    }
    tap = (lis3dh_read_click() == 1);
    board_debug_pin(false);
    return tap;
}

#if APP_MODE == 3
/**
 * Map one tilt axis (+-1 g = +-500 counts) to a matrix index 0..7.
 * @param v axis value in counts
 * @return index 0..7, 3/4 when level
 */
static uint8_t tilt_to_idx(int16_t v)
{
    int32_t i = (((int32_t)v + 500) * 8) / 1000;
    if (i < 0) {
        i = 0;
    }
    if (i > 7) {
        i = 7;
    }
    return (uint8_t)i;
}
#endif
#endif /* APP_MODE 2 || 3 */

/**
 * Firmware entry point; runs the loop selected by APP_MODE.
 * @return never returns
 */
int main(void)
{
    board_init();
    IEC1bits.INT1IE = 0;               /* INT1IE = 0: INT1 (RB12) off; LIS3DH breakout has no INT2, pin floats (TODO T-1) */
    ws2812_init();
    display_clear();
    while (!show_frame()) {
        /* first frame: blank the matrix (power-up colours are random) */
    }

#if APP_MODE == 0
    {
        int8_t rc = gesture_init(100U, 4U);  /* 100 Hz ODR, +-4 g: must match the model */
        if (rc == -2) {
            board_error_blink(2);
        } else if (rc != 0) {
            board_error_blink(3);
        }
        for (;;) {
            if (gesture_poll()) {
                uint8_t conf = 0U;
                int8_t id = gesture_classify(&conf);
                display_clear();
                icon_show(id);
                while (!show_frame()) {
                    /* wait for the WS2812 gap (<= 2 ms) */
                }
            }
        }
    }

#elif APP_MODE == 1
    {
        static const uint8_t colours[7][3] = {
            {32U, 0U, 0U}, {0U, 32U, 0U}, {0U, 0U, 32U}, {32U, 32U, 32U},
            {32U, 32U, 0U}, {0U, 32U, 32U}, {32U, 0U, 32U}
        };
        uint16_t t0 = board_millis();
        uint8_t step = 0U;           /* 0..6 = colour fills (500 ms each), 7..70 = walking pixel (60 ms each) */
        bool dirty = true;

        for (;;) {
            uint16_t period = (step < 7U) ? 500U : 60U;
            if ((uint16_t)(board_millis() - t0) >= period) {
                t0 = board_millis();
                step = (uint8_t)(step + 1U);
                if (step > 70U) {
                    step = 0U;
                }
                dirty = true;
            }
            if (dirty) {
                if (step < 7U) {
                    fill(colours[step][0], colours[step][1], colours[step][2]);
                } else {
                    uint8_t p = (uint8_t)(step - 7U);
                    display_clear();
                    /* pixel 0 = row 0 col 0 should light first; red on row 0 helps spot orientation */
                    display_set((uint8_t)(p / 8U), (uint8_t)(p % 8U), (p < 8U) ? 32U : 0U, 32U, 0U);
                }
                if (show_frame()) {
                    dirty = false;
                }
            }
        }
    }

#elif APP_MODE == 2
    if (lis3dh_init(&s_axes) != LIS3DH_OK) {
        board_error_blink(2);
    }
    {
        static const uint8_t tap_msg[5] = {'T', 'A', 'P', '\r', '\n'};
        for (;;) {
            if (sensor_service() && port_tx_room() >= 5U) {
                port_tx_write(tap_msg, 5U);
            }
        }
    }

#elif APP_MODE == 3
    if (lis3dh_init(&s_axes) != LIS3DH_OK) {
        board_error_blink(2);
    }
    {
        uint16_t frame_ms = board_millis();
        uint16_t tap_ms = 0U;
        bool tap_on = false;

        for (;;) {
            if (sensor_service()) {
                tap_on = true;
                tap_ms = board_millis();
            }
            if (tap_on && (uint16_t)(board_millis() - tap_ms) >= 300U) {
                tap_on = false;
            }
            if ((uint16_t)(board_millis() - frame_ms) >= 40U) {   /* ~25 fps */
                uint8_t row = tilt_to_idx(s_last[0]);  /* wand X tilt -> row */
                uint8_t col = tilt_to_idx(s_last[1]);  /* wand Y tilt -> column */
                display_clear();
                if (tap_on) {
                    fill(8U, 0U, 0U);
                    display_set(row, col, 32U, 0U, 0U);
                } else {
                    display_set(row, col, 0U, 32U, 0U);
                }
                if (show_frame()) {
                    frame_ms = board_millis();
                }
            }
        }
    }

#else
#error "APP_MODE must be 0, 1, 2 or 3"
#endif
}
// [END AI-GENERATED]
