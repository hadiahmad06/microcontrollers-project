// [AI-GENERATED: Claude Code]
/**
 * @file main_record.c
 * @brief Recording firmware: streams raw LIS3DH windows to the PC (tools/recorder.py) over UART1.
 *
 * UNVERIFIED: not compiled with XC16; register names from memory. Implements SPEC 3.7 G3.
 * WORKING ASSUMPTION: open_questions Q1 (C2), Q2 (trigger C1b), Q3 (keep C1.6), not decided.
 * Build with -DGESTURE_BRINGUP_SAMPLES=1 for bringup.hex (continuous SAMPLES stream, no classifier).
 * The model header may be synthetic-trained; the recorder ignores the on-device result.
 */
#include <stddef.h>
#include <stdint.h>

#include "board.h"

#ifdef HAL_CHECK_STUB_API
#include "gesture_api_stub.h"   /* host check only: gesture.h does not exist yet */
#else
#include "gesture.h"
#endif

/** Blink codes for board_error_blink (see board.h). */
#define ERR_CONFIG  3   /* gesture_init returned -1: odr/range differs from the model */
#define ERR_SENSOR  2   /* gesture_init returned -2: LIS3DH not found / I2C failure */
#define ERR_OTHER   4   /* any other non-zero code */

/**
 * Firmware entry point: init board and library, switch raw streaming on, then poll forever.
 * @return never returns
 */
int main(void)
{
    int8_t rc;

    board_init();

    rc = gesture_init(100U, 4U);       /* 100 Hz ODR, +-4 g (must equal GM_ODR_HZ / GM_RANGE_G of the model) */
    if (rc != 0) {
        if (rc == -1) {
            board_error_blink(ERR_CONFIG);
        } else if (rc == -2) {
            board_error_blink(ERR_SENSOR);
        } else {
            board_error_blink(ERR_OTHER);
        }
    }

    gesture_stream_raw(true);

    for (;;) {
        if (gesture_poll()) {
            (void)gesture_classify(NULL);  /* completes the window; its frame goes out via the C2 stream */
        }
    }
}
// [END AI-GENERATED]
