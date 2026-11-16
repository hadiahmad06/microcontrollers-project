<!-- [AI-GENERATED: Claude Code] -->
# HAL-R review (review-26): PIC24 HAL, main_record.c, Makefile

Reviewer: review-26, for hadi. Desk check only; no XC16 here. "From memory" = my recollection of Microchip headers, DS39881 and XC16 config_index, not re-read. Reviewed commit e064c1c (fast-forwarded into this worktree).

**Verdict: MERGE AFTER FIXES.** The structure and register-level logic match my memory of the part. Nothing is certainly wrong. One likely compile error (POSCMD pragma name), plus a few things that can bite on the first flash.

`make -C firmware/build check` tail:
```
cc -fsyntax-only ../hal/pic24/port_pic24.c
cc -fsyntax-only ../app/main_record.c
check: OK (mock only; NOT a substitute for an XC16 build)
```
The mock is hand-written, so this proves syntax and C99 hygiene only, not a single register name.

## Findings

1. **HIGH (likely build error), config_bits.c:32.** `#pragma config POSCMD = NONE`. On the GA002 the XC16 setting is, from memory, `POSCMOD` (old header: `_CONFIG2(POSCMOD_NONE & I2C1SEL_PRI & IOL1WAY_OFF & OSCIOFNC_ON & FCKSM_CSDCMD & FNOSC_FRCPLL & IESO_OFF)`; POSCMD is the datasheet bit name). Fix: use `POSCMOD = NONE`; if XC16 rejects it, check config_index.html. Confidence about 75%. Every other CW1/CW2 name and value matches my memory of the canonical `_CONFIG1(JTAGEN_OFF & GCP_OFF & GWRP_OFF & BKBUG_OFF & COE_OFF & ICS_PGx1 & FWDTEN_OFF & WINDIS_OFF & FWPSA_PR128 & WDTPS_PS32768)` line (about 85%).
2. **MEDIUM, config_bits.c:29 and C6a 3.8.** `OSCIOFNC = ON` is, from memory, "OSCO pin is digital I/O (RA3)" (bit = 1), which is the intent. The C6a table says "0 = port I/O", which is the wrong polarity, and the pragma name is OSCIOFNC (the spec's OSCIOFCN is a typo). The code is probably right and the doc wrong; ON vs OFF is harmless anyway (RA3 unused). Confidence 70%. Fix: correct the C6a wording (main agent, top-level doc territory) and keep the pragma.
3. **MEDIUM, port_pic24.c:58-70 (ring ordering).** The header comment says "the compiler may not reorder volatile accesses". That is true only between volatile accesses. `s_ring[]` is non-volatile, so GCC may legally sink the `s_ring[h]=` stores below the volatile `s_head = h` store (producer), or hoist the `s_ring[t]` load above the `s_head` load (ISR). Unlikely at -Os, but it is a silent corruption bug. Fix: put `__asm__ volatile ("" ::: "memory");` before `s_head = h;` in `port_tx_write` and after the `t != s_head` test in the ISR, or declare `s_ring` `volatile uint8_t`. Confidence 80% that it is a real (if unlikely) hazard.
4. **MEDIUM (hardening), port_pic24.c:43-52, 78-83, 106-113. TX interrupt storm risk.** The design relies on U1TXIF being event-based in UTXISEL=00 mode ("a char was moved to the shift register"). From memory that is right on PIC24F (flag set per transfer, 4-deep buffer + TSR), so the software-set U1TXIF does enter the ISR, the ISR drains while !UTXBF, and each later hardware transfer re-raises the flag until the ring is empty. UTXEN=1 also sets U1TXIF, hence the clear after it. Confidence about 75%. If I am wrong and the flag is re-set whenever the buffer has room, the ISR at priority 6 spins forever on an empty ring and the main loop never runs (symptom: board hangs after boot, nothing on the UART). Safer, standard pattern: leave U1TXIE = 0 at init; `port_tx_write` sets `U1TXIE = 1` and `U1TXIF = 1`; the ISR sets `U1TXIE = 0` when the ring empties, taking care not to lose a byte published meanwhile: after clearing IE, re-test `t != s_head` and re-enable if so. Cheap; do it, or at least put "hang after boot = TX ISR storm, see finding 4" in the README bring-up list.
5. **MEDIUM, Makefile:53, 60-68 (model dependency).** `gesture_model.h` is copied by the phony `refresh-model`, which is a prerequisite of the `.elf` only. The objects do not depend on the header, so (a) a changed MODEL does not recompile `mlp.o`, which silently ships the old model, and (b) under `make -j` objects can compile before the copy. Fix: make the copy a real file target, then make every `$(1)_OBJS` depend on `gesture_model.h`. Confidence 90%.
6. **LOW-MEDIUM, Makefile:28 (linker script flag).** `-Wl,-Tp24FJ64GA002.gld`. From memory xc16-gcc selects the device script from `-mcpu` automatically, and the .gld lives in `support/PIC24F/gld`, which may not be on the `-T` search path. An explicit `-T` can therefore fail with "cannot open linker script". Fix: drop it (the spec asks for it, but a default build is the lower-risk first build); if you want it, use `-Wl,--script=p24FJ64GA002.gld`. Confidence 70%. Same line: `--heap=0,--stack=512,-Map=` are right (80%). `--gc-sections` is probably fine but is one more unknown for the first link (ISR/IVT references); drop it for the first build, add it back if flash is tight.
7. **LOW-MEDIUM, lis3dh_hal_pic24.c:47-52 (error recovery).** `i2c_reset()` toggles I2CEN and clears I2C1STAT, but does not free a slave that is holding SDA low mid-byte (after an MCU reset during a transfer, which happens a lot during flashing/debug). The next start then fails with BCL forever. Fix: on reset, if SDA reads low, bit-bang up to 9 SCL pulses on RB8 before re-enabling (or document in the README: power-cycle the board if the sensor is not found after a reflash). Confidence 80%.
8. **LOW, lis3dh_hal_pic24.c:23 (spin bound).** I2C_SPIN_MAX 20000 with about 8-12 FCY per iteration is about 10-15 ms, not "over 4 ms". Fine for correctness (a legal byte is about 23 us), but a dead bus stalls the main loop 10+ ms per failed call, so `gesture_init` probing two addresses can take about 60 ms. Acceptable. Fix: correct the comment.
9. **LOW, lis3dh_hal_pic24.c:56.** `I2C1CON = 0` also clears SCLREL (reset value 0x1000). SCLREL is ignored in master mode, so harmless; Microchip examples leave it at 1. Confidence 75% it does not matter.
10. **LOW, board.c:102-107 (PLL).** Setting `RCDIV = 0` after reset is right (the reset default can be 2:1, from memory of lab code), so the explicit write is good. But the LOCK test right after the write can read a stale LOCK = 1 before the PLL re-locks. Consider a short wait first, or also check `OSCCONbits.COSC == 1`. Timer1 is configured for 16 MIPS before the switch settles, so the first few ms ticks are long; harmless. FRC 8 MHz x4 = 32 MHz, Fcy = 16 MHz is correct. Confidence 80%.
11. **LOW, README / Makefile (`GESTURE_BRINGUP_SAMPLES`).** Nothing in `firmware/src` uses this define yet (gesture.c is missing), so `bringup.hex` equals `record.hex` for now. The 3.7 spec owner must honour it. `main_record.c` includes `gesture.h`, which does not exist, so the real build cannot compile or link yet (documented; the stub keeps `check` green). The stub prototypes match the CONTRACTS API.
12. **INFO, AGENTS.md section 7.** AI markers present on all files; register writes are commented (T1CON, U1MODE/STA, IPCx, INTCON2, I2C1CON/STAT/TRN, AD1PCFG, OSCCON builtin); public functions are documented in the headers; citations are "from memory, page not re-read" and honest. AI_USAGE.md rows are the main agent's job. C7: no printf, no float, no malloc in the HAL or app; Makefile has `--heap=0`, `--stack=512`. `firmware/src/*.c` is globbed; display.c and icons.c are hardware-free (framebuffer, const data), so they compile on XC16 and only cost flash/RAM (192 B framebuffer). c2_stream.c and trigger.c are in the glob too.

## Opinions on the implementer's unsure names (README checklist)
| Item | My opinion |
|---|---|
| Config names JTAGEN/GCP/GWRP/BKBUG/COE/ICS=PGx1/FWDTEN/WINDIS/FWPSA=PR128/WDTPS=PS32768/IESO/FNOSC=FRCPLL/FCKSM=CSDCMD/IOL1WAY/I2C1SEL=PRI | Correct from memory, about 85%. WINDIS polarity is irrelevant with WDT off. |
| POSCMD = NONE | Probably `POSCMOD`, 75% (finding 1). |
| OSCIOFNC ON | Probably correct, 70% (finding 2). |
| FRCPLL = 32 MHz / 16 MIPS, RCDIV = 0, OSCCONbits.LOCK | Correct, 80% (finding 10). |
| RPINR18bits.U1RXR, RPINR0bits.INT1R, RPOR6bits.RP13R; RPOR6 holds RP12R low byte / RP13R high byte; U1TX function code 3 | Correct, 90%. |
| `__builtin_write_OSCCONL(OSCCON & 0xFFBF)` / `\| 0x0040`, IOLOCK = OSCCON bit 6 | Correct, 90%; the builtin does the 0x46/0x57 unlock. |
| AD1PCFG = 0xFFFF frees RB12..RB15 (AN12..AN9) | Correct, 90%. |
| T1: PR1 = 15999 = 1 ms at 16 MHz; IPC0bits.T1IP, IFS0bits.T1IF, IEC0bits.T1IE | Correct, 90%. |
| ISR names `_T1Interrupt`, `_U1TXInterrupt`, `_INT0Interrupt`, `_INT1Interrupt`; `interrupt, no_auto_psv` | Correct, 90%. |
| INTCON2bits.INT0EP/INT1EP (0 = rising), IPC0bits.INT0IP, IPC5bits.INT1IP, IPC3bits.U1TXIP, IFS1bits.INT1IF, IEC1bits.INT1IE | Correct, 85-90%. |
| U1MODEbits.BRGH/PDSEL/STSEL/UARTEN, U1STAbits.UTXISEL0/1/UTXEN/UTXBF; U1BRG = 34 | Names correct 90%. Math right: 16e6/(4*35) = 114286, -0.79%. UTXISEL = 00 semantics: finding 4. |
| I2C1 names; I2C1BRG = 38 | Names correct 85%. 38 is right: 16e6/(38+1+1.6) = 394 kHz (37 gives 404 kHz, over spec). DISSLW = 0 at 400 kHz is right. |
| Start/RSEN/RCEN/ACKEN/NACK-last/STOP sequence, TRSTAT wait for ACK validity | Logic correct, 85%. |
| `-mconst-in-code`, `-std=gnu99`, `xc16-bin2hex record.elf`, `-mcpu=24FJ64GA002`, `xc16-gcc` | Correct, 85%. Linker script option: finding 6. |

## Checked and found fine
SPSC ring index logic (127 usable, room = (tail - head - 1) & 127, uint8 indices atomic, ISR at priority 6 cannot be preempted by main so no tail/head race) apart from compiler ordering (finding 3). INT0/INT1 rising edge (0), priorities 6/5/4/3, nothing at 7. `port_take_*` masking is correct and loses no edge. `IFS0bits.U1TXIF = 1` compiles to one BSET (atomic).
<!-- [END AI-GENERATED] -->
