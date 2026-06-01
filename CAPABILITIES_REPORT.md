# Cascade — Software Capabilities Report

**Version:** 0.1.0 (pre-release) · **License:** AGPL-3.0-or-later (core), MIT (Python SDK) · **Report date:** 2026-06-01

## What it is

Cascade is a **web-native turbomachinery design environment** aimed at small engineering teams. It lets engineers go from a thermodynamic cycle, through preliminary aero design of the rotating machine, into geometry and rotor dynamics — entirely in a browser with no install. Its design philosophy is **transparency, reproducibility, and validation**: every loss model carries a published citation, projects are text-based and git-diffable, and every solver ships a public validation report against canonical published cases rather than marketing accuracy claims.

## Core capabilities (implemented in v1)

| Domain | Capability |
|---|---|
| **0D cycle thermodynamics** | Brayton variants — simple, recuperated, reheat, intercooled (single-shaft). Real-gas EOS via NASA polynomials + CoolProp (REFPROP optional). Solves η_thermal in < 200 ms. Components: compressor, turbine, burner, recuperator, inlet loss. |
| **Mean-line preliminary design** | Radial inflow turbine (RIT) and centrifugal compressor with transparent, citable loss models (Whitfield–Baines, Aungier, Wiesner slip). Design-incidence and slip-factor physics. |
| **Design space exploration** | Sobol' quasi-random sampling of hundreds–thousands of candidate geometries; interactive filter-and-pick scatter plots; live 3D geometry preview. |
| **Performance maps** | Full-factorial grid map generator with explicit per-point convergence codes (surge / choke / non-converged). |
| **Rotor dynamics** | Linear Timoshenko beam-FEM with gyroscopic coupling: critical-speed map, unbalance response (Bode + amplification factor + separation margin), Campbell diagram, stability/eigenanalysis. |
| **Bearings** | Plain-journal solver (Reynolds + Christopherson PSOR). Tabulated K–C input accepted for any bearing type. |
| **Geometry** | Parametric impeller, radial-turbine, volute, and rotor geometry; curve generation; optional STEP/IGES CAD export (OpenCASCADE, optional `cad` extra). |
| **Materials & manufacturability** | Materials database/registry; rule-based manufacturability checks and reports. |
| **Optimization** | SLSQP, NSGA-II, CMA-ES, Powell (BOBYQA API) for single/multi-objective design. |
| **Project format** | `.cascade` directory of units-aware TOML files (Pint-backed). Async collaboration via git branch + diff + pull request. |
| **Interfaces** | Python SDK + CLI (`cascade`) with parity to the web UI; FastAPI server with auto-generated OpenAPI; extensible plugin/adapter system with a sandboxed runner. |

## Architecture & tech stack

- **Numerical core:** Python 3.12 — numpy, scipy, Pint (units), Pydantic, CoolProp; packaged as `src/cascade/` with `pint`/`typer`/`rich` CLI.
- **API:** FastAPI + Uvicorn, SQLAlchemy 2.0 (async) + Alembic, Celery + Redis jobs, ReportLab. Routers cover cycle, meanline, analysis, rotor, map, explore, candidates, materials, manufacturability, validation, projects.
- **Frontend:** Next.js 15 / React 19 App Router; Plotly + react-three-fiber (3D). Component areas: cycle, flowpath, rotor, map, materials, analysis, learn, three.
- **Data:** PostgreSQL 16 with pgvector. **Deploy:** Fly.io.
- **Quality gates:** pytest + hypothesis, ruff, mypy (strict). **1,115 tests passing**; 130 pass-gate (`@pytest.mark.validation`) cases block CI.

## Validation status (selected pass-gates)

- **CYC-1** simple Brayton: η_th 44.80% vs textbook 44.79% (±0.01 pt) ✅
- **CYC-2** recuperated Brayton: η_th 54.91% ✅ · **CYC-3** Capstone C30: η_e 26.09% vs 26% ✅
- **CC-1** Eckardt Rotor A (calibrated): π_tt within ±0.10 ✅ · **RIT-1** NASA TN D-7508: η_ts 0.817 vs ~0.84 (±5 pt) ✅
- All currently-implemented pass-gates pass within their published tolerance bands (validation subset runs in ≈14 s).

## Honest scope boundaries (not in v1)

Cascade documents its gaps explicitly (`KNOWN_GAPS.md`). **Not implemented in v1:** the 1D thermal-fluid network solver (`cascade.network` — Fanno/Rayleigh ducts, labyrinth seals, disc cavities, ε-NTU HX) and the **axial turbine/compressor mean-line solver** are specified but not yet built. Several validation cases (CYC-4/5/6/7, RIT-3/4, CC-3/4/5, AXT/AXC, TFN) are characterization-only or have no test. **Deferred to v1.1+:** real-time multi-user co-edit (Yjs/Hocuspocus), multi-stage radial, multi-spool/cooled-turbine cycle matching, tilt-pad/thrust/foil bearings, 2D streamline-curvature throughflow, Bayesian optimization, and a visual node-graph editor. **Permanent adapter-only (never native):** RANS CFD (OpenFOAM stub) and full 3D FEA (CalculiX adapter; v1 ships 2D-axisymmetric disc stress).

## Hero workflow

Land → start a recuperated Brayton microturbine cycle → run cycle (<200 ms) → design the radial turbine with cycle exit conditions pre-loaded → explore 2,000 Sobol candidates (~30 s) → generate a performance map with surge/choke lines (~60 s) → send the impeller to rotor dynamics and run a lateral analysis (Bode, critical-speed map, separation margin) in ~5 s — all in-browser, reproducibly, with cited physics.

---
*Generated from README.md, SPEC_SHEET.md, VALIDATION_REPORT.md, KNOWN_GAPS.md, pyproject.toml, and source inspection of `src/cascade/`, `apps/api/`, and `apps/web/`.*
