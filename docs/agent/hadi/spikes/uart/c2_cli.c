// [AI-GENERATED: Claude Code]
/*
 * c2_cli.c - host test driver for c2_frame (not firmware; uses stdio on purpose).
 *   c2_cli crc <string>   prints the CRC-16/IBM-3740 of the string as 4 hex digits; also
 *                         checks that a split update (two halves) gives the same value.
 *   c2_cli encode         reads text records on stdin, writes the binary frames to stdout.
 * Record formats (decimal integers, whitespace separated):
 *   W seq window_id trig_idx overruns model_hash flags class_id conf events  (450 sample values)
 *   H seq proto odr range n_samples pre_trig feature_ver model_hash
 */
#include <stdio.h>
#include <string.h>
#include "c2_frame.h"

/**
 * Read one signed decimal from stdin.
 * @param v destination
 * @return 1 on success, 0 on EOF or parse failure
 */
static int rd(long *v)
{
    return scanf("%ld", v) == 1;
}

/**
 * Encode all records from stdin to stdout.
 * @return 0 on success, 1 on a malformed record or write failure
 */
static int do_encode(void)
{
    static uint8_t out[C2_WINDOW_FRAME_LEN];
    static int16_t samples[C2_N_SAMPLES][C2_N_AXES];
    char tag[4];

    while (scanf("%3s", tag) == 1) {
        long v[9];
        uint16_t n = 0u;
        unsigned i;
        if (tag[0] == 'W') {
            c2_window_meta_t m;
            unsigned k;
            for (i = 0u; i < 9u; i++) { if (!rd(&v[i])) { return 1; } }
            m.window_id  = (uint16_t)v[1];
            m.trig_idx   = (uint8_t)v[2];
            m.overruns   = (uint16_t)v[3];
            m.model_hash = (uint32_t)v[4];
            m.flags      = (uint8_t)v[5];
            m.class_id   = (int8_t)v[6];
            m.conf       = (uint8_t)v[7];
            m.events     = (uint8_t)v[8];
            for (i = 0u; i < C2_N_SAMPLES; i++) {
                for (k = 0u; k < C2_N_AXES; k++) {
                    long s;
                    if (!rd(&s)) { return 1; }
                    samples[i][k] = (int16_t)s;
                }
            }
            n = c2_encode_window(out, (uint16_t)sizeof out, (uint8_t)v[0], &m,
                                 (const int16_t (*)[C2_N_AXES])samples); /* C99 has no implicit T(*)[3] -> const T(*)[3] */
        } else if (tag[0] == 'H') {
            c2_hello_t h;
            for (i = 0u; i < 8u; i++) { if (!rd(&v[i])) { return 1; } }
            h.proto_ver   = (uint8_t)v[1];
            h.odr_hz      = (uint8_t)v[2];
            h.range_g     = (uint8_t)v[3];
            h.n_samples   = (uint8_t)v[4];
            h.pre_trig    = (uint8_t)v[5];
            h.feature_ver = (uint8_t)v[6];
            h.model_hash  = (uint32_t)v[7];
            n = c2_encode_hello(out, (uint16_t)sizeof out, (uint8_t)v[0], &h);
        } else {
            return 1;
        }
        if ((n == 0u) || (fwrite(out, 1u, n, stdout) != n)) { return 1; }
    }
    return 0;
}

/**
 * Entry point.
 * @param argc argument count
 * @param argv "crc <string>" or "encode"
 * @return 0 on success, nonzero on error
 */
int main(int argc, char **argv)
{
    if ((argc == 3) && (strcmp(argv[1], "crc") == 0)) {
        const uint8_t *d = (const uint8_t *)argv[2];
        uint16_t len = (uint16_t)strlen(argv[2]);
        uint16_t half = (uint16_t)(len / 2u);
        uint16_t split = c2_crc16_update(c2_crc16_update(0xFFFFu, d, half), &d[half], (uint16_t)(len - half));
        if (split != c2_crc16(d, len)) { return 2; }
        printf("%04X\n", (unsigned)c2_crc16(d, len));
        return 0;
    }
    if ((argc == 2) && (strcmp(argv[1], "encode") == 0)) {
        return do_encode();
    }
    return 1;
}
// [END AI-GENERATED]
