# [AI-GENERATED: Claude Code]
# Shared settings for every firmware/test/<module>/Makefile. Include it with
#   ROOT := ../../..
#   include $(ROOT)/firmware/test/common.mk
# Two build flavours of the same test sources:
#   host  : cc, 32-bit int, fast, big vector sets
#   sim16 : avr-gcc for ATmega2560 under simavr, 16-bit int like XC16 (FRAMEWORK_REVIEW T2)
SRC_DIR    := $(ROOT)/firmware/src
SIM16_DIR  := $(ROOT)/firmware/test/sim16
TOOLS_DIR  := $(ROOT)/tools
PY         ?= python3
HOST_CC    ?= cc
HOST_CFLAGS := -std=c99 -Wall -Wextra -Wconversion -Werror -pedantic -O2 -I$(SRC_DIR) -I$(SIM16_DIR)
AVR_CC     ?= avr-gcc
AVR_CFLAGS := -mmcu=atmega2560 -std=c99 -Wall -Wextra -Wconversion -Werror -O1 -I$(SRC_DIR) -I$(SIM16_DIR)
SIM16_RUN  := $(SIM16_DIR)/run_sim16.sh
SIM16_SRC  := $(SIM16_DIR)/sim16.c
# [END AI-GENERATED]
