// [AI-GENERATED: Claude Code]
/*
 * test_lis3dh.c - tests for lis3dh.c (ticket WP1-bT), written from the SPEC (CONTRACTS C1.1,
 * C1.3, C1.4, C1.10, C6.1 and the main-agent rulings), never from the implementation.
 * Pure C: prints "PASS <group>" / "FAIL <group>" lines and exits 0 only if every group passed.
 * Built for the host (32-bit int) and for sim16 (avr-gcc, 16-bit int, run under simavr).
 *
 * Oracles here are independent of the driver: the sample value is computed by floor division,
 * not by ">>", and the drain schedule comes from a counting model of the FIFO (model_drain).
 *
 * Reading of C1.4 used by default (DRAIN_MODEL A, "FSS < 16 at the re-read" is the stop test):
 *   F = read FIFO_SRC; if FSS == 0 stop; loop { burst min(FSS,16); re-read FIFO_SRC;
 *   if FSS < 16 stop; if 4 bursts done: more = true, stop }.   => FIFO_SRC reads = bursts + 1.
 * DRAIN_MODEL_B (make DRAIN_MODEL=B) instead keeps draining while FSS > 0 after the re-read.
 *
 * Assumptions that the spec does not pin down (reported to the main agent as open questions):
 *   - axis table meaning: out[i] = sign[i] * in[src[i]]
 *   - lis3dh_address() returns the 7-bit address; lis3dh_read_click() returns > 0 for a double
 *     click (IA|DCLICK pending), 0 for none, LIS3DH_ERR_BUS on a bus error
 *   - config registers CLICK_CFG 0x38, CLICK_THS 0x3A, TIME_LIMIT 0x3B, TIME_LATENCY 0x3C,
 *     TIME_WINDOW 0x3D (LIS3DH datasheet register map)
 */
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include "sim16.h"
#include "fake_lis3dh.h"
#include "lis3dh.h"

/* ---------------------------------------------------------------- tiny test framework */

static uint16_t g_fails;
static uint16_t g_group_start;
static uint16_t g_c1, g_c2;          /* case parameters printed with a failure */
static const char *g_group = "";

/**
 * Record one check result; prints the first few failures of a group.
 *
 * @param ok Non-zero if the check passed.
 * @param line Source line of the check.
 * @param expr Source text of the check (empty on sim16 to save RAM).
 * @return None.
 */
static void check(uint8_t ok, uint16_t line, const char *expr)
{
    if (!ok) {
        g_fails++;
        if ((uint16_t)(g_fails - g_group_start) <= 8u) {
            printf("  FAIL %s line %u (case %u,%u) %s\n", g_group, (unsigned)line,
                   (unsigned)g_c1, (unsigned)g_c2, expr);
        }
    }
}
#ifdef __AVR__
#define CHECK(c) check((uint8_t)((c) ? 1 : 0), (uint16_t)__LINE__, "")
#else
#define CHECK(c) check((uint8_t)((c) ? 1 : 0), (uint16_t)__LINE__, #c)
#endif

/**
 * Start a named test group.
 *
 * @param name Group name printed with its result.
 * @return None.
 */
static void group_begin(const char *name)
{
    g_group = name;
    g_group_start = g_fails;
    g_c1 = 0u;
    g_c2 = 0u;
}

/**
 * Finish the current group and print its PASS / FAIL line.
 *
 * @return None.
 */
static void group_end(void)
{
    if (g_fails == g_group_start) {
        printf("PASS %s\n", g_group);
    } else {
        printf("FAIL %s (%u checks failed)\n", g_group, (unsigned)(g_fails - g_group_start));
    }
}

/* ---------------------------------------------------------------- oracles */

static const lis3dh_axes_t AX_ID   = {{0u, 1u, 2u}, {1, 1, 1}};
static const lis3dh_axes_t AX_SWAP = {{1u, 0u, 2u}, {1, -1, 1}};   /* X<-Y, Y<- -X, Z<-Z */
static const lis3dh_axes_t AX_CYC  = {{1u, 2u, 0u}, {-1, 1, -1}};  /* 3-cycle + flips */

/**
 * Reference sample value: the 12-bit signed number held left-justified in a 16-bit register word.
 * Floor division, deliberately not ">>" (which is what the driver uses).
 *
 * @param w Raw 16-bit word (OUT_x_H:OUT_x_L).
 * @return Value in [-2048, 2047].
 */
static int16_t ref_value(uint16_t w)
{
    int32_t s = (w >= 0x8000u) ? ((int32_t)w - 65536L) : (int32_t)w;
    return (int16_t)((s >= 0) ? (s / 16L) : -((-s + 15L) / 16L));
}

/**
 * Reference axis remap: out[i] = sign[i] * in[src[i]].
 *
 * @param in Sensor-frame values.
 * @param ax Axis table.
 * @param out Wand-frame values.
 * @return None.
 */
static void ref_remap(const int16_t in[3], const lis3dh_axes_t *ax, int16_t out[3])
{
    uint8_t i;
    for (i = 0u; i < 3u; i++) {
        out[i] = (int16_t)((int32_t)ax->sign[i] * (int32_t)in[ax->src[i]]);
    }
}

/**
 * Lay three words out as one burst group (X_L X_H Y_L Y_H Z_L Z_H).
 *
 * @param w Words for X, Y, Z.
 * @param raw 6-byte result.
 * @return None.
 */
static void make_raw(const uint16_t w[3], uint8_t raw[6])
{
    uint8_t i;
    for (i = 0u; i < 3u; i++) {
        raw[2u * i] = (uint8_t)(w[i] & 0xFFu);
        raw[2u * i + 1u] = (uint8_t)(w[i] >> 8);
    }
}

/* ---------------------------------------------------------------- init tests */

typedef struct { uint8_t reg, val; } regval_t;

/* Init order from the main-agent ruling (after the WHO_AM_I probe). */
static const regval_t EXP_W[] = {
    {0x20u, 0x00u}, {0x23u, 0x18u}, {0x22u, 0x06u}, {0x25u, 0x80u},
    {0x38u, 0x2Au}, {0x3Au, 0xB0u}, {0x3Bu, 0x04u}, {0x3Cu, 0x10u}, {0x3Du, 0x30u},
    {0x24u, 0x40u}, {0x2Eu, 0x00u}, {0x2Eu, 0x8Fu}, {0x20u, 0x57u}
};
#define N_EXP_W ((uint8_t)(sizeof EXP_W / sizeof EXP_W[0]))

/**
 * Reset the fake with a sensor at addr and run lis3dh_init with the given axes.
 *
 * @param addr Sensor address (0x18, 0x19, or 0 for none).
 * @param ax Axis table.
 * @return Result of lis3dh_init.
 */
static int8_t setup(uint8_t addr, const lis3dh_axes_t *ax)
{
    fake_reset(addr);
    return lis3dh_init(ax);
}

/**
 * Init with the sensor at addr: probe order, exact register write sequence, read-back of every
 * write, final state.
 *
 * @param addr Sensor address under test.
 * @return None.
 */
static void t_init_ok(uint8_t addr)
{
    uint16_t n, j, k;
    uint8_t nw = 0u, immediate = 0u, ok_seq = 1u;
    int8_t r;
    g_c1 = addr;
    r = setup(addr, &AX_ID);
    CHECK(r == LIS3DH_OK);
    CHECK(lis3dh_address() == addr);
    n = fake_log_count();
    CHECK(n >= 2u && n < FAKE_LOG_MAX);
    if (n >= 1u) {
        const fake_txn_t *t = fake_log_get(0u);
        CHECK(t->is_read == 1u && t->addr == 0x18u && t->reg == 0x0Fu && t->n == 1u);   /* probe 0x18 first */
        if (addr == 0x19u) {
            const fake_txn_t *u = fake_log_get(1u);
            CHECK((t->flags & FAKE_F_NACK) != 0u);
            CHECK(u->is_read == 1u && u->addr == 0x19u && u->reg == 0x0Fu && u->n == 1u);  /* then 0x19 */
        }
    }
    for (j = 0u; j < n; j++) {
        const fake_txn_t *t = fake_log_get(j);
        if (t->is_read == 0u) {
            CHECK(t->addr == addr);
            if (nw < N_EXP_W) {
                if (t->reg != EXP_W[nw].reg || t->val != EXP_W[nw].val) { ok_seq = 0u; }
            }
            /* read-back: a later 1-byte read of the same register at the same address */
            {
                uint8_t found = 0u;
                for (k = (uint16_t)(j + 1u); k < n; k++) {
                    const fake_txn_t *u = fake_log_get(k);
                    if (u->is_read == 1u && u->addr == addr && u->reg == t->reg && u->n == 1u) {
                        found = 1u;
                        if (k == (uint16_t)(j + 1u)) { immediate++; }
                        break;
                    }
                }
                CHECK(found == 1u);
            }
            nw++;
        }
    }
    CHECK(nw == N_EXP_W);
    CHECK(ok_seq == 1u);                          /* exact order and values of the 13 writes */
    CHECK(fake_reg(0x20u) == 0x57u && fake_reg(0x2Eu) == 0x8Fu && fake_reg(0x24u) == 0x40u);
    CHECK(fake_fifo_active() == 1u);              /* Stream mode, FIFO enabled */
    CHECK(fake_fifo_level() == 0u);
    printf("INFO init@0x%02X: %u txns, read-back immediately after write: %u of %u\n",
           (unsigned)addr, (unsigned)n, (unsigned)immediate, (unsigned)N_EXP_W);
}

/**
 * Init error paths: no sensor, wrong WHO_AM_I, NACK at every transaction after the probe,
 * read-back mismatch of every configuration register, init after a failed init.
 *
 * @return None.
 */
static void t_init_faults(void)
{
    uint16_t n, t;
    uint8_t a, i;
    int8_t r;
    /* no sensor at either address: -2, both probed in order, nothing written */
    r = setup(0u, &AX_ID);
    CHECK(r == LIS3DH_ERR_SENSOR);
    n = fake_log_count();
    CHECK(n >= 2u);
    if (n >= 2u) {
        CHECK(fake_log_get(0u)->addr == 0x18u && fake_log_get(1u)->addr == 0x19u);
    }
    for (t = 0u; t < n; t++) {
        CHECK(fake_log_get(t)->is_read == 1u);
    }
    /* wrong WHO_AM_I at 0x18 / 0x19: -2 and no configuration written */
    for (a = 0x18u; a <= 0x19u; a++) {
        static const uint8_t bad[] = {0x32u, 0x00u, 0xFFu, 0x34u};
        for (i = 0u; i < (uint8_t)sizeof bad; i++) {
            g_c1 = a;
            g_c2 = bad[i];
            fake_reset(a);
            fake_set_who(bad[i]);
            r = lis3dh_init(&AX_ID);
            CHECK(r == LIS3DH_ERR_SENSOR);
            for (t = 0u; t < fake_log_count(); t++) {
                CHECK(fake_log_get(t)->is_read == 1u);
            }
        }
    }
    /* NACK at transaction t (after the successful WHO_AM_I read): every one is -3 */
    for (a = 0x18u; a <= 0x19u; a++) {
        uint16_t first = (a == 0x18u) ? 2u : 3u;     /* 0x19: txn 1 is the NACKed probe of 0x18 */
        (void)setup(a, &AX_ID);
        n = fake_log_count();
        for (t = first; t <= n; t++) {
            g_c1 = a;
            g_c2 = t;
            fake_reset(a);
            fake_nack_txn(t);
            r = lis3dh_init(&AX_ID);
            CHECK(r == LIS3DH_ERR_BUS);
        }
    }
    /* read-back mismatch of each configuration register: -3 */
    for (i = 0u; i < N_EXP_W; i++) {
        g_c1 = EXP_W[i].reg;
        g_c2 = 0u;
        fake_reset(0x18u);
        fake_corrupt_readback(EXP_W[i].reg);
        r = lis3dh_init(&AX_ID);
        CHECK(r == LIS3DH_ERR_BUS);
    }
    /* a failed init does not poison the next one */
    g_c1 = 0u;
    fake_reset(0x18u);
    fake_nack_txn(5u);
    r = lis3dh_init(&AX_ID);
    CHECK(r == LIS3DH_ERR_BUS);
    fake_reset(0x18u);
    r = lis3dh_init(&AX_ID);
    CHECK(r == LIS3DH_OK);
    fake_clear_log();
    r = lis3dh_init(&AX_ID);                         /* init twice in a row */
    CHECK(r == LIS3DH_OK);
}

/* ---------------------------------------------------------------- unpack tests */

/**
 * Unpack one word on every axis position and compare with the reference value.
 *
 * @param w Raw word.
 * @param expect_known If non-zero, also compare with a hand-computed literal.
 * @param lit The literal for w (only used if expect_known).
 * @return None.
 */
static void unpack_word(uint16_t w, uint8_t expect_known, int16_t lit)
{
    uint8_t a;
    for (a = 0u; a < 3u; a++) {
        uint16_t words[3];
        uint8_t raw[6];
        int16_t out[3];
        words[a] = w;
        words[(a + 1u) % 3u] = (uint16_t)(w ^ 0x5A5Au);
        words[(a + 2u) % 3u] = (uint16_t)(~w);
        make_raw(words, raw);
        lis3dh_unpack(raw, &AX_ID, out);
        g_c1 = w;
        g_c2 = a;
        CHECK(out[a] == ref_value(w));
        CHECK(out[(a + 1u) % 3u] == ref_value((uint16_t)(w ^ 0x5A5Au)));
        CHECK(out[(a + 2u) % 3u] == ref_value((uint16_t)(~w)));
        if (expect_known) { CHECK(out[a] == lit); }
    }
}

/**
 * Byte assembly and arithmetic shift (C1.1): literal table, every word (host) or a stride (sim16).
 *
 * @return None.
 */
static void t_unpack_table(void)
{
    static const struct { uint16_t w; int16_t v; } T[] = {
        {0x8000u, -2048}, {0x7FF0u, 2047}, {0xFFF0u, -1}, {0x0010u, 1}, {0x0000u, 0},
        {0x7FFFu, 2047}, {0x800Fu, -2048}, {0x8010u, -2047}, {0xFFFFu, -1}, {0xFFEFu, -2},
        {0x0001u, 0}, {0x000Fu, 0}, {0x001Fu, 1}, {0x0100u, 16}, {0x1000u, 256},
        {0x4000u, 1024}, {0xC000u, -1024}, {0x00F0u, 15}, {0x0FF0u, 255}, {0xF000u, -256}
    };
    uint16_t i;
    uint32_t w, step;
    for (i = 0u; i < (uint16_t)(sizeof T / sizeof T[0]); i++) {
        unpack_word(T[i].w, 1u, T[i].v);
    }
#ifdef __AVR__
    step = 251u;                  /* sim16: a prime stride, ~260 words (speed) */
#else
    step = 1u;                    /* host: all 65536 words */
#endif
    for (w = 0u; w < 65536u; w += step) {
        unpack_word((uint16_t)w, 0u, 0);
    }
    unpack_word(0xFFFFu, 1u, -1);
}

/**
 * Axis remap at unpack time (C1.3): identity, a swap with a sign flip, a 3-cycle with flips,
 * and all 6 permutations x 8 sign patterns against the reference.
 *
 * @return None.
 */
static void t_unpack_axes(void)
{
    static const uint16_t W[3] = {0x1230u, 0x8F50u, 0x7010u};   /* 291, -1803, 1793 */
    static const uint8_t P[6][3] = {{0,1,2},{0,2,1},{1,0,2},{1,2,0},{2,0,1},{2,1,0}};
    uint8_t raw[6];
    int16_t out[3], in[3], exp[3];
    uint8_t p, s, i;
    make_raw(W, raw);
    in[0] = ref_value(W[0]);
    in[1] = ref_value(W[1]);
    in[2] = ref_value(W[2]);
    CHECK(in[0] == 291 && in[1] == -1803 && in[2] == 1793);
    lis3dh_unpack(raw, &AX_ID, out);
    CHECK(out[0] == 291 && out[1] == -1803 && out[2] == 1793);
    lis3dh_unpack(raw, &AX_SWAP, out);              /* out = {in[1], -in[0], in[2]} */
    CHECK(out[0] == -1803 && out[1] == -291 && out[2] == 1793);
    lis3dh_unpack(raw, &AX_CYC, out);               /* out = {-in[1], in[2], -in[0]} */
    CHECK(out[0] == 1803 && out[1] == 1793 && out[2] == -291);
    for (p = 0u; p < 6u; p++) {
        for (s = 0u; s < 8u; s++) {
            lis3dh_axes_t ax;
            g_c1 = p;
            g_c2 = s;
            for (i = 0u; i < 3u; i++) {
                ax.src[i] = P[p][i];
                ax.sign[i] = (int8_t)((((s >> i) & 1) != 0) ? -1 : 1);
            }
            ref_remap(in, &ax, exp);
            lis3dh_unpack(raw, &ax, out);
            CHECK(out[0] == exp[0] && out[1] == exp[1] && out[2] == exp[2]);
        }
    }
    /* sign flip of -2048: outside the C1 range [-2048, 2047]. NOT asserted: report only. */
    {
        static const uint16_t E[3] = {0x8000u, 0x8000u, 0x8000u};
        lis3dh_axes_t flip = {{0u, 1u, 2u}, {-1, -1, 1}};
        make_raw(E, raw);
        lis3dh_unpack(raw, &flip, out);
        printf("INFO unpack(-2048) with sign -1 -> %d (C1 range max 2047); sign +1 -> %d\n",
               (int)out[0], (int)out[2]);
        CHECK(out[2] == -2048);                     /* sign +1 must stay -2048 */
    }
}

/* ---------------------------------------------------------------- drain tests */

#define DRAIN_MAX 64u

typedef struct { uint16_t n; int16_t s[DRAIN_MAX][3]; } rec_t;

/**
 * Sample callback: records every delivered sample in call order.
 *
 * @param s The three wand-frame values.
 * @param ctx rec_t to append to.
 * @return None.
 */
static void rec_cb(const int16_t s[3], void *ctx)
{
    rec_t *r = (rec_t *)ctx;
    if (r->n < DRAIN_MAX) {
        r->s[r->n][0] = s[0];
        r->s[r->n][1] = s[1];
        r->s[r->n][2] = s[2];
    }
    r->n++;
}

/* Counting model of the sensor FIFO: head = oldest unread sequence number, tail = next to push. */
typedef struct { uint16_t head, tail; } mdl_t;

/**
 * Push k samples into the model (Stream mode: a full FIFO discards the oldest).
 *
 * @param m Model.
 * @param k Number of samples.
 * @return None.
 */
static void m_push(mdl_t *m, uint16_t k)
{
    uint16_t i;
    for (i = 0u; i < k; i++) {
        m->tail++;
        if ((uint16_t)(m->tail - m->head) > 32u) { m->head++; }
    }
}

/**
 * FSS as the fake reports it in FAKE_FSS32_SATURATE mode: min(unread, 31).
 *
 * @param m Model.
 * @return FSS value.
 */
static uint8_t m_fss(const mdl_t *m)
{
    uint16_t u = (uint16_t)(m->tail - m->head);
    return (uint8_t)((u > 31u) ? 31u : u);
}

/** What one lis3dh_drain call must do, from the spec. */
typedef struct {
    uint16_t seq[DRAIN_MAX];   /**< sequence numbers delivered, in order */
    uint16_t count;            /**< samples delivered */
    uint8_t  bursts;           /**< burst reads */
    uint8_t  bsz[4];           /**< samples in each burst */
    uint8_t  fss[5];           /**< FSS seen by each FIFO_SRC read */
    uint8_t  nreads;           /**< FIFO_SRC reads */
    uint8_t  more;             /**< expected *more */
    uint8_t  overrun;          /**< expected *overrun */
} expect_t;

/**
 * Run the C1.4 drain schedule on the model (see the file header for the two readings).
 *
 * @param m Model; advanced to the state after the drain.
 * @param k Samples that arrive after every burst.
 * @param e Expected behaviour.
 * @return None.
 */
static void model_drain(mdl_t *m, uint8_t k, expect_t *e)
{
    uint8_t fss, n, i;
    e->count = 0u;
    e->bursts = 0u;
    e->more = 0u;
    e->nreads = 1u;
    e->overrun = (uint8_t)((uint16_t)(m->tail - m->head) == 32u);   /* OVRN = 32 unread, first read only */
    fss = m_fss(m);
    e->fss[0] = fss;
    if (fss == 0u) { return; }
    for (;;) {
        n = (uint8_t)((fss < 16u) ? fss : 16u);
        e->bsz[e->bursts] = n;
        for (i = 0u; i < n; i++) { e->seq[e->count++] = m->head++; }
        e->bursts++;
        m_push(m, k);
        fss = m_fss(m);
        e->fss[e->bursts] = fss;
        e->nreads++;
#ifdef DRAIN_MODEL_B
        if (fss == 0u) { break; }
        if (e->bursts >= 4u) { e->more = (uint8_t)(fss >= 16u); break; }
#else
        if (fss < 16u) { break; }
        if (e->bursts >= 4u) { e->more = 1u; break; }
#endif
    }
}

static uint8_t g_msb_seen, g_msb_missing;   /* did the driver set bit 7 of the burst sub-address */

/**
 * One drain scenario: init, preload level samples, add k samples after every burst, call
 * lis3dh_drain, compare with the model: delivered count, order, remapped values, every
 * transaction in the log (one burst per FSS read, size min(FSS,16) <= 16), overrun, more.
 *
 * @param ax Axis table given to init.
 * @param level Samples pushed before the call (more than 32 overflows the FIFO).
 * @param k Samples arriving after each burst.
 * @return None.
 */
static void run_drain(const lis3dh_axes_t *ax, uint16_t level, uint8_t k)
{
    mdl_t m;
    expect_t e;
    rec_t rec;
    uint8_t ov = 0xAAu;
    bool more;
    int16_t r;
    uint16_t i, nl, j;
    uint8_t a;
    g_c1 = level;
    g_c2 = k;
    CHECK(setup(0x18u, ax) == LIS3DH_OK);
    m.head = 0u;
    m.tail = 0u;
    fake_push_next(level);
    m_push(&m, level);
    CHECK(fake_next_seq() == m.tail);
    fake_clear_log();
    fake_set_arrivals(k, 0xFFFFu);
    model_drain(&m, k, &e);
    rec.n = 0u;
    more = (e.more == 0u);                         /* start with the wrong answer */
    r = lis3dh_drain(rec_cb, &rec, &ov, &more);
    CHECK(r == (int16_t)e.count);
    CHECK(rec.n == e.count);
    CHECK((ov != 0u) == (e.overrun != 0u));
    CHECK(ov <= 1u);                               /* a flag, not the raw FIFO_SRC bits */
    CHECK(more == (e.more != 0u));
    CHECK(e.bursts <= 4u);
    CHECK(fake_next_seq() == m.tail);              /* arrivals happened as modelled */
    CHECK(fake_fifo_level() == (uint8_t)(m.tail - m.head));
    for (i = 0u; i < e.count && i < rec.n && i < DRAIN_MAX; i++) {
        int16_t in[3], exp[3];
        for (a = 0u; a < 3u; a++) { in[a] = ref_value(fake_sample_word(e.seq[i], a)); }
        ref_remap(in, ax, exp);
        CHECK(rec.s[i][0] == exp[0] && rec.s[i][1] == exp[1] && rec.s[i][2] == exp[2]);
    }
    nl = fake_log_count();
    CHECK(nl == (uint16_t)(2u * e.bursts + 1u));   /* F B F B ... F : one burst per FSS read */
    for (j = 0u; j < nl; j++) {
        const fake_txn_t *t = fake_log_get(j);
        CHECK(t->addr == 0x18u && t->is_read == 1u && (t->flags & FAKE_F_NACK) == 0u);
        if ((j & 1u) == 0u) {
            CHECK(t->reg == 0x2Fu && t->n == 1u);
            if ((uint16_t)(j / 2u) < 5u) { CHECK((uint8_t)(t->val & 0x1Fu) == e.fss[j / 2u]); }
        } else {
            uint8_t b = (uint8_t)((j - 1u) / 2u);
            CHECK(t->reg == 0x28u);                /* starts at OUT_X_L */
            CHECK(b < 4u && t->n == (uint8_t)(6u * e.bsz[b]));
            CHECK(t->n % 6u == 0u && t->n / 6u >= 1u && t->n / 6u <= LIS3DH_BURST_MAX);
            if ((t->flags & FAKE_F_MSB) != 0u) { g_msb_seen = 1u; } else { g_msb_missing = 1u; }
        }
    }
}

/**
 * Drain with 0, 1, 15, 16, 17, 31, 32 unread and overflowed FIFOs, no arrivals; plus literal
 * expectations (reading A only) so the model is not the only judge.
 *
 * @return None.
 */
static void t_drain_levels(void)
{
    static const uint16_t L[] = {0u, 1u, 15u, 16u, 17u, 31u, 32u, 33u, 35u, 64u};
    uint8_t i;
    for (i = 0u; i < (uint8_t)(sizeof L / sizeof L[0]); i++) {
        run_drain(&AX_SWAP, L[i], 0u);
        run_drain(&AX_ID, L[i], 0u);
    }
#ifndef DRAIN_MODEL_B
    {
        /* hand-computed (reading A): delivered counts, no arrivals */
        static const struct { uint16_t level; int16_t ret; uint8_t ovr; } LIT[] = {
            {0u, 0, 0u}, {1u, 1, 0u}, {15u, 15, 0u}, {16u, 16, 0u}, {17u, 16, 0u},
            {31u, 16, 0u}, {32u, 32, 1u}, {35u, 32, 1u}
        };
        for (i = 0u; i < (uint8_t)(sizeof LIT / sizeof LIT[0]); i++) {
            rec_t rec;
            uint8_t ov = 0xAAu;
            bool more = true;
            int16_t r;
            g_c1 = LIT[i].level;
            g_c2 = 0u;
            (void)setup(0x18u, &AX_ID);
            fake_push_next(LIT[i].level);
            rec.n = 0u;
            r = lis3dh_drain(rec_cb, &rec, &ov, &more);
            CHECK(r == LIT[i].ret);
            CHECK(ov == LIT[i].ovr);
            CHECK(more == false);
        }
    }
#endif
}

/**
 * Samples arriving between bursts, the 4-burst bound and the `more` flag, overrun from the
 * first FIFO_SRC read only.
 *
 * @return None.
 */
static void t_drain_arrivals(void)
{
    static const uint16_t LV[] = {1u, 15u, 16u, 17u, 31u, 32u};
    static const uint8_t K[] = {1u, 3u, 15u, 16u, 31u};
    static const struct { uint16_t level; uint8_t k; } BOUND[] = {
        {19u, 15u},  /* 19 -> 18 -> 17 -> 16 -> 15: 4 bursts, FSS 15 at the end: more = false */
        {20u, 15u},  /* ends at FSS 16: stopped by the bound, more = true */
        {17u, 16u}, {32u, 16u}, {24u, 8u}
    };
    uint8_t i, j;
    for (i = 0u; i < (uint8_t)(sizeof LV / sizeof LV[0]); i++) {
        for (j = 0u; j < (uint8_t)(sizeof K); j++) {
            run_drain(&AX_SWAP, LV[i], K[j]);
        }
    }
    for (i = 0u; i < (uint8_t)(sizeof BOUND / sizeof BOUND[0]); i++) {
        run_drain(&AX_CYC, BOUND[i].level, BOUND[i].k);
    }
    /* explicit (model-independent) expectations for the bound */
    {
        rec_t rec;
        uint8_t ov = 0xAAu;
        bool more = false;
        int16_t r;
        g_c1 = 17u;
        g_c2 = 16u;
        (void)setup(0x18u, &AX_ID);
        fake_push_next(17u);
        fake_clear_log();
        fake_set_arrivals(16u, 0xFFFFu);
        rec.n = 0u;
        r = lis3dh_drain(rec_cb, &rec, &ov, &more);
        CHECK(r == 64);                       /* 4 bursts x 16, never more */
        CHECK(more == true);                  /* FSS still >= 16 when the bound stopped it */
        CHECK(ov == 0u);                      /* 17 unread at the first read: no OVRN */
        CHECK(fake_log_count() == 9u);        /* 4 x (FIFO_SRC + burst) + final FIFO_SRC */
    }
    /* overrun only from the FIRST FIFO_SRC read: later reads see 32 unread, flag stays 0 */
    {
        rec_t rec;
        uint8_t ov = 0xAAu;
        bool more = false;
        g_c1 = 17u;
        g_c2 = 31u;
        (void)setup(0x18u, &AX_ID);
        fake_push_next(17u);
        fake_set_arrivals(31u, 0xFFFFu);
        rec.n = 0u;
        (void)lis3dh_drain(rec_cb, &rec, &ov, &more);
        CHECK(ov == 0u);
        CHECK(fake_lost() > 0u);              /* the fake did overflow after the first read */
    }
    /* and the converse: 32 unread at the first read, then drained below 32: flag stays 1 */
    {
        rec_t rec;
        uint8_t ov = 0u;
        bool more = true;
        g_c1 = 32u;
        g_c2 = 0u;
        (void)setup(0x18u, &AX_ID);
        fake_push_next(32u);
        rec.n = 0u;
        (void)lis3dh_drain(rec_cb, &rec, &ov, &more);
        CHECK(ov == 1u);
    }
}

/**
 * Bus errors at every point of a drain: the call returns LIS3DH_ERR_BUS and does not hang.
 *
 * @return None.
 */
static void t_drain_bus(void)
{
    rec_t rec;
    uint8_t ov;
    bool more;
    int16_t r;
    uint16_t nl, t;
    g_c1 = 0u;
    g_c2 = 0u;
    /* NACK on the first FIFO_SRC read: nothing delivered */
    (void)setup(0x18u, &AX_ID);
    fake_push_next(20u);
    fake_clear_log();
    fake_nack_fifo_src(1u);
    rec.n = 0u; ov = 0u; more = false;
    r = lis3dh_drain(rec_cb, &rec, &ov, &more);
    CHECK(r == LIS3DH_ERR_BUS);
    CHECK(rec.n == 0u);
    /* NACK on the first burst: nothing delivered */
    (void)setup(0x18u, &AX_ID);
    fake_push_next(20u);
    fake_clear_log();
    fake_nack_burst(1u);
    rec.n = 0u;
    r = lis3dh_drain(rec_cb, &rec, &ov, &more);
    CHECK(r == LIS3DH_ERR_BUS);
    CHECK(rec.n == 0u);
    /* NACK on the re-read of FIFO_SRC after the first burst */
    (void)setup(0x18u, &AX_ID);
    fake_push_next(20u);
    fake_clear_log();
    fake_nack_fifo_src(2u);
    rec.n = 0u;
    r = lis3dh_drain(rec_cb, &rec, &ov, &more);
    CHECK(r == LIS3DH_ERR_BUS);
    printf("INFO drain: NACK on the re-read after a burst delivered %u samples before -3\n", (unsigned)rec.n);
    /* NACK on the second burst (32 unread + arrivals guarantee a second burst) */
    (void)setup(0x18u, &AX_ID);
    fake_push_next(32u);
    fake_clear_log();
    fake_set_arrivals(16u, 0xFFFFu);
    fake_nack_burst(2u);
    rec.n = 0u;
    r = lis3dh_drain(rec_cb, &rec, &ov, &more);
    CHECK(r == LIS3DH_ERR_BUS);
    printf("INFO drain: NACK on the 2nd burst delivered %u samples before -3\n", (unsigned)rec.n);
    /* NACK at every single transaction of a 32-unread drain */
    (void)setup(0x18u, &AX_ID);
    fake_push_next(32u);
    fake_clear_log();
    rec.n = 0u;
    (void)lis3dh_drain(rec_cb, &rec, &ov, &more);
    nl = fake_log_count();
    CHECK(nl >= 3u);
    for (t = 1u; t <= nl; t++) {
        g_c1 = t;
        (void)setup(0x18u, &AX_ID);
        fake_push_next(32u);
        fake_clear_log();
        fake_nack_txn(t);
        rec.n = 0u;
        r = lis3dh_drain(rec_cb, &rec, &ov, &more);
        CHECK(r == LIS3DH_ERR_BUS);
    }
}

/**
 * Informational runs (never fail the suite): FSS reported as 0 at 32 unread, burst sub-address
 * bit 7.
 *
 * @return None.
 */
static void info_runs(void)
{
    rec_t rec;
    uint8_t ov = 0xAAu;
    bool more = false;
    int16_t r;
    (void)setup(0x18u, &AX_ID);
    fake_set_fss32(FAKE_FSS32_WRAP);
    fake_push_next(32u);
    rec.n = 0u;
    r = lis3dh_drain(rec_cb, &rec, &ov, &more);
    printf("INFO FSS-wrap model (FSS=0, OVRN=1 at 32 unread): ret=%d delivered=%u overrun=%u more=%u left=%u\n",
           (int)r, (unsigned)rec.n, (unsigned)ov, (unsigned)more, (unsigned)fake_fifo_level());
    printf("INFO burst sub-address bit 7 (auto-increment) set by driver: %s%s\n",
           g_msb_seen ? "yes" : "no", g_msb_missing ? " (missing on some bursts)" : "");
}

/* ---------------------------------------------------------------- click */

/**
 * lis3dh_read_click: one CLICK_SRC read, clear-on-read seen through the driver, bus error.
 *
 * @return None.
 */
static void t_click(void)
{
    int8_t d, s, again, none;
    (void)setup(0x18u, &AX_ID);
    fake_clear_log();
    fake_set_click_src(0x60u);                      /* IA | DCLICK */
    d = lis3dh_read_click();
    CHECK(fake_log_count() == 1u);
    if (fake_log_count() >= 1u) {
        const fake_txn_t *t = fake_log_get(0u);
        CHECK(t->is_read == 1u && t->addr == 0x18u && t->reg == 0x39u && t->n == 1u);
    }
    CHECK(d > 0);                                   /* a double click is reported */
    again = lis3dh_read_click();                    /* CLICK_SRC cleared by the first read */
    CHECK(again == 0);
    fake_set_click_src(0x00u);
    none = lis3dh_read_click();
    CHECK(none == 0);
    fake_set_click_src(0x50u);                      /* IA | SCLICK */
    s = lis3dh_read_click();
    CHECK(s >= 0);
    printf("INFO click return codes: double=%d single=%d none=%d\n", (int)d, (int)s, (int)none);
    (void)setup(0x19u, &AX_ID);                     /* address follows the probe result */
    fake_clear_log();
    fake_set_click_src(0x60u);
    CHECK(lis3dh_read_click() > 0);
    CHECK(fake_log_count() == 1u && fake_log_get(0u)->addr == 0x19u);
    fake_clear_log();
    fake_nack_txn(1u);
    CHECK(lis3dh_read_click() == LIS3DH_ERR_BUS);
}

/**
 * Run every group; exit 0 only if none failed.
 *
 * @return 0 on the host when all pass (on sim16 sim16_exit stops the CPU).
 */
int main(void)
{
    sim16_init();
    printf("sizeof(int)=%u\n", (unsigned)sizeof(int));
    group_begin("init@0x18"); t_init_ok(0x18u); group_end();
    group_begin("init@0x19"); t_init_ok(0x19u); group_end();
    group_begin("init faults"); t_init_faults(); group_end();
    group_begin("unpack table"); t_unpack_table(); group_end();
    group_begin("unpack axes"); t_unpack_axes(); group_end();
    group_begin("drain levels"); t_drain_levels(); group_end();
    group_begin("drain arrivals/bound/overrun"); t_drain_arrivals(); group_end();
    group_begin("drain bus errors"); t_drain_bus(); group_end();
    group_begin("click"); t_click(); group_end();
    info_runs();
    if (g_fails != 0u) {
        printf("lis3dh tests: %u checks FAILED\n", (unsigned)g_fails);
    } else {
        printf("lis3dh tests: all groups passed\n");
    }
    sim16_exit((int16_t)((g_fails != 0u) ? 1 : 0));
    return (g_fails != 0u) ? 1 : 0;
}
// [END AI-GENERATED]
