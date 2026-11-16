# [AI-GENERATED: Claude Code]
# Suite for gesture.c (ticket 3.7T): scripted scenarios through the REAL modules on a fake LIS3DH and a
# fake board port; host build + sim16 (16-bit int) build + a bring-up build (-DGESTURE_BRINGUP_SAMPLES=1).
#   make test                      test firmware/src
#   make test IMPL_DIR=<dir>       take gesture.c (and any module present there) from <dir>
#   make test MODEL_SEED=3         other model (tests/mlp/gen_model.py seed; seed % 3 == 0 gives 100 Hz, +-4 g)
# gesture_port.h: firmware/src/gesture_port.h (merged); the test-local copy was removed.
ROOT := ../../..
include $(ROOT)/firmware/test/common.mk
MODEL_SEED ?= 48
MODS := lis3dh capture trigger features mlp knn classify c2_stream gesture
MOD_SRC := $(foreach m,$(MODS),$(or $(wildcard $(IMPL_DIR)/$(m).c),$(SRC_DIR)/$(m).c))
.PHONY: test clean
test:
	HOST_CC='$(HOST_CC)' HOST_CFLAGS='$(HOST_CFLAGS)' AVR_CC='$(AVR_CC)' AVR_CFLAGS='$(AVR_CFLAGS)' \
	SIM16_RUN='$(SIM16_RUN)' SIM16_SRC='$(SIM16_SRC)' MOD_SRC='$(MOD_SRC)' TOOLS_DIR='$(TOOLS_DIR)' \
	MLP_TEST_DIR='$(ROOT)/firmware/test/mlp' \
	$(PY) run_tests.py --build build --model-seed $(MODEL_SEED)
clean:
	rm -rf build
# [END AI-GENERATED]
