// [AI-GENERATED: Claude Code]
/**
 * @file gesture_api_stub.h
 * @brief Stand-in for firmware/src/gesture.h so the host `check` target works before gesture.h
 *        exists. Used only under -DHAL_CHECK_STUB_API. The eight prototypes are copied from
 *        docs/agent/CONTRACTS.md section "API" (decided 2026-11-14). Never part of a target build.
 */
#ifndef GESTURE_API_STUB_H
#define GESTURE_API_STUB_H

#include <stdbool.h>
#include <stdint.h>

int8_t  gesture_init(uint8_t odr_hz, uint8_t range_g);
void    gesture_set_trigger(uint16_t threshold_mg);
bool    gesture_poll(void);
int8_t  gesture_classify(uint8_t *confidence);
int8_t  gesture_learn(uint8_t class_id);
void    gesture_set_reject(uint8_t min_conf);
void    gesture_stream_raw(bool on);
uint8_t gesture_events(void);

#endif /* GESTURE_API_STUB_H */
// [END AI-GENERATED]
