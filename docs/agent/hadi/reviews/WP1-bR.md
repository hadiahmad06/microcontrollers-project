<!-- [AI-GENERATED: Claude Code] -->
# WP1-bR: review of the LIS3DH driver and its suite

Reviewer: review-18 (wrote none of the code). Working for: hadi. Date: 2026-11-15.
Scope: `firmware/src/{lis3dh.c,lis3dh.h,lis3dh_hal.h,board_axes.h}`, `firmware/test/lis3dh/**`, against CONTRACTS C0, C1, C6.1, C6.2, the C1/C6a proposal fact tables, AGENTS.md section 7 and the rulings R1-R5 (treated as spec). Nothing was fixed.

## Verdict: APPROVE WITH NITS

No high findings. Every register value, the init order, the 16-bit byte assembly, the drain bounds and all five rulings match the spec. The 4 medium findings are one doc/code mismatch (`lis3dh_address()` after a failed init), two coverage gaps that let a real mutant survive, and one bench risk (read-back of CLICK_THS bit 7). Counts: high 0, medium 4, low 6.

## Findings

| ID | file:line | Finding | Evidence | Severity |
|---|---|---|---|---|
| F1 | `lis3dh.c:66-81`, `lis3dh.h:32` | After a failed `lis3dh_init` that got past the probe (`LIS3DH_ERR_BUS` from any config write or read-back), `s_addr` stays non-zero, so `lis3dh_address()` returns 0x18/0x19. The header says "0x18 or 0x19 after a successful init, otherwise 0". `s_addr` is only cleared at the start of init. No test asserts the value after a failed init (`t_init_faults` never calls `lis3dh_address`). | Harness `scratchpad/ex/ex.c` with a HAL whose read-backs return 0: `init=-3 addr=18`. | medium |
| F2 | `test_lis3dh.c:239` (`t_init_faults`) | The suite does not check that init stops at the first fault. A mutant that records the error, keeps writing the remaining registers and returns `LIS3DH_ERR_BUS` at the end passes every group (m16). The contract (every write read back, mismatch gives ERR_BUS) is satisfied by the return value, but a half-failed bus would keep being hammered and CTRL_REG1 = 0x57 could be written after an earlier failure. | Mutation m16: all 24 PASS lines, rc 0. | medium |
| F3 | `test_lis3dh.c` (whole), `lis3dh.c:65,148` | `lis3dh_init(NULL)` and `lis3dh_unpack(raw, NULL, out)` (documented "NULL = identity") are never called by the suite. The defensive clamp `s > 2 -> 0` (`lis3dh.c:157`) and non-+-1 sign values (`a->sign[k] < 0` test, anything else treated as +1) are untested too. `grep` of the test file for NULL / 0-pointer init/unpack finds nothing; `setup()` always passes a table. | grep shows no NULL-axes call. | medium |
| F4 | `lis3dh.c:106-108` | Bench risk, not a defect against the spec: `write_verify(REG_CLICK_THS, 0xB0)` fails init with `LIS3DH_ERR_BUS` if bit 7 (LIR_Click) is reserved on the real part and reads back as 0 (value 0x30). The C6a proposal 3.5 and C1 open question 2 say the Rev 1 datasheet shows bit 7 as "-" and only AN3308 Rev 3 shows LIR_Click, so this is a live uncertainty (BENCH C-7). A permanent init failure would block everything, with no fallback or diagnostic that names the register. Suggest: the bench item must run before the first full-firmware flash, or mask bit 7 in the read-back compare for this one register. | C6a 3.5 "Spec detail (S1-1R)", C1 4.2. | medium |
| F5 | `lis3dh.c:46`, `fake_lis3dh.c:92,120,134,149,166` | `write_verify` (static helper) has only a one-line brief: no `@param`/`@return`. Same for the five static helpers in the fake (one-line `/** */`). `fifo_unread` is complete. AGENTS.md 7 requires purpose, each argument and the return value on public functions; the ticket asks the same of static helpers. Public functions are documented in `lis3dh.h` / `lis3dh_hal.h` and are complete. | read of the files | low |
| F6 | `lis3dh.c:103` | CLICK_CFG comment says "bits 7:6 = 0 (LIR reserved / unused)". LIR for the click engine is CLICK_THS bit 7 (the next register, line 106), not a CLICK_CFG bit. Bits 7:6 are simply unused. Wording could mislead a bench reader. | AN3308 sec 8.3 as cited in C6a 3.5 | low |
| F7 | `lis3dh.c:119-120` | CTRL_REG5 comment lists bits 7, 6, 3:0 but not bits 5:4 (unused, 0). CTRL_REG6 comment (98-99) lists bits 7:1 but not bit 0 (unused). The "comment every register write, bit field by bit field" rule is nearly but not fully met. Values are correct. | read | low |
| F8 | `lis3dh.c:208,227,244` | `lis3dh_drain` and `lis3dh_read_click` issue I2C reads at address 0 (the general-call address) if called before a successful init (`s_addr == 0`). Not reachable by the specified call sequence, but a one-line guard returning `LIS3DH_ERR_BUS` when `s_addr == 0` would remove the case. Also relevant to F1 (after a failed init `s_addr != 0`, so the guard alone would not help; clear `s_addr` on failure). | read | low |
| F9 | `lis3dh.c:133` | If the final CTRL_REG1 = 0x57 write succeeds but the read-back fails or mismatches, init returns `LIS3DH_ERR_BUS` while the sensor may already be sampling and filling its FIFO. Benign (a later init starts from CTRL_REG1 = 0x00 and Bypass), but worth a comment or a power-down write on failure. | read | low |
| F10 | `lis3dh.c:152` | Informational: the missing `(uint16_t)` cast in the byte assembly is invisible to both builds (mutant m5 survives on host and sim16, as the tester warned). The cast is present at `lis3dh.c:152` in exactly the C1.1 form. No action. | m5 survives; read by eye | info |
| F11 | `test_lis3dh.c` (R5) | R5 is asserted only for bursts (`FAKE_F_MSB` on every burst read, `test_lis3dh.c:644`). It is not asserted that single-byte reads (WHO_AM_I, FIFO_SRC, CLICK_SRC, read-backs) leave bit 7 clear. The driver is correct (only the burst ORs `AUTO_INC`); a mutant that set 0x80 on every read (single-byte ones included) would survive, because the fake strips bit 7 and only the burst reads are checked for the flag. | read | low |

Medium: F1, F2, F3, F4. Low: F5, F6, F7, F8, F9, F11. Info: F10.

## Checklist results

1. Register writes (all match C0, C1 and C6a fact tables; ODR/FS/HR values correct for 100 Hz, +-4 g, HR; comments agree except F6, F7):
   - CTRL_REG1 0x00 then 0x57: ODR 0101 (100 Hz), LPen 0, Zen/Yen/Xen = 1; last write starts sampling.
   - CTRL_REG4 0x18: BDU 0, BLE 0, FS 01 (+-4 g, 0x10), HR 1 (0x08), ST 00, SIM 0. Matches C0 (+-4 g, HR, 12-bit). BDU = 0 is the ruled UNVERIFIED value and is commented as such.
   - CTRL_REG3 0x06: I1_WTM (bit 2) and I1_OVERRUN (bit 1). Matches C1.6 and the C1 fact row "INT1 sources".
   - CTRL_REG6 0x80: I2_CLICK, INT_POLARITY 0 (active high, rising edge, as C6.1).
   - CLICK_CFG 0x2A (ZD, YD, XD), CLICK_THS 0xB0 (LIR + 48 counts = 1.5 g at 31.25 mg/count), TIME_LIMIT 0x04 (40 ms), TIME_LATENCY 0x10 (160 ms), TIME_WINDOW 0x30 (480 ms): equal to C6.1 and C6a 3.5; unit comments correct at 100 Hz.
   - CTRL_REG5 0x40 (FIFO_EN), FIFO_CTRL 0x00 (Bypass, clears the FIFO) then 0x8F (Stream = 10, TR 0, FTH 01111 = 15). Matches C1.4.
   - Order is exactly the ruling. Register addresses (0x0F, 0x20, 0x22-0x25, 0x28, 0x2E, 0x2F, 0x38-0x3D) match C6a facts; CLICK_SRC bit 6 IA / bit 5 DCLICK match C6a 3.5.
2. 16-bit int: byte assembly is `(int16_t)(((uint16_t)raw[2k+1] << 8) | raw[2k])` then `(int16_t)(w >> 4)` (`lis3dh.c:152-153`), the required C1.1 form. Index math `2u*k+1u` is uint8 and small. Burst length `(uint8_t)(k * 6u)` with k <= 16 is at most 96, fits uint8_t; `(uint8_t)(j * 6u)` at most 90. `total` is int16_t, at most 64. R2: `-2048 -> 2047` clamp present (`lis3dh.c:164`). R4: `out[k] = sign[k] * in[src[k]]` implemented as written. The sim16 build (int = 16 bits, `-Wconversion -Werror`) passes.
3. Bounded behaviour: `lis3dh_drain` has one `for(;;)` with three exits (n==0 on first read, re-read n < 16, bursts >= 4). Maximum per call is 5 FIFO_SRC reads and 4 bursts, so it cannot loop more than 4 bursts or block on a HAL that always returns data. `k = min(n,16)`, so a burst is at most 96 B, the size of `s_stage`. Verified by running all 256 FIFO_SRC values against a standalone HAL stub (always returns that value, bursts return data) under ASan+UBSan: worst case 4 bursts, 5 FIFO_SRC reads, 64 samples, every burst length a multiple of 6 and at most 96 with bit 7 set, no sanitizer report, 0 violations. `*more` and `*overrun` are set from the right reads (`first` flag; `more` only after a re-read with n >= 16 at the bound).
4. Error paths: every HAL error returns `LIS3DH_ERR_BUS` (init via `write_verify`, drain at the FIFO_SRC read and the burst, click). Probe errors are treated as "nobody here" and end in `LIS3DH_ERR_SENSOR`, consistent with C6.1. Residual issues: F1, F8, F9. A later init after a failed one works (CTRL_REG1 = 0x00 and Bypass come first; tested by `t_init_faults`).
5. Test quality: the suite covers R1 (both FSS encodings, literal and model checks, levels 0..64), R2 (all permutations x signs with extreme words, literals), R3 (all 256 CLICK_SRC values, clear-on-read, bus error), R4, R5 for bursts, every NACK position after the probe for both addresses, a read-back mismatch for every config register, the 4-burst bound, `more` and overrun from the first read only, bus errors at every drain transaction, host and sim16. Gaps: F2, F3, F11, plus no assertion on `lis3dh_address()` after failure (F1). Mutation results below.
6. Course rules: AI markers are the exact `// [AI-GENERATED: Claude Code]` / `// [END AI-GENERATED]` form in every C and header file (Makefile uses `#`, fine). `AI_USAGE.md` has a row for every function in `lis3dh.c` (including `write_verify`, `fifo_unread`), `test_lis3dh.c`, `fake_lis3dh.c` and the stand-in (script check, no missing rows). ST DocID17530 and AN3308 Rev 3 are cited in `lis3dh.h`, `lis3dh.c`. Fixed-width types everywhere; no float, double or malloc; no delays (`grep` clean). `lis3dh_hal.h` doc comments complete. Doc comments: see F5. Register writes commented bit by bit: see F6, F7.

## Commands and outputs

```
git merge --ff-only claude/optimistic-meitner-67qdon      # fast-forwarded
cd firmware/test/lis3dh && make clean; make test          # host + sim16 (int = 2): all groups PASS, "lis3dh suite PASS"
bash scratchpad/mut.sh                                    # 15 mutations (table below)
cc -std=c99 -fsanitize=address,undefined -iquote firmware/src ex.c lis3dh.c && ./ex
   init=-3 addr=18                                        # F1 (HAL read-back returns 0)
   worst bursts=4 fifo_reads=5 samples=64 bad=0           # all 256 FIFO_SRC values
make test IMPL_DIR=<scratch>/mut/m16 (init continues) ; m17 (burst not clamped) ; m18 (probe 0x19 first)
```
All mutants live in the session scratchpad (`.../scratchpad/mut/mN/lis3dh.c`), never in the repo.

## Mutation table

| # | Mutation of `lis3dh.c` | Result | Caught by |
|---|---|---|---|
| m1 | CTRL_REG4 = 0x08 instead of 0x18 | killed | init@0x18, init@0x19 (exact write sequence) |
| m2 | CTRL_REG3 and CTRL_REG4 writes swapped | killed | init@0x18, init@0x19 (order) |
| m3 | re-read stop test changed to `n <= 16` (drain continues only while n > 16 instead of n >= 16) | killed | drain levels and arrivals, both encodings |
| m4 | missing read-back compare in `write_verify` | killed | init faults (13 checks) |
| m5 | drop the `(uint16_t)` cast in the byte assembly | SURVIVED (host and sim16) | nothing; known invisible, fine by eye (F10) |
| m6 | burst sub-address without 0x80 | killed | drain levels, arrivals (R5 via `FAKE_F_MSB`) |
| m7 | MAX_BURSTS = 5 | killed | drain arrivals/bound, both encodings |
| m8 | R1 decode disabled (FSS 0 with OVRN taken as empty) | killed | the three FSS-wrap groups only (as designed) |
| m9 | init no longer clears `s_addr` at start | killed | init faults (stale address) |
| m10 | FIFO_CTRL second write 0x8E | killed | init@0x18, init@0x19 |
| m11 | `lis3dh_read_click` returns 1 on IA alone | killed | click (R3) |
| m12 | `-(-2048)` clamp removed | killed | unpack axes (R2) |
| m13 | overrun taken from every FIFO_SRC read, not only the first | killed | drain arrivals, both encodings |
| m14 | CTRL_REG5 = 0x44 | killed | init@0x18, init@0x19 |
| m15 | `(uint16_t)w >> 4` (logical shift) | killed | unpack and drain groups |
| m16 | init keeps writing after a failed write, returns ERR_BUS at the end | SURVIVED | nothing (F2) |
| m17 | burst size k = n (no clamp to 16) | killed | drain levels and arrivals |
| m18 | probe order 0x19 then 0x18 | killed | init@0x18, init@0x19, init faults |

Of 18 mutants, 16 are killed; the two survivors are m5 (not detectable by design) and m16 (a real gap, F2).
<!-- [END AI-GENERATED] -->
