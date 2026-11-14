// [AI-GENERATED: Claude Code]
/* TEST STAND-IN written from CONTRACTS.md C1 and the main-agent rulings only (API of ticket WP1-aT),
 * to prove the capture test harness. The real implementation is firmware/src/capture.c. Do not ship. */
#ifndef CAPTURE_H
#define CAPTURE_H

#include <stdbool.h>
#include <stdint.h>

#define CAPTURE_LEN   150u
#define CAPTURE_PRE    15u
#define CAPTURE_RING   16u

typedef enum { CAPTURE_IDLE = 0, CAPTURE_ARMED = 1, CAPTURE_CAPTURING = 2, CAPTURE_READY = 3 } capture_state_t;

typedef struct { uint16_t overruns; uint16_t windows; uint16_t early_triggers; } capture_stats_t;

/** Reset everything: IDLE, ring empty, statistics zero. @return None. */
void capture_init(void);
/** IDLE -> ARMED, any other state unchanged. @return None. */
void capture_arm(void);
/** Any state except READY -> IDLE (an open window is dropped, nothing counted). @return None. */
void capture_disarm(void);
/**
 * Feed one sample in stream order.
 * @param s       Wand-frame X, Y, Z.
 * @param trigger True when the trigger rule fired on this sample.
 * @return None.
 */
void capture_push(const int16_t s[3], bool trigger);
/** FIFO overrun seen: count it, empty the ring, drop an open window. @return None. */
void capture_overrun(void);
/** READY -> ARMED. @return true if the state was READY, else false with no change. */
bool capture_release(void);
/** @return Current state. */
capture_state_t capture_state(void);
/** @return The 150 x 3 window buffer (valid and stable while READY). */
int16_t (*capture_buffer(void))[3];
/** @return Number of samples currently in the ring (0..16). */
uint8_t capture_ring_count(void);
/**
 * Copy the statistics.
 * @param out Receives the counters.
 * @return None.
 */
void capture_stats(capture_stats_t *out);

#endif
// [END AI-GENERATED]
