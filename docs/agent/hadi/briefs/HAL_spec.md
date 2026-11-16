<!-- [AI-GENERATED: Claude Code] -->
# SPEC HAL: PIC24FJ64GA002 board layer + recording firmware (UNVERIFIED until built with XC16 on Hadi's Mac)

Goal: Hadi builds one image with XC16 v2.10 (`xc16-gcc -mcpu=24FJ64GA002`), flashes it, plugs in the USB-serial
adapter and records with `tools/recorder.py`. No XC16 exists in this cloud container: the code cannot be compiled
for target here. Everything must be written so a human can check it against the datasheet line by line.

## H1. Sources that are part of this spec (read them)
- `docs/agent/CONTRACTS.md` C6.1 (pins, I2C1 400 kHz BRG 38, UART1 115200 BRGH=1 U1BRG=34, INT0/INT1 + PPS, config
  words), C6.2 (interrupt priorities), C1.4 (drain from the main loop, ISR only sets a flag), C7 build rules.
- `docs/agent/hadi/proposals/C6a_sensor_io.md` §3 (config words §3.8, PPS, oscillator FRCPLL 32 MHz / 16 MIPS).
- `docs/agent/hadi/briefs/3.7_spec.md` G1 (the port functions you implement) and G3 (the app).
- `firmware/src/lis3dh_hal.h` (the two I2C functions you implement).

## H2. Files
- `firmware/hal/pic24/board.h`, `board.c`: `board_init()` (oscillator per C6a, `AD1PCFG = 0xFFFF`, PPS unlock/map/lock:
  U1TX → RP13, U1RX ← RP14, INT1 ← RP12; RB4 debug pin output), Timer1 1 ms tick (priority 3), `board_debug_pin(bool)`,
  `board_error_blink(uint8_t code)` (toggles RB4 forever: the only blocking function, app use only, documented).
- `firmware/hal/pic24/port_pic24.c`: `gesture_port.h` on UART1 (TX ring 128 B, TX ISR priority 6 moves bytes from the
  ring to U1TXREG while `!U1STAbits.UTXBF`; enable/disable U1TXIE around ring updates or use a lock-free single-producer
  single-consumer index pair: say which, and why it is safe on a 16-bit core), `port_millis` (Timer1 counter, read
  atomically), INT0/INT1 ISRs (rising edge, priorities 5 and 4) that only set volatile flags and clear their IF;
  `port_take_*` read-and-clear atomically.
- `firmware/hal/pic24/lis3dh_hal_pic24.c`: `lis3dh_hal_write/read` on I2C1 master, polled (main loop only, allowed by
  `lis3dh_hal.h`), with a bounded timeout loop on every wait (no infinite spin: return < 0 on timeout), NACK checks,
  repeated start for reads, ACK all but the last byte.
- `firmware/hal/pic24/config_bits.c`: `#pragma config` lines per C6a §3.8, each commented.
- `firmware/app/main_record.c`: 3.7 spec G3.
- `firmware/build/Makefile` (for the Mac): builds `record.hex` from `firmware/src/*.c` (excluding nothing),
  `firmware/hal/pic24/*.c`, `firmware/app/main_record.c` and a model header chosen by `MODEL=path/to/gesture_model.h`
  (copied to `build/gesture_model.h`, `-iquote build` first), with the C7 flags (`--heap=0`, `--stack=512`,
  `-mconst-in-code`, linker script `p24FJ64GA002.gld`, `-Wl,-Map=...`), plus a `bringup.hex` target with
  `-DGESTURE_BRINGUP_SAMPLES=1`. XC16 path default `/Applications/microchip/xc16/v2.10/bin`. Also a `check` target
  that only syntax-checks with the host `cc` against `firmware/hal/pic24/test/p24_mock.h` (see H3).
- `firmware/hal/pic24/README.md`: build, flash (MPLAB X IPE / PICkit), wiring table, first bring-up steps
  (bringup.hex + `recorder.py` SAMPLES check, tilt test of C1 §3.3 axes), and a checklist of every UNVERIFIED item.

## H3. Host syntax check (the only check possible here)
`firmware/hal/pic24/test/p24_mock.h`: a minimal stand-in declaring the SFRs and bit-field structs the HAL uses
(names exactly as in Microchip's `p24FJ64GA002.h`, from your knowledge; mark each as "from memory, UNVERIFIED") and
`__attribute__((interrupt, no_auto_psv))` / `#pragma config` as no-ops for the host. `make -C firmware/build check`
compiles every HAL and app file with `cc -std=c99 -Wall -Wextra -Wconversion -Werror -fsyntax-only` against it.
Header comments of every file: `UNVERIFIED: not compiled with XC16; register names from memory`.

## H4. Rules
C99, fixed-width types, no float/malloc; every register write commented with what each bit field does (AGENTS.md §7);
every ISR only sets flags or moves bytes (C6.2); nothing at priority 7; cite every datasheet / family reference manual
section you rely on (DS39881 for the PIC24FJ64GA004 family, FRM sections for UART/I2C/PPS), saying "from memory, page
not re-read" where true.
<!-- [END AI-GENERATED] -->
