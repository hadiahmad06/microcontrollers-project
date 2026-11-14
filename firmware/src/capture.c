// [AI-GENERATED: Claude Code]
/**
 * @file capture.c
 * @brief Sample-level gesture capture (ticket WP1-a; contracts C0, C1). See capture.h.
 *
 * Design: the ring always tracks the stream (it is pushed in every state, so the 15 samples before
 * a trigger are available), is emptied on an overrun (sample gap), and is not touched by
 * arm/disarm/release. The trigger flag is honoured only in ARMED.
 */
#include "capture.h"

#define RING_MASK ((uint8_t)(CAPTURE_RING - 1u))  /* CAPTURE_RING is a power of two */

static int16_t         s_buf[CAPTURE_LEN][3];   /* window buffer, sample-major, 900 B */
static int16_t         s_ring[CAPTURE_RING][3]; /* pre-trigger ring, 96 B */
static uint8_t         s_head;                  /* ring index of the next write (= oldest when full) */
static uint8_t         s_count;                 /* valid ring entries 0..CAPTURE_RING */
static uint8_t         s_fill;                  /* samples stored in s_buf while CAPTURING */
static capture_state_t s_state;
static capture_stats_t s_stats;

/**
 * Push one sample into the ring, overwriting the oldest entry when full.
 * @param s three int16_t values to store
 */
static void ring_push(const int16_t s[3])
{
    s_ring[s_head][0] = s[0];
    s_ring[s_head][1] = s[1];
    s_ring[s_head][2] = s[2];
    s_head = (uint8_t)((s_head + 1u) & RING_MASK);
    if (s_count < CAPTURE_RING) {
        s_count++;
    }
}

/** Copy the whole (full) ring, oldest first and trigger sample last, to the buffer start; open the window. */
static void window_start(void)
{
    uint8_t i;
    uint8_t idx = (uint8_t)((s_head - s_count) & RING_MASK); /* oldest entry */

    for (i = 0u; i < s_count; i++) {
        s_buf[i][0] = s_ring[idx][0];
        s_buf[i][1] = s_ring[idx][1];
        s_buf[i][2] = s_ring[idx][2];
        idx = (uint8_t)((idx + 1u) & RING_MASK);
    }
    s_fill = s_count;
    s_state = CAPTURE_CAPTURING;
}

void capture_init(void)
{
    s_head = 0u;
    s_count = 0u;
    s_fill = 0u;
    s_state = CAPTURE_IDLE;
    s_stats.overruns = 0u;
    s_stats.windows = 0u;
    s_stats.early_triggers = 0u;
}

void capture_arm(void)
{
    if (s_state == CAPTURE_IDLE) {
        s_state = CAPTURE_ARMED;
    }
}

void capture_disarm(void)
{
    if (s_state == CAPTURE_ARMED || s_state == CAPTURE_CAPTURING) {
        s_fill = 0u;
        s_state = CAPTURE_IDLE;
    }
}

void capture_push(const int16_t s[3], bool trigger)
{
    ring_push(s);

    if (s_state == CAPTURE_ARMED && trigger) {
        if (s_count >= CAPTURE_RING) {   /* trigger sample + CAPTURE_PRE earlier ones present */
            window_start();
        } else {
            s_stats.early_triggers++;
        }
    } else if (s_state == CAPTURE_CAPTURING) {
        s_buf[s_fill][0] = s[0];
        s_buf[s_fill][1] = s[1];
        s_buf[s_fill][2] = s[2];
        s_fill++;
        if (s_fill >= CAPTURE_LEN) {
            s_state = CAPTURE_READY;
            s_stats.windows++;
        }
    }
}

void capture_overrun(void)
{
    s_stats.overruns++;
    s_count = 0u;
    s_head = 0u;
    if (s_state == CAPTURE_CAPTURING) {
        s_fill = 0u;
        s_state = CAPTURE_ARMED;
    }
}

bool capture_release(void)
{
    if (s_state != CAPTURE_READY) {
        return false;
    }
    s_state = CAPTURE_ARMED;
    return true;
}

capture_state_t capture_state(void)
{
    return s_state;
}

int16_t (*capture_buffer(void))[3]
{
    return s_buf;
}

uint8_t capture_ring_count(void)
{
    return s_count;
}

void capture_stats(capture_stats_t *out)
{
    *out = s_stats;
}
// [END AI-GENERATED]
