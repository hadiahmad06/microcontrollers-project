// [AI-GENERATED: Claude Code]
/**
 * @file board.c
 * @brief Clock check, pins, PPS, Timer1 1 ms tick, debug pin, error blink. See board.h.
 *
 * UNVERIFIED: not compiled with XC16; register names from memory.
 * Sources (from memory, page not re-read): DS39881 oscillator chapter (OSCCON, CLKDIV, PLL 4x of
 * the 8 MHz FRC = 32 MHz Fosc, FCY = Fosc/2 = 16 MHz), I/O Ports chapter (AD1PCFG, TRISx, LATx),
 * PPS chapter (OSCCON<IOLOCK>, RPINRx, RPORx, unlock via OSCCONL builtin), Timer1 chapter.
 * Oscillator choice follows C6a section 3.8 (FNOSC = FRCPLL, set in config_bits.c); WORKING
 * ASSUMPTION: C6a open question 4 (main oscillator, FRC+PLL vs crystal), not decided.
 */
#include "board.h"
#include "p24_regs.h"

/** Instruction clock in Hz (FRCPLL: 32 MHz / 2). */
#define BOARD_FCY_HZ 16000000UL

/** Timer1 period register for a 1 ms tick with prescaler 1:1: FCY/1000 - 1 = 15999. */
#define BOARD_T1_PR ((uint16_t)(BOARD_FCY_HZ / 1000UL - 1UL))

/** Milliseconds since start; written only by the Timer1 ISR. */
static volatile uint16_t s_ms;

/** Timer1 interrupt (priority 3, C6.2): only counts, clears its flag. */
HAL_ISR(_T1Interrupt)
{
    IFS0bits.T1IF = 0;                 /* T1IF = 0: acknowledge the Timer1 interrupt */
    s_ms = (uint16_t)(s_ms + 1U);
}

uint16_t board_millis(void)
{
    /* 16-bit load of a volatile word is one MOV on the PIC24: atomic w.r.t. the T1 ISR. */
    return s_ms;
}

void board_debug_pin(bool level)
{
    if (level) {
        LATBbits.LATB4 = 1;            /* LATB4 = 1: RB4 drives high */
    } else {
        LATBbits.LATB4 = 0;            /* LATB4 = 0: RB4 drives low */
    }
}

/** Map pins through PPS: U1TX -> RP13, U1RX <- RP14, INT1 <- RP12. DS39881 PPS chapter. */
static void board_pps_map(void)
{
    /* Unlock PPS: IOLOCK (OSCCON bit 6) cleared via the builtin that performs the 0x46/0x57 sequence. */
    __builtin_write_OSCCONL((unsigned int)(OSCCON & 0xFFBFU));

    RPINR18bits.U1RXR = 14;            /* U1RXR<4:0> = 14: UART1 receive input comes from RP14 (RB14, pin 25) */
    RPINR0bits.INT1R = 12;             /* INT1R<4:0> = 12: external interrupt 1 comes from RP12 (RB12, pin 23) */
    RPOR6bits.RP13R = 3;               /* RP13R<4:0> = 3: RP13 (RB13, pin 24) drives function 3 = U1TX */

    /* Lock PPS again: IOLOCK = 1 (OSCCON bit 6). */
    __builtin_write_OSCCONL((unsigned int)(OSCCON | 0x0040U));
}

/** Pin directions and digital mode. */
static void board_pins_init(void)
{
    AD1PCFG = 0xFFFFU;                 /* every PCFGn = 1: AN0..AN12 pins are digital I/O (reset default is analog) */

    LATBbits.LATB4 = 0;                /* debug pin idles low */
    TRISBbits.TRISB4 = 0;              /* TRISB4 = 0: RB4 output (debug pin) */
    TRISBbits.TRISB7 = 1;              /* TRISB7 = 1: RB7 input (INT0, LIS3DH INT1) */
    TRISBbits.TRISB12 = 1;             /* TRISB12 = 1: RB12 input (INT1 via PPS, LIS3DH INT2) */
    TRISBbits.TRISB14 = 1;             /* TRISB14 = 1: RB14 input (U1RX) */
    LATBbits.LATB13 = 1;               /* UART TX idles high: preset latch before the pin becomes an output */
    TRISBbits.TRISB13 = 0;             /* TRISB13 = 0: RB13 output (U1TX via PPS) */
    /* RB8/RB9 (I2C1) are taken over by the I2C module when I2CEN = 1; JTAGEN = OFF in config_bits.c. */
}

/** Timer1: 1 ms tick from FCY, interrupt priority 3. */
static void board_timer1_init(void)
{
    T1CON = 0;                         /* TON=0 stop, TSIDL=0, TGATE=0, TCKPS=00 (1:1), TSYNC=0, TCS=0 (internal FCY) */
    TMR1 = 0;                          /* clear the count */
    PR1 = BOARD_T1_PR;                 /* period register: match every 15999+1 FCY cycles = 1 ms */
    IPC0bits.T1IP = 3;                 /* T1IP<2:0> = 3: Timer1 interrupt priority 3 (C6.2: timers = 3) */
    IFS0bits.T1IF = 0;                 /* T1IF = 0: no stale flag */
    IEC0bits.T1IE = 1;                 /* T1IE = 1: Timer1 interrupt enabled */
    T1CONbits.TON = 1;                 /* TON = 1: start Timer1 */
}

void board_init(void)
{
    uint16_t guard;

    board_pins_init();
    board_pps_map();

    /* Oscillator is selected by the config word FNOSC = FRCPLL (config_bits.c); no run-time switch. */
    CLKDIVbits.RCDIV = 0;              /* RCDIV<2:0> = 000: FRC post-scaler 1:1 (8 MHz into the PLL), see C6a 3.8 caveat */
    CLKDIVbits.DOZEN = 0;              /* DOZEN = 0: no doze, CPU runs at full FCY */

    board_timer1_init();               /* started first so board_error_blink() has a time base */

    /* Let the RCDIV write take effect so a stale LOCK = 1 is not read (review F10). */
    for (guard = 0U; guard < 200U; guard++) {
        __builtin_nop();
    }
    /* Bounded wait for FRCPLL running (COSC<2:0> = 001) and PLL locked (LOCK = OSCCON bit 5); no infinite spin. */
    for (guard = 0xFFFFU; (guard != 0U) && !((OSCCONbits.COSC == 1U) && (OSCCONbits.LOCK != 0U)); guard--) {
        /* spin */
    }
    if (!((OSCCONbits.COSC == 1U) && (OSCCONbits.LOCK != 0U))) {
        board_error_blink(1);
    }

    port_pic24_init();
    lis3dh_hal_pic24_init();
}

/** Busy-wait using the Timer1 tick; only used by board_error_blink. */
static void board_wait_ms(uint16_t ms)
{
    uint16_t t0 = board_millis();
    while ((uint16_t)(board_millis() - t0) < ms) {
        /* blocking by design: fatal-error path only */
    }
}

void board_error_blink(uint8_t code)
{
    uint8_t i;
    if (code == 0U) {
        code = 1U;
    }
    for (;;) {
        for (i = 0U; i < code; i++) {
            board_debug_pin(true);
            board_wait_ms(150U);
            board_debug_pin(false);
            board_wait_ms(150U);
        }
        board_wait_ms(1000U);
    }
}
// [END AI-GENERATED]
