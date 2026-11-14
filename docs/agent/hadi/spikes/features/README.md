# C3 feature-extraction spike (S1-2)

Spike, not product code. Integer feature extraction in C (`features.c`) and Python
(`features_ref.py`), proven bit-exact. Spec and decisions: `../../proposals/C3_features.md`.

## Run
    make test   # host build (clang, -std=c99 -Wall -Wextra -Wconversion -Werror), 10062 windows, exact compare
    make xc16   # XC16 v2.10 compile, zero warnings, prints size
    make clean

## Files
- `features.c/.h` C99 implementation; `features_ref.py` Python reference (integer-only)
- `host_runner.c` windows file -> features file; `gen_vectors.py` vector generator
- `compare.py` exact comparison; `div15_check.c` exhaustive /15 vs multiply-shift check

## Results (2026-11-14)
- `make test`: `PASS 10062/10062` (edge cases, 4000 uniform, 4000 smooth, 2000 segment-extreme); `DIV15 PASS 61426 sums`.
- `make xc16`: zero warnings. `.text` = 0x98 address units = 76 instructions = 228 bytes of flash
  (`features_extract` 0x40 + `segment_features` 0x58 address units). Uses `div.sw` for /15, no library calls, 0 data/bss.
- Not run on target: the on-target vector check (gate G3) is still required.
