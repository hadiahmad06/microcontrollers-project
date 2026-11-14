<!-- [AI-GENERATED: Claude Code] -->
# Headless MPLAB X simulator spike (S1-4)

Result: **works headlessly**. MDB runs an XC16 ELF for PIC24FJ64GA002 in the software simulator,
we read globals back with `print`, and count instruction cycles with `Stopwatch`.
No GUI, no hardware, no install needed (MPLAB X ships its own arm64 Zulu JRE 8).

## Quick start

```sh
cd docs/agent/hadi/spikes/sim
make demo          # build + simulate + compare with expected.py
```

Output of the last run:

```
result_checksum=73432160
result_dot=-60661056
result_done=1
cycles=1130
PASS (cycles=1130)
```

Manual pieces:

```sh
/Applications/microchip/xc16/v2.10/bin/xc16-gcc -mcpu=24FJ64GA002 -O1 -g -o build/demo.elf demo.c
./run_sim.sh build/demo.elf result_checksum result_dot result_done   # name=value + cycles=N
python3 expected.py
```

`run_sim.sh` exit codes: 2 usage/no ELF, 3 timeout (MDB killed), 4 sim did not halt at all three
markers or MDB reported an error, 5 no cycle count, 6 requested symbol not printed.
Env overrides: `MDB`, `DEVICE`, `SIM_TIMEOUT` (wall seconds, default 120), `RUN_WAIT_MS` (default 60000).

## How it works: MDB script template

MDB is run as `mplab_platform/bin/mdb.sh <script>` (it forces headless java, uses the bundled JRE).

```
Device PIC24FJ64GA002
Hwtool SIM
Program "/abs/path/demo.elf"
Break sim_start
Break sim_end
Break sim_done
Run
Wait 60000        # halts at sim_start (Wait returns as soon as the target halts)
Run
Wait 60000        # halts at sim_end
Stopwatch         # prints "Stopwatch cycle count = N"  (reset on each Run by default)
Run
Wait 60000        # halts at sim_done
print result_dot  # prints "result_dot=" then the value on the next line
print /x result_checksum
Quit
```

Convention for test programs (see `demo.c`): three `noinline` empty functions `sim_start()`,
`sim_end()`, `sim_done()`. Breakpoints are by function name. Results go in global variables
(use `volatile` or make sure they are not optimised away).

Parse an array on the host: `[int(t) for t in line.split("=",1)[1].strip("{}").split(",")]`.

`make selftest` checks the runner itself: wrong order (rc 7), never-ending program (rc 3 or 4), two parallel runs (rc 0).
`make demo` also asserts `cycles=1130` exactly (`EXPECT_CYCLES` in the Makefile; the simulator is deterministic).

Chosen results mechanism: **breakpoint + `print` of globals** (no UART needed). UART-to-file was not tried.

## Timing

- One run: `run_sim.sh` alone about 6 s; `make demo` about 6.3 s warm (ELF already built) and about 11.5 s cold (includes the xc16 compile).
  Almost all of it is JVM + MDB startup and device load; the simulation itself is milliseconds.
  Only one MDB launch per program, so batch many test cases into one ELF.
- A bare `help` script takes about 5 s.

## Cycle counting notes

- `Stopwatch` counts instruction cycles (Fcy) between the last `Run` and the halt; default
  `Stopwatch ror` resets it on every Run, so the second `Stopwatch` printed after the
  sim_start -> sim_end run gives exactly that region. `Stopwatch nror` / `Stopwatch clear` exist.
- The count is from entering `sim_start` (breakpoint is at function entry) to entering `sim_end`,
  so it includes the few cycles of `sim_start`'s own nop/return and the call to `sim_end`.
  For a baseline, measure an empty region and subtract (a few cycles).
- The printed "(1.13 ms)" time assumes the simulator's default clock; trust only the cycle number.

## Gotchas

- Run from any directory; script paths must be absolute (run_sim.sh does this).
- Output is noisy: MDB echoes commands, prints a jline "dumb terminal" WARNING and `INFO: Could not read
  file ...seggerjlink` lines. Harmless. The login-shell zoxide banner in this environment also lands
  in the log (set `_ZO_DOCTOR=0` to silence).
- `print` format is `name=` newline `value`. Default is decimal (signed for signed types);
  `print /x` is hex. 32-bit values print correctly. Arrays work: `print arr` gives `arr=` then `{v0, v1, ...}` on one line (60 x int16 verified; not static, must survive -O1).
- An unknown symbol does not abort the script; run_sim.sh detects a missing value and fails.
- If the program never reaches a breakpoint, `Wait 60000` times out per Run; run_sim.sh then fails
  (halt count != 3). The wall-clock watchdog kills MDB after `SIM_TIMEOUT`.
- Parallel runs are safe: each run uses its own `mktemp -d` dir (`$TMPDIR/run_sim.XXXXXX`), deleted on success and kept on failure (the error message names the log). A harmless `SEVERE ... BindException` websocket message can appear in the log when two MDBs start at once; it does not affect results, so the runner does not treat it as an error.
- In XC16 inline asm `;` starts a comment; separate instructions with `\n` (a `nop;nop;nop` silently assembles to one nop).
- Exit code 7: halts did not occur at sim_start, sim_end, sim_done in that order (addresses resolved with `xc16-nm`); e.g. a test calling `sim_start` twice or skipping `sim_end`.
- Java: the bundled `zulu8...` JRE is used automatically (`common-vars.sh`); no system Java needed.
  Native arm64, no Rosetta involved.
- The simulator is the MPLAB X software model, not cycle-exact for peripherals/flash wait states;
  it is fine for CPU-bound code like the DSP/integer routines we want to check.
- `-O1` was used; XC16 `int` is 16-bit, so the demo exercises exactly the overflow behaviour
  host-compiled tests miss.
<!-- [END AI-GENERATED] -->
