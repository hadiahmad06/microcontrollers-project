# C6b: Display (WS2812 matrix) and bulb control, timing and interrupt interaction

> Proposal by `research-display` (ticket S1-5) for `hadi`, 2026-11-14. **Not a decision.** Nothing here is in
> CONTRACTS.md. Companion: `C7_budget.md`. Pin merge target: `C6a` (sensor/I2C/UART pins, written separately).
> Sources: `DS39881E` = Microchip PIC24FJ64GA004 Family datasheet (covers the 28-pin PIC24FJ64GA002),
> downloaded from `ww1.microchip.com/downloads/en/DeviceDoc/39881e.pdf`. `WS2812B-old` = Worldsemi WS2812B sheet,
> 2013, local copy `~/Downloads/WS2812B.pdf`. `WS2812B-V5` = Worldsemi WS2812B-V5,
> `learn.watterott.com/kb/ws281x/WS2812B-v5.pdf`. Page numbers are the printed DS39881E footer numbers.

## 1. Decisions needed

**D1. Which WS2812 driver method?**
- (a) Cycle-counted asm bit-bang, IRQs masked in short chunks (one 8-LED row at a time).
- (b) SPI encoding (10 SPI bits per WS bit at 8 MHz, or 3 per bit at 2.667 MHz).
- (c) Output Compare/PWM or UART tricks. Not feasible (§3.3).
- Tradeoff: (a) is the simplest, needs no extra pin function, and its timing is exact to 62.5 ns. It costs CPU for the whole ~2 ms frame. (b) puts the timing in hardware, but the CPU must still feed a word every 2 to 3 µs, so it saves almost nothing, and the SPI inter-word gap is **UNVERIFIED**.
- **RECOMMENDATION (needs Hadi's decision): (a)** asm bit-bang, masking IRQs per 8-LED row (about 250 µs), with a 10-NOP unmasked gap between rows. Keep (b) as a fallback if a scope shows (a) glitching.

**D2. Interaction rule between matrix/bulb updates and the sensor/UART/I2C code.**
- (i) "Never update during a capture window." Strictest. It blocks the animation while a gesture is being made.
- (ii) "Update any time, but chunked": `ws2812_show()` is called from the main loop only, masks per row, and returns BUSY while an IR frame is being sent. The FIFO slack (320 ms) is about 150x the cost of a frame.
- (iii) Single 2 ms mask. Simplest, but it overruns the UART RX FIFO if the PC is sending at 115200 (§4).
- **RECOMMENDATION (needs Hadi's decision): (ii)**, plus two sub-rules: ISRs must stay under about 30 µs; and no WS2812 show while an IR frame is in flight (§4.4).

**D3. Global brightness cap.**
- Options: no cap, a cap at 25% (value 64/255 per channel), or a cap at 12.5% (value 32) plus a runtime current limiter.
- **RECOMMENDATION (needs Hadi's decision): compile-time per-channel cap of 32 (12.5%) plus a software limiter of sum(R+G+B) so the estimated draw stays at or below 300 mA**, so a USB-powered board survives (§5).

**D4. Level shifting for the WS2812 data line.** The matrix is powered at 5 V and the PIC outputs 3.3 V. `WS2812B-old` needs VIH of at least 0.7 x VDD = 3.5 V, and the PIC's VOH is at least 3.0 V, so a plain connection is out of spec.
- Options: 74AHCT125 or 74HCT-family buffer powered at 5 V (about $1); power the matrix from about 4.0 to 4.3 V (a series diode, which is a hack); direct connection and hope.
- **RECOMMENDATION (needs Hadi's decision): a 74AHCT125-class level shifter plus a series resistor of about 330 ohm on the data line**, with a 500 to 1000 µF capacitor across the matrix supply.

**D5. How is the "light bulb" controlled? (the biggest open hardware question; needs a team decision)**
- (a) IR LED sending NEC codes to an off-the-shelf IR-remote RGB bulb (or an IR-controlled RGB LED strip controller).
- (b) 12 V RGB strip driven by 3 MOSFETs from 3 PWM (OC) pins.
- (c) Relay on a mains bulb. On/off only.
- (d) Wi-Fi/BLE smart bulb through an ESP32.
- (e) WS2812 ring or the matrix itself as the "bulb".
- **RECOMMENDATION (needs Hadi's decision): (a) as primary, with (e) wired from day one as the guaranteed fallback demo.** Reasoning: (a) is closest to the proposal's wording ("color-changing light bulb"). It uses one pin and one OC module, and it is isolated from mains. Its risk is that the remote's codes are unknown. A $1 IR receiver plus a logic analyzer or scope solves that in an hour. If the bulb turns out not to be NEC, fall back to (b), which is fully deterministic and wired. Avoid (c). Avoid (d) unless the team wants a networking project.

**D6. WS2812 part variant.** Identify which WS2812B revision the matrix has (old: reset >50 µs, V5: reset >280 µs). The timing windows differ and **no single cycle-counted waveform satisfies both** (§2.2). Check the board's markings or datasheet link, or test empirically. Until then, assume old timing and a reset gap of at least 300 µs, which is safe for both.

## 2. Facts

### 2.1 WS2812 protocol

| Fact | Value | Source |
|------|-------|--------|
| Data rate / bit period | 800 kbps, TH+TL = 1.25 µs +/-600 ns | WS2812B-old, "Data transfer time"; WS2812B-V5 |
| Old WS2812B: T0H, T0L | 0.40 µs +/-150 ns, 0.85 µs +/-150 ns | WS2812B-old, Data transfer time table |
| Old WS2812B: T1H, T1L | 0.80 µs +/-150 ns, 0.45 µs +/-150 ns | same |
| Old WS2812B: reset (RES) | low > 50 µs | same |
| V5: T0H | 220 ns to 380 ns | WS2812B-V5, Data Transfer Time table |
| V5: T1H | 580 ns to 1 µs | same |
| V5: T0L, T1L | 580 ns to 1 µs (both) | same |
| V5: reset (RES) | low > 280 µs ("won't cause wrong reset while interruption") | same, features and table |
| Bit order and color order | 24 bit per pixel, **G then R then B**, MSB first | WS2812B-old, "Composition of 24bit data" |
| Pixel shifts and reshapes data | first pixel keeps 24 bits, the rest is forwarded | WS2812B-old, General description |
| Input high threshold | old: VIH min 0.7 VDD (VDD 4.5 to 5.5 V). V5: 0.63 VDD | WS2812B-old Electrical characteristics; WS2812B-V5 |
| Supply | old: VDD absolute max 3.5 to 5.3 V, operating test at 4.5 to 5.5 V | WS2812B-old |
| Quiescent current | V5: 0.6 mA per pixel (center value) | WS2812B-V5, LED characteristics |
| Max current per pixel at full white | about 60 mA (20 mA per channel) | Adafruit NeoPixel Uberguide, "Powering NeoPixels", `learn.adafruit.com/adafruit-neopixel-uberguide/powering-neopixels` |
| Adafruit advice | 500 to 1000 µF cap across supply; level shifter for 3.3 V logic (74AHCT125 / 74HCT245); signal should be at least 70% of pixel VDD | Adafruit Uberguide "Powering" and "Basic connections" pages |
| Original (non-B) WS2812 timing | **UNVERIFIED**. The Adafruit-hosted `WS2812.pdf` could not be text-extracted. Not used here. | n/a |

### 2.2 PIC24FJ64GA002 facts used here (all DS39881E)

| Fact | Value | Source |
|------|-------|--------|
| Fcy | Fcy = Fosc/2. 16 MIPS at Fosc = 32 MHz, so 62.5 ns per cycle | DS39881E p.1 (features), Eq. 15-1 note, §8 |
| SPI module count and FIFO | Two SPI modules; **8-level FIFO in Enhanced Buffer mode** (SPIBEN = SPIxCON2<0>) | DS39881E p.1, §15 (p.141), Fig 15-2 (p.143), Reg 15-1/15-2 |
| SPI clock options at Fcy = 16 MHz | 8000, 4000, 2667, 2000, 1000 kHz and slower. 1:1 primary with 1:1 secondary is invalid; 1:1 with 2:1 gives 8 MHz | Table 15-1 (p.150), Eq. 15-1 |
| SPI word size | 8 or 16 bit (MODE16 = SPIxCON1<10>) | SPIxCON1 register map, p.37 |
| SPI TX interrupt choices | SISEL<2:0> in SPIxSTAT: TX buffer full; last bit shifted in (TX FIFO empty); last bit shifted out; **one open spot in TX FIFO** | Reg 15-1 SPIxSTAT (p.144) |
| SPI pins | SDO1 / SCK1OUT / SS1OUT are on Peripheral Pin Select outputs (RPn pins) | Table 10-3 (PPS outputs), p.109 |
| Inter-word gap when FIFO stays non-empty | **UNVERIFIED** (not stated in DS; needs a scope or logic analyzer) | n/a |
| UART RX/TX buffering | **4-level deep FIFO**. `URXISEL<1:0>`: interrupt at 1, 3 or 4 characters in the buffer. 4-character-full is the maximum. OERR flag marks an overrun | DS39881E p.1 (UART features); Reg 17-2 UxSTA (p.164) |
| Max UART baud | BRGH=1: Fcy/4 = 4 Mbaud at UxBRG = 0 | DS39881E §17.1 (p.160) |
| Hardware I2C clock | 400 kHz at Fcy = 16 MHz: I2CxBRG = 37 (actual 404 kHz) | Table 16-1 (p.153) |
| Interrupt disable instruction | `DISI #lit14`: a 14-bit literal, so at most 16383 cycles = 1.02 ms. Priority 7 sources are NOT disabled by DISI | Instruction set overview Table 26-2 (p.226); §7.4 (p.94) |
| Output Compare modules | 5 (OC1 to OC5), PWM mode OCM<2:0> = 110, remappable via PPS | DS39881E p.1, §14 (p.135), Table 10-3 |
| 5.5 V tolerant | Digital-pin inputs only. Not a reason to run VDD at 5 V | DS39881E p.1 |
| Operating voltage | 2.0 to 3.6 V | Table 27-3 (p.234) |
| VOH | at least 3.0 V at IOH = -3 mA, VDD = 3.6 V | Table 27-8 DO20 (p.242) |
| Analog pins reset to analog | AD1PCFG resets to 0x0000, i.e. all AN pins start as analog; set AD1PCFG = 0xFFFF before using RB12..RB15 or RA0..RA1 as digital I/O | AD1PCFG register map (p.39), §10.2 (p.106) |
| 28-pin DIP/SSOP pin map | RP0 to RP15 are RB0 to RB15. SCL1/SDA1 = RB8/RB9 (fixed). SCL2/SDA2 = RB3/RB2. INT0 = RB7. PGEC1/PGED1 = RB1/RB0, PGEC2/PGED2 = RB11/RB10, PGEC3/PGED3 = RB6/RB5. RA0..RA4 have no RP function | 28-pin diagram, DS39881E p.2 |

### 2.3 Other facts

| Fact | Value | Source |
|------|-------|--------|
| NEC IR | 38 kHz carrier, duty 1/4 or 1/3 recommended, 560 µs burst; leader 9 ms burst + 4.5 ms space; bit 0 = 560 µs mark + 560 µs space, bit 1 = 560 µs mark + 1.69 ms space; LSB first; address, ~address, command, ~command; one trailing burst; repeat code every 110 ms; total frame about 68 ms | `sbprojects.net/knowledge/ir/nec.php` |
| 38 kHz from PIC | Timer2 period 421 cycles (16 MHz / 38 kHz = 421.05) gives 38.0 kHz; 25% duty is OCxRS about 105 | Computed from Fcy (not from a source) |
| Timing computations below | 62.5 ns per cycle; 20 cycles = 1.25 µs | Computed |

## 3. Details: driving WS2812

### 3.1 (a) Cycle-counted bit-bang
- 1.25 µs = 20 cycles per bit. Per-bit targets (resolution 62.5 ns):

| Code | High | Low | Check vs old spec | Check vs V5 |
|------|------|-----|-------------------|-------------|
| 0 | 6 cycles = 0.375 µs | 14 = 0.875 µs | T0H in 0.25..0.55 ok, T0L in 0.70..1.00 ok | T0H <= 0.38 ok (tight), T0L ok |
| 1 | 13 cycles = 0.8125 µs | 7 = 0.4375 µs | T1H 0.65..0.95 ok, T1L 0.30..0.60 ok | T1H ok, **T1L 0.4375 < 0.58, out of spec** |

- Old spec needs T1L at most 0.60 µs, V5 needs at least 0.58 µs. Cycle steps are 62.5 ns, so 0.5625 µs (9 cycles) or 0.625 µs (10 cycles) are the only candidates, and neither fits both. **No single waveform is in spec for both revisions.** I computed this with a small script. Real V5 parts are reported to be forgiving, but that is **UNVERIFIED**.
- Feasibility: at 20 cycles per bit, the loop must set the pin high, hold, conditionally drop it, then fetch the next bit with no branch penalty (taken branches cost extra cycles on PIC24). Unrolling 8 bits with `btss` or `rlc` tests is the usual solution. I have not found a PIC24 reference implementation to cite, so feasibility is by cycle count only. **A spike on the simulator (S1-4) can confirm the cycle counts; the pin waveform needs a scope.**
- Frame time: 64 x 24 = 1536 bits x 1.25 µs = **1.92 ms**, plus reset: **about 2.0 ms (old) / 2.2 ms (V5)**. 30720 cycles, which is more than DISI can cover (§2.2: 16383 max), so masking must use IPL = 7 (`SRbits.IPL`) or chunked DISI.
- Chunked masking: 8 LEDs x 24 bits x 1.25 µs = 240 µs per row. Raise IPL to 7, send a row, restore the old IPL, run about 10 NOPs (about 0.6 µs, enough for a pending ISR to be taken), then the next row. The line is low in the gap, so the gap only adds to T_L. **The total low gap must stay under 50 µs for old parts** or the part latches mid-frame. That means every ISR that can fire in the gap must run for under about 30 to 40 µs. If it is longer, the visible result is one garbled frame, which the next show fixes.

### 3.2 (b) SPI encoding
- Encode each WS2812 bit as N SPI bits. Candidates (script-checked against the old and V5 windows; SCK options from Table 15-1):

| SCK | SPI bits per WS bit | 0 pattern (H/L bits) | 1 pattern | Meets |
|-----|---------------------|----------------------|-----------|-------|
| 2.667 MHz | 3 (period 1.125 µs) | 1 / 2 (0.375/0.75 µs) | 2 / 1 (0.75/0.375 µs) | old only |
| 4 MHz | 5 (period 1.25 µs) | 2 / 3 | 3 / 2 | old only |
| 8 MHz | 10 (period 1.25 µs) | 3 / 7 (0.375/0.875 µs) | 6 / 4 (0.75/0.5 µs) | old |
| 8 MHz | 10 | 3 / 7 | 5 / 5 (0.625/0.625 µs) | V5 |

- A 16-bit SPI word at 8 MHz holds 1.6 WS bits. 8 WS bits (one color byte) = 80 SPI bits = exactly 5 words, so word boundaries line up with color-byte boundaries only.
- CPU load: at 8 MHz, a 16-bit word is shifted every 2 µs = 32 cycles. An ISR per word cannot fit (entry/exit alone is about 10 to 20 cycles; **UNVERIFIED**). At 2.667 MHz with 8-bit words, one word every 3 µs = 48 cycles per ISR is about 60 to 70% CPU. Either way the CPU is mostly busy for the whole 2 ms. The only gain is tolerance to a short preemption: the 8-deep FIFO covers about 16 µs (8 words at 2 µs) or 24 µs (8 bytes at 3 µs) of ISR delay.
- Costs: either a 576 B pre-encoded buffer (3-bit scheme, 64 x 9 B) or an on-the-fly encoder (a lookup table of 256 x 3 B = 768 B, or shift logic), and it needs SDO1 (and SCK, unless DISSCK = 1) on RPn pins.
- Risk: **UNVERIFIED** whether the SPI inserts a gap between back-to-back words in master mode even when the TX FIFO is non-empty. If it does, it must land only in the low part, so each word has to end with 0 bits. The 10-bit patterns above do not end every word with 0, so a gap could corrupt a bit. Verify on a scope before relying on this.

### 3.3 (c) Other tricks (not recommended)
- **Output Compare PWM:** the period would need to be 1.25 µs with the duty changed every bit (6 vs 13 counts). That requires a new OCxRS write every 20 cycles, which is not possible without DMA (this part has none). Rejected.
- **UART at 4 Mbaud, TX inverted** (UxSTA UTXINV exists, Reg 17-2): one 10-bit frame (2.5 µs) can carry two WS bits as two 5-bit symbols (start bit = high with inversion, stop = low). In theory this meets the old spec (H2/L3 for 0, H3/L2 for 1). The UART TX FIFO is 4 deep. Same problem as SPI (a byte every 2.5 µs = 40 cycles), **UNVERIFIED** in practice. Not recommended; listed only for completeness.

### 3.4 Recommendation reasoning
Bit-bang gives exact timing, needs no extra buffers and no PPS pin, and its cost (2 ms CPU per frame, at most a few frames per second) is negligible for a gesture demo. Chunking makes it safe for UART RX and keeps a rule that is easy to state. SPI saves nothing material, needs more RAM, and carries the unknown gap behavior.

## 4. Details: interaction with sensor, I2C, UART

### 4.1 LIS3DH FIFO
- Stream mode, 100 Hz, 32 deep: 320 ms to overflow (given in the task brief and PLAN.md). A 2.2 ms full-frame mask is **0.7% of the slack**. Even three back-to-back shows are fine.
- If FIFO draining is driven by a watermark interrupt (INT1/INT2 flag), the flag stays set in hardware while masked, and the ISR runs after unmasking.
- Rule: if the FIFO is at 24+ samples, drain before calling show (keeps 80 ms of slack for the show).

### 4.2 I2C in flight
- The PIC24 I2C master holds SCL low between operations until software issues the next step, so a delay of up to 250 µs (chunked) or 2 ms (unchunked) while an ISR-driven I2C transfer is mid-byte just stretches the bus. This is allowed by the I2C spec, since there is no minimum SCL frequency. **UNVERIFIED** that the LIS3DH has no SCL-low timeout (the DS does not cover it; check the LIS3DH datasheet, which is C6a/C1 territory). If the I2C driver is blocking and called only from the main loop (likely), the matrix update cannot overlap it at all because both run on the single main thread.
- Rule: call `ws2812_show()` only from the main loop, never from an ISR, and only when the I2C driver reports idle. This costs nothing since I2C bursts take about 2 to 3 ms at 400 kHz (C7 §4).

### 4.3 UART RX overflow at 115200
- 115200 baud, 8N1: 10 bits = 86.8 µs per character.
- RX FIFO is 4 characters deep (DS39881E p.1; Reg 17-2). With the ISR reading one character per interrupt, the FIFO normally holds 0 to 1 character. Overflow (OERR) occurs when about 5 characters arrive without a read: **about 350 to 430 µs of masking at worst, if the PC is sending continuously**.
- A single 2.0 ms mask fits 23 characters, so it **will** overflow if the host is sending. A per-row mask (about 250 µs + about 10 µs gap) fits 2.9 characters, which is safe.
- If the PC never sends during a show (likely: C2 is mostly wand to PC), even the single-mask option works. Chunking is cheap insurance.
- UART TX is unaffected (the ring buffer drains slower for 2 ms).

### 4.4 Proposed rules (summary, for CONTRACTS C6)
1. `ws2812_show()` runs only in the main loop, only when I2C is idle and no IR frame is in progress; otherwise it returns BUSY and the caller retries.
2. It masks interrupts (IPL = 7) for at most one 8-LED row (about 240 µs) at a time, with a 10-NOP unmasked gap between rows. Reset gap after the last row is at least 300 µs unmasked.
3. No ISR may run longer than about 30 µs (480 cycles). Longer work is deferred to the main loop.
4. IR frames use hardware PWM for the 38 kHz carrier (OC module, unaffected by masking) and a timer ISR for the mark/space envelope. A 250 µs jitter on a 560 µs mark/space can break NEC decoding, so **do not call `ws2812_show()` while an IR frame is being sent** (about 68 ms). Send the icon first, then the IR frame.
5. FIFO drain has priority: if the FIFO holds 24 or more samples, drain first, then show.
6. Flash writes (C7 §3) are never done during a show or an IR frame, and never during a capture window.

## 5. Power

| Case | Current at 5 V | Notes |
|------|----------------|-------|
| 64 LEDs full white (255,255,255) | 64 x 60 mA = **3.84 A** (19 W) | Adafruit Uberguide (60 mA per pixel max). Not survivable on USB. |
| 64 LEDs idle (all off) | 64 x 0.6 mA = about 38 mA | WS2812B-V5 quiescent. **UNVERIFIED** for old parts. |
| Typical icon: 20 LEDs on, one channel, at value 255 | 20 x 20 mA = 400 mA | 20 mA per channel, Uberguide figure |
| Same at cap 32/255 (12.5%) | about 50 mA | scales linearly (approximately, since PWM scaling is in the LED driver) |
| All 64 white at cap 32 | 64 x 60 x 0.125 = **0.48 A** | worst case that the cap alone allows |
| Software limit 300 mA (sum of channel values) | about 300 mA | recommended on top of the cap |

- USB 2.0 supplies 100 mA before enumeration and up to 500 mA after (**UNVERIFIED**, general knowledge; the actual supply for the wand is an open question, §7).
- Use a 500 to 1000 µF capacitor across the matrix (Adafruit Uberguide), common ground with the PIC, 5 V supply sized for the cap plus IR/bulb, and a level shifter (D4).
- Implementation: store icons as full 8-bit colors, scale by a global brightness constant in `ws2812_show()`, and estimate current as sum(R+G+B) x 20 mA / 255 before sending. If it exceeds the limit, scale the frame down uniformly.

## 6. Details: bulb control options

All options are compared on the same axes. Costs are rough guesses (**UNVERIFIED**, check retailers).

### 6.1 (a) IR LED sending NEC to an off-the-shelf IR-remote RGB bulb or strip controller
- **How:** an IR LED (940 nm) driven by a small NPN (the PIC pin can only source about 18 mA, DS39881E p.1) transmits the codes a cheap RGB bulb's remote would send. 38 kHz carrier from an Output Compare module in PWM mode (Timer2, 25% duty); a timer ISR switches the OC mode on and off to make the NEC marks and spaces.
- **Parts:** IR LED, NPN (2N3904), about 100 ohm resistor, and the bulb or an IR-controlled RGB strip controller (the usual 12 V "24-key" or "44-key" box). Also an IR receiver (VS1838B or TSOP38238-class) to read the remote's codes once. About $10 to $20 total.
- **Safety:** the wand has no connection to mains. A commercial bulb sits in its normal lamp socket (or use the 12 V strip variant, which has no mains at all). Low risk.
- **PIC:** 1 pin (RPn mapped to OC1), Timer2 (carrier), a second timer or Timer3 (envelope). No I2C/UART conflict. IR input capture optional (for learning codes) uses another IC pin.
- **Complexity:** low-medium. NEC encoding is about 60 lines. The unknown is whether the target remote is NEC (many cheap RGB remotes are, **UNVERIFIED**; others use different protocols). Codes have to be captured from the real remote.
- **Demo reliability:** good at 1 to 3 m line of sight. Indoor lighting can add noise. No network, no pairing.

### 6.2 (b) 12 V RGB strip (or "bulb") driven by 3 MOSFETs from PWM
- **How:** three logic-level N-MOSFETs (gate threshold well under 3.3 V; e.g. IRLZ44N class or smaller SOT-23 types) switch R, G, B of a common-anode 12 V strip. Hardware PWM from OC modules: no CPU load, linear brightness.
- **Parts:** strip (about $8 to $15), 12 V supply (lab bench or $8 adapter), 3 MOSFETs, 3 gate resistors (about 100 ohm) and 10 k pull-downs, wire. The strip is not a "bulb" in the narrow sense. A frosted jar or diffuser tube can make it look like one.
- **Safety:** 12 V DC, low voltage. Safe in a student lab. Common ground with the PIC. Check the strip current (about 1 to 1.5 A per meter at full white, **UNVERIFIED**); use a short piece.
- **PIC:** 3 OC pins (OC1 to OC3, via PPS) and 1 timer (Timer2) at about 2 to 8 kHz PWM (above flicker/visible range). Supports on/off, color (R:G:B ratio) and brightness (scaled duty) natively.
- **Complexity:** lowest firmware, moderate wiring (breadboard and 12 V).
- **Demo reliability:** highest (wired, deterministic).

### 6.3 (c) Relay switching a mains bulb
- **How:** a GPIO drives a relay (or solid-state relay) that opens and closes a mains lamp circuit. Only on/off. No color or brightness (a dimmer or phase control is far riskier).
- **Safety: a student lab concern.** Exposed mains wiring is a shock and fire hazard; a self-built relay board is **not recommended** without instructor approval. If the team insists, use only an enclosed, opto-isolated commercial module (a "PowerSwitch Tail"-type device with a 3 to 12 V DC control input; price **UNVERIFIED**, about $30 or more) and never open it.
- **PIC:** 1 GPIO (plus a transistor if driving a bare relay coil).
- **Complexity:** very low in code, high in risk. **Demo reliability:** high mechanically, but it fails the proposal's "color, brightness" goals. **Not recommended.**

### 6.4 (d) Wi-Fi or Bluetooth smart bulb through an ESP32
- **How:** the PIC sends a command over UART to an ESP32, which talks to the bulb over Wi-Fi/BLE (or runs a controller such as WLED).
- **Parts:** ESP32 dev board (about $8 to $12), smart bulb (about $10 to $20), possibly a travel router or phone hotspot. Campus Wi-Fi with 802.1X login or client isolation typically blocks both the ESP32 and smart bulbs (**UNVERIFIED** for UMN specifically, but common).
- **Safety:** the bulb is a normal commercial mains bulb. The ESP32 is low voltage.
- **PIC:** UART2 TX (and RX if acks wanted) via PPS, 2 pins, common ground, 3.3 V logic on both ends.
- **Complexity:** highest. A second firmware, network configuration and an extra project dependency. It also arguably moves the interesting part off the PIC.
- **Demo reliability:** lowest (Wi-Fi setup at demo time, pairing, latency).

### 6.5 (e) WS2812 ring or the matrix itself as the bulb
- **How:** a 12 or 16-LED WS2812 ring (about $5 to $10), daisy-chained from the matrix's DOUT or driven from its own pin, shows color and brightness with a diffuser. Or flood the matrix itself with one color.
- **Parts:** ring, same level shifter and supply as the matrix.
- **Safety:** low voltage. Same power concerns as §5 (a ring at cap 32 is small).
- **PIC:** no extra pins if chained (frame grows to 80 LEDs and 2.4 ms); otherwise 1 more GPIO.
- **Complexity:** very low (code reuse). **Demo reliability:** very high.
- **Weakness:** it is not "a light bulb". The proposal says "color-changing light bulb"; a grader may expect a separate lamp. Using the matrix itself conflicts with showing the icon at the same time.

### 6.6 Comparison

| Option | Extra HW cost | Mains? | PIC resources | Firmware complexity | Demo reliability | Matches proposal wording |
|--------|---------------|--------|---------------|---------------------|------------------|--------------------------|
| a IR + RGB bulb or controller | $10 to $20 | bulb only, isolated | 1 pin, OC + 2 timers | low-medium | good | yes |
| b 12 V strip + MOSFETs | $15 to $30 | no | 3 OC pins, Timer2 | low | highest | partly (a strip) |
| c relay + mains bulb | $30+ | yes, hazard | 1 GPIO | very low | on/off only | no |
| d ESP32 + smart bulb | $20 to $40 | bulb only | UART2 (2 pins) | high | lowest | yes |
| e WS2812 ring/matrix | $5 to $10 | no | 0 to 1 pin | very low | very high | weak |

## 7. Pins and peripherals (for merging with C6a)

All pins below are **proposals**, not decisions. They avoid I2C1 (RB8/RB9), INT0 (RB7) and the debug/program pairs (RB0/RB1, RB5/RB6, RB10/RB11 are PGEDx/PGECx; only the pair the programmer uses is actually reserved, so confirm the debugger channel first). Pins RB12 to RB15 are AN-capable, so set `AD1PCFG = 0xFFFF` (reset is 0 = analog; DS39881E §10.2, p.106) before using them as digital output.

| Function | Needs | Proposed pin | Notes |
|----------|-------|--------------|-------|
| WS2812 data (bit-bang) | 1 GPIO + level shifter input | RB13 (RP13) | Any GPIO works. RP-capable so SPI fallback (SDO1) stays possible without rewiring |
| Option a IR LED | 1 pin, OC1 (PWM), Timer2, one more timer | RB14 (RP14, OC1) | NPN transistor drive |
| Option b strip | 3 pins, OC1 to OC3, Timer2 | RB14, RB15, RB12 (RP14, RP15, RP12) | exclusive with a unless OC pins are reused |
| Option c relay | 1 GPIO | RB12 | transistor + flyback diode if bare relay |
| Option d ESP32 | UART2 TX (+RX) | RB12 and RB11 or whichever RPn are free | exclusive of UART1 pins from C6a |
| Option e ring | 0 pins (chained) or 1 GPIO | RB12 | chained shares the WS2812 data pin |
| Already planned (C6a, for reference) | I2C (RB8/RB9 or RB2/RB3), INT1 and INT2 pins, UART TX/RX | per C6a | no overlap with the proposals above, as far as pin numbers go |

Timers: Timer1 (RTC/time base) is probably used by the capture code; Timer2/3 are free. OC1 to OC5 and Timer2/3 are the only shared resources between options a and b.

## 8. Open questions
1. Which WS2812B revision does the matrix use (old 50 µs reset vs V5 280 µs)? Do the pixels accept a 0.4375 µs T1L (V5 wants at least 0.58)? A scope/logic-analyzer test is needed.
2. Does the PIC24 SPI master insert a gap between back-to-back words when the FIFO is non-empty? Needed only if the team picks SPI.
3. What is the wand's power source (USB from PC, 5 V adapter, battery)? It sets the brightness cap and whether 5 V is available for the level shifter.
4. Does the lab kit provide a 5 V rail alongside the PIC's 3.3 V? Is a 74AHCT125 available?
5. Which bulb or strip, and which remote protocol? If it is IR, do we have an IR receiver and logic analyzer to capture codes?
6. Is a physical separate lamp mandatory, or may the ring/matrix count as the "bulb"? (Instructor/TA question.)
7. Does the LIS3DH tolerate a long SCL-low pause? (Check the LIS3DH datasheet: C6a/C1.)
8. Is the PC ever sending to the wand while a show runs? (If never, the chunking could be dropped.)
9. Debug interface: which PGEDx/PGECx pair does the programmer use? That decides whether RB10/RB11 or RB5/RB6 are free.
