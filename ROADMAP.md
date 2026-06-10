# Cascade Roadmap

Cascade's goal is to be the tool a small team reaches for to develop a small
gas turbine — and to earn that position with transparency: cited loss models,
published validation, honest refusals, and this roadmap.

Every deferred item below carries a stable gap ID from `KNOWN_GAPS.md`.
Nothing unshipped is described in the present tense. When this document and
the code disagree, the code and `KNOWN_GAPS.md` win — file an issue.

## Where Cascade serves today

Cascade v1 covers **single-shaft radial machines in the microturbine class**:
recuperated Brayton cycles, radial inflow turbines, and centrifugal
compressors — the architecture of natural-gas microturbines, small
turbogenerators, and ORC/sCO2 expanders. The larger end of "small gas
turbines" (1-20 MW axial and multi-spool machines) is the v1.1 trajectory
below, not a current capability (KG-AXT-01, KG-003).

Measured against the credibility table stakes in
[docs/research/competitive-landscape.md](docs/research/competitive-landscape.md):

| Table stake | Status |
|---|---|
| Published-case validation | Shipped — `VALIDATION_REPORT.md`, reproducible via `make validation` |
| Citable loss models | Shipped — every loss model carries a citation, enforced by `make check-citations` |
| Real-gas equation of state | Shipped in the cycle solver (NASA polynomials + CoolProp); mean-line plumbing is KG-ML-07 |
| Units discipline (SI + US customary) | Shipped — pint-backed, dimension-checked at boundaries |
| Performance-map conventions | Shipped — corrected-flow maps with explicit surge/choke/non-convergence codes |
| Refusal over extrapolation | Shipped — `SPEC_SHEET.md` §13 doctrine, enforced in solvers and API |
| API 617/684 rotor outputs | Partial — separation margin and amplification factor per API 684 ship; full report alignment is roadmap work |
| STEP/IGES + TurboGrid handoff | Partial — TurboGrid/CGNS/point-cloud export ship; STEP/IGES requires the optional CAD dependency (KG-G-09) |
| Axial machines | Not shipped (KG-AXT-01) |
| Secondary-air / thermal-fluid networks | Not shipped (KG-TFN-01) |

## Landing in this release

- Job refusal contract: invalid or incomplete projects fail with a
  plain-English explanation and structured envelope — never a silent
  zero-efficiency "success".
- Test and build gates: API contract tests, web unit tests, typecheck, and
  the production build all run in `make ci`; test runs are isolated from
  user project storage.
- Truthful README: capability claims reconciled against shipped code.
- Burner fuel-mass-flow mode wired end-to-end: specify ṁ_fuel, get derived
  turbine inlet temperature — with design-class refusals for invalid inputs.
- Candidate detail pages: deep-linkable URLs for design-exploration
  candidates, with geometry, objectives, manufacturability, exports, and a
  "send to cycle" handoff that feeds live mean-line co-simulation.
- Live mean-line attribution: the result panel reports each rotor's
  efficiency source (live mean-line, fixed isentropic, or fallback) —
  fallback is visible, never silent.
- This roadmap and the competitive landscape document.

## Next (v1.1)

Solver capability, in priority order for the small-NG-turbine persona:

1. **Axial turbine and compressor mean-line** (KG-AXT-01) — Kacker-Okapuu and
   Koch-Smith loss systems with the same citation and validation discipline
   as the radial solvers. Opens the 1-20 MW segment.
2. **1D thermal-fluid network solver** (KG-TFN-01) — secondary air, cooling,
   seals, disc cavities; the missing piece for whole-machine thermal design.
3. **Multi-spool cycle matching** (KG-003) and **cooled turbine** (KG-004).
4. **Foil and tilt-pad bearing solvers** (KG-009, KG-007) — foil bearings are
   the microturbine-standard configuration; today they enter rotor dynamics
   as tabulated stiffness/damping.
5. **Off-design mean-line choke/surge** (KG-ML-06) and **real-gas mean-line
   plumbing** (KG-ML-07) — unlocks sCO2 validation cases (KG-ML-09/10).
6. **Performance map follows the candidate** (KG-PLAT-03) — candidate-scaled
   grids and design points instead of reference geometry.

Platform:

- **Real-time co-edit** (KG-PLAT-01) — Yjs/Hocuspocus path documented in the
  gap entry.
- **Canvas connectivity semantics** (KG-PLAT-02) — recuperator-aware edge
  validation; edges are illustrative today and the UI says so.
- **Hosted instance** (KG-PLAT-04) — auth, multi-user storage, job queue.
  AGPL self-host stays free and first-class; hosting is how the project
  sustains itself without compromising the open core.
- **TypeScript SDK** generated from the OpenAPI schema.
- **Validation coverage debt** (KG-ML-09/10, KG-RD-06) — digitize the
  remaining published cases so claimed coverage equals tested coverage.

## Later (adapter strategy)

Per `SPEC_SHEET.md` §2, these stay outside the core on purpose:

- 3D RANS CFD — adapter contract (OpenFOAM stub ships; native CFD is not the
  product).
- Full 3D FEA — CalculiX adapter; native v1 stress is 2D-axisymmetric.
- CAM / 5-axis manufacturing — out of identity; export formats are the
  boundary.

## What we will not build

Cascade competes on transparency, reproducibility, and access — not on
module count. No 70-module sprawl, no quote-only pricing, no dongles, no
native CFD/FEA arms race. The scope refusals above are commitments, not
omissions.
