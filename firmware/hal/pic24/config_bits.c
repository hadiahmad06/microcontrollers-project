// [AI-GENERATED: Claude Code]
/**
 * @file config_bits.c
 * @brief Device configuration words, per docs/agent/hadi/proposals/C6a_sensor_io.md section 3.8
 *        (DS39881 Registers 24-1 CW1 and 24-2 CW2, from memory, page not re-read).
 *
 * UNVERIFIED: not compiled with XC16. Setting and value NAMES below are from memory of the XC16
 * `#pragma config` vocabulary for PIC24FJ64GA002: check each one against
 * <xc16>/docs/config_index.html (or MPLAB X: Window > Target Memory Views > Configuration Bits).
 * WORKING ASSUMPTION: C6a open questions 1 and 4 (ICSP set, oscillator), not decided.
 */

/* ---- CW1 ---- */
#pragma config JTAGEN = OFF        /* JTAGEN=0: JTAG port off, frees RB8/RB9 (pins 17/18) for I2C1 */
#pragma config GCP = OFF           /* GCP=1: general code protect off */
#pragma config GWRP = OFF          /* GWRP=1: general write protect off */
#pragma config BKBUG = OFF         /* DEBUG bit: background debugger disabled (MPLAB X may override at debug time) */
#pragma config COE = OFF           /* COE=1: no clip-on emulation mode */
#pragma config ICS = PGx1          /* ICS<1:0>=11: emulator/debugger on PGC1/PGD1 (pins 5/4); must match the programmer header */
#pragma config FWDTEN = OFF        /* FWDTEN=0: watchdog off (development) */
#pragma config WINDIS = OFF        /* WINDIS=1: watchdog non-window mode (irrelevant while FWDTEN = OFF) */
#pragma config FWPSA = PR128       /* WDT prescaler 1:128 (irrelevant while FWDTEN = OFF) */
#pragma config WDTPS = PS32768     /* WDT postscaler 1:32768 (irrelevant while FWDTEN = OFF) */

/* ---- CW2 ---- */
#pragma config IESO = OFF          /* IESO=0: no two-speed start-up */
#pragma config FNOSC = FRCPLL      /* FNOSC<2:0>=001: fast RC oscillator with 4x PLL = 32 MHz Fosc, FCY = 16 MHz */
#pragma config FCKSM = CSDCMD      /* FCKSM<1:0>=11: clock switching and fail-safe monitor disabled */
#pragma config OSCIOFNC = ON       /* OSCIOFNC=1: OSCO pin is digital I/O (RA3). Spec spells it OSCIOFCN and C6a 3.8 has the polarity inverted (review F2); RA3 is unused so ON/OFF is harmless */
#pragma config IOL1WAY = OFF       /* IOL1WAY=0: PPS may be unlocked more than once (development) */
#pragma config I2C1SEL = PRI       /* I2C1SEL=1: I2C1 on the default pins SCL1/SDA1 (RB8/RB9) */
#pragma config POSCMOD = NONE      /* POSCMD<1:0>=11: primary oscillator disabled (RA2/RA3 free); XC16 names the setting POSCMOD (review F1), check config_index.html */
// [END AI-GENERATED]
