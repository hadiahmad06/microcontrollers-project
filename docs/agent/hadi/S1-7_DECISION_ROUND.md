<!-- [AI-GENERATED: Claude Code] -->
# S1-7 decision round: main agent's recommendations for the Part B gaps

> Working note for Hadi (main agent, 2026-11-14). Companion to `DECISION_SHEET.md`. **Nothing here is decided.**
> Part B items where the proposals already agree (B4, B5, B6) just take the proposal's recommendation.
> Items with no recommendation in any proposal (B2 rule, B7, B8, B9, B10, B11) get one here, marked **MAIN-AGENT**, so
> every item can be answered with a yes/no.

## Errata found while checking the sheet (main agent pass, 2026-11-14)
- C3 §1 D4 cost row: "5-9k cycles per window (about 1.3-2.2 ms at 4 MIPS)". At the 16 MIPS used everywhere
  else that is **0.3-0.56 ms**. The cycle estimate itself is unchanged.
- B1: C6a D7's wording ("if C6b's RB13/RB14 stands, use (b)") predates C6b revision 2, which now recommends
  layout (a). Both proposals now point to (a); the sheet already says so.
- No other mismatch found between the sheet's Part A rows and C1, C3, C4, C5, C6a, C6b, C7 (all read in full or
  in the decision sections). Independent check: `reviews/S2-0R.md` (review-6).

## Part B recommendations

| ID | Recommendation | Why | Origin |
|---|---|---|---|
| B1 | Layout (a): WS2812 RB15, UART1 TX/RX RB13/RB14, debug RB4. Provisional until the lab-board check (C-1, C-2) | Both proposals now point to (a); leaves more free pins | C6a D7, C6b D7 |
| B2 | **Software threshold trigger** on drained samples; hardware IA1 stays an optional wake-up. Threshold rule, default and units go into a small follow-up proposal (ticket S2-2) before the capture state machine is coded | Frees an interrupt route, same rule runs in Python on recordings | C6a D8 + MAIN-AGENT (rule ticket) |
| B3 | Take C3-D4 = `isqrt(SS)` (mode 1). C3 owns the `nonneg` flag: odd feature index (energy) = non-negative; it ships as a constant/table in `features.h` and `features_ref.py`, and the exporter reads it from there | One owner; the flag follows from C3-D5's ordering | C3 D4 + MAIN-AGENT (owner) |
| B4 | int8 `x8` templates; `gesture_learn` stores the `x8` of the most recent READY window, so it must be called before the C1 buffer is released; fallback (d) only if k-NN stays int8 | Already consistent in C4/C5/C7 | C5 D4, C7 D2 |
| B5 | C6b-D2 (ii) and the §4.4 rules; add C6b §4.3 rule (3) "host does not transmit during show" only if C2 needs PC→wand traffic during animations (D-6) | Proposals agree | C6b D2 |
| B6 | RAM-only for the MVP, with `knn_export()` / `knn_import()` (version + count + data + CRC16). P2 if persistence is wanted later | Proposals agree; persistence is a team question (D-5) | C7 D4 |
| B7 | **Cap drain bursts at 16 samples: staging = 96 B, capture path = 1092 B** | C1's drain loop already allows it ("96 B if bursts are capped at 16"); C7's table already uses 96; one more loop pass costs ~0.1 ms | MAIN-AGENT |
| B8 | **Lock 100 Hz, ±4 g, 12-bit, 150 samples for v1.** Revisit via §5B only if bench tests show missed taps (C6a D6) or clipping (C-8) | Every proposal and both spikes assume it; changing it later is a contract change anyway | MAIN-AGENT |
| B9 | **Priorities: UART1 RX = 6, INT0 (FIFO watermark) = 5, INT1 (click) = 4, timers = 3, everything else <= 2; nothing at 7.** Every ISR only sets flags / moves bytes (<= 15 µs) | RX is the only source that cannot tolerate masking (4-deep FIFO); watermark has a 160 ms deadline, click is human-scale; 7 is forbidden by C6b §4.4 | MAIN-AGENT |
| B10 | **Ignore: a double tap during an open window does not invalidate it.** The event is still reported via `gesture_events()` | C5 D6 makes events independent of capture; a tap inside a gesture will usually just be classified as noise/none; simpler state machine | MAIN-AGENT |
| B11 | **`int8_t gesture_init(uint8_t odr_hz, uint8_t range_g)`: 0 = OK, -1 = ODR/range mismatch with the model, -2 = sensor not found (WHO_AM_I).** `gesture_learn` returns `int8_t` (C5 D2b); add `uint8_t gesture_events(void)` (C5 D6); `gesture_set_trigger` keeps its signature, meaning set by S2-2. Public API = 8 functions | init already probes the sensor (C6a D2) and refuses mismatches (C4 D6); a status is the only way to report either | MAIN-AGENT |

## Proposed follow-up tickets created by these recommendations
- **S2-2** Trigger rule proposal (B2): the exact software threshold test on drained samples, its units (`threshold_mg`
  → counts at ±4 g, 2 mg/LSB), the default, the refractory time, and the Python mirror. Small, research.
<!-- [END AI-GENERATED] -->
