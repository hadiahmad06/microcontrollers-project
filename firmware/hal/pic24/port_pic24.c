// [AI-GENERATED: Claude Code]
/**
 * @file port_pic24.c
 * @brief gesture_port.h on PIC24FJ64GA002: UART1 TX ring + ISR, INT0/INT1 flags, millisecond clock.
 *
 * UNVERIFIED: not compiled with XC16; register names from memory.
 * Sources (from memory, page not re-read): DS39881 UART chapter and FRM "UART" (U1MODE, U1STA,
 * U1BRG, UTXISEL, UTXBF), External Interrupts section (INTCON2<INTxEP>, IFSx, IECx, IPCx),
 * docs/agent/CONTRACTS.md C6.1 (115200 baud, BRGH = 1, U1BRG = 34), C6.2 (priorities), C1.4.
 *
 * TX ring concurrency (the "which and why" asked by spec H2): LOCK-FREE single-producer /
 * single-consumer index pair, no interrupt masking. The main loop is the only writer of s_head and
 * of ring bytes in the free region; the TX ISR is the only writer of s_tail. Both indices are
 * uint8_t (one-byte accesses are atomic on a 16-bit core) and each side only ever reads the OTHER
 * index, so a stale read is conservative: the producer may think there is less room than there is,
 * the consumer may think there is less data than there is; never the reverse. The producer stores
 * the data BEFORE it advances s_head. s_ring[] is NOT volatile, so volatile ordering alone does not
 * cover it: HAL_COMPILER_BARRIER() sits between the ring stores and the s_head store (producer) and
 * between the s_head test and the ring load (ISR). The PIC24 has no cache or write buffer, so a
 * compiler barrier is enough. One slot is kept empty to tell full from empty (127 usable bytes).
 * Wake-up and storm protection (review F4): U1TXIE stays 0 while the ring is empty. port_tx_write
 * publishes s_head, then sets U1TXIE = 1 and U1TXIF = 1. When the ISR empties the ring it clears
 * U1TXIE, then re-tests head != tail and re-enables if a byte was published meanwhile (no lost
 * wake-up). Why: if U1TXIF were level-style (set whenever the buffer has room) an always-enabled
 * ISR at priority 6 would spin on an empty ring and starve the main loop; with IE off it cannot.
 *
 * The RX side of UART1 is enabled (UARTEN) but not serviced: the recording firmware does not
 * receive. C6.1's RX ISR is NOT implemented here (open item for the demo firmware).
 */
#include <stdbool.h>
#include <stdint.h>

#include "board.h"
#include "gesture_port.h"
#include "p24_regs.h"

/** TX ring size in bytes; must be a power of two <= 256. */
#define PORT_TX_SIZE 128U
#define PORT_TX_MASK (PORT_TX_SIZE - 1U)

static uint8_t s_ring[PORT_TX_SIZE];   /* TX ring storage (128 B, C7 "UART rings") */
static volatile uint8_t s_head;        /* next slot the producer fills; written by main only */
static volatile uint8_t s_tail;        /* next slot the consumer sends; written by U1TX ISR only */
static volatile uint8_t s_fifo_flag;   /* set by INT0 ISR, cleared by port_take_fifo_flag */
static volatile uint8_t s_click_flag;  /* set by INT1 ISR, cleared by port_take_click_flag */

/** UART1 TX interrupt (priority 6): moves bytes from the ring to U1TXREG while the TX buffer has room. */
HAL_ISR(_U1TXInterrupt)
{
    uint8_t t;
    IFS0bits.U1TXIF = 0;               /* U1TXIF = 0: acknowledge; cleared first so a later move re-raises it */
    t = s_tail;
    while ((t != s_head) && (U1STAbits.UTXBF == 0U)) {  /* UTXBF = 0: TX buffer has room */
        HAL_COMPILER_BARRIER();        /* s_head test before the ring load */
        U1TXREG = (unsigned int)s_ring[t];
        t = (uint8_t)((t + 1U) & PORT_TX_MASK);
    }
    s_tail = t;
    if (t == s_head) {                 /* ring empty: stop the interrupt until port_tx_write publishes more */
        IEC0bits.U1TXIE = 0;           /* U1TXIE = 0: TX interrupt off (no storm on an empty ring) */
        HAL_COMPILER_BARRIER();
        if (t != s_head) {             /* a byte was published meanwhile: do not lose the wake-up */
            IEC0bits.U1TXIE = 1;       /* U1TXIE = 1: back on */
        }
    }
}

/** INT0 interrupt (priority 5): LIS3DH INT1 rising edge. Only sets a flag. */
HAL_ISR(_INT0Interrupt)
{
    IFS0bits.INT0IF = 0;               /* INT0IF = 0: acknowledge */
    s_fifo_flag = 1U;
}

/** INT1 interrupt (priority 4): LIS3DH INT2 rising edge. Only sets a flag. */
HAL_ISR(_INT1Interrupt)
{
    IFS1bits.INT1IF = 0;               /* INT1IF = 0: acknowledge */
    s_click_flag = 1U;
}

void port_pic24_init(void)
{
    /* ---- UART1: 115200 8N1, BRGH = 1, U1BRG = 34 (C6.1; 16 MIPS: 16e6/(4*115200)-1 = 33.7 -> 34) ---- */
    U1MODE = 0;                        /* UARTEN=0 while configuring; all other fields 0 */
    U1MODEbits.BRGH = 1;               /* BRGH = 1: high-speed mode, baud = FCY / (4 * (U1BRG + 1)) */
    U1MODEbits.PDSEL = 0;              /* PDSEL<1:0> = 00: 8 data bits, no parity */
    U1MODEbits.STSEL = 0;              /* STSEL = 0: one stop bit */
    U1BRG = 34;                        /* U1BRG = 34: 16e6 / (4 * 35) = 114286 baud (-0.79 %) */
    U1STA = 0;                         /* clear errors and select fields */
    U1STAbits.UTXISEL1 = 0;            /* UTXISEL<1:0> = 00: TX interrupt when a char moves to the shift reg */
    U1STAbits.UTXISEL0 = 0;            /*   (i.e. when the buffer has room); see ISR */
    U1MODEbits.UARTEN = 1;             /* UARTEN = 1: UART module on (RX enabled, not serviced) */
    U1STAbits.UTXEN = 1;               /* UTXEN = 1: transmitter on (sets U1TXIF; cleared below) */
    IPC3bits.U1TXIP = 6;               /* U1TXIP<2:0> = 6: TX interrupt priority 6 (spec H2; C6.2 nothing at 7) */
    IFS0bits.U1TXIF = 0;               /* U1TXIF = 0: drop the flag raised by UTXEN */
    IEC0bits.U1TXIE = 0;               /* U1TXIE = 0: stays off until port_tx_write publishes bytes (review F4) */

    /* ---- INT0 (RB7): rising edge, priority 5 ---- */
    INTCON2bits.INT0EP = 0;            /* INT0EP = 0: interrupt on rising edge (LIS3DH is active high) */
    IPC0bits.INT0IP = 5;               /* INT0IP<2:0> = 5: FIFO watermark interrupt priority 5 (C6.2) */
    IFS0bits.INT0IF = 0;               /* INT0IF = 0: no stale flag */
    IEC0bits.INT0IE = 1;               /* INT0IE = 1: enabled */

    /* ---- INT1 (RB12 via PPS): rising edge, priority 4 ---- */
    INTCON2bits.INT1EP = 0;            /* INT1EP = 0: interrupt on rising edge */
    IPC5bits.INT1IP = 4;               /* INT1IP<2:0> = 4: click interrupt priority 4 (C6.2) */
    IFS1bits.INT1IF = 0;               /* INT1IF = 0: no stale flag */
    IEC1bits.INT1IE = 0;               /* INT1IE = 0: disabled. The LIS3DH breakout has no INT2, RB12 floats
                                          (CONTRACTS C6.1, overruled 2026-11-18; TODO T-1) */
    /* A pin already high at enable time gives no edge; gesture_poll's 50 ms drain timer covers the FIFO. */
}

uint8_t port_tx_room(void)
{
    /* Producer-side view: s_tail only advances, so this never over-reports room. */
    return (uint8_t)((s_tail - s_head - 1U) & PORT_TX_MASK);
}

void port_tx_write(const uint8_t *p, uint8_t n)
{
    uint8_t h = s_head;
    uint8_t i;
    for (i = 0U; i < n; i++) {
        s_ring[h] = p[i];
        h = (uint8_t)((h + 1U) & PORT_TX_MASK);
    }
    HAL_COMPILER_BARRIER();            /* ring stores must not sink below the s_head store */
    s_head = h;                        /* publish AFTER the data is stored (single-byte write, atomic) */
    if (n != 0U) {
        IEC0bits.U1TXIE = 1;           /* U1TXIE = 1: allow the TX ISR */
        IFS0bits.U1TXIF = 1;           /* U1TXIF = 1: software-trigger the TX ISR so it picks the bytes up */
    }
}

uint16_t port_millis(void)
{
    return board_millis();
}

bool port_take_fifo_flag(void)
{
    uint8_t f;
    IEC0bits.INT0IE = 0;               /* INT0IE = 0: hold the ISR off for the two-statement read-and-clear */
    f = s_fifo_flag;
    s_fifo_flag = 0U;
    IEC0bits.INT0IE = 1;               /* INT0IE = 1: an edge seen meanwhile fires now (IF stays latched) */
    return f != 0U;
}

bool port_take_click_flag(void)
{
    uint8_t f;
    uint8_t ie = (uint8_t)IEC1bits.INT1IE;   /* previous enable state (0 while INT2 is not wired, TODO T-1) */
    IEC1bits.INT1IE = 0;               /* INT1IE = 0: hold the ISR off for the read-and-clear */
    f = s_click_flag;
    s_click_flag = 0U;
    IEC1bits.INT1IE = ie;              /* INT1IE: restore the previous state (review B7-1R F1: never force it on) */
    return f != 0U;
}
// [END AI-GENERATED]
