# [AI-GENERATED: Claude Code]
# Repo-level entry point. `make test` runs every host test suite under firmware/test/<module>/
# (each suite's Makefile has a `test` target; host + sim16 flavours, see firmware/test/common.mk).
SUITES := $(sort $(dir $(wildcard firmware/test/*/Makefile)))

.PHONY: test clean
test:
	@set -e; for d in $(SUITES); do echo "=== $$d ==="; $(MAKE) --no-print-directory -C $$d test; done; \
	 echo "ALL SUITES PASS ($(words $(SUITES)) suites)"

clean:
	@for d in $(SUITES); do $(MAKE) --no-print-directory -C $$d clean; done
# [END AI-GENERATED]
