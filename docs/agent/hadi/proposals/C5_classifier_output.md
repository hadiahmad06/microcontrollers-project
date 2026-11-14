# C5 proposal: classifier output (class IDs, GESTURE_UNKNOWN, confidence, events)

> Agent draft (research-quant) for `hadi`, ticket S1-3, revised 2026-11-14 after review S1-3R. **Not a decision.** Companion to `C4_model_header.md` (provides `margin`, `GM_CONF_SHIFT`, `GM_DEFAULT_REJECT`). Math is exercised by `docs/agent/hadi/spikes/quant/quant_ref.py` (**VERIFIED** to run: `classify_ref`, `class_radius` and the vectors below are asserted in `selftest_c5`). Anything not checked is tagged **UNVERIFIED**.

## 1. Decisions needed

**D1. Is class 0 "none" a trained class?**
- (a) Yes: the MLP has 9 outputs; class 0 is trained on idle/noise/bump windows. A confident 0 is returned as ID 0 (not UNKNOWN).
- (b) No: 8 outputs, "none" = rejected result.
RECOMMENDATION (needs Hadi's decision): **(a)**. The motion trigger will fire on bumps and walking; a trained "none" gives the net somewhere to put them, matches the overview (9 classes, `GM_N_CLASSES = 9`), and keeps UNKNOWN meaning "ambiguous", not "nothing happened". Consumers treat 0 as "show nothing".

**D2. Value of `GESTURE_UNKNOWN` and the ID space.**
- (a) `GESTURE_UNKNOWN = -1` (`int8_t`), built-ins 0..8, learned 9..15.
- (b) `GESTURE_UNKNOWN = -128` or `0x7F`. No advantage; -1 is the usual "no result" idiom and `if (id < 0)` works.
RECOMMENDATION (needs Hadi's decision): **(a)**. Learned IDs start at `GM_N_CLASSES` (=9) and are reserved up to 15 (7 slots; fits 4 bits). Firmware limit **`GESTURE_MAX_LEARNED = 4`** (IDs 9..12), matching PLAN §4 (4 classes x 5 templates x 60 B = 1200 B); raisable to 7 at compile time (7x5x60 = 2100 B). `gesture_learn` rejects other ids (see D2b).

**D2b. `gesture_learn` return type.** The overview declares `void gesture_learn(uint8_t class_id)`, but it must be able to refuse a bad id or a missing window.
RECOMMENDATION (needs Hadi's decision): **`int8_t gesture_learn(uint8_t class_id)`**. Return `>= 1`: number of templates now stored for `class_id` (1..`GESTURE_TEMPLATES_PER_CLASS` = 5; when full, the oldest slot is overwritten round-robin and 5 is returned). Negative: `GESTURE_LEARN_ERR_ID = -1` (id outside `[9, 9+GESTURE_MAX_LEARNED-1]`), `GESTURE_LEARN_ERR_NO_WINDOW = -2` (no captured window / `x8` available). It stores the `x8` vector of the most recent ready window; it never touches the MLP. (Distinct from `GESTURE_UNKNOWN = -1`, which is only a classify result.)

**D3. Confidence mapping: (top1 - top2) int32 margin -> uint8.**
- (a) **Saturating shift**: `conf = min(255, margin >> GM_CONF_SHIFT)`. One header constant, 1-2 instructions, trivially bit-exact. Scale granularity is a power of two.
- (b) Multiplier: `conf = min(255, (margin * GM_CONF_M) >> 15)`; finer scale, needs the 32x16 split multiply of C4 D3.
- (c) 256-entry LUT approximating a probability of top1 vs top2 (sigmoid of margin): interpretable as "% sure", costs 256 B flash + calibration; true softmax also depends on the other logits, so it is only an approximation.
- (d) Integer softmax (exp table + division): overkill.
RECOMMENDATION (needs Hadi's decision): **(a)**. The exporter picks `GM_CONF_SHIFT` as the smallest shift for which the 95th percentile of margins of *correctly classified validation windows* is <= 255. Confidence is a rank-friendly score, **not a calibrated probability**; docs must say so. Revisit (c) only if the demo needs "% sure" text.

**D4. k-NN confidence and MLP-vs-kNN precedence.**
k-NN: `d1` = L1 distance to the nearest template (class A, lowest slot on ties); `d2` = nearest template **of any other class**; `conf_knn = ((d2 - d1) * 255) / d2` (floor; 0 if `d2 == 0`; **255 if no other-class template exists**).
- (a) **kNN-first**, gated only by distance: rejected after review (finding 3): with one learned class `conf_knn` is always 255, so a loose radius lets a template steal a margin-saturated built-in result, and `min_conf = 0` removes the other gate.
- (b) MLP-first: kNN only when the MLP said class 0 or was rejected: safest for built-ins, but a user gesture the MLP confidently mislabels is never learned.
- (c) **Override rule** (recommended): a learned class may override the MLP **only** when its template gates pass **and** the MLP is weak: MLP class 0, or MLP rejected (`c_mlp < min_conf`), or `c_mlp < GESTURE_OVERRIDE_CONF`.
- (d) Compare confidences: rejected (a logit margin and a distance ratio are not commensurable).
RECOMMENDATION (needs Hadi's decision): **(c)**, provisional `GESTURE_OVERRIDE_CONF = 192` (tune on data; 255 would let kNN override everything, `min_conf` makes it (b)). Trade-off accepted: a learned gesture the MLP calls with conf >= 192 is not recognised; tell the demo user to teach gestures the MLP rejects, or add anti-templates (class-0 windows) only if needed.
**Acceptance radius (review finding 4), per class:** `R_c = clamp(2 * lower_median(pairwise L1 of class c's templates), GESTURE_KNN_RADIUS_MIN, GESTURE_KNN_RADIUS_MAX)`; with fewer than 2 templates `R_c = GESTURE_KNN_RADIUS_DEFAULT`. `lower_median` of the sorted `n(n-1)/2` pairwise distances is element `(k-1)//2`. The gate is `d1 <= R_{class of nearest template}`. Provisional constants (**UNVERIFIED, need recordings**): MIN 600 (~10 x8 units per feature), DEFAULT 1200, MAX 4000. L1 is over the C4 `x8` vector (int8 templates, 60 B each, max distance 60*254 = 15240 fits uint16). PLAN task 3.6's old wording "int16 features" is superseded by int8 `x8` (reviewer ruled this sound).

**D5. `gesture_set_reject(min_conf)`.**
RECOMMENDATION (needs Hadi's decision): reject iff `confidence < min_conf` (strict, unsigned). `0` disables rejection; applies to MLP and kNN results and to class 0. Default `GM_DEFAULT_REJECT` from the header; **provisional 64**, to be replaced by the exporter's value (suggested rule: smallest value such that <= ~2 % of held-out true gestures are rejected, then report false accepts on a "random wiggle" set). May be called before or after `gesture_init`; persists until reset.

**D6. Double-tap representation.**
- (a) Pseudo class ID: mixes a hardware event into classifier output; can occur with no capture window.
- (b) Separate latched flag `bool gesture_take_double_tap(void)`.
- (c) Event bitmask `uint8_t gesture_events(void)` (read-and-clear) with `GESTURE_EVT_DOUBLE_TAP = 0x01`, other bits reserved.
RECOMMENDATION (needs Hadi's decision): **(c)**. Same cost as (b) (one `volatile uint8_t` set by the click ISR when LIS3DH `CLICK_SRC` (0x39) shows `IA` (bit 6) and `DCLICK` (bit 5); bit positions confirmed by review S1-3R against the LIS3DH datasheet (Doc ID 17530, §8.26)). Independent of `gesture_poll()`/`gesture_classify()`, never a class ID, not subject to `min_conf`.

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
#define GESTURE_TEMPLATES_PER_CLASS 5
#define GESTURE_LEARN_ERR_ID        (-1)
#define GESTURE_LEARN_ERR_NO_WINDOW (-2)
#define GESTURE_OVERRIDE_CONF       192    /* provisional; tune on data */
#define GESTURE_KNN_RADIUS_MIN      600    /* provisional */
#define GESTURE_KNN_RADIUS_DEFAULT  1200   /* provisional */
#define GESTURE_KNN_RADIUS_MAX      4000   /* provisional */
int8_t gesture_learn(uint8_t class_id);     /* >=1 templates stored, <0 error (D2b) */
```
IDs 0..8 equal the MLP output index (the exporter must order output neurons that way). The MLP never emits 9..15.

`int8_t gesture_classify(uint8_t *conf)`, once per ready window, after `x8` and logits exist:
```
1. MLP:   id = top1;  c = min(255, margin >> GM_CONF_SHIFT)        # margin >= 0 int32 (C4 §2)
2. if n_learned_templates > 0:
       k = nearest template (L1 over x8, lowest slot on ties); kid = its class; d1 = its distance
       d2 = nearest distance among templates of other classes (none -> c_k = 255)
       c_k = 255 if none else (0 if d2 == 0 else ((uint32_t)(d2 - d1) * 255) / d2)
       weak = (id == 0) or (c < min_conf) or (c < GESTURE_OVERRIDE_CONF)
       if weak and d1 <= R[kid] and c_k >= min_conf:  id, c = kid, c_k
3. if conf != NULL: *conf = c        # written also when rejected
4. return (c < min_conf) ? GESTURE_UNKNOWN : id
```
Ties: argmax lowest index wins; a logit tie gives margin 0, conf 0, hence UNKNOWN for any `min_conf >= 1`. Distance ties: lowest slot index wins. All divisions are floor division of non-negative operands, so C `/` equals Python `//`. `(d2-d1)*255` can reach ~3.9e6, so it needs an explicit `uint32_t` on XC16 (16-bit `int`). With no learned templates, step 2 is skipped (the MLP-only path is the bit-exact target for tickets 3.4/3.5).

Python mirror: `classify_ref(x8, logits, templates, min_conf, conf_shift, t_ovr) -> (id, conf)` in `quant_ref.py` (**VERIFIED**). Required test vectors (all asserted in `selftest_c5`; one learned class 9 with a single template at L1 distance 4 from the window, so no other-class template, `c_k = 255`):

| case | MLP | expected (id, conf) |
|---|---|---|
| confident built-in within radius (margin conf 255) | class 3, 255 | (3, 255): MLP must win |
| weak MLP (conf 100 < 192) | class 3, 100 | (9, 255) |
| MLP class 0, conf 255 | 0, 255 | (9, 255) |
| MLP rejected (conf 30 < min_conf 64) | class 3, 30 | (9, 255) |
| window outside radius, MLP conf 30 / 255 | | (-1, 30) / (3, 255) |
| no templates, all logits tied, min_conf 1 / 0 | | (-1, 0) / (0, 0) |
| two learned classes, d1=4, d2=40 | margin 0 | (9, 229) |
Include the same boundaries for `min_conf` in {0, default, 255} in the exported on-target vectors.

Events: `uint8_t gesture_events(void)` returns and clears pending bits; repeated taps coalesce.

## 3. Details and rationale

- **Why margin, not max logit:** raw logits scale with input magnitude; top1 - top2 cancels the common scale and is the rule already in the overview ("My part" item 3). If (and only if) the model is trained with softmax cross-entropy, the margin times the logit scale (`GM_LOGIT_SCALE_Q32 / 2^32`) is the log-odds of top1 vs top2, so `conf` is monotone in it. It is still a score, not a calibrated probability.
- **Resolution:** logits are < 2^19 + bias (C4), so `GM_CONF_SHIFT` of about 4..10 is expected; exporter asserts `<= 24`.
- **255 is common by design:** the 95th-percentile mapping puts good examples at full scale; `min_conf` trades false rejects vs false accepts in the lower range.
- **k-NN ratio** is Lowe's nearest-neighbor distance-ratio idea in "1 minus ratio" form so 255 = clearly distinct (Lowe 2004, from memory, **UNVERIFIED** citation detail). With one learned class and no other-class template the ratio is undefined (`c_k = 255` by definition), so the per-class radius and the MLP-weakness condition of D4(c) are the protection; an optional fix is to keep 1-2 class-0 windows as "anti-templates" (+120 B), only if false positives appear.
- **Persistence:** templates are RAM-only and lost at reset (FRAMEWORK_REVIEW T7); IDs 9..12 have no fixed meaning across power cycles.
- **API consistency:** `int8_t` return, `uint8_t *confidence` (NULL allowed), `gesture_set_reject(uint8_t)` as in the overview. `gesture_learn` returns a status (D2b); one template per call, round-robin overwrite.

## 4. Open questions
1. Does the display want a distinct icon for UNKNOWN vs 0? (WP4 assumes yes.)
2. Provisional constants (`GESTURE_OVERRIDE_CONF` 192, radius MIN/DEFAULT/MAX 600/1200/4000, `GM_DEFAULT_REJECT` 64) all need real recordings; who collects the 5-template spread data?
3. Should learning require the MLP to reject/say none first, to avoid relabeling a built-in gesture?
4. Final `GM_DEFAULT_REJECT` (64 is a placeholder) and target false-reject / false-accept rates.
5. Should a double tap during an active capture window invalidate that window (C6/WP1)?
6. (Resolved by review S1-3R: LIS3DH `CLICK_SRC` IA bit 6, DCLICK bit 5 confirmed against ST Doc ID 17530 Table 57/58.)
