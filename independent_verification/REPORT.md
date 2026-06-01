# Independent Verification Report

_Generated: 2026-06-01 01:15:09_

This report is intentionally coarse. It identifies the engineering area and the kind of physics implicated, but not the specific failing check, expected value, or assertion. Fix the underlying behaviour, not the test.

## Headline: ATTENTION REQUIRED

- Total checks: **165**
- Passed: **163**
- Failed (outside accepted bounds): **2**
- Needs review (could not run / skipped): **0**

## By subsystem

| Subsystem | Passed | Failed | Review |
|-----------|-------:|-------:|-------:|
| Cycle thermodynamics (0D Brayton) | 19 | 0 | 0 |
| Journal bearing (hydrodynamic) | 8 | 0 | 0 |
| Materials database | 53 | 0 | 0 |
| Mean-line: centrifugal compressor | 11 | 0 | 0 |
| Mean-line: radial inflow turbine | 12 | 1 | 0 |
| Optimization (SLSQP / CMA-ES / NSGA-II) | 9 | 0 | 0 |
| Rotor dynamics (beam-FEM) | 10 | 0 | 0 |
| Slip-factor correlations | 25 | 1 | 0 |
| Design-space sampling (Sobol') | 6 | 0 | 0 |
| Units engine | 10 | 0 | 0 |

## Areas to investigate

- **Mean-line: radial inflow turbine** — One or more derived radial-turbine performance metrics fall outside the physically-consistent range. Revisit the efficiency definitions (total-to-total, total-to-static, polytropic) and their consistency with the computed enthalpy and pressure changes.
- **Slip-factor correlations** — Slip-factor behaviour at (and below) the edge of its documented validity envelope is not fully safe. Review how out-of-envelope blade counts are handled against SPEC_SHEET §13 / §15 (clip to a physical value WITH a warning; never silently extrapolate to a degenerate result).
