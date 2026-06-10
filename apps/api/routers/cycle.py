"""Cycle solver routes.

Builds a cascade `RecuperatedBraytonSpec` from the project's component
parameter bag and runs the solver on a worker thread. Progress is
streamed via SSE.

## Air-standard (ideal Brayton) mode — public flag (F1)

Set ``air_standard: true`` in the project's ``settings`` dict to engage the
textbook air-standard ideal Brayton mode.  When the flag is present and True:

- The cycle solver uses ``IdealGasFluid`` (calorically perfect, constant
  cp = 1005 J/(kg·K), γ = 1.4 — matching Çengel & Boles 9th ed., §9-5).
- All burner components in the project are forced to ``air_standard=True``
  (no composition shift across heat addition).
- The closed-form thermal efficiency η_th = 1 − PR^(−(γ−1)/γ) holds within
  numerical precision.  This is the basis for CYC-1 and CYC-2 validation.

When the flag is absent or False the solver uses ``NasaFluid`` (or
``CoolPropPureFluid`` for pure-fluid working media), which is the production
default for real-gas combustion-products Brayton cycles.

Buyer reproduction path (HTTP API):
  1. Create a project via ``POST /api/projects`` (or use any existing project).
  2. Update the project settings: ``PATCH /api/projects/{id}``
     with ``{"settings": {"air_standard": true}}``.
  3. Solve: ``POST /api/projects/{id}/cycle/solve``.
  4. Compare ``result.thermal_efficiency`` to the closed form
     ``1 - PR^(-(γ-1)/γ)``.

See also: ``tests/integration/test_air_standard_http.py`` for the
regression test that exercises both paths (HTTP + Python SDK).

Reference: Çengel, Y., Boles, M., *Thermodynamics: An Engineering Approach*
9th ed., McGraw-Hill, 2019, §9-5 (simple Brayton), §9-7 (recuperated Brayton).
SPEC_SHEET §12 CYC-1 / CYC-2 tolerance: η_th within ±0.1 pt (simple),
±0.2 pt (recuperated).
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Any, Dict, List, NoReturn, Optional

from fastapi import APIRouter, HTTPException

from deps import get_project_or_404
from jobs import (
    Job,
    JobRefusal,
    publish_event,
    register_job,
    report_progress,
    run_in_worker,
)
from models import JobAcceptedResponse


log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/cycle", tags=["cycle"])


def _save_last_run_status(project_id: str) -> None:
    """Persist the ``last_run_status`` badge, tolerating disk failure.

    The terminal worker paths (refusal / non-converged / converged) flush
    the badge with ``PROJECTS.save``. An ``OSError`` here (disk full,
    permissions) must never propagate: it would reach ``run_in_worker``'s
    generic handler and reclassify a design refusal — or a CORRECT
    converged result — as a class-3 crash. The badge not persisting is far
    less harmful than misclassifying the run, so log and continue.
    """
    # Late import mirrors the worker: tests monkeypatch ``jobs.PROJECTS``.
    from jobs import PROJECTS

    try:
        PROJECTS.save(project_id)
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "Could not persist last_run_status for project %s: %s",
            project_id,
            exc,
        )


class MissingRequiredComponents(ValueError):
    """Raised by ``_build_recuperated_spec`` when the canvas lacks the
    minimum component set for a Brayton cycle.

    ``missing`` lists only the component kinds actually absent, so the
    refusal message can name exactly what the user has to add (not always
    all three). ``str(exc)`` is the plain-English job message.
    """

    CAUSE_CODE = "MISSING_REQUIRED_COMPONENTS"

    def __init__(self, missing: List[str]) -> None:
        self.missing = list(missing)
        super().__init__(
            "Cycle canvas is missing required components: "
            + ", ".join(self.missing)
            + "."
        )


class GeometryParamsIncomplete(ValueError):
    """Raised by the rotor geometry builders when ``geometry_params`` is
    ATTACHED to the component but missing required keys — or carrying
    non-finite (NaN / ±Inf) values on required keys.

    U9 doctrine (ADAPT-045 — supersedes the W-03 graceful-degradation rule
    for the attached-but-invalid case): a partial geometry bag is a
    user-input problem the solver must refuse, never silently paper over
    with constant-η — refusal-over-guess (SPEC_SHEET §13). A NaN/Inf
    dimension is the same class of problem as a missing one (no
    trustworthy η can come from it), so it travels the same refusal,
    named distinctly as non-finite. Geometry that is entirely ABSENT
    still falls back to constant η; that fallback is surfaced via the
    result payload's ``requested_efficiency_modes`` /
    ``efficiency_fallbacks``.

    The ``code`` attribute mirrors ``RegimeOutOfValidity.code`` so the
    worker's ``_refusal_cause_code`` picks it up automatically.
    """

    CAUSE_CODE = "GEOMETRY_PARAMS_INCOMPLETE"

    def __init__(
        self,
        component_kind: str,
        missing: List[str],
        non_finite: Optional[List[str]] = None,
    ) -> None:
        self.component_kind = component_kind
        self.missing = list(missing)
        self.non_finite = list(non_finite or [])
        problems: List[str] = []
        if self.missing:
            problems.append(
                "missing required field(s): " + ", ".join(self.missing)
            )
        if self.non_finite:
            problems.append(
                "non-finite (NaN/Inf) value(s) on required field(s): "
                + ", ".join(self.non_finite)
            )
        super().__init__(
            f"{component_kind} geometry_params is attached but has "
            + "; ".join(problems)
            + "."
        )
        self.code = self.CAUSE_CODE
        self.suggestions = [
            "Re-send the geometry from a candidate detail page in Flow Path — 'Send to cycle' writes the full key set.",
            "Or detach the geometry from this component; with no geometry attached the solve falls back to constant isentropic η (flagged in the result).",
        ]


class BurnerSpecInvalid(ValueError):
    """Raised by ``_build_recuperated_spec`` when the Burner params bag
    cannot yield exactly one valid specification.

    Covers the degenerate fuel-mass-flow bags (U7): ``spec_mode ==
    "fuel_mass_flow"`` with no fuel value, or a value that is zero,
    negative, or NaN — plus the symmetric outlet-temperature-mode bag with
    no TIT. These are user-input problems, so they classify design-kind
    (friendly explanation + suggestions), never as a software bug with a
    traceback.

    The ``code`` attribute mirrors ``RegimeOutOfValidity.code`` so the
    worker's ``_refusal_cause_code`` picks it up automatically.
    """

    CAUSE_CODE = "BURNER_SPEC_INVALID"

    def __init__(self, message: str, suggestions: List[str]) -> None:
        super().__init__(message)
        self.code = self.CAUSE_CODE
        self.suggestions = list(suggestions)


def _q(d: Dict[str, Any]):
    """Convert {value, unit} to a cascade Quantity."""

    from cascade.units import Q

    return Q(float(d["value"]), str(d["unit"]))


def _component_by_kind(project: Dict[str, Any], kind: str) -> Optional[Dict[str, Any]]:
    for c in project.get("components", []):
        if c.get("kind") == kind:
            return c
    return None


def _normalise_efficiency_mode(raw: str) -> str:
    """Map the UI's efficiency_mode strings to the solver's EfficiencyMode literal.

    The properties panel uses "isentropic" (human-readable) while the Python
    component dataclass uses "constant" as the backward-compatible default.
    All three modes are accepted; unknown values fall back to "constant".

    Mapping:
      "isentropic"   → "constant"   (lumped η = efficiency_isentropic value)
      "polytropic"   → "polytropic" (constant in v1; polytropic wiring deferred)
      "live_meanline"→ "live_meanline" (Aitken co-sim loop — W-03 / ADAPT-036)
    """
    _MAP = {
        "isentropic": "constant",
        "constant": "constant",
        "polytropic": "polytropic",
        "live_meanline": "live_meanline",
    }
    return _MAP.get(str(raw), "constant")


def _requested_efficiency_modes(project: Dict[str, Any]) -> Dict[str, str]:
    """Map rotor component name → the normalised efficiency mode the user's
    params REQUESTED, before any fallback.

    The spec builder downgrades ``live_meanline`` to ``constant`` when no
    geometry is attached, so the result payload's ``efficiency_modes``
    (read back from the built spec) records only the ACTUAL mode. Comparing
    this map against it is how callers detect the fallback — U9 / ADAPT-045:
    the fallback is surfaced, never silent.
    """
    out: Dict[str, str] = {}
    for c in project.get("components", []) or []:
        if c.get("kind") not in ("Compressor", "Turbine"):
            continue
        raw = str(c.get("params", {}).get("efficiency_mode", "isentropic"))
        out[str(c.get("name", c.get("id", "?")))] = _normalise_efficiency_mode(raw)
    return out


def _resolve_burner_spec_mode(bp: Dict[str, Any]) -> str:
    """Resolve which side of the burner energy balance the user pinned.

    Component PATCH is merge-only, so a bag that has flipped modes once
    holds BOTH ``outlet_temperature`` and ``fuel_mass_flow`` forever;
    ``spec_mode`` is the discriminator (default ``outlet_temperature``).
    Retaining the inactive value is intentional — flipping back restores
    it (pinned by ``test_burner_fuel_mode.py``).

    Legacy bags that predate ``spec_mode`` carry exactly one of the two
    value keys, so when ``spec_mode`` is absent we infer the mode from
    whichever key is present (default-mode inference). A bag with both
    keys and no ``spec_mode`` keeps the historical behaviour:
    outlet-temperature mode.
    """
    mode = bp.get("spec_mode")
    if mode in ("outlet_temperature", "fuel_mass_flow"):
        return str(mode)
    if "fuel_mass_flow" in bp and "outlet_temperature" not in bp:
        return "fuel_mass_flow"
    return "outlet_temperature"


def _burner_fuel_mass_flow_quantity(bp: Dict[str, Any]):
    """Extract + validate the fuel mass flow for a fuel-mode Burner bag.

    Raises ``BurnerSpecInvalid`` (design-class) for degenerate bags: the
    key is absent, or the value is zero / negative / NaN. Refusing here —
    before the Burner constructor — keeps user-input problems out of the
    bug-classified traceback path (U7 / R8).
    """
    import math

    from cascade.units import Q

    _SUGGESTIONS = [
        "Set a positive fuel mass flow in the Burner's properties (a 30 kW-class microturbine burns roughly 0.002 kg/s of natural gas).",
        "Or switch the Burner's spec mode back to 'Outlet T (TIT)' to pin the turbine inlet temperature instead.",
    ]
    raw = bp.get("fuel_mass_flow")
    if raw is None:
        raise BurnerSpecInvalid(
            "Burner is in fuel-mass-flow mode but no fuel mass flow is set.",
            _SUGGESTIONS,
        )
    try:
        if isinstance(raw, dict):
            fuel_q = _q(raw)
        else:
            fuel_q = Q(float(raw), "kg/s")
        fuel_si = float(fuel_q.to("kg/s").magnitude)
    except Exception as exc:
        raise BurnerSpecInvalid(
            f"Burner fuel mass flow could not be read as a quantity: {raw!r}.",
            _SUGGESTIONS,
        ) from exc
    if math.isnan(fuel_si) or math.isinf(fuel_si) or fuel_si <= 0.0:
        raise BurnerSpecInvalid(
            f"Burner fuel mass flow must be a positive, finite number; "
            f"got {fuel_si} kg/s. Zero fuel means no heat addition — the "
            f"cycle would have nothing to expand.",
            _SUGGESTIONS,
        )
    return fuel_q


def _non_finite_geometry_keys(
    gp: Dict[str, Any], required: List[str]
) -> List[str]:
    """Required keys whose value is present but non-finite (NaN / ±Inf).

    The builders' missing-key check (``gp.get(k) is None``) catches only
    absent keys; a NaN smuggled in as a raw float (or inside a
    ``{value, unit}`` dict) would otherwise sail into the geometry
    constructor and poison the mean-line solve. Non-numeric values return
    ``False`` here — they are handled by the constructor's own
    try/except path (unknown-unit 422 or constant-η fallback).
    """
    import math

    out: List[str] = []
    for key in required:
        val = gp.get(key)
        if val is None:
            continue
        raw = val.get("value") if isinstance(val, dict) else val
        try:
            num = float(raw)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(num):
            out.append(key)
    return out


def _build_compressor_geometry(params: Dict[str, Any]):
    """Build a CentrifugalCompressorGeometry from the component params dict.

    Returns the geometry object on success, or None when ``geometry_params``
    is absent entirely (the caller falls back to 'constant' mode — surfaced
    to the user via the result payload's requested-vs-actual modes, U9).

    Raises ``GeometryParamsIncomplete`` (design-class) when the bag is
    ATTACHED but missing required keys, and ``HTTPException(422)`` for an
    unknown unit string — both classify design-class when raised in-worker
    (ADAPT-045: refusal-over-guess for attached-but-invalid geometry).

    All geometry fields use SI base units internally.  The project params
    dict may store them as {value, unit} quantity dicts (the same pattern
    used by the boundary conditions) or as raw floats (already in SI).
    """
    import logging
    import math

    log = logging.getLogger(__name__)
    gp = params.get("geometry_params", {})
    if not gp:
        return None

    def _f(key: str, default=None):
        """Extract a numeric value, unwrapping {value, unit} dicts.

        G2 / Item 3a (Verifier V finding): an unrecognised unit string must
        raise a structured 422 rather than silently falling back to the raw
        float, which would produce a dimensionally incorrect geometry.
        """
        val = gp.get(key, default)
        if val is None:
            return None
        if isinstance(val, dict) and "value" in val:
            from cascade.units import Q as _Q
            unit_str = str(val["unit"])
            try:
                return float(_Q(float(val["value"]), unit_str).to_base_units().magnitude)
            except Exception as exc:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error_code": "UNKNOWN_UNIT",
                        "message": (
                            f"Unknown unit '{unit_str}' for field '{key}': {exc}"
                        ),
                        "field": key,
                        "unit": unit_str,
                    },
                ) from exc
        return float(val)

    required = [
        "inducer_hub_radius",
        "inducer_tip_radius",
        "impeller_outlet_radius",
        "blade_height_outlet",
        "blade_count",
        "beta_2_metal_rad",
        "tip_clearance",
    ]
    missing = [k for k in required if gp.get(k) is None]
    non_finite = _non_finite_geometry_keys(gp, required)
    if missing or non_finite:
        # U9 / ADAPT-045: an attached-but-incomplete bag refuses design-class
        # (it previously fell back to constant-η with only a log line — see
        # the superseded W-03 doctrine recorded in internal/ADAPTATIONS.md).
        # Non-finite values (NaN/Inf) are the same refusal, named distinctly.
        raise GeometryParamsIncomplete("Compressor", missing, non_finite=non_finite)

    try:
        from cascade.meanline import CentrifugalCompressorGeometry

        return CentrifugalCompressorGeometry(
            inducer_hub_radius=_f("inducer_hub_radius"),
            inducer_tip_radius=_f("inducer_tip_radius"),
            impeller_outlet_radius=_f("impeller_outlet_radius"),
            blade_height_outlet=_f("blade_height_outlet"),
            blade_count=int(_f("blade_count")),
            beta_2_metal_rad=_f("beta_2_metal_rad", math.pi / 6),
            tip_clearance=_f("tip_clearance", 3e-4),
            disc_gap_ratio=_f("disc_gap_ratio", 0.02),
            blockage_outlet=_f("blockage_outlet", 0.08),
            epsilon_clearance=_f("epsilon_clearance", 1e-4),
        )
    except HTTPException:
        # G2 / Item 3a: re-raise structured validation errors from _f()
        # so the unknown-unit 422 propagates to the HTTP layer.
        raise
    except Exception as exc:
        # Construction failed despite a complete key set (e.g. a value the
        # geometry dataclass rejects). The fallback to constant-η stands for
        # robustness, but it is no longer silent: the result payload's
        # requested-vs-actual efficiency modes flag it to the user (U9).
        log.warning(
            "W-03/U9: Could not construct CentrifugalCompressorGeometry: %s; "
            "falling back to constant-η mode (surfaced via "
            "requested_efficiency_modes).",
            exc,
        )
        return None


def _build_turbine_geometry(params: Dict[str, Any]):
    """Build a RadialTurbineGeometry from the component params dict.

    Returns the geometry object on success, or None when ``geometry_params``
    is absent entirely (constant-η fallback, surfaced via the result
    payload's requested-vs-actual modes). Raises ``GeometryParamsIncomplete``
    when the bag is attached but missing required keys (ADAPT-045 —
    identical contract to ``_build_compressor_geometry``).
    """
    import logging
    import math

    log = logging.getLogger(__name__)
    gp = params.get("geometry_params", {})
    if not gp:
        return None

    def _f(key: str, default=None):
        """Extract a numeric value, unwrapping {value, unit} dicts.

        G2 / Item 3a (Verifier V finding): an unrecognised unit string must
        raise a structured 422 rather than silently falling back to the raw
        float, which would produce a dimensionally incorrect geometry.
        """
        val = gp.get(key, default)
        if val is None:
            return None
        if isinstance(val, dict) and "value" in val:
            from cascade.units import Q as _Q
            unit_str = str(val["unit"])
            try:
                return float(_Q(float(val["value"]), unit_str).to_base_units().magnitude)
            except Exception as exc:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error_code": "UNKNOWN_UNIT",
                        "message": (
                            f"Unknown unit '{unit_str}' for field '{key}': {exc}"
                        ),
                        "field": key,
                        "unit": unit_str,
                    },
                ) from exc
        return float(val)

    required = [
        "rotor_inlet_radius",
        "rotor_outlet_radius_hub",
        "rotor_outlet_radius_tip",
        "blade_height_inlet",
        "blade_height_outlet",
        "blade_count",
        "inlet_metal_angle_rad",
        "exducer_angle_rad",
        "tip_clearance",
    ]
    missing = [k for k in required if gp.get(k) is None]
    non_finite = _non_finite_geometry_keys(gp, required)
    if missing or non_finite:
        # U9 / ADAPT-045: attached-but-incomplete refuses design-class —
        # symmetric with the compressor builder. Non-finite values (NaN/Inf)
        # are the same refusal, named distinctly.
        raise GeometryParamsIncomplete("Turbine", missing, non_finite=non_finite)

    try:
        from cascade.meanline import RadialTurbineGeometry

        return RadialTurbineGeometry(
            rotor_inlet_radius=_f("rotor_inlet_radius"),
            rotor_outlet_radius_hub=_f("rotor_outlet_radius_hub"),
            rotor_outlet_radius_tip=_f("rotor_outlet_radius_tip"),
            blade_height_inlet=_f("blade_height_inlet"),
            blade_height_outlet=_f("blade_height_outlet"),
            blade_count=int(_f("blade_count")),
            inlet_metal_angle_rad=_f("inlet_metal_angle_rad", 0.0),
            exducer_angle_rad=_f("exducer_angle_rad", math.pi / 3),
            tip_clearance=_f("tip_clearance", 3e-4),
            disc_gap_ratio=_f("disc_gap_ratio", 0.02),
        )
    except HTTPException:
        # G2 / Item 3a: re-raise structured validation errors from _f()
        # so the unknown-unit 422 propagates to the HTTP layer.
        raise
    except Exception as exc:
        # See the compressor builder: complete key set but construction
        # failed — fallback retained, surfaced via requested-vs-actual
        # efficiency modes in the result payload (U9).
        log.warning(
            "W-03/U9: Could not construct RadialTurbineGeometry: %s; "
            "falling back to constant-η mode (surfaced via "
            "requested_efficiency_modes).",
            exc,
        )
        return None


def _build_recuperated_spec(project: Dict[str, Any]):
    from cascade.cycle.components import (
        Burner,
        Compressor,
        ConstantPressureLoss,
        Recuperator,
        Turbine,
    )
    from cascade.cycle.solver import RecuperatedBraytonSpec
    from cascade.units import Composition, Port, Q

    bc = project.get("boundary_conditions", {})
    composition_kind = bc.get("composition", "air")
    # For pure-fluid working media (sCO2, He, H2, etc.) a "Burner" in the
    # cycle is really a closed-loop external heat exchanger — no combustion,
    # no species shift. We force `air_standard=True` on every burner so the
    # composition stays single-species through the heat-addition step. (A
    # combustion burner on a pure-CO2 loop would produce H2O + CO2 + CO and
    # immediately break the CoolPropPureFluid single-species invariant.)
    if composition_kind == "air":
        comp = Composition.air()
        is_pure_fluid = False
    else:
        from cascade.units import Species

        sp = Species(composition_kind)
        comp = Composition.pure(sp)
        is_pure_fluid = True

    inlet = Port(
        pressure_total=_q(bc["pressure_total"]),
        temperature_total=_q(bc["temperature_total"]),
        mass_flow=_q(bc["mass_flow"]),
        composition=comp,
    )

    comp_dict = _component_by_kind(project, "Compressor")
    turb_dict = _component_by_kind(project, "Turbine")
    burn_dict = _component_by_kind(project, "Burner")
    recup_dict = _component_by_kind(project, "Recuperator")
    inlet_loss_dict = _component_by_kind(project, "ConstantPressureLoss")

    missing_kinds = [
        kind
        for kind, found in (
            ("Compressor", comp_dict),
            ("Burner", burn_dict),
            ("Turbine", turb_dict),
        )
        if found is None
    ]
    if missing_kinds:
        raise MissingRequiredComponents(missing_kinds)

    # W-03 (ADAPT-036): read efficiency_mode from the component params dict.
    # The UI dropdown emits "isentropic" | "polytropic" | "live_meanline";
    # the solver dataclass uses "constant" | "polytropic" | "live_meanline".
    # _normalise_efficiency_mode() maps between the two conventions.
    #
    # For "live_meanline" we also read geometry_params from the same dict and
    # build the appropriate geometry object (option A per W-03 spec).
    #
    # U9 doctrine (ADAPT-045 — supersedes the W-03 "graceful degradation is
    # a hard requirement" rule for invalid geometry):
    #   - geometry ABSENT (no geometry_params on the component): fall back
    #     to "constant" η so a bare canvas still solves, but the fallback is
    #     SURFACED — the result payload carries requested_efficiency_modes /
    #     efficiency_fallbacks alongside the actual efficiency_modes, and
    #     the UI renders the per-rotor attribution + fallback warning.
    #   - geometry ATTACHED but incomplete (missing required keys) or
    #     carrying an unknown unit: design-class REFUSAL
    #     (GeometryParamsIncomplete / UNKNOWN_UNIT) — refusal-over-guess,
    #     SPEC_SHEET §13. The builders raise; nothing here swallows it.
    comp_raw_mode = str(
        comp_dict["params"].get("efficiency_mode", "isentropic")
    )
    comp_mode = _normalise_efficiency_mode(comp_raw_mode)
    comp_geometry = None
    comp_rpm = None
    if comp_mode == "live_meanline":
        comp_geometry = _build_compressor_geometry(comp_dict["params"])
        if comp_geometry is None:
            # Absent-geometry fallback — surfaced via the payload's
            # requested-vs-actual efficiency modes (U9 / ADAPT-045).
            comp_mode = "constant"
        else:
            # RPM for the meanline solve: prefer an explicit field, else use
            # the solver-side default (60 000 rpm Capstone-class fallback).
            rpm_val = comp_dict["params"].get("meanline_rpm_rpm")
            if rpm_val is not None:
                comp_rpm = Q(float(rpm_val), "rpm")

    turb_raw_mode = str(
        turb_dict["params"].get("efficiency_mode", "isentropic")
    )
    turb_mode = _normalise_efficiency_mode(turb_raw_mode)
    turb_geometry = None
    turb_rpm = None
    if turb_mode == "live_meanline":
        turb_geometry = _build_turbine_geometry(turb_dict["params"])
        if turb_geometry is None:
            # Absent-geometry fallback — surfaced, see compressor above.
            turb_mode = "constant"
        else:
            rpm_val = turb_dict["params"].get("meanline_rpm_rpm")
            if rpm_val is not None:
                turb_rpm = Q(float(rpm_val), "rpm")

    compressor = Compressor(
        name=comp_dict["name"],
        pressure_ratio=float(comp_dict["params"]["pressure_ratio"]),
        efficiency_isentropic=float(comp_dict["params"]["efficiency_isentropic"]),
        efficiency_mode=comp_mode,
        meanline_geometry=comp_geometry,
        meanline_rpm=comp_rpm,
    )
    turbine = Turbine(
        name=turb_dict["name"],
        pressure_ratio=float(turb_dict["params"]["pressure_ratio"]),
        efficiency_isentropic=float(turb_dict["params"]["efficiency_isentropic"]),
        efficiency_mode=turb_mode,
        meanline_geometry=turb_geometry,
        meanline_rpm=turb_rpm,
    )
    bp = burn_dict["params"]
    # Three sources can request air-standard mode (highest priority first):
    # 1. Project-level settings.air_standard — the public F1 flag documented
    #    in this module's docstring.  Enables the textbook ideal Brayton mode
    #    via the HTTP API (POST /api/projects/{id}/cycle/solve).
    # 2. Burner component params.air_standard — per-component override (used
    #    by the sCO2 seed which hardcodes air_standard=True on its heater).
    # 3. is_pure_fluid — derived automatically for CoolProp-species projects.
    project_air_standard = bool(project.get("settings", {}).get("air_standard", False))
    air_standard = project_air_standard or bool(bp.get("air_standard", False)) or is_pure_fluid
    burner_kwargs: Dict[str, Any] = {
        "name": burn_dict["name"],
        "pressure_drop_fraction": float(bp.get("pressure_drop_fraction", 0.04)),
        "combustion_efficiency": float(bp.get("combustion_efficiency", 0.99)),
        "air_standard": air_standard,
    }
    # U7: the Burner has two specification modes and the core constructor
    # requires EXACTLY one of outlet_temperature / fuel_mass_flow. Because
    # PATCH is merge-only the bag may hold both values; branch on the
    # resolved spec_mode and pass exactly one kwarg.
    spec_mode = _resolve_burner_spec_mode(bp)
    if spec_mode == "fuel_mass_flow":
        if air_standard:
            # Belt-and-braces behind the synchronous 422 in the solve
            # endpoint (_check_burner_fuel_mode_air_standard_conflict):
            # the air-standard heat-addition model has no combustion, so
            # there is no fuel stream to pin. Refuse design-class rather
            # than letting the core constructor traceback as a bug.
            raise BurnerSpecInvalid(
                "Fuel mass-flow mode requires a combustion working fluid; "
                "this project runs the burner as an air-standard / "
                "pure-fluid heat exchanger (no fuel stream exists).",
                [
                    "Switch the Burner's spec mode back to 'Outlet T (TIT)'.",
                    "Or switch the project to the open-air combustion working fluid to use fuel-mass-flow mode.",
                ],
            )
        burner_kwargs["fuel_mass_flow"] = _burner_fuel_mass_flow_quantity(bp)
    else:
        if "outlet_temperature" not in bp:
            raise BurnerSpecInvalid(
                "Burner is in outlet-temperature mode but no outlet "
                "temperature (TIT) is set.",
                [
                    "Set the Burner's outlet temperature (a 30 kW-class microturbine runs around 1116 K).",
                    "Or switch the Burner's spec mode to 'Fuel ṁ' and set a fuel mass flow.",
                ],
            )
        burner_kwargs["outlet_temperature"] = _q(bp["outlet_temperature"])
    if "fuel_lhv" in bp:
        burner_kwargs["fuel_lhv"] = _q(bp["fuel_lhv"])
    if "fuel_carbon_atoms" in bp:
        burner_kwargs["fuel_carbon_atoms"] = int(bp["fuel_carbon_atoms"])
    if "fuel_hydrogen_atoms" in bp:
        burner_kwargs["fuel_hydrogen_atoms"] = int(bp["fuel_hydrogen_atoms"])
    if "fuel_molar_mass" in bp:
        burner_kwargs["fuel_molar_mass"] = _q(bp["fuel_molar_mass"])
    burner = Burner(**burner_kwargs)

    if recup_dict is not None:
        recup = Recuperator(
            name=recup_dict["name"],
            effectiveness=float(recup_dict["params"]["effectiveness"]),
            cold_pressure_drop_fraction=float(
                recup_dict["params"].get("cold_pressure_drop_fraction", 0.03)
            ),
            hot_pressure_drop_fraction=float(
                recup_dict["params"].get("hot_pressure_drop_fraction", 0.03)
            ),
        )
    else:
        recup = None

    inlet_loss = None
    if inlet_loss_dict is not None:
        inlet_loss = ConstantPressureLoss(
            name=inlet_loss_dict["name"],
            pressure_drop_fraction=float(
                inlet_loss_dict["params"].get("pressure_drop_fraction", 0.02)
            ),
        )

    settings = project.get("settings", {})
    # W-10 / B1 / B2: per-component mechanical_efficiency is now wired.
    #
    # Walsh & Fletcher (2004) §5 convention: the shaft carries a single
    # mechanical-loss factor η_m.  When the user sets η_m on individual
    # rotating components, we combine them as a product (each component's
    # bearings and windage contribute independently: η_m_shaft = η_c × η_t).
    # If neither component sets an explicit η_m we fall back to the
    # project-level settings.mechanical_efficiency (backward-compatible).
    _MECH_DEFAULT = 1.0
    comp_mech = float(comp_dict["params"].get("mechanical_efficiency", _MECH_DEFAULT))
    turb_mech = float(turb_dict["params"].get("mechanical_efficiency", _MECH_DEFAULT))
    # Detect whether either component has a non-unity value (i.e., the user
    # explicitly set it — the form default is 0.99 once the user opens
    # Advanced, but the stored default from the seed project is 1.0).
    # If any component-level override is non-unity, use the product; otherwise
    # fall back to the project-level setting so old projects are unaffected.
    if comp_mech != _MECH_DEFAULT or turb_mech != _MECH_DEFAULT:
        mech_eta = comp_mech * turb_mech
    else:
        mech_eta = float(settings.get("mechanical_efficiency", _MECH_DEFAULT))
    gen_eta = float(settings.get("generator_efficiency", 1.0))

    if recup is None:
        from cascade.cycle.solver import SimpleBraytonSpec

        return SimpleBraytonSpec(
            inlet_port=inlet,
            compressor=compressor,
            burner=burner,
            turbine=turbine,
            mechanical_efficiency=mech_eta,
            generator_efficiency=gen_eta,
        )
    return RecuperatedBraytonSpec(
        inlet_port=inlet,
        compressor=compressor,
        burner=burner,
        turbine=turbine,
        recuperator=recup,
        mechanical_efficiency=mech_eta,
        generator_efficiency=gen_eta,
        inlet_loss=inlet_loss,
    )


def _quantity_to_dict(q) -> Dict[str, Any]:
    base = q.to_base_units()
    return {"value": float(base.magnitude), "unit": str(base.units)}


def _port_to_dict(port) -> Dict[str, Any]:
    return {
        "pressure_total": _quantity_to_dict(port.pressure_total),
        "temperature_total": _quantity_to_dict(port.temperature_total),
        "mass_flow": _quantity_to_dict(port.mass_flow),
        "composition": {k.value: v for k, v in port.composition.mass_fractions.items()},
        "swirl_ratio": float(port.swirl_ratio),
    }


_AIR_LIKE_KINDS = {"air", "combustion_products"}

# Working-fluid species that route to CoolProp's real-gas Helmholtz EOS rather
# than NASA polynomials. Species names use the enum NAME for canonical
# comparison (e.g. SCO2). The lookup is case-insensitive over the enum value
# (e.g. "sCO2") and the enum name (e.g. "SCO2").
_COOLPROP_SPECIES_NAMES = {"SCO2", "H2", "HE", "H2O"}
# Common synonyms a project may declare; we map them to canonical enum names.
_COMPOSITION_SYNONYMS = {
    "co2": "SCO2",  # CoolProp's CO2 spans liquid → supercritical seamlessly.
    "sco2": "SCO2",
    "water": "H2O",
    "steam": "H2O",
    "helium": "HE",
    "he": "HE",
    "hydrogen": "H2",
    "h2": "H2",
}


def _resolve_species_name(composition_kind: str) -> str:
    """Map a project's free-form 'composition' string to an enum NAME.

    Accepts either the enum name (case-insensitive: 'SCO2', 'sCO2') or a
    common synonym ('CO2', 'water', 'helium'). Returns the canonical
    `Species` enum name. Raises `KeyError` if no mapping is found.
    """

    from cascade.units import Species

    raw = composition_kind.strip()
    # Direct enum name match (case-insensitive).
    for s in Species:
        if s.name.lower() == raw.lower():
            return s.name
    # Synonym table.
    if raw.lower() in _COMPOSITION_SYNONYMS:
        return _COMPOSITION_SYNONYMS[raw.lower()]
    raise KeyError(composition_kind)


def _select_fluid(project: Dict[str, Any]):
    """Pick the right ``FluidModel`` for the project's working fluid.

    Priority order:
    1. If ``settings.air_standard == True`` (see module docstring) →
       ``IdealGasFluid`` (calorically perfect, constant γ = 1.4, cp = 1005
       J/(kg·K)).  This is the textbook air-standard assumption used for CYC-1
       and CYC-2 validation (Çengel & Boles).
    2. "air" / "combustion_products" → ``NasaFluid`` (real-gas, variable cp,
       workhorse for combustion-product Brayton cycles).
    3. Any CoolProp-supported pure species (sCO2, He, H2, water/steam) →
       ``CoolPropPureFluid`` backed by the Helmholtz EOS.

    On an unrecognised composition string we fall back to ``NasaFluid`` so the
    user gets a clear regime-out-of-validity message from the NASA layer.
    """

    from cascade.cycle.fluid_model import CoolPropPureFluid, IdealGasFluid, NasaFluid
    from cascade.units import Q, Species

    # 1. Air-standard mode: textbook constant-cp, constant-γ assumption.
    settings = project.get("settings", {})
    if bool(settings.get("air_standard", False)):
        return IdealGasFluid(cp=Q(1005.0, "J/(kg*K)"), gamma=1.4)

    bc = project.get("boundary_conditions", {})
    kind = str(bc.get("composition", "air"))

    if kind.lower() in _AIR_LIKE_KINDS:
        return NasaFluid()

    try:
        species_name = _resolve_species_name(kind)
    except KeyError:
        return NasaFluid()

    if species_name in _COOLPROP_SPECIES_NAMES:
        return CoolPropPureFluid(Species[species_name])

    # Recognised species but not one we route to CoolProp (e.g. N2 alone).
    # Defer to NasaFluid as a single-species mixture.
    return NasaFluid()


def _classify_failure(exc: BaseException) -> Dict[str, Any]:
    """Turn an exception from the cycle solver into a structured payload
    the UI can render as either a friendly design-error explanation or a
    "copy this log" bug report.

    Returns a dict with keys:
      kind: "design" | "bug"
      title: short headline (display in the result panel header)
      plain_english: first-principles explanation of what went wrong
      suggestions: list of concrete things the user can try
      bug_log: full traceback (only present when kind == "bug")
    """

    msg = str(exc)
    msg_lc = msg.lower()
    exc_type = type(exc).__name__
    full_tb = traceback.format_exc()

    # --- Known design errors (physical impossibilities) -----------------

    # W-03 / AC5: Live mean-line co-simulation failures — catch these before
    # the generic Mach / regime patterns so the user gets an actionable message
    # rather than a generic "operating point out of validity" description.
    if "live_meanline_regime_refused" in msg_lc or "live mean-line refused" in msg_lc:
        return {
            "kind": "design",
            "title": "Mean-line solver refused the cycle operating point",
            "plain_english": (
                "The cycle co-simulation ran the mean-line solver at the current "
                "operating point (ṁ, Pt_in, Tt_in, π) and the mean-line solver "
                "returned a regime refusal — typically surge, choke, or a "
                "relative Mach above the validity limit. "
                "The full reason is shown below."
            ),
            "suggestions": [
                "Switch the efficiency mode back to 'Isentropic' to see whether the cycle itself solves — if it does, the geometry is the issue.",
                "Check that the cycle pressure ratio is consistent with what the mean-line geometry was designed for.",
                "Try lower RPM (or adjust geometry) to bring the relative Mach below 2.5.",
                "Check the mass flow: too high can cause choke, too low can cause surge.",
            ],
            "details": msg,
        }

    if "live_meanline_eta_out_of_range" in msg_lc:
        return {
            "kind": "design",
            "title": "Mean-line solver returned η outside (0, 1]",
            "plain_english": (
                "The mean-line solver produced an efficiency value outside the "
                "physically valid range (0, 1]. This usually means the operating "
                "point is very close to a physical limit (near-surge, near-choke, "
                "or the stage is deeply off-design)."
            ),
            "suggestions": [
                "Check that the pressure ratio is within the design range of the geometry.",
                "Try starting from the isentropic mode, then switch to live mean-line.",
                "Reduce the operating pressure ratio or mass flow to bring the stage back into its valid operating band.",
            ],
            "details": msg,
        }

    if "live_meanline_outer_nonconvergent" in msg_lc:
        return {
            "kind": "design",
            "title": "Cycle ↔ mean-line co-simulation did not converge",
            "plain_english": (
                "The Aitken-accelerated outer iteration between the cycle solver "
                "and the mean-line solver ran the maximum number of passes without "
                "settling. This usually means the operating point is right at the "
                "edge of a physical limit where η is very sensitive to operating "
                "conditions, and the relaxation can't damp the oscillation."
            ),
            "suggestions": [
                "Move the pressure ratio back toward the geometry's design point.",
                "Try 'Isentropic' mode first — if the cycle doesn't converge there either, the cycle parameters are the issue.",
                "Reduce the recuperator effectiveness if it's above 0.88 — very high ε magnifies the cycle ↔ meanline coupling.",
            ],
            "details": msg,
        }

    # Open-cycle sub-atmospheric exhaust (ADAPT-011).
    if "below ambient" in msg_lc or "sub_atmospheric" in msg_lc or "sub-atmospheric" in msg_lc:
        return {
            "kind": "design",
            "title": "Turbine would need to expand below ambient pressure",
            "plain_english": (
                "An open-cycle Brayton turbine breathes air from the atmosphere "
                "and exhausts back to it, so the gas has to be at roughly 1 atm "
                "on its way out. With the current settings, the compressor "
                "isn't building enough pressure for the turbine to expand "
                "across — the turbine would have to push gas to a pressure "
                "below ambient to balance the cycle, which is physically "
                "impossible."
            ),
            "suggestions": [
                "Increase the compressor pressure ratio so there is more pressure for the turbine to expand across.",
                "Decrease the turbine pressure ratio (it is usually derived from the chain of pressure drops — if you set it manually, check the math).",
                "Check that the recuperator and burner pressure drops aren't unreasonably high (typical ≤ 5 % each).",
            ],
        }

    # Supersonic flow / Mach out of validity.
    if "mach" in msg_lc and ("> 2.5" in msg_lc or "supersonic" in msg_lc or "out of valid" in msg_lc):
        return {
            "kind": "design",
            "title": "Flow goes supersonic somewhere in the stage",
            "plain_english": (
                "Relative Mach number exceeded the validity envelope of the "
                "loss correlations (about 2.5 for radial machines). The flow "
                "is going too fast for the mean-line solver to give a "
                "trustworthy answer. Physically the rotor can still operate, "
                "but the published correlations stop applying."
            ),
            "suggestions": [
                "Lower the rotor tip speed — either reduce RPM or shrink the tip radius.",
                "Lower the inlet Mach — increase the inlet area, or reduce mass flow.",
                "Check the working fluid: light gases (H₂, He) have a high speed of sound but also a low molecular mass, so geometry that works in air can be sonic in helium.",
            ],
        }

    # Topology incompleteness (raised by _build_recuperated_spec). The typed
    # exception carries the kinds actually absent so the explanation names
    # exactly what is missing, not always all three.
    if isinstance(exc, MissingRequiredComponents):
        missing = ", ".join(exc.missing)
        return {
            "kind": "design",
            "title": "Cycle is missing required components",
            "plain_english": (
                "A Brayton cycle needs at minimum a Compressor, a Burner, "
                f"and a Turbine. The cycle canvas is missing: {missing}."
            ),
            "suggestions": [
                f"Drag the missing component kind(s) onto the canvas from the left palette: {missing}.",
                # Edges are decorative in v1 — the solver never reads them, so
                # the refusal must not send the user off to draw wiring.
                "Edges drawn on the canvas are illustrative in v1 — the solver infers a series flow path from the component kinds present (see KNOWN_GAPS.md, KG-PLAT-02).",
                "The microturbine-30kw seed project is a working example you can copy from.",
            ],
        }

    # U7: degenerate Burner specification bag (fuel-mass-flow mode with no
    # / zero / NaN fuel value, or outlet-T mode with no TIT). Typed by the
    # spec builder; always a user-input problem, never a traceback.
    if isinstance(exc, BurnerSpecInvalid):
        return {
            "kind": "design",
            "title": "Burner specification is incomplete",
            "plain_english": (
                "The Burner's parameters don't pin one side of the energy "
                f"balance, so the solver has nothing to solve for. {msg}"
            ),
            "suggestions": exc.suggestions,
        }

    # U9 / ADAPT-045: geometry_params attached to a rotor but missing
    # required keys. A user-input problem — refuse design-class, naming the
    # missing field(s), rather than silently degrading to constant η.
    if isinstance(exc, GeometryParamsIncomplete):
        problems: List[str] = []
        if exc.missing:
            problems.append(
                "is missing required field(s): " + ", ".join(exc.missing)
            )
        if exc.non_finite:
            problems.append(
                "has non-finite (NaN/Inf) value(s) on field(s): "
                + ", ".join(exc.non_finite)
            )
        return {
            "kind": "design",
            "title": f"{exc.component_kind} geometry is incomplete",
            "plain_english": (
                f"Live mean-line mode found a geometry_params bag on the "
                f"{exc.component_kind} but it "
                + "; and ".join(problems)
                + ". A partial or non-finite geometry cannot produce a "
                "trustworthy η, so the solver refuses rather than guessing "
                "the dimensions (refusal-over-guess, SPEC_SHEET §13)."
            ),
            "suggestions": exc.suggestions,
            "details": msg,
        }

    # U9: an unknown unit inside an attached geometry bag raises the same
    # structured 422 HTTPException the synchronous validation path uses
    # (G2 / Item 3a). Raised mid-worker it is still a user-input problem,
    # so it classifies design-class — never a bug traceback.
    if isinstance(exc, HTTPException) and isinstance(exc.detail, dict):
        detail = exc.detail
        if detail.get("error_code") == "UNKNOWN_UNIT":
            return {
                "kind": "design",
                "title": "Unknown unit in the attached geometry",
                "plain_english": (
                    "A field in the attached geometry_params carries a unit "
                    "string the unit registry doesn't recognise, so the "
                    "value cannot be converted to SI. The solver refuses "
                    "rather than guessing the dimension."
                ),
                "suggestions": [
                    f"Fix the unit on field '{detail.get('field', '?')}' — "
                    "use an SI unit string (m, mm, rad, …) or a plain float "
                    "already in SI base units.",
                    "Re-send the geometry from a candidate detail page in Flow Path — 'Send to cycle' writes plain SI floats.",
                ],
                "details": str(detail.get("message", msg)),
            }

    # U7: burner exit temperature above the uncooled material limit. In
    # fuel-mass-flow mode the TIT is back-derived from ṁ_fuel, so the fix
    # is to reduce the fuel flow; in outlet-temperature mode, lower the
    # TIT directly. Match on the stable cause code so the message stays
    # specific even though the generic RegimeOutOfValidity branch below
    # would also catch it.
    if getattr(exc, "code", "") == "T_BURNER_OUT_OF_VALIDITY":
        return {
            "kind": "design",
            "title": "Burner exit temperature exceeds the material limit",
            "plain_english": (
                "The burner outlet (turbine inlet) temperature came out "
                "above 2100 K — the uncooled hot-section material limit "
                "(SPEC_SHEET §13). The solver refuses rather than "
                "extrapolating past the validated envelope."
            ),
            "suggestions": [
                "If the Burner is in fuel-mass-flow mode, reduce the fuel mass flow — the derived TIT scales with the fuel-to-air ratio.",
                "If the Burner is in outlet-temperature mode, lower the target TIT below 2100 K.",
                "Increase the air mass flow at the inlet so the same fuel heats more air to a lower temperature.",
            ],
            "details": msg,
        }

    # Negative / zero / NaN boundary conditions (raised by Port / cycle BC).
    if (
        ("non-positive" in msg_lc)
        or ("must be positive" in msg_lc)
        or ("must be finite" in msg_lc)
        or ("mass_flow" in msg_lc and ("zero" in msg_lc or "<= 0" in msg_lc))
    ):
        return {
            "kind": "design",
            "title": "A parameter is zero, negative, or NaN where it must be positive",
            "plain_english": (
                "One of the boundary conditions or component parameters is "
                "physically impossible — most often a zero mass flow, a "
                "negative temperature, a non-finite pressure, or an empty "
                "input box that defaulted to zero."
            ),
            "suggestions": [
                "Check the Inlet's pressure, temperature, and mass flow are all > 0 and finite.",
                "Check no input box was left blank or showing NaN.",
                "Recent edit? Make sure you clicked Save in the Properties Panel — the solver reads from the saved values.",
            ],
        }

    # Composition / fluid mismatch.
    if "regime" in msg_lc and ("composition" in msg_lc or "species" in msg_lc):
        return {
            "kind": "design",
            "title": "Working fluid isn't compatible with this cycle",
            "plain_english": (
                "The fluid model can't handle the species that the cycle "
                "generates. For example, a closed-cycle sCO₂ loop with a "
                "real Burner produces H₂O and CO₂ as combustion products, "
                "but the sCO₂ fluid model only handles pure CO₂."
            ),
            "suggestions": [
                "If the cycle is closed-loop (sCO₂, He, H₂), use an electric heater (Burner with air_standard=true) instead of a combustor.",
                "If the cycle is open-air, switch the working fluid to 'air' in the right rail.",
                "Check the Burner's fuel composition matches what your fluid model supports.",
            ],
        }

    # ZeroDivisionError — almost always a degenerate parameter.
    if exc_type == "ZeroDivisionError":
        return {
            "kind": "design",
            "title": "A parameter hit a degenerate value (division by zero)",
            "plain_english": (
                "The solver hit a division by zero. This usually means "
                "one of the parameters is at a physically degenerate value "
                "where the math breaks down — for example an efficiency of "
                "exactly 1.0 (zero losses), an effectiveness of exactly 1.0 "
                "(perfect heat exchanger), a pressure ratio of exactly 1.0 "
                "(no compression), or a mass flow of exactly 0."
            ),
            "suggestions": [
                "Keep efficiencies below 1.0 — try 0.99 max for compressor/turbine isentropic, 0.999 for combustion.",
                "Keep recuperator effectiveness below 1.0 — try 0.95 max.",
                "Make sure all pressure ratios are > 1.0 (and the turbine PR matches the chain of compressor PR × pressure drops).",
                "Make sure mass flow is > 0.",
            ],
        }

    # RegimeOutOfValidity catch-all (when the more specific patterns above didn't match).
    if exc_type == "RegimeOutOfValidity":
        return {
            "kind": "design",
            "title": "Operating point is outside the solver's validity envelope",
            "plain_english": (
                "The cycle reached a state the solver's correlations don't "
                "trust. The internal message is shown below; if it doesn't "
                "make sense, the suggestions are a good starting point."
            ),
            "suggestions": [
                "Move each parameter back toward the seed project's value one at a time — when the cycle starts solving again, the last change you made is the culprit.",
                "Check temperatures, pressures, and mass flows are physically realistic.",
                "If you just switched working fluids, the cycle may need re-tuning (different fluids have different optimal PRs and TITs).",
            ],
            "details": msg,
        }

    # Anything else → treat as a software bug.
    return {
        "kind": "bug",
        "title": f"Unexpected internal error: {exc_type}",
        "plain_english": (
            "Cascade's cycle solver hit an internal error that isn't a known "
            "physical impossibility. This looks like a software bug, not a "
            "problem with your design. The log below has the full traceback "
            "— copy it and pass it to the developer so they can fix it."
        ),
        "suggestions": [
            "Click 'Copy bug log' below to grab the traceback.",
            "Try the seed defaults to see whether the bug is parameter-dependent.",
            "If the bug only fires with specific values, note those — they make the bug much easier to reproduce.",
        ],
        "bug_log": full_tb,
    }


def _cycle_worker(project_id: str):
    """Build the worker closure for a project's cycle solve."""

    from jobs import PROJECTS

    def _empty_quantity(unit: str) -> Dict[str, Any]:
        return {"value": 0.0, "unit": unit}

    def _failure_result(failure: Dict[str, Any]) -> Dict[str, Any]:
        """Build a result envelope when the solver couldn't produce a valid
        answer — keeps the field shape stable so the frontend's adapter
        doesn't have to special-case missing keys.

        Pure envelope builder: ``last_run_status`` is written directly by
        the worker on each terminal path (done / non_converged / failed),
        followed by a ``PROJECTS.save`` so the badge survives a restart."""
        return {
            "converged": False,
            "outer_iterations": 0,
            "residual_norm": float("nan"),
            "thermal_efficiency": 0.0,
            "electrical_efficiency": 0.0,
            "net_shaft_work": _empty_quantity("W"),
            "electrical_output": _empty_quantity("W"),
            "specific_work": _empty_quantity("J/kg"),
            "heat_input": _empty_quantity("W"),
            "fuel_mass_flow": _empty_quantity("kg/s"),
            "ports": {},
            "shaft_work_components": {},
            "energy_balance": None,
            "states": [],
            "components": [],
            # W-03 / AC3: stable field shape on failure — empty dicts.
            "component_efficiencies": {},
            "efficiency_modes": {},
            # U9: requested-vs-actual fields keep the same stable shape.
            "requested_efficiency_modes": {},
            "efficiency_fallbacks": {},
            "failure": failure,
        }

    def _refusal_message(failure: Dict[str, Any], exc: BaseException) -> str:
        """Plain-English one-liner for ``job.message`` on a refusal."""
        if isinstance(exc, MissingRequiredComponents):
            # Names only the kinds actually absent — pinned by the refusal
            # contract tests.
            return str(exc)
        return str(failure.get("title", "Run refused — no result produced."))

    def _refusal_cause_code(failure: Dict[str, Any], exc: BaseException) -> str:
        """Stable machine-readable cause code for a refusal."""
        if isinstance(exc, MissingRequiredComponents):
            return MissingRequiredComponents.CAUSE_CODE
        # RegimeOutOfValidity carries its own stable code (e.g.
        # OPEN_CYCLE_SUB_ATMOSPHERIC, LIVE_MEANLINE_REGIME_REFUSED), as do
        # the typed builder exceptions (GEOMETRY_PARAMS_INCOMPLETE, …).
        code = getattr(exc, "code", None)
        if code:
            return str(code)
        # In-worker structured HTTPException (e.g. the geometry builders'
        # UNKNOWN_UNIT 422) — reuse its error_code as the cause code.
        if isinstance(exc, HTTPException) and isinstance(exc.detail, dict):
            error_code = exc.detail.get("error_code")
            if error_code:
                return str(error_code)
        if failure.get("kind") == "bug":
            return "UNEXPECTED_SOLVER_ERROR"
        return "DESIGN_REFUSED"

    def _refuse(
        job: Job, project: Dict[str, Any], exc: BaseException
    ) -> "NoReturn":
        """Terminal refusal path (class 1 of the job taxonomy).

        Classifies the exception into the failure envelope, persists the
        ``failed`` badge (the worker owns project state so ``run_in_worker``
        stays project-agnostic), and raises ``JobRefusal`` for
        ``run_in_worker`` to unwrap into ``status="failed"`` + envelope.
        """
        failure = _classify_failure(exc)
        if not job.cancelled:
            # A cancelled job keeps whatever badge the last completed run
            # wrote (cancel_job already owns the job's terminal state), and
            # gets no further progress events after its final one.
            report_progress(job, 1.0, failure["title"])
            project["last_run_status"] = "failed"
            _save_last_run_status(project_id)
        raise JobRefusal(
            envelope=_failure_result(failure),
            message=_refusal_message(failure, exc),
            cause_code=_refusal_cause_code(failure, exc),
        )

    def worker(job: Job) -> Dict[str, Any]:
        from cascade.cycle.solver import energy_balance_report, solve_cycle

        project = PROJECTS[project_id]
        report_progress(job, 0.1, "Building cycle spec.")
        if job.cancelled:
            return {}
        try:
            spec = _build_recuperated_spec(project)
            fluid = _select_fluid(project)
        except Exception as exc:  # noqa: BLE001
            _refuse(job, project, exc)
        # Give the SSE consumer a chance to see at least 3 events before
        # the (typically sub-second) solve finishes. The cascade cycle
        # solver is internally fast; we emit intermediate progress here.
        fluid_kind = type(fluid).__name__
        report_progress(job, 0.3, f"Spec built. Initialising solver ({fluid_kind}).")
        time.sleep(0.02)
        if job.cancelled:
            return {}
        report_progress(job, 0.5, "Running outer fixed-point on recycle.")
        try:
            result = solve_cycle(spec, fluid=fluid)
        except Exception as exc:  # noqa: BLE001
            _refuse(job, project, exc)
        if job.cancelled:
            return {}
        # Non-convergence isn't an exception — the solver sets
        # result.converged = False and lets the caller decide. Class 2 of
        # the job taxonomy: the run completed and produced a result, so the
        # job stays "done" with converged=False — it is NOT a refusal — and
        # the failure envelope rides along for the friendly explanation.
        if not result.converged:
            failure = {
                "kind": "design",
                "title": "Solver didn't converge",
                "plain_english": (
                    "The fixed-point iteration ran the maximum number of "
                    "passes without the recycle settling. This usually "
                    "means the operating point is right at the edge of a "
                    "physical limit, or two parameters are fighting each "
                    "other (for example, a very effective recuperator AND "
                    "a very low TIT)."
                ),
                "suggestions": [
                    "Move parameters back toward the seed defaults one at a time.",
                    "Lower the recuperator effectiveness if it's > 0.9 — high ε can stall the recycle.",
                    "Make sure the turbine PR matches the compressor PR × the chain of pressure drops.",
                ],
                "details": f"residual = {result.residual_norm:.3e} after {result.outer_iterations} iterations",
            }
            project["last_run_status"] = "non_converged"
            _save_last_run_status(project_id)
            return _failure_result(failure)
        report_progress(job, 0.9, "Solver converged. Packaging result.")
        time.sleep(0.02)
        # ADAPT-012: every cycle solve carries an explicit energy-balance
        # report so the UI / auditors see the Walsh-Fletcher convention
        # documented end-to-end.
        try:
            rpt = energy_balance_report(spec, result, fluid=fluid)
            energy_balance: Optional[Dict[str, Any]] = {
                "convention": rpt.convention,
                "compressor_work_in_kW": float(rpt.compressor_work_in),
                "turbine_work_out_kW": float(rpt.turbine_work_out),
                "recuperator_heat_xfer_kW": float(rpt.recuperator_heat_xfer),
                "burner_chemical_input_kW": float(rpt.burner_chemical_input),
                "exhaust_sensible_out_kW": float(rpt.exhaust_sensible_out),
                "inlet_sensible_in_kW": float(rpt.inlet_sensible_in),
                "sensible_balance_residual_kW": float(
                    rpt.sensible_balance_residual
                ),
                "absolute_balance_residual_kW": float(
                    rpt.absolute_balance_residual
                ),
                "report_text": str(rpt),
            }
        except Exception:  # pragma: no cover — defensive only
            energy_balance = None
        # Build UI-friendly states[] and components[] arrays for the T-s
        # diagram and the per-component breakdown. These are derived from
        # result.ports + result.shaft_work_components — every port already
        # carries (T_t, p_t, mass_flow, composition); we ask the fluid
        # model for entropy at each state.
        def _entropy_kJ(port_) -> float:
            try:
                s_q = fluid.s(
                    port_.temperature_total,
                    port_.pressure_total,
                    port_.composition,
                )
                # Quantity in J/(kg·K) — convert to kJ/(kg·K) for the UI.
                return float(s_q.to("J/(kg*K)").magnitude) / 1000.0
            except Exception:  # pragma: no cover — defensive
                return 0.0

        states_list = []
        for idx, (port_name, port) in enumerate(result.ports.items(), start=1):
            states_list.append(
                {
                    "label": str(idx),
                    "name": port_name,
                    "temperature": float(
                        port.temperature_total.to("K").magnitude
                    ),
                    "entropy": _entropy_kJ(port),
                    "pressure": float(port.pressure_total.to("kPa").magnitude),
                    "massFlow": float(port.mass_flow.to("kg/s").magnitude),
                }
            )

        components_list = []
        for comp_name, W in result.shaft_work_components.items():
            p = result.ports.get(comp_name)
            components_list.append(
                {
                    "componentId": comp_name,
                    "shaftWork": float(W.to("kW").magnitude),
                    "outletTemperature": float(
                        p.temperature_total.to("K").magnitude
                    )
                    if p is not None
                    else 0.0,
                    "outletPressure": float(p.pressure_total.to("kPa").magnitude)
                    if p is not None
                    else 0.0,
                    "outletMassFlow": float(p.mass_flow.to("kg/s").magnitude)
                    if p is not None
                    else 0.0,
                }
            )

        # U7: the Burner carries no shaft work, so the loop above never
        # emits a row for it — but its outlet temperature IS the TIT, and
        # in fuel-mass-flow mode that value is back-derived (the user never
        # typed it). Surface the burner row so the canvas chip and the
        # result panel can show the derived TIT.
        burner_port = result.ports.get(spec.burner.name)
        if burner_port is not None and spec.burner.name not in result.shaft_work_components:
            components_list.append(
                {
                    "componentId": spec.burner.name,
                    "shaftWork": 0.0,
                    "outletTemperature": float(
                        burner_port.temperature_total.to("K").magnitude
                    ),
                    "outletPressure": float(
                        burner_port.pressure_total.to("kPa").magnitude
                    ),
                    "outletMassFlow": float(
                        burner_port.mass_flow.to("kg/s").magnitude
                    ),
                }
            )

        # W-03 / AC3: build the per-component efficiency metadata so callers
        # can see (a) the converged η actually used, and (b) which efficiency
        # mode was active for each component.  The `efficiency_modes` dict
        # maps component name → the normalised solver mode string.
        efficiency_modes: Dict[str, str] = {}
        try:
            efficiency_modes[spec.compressor.name] = spec.compressor.efficiency_mode
            efficiency_modes[spec.turbine.name] = spec.turbine.efficiency_mode
        except AttributeError:
            pass  # non-recuperated specs expose the same fields; defensive

        # U9 / ADAPT-045: requested-vs-actual. `efficiency_modes` above is
        # read back from the built spec, so it records only the mode the
        # solve ACTUALLY used — the spec builder downgrades live_meanline
        # to constant when no geometry is attached. Record what the user's
        # params REQUESTED, plus an explicit per-rotor fallback flag, so
        # the UI can render "requested live mean-line, got isentropic"
        # instead of an unlabelled isentropic number.
        requested_modes = _requested_efficiency_modes(project)
        efficiency_fallbacks = {
            name: bool(
                requested_modes.get(name) == "live_meanline"
                and actual != "live_meanline"
            )
            for name, actual in efficiency_modes.items()
        }

        out = {
            "converged": bool(result.converged),
            "outer_iterations": int(result.outer_iterations),
            "residual_norm": float(result.residual_norm),
            "thermal_efficiency": float(result.thermal_efficiency),
            "electrical_efficiency": float(result.electrical_efficiency),
            "net_shaft_work": _quantity_to_dict(result.net_shaft_work),
            "electrical_output": _quantity_to_dict(result.electrical_output),
            "specific_work": _quantity_to_dict(result.specific_work),
            "heat_input": _quantity_to_dict(result.heat_input),
            "fuel_mass_flow": _quantity_to_dict(result.fuel_mass_flow),
            "ports": {name: _port_to_dict(p) for name, p in result.ports.items()},
            "shaft_work_components": {
                name: _quantity_to_dict(q)
                for name, q in result.shaft_work_components.items()
            },
            "energy_balance": energy_balance,
            # UI-friendly arrays (T-s diagram + per-component table).
            "states": states_list,
            "components": components_list,
            # W-03 / ADAPT-036 metadata: which η was used for each component
            # and which efficiency mode was active in the converged solve.
            "component_efficiencies": {
                k: float(v) for k, v in result.component_efficiencies.items()
            },
            "efficiency_modes": efficiency_modes,
            # U9: what the user's params asked for + explicit fallback flags.
            "requested_efficiency_modes": requested_modes,
            "efficiency_fallbacks": efficiency_fallbacks,
        }
        # Converged run: the non-converged branch returned above, so this is
        # always "done". Save so the badge survives a restart.
        project["last_run_status"] = "done"
        _save_last_run_status(project_id)
        return out

    return worker


def _check_air_standard_live_meanline_conflict(project: Dict[str, Any]) -> None:
    """Raise 422 if air_standard=true and any component uses efficiency_mode='live_meanline'.

    C-1 refusal: air_standard uses IdealGasFluid (constant cp/γ) for the
    entire cycle deck. The 'live_meanline' co-simulation runs its own
    thermodynamic model internally (NasaFluid / CoolPropPureFluid). Running
    both simultaneously means the cycle and the mean-line solver use
    incompatible thermodynamic assumptions — the enthalpy and entropy values
    exchanged across the Aitken outer loop would be inconsistent, producing
    undefined results.

    Citation: Çengel & Boles, *Thermodynamics* 9th ed. §9-5 (air-standard
    assumption); see also cycle.py module docstring for the F1 flag.
    """
    settings = project.get("settings", {})
    if not bool(settings.get("air_standard", False)):
        return  # no conflict possible when air_standard is off

    components = project.get("components", []) or []
    live_meanline_components = []
    for comp in components:
        raw_mode = str(
            comp.get("params", {}).get("efficiency_mode", "isentropic")
        )
        if _normalise_efficiency_mode(raw_mode) == "live_meanline":
            live_meanline_components.append(comp.get("name", comp.get("id", "?")))

    if live_meanline_components:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "INCOMPATIBLE_SETTINGS",
                "message": (
                    "air_standard cycle mode is incompatible with live_meanline "
                    "co-simulation; choose one. "
                    "air_standard=true engages IdealGasFluid (constant cp/γ) for "
                    "the cycle deck, while live_meanline runs the mean-line solver "
                    "with its own thermodynamic model. Running both simultaneously "
                    "produces thermodynamically inconsistent enthalpy/entropy "
                    "exchanges across the Aitken outer loop."
                ),
                "conflicting_components": live_meanline_components,
            },
        )


def _check_burner_fuel_mode_air_standard_conflict(project: Dict[str, Any]) -> None:
    """Raise 422 if any Burner is in fuel-mass-flow mode on a project whose
    burners are forced to air-standard heat addition.

    U7 refusal: the air-standard burner model is a heat exchanger — no
    combustion, no fuel stream — so a pinned ṁ_fuel has no physical
    meaning there, and the core Burner would raise a constructor error
    mid-worker (classified as a software bug with a traceback — the wrong
    message for a user-input problem). Mirror the live-meanline conflict
    above: refuse synchronously, before a job is created.

    Air-standard is forced by any of the three sources used by
    ``_build_recuperated_spec`` (same priority order):
      1. project-level ``settings.air_standard`` (the public F1 flag),
      2. per-burner ``params.air_standard`` (the sCO2 seed's heater),
      3. a pure-fluid working medium (``boundary_conditions.composition``
         other than air — closed loops have no combustion).
    """
    settings = project.get("settings", {})
    project_air_standard = bool(settings.get("air_standard", False))
    composition_kind = str(
        project.get("boundary_conditions", {}).get("composition", "air")
    )
    is_pure_fluid = composition_kind != "air"

    for comp in project.get("components", []) or []:
        if comp.get("kind") != "Burner":
            continue
        bp = comp.get("params", {}) or {}
        if _resolve_burner_spec_mode(bp) != "fuel_mass_flow":
            continue
        forced_by = [
            source
            for source, active in (
                ("settings.air_standard", project_air_standard),
                ("burner.params.air_standard", bool(bp.get("air_standard", False))),
                (f"pure-fluid working medium ({composition_kind})", is_pure_fluid),
            )
            if active
        ]
        if forced_by:
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": "FUEL_MODE_REQUIRES_COMBUSTION",
                    "message": (
                        "Fuel mass-flow mode requires a combustion working "
                        "fluid. This project runs its burner as an "
                        "air-standard / pure-fluid heat exchanger (forced by: "
                        + ", ".join(forced_by)
                        + "), so there is no fuel stream to pin. Switch the "
                        "Burner's spec mode back to 'Outlet T (TIT)', or use "
                        "an open-air combustion working fluid."
                    ),
                    "component": comp.get("name", comp.get("id", "?")),
                    "forced_by": forced_by,
                },
            )


@router.post("/solve", response_model=JobAcceptedResponse)
async def solve_cycle_endpoint(project_id: str) -> JobAcceptedResponse:
    project = get_project_or_404(project_id)
    # C-1 refusal: air_standard + live_meanline is thermodynamically inconsistent.
    # Check synchronously so the caller receives 422 before a job is queued.
    _check_air_standard_live_meanline_conflict(project)
    # U7 refusal: fuel-mass-flow mode needs a real fuel stream — refuse
    # synchronously on air-standard / pure-fluid projects.
    _check_burner_fuel_mode_air_standard_conflict(project)
    job = register_job(project_id, "cycle")
    # Emit a queued event so the SSE stream has something on subscribe.
    publish_event(
        job.id,
        {
            "job_id": job.id,
            "status": "queued",
            "progress": 0.0,
            "message": "Queued.",
        },
    )
    run_in_worker(job, _cycle_worker(project_id))
    return JobAcceptedResponse(job_id=job.id)
