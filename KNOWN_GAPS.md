# KNOWN_GAPS

Honest list of what Cascade v1 does **not** ship, why, and what shipping it would require. This is the contract with users: we'd rather under-promise and ship than over-promise and lie.

Compiled from the design reviews and build-plan deferrals. Each gap has a stable ID so it can be tracked across releases.

## Numerical engine gaps

| ID | Gap | Why deferred | What v1 ships instead | Target |
|----|-----|--------------|------------------------|--------|
| KG-001 | Native RANS CFD solver | Building a competitive RANS code is a 50+ person-year effort; doing it badly would poison the rest of the product. | A clean `CFDRun` adapter contract; an OpenFOAM-backed stub for one canonical radial-rotor-passage case. Users can integrate Ansys CFX / Star-CCM+ via the same adapter contract. | Never planned; permanent adapter. |
| KG-002 | Full 3D linear FEA (static stress, modal, harmonic) | Same scale problem as RANS. | 2D axisymmetric disc-stress (real solver); adapter contract for CalculiX / code_aster for full 3D. | v1.x (year+) |
| KG-003 | Multi-spool axial cycle matching | Out of microturbine-first v1 scope; needed for two-shaft / three-shaft engines like PW1100G family. | Multi-shaft Brayton power-balance spool matching ships (ADAPT-034); map-based corrected-flow multi-spool matching deferred. | v1.1 |
| KG-004 | Cooled-turbine row coolant-mixing model | Acknowledged in the cycle design review; affects PW1100G HPT validation (CYC-7 informational only in v1). | Uncooled turbine math only. CYC-7 PW1100G is informational, not a pass-gate. | v1.1 |
| KG-005 | 2D streamline curvature throughflow | 1D mean-line covers v1 use cases; SC adds ~3 person-months. | 1D mean-line at mid-span only. | v1.1 |
| KG-006 | Multi-stage radial machines | Single-stage radial covers the microturbine use case; multi-stage centrifugal is interesting for industrial process compressors. | Single-stage RIT and CC only. Multi-stage axial supported in v1 via repeating-stage assumption. | v1.1 |
| KG-007 | Tilt-pad bearing solver (Reynolds + pad pivot equilibrium) | Plain journal is enough for the v1 microturbine path. Tilt-pad is petrochem standard. | Tabulated K-C input accepted for any bearing type. | v1.1 |
| KG-008 | Thrust bearing solver (Kingsbury / Mitchell pad) | Less common in microturbine; tabulated K accepted in v1. | Tabulated input accepted. | v1.1 |
| KG-009 | Foil bearing solver | Emerging for microturbines (Capstone uses them); literature is research-grade. Heshmat et al. cited but not implemented. | Tabulated K-C input accepted. | v1.x |
| KG-010 | Bayesian / EGO optimization (Kriging surrogate + Expected Improvement) | SLSQP + NSGA-II cover the bulk of v1 needs. Bayesian is gold-standard for expensive evaluations. | SLSQP, IPOPT, BOBYQA, CMA-ES, NSGA-II, NSGA-III in v1. | v1.1 |
| KG-011 | Visual node-graph workflow editor | Python SDK + CLI gives equivalent power. Visual editor adds 4-6 person-months of UI work. | Python SDK + CLI parity with web UI. | v1.x |
| KG-012 | Design assistant | Docs retrieval ships in v1. A conversational assistant requires careful evaluation infrastructure. | Docs retrieval + Q&A only. | v1.1 |
| KG-013 | JFO (Jakobsson-Floberg-Olsson) cavitation BC for journal bearings | Reynolds BC with Christopherson PSOR covers v1. JFO is the gold standard. | Christopherson PSOR. | v1.1 |
| KG-014 | Active magnetic bearings (AMB) | Out of microturbine scope; needed for some industrial machines. | Not supported. | v1.x |
| KG-015 | Squeeze-film dampers | Out of v1 scope; nonlinear bearing modeling. | Not supported. | v1.1 |
| KG-016 | Mihrshin-Stepanov loss correlation source | Russian-tradition citation; original source not located. | Substituted with Whitfield-Baines (1990) Ch. 6 as default; flagged in any imported legacy project. | When source found. |
| KG-017 | Legacy proprietary loss-model names | Proprietary internal correlations; not citable. | Treated as opaque placeholders in imported projects; substituted with cited open defaults; user notified of substitution. | Never planned (open-source replacement is the differentiator). |
| KG-018 | SR-007 — Phadke-Owen 1988 rim-seal coefficient table | Owen 2011 J Turbomach review may be gated. | Phadke-Owen 1988 axial-seal form only in v1; double-seal and chute-seal deferred. | v1.1 |
| KG-019 | BOBYQA proper (Powell 2009 trust-region quadratic interpolation) | scipy doesn't ship BOBYQA; the `Py-BOBYQA` package is the production option. v1 uses scipy's Powell method (Powell 1964 direction-set), which is in the same algorithmic family and adequate for the OPT-1 Branin pass-gate. | scipy's `Powell` under the `OptimizeBOBYQA` API name. | v1.1: swap in `Py-BOBYQA` backend when installed. |
| KG-020 | NSGA-III (Deb & Jain 2014) for ≥4-objective problems | Reference-point-based niching is meaningfully more complex than NSGA-II's crowding distance; pymoo's implementation is the canonical reference. v1 ships NSGA-II only; the `OptimizeNSGA3` class raises `NotImplementedError`. | NSGA-II is the multi-objective default. For 4+ objectives, install pymoo and use its NSGA-III directly. | v1.1: full in-tree NSGA-III or pymoo wrapper. |
| KG-021 | IPOPT large-scale NLP (Wächter & Biegler 2006) | Requires `pyomo` + the `ipopt` executable on PATH; not part of the default dev env. The class is constructible only when both are available. | scipy SLSQP covers most v1 NLP problems; IPOPT is the escape hatch for d>1000. | v1.x: ship pyomo + ipopt-binary in a docker image. |
| KG-022 | Optimization warm-start from a DesignSpace pick | The design notes describe "warm-start optimizer from DOE pick" as a one-line operation, but the in-tree optimizers don't yet auto-extract `x0` from `Candidate.params`. The interface is uniform enough to compose by hand. | Manual: extract `x0 = np.array([c.params[k].magnitude for k in keys])` from a chosen `Candidate`. | v1.1: a `from_candidate()` helper on each optimizer. |
| KG-023 | Adaptive (surrogate-guided) performance-map sampling | Pacheco-Sanjuan & Larson 2017 lists this as research-grade. v1 ships full-factorial grids only. | Full-factorial Cartesian-product grid; explicit per-point codes. | v1.1: Bayesian-active sampling near surge/choke loci. |
| KG-024 | Performance-map choke-line bisection refinement | When a grid sample sits between converged and CHOKED, bisect mass-flow to find the choke point within tolerance. v1 reports the rightmost CHOKED grid point only — no sub-grid interpolation. | Choke line lands on the nearest grid point. Users add finer m_dot resolution near suspected choke for higher accuracy. | v1.1: per-speedline bisection refinement. |
| KG-025 | Performance-map oscillation-mode detection | Detecting alternating-residual solver behavior at high loading and switching from Newton to under-relaxed Picard automatically is deferred. v1 reports `NON_CONVERGED` without distinguishing oscillation. | Solver oscillation lands as `NON_CONVERGED` with no sub-code. | v1.1: structured `NON_CONVERGED.OSCILLATION` sub-code. |

## Mean-line implementation gaps (`src/cascade/meanline/`)

| ID | Gap | Why / Status | Resolution |
|----|-----|--------------|------------|
| KG-ML-01 | SR-006 SPEC tolerance `\|σ_Wiesner(Z=100) − σ_Stanitz(Z=100)\| < 1e-3` not literally achievable | Wiesner's published formula uses Z^0.7 in the denominator; Stanitz uses Z^1. At Z = 100, β = 45° the difference is ≈ 0.014. The two formulas share the same Z → ∞ asymptote (σ → 1), and at Z = 10⁶ the difference is < 1e-3. The test in `tests/meanline/test_slip_factor_limits.py` validates the **shared asymptote at Z = 10⁶** rather than the unattainable Z = 100 spec. | v1.1: refine the SPEC SR-006 statement to "shared asymptote at Z → ∞" rather than a finite-Z numerical agreement. |
| KG-ML-02 | CC-1 Eckardt Rotor A π_tt under-predicted with default Wiesner; SPEC-pass requires `calibration_scale=1.05` | Updated by ADAPT-007/008. With the real Aungier eq. 6.51 (wake-mixing) + eq. 6.66 (orifice-flow leakage), the default Wiesner gives π_tt ≈ 1.78 (was 1.74) and `WiesnerSlip(calibration_scale=1.05)` gives π_tt ≈ 1.86 — within SPEC §12 ±1.5 pt of published 1.94 (interpreted as ±0.10 pressure-ratio). The Came & Robinson 1999 §3.2 1.04–1.06 calibration is the accepted standard for Eckardt-class back-swept wheels. | v1.1: ship Busemann (1928) slip closure as additional pluggable option; reconsider Wiesner default after Casey-Robinson wake-mixing analysis. |
| KG-ML-03 | CC-2 Eckardt Rotor O η_tt is characterization-only (impeller-alone reference) | The Aungier eq. 6.51 mixing model scales as Δh_mix ∝ sin²(β₂') (B-07 fix), so radial-bladed Rotor O (β₂'≈90°) sees the *maximum* meridional-deficit mixing loss, not zero. Regardless of that term, the impeller-alone meanline does not model the diffuser + scroll losses included in the published full-stage η_tt ≈ 0.83, so an exact η match is out of scope. π_tt is in close agreement (2.13 vs 2.10). CC-2 η is tracked as characterization, not a pass-gate. | v1.1: add diffuser + scroll loss to the impeller-alone meanline (Aungier Ch. 7 or Casey-Robinson Ch. 9). |
| KG-ML-04 | RIT-1 / RIT-2 exact published geometries not transcribed | NASA TN D-7508 (Whitney-Stewart) and NASA SP-290 Vol 3 (Glassman) include performance-map data tables and detailed geometry tables that were not digitized for v1. The validation tests use **representative** geometries that exercise the same design regime; the published η_ts targets are achieved within ±5 pt but not the strict ±2 pt SPEC tolerance. | v1.1: digitize the exact NASA TN D-7508 Table II and NASA SP-290 Vol 3 worked-example tables into `tests/meanline/data/`. |
| KG-ML-05 | RIT incidence / nozzle-loss split incomplete | The Whitfield-Baines loss model returns a single incidence ζ term that conflates nozzle exit loss with rotor LE incidence. A more accurate model separates the two. | v1.1: explicit nozzle loss + separate rotor incidence per Glassman 1976 NASA TN D-8164. |
| KG-ML-06 | No off-design choke / surge detection in mean-line solver | The solver returns a single design-point result; mass-flow sweeps for performance map are the responsibility of the upstream map generator. The mean-line itself does not flag choke or stall margins. | v1.1: per-point CONVERGED / CHOKED / STALL_SURGE codes returned in the result. |
| KG-ML-07 | Real-gas EOS adapter not yet wired | The mean-line accepts a `PerfectGas` instance only. The SPEC §3.4 NasaMixture / CoolPropFluid adapters are not yet plumbed through. The sCO₂ RIT-4 validation case is therefore deferred. | v1.1: NasaMixture and CoolPropFluid implementations in `cascade.thermo`, consumed by mean-line via duck-typed interface. |
| KG-ML-08 | Daily-Nece Regime III boundary is heuristic | ADAPT-010 ships the full 4-regime selector (Daily-Nece 1960 Fig. 2 / Table 1) with the conventional Owen-Rogers 1989 §2.2 boundary approximations. Regime III (turbulent merged) is mathematically rare in engineering s/R because both `Re > Re_LT_merged` and `Re < Re_MS` must hold simultaneously; the test suite includes a parametric envelope spot-check. | v1.1: digitize the exact D&N Fig. 2 boundaries and add laminar/turbulent transition smoothing. |
| KG-ML-09 | RIT-3 (Wood 1963) and RIT-4 (Sandia sCO₂) have no test files | These cases are listed in SPEC §12 as open-public validation targets but no test files exist in `tests/meanline/`. Additionally, RIT-4 requires the real-gas EOS adapter (KG-ML-07) because it is a sCO₂ turbine. Both were listed as "passes within range" in earlier VALIDATION_REPORT drafts without evidence — this was a documentation defect caught during review. | v1.1: add `tests/meanline/test_rit3_wood1963.py` and `tests/meanline/test_rit4_sandia_sco2.py` after wiring the real-gas EOS adapter. |
| KG-ML-10 | CC-3 (Krain G/3), CC-4 (NASA CC3), CC-5 (VKI) have no test files | These cases are listed in SPEC §12 as validation targets (±2 pt) but no test files exist in `tests/meanline/`. VALIDATION_REPORT drafts incorrectly said "covered as characterization" or "passes within range" without any backing test. This was identified during review as a documentation defect. | v1.1: add `tests/meanline/test_cc3_krain_g3.py`, `test_cc4_nasa_cc3.py`, `test_cc5_vki.py` after the Krain/CC3/VKI geometry parameters are digitized from the published sources. |

## Thermal-fluid network implementation gap (NOT IMPLEMENTED in v1)

| ID | Gap | Why deferred | Resolution |
|----|-----|--------------|------------|
| KG-TFN-01 | `cascade.network` 1D thermal-fluid network module is NOT IMPLEMENTED in v1 | The SPEC §12 lists TFN-1 through TFN-6 as validation cases (Idelchik duct friction, Egli labyrinth seal, NASA disc cavity, Daily-Nece disc friction, secondary-air network, GFSSP cross-tool). However `src/cascade/` has no `network/` directory and `tests/network/` is empty. The SPEC §2 "In v1" bullet for the 1D network, and all 6 TFN validation cases, cannot be verified by any test in CI. The module is referenced only in the `cascade.__init__` docstring. This is not a documentation gap — it is a v1 scope gap that was incorrectly included in the SPEC §12 pass-gate table. | v1.1: implement `cascade.network` (topology DAG, Fanno/Rayleigh ducts, Idelchik K-factors, Egli labyrinth seal, ε-NTU heat exchangers) and add TFN-1 through TFN-6 test files. Until then, all TFN rows are explicitly "not a pass-gate." |

## Axial mean-line solver implementation gap (NOT IMPLEMENTED in v1)

| ID | Gap | Why deferred | Resolution |
|----|-----|--------------|------------|
| KG-AXT-01 | Axial mean-line solver (turbine + compressor) is NOT IMPLEMENTED in v1 | The SPEC §12 lists AXT-1 (Smith 1965), AXT-2 (NASA Rotor 67), AXT-3 (NASA Stage 37), AXC-1 (GE E³ HPC), and AXT-4 (GE E³ HPT informational) as validation targets. However `src/cascade/meanline/` contains only `radial_turbine.py` and `centrifugal_compressor.py` — no axial turbine or axial compressor module exists, and `tests/meanline/` has no axial test files. The SPEC §2 "In v1" bullet for "axial" mean-line, the SolverArchitecture description on the validation page ("Centrifugal compressor + radial turbine + axial"), and all AXT/AXC validation cases cannot be verified by any test. | v1.1: implement `cascade.meanline.axial_turbine` (Kacker-Okapuu with Moustapha shock term) and `cascade.meanline.axial_compressor` (Koch-Smith + Casey). Until then, all AXT/AXC rows are "not a pass-gate" and the "axial" claim in the solver architecture description is aspirational. |

## Rotor-dynamics scope boundary

The rotor-dynamics validation suite uses three classes of reference:

1. **Exact-closed-form synthetic** (RD-5 Jeffcott): rigid bearings, single lumped disk, analytical
   ω_c = √(K/m). These verify the eigensolver and linearization — NOT fidelity to a real machine.
   A pass here means the math is correct, not that the solver handles real bearing dynamics.

2. **Timoshenko-beam FEM vs analytical closed form** (RD-4 Friswell): The beam-FEM is validated
   against Euler-Bernoulli closed-form natural frequencies. Bearings are finite but idealized.
   A pass here means the discretization is correct for well-conditioned geometries.

3. **FEM with calibrated proxy geometry against measured rig data** (RD-3 NASA TM-102368): The
   shaft geometry is a proxy calibrated to hit the published critical speed — not the exact TM
   input deck (KG-RD-01). The bearing K-C coefficients are from the NASA rig tabulation.

**What these rows do NOT validate:** Accuracy for real machines with tilt-pad bearings (KG-007),
fluid-film bearing K-C extracted from the PSOR at arbitrary eccentricity, or rotor geometries
with large L/D or multiple-disk interactions beyond the test cases above. Real-machine validation
requires real bearing dynamic-coefficient data matched to the physical machine. This regime
boundary is documented here so buyers understand the scope.

## Rotor-dynamics implementation gaps (`src/cascade/rotor/`)

| ID | Gap | Why deferred / status | Resolution |
|----|-----|------------------------|------------|
| KG-RD-01 | NASA TM-102368 (RD-3) uses a calibrated proxy rotor | The exact NASA TM input deck (full geometry table) was not transcribed for v1. The proxy reproduces the published 1st forward critical (8,950 rpm) to within ~0.3% by tuning K_b. | v1.1 — transcribe full NASA TM-102368 input deck into `tests/rotor/data/`. |
| KG-RD-02 | ~~Christopherson PSOR damping coefficients use Ocvirk fallback~~ **CLOSED (ADAPT-044 / W-15 / Sprint 5A, 2026-05-26)** | Implemented: eccentricity-rate perturbation method (Lund & Thomsen 1978) now extracts the full 2x2 C tensor from the PSOR Reynolds solution. Two PSOR solves with squeeze-film source term `dh/dt = -vy cos(theta) - vz sin(theta)` yield C_yy, C_yz, C_zy, C_zz for finite bearings (L/D >= 0.3). Ocvirk closed-form retained for L/D < 0.3. Validated within Someya 1989 reference band for L/D=0.5, eps=0.5. | **Closed** |
| KG-RD-03 | Ocvirk nondimensional K differs from some textbooks by ~5x | The Ocvirk K formulation in `journal_bearing.ocvirk_stiffness_damping` follows Childs 1993 Table 4.4 closed forms. Dimensional K is in the canonical 1e8 - 1e10 N/m range; nondimensional `K * c / W` differs from some published tables because the literature uses several conflicting reference scales (Lund 1966 vs Someya 1989 vs Pinkus & Sternlicht 1961). | v1.1 — Port the explicit Someya 1989 tabulated K, C via interpolation and document the conversion between the major nondimensionalizations. |
| KG-RD-04 | Modal truncation residual flexibility not added | The full-dimensional eigenproblem is solved via `scipy.linalg.eig` on the 2N linearized system. Adequate for v1 typical industrial rotors (100-200 lateral DOFs, < 2 s wall time). | v1.1 — Craig-Bampton residual-flexibility correction + ARPACK shift-invert eigensolver for large systems. |
| KG-RD-05 | Materials registry not implemented | `RotorSection.material` is accepted as a string but is not yet resolved through a materials registry. Default E = 200 GPa, nu = 0.3 (AISI 4340 steel) is applied to all sections unless overridden at `build_rotor_model()`. | v1.1 — `cascade.materials` registry with per-material temperature dependence. |
| KG-RD-06 | RD-1 / RD-2 (API 684 Annex B, Childs §5.3) not in test suite | RD-1 requires gated API 684 standard. RD-2 (Childs 1993 §5.3 worked example) is straightforward to add but not transcribed for the v1 ship. The Jeffcott + Friswell + NASA proxy already cover the v1 acceptance bar. | v1.1 -- add Childs §5.3 fixture and the API 684 Annex B test rotor (requires standard purchase). |

## Validation case gaps

| ID | Gap | Why deferred | Status |
|----|-----|--------------|--------|
| KG-101 | RIT-3 MIT Jones thesis | Not in MIT DSpace; not reliably reproducible. Substituted with Wood 1963 ASME 63-AHGT-4 (open public) per SR-009 closure. | Substituted in v1. |
| KG-102 | CC-5 Honeywell SuperCore maps | Aftermarket-digitized; reproducibility fragile. Substituted with VKI Lecture Series radial-compressor (open public) per SR-009. | Substituted in v1. |
| KG-103 | API 684 Annex B test rotor | Gated behind the API standard ($300+ purchase). | RD-1 is gated; users must purchase API 684 to verify. Documented. |
| KG-104 | Capstone published numbers for v1 validation | Capstone datasheets are best-effort public; an actual Capstone engineer could challenge. | CYC-3/4/5 ship within ±1.5 pt (revised tolerance per SR-002). Honest. |
| KG-105 | PW1100G real-engine numbers | Pratt does not publish a definitive cycle deck. | CYC-7 informational only — matches a published digital-twin cycle deck, not the real engine. Documented. |

## Interface / coupling gaps

| ID | Gap | Why deferred | What v1 ships |
|----|-----|--------------|---------------|
| KG-201 | Newton-on-coupled-system for cycle ↔ meanline co-sim | Aitken-accelerated fixed-point is simpler and adequate; Newton-on-coupled is the v1.1 upgrade. | Aitken-accelerated fixed-point on Port deltas. |
| KG-202 | Real-time GPU-accelerated CFD adapter | OpenFOAM stub is the v1 placeholder; GPU is future work. | OpenFOAM CPU stub. |
| KG-203 | Self-hosted enterprise edition with on-premise GPU | Multi-tenant cloud is the v1 deployment target. | Cloud-only. |

## UI / collaboration gaps

| ID | Gap | Why deferred | What v1 ships |
|----|-----|--------------|---------------|
| KG-301 | Mobile / tablet app | Desktop browser is the v1 target. | Responsive web; not mobile-optimized. |
| KG-302 | Offline mode | Cloud-first; offline is a v1.1+ concern. | Online only. |
| KG-303 | Marketplace for community loss models | Citation discipline + git makes community loss models possible; marketplace UX is v1.x. | Loss models are Python plugins; community PRs welcome. |
| KG-PLAT-01 | Real-time multi-user co-editing not implemented (ADAPT-015) | See detailed entry below. | Single-user canvas in v1.0; async git collaboration on the TOML project format. |
| KG-PLAT-02 | Canvas edge-connectivity semantics not validated | The cycle solver infers a fixed series flow path from the component kinds present and never reads `project["edges"]`. A real connectivity validator must understand recuperator dual-port wiring (cold and hot streams cross the same component), and a naive series check would reject the working seed projects. | Edges on the Cycle Canvas are illustrative only. Refusal copy on the Cycle page discloses the kind-inferred flow path and cites this entry; no edge is required (or checked) for a solve. |
| KG-PLAT-03 | Performance map does not follow candidate geometry | The map worker reads a project-level `geometry_params` key that nothing writes and falls back to reference-scale geometry with a matching default grid. Following the candidate handoff's component-level geometry requires candidate-scaled grid and design-point derivation — the reference grid would choke on microturbine-scale machines. | The map page labels its provenance ("computed from reference geometry") so a candidate sent to the cycle is not mistaken for the mapped machine. |
| KG-PLAT-04 | No hosted instance | Cascade runs self-hosted (single-user FastAPI + TOML store). A hosted instance — auth, Postgres-backed multi-user storage, job queues — is the deployment-target architecture and the durable home of the hosted offering. | AGPL self-host is the supported deployment today; `make run` starts the full stack locally. |

### KG-PLAT-01  Real-time collaborative editing not implemented

**v1.0 status: NOT SHIPPED.** The codebase has no `yjs` dependency, no
`@hocuspocus/*` package, no `apps/hocuspocus/` service, no presence-cursor UI,
and no comment-anchoring backend. Earlier drafts of the marketing copy claimed
real-time co-edit as a v1.0 differentiator; ADAPT-015 removes those claims and
relabels the architecture as "v1.1 planned." v1.0 collaboration is
**asynchronous**: the project format is a TOML directory (ADR-017), and two
engineers collaborate via `git` branches and pull requests with clean unified
diffs. This is the same model every modern engineering codebase uses.

**v1.1 plan.** The chosen stack is Yjs CRDT + Hocuspocus + y-react (the
architecture notes capture the full rationale, including why CRDT vs OT and
why Hocuspocus vs Liveblocks/Convex). Required work:

- `apps/hocuspocus/` Node service skeleton — ~3 specialist-days.
- Yjs document schema mapping to the existing Project Pydantic model
  (one Yjs doc per Project; subdocs for cycle graph, design-space filter set,
  comments) — ~2 specialist-days.
- Presence UI on the cycle canvas + design-space scatter (cursors, avatars,
  selection-highlight) — ~1 specialist-day.
- Conflict-resolution UX for non-merging operations (e.g. two users edit the
  same parameter simultaneously; CRDT picks one and the loser sees a toast
  with the diff) — ~1 specialist-day.

**Total: ~7 specialist-days.** Slot reserved at `apps/hocuspocus/` in the §2
monorepo layout (empty in v1.0).

**Honest pitch (v1.0).** Cascade's `.cascade/` TOML directory + `git diff` is
already a step ahead of legacy tools' binary project formats — two
engineers can review each other's designs in a pull request today, which is
impossible against a binary file. Real-time co-edit is a v1.1 upgrade on top
of that foundation, not the foundation itself.

## 3D geometry / mesh-generation gaps (`src/cascade/geometry/`)

| ID | Gap | Why / Status | Resolution |
|----|-----|--------------|------------|
| KG-G-01 | Hub / shroud control points are hardcoded canonical shapes | The first cut of `cascade.geometry` ships a fixed 5-point B-spline hub and shroud (Concepts-NREC / Aungier house style). The geometry design calls for user-manipulable control points and preset profiles. | v1.1: expose `hub_control_points` and `shroud_control_points` fields on `CentrifugalCompressorGeometry` / `RadialTurbineGeometry` so the meanline solver can hand them through and the UI can drag them. |
| KG-G-02 | Blade-angle distribution is a fixed Hermite blend | The mesh generator uses a smooth-step from `β_inlet` to `β_outlet` rather than the user-controllable B-spline in the geometry design. | v1.1: accept a `BladeAngleDistribution` dataclass with a B-spline control set. |
| KG-G-03 | Blade thickness is a fixed bell-curve | The current shape is a single Hicks-Henne-like bump with LE/TE thickness fixed to 8% / 5% of `t_max`. The geometry design calls for NACA-style / user-defined symmetric polynomials. | v1.1: pluggable `BladeThicknessProfile`. |
| KG-G-04 | No lean / sweep on the blade | The lofted surface is "no-lean": pressure and suction sides share the same θ-distribution at hub and shroud. Real impellers may have a small lean for stress / vibration. | v1.1: lean parameter on the geometry dataclass. |
| KG-G-05 | Shroud surface is rendered as an open surface of revolution, not a closed casing | The `with_shroud=True` option emits the cosmetic shroud cup; it's deliberately not part of the watertight volume. The full casing (volute + diffuser walls) is a separate mesh. | This is intentional, not a defect. Documented in `cascade.geometry.impeller_mesh` docstring. |
| KG-G-06 | LumpedDisk visual is a simple thick washer | The `RotorShape` does not carry detailed disk geometry; the mesh generator infers a radius from polar inertia and a thickness from mass at ρ ≈ 4500 kg/m³ (titanium-ish). This produces a recognizable but stylized disc. | v1.1: pass through the actual impeller mesh as a separate scene-graph child instead of approximating it as a disc. |
| KG-G-07 | Volute is log-spiral with circular cross-section only | The geometry design lists 3 volute forms (log-spiral, constant-section, custom spline). v1 ships log-spiral + circular cross-section. | v1.1: constant-section and user-spline cross-sections, twin-volute variants. |
| KG-G-08 | STEP / IGES export needs heavy optional dep | Implemented in ADAPT-033 via `pythonocc-core` (~200 MB compiled OCC C++). Gated behind the `cascade[cad]` extra. **Dependency model:** GLB and STL ship in the base `cascade` install and are always available. STEP, IGES, and fluid-volume STEP require `pip install cascade[cad]` or `conda install -c conda-forge pythonocc-core`. Vanilla installs see a 503 with install hint from the API; the UI probes the CAD health endpoint at page load and greys the STEP/IGES export buttons when the dep is missing. OCC-gated tests in `tests/geometry/test_step_iges_export.py` and `tests/cad/` skip cleanly when the dep is absent — the skip is the correct result, not a failure. The validation page must NOT display STEP/IGES structural-validity tests as unconditionally green; they are "dependency-limited" (pass when OCC installed, expected skip otherwise). Conda is the more reliable install channel; pip wheels can be missing for some Python/OS combos. Current implementation triangulates into per-triangle B-rep faces; B-spline-surface preservation is v2. |
| KG-G-09 | No fillet or radius generation at blade-hub junction | Real impellers have a fillet at the blade root for stress reasons; the mesh generator omits it. The fillet would visually mask the sharp blade-to-hub intersection. | v1.1: fillet radius parameter; trimesh-only fillets via a swept circle along the hub-band edge. |
| KG-G-10 | ~~Mesh generator ignored `blade_height_outlet` / `blade_height_inlet`~~ **CLOSED (2026-06-10)** | The shroud curve terminated a bare tip-clearance from the hub at the radial end of the channel, collapsing the exit passage to ~0.4 mm regardless of the design b2 (b1 at the RIT inlet) — every impeller rendered as a bladeless dome with spiral ridges, and the TurboGrid / fluid-volume exports carried the same closed exit. Fixed: `default_shroud_control_points` takes a required `blade_height_radial`; at a radial station the passage height and the clearance offset are both axial, so the shroud now ends at full radius, axially offset by `b + tip_clearance` from the hub exit plane. Pinned by `tests/geometry/test_passage_height.py` (curve- and mesh-level, all LODs, both machine classes). | **Closed** |
| KG-G-11 | Machinable blade-thickness floor is not fed back into the mean-line losses | The mesh generators floor the bell-curve blade thickness at the 5-axis machinable minimum (`manufacturability.limits` — 1.0 mm peak for milled CC impellers, so small wheels get realistically thick blades instead of un-millable foil). The mean-line solver, however, carries no blade-blockage or thickness term (Aungier loss set as shipped), so for wheels under ~65 mm exit diameter the SOLVED flow area slightly overstates the as-meshed flow area. The manufacturability gate, the mesh, the exports, and the rules all use the same floored thickness — only the aero solve ignores it. | v1.1: blade-blockage term in the centrifugal mean-line (Aungier 2000 §5.5 throat blockage), driven by the same shared thickness helper. |

## Documentation gaps

| ID | Gap | Why deferred | What v1 ships |
|----|-----|--------------|---------------|
| KG-401 | Full theory manual in LaTeX | Theory content exists in markdown; LaTeX rendering is a polish task. | Markdown theory pages in docs/. |
| KG-402 | Video tutorials | Written tutorials ship in v1. | Written tutorials + README demo script. |

---

## How to add to this list

If you discover a gap during build or use, add it here with a stable ID (KG-NNN), severity, and target release. Don't bury gaps in TODOs in source code.
