// [AI-GENERATED: Claude Code]
/* probe.c - self-test of the sim16 harness: proves the sim16 build really has a 16-bit int
 * (so it can catch the bugs host builds miss) and that output and exit codes reach the runner. */
#include <stdint.h>
#include "sim16.h"

/**
 * Multiply two int16 values the WRONG way (no cast before the multiply). In a 16-bit-int build
 * the product is computed in 16 bits; volatile stops the compiler from folding it at compile time.
 *
 * @param a First factor.
 * @param b Second factor.
 * @return The product as computed in `int` width, widened afterwards.
 */
static int32_t mul_uncast(int16_t a, int16_t b)
{
    volatile int16_t va = a, vb = b;
    return (int32_t)(va * vb);  /* product has type int: 16 bits on AVR/XC16, 32 on host */
}

/**
 * Harness self-test entry point.
 *
 * @return 0 on the host; on AVR it never returns (sim16_exit stops the simulated CPU).
 */
int main(void)
{
    int16_t fail = 0;
    int32_t wrong, right;
    sim16_init();
    wrong = mul_uncast(300, 300);
    right = (int32_t)300 * (int32_t)300;
    printf("sizeof(int)=%u uncast300x300=%ld cast300x300=%ld\n",
           (unsigned)sizeof(int), (long)wrong, (long)right);
#ifdef __AVR__
    if (sizeof(int) != 2u) { printf("FAIL sim16 int is not 16-bit\n"); fail = 1; }
    if (wrong != 24464L) { printf("FAIL expected 16-bit wraparound\n"); fail = 1; }
#else
    if (wrong != 90000L) { printf("FAIL host int is not 32-bit\n"); fail = 1; }
#endif
    if (right != 90000L) { printf("FAIL cast product\n"); fail = 1; }
    printf(fail ? "FAIL probe\n" : "PASS probe\n");
    sim16_exit(fail);
    return 0;
}
// [END AI-GENERATED]
