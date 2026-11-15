#!/bin/bash
# [AI-GENERATED: Claude Code]
# run_sim16.sh ELF [TIMEOUT_S] - run an AVR test image under simavr and print its clean output.
# Exit code: 0 if the program printed "SIM16_EXIT 0"; 1 if it printed another code;
# 2 if it timed out or never printed SIM16_EXIT. simavr colours UART lines and ends each one
# with a "." in place of the newline, so both are stripped here (tests must not end a line in ".").
elf=$1; t=${2:-120}
[ -f "$elf" ] || { echo "run_sim16: no such file: $elf" >&2; exit 2; }
command -v simavr >/dev/null || { echo "run_sim16: simavr not installed (apt-get install simavr gcc-avr avr-libc)" >&2; exit 2; }
out=$(timeout "$t" simavr -m atmega2560 -f 16000000 "$elf" 2>&1 \
      | sed -e 's/\x1b\[[0-9;]*m//g' -e 's/\.$//' | grep -v '^Loaded [0-9]* \.')
printf '%s\n' "$out" | grep -v '^SIM16_EXIT '
code=$(printf '%s\n' "$out" | sed -n 's/^SIM16_EXIT \(-\{0,1\}[0-9]*\)$/\1/p' | tail -1)
[ -z "$code" ] && { echo "run_sim16: no SIM16_EXIT line (timeout ${t}s or crash)" >&2; exit 2; }
[ "$code" = 0 ] && exit 0 || exit 1
# [END AI-GENERATED]
