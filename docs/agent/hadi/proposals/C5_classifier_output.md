# C5 proposal: classifier output (class IDs, GESTURE_UNKNOWN, confidence, events)

> Agent draft (research-quant) for `hadi`, ticket S1-3, 2026-11-14. **Not a decision.** Companion to `C4_model_header.md` (provides `margin`, `GM_CONF_SHIFT`, `GM_DEFAULT_REJECT`). Math is exercised by `docs/agent/hadi/spikes/quant/quant_ref.py` (**VERIFIED** to run: tie-break and saturation asserts). Anything not checked is tagged **UNVERIFIED**.

## 1. Decisions needed

**D1. Is class 0 "none" a trained class?**
- (a) Yes: the MLP has 9 outputs; class 0 is trained on idle/noise/bump windows. A confident 0 is returned as ID 0 (not UNKNOWN).
- (b) No: 8 outputs, "none" = rejected result.
RECOMMENDATION (needs Hadi's decision): **(a)**. The motion trigger will fire on bumps and walking; a trained "none" gives the net somewhere to put them, matches the overview (9 classes, `GM_N_CLASSES = 9`), and keeps UNKNOWN meaning "ambiguous", not "nothing happened". Consumers treat 0 as "show nothing".

**D2. Value of `GESTURE_UNKNOWN` and the ID space.**
- (a) `GESTURE_UNKNOWN = -1` (`int8_t`), built-ins 0..8, learned 9..15.
- (b) `GESTURE_UNKNOWN = -128` or `0x7F`. No advantage; -1 is the usual "no result" idiom and `if (id < 0)` works.
RECOMMENDATION (needs Hadi's decision): **(a)**. Learned IDs start at `GM_N_CLASSES` (=9) and are reserved up to 15 (7 slots; fits 4 bits). Firmware limit **`GESTURE_MAX_LEARNED = 4`** (IDs 9..12), matching PLAN §4 (4 classes x 5 templates x 60 B = 1200 B); raisable to 7 at compile time (7x5x60 = 2100 B). `gesture_learn(class_id)` rejects ids outside `[9, 9+GESTURE_MAX_LEARNED-1]`.

**D3. Confidence mapping: (top1 - top2) int32 margin -> uint8.**
- (a) **Saturating shift**: `conf = min(255, margin >> GM_CONF_SHIFT)`. One header constant, 1-2 instructions, trivially bit-exact. Scale granularity is a power of two.
- (b) Multiplier: `conf = min(255, (margin * GM_CONF_M) >> 15)`; finer scale, needs the 32x16 split multiply of C4 D3.
- (c) 256-entry LUT approximating a probability of top1 vs top2 (sigmoid of margin): interpretable as "% sure", costs 256 B flash + calibration; true softmax also depends on the other logits, so it is only an approximation.
- (d) Integer softmax (exp table + division): overkill.
RECOMMENDATION (needs Hadi's decision): **(a)**. The exporter picks `GM_CONF_SHIFT` as the smallest shift for which the 95th percentile of margins of *correctly classified validation windows* is <= 255. Confidence is a rank-friendly score, **not a calibrated probability**; docs must say so. Revisit (c) only if the demo needs "% sure" text.

**D4. k-NN confidence and MLP-vs-kNN arbitration.**
k-NN confidence: `d1` = L1 distance to the nearest template (class A); `d2` = distance to the nearest template **of any other class**; `conf_knn = ((d2 - d1) * 255) / d2` (floor; 0 if `d2 == 0`; 255 if no other-class template exists).
- (a) **kNN-first with gates**: if learned classes exist, accept kNN iff `d1 <= GESTURE_KNN_MAX_DIST` and `conf_knn >= min_conf`; else use the MLP result.
- (b) MLP-first: use kNN only when the MLP is rejected or says class 0.
- (c) Take the larger confidence. Rejected: logit margin and distance ratio are not commensurable.
RECOMMENDATION (needs Hadi's decision): **(a)**. A ReLU MLP is often overconfident on inputs unlike its training data, so a user-taught gesture would likely be labeled as some built-in class with a healthy margin; (b) would hide learned gestures. The absolute gate keeps (a) from hijacking built-ins. `GESTURE_KNN_MAX_DIST` is empirical (**UNVERIFIED, needs recordings**; first guess: 2x the median intra-class template distance at learn time). Distance is L1 over the C4 `x8` vector (the same normalized input the MLP sees; templates cost 60 B; max distance 60*254 = 15240 fits uint16). Note: PLAN task 3.6 says "L1 on int16 features" while PLAN §4 budgets int8 templates; this proposal resolves toward int8 `x8` (flag for Hadi).

**D5. `gesture_set_reject(min_conf)`.**
RECOMMENDATION (needs Hadi's decision): reject iff `confidence < min_conf` (strict, unsigned). `0` disables rejection; applies to MLP and kNN results and to class 0. Default `GM_DEFAULT_REJECT` from the header; **provisional 64**, to be replaced by the exporter's value (suggested rule: smallest value such that <= ~2 % of held-out true gestures are rejected, then report false accepts on a "random wiggle" set). May be called before or after `gesture_init`; persists until reset.

**D6. Double-tap representation.**
- (a) Pseudo class ID: mixes a hardware event into classifier output; can occur with no capture window.
- (b) Separate latched flag `bool gesture_take_double_tap(void)`.
- (c) Event bitmask `uint8_t gesture_events(void)` (read-and-clear) with `GESTURE_EVT_DOUBLE_TAP = 0x01`, other bits reserved.
RECOMMENDATION (needs Hadi's decision): **(c)**. Same cost as (b) (one `volatile uint8_t` set by the click ISR when LIS3DH `CLICK_SRC` (0x39) shows `IA` (bit 6) and `DCLICK` (bit 5); bit positions from the datasheet **recalled from memory, UNVERIFIED**). Independent of `gesture_poll()`/`gesture_classify()`, never a class ID, not subject to `min_conf`.

## 2. Normative spec of the recommended option

```c
/* gesture.h (C5 part) */
#define GESTURE_UNKNOWN        (-1)        /* int8_t: rejected / ambiguous           */
#define GESTURE_NONE            0
#define GESTURE_SWIPE_RIGHT     1
#define GESTURE_SWIPE_LEFT      2
#define GESTURE_RAISE           3
#define GESTURE_PUSH_DOWN       4
#define GESTURE_CIRCLE_CW       5
#define GESTURE_CIRCLE_CCW      6
#define GESTURE_TWIST           7
#define GESTURE_THRUST          8
#define GESTURE_LEARNED_BASE    9          /* == GM_N_CLASSES (static-assert)        */
#define GESTURE_MAX_LEARNED     4          /* ids 9..12; 13..15 reserved             */
#define GESTURE_EVT_DOUBLE_TAP  0x01u
```
IDs 0..8 equal the MLP output index (the exporter must order output neurons that way). The MLP never emits 9..15.

`int8_t gesture_classify(uint8_t *conf)`, once per ready window, after `x8` and logits exist:
```
1. MLP:   id = top1;  c = min(255, margin >> GM_CONF_SHIFT)        # margin>=0 int32 (C4 §2)
2. if n_learned_templates > 0:
       (kid, d1, d2) = knn(x8)     # L1 over x8; d2 = nearest other-class template
       c_k = 255 if no other class else (0 if d2 == 0 else ((uint32)(d2-d1) * 255) // d2)
       if d1 <= GESTURE_KNN_MAX_DIST and c_k >= min_conf:  id, c = kid, c_k
3. if conf != NULL: *conf = c        # written also when rejected
4. return (c < min_conf) ? GESTURE_UNKNOWN : id
```
Ties: argmax lowest index wins; a logit tie gives margin 0, conf 0, hence UNKNOWN for any `min_conf >= 1`. Distance ties: lowest slot index wins. All divisions are floor division of non-negative operands, so C `/` equals Python `//`. `(d2-d1)*255` can reach ~3.9e6, so it needs an explicit `uint32_t` on XC16 (16-bit `int`). With no learned templates, step 2 is skipped (the MLP-only path is the bit-exact target for tickets 3.4/3.5).

Python mirror `classify_ref(x8, logits, templates, min_conf, conf_shift, knn_max_dist) -> (id, conf)`; the test vectors store `(logits, id, conf)` for `min_conf` in {0, default, 255} to cover reject boundaries.

Events: `uint8_t gesture_events(void)` returns and clears pending bits; repeated taps coalesce.

## 3. Details and rationale

- **Why margin, not max logit:** raw logits scale with input magnitude; top1 - top2 cancels the common scale and is the rule already in the overview ("My part" item 3). The pairwise margin times `GM_LOGIT_SCALE` is the log-odds of top1 vs top2 under softmax, so `conf` is monotone in it.
- **Resolution:** logits are < 2^19 + bias (C4), so `GM_CONF_SHIFT` of about 4..10 is expected; exporter asserts `<= 24`.
- **255 is common by design:** the 95th-percentile mapping puts good examples at full scale; `min_conf` trades false rejects vs false accepts in the lower range.
- **k-NN ratio** is Lowe's nearest-neighbor distance-ratio idea in "1 minus ratio" form so 255 = clearly distinct (Lowe 2004, from memory, **UNVERIFIED** citation detail). With one learned class and no other-class template the ratio is undefined, so only the absolute gate protects it; an optional fix is to keep 1-2 class-0 windows as "anti-templates" (+120 B), only if false positives appear.
- **Persistence:** templates are RAM-only and lost at reset (FRAMEWORK_REVIEW T7); IDs 9..12 have no fixed meaning across power cycles.
- **API consistency:** `int8_t` return, `uint8_t *confidence` (NULL allowed), `gesture_set_reject(uint8_t)` as in the overview. Template count per `gesture_learn` call and overwrite policy are WP3's call.

## 4. Open questions
1. Does the display want a distinct icon for UNKNOWN vs 0? (WP4 assumes yes.)
2. `GESTURE_KNN_MAX_DIST`: one global constant or per class computed at learn time? Needs real recordings.
3. Should learning require the MLP to reject/say none first, to avoid relabeling a built-in gesture?
4. Final `GM_DEFAULT_REJECT` (64 is a placeholder) and target false-reject / false-accept rates.
5. Should a double tap during an active capture window invalidate that window (C6/WP1)?
6. Confirm LIS3DH click-register bit positions against the datasheet (UNVERIFIED).
