// [AI-GENERATED: Claude Code]
/*
 * trigger.h : software motion trigger (EMA-L1 statistic), product module for ticket T-trig.
 *
 * WORKING ASSUMPTION: open_questions Q2, Q3, not decided
 *   (Q2: trigger C1b as proposed, fixed by S2-2F; Q3: keep C1.6). See docs/agent/WORKING_ASSUMPTIONS.md.
 *
 * Promoted from the spike docs/agent/hadi/spikes/trigger/{trigger.h,trigger.c} (our own code, S2-2);
 * the other spike statistics and the runtime shift are removed. Python mirror: tools/trigger_ref.py
 * (bit-exact: same trigger indices and same per-sample state hash).
 *
 * One call to trigger_feed() per drained sample, in order, in every state (C1.4).
 * C99, fixed-width types, integer only, no malloc, no blocking.
 * Samples are C1.1 counts (about 512 per g at +-4 g). Each axis is clamped to [-2048, 2047]
 * before use, so no overflow is possible. Right shifts of negative int32 are arithmetic
 * (gcc, XC16), same rule as C1.1.
 */
#ifndef TRIGGER_H
#define TRIGGER_H

#include <stdbool.h>
#include <stdint.h>

/** Baseline EMA shift S: time constant 2^3 = 8 samples = 80 ms. Compile-time constant (S2-2R F-10). */
#define TRIG_SHIFT 3

/* Trigger states (only what the trigger itself needs; not the capture state machine). */
#define TRIG_WARMUP 0u  /* seeding the baseline, never fires            */
#define TRIG_ARMED  1u  /* may fire                                     */
#define TRIG_LOCKED 2u  /* fired, waiting for trigger_release()         */
#define TRIG_REARM  3u  /* released, waiting for a quiet period         */

/* Largest possible L1 statistic in counts: 3 axes * 4095 (full-scale swing on all axes). */
#define TRIG_STAT_MAX_COUNTS 12285u
/* Largest threshold that can still fire (the test is stat > thr); larger thresholds are clamped. */
#define TRIG_THR_MAX_COUNTS  12284u
/* Smallest quiet period accepted: re-arm after a release must outlast the 16-sample ring. */
#define TRIG_MIN_QUIET 16u

/* Defaults (proposal C1b decisions 1-5). */
#define TRIG_DEFAULT_DEBOUNCE 2u   /* 2 consecutive samples above threshold           */
#define TRIG_DEFAULT_QUIET    30u  /* 0.3 s of quiet after release before re-arming    */
#define TRIG_DEFAULT_WARM     32u  /* samples after seeding before the first trigger   */
#define TRIG_DEFAULT_MG       250u /* default threshold_mg (125 counts)                */

/** Trigger configuration (fixed after trigger_init). */
typedef struct {
    uint8_t debounce; /**< consecutive samples above threshold needed; init raises to >= 1 */
    uint8_t quiet;    /**< quiet samples needed after release; init raises to >= 16        */
    uint8_t warm;     /**< samples after seeding before the first trigger; raised to >= 16  */
} trigger_cfg_t;

/** Trigger state. Fields are public so the host tests can print and compare them. */
typedef struct {
    trigger_cfg_t cfg;
    uint16_t thr_mg;  /**< last value given to trigger_set_threshold_mg              */
    uint16_t thr;     /**< threshold in counts (0 = disabled)                        */
    uint16_t lo;      /**< hysteresis level in counts, (thr + 1) >> 1                */
    uint8_t  state;   /**< TRIG_*                                                    */
    uint8_t  seeded;  /**< 0 until the first sample after init/resync                */
    uint8_t  warm_n;  /**< samples processed since seeding (saturates at 255)        */
    uint8_t  run;     /**< consecutive samples above threshold                       */
    uint8_t  quiet_n; /**< consecutive quiet samples while in TRIG_REARM (saturates) */
    int32_t  base[3]; /**< baseline accumulators, mean << TRIG_SHIFT                 */
    uint16_t stat;    /**< statistic of the last sample fed                          */
} trigger_t;

/**
 * Convert threshold_mg to counts: (mg + 1) >> 1 computed in uint32_t (2 mg per count, round half
 * up), clamped to TRIG_THR_MAX_COUNTS. 0 stays 0 (= disabled); 24567 and above give 12284.
 * @param mg threshold in mg (0..65535)
 * @return threshold in counts
 */
uint16_t trigger_mg_to_counts(uint16_t mg);

/**
 * Initialise the trigger: store the configuration, set the default threshold, enter WARMUP.
 * Configuration values are clamped (debounce >= 1, quiet >= 16, warm >= 16).
 * @param t   trigger instance (NULL: nothing happens)
 * @param cfg configuration, or NULL for the defaults
 * @return none
 */
void trigger_init(trigger_t *t, const trigger_cfg_t *cfg);

/**
 * Set the trigger threshold; may be called at any time. Changes thr, lo and thr_mg only; the
 * state machine is untouched. 0 disables triggering (the baseline keeps running).
 * @param t  trigger instance (NULL: nothing happens)
 * @param mg threshold in mg of L1 deviation summed over 3 axes
 * @return none
 */
void trigger_set_threshold_mg(trigger_t *t, uint16_t mg);

/**
 * Feed one drained sample, in every state, so the baseline keeps following the wand. If it
 * returns true and the capture state machine cannot start a window, the caller must call
 * trigger_release() at once, or the trigger stays LOCKED.
 * @param t trigger instance (NULL: returns false)
 * @param s sample {x, y, z}, counts; each axis is clamped to [-2048, 2047] (NULL: returns false)
 * @return true if this sample is the trigger sample t (window = t-15 .. t+134); at most once
 *         per release
 */
bool trigger_feed(trigger_t *t, const int16_t s[3]);

/**
 * Tell the trigger that the capture buffer was released (or the window dropped for an overrun).
 * Moves LOCKED to REARM. Ignored in any other state (WARMUP, ARMED, REARM). The caller must never
 * deliver a stale release after trigger_resync(): once warm-up has finished and a new trigger has
 * fired, a late release would unlock that NEW trigger early.
 * @param t trigger instance (NULL: nothing happens)
 * @return none
 */
void trigger_release(trigger_t *t);

/**
 * Restart after a gap in the sample stream not covered by an open window: the baseline is
 * re-seeded from the next sample and the warm-up runs again. Resync from LOCKED unlocks the trigger
 * (state := WARMUP, run and quiet_n cleared). The caller must therefore drop any open capture window
 * when it resyncs, and must not send a stale trigger_release() afterwards.
 * @param t trigger instance (NULL: nothing happens)
 * @return none
 */
void trigger_resync(trigger_t *t);

/**
 * Statistic of the last sample fed (debug).
 * @param t trigger instance (NULL: returns 0)
 * @return L1 deviation from the baseline in counts (0 for the seed sample)
 */
uint16_t trigger_statistic(const trigger_t *t);

#endif /* TRIGGER_H */
// [END AI-GENERATED]
