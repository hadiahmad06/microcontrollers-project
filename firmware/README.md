<!-- [AI-GENERATED: Claude Code] -->
# firmware/

Layout (docs/human/REPO_LAYOUT.md): product code in `src/` (one `.c`/`.h` pair per module),
host tests in `test/<module>/`, Python tools in `../tools/`.

`make test` at the repo root runs every suite. Each suite builds its tests twice:
- **host**: `cc`, 32-bit `int`, large vector sets.
- **sim16**: `avr-gcc` for an ATmega2560 run under `simavr`. It has a 16-bit `int` like XC16 and
  8 KB RAM like the PIC24FJ64GA002, so missing casts and int-promotion overflows show up
  (FRAMEWORK_REVIEW T2). It is **not** the PIC24: gate G3 (MPLAB simulator / hardware) is still required.

Needs: `cc`, `python3`, and for sim16 `apt-get install simavr gcc-avr avr-libc`.
Contracts every module follows: `docs/agent/CONTRACTS.md`.
<!-- [END AI-GENERATED] -->
