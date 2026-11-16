// [AI-GENERATED: Claude Code]
/*
 * standin/trigger.h - minimal spec implementation used only to prove the test harness
 * (ticket T-trigT). Written from docs/agent/hadi/briefs/T-trig_spec.md; NOT the product module.
 * WORKING ASSUMPTION: open_questions Q2, Q3, not decided.
 */
#ifndef TRIGGER_H
#define TRIGGER_H

#include <stdint.h>
#include <stdbool.h>

#define TRIG_WARMUP 0
#define TRIG_ARMED 1
#define TRIG_LOCKED 2
#define TRIG_REARM 3
#define TRIG_SHIFT 3
#define TRIG_STAT_MAX_COUNTS 12285
#define TRIG_THR_MAX_COUNTS 12284
#define TRIG_MIN_QUIET 16
#define TRIG_DEFAULT_DEBOUNCE 2
#define TRIG_DEFAULT_QUIET 30
#define TRIG_DEFAULT_WARM 32
#define TRIG_DEFAULT_MG 250

typedef struct { uint8_t debounce; uint8_t quiet; uint8_t warm; } trigger_cfg_t;

typedef struct {
    trigger_cfg_t cfg;
    uint16_t thr_mg, thr, lo;
    uint8_t state, seeded, warm_n, run, quiet_n;
    int32_t base[3];
    uint16_t stat;
} trigger_t;

/** Convert mg to counts: (mg+1)>>1 clamped to 12284 (0 stays 0). @param mg threshold in mg. @return counts. */
uint16_t trigger_mg_to_counts(uint16_t mg);
/** Initialise. @param t state (NULL ignored). @param cfg configuration or NULL for defaults. */
void trigger_init(trigger_t *t, const trigger_cfg_t *cfg);
/** Set threshold. @param t state. @param mg threshold in mg. */
void trigger_set_threshold_mg(trigger_t *t, uint16_t mg);
/** Feed one sample. @param t state. @param s x,y,z counts. @return true when the trigger fires. */
bool trigger_feed(trigger_t *t, const int16_t s[3]);
/** Release a LOCKED trigger into REARM. @param t state. */
void trigger_release(trigger_t *t);
/** Return to WARMUP with re-seed. @param t state. */
void trigger_resync(trigger_t *t);
/** Statistic of the last sample. @param t state. @return stat (0 for NULL). */
uint16_t trigger_statistic(const trigger_t *t);
#endif
// [END AI-GENERATED]
