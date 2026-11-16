// [AI-GENERATED: Claude Code]
/**
 * @file p24_regs.h
 * @brief Single include point for device registers and the ISR attribute.
 *
 * Target build (XC16): <xc.h> pulls in p24FJ64GA002.h. Host `check` build (-DHAL_CHECK_MOCK):
 * firmware/hal/pic24/test/p24_mock.h and a plain function for HAL_ISR (the mock makes
 * `__attribute__((interrupt, no_auto_psv))` a no-op, as the host compiler cannot take it).
 * UNVERIFIED: not compiled with XC16; register names from memory.
 */
#ifndef P24_REGS_H
#define P24_REGS_H

#ifdef HAL_CHECK_MOCK
#include "p24_mock.h"
#define HAL_ISR(name) void name(void)
#else
#include <xc.h>
/* XC16 interrupt handler: auto-saves context; no_auto_psv = ISR does not touch PSVPAG (-mconst-in-code) */
#define HAL_ISR(name) void __attribute__((interrupt, no_auto_psv)) name(void)
#endif

#endif /* P24_REGS_H */
// [END AI-GENERATED]
