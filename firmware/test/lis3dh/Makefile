# [AI-GENERATED: Claude Code]
# Suite for lis3dh.c (ticket WP1-bT): fake LIS3DH + driver tests, host build and sim16 (16-bit int).
#   make test                       test the real firmware/src implementation
#   make test IMPL_DIR=standin      prove the harness against the spec stand-in in standin/
#   make test DRAIN_MODEL=B         oracle reading B: after each burst keep draining while FSS > 0
#                                   (default A, the only asserted one: stop when the re-read n < 16)
ROOT := ../../..
include $(ROOT)/firmware/test/common.mk
IMPL_DIR ?= $(SRC_DIR)
DRAIN_MODEL ?= A
IMPL_SRC := $(IMPL_DIR)/lis3dh.c
IMPL_HDR := $(wildcard $(IMPL_DIR)/*.h)
TEST_SRC := test_lis3dh.c fake_lis3dh.c
TEST_HDR := fake_lis3dh.h
DEFS     := -DDRAIN_MODEL_$(DRAIN_MODEL)
.PHONY: test clean FORCE
test: build/test_lis3dh_host build/test_lis3dh_avr.elf
	@echo "== host (32-bit int) =="
	./build/test_lis3dh_host
	@echo "== sim16 (16-bit int, simavr) =="
	$(SIM16_RUN) build/test_lis3dh_avr.elf 120
	@echo "lis3dh suite PASS"
# FORCE: IMPL_DIR may change between runs without any file getting newer.
build/test_lis3dh_host: $(TEST_SRC) $(TEST_HDR) $(IMPL_SRC) $(IMPL_HDR) $(SIM16_SRC) $(SIM16_DIR)/sim16.h FORCE
	@mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) $(DEFS) -o $@ $(TEST_SRC) $(IMPL_SRC) $(SIM16_SRC)
build/test_lis3dh_avr.elf: $(TEST_SRC) $(TEST_HDR) $(IMPL_SRC) $(IMPL_HDR) $(SIM16_SRC) $(SIM16_DIR)/sim16.h FORCE
	@mkdir -p build
	$(AVR_CC) $(AVR_CFLAGS) $(DEFS) -o $@ $(TEST_SRC) $(IMPL_SRC) $(SIM16_SRC)
FORCE:
clean:
	rm -rf build
# [END AI-GENERATED]
