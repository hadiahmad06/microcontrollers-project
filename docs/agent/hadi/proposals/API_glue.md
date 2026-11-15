<!-- [AI-GENERATED: Claude Code] -->
# gesture.c glue design (ticket 3.7): proposal

Author: Hadi's main agent, 2026-11-15. **Status: design note for ticket 3.7, not a decision.** The public API itself is
decided (CONTRACTS "API"); this note only says how the eight functions compose the modules that now exist and are
tested. It assumes Q1 (C2) and Q2 (trigger, C1b) are accepted as recommended; where they are not, the affected rows say so.

## 1. State owned by gesture.c (static)
| Item | Bytes | Notes |
|---|---:|---|
| `min_conf` | 1 | default `GM_DEFAULT_REJECT` (via `mlp_model_info`), set by `gesture_set_reject` |
| `stream_on` | 1 | `gesture_stream_raw` |
| `events` | 1 | volatile; set by the click ISR flag handler, read-and-clear by `gesture_events` |
| `x8_last[60]`, `x8_valid` | 61 | x8 of the most recent READY window (C1.12, B4): `gesture_learn` uses it |
| trigger state | ~16 | C1b `trigger_t` |
| ISR flags | 2 | INT0 (watermark) and INT1 (click) set flags only (C1.4, C6.2) |

## 2. The eight functions
| Function | Composition |
|---|---|
| `gesture_init(odr, range)` | `mlp_model_info` → return −1 if `odr != GM_ODR_HZ` or `range != GM_RANGE_G` (C4 D6); `knn_reset`; `capture_init`; `trigger_init` (C1b defaults: S = 3, 250 mg); `lis3dh_init(&board_axes)` → −2 on `LIS3DH_ERR_SENSOR`, −3?? on `LIS3DH_ERR_BUS` (**gap:** the API only defines 0/−1/−2; proposal: report a bus error as −2 "sensor not usable"); `capture_arm`; enable INT0/INT1 (board HAL); print `GM_MODEL_HASH` (C4 D6) only as ASCII between frames (C2 §3.11). |
| `gesture_set_trigger(mg)` | `trigger_set_threshold_mg(mg)` (C1b decision 3). |
| `gesture_poll()` | Non-blocking service step, called every main-loop iteration: (1) if the INT0 flag is set or 50 ms passed since the last drain (C1.4 backstop), call `lis3dh_drain(cb, …, &ovr, &more)`; the per-sample callback runs `t = trigger_feed(s)`, then `opened = capture_push(s, t)`; if `t && !opened` → `trigger_release()` (C1b F-11); (2) if `ovr`: `if (capture_overrun()) trigger_release()` (C1.6; returns from WP1-aF); (3) if the INT1 flag is set: `if (lis3dh_read_click() == 1)` set `GESTURE_EVT_DOUBLE_TAP` (C5.2); (4) run the C2 TX pump if `stream_on`; (5) return `capture_state() == CAPTURE_READY`. A `more == true` drain is continued on the next call (bounded per call). |
| `gesture_classify(&conf)` | Requires READY (else return `GESTURE_UNKNOWN`, conf 0). `features_extract(capture_buffer(), feat)` → `top1 = mlp_forward(feat, x8_last, logits, &margin)`, `x8_valid = 1` → `have = knn_query(x8_last, &k)` → `id = classify_decide(top1, margin, info.conf_shift, have ? &k : NULL, min_conf, &conf)`. If `stream_on`: queue the C2 WINDOW frame with the result (C2 §3.4 SENDING), and release when its last byte is queued; else `capture_release()` immediately (then `trigger_release()`). Return `id`. |
| `gesture_learn(id)` | If `!x8_valid` → `GESTURE_LEARN_ERR_NO_WINDOW`; else `knn_learn(id, x8_last)` (returns count or `GESTURE_LEARN_ERR_ID`). **Ordering rule (C1.12):** the application calls `gesture_learn` right after `gesture_classify` on the same window; `x8_last` keeps that window's vector even after the buffer is released, so the C1.12 constraint is met by keeping x8, not the raw buffer (no extra RAM: 61 B already counted as the MLP working set). |
| `gesture_set_reject(m)` | `min_conf = m` (works before or after init: C5.2). |
| `gesture_stream_raw(on)` | `stream_on = on`; on enable send a HELLO (C2 decision 8). **If Q1 is not accepted:** a no-op stub that keeps the API. |
| `gesture_events()` | Atomically read-and-clear `events` (mask INT1 for 2 instructions or use a single-word read/clear). |

## 3. Interrupts and priorities (C6.2)
INT0 (prio 5) and INT1 (prio 4) ISRs only set a flag and clear their IF. UART1 TX (prio 6, shared level with RX) moves
bytes from the TX ring. No ISR at 7. The display `ws2812_show()` (not yet written) is called by the application from
the main loop only and returns BUSY while a drain is pending (C6.3 rule 1).

## 4. Gaps found while writing this
1. `gesture_init` has no code for an I2C bus error (`LIS3DH_ERR_BUS`); proposal: map it to −2.
2. The C1b trigger module is still a spike under `docs/agent/hadi/spikes/trigger/`; after Q2 it is promoted to
   `firmware/src/trigger.c/.h` (impl + test + review tickets, same pattern as 3.3).
3. The C2 TX pump is not written; after Q1 it becomes `firmware/src/c2_tx.c/.h` (promoting the spike's CRC and frame
   layout; the incremental pump of C2 §3.5).
4. The board HAL (`lis3dh_hal_*` on I2C1, UART1, INT0/INT1, PPS, config words) needs XC16 headers: Mac session.

## 5. Tickets this creates (after Q1/Q2)
T-trig (promote trigger, +T, +R), T-c2tx (TX pump, +T, +R), 3.7 (gesture.c, +T on host with the fake LIS3DH from
`firmware/test/lis3dh/` and the e2e models, +R), HAL-pic24 (Mac).
<!-- [END AI-GENERATED] -->
