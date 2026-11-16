// [AI-GENERATED: Claude Code]
/**
 * @file p24_mock.h
 * @brief Host stand-in for <xc.h> / p24FJ64GA002.h: ONLY for `make -C firmware/build check`
 *        (cc -fsyntax-only). It proves the HAL sources are syntactically and type-wise consistent
 *        with these declarations; it proves NOTHING about the real device header.
 *
 * UNVERIFIED: every register and bit-field name below is "from memory, UNVERIFIED" against
 * Microchip's p24FJ64GA002.h (XC16 v2.10). Diff each name against the real header on the Mac
 * (see firmware/hal/pic24/README.md checklist). Bit positions are NOT modelled: the structs
 * only carry the names, in no claimed order, so never use this file to decide a bit position.
 */
#ifndef P24_MOCK_H
#define P24_MOCK_H

#include <stdint.h>

#define P24_BIT(n) unsigned int n : 1

/* ---- oscillator ---- */
extern volatile unsigned int OSCCON;
extern volatile struct { unsigned int OSWEN : 1; unsigned int : 1; unsigned int LOCK : 1;
                         unsigned int IOLOCK : 1; unsigned int CF : 1; unsigned int : 1;
                         unsigned int LPOSCEN : 1; unsigned int : 1;
                         unsigned int NOSC : 3; unsigned int : 1; unsigned int COSC : 3; } OSCCONbits;
extern volatile unsigned int CLKDIV;
extern volatile struct { unsigned int RCDIV : 3; unsigned int DOZEN : 1; unsigned int DOZE : 3; } CLKDIVbits;
void __builtin_write_OSCCONL(unsigned int value); /* XC16 builtin: does the OSCCON unlock sequence */

/* ---- pins ---- */
extern volatile unsigned int AD1PCFG;
extern volatile struct { P24_BIT(TRISB4); P24_BIT(TRISB7); P24_BIT(TRISB8); P24_BIT(TRISB9); P24_BIT(TRISB12); P24_BIT(TRISB13);
                         P24_BIT(TRISB14); } TRISBbits;
extern volatile struct { P24_BIT(LATB4); P24_BIT(LATB8); P24_BIT(LATB13); } LATBbits;
extern volatile struct { P24_BIT(RB9); } PORTBbits;
void __builtin_nop(void);
extern volatile struct { unsigned int : 8; unsigned int INT1R : 5; } RPINR0bits;
extern volatile struct { unsigned int U1RXR : 5; } RPINR18bits;
extern volatile struct { unsigned int RP12R : 5; unsigned int : 3; unsigned int RP13R : 5; } RPOR6bits;

/* ---- Timer1 ---- */
extern volatile unsigned int T1CON;
extern volatile struct { unsigned int : 1; unsigned int TCS : 1; unsigned int TSYNC : 1; unsigned int : 1;
                         unsigned int TCKPS : 2; unsigned int TGATE : 1; unsigned int : 6;
                         unsigned int TSIDL : 1; unsigned int : 1; unsigned int TON : 1; } T1CONbits;
extern volatile unsigned int TMR1;
extern volatile unsigned int PR1;

/* ---- interrupt controller ---- */
extern volatile struct { P24_BIT(INT0EP); P24_BIT(INT1EP); } INTCON2bits;
extern volatile struct { unsigned int INT0IF : 1; unsigned int : 2; unsigned int T1IF : 1;
                         unsigned int U1TXIF : 1; } IFS0bits;
extern volatile struct { P24_BIT(INT1IF); } IFS1bits;
extern volatile struct { unsigned int INT0IE : 1; unsigned int : 2; unsigned int T1IE : 1;
                         unsigned int U1TXIE : 1; } IEC0bits;
extern volatile struct { P24_BIT(INT1IE); } IEC1bits;
extern volatile struct { unsigned int T1IP : 3; unsigned int INT0IP : 3; } IPC0bits;
extern volatile struct { unsigned int U1TXIP : 3; } IPC3bits;
extern volatile struct { unsigned int INT1IP : 3; } IPC5bits;

/* ---- UART1 ---- */
extern volatile unsigned int U1MODE;
extern volatile struct { unsigned int STSEL : 1; unsigned int PDSEL : 2; unsigned int BRGH : 1;
                         unsigned int : 3; unsigned int UARTEN : 1; } U1MODEbits;
extern volatile unsigned int U1STA;
extern volatile struct { unsigned int URXDA : 1; unsigned int OERR : 1; unsigned int FERR : 1;
                         unsigned int PERR : 1; unsigned int RIDLE : 1; unsigned int ADDEN : 1;
                         unsigned int URXISEL : 2; unsigned int TRMT : 1; unsigned int UTXBF : 1;
                         unsigned int UTXEN : 1; unsigned int UTXBRK : 1; unsigned int : 1;
                         unsigned int UTXISEL0 : 1; unsigned int UTXINV : 1;
                         unsigned int UTXISEL1 : 1; } U1STAbits;
extern volatile unsigned int U1BRG;
extern volatile unsigned int U1TXREG;

/* ---- I2C1 ---- */
extern volatile unsigned int I2C1CON;
extern volatile struct { P24_BIT(SEN); P24_BIT(RSEN); P24_BIT(PEN); P24_BIT(RCEN); P24_BIT(ACKEN);
                         P24_BIT(ACKDT); P24_BIT(STREN); P24_BIT(GCEN); P24_BIT(SMEN);
                         P24_BIT(DISSLW); P24_BIT(A10M); P24_BIT(IPMIEN); P24_BIT(SCLREL);
                         P24_BIT(I2CSIDL); P24_BIT(I2CEN); } I2C1CONbits;
extern volatile unsigned int I2C1STAT;
extern volatile struct { P24_BIT(TBF); P24_BIT(RBF); P24_BIT(R_W); P24_BIT(S); P24_BIT(P);
                         P24_BIT(D_A); P24_BIT(I2COV); P24_BIT(IWCOL); P24_BIT(ADD10);
                         P24_BIT(GCSTAT); P24_BIT(BCL); P24_BIT(TRSTAT); P24_BIT(ACKSTAT); } I2C1STATbits;
extern volatile unsigned int I2C1BRG;
extern volatile unsigned int I2C1TRN;
extern volatile unsigned int I2C1RCV;

#endif /* P24_MOCK_H */
// [END AI-GENERATED]
