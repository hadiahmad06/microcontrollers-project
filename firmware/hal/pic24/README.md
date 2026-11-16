<!-- [AI-GENERATED: Claude Code] -->
# PIC24FJ64GA002 board layer and recording firmware

**UNVERIFIED: this code was never compiled with XC16.** It was written in a container without XC16;
the only check done is a host syntax check against a hand-written register mock (`make -C firmware/build check`).
Register and config-pragma names are from memory. Work through the checklist at the end first.

## Files
| File | Purpose |
|---|---|
| `board.[ch]` | clock check, pins (`AD1PCFG`), PPS, Timer1 1 ms tick, `board_debug_pin`, `board_error_blink` |
| `port_pic24.c` | `gesture_port.h`: UART1 TX ring + ISR, INT0/INT1 flags, `port_millis` |
| `lis3dh_hal_pic24.c` | `lis3dh_hal.h` on I2C1 (400 kHz, polled, bounded waits) |
| `config_bits.c` | `#pragma config` words (C6a 3.8) |
| `p24_regs.h` | one include switch: `<xc.h>` or the host mock |
| `test/p24_mock.h`, `test/gesture_api_stub.h` | host check only |
| `../app/main_record.c` | recording app (SPEC 3.7 G3) |
| `../build/Makefile` | `record.hex`, `bringup.hex`, `check` |

## Build (Mac, XC16 v2.10)
```
make -C firmware/build record.hex  MODEL=/abs/path/to/gesture_model.h
make -C firmware/build bringup.hex MODEL=/abs/path/to/gesture_model.h   # -DGESTURE_BRINGUP_SAMPLES=1
make -C firmware/build check                                            # host syntax check only
```
`XC16=/path/to/xc16/bin` overrides the default `/Applications/microchip/xc16/v2.10/bin`. The `.map` file
(`record.map`) must be checked: RAM headroom >= 25 %, stack 512 B, all `const` data in one PSV page (C7).
`MODEL` is copied to `firmware/build/gesture_model.h` (found first via `-iquote .`).
The Makefile compiles all of `firmware/src/*.c` including `display.c`/`icons.c`; if those need
hardware that is not wired, exclude them.

## Flash
MPLAB X IPE with a PICkit (or ICD): select device PIC24FJ64GA002, load `record.hex`, Program.
Power the board at 3.3 V. The programmer must be on PGC1/PGD1 (pins 5/4) to match `ICS = PGx1`.

## Wiring
| PIC pin | Port | Use | Connect to |
|---|---|---|---|
| 16 | RB7 / INT0 | LIS3DH INT1 | LIS3DH INT1 |
| 17 | RB8 / SCL1 | I2C1 clock | LIS3DH SCL + 2.2 to 4.7 kohm pull-up to 3.3 V |
| 18 | RB9 / SDA1 | I2C1 data | LIS3DH SDA + pull-up |
| 23 | RB12 / RP12 | INT1 via PPS | LIS3DH INT2 |
| 24 | RB13 / RP13 | U1TX | USB-serial adapter RX (3.3 V logic) |
| 25 | RB14 / RP14 | U1RX | USB-serial adapter TX |
| 11 | RB4 | debug pin / error blink | LED + resistor or scope |
| 19 / 20 | DISVREG / VCAP | tie 19 to VSS, capacitor on 20 | per DS39881 section 2.4 |
| 4, 5 | PGED1, PGEC1 | programmer | PICkit |

LIS3DH CS must be tied high (I2C mode); SA0 selects 0x18 or 0x19 (the library probes both).
Error blink on RB4: n pulses, 1 s pause: 1 = PLL did not lock, 2 = sensor not found, 3 = odr/range differs
from the model, 4 = other.

## First bring-up
1. Flash `bringup.hex`. Run `tools/recorder.py` (see its `--help`) at 115200 8N1 on the adapter's port. Expect the boot line
   `GM_MODEL_HASH=0x........`, then HELLO frames every 2 s, then SAMPLES frames at 100 Hz of data (16 rows each).
2. Check the SAMPLES count: about 100 samples per second, no `OVR <n>` lines. If `OVR` appears or rows are missing,
   the INT0 path or I2C drain is too slow.
3. Tilt test (C1 section 3.3 axes): lay the board flat; z should read about +1 g; tilt each edge up in turn and confirm x
   and y change sign as C1 3.3 / `board_axes.h` define. Bits 3..0 of each 16-bit raw value stay zero.
4. Flash `record.hex` and record a gesture; the recorder should receive one WINDOW frame per gesture.
5. Symptoms: board hangs right after boot (nothing on the UART, RB4 silent) -> suspect the TX ISR storm (review F4).
   I2C not found after a reflash -> power-cycle the board (a slave stuck holding SDA; the HAL clocks SCL up to 9 times
   but cannot always free it) (F7).
6. Timing rule: the main loop must reach `gesture_poll` at least every ~11 ms (128 B TX ring at 115200 baud drains in
   about 11 ms; review T-c2txR), so never add blocking code to the loop.
7. Scope RB4 (or the SCL line) to confirm the 400 kHz I2C clock (~394 kHz) and 115200 baud on U1TX (8.7 us per bit).

## Design notes
- TX ring (128 B, 127 usable): lock-free single-producer/single-consumer. Main loop owns `s_head`, the TX ISR owns
  `s_tail`; both are `uint8_t` (atomic on a 16-bit core), each side reads only the other's index, so staleness is
  conservative. The producer forces `U1TXIF = 1` after publishing so no wake-up is lost.
- INT0/INT1 ISRs only set a flag. `port_take_*` masks the single interrupt enable around read-and-clear, so no edge is lost.
- UART1 RX is enabled but has no ISR: this app never receives (C6.1's RX ISR is for the demo firmware).
- Priorities: U1TX 6, INT0 5, INT1 4, Timer1 3, nothing at 7 (C6.2).
- I2C waits are bounded by `I2C_SPIN_MAX` (20000 iterations, several ms); timeout or collision resets I2C1 and returns -1, NACK returns -2.

## UNVERIFIED checklist (tick each on the Mac)
Compile with XC16 first; any "undeclared identifier" is a wrong name from this list.
- [ ] `#pragma config` setting and value names in `config_bits.c`: `JTAGEN`, `GCP`, `GWRP`, `BKBUG`, `COE`, `ICS = PGx1`,
      `FWDTEN`, `WINDIS`, `FWPSA = PR128`, `WDTPS = PS32768`, `IESO`, `FNOSC = FRCPLL`, `FCKSM = CSDCMD`,
      `OSCIOFNC` (spec spells `OSCIOFCN`; polarity of ON/OFF unchecked), `IOL1WAY`, `I2C1SEL = PRI`, `POSCMOD = NONE` (was POSCMD).
- [ ] Oscillator: FRCPLL gives 32 MHz Fosc / 16 MIPS; `CLKDIVbits.RCDIV = 0` really feeds the PLL 8 MHz (C6a 3.8 caveat);
      `OSCCONbits.LOCK` exists and means PLL locked.
- [ ] PPS: `RPINR18bits.U1RXR`, `RPINR0bits.INT1R`, `RPOR6bits.RP13R`; that RPOR6 holds RP12R (low byte) and RP13R (high byte);
      U1TX output function code 3; `__builtin_write_OSCCONL` unlock/lock with the 0xFFBF / 0x0040 masks (IOLOCK = OSCCON bit 6).
- [ ] `AD1PCFG = 0xFFFF` makes RB12..RB15 digital (they are AN12..AN9).
- [ ] Timer1: `T1CON = 0`, `PR1 = 15999` gives 1 ms at FCY = 16 MHz; names `IPC0bits.T1IP`, `IFS0bits.T1IF`, `IEC0bits.T1IE`.
- [ ] Interrupt names: `_T1Interrupt`, `_U1TXInterrupt`, `_INT0Interrupt`, `_INT1Interrupt`; `no_auto_psv` attribute with `-mconst-in-code`.
- [ ] INT regs: `INTCON2bits.INT0EP/INT1EP` (0 = rising), `IPC0bits.INT0IP`, `IPC5bits.INT1IP`, `IPC3bits.U1TXIP`,
      `IFS0bits.INT0IF`, `IFS1bits.INT1IF`, `IEC0bits.INT0IE`, `IEC1bits.INT1IE`, `IFS0bits.U1TXIF`, `IEC0bits.U1TXIE`.
- [ ] UART: `U1MODEbits.BRGH/PDSEL/STSEL/UARTEN`, `U1STAbits.UTXISEL0/UTXISEL1/UTXEN/UTXBF`, `U1BRG = 34`; UTXISEL = 00 raises the
      interrupt whenever the buffer has room; `UTXEN = 1` sets U1TXIF (hence the clear after it).
- [ ] I2C1: `I2C1CONbits.SEN/RSEN/PEN/RCEN/ACKEN/ACKDT/DISSLW/I2CEN`, `I2C1STATbits.TBF/RBF/TRSTAT/ACKSTAT/BCL/IWCOL/I2COV`,
      `I2C1BRG = 38`, `I2C1TRN`, `I2C1RCV`; DISSLW = 0 at 400 kHz; RCEN clears when a byte is in and RBF is set.
- [ ] Linker flags in the Makefile: `-Wl,--heap=0,--stack=512`, `-Map=` (linker script left to `-mcpu`), `-mconst-in-code`,
      `-std=gnu99` (spec says C99; XC16 headers may need GNU mode), `xc16-bin2hex record.elf`.
- [ ] Pin conflicts on the real lab board (C6a open question 1): ICSP set, I2C pins, UART bridge.
- [ ] Stack/RAM in `record.map` within C7 budget.
<!-- [END AI-GENERATED] -->
