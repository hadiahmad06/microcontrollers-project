// [AI-GENERATED: Claude Code]
/* STAND-IN (test harness proof only, written from the spec by test-lis3dh; the real file is
 * firmware/src/board_axes.h). Axis remap table: out[i] = sign[i] * in[src[i]]. */
#ifndef BOARD_AXES_H
#define BOARD_AXES_H
#include <stdint.h>

typedef struct { uint8_t src[3]; int8_t sign[3]; } lis3dh_axes_t;

#endif
// [END AI-GENERATED]
