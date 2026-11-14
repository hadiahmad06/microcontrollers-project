<!-- [AI-GENERATED: Claude Code] -->
# sim_qa: independent tests for spikes/sim/run_sim.sh (S1-4R)

| File | Purpose |
|---|---|
| `cyc.c`, `cyc.sh` | Regions of known cycle cost (`-DREGION=0..7`); `./cyc.sh` builds and prints cycles for each. |
| `vals.c`, `check_vals.py` | Negative int16/int32, uint32 max, 16-bit multiply bug (`a*b` without cast), 60-element array; oracle checks the output. |
| `hang.c`, `order.c` | Failure-path programs (never halts; wrong breakpoint order). |
| `run_sim_mktemp.sh` | Copy of `run_sim.sh` with a per-run `mktemp -d` work dir (proposed concurrency fix). |

## Reading an array back (60 x int16 verified)

`print <array>` works directly. MDB prints `feat=` then `{v0, v1, ...}` on one line, signed decimal.
`run_sim.sh` already handles that shape, so no change is needed:

```sh
xc16-gcc -mcpu=24FJ64GA002 -O1 -g -o build/vals.elf vals.c
../sim/run_sim.sh build/vals.elf feat r_nocast   # -> feat={-30000, -28889, ...}   (one line)
```

Parse on the host: `[int(t) for t in line.split("=",1)[1].strip("{}").split(",")]`
(see `check_vals.py`). Requirements: the array is a non-static global (or `volatile`/used so it
survives -O1), and the program reaches `sim_done()` before the read. `print /x feat` should give hex
(not tested). Larger arrays than 60 were not tested.

## Notes for test authors

- In XC16 inline asm `;` starts a comment. Separate instructions with `\n`, not `;`
  (a `nop;nop;...` macro silently assembled to one nop in the first run of cyc.c).
- Baseline of an empty region is 6 cycles (nop 1 + return 3 + call 2). Subtract it.
<!-- [END AI-GENERATED] -->
