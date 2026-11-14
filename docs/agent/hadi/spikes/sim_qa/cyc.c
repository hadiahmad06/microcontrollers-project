// [AI-GENERATED: Claude Code]
/* cyc.c - QA program: regions of known cycle cost. Select with -DREGION=n.
 * Measured by sim/run_sim.sh between sim_start() and sim_end(). */
#include <stdint.h>

volatile uint16_t result_done;

/** Marker: breakpoint here starts the measurement. */
void __attribute__((noinline)) sim_start(void) { __asm__ volatile("nop"); }
/** Marker: breakpoint here stops the measurement. */
void __attribute__((noinline)) sim_end(void)   { __asm__ volatile("nop"); }
/** Marker: breakpoint here means the program finished. */
void __attribute__((noinline)) sim_done(void)  { __asm__ volatile("nop"); }

/** Empty callee used by region 7 (call + return cost). */
void __attribute__((noinline)) callee(void) { __asm__ volatile(""); }

#define NOP10 __asm__ volatile("nop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop\nnop")

/** Entry: runs the region chosen by REGION, then parks at sim_done(). */
int main(void)
{
    sim_start();
#if REGION == 0
    /* empty baseline */
#elif REGION == 1
    NOP10; NOP10; NOP10; NOP10; NOP10; NOP10; NOP10; NOP10; NOP10; NOP10; /* 100 nop */
#elif REGION == 2
    __asm__ volatile("repeat #99\n nop");            /* nop executed 100x */
#elif REGION == 3
    __asm__ volatile("bra 1f\n1: bra 2f\n2: bra 3f\n3: bra 4f\n4: bra 5f\n5: bra 6f\n6: bra 7f\n7: bra 8f\n8: bra 9f\n9: bra 10f\n10:"); /* 10 taken bra */
#elif REGION == 4
    __asm__ volatile("mov #1,w0\n cp0 w0\n"          /* Z=0 */
        "bra z,1f\nbra z,1f\nbra z,1f\nbra z,1f\nbra z,1f\n"
        "bra z,1f\nbra z,1f\nbra z,1f\nbra z,1f\nbra z,1f\n1:" : : : "w0","cc"); /* 10 not-taken, +2 setup */
#elif REGION == 5
    __asm__ volatile("mov #300,w0\n mov #300,w1\n"
        "mul.uu w0,w1,w2\nmul.uu w0,w1,w2\nmul.uu w0,w1,w2\nmul.uu w0,w1,w2\nmul.uu w0,w1,w2\n"
        "mul.uu w0,w1,w2\nmul.uu w0,w1,w2\nmul.uu w0,w1,w2\nmul.uu w0,w1,w2\nmul.uu w0,w1,w2"
        : : : "w0","w1","w2","w3"); /* 2 mov + 10 mul = 12 */
#elif REGION == 6
    __asm__ volatile("mov #1000,w0\n mov #7,w1\n repeat #17\n div.s w0,w1" : : : "w0","w1","cc"); /* 2 + 1 + 18 */
#elif REGION == 7
    callee();                                         /* call + return */
#endif
    sim_end();
    result_done = 1;
    sim_done();
    for (;;) { }
    return 0;
}
// [END AI-GENERATED]
