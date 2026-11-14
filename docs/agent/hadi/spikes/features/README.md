<!-- [AI-GENERATED: Claude Code] -->
# C3 feature-extraction spike (S1-2, fix round on branch s1-2-fixes)

Spike, not product code. Integer feature extraction in C (`features.c`) and Python
(`features_ref.py`), proven bit-exact. Spec, decisions and the energy-scaling comparison:
`../../proposals/C3_features.md`.

## Run
    make test   # 6 energy variants x 12339 windows, exact compare, plus exhaustive /15 and isqrt checks
    make xc16   # XC16 v2.10 -O1 and -O2, zero warnings, sizes, plain-buffer caller check
    make clean
    python3 energy_study.py   # the energy option comparison table

## Files
- `features.c/.h` C99; energy mode via `FEAT_ENERGY_MODE` (0 shift, 1 isqrt(SS), 2 isqrt(SS/15)) and `FEAT_ENERGY_SHIFT`
  (default mode 0, shift 11, pending decision D4; recommended: mode 1)
- `features_ref.py` Python reference (integer-only, same modes via arguments)
- `host_runner.c`, `gen_vectors.py`, `compare.py`, `div15_check.c`, `call_check.c`, `energy_study.py`

## Results
See proposal section 4. `make test`: ALL VARIANTS PASS (12339/12339 each). `make xc16`: zero warnings.
Not run on target: the on-target vector check (gate G3) is still required.
<!-- [END AI-GENERATED] -->
