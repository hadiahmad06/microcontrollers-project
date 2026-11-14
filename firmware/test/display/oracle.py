# [AI-GENERATED: Claude Code]
"""Python oracle for the display.c suite (ticket WP4-aT), built from the SPEC only.

Spec: docs/agent/CONTRACTS.md C6.3 plus main-agent rulings. Framebuffer 64 x 3 (R,G,B) row-major
(pixel = row*8+col, row 0 top). Cap c' = (c*CAP+127)//255. units = sum of capped values;
limit = LIMIT_MA*255//20; if units > limit every capped v -> v*limit//units. Wire image per pixel
G,R,B; with SERPENTINE odd rows are emitted with the column order reversed. Return value of
render = floor(units_after*20/255); display_units = units before limiting.
expected() reproduces the exact text lines test_display.c prints before its ICONS section.
"""

NBYTES = 192
FRAME_NAMES = ["zero", "all255", "one_r255", "one_white", "ramp_a", "ramp_c", "ramp_rev",
               "lim_m1", "lim_eq", "lim_p1", "lim_p2", "lim_x15", "half128"]


class Rng:
    """xorshift32 (13, 17, 5), identical to rnd() in test_display.c."""

    def __init__(self, seed):
        """Seed the generator; 0 is mapped to 1 like the driver.

        :param seed: 32-bit seed.
        """
        self.x = (seed & 0xFFFFFFFF) or 1

    def next(self):
        """Advance and return the next 32-bit value.

        :return: next pseudo-random uint32.
        """
        x = self.x
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self.x = x
        return x


def cap_of(c, cap):
    """Spec cap formula.

    :param c: channel value 0..255.
    :param cap: DISPLAY_CAP.
    :return: capped value.
    """
    return (c * cap + 127) // 255


def limit_of(limit_ma):
    """Spec limiter threshold in units.

    :param limit_ma: DISPLAY_LIMIT_MA.
    :return: limit = limit_ma*255//20.
    """
    return limit_ma * 255 // 20


def render(fb, cap, limit_ma, serp):
    """Reference of display_render() and display_units().

    :param fb: list of 192 ints (R,G,B per pixel, row-major).
    :param cap: DISPLAY_CAP.
    :param limit_ma: DISPLAY_LIMIT_MA.
    :param serp: DISPLAY_SERPENTINE (0/1).
    :return: (wire bytes list of 192, estimated mA after limiting, units before limiting).
    """
    caps = [cap_of(c, cap) for c in fb]
    units = sum(caps)
    limit = limit_of(limit_ma)
    if units > limit:
        caps = [v * limit // units for v in caps]
    after = sum(caps)
    out = []
    for row in range(8):
        for k in range(8):
            col = 7 - k if (serp and row % 2 == 1) else k
            p = row * 8 + col
            out += [caps[3 * p + 1], caps[3 * p], caps[3 * p + 2]]
    return out, after * 20 // 255, units


def frame_target(target, cap):
    """Frame whose capped sum is `target`: 255s first, then the smallest input for the remainder.

    :param target: wanted capped sum.
    :param cap: DISPLAY_CAP.
    :return: list of 192 ints.
    """
    fb = [0] * NBYTES
    for i in range(NBYTES):
        if target <= 0:
            break
        if target >= cap:
            fb[i] = 255
            target -= cap
        else:
            for c in range(256):
                if cap_of(c, cap) == target:
                    fb[i] = c
                    break
            target = 0
    return fb


def build_frame(k, cap, limit_ma):
    """Directed frame k (same order as FRAME_NAMES / build_frame() in the driver).

    :param k: case index.
    :param cap: DISPLAY_CAP.
    :param limit_ma: DISPLAY_LIMIT_MA.
    :return: list of 192 ints.
    """
    limit = limit_of(limit_ma)
    fb = [0] * NBYTES
    if k == 1:
        fb = [255] * NBYTES
    elif k == 2:
        fb[0] = 255
    elif k == 3:
        p = 3 * 8 + 4
        fb[3 * p:3 * p + 3] = [255, 255, 255]
    elif k == 4:
        fb = [i & 0xFF for i in range(NBYTES)]
    elif k == 5:
        fb = [(i + 64) & 0xFF for i in range(NBYTES)]
    elif k == 6:
        fb = [(255 - i) & 0xFF for i in range(NBYTES)]
    elif k == 7:
        fb = frame_target(limit - 1, cap)
    elif k == 8:
        fb = frame_target(limit, cap)
    elif k == 9:
        fb = frame_target(limit + 1, cap)
    elif k == 10:
        fb = frame_target(limit + 2, cap)
    elif k == 11:
        fb = frame_target(limit + limit // 2, cap)
    elif k == 12:
        fb = [128] * NBYTES
    return fb


def bitmap_frame(bits, rgb):
    """Framebuffer after display_draw_bitmap (byte 0 = top row, bit 7 = leftmost column).

    :param bits: 8 row bytes.
    :param rgb: (r, g, b).
    :return: list of 192 ints.
    """
    fb = [0] * NBYTES
    for row in range(8):
        for col in range(8):
            if bits[row] & (0x80 >> col):
                p = row * 8 + col
                fb[3 * p:3 * p + 3] = list(rgb)
    return fb


def scenario_frame(rng, i):
    """Pseudo-random framebuffer of scenario i (mode i%4), consuming 192 draws.

    :param rng: Rng instance.
    :param i: scenario index.
    :return: list of 192 ints.
    """
    mode = i % 4
    fb = []
    for _ in range(NBYTES):
        r = rng.next()
        if mode == 0:
            v = (r >> 8) & 0xFF
        elif mode == 1:
            v = 255 if ((r >> 8) & 3) == 0 else 0
        elif mode == 2:
            v = ((r >> 8) & 0xFF) % 41
        else:
            v = 0 if ((r >> 8) & 3) == 0 else ((r >> 12) & 0xFF)
        fb.append(v)
    return fb


def case_lines(name, fb, cap, limit_ma, serp):
    """The 4 text lines the driver prints for one frame (guard and get checks expected to be 1).

    :param name: case name.
    :param fb: expected framebuffer (192 ints).
    :param cap: DISPLAY_CAP.
    :param limit_ma: DISPLAY_LIMIT_MA.
    :param serp: DISPLAY_SERPENTINE.
    :return: list of 4 strings.
    """
    out, ret, units = render(fb, cap, limit_ma, serp)
    lines = ["C %s %d %d 1 1" % (name, ret, units)]
    for line in range(3):
        lines.append("D " + "".join("%02X" % b for b in out[64 * line:64 * line + 64]))
    return lines


def expected(seed, nscen, cap, limit_ma, serp):
    """Every line the driver prints before the ICONS marker.

    :param seed: run seed.
    :param nscen: number of random scenarios.
    :param cap: DISPLAY_CAP.
    :param limit_ma: DISPLAY_LIMIT_MA.
    :param serp: DISPLAY_SERPENTINE.
    :return: list of expected lines.
    """
    rng = Rng(seed)
    L = ["CFG %d %d %d" % (cap, limit_ma, serp)]
    for k, name in enumerate(FRAME_NAMES):
        L += case_lines(name, build_frame(k, cap, limit_ma), cap, limit_ma, serp)
    corners = [("bm_tl", 0, 0x80), ("bm_tr", 0, 0x01), ("bm_bl", 7, 0x80), ("bm_br", 7, 0x01), ("bm_mid", 2, 0x08)]
    for name, idx, val in corners:
        bits = [0] * 8
        bits[idx] = val
        L += case_lines(name, bitmap_frame(bits, (200, 100, 50)), cap, limit_ma, serp)
    L += case_lines("bm_full", bitmap_frame([0xFF] * 8, (255, 255, 255)), cap, limit_ma, serp)
    L += case_lines("bm_checker", bitmap_frame([0x55 if i & 1 else 0xAA for i in range(8)], (255, 255, 0)),
                    cap, limit_ma, serp)
    for k in range(3):
        bits = [(rng.next() >> 8) & 0xFF for _ in range(8)]
        rgb = tuple((rng.next() >> 8) & 0xFF for _ in range(3))
        L += case_lines("bm_rnd%d" % k, bitmap_frame(bits, rgb), cap, limit_ma, serp)
    oor = [0] * NBYTES
    oor[3 * 63:3 * 63 + 3] = [255, 128, 10]
    L += case_lines("out_of_range", oor, cap, limit_ma, serp)
    L.append("O 1")
    L += case_lines("cleared", [0] * NBYTES, cap, limit_ma, serp)
    scenario_frame(rng, 0)          # the frame loaded before display_clear() in the "cleared" case
    for i in range(nscen):
        L += case_lines("s%d" % i, scenario_frame(rng, i), cap, limit_ma, serp)
    return L
# [END AI-GENERATED]
