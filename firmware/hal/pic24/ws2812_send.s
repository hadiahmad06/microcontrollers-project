; [AI-GENERATED: Claude Code]
; ws2812_send.s: cycle-counted WS2812 bit-bang on RB15 (pin 26), FCY = 16 MHz (62.5 ns per cycle).
;
; void ws2812_send_asm(const uint8_t *p /* W0 */, uint16_t n /* W1 */);
;   Sends n bytes MSB first. The CALLER masks interrupts (ws2812_pic24.c).
;
; Timing per bit (cycles, 1 cycle = 62.5 ns), counted from the BSET:
;   0-bit: high 6  (375 ns), low 15 (938 ns)
;   1-bit: high 12 (750 ns), low 9  (563 ns)   -> WS2812_T1L_CYCLES = 9 (CONTRACTS C6.3)
;   period 21 cycles = 1.31 us; the last bit of each byte has a 4-cycle longer low (harmless).
; BTSS skip = 2 cycles, BRA taken = 2, everything else 1 (PIC24 instruction set, DS70157).
; Debug driver (docs/agent/hadi/TODO.md T-2): scope-verify before trusting the numbers.

    .include "xc.inc"
    .text
    .global _ws2812_send_asm

_ws2812_send_asm:
    cp0     W1                  ; n == 0 ?
    bra     z, 9f
1:  mov.b   [W0++], W2          ; next byte into W2 low byte
    mov     #8, W3              ; 8 bits per byte
2:  bset    LATB, #15           ; c0: LATB15 = 1, data line high
    nop                         ; c1
    nop                         ; c2
    nop                         ; c3
    nop                         ; c4
    btss    W2, #7              ; c5 (c5-c6 when the bit is 1: skip)
    bclr    LATB, #15           ; c6: 0-bit -> LATB15 = 0 after 6 cycles high
    nop                         ; c7
    nop                         ; c8
    nop                         ; c9
    nop                         ; c10
    nop                         ; c11
    bclr    LATB, #15           ; c12: 1-bit -> LATB15 = 0 after 12 cycles high
    nop                         ; c13
    nop                         ; c14
    nop                         ; c15
    nop                         ; c16
    sl      W2, W2              ; c17: next bit into bit 7
    dec     W3, W3              ; c18
    bra     nz, 2b              ; c19-c20 -> next BSET at c21
    dec     W1, W1
    bra     nz, 1b
9:  return

; [END AI-GENERATED]
