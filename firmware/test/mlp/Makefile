# [AI-GENERATED: Claude Code]
# Independent test suite for mlp.c (ticket 3.4T). `make test` generates random models, builds the
# driver for host and sim16 against $(IMPL_DIR)/mlp.c and compares everything with oracle.py.
#   make test                       # tests firmware/src/mlp.c
#   make test IMPL_DIR=standin      # tests the stand-in (suite self-validation)
ROOT := ../../..
include $(ROOT)/firmware/test/common.mk
IMPL_DIR ?= $(SRC_DIR)
SEEDS    ?= 1,2,3,4,5
HOST_N   ?= 3000
SIM_N    ?= 150
.PHONY: test clean
test:
	HOST_CC='$(HOST_CC)' HOST_CFLAGS='$(HOST_CFLAGS)' AVR_CC='$(AVR_CC)' AVR_CFLAGS='$(AVR_CFLAGS)' \
	SIM16_RUN='$(SIM16_RUN)' SIM16_SRC='$(SIM16_SRC)' \
	$(PY) run_tests.py --impl '$(IMPL_DIR)' --build build --seeds $(SEEDS) --host-n $(HOST_N) --sim-n $(SIM_N)
clean:
	rm -rf build
# [END AI-GENERATED]
