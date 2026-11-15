# [AI-GENERATED: Claude Code]
# Shared settings for every firmware/test/<module>/Makefile. Include it with
#   ROOT := ../../..
#   include $(ROOT)/firmware/test/common.mk
# Two build flavours of the same test sources:
#   host  : cc, 32-bit int, fast, big vector sets
#   sim16 : avr-gcc for ATmega2560 under simavr, 16-bit int like XC16 (FRAMEWORK_REVIEW T2)
# Firmware headers are on the QUOTE path only (-iquote): firmware/src/features.h would otherwise
# shadow glibc's <features.h> and break <stdint.h>/<stdio.h>. Include them as "features.h".
SRC_DIR    := $(ROOT)/firmware/src
# Implementation under test; `make test IMPL_DIR=dir` swaps it. Searched BEFORE firmware/src (review 3.3R L1).
IMPL_DIR   ?= $(SRC_DIR)
SIM16_DIR  := $(ROOT)/firmware/test/sim16
TOOLS_DIR  := $(ROOT)/tools
PY         ?= python3
HOST_CC    ?= cc
HOST_CFLAGS := -std=c99 -Wall -Wextra -Wconversion -Werror -pedantic -O2 -iquote $(IMPL_DIR) -iquote $(SRC_DIR) -iquote $(SIM16_DIR)
AVR_CC     ?= avr-gcc
AVR_CFLAGS := -mmcu=atmega2560 -std=c99 -Wall -Wextra -Wconversion -Werror -O1 -iquote $(IMPL_DIR) -iquote $(SRC_DIR) -iquote $(SIM16_DIR)
SIM16_RUN  := $(SIM16_DIR)/run_sim16.sh
SIM16_SRC  := $(SIM16_DIR)/sim16.c
# [END AI-GENERATED]
