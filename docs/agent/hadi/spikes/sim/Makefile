# [AI-GENERATED: Claude Code]
XC16 ?= /Applications/microchip/xc16/v2.10/bin/xc16-gcc
SYMS  = result_checksum result_dot result_done
# Expected sim_start->sim_end cycles for demo.c at -O1 (exact; the simulator is deterministic).
# Update this number deliberately if demo.c or the compiler flags change.
EXPECT_CYCLES = 1130

.PHONY: demo selftest clean
demo: build/demo.elf
	@./run_sim.sh build/demo.elf $(SYMS) > build/sim.out || { cat build/sim.out; echo FAIL; exit 1; }
	@cat build/sim.out
	@grep -v '^cycles=' build/sim.out | sort > build/sim.vals
	@python3 expected.py | sort > build/exp.vals
	@if diff build/exp.vals build/sim.vals >/dev/null && [ "$$(grep ^cycles= build/sim.out)" = "cycles=$(EXPECT_CYCLES)" ]; then \
	  echo "PASS ($$(grep ^cycles= build/sim.out))"; \
	 else echo "FAIL (expected cycles=$(EXPECT_CYCLES))"; diff build/exp.vals build/sim.vals; exit 1; fi

build/demo.elf: demo.c
	@mkdir -p build
	$(XC16) -mcpu=24FJ64GA002 -O1 -g -o $@ demo.c

selftest: build/demo.elf
	@XC16="$(XC16)" ./selftest.sh

clean:
	rm -f build/*
# [END AI-GENERATED]
