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
