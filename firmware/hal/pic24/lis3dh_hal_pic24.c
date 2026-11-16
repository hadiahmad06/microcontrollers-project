// [AI-GENERATED: Claude Code]
/**
 * @file lis3dh_hal_pic24.c
 * @brief lis3dh_hal.h on I2C1, 400 kHz master, polled, every wait bounded.
 *
 * UNVERIFIED: not compiled with XC16; register names from memory.
 * Sources (from memory, page not re-read): DS39881 I2C chapter and FRM "Inter-Integrated Circuit
 * (I2C)": I2C1CON (I2CEN, SEN, RSEN, PEN, RCEN, ACKEN, ACKDT, DISSLW), I2C1STAT (TBF, RBF, TRSTAT,
 * ACKSTAT, BCL, IWCOL, I2COV), I2C1BRG = FCY/FSCL - FCY/1e7 - 1 -> 38 for 394 kHz (C6.1; C6a 3.x).
 * LIS3DH protocol: DocID17530 section 5.1 (sub-address with bit 7 = auto-increment, repeated start).
 *
 * Called from the main loop only. Returns 0 on success, -1 on a bounded-wait timeout or bus
 * collision (the module is then reset), -2 on a NACK (STOP is still sent).
 */
#include <stdint.h>

#include "board.h"
#include "lis3dh_hal.h"
#include "p24_regs.h"

/** Maximum polling iterations per wait. One I2C byte at 400 kHz is ~25 us (~400 FCY); at about 8-12 FCY per
 *  iteration this bound is about 10-15 ms, far above any legal clock-stretch of the LIS3DH. A dead bus
 *  therefore stalls the main loop 10+ ms per failed call (gesture_init probing two addresses: ~60 ms). */
#define I2C_SPIN_MAX 20000U

/** Evaluate `cond` until true or the bound is hit; on timeout recover the bus and return -1. */
#define I2C_WAIT(cond)                                  \
    do {                                                \
        uint16_t spin_ = I2C_SPIN_MAX;                  \
        while (!(cond)) {                               \
            if (spin_ == 0U) {                          \
                i2c_reset();                            \
                return -1;                              \
            }                                           \
            spin_--;                                    \
        }                                               \
    } while (0)

/** Bus-idle condition: no start/restart/stop/receive/ack sequence running (I2C1CON<4:0> == 0). */
#define I2C_SEQ_IDLE()                                                                 \
    ((I2C1CONbits.SEN == 0U) && (I2C1CONbits.RSEN == 0U) && (I2C1CONbits.PEN == 0U) && \
     (I2C1CONbits.RCEN == 0U) && (I2C1CONbits.ACKEN == 0U))

/** Transmit finished: buffer empty and shifter idle. */
#define I2C_TX_DONE() ((I2C1STATbits.TBF == 0U) && (I2C1STATbits.TRSTAT == 0U))

/** Short bounded delay of roughly 5 us at 16 MIPS (half an SCL period for the recovery pulses). */
static void i2c_delay(void)
{
    uint8_t k;
    for (k = 0U; k < 20U; k++) {
        __builtin_nop();
    }
}

/**
 * Free a slave that holds SDA low (e.g. after an MCU reset mid-byte, review F7): with I2C1 OFF the pins
 * are plain GPIO; clock SCL up to 9 times until SDA reads high. SCL is driven low or released
 * (open-drain style through TRISB, external pull-up), never driven high. Bounded: 9 pulses.
 */
static void i2c_bus_recover(void)
{
    uint8_t n;
    LATBbits.LATB8 = 0;                /* LATB8 = 0: when TRISB8 = 0, SCL is driven low */
    TRISBbits.TRISB9 = 1;              /* TRISB9 = 1: SDA input, read through PORTB */
    TRISBbits.TRISB8 = 1;              /* TRISB8 = 1: SCL released (pulled high externally) */
    for (n = 0U; (n < 9U) && (PORTBbits.RB9 == 0U); n++) {
        TRISBbits.TRISB8 = 0;          /* TRISB8 = 0: pull SCL low */
        i2c_delay();
        TRISBbits.TRISB8 = 1;          /* TRISB8 = 1: release SCL high */
        i2c_delay();
    }
}

/** Reset the module after a timeout/collision so the next transfer starts clean. */
static void i2c_reset(void)
{
    I2C1CONbits.I2CEN = 0;             /* I2CEN = 0: module off, releases SCL/SDA, clears the state machine */
    i2c_bus_recover();                 /* free a stuck slave while the pins are GPIO */
    I2C1STAT = 0;                      /* clear BCL, IWCOL, I2COV and status flags */
    I2C1CONbits.I2CEN = 1;             /* I2CEN = 1: module back on */
}

void lis3dh_hal_pic24_init(void)
{
    I2C1CON = 0;                       /* I2CEN=0 (pins are GPIO for the recovery below); 7-bit address (A10M=0); all sequences idle */
    I2C1BRG = 38;                      /* I2C1BRG = 38: FSCL = FCY / (38 + 1 + FCY/1e7) ~ 394 kHz at 16 MHz */
    I2C1CONbits.DISSLW = 0;            /* DISSLW = 0: slew-rate control ON (required at 400 kHz) */
    I2C1STAT = 0;                      /* clear flags */
    i2c_bus_recover();                 /* SDA stuck after a reflash? clock it free before enabling I2C1 */
    I2C1CONbits.I2CEN = 1;             /* I2CEN = 1: enable the module; SCL1/SDA1 become open-drain I2C pins */
}

/** Issue a STOP and wait for it (bounded). @return 0, or -1 on timeout. */
static int8_t i2c_stop(void)
{
    I2C1CONbits.PEN = 1;               /* PEN = 1: generate a STOP condition */
    I2C_WAIT(I2C_SEQ_IDLE());
    return 0;
}

/** Send one byte and report the slave ACK. @return 0 ACK, -2 NACK, -1 timeout/collision. */
static int8_t i2c_send(uint8_t b)
{
    I2C1TRN = (unsigned int)b;         /* write transmit register: starts the 8-bit shift-out */
    if (I2C1STATbits.IWCOL != 0U) {    /* IWCOL = 1: wrote while a transfer was in progress */
        i2c_reset();
        return -1;
    }
    I2C_WAIT(I2C_TX_DONE());
    if (I2C1STATbits.BCL != 0U) {      /* BCL = 1: bus collision */
        i2c_reset();
        return -1;
    }
    if (I2C1STATbits.ACKSTAT != 0U) {  /* ACKSTAT = 1: slave did not acknowledge */
        return -2;
    }
    return 0;
}

int8_t lis3dh_hal_write(uint8_t addr7, uint8_t reg, uint8_t val)
{
    int8_t rc;

    I2C_WAIT(I2C_SEQ_IDLE());
    I2C1CONbits.SEN = 1;               /* SEN = 1: generate a START condition */
    I2C_WAIT(I2C_SEQ_IDLE());

    rc = i2c_send((uint8_t)(addr7 << 1)); /* address byte, R/W = 0 (write) */
    if (rc == 0) { rc = i2c_send(reg); }  /* register sub-address */
    if (rc == 0) { rc = i2c_send(val); }  /* data byte */
    if (rc == -1) {
        return -1;                     /* module already reset */
    }
    if (i2c_stop() < 0) {
        return -1;
    }
    return rc;                         /* 0 or -2 (NACK, after the STOP) */
}

int8_t lis3dh_hal_read(uint8_t addr7, uint8_t reg, uint8_t *buf, uint8_t n)
{
    int8_t rc;
    uint8_t i;

    if ((n == 0U) || (buf == (uint8_t *)0)) {
        return -1;
    }

    I2C_WAIT(I2C_SEQ_IDLE());
    I2C1CONbits.SEN = 1;               /* SEN = 1: START */
    I2C_WAIT(I2C_SEQ_IDLE());

    rc = i2c_send((uint8_t)(addr7 << 1)); /* address, R/W = 0: select the register */
    if (rc == 0) { rc = i2c_send(reg); }  /* sub-address (caller sets bit 7 for auto-increment) */
    if (rc == -1) {
        return -1;
    }
    if (rc == -2) {
        return (i2c_stop() < 0) ? (int8_t)-1 : (int8_t)-2;
    }

    I2C1CONbits.RSEN = 1;              /* RSEN = 1: repeated START */
    I2C_WAIT(I2C_SEQ_IDLE());
    rc = i2c_send((uint8_t)((addr7 << 1) | 1U)); /* address, R/W = 1 (read) */
    if (rc == -1) {
        return -1;
    }
    if (rc == -2) {
        return (i2c_stop() < 0) ? (int8_t)-1 : (int8_t)-2;
    }

    for (i = 0U; i < n; i++) {
        I2C1CONbits.RCEN = 1;          /* RCEN = 1: receive one byte (clears itself when the byte is in) */
        I2C_WAIT((I2C1CONbits.RCEN == 0U) && (I2C1STATbits.RBF != 0U));
        buf[i] = (uint8_t)I2C1RCV;     /* reading I2C1RCV clears RBF */
        if (I2C1STATbits.I2COV != 0U) {
            I2C1STATbits.I2COV = 0;    /* I2COV = 0: clear receive overflow (software-cleared) */
        }
        if (i + 1U < n) {
            I2C1CONbits.ACKDT = 0;     /* ACKDT = 0: send ACK (more bytes wanted) */
        } else {
            I2C1CONbits.ACKDT = 1;     /* ACKDT = 1: send NACK on the last byte */
        }
        I2C1CONbits.ACKEN = 1;         /* ACKEN = 1: transmit the ACK/NACK bit now */
        I2C_WAIT(I2C_SEQ_IDLE());
    }

    if (i2c_stop() < 0) {
        return -1;
    }
    return 0;
}
// [END AI-GENERATED]
