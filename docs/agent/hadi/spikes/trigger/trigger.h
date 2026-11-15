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
 * threshold_mg is converted once to counts with 2 mg per count (see proposal decision 3).
 * In firmware the shift S must be a compile-time constant (a runtime 32-bit shift is a library
 * call or loop on a 16-bit core, S2-2R F-10); the spike keeps it a runtime field for the tests.
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

/* Largest possible L1 statistic in counts: 3 axes * 4095 (full-scale swing on all axes). */
#define TRIG_STAT_MAX_COUNTS 12285u
/* Largest threshold that can still fire (the test is stat > thr): thresholds above it are
 * clamped to it (S2-2R F-05). It fires only on a full-scale swing on all three axes. */
#define TRIG_THR_MAX_COUNTS  12284u
/* Smallest quiet period accepted: re-arm after a release must outlast the 16-sample ring. */
#define TRIG_MIN_QUIET 16u

/* Recommended defaults (proposal decisions 1, 2, 3, 4, 5; evidence rows in proposal section 4). */
#define TRIG_DEFAULT_SHIFT    3u   /* baseline time constant 2^3 = 8 samples = 0.08 s  */
#define TRIG_DEFAULT_DEBOUNCE 2u   /* 2 consecutive samples above threshold           */
#define TRIG_DEFAULT_QUIET    30u  /* 0.3 s of quiet after release before re-arming    */
#define TRIG_DEFAULT_WARM     32u  /* samples after seeding before the first trigger   */
#define TRIG_DEFAULT_MG       250u /* default threshold_mg (125 counts)                */

/** Trigger configuration (fixed after trigger_init in firmware; variable in the spike). */
typedef struct {
    uint8_t stat;     /**< TRIG_STAT_*; an unknown value is replaced by EMA_L1 in init */
    uint8_t shift;    /**< baseline EMA shift S, clamped to 1..8 by init (time constant 2^S) */
    uint8_t debounce; /**< consecutive samples above threshold needed, >= 1         */
    uint8_t quiet;    /**< quiet samples needed after release, raised to >= 16 by init */
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
 * clamped to TRIG_THR_MAX_COUNTS (12284, the largest threshold that can still fire; mg >= 24567
 * all give 12284).
 * @param mg threshold in mg (0..65535)
 * @return threshold in counts (0 stays 0 = disabled)
 */
uint16_t trigger_mg_to_counts(uint16_t mg);

/**
 * Initialise the trigger: store the configuration, set the default threshold, enter WARMUP.
 * Out-of-range configuration values are clamped (stat to EMA_L1, shift 1..8, debounce >= 1,
 * quiet >= 16, warm >= 16).
 * @param t   trigger instance
 * @param cfg configuration, or NULL for the recommended defaults
 * @return none
 */
void trigger_init(trigger_t *t, const trigger_cfg_t *cfg);

/**
 * Set the trigger threshold. 0 disables triggering (the statistic and baseline keep running).
 * @param t  trigger instance
 * @param mg threshold in mg of L1 deviation (sum over 3 axes); see proposal decision 3
 * @return none
 */
void trigger_set_threshold_mg(trigger_t *t, uint16_t mg);

/**
 * Feed one drained sample. Must be called for every sample in order, in every state, so the
 * baseline keeps following the wand. If it returns true and the capture state machine is not
 * ready to start a window, the caller must call trigger_release() at once (S2-2R F-11), or the
 * trigger stays LOCKED.
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
