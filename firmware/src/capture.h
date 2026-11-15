// [AI-GENERATED: Claude Code]
/**
 * @file capture.h
 * @brief Sample-level gesture capture: pre-trigger ring, window cut, overrun policy, buffer lock
 *        (ticket WP1-a; contracts C0, C1).
 *
 * The caller feeds one wand-frame sample at a time, strictly in order, together with a per-sample
 * trigger flag computed elsewhere. The module keeps the 16 most recent samples in a ring and cuts a
 * window of exactly CAPTURE_LEN samples by sample index: the CAPTURE_PRE samples before the trigger
 * sample t, t itself, then the next 134 samples (window = t-15 ... t+134). A window is never padded.
 *
 * States: IDLE -> ARMED -> CAPTURING -> READY (buffer locked) -> release -> ARMED.
 *
 * Ring policy: the ring is fed by capture_push() in EVERY state (IDLE included), so the pre-trigger
 * samples exist the moment the module is armed or released. capture_arm(), capture_disarm() and
 * capture_release() never touch the ring; only capture_overrun() (a gap in the stream) and
 * capture_init() empty it.
 *
 * Trigger-module glue (C1b): the trigger module stays LOCKED after it fires until the caller runs
 * trigger_release(). The caller MUST call trigger_release() whenever (a) capture_push() returned
 * false although a trigger fired on that sample (early or ignored trigger), or (b) capture_overrun()
 * or capture_disarm() returned true (an open window was dropped), or (c) capture_release() returned
 * true. C1.6's "re-arm after a quiet period" is not done here: after a dropped window this module
 * goes straight to ARMED (or IDLE) and the refractory time comes from the trigger module's REARM
 * rule (proposal C1b: quiet >= 16 samples).
 * No float, no malloc, no blocking. All storage is static (900 B buffer + 96 B ring + state).
 */
#ifndef CAPTURE_H
#define CAPTURE_H

#include <stdint.h>
#include <stdbool.h>

#define CAPTURE_LEN   150u  /**< samples per window */
#define CAPTURE_PRE    15u  /**< samples before the trigger sample kept in the window */
#define CAPTURE_RING   16u  /**< ring entries: the trigger sample plus CAPTURE_PRE earlier ones */

/** Capture state machine states. */
typedef enum {
    CAPTURE_IDLE = 0,       /**< not armed; triggers ignored */
    CAPTURE_ARMED = 1,      /**< waiting for a trigger */
    CAPTURE_CAPTURING = 2,  /**< window open, filling the buffer */
    CAPTURE_READY = 3       /**< window complete, buffer locked until capture_release() */
} capture_state_t;

/** Event counters (wrap at 65535). */
typedef struct {
    uint16_t overruns;        /**< overrun events reported via capture_overrun() */
    uint16_t windows;         /**< transitions to READY */
    uint16_t early_triggers;  /**< triggers ignored in ARMED for lack of CAPTURE_PRE earlier samples */
} capture_stats_t;

/** Reset to IDLE, empty the ring and zero the statistics. */
void capture_init(void);

/** Arm the capture: IDLE -> ARMED. In any other state this does nothing. The ring is not touched. */
void capture_arm(void);

/**
 * Disarm: ARMED or CAPTURING -> IDLE. An open window is dropped without counting an overrun.
 * Does nothing in READY (the locked buffer is kept) or IDLE. The ring is not touched.
 * @return true iff an open window was dropped (CAPTURING -> IDLE); the caller then must call
 *         trigger_release(). False otherwise.
 */
bool capture_disarm(void);

/**
 * Process one sample. Order: ring push, trigger test, window append. The trigger flag is honoured
 * only in ARMED and only if at least CAPTURE_PRE samples were pushed before this one since the last
 * init/overrun; otherwise it is ignored (counted in early_triggers when the state was ARMED). O(1)
 * per call, except for the CAPTURE_RING-entry ring unroll at trigger time.
 * @param s       three int16_t wand-frame values (X, Y, Z); copied, must not be NULL
 * @param trigger true if the trigger rule fired on this sample (computed by the caller)
 * @return true iff this call opened a window (ARMED -> CAPTURING). False in every other case,
 *         including an early trigger and a trigger ignored outside ARMED; if @p trigger was true
 *         and false is returned, the caller must call trigger_release().
 */
bool capture_push(const int16_t s[3], bool trigger);

/**
 * Report a FIFO overrun or missed drain deadline. Increments overruns and empties the ring (the
 * stream has a gap). In CAPTURING the open window is dropped (-> ARMED). In IDLE, ARMED and READY
 * the state is unchanged; READY keeps the locked buffer intact.
 * @return true iff an open window was dropped (CAPTURING -> ARMED); the caller then must call
 *         trigger_release(). False otherwise.
 */
bool capture_overrun(void);

/**
 * Release the locked buffer: READY -> ARMED.
 * @return true if the state was READY and is now ARMED, false (and nothing done) otherwise
 */
bool capture_release(void);

/**
 * Current state.
 * @return the capture_state_t value
 */
capture_state_t capture_state(void);

/**
 * The window buffer, CAPTURE_LEN rows of {X, Y, Z}, oldest sample first.
 * @return pointer to the one static buffer (always the same, never NULL); its contents are defined
 *         only while the state is READY (it is being filled in CAPTURING, stale otherwise)
 */
int16_t (*capture_buffer(void))[3];

/**
 * Samples currently held in the ring.
 * @return count 0..CAPTURE_RING
 */
uint8_t capture_ring_count(void);

/**
 * Copy the event counters.
 * @param out destination; must not be NULL
 */
void capture_stats(capture_stats_t *out);

#endif /* CAPTURE_H */
// [END AI-GENERATED]
