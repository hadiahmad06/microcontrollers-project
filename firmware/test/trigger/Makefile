# [AI-GENERATED: Claude Code]
# Suite for trigger.c (ticket T-trigT): host build + sim16 (16-bit int) build.
#   make test                      test the real firmware/src implementation
#   make test IMPL_DIR=standin     prove the harness against the spec stand-in in standin/
#   make test NHOST=300 NSIM=6     more random episodes
ROOT := ../../..
include $(ROOT)/firmware/test/common.mk
IMPL_DIR ?= $(SRC_DIR)
SEEDS ?= 1,2,3
NHOST ?= 120
NSIM  ?= 12
SSIM  ?= 1
IMPL_SRC := $(IMPL_DIR)/trigger.c
IMPL_HDR := $(wildcard $(IMPL_DIR)/*.h)
.PHONY: test clean
test: build/test_trigger_host build/test_trigger_avr.elf
	$(PY) run_tests.py --host build/test_trigger_host --elf build/test_trigger_avr.elf \
	    --sim16 $(SIM16_RUN) --seeds $(SEEDS) --nhost $(NHOST) --seed-sim $(SSIM) --nsim $(NSIM)
# the directed scenarios live in oracle.py only; the C driver includes them generated
build/scripts.h: oracle.py
	@mkdir -p build
	$(PY) oracle.py --emit-header > $@
build/test_trigger_host: test_trigger.c build/scripts.h $(IMPL_SRC) $(IMPL_HDR) $(SIM16_SRC) $(SIM16_DIR)/sim16.h FORCE
	@mkdir -p build
	$(HOST_CC) -iquote build $(HOST_CFLAGS) -o $@ test_trigger.c $(IMPL_SRC) $(SIM16_SRC)
build/test_trigger_avr.elf: test_trigger.c build/scripts.h $(IMPL_SRC) $(IMPL_HDR) $(SIM16_SRC) $(SIM16_DIR)/sim16.h FORCE
	@mkdir -p build
	$(AVR_CC) -iquote build $(AVR_CFLAGS) -DTEST_SEED=$(SSIM)u -DTEST_NEP=$(NSIM)u -o $@ \
	    test_trigger.c $(IMPL_SRC) $(SIM16_SRC)
FORCE:
clean:
	rm -rf build
# [END AI-GENERATED]
