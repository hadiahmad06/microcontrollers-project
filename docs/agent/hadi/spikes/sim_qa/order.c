// [AI-GENERATED: Claude Code]
/* order.c - QA program: hits breakpoints in the WRONG order (start, start, start; sim_end/sim_done
 * never reached). run_sim.sh only counts "Simulator halted" lines, so it may accept this. */
#include <stdint.h>

volatile uint16_t result_done = 1;
volatile uint16_t stale_value = 1234;

/** Marker: start. */
void __attribute__((noinline)) sim_start(void) { __asm__ volatile("nop"); }
/** Marker: end (never reached). */
void __attribute__((noinline)) sim_end(void)   { __asm__ volatile("nop"); }
/** Marker: done (never reached). */
void __attribute__((noinline)) sim_done(void)  { __asm__ volatile("nop"); }

/** Entry: hits sim_start three times, then spins. */
int main(void)
{
    sim_start();
    sim_start();
    sim_start();
    stale_value = 9999;
    for (;;) { }
    return 0;
}
// [END AI-GENERATED]
