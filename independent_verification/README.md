# Independent Verification Suite

A black-box accuracy and safety-bounds suite for the implemented Cascade v1
numerical core. It is intentionally **independent** of the repository's own
`tests/` directory.

## Methodology (why this is unbiased)

Every expected value or bound in this suite is derived from one of:

- **Closed-form physics** — ideal & non-ideal Brayton efficiency, Carnot bound,
  Euler/blade-speed kinematics (`U = ωr`), isentropic & polytropic relations.
- **Published correlations** — Wiesner / Stanitz / Stodola slip factors at the
  radial-bladed limit.
- **Analytical vibration theory** — simply-supported beam natural frequency,
  disk-dominated Jeffcott `ω = √(k/m)`, two-inertia torsional `√(k(1/J₁+1/J₂))`,
  gyroscopic forward/backward whirl splitting.
- **Universal invariants** — efficiencies in (0,1), `η_ts < η_tt`, conservation
  of energy, journal eccentricity in [0,1), `yield < ultimate`, monotonic trends.
- **NIST/SI definitions** — exact unit conversions.
- **Textbook property bounds** — alloy density / modulus / Poisson ranges.

The implementation source (`src/cascade/.../*.py`) is **not** consulted to set any
expected number. Only the public call interface (function signatures, dataclass
fields) is used, and a handful of real published geometries are reused purely as
*inputs* that are known to converge — never as expected outputs.

Out-of-scope v1 features (axial mean-line, thermal-fluid network, CFD, 3-D FEA,
multi-stage, tilt-pad / foil bearings, real-gas EOS in mean-line — see
`KNOWN_GAPS.md`) are **not** tested; doing so would be unfair, not informative.

## Running

```sh
# from the repo root, with the project venv:
PYTHONPATH=src .venv/bin/python independent_verification/run_report.py
```

This runs the suite and writes a **coarse** `REPORT.md`: per-subsystem
pass/fail/review counts plus a generic, non-specific remediation theme for any
flagged area. It deliberately omits test names, expected values, and assertion
diffs so that fixes target the underlying physics rather than the test.

`.last_results.json` (git-ignored) holds the per-test detail used to build the
report; it is private to the verification process and is not shared with whoever
fixes the code.
```
