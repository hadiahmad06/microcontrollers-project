# TODO (deferred fixes, Hadi)

Things we agreed to fix later. Big fixes, not blockers for bench testing.

- [ ] **T-1: click without INT2** (2026-11-18). The Adafruit LIS3DH breakout has no INT2 pin (CONTRACTS.md C6.1).
  - `firmware/src/lis3dh.c`: write CTRL_REG6 = 0x00 instead of 0x80 (click on INT2 → off).
  - Read `CLICK_SRC` (`lis3dh_read_click()`) on every FIFO drain instead of waiting for `port_take_click_flag()`.
  - `firmware/hal/pic24/board.c` / `port_pic24.c`: drop the RB12 → INT1 PPS mapping and the INT1 ISR (RB12 is spare).
  - Update host tests in `firmware/test/lis3dh/` (fake sensor expects 0x80).
  - Until done: harmless on the breadboard (INT2 simply isn't connected; no click events arrive).
- [ ] **T-2: WS2812 driver is a debug version** (2026-11-18). `firmware/hal/pic24/ws2812_pic24.c` masks interrupts
  for the whole frame (~2 ms) and is timed with C NOP padding, not the C6.3 cycle-counted 4-LED-chunk asm. Scope it, then
  replace per C6.3 before UART RX matters.
- [ ] **T-3: `main.c` debug modes skipped test + review tickets** (2026-11-18, written in a hurry for bench testing).
