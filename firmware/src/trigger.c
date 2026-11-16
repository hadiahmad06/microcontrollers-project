// [AI-GENERATED: Claude Code]
/*
 * trigger.c : software motion trigger, EMA-L1 only (ticket T-trig).
 *
 * WORKING ASSUMPTION: open_questions Q2, Q3, not decided.
 * Promoted from our own spike docs/agent/hadi/spikes/trigger/trigger.c (S2-2). No other borrowed code.
 */
#include "trigger.h"

#include <stddef.h>

#define TRIG_AXIS_MIN (-2048) /* C1.1 sample range */
#define TRIG_AXIS_MAX 2047

/* Clamp one axis to the C1.1 range so all arithmetic below stays in int32 without overflow. */
static int32_t clamp_axis(int16_t v)
{
    int32_t x = (int32_t)v;
    if (x < TRIG_AXIS_MIN) {
        x = TRIG_AXIS_MIN;
    } else if (x > TRIG_AXIS_MAX) {
        x = TRIG_AXIS_MAX;
    }
    return x;
}

/* Absolute value of an int32 (inputs here never reach INT32_MIN). */
static int32_t abs32(int32_t v)
{
    return (v < 0) ? -v : v;
}

uint16_t trigger_mg_to_counts(uint16_t mg)
{
    uint32_t c;
    if (mg == 0u) {
        return 0u;
    }
    c = ((uint32_t)mg + 1u) >> 1; /* 2 mg per count, round half up; uint32 so 65535 + 1 cannot wrap */
    if (c > TRIG_THR_MAX_COUNTS) {
        c = TRIG_THR_MAX_COUNTS; /* 12285 could never fire (stat > thr), so stop at 12284 */
    }
    return (uint16_t)c;
}

void trigger_resync(trigger_t *t)
{
    if (t == NULL) {
        return;
    }
    t->state = TRIG_WARMUP;
    t->seeded = 0u;
    t->warm_n = 0u;
    t->run = 0u;
    t->quiet_n = 0u;
    t->stat = 0u;
}

void trigger_set_threshold_mg(trigger_t *t, uint16_t mg)
{
    uint16_t c;
    if (t == NULL) {
        return;
    }
    c = trigger_mg_to_counts(mg);
    t->thr_mg = mg;
    t->thr = c;
    t->lo = (uint16_t)(((uint32_t)c + 1u) >> 1); /* hysteresis level, never 0 for a non-zero threshold */
}

void trigger_init(trigger_t *t, const trigger_cfg_t *cfg)
{
    uint8_t i;
    if (t == NULL) {
        return;
    }
    if (cfg != NULL) {
        t->cfg = *cfg;
    } else {
        t->cfg.debounce = TRIG_DEFAULT_DEBOUNCE;
        t->cfg.quiet = TRIG_DEFAULT_QUIET;
        t->cfg.warm = TRIG_DEFAULT_WARM;
    }
    if (t->cfg.debounce < 1u) {
        t->cfg.debounce = 1u;
    }
    if (t->cfg.quiet < TRIG_MIN_QUIET) {
        t->cfg.quiet = TRIG_MIN_QUIET; /* REARM must outlast the 16-sample ring (S2-2R F-06) */
    }
    if (t->cfg.warm < 16u) {
        t->cfg.warm = 16u; /* the pre-trigger ring (15 samples) must be full */
    }
    for (i = 0u; i < 3u; i++) {
        t->base[i] = 0;
    }
    trigger_resync(t);
    trigger_set_threshold_mg(t, TRIG_DEFAULT_MG);
}

bool trigger_feed(trigger_t *t, const int16_t s[3])
{
    int32_t stat = 0;
    bool fire = false;
    uint8_t i;

    if ((t == NULL) || (s == NULL)) {
        return false;
    }

    if (t->seeded == 0u) {
        /* first sample after init/resync: baseline = sample, so the statistic starts at 0 */
        for (i = 0u; i < 3u; i++) {
            t->base[i] = clamp_axis(s[i]) * ((int32_t)1 << TRIG_SHIFT);
        }
        t->seeded = 1u;
        t->warm_n = 1u;
        t->stat = 0u;
        return false;
    }

    for (i = 0u; i < 3u; i++) {
        int32_t x = clamp_axis(s[i]);
        /* deviation from the baseline BEFORE this sample is folded in */
        stat += abs32(x - (t->base[i] >> TRIG_SHIFT));
        /* baseline: acc += x - (acc >> S), acc holds the mean << S; never frozen */
        t->base[i] += x - (t->base[i] >> TRIG_SHIFT);
    }
    t->stat = (uint16_t)stat; /* at most 3 * 4095 = 12285 */

    if ((t->state == TRIG_WARMUP) && (t->warm_n >= t->cfg.warm)) {
        t->state = TRIG_ARMED;
        t->run = 0u;
    }

    if (t->state == TRIG_WARMUP) {
        if (t->warm_n < 255u) {
            t->warm_n++;
        }
    } else if (t->state == TRIG_ARMED) {
        if ((t->thr != 0u) && (t->stat > t->thr)) {
            if (t->run < 255u) {
                t->run++;
            }
        } else {
            t->run = 0u;
        }
        if (t->run >= t->cfg.debounce) {
            t->state = TRIG_LOCKED;
            t->run = 0u;
            fire = true;
        }
    } else if (t->state == TRIG_REARM) {
        if (t->stat < t->lo) {
            if (t->quiet_n < 255u) {
                t->quiet_n++;
            }
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
    if (t == NULL) {
        return;
    }
    if (t->state == TRIG_LOCKED) {
        t->state = TRIG_REARM;
        t->quiet_n = 0u;
    }
}

uint16_t trigger_statistic(const trigger_t *t)
{
    return (t == NULL) ? 0u : t->stat;
}
// [END AI-GENERATED]
