# C6a proposal: sensor and I/O pin / peripheral allocation (PIC24FJ64GA002, 28-pin)

Author: research-sensor (ticket S1-1), 2026-11-14. **Status: PROPOSAL, not a decision.** Hadi decides.
Fact-checked in `docs/agent/hadi/reviews/S1-1R.md` (APPROVE WITH NITS); fix round applied 2026-11-14. Nothing here was tested on hardware. WS2812 timing and the bulb are out of scope (WP4).

Source keys:
**[PIC]** = Microchip PIC24FJ64GA004 family datasheet DS39881**E** (covers PIC24FJ64GA002, 28-pin), https://ww1.microchip.com/downloads/en/DeviceDoc/39881e.pdf. Page numbers are the printed DS39881E-page numbers.
**[DS]** = ST LIS3DH datasheet DocID17530 Rev 1, https://cdn-shop.adafruit.com/datasheets/LIS3DH.pdf (newest revision not read).
**[AN]** = ST AN3308 (DocID18198) Rev 3, https://core-electronics.com.au/attachments/uploads/lis3dh-application-note.pdf.
**[FRM-I2C]** = Microchip DS70000195F "Inter-Integrated Circuit", https://ww1.microchip.com/downloads/en/DeviceDoc/70000195f.pdf. (The PIC24F-specific FRM I2C section DS39702 returned HTTP 403, so it was not read.)

## 1. Decisions needed

1. **I2C module and pins.** (a) I2C1 default pins SCL1 = pin 17 (RB8), SDA1 = pin 18 (RB9); (b) I2C1 alternate pins ASCL1 = 15 (RB6), ASDA1 = 14 (RB5) via the I2C1SEL configuration bit; (c) I2C2 on SCL2 = pin 7 (RB3), SDA2 = pin 6 (RB2).
   RECOMMENDATION (needs Hadi's decision): (a), with `JTAGEN = OFF` (pins 17/18 are shared with JTAG TCK/TDO). (b) collides with ICSP set 3; (c) needs AN4/AN5 switched to digital in AD1PCFG. Check the lab board first (open question 1).
2. **LIS3DH I2C address.** 0x18 (SA0 = GND) or 0x19 (SA0 = Vdd).
   RECOMMENDATION (needs Hadi's decision): driver takes the address as a compile-time constant and probes both at `init`, verifying WHO_AM_I = 0x33. The value depends on how SA0 is wired (open question 2).
3. **I2C speed.** (a) 100 kHz, I2C1BRG = 157; (b) 400 kHz, I2C1BRG = 37 (404 kHz, about 1% over the LIS3DH 400 kHz limit); (c) 400 kHz with I2C1BRG = 38 (394 kHz).
   RECOMMENDATION (needs Hadi's decision): (c). The bus load is low either way (section 3.2), but a faster bus shortens critical sections and leaves margin; 38 stays inside the sensor's 400 kHz maximum. If bench wiring is long or pull-ups are weak, fall back to (a). The device datasheet formula governs; scope-check SCL at first bring-up (section 3.2).
4. **LIS3DH interrupt routing and PIC pins.** (a) LIS3DH INT1 to PIC INT0 (fixed pin 16), INT2 to PIC INT1 through PPS; (b) both to PPS INT1/INT2; (c) one wire only (OR of all sources on INT1 to INT0); (d) Change Notification pins.
   RECOMMENDATION (needs Hadi's decision): (a). INT1 = FIFO watermark (+ overrun, optionally motion); INT2 = click (+ optionally motion). INT0 is a fixed pin and needs no PPS unlock. Use CN only if a lab board forces a pin that has no INTx option (CN gives any-edge on a shared interrupt and needs a port read to know which pin changed).
5. **UART1 raw-stream baud.** (a) 115200 with BRGH = 1, U1BRG = 34 (-0.79%); (b) 230400 with BRGH = 1, U1BRG = 16 (+2.12%); (c) 250000 with BRGH = 1, U1BRG = 15 (0.00%, check the host adapter supports it).
   RECOMMENDATION (needs Hadi's decision): (a). Raw stream is about 600 B/s of samples plus framing, versus 11.5 KB/s capacity. BRGH = 0 is not recommended: 115200 gives -3.55% error.
6. **Click (double tap) start configuration.** Use the values in section 3.5 as a starting point and tune on the bench. Ask: use all three axes, or Z only?
   RECOMMENDATION (needs Hadi's decision): double-click on all axes at the start, narrow to the axis a tap really excites after bench tests. Concern: click timing is in units of 1/ODR = 10 ms at 100 Hz, which is coarse for a short tap pulse (UNVERIFIED, test). If taps are missed, raise ODR to 200 or 400 Hz (affects C1 and the FIFO depth in seconds).
7. **Pin map and required config words.** Proposed in sections 3.7 and 3.8. Conflict with C6b, which puts WS2812 data on RB13 (and IR/OC1 on RB14), where my map has UART TX/RX. Options: (a) this map: WS2812 = RB15 (pin 26), UART TX/RX = RB13/RB14; (b) C6b's choice: WS2812 = RB13 (pin 24), UART TX = RB15 (pin 26), UART RX = RB4 (pin 11, RP4), debug pin = RA4 (pin 12). Both keep INT0 = RB7, I2C1 = RB8/RB9, LIS3DH INT2 = RB12.
   RECOMMENDATION (needs Hadi's decision): adopt after the lab-board check; if C6b's RB13/RB14 stands, use (b). I did not edit C6b.
8. **Trigger source (cross-link C1).** Hardware motion interrupt (IA1 on INT2, shared with click) versus software threshold on drained samples.
   RECOMMENDATION (needs Hadi's decision): software threshold first (frees an interrupt route, same rule runs in Python), keep IA1 as an optional wake-up.

## 2. Facts

| Fact | Value | Source |
|---|---|---|
| Part and 28-pin I2C pins | SCL1 = 17, SDA1 = 18, SCL2 = 7, SDA2 = 6 (SPDIP/SSOP/SOIC) | [PIC] Table 1-2 (p.15); pin diagram (p.2) |
| Alternate I2C1 pins | ASCL1 = 15 (RB6), ASDA1 = 14 (RB5); selected by config bit I2C1SEL = 0 (1 = default pins) | [PIC] Table 1-2 (p.11); sec 16.1 (p.151); Register 24-2 CW2 bit 2 (p.213) |
| I2C is not remappable | "The I2C modules are tied to fixed pin assignments and cannot be reassigned ... using Peripheral Pin Select" except the I2C1 alternate pins above | [PIC] sec 16.1 (p.151); sec 10.4.2 (p.107) |
| I2C pins shared with JTAG | pin 17 = TCK/SCL1/RP8/RB8, pin 18 = TDO/SDA1/RP9/RB9. JTAGEN config bit: 1 = JTAG enabled, 0 = disabled; unprogrammed default is 1 = ENABLED (CW1 R/PO-1, S1-1R) | [PIC] pin diagram (p.2); Register 24-1 CW1 bit 14 (p.210) |
| ICSP pairs on 28-pin | PGEC1/PGED1 = pins 5/4 (RB1/RB0); PGEC2/PGED2 = pins 22/21 (RB11/RB10); PGEC3/PGED3 = pins 15/14 (RB6/RB5) per the pin diagram. **Table 1-2 lists PGEC3 = 14 and PGED3 = 15, which contradicts the pin diagram and its own RP5/RP6 rows.** Not used in my map. | [PIC] pin diagram (p.2); Table 1-2 (p.13) |
| ICSP pair selection | CW1 ICS<1:0>: 11 = PGC1/PGD1, 10 = PGC2/PGD2, 01 = PGC3/PGD3 | [PIC] Register 24-1 CW1 bits 9:8 (p.210) |
| Analog default | AD1PCFG resets to 0x0000 = **all pins analog**; set bit = 1 for digital. RB0-RB3 (AN2-AN5) and RB12-RB15 (AN12-AN9) are shared with analog | [PIC] SFR map (p.39); Register 21-5 (p.198) |
| PPS pins on 28-pin | RP0..RP15 = RB0..RB15 only; RA pins are not remappable. PPS peripherals are digital only (not I2C, not Change Notification) | [PIC] Table 1-2 RP rows (p.15); sec 10.4.1-10.4.2 (p.107) |
| External interrupts | INT0 fixed on pin 16 (RB7/RP7); INT1 and INT2 are inputs mapped with RPINR0 (INT1R<4:0>, bits 12:8) and RPINR1 (INT2R<4:0>) | [PIC] Table 1-2 (p.12); Table 10-2 (p.108); Registers 10-1, 10-2 |
| PPS unlock | Write 0x46 then 0x57 to OSCCON<7:0> (OSCCON byte), then clear IOLOCK (OSCCON<6>) | [PIC] sec 10.4.4.1 (p.109) |
| UART1 PPS | U1RX: RPINR18 U1RXR<4:0>; U1TX: RPORx output function number 3 | [PIC] Table 10-2 (p.108), Table 10-3 (p.109) |
| Edge select | INTCON2 INT0EP, INT1EP, INT2EP | [PIC] Register 7-4 INTCON2 (p.65) |
| 5.5 V tolerant pins | PORTB<11:5> tolerate 5.5 V; PORTB<15:12> and PORTB<4:0> and PORTA<4:0> only VDD | [PIC] Table 10-1 (p.106) |
| I2C baud formula | I2CxBRG = FCY/FSCL - FCY/10,000,000 - 1 (FSCL = FCY / (I2CxBRG + 1 + FCY/10,000,000)) | [PIC] Eq. 16-1 (p.153) |
| I2C baud table | 100 kHz at FCY = 16 MHz -> 157 (0x9D), 100 kHz; 400 kHz -> 37 (0x25), 404 kHz | [PIC] Table 16-1 (p.153) |
| Alternate I2C formula | FRM-I2C: I2CxBRG = (1/FSCL - Delay) x FCY - 2, delay about 110-130 ns, "refer to the device data sheet" | [FRM-I2C] Eq. 4-1 (p.19) |
| UART baud formulas | BRGH=0: Baud = FCY / (16 (U1BRG + 1)); BRGH=1: Baud = FCY / (4 (U1BRG + 1)) | [PIC] Eq. 17-1, 17-2 (p.160) |
| LIS3DH address | SAD = 001100x; SA0 = Vdd gives 0011001 (0x19), SA0 = GND gives 0011000 (0x18). 8-bit forms: 0x30/0x31 and 0x32/0x33 | [DS] sec 6.1.1, Table 12 (p.21) |
| WHO_AM_I | register 0x0F, value 0b00110011 = 0x33 | [DS] Table 17 (p.26), sec 8.6 (p.29) |
| LIS3DH I2C speed | standard 100 kHz and fast 400 kHz modes; f(SCL) max 400 kHz | [DS] sec 6.1 (p.20), Table 7 (p.14) |
| Register read | sub-address byte MSB = 1 enables auto-increment; reads use repeated START | [DS] sec 6.1.1 (p.21) |
| LIS3DH supply | Vdd 1.71 to 3.6 V; Vdd_IO 1.71 to Vdd + 0.1 V; VIH min 0.8 x Vdd_IO | [DS] Table 5 (p.12) |
| INT pin config | CTRL_REG3 (0x22) routes to INT1; CTRL_REG6 (0x25): I2_CLICK b7, I2_IA1 b6, I2_IA2 b5, I2_BOOT b4, I2_ACT b3, INT_POLARITY b1 (0 = active high, 1 = active low) | [AN] Tables 13-16 (p.20-21) |
| Click registers | CLICK_CFG 0x38, CLICK_SRC 0x39, CLICK_THS 0x3A, TIME_LIMIT 0x3B, TIME_LATENCY 0x3C, TIME_WINDOW 0x3D | [DS] Table 17 (p.27), sec 8.25-8.30; [AN] sec 8.3 (p.34-36) |
| Click units | THS: 1 LSB = full scale / 128 (31.25 mg at +-4 g); TIME_LIMIT, TIME_LATENCY, TIME_WINDOW: 1 LSB = 1/ODR | [AN] sec 8.3.3-8.3.6 (p.35-36) |

## 3. Details

### 3.1 I2C pin conflicts (decision 1)
- Pins 17/18 (RB8/RB9) have no analog function, so AD1PCFG does not matter for them. Both are on the 5.5 V tolerant list ([PIC] Table 10-1).
- They double as JTAG TCK/TDO, so the config word needs `JTAGEN = OFF` ([PIC] Register 24-1 CW1, p.210). **Confirmed (S1-1R): the unprogrammed default is 1 = JTAG enabled**, so I2C1 on 17/18 will not work unless it is turned off. (MPLAB X's GUI default was not checked.) OFF also frees TMS/TDI on pins 22/21.
- I2C2 (pins 6/7) works too but those are AN4/AN5; AD1PCFG bits PCFG4 and PCFG5 must be 1, and since AD1PCFG resets to all analog, set AD1PCFG = 0xFFFF in `board_init` for every case.
- The I2C pins are open-drain and need external pull-ups to the LIS3DH Vdd_IO (3.3 V). Use **2.2 to 4.7 kOhm at 400 kHz** (reviewer's rise-time estimate from the I2C rule Rp <= tr / (0.8473 Cb); the I2C spec itself was not read, so UNVERIFIED; 10 kOhm is too weak at 400 kHz with 50-100 pF). Many breakouts already have pull-ups (open question 2). Do not double up blindly (parallel values lower the effective resistance).
- Programming pins: PGEC/PGED sets are not on 17/18, so there is no conflict unless the lab board uses set 3 (pins 14/15) and also wants I2C1 alternate pins (option 1b).

### 3.2 I2C speed and FIFO drain time (decision 3)
BRG at FCY = 16 MHz, using [PIC] Eq. 16-1: I2CxBRG = 16e6/FSCL - 16e6/1e7 - 1 = 16e6/FSCL - 2.6.
- 100 kHz: 160 - 2.6 = 157.4 -> 157, actual 16e6 / (157 + 1 + 1.6) = 100.25 kHz.
- 400 kHz: 40 - 2.6 = 37.4 -> 37 (matches [PIC] Table 16-1), actual 404.0 kHz; 38 gives 394.1 kHz; 36 would give 414.5 kHz (too fast).
- Cross-check, FRM-I2C Eq. 4-1 with 120 ns delay: 156.1 (100 kHz) and 36.1 (400 kHz), one count lower. **Resolved (S1-1R): the device datasheet equation governs** (the FRM itself says "refer to the specific device data sheet" and calls its equation a design guideline). Use 157 / 38. **Bring-up check:** scope SCL at first I2C use; expect about 100 kHz with BRG 157 and about 394 kHz with BRG 38 at FCY = 16 MHz. The table footnote "PLL disabled" is believed irrelevant (the BRG runs from FCY) but only the scope settles it (open question 7).

Drain time, 29 + 9 clocks per byte (as in [AN] sec 9.5: 29 clocks for START, address, sub-address, repeated START, address-read, then 9 per byte; confirmed by S1-1R), bytes = 6 per sample:

| Samples | Bytes | Clocks | 100 kHz (nominal) | 400 kHz (nominal) |
|---|---|---|---|---|
| 1 | 6 | 83 | 0.83 ms | 0.21 ms |
| 16 (watermark burst) | 96 | 893 | 8.93 ms | 2.23 ms |
| 32 (full FIFO) | 192 | 1757 | 17.57 ms | 4.39 ms |

17.57 ms matches the figure in [AN] sec 9.5. The AN rule "read the whole FIFO faster than one ODR period" gives a maximum ODR of 57 Hz at 100 kHz and 228 Hz at 400 kHz, so **at 100 Hz ODR it only holds at 400 kHz** if you want to empty a full FIFO in one ODR period (17.57 ms > 10 ms at 100 kHz). The recommended driver never drains a full FIFO in one go: with FTH = 15 it reads about 16 samples every 160 ms, which is about 5.6% of bus time at 100 kHz and 1.4% at 400 kHz. Both speeds work; 400 kHz leaves margin for the FSS read before each burst (about 38 clocks) and a click/INT1_SRC read.

### 3.3 Interrupt options (decision 4)
- INT0: fixed to RB7 (pin 16). Highest natural priority tie-breaker among the externals ([PIC] sec 7). No PPS.
- INT1/INT2: any of RP0..RP15 via RPINR0/RPINR1 after the unlock sequence ([PIC] sec 10.4.4.1). Needs a digital pin (AD1PCFG = 1).
- CN: all CN pins share one interrupt; ISR must read the port to find the source; useful only if no INTx pin is free. Weak pull-ups available (CNPU1/CNPU2).
- LIS3DH side: INT1 and INT2 are push-pull outputs at Vdd_IO level (active high by default). Latch (LIR_INT1 in CTRL_REG5) the motion source if used; clear by reading INT1_SRC ([DS] sec 8.22). Click uses LIR_Click in CLICK_THS bit 7, cleared by reading CLICK_SRC ([AN] sec 8.3.3).
- Use falling or rising edge as set in INTCON2 (INT0EP etc.); default LIS3DH polarity is active high (CTRL_REG6 INT_POLARITY = 0, confirmed S1-1R), so rising edge.
- **Level versus edge (S1-1R finding 1).** The FIFO watermark flag WTM is a level: it stays 1 while unread samples exceed FTH. INT0 is edge-triggered, so after a burst, if FSS is still above FTH there is no new edge. The INT0 ISR therefore only sets a flag, and the drain task loops: read FIFO_SRC, drain FSS samples, re-read FIFO_SRC, repeat until FSS is below the watermark, then re-arm INT0 (clear its flag, enable it). A main-loop poll of FIFO_SRC at least every 50 ms is the backstop (alternatively read the INT0 pin level, RB7, in the main loop). Full algorithm and RAM: C1 section 3.4.

### 3.4 UART1 baud (decision 5)
Using [PIC] Eq. 17-1/17-2 with FCY = 16 MHz. Error = (actual - target) / target.

| Target | BRGH | U1BRG | Actual | Error |
|---|---|---|---|---|
| 115200 | 0 | 8 | 111111 | -3.55% |
| 115200 | 0 | 7 | 125000 | +8.51% |
| 115200 | 1 | 34 | 114286 | -0.79% |
| 230400 | 0 | 3 | 250000 | +8.51% |
| 230400 | 1 | 16 | 235294 | +2.12% |
| 230400 | 1 | 17 | 222222 | -3.55% |
| 250000 | 1 | 15 | 250000 | 0.00% |

Rule of thumb: keep total error (both ends) under about 3%; no datasheet statement of the tolerance found (UNVERIFIED). PPS: U1TX is output function 3 on any RPn through RPORx; U1RX is mapped via RPINR18 U1RXR<4:0>. UART RX has a 4-level FIFO ([PIC] p.1), so at 115200 (about 87 us per byte) interrupts masked for the 2 ms WS2812 frame can overrun RX; TX only pauses.

### 3.5 Click (double tap) start configuration (decision 6)
Registers ([AN] sec 8.3). All times are 1/ODR, so 10 ms per count at 100 Hz; threshold is 31.25 mg per count at +-4 g.
- `CLICK_CFG (0x38)` = 0x2A: ZD | YD | XD (double click on all axes). Single click is 0x15 (ZS|YS|XS); [AN] Table 22: D=1 gives a double-click output.
- `CLICK_THS (0x3A)` = 0x80 | 0x30: LIR_Click = 1 (latch until CLICK_SRC is read), threshold 48 counts = 1.5 g. Tune upward if wand motion alone triggers it.
- `TIME_LIMIT (0x3B)` = 0x04 (40 ms): maximum time above threshold for one click.
- `TIME_LATENCY (0x3C)` = 0x10 (160 ms): dead time after the first click.
- `TIME_WINDOW (0x3D)` = 0x30 (480 ms): window for the second click after the latency.
- `CTRL_REG6 (0x25)` = 0x80 (I2_CLICK: click on INT2), `CTRL_REG3` I1_CLICK left 0. These numbers are my starting guesses, **not validated**: UNVERIFIED. Read CLICK_SRC in the ISR (bit 5 DCLICK, bit 6 IA).
Spec detail (S1-1R): addresses and bit math confirmed. [AN] Rev 3 shows CLICK_THS bit 7 = LIR_Click (the Rev 1 datasheet shows "-"); TIME_LIMIT bit 7 is unused in both (the "TLI7" text is a typo). Treat [AN] as authoritative; verify latching on hardware (bench check, open question 3).

### 3.6 Interrupt priorities (cross-link C6)
Not decided here. Suggested to discuss: LIS3DH INT1 (watermark, 160 ms deadline) and INT2 (click, human time scale) tolerate 2 ms of masking by the WS2812 bit-bang. UART RX does not (see 3.4). So: do not refresh the matrix while the UART raw-stream receives commands, or give UART RX a lower baud.

### 3.7 Proposed pin map (PROPOSAL, 28-pin SPDIP/SSOP/SOIC numbering)

| Pin | Name | Proposed use | Note |
|---|---|---|---|
| 1 | MCLR | reserved (reset/ICSP) | |
| 2, 3 | RA0, RA1 | spare | analog by default; digital via AD1PCFG |
| 4 | RB0 PGED1 | reserved ICSP data | assumes set 1 |
| 5 | RB1 PGEC1 | reserved ICSP clock | assumes set 1 |
| 6, 7 | RB2 SDA2, RB3 SCL2 | spare | I2C2 not used |
| 8, 27 | VSS | ground | |
| 9, 10 | RA2, RA3 | spare (no crystal) or OSC if board has one | open question |
| 11 | RB4 RP4 | **debug / timing pin** (GPIO out) | for cycle measurement |
| 12 | RA4 | spare | |
| 13, 28 | VDD | 3.3 V | |
| 14 | RB5 | spare, avoid (ICSP set 3, ASDA1) | |
| 15 | RB6 | spare, avoid (ICSP set 3, ASCL1) | |
| 16 | RB7 INT0 | **LIS3DH INT1** | fixed pin |
| 17 | RB8 SCL1 | **I2C1 SCL** to LIS3DH | external pull-up; JTAG off |
| 18 | RB9 SDA1 | **I2C1 SDA** to LIS3DH | external pull-up; JTAG off |
| 19 | DISVREG | **tie to VSS** (enables the on-chip regulator), unless the lab board differs | S1-1R, [PIC] sec 2.4 (p.18) |
| 20 | VCAP | capacitor to VSS per [PIC] sec 2.4 | required when the regulator is on |
| 21, 22 | RB10, RB11 | reserved (ICSP set 2) | avoid |
| 23 | RB12 RP12 | **LIS3DH INT2** -> PIC INT1 (INT1R = 12) | |
| 24 | RB13 RP13 | **UART1 TX** (RPOR function 3) | |
| 25 | RB14 RP14 | **UART1 RX** (U1RXR = 14) | |
| 26 | RB15 RP15 | **WS2812 data out** (GPIO bit-bang) | 3.3 V output; C6b wants RB13 here, see decision 7 and 3.7 note |

Notes: **Cross-check with C6b.** C6b's pin table puts WS2812 data on RB13 (RP13, pin 24) and IR/OC1 on RB14. My map uses RB13/RB14 for UART TX/RX. Options for Hadi (decision 7): (a) this table as drawn (WS2812 = RB15); (b) WS2812 = RB13, UART TX = RB15, UART RX = RB4 (pin 11, RP4), debug pin = RA4 (pin 12). C6b's level shifter (D4) applies in both cases. I did not edit C6b. RB12..RB15 are not 5.5 V tolerant ([PIC] Table 10-1); do not drive them from 5 V sources.

### 3.8 Required configuration words (S1-1R finding 3)
All from [PIC] Registers 24-1 (CW1, p.210) and 24-2 (CW2, pp.212-213). Unprogrammed defaults are 1 for every bit below.

| Setting | Value | Why | Source |
|---|---|---|---|
| `JTAGEN` | OFF (0) | frees pins 17/18 for I2C1 (default is ON) | CW1 bit 14 |
| `ICS` | PGx1 (ICS<1:0> = 11) | debugger on PGC1/PGD1, pins 5/4; keeps sets 2 and 3 free. **Must match the lab board's programmer header** (open question 1) | CW1 bits 9:8 |
| `I2C1SEL` | 1 = default pins (SCL1/SDA1 on 17/18) | 0 selects the alternate pins on 15/14 | CW2 bit 2 |
| `IOL1WAY` | OFF (0) during development (1 allows only one PPS write session) | board_init unlocks and locks PPS once; either works, OFF eases debugging | CW2 bit 4 |
| `FNOSC` | FRCPLL (001): FRC with PLL, to reach Fosc = 32 MHz and FCY = 16 MHz | oscillator assumption, **open question 4**; if the board has a crystal use POSCMD/FNOSC accordingly | CW2 bits 10:8 |
| `POSCMD` | 11 = primary oscillator disabled (for FRCPLL) | frees RA2/RA3 | CW2 bits 1:0 |
| `OSCIOFCN` | 0 = OSCO is port I/O (RA3) when POSCMD = 11 | only if RA3 is used as GPIO | CW2 bit 5 |
| `FWDTEN` | OFF during development | avoids resets during debugging | CW1 bit 7 |
| `GCP`, `GWRP`, `DEBUG` | leave unprotected/enabled for debug | not pin related | CW1 |
| `DISVREG` (pin 19) | tied to VSS in hardware (not a config bit) | on-chip regulator on; VCAP cap needed | [PIC] sec 2.4 (p.18); S1-1R |

Assumption flagged for the FRCPLL line: whether the oscillator divider (RCDIV) must be 0 to feed the PLL 8 MHz was not checked: UNVERIFIED.

## 4. Open questions
Resolved by S1-1R (no longer open): PGEC3/PGED3 pins (pin 14 = PGED3/RB5, pin 15 = PGEC3/RB6; Table 1-2 swapped them); I2C BRG formula (-1, device datasheet); JTAGEN default (1 = enabled); INT polarity default (active high); the 29-clock I2C overhead.
1. Does the EE 2361 lab board fix any pins (I2C bus, programmer header, LEDs, UART/USB bridge)? Which ICSP set does the programmer header use (1, 2 or 3)? Is I2C already wired to pins 17/18 or to I2C2 (pins 6/7)? If so the map and `ICS` change.
2. How is SA0 wired on the LIS3DH breakout (0x18 or 0x19)? Does it have pull-ups (what value), a regulator or level shifter? Are both INT1 and INT2 broken out? (If only INT1, option 4c is forced and the sources are separated by reading INT1_SRC, CLICK_SRC and FIFO_SRC.) CS must be tied high for I2C ([DS] sec 6).
3. Two-minute LIS3DH bench check: FIFO Stream mode, tilt slowly, confirm bits 15..4 vary and 3..0 stay zero; write 0xB0 to CLICK_THS and read it back (bit 7 latches); confirm INT1 idles low.
4. Main oscillator: FRC+PLL (RA2/RA3 free) or a crystal? Confirms FCY = 16 MHz and the CW2 settings in 3.8 (RCDIV requirement unchecked).
5. WS2812 supply and level shifting (C6b D4) and the RB13 versus RB15 pin choice (decision 7). Bulb control method is open in C6b.
6. Which USB-serial adapter for the host, and does it run 115200 within +-1% (and 250000 if wanted)?
7. Scope at first I2C bring-up: SCL about 100 kHz with BRG 157, about 394 kHz with BRG 38 at FCY = 16 MHz (FRC + PLL)? The Table 16-1 footnote says "PLL disabled".
8. Is the LIS3DH mounting on the wand fixed (axis table, C1), and does +-4 g clip on real hard swipes?
9. The newest LIS3DH datasheet could not be read (st.com unreachable, also for the reviewer). If anyone can open it, check FIFO sec 5.1, CLICK_THS and CTRL_REG3 and report differences.
