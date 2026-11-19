# [AI-GENERATED: Claude Code]
# Makefile for the PIC24FJ64GA002 recording firmware (ticket HAL). Run on the Mac:
#   make -C firmware/build record.hex MODEL=/path/to/gesture_model.h
#   make -C firmware/build bringup.hex MODEL=/path/to/gesture_model.h
#   make -C firmware/build check            (host syntax check, no XC16 needed)
# UNVERIFIED: not run with XC16. Every xc16 flag below is from memory; see firmware/hal/pic24/README.md.

XC16   ?= /Applications/microchip/xc16/v2.10/bin
CC16   := $(XC16)/xc16-gcc
BIN2HEX:= $(XC16)/xc16-bin2hex
MCU    := 24FJ64GA002
MODEL  ?=

SRC    := ../src
HAL    := ../hal/pic24
APP    := ../app
OBJ    := obj

# firmware/src/*.c excluding nothing (spec H2); gesture.c is picked up automatically once it exists.
SRC_C  := $(wildcard $(SRC)/*.c)
# ws2812_pic24.c needs ws2812_send.s, which this Makefile does not assemble; the recording build does not use it.
HAL_C  := $(filter-out $(HAL)/ws2812_pic24.c,$(wildcard $(HAL)/*.c))
APP_C  := $(APP)/main_record.c

# -iquote: build dir first so the copied gesture_model.h wins; then src and the HAL.
INCS   := -iquote . -iquote $(SRC) -iquote $(HAL)
CFLAGS := -mcpu=$(MCU) -std=gnu99 -Os -Wall -Wextra $(INCS) -mconst-in-code -fno-common -ffunction-sections -fdata-sections
# --heap=0 (no malloc), --stack=512 (C7), map file. The device linker script is chosen by -mcpu (review F6);
# if flash gets tight add -Wl,--gc-sections back.
# --script: -mcpu alone does not pull in the SFR symbols (_IFS0bits, ...); C7 requires the device script.
LDFLAGS:= -mcpu=$(MCU) -Wl,--script=p$(MCU).gld,--heap=0,--stack=512

.PHONY: all clean check
all: record.hex

# --- model header: copied next to the objects so -iquote . finds it ---
# Real file target: re-copied when MODEL changes on disk; every object depends on it (review F5).
gesture_model.h: $(MODEL)
	@test -n "$(MODEL)" || { echo "error: pass MODEL=path/to/gesture_model.h"; exit 1; }
	cp "$(MODEL)" gesture_model.h

# --- one build directory per image (bringup has a different define) ---
define IMAGE
$(1)_OBJS := $$(patsubst %.c,$(OBJ)/$(1)/%.o,$$(notdir $(SRC_C) $(HAL_C) $(APP_C)))

$(OBJ)/$(1)/%.o: $(SRC)/%.c gesture_model.h | $(OBJ)/$(1)
	$(CC16) $(CFLAGS) $(2) -c $$< -o $$@
$(OBJ)/$(1)/%.o: $(HAL)/%.c gesture_model.h | $(OBJ)/$(1)
	$(CC16) $(CFLAGS) $(2) -c $$< -o $$@
$(OBJ)/$(1)/%.o: $(APP)/%.c gesture_model.h | $(OBJ)/$(1)
	$(CC16) $(CFLAGS) $(2) -c $$< -o $$@
$(OBJ)/$(1):
	mkdir -p $$@

$(1).elf: $$($(1)_OBJS)
	$(CC16) $$($(1)_OBJS) $(LDFLAGS),-Map=$(1).map -o $$@

$(1).hex: $(1).elf
	$(BIN2HEX) $$<
endef

$(eval $(call IMAGE,record,))
$(eval $(call IMAGE,bringup,-DGESTURE_BRINGUP_SAMPLES=1))

# --- host syntax check against the register mock (no XC16) ---
# Uses the stub API header only when firmware/src/gesture.h does not exist yet.
CHECK_FLAGS := -std=c99 -Wall -Wextra -Wconversion -Werror -fsyntax-only -Wno-unknown-pragmas \
               -DHAL_CHECK_MOCK $(if $(wildcard $(SRC)/gesture.h),,-DHAL_CHECK_STUB_API) \
               -iquote $(SRC) -iquote $(HAL) -iquote $(HAL)/test
check:
	@for f in $(HAL_C) $(APP_C); do \
	    echo "cc -fsyntax-only $$f"; \
	    $(CC) $(CHECK_FLAGS) $$f || exit 1; \
	done
	@echo "check: OK (mock only; NOT a substitute for an XC16 build)"

clean:
	rm -rf $(OBJ) gesture_model.h *.elf *.hex *.map
# [END AI-GENERATED]
