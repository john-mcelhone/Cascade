# Cascade

The web-native turbomachinery design environment for small engineering teams.

Cascade is built around the idea that turbomachinery design should be:

- **Transparent** — every loss model has a published citation; no opaque black boxes.
- **Reproducible** — projects are text-based, units-aware, git-diffable; what you ran yesterday runs the same today.
- **Validated** — every solver ships with a public validation report against canonical published cases. No marketing-only accuracy claims.
- **Diff-friendly** — TOML project format means git pull requests are how teams collaborate in v1.0. Real-time co-edit on the canvas is planned for v1.1 (see `KNOWN_GAPS.md` KG-PLAT-01).
- **Self-serve** — transparent pricing, free starter tier, public docs.

## What's in v1

- 0D thermodynamic cycle solver (Brayton variants, recuperated, reheat, intercooled) with real-gas equation of state (NASA polynomials + CoolProp + REFPROP optional).
- 1D thermal-fluid network solver (Fanno + Rayleigh ducts, Idelchik K-factors, labyrinth seals, disc cavities, ε-NTU heat exchangers).
- Mean-line preliminary design for radial inflow turbine, centrifugal compressor, axial turbine, axial compressor — with transparent, citable loss models (Whitfield-Baines, Aungier, Kacker-Okapuu, Koch-Smith).
- Design exploration: Sobol' sampling of hundreds-to-thousands of candidate geometries with interactive filter + pick.
- Performance map generator with explicit surge/choke/non-convergence codes.
- Rotor dynamics: linear Timoshenko beam-FEM, gyroscopic coupling, critical-speed map, unbalance response (Bode + amplification factor + separation margin), Campbell, stability.
- Plain-journal bearing solver (Reynolds + Christopherson PSOR).
- Python SDK + CLI parity with the web UI.
- Reproducible project format: `.cascade` directory of TOML files with units; collaboration model in v1.0 is asynchronous (branch + diff + pull request).

## What's deferred to v1.1

See `SPEC_SHEET.md` §2. Real-time multi-user co-edit (Yjs/Hocuspocus path; KG-PLAT-01), multi-stage radial, multi-spool axial cycle matching, tilt-pad / thrust / foil bearings (table input accepted in v1), 2D streamline-curvature throughflow, JFO cavitation BC, Bayesian optimization, visual node-graph workflow editor.

## What's out of v1 (adapter contracts only)

Native RANS CFD (OpenFOAM stub); full 3D linear FEA (CalculiX adapter; native v1 is 2D-axisymmetric disc-stress); design assistant (docs retrieval only in v1).

## Quick start

```sh
make setup       # one-time: install Python deps in .venv
make demo        # run the three demo projects end-to-end
make test        # run unit tests
make validation  # run the public validation suite vs published cases
```

## Architecture

- **Numerical core**: Python 3.12 (numpy, scipy, CoolProp, SUNDIALS via scikits.odes).
- **API**: FastAPI with auto-generated OpenAPI + Python and TypeScript SDKs.
- **Frontend**: Next.js 15 / React 19 App Router; Plotly + react-three-fiber.
- **Database**: PostgreSQL 16 with pgvector.
- **Collaboration (v1.0)**: TOML project format + git; pull-request review of designs.
- **Collaboration (v1.1, planned)**: Yjs CRDT over Hocuspocus for real-time co-edit.
- **Jobs**: Celery + Redis.
- **Deploy**: Fly.io.

## Repository layout

```
src/cascade/         The Python package — all the numerical core
apps/web/           Next.js web app
apps/api/           FastAPI server
packages/ui-components/   Shared React components
tests/              Cross-package integration + e2e tests
validation_data/    Validation datasets (where licensing permits)
docs/               User-facing documentation
scripts/            Operational scripts
SPEC_SHEET.md       The canonical specification — read this first
```

## Demo recording script

A 30-second demo for a new viewer:

1. Land on the home page → "Start a new microturbine cycle" → see the cycle canvas pre-populated with a recuperated Brayton (compressor + recuperator + burner + turbine).
2. Click "Run cycle" → see η_thermal compute in < 200 ms with the result panel showing each component's state.
3. Click "Design the radial turbine" → drop into the preliminary-design view with the cycle's exit conditions pre-loaded as boundary conditions.
4. Hit "Explore design space" → see 2,000 Sobol candidates resolve to a colored scatter plot in 30 seconds; click a high-efficiency point → see the 3D geometry update live.
5. Click "Generate performance map" → 5×11 grid resolves in 60 seconds; surge and choke lines plot automatically with explicit per-point convergence codes.
6. Click "Send to rotor dynamics" → land in the rotor sketch with the impeller imported as a lumped disk; add two bearings; click "Run lateral" → see the Bode plot, critical-speed map, and separation-margin chart render in 5 seconds.

This is the full hero workflow legacy tools demonstrate. Cascade runs in a browser with no install.

## License

AGPL-3.0-or-later for the open-source community edition. Python SDK is MIT.

## Status

Pre-release. Validation report lives at `VALIDATION_REPORT.md`.
