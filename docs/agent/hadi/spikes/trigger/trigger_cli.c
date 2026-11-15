// [AI-GENERATED: Claude Code]
/*
 * trigger_cli.c : host test harness (not firmware). Reads streams from stdin, runs the C
 * trigger, prints per stream: number of triggers, their sample indices, and an FNV-1a hash of
 * the internal state after every sample (so C and Python can be compared state for state).
 *
 * Input:  first line N (number of streams). Per stream, a header line
 *           stat shift debounce quiet warm thr_mg rel_delay resync_at n
 *         then one line with 3*n integers (x y z per sample).
 *         rel_delay < 0: never release. resync_at < 0: never resync.
 * Output: per stream one line "ntrig idx0 idx1 ... hash".
 * Hash words per sample, in order: stat, state, base0, base1, base2, run, quiet_n, warm_n.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "trigger.h"

#define MAX_N 4096

static uint32_t fnv_word(uint32_t h, uint32_t w)
{
    return (h ^ w) * 16777619u;
}

int main(void)
{
    int nstreams = 0;
    int k;
    static int16_t buf[MAX_N][3];
    if (scanf("%d", &nstreams) != 1) {
        return 1;
    }
    for (k = 0; k < nstreams; k++) {
        trigger_cfg_t cfg;
        trigger_t t;
        int stat, shift, deb, quiet, warm, thr, rel, resync_at, n, i, j;
        int trig_at = -1;
        int ntrig = 0;
        int trigs[MAX_N];
        uint32_t h = 2166136261u;
        if (scanf("%d %d %d %d %d %d %d %d %d", &stat, &shift, &deb, &quiet, &warm, &thr, &rel,
                  &resync_at, &n) != 9 || n > MAX_N) {
            return 1;
        }
        for (i = 0; i < n; i++) {
            for (j = 0; j < 3; j++) {
                int v;
                if (scanf("%d", &v) != 1) {
                    return 1;
                }
                buf[i][j] = (int16_t)v;
            }
        }
        cfg.stat = (uint8_t)stat;
        cfg.shift = (uint8_t)shift;
        cfg.debounce = (uint8_t)deb;
        cfg.quiet = (uint8_t)quiet;
        cfg.warm = (uint8_t)warm;
        trigger_init(&t, &cfg);
        trigger_set_threshold_mg(&t, (uint16_t)thr);
        for (i = 0; i < n; i++) {
            if (i == resync_at) {
                trigger_resync(&t);
                trig_at = -1;
            }
            if (trigger_feed(&t, buf[i])) {
                trigs[ntrig++] = i;
                trig_at = i;
            }
            h = fnv_word(h, (uint32_t)t.stat);
            h = fnv_word(h, t.state);
            h = fnv_word(h, (uint32_t)t.base[0]);
            h = fnv_word(h, (uint32_t)t.base[1]);
            h = fnv_word(h, (uint32_t)t.base[2]);
            h = fnv_word(h, t.run);
            h = fnv_word(h, t.quiet_n);
            h = fnv_word(h, t.warm_n);
            if ((trig_at >= 0) && (rel >= 0) && (i - trig_at >= rel)) {
                trigger_release(&t);
                trig_at = -1;
            }
        }
        printf("%d", ntrig);
        for (i = 0; i < ntrig; i++) {
            printf(" %d", trigs[i]);
        }
        printf(" %u\n", (unsigned)h);
    }
    return 0;
}
// [END AI-GENERATED]
