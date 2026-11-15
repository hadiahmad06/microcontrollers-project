<!-- [AI-GENERATED: Claude Code] -->
# Proxy measurements (cloud, avr-gcc), not the PIC24

Ticket 3.10 (cycles, RAM, flash on the PIC24 from the XC16 map file and Timer1) is still required. These numbers
come from `avr-gcc -mmcu=atmega2560 -std=c99 -Os -c` per module (2026-11-15, commit after WP1-aF), with a
gesture_model.h produced by `tools/train.py` on synthetic data. AVR code size is NOT comparable to PIC24 code
size; static RAM is (same C objects), except that AVR keeps `const` data in RAM while XC16 puts it in flash (PSV).

| Module | .text (AVR) | .data | .rodata (PIC24: flash) | .bss | C7 budget line |
|---|---:|---:|---:|---:|---|
| features | 402 | 0 | 0 | 0 | scratch on the stack |
| capture | 548 | 0 | 0 | 1007 | buffer 900 + ring 96 (+ 11 B state) |
| knn | 1912 | 0 | 0 | 1216 | templates 1200 + metadata 16 |
| classify | 192 | 0 | 0 | 0 | – |
| mlp | 1278 | 0 | 1432 | 0 | weights in flash (C4: ~1464 data B) |
| display | 736 | 0 | 0 | 192 | framebuffer 192 |
| icons | 146 | 0 | 165 | 0 | flash |
| lis3dh | 936 | 2 | 6 | 97 | staging 96 (+ 1 B address) |
| **Total** | 6150 | 2 | 1603 | **2512** | C7 lines for these items: 2500 |

Static RAM of the modules written so far is 2512 B; C7's matching lines sum to 2500 B (+12 B of state). Still missing
from the measurement: gesture.c, trigger, C2 TX pump and rings (C7: 160 B), I2C/UART driver state, stack (512 B), C runtime.
<!-- [END AI-GENERATED] -->
