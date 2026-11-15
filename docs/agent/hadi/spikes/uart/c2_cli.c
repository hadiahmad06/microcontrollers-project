// [AI-GENERATED: Claude Code]
/*
 * c2_cli.c - host test driver for c2_frame (not firmware; uses stdio on purpose).
 *   c2_cli crc <string>   prints the CRC-16/IBM-3740 of the string as 4 hex digits; also
 *                         checks that a split update (two halves) gives the same value.
 *   c2_cli encode         reads text records on stdin, writes the binary frames to stdout.
 * Host only: fixed-width types are used for all data; `char` (strings), `int main` and the
 * stdio return values are the only exceptions, because the C library and C99 fix those types.
 * Record formats (decimal integers, whitespace separated):
 *   W seq window_id trig_idx overruns model_hash flags class_id conf events  (450 sample values)
 *   H seq proto odr range n_samples pre_trig feature_ver model_hash
 */
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include "c2_frame.h"

/**
 * Read one signed decimal from stdin.
 * @param v destination (64 bit, so every uint32_t value fits)
 * @return 1 on success, 0 on EOF or parse failure
 */
static uint8_t rd(int64_t *v)
{
    return (scanf("%" SCNd64, v) == 1) ? 1u : 0u;
}

/**
 * Encode all records from stdin to stdout.
 * @return 0 on success, 1 on a malformed record or write failure
 */
static int32_t do_encode(void)
{
    static uint8_t out[C2_WINDOW_FRAME_LEN];
    static int16_t samples[C2_N_SAMPLES][C2_N_AXES];
    char tag[4];

    while (scanf("%3s", tag) == 1) {
        int64_t v[9];
        uint16_t n = 0u;
        uint16_t i;
        if (tag[0] == 'W') {
            c2_window_meta_t m;
            uint16_t k;
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
                    int64_t s;
                    if (!rd(&s)) { return 1; }
                    samples[i][k] = (int16_t)s;
                }
            }
            n = c2_encode_window(out, (uint16_t)sizeof out, (uint8_t)v[0], &m,
                                 samples);
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
        printf("%04" PRIX32 "\n", (uint32_t)c2_crc16(d, len));
        return 0;
    }
    if ((argc == 2) && (strcmp(argv[1], "encode") == 0)) {
        return do_encode();
    }
    return 1;
}
// [END AI-GENERATED]
