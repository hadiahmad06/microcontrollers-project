// [AI-GENERATED: Claude Code]
/* TEST STAND-IN written from CONTRACTS.md C1 and the main-agent rulings only, to prove the capture
 * test harness. The real implementation is firmware/src/capture.c. Do not ship this file. */
#include <string.h>
#include "capture.h"

static int16_t s_buf[CAPTURE_LEN][3];
static int16_t s_ring[CAPTURE_RING][3];
static uint8_t s_head;       /* index of the next ring slot to write */
static uint8_t s_count;      /* samples in the ring, 0..16 */
static uint8_t s_fill;       /* samples in the buffer while CAPTURING */
static capture_state_t s_state;
static capture_stats_t s_stats;

void capture_init(void)
{
    memset(s_buf, 0, sizeof s_buf);
    memset(s_ring, 0, sizeof s_ring);
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
    if (s_state != CAPTURE_READY) {
        s_state = CAPTURE_IDLE;
        s_fill = 0u;
    }
}

/**
 * Start a window: copy the ring (oldest first), which already holds the trigger sample last.
 *
 * @return None.
 */
static void start_window(void)
{
    uint8_t i;
    for (i = 0u; i < CAPTURE_PRE + 1u; i++) {
        uint8_t src = (uint8_t)((s_head + CAPTURE_RING - CAPTURE_PRE - 1u + i) % CAPTURE_RING);
        memcpy(s_buf[i], s_ring[src], sizeof s_buf[i]);
    }
    s_fill = (uint8_t)(CAPTURE_PRE + 1u);
    s_state = CAPTURE_CAPTURING;
}

void capture_push(const int16_t s[3], bool trigger)
{
    uint8_t before = s_count;
    memcpy(s_ring[s_head], s, sizeof s_ring[0]);
    s_head = (uint8_t)((s_head + 1u) % CAPTURE_RING);
    if (s_count < CAPTURE_RING) {
        s_count++;
    }
    if (s_state == CAPTURE_ARMED && trigger) {
        if (before >= CAPTURE_PRE) {
            start_window();
        } else {
            s_stats.early_triggers++;
        }
    } else if (s_state == CAPTURE_CAPTURING) {
        memcpy(s_buf[s_fill], s, sizeof s_buf[0]);
        s_fill++;
        if (s_fill == CAPTURE_LEN) {
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
        s_state = CAPTURE_ARMED;
        s_fill = 0u;
    }
}

bool capture_release(void)
{
    if (s_state == CAPTURE_READY) {
        s_state = CAPTURE_ARMED;
        return true;
    }
    return false;
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
