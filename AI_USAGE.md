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
