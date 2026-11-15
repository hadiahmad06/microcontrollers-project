# [AI-GENERATED: Claude Code]
# Suite for classify.c + knn.c (tickets 3.5T / 3.6T): host build + sim16 (16-bit int) build.
#   make test                      test the real firmware/src implementation
#   make test IMPL_DIR=standin     prove the harness against the spec stand-in in standin/
#   make test SEED=7 NHOST=5000    other seed / counts
ROOT := ../../..
include $(ROOT)/firmware/test/common.mk
SEED  ?= 1
NHOST ?= 2000
NSIM  ?= 100
IMPL_SRC := $(IMPL_DIR)/knn.c $(IMPL_DIR)/classify.c
IMPL_HDR := $(wildcard $(IMPL_DIR)/*.h)
.PHONY: test clean
test: build/test_classify_host build/test_classify_avr.elf
	$(PY) run_tests.py --host build/test_classify_host --elf build/test_classify_avr.elf \
	    --sim16 $(SIM16_RUN) --seed $(SEED) --nhost $(NHOST) --nsim $(NSIM)
build/test_classify_host: test_classify.c $(IMPL_SRC) $(IMPL_HDR) $(SIM16_SRC) $(SIM16_DIR)/sim16.h
	@mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -o $@ test_classify.c $(IMPL_SRC) $(SIM16_SRC)
build/test_classify_avr.elf: test_classify.c $(IMPL_SRC) $(IMPL_HDR) $(SIM16_SRC) $(SIM16_DIR)/sim16.h FORCE
	@mkdir -p build
	$(AVR_CC) $(AVR_CFLAGS) -DTEST_SEED=$(SEED)u -DTEST_NSCEN=$(NSIM)u -o $@ \
	    test_classify.c $(IMPL_SRC) $(SIM16_SRC)
FORCE:
clean:
	rm -rf build
# [END AI-GENERATED]
