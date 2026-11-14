<!-- [AI-GENERATED: Claude Code] -->
# C2 UART framing spike (ticket S2-1)

Host-only, throwaway. Proves that the framing recommended in
`docs/agent/hadi/proposals/C2_uart_stream.md` round-trips bit-exactly between C and Python.
Nothing here ran on a PIC24; XC16 was not available. **UNVERIFIED on target:** the code avoids
`int`-width assumptions (every shift is on `uint16_t`/`uint32_t`, byte stores are explicitly cast)
but only host `cc` (GCC, 32-bit `int`) built it.

```
make test      # builds with cc -std=c99 -Wall -Wextra -Wconversion -Werror -pedantic, runs test_c2.py
make clean
```

Expected: a list of `PASS` lines and a final `ALL PASS` (exit code 0).

| File | What |
|---|---|
| `c2_frame.h/.c` | C99 encoder for WINDOW and HELLO frames into a caller buffer, CRC-16/IBM-3740 (nibble table, 32 B data, about 48 B flash). No float, no malloc, no blocking. |
| `c2_cli.c` | Test driver only (uses stdio): `crc <string>` and `encode` (text records in, frames out). Not firmware; host only, fixed-width types except `char`/`int main`. |
| `c2_ref.py` | Python bitwise CRC, encoders, and a streaming byte-at-a-time `Decoder` with resync (drop one byte and rescan on any failure). It knows only HELLO (LEN 10) and WINDOW (LEN 914); any other TYPE or LEN is a bad header. |
| `test_c2.py` | CRC check value 0x29B1; C bytes equal Python bytes for 1 HELLO and 40 WINDOW frames (incl. -2048, 2047 and full int16 extremes); clean round trip; directed damage (garbage, fake sync, flipped bit, dropped byte, damaged LEN, truncated frame); 40 fuzzed streams; fix round S2-1R: unknown/reserved TYPE, TYPE > 0x0F, LEN 1024/1025, damaged HELLO LEN, ASCII text between frames, measured worst-case stall. |

Citation: CRC-16/IBM-3740 (poly 0x1021, init 0xFFFF, no reflection, xorout 0, check 0x29B1), Greg Cook,
"Catalogue of parametrised CRC algorithms", https://reveng.sourceforge.io/crc-catalogue/16.htm.
Recalled from memory; the check value is asserted by the test, the page was not re-read.
The nibble-table CRC technique has no citation: it is our own derivation from the bitwise definition, verified by the test. No code was borrowed.

The wire format is specified in the header comment of `c2_frame.h` and in the proposal section 3.
<!-- [END AI-GENERATED] -->
