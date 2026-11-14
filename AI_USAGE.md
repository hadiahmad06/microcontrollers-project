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
