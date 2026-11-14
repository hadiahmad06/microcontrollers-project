// [AI-GENERATED: Claude Code]
/*
 * trigger.h : software trigger rule spike (ticket S2-2, CONTRACTS C1.9).
 * UNVERIFIED: tuned on synthetic data only, not on real recordings (WP2).
 *
 * One call to trigger_feed() per drained sample, strictly in order (C1.4).
 * C99, fixed-width types, integer only, no malloc, no blocking.
 * The Python mirror (trigger_ref.py) must give bit-identical decisions and state.
 *
 * Units: samples are the C1.1 counts (int16, about 512 per g at +-4 g, wand frame).
 * threshold_mg is converted once to counts with 2 mg per count (see proposal D3).
 */
#ifndef TRIGGER_H
#define TRIGGER_H

#include <stdbool.h>
#include <stdint.h>

/* Statistic selector. */
#define TRIG_STAT_EMA_L1  0u  /* sum |x - baseline| over 3 axes (recommended)   */
#define TRIG_STAT_EMA_MAX 1u  /* max |x - baseline| over 3 axes                  */
#define TRIG_STAT_JERK_L1 2u  /* sum |x[n] - x[n-1]| over 3 axes                 */
#define TRIG_STAT_MAG2    3u  /* | x^2+y^2+z^2 - 512^2 |, threshold scaled x1024 */

/* Trigger states (only what the trigger itself needs; not the capture state machine). */
#define TRIG_WARMUP 0u  /* seeding the baseline, never fires            */
#define TRIG_ARMED  1u  /* may fire                                     */
#define TRIG_LOCKED 2u  /* fired, waiting for trigger_release()         */
#define TRIG_REARM  3u  /* released, waiting for a quiet period         */

/* Largest possible L1 statistic in counts: 3 axes * 4095. Thresholds are clamped to it. */
#define TRIG_STAT_MAX_COUNTS 12285u

/* Recommended defaults (proposal D1, D2, D4, D5). */
#define TRIG_DEFAULT_SHIFT    4u   /* baseline time constant 2^4 = 16 samples = 0.16 s */
#define TRIG_DEFAULT_DEBOUNCE 2u   /* 2 consecutive samples above threshold           */
#define TRIG_DEFAULT_QUIET    30u  /* 0.3 s of quiet after release before re-arming    */
#define TRIG_DEFAULT_WARM     32u  /* samples after seeding before the first trigger   */
#define TRIG_DEFAULT_MG       300u /* default threshold_mg                             */

/** Trigger configuration (fixed after trigger_init in firmware; variable in the spike). */
typedef struct {
    uint8_t stat;     /**< TRIG_STAT_*                                              */
    uint8_t shift;    /**< baseline EMA shift S, 1..8 (time constant 2^S samples)   */
    uint8_t debounce; /**< consecutive samples above threshold needed, >= 1         */
    uint8_t quiet;    /**< quiet samples needed after release before re-arming      */
    uint8_t warm;     /**< samples after seeding before the first trigger, >= 16    */
} trigger_cfg_t;

/** Trigger state. Fields are public so the host test can print and compare them. */
typedef struct {
    trigger_cfg_t cfg;
    uint16_t thr_mg;  /**< last value given to trigger_set_threshold_mg             */
    int32_t  thr;     /**< threshold in statistic units (0 = disabled)              */
    int32_t  lo;      /**< hysteresis level, (thr + 1) >> 1                         */
    uint8_t  state;   /**< TRIG_*                                                   */
    uint8_t  seeded;  /**< 0 until the first sample after init/resync               */
    uint8_t  warm_n;  /**< samples processed since seeding (saturates at 255)       */
    uint8_t  run;     /**< consecutive samples above threshold                      */
    uint8_t  quiet_n; /**< consecutive quiet samples while in TRIG_REARM            */
    int32_t  base[3]; /**< baseline accumulators, value << shift                    */
    int16_t  prev[3]; /**< previous sample                                          */
    int32_t  stat;    /**< statistic of the last sample fed                         */
} trigger_t;

/**
 * Convert threshold_mg to counts: counts = (mg + 1) >> 1 (2 mg per count, round half up),
 * clamped to TRIG_STAT_MAX_COUNTS.
 * @param mg threshold in mg (0..65535)
 * @return threshold in counts (0 stays 0)
 */
uint16_t trigger_mg_to_counts(uint16_t mg);

/**
 * Initialise the trigger: store the configuration, set the default threshold, enter WARMUP.
 * @param t   trigger instance
 * @param cfg configuration, or NULL for the recommended defaults
 * @return none
 */
void trigger_init(trigger_t *t, const trigger_cfg_t *cfg);

/**
 * Set the trigger threshold. 0 disables triggering (the statistic and baseline keep running).
 * @param t  trigger instance
 * @param mg threshold in mg of L1 deviation (sum over 3 axes); see proposal D3
 * @return none
 */
void trigger_set_threshold_mg(trigger_t *t, uint16_t mg);

/**
 * Feed one drained sample. Must be called for every sample in order, in every state, so the
 * baseline keeps following the wand.
 * @param t trigger instance
 * @param s sample {x, y, z}, int16 counts in wand frame
 * @return true if this sample is the trigger sample t (window = t-15 .. t+134); at most once
 *         per release
 */
bool trigger_feed(trigger_t *t, const int16_t s[3]);

/**
 * Tell the trigger that the capture buffer was released (or the window dropped). Moves
 * LOCKED to REARM. Ignored in any other state.
 * @param t trigger instance
 * @return none
 */
void trigger_release(trigger_t *t);

/**
 * Restart after a gap in the sample stream (FIFO overrun, bus error): the baseline is re-seeded
 * from the next sample and the warm-up runs again so the pre-trigger ring is refilled.
 * @param t trigger instance
 * @return none
 */
void trigger_resync(trigger_t *t);

#endif /* TRIGGER_H */
// [END AI-GENERATED]
