// [AI-GENERATED: Claude Code]
/**
 * @file gesture_ids.h
 * @brief Gesture class IDs and classifier constants (docs/agent/CONTRACTS.md C5.1, decided
 *        2026-11-14 by Hadi). Shared by knn.h/knn.c, classify.h/classify.c and gesture.h.
 *
 * IDs 0..8 equal the MLP output index. The MLP never emits 9..15. Learned IDs have no
 * meaning across resets. The *_CONF / *_RADIUS_* values are provisional (need recordings).
 */
#ifndef GESTURE_IDS_H
#define GESTURE_IDS_H

#define GESTURE_UNKNOWN        (-1)   /* int8_t: rejected / ambiguous */
#define GESTURE_NONE            0     /* trained class: idle, noise, bumps; "show nothing" */
#define GESTURE_SWIPE_RIGHT     1
#define GESTURE_SWIPE_LEFT      2
#define GESTURE_RAISE           3
#define GESTURE_PUSH_DOWN       4
#define GESTURE_CIRCLE_CW       5
#define GESTURE_CIRCLE_CCW      6
#define GESTURE_TWIST           7
#define GESTURE_THRUST          8
#define GESTURE_LEARNED_BASE    9     /* == GM_N_CLASSES (static-assert) */
#define GESTURE_MAX_LEARNED     4     /* ids 9..12; 13..15 reserved */
#define GESTURE_TEMPLATES_PER_CLASS 5
#define GESTURE_EVT_DOUBLE_TAP  0x01u
#define GESTURE_LEARN_ERR_ID        (-1)
#define GESTURE_LEARN_ERR_NO_WINDOW (-2)
#define GESTURE_OVERRIDE_CONF       192   /* provisional */
#define GESTURE_KNN_RADIUS_MIN      600   /* provisional */
#define GESTURE_KNN_RADIUS_DEFAULT  1200  /* provisional */
#define GESTURE_KNN_RADIUS_MAX      4000  /* provisional */

#endif /* GESTURE_IDS_H */
// [END AI-GENERATED]
