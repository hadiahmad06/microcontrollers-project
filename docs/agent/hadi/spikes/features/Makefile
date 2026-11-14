# [AI-GENERATED: Claude Code]
CC      ?= cc
XC16    ?= /Applications/microchip/xc16/v2.10/bin
PY      ?= python3
BUILD   := build
CFLAGS  := -std=c99 -Wall -Wextra -Wconversion -Werror -O2

.PHONY: test xc16 clean
test: $(BUILD)/host_runner $(BUILD)/div15_check $(BUILD)/vectors.bin
	$(BUILD)/div15_check
	$(BUILD)/host_runner $(BUILD)/vectors.bin $(BUILD)/c_features.bin
	$(PY) compare.py $(BUILD)/vectors.bin $(BUILD)/c_features.bin

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/host_runner: host_runner.c features.c features.h | $(BUILD)
	$(CC) $(CFLAGS) -o $@ host_runner.c features.c

$(BUILD)/div15_check: div15_check.c | $(BUILD)
	$(CC) $(CFLAGS) -o $@ div15_check.c

$(BUILD)/vectors.bin: gen_vectors.py | $(BUILD)
	$(PY) gen_vectors.py $@

xc16: | $(BUILD)
	$(XC16)/xc16-gcc -mcpu=24FJ64GA002 -O1 -std=c99 -Wall -Wextra -Wconversion -c features.c -o $(BUILD)/features_xc16.o
	@echo "--- sections (bytes) ---"
	@$(XC16)/xc16-objdump -h $(BUILD)/features_xc16.o | grep -E "\.text|\.data|\.bss"
	@echo "--- symbols ---"
	@$(XC16)/xc16-objdump -t $(BUILD)/features_xc16.o | grep -E "features_extract|segment_features"
	@$(XC16)/xc16-objdump -d $(BUILD)/features_xc16.o > $(BUILD)/features_xc16.lst
	@echo "features_extract+segment_features instruction count: $$(grep -cE '^ +[0-9a-f]+:' $(BUILD)/features_xc16.lst)"
	@echo "(.text size is in address units: 2 per 24-bit instruction word; flash bytes = instructions x 3)"

clean:
	rm -rf $(BUILD)
# [END AI-GENERATED]
