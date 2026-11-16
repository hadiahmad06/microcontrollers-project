// [AI-GENERATED: Claude Code]
/* standin/trigger.c - minimal spec implementation for harness proof (ticket T-trigT). */
#include <stddef.h>
#include "trigger.h"

uint16_t trigger_mg_to_counts(uint16_t mg)
{
    uint32_t c;
    if (mg == 0u) { return 0u; }
    c = ((uint32_t)mg + 1u) >> 1;
    if (c > TRIG_THR_MAX_COUNTS) { c = TRIG_THR_MAX_COUNTS; }
    return (uint16_t)c;
}

void trigger_resync(trigger_t *t)
{
    if (t == NULL) { return; }
    t->state = TRIG_WARMUP; t->seeded = 0u; t->warm_n = 0u;
    t->run = 0u; t->quiet_n = 0u; t->stat = 0u;
}

void trigger_set_threshold_mg(trigger_t *t, uint16_t mg)
{
    if (t == NULL) { return; }
    t->thr_mg = mg;
    t->thr = trigger_mg_to_counts(mg);
    t->lo = (uint16_t)((t->thr + 1u) >> 1);
}

void trigger_init(trigger_t *t, const trigger_cfg_t *cfg)
{
    uint8_t i;
    if (t == NULL) { return; }
    if (cfg == NULL) {
        t->cfg.debounce = TRIG_DEFAULT_DEBOUNCE; t->cfg.quiet = TRIG_DEFAULT_QUIET; t->cfg.warm = TRIG_DEFAULT_WARM;
    } else {
        t->cfg = *cfg;
        if (t->cfg.debounce < 1u) { t->cfg.debounce = 1u; }
        if (t->cfg.quiet < TRIG_MIN_QUIET) { t->cfg.quiet = TRIG_MIN_QUIET; }
        if (t->cfg.warm < 16u) { t->cfg.warm = 16u; }
    }
    for (i = 0u; i < 3u; i++) { t->base[i] = 0; }
    trigger_resync(t);
    trigger_set_threshold_mg(t, TRIG_DEFAULT_MG);
}

bool trigger_feed(trigger_t *t, const int16_t s[3])
{
    int32_t x, b, st = 0;
    uint8_t i;
    bool fire = false;
    if ((t == NULL) || (s == NULL)) { return false; }
    if (t->seeded == 0u) {
        for (i = 0u; i < 3u; i++) {
            x = s[i];
            if (x < -2048) { x = -2048; }
            if (x > 2047) { x = 2047; }
            t->base[i] = x * 8;
        }
        t->seeded = 1u; t->warm_n = 1u; t->stat = 0u;
        return false;
    }
    for (i = 0u; i < 3u; i++) {
        x = s[i];
        if (x < -2048) { x = -2048; }
        if (x > 2047) { x = 2047; }
        b = t->base[i] >> TRIG_SHIFT;
        st += (x > b) ? (x - b) : (b - x);
        t->base[i] += x - b;
    }
    t->stat = (uint16_t)st;
    if ((t->state == TRIG_WARMUP) && (t->warm_n >= t->cfg.warm)) { t->state = TRIG_ARMED; t->run = 0u; }
    if (t->state == TRIG_WARMUP) {
        if (t->warm_n < 255u) { t->warm_n++; }
    } else if (t->state == TRIG_ARMED) {
        if ((t->thr != 0u) && (t->stat > t->thr)) {
            if (t->run < 255u) { t->run++; }
        } else { t->run = 0u; }
        if (t->run >= t->cfg.debounce) { t->state = TRIG_LOCKED; t->run = 0u; fire = true; }
    } else if (t->state == TRIG_REARM) {
        if (t->stat < t->lo) { if (t->quiet_n < 255u) { t->quiet_n++; } } else { t->quiet_n = 0u; }
        if (t->quiet_n >= t->cfg.quiet) { t->state = TRIG_ARMED; t->run = 0u; }
    }
    return fire;
}

void trigger_release(trigger_t *t)
{
    if ((t != NULL) && (t->state == TRIG_LOCKED)) { t->state = TRIG_REARM; t->quiet_n = 0u; }
}

uint16_t trigger_statistic(const trigger_t *t)
{
    return (t == NULL) ? 0u : t->stat;
}
// [END AI-GENERATED]
