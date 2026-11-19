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
 *   3: DEBUG LED + accelerometer: gravity-zeroed level. At start-up (hold still ~0.5 s) the resting reading
 *      is taken as zero, so the blob sits in the centre at rest. X moves it left -> right, Y top -> bottom,
 *      Z (change from rest) sets its size and colour like a heat map: blue (-Z) / green (rest) / red (+Z).
 *      Double tap = re-zero (brief white flash). Marble style: rolls downhill, lags behind a push
 *      (LED_FLIP_X / LED_FLIP_Y, see the ORIENTATION note below).
 *
 *   4: RECORD: gesture library with raw streaming on (same as main_record.c) for tools/recorder.py over
 *      UART1 / HC-06 Bluetooth; the matrix also shows the on-device class icon (synthetic model: meaningless)
 *
 * HC06_SET_115200 = 1: at boot, send "AT+BAUD8" at 9600 baud to switch a factory HC-06 to 115200, then run the
 * selected mode. Flash it ONCE with the HC-06 NOT connected over Bluetooth (LED blinking), then set it back to 0.
 *
 * Debug pin RB4 (pin 11): toggles on every frame in mode 1; in modes 2 and 3 it is high during each I2C drain
 * (mode 3 also toggles it per frame, so use mode 2 for clean drain timing); see board_error_blink codes in board.h
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
#define APP_MODE 3
#endif

#if (APP_MODE == 2) || (APP_MODE == 3)
#include "board_axes.h"
#include "gesture_port.h"
#include "lis3dh.h"
#endif
#if (APP_MODE == 0) || (APP_MODE == 4)
#include "gesture.h"
#include "icons.h"
#endif

#ifndef HC06_SET_115200
#define HC06_SET_115200 1
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
 * @param r red 0..255 (full scale; display_render scales it by DISPLAY_CAP / 255)
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

#if APP_MODE == 3
/** Samples averaged for the resting (gravity) baseline: 32 at 100 Hz = 0.32 s. */
#define LEVEL_CAL_N 32
/** Samples ignored before the baseline starts (0.2 s: lets a double tap / hand settle). */
#define LEVEL_CAL_SKIP 20
/** s_cal_n value at which the baseline is valid. */
#define LEVEL_CAL_END (LEVEL_CAL_SKIP + LEVEL_CAL_N)
/** Counts per pixel of travel: 2 mg/LSB, so 125 counts = 0.25 g per pixel (+-1 g reaches the edges). */
#define LEVEL_COUNTS_PER_PX 125
/*
 * ORIENTATION MATTERS. Bench-verified 2026-11-18 (Hadi) with LED_FLIP_X = 0, LED_FLIP_Y = 1: both axes are
 * "marble on a tray" style. Tilt the board and the blob rolls DOWNHILL; push the board and the blob LAGS
 * behind (moves opposite to the push, then settles back to centre). Freefall shows a big blue blob (Z reads 0 g).
 * These two flags only hold for the LIS3DH breakout and the 8x8 matrix mounted the way they were on that
 * breadboard. If either one is rotated or remounted, redo the tilt test (slow tilt: blob must roll downhill on
 * each axis; flip the axis that goes uphill). The flags fix the display only; the gesture pipeline uses the
 * sensor axes through LIS3DH_BOARD_AXES (board_axes.h, BENCH C-8), which this test does not set.
 */
#ifndef LED_FLIP_X
#define LED_FLIP_X 0
#endif
#ifndef LED_FLIP_Y
#define LED_FLIP_Y 1
#endif

/** Running sums for the baseline. */
static int32_t s_cal_sum[3];
/** Samples seen since the re-zero; == LEVEL_CAL_END once the baseline is valid. */
static uint8_t s_cal_n;
/** Resting reading (gravity), subtracted from every sample. */
static int16_t s_base[3];
/** Low-pass filtered (sample - baseline), filter weight 1/4. */
static int16_t s_filt[3];

/**
 * Restart the baseline: skip LEVEL_CAL_SKIP samples, then the next LEVEL_CAL_N become the new zero (hold still).
 */
static void level_recal(void)
{
    uint8_t k;
    for (k = 0U; k < 3U; k++) {
        s_cal_sum[k] = 0;
        s_filt[k] = 0;
    }
    s_cal_n = 0U;
}

/**
 * Feed one sample: accumulate the baseline, or update the filtered offset from it.
 * @param s one sample, wand frame, counts (2 mg/LSB)
 */
static void level_feed(const int16_t s[3])
{
    uint8_t k;
    if (s_cal_n < LEVEL_CAL_END) {
        if (s_cal_n >= LEVEL_CAL_SKIP) {
            for (k = 0U; k < 3U; k++) {
                s_cal_sum[k] += s[k];
            }
        }
        s_cal_n++;
        if (s_cal_n == LEVEL_CAL_END) {
            for (k = 0U; k < 3U; k++) {
                s_base[k] = (int16_t)(s_cal_sum[k] / LEVEL_CAL_N);
            }
        }
        return;
    }
    for (k = 0U; k < 3U; k++) {
        int16_t d = (int16_t)(s[k] - s_base[k]);                 /* |d| <= 4095 */
        s_filt[k] = (int16_t)(s_filt[k] + (d - s_filt[k]) / 4);  /* IIR low-pass, cuts jitter */
    }
}

/**
 * Clamp a 1/16-pixel coordinate to the matrix (0 .. 7 px).
 * @param v coordinate in 1/16 px
 * @return v limited to 0..112
 */
static int32_t level_clamp(int32_t v)
{
    if (v < 0) {
        return 0;
    }
    if (v > 112) {
        return 112;
    }
    return v;
}

/**
 * Draw the level into the framebuffer: blob position from X/Y, size and heat colour from Z.
 * Coordinates are in 1/16 pixel; the centre 56 = 3.5 px lies between the middle four LEDs.
 * @param flash true = dim white background (re-zero confirmation)
 */
static void level_draw(bool flash)
{
    int32_t cx;
    int32_t cy;
    int32_t r2;
    int32_t az;
    uint8_t hot;
    uint8_t red;
    uint8_t grn;
    uint8_t blu;
    uint8_t row;
    uint8_t col;

    display_clear();
    if (flash) {
        fill(32U, 32U, 32U);           /* dim white flash (renders as 4 of 255) */
    }
    if (s_cal_n < LEVEL_CAL_END) {
        display_set(3U, 3U, 64U, 64U, 64U);   /* calibrating: dim white centre, hold still */
        display_set(3U, 4U, 64U, 64U, 64U);
        display_set(4U, 3U, 64U, 64U, 64U);
        display_set(4U, 4U, 64U, 64U, 64U);
        return;
    }

    cx = 56 + ((int32_t)s_filt[0] * 16) / LEVEL_COUNTS_PER_PX;   /* X -> column, left to right */
    cy = 56 + ((int32_t)s_filt[1] * 16) / LEVEL_COUNTS_PER_PX;   /* Y -> row, top to bottom */
#if LED_FLIP_X
    cx = 112 - cx;
#endif
#if LED_FLIP_Y
    cy = 112 - cy;
#endif
    cx = level_clamp(cx);
    cy = level_clamp(cy);

    az = (s_filt[2] < 0) ? -(int32_t)s_filt[2] : (int32_t)s_filt[2];
    if (az > 500) {
        az = 500;                                   /* saturate at 1 g change */
    }
    hot = (uint8_t)((az * 255) / 500);              /* 0..255 */
    red = (s_filt[2] > 0) ? hot : 0U;               /* +Z: green -> red */
    blu = (s_filt[2] < 0) ? hot : 0U;               /* -Z: green -> blue */
    grn = (uint8_t)(255U - hot);
    {
        int32_t r = 12 + (az * 40) / 500;           /* radius 0.75 px at rest (centre 2x2) .. 3.25 px at 1 g */
        r2 = r * r;
    }

    for (row = 0U; row < DISPLAY_H; row++) {
        for (col = 0U; col < DISPLAY_W; col++) {
            int32_t dx = (int32_t)col * 16 - cx;
            int32_t dy = (int32_t)row * 16 - cy;
            int32_t d2 = dx * dx + dy * dy;
            if (d2 <= r2 / 4) {
                display_set(row, col, red, grn, blu);                                   /* hot core */
            } else if (d2 <= r2) {
                display_set(row, col, (uint8_t)(red / 3U), (uint8_t)(grn / 3U), (uint8_t)(blu / 3U)); /* rim */
            }
        }
    }
}
#endif

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
#if APP_MODE == 3
    level_feed(s);
#endif
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

#endif /* APP_MODE 2 || 3 */

#if HC06_SET_115200
/**
 * Blocking wait on the 1 ms tick (application code only, never library code).
 * @param ms milliseconds to wait
 */
static void wait_ms(uint16_t ms)
{
    uint16_t t0 = board_millis();
    while ((uint16_t)(board_millis() - t0) < ms) {
        /* wait */
    }
}

/**
 * Send one string on UART1 by polling (the TX ring/ISR is not used yet at this point).
 * @param str NUL-terminated text
 */
static void uart1_puts_polled(const char *str)
{
    while (*str != '\0') {
        while (U1STAbits.UTXBF) {
            /* UTXBF = 1: transmit buffer full */
        }
        U1TXREG = (uint8_t)*str++;     /* U1TXREG: next byte to transmit */
    }
    while (!U1STAbits.TRMT) {
        /* TRMT = 0: shift register still sending */
    }
}

/**
 * Switch a factory HC-06 (9600 baud) to 115200: "AT+BAUD8" at 9600, then UART1 back to 115200.
 * Works only while the HC-06 is not connected over Bluetooth. Sent twice: old (linvor) firmware wants no line
 * ending, newer clones want CR LF; the extra copy is ignored by either. Matrix pixel 0 is blue while busy.
 */
static void hc06_set_115200(void)
{
    display_clear();
    display_set(0U, 0U, 0U, 0U, 255U);
    while (!show_frame()) {
        /* wait for the WS2812 gap */
    }
    wait_ms(1000U);                    /* HC-06 boot time */
    U1BRG = 416;                       /* U1BRG = 416: 16e6 / (4 * 417) = 9592 baud (-0.08 %), HC-06 factory rate */
    uart1_puts_polled("AT+BAUD8");
    wait_ms(1500U);                    /* linvor firmware ends a command after ~1 s of silence */
    uart1_puts_polled("AT+BAUD8\r\n");
    wait_ms(1500U);
    U1BRG = 34;                        /* U1BRG = 34: back to 114286 baud (C6.1) */
    U1STAbits.OERR = 0;                /* OERR = 0: clear the RX overrun caused by the unread "OK115200" reply */
}
#endif

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
#if HC06_SET_115200
    hc06_set_115200();
#endif

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
            {255U, 0U, 0U}, {0U, 255U, 0U}, {0U, 0U, 255U}, {255U, 255U, 255U},
            {255U, 255U, 0U}, {0U, 255U, 255U}, {255U, 0U, 255U}
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
                    display_set((uint8_t)(p / 8U), (uint8_t)(p % 8U), (p < 8U) ? 255U : 0U, 255U, 0U);
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
    level_recal();
    {
        uint16_t frame_ms = board_millis();
        uint16_t tap_ms = 0U;
        bool tap_on = false;

        for (;;) {
            if (sensor_service()) {
                level_recal();                  /* double tap: re-zero (hold still ~0.5 s) */
                tap_on = true;
                tap_ms = board_millis();
            }
            if (tap_on && (uint16_t)(board_millis() - tap_ms) >= 300U) {
                tap_on = false;
            }
            if ((uint16_t)(board_millis() - frame_ms) >= 40U) {   /* ~25 fps */
                level_draw(tap_on);
                if (show_frame()) {
                    frame_ms = board_millis();
                }
            }
        }
    }

#elif APP_MODE == 4
    {
        int8_t rc = gesture_init(100U, 4U);  /* 100 Hz ODR, +-4 g: must match the model */
        if (rc == -2) {
            board_error_blink(2);
        } else if (rc != 0) {
            board_error_blink(3);
        }
        gesture_stream_raw(true);            /* HELLO every 2 s + one C2 frame per captured window */
        for (;;) {
            if (gesture_poll()) {
                int8_t id = gesture_classify(NULL);  /* completes the window; its frame goes out on the stream */
                display_clear();
                icon_show(id);
                (void)show_frame();          /* skip the icon rather than block the stream */
            }
        }
    }

#else
#error "APP_MODE must be 0, 1, 2, 3 or 4"
#endif
}
// [END AI-GENERATED]
