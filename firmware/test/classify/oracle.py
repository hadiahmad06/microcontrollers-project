# [AI-GENERATED: Claude Code]
"""Independent oracle for the classify.c / knn.c suite (tickets 3.5T / 3.6T).

Written from the SPEC only (docs/agent/CONTRACTS.md C5.2 and C7, the main-agent rulings and the
API in the ticket), never from the implementation or from quant_ref.py. It replays exactly what
test_classify.c does (same xorshift32 PRNG, same scenario generator, same directed cases) and
returns the expected output text, one line per result. run_tests.py diffs that against the binary.

Usage: python3 oracle.py SEED NSCEN   (prints the expected output)
"""
import sys

M32 = 0xFFFFFFFF
DIM = 60
NCLS = 4                  # GESTURE_MAX_LEARNED
NSLOT = 5                 # GESTURE_TEMPLATES_PER_CLASS
BASE_ID = 9               # GESTURE_LEARNED_BASE
OVERRIDE_CONF = 192
R_MIN, R_DEF, R_MAX = 600, 1200, 4000
BLOB_SIZE = 4 + NCLS * 2 + NCLS * NSLOT * DIM + 2     # 1214
AMP_TAB = [0, 1, 3, 8, 20, 60]
BAD_TAB = [0, 8, 13, 255, 14, 15, 100]
MC_TAB = [0, 1, 64, 191, 192, 193, 255]


# ----------------------------------------------------------------------------- PRNG / vectors
class Rng:
    """xorshift32 (13, 17, 5), identical to test_classify.c."""

    def __init__(self):
        self.s = 1

    def seed(self, seed, s):
        self.s = (seed + (s + 1) * 0x9E3779B9) & M32
        if self.s == 0:
            self.s = 1
        for _ in range(3):
            self.next()

    def next(self):
        x = self.s
        x ^= (x << 13) & M32
        x ^= x >> 17
        x ^= (x << 5) & M32
        self.s = x
        return x


def v_base(rng):
    style = rng.next() % 3
    v = []
    for _ in range(DIM):
        if style == 0:
            v.append(rng.next() % 255 - 127)
        elif style == 1:
            v.append(127 if (rng.next() & 1) else -127)
        else:
            v.append(rng.next() % 41 - 20)
    return v


def v_noisy(rng, base, amp):
    out = []
    for i in range(DIM):
        x = base[i]
        if amp > 0:
            x += rng.next() % (2 * amp + 1) - amp
        out.append(max(-127, min(127, x)))
    return out


def v_dist(d, sign):
    v = []
    for _ in range(DIM):
        e = min(127, d)
        v.append(sign * e)
        d -= e
    return v


def v_mk(fill, n, val):
    return [val if i < n else fill for i in range(DIM)]


# ----------------------------------------------------------------------------- spec model
def crc16(data):
    """CRC-16/IBM-3740: poly 0x1021, init 0xFFFF, no reflection, xorout 0."""
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


assert crc16(b"123456789") == 0x29B1


def l1(a, b):
    return sum(abs(x - y) for x, y in zip(a, b))


class Knn:
    """Spec model of knn.c. Slots are ordered class-major, then slot (ruling of the main agent)."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.t = [[[0] * DIM for _ in range(NSLOT)] for _ in range(NCLS)]
        self.cnt = [0] * NCLS
        self.nxt = [0] * NCLS

    def copy_from(self, o):
        self.t = [[list(v) for v in c] for c in o.t]
        self.cnt = list(o.cnt)
        self.nxt = list(o.nxt)

    @staticmethod
    def valid(cid):
        return BASE_ID <= cid < BASE_ID + NCLS

    def learn(self, cid, x):
        if not self.valid(cid):
            return -1
        c = cid - BASE_ID
        self.t[c][self.nxt[c]] = list(x)
        self.nxt[c] = (self.nxt[c] + 1) % NSLOT
        self.cnt[c] = min(NSLOT, self.cnt[c] + 1)
        return self.cnt[c]

    def count(self, cid):
        return self.cnt[cid - BASE_ID] if self.valid(cid) else 0

    def total(self):
        return sum(self.cnt)

    def radius(self, cid):
        if not self.valid(cid):
            return 0
        c = cid - BASE_ID
        n = self.cnt[c]
        if n < 2:
            return R_DEF
        d = sorted(l1(self.t[c][i], self.t[c][j]) for i in range(n) for j in range(i + 1, n))
        med = d[(len(d) - 1) // 2]
        return max(R_MIN, min(R_MAX, 2 * med))

    def query(self, x):
        """Return None if empty else (kid, d1, d2, has_other, c_k, radius)."""
        best = None
        kc = 0
        for c in range(NCLS):                       # class-major, slot-major; strict < keeps lowest slot
            for s in range(self.cnt[c]):
                d = l1(x, self.t[c][s])
                if best is None or d < best:
                    best, kc = d, c
        if best is None:
            return None
        d2 = None
        for c in range(NCLS):
            if c == kc:
                continue
            for s in range(self.cnt[c]):
                d = l1(x, self.t[c][s])
                if d2 is None or d < d2:
                    d2 = d
        if d2 is None:
            ck = 255
        elif d2 == 0:
            ck = 0
        else:
            ck = ((d2 - best) * 255) // d2
        kid = BASE_ID + kc
        return (kid, best, d2 if d2 is not None else 0, 1 if d2 is not None else 0, ck, self.radius(kid))

    def export(self):
        b = bytearray([1, NCLS, NSLOT, DIM])
        for c in range(NCLS):
            b += bytes([self.cnt[c], self.nxt[c]])
        for c in range(NCLS):
            for s in range(NSLOT):
                b += bytes(v & 0xFF for v in self.t[c][s])
        crc = crc16(bytes(b))
        b += bytes([crc & 0xFF, crc >> 8])
        return bytes(b)


def mlp_conf(margin, sh):
    return min(255, margin >> sh)


def decide(top1, margin, sh, q, mc):
    """classify_decide per C5.2. q is a query tuple or None. Returns (id, conf)."""
    ident = top1
    c = mlp_conf(margin, sh)
    if q is not None:
        kid, d1, _d2, _ho, ck, rad = q
        weak = ident == 0 or c < mc or c < OVERRIDE_CONF
        if weak and d1 <= rad and ck >= mc:
            ident, c = kid, ck
    return (-1 if c < mc else ident), c


# ----------------------------------------------------------------------------- output mirror
class Replay:
    """Mirrors the C driver call for call and collects the expected lines."""

    def __init__(self):
        self.rng = Rng()
        self.k = Knn()
        self.out = []
        self.base = [[0] * DIM for _ in range(NCLS)]
        self.last = [0] * DIM

    def p(self, s):
        self.out.append(s)

    def report_state(self, pfx):
        k = self.k
        self.p("%sN %d %d %d %d %d %d %d %d" % (pfx, k.count(9), k.count(10), k.count(11), k.count(12),
                                               k.total(), k.count(0), k.count(13), k.count(255)))
        self.p("%sR %d %d %d %d %d %d %d %d" % (pfx, k.radius(9), k.radius(10), k.radius(11), k.radius(12),
                                               k.radius(0), k.radius(8), k.radius(13), k.radius(255)))
        blob = k.export()
        self.p("%sE %d %d 1 0 0" % (pfx, len(blob), blob[-2] | (blob[-1] << 8)))

    def emit_query(self, win):
        q = self.k.query(win)
        if q is None:
            self.p("Q 0")
        else:
            self.p("Q 1 %d %d %d %d %d %d" % q)
        return q

    def emit_decide(self, tag, top1, margin, sh, mc, q):
        r, c = decide(top1, margin, sh, q, mc)
        self.p("%s %d %d %d %d %d %d %d %d %d" % (tag, top1, margin, sh, mc, 1 if q is not None else 0,
                                                  r, c, r, mlp_conf(margin, sh)))

    def T_case(self, name, win, top1, margin, sh, mc):
        q = self.emit_query(win)
        self.emit_decide("T " + name, top1, margin, sh, mc, q)

    # ------------------------------------------------------------------ blob I/O
    def io_tests(self, amp):
        rng = self.rng
        saved = Knn()
        saved.copy_from(self.k)
        size = len(self.k.export())
        assert size == BLOB_SIZE
        names = ["len_short", "len_long", "len_zero", "ver0", "ver2", "ver255", "shape_classes",
                 "shape_tpc", "shape_dim", "flip_first", "flip_rand", "flip_last", "crc_lo", "crc_hi"]
        for k, name in enumerate(names):
            if k == 10:
                rng.next()          # idx draw
                rng.next()          # bit draw
            rc = -1 if k <= 2 else (-2 if k <= 8 else -3)
            self.p("X %s %d 1" % (name, rc))
        # round trip: reset, junk, import replaces everything, including the next-slot pointers
        self.k.copy_from(saved)
        self.p("I 0 1")
        self.report_state("p")
        ident = 9 + rng.next() % 4
        cur = v_noisy(rng, self.base[ident - 9], amp)
        self.p("pL %d %d" % (ident, self.k.learn(ident, cur)))
        self.report_state("q")

    # ------------------------------------------------------------------ random scenario
    def scenario(self, seed, s):
        rng, k = self.rng, self.k
        rng.seed(seed, s)
        self.p("S %d" % s)
        amp = AMP_TAB[rng.next() % 6]
        for c in range(NCLS):
            self.base[c] = v_base(rng)
        self.last = list(self.base[0])
        k.reset()
        nl = rng.next() % 24
        for _ in range(nl):
            sel = rng.next() % 16
            if sel < 13:
                ident = 9 + rng.next() % 4
            else:
                ident = BAD_TAB[rng.next() % 7]
            cls = ident - 9 if 9 <= ident <= 12 else 0
            cur = v_noisy(rng, self.base[cls], amp)
            self.last = list(cur)
            self.p("L %d %d" % (ident, k.learn(ident, cur)))
        self.report_state("")
        for _ in range(8):
            mode = rng.next() % 4
            cls = rng.next() % 4
            if mode == 0:
                win = v_noisy(rng, self.base[cls], amp)
            elif mode == 1:
                win = v_noisy(rng, self.base[cls], AMP_TAB[rng.next() % 6])
            elif mode == 2:
                win = v_base(rng)
            else:
                win = list(self.last)
            q = self.emit_query(win)
            for _j in range(3):
                top1 = rng.next() % 9
                shsel = rng.next() % 4
                if shsel == 0:
                    sh = 0
                elif shsel == 1:
                    sh = 24
                else:
                    sh = rng.next() % 25
                mm = rng.next() % 6
                if mm == 0:
                    margin = 0
                elif mm == 1:
                    margin = rng.next() % 8
                elif mm == 2:
                    margin = 1 << 30
                elif mm == 3:
                    margin = rng.next() & 0xFFFFF
                elif mm == 4:
                    tgt = rng.next() % 256
                    off = rng.next() % 3
                    v = tgt << sh
                    if off == 0 and v > 0:
                        v -= 1
                    elif off == 2:
                        v += 1
                    margin = min(v, 0x7FFFFFFF)
                else:
                    margin = rng.next() & 0x3FFFFFFF
                mcs = rng.next() % 9
                mc = MC_TAB[mcs] if mcs < 7 else rng.next() % 256
                fl = rng.next() % 8
                self.emit_decide("D", top1, margin, sh, mc, q if (q is not None and fl != 0) else None)
        self.io_tests(amp)

    # ------------------------------------------------------------------ directed cases
    def directed(self):
        k, rng = self.k, self.rng
        MARG = [0, 1, 255, 256, 0x7FFFFFFF, 0x40000000]
        SHS = [0, 1, 8, 24]
        BM = [63, 64, 65, 191, 192, 193, 254, 255, 256, 10000]
        SM = [0, 5, 255, 0x40000000]
        GROW = [0, 300, 700, 1500, 2100, 3000, 5000]
        self.p("G %d" % crc16(b"123456789"))
        rng.s = 12345
        k.reset()
        a = v_mk(0, 0, 0)
        for i in range(21):
            self.p("DL %d %d" % (i, k.learn(i, a)))
        self.p("DL 255 %d" % k.learn(255, a))
        self.report_state("d")
        for m in MARG:
            for sh in SHS:
                self.p("DM %d %d %d" % (m, sh, mlp_conf(m, sh)))
        # C5 section 2 vectors
        k.reset()
        a = v_mk(0, 0, 0)
        k.learn(9, a)
        win = v_mk(0, 4, 1)
        self.T_case("c5_1", win, 3, 255, 0, 64)
        self.T_case("c5_2", win, 3, 100, 0, 64)
        self.T_case("c5_3", win, 0, 255, 0, 64)
        self.T_case("c5_4", win, 3, 30, 0, 64)
        b = v_mk(0, 10, 127)
        self.T_case("c5_5a", b, 3, 30, 0, 64)
        self.T_case("c5_5b", b, 3, 255, 0, 64)
        k.reset()
        self.T_case("c5_6a", win, 0, 0, 0, 1)
        self.T_case("c5_6b", win, 0, 0, 0, 0)
        k.reset()
        k.learn(9, v_mk(0, 0, 0))
        k.learn(10, v_mk(0, 44, 1))
        self.T_case("c5_7", win, 3, 0, 0, 64)
        # sweeps
        for kk in range(2):
            k.reset()
            if kk == 0:
                k.learn(9, v_mk(0, 0, 0))
            for i in range(2):
                for j in range(4):
                    for s in range(2):
                        for m in range(7):
                            self.T_case("sw", win, i * 3, SM[j], s * 24, MC_TAB[m])
            for j in range(10):
                for m in range(7):
                    self.T_case("bd", win, 3, BM[j], 0, MC_TAB[m])
        # d2 == 0
        k.reset()
        a = v_mk(0, 0, 0)
        k.learn(9, a)
        k.learn(10, a)
        self.T_case("dz_a", a, 3, 0, 0, 0)
        self.T_case("dz_b", a, 3, 0, 0, 1)
        self.T_case("dz_c", win, 3, 0, 0, 0)
        # radius cases
        k.reset()
        k.learn(9, a)
        k.learn(9, a)
        self.p("DR %d" % k.radius(9))
        self.T_case("rmin_eq", v_dist(600, 1), 3, 0, 0, 1)
        self.T_case("rmin_over", v_dist(601, 1), 3, 0, 0, 1)
        k.reset()
        k.learn(9, a)
        self.p("DR %d" % k.radius(9))
        self.T_case("rdef_eq", v_dist(1200, 1), 3, 0, 0, 1)
        self.T_case("rdef_over", v_dist(1201, 1), 3, 0, 0, 1)
        k.reset()
        k.learn(9, a)
        k.learn(9, v_dist(3000, -1))
        self.p("DR %d" % k.radius(9))
        self.T_case("rmax_eq", v_dist(4000, 1), 3, 0, 0, 1)
        self.T_case("rmax_over", v_dist(4001, 1), 3, 0, 0, 1)
        k.reset()
        k.learn(9, a)
        k.learn(9, v_dist(1000, 1))
        self.p("DR %d" % k.radius(9))
        self.T_case("rmid_eq", v_dist(2000, -1), 3, 0, 0, 1)
        self.T_case("rmid_over", v_dist(2001, -1), 3, 0, 0, 1)
        # growth and overwrite
        k.reset()
        self.p("DG 0 0 %d %d" % (k.count(9), k.radius(9)))
        for i in range(7):
            r = k.learn(9, v_dist(GROW[i], 1))
            self.p("DG %d %d %d %d" % (i + 1, r, k.count(9), k.radius(9)))
        for i in range(7):
            self.T_case("gr", v_dist(GROW[i], 1), 3, 0, 0, 1)
        self.io_tests(3)
        # ties
        k.reset()
        a = v_mk(5, 20, -33)
        k.learn(10, a)
        k.learn(9, a)
        self.T_case("tie_cls", a, 3, 0, 0, 0)
        k.reset()
        a = v_mk(0, 0, 0)
        k.learn(9, a)
        k.learn(9, a)
        k.learn(10, a)
        k.learn(10, v_dist(3000, -1))
        self.T_case("tie_rad", v_dist(700, 1), 3, 0, 0, 0)
        # extremes
        k.reset()
        a = v_mk(127, 0, 0)
        b = v_mk(-127, 0, 0)
        k.learn(9, a)
        k.learn(10, b)
        self.p("DX %d" % l1(a, b))
        self.T_case("ex_p", a, 3, 0, 0, 64)
        self.T_case("ex_n", b, 3, 0, 0, 64)
        self.T_case("ex_z", v_mk(0, 0, 0), 3, 0, 0, 64)
        self.T_case("ex_m", v_mk(127, 4, -127), 3, 0, 0, 64)
        self.T_case("ex_far", v_mk(127, 20, -127), 3, 0, 0, 0)
        self.io_tests(60)
        for i in range(NCLS):
            self.base[i] = v_base(rng)
        k.reset()
        for _j in range(7):
            for i in range(4):
                k.learn(9 + i, v_noisy(rng, self.base[i], 8))
        self.report_state("w")
        self.io_tests(8)


def expected(seed, nscen):
    """Return the list of expected output lines (without the final 'DONE')."""
    r = Replay()
    r.directed()
    for s in range(nscen):
        r.scenario(seed, s)
    r.p("DONE")
    return r.out


if __name__ == "__main__":
    sd = int(sys.argv[1], 0) if len(sys.argv) > 1 else 1
    ns = int(sys.argv[2], 0) if len(sys.argv) > 2 else 10
    print("\n".join(expected(sd, ns)))
# [END AI-GENERATED]
