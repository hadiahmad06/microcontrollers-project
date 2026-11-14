# [AI-GENERATED: Claude Code]
# QA for S1-2 features. The implementation is read from IMPL (read-only), copied into build/.
IMPL   ?= /Users/hadiahmad/Documents/Academic/ee2361/project/docs/agent/hadi/spikes/features
CC     := clang
XC16   ?= /Applications/microchip/xc16/v2.10/bin
PY     ?= python3
BUILD  := build
CFLAGS := -std=c99 -Wall -Wextra -Wconversion -Werror -O2

.PHONY: test xc16 clean
test: $(BUILD)/host_runner
	$(PY) run_tests.py $(BUILD)/host_runner $(BUILD)
	$(MAKE) --no-print-directory xc16

$(BUILD)/src.stamp: $(IMPL)/features.c $(IMPL)/features.h $(IMPL)/host_runner.c
	mkdir -p $(BUILD)
	cp $(IMPL)/features.c $(IMPL)/features.h $(IMPL)/host_runner.c $(BUILD)/
	touch $@

$(BUILD)/host_runner: $(BUILD)/src.stamp
	$(CC) $(CFLAGS) -o $@ $(BUILD)/host_runner.c $(BUILD)/features.c

xc16: $(BUILD)/src.stamp
	@for o in O1 O2 Os; do \
	  echo "== XC16 -$$o =="; \
	  $(XC16)/xc16-gcc -mcpu=24FJ64GA002 -$$o -std=c99 -Wall -Wextra -Wconversion -c \
	    $(BUILD)/features.c -o $(BUILD)/f_$$o.o > $(BUILD)/xc16_$$o.log 2>&1; rc=$$?; \
	  cat $(BUILD)/xc16_$$o.log; \
	  if grep -q "restricted license" $(BUILD)/xc16_$$o.log; then echo "NOTE -$$o disabled by free-license limits (not actually tested at -$$o)"; fi; \
	  if grep -v -e "restricted license" -e "microchip.com" $(BUILD)/xc16_$$o.log | grep -q .; then echo "FAIL xc16 -$$o (warnings)"; \
	  elif [ $$rc -ne 0 ]; then echo "FAIL xc16 -$$o (error)"; else echo "PASS xc16 -$$o (no warnings)"; fi; \
	done

clean:
	rm -rf $(BUILD)
# [END AI-GENERATED]
