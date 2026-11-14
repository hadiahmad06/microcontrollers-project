# C6b: Display (WS2812 matrix) and bulb control, timing and interrupt interaction

> Proposal by `research-display` (ticket S1-5) for `hadi`, 2026-11-14. **Not a decision.** Nothing here is in
> CONTRACTS.md. Companion: `C7_budget.md`. Pin merge target: `C6a_sensor_io.md` (decision 7). Revision 2 reconciles this file with C1, C3, C4, C5, C6a and review `reviews/S1-5R.md`.
> Sources: `DS39881E` = Microchip PIC24FJ64GA004 Family datasheet (covers the 28-pin PIC24FJ64GA002),
> downloaded from `ww1.microchip.com/downloads/en/DeviceDoc/39881e.pdf`. `WS2812B-old` = Worldsemi WS2812B sheet,
> 2013, local copy `~/Downloads/WS2812B.pdf`. `WS2812B-V5` = Worldsemi WS2812B-V5,
> `learn.watterott.com/kb/ws281x/WS2812B-v5.pdf`. Page numbers are the printed DS39881E footer numbers.

## 1. Decisions needed

*Revision 2 (S1-5 fix round): reconciled with C1, C3, C4, C5, C6a and with review `S1-5R.md`.*

**D1. Which WS2812 driver method?**
- (a) Cycle-counted asm bit-bang, IRQs masked in short chunks of **4 LEDs** (about 138 µs worst case).
- (b) SPI encoding (10 SPI bits per WS bit at 8 MHz, or 3 per bit at 2.667 MHz).
- (c) Output Compare/PWM or UART tricks. Not feasible without DMA (§3.3).
- Tradeoff: (a) is the simplest, needs no extra pin function, and its timing is exact to 62.5 ns. It costs CPU for the whole ~2 ms frame. (b) puts the timing in hardware, but the CPU must still feed a word every 2 to 3 µs, so it saves almost nothing, and the SPI inter-word gap is **UNVERIFIED**.
- **RECOMMENDATION (needs Hadi's decision): (a)**, with the timing of §3.1 behind a compile-time variant switch, 4-LED chunks, and a short unmasked gap between chunks. Keep (b) as a fallback if a scope shows (a) glitching.

**D2. Interaction rule between matrix/bulb updates and the sensor/UART/I2C code.**
- (i) "Never update during a capture window." Strictest. It blocks animation while a gesture is being made.
- (ii) "Update any time, but chunked and drain-aware": `ws2812_show()` runs from the main loop only, masks one 4-LED chunk at a time, and returns BUSY while a FIFO drain is pending or running, or while an IR frame is in flight.
- (iii) One 2 ms mask. Simplest, but it overruns the UART RX FIFO if the PC is sending at 115200 (§4.3).
- **RECOMMENDATION (needs Hadi's decision): (ii)**, with the rules of §4.4. The deadline it protects is C1/C6a's: watermark FTH = 15, so 160 ms from the watermark to the first overwritten sample. A ~2.1 ms show is about 1.3% of that.

**D3. Global brightness cap.**
- Options: no cap, 25% (value 64/255 per channel), or 12.5% (value 32) plus a runtime current limiter.
- **RECOMMENDATION (needs Hadi's decision): compile-time per-channel cap of 32 plus a software limiter on sum(R+G+B) so the estimated draw stays at or below 300 mA.** Note a cap of 32 leaves only 33 levels per channel, so dim gradients band (acceptable for icons). Prefer a separate 5 V supply with common ground over USB-bridge power (§5).

**D4. Level shifting for the WS2812 data line.** The matrix is powered at 5 V and the PIC outputs at most 3.3 V.
- The old WS2812B needs VIH of at least 0.7 x VDD = 3.5 V; V5 needs 0.63 x VDD = 3.15 V. The PIC's guaranteed VOH is 3.0 V min, but **only at VDD = 3.6 V and IOH = -3 mA** (DS39881E Table 27-8, DO20). At a 3.3 V supply the pin can never exceed 3.3 V, so the old part is out of spec and V5 is marginal (about 0.15 V, before load and drop). This makes the case for a shifter stronger.
- Options: 74AHCT125-class buffer at 5 V (about $1); power the matrix from about 4.0 to 4.3 V through a diode (hack); direct connection and hope.
- **RECOMMENDATION (needs Hadi's decision): a 74AHCT125-class shifter plus a ~330 ohm series resistor on the data line**, with a 500 to 1000 µF capacitor across the matrix supply.

**D5. How is the "light bulb" controlled? (the biggest open hardware question; needs a team decision)**
- (a) IR LED sending NEC codes to an off-the-shelf IR-remote RGB bulb (or an IR-controlled RGB LED strip controller).
- (b) 12 V RGB strip driven by 3 MOSFETs from 3 PWM (OC) pins.
- (c) Relay on a mains bulb. On/off only.
- (d) Wi-Fi/BLE smart bulb through an ESP32.
- (e) WS2812 ring or the matrix itself as the "bulb".
- **RECOMMENDATION (needs Hadi's decision): (a) as primary, with (e) wired from day one as the guaranteed fallback demo.** It is closest to the proposal's wording, uses one pin and one OC module, and is isolated from mains. Its risk is the unknown remote protocol: capture the real remote's codes with a ~$1 IR receiver before buying. If the bulb is not NEC, fall back to (b). Avoid (c) (safety) and (d) (campus Wi-Fi, demo risk).

**D6. WS2812 part variant.** Is the matrix an old WS2812B (reset above 50 µs) or V5 (above 280 µs)? **No single cycle-counted waveform satisfies both**: the only conflict is T1L, and the two windows leave an empty gap (§3.1). Use a compile-time switch (`WS2812_T1L_CYCLES` = 9 for old, 10 for V5; everything else is shared) and confirm on a scope. Until the revision is known, use 9 and a reset gap of at least 300 µs (safe for both).

**D7. Pin layout (this is C6a decision 7; it stays Hadi's call).** C6a now proposes two consistent layouts, and C6b works with both:
- **Layout (a):** WS2812 = RB15 (pin 26), UART1 TX/RX = RB13/RB14 (pins 24/25), debug = RB4 (pin 11).
- **Layout (b):** WS2812 = RB13 (pin 24), UART1 TX = RB15 (pin 26), UART1 RX = RB4 (pin 11, RP4), debug = RA4 (pin 12).
- Both keep INT0 = RB7 (LIS3DH INT1), I2C1 = RB8/RB9, LIS3DH INT2 = RB12. The bulb options in §7 use only RB2/RB3 (and RB4 or RB5/RB6/RB10/RB11 when free). **No bulb option uses RB12, RB13, RB14 or RB15.**
- (a) leaves RB2, RB3 and RB4 free (RB4 only if the debug pin is given up), plus RB5/RB6 or RB10/RB11 if the programmer uses ICSP set 1. (b) leaves RB2 and RB3 clean; a third pin needs RB5, RB6, RB10 or RB11.
- **RECOMMENDATION (needs Hadi's decision): (a)** after the lab-board check (C6a open question 1). It matches C6a's map as drawn and leaves more free pins; take (b) only if the board forces RB13 for the WS2812 data.

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
| Interrupt disable instruction | `DISI #lit14` disables interrupts for **lit14 + 1 = at most 16384 cycles = 1.024 ms** (S1-5R, from DS70157). Priority 0 to 6 only: **priority-7 ISRs and traps keep running** | Table 26-2 (p.226); §7.4 (p.94); DS70157 DISI |
| Output Compare modules | 5 (OC1 to OC5), PWM mode OCM<2:0> = 110, remappable via PPS | DS39881E p.1, §14 (p.135), Table 10-3 |
| 5.5 V tolerant | Digital-pin inputs only, and only PORTB<11:5> (not RB12 to RB15, RB0 to RB4, RA). Not a reason to run VDD at 5 V | DS39881E p.1; Table 10-1 (p.106); C6a §2 |
| Operating voltage | 2.0 to 3.6 V | Table 27-3 (p.234) |
| VOH | at least 3.0 V **only at IOH = -3 mA and VDD = 3.6 V**. At a 3.3 V supply the pin cannot exceed 3.3 V | Table 27-8 DO20 (p.242) |
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
- Resolution is one cycle = 62.5 ns. Per S1-5R, the intersection of the two datasheet windows is T0H [0.25, 0.38] µs, T0L [0.70, 1.00], T1H [0.65, 0.95], T1L [0.58, 0.60]. Every window holds a cycle count except **T1L, which holds none** (9 cycles = 0.5625 µs, 10 = 0.625 µs). So **no single waveform is in spec for both revisions**, but the miss is small (17.5 ns or 25 ns). The bit period is free (old sheet: 1.25 µs +/-600 ns), so T0 and T1 need not have the same length.
- **Adopted timing (replaces the earlier 6H/14L, 7L compromise):** T0 = 5H/14L; T1 = 13H/9L for old parts or 13H/10L for V5 (`WS2812_T1L_CYCLES`, compile-time).

| Symbol | Cycles | Value | Old window | V5 window |
|--------|-------:|-------|------------|-----------|
| T0H | 5 | 312.5 ns | 250..550 ok (62.5 margin) | 220..380 ok (67.5 margin) |
| T0L | 14 | 875 ns | 700..1000 ok | 580..1000 ok |
| T1H | 13 | 812.5 ns | 650..950 ok | 580..1000 ok |
| T1L, old variant | 9 | 562.5 ns | 300..600 ok (37.5 margin) | misses 580 by 17.5 ns |
| T1L, V5 variant | 10 | 625 ns | misses 600 by 25 ns | 580..1000 ok (45 margin) |
| Bit period | 19 (0), 22 or 23 (1) | 1.1875, 1.375, 1.4375 µs | within 1.25 +/-0.6 µs | n/a |

  The earlier compromise (T1L = 7 cycles, 437.5 ns) missed V5 by 142 ns, and T0H = 6 cycles sat 5 ns from V5's maximum. FastLED ships separate timing for WS2812 and WS2812B-V5 (S1-5R, from `chipsets.h`), consistent with a per-variant switch. Real V5 parts being forgiving is **UNVERIFIED**.
- Feasibility: the loop must set the pin high, hold, conditionally drop it, then fetch the next bit with no branch penalty (taken `BRA` is 2 cycles). Unrolling 8 bits with `btss` or `rlc` is the usual solution. I found no PIC24 reference implementation to cite, so feasibility is by cycle count only. The simulator spike (S1-4) can confirm cycle counts; the pin waveform needs a scope.
- Frame time: 1536 bits. All ones: 1536 x 1.375 = 2.11 ms (old) or 2.21 ms (V5). All zeros: 1.82 ms. Typical about 2.0 ms, plus the reset gap (at least 300 µs for safety). That is about 29,000 to 35,000 cycles, which exceeds one `DISI` (16384 cycles, §4.4), so masking uses IPL = 7.
- Chunked masking: 4 LEDs x 24 bits x at most 1.4375 µs = at most **138 µs per chunk** (about 2200 cycles); 16 chunks per frame. Raise IPL to 7, send a chunk, restore IPL, run at least 10 NOPs so a pending ISR can be taken, then the next chunk. The line is low in the gap. **The sum of the pending ISRs' run time must stay under 50 µs for old parts** (budget 40 µs; §4.4 rule 3) or the part latches mid-frame; if it does, the result is one garbled frame that the next show fixes.

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
Bit-bang gives exact timing, needs no extra buffers and no PPS pin, and its cost (2 ms CPU per frame, at most a few frames per second) is negligible for a gesture demo. 4-LED chunking plus an RX drain loop keeps UART RX safe (§4.3) and keeps the rule easy to state. SPI saves nothing material, needs more RAM, and carries the unknown gap behavior.

## 4. Details: interaction with sensor, I2C, UART

### 4.1 LIS3DH FIFO (C1 §3.4 / §3.5 and C6a §3.2 scheme)
- FIFO stream mode, 100 Hz, 32 deep. The watermark is set to **FTH = 15**, so the flag rises at 16 unread samples, leaving **160 ms before the first overwrite** (not the 320 ms of a full FIFO). INT0 (RB7) only sets a flag; the drain loop of C1 §3.4 (read FIFO_SRC, drain FSS samples, re-read, repeat until below the watermark, re-arm INT0) runs from the main loop, with a main-loop FIFO_SRC poll at least every 50 ms as a backstop.
- A ~2.1 ms show is about 1.3% of the 160 ms deadline (about 75x margin). A show that starts just before the watermark delays the drain by at most one show.
- Rule: `ws2812_show()` returns BUSY while a drain is pending (watermark flag set) or a burst is running. Otherwise it proceeds. No extra FIFO_SRC read is needed. Between chunks and between frames of an animation the main loop services the drain first.
- Drain bursts (16 samples = 96 B) take 2.2 ms at 400 kHz (C6a recommends BRG 38, 394 kHz: 2.27 ms) or 8.9 ms at 100 kHz. They must run from the main loop or a non-blocking state machine and **never as one long ISR**, otherwise the "short ISR" rule of §4.4 and NEC timing break.

### 4.2 I2C in flight
- The PIC24 I2C master holds SCL low between operations until software issues the next step, so a pause while a transfer is mid-byte only stretches the bus. **UNVERIFIED** that the LIS3DH has no SCL-low timeout (LIS3DH datasheet, C6a territory).
- With the rule "show only from the main loop and only when no drain is pending or running", a show can never overlap an I2C burst, because both run on the single main thread. This costs nothing.

### 4.3 UART RX overflow at 115200
- 115200 baud, 8N1: 10 bits = 86.8 µs per character. The RX FIFO is 4 deep (DS39881E p.1; Reg 17-2). OERR is set when a 5th character completes while 4 are unread.
- Worst case is not an empty FIFO. If one character is already waiting (its ISR pending when the mask starts), three more fill the FIFO and the fourth overflows: **260 to 347 µs** depending on phase (earlier drafts said 350 to 430 µs, which is the empty-FIFO case only).
- With the new timing a 4-LED chunk masks at most 96 x 1.4375 µs = **138 µs**; an 8-LED row masks 264 to 276 µs, which is above the 260 µs lower bound. So the earlier per-row mask is **not** safe against a continuously transmitting host.

| Mitigation | Effect |
|------------|--------|
| (1) RX ISR loops `while (U1STAbits.URXDA)` | needed in any case: one char per interrupt can accumulate across chunks |
| (2) 4-LED chunks (138 µs mask) | worst-case window 260 µs, so this is safe even with a character pending, provided each gap's ISRs read all pending characters |
| (3) Rule: host does not transmit during `show()` | removes the issue, but needs a PC-side protocol rule (C2) |

- **RECOMMENDATION (needs Hadi's decision): (1) plus (2)**, implemented together (the chunk size is a compile-time constant `WS2812_CHUNK_LEDS = 4`). Add (3) only if the recorder tool streams commands during animations. If the PC never transmits during a show, even one long mask would work (open question 8).
- UART TX is unaffected (the ring drains more slowly for 2 ms).

### 4.4 Proposed rules (summary, for CONTRACTS C6)
1. `ws2812_show()` runs only in the main loop. It returns BUSY while (i) a FIFO drain is pending or running, or (ii) an IR frame is in flight (about 68 ms). The caller retries.
2. It masks interrupts with `SRbits.IPL = 7` for at most one 4-LED chunk (about 138 µs). It then restores the previous IPL and executes at least 10 NOPs so a pending ISR can be taken. `DISI` cannot be used: it covers lit14 + 1 = **16384 cycles = 1.02 ms** (per S1-5R, from DS70157; the earlier "16383" was off by one), shorter than the frame, and it does not block priority-7 ISRs, which keep running during it. IPL = 7 blocks all user ISRs. Do not assign priority 7 to any ISR.
3. **Gap budget (the sum, not per ISR).** The unmasked gap between chunks is the total run time of every ISR that was pending, not of one. The old part latches after about 50 µs low. Budget each ISR at about 15 µs and the sum at **40 µs total** (two or three pending ISRs: UART RX, INT0 flag, timer). Longer work is deferred to the main loop. Measure the real ISR times with a pin toggle.
4. The extra low time at chunk boundaries lengthens the last bit's low phase beyond the nominal T0L/T1L maxima on both variants. Only the reset threshold matters on real parts, so this is **empirical, scope-verify**, not "in spec".
5. IR frames use hardware PWM for the 38 kHz carrier (OC module, unaffected by masking) and a timer ISR for the mark/space envelope. A 138 µs jitter on a 560 µs mark/space is risky for NEC decoders, so **do not show while an IR frame is in flight**. Send the icon first, then the IR frame.
6. Flash writes (C7 §4) are never done during a show, an IR frame or a capture window.
7. After the last chunk, leave at least 300 µs low (reset for both variants) before the next show; do not start a new show sooner.

## 5. Power

| Case | Current at 5 V | Notes |
|------|----------------|-------|
| 64 LEDs full white (255,255,255) | 64 x 60 mA = **3.84 A** (19 W) | Adafruit Uberguide (60 mA per pixel max). Not survivable on USB. |
| 64 LEDs idle (all off) | 64 x 0.6 mA = about 38 mA | WS2812B-V5 quiescent. **UNVERIFIED** for old parts. |
| Typical icon: 20 LEDs on, one channel, at value 255 | 20 x 20 mA = 400 mA | 20 mA per channel, Uberguide figure |
| Same at cap 32/255 (12.5%) | about 50 mA | scales linearly (approximately, since PWM scaling is in the LED driver) |
| All 64 white at cap 32 | 64 x 60 x 0.125 = **0.48 A** | worst case that the cap alone allows |
| Software limit 300 mA (sum of channel values) | about 300 mA | recommended on top of the cap |

- USB 2.0 supplies 100 mA before enumeration and up to 500 mA after (**UNVERIFIED**, general knowledge; the actual supply for the wand is an open question, §8). If power comes from USB through a serial bridge, 300 mA may exceed what the bridge requested, so prefer a separate 5 V supply with a common ground (S1-5R).
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
- **PIC:** no extra pins if chained (frame grows to 80 LEDs and about 2.6 ms); otherwise 1 more GPIO.
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

## 7. Pins and peripherals (merge with C6a decision 7)

All pins below are **proposals**. They follow C6a (UART1 on RB13/RB14 or RB15/RB4, INT2 on RB12, I2C1 on RB8/RB9, INT0 on RB7). Bulb options use only pins that neither layout takes. RB2/RB3 are AN4/AN5 (set `AD1PCFG = 0xFFFF`, which C6a does for every case) and are **not** 5.5 V tolerant (only PORTB<11:5> are, per C6a Table 10-1 note), so never feed 5 V logic back into them. The ICSP set in use decides whether RB5/RB6 (set 3) or RB10/RB11 (set 2) are free; C6a assumes set 1 (RB0/RB1).

| Function | Layout (a) | Layout (b) | Notes |
|----------|------------|------------|-------|
| WS2812 data (level shifter input) | RB15 (RP15, pin 26) | RB13 (RP13, pin 24) | both RP-capable, so the SPI fallback (SDO1) needs no rewiring |
| UART1 TX / RX | RB13 / RB14 | RB15 / RB4 | from C6a |
| LIS3DH INT1 / INT2, I2C1 | RB7 / RB12, RB8+RB9 | same | from C6a |
| Debug / timing pin | RB4 (pin 11) | RA4 (pin 12) | from C6a |
| **Option a: IR LED** | RB2 (RP2, pin 6) = OC1, Timer2 + one more timer | same | NPN transistor drive |
| **Option b: 12 V strip, 3 MOSFETs** | RB2, RB3 (OC1, OC2) + RB4 (OC3) | RB2, RB3 + one of RB5, RB6, RB10, RB11 (only if the programmer does not use that set) | in (a) using RB4 gives up the debug pin; OC1 to OC3, Timer2 |
| **Option c: relay** | RB3 (pin 7), 1 GPIO | same | transistor + flyback diode if bare relay coil |
| **Option d: ESP32** | UART2 TX/RX on RB2/RB3 (PPS) | same | exclusive of options a and c on those pins |
| **Option e: ring** | chained: 0 pins; separate: RB3 | same | chained shares the WS2812 data pin and grows the frame to 80 LEDs (about 2.6 ms) |

Timers: Timer1 is probably the capture time base; Timer2/3 are free. OC1 to OC5 and Timer2/3 are the only resources shared between options a and b. None of the bulb options touches I2C, INT0, INT1/INT2 or UART1.

## 8. Open questions
1. Which WS2812B revision does the matrix use? Does it accept T1L = 9 cycles (0.5625 µs) or need 10 (0.625 µs)? A scope/logic-analyzer test is needed (D6).
2. Does the PIC24 SPI master insert a gap between back-to-back words when the FIFO is non-empty? Needed only if SPI is chosen.
3. What is the wand's power source (USB through a serial bridge, a 5 V adapter, battery)? It sets the brightness cap. A bridge may have requested far less than 300 mA.
4. Is a 5 V rail and a 74AHCT125 available on the lab kit?
5. Which bulb or strip, and which remote protocol? Do we have an IR receiver and logic analyzer to capture the codes?
6. Is a separate physical lamp mandatory, or may the ring or matrix count as the "bulb"? (TA question.) Is mains in a lamp socket acceptable, or must it be the 12 V strip?
7. Does the LIS3DH tolerate a long SCL-low pause? (C6a/C1.)
8. Does the PC ever send to the wand while a show runs (recorder tool commands during animations)?
9. Which ICSP set does the lab programmer use (C6a open question 1)? It decides whether RB5/RB6 or RB10/RB11 are free for option b in layout (b).
10. Layout (a) or (b) (D7)?
