# [AI-GENERATED: Claude Code]
# Trigger spike (ticket S2-2). UNVERIFIED on real data. Host only, throwaway.
CFLAGS = -std=c99 -Wall -Wextra -Wconversion -Werror -pedantic -O1
AVRFLAGS = -mmcu=atmega2560 -std=c99 -Wall -Wextra -Wconversion -Werror -O1 -c

.PHONY: test clean

trigger_cli: trigger_cli.c trigger.c trigger.h
	cc $(CFLAGS) -o $@ trigger_cli.c trigger.c

test: trigger_cli
	@echo "== compile check: host cc"
	cc $(CFLAGS) -c trigger.c -o /dev/null
	@echo "== compile check: avr-gcc atmega2560 (16-bit int)"
	avr-gcc $(AVRFLAGS) trigger.c -o /dev/null
	@echo "== C versus Python mirror"
	python3 evaluate.py compare
	@echo "== rate table (C code, synthetic data)"
	python3 evaluate.py table
	@echo "ALL PASS"

clean:
	rm -f trigger_cli *.o
	rm -rf __pycache__
# [END AI-GENERATED]
