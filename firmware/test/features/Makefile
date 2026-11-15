# [AI-GENERATED: Claude Code]
# Test suite for firmware/src/features.c and tools/features_ref.py (ticket 3.3T).
#   make test                       test the real implementation
#   make test IMPL_DIR=<dir> SPIKE=1  test another implementation dir (e.g. the reviewed spike);
#                                   SPIKE=1 builds it with -DFEAT_ENERGY_MODE=1 -DSPIKE_STANDIN and
#                                   skips only the tools/features_ref.py, FEATURES_VERSION and
#                                   FEAT_IS_NONNEG checks (the spike does not have them).
ROOT := ../../..
include $(ROOT)/firmware/test/common.mk
IMPL_DIR ?= $(SRC_DIR)
SPIKE    ?=
SEED     ?= 12345
N_HOST   ?= 5000
N_SIM    ?= 300
SIM_TIMEOUT ?= 600
ifeq ($(SPIKE),1)
EXTRA := -DFEAT_ENERGY_MODE=1 -DSPIKE_STANDIN
RUNFLAGS := --spike
else
EXTRA :=
RUNFLAGS :=
endif
# Implementation dir goes on the QUOTE path only (-iquote, never -I): a features.h on a -I path
# would shadow glibc's <features.h>. common.mk already uses -iquote for src/ and sim16/.
INC := -iquote $(IMPL_DIR) -iquote .
SIMDEFS := -DTEST_SEED=$(SEED)u -DTEST_N=$(N_SIM) -DTEST_KSTEP=509 -DTEST_NRAND_ISQRT=150
SRCS := test_features.c $(IMPL_DIR)/features.c $(SIM16_SRC)
DEPS := test_features.c ss_table.h $(IMPL_DIR)/features.c $(IMPL_DIR)/features.h $(SIM16_DIR)/sim16.h

.PHONY: test clean FORCE
test: build/test_host build/test_avr.elf ss_table.py
	$(PY) run_tests.py --host build/test_host --elf build/test_avr.elf --sim-run $(SIM16_RUN) \
	    --tools $(TOOLS_DIR) --seed $(SEED) --n-host $(N_HOST) --n-sim $(N_SIM) \
	    --sim-timeout $(SIM_TIMEOUT) $(RUNFLAGS)

# Rebuilt every time because IMPL_DIR / SPIKE / SEED may change between runs.
build/test_host: $(DEPS) FORCE
	@mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) $(INC) $(EXTRA) -o $@ $(SRCS)
build/test_avr.elf: $(DEPS) FORCE
	@mkdir -p build
	$(AVR_CC) $(AVR_CFLAGS) $(INC) $(EXTRA) $(SIMDEFS) -o $@ $(SRCS)
	@avr-size $@ | tail -1
FORCE:
clean:
	rm -rf build
# [END AI-GENERATED]
