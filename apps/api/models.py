"""Pydantic schemas for the Cascade API.

These mirror the canonical cascade types but are JSON-friendly. The
quantity-with-unit pattern is preserved as `{"value": float, "unit": str}`
so the frontend can render the unit and reason about conversions; the
server converts to/from `cascade.units.Quantity` at the boundary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


class QuantityModel(BaseModel):
    """A dimensioned quantity, e.g. {"value": 4.0, "unit": "kg/s"}."""

    value: float
    unit: str

    model_config = ConfigDict(json_schema_extra={"example": {"value": 101.325, "unit": "kPa"}})


# ---------------------------------------------------------------------------
# Cycle components
# ---------------------------------------------------------------------------


class PortModel(BaseModel):
    """JSON shape of a cascade `Port`."""

    pressure_total: QuantityModel
    temperature_total: QuantityModel
    mass_flow: QuantityModel
    composition: Dict[str, float] = Field(
        default_factory=dict, description="Mass-fractions, keyed by Species enum value."
    )
    rotational_speed: Optional[QuantityModel] = None
    swirl_ratio: float = 0.0


ComponentKind = Literal[
    "Inlet",
    "Outlet",
    "Compressor",
    "Turbine",
    "Burner",
    "Recuperator",
    "Intercooler",
    "Mixer",
    "Splitter",
    "ConstantPressureLoss",
    # ADAPT-034: shaft component (multi-spool). Must mirror the UI palette's
    # 'shaft' kind so drag-drop from the palette doesn't 422 at POST.
    "Shaft",
]


class ComponentModel(BaseModel):
    """A node on the cycle canvas."""

    id: str
    kind: ComponentKind
    name: str
    # Free-form parameter bag — strict schema is enforced at solve-time.
    # Values can be numbers, quantities, strings, or booleans.
    params: Dict[str, Any] = Field(default_factory=dict)
    # Layout hints for the canvas (purely UI metadata)
    position: Dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "y": 0.0})


class EdgeModel(BaseModel):
    """A connection between two component ports on the canvas."""

    id: str
    source: str
    target: str
    # Source/target port labels (e.g. "out", "cold_in", "hot_out")
    source_port: str = "out"
    target_port: str = "in"


class ComponentsResponse(BaseModel):
    components: List[ComponentModel]
    edges: List[EdgeModel]


# ---------------------------------------------------------------------------
# Cycle solve
# ---------------------------------------------------------------------------


class CycleSolveResult(BaseModel):
    """Subset of `CycleResult` suitable for JSON."""

    converged: bool
    outer_iterations: int
    residual_norm: float
    thermal_efficiency: float
    electrical_efficiency: float
    net_shaft_work: QuantityModel
    electrical_output: QuantityModel
    specific_work: QuantityModel
    heat_input: QuantityModel
    fuel_mass_flow: QuantityModel
    ports: Dict[str, PortModel] = Field(default_factory=dict)
    shaft_work_components: Dict[str, QuantityModel] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


ProjectKind = Literal["microturbine", "sco2", "aero", "blank"]
WorkingFluid = Literal["air", "co2_supercritical", "helium", "custom"]


class ProjectSummary(BaseModel):
    id: str
    name: str
    kind: ProjectKind
    working_fluid: WorkingFluid
    description: str = ""
    created_at: datetime
    updated_at: datetime
    last_run_status: Optional[str] = None


class ProjectDetail(ProjectSummary):
    components: List[ComponentModel] = Field(default_factory=list)
    edges: List[EdgeModel] = Field(default_factory=list)
    boundary_conditions: Dict[str, Any] = Field(default_factory=dict)
    settings: Dict[str, Any] = Field(default_factory=dict)


class ProjectCreateRequest(BaseModel):
    name: str
    template: ProjectKind = "blank"
    description: str = ""


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    boundary_conditions: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Component CRUD
# ---------------------------------------------------------------------------


class ComponentCreateRequest(BaseModel):
    kind: ComponentKind
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    position: Dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "y": 0.0})


class ComponentUpdateRequest(BaseModel):
    name: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    position: Optional[Dict[str, float]] = None


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


JobKind = Literal["cycle", "explore", "map", "analysis", "rotor"]
JobStatus = Literal["queued", "running", "done", "failed", "cancelled"]


class JobModel(BaseModel):
    id: str
    project_id: str
    kind: JobKind
    status: JobStatus
    progress: float = 0.0
    message: str = ""
    created_at: datetime
    updated_at: datetime
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    # Result is set when status == "done", and also on a refused run
    # (status == "failed" with error=None): the refusal keeps the
    # structured failure envelope under result["failure"] so the UI can
    # render the explanation. A crash (status == "failed" with error set)
    # carries no result. Shape depends on kind.
    result: Optional[Dict[str, Any]] = None


class JobAcceptedResponse(BaseModel):
    job_id: str


# ---------------------------------------------------------------------------
# Explore
# ---------------------------------------------------------------------------


class ParameterRangeModel(BaseModel):
    min: float
    max: float
    unit: str
    scale: Literal["linear", "log"] = "linear"


class ExploreRequest(BaseModel):
    n_samples: int = 256
    seed: int = 0
    parallelism: int = 1
    parameter_ranges: Dict[str, ParameterRangeModel] = Field(default_factory=dict)
    primary_objective: str = "eta_tt"
    minimize_primary: bool = False


class CandidateModel(BaseModel):
    id: str
    job_id: str
    # U8: candidates are project-scoped — the in-memory dicts have always
    # carried project_id (the explore worker writes it); exposing it lets
    # the candidate detail page guard cross-project routes client-side.
    project_id: Optional[str] = None
    index: int
    params: Dict[str, Any] = Field(default_factory=dict)
    objectives: Dict[str, float] = Field(default_factory=dict)
    constraints: Dict[str, bool] = Field(default_factory=dict)
    status: str = "VALID"
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Candidate geometry handoff (U8)
# ---------------------------------------------------------------------------


class MergedGeometryResponse(BaseModel):
    """The full merged geometry a candidate actually resolves to.

    Built by the same ``build_cc_geometry(sample=candidate.params)`` helper
    the explore evaluator uses (key rename, r2-scaling of inducer
    dimensions, candidate rpm) — NOT the bare 3 sampled params. This is the
    exact key set "Send to cycle" writes into the Compressor component's
    ``geometry_params`` bag, so the detail page's parameter table and the
    cycle co-simulation can never disagree.
    """

    candidate_id: str
    machine_class: str
    # Plain SI floats keyed by geometry dataclass field name.
    geometry_params: Dict[str, float] = Field(default_factory=dict)
    # Candidate design point: mass_flow_kg_per_s, rpm, pressure_total_Pa,
    # temperature_total_K (floats) + fluid (str).
    operating_point: Dict[str, Any] = Field(default_factory=dict)
    # Geometry field names that were directly driven by the Sobol' sample
    # (the rest are r2-scaled / reference defaults).
    sampled_keys: List[str] = Field(default_factory=list)
    meanline_rpm_rpm: float
    # Meridional (z, r) polylines in metres, sampled from the SAME hub /
    # shroud B-splines the mesh generator and the vendor exports use —
    # named-contour dict: {"hub": [[z, r], ...], "shroud": [[z, r], ...]}.
    # Empty when cascade.geometry is unavailable (dev mode).
    meridional: Dict[str, List[List[float]]] = Field(default_factory=dict)


class SendToCycleRequest(BaseModel):
    """Body for POST /api/candidates/{cid}/send-to-cycle."""

    project_id: str
    # Default-on alignment: explore candidates are built at a conservative
    # reference tip speed (PR ≈ 1.8) while the seed cycles impose higher
    # pressure ratios — geometry+rpm alone would run the co-sim deep
    # off-design.
    align_operating_point: bool = Field(
        default=True,
        description=(
            "Align the cycle's operating point to the candidate's design "
            "point (default on). When true, the handoff also writes the "
            "compressor pressure_ratio, the project boundary-condition "
            "mass flow (mirrored onto the Inlet component), and a "
            "consistent Turbine pressure_ratio derived from the project's "
            "inlet/recuperator/burner/exhaust pressure-drop chain. Without "
            "alignment only geometry + rpm are written and a live-meanline "
            "refusal is the expected outcome on the default seeds (the "
            "seed operating point runs the candidate geometry deep "
            "off-design)."
        ),
    )


class SendToCycleResponse(BaseModel):
    project_id: str
    candidate_id: str
    component_id: str
    geometry_params: Dict[str, float] = Field(default_factory=dict)
    meanline_rpm_rpm: float
    aligned: bool
    # Present only when aligned=True.
    pressure_ratio: Optional[float] = None
    mass_flow_kg_per_s: Optional[float] = None
    # The consistent Turbine pressure_ratio written alongside the aligned
    # compressor PR (derived through the project's pressure-drop chain).
    # None when not aligned or when the canvas has no Turbine component.
    turbine_pressure_ratio: Optional[float] = None


class PinCandidateRequest(BaseModel):
    """Body for POST /api/candidates/{cid}/pin."""

    project_id: str


class PinCandidateResponse(BaseModel):
    project_id: str
    active_candidate_id: str
    # The params snapshot persisted under settings.pinned_candidates[cid].
    snapshot: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Performance map
# ---------------------------------------------------------------------------


class MapRequest(BaseModel):
    speedline_rpms: List[float] = Field(default_factory=lambda: [50000.0, 75000.0, 100000.0])
    mass_flows: List[float] = Field(default_factory=lambda: [0.1, 0.2, 0.3, 0.4, 0.5])
    parallelism: int = 1
    # G2 / Item 1: corrected speedline and mass-flow sweeps.
    # Supply either ``speedline_rpms`` + ``mass_flows`` (dimensional) OR
    # ``corrected_speedline_rpms`` + ``corrected_mass_flows`` (corrected) — not both.
    # The router uses the same inlet conditions as the project boundary conditions
    # to translate corrected → dimensional before building the grid.
    corrected_speedline_rpms: Optional[List[float]] = Field(
        default=None,
        description=(
            "Corrected speedline values [rpm]: N_corr = N_dim / √(T₀₁/T_ref). "
            "Supply this OR speedline_rpms — not both."
        ),
    )
    corrected_mass_flows: Optional[List[float]] = Field(
        default=None,
        description=(
            "Corrected mass-flow values [kg/s]: ṁ_corr = ṁ_dim × √(T₀₁/T_ref) / (P₀₁/P_ref). "
            "Supply this OR mass_flows — not both."
        ),
    )
    # Reference inlet conditions for corrected → dimensional conversion.
    # Must be supplied when corrected_speedline_rpms or corrected_mass_flows are used.
    inlet_total_pressure_Pa: Optional[float] = Field(
        default=None,
        description="Inlet total pressure [Pa] for corrected → dimensional conversion.",
    )
    inlet_total_temperature_K: Optional[float] = Field(
        default=None,
        description="Inlet total temperature [K] for corrected → dimensional conversion.",
    )
    reference_temperature_K: float = Field(
        default=288.15,
        gt=0,
        description=(
            "Reference temperature for corrected-variable convention [K]. "
            "Default: ISA 288.15 K. Must be > 0 (C-3 refusal boundary)."
        ),
    )
    reference_pressure_Pa: float = Field(
        default=101_325.0,
        gt=0,
        description=(
            "Reference pressure for corrected-variable convention [Pa]. "
            "Default: ISA 101 325 Pa. Must be > 0 (C-3 refusal boundary)."
        ),
    )


# ---------------------------------------------------------------------------
# Corrected operating-point helpers (G2 / Item 1)
# ---------------------------------------------------------------------------


class CorrectedOperatingPoint(BaseModel):
    """Corrected-form operating point (dimensionless-like variables).

    A buyer may supply either dimensional OR corrected operating-point variables.
    Supplying both is overconstrained and rejected with 422 + error code
    ``OVERCONSTRAINED_OPERATING_POINT``.

    Convention (ISA sea-level standard, used by NASA and Cascade by default):

        ṁ_dim  = ṁ_corr × (P₀₁ / P_ref) / √(T₀₁ / T_ref)
        N_dim  = N_corr × √(T₀₁ / T_ref)

    Reference: Saravanamuttoo et al., "Gas Turbine Theory" 7th ed., Ch. 4
    (eqs. 4.16–4.17). NASA benchmarks (e.g. TN D-7508) tabulate corrected
    variables using T_ref = 288.15 K, P_ref = 101 325 Pa unless the source
    explicitly states otherwise. Supply ``reference_temperature_K`` and
    ``reference_pressure_Pa`` to override the convention.
    """

    # Corrected mass flow: ṁ_corr = ṁ_dim × √(T₀₁/T_ref) / (P₀₁/P_ref)  [kg/s]
    corrected_mass_flow_kg_s: Optional[float] = Field(
        default=None,
        description=(
            "Corrected mass flow [kg/s]: ṁ_corr = ṁ_dim × √(T₀₁/T_ref) / (P₀₁/P_ref). "
            "Supply this OR mass_flow_kg_per_s in operating_point — not both."
        ),
    )
    # Corrected rotational speed: N_corr = N_dim / √(T₀₁/T_ref)  [rpm]
    corrected_rotational_speed_rpm: Optional[float] = Field(
        default=None,
        description=(
            "Corrected rotational speed [rpm]: N_corr = N_dim / √(T₀₁/T_ref). "
            "Supply this OR rpm in operating_point — not both."
        ),
    )
    # Reference conditions (ISA sea-level standard by default)
    # C-3 constraint: gt=0 prevents division-by-zero inside _corrected_to_dimensional()
    # (which computes sqrt(T₀₁/T_ref) and P₀₁/P_ref). A zero or negative reference
    # temperature would cause ZeroDivisionError inside the worker, returning HTTP 200
    # with an embedded error — the constraint makes it a synchronous 422 instead.
    reference_temperature_K: float = Field(
        default=288.15,
        gt=0,
        description=(
            "Reference temperature for the corrected-variable convention [K]. "
            "Must be > 0 K (physically: absolute temperature). "
            "Default: 288.15 K (ISA sea-level, used by NASA benchmarks). "
            "Alternative: 298.15 K (25 °C / 1 bar), 273.15 K (0 °C / 1 atm). "
            "Zero or negative values are rejected with HTTP 422 "
            "INVALID_REFERENCE_CONDITIONS (C-3 refusal boundary)."
        ),
    )
    reference_pressure_Pa: float = Field(
        default=101_325.0,
        gt=0,
        description=(
            "Reference pressure for the corrected-variable convention [Pa]. "
            "Must be > 0 Pa (physically: absolute pressure). "
            "Default: 101 325 Pa (ISA sea-level). "
            "Alternative: 100 000 Pa (1 bar, used by some European references). "
            "Zero or negative values are rejected with HTTP 422 "
            "INVALID_REFERENCE_CONDITIONS (C-3 refusal boundary)."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "corrected_mass_flow_kg_s": 0.15,
                "corrected_rotational_speed_rpm": 82000.0,
                "reference_temperature_K": 288.15,
                "reference_pressure_Pa": 101325.0,
            }
        }
    )


# ---------------------------------------------------------------------------
# Analysis (mean-line)
# ---------------------------------------------------------------------------


class AnalysisRequest(BaseModel):
    candidate_id: Optional[str] = None
    machine_class: Literal["radial_turbine", "centrifugal_compressor"] = "radial_turbine"
    loss_model: str = "whitfield-baines-radial-v1"
    geometry: Dict[str, Any] = Field(default_factory=dict)
    operating_point: Dict[str, Any] = Field(default_factory=dict)
    # Public independent variable (F1 / Audit C remaining issue).
    # When supplied, the radial-turbine solver uses this static pressure as the
    # outlet boundary condition (exducer exit).  If omitted the solver uses its
    # internally derived static pressure (current default — appropriate for a
    # free-discharge case).
    #
    # Convention: SI Pascals. Published benchmark tables (e.g. NASA TN D-7508
    # Table II) often list corrected static pressure at the exducer exit; supply
    # that value here to reproduce η_ts against a specific test-point static BC.
    #
    # Applies only to radial_turbine solves. Silently ignored for
    # centrifugal_compressor (which has no analogous public outlet-static BC).
    outlet_pressure_static_Pa: Optional[float] = Field(
        default=None,
        description=(
            "Outlet static pressure boundary condition for radial-turbine "
            "solves [Pa]. When supplied, η_ts is computed against this "
            "externally specified static pressure rather than the internally "
            "derived value. Omit for a free-discharge solve."
        ),
    )
    # G2 / Item 1: corrected operating-point variables.
    # The buyer may supply corrected mass flow and corrected rotational speed
    # instead of (or as an alternative to) the dimensional values in
    # `operating_point`.  The router translates corrected → dimensional before
    # calling the solver.
    corrected_operating_point: Optional[CorrectedOperatingPoint] = Field(
        default=None,
        description=(
            "Corrected operating-point variables. Supply this OR "
            "mass_flow_kg_per_s / rpm in operating_point — not both. "
            "See CorrectedOperatingPoint for the conversion convention."
        ),
    )
    # H1 / Item 1: inverse-solve mode for radial turbines.
    # When supplied, the solver iterates mass flow to find the value that
    # produces the target total-to-static pressure ratio at the given speed.
    # This is a 1-D root-find (scipy.optimize.brentq) wrapping the existing
    # forward solver.  Applies only to radial_turbine solves.
    #
    # Supplying both inverse_solve_pr_ts_target AND mass_flow_kg_per_s in
    # operating_point is overconstrained and rejected with 422
    # OVERCONSTRAINED_OPERATING_POINT.
    inverse_solve_pr_ts_target: Optional[float] = Field(
        default=None,
        description=(
            "Inverse-solve mode for radial-turbine solves: find the mass flow "
            "that produces this total-to-static pressure ratio at the given "
            "rotational speed. The solver iterates m_dot using brentq. "
            "Supply rotational_speed_rpm (dimensional) or corrected_rotational_speed_rpm "
            "in corrected_operating_point — but NOT mass_flow_kg_per_s (overconstrained). "
            "Applies only to machine_class=radial_turbine. "
            "Bracket search range: [m_dot_min, m_dot_max] from operating_point "
            "or defaults [0.001, 100.0] kg/s. "
            "Reference: Whitney & Stewart 1974 NASA TN D-7508 — many speed-line "
            "operating points are defined at a specified PR_ts."
        ),
    )
    # H1 / Item 2: Wiesner slip-factor calibration scale for centrifugal
    # compressor solves.
    # When supplied, WiesnerSlip(calibration_scale=wiesner_calibration_scale)
    # is used instead of the default WiesnerSlip(calibration_scale=1.0).
    #
    # Citation: Came & Robinson 1999 §3.2 recommend scale=1.05 for back-swept
    # high-performance impellers (Eckardt-class, β₂' ~ 55–65°). The default
    # (1.0) is the unmodified Wiesner (1967) formula.
    #
    # C-2 constraint: gt=0 prevents negative/zero values that cause WiesnerSlip
    # to silently produce σ=0 (wrong physics, no error). le=2.0 prevents absurd
    # values. Came-Robinson 1999 §3.2 report values in [1.0, 1.10]; the broader
    # (0, 2] range allows experimental calibration beyond the Came-Robinson range.
    #
    # Applies only to centrifugal_compressor solves. Silently ignored for
    # radial_turbine (which has no Wiesner slip factor).
    wiesner_calibration_scale: Optional[float] = Field(
        default=None,
        gt=0,
        le=2.0,
        description=(
            "Wiesner (1967) slip-factor empirical calibration multiplier for "
            "centrifugal compressor solves. When supplied, overrides the default "
            "calibration_scale=1.0 on WiesnerSlip. "
            "Came & Robinson 1999 §3.2 recommend 1.05 for back-swept Eckardt-class "
            "wheels (30° back-sweep, β₂' ~ 60° from tangential). "
            "Default (None / omitted): calibration_scale=1.0 (unmodified Wiesner). "
            "Accepted range: (0, 2.0]. Values in [1.0, 1.10] are typical per "
            "Came-Robinson 1999 §3.2; the broader (0, 2] range allows experimental "
            "calibration. Negative, zero, and absurd values (e.g. 100.0) are rejected "
            "with HTTP 422 (C-2 refusal boundary). "
            "Applies only to machine_class=centrifugal_compressor."
        ),
    )


# ---------------------------------------------------------------------------
# Rotor
# ---------------------------------------------------------------------------


class RotorRequest(BaseModel):
    analysis: Literal["lateral", "torsional", "critical_speed_map", "campbell", "unbalance"] = (
        "lateral"
    )
    speed_range_rpm: List[float] = Field(default_factory=lambda: [1000.0, 60000.0])
    n_modes: int = 6
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    disks: List[Dict[str, Any]] = Field(default_factory=list)
    bearings: List[Dict[str, Any]] = Field(default_factory=list)
    # W-14: blade counts from meanline result (one entry per blade row).
    # Used to auto-build the Campbell engine-order list (blade-pass frequencies).
    blade_counts: List[int] = Field(
        default_factory=list,
        description=(
            "Blade counts for each blade row (one integer per row). "
            "Each value N adds N× to the Campbell engine-order list. "
            "Ignored when engine_orders is supplied explicitly."
        ),
    )
    # W-14: explicit engine-order override. When provided, overrides auto-computed
    # list (1×, 2×, plus blade-pass frequencies from blade_counts).
    engine_orders: Optional[List[float]] = Field(
        default=None,
        description=(
            "Explicit engine-order list for the Campbell diagram. "
            "When supplied, blade_counts is ignored. "
            "When omitted, auto-computed as [1.0, 2.0] + blade-pass orders."
        ),
    )


# ---------------------------------------------------------------------------
# Loss-model catalogue / validation
# ---------------------------------------------------------------------------


class LossModelInfo(BaseModel):
    name: str
    machine_class: str
    citation: str
    description: str = ""
    scale_factors: Dict[str, float] = Field(default_factory=dict)
    validity_envelope: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Plugin (custom loss model) management
# ---------------------------------------------------------------------------


class PluginLossModelInfo(BaseModel):
    """Public metadata for a registered LossModel plugin.

    Returned by `GET /api/projects/{id}/loss-models`. The frontend uses
    this to populate the Properties Panel "Loss model" dropdown and the
    Settings page "Installed plugins" list.
    """

    name: str
    origin: Literal["builtin", "user"]
    applicable_machine_classes: List[str] = Field(default_factory=list)
    description: str = ""
    citation: str = ""
    author: str = ""
    version: str = ""


class PluginUploadResponse(BaseModel):
    """Returned by POST /api/projects/{id}/loss-models/upload.

    Echoes the loaded class so the client can immediately surface
    "Installed: <name>" in the UI.
    """

    plugin: PluginLossModelInfo
    stored_path: str
    message: str = "Plugin loaded and registered."


class ActiveLossModelResponse(BaseModel):
    """Returned by POST /api/projects/{id}/loss-models/{name}/select."""

    project_id: str
    active_loss_model: str


class ValidationCase(BaseModel):
    id: str
    source: str
    tolerance: str
    result: str
    status: str
    category: str
