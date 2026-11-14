#!/bin/bash
# [AI-GENERATED: Claude Code]
# cyc.sh - build cyc.c for each REGION and print simulator cycles.
# Usage: ./cyc.sh   (needs XC16 and MPLAB X at the standard paths)
export _ZO_DOCTOR=0
HERE=$(cd "$(dirname "$0")" && pwd)
SIM="$HERE/../sim/run_sim.sh"
XC16=${XC16:-/Applications/microchip/xc16/v2.10/bin/xc16-gcc}
mkdir -p "$HERE/build"
for r in 0 1 2 3 4 5 6 7; do
  "$XC16" -mcpu=24FJ64GA002 -O1 -g -DREGION=$r -o "$HERE/build/cyc$r.elf" "$HERE/cyc.c" || exit 1
  out=$("$SIM" "$HERE/build/cyc$r.elf" result_done 2>&1) || { echo "region $r FAILED: $out"; continue; }
  echo "region $r: $(echo "$out" | grep ^cycles=)"
done
# [END AI-GENERATED]
