// [AI-GENERATED: Claude Code]
/*
 * sim16.h - tiny I/O shim for running host-style tests on a 16-bit-int target.
 *
 * Purpose: XC16 (PIC24) has a 16-bit `int`; host gcc has 32 bits, so host tests cannot catch
 * missing casts or int-promotion overflow (FRAMEWORK_REVIEW T2). These tests are also built
 * with avr-gcc for an ATmega2560 (16-bit int, 8 KB RAM like the PIC24FJ64GA002) and run under
 * simavr. This is NOT the PIC24: gate G3 (real target / MPLAB simulator) is still mandatory.
 *
 * On the host build (no __AVR__) both functions reduce to stdio / exit().
 */
#ifndef SIM16_H
#define SIM16_H

#include <stdint.h>
#include <stdio.h>

/**
 * Route stdout to the simulated USART0 (AVR) so printf output reaches the test runner.
 * On the host this does nothing.
 *
 * @return None.
 */
void sim16_init(void);

/**
 * Print the line "SIM16_EXIT <code>" and stop. On AVR the CPU is put to sleep with interrupts
 * disabled, which makes simavr terminate; run_sim16.sh turns the printed code into its exit code.
 * On the host it calls exit(code).
 *
 * @param code 0 for success, anything else for failure.
 * @return Does not return.
 */
void sim16_exit(int16_t code);

#endif
// [END AI-GENERATED]
