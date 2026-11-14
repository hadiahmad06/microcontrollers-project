// [AI-GENERATED: Claude Code]
#include <stdio.h>
#include <stdint.h>
#include "features.h"

/**
 * Exhaustively prove (a) (|s|*34953)>>19 with sign restore equals C's s/15 for every
 * possible segment sum s in [-30720, 30705], and (b) features_isqrt32 is exact floor(sqrt)
 * for every n in 0..2^27 and the top 100001 uint32 values.
 *
 * @param void No arguments.
 * @return     0 if all sums agree, 1 on the first mismatch.
 */
int main(void)
{
    int32_t s;
    for (s = -30720; s <= 30705; s++) {
        int32_t a = s < 0 ? -s : s;
        int32_t q = (int32_t)(((uint32_t)a * 34953u) >> 19);
        if (s < 0) q = -q;
        if (q != s / 15) {
            printf("DIV15 MISMATCH s=%ld mulshift=%ld div=%ld\n", (long)s, (long)q, (long)(s / 15));
            return 1;
        }
    }
    printf("DIV15 PASS %ld sums\n", (long)(30705 + 30720 + 1));
    /* isqrt: r*r <= n < (r+1)^2 for EVERY n in 0..2^27 (covers max SS 62,604,360) plus the
       top of the uint32 range. */
    uint32_t n;
    for (n = 0; n <= (1u << 27); n++) {
        uint64_t r = features_isqrt32(n);
        if (r * r > n || (r + 1) * (r + 1) <= n) {
            printf("ISQRT MISMATCH n=%lu r=%lu\n", (unsigned long)n, (unsigned long)r);
            return 1;
        }
    }
    for (n = 0xFFFFFFFFu - 100000u; n != 0u; n++) {
        uint64_t r = features_isqrt32(n);
        if (r * r > n || (r + 1) * (r + 1) <= n) {
            printf("ISQRT MISMATCH n=%lu\n", (unsigned long)n);
            return 1;
        }
    }
    printf("ISQRT PASS 0..2^27 and top 100001 of uint32\n");
    return 0;
}
// [END AI-GENERATED]
