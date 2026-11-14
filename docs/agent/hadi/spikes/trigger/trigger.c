// [AI-GENERATED: Claude Code]
/*
 * trigger.c : software trigger rule spike (ticket S2-2). UNVERIFIED on real data.
 * Right shifts of negative int32 values are arithmetic (gcc, XC16), same rule as C1.1.
 * No borrowed code.
 */
#include "trigger.h"

#include <stddef.h>

#define TRIG_G_COUNTS   512  /* nominal 1 g in counts (C1.1) */
#define TRIG_MAG2_SCALE 10   /* MAG2 threshold = counts * 1024 = counts * 2 * 512 (first order) */

/* Absolute value of an int32 (inputs here never reach INT32_MIN). */
static int32_t abs32(int32_t v)
{
    return (v < 0) ? -v : v;
}

/**
 * Compute the statistic of one sample and update baseline and previous sample.
 * @param t trigger instance
 * @param s sample {x, y, z}
 * @return statistic in the units of the selected mode (counts, or counts^2 for MAG2)
 */
static int32_t trigger_statistic(trigger_t *t, const int16_t s[3])
{
    int32_t stat = 0;
    int32_t m2 = 0;
    uint8_t i;
    for (i = 0u; i < 3u; i++) {
        int32_t x = (int32_t)s[i];
        /* deviation from the baseline BEFORE this sample is folded in */
        int32_t dev = x - (t->base[i] >> t->cfg.shift);
        int32_t jerk = x - (int32_t)t->prev[i];
        if (t->cfg.stat == TRIG_STAT_EMA_L1) {
            stat += abs32(dev);
        } else if (t->cfg.stat == TRIG_STAT_EMA_MAX) {
            if (abs32(dev) > stat) {
                stat = abs32(dev);
            }
        } else if (t->cfg.stat == TRIG_STAT_JERK_L1) {
            stat += abs32(jerk);
        } else {
            m2 += x * x; /* up to 3 * 2048^2 = 12.6e6, fits int32 */
        }
        /* baseline: acc += x - (acc >> S), acc holds the average << S */
        t->base[i] += x - (t->base[i] >> t->cfg.shift);
        t->prev[i] = s[i];
    }
    if (t->cfg.stat == TRIG_STAT_MAG2) {
        stat = abs32(m2 - (int32_t)TRIG_G_COUNTS * TRIG_G_COUNTS);
    }
    return stat;
}

uint16_t trigger_mg_to_counts(uint16_t mg)
{
    uint32_t c = ((uint32_t)mg + 1u) >> 1; /* 2 mg per count, round half up (0 -> 0) */
    if (mg == 0u) {
        return 0u;
    }
    if (c > TRIG_STAT_MAX_COUNTS) {
        c = TRIG_STAT_MAX_COUNTS;
    }
    return (uint16_t)c;
}

void trigger_resync(trigger_t *t)
{
    t->state = TRIG_WARMUP;
    t->seeded = 0u;
    t->warm_n = 0u;
    t->run = 0u;
    t->quiet_n = 0u;
    t->stat = 0;
}

void trigger_set_threshold_mg(trigger_t *t, uint16_t mg)
{
    int32_t c = (int32_t)trigger_mg_to_counts(mg);
    t->thr_mg = mg;
    if (t->cfg.stat == TRIG_STAT_MAG2) {
        c = c * ((int32_t)1 << TRIG_MAG2_SCALE); /* <= 12285 * 1024 = 12.58e6 */
    }
    t->thr = c;
    t->lo = (c + 1) >> 1; /* hysteresis level, never 0 for a non-zero threshold */
}

void trigger_init(trigger_t *t, const trigger_cfg_t *cfg)
{
    uint8_t i;
    if (cfg != NULL) {
        t->cfg = *cfg;
    } else {
        t->cfg.stat = TRIG_STAT_EMA_L1;
        t->cfg.shift = TRIG_DEFAULT_SHIFT;
        t->cfg.debounce = TRIG_DEFAULT_DEBOUNCE;
        t->cfg.quiet = TRIG_DEFAULT_QUIET;
        t->cfg.warm = TRIG_DEFAULT_WARM;
    }
    if (t->cfg.debounce < 1u) {
        t->cfg.debounce = 1u;
    }
    if (t->cfg.warm < 16u) {
        t->cfg.warm = 16u; /* the pre-trigger ring (15 samples) must be full */
    }
    for (i = 0u; i < 3u; i++) {
        t->base[i] = 0;
        t->prev[i] = 0;
    }
    trigger_resync(t);
    trigger_set_threshold_mg(t, TRIG_DEFAULT_MG);
}

bool trigger_feed(trigger_t *t, const int16_t s[3])
{
    int32_t stat;
    bool fire = false;
    uint8_t i;

    if (t->seeded == 0u) {
        /* first sample: baseline = sample, no deviation */
        for (i = 0u; i < 3u; i++) {
            t->base[i] = (int32_t)s[i] * ((int32_t)1 << t->cfg.shift);
            t->prev[i] = s[i];
        }
        t->seeded = 1u;
        t->warm_n = 1u;
        t->stat = 0;
        return false;
    }

    stat = trigger_statistic(t, s);
    t->stat = stat;

    if ((t->state == TRIG_WARMUP) && (t->warm_n >= t->cfg.warm)) {
        t->state = TRIG_ARMED;
        t->run = 0u;
    }

    if (t->state == TRIG_WARMUP) {
        if (t->warm_n < 255u) {
            t->warm_n++;
        }
    } else if (t->state == TRIG_ARMED) {
        if ((t->thr != 0) && (stat > t->thr)) {
            t->run++;
        } else {
            t->run = 0u;
        }
        if (t->run >= t->cfg.debounce) {
            t->state = TRIG_LOCKED;
            t->run = 0u;
            fire = true;
        }
    } else if (t->state == TRIG_REARM) {
        if (stat < t->lo) {
            t->quiet_n++;
        } else {
            t->quiet_n = 0u;
        }
        if (t->quiet_n >= t->cfg.quiet) {
            t->state = TRIG_ARMED;
            t->run = 0u;
        }
    } else {
        /* TRIG_LOCKED: nothing, wait for trigger_release() */
    }
    return fire;
}

void trigger_release(trigger_t *t)
{
    if (t->state == TRIG_LOCKED) {
        t->state = TRIG_REARM;
        t->quiet_n = 0u;
    }
}
// [END AI-GENERATED]
