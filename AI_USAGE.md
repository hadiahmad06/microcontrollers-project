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
