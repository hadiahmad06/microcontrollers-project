#!/bin/bash
# [AI-GENERATED: Claude Code]
# selftest.sh - check run_sim.sh failure paths and concurrency.
#  order.c  -> expect rc 7 (wrong breakpoint order)
#  hang.c   -> expect rc 3 or 4 (never reaches sim_end)
#  2 parallel demo runs -> both rc 0
export _ZO_DOCTOR=0
HERE=$(cd "$(dirname "$0")" && pwd)
XC16=${XC16:-/Applications/microchip/xc16/v2.10/bin/xc16-gcc}
T="$HERE/build/selftest"; mkdir -p "$T/tmp"
# expected-failure runs keep their work dirs; keep them inside build/ rather than $TMPDIR
export TMPDIR="$T/tmp"
fail=0
# check <name> <rc> <allowed rc>... : print ok/FAIL and record failure
check() {
  local n=$1 rc=$2; shift 2
  for ok in "$@"; do [ "$rc" = "$ok" ] && { echo "ok   $n (rc=$rc)"; return; }; done
  echo "FAIL $n (rc=$rc, wanted: $*)"; fail=1
}
for p in order hang; do
  "$XC16" -mcpu=24FJ64GA002 -O1 -g -o "$T/$p.elf" "$HERE/../sim_qa/$p.c" || exit 1
done
"$HERE/run_sim.sh" "$T/order.elf" result_done >"$T/order.out" 2>&1; check order "$?" 7
RUN_WAIT_MS=2000 SIM_TIMEOUT=60 "$HERE/run_sim.sh" "$T/hang.elf" result_done >"$T/hang.out" 2>&1; check hang "$?" 3 4
"$HERE/run_sim.sh" "$HERE/build/demo.elf" result_dot >"$T/p1.out" 2>&1 & P1=$!
"$HERE/run_sim.sh" "$HERE/build/demo.elf" result_dot >"$T/p2.out" 2>&1 & P2=$!
wait $P1; check parallel1 "$?" 0
wait $P2; check parallel2 "$?" 0
grep -q '^result_dot=-60661056$' "$T/p1.out" || { echo "FAIL parallel1 values"; fail=1; }
grep -q '^result_dot=-60661056$' "$T/p2.out" || { echo "FAIL parallel2 values"; fail=1; }
[ $fail = 0 ] && echo "SELFTEST PASS" || { echo "SELFTEST FAIL"; exit 1; }
# [END AI-GENERATED]
