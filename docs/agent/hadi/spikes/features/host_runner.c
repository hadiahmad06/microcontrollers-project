// [AI-GENERATED: Claude Code]
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include "features.h"

/**
 * Host test runner: read raw windows (little-endian int16, 450 values each,
 * sample-major) from a file and write 60 int16 features per window. The whole
 * input is validated (non-empty, whole number of windows, no read error)
 * before the output file is created.
 *
 * @param argc Argument count (must be 3).
 * @param argv argv[1] = input windows file, argv[2] = output features file.
 * @return     0 on success, 1 on usage/IO/validation error.
 */
int main(int argc, char **argv)
{
    if (argc != 3) {
        fprintf(stderr, "usage: %s windows.bin features.bin\n", argv[0]);
        return 1;
    }
    FILE *in = fopen(argv[1], "rb");
    if (!in) {
        perror("fopen input");
        return 1;
    }
    if (fseek(in, 0, SEEK_END) != 0) {
        perror("fseek");
        return 1;
    }
    long size = ftell(in);
    rewind(in);
    long wbytes = (long)sizeof(int16_t) * FEAT_WINDOW_LEN * FEAT_AXES;
    if (size <= 0 || size % wbytes != 0) {
        fprintf(stderr, "input size %ld is empty or not a multiple of %ld bytes\n", size, wbytes);
        return 1;
    }
    FILE *out = fopen(argv[2], "wb");
    if (!out) {
        perror("fopen output");
        return 1;
    }
    static int16_t win[FEAT_WINDOW_LEN][FEAT_AXES];
    int16_t feat[FEAT_COUNT];
    long n = 0;
    while (fread(win, sizeof(win), 1, in) == 1) {
        features_extract(win, feat);
        if (fwrite(feat, sizeof(feat), 1, out) != 1) {
            perror("fwrite");
            return 1;
        }
        n++;
    }
    if (ferror(in) || !feof(in) || n != size / wbytes) {
        fprintf(stderr, "read error or short read after %ld windows\n", n);
        return 1;
    }
    if (fclose(in) != 0 || fclose(out) != 0) {
        perror("fclose");
        return 1;
    }
    return 0;
}
// [END AI-GENERATED]
