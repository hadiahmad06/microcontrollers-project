# features_qa (S1-2T)

Independent test of the S1-2 feature extractor. The oracle was written from the spec only.

    make test    # builds the implementation (copied read-only from IMPL into build/), runs
                 # oracle sanity, exhaustive mean, 7 adversarial groups, 4 sinusoid groups,
                 # then XC16 -O1/-O2/-Os warning checks
    make clean

Files: `oracle.py` (spec oracle), `gen.py` (window generators), `run_tests.py` (runner),
`Makefile`. Override the implementation location with `make IMPL=<dir>`.

Notes: XC16 free license disables -Os ("Options have been disabled due to
restricted license"), so that level is not really exercised; the Makefile flags this.
