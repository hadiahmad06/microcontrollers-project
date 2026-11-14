// [AI-GENERATED: Claude Code]
/* demo.c - MDB simulator spike program for PIC24FJ64GA002.
 * Computes a 32-bit checksum and an int32 dot product of int16 arrays whose
 * intermediate values overflow a 16-bit int if computed naively.
 * Results land in globals read back by run_sim.sh. */
#include <stdint.h>

#define N 64

int16_t  A[N];
int16_t  B[N];
volatile uint32_t result_checksum;
volatile int32_t  result_dot;
volatile uint16_t result_done;

/** Marker: simulator breakpoint here starts the cycle measurement. */
void __attribute__((noinline)) sim_start(void) { __asm__ volatile("nop"); }
/** Marker: simulator breakpoint here stops the cycle measurement. */
void __attribute__((noinline)) sim_end(void)   { __asm__ volatile("nop"); }
/** Marker: breakpoint here means the program finished; globals are valid. */
void __attribute__((noinline)) sim_done(void)  { __asm__ volatile("nop"); }

/**
 * Fill A and B with deterministic int16 values (LCG-like, large magnitude).
 * Args: none. Return: none.
 */
static void init_data(void)
{
    uint16_t i;
    for (i = 0; i < N; i++) {
        A[i] = (int16_t)(i * 1000u + 12345u - (i * 7u));  /* wraps through int16 */
        B[i] = (int16_t)(30000 - (int16_t)(i * 997u));
    }
}

/**
 * 32-bit checksum of an int16 array: sum of (uint16)x * (i+1), mod 2^32.
 * Args: a - array, n - element count. Return: checksum (uint32_t).
 */
static uint32_t checksum32(const int16_t *a, uint16_t n)
{
    uint32_t s = 0;
    uint16_t i;
    for (i = 0; i < n; i++)
        s += (uint32_t)(uint16_t)a[i] * (uint32_t)(i + 1u);
    return s;
}

/**
 * Dot product of two int16 arrays accumulated in int32 (each product is
 * widened first so it does not overflow 16-bit int).
 * Args: a, b - arrays, n - count. Return: sum as int32_t.
 */
static int32_t dot32(const int16_t *a, const int16_t *b, uint16_t n)
{
    int32_t s = 0;
    uint16_t i;
    for (i = 0; i < n; i++)
        s += (int32_t)a[i] * (int32_t)b[i];
    return s;
}

/** Entry point: runs the measured region once, then parks at sim_done(). */
int main(void)
{
    init_data();
    sim_start();
    result_checksum = checksum32(A, N);
    result_dot = dot32(A, B, N);
    sim_end();
    result_done = 1;
    sim_done();
    for (;;) { }
    return 0;
}
// [END AI-GENERATED]
