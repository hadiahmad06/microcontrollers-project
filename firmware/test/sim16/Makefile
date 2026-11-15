# [AI-GENERATED: Claude Code]
# Self-test of the sim16 harness (host + 16-bit-int AVR build of probe.c).
ROOT := ../../..
include $(ROOT)/firmware/test/common.mk
.PHONY: test clean
test: build/probe_host build/probe_avr.elf
	./build/probe_host
	$(SIM16_RUN) build/probe_avr.elf 30
	@echo "sim16 harness PASS"
build/probe_host: probe.c sim16.c sim16.h
	@mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) -o $@ probe.c sim16.c
build/probe_avr.elf: probe.c sim16.c sim16.h
	@mkdir -p build
	$(AVR_CC) $(AVR_CFLAGS) -o $@ probe.c sim16.c
clean:
	rm -rf build
# [END AI-GENERATED]
