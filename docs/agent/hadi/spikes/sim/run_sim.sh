#!/bin/bash
# [AI-GENERATED: Claude Code]
# run_sim.sh - run an XC16 ELF in the MPLAB X simulator (MDB, headless).
# Usage: ./run_sim.sh <elf> [symbols...]
#   Program must define sim_start(), sim_end(), sim_done() (see demo.c).
#   cycles = instruction cycles from breakpoint sim_start to sim_end.
# Exit 7 = breakpoints hit in wrong order/count (or marker symbol missing).
# Output: name=value lines, then cycles=<n>. Non-zero exit on any failure.
# Env: MDB (path to mdb.sh), DEVICE, SIM_TIMEOUT (wall seconds, default 120),
#      RUN_WAIT_MS (per-Run Wait limit, default 60000).
set -u
ELF=${1:-}; shift || true
[ -n "$ELF" ] && [ -f "$ELF" ] || { echo "usage: $0 <elf> [symbols...]" >&2; exit 2; }
MDB=${MDB:-/Applications/microchip/mplabx/v6.35/mplab_platform/bin/mdb.sh}
DEVICE=${DEVICE:-PIC24FJ64GA002}
SIM_TIMEOUT=${SIM_TIMEOUT:-120}
RUN_WAIT_MS=${RUN_WAIT_MS:-60000}
HERE=$(cd "$(dirname "$0")" && pwd)
# per-run work dir: removed on success, kept on failure so "see $LOG" stays valid
BUILD=$(mktemp -d "${TMPDIR:-/tmp}/run_sim.XXXXXX")
trap '[ $? -eq 0 ] && rm -rf "$BUILD"' EXIT
NM=${NM:-/Applications/microchip/xc16/v2.10/bin/xc16-nm}
ELF=$(cd "$(dirname "$ELF")" && pwd)/$(basename "$ELF")
SCRIPT="$BUILD/run.mdb"; LOG="$BUILD/run.log"

{
  echo "Device $DEVICE"
  echo "Hwtool SIM"
  echo "Program \"$ELF\""
  echo "Break sim_start"
  echo "Break sim_end"
  echo "Break sim_done"
  echo "Run"; echo "Wait $RUN_WAIT_MS"          # halts at sim_start
  echo "Run"; echo "Wait $RUN_WAIT_MS"          # halts at sim_end
  echo "Stopwatch"                              # cycles (reset-on-run is default)
  echo "Run"; echo "Wait $RUN_WAIT_MS"          # halts at sim_done
  for s in "$@"; do echo "print $s"; done
  echo "Quit"
} > "$SCRIPT"

# watchdog: kill MDB (and its java child) if it exceeds SIM_TIMEOUT wall seconds
"$MDB" "$SCRIPT" > "$LOG" 2>&1 &
PID=$!
( exec >/dev/null 2>&1; sleep "$SIM_TIMEOUT"; pkill -P $PID; kill $PID ) &
WD=$!
wait $PID 2>/dev/null; RC=$?
pkill -P $WD 2>/dev/null; kill $WD 2>/dev/null; wait $WD 2>/dev/null
if [ $RC -ge 128 ]; then echo "ERROR: MDB timed out/killed (rc=$RC), see $LOG" >&2; exit 3; fi

HALTS=$(grep -c "Simulator halted" "$LOG")
if [ "$HALTS" -ne 3 ] || grep -q -i -E "^(Error|Exception)|Unknown (symbol|command)|(Could not|Unable to) (load|find|open) (the )?(program|file|symbol)" "$LOG"; then
  echo "ERROR: simulation did not halt at 3 markers (halts=$HALTS), see $LOG" >&2; exit 4
fi

# F1: the three halts must be at sim_start, sim_end, sim_done, in that order
sym_addr() { "$NM" "$ELF" | awk -v s="$1" '$3=="_"s {print $1; exit}'; }
EXP=""; for f in sim_start sim_end sim_done; do
  a=$(sym_addr $f); [ -n "$a" ] || { echo "ERROR: symbol $f not found in $ELF" >&2; exit 7; }
  EXP="$EXP $((16#$a))"
done
GOT=""; for a in $(sed -n 's/^Single breakpoint: @0x\([0-9A-Fa-f]*\).*/\1/p' "$LOG"); do GOT="$GOT $((16#$a))"; done
if [ "$(echo $GOT)" != "$(echo $EXP)" ]; then
  echo "ERROR: breakpoint order wrong: halted at [$(echo $GOT)], expected sim_start/sim_end/sim_done at [$(echo $EXP)] (decimal addrs), see $LOG" >&2; exit 7
fi

NSW=$(grep -c '^Stopwatch cycle count = ' "$LOG")
[ "$NSW" -eq 1 ] || { echo "ERROR: expected exactly 1 stopwatch line, got $NSW, see $LOG" >&2; exit 5; }
CYC=$(sed -n 's/^Stopwatch cycle count = \([0-9]*\).*/\1/p' "$LOG")
[ -n "$CYC" ] || { echo "ERROR: no cycle count in $LOG" >&2; exit 5; }

# values: MDB prints "name=" then the value on the next non-blank line
awk -v syms="$*" '
  BEGIN { n = split(syms, S, " "); for (i=1;i<=n;i++) want[S[i]]=1 }
  /^[A-Za-z_][A-Za-z0-9_]*=$/ { nm=$0; sub(/=$/,"",nm); if (nm in want) { getline; while ($0 ~ /^[ \t]*$/) getline; v=$0; gsub(/^[ \t]+|[ \t]+$/,"",v); print nm "=" v } }
' "$LOG" > "$BUILD/vals.txt"
for s in "$@"; do
  grep -q "^$s=" "$BUILD/vals.txt" || { echo "ERROR: no value for $s, see $LOG" >&2; exit 6; }
done
cat "$BUILD/vals.txt"
echo "cycles=$CYC"
# [END AI-GENERATED]
