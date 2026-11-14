# [AI-GENERATED: Claude Code]
# End-to-end bit-exact suite (ticket 3.8, PLAN gate G2 + 16-bit pre-check of G3): C firmware path
# (features -> mlp -> knn -> classify) versus the Python tools, host and sim16.
#   make test                       test firmware/src
#   make test IMPL_DIR=/tmp/broken  swap in modules from another directory (any module missing
#                                   there falls back to firmware/src); proves the suite can fail
#   make test SEED=7 NPER_HOST=500  other seed / counts (host windows per model = 7 * NPER_HOST)
# Generated gesture_model.h files go to build/m<N>/ and are never committed.
ROOT := ../../..
include $(ROOT)/firmware/test/common.mk
SEED      ?= 1
MODELS    ?= 3
NPER_HOST ?= 300
NPER_SIM  ?= 15
# Module sources: from IMPL_DIR when present there, else firmware/src.
MOD_SRC := $(foreach m,features mlp knn classify,$(or $(wildcard $(IMPL_DIR)/$(m).c),$(SRC_DIR)/$(m).c))
.PHONY: test clean build
test:
	HOST_CC='$(HOST_CC)' HOST_CFLAGS='$(HOST_CFLAGS)' AVR_CC='$(AVR_CC)' AVR_CFLAGS='$(AVR_CFLAGS)' \
	SIM16_RUN='$(SIM16_RUN)' SIM16_SRC='$(SIM16_SRC)' MOD_SRC='$(MOD_SRC)' TOOLS_DIR='$(TOOLS_DIR)' \
	$(PY) run_e2e.py --build build --seed $(SEED) --models $(MODELS) --nper-host $(NPER_HOST) --nper-sim $(NPER_SIM)
build:
	mkdir -p build
clean:
	rm -rf build
# [END AI-GENERATED]
