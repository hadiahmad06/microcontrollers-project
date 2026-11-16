// [AI-GENERATED: Claude Code]
/**
 * @file gesture_port.h
 * @brief Board port of the gesture library: the only hardware dependency of gesture.c besides
 *        lis3dh_hal.h (SPEC 3.7 G1). The PIC24 board implements these in
 *        firmware/hal/pic24/port_pic24.c; host tests implement them with fakes.
 *
 * All five functions are called from the main loop only.
 */
#ifndef GESTURE_PORT_H
#define GESTURE_PORT_H

#include <stdbool.h>
#include <stdint.h>

/**
 * Free space in the UART1 TX ring.
 * @return free bytes, 0..255 (a 128 B ring reports at most 127)
 */
uint8_t port_tx_room(void);

/**
 * Append bytes to the UART1 TX ring and make sure they start to go out.
 * @param p pointer to the bytes to send (not retained after return)
 * @param n number of bytes; the caller guarantees n <= port_tx_room()
 */
void port_tx_write(const uint8_t *p, uint8_t n);

/**
 * Free-running millisecond counter.
 * @return milliseconds since start-up, wrapping at 65536; compare with wrap-safe uint16 subtraction
 */
uint16_t port_millis(void);

/**
 * Has INT0 (LIS3DH INT1, FIFO watermark/overrun) fired since the last call?
 * @return true once per event burst; the flag is read and cleared atomically
 */
bool port_take_fifo_flag(void);

/**
 * Has INT1 (LIS3DH INT2, click) fired since the last call?
 * @return true once per event burst; the flag is read and cleared atomically
 */
bool port_take_click_flag(void);

#endif /* GESTURE_PORT_H */
// [END AI-GENERATED]
