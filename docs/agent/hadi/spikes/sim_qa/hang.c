// [AI-GENERATED: Claude Code]
/* hang.c - QA program: never reaches sim_end/sim_done (tests runner failure paths). */
#include <stdint.h>

volatile uint16_t result_done = 1;

/** Marker: breakpoint here starts the measurement. */
void __attribute__((noinline)) sim_start(void) { __asm__ volatile("nop"); }
/** Marker: end (never reached). */
void __attribute__((noinline)) sim_end(void)   { __asm__ volatile("nop"); }
/** Marker: done (never reached). */
void __attribute__((noinline)) sim_done(void)  { __asm__ volatile("nop"); }

/** Entry: reaches sim_start then spins forever. */
int main(void)
{
    sim_start();
    for (;;) { }
    return 0;
}
// [END AI-GENERATED]
