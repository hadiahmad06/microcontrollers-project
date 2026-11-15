# [AI-GENERATED: Claude Code]
# SPIKE S3-1 (throwaway): integration of drain -> trigger -> capture -> classify on synthetic continuous
# streams. SYNTHETIC, UNVERIFIED. Compiles the REAL firmware/src modules and the trigger spike in place.
#   make test    builds, runs host and sim16 (16-bit int), checks host == sim16 and C == Python, prints
#                the table and "INTEGRATION SPIKE DONE"
#   make ram     static RAM of the glue and of the modules (avr-size / avr-nm)
ROOT := ../../../../..
include $(ROOT)/firmware/test/common.mk
TRIG   := ../trigger
MODEL  := build/model
SPIKE_INC := -iquote . -iquote $(TRIG) -iquote $(MODEL)
MODS   := $(foreach m,lis3dh capture features mlp knn classify,$(SRC_DIR)/$(m).c)
SRCS   := glue.c fake_lis3dh.c $(TRIG)/trigger.c $(MODS) $(SIM16_SRC)
HDRS   := $(wildcard $(SRC_DIR)/*.h) $(wildcard *.h) $(TRIG)/trigger.h
HCF    := $(HOST_CFLAGS) $(SPIKE_INC)
ACF    := $(AVR_CFLAGS) $(SPIKE_INC)

# host runs: NAME:STREAM:OVR_MODE
# OVR_MODE 1 = corrected order (default); stall0 keeps 0 on purpose to demonstrate the bug fixed by S3-1 finding 1.
HOSTRUNS := main:main:1 big:big:1 tight:tight:1 stall0:stall:0 stall1:stall:1 stall2:stall:2 stallw:stall:1 short:short:1
EXTRA_stallw := -DFSS_WRAP   # FIFO_SRC reports a full FIFO as FSS = 0 + OVRN (bench item C-7 alternative)
NAMES    := $(foreach r,$(HOSTRUNS),$(word 1,$(subst :, ,$(r))))
# W2-3: the same streams classified by a model trained with --onset-jitter -25,12 (host only, no sim16)
MODEL_J  := build/model_jit
JITRUNS  := main_jit:main:1 big_jit:big:1
JNAMES   := $(foreach r,$(JITRUNS),$(word 1,$(subst :, ,$(r))))

.PHONY: test clean ram all
test: $(foreach n,$(NAMES) $(JNAMES),build/out_$(n)_host.txt) build/out_short_sim16.txt
	$(PY) evaluate.py --build build --runs "$(NAMES) $(JNAMES)" --sim short
	@echo "INTEGRATION SPIKE DONE"

# ---- model: seeded synthetic dataset -> tools/train.py -> gesture_model.h (never committed) ----
$(MODEL)/gesture_model.h:
	@mkdir -p build
	$(PY) $(TOOLS_DIR)/synth_dataset.py --out build/train_ds.npz --per-class 120 --seed 1
	$(PY) $(TOOLS_DIR)/train.py --data build/train_ds.npz --out-dir $(MODEL) --seed 1 --epochs 60 > build/train.log 2>&1
	@tail -1 build/train.log

# jittered model: same seeds and sizes, only the gesture onset position differs (tools/synth_dataset.py --onset-jitter)
$(MODEL_J)/gesture_model.h:
	@mkdir -p build
	$(PY) $(TOOLS_DIR)/synth_dataset.py --out build/train_ds_jit.npz --per-class 120 --seed 1 --onset-jitter=-25,12
	$(PY) $(TOOLS_DIR)/train.py --data build/train_ds_jit.npz --out-dir $(MODEL_J) --seed 1 --epochs 60 > build/train_jit.log 2>&1
	@tail -1 build/train_jit.log

# ---- streams ----
build/main.h build/big.h build/tight.h build/stall.h build/short.h: make_stream.py
	@mkdir -p build
	$(PY) make_stream.py --out build

# ---- host builds (one per run; the stream header and OVR_MODE are compile-time) ----
define HOSTRULE
build/glue_$(1)_host: $(SRCS) $(HDRS) build/$(2).h $(MODEL)/gesture_model.h Makefile
	@mkdir -p build
	$(HOST_CC) $(HCF) -DSTREAM_HDR='"build/$(2).h"' -DOVR_MODE=$(3) $$(EXTRA_$(1)) -o $$@ $(SRCS)
build/out_$(1)_host.txt: build/glue_$(1)_host
	./$$< > $$@
endef
$(foreach r,$(HOSTRUNS),$(eval $(call HOSTRULE,$(word 1,$(subst :, ,$(r))),$(word 2,$(subst :, ,$(r))),$(word 3,$(subst :, ,$(r))))))

# jittered-model host runs: the jittered model dir comes first on the include path
define JITRULE
build/glue_$(1)_host: $(SRCS) $(HDRS) build/$(2).h $(MODEL_J)/gesture_model.h Makefile
	@mkdir -p build
	$(HOST_CC) -iquote $(MODEL_J) $(HCF) -DSTREAM_HDR='"build/$(2).h"' -DOVR_MODE=$(3) -o $$@ $(SRCS)
build/out_$(1)_host.txt: build/glue_$(1)_host
	./$$< > $$@
endef
$(foreach r,$(JITRUNS),$(eval $(call JITRULE,$(word 1,$(subst :, ,$(r))),$(word 2,$(subst :, ,$(r))),$(word 3,$(subst :, ,$(r))))))

# ---- sim16: avr-gcc ATmega2560, 16-bit int, under simavr; short stream only ----
build/glue_short_avr.elf: $(SRCS) $(HDRS) build/short.h $(MODEL)/gesture_model.h
	@mkdir -p build
	$(AVR_CC) $(ACF) -DSTREAM_HDR='"build/short.h"' -DOVR_MODE=1 -o $@ $(SRCS)
build/out_short_sim16.txt: build/glue_short_avr.elf
	$(SIM16_RUN) $< 900 > $@

ram: build/glue_short_avr.elf
	avr-size -C --mcu=atmega2560 build/glue_short_avr.elf
	avr-nm -S --size-sort -t d build/glue_short_avr.elf | grep -i " [bBdD] " | tail -25

clean:
	rm -rf build __pycache__
# [END AI-GENERATED]
