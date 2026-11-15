# [AI-GENERATED: Claude Code]
# Suite for capture.c (ticket WP1-aT): host build + sim16 (16-bit int) build.
#   make test                      test the real firmware/src implementation
#   make test IMPL_DIR=standin     prove the harness against the spec stand-in in standin/
#   make test SEED=7 NHOST=1500    other seed / episode counts
ROOT := ../../..
include $(ROOT)/firmware/test/common.mk
IMPL_DIR ?= $(SRC_DIR)
SEED  ?= 1
NHOST ?= 1500
NSIM  ?= 150
IMPL_SRC := $(IMPL_DIR)/capture.c
IMPL_HDR := $(wildcard $(IMPL_DIR)/*.h)
.PHONY: test clean
test: build/test_capture_host build/test_capture_avr.elf
	$(PY) run_tests.py --host build/test_capture_host --elf build/test_capture_avr.elf \
	    --sim16 $(SIM16_RUN) --seed $(SEED) --nhost $(NHOST) --nsim $(NSIM)
# the directed scripts live in oracle.py only; the C driver includes them generated
build/scripts.h: oracle.py
	@mkdir -p build
	$(PY) oracle.py --emit-header > $@
build/test_capture_host: test_capture.c build/scripts.h $(IMPL_SRC) $(IMPL_HDR) $(SIM16_SRC) $(SIM16_DIR)/sim16.h
	@mkdir -p build
	$(HOST_CC) -iquote build $(HOST_CFLAGS) -o $@ test_capture.c $(IMPL_SRC) $(SIM16_SRC)
build/test_capture_avr.elf: test_capture.c build/scripts.h $(IMPL_SRC) $(IMPL_HDR) $(SIM16_SRC) $(SIM16_DIR)/sim16.h FORCE
	@mkdir -p build
	$(AVR_CC) -iquote build $(AVR_CFLAGS) -DTEST_SEED=$(SEED)u -DTEST_NEP=$(NSIM)u -o $@ \
	    test_capture.c $(IMPL_SRC) $(SIM16_SRC)
FORCE:
clean:
	rm -rf build
# [END AI-GENERATED]
