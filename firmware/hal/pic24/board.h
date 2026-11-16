// [AI-GENERATED: Claude Code]
/**
 * @file board.h
 * @brief PIC24FJ64GA002 board layer: clock, pins, PPS, 1 ms tick, debug pin (ticket HAL).
 *
 * UNVERIFIED: not compiled with XC16; register names from memory.
 * Sources (all "from memory, page not re-read"): DS39881 (PIC24FJ64GA004 family data sheet:
 * oscillator, I/O ports, PPS, Timer1, interrupts); docs/agent/CONTRACTS.md C6.1, C6.2;
 * docs/agent/hadi/proposals/C6a_sensor_io.md section 3.
 *
 * Pin map (C6.1): RB7/INT0 = LIS3DH INT1, RB8/RB9 = I2C1 SCL/SDA, RB12/RP12 = LIS3DH INT2 -> INT1,
 * RB13/RP13 = U1TX, RB14/RP14 = U1RX, RB4 = debug pin. RB15 (WS2812) is untouched here.
 */
#ifndef BOARD_H
#define BOARD_H

#include <stdbool.h>
#include <stdint.h>

/**
 * Bring up the whole board: pins (all analog off), PPS, 1 ms Timer1 tick, UART1, INT0/INT1 and
 * I2C1. Returns with interrupts enabled at CPU priority 0 (the PIC24 reset state: nothing to enable
 * globally). If the PLL does not lock it never returns (board_error_blink(1)).
 */
void board_init(void);

/**
 * Drive the debug/timing pin RB4 (pin 11).
 * @param level true = high, false = low
 */
void board_debug_pin(bool level);

/**
 * Millisecond counter kept by the Timer1 ISR (same value port_millis() returns).
 * @return ms since board_init, wraps at 65536; a single 16-bit read is atomic on the PIC24
 */
uint16_t board_millis(void);

/**
 * Signal a fatal error on the debug pin RB4 and NEVER RETURN. This is the only blocking function
 * in the HAL: application code only, never library code. Pattern: `code` pulses of 150 ms, then a
 * 1 s pause, forever (1 = clock/PLL, 2 = sensor not found, 3 = model/config mismatch, 4 = other).
 * @param code number of pulses per cycle (0 is treated as 1)
 */
void board_error_blink(uint8_t code) __attribute__((noreturn));

/* ---- implemented in other HAL files, called by board_init() ---- */

/** UART1 + INT0/INT1 + TX ring set-up (port_pic24.c). Pins/PPS must already be mapped. */
void port_pic24_init(void);

/** I2C1 400 kHz master set-up (lis3dh_hal_pic24.c). */
void lis3dh_hal_pic24_init(void);

#endif /* BOARD_H */
// [END AI-GENERATED]
