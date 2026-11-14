// [AI-GENERATED: Claude Code]
#include <stdio.h>
#include <stdint.h>

/**
 * Exhaustively prove (|s|*34953)>>19 with sign restore equals C's s/15 for
 * every possible segment sum s in [-30720, 30705].
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
    return 0;
}
// [END AI-GENERATED]
