# [AI-GENERATED: Claude Code]
CC      ?= cc
PY      ?= python3
BUILD   := build
CFLAGS  := -std=c99 -Wall -Wextra -Wconversion -Werror -pedantic -O2

.PHONY: test clean
test: $(BUILD)/c2_cli
	$(PY) test_c2.py $(BUILD)/c2_cli

$(BUILD)/c2_cli: c2_cli.c c2_frame.c c2_frame.h | $(BUILD)
	$(CC) $(CFLAGS) -o $@ c2_cli.c c2_frame.c

$(BUILD):
	mkdir -p $(BUILD)

clean:
	rm -rf $(BUILD) __pycache__
# [END AI-GENERATED]
