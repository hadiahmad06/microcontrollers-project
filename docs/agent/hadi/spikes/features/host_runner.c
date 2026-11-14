// [AI-GENERATED: Claude Code]
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include "features.h"

/**
 * Host test runner: read raw windows (little-endian int16, 450 values each,
 * sample-major) from a file and write 60 int16 features per window.
 *
 * @param argc Argument count (must be 3).
 * @param argv argv[1] = input windows file, argv[2] = output features file.
 * @return     0 on success, 1 on usage/IO error.
 */
int main(int argc, char **argv)
{
    if (argc != 3) {
        fprintf(stderr, "usage: %s windows.bin features.bin\n", argv[0]);
        return 1;
    }
    FILE *in = fopen(argv[1], "rb");
    FILE *out = fopen(argv[2], "wb");
    if (!in || !out) {
        perror("fopen");
        return 1;
    }
    static int16_t win[FEAT_WINDOW_LEN][FEAT_AXES];
    int16_t feat[FEAT_COUNT];
    while (fread(win, sizeof(win), 1, in) == 1) {
        features_extract(win, feat);
        if (fwrite(feat, sizeof(feat), 1, out) != 1) {
            perror("fwrite");
            return 1;
        }
    }
    fclose(in);
    fclose(out);
    return 0;
}
// [END AI-GENERATED]
