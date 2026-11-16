# [AI-GENERATED: Claude Code]
# Suite for c2_stream.c (ticket T-c2txT): host build + sim16 (16-bit int) build.
#   make test                      test the real firmware/src implementation
#   make test IMPL_DIR=standin     prove the harness against the spec stand-in in standin/
ROOT := ../../..
include $(ROOT)/firmware/test/common.mk
IMPL_DIR ?= $(SRC_DIR)
IMPL_SRC := $(IMPL_DIR)/c2_stream.c
IMPL_HDR := $(wildcard $(IMPL_DIR)/*.h)
.PHONY: test clean
test: build/test_c2_stream_host build/test_c2_stream_avr.elf
	$(PY) run_tests.py --host build/test_c2_stream_host --elf build/test_c2_stream_avr.elf \
	    --sim16 $(SIM16_RUN)
# the directed scripts live in oracle.py only; the C driver includes them generated
build/scripts.h: oracle.py
	@mkdir -p build
	$(PY) oracle.py --emit-header > $@
build/test_c2_stream_host: test_c2_stream.c build/scripts.h $(IMPL_SRC) $(IMPL_HDR) $(SIM16_SRC) $(SIM16_DIR)/sim16.h FORCE
	@mkdir -p build
	$(HOST_CC) -iquote build $(HOST_CFLAGS) -o $@ test_c2_stream.c $(IMPL_SRC) $(SIM16_SRC)
build/test_c2_stream_avr.elf: test_c2_stream.c build/scripts.h $(IMPL_SRC) $(IMPL_HDR) $(SIM16_SRC) $(SIM16_DIR)/sim16.h FORCE
	@mkdir -p build
	$(AVR_CC) -iquote build $(AVR_CFLAGS) -o $@ test_c2_stream.c $(IMPL_SRC) $(SIM16_SRC)
FORCE:
clean:
	rm -rf build
# [END AI-GENERATED]
