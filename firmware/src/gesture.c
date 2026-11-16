// [AI-GENERATED: Claude Code]
/**
 * @file gesture.c
 * @brief Public gesture API glue (ticket 3.7). Composes lis3dh, capture, trigger, features, mlp, knn, classify
 *        and c2_stream; the only board dependencies are gesture_port.h (G1) and lis3dh_hal.h (via lis3dh.c).
 *
 * WORKING ASSUMPTION: open_questions Q1 (C2), Q2 (trigger C1b), Q3 (keep C1.6), not decided.
 *
 * Reference composition (our own code, cited): docs/agent/hadi/spikes/integration/glue.c (spike S3-1, the
 * drain callback, the overrun-first order and the release protocol) and docs/agent/hadi/proposals/API_glue.md.
 * No code was borrowed from outside the project.
 *
 * Rules kept here: overrun is handled once, before the first delivered sample (S3-1 finding 1); the trigger is
 * released only when capture dropped or released a window (S3-1 finding 3); an overrun while no window is open
 * only counts (C1.6) and trigger_resync() is never called, because it unlocks a LOCKED trigger (S3-1 finding 2).
 * The WINDOW buffer stays locked until its frame's last byte is queued (C2 section 3).
 *
 * Build option -DGESTURE_BRINGUP_SAMPLES=1 (C2 section 10, never in the demo build): every drained sample is
 * sent in SAMPLES chunks of 16 rows (only while gesture_stream_raw(true) is on), no trigger, capture or
 * classification; the two chunk buffers are the first 32 rows of the (otherwise unused) capture buffer.
 *
 * C99, fixed-width types, no float, no malloc, no blocking.
 */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "gesture.h"
#include "gesture_port.h"
#include "board_axes.h"
#include "lis3dh.h"
#include "capture.h"
#include "trigger.h"
#include "features.h"
#include "mlp.h"
#include "knn.h"
#include "classify.h"
#include "c2_stream.h"

#define GESTURE_BACKSTOP_MS 50u    /* drain at least this often even without the watermark flag (C1.4) */
#define GESTURE_HELLO_MS    2000u  /* HELLO beacon period while streaming (C2) */
#define GESTURE_BOOT_LEN    25u    /* "GM_MODEL_HASH=0x" + 8 hex digits + '\n' */
#define GESTURE_CHUNK_ROWS  16u    /* rows per SAMPLES frame (bring-up) */

/* Flag bits in fl. */
#define F_INIT      0x01u  /* gesture_init succeeded */
#define F_STREAM    0x02u  /* gesture_stream_raw(true) */
#define F_X8        0x04u  /* x8_last holds a window not yet learned */
#define F_CLASSIFED 0x08u  /* the READY window was classified */
#define F_REJ_USER  0x10u  /* gesture_set_reject was called: keep it over the model default */
#define F_HELLO     0x20u  /* a HELLO is pending (stream just switched on) */
#define F_WIN_PEND  0x40u  /* a WINDOW frame is waiting for the transmitter */
#define F_MORE      0x80u  /* the last drain stopped at its burst bound: drain again at once */

/* ---- state (static RAM) ---- */
static uint8_t           fl;                /* F_* flags */
static uint8_t           min_conf;          /* reject threshold */
static volatile uint8_t  events;            /* GESTURE_EVT_* bits, only the main loop writes */
static uint16_t          last_drain_ms;     /* port_millis at the last drain */
static uint16_t          last_hello_ms;     /* port_millis at the last HELLO start */
static c2_tx_t           tx;                /* C2 sender (module state) */
static char              txt[GESTURE_BOOT_LEN + 1u]; /* ASCII line in flight (boot line, bring-up OVR line) */
#ifndef GESTURE_BRINGUP_SAMPLES
static trigger_t         trg;               /* motion trigger (module state) */
static int8_t            x8_last[KNN_DIM];  /* x8 of the last classified window (C1.12) */
static uint8_t           win_events;        /* per-window event latch */
static c2_window_meta_t  win_meta;          /* metadata of the pending WINDOW frame */
#else
static uint8_t           bu_fill;           /* rows in the buffer being filled */
static uint8_t           bu_cur;            /* buffer being filled (0/1) */
static uint8_t           bu_full;           /* bit i: buffer i is full or in flight */
static uint8_t           bu_send;           /* next buffer to send (0/1) */
static uint8_t           bu_sending;        /* 1 while a SAMPLES frame is in flight */
static uint8_t           bu_ovr_pend;       /* an "OVR n" line is waiting */
static uint16_t          bu_ovr_total;      /* overruns seen (plus drains that lost rows) */
#endif

/** Per-drain context shared with the callback. */
typedef struct {
    uint8_t ovr;      /**< OVRN seen at the first FIFO_SRC read of this drain (written by the driver) */
    bool    handled;  /**< the overrun was already handled for this drain */
#ifdef GESTURE_BRINGUP_SAMPLES
    bool    lost;     /**< rows were dropped because both chunk buffers were busy */
#endif
} drain_ctx_t;

static const lis3dh_axes_t board_axes = LIS3DH_BOARD_AXES;

/**
 * Write the boot line "GM_MODEL_HASH=0x%08lX\n" (upper-case hex, no printf) into txt.
 *
 * @param hash model hash
 * @return None.
 */
static void format_boot_line(uint32_t hash)
{
    static const char prefix[] = "GM_MODEL_HASH=0x";
    static const char hex[] = "0123456789ABCDEF";
    uint8_t i;
    for (i = 0u; i < 16u; i++) {
        txt[i] = prefix[i];
    }
    for (i = 0u; i < 8u; i++) {
        uint8_t nib = (uint8_t)((hash >> (28u - (4u * i))) & 0x0Fu);
        txt[16u + i] = hex[nib];
    }
    txt[24] = '\n';
    txt[25] = '\0';
}

/**
 * Tell whether a HELLO is due: pending after a stream switch-on, or 2000 ms since the last one.
 *
 * @param now port_millis value
 * @return true if a HELLO should start as soon as the transmitter is idle
 */
static bool hello_due(uint16_t now)
{
    return ((fl & F_STREAM) != 0u) &&
           (((fl & F_HELLO) != 0u) || ((uint16_t)(now - last_hello_ms) >= GESTURE_HELLO_MS));
}

/**
 * Start a HELLO frame from the model identity and record the time.
 *
 * @param now port_millis value
 * @return None.
 */
static void start_hello(uint16_t now)
{
    mlp_model_info_t info;
    c2_hello_t h;
    mlp_model_info(&info);
    h.odr_hz = info.odr_hz;
    h.range_g = info.range_g;
    h.n_samples = (uint8_t)CAPTURE_LEN;
    h.pre_trig = (uint8_t)CAPTURE_PRE;
    h.feature_ver = info.feature_version;
    h.model_hash = info.model_hash;
    if (c2_tx_start_hello(&tx, &h)) {
        fl = (uint8_t)(fl & (uint8_t)~F_HELLO);
        last_hello_ms = now;
    }
}

#ifndef GESTURE_BRINGUP_SAMPLES
/**
 * Handle a reported FIFO overrun (C1.6): capture_overrun() drops an open window and then the trigger must be
 * released; while no window is open it only counts. trigger_resync() is never called (S3-1 finding 2).
 *
 * @return None.
 */
static void handle_overrun(void)
{
    if (capture_overrun()) {
        trigger_release(&trg);
    }
}

/**
 * Drain callback, one wand-frame sample (glue.c spike on_sample): overrun first, then trigger, capture, release
 * of an ignored trigger (C1b F-11), and the per-window event latch reset when a window opens.
 *
 * @param s   sample X, Y, Z
 * @param ctx drain_ctx_t of the current drain
 * @return None.
 */
static void on_sample(const int16_t s[3], void *ctx)
{
    drain_ctx_t *d = (drain_ctx_t *)ctx;
    bool t;
    bool opened;
    if ((d->ovr != 0u) && !d->handled) {
        d->handled = true;               /* the first delivered sample is the first one after the gap */
        handle_overrun();
    }
    t = trigger_feed(&trg, s);
    opened = capture_push(s, t);
    if (opened) {
        win_events = 0u;
        fl = (uint8_t)(fl & (uint8_t)~F_CLASSIFED);
    }
    if (t && !opened) {
        trigger_release(&trg);
    }
}
#else
/**
 * Pointer to chunk buffer i: rows 0..15 or 16..31 of the capture buffer (unused in the bring-up build).
 *
 * @param i buffer number 0 or 1
 * @return first row of the buffer
 */
static int16_t (*chunk_buf(uint8_t i))[3]
{
    return capture_buffer() + (i != 0u ? GESTURE_CHUNK_ROWS : 0u);
}

/**
 * Bring-up drain callback: append the sample to the current chunk; when it is full switch to the other buffer.
 * If both buffers are busy the row is dropped and counted as an overrun once per drain.
 *
 * @param s   sample X, Y, Z
 * @param ctx drain_ctx_t of the current drain
 * @return None.
 */
static void on_sample(const int16_t s[3], void *ctx)
{
    drain_ctx_t *d = (drain_ctx_t *)ctx;
    int16_t (*row)[3];
    if ((d->ovr != 0u) && !d->handled) {
        d->handled = true;
        bu_ovr_total++;
        bu_ovr_pend = 1u;
    }
    if ((fl & F_STREAM) == 0u) {
        return;
    }
    if ((bu_full & (uint8_t)(1u << bu_cur)) != 0u) {
        if (!d->lost) {
            d->lost = true;
            bu_ovr_total++;
            bu_ovr_pend = 1u;
        }
        return;
    }
    row = chunk_buf(bu_cur) + bu_fill;
    (*row)[0] = s[0];
    (*row)[1] = s[1];
    (*row)[2] = s[2];
    bu_fill++;
    if (bu_fill >= GESTURE_CHUNK_ROWS) {
        bu_full = (uint8_t)(bu_full | (uint8_t)(1u << bu_cur));
        bu_cur = (uint8_t)(bu_cur ^ 1u);
        bu_fill = 0u;
    }
}

/**
 * Write "OVR <n>\n" (decimal) into txt.
 *
 * @param n total overruns
 * @return None.
 */
static void format_ovr_line(uint16_t n)
{
    char dig[5];
    uint8_t k = 0u;
    uint8_t i = 0u;
    txt[i++] = 'O';
    txt[i++] = 'V';
    txt[i++] = 'R';
    txt[i++] = ' ';
    do {
        dig[k++] = (char)((uint8_t)'0' + (uint8_t)(n % 10u));
        n = (uint16_t)(n / 10u);
    } while (n != 0u);
    while (k != 0u) {
        txt[i++] = dig[--k];
    }
    txt[i++] = '\n';
    txt[i] = '\0';
}
#endif

/**
 * Drain the FIFO once through the driver and handle a pending overrun even if no sample was delivered.
 *
 * @return None.
 */
static void drain_once(void)
{
    drain_ctx_t d;
    bool more = false;
    int16_t n;
    d.ovr = 0u;
    d.handled = false;
#ifdef GESTURE_BRINGUP_SAMPLES
    d.lost = false;
#endif
    n = lis3dh_drain(on_sample, &d, &d.ovr, &more);
    if (((n < 0) || (d.ovr != 0u)) && !d.handled) {
        /* overrun reported with no sample delivered, or a bus error: treat as a gap in the stream */
#ifndef GESTURE_BRINGUP_SAMPLES
        handle_overrun();
#else
        bu_ovr_total++;
        bu_ovr_pend = 1u;
#endif
    }
    fl = (uint8_t)(more ? (fl | F_MORE) : (fl & (uint8_t)~F_MORE));
}

/**
 * Transmit step: start the next frame or text if the sender is idle, pump at most C2_PUMP_MAX bytes into the
 * port TX ring, and give the capture buffer back when a WINDOW frame has been fully queued.
 *
 * @param now port_millis value
 * @return None.
 */
static void tx_service(uint16_t now)
{
    uint8_t tmp[C2_PUMP_MAX];
    uint8_t n;
#ifndef GESTURE_BRINGUP_SAMPLES
    if (!c2_tx_busy(&tx)) {
        if ((fl & F_WIN_PEND) != 0u) {
            /* explicit cast: C99 -pedantic has no implicit int16_t (*)[3] -> const int16_t (*)[3] (T-c2txR F1) */
            if (c2_tx_start_window(&tx, &win_meta, (const int16_t (*)[3])capture_buffer())) {
                fl = (uint8_t)(fl & (uint8_t)~F_WIN_PEND);
            }
        } else if (hello_due(now)) {
            start_hello(now);
        }
    }
#else
    if (!c2_tx_busy(&tx)) {
        if ((bu_ovr_pend != 0u) && (bu_full == 0u)) {   /* 3.7F F3: text only between chunks, at the gap */
            format_ovr_line(bu_ovr_total);
            if (c2_tx_start_text(&tx, txt)) {
                bu_ovr_pend = 0u;
            }
        } else if (hello_due(now)) {
            start_hello(now);
        } else if ((bu_full & (uint8_t)(1u << bu_send)) != 0u) {
            /* explicit cast, same reason (T-c2txR F1) */
            if (c2_tx_start_samples(&tx, (const int16_t (*)[3])chunk_buf(bu_send))) {
                bu_sending = 1u;
            }
        }
    }
#endif
    n = c2_tx_pump(&tx, tmp, port_tx_room());
    if (n != 0u) {
        port_tx_write(tmp, n);
    }
#ifndef GESTURE_BRINGUP_SAMPLES
    if (c2_tx_take_release(&tx) && capture_release()) {
        trigger_release(&trg);
    }
#else
    if ((bu_sending != 0u) && !c2_tx_busy(&tx)) {   /* the chunk's last byte is queued: free the buffer */
        bu_full = (uint8_t)(bu_full & (uint8_t)~(uint8_t)(1u << bu_send));
        bu_send = (uint8_t)(bu_send ^ 1u);
        bu_sending = 0u;
    }
#endif
}

int8_t gesture_init(uint8_t odr_hz, uint8_t range_g)
{
    mlp_model_info_t info;
    int8_t r;
    fl = (uint8_t)(fl & F_REJ_USER);   /* keep only the user's reject choice, drop everything else */
    events = 0u;
    mlp_model_info(&info);
    if ((odr_hz != info.odr_hz) || (range_g != info.range_g)) {
        return -1;                      /* C4 D6: configuration differs from the model */
    }
    if ((fl & F_REJ_USER) == 0u) {
        min_conf = info.default_reject;
    }
    knn_reset();
    capture_init();
    c2_tx_init(&tx);
#ifndef GESTURE_BRINGUP_SAMPLES
    trigger_init(&trg, NULL);           /* C1b defaults: S = 3, debounce 2, quiet 30, warm-up 32, 250 mg */
    win_events = 0u;
#else
    bu_fill = 0u; bu_cur = 0u; bu_full = 0u; bu_send = 0u; bu_sending = 0u; bu_ovr_pend = 0u; bu_ovr_total = 0u;
#endif
    r = lis3dh_init(&board_axes);
    if (r != LIS3DH_OK) {
        return -2;                      /* LIS3DH_ERR_SENSOR and LIS3DH_ERR_BUS both: sensor not usable (gap 1) */
    }
#ifndef GESTURE_BRINGUP_SAMPLES
    capture_arm();
#endif
    last_drain_ms = port_millis();
    last_hello_ms = last_drain_ms;
    format_boot_line(info.model_hash);  /* C4 D6, C2 section 9: ASCII only between frames */
    (void)c2_tx_start_text(&tx, txt);   /* tx is idle after c2_tx_init, so this cannot fail */
    fl = (uint8_t)(fl | F_INIT);
    return 0;
}

void gesture_set_trigger(uint16_t threshold_mg)
{
#ifndef GESTURE_BRINGUP_SAMPLES
    if ((fl & F_INIT) != 0u) {
        trigger_set_threshold_mg(&trg, threshold_mg);
    }
#else
    (void)threshold_mg;
#endif
}

bool gesture_poll(void)
{
    uint16_t now;
    bool fifo_flag;
    if ((fl & F_INIT) == 0u) {
        return false;
    }
    now = port_millis();
    /* (1) drain: INT0 watermark flag (always read, it is read-and-clear), the 50 ms backstop, or more data left */
    fifo_flag = port_take_fifo_flag();
    if ((fl & F_MORE) != 0u) {
        tx_service(now);   /* 3.7F F5: the last drain left data; pump the TX ring before the next long drain */
    }
    if (fifo_flag || ((fl & F_MORE) != 0u) || ((uint16_t)(now - last_drain_ms) >= GESTURE_BACKSTOP_MS)) {
#ifdef GESTURE_BRINGUP_SAMPLES
        if ((bu_full & (uint8_t)(1u << bu_cur)) != 0u) {
            fl = (uint8_t)(fl | F_MORE);   /* both chunk buffers busy: leave the rows in the FIFO, retry next call */
        } else
#endif
        {
            drain_once();
            last_drain_ms = now;
        }
    }
    /* (2) click: INT1 flag, double click confirmed by CLICK_SRC */
    if (port_take_click_flag() && (lis3dh_read_click() == 1)) {
        events = (uint8_t)(events | GESTURE_EVT_DOUBLE_TAP);
#ifndef GESTURE_BRINGUP_SAMPLES
        {
            capture_state_t st = capture_state();
            if ((st == CAPTURE_CAPTURING) || (st == CAPTURE_READY)) {
                win_events = (uint8_t)(win_events | GESTURE_EVT_DOUBLE_TAP);
            }
        }
#endif
    }
    /* (3) transmit */
    tx_service(now);
    /* (4) a window is ready for the application */
#ifndef GESTURE_BRINGUP_SAMPLES
    return (capture_state() == CAPTURE_READY) && ((fl & F_CLASSIFED) == 0u);
#else
    return false;
#endif
}

int8_t gesture_classify(uint8_t *confidence)
{
#ifndef GESTURE_BRINGUP_SAMPLES
    mlp_model_info_t info;
    int16_t feat[FEAT_COUNT];
    int32_t logits[MLP_N_CLASSES];
    int32_t margin = 0;
    knn_result_t kr;
    uint8_t top1;
    uint8_t conf = 0u;
    int8_t id;
    bool have;
    if (confidence != NULL) {
        *confidence = 0u;
    }
    if (((fl & F_INIT) == 0u) || (capture_state() != CAPTURE_READY) || ((fl & F_CLASSIFED) != 0u)) {
        return GESTURE_UNKNOWN;
    }
    mlp_model_info(&info);
    features_extract(capture_buffer(), feat);
    top1 = mlp_forward(feat, x8_last, logits, &margin);
    fl = (uint8_t)(fl | F_X8 | F_CLASSIFED);
    have = knn_query(x8_last, &kr);
    id = classify_decide(top1, margin, info.conf_shift, have ? &kr : NULL, min_conf, &conf);
    if (confidence != NULL) {
        *confidence = conf;
    }
    if ((fl & F_STREAM) != 0u) {
        /* C2 section 3: the frame is sent from the locked buffer; tx_service releases it after the last byte */
        capture_stats_t cs;
        capture_stats(&cs);
        win_meta.trig_idx = (uint8_t)CAPTURE_PRE;
        win_meta.overruns = cs.overruns;
        win_meta.model_hash = info.model_hash;
        win_meta.flags = 1u;
        win_meta.class_id = id;
        win_meta.conf = conf;
        win_meta.events = win_events;
        fl = (uint8_t)(fl | F_WIN_PEND);
    } else if (capture_release()) {
        trigger_release(&trg);
    }
    return id;
#else
    if (confidence != NULL) {
        *confidence = 0u;
    }
    return GESTURE_UNKNOWN;
#endif
}

int8_t gesture_learn(uint8_t class_id)
{
#ifndef GESTURE_BRINGUP_SAMPLES
    int8_t r;
    if (((fl & F_INIT) == 0u) || ((fl & F_X8) == 0u)) {
        return GESTURE_LEARN_ERR_NO_WINDOW;
    }
    r = knn_learn(class_id, x8_last);
    if (r > 0) {
        fl = (uint8_t)(fl & (uint8_t)~F_X8);   /* API_glue risk note: a window can be learned only once */
    }
    return r;
#else
    (void)class_id;
    return GESTURE_LEARN_ERR_NO_WINDOW;
#endif
}

void gesture_set_reject(uint8_t min_conf_new)
{
    min_conf = min_conf_new;
    fl = (uint8_t)(fl | F_REJ_USER);
}

void gesture_stream_raw(bool on)
{
    if ((fl & F_INIT) == 0u) {
        return;
    }
    if (on && ((fl & F_STREAM) == 0u)) {
        fl = (uint8_t)(fl | F_STREAM | F_HELLO);   /* a HELLO goes out as soon as the sender is idle */
#ifdef GESTURE_BRINGUP_SAMPLES
        bu_fill = 0u;   /* 3.7F F4: drop a stale partial chunk; the filling buffer is never in flight (full bit clear) */
#endif
    } else if (!on) {
        fl = (uint8_t)(fl & (uint8_t)~(F_STREAM | F_HELLO));   /* a pending or running WINDOW still completes */
    }
}

uint8_t gesture_events(void)
{
    uint8_t e = events;     /* only the main loop writes events, so this read-and-clear cannot lose a bit */
    events = 0u;
    return e;
}
// [END AI-GENERATED]
