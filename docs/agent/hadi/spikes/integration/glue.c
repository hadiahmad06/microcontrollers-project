// [AI-GENERATED: Claude Code]
/*
 * glue.c - SPIKE S3-1: the gesture.c glue of docs/agent/hadi/proposals/API_glue.md, built from the REAL
 * firmware modules (lis3dh, capture, features, mlp, knn, classify) plus the trigger SPIKE
 * (docs/agent/hadi/spikes/trigger/trigger.c) as a stand-in, driven by a fake LIS3DH that is fed a
 * recorded synthetic stream (fake_lis3dh.c, spike copy with fake_push_sample).
 * THROWAWAY. NOT product code. All numbers it prints are SYNTHETIC, UNVERIFIED.
 *
 * Simulated time: one loop iteration = one 10 ms sample period. The sensor pushes one sample per
 * tick; the "main loop" drains when the FIFO watermark is reached (>= 16 unread, INT0) or when
 * DRAIN_PERIOD ticks have passed since the last drain (the backstop), unless a stall is active.
 *
 * Per-sample flow (inside the drain callback):  t = trigger_feed(s); opened = capture_push(s, t);
 *   if (t && !opened) trigger_release();                    (C1b F-11)
 * After the drain: overrun handling (OVR_MODE), then if capture is READY:
 *   features_extract -> mlp_forward -> knn_query -> classify_decide -> print -> capture_release()
 *   -> trigger_release().
 *
 * Output lines (all integers, short, identical on host and sim16):
 *   M hash conf_shift default_reject         model identity
 *   R pass                                   start of pass 0 (no templates) / 1 (learn from plan)
 *   W start trig ready rel top1 margin id conf kid d1 d2 ck rad    one per READY window; kid -1 = no template
 *   A idx            trigger re-armed at sample idx          E idx   trigger fired but capture did not open
 *   G idx missing flag   gap in the delivered sample indices (missing samples, flag = OVRN seen)
 *   O idx dropped    overrun handled (dropped = an open window was dropped)
 *   L idx class count   template learned from x8_last
 *   S ...            pass statistics
 *   DONE
 * Build defines: STREAM_HDR (quoted header from make_stream.py), DRAIN_PERIOD (default 10),
 * OVR_MODE (0 = as API_glue.md: after the drain, 1 = at the first delivered sample, 2 = 1 plus
 * trigger_resync when no window was dropped and the trigger is not LOCKED).
 */
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include "sim16.h"
#include "board_axes.h"
#include "lis3dh.h"
#include "fake_lis3dh.h"
#include "capture.h"
#include "trigger.h"
#include "features.h"
#include "mlp.h"
#include "knn.h"
#include "classify.h"
#include "gesture_ids.h"
#include STREAM_HDR

#ifndef DRAIN_PERIOD
#define DRAIN_PERIOD 10u
#endif
#ifndef OVR_MODE
#define OVR_MODE 0
#endif
#define UL(x) ((unsigned long)(x))

#ifdef __AVR__
#define SGET(i, a) ((int16_t)pgm_read_word(&stream_data[(i)][(a)]))
#else
#define SGET(i, a) (stream_data[(i)][(a)])
#endif

static const lis3dh_axes_t board_axes = LIS3DH_BOARD_AXES;

/* ---- gesture.c state per API_glue.md section 1 ---- */
static uint8_t  min_conf;
static int8_t   x8_last[KNN_DIM];
static bool     x8_valid;
static trigger_t trg;

/* ---- spike-only scaffolding and statistics ---- */
static uint32_t pushed;          /* samples pushed into the fake FIFO so far = index of the next one */
static uint32_t last_idx;        /* index of the last delivered sample */
static bool     have_last;
static uint32_t trig_idx;        /* index of the trigger sample of the open/ready window */
static uint32_t ready_idx;       /* index of the sample that completed the window */
static bool     ready_seen;
static uint8_t  prev_tstate;
static bool     learned[LEARN_N > 0u ? LEARN_N : 1u];
static uint16_t st_windows, st_early, st_over, st_drop, st_gap, st_unflagged, st_drains, st_more, st_learn;
static uint8_t  max_per_drain;
static bool     learn_on;

/** Per-drain context handed to the callback. */
typedef struct {
    uint32_t base;      /**< stream index of the first delivered sample (test scaffolding: next_seq - level) */
    uint8_t  j;         /**< samples delivered so far in this call */
    uint8_t  ovr;       /**< OVRN seen at the first FIFO_SRC read of this call */
    bool     ovr_done;  /**< OVR_MODE >= 1: overrun already handled for this call */
} drain_ctx_t;

/**
 * Handle a reported FIFO overrun as API_glue.md step (2): capture_overrun(), and if an open window
 * was dropped, release the trigger (C1.6). OVR_MODE 2 additionally resyncs the trigger baseline.
 *
 * @param idx stream index used for the log line
 * @return None.
 */
static void handle_overrun(uint32_t idx)
{
    bool dropped = capture_overrun();
    st_over++;
    if (dropped) {
        trigger_release(&trg);
        st_drop++;
    } else if ((OVR_MODE == 2) && (trg.state != TRIG_LOCKED)) {
        trigger_resync(&trg);
    }
    printf("O %lu %u\n", UL(idx), (unsigned)(dropped ? 1u : 0u));
}

/**
 * Drain callback: one wand-frame sample from lis3dh_drain (see file comment for the flow).
 *
 * @param s   sample X, Y, Z
 * @param ctx drain_ctx_t of the current call
 * @return None.
 */
static void on_sample(const int16_t s[3], void *ctx)
{
    drain_ctx_t *d = (drain_ctx_t *)ctx;
    uint32_t cur = d->base + d->j;
    bool t;
    bool opened;
    d->j++;
    if ((OVR_MODE >= 1) && (d->ovr != 0u) && !d->ovr_done) {
        d->ovr_done = true;   /* the first delivered sample is the first one after the gap */
        handle_overrun(cur);
    }
    if (have_last && (cur != (last_idx + 1u))) {
        st_gap++;
        if (d->ovr == 0u) { st_unflagged++; }
        printf("G %lu %lu %u\n", UL(cur), UL(cur - last_idx - 1u), (unsigned)d->ovr);
    }
    have_last = true;
    last_idx = cur;

    t = trigger_feed(&trg, s);
    opened = capture_push(s, t);
    if (t && opened) {
        trig_idx = cur;
    }
    if (t && !opened) {                     /* C1b F-11: early or ignored trigger */
        trigger_release(&trg);
        st_early++;
        printf("E %lu\n", UL(cur));
    }
    if ((capture_state() == CAPTURE_READY) && !ready_seen) {
        ready_seen = true;
        ready_idx = cur;
    }
    if ((prev_tstate == TRIG_REARM) && (trg.state == TRIG_ARMED)) {
        printf("A %lu\n", UL(cur));
    }
    prev_tstate = trg.state;
}

/**
 * Advance simulated time by n sample periods WITHOUT servicing the FIFO (the main loop is busy).
 *
 * @param n number of samples the sensor produces meanwhile
 * @return None.
 */
static void sensor_run(uint16_t n)
{
    uint16_t i;
    for (i = 0u; i < n; i++) {
        if (pushed < STREAM_N) {
            int16_t s[3];
            s[0] = SGET(pushed, 0); s[1] = SGET(pushed, 1); s[2] = SGET(pushed, 2);
            fake_push_sample(s);
            pushed++;
        }
    }
}

/**
 * Classify the READY window as gesture_classify() would (API_glue.md section 2), print one line,
 * release the buffer and the trigger.
 *
 * @return None.
 */
static void process_ready(void)
{
    mlp_model_info_t info;
    int16_t feat[FEAT_COUNT];
    int32_t logits[MLP_N_CLASSES];
    int32_t margin = 0;
    knn_result_t kr;
    bool have;
    uint8_t top1, conf = 0u;
    int8_t id;
    uint8_t p;

    mlp_model_info(&info);
    features_extract(capture_buffer(), feat);
    top1 = mlp_forward(feat, x8_last, logits, &margin);
    x8_valid = true;
    have = knn_query(x8_last, &kr);
    id = classify_decide(top1, margin, info.conf_shift, have ? &kr : 0, min_conf, &conf);
    sensor_run(CLASSIFY_BUSY);              /* main loop busy: the FIFO keeps filling, nobody drains */
    if (capture_release()) {
        trigger_release(&trg);
    }
    st_windows++;
    printf("W %lu %lu %lu %lu %u %ld %d %u %d %u %u %u %u\n", UL(trig_idx - 15u), UL(trig_idx), UL(ready_idx),
           UL(last_idx), (unsigned)top1, (long)margin, (int)id, (unsigned)conf,
           have ? (int)kr.kid : -1, have ? (unsigned)kr.d1 : 0u, have ? (unsigned)kr.d2 : 0u,
           have ? (unsigned)kr.c_k : 0u, have ? (unsigned)kr.radius : 0u);
    ready_seen = false;
    /* gesture_learn(): uses x8_last, the raw buffer is not needed any more (C1.12 via x8) */
    if (x8_valid) {
        for (p = 0u; p < LEARN_N; p++) {
            if (!learned[p] && (trig_idx + 5u >= learn_onset[p]) && (trig_idx <= learn_onset[p] + 40u) && (learn_on)) {
                int8_t n = knn_learn(learn_id[p], x8_last);
                learned[p] = true;
                st_learn++;
                printf("L %lu %u %d\n", UL(trig_idx), (unsigned)learn_id[p], (int)n);
            }
        }
    }
}

/**
 * One gesture_poll() service step: drain once, handle overrun, classify when READY.
 *
 * @return true if the drain stopped at its 4-burst bound with data left (call again next tick)
 */
static bool poll_once(void)
{
    drain_ctx_t d;
    bool more = false;
    int16_t n;
    d.base = pushed - (uint32_t)fake_fifo_level();
    d.j = 0u;
    d.ovr = 0u;
    d.ovr_done = false;
    n = lis3dh_drain(on_sample, &d, &d.ovr, &more);   /* the driver writes d.ovr before the first callback */
    st_drains++;
    if (n < 0) {
        printf("BUSERR %d\n", (int)n);
        sim16_exit(1);
    }
    if ((uint8_t)n > max_per_drain) { max_per_drain = (uint8_t)n; }
    if (more) { st_more++; }
    if ((OVR_MODE == 0) && (d.ovr != 0u)) {   /* API_glue.md order: after the drain */
        handle_overrun(last_idx);
    }
    if (capture_state() == CAPTURE_READY) {
        process_ready();
    }
    return more;
}

/**
 * True while a configured stall is active (the main loop does not service the FIFO).
 *
 * @return true if the sensor clock is inside a stall interval
 */
static bool stalled(void)
{
#if STALL_N > 0
    uint8_t k;
    for (k = 0u; k < STALL_N; k++) {
        if ((pushed >= stall_at[k]) && (pushed < (stall_at[k] + stall_len[k]))) {
            return true;
        }
    }
#endif
    return false;
}

/**
 * Run the whole stream once: gesture_init() per API_glue.md, then the simulated main loop.
 *
 * @param pass 0 = no templates, 1 = learn one template for each class of the learn plan
 * @return None.
 */
static void run_pass(uint8_t pass)
{
    mlp_model_info_t info;
    uint32_t tick;
    uint16_t since = 0u;
    bool more = false;
    uint8_t p;

    printf("R %u\n", (unsigned)pass);
    learn_on = (pass != 0u);
    pushed = 0u; have_last = false; last_idx = 0u; trig_idx = 0u; ready_idx = 0u; ready_seen = false;
    st_windows = st_early = st_over = st_drop = st_gap = st_unflagged = st_drains = st_more = st_learn = 0u;
    max_per_drain = 0u; x8_valid = false;
    for (p = 0u; p < LEARN_N; p++) { learned[p] = false; }

    /* gesture_init(): mlp_model_info, knn_reset, capture_init, trigger_init, lis3dh_init, capture_arm */
    mlp_model_info(&info);
    min_conf = info.default_reject;
    knn_reset();
    capture_init();
    trigger_init(&trg, 0);                  /* C1b defaults: S = 3, N = 2, quiet 30, warm 32, 250 mg */
    fake_reset(0x18u);
#ifdef FSS_WRAP
    fake_set_fss32(FAKE_FSS32_WRAP);
#endif
    if (lis3dh_init(&board_axes) != LIS3DH_OK) {
        printf("INITERR\n");
        sim16_exit(1);
    }
    capture_arm();
    prev_tstate = trg.state;

    for (tick = 0u; tick < (STREAM_N + 40u); tick++) {
        bool wtm;
        sensor_run(1u);                     /* the sensor produces one sample */
        since++;
        if (stalled()) {
            continue;
        }
        wtm = (fake_fifo_level() >= 16u);   /* INT0 flag: watermark FTH = 15 -> 16 unread */
        if (wtm || (since >= DRAIN_PERIOD) || more) {
            more = poll_once();
            since = 0u;
        }
    }
    while (poll_once()) { }                 /* flush */
    printf("S samples %lu windows %u early %u overruns %u dropped %u gaps %u unflagged %u drains %u more %u "
           "learned %u maxdrain %u fifolost %u knn %u\n",
           UL(pushed), st_windows, st_early, st_over, st_drop, st_gap, st_unflagged, st_drains, st_more,
           st_learn, (unsigned)max_per_drain, (unsigned)fake_lost(), (unsigned)knn_total());
}

/**
 * Entry point: print the model identity, run pass 0 (no templates) and pass 1 (learn from the plan).
 *
 * @return 0 (via sim16_exit)
 */
int main(void)
{
    mlp_model_info_t info;
    sim16_init();
    mlp_model_info(&info);
    printf("M %08lx %u %u\n", UL(info.model_hash), (unsigned)info.conf_shift, (unsigned)info.default_reject);
    run_pass(0u);
    run_pass(1u);
    printf("DONE\n");
    sim16_exit(0);
    return 0;
}
// [END AI-GENERATED]
