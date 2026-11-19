// [AI-GENERATED: Claude Code]
/**
 * @file ws2812_pic24.c
 * @brief WS2812 frame output, see ws2812_pic24.h. The bit timing lives in ws2812_send.s.
 */
#include "ws2812_pic24.h"
#include "board.h"
#include "p24_regs.h"

/** Cycle-counted sender in ws2812_send.s (interrupts must already be masked). */
extern void ws2812_send_asm(const uint8_t *p, uint16_t n);

/** board_millis() at the end of the last frame. */
static uint16_t s_last_ms;
/** true once a frame has been sent (the gap check only applies after that). */
static bool s_sent;

void ws2812_init(void)
{
    LATBbits.LATB15 = 0;               /* LATB15 = 0: data line idles low (also the WS2812 reset level) */
    TRISBbits.TRISB15 = 0;             /* TRISB15 = 0: RB15 (pin 26) is an output */
}

bool ws2812_show(const uint8_t *bytes, uint16_t n)
{
    uint16_t saved_ipl;

    /* >= 2 ticks of the 1 ms timer guarantees >= 1 ms of low line since the last frame (reset >= 300 us). */
    if (s_sent && (uint16_t)(board_millis() - s_last_ms) < 2U) {
        return false;
    }

    saved_ipl = SRbits.IPL;
    SRbits.IPL = 7;                    /* IPL<2:0> = 7: CPU priority 7, masks every maskable interrupt during the frame */
    ws2812_send_asm(bytes, n);
    SRbits.IPL = saved_ipl;            /* IPL<2:0>: restore the previous CPU priority */

    s_last_ms = board_millis();
    s_sent = true;
    return true;
}
// [END AI-GENERATED]
