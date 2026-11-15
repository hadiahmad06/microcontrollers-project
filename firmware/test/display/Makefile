# [AI-GENERATED: Claude Code]
# Suite for display.c + icons.c (ticket WP4-aT): host build + sim16 (16-bit int) build, three configs:
#   default   spec defaults (CAP 32, LIMIT 300 mA, no serpentine)
#   serp      -DDISPLAY_SERPENTINE=1
#   alt       -DDISPLAY_CAP=64 -DDISPLAY_LIMIT_MA=150
#   serpalt   serpentine together with the alt cap/limit (review finding L8)
#   make test                      test the real firmware/src implementation
#   make test IMPL_DIR=standin GOLDEN=0   prove the harness against the spec stand-in in standin/
#                                  (the stand-in has its own icons, so the golden table is skipped)
#   Any other IMPL_DIR (e.g. a mutated copy of firmware/src) is checked against the golden icon table.
#   make test SEED=7 NHOST=5000    other seed / counts
ROOT := ../../..
include $(ROOT)/firmware/test/common.mk
IMPL_DIR ?= $(SRC_DIR)
SEED  ?= 1
GOLDEN ?= 1
GOLDEN_OPT := $(if $(filter 0,$(GOLDEN)),--no-golden,)
NHOST ?= 1000
NSIM  ?= 40
CFGS  := default serp alt serpalt
FL_default :=
FL_serp := -DDISPLAY_SERPENTINE=1
FL_alt := -DDISPLAY_CAP=64 -DDISPLAY_LIMIT_MA=150
FL_serpalt := -DDISPLAY_SERPENTINE=1 -DDISPLAY_CAP=64 -DDISPLAY_LIMIT_MA=150
IMPL_SRC := $(IMPL_DIR)/display.c $(IMPL_DIR)/icons.c
IMPL_HDR := $(wildcard $(IMPL_DIR)/*.h)
HOSTS := $(foreach c,$(CFGS),build/test_display_$(c)_host)
ELFS  := $(foreach c,$(CFGS),build/test_display_$(c)_avr.elf)
.PHONY: test clean FORCE
test: $(HOSTS) $(ELFS)
	$(PY) run_tests.py --build build --sim16 $(SIM16_RUN) --seed $(SEED) --nhost $(NHOST) --nsim $(NSIM) $(GOLDEN_OPT) \
	    --cfg default:32:300:0 --cfg serp:32:300:1 --cfg alt:64:150:0 --cfg serpalt:64:150:1
build/test_display_%_host: test_display.c $(IMPL_SRC) $(IMPL_HDR) $(SIM16_SRC) $(SIM16_DIR)/sim16.h
	@mkdir -p build
	$(HOST_CC) $(HOST_CFLAGS) $(FL_$*) -o $@ test_display.c $(IMPL_SRC) $(SIM16_SRC)
build/test_display_%_avr.elf: test_display.c $(IMPL_SRC) $(IMPL_HDR) $(SIM16_SRC) $(SIM16_DIR)/sim16.h FORCE
	@mkdir -p build
	$(AVR_CC) $(AVR_CFLAGS) $(FL_$*) -DTEST_SEED=$(SEED)u -DTEST_NSCEN=$(NSIM)u -o $@ \
	    test_display.c $(IMPL_SRC) $(SIM16_SRC)
FORCE:
clean:
	rm -rf build
# [END AI-GENERATED]
