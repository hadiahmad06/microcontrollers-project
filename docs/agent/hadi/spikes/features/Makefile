# [AI-GENERATED: Claude Code]
CC      ?= cc
XC16    ?= /Applications/microchip/xc16/v2.10/bin
PY      ?= python3
BUILD   := build
CFLAGS  := -std=c99 -Wall -Wextra -Wconversion -Werror -O2
XFLAGS  := -mcpu=24FJ64GA002 -std=c99 -Wall -Wextra -Wconversion
NOISE   := restricted license\|microchip.com
# Energy variants exercised by `make test`, as name:FEAT_ENERGY_MODE:FEAT_ENERGY_SHIFT.
# "default" uses the header default (mode 0, shift 11); the others prove the alternatives bit-exact too.
MODES   := default s8:0:8 s7:0:7 s6:0:6 isqrt:1:0 isqrt15:2:0

.PHONY: test xc16 clean
test: $(BUILD)/div15_check $(BUILD)/vectors.bin
	$(BUILD)/div15_check
	@set -e; for m in $(MODES); do \
	  name=$${m%%:*}; rest=$${m#*:}; \
	  if [ "$$name" = default ]; then defs=""; args=""; else \
	    mode=$${rest%%:*}; shift=$${rest#*:}; \
	    defs="-DFEAT_ENERGY_MODE=$$mode -DFEAT_ENERGY_SHIFT=$$shift"; args="$$mode $$shift"; fi; \
	  echo "=== energy variant: $$name ($$defs) ==="; \
	  $(CC) $(CFLAGS) $$defs -o $(BUILD)/host_runner_$$name host_runner.c features.c; \
	  $(BUILD)/host_runner_$$name $(BUILD)/vectors.bin $(BUILD)/c_features_$$name.bin; \
	  $(PY) compare.py $(BUILD)/vectors.bin $(BUILD)/c_features_$$name.bin $$(cat $(BUILD)/vectors.bin.count) $$args; \
	done
	@echo "ALL VARIANTS PASS"

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/div15_check: div15_check.c features.c features.h | $(BUILD)
	$(CC) $(CFLAGS) -DFEAT_ENERGY_MODE=1 -o $@ div15_check.c features.c

$(BUILD)/vectors.bin: gen_vectors.py | $(BUILD)
	$(PY) gen_vectors.py $@

xc16: | $(BUILD)
	@set -e; for o in O1 O2; do \
	  echo "=== xc16-gcc -$$o: features.c and call_check.c (plain int16_t[150][3] caller) ==="; \
	  $(XC16)/xc16-gcc $(XFLAGS) -$$o -c features.c -o $(BUILD)/features_$$o.o 2>&1 | grep -v -i "$(NOISE)" || true; \
	  $(XC16)/xc16-gcc $(XFLAGS) -$$o -c call_check.c -o $(BUILD)/call_check_$$o.o 2>&1 | grep -v -i "$(NOISE)" || true; \
	done
	@set -e; for v in "0 11" "1 0" "2 0"; do set -- $$v; for o in O1 O2; do \
	  $(XC16)/xc16-gcc $(XFLAGS) -$$o -DFEAT_ENERGY_MODE=$$1 -DFEAT_ENERGY_SHIFT=$$2 -c features.c -o $(BUILD)/f_m$$1_$$o.o 2>&1 | grep -v -i "$(NOISE)" || true; \
	  $(XC16)/xc16-objdump -d $(BUILD)/f_m$$1_$$o.o > $(BUILD)/f_m$$1_$$o.lst; \
	  n=$$(grep -cE '^ +[0-9a-f]+:' $(BUILD)/f_m$$1_$$o.lst); \
	  echo "energy mode $$1 -$$o: $$n instructions = $$((n*3)) bytes flash; library calls: $$(grep -E 'call +_|call .*__' $(BUILD)/f_m$$1_$$o.lst | grep -c '__')"; \
	done; done
	@echo "xc16 done: any compiler warning text appears above (none expected)"

clean:
	rm -rf $(BUILD)
# [END AI-GENERATED]
