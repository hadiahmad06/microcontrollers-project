# AI usage log

Course requirement (EE 2361): list every piece of AI-written code. In the source, AI-written
code is wrapped in `[AI-GENERATED: …]` / `[END AI-GENERATED]` markers. This log only
separates agent from human (docs/human/TEAM_PROCESS.md). Git history shows which agent and
which person.

| File | Function | What it does | Date | Author |
|------|----------|--------------|------|--------|
| docs/agent/hadi/spikes/features/features.c | `features_extract` | 150×3 int16 window → 60 int16 features (spike for C3) | 2026-11-14 | agent |
| docs/agent/hadi/spikes/features/features.c | `segment_features` | Mean and energy for one 15-sample segment on one axis | 2026-11-14 | agent |
| docs/agent/hadi/spikes/features/host_runner.c | `main` | Reads windows file, writes features file | 2026-11-14 | agent |
| docs/agent/hadi/spikes/features/div15_check.c | `main` | Exhaustive check that the multiply-shift equals `/15` | 2026-11-14 | agent |
| docs/agent/hadi/spikes/features/features_ref.py | `c_div_trunc`, `shr_nonneg`, `check_int16`, `mean_mulshift`, `extract` | Integer-only Python reference for the features | 2026-11-14 | agent |
| docs/agent/hadi/spikes/features/gen_vectors.py | `edge_cases`, `main` | Test-window generator | 2026-11-14 | agent |
| docs/agent/hadi/spikes/features/compare.py | `main` | Exact C-vs-Python comparison | 2026-11-14 | agent |
| docs/agent/hadi/spikes/quant/quant_ref.py | `rshift_r`, `sat`, `normalize`, `requant_big`, `requant_split`, `dense`, `infer`, `top2`, `confidence`, `mshift`, `choose_norm`, `export_quant`, `assert_bounds`, `l1`, `class_radius`, `classify_ref`, `fallback_needed`, `selftest_requant`, `selftest_mshift`, `selftest_rshift`, `selftest_c5`, `synth`, `demo` | Integer quantization reference and self-tests (spike for C4/C5) | 2026-11-14 | agent |
| docs/agent/hadi/spikes/sim/demo.c | `sim_start`, `sim_end`, `sim_done`, `init_data`, `checksum32`, `dot32`, `main` | Simulator demo program with breakpoint markers | 2026-11-14 | agent |
| docs/agent/hadi/spikes/sim/expected.py | `s16`, module body | Host-side expected values for the simulator demo | 2026-11-14 | agent |
| docs/agent/hadi/spikes/sim/run_sim.sh | whole script | Runs the MPLAB simulator headlessly, parses values and the cycle count | 2026-11-14 | agent |
| docs/agent/hadi/spikes/sim/Makefile | `demo` target | Build, simulate, compare | 2026-11-14 | agent |
| docs/agent/hadi/spikes/features/features.c | `features_isqrt32`, `scale_energy` | Exact integer square root; energy scaling modes (shift / isqrt / isqrt of SS/15) | 2026-11-14 | agent |
| docs/agent/hadi/spikes/features/call_check.c | `call_check` | Compile-only check that a plain int16 buffer can be passed without warnings | 2026-11-14 | agent |
| docs/agent/hadi/spikes/features/features_ref.py | `isqrt32`, `scale_energy` | Integer reference for the energy modes | 2026-11-14 | agent |
| docs/agent/hadi/spikes/features/gen_vectors.py | `spike_sweep`, `boundary_hunt`, `mixed_extremes` | Extra test-vector groups | 2026-11-14 | agent |
| docs/agent/hadi/spikes/features/energy_study.py | `segments_ss`, `options`, `main` | Compares energy scaling options on synthetic motion | 2026-11-14 | agent |
| docs/agent/hadi/spikes/features_qa/oracle.py | `trunc_div`, `mean_alt`, `check_int16`, `segment_features`, `features` | Independent oracle for the features spec | 2026-11-14 | agent |
| docs/agent/hadi/spikes/features_qa/gen.py | `clamp`, `from_axes`, `segment_with_sum`, `window_from_segments`, `g_*`, `sinusoid_window` | Adversarial and realistic test-window generators | 2026-11-14 | agent |
| docs/agent/hadi/spikes/features_qa/run_tests.py | `pack`, `run_c`, `report`, `diff_group`, `sanity`, `exhaustive_mean`, `sin_stats`, `main` | Differential test runner | 2026-11-14 | agent |
| docs/agent/hadi/spikes/features_qa/Makefile | `test`, `xc16`, `clean` | Build and run the QA suite | 2026-11-14 | agent |
| docs/agent/hadi/spikes/sim_qa/cyc.c | `main`, `sim_start`, `sim_end`, `sim_done`, `callee` | Regions of known cycle cost for checking simulator cycle counts | 2026-11-14 | agent |
| docs/agent/hadi/spikes/sim_qa/vals.c, hang.c, order.c | `main`, `sim_*` | Simulator runner edge-case programs (signs, 16-bit bug, arrays, hangs, breakpoint order) | 2026-11-14 | agent |
| docs/agent/hadi/spikes/sim_qa/check_vals.py | `s16` | Host oracle for vals.c | 2026-11-14 | agent |
| docs/agent/hadi/spikes/sim_qa/cyc.sh, run_sim_mktemp.sh | scripts | Cycle-table runner; proposed per-run temp-dir runner | 2026-11-14 | agent |
| docs/agent/hadi/spikes/sim/run_sim.sh, selftest.sh | `sym_addr`, `check`, scripts | Breakpoint-order check, per-run temp dir, simulator self-test | 2026-11-14 | agent |
| docs/agent/hadi/spikes/uart/c2_frame.c | `c2_crc16_update` | Continue a CRC-16/IBM-3740 over a byte range (nibble table) | 2026-11-14 | agent |
| docs/agent/hadi/spikes/uart/c2_frame.c | `c2_crc16` | CRC-16/IBM-3740 of a whole buffer | 2026-11-14 | agent |
| docs/agent/hadi/spikes/uart/c2_frame.c | `c2_encode_window` | Encode one 922 B C2 WINDOW frame into a caller buffer | 2026-11-14 | agent |
| docs/agent/hadi/spikes/uart/c2_frame.c | `c2_encode_hello` | Encode one 18 B C2 HELLO frame into a caller buffer | 2026-11-14 | agent |
| docs/agent/hadi/spikes/uart/c2_frame.c | `c2_put_u16`, `c2_put_u32`, `c2_put_header` | Little-endian store and frame header helpers | 2026-11-14 | agent |
| docs/agent/hadi/spikes/uart/c2_cli.c | `main`, `do_encode`, `rd` | Host test driver for the C2 encoder | 2026-11-14 | agent |
| docs/agent/hadi/spikes/uart/c2_ref.py | `crc16`, `_frame`, `encode_window`, `encode_hello`, `parse_payload`, `Decoder` | Python reference C2 encoder and resyncing stream decoder | 2026-11-14 | agent |
| docs/agent/hadi/spikes/uart/test_c2.py | `check`, `rand_meta`, `rand_samples`, `c_record`, `main` | C2 spike test harness (CRC, C vs Python bytes, resync fuzz) | 2026-11-14 | agent |
| firmware/test/sim16/sim16.c | `sim16_init`, `sim16_exit`, `sim16_putc` | stdout over simulated USART0 and exit-code reporting for 16-bit-int test runs | 2026-11-14 | agent |
| firmware/test/sim16/probe.c | `main`, `mul_uncast` | Self-test proving the sim16 build has a 16-bit int | 2026-11-14 | agent |
| firmware/test/sim16/run_sim16.sh | (script) | Run an AVR test image under simavr, clean its output, map SIM16_EXIT to an exit code | 2026-11-14 | agent |
| Makefile, firmware/test/common.mk | (build rules) | Repo-level `make test` over all suites; shared host/sim16 flags | 2026-11-14 | agent |
| firmware/src/features.c | `features_extract` | 150x3 int16 window → 60 int16 features (C3: truncated mean, isqrt energy) | 2026-11-14 | agent |
| firmware/src/features.c | `segment_features` | Mean and isqrt energy of one 15-sample segment on one axis | 2026-11-14 | agent |
| firmware/src/features.c | `features_isqrt32` | Exact floor(sqrt(n)) for uint32, digit-by-digit | 2026-11-14 | agent |
| firmware/src/features.h | `FEAT_IS_NONNEG` (macro) | C3 non-negative flag: odd feature index = energy | 2026-11-14 | agent |
| tools/features_ref.py | `features_extract` | Integer-only Python reference of C3, bit-exact with features.c | 2026-11-14 | agent |
| tools/features_ref.py | `c_div_trunc` | C99 truncating division | 2026-11-14 | agent |
| tools/features_ref.py | `isqrt32` | Digit-by-digit isqrt (same loop as the C) | 2026-11-14 | agent |
| tools/features_ref.py | `_check_int16` | Assert a value fits int16 (mirrors C intermediates) | 2026-11-14 | agent |
| tools/features_ref.py | `_selftest` | isqrt32 vs math.isqrt self-test | 2026-11-14 | agent |
| firmware/test/features/test_features.c | `rng_seed` | xorshift32 seed (mirrored in oracle.py) | 2026-11-14 | agent |
| firmware/test/features/test_features.c | `rng_next` | xorshift32 step | 2026-11-14 | agent |
| firmware/test/features/test_features.c | `fill_edge` | Build the fixed edge windows | 2026-11-14 | agent |
| firmware/test/features/test_features.c | `fill_random` | Build one pseudo-random window | 2026-11-14 | agent |
| firmware/test/features/test_features.c | `print_line` | Print one window's features (3 lines of 20) | 2026-11-14 | agent |
| firmware/test/features/test_features.c | `isqrt_ok` | Check r*r <= n < (r+1)^2 | 2026-11-14 | agent |
| firmware/test/features/test_features.c | `check_isqrt` | isqrt sweep | 2026-11-14 | agent |
| firmware/test/features/test_features.c | `main` | Features test driver (host + sim16) | 2026-11-14 | agent |
| firmware/test/features/oracle.py | `tdiv` | Independent truncating division | 2026-11-14 | agent |
| firmware/test/features/oracle.py | `expected` | Independent C3 oracle (math.isqrt) | 2026-11-14 | agent |
| firmware/test/features/oracle.py | `Rng`, `Rng.next` | xorshift32 mirror of the C driver | 2026-11-14 | agent |
| firmware/test/features/oracle.py | `edge_window` | Fixed edge windows (mirror of fill_edge) | 2026-11-14 | agent |
| firmware/test/features/oracle.py | `random_window` | Random windows (mirror of fill_random) | 2026-11-14 | agent |
| firmware/test/features/run_tests.py | `report` | Print PASS/FAIL line | 2026-11-14 | agent |
| firmware/test/features/run_tests.py | `parse` | Parse driver output | 2026-11-14 | agent |
| firmware/test/features/run_tests.py | `compare` | Compare driver output with the oracle | 2026-11-14 | agent |
| firmware/test/features/run_tests.py | `checks` | Macro/isqrt checks from driver output | 2026-11-14 | agent |
| firmware/test/features/run_tests.py | `run_driver` | Run host binary or sim16 ELF | 2026-11-14 | agent |
| firmware/test/features/run_tests.py | `test_ref` | Check tools/features_ref.py against the oracle | 2026-11-14 | agent |
| firmware/test/features/run_tests.py | `main` | Features suite entry point | 2026-11-14 | agent |
| firmware/test/features/gen_sstable.py | `find` | Search a 15-sample segment with a given SS | 2026-11-14 | agent |
| firmware/test/features/gen_sstable.py | `main` | Generate ss_table.h / ss_table.py | 2026-11-14 | agent |
| firmware/test/features/ss_table.h, ss_table.py | (generated data) | 72 segments with SS = k²-1, k², k²+1 | 2026-11-14 | agent |
| firmware/src/mlp.c | `mlp_model_info` | Copy model identity fields from gesture_model.h | 2026-11-14 | agent |
| firmware/src/mlp.c | `mlp_normalize` | Stage 0: offset, rounding shift, clamp to int8 x8 | 2026-11-14 | agent |
| firmware/src/mlp.c | `mlp_requant` | Split-multiply requant + ReLU clamp [0,127], no int64 | 2026-11-14 | agent |
| firmware/src/mlp.c | `mlp_layer1` | Dense int8 layer 1 into acc1, requant into h | 2026-11-14 | agent |
| firmware/src/mlp.c | `mlp_layer2` | Dense int8 layer 2 into int32 logits | 2026-11-14 | agent |
| firmware/src/mlp.c | `mlp_top2` | Argmax (lowest index on ties), runner-up, margin | 2026-11-14 | agent |
| firmware/src/mlp.c | `mlp_forward` | All MLP stages; returns top1, fills x8 and logits | 2026-11-14 | agent |
| firmware/test/mlp/oracle.py | `to_s32` | Reinterpret unsigned as signed | 2026-11-14 | agent |
| firmware/test/mlp/oracle.py | `to_s16` | Reinterpret unsigned as signed | 2026-11-14 | agent |
| firmware/test/mlp/oracle.py | `XorShift32.__init__` | xorshift32 PRNG mirrored in C | 2026-11-14 | agent |
| firmware/test/mlp/oracle.py | `XorShift32.next` | xorshift32 PRNG mirrored in C | 2026-11-14 | agent |
| firmware/test/mlp/oracle.py | `rshift_r` | Spec RSHIFT_R, SAT, exact big-int requant | 2026-11-14 | agent |
| firmware/test/mlp/oracle.py | `sat` | Spec RSHIFT_R, SAT, exact big-int requant | 2026-11-14 | agent |
| firmware/test/mlp/oracle.py | `requant` | Spec RSHIFT_R, SAT, exact big-int requant | 2026-11-14 | agent |
| firmware/test/mlp/oracle.py | `normalize` | Stage-by-stage independent MLP oracle | 2026-11-14 | agent |
| firmware/test/mlp/oracle.py | `layer1` | Stage-by-stage independent MLP oracle | 2026-11-14 | agent |
| firmware/test/mlp/oracle.py | `layer2` | Stage-by-stage independent MLP oracle | 2026-11-14 | agent |
| firmware/test/mlp/oracle.py | `top2` | Stage-by-stage independent MLP oracle | 2026-11-14 | agent |
| firmware/test/mlp/oracle.py | `forward` | Stage-by-stage independent MLP oracle | 2026-11-14 | agent |
| firmware/test/mlp/oracle.py | `random_features` | Mirror of the driver's feature generator | 2026-11-14 | agent |
| firmware/test/mlp/oracle.py | `requant_sweep` | Requant sweep cases | 2026-11-14 | agent |
| firmware/test/mlp/gen_model.py | `check_bounds` | Assert C4 exporter bounds | 2026-11-14 | agent |
| firmware/test/mlp/gen_model.py | `rnd_weight` | Random valid model, 5 variants | 2026-11-14 | agent |
| firmware/test/mlp/gen_model.py | `make_model` | Random valid model, 5 variants | 2026-11-14 | agent |
| firmware/test/mlp/gen_model.py | `model_bytes` | Little-endian array bytes for CRC-32 | 2026-11-14 | agent |
| firmware/test/mlp/gen_model.py | `lit32` | Emit gesture_model.h with portable literals | 2026-11-14 | agent |
| firmware/test/mlp/gen_model.py | `lit16` | Emit gesture_model.h with portable literals | 2026-11-14 | agent |
| firmware/test/mlp/gen_model.py | `arr1` | Emit gesture_model.h with portable literals | 2026-11-14 | agent |
| firmware/test/mlp/gen_model.py | `arr2` | Emit gesture_model.h with portable literals | 2026-11-14 | agent |
| firmware/test/mlp/gen_model.py | `write_header` | Emit gesture_model.h with portable literals | 2026-11-14 | agent |
| firmware/test/mlp/gen_model.py | `edge_vectors` | Edge feature vectors as edge_vectors.h | 2026-11-14 | agent |
| firmware/test/mlp/gen_model.py | `write_edge` | Edge feature vectors as edge_vectors.h | 2026-11-14 | agent |
| firmware/test/mlp/gen_model.py | `main` | Generator CLI | 2026-11-14 | agent |
| firmware/test/mlp/run_tests.py | `report` | Build, run and compare MLP suite | 2026-11-14 | agent |
| firmware/test/mlp/run_tests.py | `run` | Build, run and compare MLP suite | 2026-11-14 | agent |
| firmware/test/mlp/run_tests.py | `build` | Build, run and compare MLP suite | 2026-11-14 | agent |
| firmware/test/mlp/run_tests.py | `execute` | Build, run and compare MLP suite | 2026-11-14 | agent |
| firmware/test/mlp/run_tests.py | `parse` | Build, run and compare MLP suite | 2026-11-14 | agent |
| firmware/test/mlp/run_tests.py | `check_output` | Build, run and compare MLP suite | 2026-11-14 | agent |
| firmware/test/mlp/run_tests.py | `coverage` | Build, run and compare MLP suite | 2026-11-14 | agent |
| firmware/test/mlp/run_tests.py | `main` | Build, run and compare MLP suite | 2026-11-14 | agent |
| firmware/test/mlp/driver.c | `rng` | MLP test driver (host + sim16) | 2026-11-14 | agent |
| firmware/test/mlp/driver.c | `gen_feat` | MLP test driver (host + sim16) | 2026-11-14 | agent |
| firmware/test/mlp/driver.c | `print_i8` | MLP test driver (host + sim16) | 2026-11-14 | agent |
| firmware/test/mlp/driver.c | `print_i32` | MLP test driver (host + sim16) | 2026-11-14 | agent |
| firmware/test/mlp/driver.c | `run_vector` | MLP test driver (host + sim16) | 2026-11-14 | agent |
| firmware/test/mlp/driver.c | `requant_sweep` | MLP test driver (host + sim16) | 2026-11-14 | agent |
| firmware/test/mlp/driver.c | `main` | MLP test driver (host + sim16) | 2026-11-14 | agent |
| firmware/test/mlp/standin/mlp.c | `rshift_r` | Test-only stand-in from the spec | 2026-11-14 | agent |
| firmware/test/mlp/standin/mlp.c | `mlp_model_info` | Test-only stand-in from the spec | 2026-11-14 | agent |
| firmware/test/mlp/standin/mlp.c | `mlp_normalize` | Test-only stand-in from the spec | 2026-11-14 | agent |
| firmware/test/mlp/standin/mlp.c | `mlp_requant` | Test-only stand-in from the spec | 2026-11-14 | agent |
| firmware/test/mlp/standin/mlp.c | `mlp_layer1` | Test-only stand-in from the spec | 2026-11-14 | agent |
| firmware/test/mlp/standin/mlp.c | `mlp_layer2` | Test-only stand-in from the spec | 2026-11-14 | agent |
| firmware/test/mlp/standin/mlp.c | `mlp_top2` | Test-only stand-in from the spec | 2026-11-14 | agent |
| firmware/test/mlp/standin/mlp.c | `mlp_forward` | Test-only stand-in from the spec | 2026-11-14 | agent |
| firmware/src/knn.c | `cls_index` | Map a class id to its index 0..NCLS-1; returns NCLS if invalid. | 2026-11-14 | agent |
| firmware/src/knn.c | `recompute_radius` | Recompute R_c of class index c from its stored templates (C5.2 per-class radius). | 2026-11-14 | agent |
| firmware/src/knn.c | `crc16_byte` | CRC-16/IBM-3740 update with one byte (poly 0x1021, MSB first). | 2026-11-14 | agent |
| firmware/src/knn.c | `crc16` | CRC-16/IBM-3740 of len bytes starting at p, init 0xFFFF. | 2026-11-14 | agent |
| firmware/src/knn.c | `knn_reset` | Erase all templates, counts and round-robin indices | 2026-11-14 | agent |
| firmware/src/knn.c | `knn_learn` | Store one x8 template (round-robin overwrite); stored count or GESTURE_LEARN_ERR_ID | 2026-11-14 | agent |
| firmware/src/knn.c | `knn_count` | Templates stored for a learned class | 2026-11-14 | agent |
| firmware/src/knn.c | `knn_total` | Templates stored over all classes | 2026-11-14 | agent |
| firmware/src/knn.c | `knn_radius` | Current per-class radius R_c | 2026-11-14 | agent |
| firmware/src/knn.c | `knn_l1` | L1 distance over 60 int8 values | 2026-11-14 | agent |
| firmware/src/knn.c | `knn_query` | Nearest template, d1, d2, c_k, radius | 2026-11-14 | agent |
| firmware/src/knn.c | `knn_export` | Write the flat template blob (version, counts, data, CRC16) | 2026-11-14 | agent |
| firmware/src/knn.c | `knn_import` | Validate and load a template blob; store unchanged on error | 2026-11-14 | agent |
| firmware/src/classify.c | `classify_mlp_conf` | MLP confidence min(255, margin >> shift) | 2026-11-14 | agent |
| firmware/src/classify.c | `classify_decide` | C5.2 decision: MLP vs k-NN override, reject | 2026-11-14 | agent |
| firmware/test/classify/test_classify.c | `rnd` | xorshift32 PRNG (13, 17, 5); mirrored bit for bit in oracle.py. | 2026-11-14 | agent |
| firmware/test/classify/test_classify.c | `rng_seed` | Seed the PRNG for scenario s: state = seed + (s + 1) * 0x9E3779B9 (0 becomes 1), then 3 draws dropped. | 2026-11-14 | agent |
| firmware/test/classify/test_classify.c | `crc16` | CRC-16/IBM-3740 (poly 0x1021, init 0xFFFF, no reflection, xorout 0), the C7 blob checksum. | 2026-11-14 | agent |
| firmware/test/classify/test_classify.c | `v_base` | Fill a vector with a random "base" pattern: style 0 uniform [-127,127], 1 extremes +-127, 2 small [-20,20]. | 2026-11-14 | agent |
| firmware/test/classify/test_classify.c | `v_noisy` | out = clamp(base + uniform noise in [-amp, amp], -127, 127). No PRNG draws when amp == 0. | 2026-11-14 | agent |
| firmware/test/classify/test_classify.c | `v_dist` | Vector with L1 distance d (<= 7620) from the zero vector: entries of sign*127 filled first, remainder next. | 2026-11-14 | agent |
| firmware/test/classify/test_classify.c | `v_mk` | Vector of `fill` with the first n entries set to val. | 2026-11-14 | agent |
| firmware/test/classify/test_classify.c | `report_state` | Print N (counts), R (radii) and E (export size / crc / self-check / short-cap / zero-cap) lines. | 2026-11-14 | agent |
| firmware/test/classify/test_classify.c | `emit_query` | Print one "Q" line for a knn_query result. | 2026-11-14 | agent |
| firmware/test/classify/test_classify.c | `emit_decide` | Run classify_decide with a conf pointer and with NULL, print one line "<tag> ...". | 2026-11-14 | agent |
| firmware/test/classify/test_classify.c | `T_case` | Directed case: print the Q line for the window and one T line with the decision. | 2026-11-14 | agent |
| firmware/test/classify/test_classify.c | `io_tests` | Error-path and round-trip tests of knn_export / knn_import on the current store. | 2026-11-14 | agent |
| firmware/test/classify/test_classify.c | `scenario` | One pseudo-random scenario: learns (some with bad ids), state report, queries, decisions, I/O tests. | 2026-11-14 | agent |
| firmware/test/classify/test_classify.c | `directed` | Directed cases: C5 §2 table, min_conf sweeps, d2 == 0, radius boundaries and clamps, template growth and | 2026-11-14 | agent |
| firmware/test/classify/test_classify.c | `main` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `Rng` | xorshift32 (13, 17, 5), identical to test_classify.c. | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `v_base`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `v_noisy`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `v_dist`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `v_mk`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `crc16` | CRC-16/IBM-3740: poly 0x1021, init 0xFFFF, no reflection, xorout 0. | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `l1`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `Knn` | Spec model of knn.c. Slots are ordered class-major, then slot (ruling of the main agent). | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `mlp_conf`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `decide` | classify_decide per C5.2. q is a query tuple or None. Returns (id, conf). | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `Replay` | Mirrors the C driver call for call and collects the expected lines. | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `expected` | Return the list of expected output lines (without the final 'DONE'). | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `__init__`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `seed`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `next`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `__init__`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `reset`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `copy_from`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `valid`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `learn`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `count`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `total`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `radius`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `query` | Return None if empty else (kid, d1, d2, has_other, c_k, radius). | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `export`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `__init__`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `p`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `report_state`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `emit_query`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `emit_decide`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `T_case`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `io_tests`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `scenario`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `directed`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/run_tests.py | `compare` | Compare line lists; report up to 5 mismatches with the scenario they occur in. | 2026-11-14 | agent |
| firmware/test/classify/run_tests.py | `literal_checks` | Check the C5 table and a few hand-computed values directly on the program output. | 2026-11-14 | agent |
| firmware/test/classify/run_tests.py | `run` | Run a command; return (exit code, stdout lines) or (None, []) on timeout. | 2026-11-14 | agent |
| firmware/test/classify/run_tests.py | `check` | Run one target and compare it with the oracle. Returns True on PASS. | 2026-11-14 | agent |
| firmware/test/classify/run_tests.py | `main`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| firmware/test/classify/standin/knn.c | `knn_reset` | Clear all templates. @return None. | 2026-11-14 | agent |
| firmware/test/classify/standin/knn.c | `knn_l1` | L1 distance of two x8 vectors. | 2026-11-14 | agent |
| firmware/test/classify/standin/knn.c | `knn_learn` | Store one template (round-robin overwrite when full). | 2026-11-14 | agent |
| firmware/test/classify/standin/knn.c | `knn_count` | @param class_id Class id. @return Template count, 0 for a bad id. | 2026-11-14 | agent |
| firmware/test/classify/standin/knn.c | `knn_total` | @return Total templates stored. | 2026-11-14 | agent |
| firmware/test/classify/standin/knn.c | `knn_radius` | Acceptance radius of a class. | 2026-11-14 | agent |
| firmware/test/classify/standin/knn.c | `knn_query` | Nearest-template query (class-major, slot-major scan; lowest slot wins ties). | 2026-11-14 | agent |
| firmware/test/classify/standin/knn.c | `knn_export` | Serialise the store to a flat blob. | 2026-11-14 | agent |
| firmware/test/classify/standin/knn.c | `knn_import` | Load a blob made by knn_export. | 2026-11-14 | agent |
| firmware/test/classify/standin/knn.c | `crc16` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/classify/standin/classify.c | `classify_mlp_conf` | MLP confidence score: min(255, margin >> conf_shift). | 2026-11-14 | agent |
| firmware/test/classify/standin/classify.c | `classify_decide` | Combine the MLP result with an optional k-NN result (C5.2 steps 1-4). | 2026-11-14 | agent |
| tools/infer_ref.py | `rshift_r` | Round-half-up arithmetic right shift, RSHIFT_R(v, s) = (v + (1 << s >> 1)) >> s. | 2026-11-14 | agent |
| tools/infer_ref.py | `rshift_r64` | Rounding shift on the exact (unbounded) product: (p + 2^(s-1)) >> s. | 2026-11-14 | agent |
| tools/infer_ref.py | `sat` | Clamp v to [lo, hi]. Args: v, lo, hi (ints). Returns: int. | 2026-11-14 | agent |
| tools/infer_ref.py | `requant_split` | int64-free requantisation mirroring the firmware C `gm_requant` (C4 section 2). | 2026-11-14 | agent |
| tools/infer_ref.py | `_c_int_expr` | Evaluate a C integer constant expression made of literals, + - * and parentheses. | 2026-11-14 | agent |
| tools/infer_ref.py | `_strip_comments` | Remove /* */ and // comments. Args: src (str). Returns: str. | 2026-11-14 | agent |
| tools/infer_ref.py | `_flatten` | Row-major flatten of a nested list of ints. Args: x (list). Returns: list[int]. | 2026-11-14 | agent |
| tools/infer_ref.py | `model_hash` | CRC-32 (IEEE) over the little-endian bytes of all arrays in file order (C4.3). | 2026-11-14 | agent |
| tools/infer_ref.py | `parse_header` | Parse the text of a generated gesture_model.h into a dict. | 2026-11-14 | agent |
| tools/infer_ref.py | `_expand_exprs` | Replace parenthesised constant expressions like (-2147483647L - 1L) inside an array body | 2026-11-14 | agent |
| tools/infer_ref.py | `load_header` | Parse a generated gesture_model.h file (macros and arrays). | 2026-11-14 | agent |
| tools/infer_ref.py | `normalize` | C4 stage 0: x8[i] = SAT(RSHIFT_R((int32)x - GM_IN_OFF[i], GM_IN_SH[i]), -127, 127). | 2026-11-14 | agent |
| tools/infer_ref.py | `layer1` | C4 layer 1: acc1[j] = B1[j] + sum_i W1[j][i]*x8[i]; h[j] = SAT(RSHIFT_R64(acc1*M1, SH1), 0, 127). | 2026-11-14 | agent |
| tools/infer_ref.py | `layer2` | C4 layer 2: logit[c] = B2[c] + sum_j W2[c][j]*h[j] (int32, no requant, no clamp). | 2026-11-14 | agent |
| tools/infer_ref.py | `top2_idx` | Argmax (lowest index on ties) and runner-up index (largest among c != top1, lowest index on ties). | 2026-11-14 | agent |
| tools/infer_ref.py | `top2` | C4 argmax and margin. | 2026-11-14 | agent |
| tools/infer_ref.py | `mlp_conf` | C5 MLP confidence: min(255, margin >> GM_CONF_SHIFT). | 2026-11-14 | agent |
| tools/infer_ref.py | `forward` | Run every stage and keep every intermediate. | 2026-11-14 | agent |
| tools/infer_ref.py | `knn_l1` | L1 distance of two int8 vectors (max 60*254 = 15240). Args: a, b (equal-length lists). Returns: int. | 2026-11-14 | agent |
| tools/infer_ref.py | `class_radius` | C5 per-class acceptance radius: clamp(2 * lower_median(pairwise L1), rmin, rmax). | 2026-11-14 | agent |
| tools/infer_ref.py | `knn_query` | C5 k-NN gate inputs. | 2026-11-14 | agent |
| tools/infer_ref.py | `classify_decide` | C5 normative decision (steps 1, 2, 4). | 2026-11-14 | agent |
| tools/infer_ref.py | `_tiny_model` | Hand-built 2-feature, 2-hidden, 3-class model for stage checks. Returns: model dict. | 2026-11-14 | agent |
| tools/infer_ref.py | `selftest` | Run the C5 section 2 vector table, stage checks and requant checks. Raises AssertionError on | 2026-11-14 | agent |
| tools/infer_ref.py | `one`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| tools/infer_ref.py | `lg`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| tools/infer_ref.py | `run`  | test helper (no docstring: review 3.5R) | 2026-11-14 | agent |
| tools/export_model.py | `BoundError` | Raised when a C4 exporter bound is violated; the message names the bound. | 2026-11-14 | agent |
| tools/export_model.py | `_need` | Raise BoundError naming `bound` unless cond. Args: cond (bool); bound (str); detail (str). | 2026-11-14 | agent |
| tools/export_model.py | `mshift` | Real requant scale -> (M, SH) with 2^14 <= M < 2^15, 16 <= SH <= 31, M * 2^-SH ~= scale. | 2026-11-14 | agent |
| tools/export_model.py | `choose_norm` | Per-feature (off, sh) from calibration features (C4 D1b). | 2026-11-14 | agent |
| tools/export_model.py | `_as_int_features` | Validate a calibration/validation feature array. Args: a (ndarray); name (str). | 2026-11-14 | agent |
| tools/export_model.py | `quantize` | C4 exporter recipe steps 2-6 on a float net defined on the training input x8 / K. | 2026-11-14 | agent |
| tools/export_model.py | `check_bounds` | C4 step 6 bounds on a quantized model dict. Args: q (dict with GM_* lists). Returns: None. | 2026-11-14 | agent |
| tools/export_model.py | `model_hash` | CRC-32 IEEE over the little-endian bytes of all arrays in file order (C4.3). | 2026-11-14 | agent |
| tools/export_model.py | `choose_conf_shift` | C5 rule: smallest shift s with P95(margins of correct validation windows) >> s <= 255. | 2026-11-14 | agent |
| tools/export_model.py | `_c32` | int32 C literal portable to 16-bit int. Args: v (int). Returns: str. | 2026-11-14 | agent |
| tools/export_model.py | `_c16` | int16 C literal (INT16_MIN-safe). Args: v (int). Returns: str. | 2026-11-14 | agent |
| tools/export_model.py | `_fmt_1d` | Wrap a 1-D initializer. Args: vals (ints), conv (int -> str), indent, width. Returns: str. | 2026-11-14 | agent |
| tools/export_model.py | `_fmt_2d` | Initializer with one braced row per line. Args: rows (list of lists), conv. Returns: str. | 2026-11-14 | agent |
| tools/export_model.py | `render_header` | Render gesture_model.h text per the C4 header layout. | 2026-11-14 | agent |
| tools/export_model.py | `cmd_norm` | `norm` subcommand: write norm.json from calibration features. Args: args (Namespace). | 2026-11-14 | agent |
| tools/export_model.py | `cmd_header` | `header` subcommand: quantize, check bounds, write gesture_model.h. Args: args (Namespace). | 2026-11-14 | agent |
| tools/export_model.py | `main` | CLI entry. Args: argv (list or None). Returns: process exit code (0 ok, 2 bad input, 3 bound violation). | 2026-11-14 | agent |
| firmware/test/e2e/test_e2e.c | `rng_next` | xorshift32 step (13, 17, 5). | 2026-11-14 | agent |
| firmware/test/e2e/test_e2e.c | `rnd` | Random integer in [0, n). | 2026-11-14 | agent |
| firmware/test/e2e/test_e2e.c | `clamp12` | Clamp to the C1 sample range [-2048, 2047]. | 2026-11-14 | agent |
| firmware/test/e2e/test_e2e.c | `rest_orientation` | Pick a rest orientation: gravity of about 512 counts split over the three axes. | 2026-11-14 | agent |
| firmware/test/e2e/test_e2e.c | `gen_base` | Generate one window of a randomly chosen base kind (rest x3, burst x2, extreme, uniform). | 2026-11-14 | agent |
| firmware/test/e2e/test_e2e.c | `print_mlp_stage` | Print the W/F/X/G lines of a window (everything up to the MLP). | 2026-11-14 | agent |
| firmware/test/e2e/test_e2e.c | `round_trip` | Export, reset, import and verify the template store survives (CRC trailer, counts, radii). | 2026-11-14 | agent |
| firmware/test/e2e/test_e2e.c | `run_all` | Run the whole plan: 7 scenarios, each learning its templates then answering nper queries. | 2026-11-14 | agent |
| firmware/test/e2e/test_e2e.c | `main` | Entry point on sim16: runs the plan with the compile-time seed and count. | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `report` | Print one PASS/FAIL line and remember failures. Args: ok: bool; name: check name; | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `Rng` | xorshift32 (13, 17, 5), identical to rng_next() in test_e2e.c. | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `clamp12` | Clamp to [-2048, 2047]. Args: v: int. Returns: int. | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `rest_orientation` | Mirror of rest_orientation() in C. Args: r: Rng. Returns: list of 3 per-axis offsets. | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `gen_base` | Mirror of gen_base() in C (rest x3, burst x2, extreme, uniform). Args: r: Rng (advanced). | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `expected` | Run the whole plan with the Python tools. Args: m: model dict (infer_ref.load_header); | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `s16` | Args: h: hex string of 16 bits. Returns: signed int. | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `s8` | Args: h: hex string of 8 bits. Returns: signed int. | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `s32` | Args: h: hex string of 32 bits. Returns: signed int. | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `parse_c` | Parse the output of test_e2e.c. Args: text: program output. Returns: (dict idx -> record, | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `knn_tuple` | Args: k: dict from infer_ref.knn_query or None. Returns: tuple in the C print order | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `compare` | Compare one C run with the expected records and report every stage. | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `run` | Run a command. Args: cmd: argv list; timeout: seconds. Returns: CompletedProcess with text. | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `export_model` | Create model m with the real exporter. Args: m: model number; mdir: output dir; tools: tools dir. | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `build` | Compile test_e2e.c with the module sources for host or sim16. | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `main` | Entry point. Returns: process exit code (0 all pass, 1 any failure). | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `__init__` | Args: seed: int; 0 is replaced by 1 (as in C). Returns: None. | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `next` | Advance one step. Returns: the new state (uint32). | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `rnd` | Args: n: int > 0. Returns: next() % n (as rnd() in C). | 2026-11-14 | agent |
| firmware/test/e2e/run_e2e.py | `stages` | Features and MLP stages of one window. Args: win. Returns: (feat, forward dict). | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger.c | `trigger_statistic` | Compute the statistic of one sample and update baseline and previous sample. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger.c | `abs32` | Absolute value of an int32 (helper for the L1 statistic) | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger.c | `trigger_mg_to_counts` | Convert threshold_mg to counts: (mg + 1) >> 1, saturating | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger.c | `trigger_resync` | Re-seed the baseline and restart the warm-up after a stream gap | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger.c | `trigger_set_threshold_mg` | Set the trigger threshold in mg (0 disables) | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger.c | `trigger_init` | Initialise the trigger state with a config (or defaults) | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger.c | `trigger_feed` | Feed one sample; returns true on the sample that completes the trigger | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger.c | `trigger_release` | Start the hysteresis re-arm after the capture buffer is released | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger_cli.c | `fnv_word` | FNV-1a hash step for the per-sample state hash | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger_cli.c | `main` | Host CLI: run the trigger on a sample stream, print decisions and state hash | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger_ref.py | `mg_to_counts` | Convert threshold_mg to counts: (mg + 1) >> 1, clamped to 12285; 0 stays 0. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger_ref.py | `Trigger` | Mirror of trigger_t. Fields have the same names and meaning as in trigger.h. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger_ref.py | `run` | Run the trigger over a whole stream like trigger_cli.c does. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger_ref.py | `__init__` | Initialise like trigger_init(). | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger_ref.py | `resync` | Restart after a gap (trigger_resync): re-seed from the next sample, warm up again. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger_ref.py | `set_threshold_mg` | Set the threshold (trigger_set_threshold_mg); 0 disables triggering. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger_ref.py | `_statistic` | Compute the statistic and update baseline/previous sample (trigger_statistic). | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger_ref.py | `feed` | Feed one drained sample (trigger_feed). | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger_ref.py | `release` | Buffer released or window dropped (trigger_release): LOCKED -> REARM. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/trigger_ref.py | `hash_words` | State words hashed after every sample (same order as trigger_cli.c). | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/synth.py | `_clip` | Round to int and clip to the 12-bit range [-2048, 2047]. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/synth.py | `_unit` | Random unit vector (uniform on the sphere). | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/synth.py | `_rot` | Rotate vector v about unit axis by ang radians (Rodrigues). | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/synth.py | `_smooth` | Smoothstep 0..1. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/synth.py | `make_stream` | Generate one synthetic stream. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/evaluate.py | `cfg_tuple` | Config dict to the tuple order of the CLI header (stat shift debounce quiet warm). | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/evaluate.py | `run_c` | Run many streams through the C harness. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/evaluate.py | `compare` | Check C and Python agree on trigger indices and per-sample internal state. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/evaluate.py | `pct` | Percentage string. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/evaluate.py | `table` | Print the rate table (computed with the C code) for the rules in RULES. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/evaluate.py | `per_gesture` | Print per-gesture detection rate and latency for one rule. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/evaluate.py | `margins` | Print the largest statistic seen on non-event streams versus the weakest gesture peak. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/evaluate.py | `selfcheck` | Assert the rule properties claimed in the proposal (Python mirror, equal to C). | 2026-11-14 | agent |
| tools/export_model.py | `feature_defs` | Read NONNEG and FEATURES_VERSION from features_ref; check length 60 | 2026-11-14 | agent |
| tools/export_model.py | `check_norm` | Validate norm.json offsets/shifts (length, type, C4 bounds) | 2026-11-14 | agent |
| tools/export_model.py | `choose_default_reject` | C5.2 GM_DEFAULT_REJECT rule from validation data | 2026-11-14 | agent |
| tools/export_model.py | `fallback_needed` | C4.3 int16-input fallback criterion (agreement / Wilson bound) | 2026-11-14 | agent |
| tools/infer_ref.py | `_shape_of` | Full-shape check that rejects ragged arrays | 2026-11-14 | agent |
| tools/infer_ref.py | `check_model_bounds` | Reject parsed headers that violate C4 bounds | 2026-11-14 | agent |
| tools/infer_ref.py | `_selftest_header_text` | Self-test helper: render a tiny header | 2026-11-14 | agent |
| tools/infer_ref.py | `_selftest_header` | Self-test of parse_header, hash and bound checks | 2026-11-14 | agent |
| tools/infer_ref.py | `_selftest_integer_only` | AST scan proving the inference path has no float or `/` | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/evaluate.py | `rearm` | Re-arm failure rate vs threshold on tremor | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/evaluate.py | `fresh` | Tilt false triggers and margins on fresh seeds | 2026-11-14 | agent |
| docs/agent/hadi/spikes/trigger/evaluate.py | `header_defaults` | Parse TRIG_DEFAULT_* from trigger.h for the defaults check | 2026-11-14 | agent |
| firmware/src/display.c | `cap_channel` | Applies the compile-time cap to one raw channel value. @return 0..DISPLAY_CAP. | 2026-11-14 | agent |
| firmware/src/display.c | `display_clear` | Zero the 192 B framebuffer | 2026-11-14 | agent |
| firmware/src/display.c | `display_set` | Store raw RGB for one pixel (out of range ignored) | 2026-11-14 | agent |
| firmware/src/display.c | `display_get` | Read raw RGB of one pixel (out of range: unchanged) | 2026-11-14 | agent |
| firmware/src/display.c | `display_draw_bitmap` | Clear, then set lit bits of an 8x8 bitmap to one colour | 2026-11-14 | agent |
| firmware/src/display.c | `display_units` | Sum of capped channel values (current estimate units) | 2026-11-14 | agent |
| firmware/src/display.c | `display_render` | Capped + limited GRB wire bytes; returns estimated mA | 2026-11-14 | agent |
| firmware/src/icons.c | `icon_index` | Maps an id to a table index; unsupported ids map to UNKNOWN. | 2026-11-14 | agent |
| firmware/src/icons.c | `icon_bitmap` | 8-byte bitmap for a class id (UNKNOWN fallback) | 2026-11-14 | agent |
| firmware/src/icons.c | `icon_color` | RGB colour for a class id | 2026-11-14 | agent |
| firmware/src/icons.c | `icon_show` | Draw the icon for a class id | 2026-11-14 | agent |
| firmware/test/display/test_display.c | `rnd` | xorshift32 PRNG (13, 17, 5); mirrored bit for bit in oracle.py. | 2026-11-14 | agent |
| firmware/test/display/test_display.c | `cap_of` | Spec cap formula c_cap = (c * cap + 127) / 255. | 2026-11-14 | agent |
| firmware/test/display/test_display.c | `load` | Write every channel of the framebuffer from a 192-byte R,G,B row-major array via display_set. | 2026-11-14 | agent |
| firmware/test/display/test_display.c | `noise` | Fill the whole framebuffer with a constant noise colour (to prove later calls overwrite/clear). | 2026-11-14 | agent |
| firmware/test/display/test_display.c | `emit` | Print one frame record: render + units + guard check + display_get check against expect. | 2026-11-14 | agent |
| firmware/test/display/test_display.c | `frame_target` | Build a frame whose capped sum is exactly `target` (as far as 192 channels allow): channels at | 2026-11-14 | agent |
| firmware/test/display/test_display.c | `build_frame` | Build directed frame k (names in FRAME_NAME); mirrored in oracle.py. | 2026-11-14 | agent |
| firmware/test/display/test_display.c | `bitmap_case` | Directed bitmap cases: noise first (draw_bitmap must clear), draw, emit. | 2026-11-14 | agent |
| firmware/test/display/test_display.c | `scenario_frame` | Pseudo-random framebuffer for scenario i: mode i%4 = uniform / sparse 255 / small / mostly bright. | 2026-11-14 | agent |
| firmware/test/display/test_display.c | `icon_section` | Icon section: for each id print the bitmap/colour and the rendered icon_show result. | 2026-11-14 | agent |
| firmware/test/display/test_display.c | `main` | Program entry: prints CFG, directed cases, scenarios, the icon section and END. | 2026-11-14 | agent |
| firmware/test/display/oracle.py | `Rng` | xorshift32 (13, 17, 5), identical to rnd() in test_display.c. | 2026-11-14 | agent |
| firmware/test/display/oracle.py | `cap_of` | Spec cap formula. | 2026-11-14 | agent |
| firmware/test/display/oracle.py | `limit_of` | Spec limiter threshold in units. | 2026-11-14 | agent |
| firmware/test/display/oracle.py | `render` | Reference of display_render() and display_units(). | 2026-11-14 | agent |
| firmware/test/display/oracle.py | `frame_target` | Frame whose capped sum is `target`: 255s first, then the smallest input for the remainder. | 2026-11-14 | agent |
| firmware/test/display/oracle.py | `build_frame` | Directed frame k (same order as FRAME_NAMES / build_frame() in the driver). | 2026-11-14 | agent |
| firmware/test/display/oracle.py | `bitmap_frame` | Framebuffer after display_draw_bitmap (byte 0 = top row, bit 7 = leftmost column). | 2026-11-14 | agent |
| firmware/test/display/oracle.py | `scenario_frame` | Pseudo-random framebuffer of scenario i (mode i%4), consuming 192 draws. | 2026-11-14 | agent |
| firmware/test/display/oracle.py | `case_lines` | The 4 text lines the driver prints for one frame (guard and get checks expected to be 1). | 2026-11-14 | agent |
| firmware/test/display/oracle.py | `expected` | Every line the driver prints before the ICONS marker. | 2026-11-14 | agent |
| firmware/test/display/oracle.py | `__init__` | Seed the generator; 0 is mapped to 1 like the driver. | 2026-11-14 | agent |
| firmware/test/display/oracle.py | `next` | Advance and return the next 32-bit value. | 2026-11-14 | agent |
| firmware/test/display/run_tests.py | `run` | Run a command and return its non-empty output lines. | 2026-11-14 | agent |
| firmware/test/display/run_tests.py | `bitmap_ascii` | Render an 8-byte bitmap as 8 strings of '#' and '.'. | 2026-11-14 | agent |
| firmware/test/display/run_tests.py | `check_frames` | Compare the frame section of the output (up to the ICONS marker) with the oracle. | 2026-11-14 | agent |
| firmware/test/display/run_tests.py | `parse_icons` | Parse the ICONS section. | 2026-11-14 | agent |
| firmware/test/display/run_tests.py | `lit` | Number of lit pixels of a bitmap. | 2026-11-14 | agent |
| firmware/test/display/run_tests.py | `check_icons` | Check the icon properties (not exact shapes) and that icon_show matches the spec render. | 2026-11-14 | agent |
| firmware/test/display/run_tests.py | `print_art` | Print every icon as ASCII art into the log. | 2026-11-14 | agent |
| firmware/test/display/run_tests.py | `check` | Run one target and verify frames + icons. Returns True on PASS. | 2026-11-14 | agent |
| firmware/test/display/run_tests.py | `main` | Parse arguments and run all configurations on host and sim16. | 2026-11-14 | agent |
| firmware/test/display/standin/display.c | `display_clear` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/display/standin/display.c | `display_set` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/display/standin/display.c | `display_get` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/display/standin/display.c | `display_draw_bitmap` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/display/standin/display.c | `cap_of` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/display/standin/display.c | `display_units` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/display/standin/display.c | `display_render` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/display/standin/icons.c | `icon_bitmap` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/display/standin/icons.c | `icon_color` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/display/standin/icons.c | `icon_show` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/classify/test_classify.c | `blob_case` | Import a blob (optionally CRC-repaired), re-export, print result | 2026-11-14 | agent |
| firmware/test/classify/test_classify.c | `meta_tests` | 32 per-class metadata import cases (-2/-3 paths) | 2026-11-14 | agent |
| firmware/test/classify/oracle.py | `Replay.meta_tests` | Expected lines for the metadata import cases | 2026-11-14 | agent |
| firmware/src/capture.c | `ring_push` | Push one sample into the ring, overwriting the oldest entry when full. | 2026-11-14 | agent |
| firmware/src/capture.c | `window_start` | Copy the whole (full) ring, oldest first and trigger sample last, to the buffer start; open the window. | 2026-11-14 | agent |
| firmware/src/capture.c | `capture_init` | Reset to IDLE, empty ring, zero stats | 2026-11-14 | agent |
| firmware/src/capture.c | `capture_arm` | IDLE to ARMED | 2026-11-14 | agent |
| firmware/src/capture.c | `capture_disarm` | ARMED/CAPTURING to IDLE; true iff an open window was dropped | 2026-11-14 | agent |
| firmware/src/capture.c | `capture_push` | One sample: ring push, trigger test, window append; true iff a window opened | 2026-11-14 | agent |
| firmware/src/capture.c | `capture_overrun` | Count overrun, empty ring, drop an open window; true iff one was dropped | 2026-11-14 | agent |
| firmware/src/capture.c | `capture_release` | READY to ARMED | 2026-11-14 | agent |
| firmware/src/capture.c | `capture_state` | Current state | 2026-11-14 | agent |
| firmware/src/capture.c | `capture_ring_count` | Ring fill 0..16 | 2026-11-14 | agent |
| firmware/src/capture.c | `capture_stats` | Copy the counters out | 2026-11-14 | agent |
| firmware/test/capture/test_capture.c | `rnd` | xorshift32 PRNG (13, 17, 5); mirrored bit for bit in oracle.py (class Rng). | 2026-11-14 | agent |
| firmware/test/capture/test_capture.c | `make_sample` | Build the sample for stream index n; x and y carry the index, z mixes it. Mirrors oracle.sample. | 2026-11-14 | agent |
| firmware/test/capture/test_capture.c | `report` | Print the observable state after an event, plus the locked buffer while READY. | 2026-11-14 | agent |
| firmware/test/capture/test_capture.c | `ev` | Execute one event on the API and report it. | 2026-11-14 | agent |
| firmware/test/capture/test_capture.c | `begin` | Start a scenario: print its header and reset the per-scenario bookkeeping. | 2026-11-14 | agent |
| firmware/test/capture/test_capture.c | `run_script` | Run one directed script (grammar in oracle.py): op letter plus optional decimal repeat count. | 2026-11-14 | agent |
| firmware/test/capture/test_capture.c | `run_random` | Run one random episode: init, then 150..400 random events, optionally ending in a disarm. | 2026-11-14 | agent |
| firmware/test/capture/test_capture.c | `main` | Entry point: directed scripts, then NEP random episodes. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `ScriptError` | A script asks for a behaviour the spec leaves open. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `sample` | Return the 3-axis sample for stream index n (unique per n below 2**24, axes differ). | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `_build_directed` | Build the list of (name, script, dump) directed scenarios from the ticket's mandatory list. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `parse` | Split a script into (op, count) pairs. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `Rng` | xorshift32 (13, 17, 5), identical to test_capture.c. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `Model` | The capture state machine as written in the spec and the main-agent rulings. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `_checksum` | Order-sensitive 32-bit checksum of all 450 buffer values (mirror of the C driver). | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `_tri` | Format up to three samples as 'x,y,z x,y,z x,y,z'. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `Replay` | Mirror of the event executor and reporter of test_capture.c; collects the output lines. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `expected` | Expected program output for `seed` and `nep` random episodes (directed scripts first). | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `emit_header` | Print build/scripts.h: the directed scripts as C data (single source of truth). | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `add` | Append one directed scenario. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `__init__` | Seed the generator exactly like the C driver. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `next` | Return the next 32-bit value. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `__init__` | Start in the post-init state. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `init` | capture_init: IDLE, ring empty, no window, statistics zero (assumption, see report). | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `ring_count` | Ring fill count, or None when unknown (see module docstring). | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `push` | capture_push: ring push, trigger test (ARMED only), window append, strictly in order. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `overrun` | capture_overrun: count it, empty the ring, drop an open window (CAPTURING -> ARMED). | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `release` | capture_release: READY -> ARMED returning True, anything else False with no change. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `arm` | capture_arm: IDLE -> ARMED only. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `disarm` | capture_disarm: any state except READY -> IDLE, an open window is dropped, no count. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `__init__` | Create an empty replay. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `begin` | Start a scenario: print its header and reset the per-scenario state. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `ev` | Execute one event on the model and append its report lines. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `script` | Run one directed script. | 2026-11-14 | agent |
| firmware/test/capture/oracle.py | `episode` | Run random episode k, mirroring run_random() in test_capture.c exactly. | 2026-11-14 | agent |
| firmware/test/capture/run_tests.py | `same` | True when line `got` equals `exp`, treating a '*' field of `exp` as a wildcard. | 2026-11-14 | agent |
| firmware/test/capture/run_tests.py | `compare` | Compare line lists; record up to 5 mismatches with the scenario they occur in. | 2026-11-14 | agent |
| firmware/test/capture/run_tests.py | `run` | Run a command; return (exit code, stdout lines, stderr) or (None, [], '') on timeout. | 2026-11-14 | agent |
| firmware/test/capture/run_tests.py | `check` | Run one target and compare it with the oracle. Returns True on PASS. | 2026-11-14 | agent |
| firmware/test/capture/run_tests.py | `main` | Parse arguments, run host and sim16 targets, print the final verdict. | 2026-11-14 | agent |
| firmware/test/capture/standin/capture.c | `start_window` | Start a window: copy the ring (oldest first), which already holds the trigger sample last. | 2026-11-14 | agent |
| firmware/test/capture/standin/capture.c | `capture_init` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/capture/standin/capture.c | `capture_arm` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/capture/standin/capture.c | `capture_disarm` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/capture/standin/capture.c | `capture_push` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/capture/standin/capture.c | `capture_overrun` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/capture/standin/capture.c | `capture_release` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/capture/standin/capture.c | `capture_state` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/capture/standin/capture.c | `capture_ring_count` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/capture/standin/capture.c | `capture_stats` | test stand-in (doc in its header) | 2026-11-14 | agent |
| tools/train.py | `TrainError` | Unusable input or an exporter refusal. Carries a message printed once by main(). | 2026-11-14 | agent |
| tools/train.py | `load_dataset` | Load and validate a dataset .npz. | 2026-11-14 | agent |
| tools/train.py | `compute_features` | Compute the 60 C3 features of every window with features_ref, with an on-disk cache. | 2026-11-14 | agent |
| tools/train.py | `split_indices` | Deterministic train/validation split. | 2026-11-14 | agent |
| tools/train.py | `init_net` | He-initialised 60-hidden-9 net. Args: hidden (int); rng (numpy Generator). | 2026-11-14 | agent |
| tools/train.py | `float_logits` | Float forward pass. Args: net (dict W1,b1,W2,b2); X (float [n,60], i.e. x8 / K). | 2026-11-14 | agent |
| tools/train.py | `train_epoch` | One epoch of minibatch Adam on softmax cross-entropy (in place). | 2026-11-14 | agent |
| tools/train.py | `run_exporter` | Run tools/export_model.py as a subprocess. | 2026-11-14 | agent |
| tools/train.py | `integer_eval` | Score a parsed header model on raw features with infer_ref.forward (the integer path). | 2026-11-14 | agent |
| tools/train.py | `export_candidate` | Write net.npz, export a header with validation data, and score it on the integer path. | 2026-11-14 | agent |
| tools/train.py | `_confusion` | 9x9 confusion matrix, rows = true, columns = predicted. Args: two int arrays. Returns: list of lists. | 2026-11-14 | agent |
| tools/train.py | `_write_report_md` | Write the human-readable report. Args: path (str); rep (dict as written to report.json). | 2026-11-14 | agent |
| tools/train.py | `run_training` | Run the whole pipeline and write the output files. | 2026-11-14 | agent |
| tools/train.py | `_selftest` | Train on a tiny synthetic dataset in a temp dir and check the outputs. | 2026-11-14 | agent |
| tools/train.py | `main` | CLI entry. Args: argv (list of str or None). Returns: int exit code (0 ok, 2 bad input, 3 exporter refusal). | 2026-11-14 | agent |
| tools/train.py | `say` |  | 2026-11-14 | agent |
| tools/synth_dataset.py | `_unit` | Random unit vector, uniform on the sphere. Args: rng (numpy Generator). Returns: ndarray[3]. | 2026-11-14 | agent |
| tools/synth_dataset.py | `_smooth` | Smoothstep clamped to 0..1. Args: u (ndarray). Returns: ndarray, same shape. | 2026-11-14 | agent |
| tools/synth_dataset.py | `_rot` | Rodrigues rotation of one vector by an angle per time step. | 2026-11-14 | agent |
| tools/synth_dataset.py | `make_window` | Generate one synthetic window. | 2026-11-14 | agent |
| tools/synth_dataset.py | `make_dataset` | Build a whole synthetic dataset. | 2026-11-14 | agent |
| tools/synth_dataset.py | `main` | CLI entry. Args: argv (list of str or None for sys.argv). Returns: int exit code (0 ok). | 2026-11-14 | agent |
| firmware/src/lis3dh.c | `write_verify` | Write a config register and read it back (main-agent ruling: every config write is verified). | 2026-11-14 | agent |
| firmware/src/lis3dh.c | `lis3dh_init` | Probe 0x18/0x19 for WHO_AM_I 0x33; write and read back the config sequence | 2026-11-14 | agent |
| firmware/src/lis3dh.c | `lis3dh_address` | 7-bit address after a successful init, else 0 | 2026-11-14 | agent |
| firmware/src/lis3dh.c | `lis3dh_unpack` | C1.1 byte assembly, >>4, axis remap (clamps a flipped -2048) | 2026-11-14 | agent |
| firmware/src/lis3dh.c | `lis3dh_drain` | C1.4 FIFO drain loop, bursts <= 16, bounded per call | 2026-11-14 | agent |
| firmware/src/lis3dh.c | `lis3dh_read_click` | Read CLICK_SRC; 1 on IA+DCLICK | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `push_one` | Push one sample (raw words) into the FIFO; discard the oldest when full (Stream mode). | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `pop_one` | Pop the oldest sample into the output-register latch (no-op when empty: old data stays). | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fifo_src_value` | FIFO_SRC_REG: b7 WTM (unread > FTH), b6 OVRN (32 unread), b5 EMPTY, b4:0 FSS. | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `log_add` | Append a log entry (counted but dropped when the log is full). | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `should_nack` | Common NACK decision: wrong address, n-th transaction, n-th FIFO_SRC read, n-th burst. | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_reset` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_set_who` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_set_fss32` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_set_click_src` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_set_arrivals` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_next_seq` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_fifo_level` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_lost` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_reg` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_log_count` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_log_get` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_nack_txn` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_nack_fifo_src` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_nack_burst` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_corrupt_readback` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_clear_log` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_fifo_active` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_sample_word` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `fake_push_next` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `lis3dh_hal_write` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/fake_lis3dh.c | `lis3dh_hal_read` | fake sensor / test helper (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `check` | Record one check result; prints the first few failures of a group. | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `group_begin` | Start a named test group. | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `group_end` | Finish the current group and print its PASS / FAIL line. | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `ref_value` | Reference sample value: the 12-bit signed number held left-justified in a 16-bit register word. | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `ref_remap` | Reference axis remap: out[i] = sign[i] * in[src[i]]. | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `make_raw` | Lay three words out as one burst group (X_L X_H Y_L Y_H Z_L Z_H). | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `setup` | Reset the fake with a sensor at addr and run lis3dh_init with the given axes. | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `t_init_ok` | Init with the sensor at addr: probe order, exact register write sequence, read-back of every | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `t_init_faults` | Init error paths: no sensor, wrong WHO_AM_I, NACK at every transaction after the probe, | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `unpack_word` | Unpack one word on every axis position and compare with the reference value. | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `t_unpack_table` | Byte assembly and arithmetic shift (C1.1): literal table, every word (host) or a stride (sim16). | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `t_unpack_axes` | Axis remap at unpack time (C1.3): identity, a swap with a sign flip, a 3-cycle with flips, | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `rec_cb` | Sample callback: records every delivered sample in call order. | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `m_push` | Push k samples into the model (Stream mode: a full FIFO discards the oldest). | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `m_fss` | FSS as the fake reports it in FAKE_FSS32_SATURATE mode: min(unread, 31). | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `model_drain` | Run the C1.4 drain schedule on the model (see the file header for the two readings). | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `run_drain` | One drain scenario: init, preload level samples, add k samples after every burst, call | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `t_drain_levels` | Drain with 0, 1, 15, 16, 17, 31, 32 unread and overflowed FIFOs, no arrivals; plus literal | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `t_drain_arrivals` | Samples arriving between bursts, the 4-burst bound and the `more` flag, overrun from the | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `t_drain_bus` | Bus errors at every point of a drain: the call returns LIS3DH_ERR_BUS and does not hang. | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `info_runs` | Informational runs (never fail the suite): FSS reported as 0 at 32 unread, burst sub-address | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `t_click` | lis3dh_read_click: one CLICK_SRC read, clear-on-read seen through the driver, bus error. | 2026-11-14 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `main` | Run every group; exit 0 only if none failed. | 2026-11-14 | agent |
| firmware/test/lis3dh/standin/lis3dh.c | `cfg` | Write a register and read it back; any HAL error or mismatch is LIS3DH_ERR_BUS. | 2026-11-14 | agent |
| firmware/test/lis3dh/standin/lis3dh.c | `probe` | Probe one address: 1 = WHO_AM_I ok, 0 = no answer or wrong value. | 2026-11-14 | agent |
| firmware/test/lis3dh/standin/lis3dh.c | `lis3dh_init` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/standin/lis3dh.c | `lis3dh_address` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/standin/lis3dh.c | `lis3dh_unpack` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/standin/lis3dh.c | `lis3dh_drain` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/test/lis3dh/standin/lis3dh.c | `lis3dh_read_click` | test stand-in (doc in its header) | 2026-11-14 | agent |
| firmware/src/lis3dh.c | `fifo_unread` | Decode unread count from FIFO_SRC; FSS=0 with OVRN and not EMPTY means 32 | 2026-11-15 | agent |
| tools/infer_ref.py | `arr` | parse_header helper: read one array literal | 2026-11-15 | agent |
| tools/infer_ref.py | `bad` | parse_header helper: raise a ValueError naming the bound | 2026-11-15 | agent |
| tools/infer_ref.py | `dim` | parse_header helper: resolve one array dimension | 2026-11-15 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `m_n` | Model: true unread count 0..32 (ruling R1) | 2026-11-15 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `m_fss` | Model: raw FSS field under the selected encoding | 2026-11-15 | agent |
| firmware/test/lis3dh/standin/lis3dh.c | `unread` | Stand-in: R1 FIFO_SRC decode | 2026-11-15 | agent |
| firmware/src/capture.c | `capture_buffer` | The 150x3 capture buffer (contents valid only in READY) | 2026-11-15 | agent |
| firmware/test/display/run_tests.py | `mirror_lr` | Left-right mirror of an 8x8 bitmap | 2026-11-15 | agent |
| firmware/test/display/run_tests.py | `check_golden` | Icon identity vs golden snapshot + mirror relations | 2026-11-15 | agent |
| firmware/test/display/icons_golden.py | (data) | Golden snapshot of icon bitmaps/colours | 2026-11-15 | agent |
| tools/train.py | `TrainError.__init__` | Exception carrying the process exit code | 2026-11-15 | agent |
| tools/train.py | `min_groups` | Fewest groups a grouped split needs | 2026-11-15 | agent |
| tools/train.py | `resolve_group` | Automatic/forced/requested grouping choice | 2026-11-15 | agent |
| tools/train.py | `missing_class_warnings` | Warn about classes missing from a split set | 2026-11-15 | agent |
| tools/train.py | `load_model` | load_header wrapper raising an exit-3 TrainError | 2026-11-15 | agent |
| tools/train.py | `wilson_interval` | 95 % Wilson interval for reported accuracy | 2026-11-15 | agent |
| tools/train.py | `evaluate_set` | Integer-path metrics + rejection stats for one set | 2026-11-15 | agent |
| tools/train.py | `_accuracy_lines` | Report text: accuracy section | 2026-11-15 | agent |
| tools/train.py | `_reject_lines` | Report text: rejection section | 2026-11-15 | agent |
| tools/train.py | `_fallback_verdict` | Report text: C4.3 fallback verdict (set and n) | 2026-11-15 | agent |
| tools/train.py | `summarize_seeds` | Multi-seed mean/min/max | 2026-11-15 | agent |
| tools/train.py | `_write_seeds_summary` | Write seeds.md / seeds.json | 2026-11-15 | agent |
| tools/train.py | `warn` | Nested helper: warning to stderr and report | 2026-11-15 | agent |
| tools/synth_dataset.py | `_start_gravity` | Shared start orientation cone for all classes | 2026-11-15 | agent |
| tools/synth_dataset.py | `start_tilt_deg` | Start tilt of a window from vertical | 2026-11-15 | agent |
| tools/synth_dataset.py | `start_tilt_separability` | S1 check: class 0 not separable by start tilt | 2026-11-15 | agent |
| tools/synth_dataset.py | `_selftest` | Shape, determinism, S1, S2 self-test | 2026-11-15 | agent |
| firmware/test/capture/oracle.py | `expand` | Flatten a script incl. (ops)N groups | 2026-11-15 | agent |
| firmware/test/capture/test_capture.c | `read_count` | Script parser: repeat count | 2026-11-15 | agent |
| firmware/test/capture/test_capture.c | `exec_seq` | Script parser: run a sequence with repeat groups | 2026-11-15 | agent |
| firmware/test/features/run_tests.py | `run_selftest` | Run tools/features_ref.py --selftest | 2026-11-15 | agent |
| firmware/test/*/Makefile (capture, classify, display, e2e, features, lis3dh, mlp) | (build rules) | Suite build + run (host and sim16) | 2026-11-15 | agent |
| tools/train.py | `counting` | Self-test helper: count integer_eval calls per feature hash | 2026-11-15 | agent |
| firmware/src/lis3dh.c | `init_fail` | Common init failure exit: best-effort CTRL_REG1 power-down, clear address | 2026-11-15 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `check_r5` | Bit 7 clear on single-byte reads, set on multi-byte reads | 2026-11-15 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `null_cb` | Sample callback that ignores its input | 2026-11-15 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `check_guards` | Pre-init guards: ERR_BUS with zero HAL transactions | 2026-11-15 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `check_stop_at` | Init stops at the first fault (only the allowed power-down after it) | 2026-11-15 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `t_guards_fresh` | Test groups: fresh guards, NULL tables, odd axis tables | 2026-11-15 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `t_null_tables` | Test groups: fresh guards, NULL tables, odd axis tables | 2026-11-15 | agent |
| firmware/test/lis3dh/test_lis3dh.c | `t_odd_tables` | Test groups: fresh guards, NULL tables, odd axis tables | 2026-11-15 | agent |
| firmware/test/e2e/test_e2e.c | `apply_noise` | e2e driver: directed windows, per-stage output, raw-sample checksum | 2026-11-15 | agent |
| firmware/test/e2e/test_e2e.c | `win_checksum` | e2e driver: directed windows, per-stage output, raw-sample checksum | 2026-11-15 | agent |
| firmware/test/e2e/test_e2e.c | `build_window` | e2e driver: directed windows, per-stage output, raw-sample checksum | 2026-11-15 | agent |
| firmware/test/e2e/test_e2e.c | `stage_mlp` | e2e driver: directed windows, per-stage output, raw-sample checksum | 2026-11-15 | agent |
| firmware/test/e2e/test_e2e.c | `stage_query` | e2e driver: directed windows, per-stage output, raw-sample checksum | 2026-11-15 | agent |
| firmware/test/e2e/test_e2e.c | `run_directed` | e2e driver: directed windows, per-stage output, raw-sample checksum | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `apply_noise` | e2e runner: window construction, expectations, directed plan | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `window_checksum` | e2e runner: window construction, expectations, directed plan | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `desc` | e2e runner: window construction, expectations, directed plan | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `make_window` | e2e runner: window construction, expectations, directed plan | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `evaluate` | e2e runner: window construction, expectations, directed plan | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `query_result` | e2e runner: window construction, expectations, directed plan | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `make_rec` | e2e runner: window construction, expectations, directed plan | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `crc16_ibm3740` | e2e runner: window construction, expectations, directed plan | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `store_crc` | e2e runner: window construction, expectations, directed plan | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `expected_steps` | e2e runner: window construction, expectations, directed plan | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `write_dplan` | e2e runner: window construction, expectations, directed plan | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `weak` | e2e runner: window construction, expectations, directed plan | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `gate_open` | e2e runner: window construction, expectations, directed plan | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `Planner` | Directed boundary search (x8 saturation, ties, radius, d2=0, conf gates, min_conf) | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `Planner.search` | Directed boundary search (x8 saturation, ties, radius, d2=0, conf gates, min_conf) | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `Planner.candidates` | Directed boundary search (x8 saturation, ties, radius, d2=0, conf gates, min_conf) | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `Planner.build` | Directed boundary search (x8 saturation, ties, radius, d2=0, conf gates, min_conf) | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `Planner.plan_saturation` | Directed boundary search (x8 saturation, ties, radius, d2=0, conf gates, min_conf) | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `Planner.plan_minconf_mlp` | Directed boundary search (x8 saturation, ties, radius, d2=0, conf gates, min_conf) | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `Planner.far_templates` | Directed boundary search (x8 saturation, ties, radius, d2=0, conf gates, min_conf) | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `Planner.plan_radius` | Directed boundary search (x8 saturation, ties, radius, d2=0, conf gates, min_conf) | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `Planner.plan_d2_zero` | Directed boundary search (x8 saturation, ties, radius, d2=0, conf gates, min_conf) | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `Planner.plan_conf_gate` | Directed boundary search (x8 saturation, ties, radius, d2=0, conf gates, min_conf) | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `Planner.plan_ck` | Directed boundary search (x8 saturation, ties, radius, d2=0, conf gates, min_conf) | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `boundary_hits` | Coverage counting, calibration windows, class-balanced bias, top1 histogram | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `calib_windows` | Coverage counting, calibration windows, class-balanced bias, top1 histogram | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `balance_bias` | Coverage counting, calibration windows, class-balanced bias, top1 histogram | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `histogram` | Coverage counting, calibration windows, class-balanced bias, top1 histogram | 2026-11-15 | agent |
| firmware/test/classify/test_classify.c | `v_x128` | Random x8 vector including -128 | 2026-11-15 | agent |
| firmware/test/classify/test_classify.c | `pad_tests` | knn_import padding (-2/-3) and NULL import/export cases | 2026-11-15 | agent |
| firmware/test/classify/test_classify.c | `edges` | 3.5R F4-F6 block: conf table, -128 scenarios, round trip | 2026-11-15 | agent |
| firmware/test/classify/oracle.py | `v_x128` | Mirror of the C -128 generator | 2026-11-15 | agent |
| firmware/test/classify/oracle.py | `Replay.pad_tests` | Expected padding/NULL lines | 2026-11-15 | agent |
| firmware/test/classify/oracle.py | `Replay.edges` | Expected F4-F6 lines | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `_q`, `_decisive`, `_conf_edge` | Coverage predicates for the boundary table | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `Planner.start`, `Planner.add`, `Planner.want`, `Planner.of`, `Planner.first` | Directed-plan bookkeeping helpers | 2026-11-15 | agent |
| firmware/test/e2e/run_e2e.py | `score`, `pred` | Nested search helpers inside Planner | 2026-11-15 | agent |
| docs/agent/hadi/spikes/integration/glue.c | `handle_overrun` | Handle a reported FIFO overrun as API_glue.md step (2): capture_overrun(), and if an open window | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/glue.c | `on_sample` | Drain callback: one wand-frame sample from lis3dh_drain (see file comment for the flow). | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/glue.c | `sensor_run` | Advance simulated time by n sample periods WITHOUT servicing the FIFO (the main loop is busy). | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/glue.c | `process_ready` | Classify the READY window as gesture_classify() would (API_glue.md section 2), print one line, | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/glue.c | `poll_once` | One gesture_poll() service step: drain once, handle overrun, classify when READY. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/glue.c | `stalled` | True while a configured stall is active (the main loop does not service the FIFO). | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/glue.c | `run_pass` | Run the whole stream once: gesture_init() per API_glue.md, then the simulated main loop. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/glue.c | `main` | Entry point: print the model identity, run pass 0 (no templates) and pass 1 (learn from the plan). | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/make_stream.py | `_unit` | integration spike helper | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/make_stream.py | `_rot_between` | Rotation matrix taking direction a to direction b. Args: a, b (3-vectors). Returns: 3x3. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/make_stream.py | `_tilt` | Smooth pose change p0 -> p1 over span samples (direction slerp, magnitude linear). | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/make_stream.py | `_mirror` | Mirror the first draws of synth_dataset.make_window to learn onset and duration. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/make_stream.py | `build` | Build one stream. Args: seed (int); classes (list of labels 1..8); reps (int per class); | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/make_stream.py | `check_mirror` | Assert that the mirrored onset equals the actual onset of the generated window. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/make_stream.py | `write_header` | Write the C header for glue.c. Args: path; name (str); x (int16 [N,3]); gt (dict). | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/make_stream.py | `emit` | Write NAME.npy, NAME.json, NAME.h. Args: outdir; name; x; gt. Returns: None. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/make_stream.py | `main` | CLI: make_stream.py --out DIR. Writes the streams main, big, tight, stall, short. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/make_stream.py | `add` | integration spike helper | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/evaluate.py | `parse` | Parse a glue output file. Args: path. Returns: list of passes, each dict(W=[...], ev=[...], S=str). | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/evaluate.py | `python_check` | Replay every window through the Python reference. Args: passes; x (int16 [N,3]); model. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/evaluate.py | `match` | Match the windows of one pass to the ground truth. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/evaluate.py | `pct` | Percentage string. Args: a, b ints. Returns: str. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/evaluate.py | `med` | Percentile of a list. Args: v; q. Returns: int or None. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/evaluate.py | `report_run` | Print the per-class table of pass 0 and the k-NN delta of pass 1 for one run. Returns: dict summary. | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/evaluate.py | `main` | CLI. Args: --build DIR --runs "a b c" --sim NAME. Returns: exit code (1 on host/sim16 or Python mismatch). | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/evaluate.py | `clean` | Read an output file without the SIM16_EXIT line (run_sim16.sh strips it, the host build prints it). | 2026-11-14 | agent |
| docs/agent/hadi/spikes/integration/fake_lis3dh.c | `fake_push_sample` (+ copy of firmware/test/lis3dh fake) | Inject one recorded sample into the fake FIFO | 2026-11-15 | agent |
| docs/agent/hadi/spikes/integration/fake_lis3dh.c | `push_one_w` | Push one raw sample word into the fake FIFO (helper of fake_push_sample) | 2026-11-15 | agent |
| tools/synth_dataset.py | `make_window` (onset_jitter option) | Optional onset jitter to approximate trigger latency (default unchanged) | 2026-11-15 | agent |
| tools/synth_dataset.py | `make_dataset` (onset_jitter option) | Thread onset jitter through dataset generation | 2026-11-15 | agent |
| docs/agent/hadi/spikes/integration/evaluate.py | `onset_bin_accuracy` | Hit-window accuracy per onset-position bin, side by side for two models | 2026-11-15 | agent |
