# Cascade

The web-native turbomachinery design environment for small engineering teams.

Cascade is built around the idea that turbomachinery design should be:

- **Transparent** — every loss model has a published citation; no opaque black boxes.
- **Reproducible** — projects are text-based, units-aware, git-diffable; what you ran yesterday runs the same today.
- **Validated** — every solver ships with a public validation report against canonical published cases. No marketing-only accuracy claims.
- **Diff-friendly** — TOML project format means git pull requests are how teams collaborate in v1.0. Real-time co-edit on the canvas is planned for v1.1 (see `KNOWN_GAPS.md` KG-PLAT-01).
- **Open** — AGPL-3.0 community edition, free to self-host, public docs and a public roadmap. A hosted instance is on the roadmap (`ROADMAP.md`).

## What's in v1

- 0D thermodynamic cycle solver (simple, recuperated, and multi-shaft Brayton) with real-gas equation of state (NASA polynomials + CoolProp; REFPROP optional).
- Mean-line preliminary design for radial inflow turbine and centrifugal compressor — with transparent, citable loss models (Whitfield-Baines, Aungier, Wiesner/Stanitz/Stodola, Daily-Nece).
- Design exploration: Sobol' sampling of hundreds-to-thousands of candidate geometries with interactive filter + pick.
- Performance map generator with explicit surge/choke/non-convergence codes.
- Rotor dynamics: linear Timoshenko beam-FEM, gyroscopic coupling, critical-speed map, unbalance response (Bode + amplification factor + separation margin), Campbell, stability.
- Plain-journal bearing solver (Reynolds + Christopherson PSOR). Tilt-pad, thrust, and foil bearings accept tabulated stiffness/damping input (native solvers: see `KNOWN_GAPS.md` KG-007/008/009).
- CLI (`cascade demo`, `validate`, `sweep`, `export`, plugin management). The Python package doubles as the scripting interface; full SDK/CLI parity with the web UI is not yet reached — the spec-parity gate (`make spec-parity`) tracks the uncovered surface.
- Reproducible project format: `.cascade` directory of TOML files with units; collaboration model in v1.0 is asynchronous (branch + diff + pull request).

## What's deferred to v1.1

See `SPEC_SHEET.md` §2 and `ROADMAP.md`. Headline items:

- 1D thermal-fluid network solver (Fanno + Rayleigh ducts, Idelchik K-factors, labyrinth seals, disc cavities, ε-NTU heat exchangers) — not yet implemented (KG-TFN-01).
- Axial turbine and axial compressor mean-line design (Kacker-Okapuu, Koch-Smith) — not yet implemented (KG-AXT-01).
- Real-time multi-user co-edit (Yjs/Hocuspocus path; KG-PLAT-01), multi-stage radial, multi-spool axial cycle matching, native tilt-pad/thrust/foil bearing solvers, 2D streamline-curvature throughflow, JFO cavitation BC, Bayesian optimization, visual node-graph workflow editor.
- TypeScript SDK generated from the OpenAPI schema.

## What's out of v1 (adapter contracts only)

Native RANS CFD (OpenFOAM stub); full 3D linear FEA (CalculiX adapter; native v1 is 2D-axisymmetric disc-stress); design assistant (docs retrieval only in v1).

## Quick start

```sh
make setup       # one-time: install Python deps in .venv
make demo        # run the three demo projects end-to-end
make test        # run unit tests (core + API)
make validation  # run the public validation suite vs published cases
make ci          # full gate: tests + validation + web tests + production build + citations
```

## Architecture

**Running today** (what `make run` starts):

- **Numerical core**: Python 3.12 (numpy, scipy, CoolProp, pint).
- **API**: FastAPI with auto-generated OpenAPI. In-memory project store with TOML write-through persistence (`~/.cascade/projects`); jobs on a thread pool. Single-user.
- **Frontend**: Next.js 15 / React 19 App Router; Plotly + react-three-fiber.

**Deployment target** (planned; see `ROADMAP.md`):

- PostgreSQL for multi-user project storage, Celery + Redis for job queues, hosted deployment, authentication, real-time collaboration (KG-PLAT-01).

## Repository layout

```
src/cascade/         The Python package — all the numerical core
apps/web/            Next.js web app
apps/api/            FastAPI server
tests/               Core unit + integration + validation tests
apps/api/tests/      API contract tests (separate pytest invocation)
docs/                Plans and research documents
SPEC_SHEET.md        The canonical specification — read this first
KNOWN_GAPS.md        Every known gap, with stable KG-IDs
VALIDATION_REPORT.md What is validated against which published cases
ROADMAP.md           Public roadmap
```

Interactive theory chapters and tutorials live in the web app under `/learn`.

## Demo walkthrough

A 2-minute tour for a new viewer:

1. Land on the home page → "Start a new microturbine cycle" → see the cycle canvas pre-populated with a recuperated Brayton (compressor + recuperator + burner + turbine).
2. Click "Run cycle" → η_thermal computes with the result panel showing each component's state.
3. Click "Design the radial turbine" → drop into the preliminary-design view with the cycle's exit conditions pre-loaded as boundary conditions.
4. Hit "Explore design space" → thousands of Sobol candidates resolve to a colored scatter plot; click a high-efficiency point → see the 3D geometry update.
5. Click "Generate performance map" → the grid resolves with surge and choke lines plotted automatically and explicit per-point convergence codes.
6. Open Rotor Dynamics → build the rotor sketch, add bearings, run lateral analysis → Bode plot, critical-speed map, and separation-margin chart.

Cascade runs in a browser with no install.

## License

AGPL-3.0-or-later.

## Status

Pre-release. Validation report lives at `VALIDATION_REPORT.md`; every known gap has a stable ID in `KNOWN_GAPS.md`.
