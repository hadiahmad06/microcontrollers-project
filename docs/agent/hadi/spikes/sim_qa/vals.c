// [AI-GENERATED: Claude Code]
/* vals.c - QA program: value formatting/sign, 16-bit int promotion bug, arrays. */
#include <stdint.h>

volatile int16_t  v_i16_neg = -12345;
volatile int16_t  v_i16_min = -32768;
volatile int32_t  v_i32_neg = -2000000000L;
volatile int32_t  v_i32_min = (-2147483647L - 1);
volatile uint32_t v_u32_max = 0xFFFFFFFFUL;
volatile uint32_t v_u32_big = 3000000000UL;
volatile uint16_t v_u16_max = 65535;
volatile int8_t   v_i8_neg  = -5;
volatile int16_t  in_a = 300, in_b = 300;
volatile int32_t  r_nocast;   /* a*b without cast: 16-bit multiply, then widened */
volatile int32_t  r_cast;     /* (int32_t)a*b: correct */
volatile uint16_t result_done;

#define NF 60
int16_t feat[NF];             /* feature-vector-like array, mixed signs */

/** Marker: breakpoint here starts the measurement. */
void __attribute__((noinline)) sim_start(void) { __asm__ volatile("nop"); }
/** Marker: breakpoint here stops the measurement. */
void __attribute__((noinline)) sim_end(void)   { __asm__ volatile("nop"); }
/** Marker: breakpoint here means the program finished. */
void __attribute__((noinline)) sim_done(void)  { __asm__ volatile("nop"); }

/** Entry: fills values, parks at sim_done(). */
int main(void)
{
    uint16_t i;
    int16_t a, b;
    for (i = 0; i < NF; i++)
        feat[i] = (int16_t)((int16_t)i * 1111 - 30000);   /* -30000 .. +35549 wraps */
    sim_start();
    a = in_a; b = in_b;
    r_nocast = a * b;                 /* BUG CLASS: int is 16-bit on PIC24 */
    r_cast   = (int32_t)a * b;
    sim_end();
    result_done = 1;
    sim_done();
    for (;;) { }
    return 0;
}
// [END AI-GENERATED]
