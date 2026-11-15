<!-- [AI-GENERATED: Claude Code] -->
# CITATIONS: consolidated source list (ticket S4-1)

Purpose: AGENTS.md section 7 says borrowed code and sources must be cited in a comment **and** in the docs. This
file is the "in the docs" half: one place listing every external source cited anywhere in the repo, where it is
cited, what it was used for, and whether the citing agent actually read it. Built by grep over `firmware/`,
`tools/`, `docs/agent/**` (proposals, reviews, spikes, CONTRACTS, PLAN, DECISION_SHEET) and `docs/human/**` at
branch `claude/optimistic-meitner-67qdon`. The author of this file read none of the sources itself; "Read?"
columns copy what the citing text or review says. `docs/archive/**` was not searched.

**For the course report: copy sections (a), (b) and (c).** Section (d) is internal provenance (our own spikes,
specs) and is for the repo. Read the Gaps list first: several entries are "recalled from memory" and should not be
presented in the report as verified.

Tags used in the "Read?" columns: **READ** = the citing agent or a named reviewer says it opened the text;
**READ (mirror)** = read through a third-party copy; **NOT READ** = text says it was not read; **FROM MEMORY** =
text says "recalled/from memory"; **UNTAGGED** = nothing says either way (treat as unverified).

Line numbers are for this commit and will drift; re-grep the token (for example `DocID17530`).

---

## (a) Datasheets, reference manuals, application notes (11)

| # | Exact title / document | ID, revision, date | URL as written in the repo | Cited at (file:line) | Used for | Read? |
|---|---|---|---|---|---|---|
| A1 | ST LIS3DH datasheet, MEMS digital output motion sensor | DocID17530 **Rev 1**, May 2010. Newest revision never read | `https://cdn-shop.adafruit.com/datasheets/LIS3DH.pdf` (Adafruit mirror; st.com unreachable) | code: `firmware/src/lis3dh.c:6,12` ("table 17"); `firmware/src/lis3dh.h:7`; `firmware/src/lis3dh_hal.h:28` ("section 5.1.1"); `firmware/test/lis3dh/test_lis3dh.c:32`; `firmware/test/lis3dh/fake_lis3dh.c:8`; `docs/agent/hadi/spikes/integration/fake_lis3dh.c:10` ("LIS3DH datasheet register map", no ID). docs: `proposals/C1_capture_buffer.md:6-7` (key [DS], 14 uses); `proposals/C6a_sensor_io.md:8` (9 uses); `proposals/C1b_trigger.md:42` (sensitivity 2 mg/digit, "datasheet Table 3"); `proposals/C5_classifier_output.md:43` (CLICK_SRC bits); `reviews/S1-1R.md:11-12`; `reviews/S1-3R.md:43` (CLICK_SRC 0x39 bits, Doc ID 17530 Rev 1 section 8.26 tables 57/58) | Register map, FIFO, click engine, sensitivity, I2C auto-increment bit; driver register values | **READ** Rev 1 by author of C1/C6a and by reviewers S1-1R, S1-3R. Code comments for CTRL_REG5/CTRL_REG6 reserved bits: **FROM MEMORY** (open_questions.md:88-90, see Gaps 3) |
| A2 | ST AN3308 application note, FIFO and click usage | DocID18198 **Rev 3**, June 2017 | `https://core-electronics.com.au/attachments/uploads/lis3dh-application-note.pdf` | code: `firmware/src/lis3dh.c:6`; `firmware/src/lis3dh.h:7` (both say "AN3308 Rev 3", neither gives DocID18198). docs: `proposals/C1_capture_buffer.md:7` (key [AN], 24 uses); `proposals/C6a_sensor_io.md:9` (10 uses); `reviews/S1-1R.md:13`; `reviews/WP1-bR.md:20` (sec 8.3) | FIFO drain timing (sec 9.5, 17.57 ms), CTRL_REG3 I1_OVERRUN, click setup | **READ (mirror)** by C1/C6a author and S1-1R |
| A3 | Microchip PIC24FJ64GA004 family data sheet (covers PIC24FJ64GA002, 28-pin) | **DS39881E** | `https://ww1.microchip.com/downloads/en/DeviceDoc/39881e.pdf` | `proposals/C6a_sensor_io.md:7` (key [PIC], 30 uses); `proposals/C6b_display_bulb.md:5-6` (13 uses); `proposals/C7_budget.md:4-5` (20 uses); `proposals/C2_uart_stream.md:48-52` (Eq. 17-2, Reg 17-2); `proposals/C4_model_header.md:127` (PSV timing, via review); `reviews/S1-1R.md`, `S1-3R.md`, `S1-5R.md` (19 uses, "actually opened and text-extracted", `S1-5R.md:5`). No firmware code comment cites it | Pin map, I2C/UART baud formulas (Eq. 16-1, 17-1/17-2), config words, PSV +1/+2 cycles, erase block size, 18 mA pin source, 16 MIPS | **READ** by C6a/C6b/C7 authors and S1-1R, S1-5R. **NOT READ by C4 author** (`C4_model_header.md:127`, "I did not read it", relied on review) |
| A4 | Microchip dsPIC33/PIC24 Family Reference Manual, "Inter-Integrated Circuit" | **DS70000195F** | `https://ww1.microchip.com/downloads/en/DeviceDoc/70000195f.pdf` | `proposals/C6a_sensor_io.md:10` (key [FRM-I2C], 2 uses); `reviews/S1-1R.md:15,23` | I2C BRG equation question; ruling: use DS39881E Eq. 16-1, not FRM Eq. 4-1 | **READ** (S1-1R) |
| A5 | Microchip PIC24F Family Reference Manual, I2C section | **DS39702** | none | `proposals/C6a_sensor_io.md:10`; `reviews/S1-1R.md:15` | Would have been the PIC24F-specific I2C chapter | **NOT READ** (HTTP 403); superseded by A4 per A4's preface |
| A6 | Microchip PIC24F Family Reference Manual (flash programming section assumed; title not stated in repo) | **DS39715** | none | `reviews/S1-5R.md:55`; `proposals/C7_budget.md:245` | Block erase time for k-NN persistence | **NOT READ**; erase time remains UNVERIFIED |
| A7 | Microchip MPLAB XC16 C Compiler User's Guide, v2.10 | **DS-50002071M** (ID appears only in C4, reviews and `mlp.c`; C7 gives the title and a local path) | local only: `/Applications/microchip/xc16/v2.10/docs/MPLAB_XC16_C_Compiler_Users_Guide.pdf` (`proposals/C7_budget.md:5`) | code: `firmware/src/mlp.c:11` (section 23, `>>` on negatives is `asr`). docs: `proposals/C4_model_header.md:5,36,117,127` (sections 23, 8.7.1, 12.3.1.1, `-mconst-in-code`, `auto_psv`); `reviews/S1-3R.md:32,48,49`; `reviews/3.4R.md:85`; `proposals/C7_budget.md:5`; `reviews/S1-1R.md:16` | Arithmetic shift semantics, const-in-code and PSV placement, 32K `auto_psv` limit, `--stack` option | **READ** (local PDF) by C4 author and S1-3R |
| A8 | Microchip dsPIC30F/33F Programmer's Reference Manual (title as given in `S1-5R.md:5`) | **DS70157** | none | `reviews/S1-5R.md:5,42,84,105,201`; `proposals/C6b_display_bulb.md:90,176` (via S1-5R) | `DISI` semantics (lit14 + 1 = 16384 cycles; priority 0 to 6 only), BRA/MUL.SS cycle counts | **READ** by S1-5R. Not cited in any code comment |
| A9 | XC16 v2.10 linker script `p24FJ64GA002.gld` (vendor file, not a document) | none | local only: `/Applications/microchip/xc16/v2.10/support/PIC24F/gld/p24FJ64GA002.gld` (`proposals/C7_budget.md:6`) | `proposals/C7_budget.md:6-7,41,125`; `reviews/S1-5R.md:5,50,51` | Config word addresses (0xABFC/0xABFE), program region 0x200..0xABFC | **READ** by C7 author and S1-5R |
| A10 | Worldsemi WS2812B datasheet (old revision), 2013 | no document ID; revision identified by date only | local copy `~/Downloads/WS2812B.pdf` (`proposals/C6b_display_bulb.md:7`) | `proposals/C6b_display_bulb.md:7,59-71`; `reviews/S1-5R.md:5,74`; `docs/agent/CONTRACTS.md:272` (variant switch, no citation); code `firmware/src/display.h:4,85` (names WS2812, GRB order, **no citation**) | Bit timings (T0H 0.40, T0L 0.85, T1H 0.80, T1L 0.45 us, +/-150 ns), reset above 50 us, GRB wire order | **READ** by C6b author and S1-5R |
| A11 | Worldsemi WS2812B-V5 datasheet | no document ID or revision stated | `learn.watterott.com/kb/ws281x/WS2812B-v5.pdf` (`proposals/C6b_display_bulb.md:8`) | `proposals/C6b_display_bulb.md:8,63,69-71,188`; `reviews/S1-5R.md:5,76`; `docs/agent/CONTRACTS.md:272` | V5 timing window (T0H 220-380 ns, others 580 ns to 1 us), reset above 280 us, VIH 0.63 VDD, quiescent 0.6 mA | **READ** by C6b author and S1-5R. C6b:188 ("idle 38 mA ... **UNVERIFIED** for old parts") is the one flagged figure |

---

## (b) Papers (5)

| # | Exact title | Authors, venue, year, ID | URL as written | Cited at (file:line) | Used for | Read? |
|---|---|---|---|---|---|---|
| B1 | "Quantization and Training of Neural Networks for Efficient Integer-Arithmetic-Only Inference" | Jacob et al. (first name list not given in repo), CVPR 2018, arXiv:1712.05877 | none (arXiv ID only) | code: `firmware/src/mlp.c:7-8`; `tools/infer_ref.py:14-17`; `tools/export_model.py:19-20`; `tools/README.md:67`. docs: `proposals/C4_model_header.md:127` (sections 2.1, 2.2 Eq. 6, 2.4, 3, Appendix B); `reviews/S1-3R.md:24,51-53`; `reviews/3.4R.md:85`. Not in any top-level doc | Fixed-point requantization M = 2^-n * M0, int32 bias, int8 weights in [-127,127]. The firmware uses the *idea*; the int64-free split multiply is our own (C4 section 2) | **READ** for the claims reviewed: S1-3R checked section 2.2 Eq. 6 and 2.1/2.4 CONFIRMED and found the section 3 cite for [-127,127] WRONG (fixed in C4). Not confirmed that the paper itself was fetched (S1-3R does not list it under sources) |
| B2 | "Distinctive Image Features from Scale-Invariant Keypoints" | Lowe, IJCV, 2004. No volume, pages or DOI anywhere | none | code: `firmware/src/knn.h:10-11` (full title); `firmware/src/knn.c:9` ("Lowe 2004"). docs: `proposals/C5_classifier_output.md:107`; `reviews/3.5R.md:23,97` (F8); `reviews/S1-3R.md:54`; `DECISION_SHEET.md:183`. **Not in CONTRACTS.md or any top-level doc** | Nearest-neighbour distance-ratio idea, used as "1 - d1/d2" confidence (C5.2) | **FROM MEMORY**: C5:107 says "from memory, UNVERIFIED citation detail"; S1-3R:54 "STILL UNVERIFIED, not checked" |
| B3 | "Adam: A Method for Stochastic Optimization" (title inferred; the repo gives no title) | Kingma and Ba, 2015, arXiv:1412.6980 | none | `tools/train.py:28`; `tools/README.md:137-138`; `reviews/W2-2R.md:102` | Optimizer in `train.py`; "textbook algorithm, no code borrowed" | **UNTAGGED**. Textbook-level citation, author did not state it was read. Not in any top-level doc |
| B4 | Wilson score interval (Wilson 1927; no title, journal or pages given) | E. B. Wilson, 1927 | none | `tools/train.py:29,356`; formula use without citation: `docs/agent/CONTRACTS.md:148` (C4.3 criterion), `proposals/C4_model_header.md:15`, `tools/export_model.py:243`, `spikes/quant/quant_ref.py:177` | 95 % interval on accuracy; C4.3 fallback rule | **UNTAGGED**; stated as "the standard formula" |
| B5 | "Xorshift RNGs" | G. Marsaglia, Journal of Statistical Software 8(14), 2003 | none | test drivers and Python oracles that implement xorshift32 (shifts 13/17/5), e.g. `firmware/test/{capture,classify,display,features,mlp,e2e}` (added by SW-3) | Deterministic PRNG mirrored in C and Python for test vectors | **FROM MEMORY** (citation added by the main agent's brief, SW-3; not re-read) |

---

## (c) Algorithm catalogues, guides, protocol and spec notes (5)

| # | Exact title | ID / revision | URL as written | Cited at (file:line) | Used for | Read? |
|---|---|---|---|---|---|---|
| C1 | Greg Cook, "Catalogue of parametrised CRC algorithms", entry **CRC-16/IBM-3740** (aliases CRC-16/CCITT-FALSE, CRC-16/AUTOSAR per S2-1R). Parameters: width 16, poly 0x1021, init 0xFFFF, refin/refout false, xorout 0, check("123456789") = 0x29B1 | no revision or access date | `https://reveng.sourceforge.io/crc-catalogue/16.htm` | **URL appears only in spike/doc files**: `docs/agent/hadi/spikes/uart/c2_frame.h:12-16`; `spikes/uart/c2_ref.py:6-9`; `spikes/uart/README.md:24-26`; `proposals/C2_uart_stream.md:7,23,68`; `drafts/C2_contract_section.md:24` (no source named). **Product code names only the algorithm, no catalogue**: `firmware/src/knn.c:10,89,110`; `firmware/src/knn.h:83`; `firmware/test/classify/oracle.py:170`; `firmware/test/classify/test_classify.c:77`; `firmware/test/e2e/run_e2e.py:196`; `reviews/3.5R.md:44` | CRC-16 over C2 UART frames and the C7 template blob | **FROM MEMORY**: "recalled from memory ... the page itself was not re-read" (`c2_frame.h:15-16`, `c2_ref.py:8`, `README.md:26`, `C2:7`); S2-1R:55 also "recalled from memory by me as well; the page was not fetched". The check value 0x29B1 is asserted by tests (C, Python, e2e), which is real evidence for the parameters, not for the catalogue text |
| C2 | Adafruit NeoPixel Uberguide, pages "Powering NeoPixels" and "Basic connections" | no revision or date | `learn.adafruit.com/adafruit-neopixel-uberguide/powering-neopixels` | `proposals/C6b_display_bulb.md:72-73,187,189,195`. No code cites it, although `firmware/src/display.c:11` and `display.h` use the 20 mA/channel figure (limiter, `DISPLAY_LIMIT_UNITS`) | 60 mA per pixel (20 mA per channel) at full white, 500-1000 uF capacitor, 74AHCT125 level shifter, signal at least 70 % of VDD | **UNTAGGED**; page URL given for one page only. No statement that it was fetched |
| C3 | I2C-bus specification and user manual | **UM10204** (NXP; revision not stated) | none | `reviews/S1-1R.md:35`; `DECISION_SHEET.md:175` | Pull-up range rule Rp <= tr / (0.8473 Cb); suggested 2.2 to 4.7 kOhm at 3.3 V | **NOT READ** ("UM10204, not read here"); the 2.2 to 10 kOhm figure in C6a is STILL UNVERIFIED |
| C4 | FastLED `chipsets.h` header (no version, no URL) | none | none | `reviews/S1-5R.md:5,36,90`; `proposals/C6b_display_bulb.md:121` (via S1-5R) | Practice figures: WS2812 250/625/375 ns vs V5 220/360/580 ns; supports a per-variant timing switch | **READ** by S1-5R (informational only; not a design source). Adafruit NeoPixel library source: "I did not fetch ... from memory" (`S1-5R.md:36`) |
| C5 | NEC infrared transmission protocol, "public NEC description" (no title, document or URL) | none | none | `proposals/C6b_display_bulb.md:102,203-207`; `reviews/S1-5R.md:94,175`; `DECISION_SHEET.md:188`; `proposals/C7_budget.md:197` | 38 kHz carrier, 560 us burst, 9 ms + 4.5 ms leader, bit encodings for the bulb option | **FROM MEMORY / NOT RE-FETCHED**: `S1-5R.md:94` "not re-fetched"; `S1-5R.md:175` "as I know it; I did not re-fetch it"; `DECISION_SHEET.md:188` "NEC numbers not re-fetched" |

Not sources but tools the docs rely on (no citation needed unless the report lists tools): MPLAB X / MDB simulator
(`spikes/sim/README.md:2-6`), XC16 v2.10 compiler, `avr-gcc` + `simavr` (`firmware/README.md:44,63`,
`firmware/test/sim16/run_sim16.sh:10`), numpy, Python 3.

---

## (d) Internal provenance

### d1. Product file promoted or adapted from our own spike or spec

| Product file | Origin | Stated at | Notes |
|---|---|---|---|
| `firmware/src/features.c`, `features.h` | spike `docs/agent/hadi/spikes/features/features.{h,c}` (S1-2); spec `proposals/C3_features.md` | `features.c:6` ("Adapted ... no external code"); `features.h:8` ("Promoted from our own spike"); `BOARD.md:185` | The digit-by-digit `isqrt` (`features.h:47`) has no algorithm citation, see Gaps 6 |
| `tools/features_ref.py` | spike `spikes/features/features_ref.py` | `tools/features_ref.py:5` | |
| `tools/infer_ref.py` | spike `spikes/quant/quant_ref.py` (`rshift_r`, `sat`, `requant_big/split`, `top2`, `classify_ref`, `class_radius`, `l1` promoted); C4/C5 in CONTRACTS | `tools/infer_ref.py:11-14`; `tools/README.md:67-68` | |
| `tools/export_model.py` | spike `spikes/quant/quant_ref.py` (`mshift`, `choose_norm`, `export_quant`, `assert_bounds` promoted; `fallback_needed` ported) | `tools/export_model.py:19-20,242` | |
| `tools/synth_dataset.py` | shapes adapted from spike `spikes/trigger/synth.py` ("not copied code") | `synth_dataset.py:24`; `tools/README.md:136` | Synthetic data, never for accuracy claims |
| `firmware/src/mlp.c` | spec `proposals/C4_model_header.md` section 2; checked against `spikes/quant/quant_ref.py` | `mlp.c:5-9` | |
| `firmware/src/classify.c` | "Mirror of `classify_ref()`" in `spikes/quant/quant_ref.py`; CONTRACTS C5.2 | `classify.c:4-5` | |
| `firmware/src/knn.c`, `knn.h` | CONTRACTS C5.2, C7; main-agent rulings; Lowe idea (B2) | `knn.c:3-9`; `knn.h:4-11` | |
| `firmware/src/lis3dh.c` | CONTRACTS C0, C1.1, C1.3, C1.4, C1.6, C1.10, C6.1; A1, A2 | `lis3dh.c:6-7` | |
| `firmware/src/capture.c` | CONTRACTS C0, C1; trigger proposal `C1b_trigger.md` | `capture.c:3,11` | |
| `firmware/src/display.c`, `icons.c` | CONTRACTS C6.3 | `display.c:3` | `firmware/test/display/icons_golden.py:4-5`: golden table is a regression snapshot copied from `icons.c` (same-source copy, not a spec) |
| Planned, not yet promoted | `spikes/trigger/` -> `firmware/src/trigger.*` (T-trig); `spikes/uart/c2_frame.{h,c}` (T-c2tx) | `BOARD.md:200` | When promoted, carry over the Gaps 1 and 4 notes |

Spikes state "No borrowed code" or equivalent: `spikes/trigger/trigger.c:5`. `spikes/integration/` models
(`fake_lis3dh.c`, `glue.c`) and `firmware/test/lis3dh/fake_lis3dh.*` are our own, based on A1.

### d2. Test derived from which spec section

| Test | Spec it was written from | Stated at |
|---|---|---|
| `firmware/test/capture/test_capture.c`, `oracle.py` | CONTRACTS C1.2, C1.4 to C1.8 + main-agent rulings | `test_capture.c:5`; `oracle.py:5` |
| `firmware/test/classify/test_classify.c`, `oracle.py` | CONTRACTS C5.2, C7; `proposals/C5_classifier_output.md` section 2 | `test_classify.c:5`; `oracle.py:4` |
| `firmware/test/display/test_display.c`, `oracle.py` | CONTRACTS C6.3 + rulings | `test_display.c:5`; `oracle.py:4` |
| `firmware/test/features/test_features.c`, `oracle.py` | CONTRACTS C3 (energy mode isqrt) | `oracle.py:2-4` |
| `firmware/test/lis3dh/test_lis3dh.c` | CONTRACTS C1.1, C1.3, C1.4, C1.10, C6.1 + rulings (register addresses from A1) | `test_lis3dh.c:3-4,32` |
| `firmware/test/mlp/oracle.py`, `gen_model.py` | CONTRACTS C4 section 2 | `oracle.py:2-3`; `gen_model.py:3` |
| `firmware/test/e2e/*` | real firmware modules + real `tools/export_model.py`; CRC in `run_e2e.py:196` | `run_e2e.py:6` |
| `docs/agent/hadi/spikes/uart/test_c2.py` | `proposals/C2_uart_stream.md` section 3 | `spikes/uart/README.md` |
| `firmware/test/sim16/*` | harness only; no spec (host/AVR 16-bit-int check, FRAMEWORK_REVIEW T2) | `sim16.h:3-8` |

---

## Gaps

> **Status after SW-3 (2026-11-15):** gaps 1, 2, 3, 5, 6 and 7 are closed in the code: the comments now carry the
> citation and, where applicable, the "from memory / UNVERIFIED" tag (comments only; objects byte-identical, review PR-3R).
> Gap 4 stays open until the C2 TX pump is promoted; gaps 8-11 are documentation gaps that still need a person.
> File:line references below were taken before SW-3 added comment lines, so some point a few lines early (PR-3R F-03):
> search for the quoted text instead.

1. **Lowe 2004 cited from memory in code.** `firmware/src/knn.h:10-11` and `knn.c:9` cite it; `C5_classifier_output.md:107` says "from memory, UNVERIFIED citation detail"; no volume, pages or DOI; absent from CONTRACTS.md (`reviews/3.5R.md` F8). The code comment does not carry the UNVERIFIED tag. Fix: either read the paper and add volume/pages, or reword to "nearest-neighbour distance ratio (cf. Lowe 2004)" and keep the tag.
2. **CRC-16/IBM-3740 catalogue entry from memory.** Stated in `c2_frame.h:15-16`, `c2_ref.py:8`, `spikes/uart/README.md:26`, `C2_uart_stream.md:7`, `S2-1R.md:55`. The product code (`knn.c:10,89,110`, `knn.h:83`, oracles) names the algorithm with no source and no tag. The check value 0x29B1 is tested, so the parameters are probably right; the catalogue page itself was never opened. Cheap fix: someone opens the URL once and removes the caveat.
3. **LIS3DH reserved-bit comments in `lis3dh.c` written from memory.** Per `open_questions.md:88-90` (WP1-bF2): the CTRL_REG5 bits 5:4 and CTRL_REG6 bits 2 and 0 "unused = 0" comments (`lis3dh.c:129-130,151-152`) were written from memory; the written values 0x40 and 0x80 come from reviewed proposals. The comments carry no tag in the source. Also `lis3dh.c:113` BDU = 0 is tagged UNVERIFIED, and `lis3dh.c:139` (CLICK_THS bit 7 read-back) is a bench question C-7, not a citation. The newest datasheet revision was never read by anyone (`DECISION_SHEET.md:169`, C-15), so all A1 facts are Rev 1 only.
4. **Table-driven (nibble) CRC method uncited.** `spikes/uart/c2_frame.c` is called "textbook ... generated independently" with no source (`reviews/S2-1R.md:35`, F-18; `C2_uart_stream.md:173`). Will transfer to product code when T-c2tx is promoted.
5. **Citation inconsistency between code and docs.** `lis3dh.c:6` and `lis3dh.h:7` give "DocID17530" and "AN3308 Rev 3" but not the AN DocID (18198), the Datasheet revision (Rev 1), or the title. `lis3dh.c:12` cites "table 17" and `lis3dh_hal.h:28` "section 5.1.1" in Rev 1 numbering; no review in the repo checked those two numbers. The ST sheet and the AN are cited in code but appear in no top-level doc (CONTRACTS.md and PLAN.md name no external source at all, only `Source: proposals/...` lines).
6. **Algorithms and generators used without any citation:**
   - xorshift32 (shifts 13, 17, 5) is used in at least 8 test files (`test_capture.c:42`, `test_classify.c:48`, `test_display.c:54`, `test_features.c:51-62`, `mlp/driver.c:32`, `e2e/test_e2e.c:82`, plus the Python mirrors). It is a published generator (Marsaglia) but cited nowhere.
   - Digit-by-digit integer square root in `firmware/src/features.h:47` (and spike). No source; probably textbook, unconfirmed.
   - Insertion sort in `knn.c:8,68` (trivial, listed for completeness).
7. **Vendor figures used in code with the source only in proposals.** `display.c:11` (1 unit = 20 mA / 255, 20 mA per channel) and `display.h` WS2812 GRB wire order depend on C2 (Adafruit Uberguide, **UNTAGGED**) and A10/A11. Neither code comment points to the doc. `docs/agent/CONTRACTS.md:272` states the T1L = 9 or 10 cycle rule with no citation to A10/A11.
8. **Sources never read.** DS39702 (HTTP 403), DS39715 (erase time), UM10204 (I2C pull-up rule), newest LIS3DH datasheet, NEC original, Adafruit NeoPixel library source. C4's use of DS39881E PSV timing was second-hand (`C4_model_header.md:127`). Open claims that depend on these are listed in `DECISION_SHEET.md:167-190` ("Still UNVERIFIED").
9. **Missing identifiers.** B1 (author list), B3 (title and URL), B4 (title, journal), A10/A11 (document ID or revision), A6 (title of DS39715 not given), A8 (cited in the repo only as "DS70157"; title taken from `S1-5R.md:5`), C2 (no date). The B3 title above is the author's inference and should be checked before it goes in the report. A7: the ID DS-50002071M is cited for v2.10 only through reviews; the PDF itself is local and not in the repo.
10. **Source versions are Mac-local paths.** A7, A9, A10 point at `/Applications/...` and `~/Downloads/...`. Nobody else on the team can reproduce those reads. For the report, give the Microchip download page instead of the local path.
11. **No top-level doc lists any of this.** Per AGENTS.md section 7, docs citation exists only in proposals, reviews and `tools/README.md`. Team lead may want to move sections (a) to (c) of this file into a top-level doc (needs the section 5 process, so not done here).
<!-- [END AI-GENERATED] -->
