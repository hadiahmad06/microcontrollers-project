// [AI-GENERATED: Claude Code]
#include "sim16.h"
#include <stdlib.h>

#ifdef __AVR__
#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/sleep.h>

/**
 * stdio put-char hook: busy-waits for the USART0 data register to be empty, then sends c.
 * (Busy-waiting is fine here: this is test-only code, never product library code.)
 *
 * @param c Character to send.
 * @param f Stream (unused).
 * @return 0 (always succeeds).
 */
static int sim16_putc(char c, FILE *f)
{
    (void)f;
    while ((UCSR0A & (1u << UDRE0)) == 0u) {
        /* UCSR0A bit UDRE0 = 1: transmit data register empty */
    }
    UDR0 = (uint8_t)c;   /* USART0 data register: writing starts transmission */
    return 0;
}

static FILE sim16_out = FDEV_SETUP_STREAM(sim16_putc, NULL, _FDEV_SETUP_WRITE);

void sim16_init(void)
{
    stdout = &sim16_out;
}

void sim16_exit(int16_t code)
{
    printf("SIM16_EXIT %d\n", (int)code);
    cli();          /* SREG.I = 0: no interrupt can wake the CPU */
    sleep_cpu();    /* simavr stops when the core sleeps with interrupts off */
    for (;;) {
    }
}
#else
void sim16_init(void)
{
}

void sim16_exit(int16_t code)
{
    printf("SIM16_EXIT %d\n", (int)code);
    fflush(stdout);
    exit(code == 0 ? 0 : 1);
}
#endif
// [END AI-GENERATED]
