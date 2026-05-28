"""Mean-line analysis routes (ADAPT-020).

H1 additions:
- ``inverse_solve_pr_ts_target`` (Item 1): 1-D root-find on mass flow to hit a
  target PR_ts at a given speed. Enables reproduction of published PR-defined
  radial-turbine cases without external iteration. Uses ``scipy.optimize.brentq``.
- ``wiesner_calibration_scale`` (Item 2): exposes ``WiesnerSlip.calibration_scale``
  publicly for centrifugal-compressor solves. Default (None) keeps the production
  default of 1.0. Came & Robinson 1999 §3.2 recommend 1.05 for back-swept
  Eckardt-class wheels.

Wraps ``cascade.meanline.RadialTurbineMeanline`` and
``cascade.meanline.CentrifugalCompressorMeanline`` so the Analysis page can
fire the real solver against an active component in the project topology.

The endpoint resolves the active machine class by:

1. Reading ``machine_class`` from the request body when the client knows
   which solver it wants (the page lets the user toggle).
2. Otherwise scanning the cycle topology for a ``Compressor`` or
   ``Turbine`` node — present in the Capstone seed.

The geometry is built from a small set of demo defaults (mirroring the
Whitney-Stewart RIT-1 and Eckardt-Rotor-A validation cases). When the
``geometry`` override is non-empty the keys merge into the defaults. This
is the seam where, in a later iteration, candidate-picked geometry would
flow in (see KNOWN_GAPS — geometry persistence is M02-deferred).

## Public independent variables (added F1 / Audit C)

**``outlet_pressure_static_Pa``** (radial turbine only): the exducer-exit
static pressure in Pa.  This is a public independent variable that maps
directly to ``RadialTurbineMeanline.solve(p_out_static=...)``.

*When supplied*: the solver uses this BC to anchor η_ts against an
externally specified outlet state, which is required to reproduce published
NASA RIT test-point data (e.g. TN D-7508 Table II reports the static
pressure at the exducer exit for each speed-line point).

*When omitted*: the solver uses its internally derived static pressure
(free-discharge default — appropriate when outlet pressure is not known
from test data).

Convention (Saravanamuttoo et al., "Gas Turbine Theory" 7th ed. Ch. 4,
eq. 4.16–4.17): published RIT benchmarks report operating points as
corrected mass flow and corrected speed, not dimensional values.  To
convert before calling this endpoint:

    ṁ_dim    = ṁ_corr × (P₀₁ / P_ref) / √(T₀₁ / T_ref)
    N_dim    = N_corr × √(T₀₁ / T_ref)

where P_ref = 101 325 Pa and T_ref = 288.15 K (ISA sea-level standard,
used by NASA and Cascade unless the benchmark explicitly states otherwise).
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException

from deps import get_project_or_404
from jobs import (
    CANDIDATE_INDEX,
    Job,
    publish_event,
    register_job,
    report_progress,
    run_in_worker,
)
from models import AnalysisRequest, CorrectedOperatingPoint, JobAcceptedResponse


log = logging.getLogger("cascade.api.analysis")

router = APIRouter(prefix="/api/projects/{project_id}/analysis", tags=["analysis"])


# ---------------------------------------------------------------------------
# Corrected → dimensional conversion (G2 / Item 1)
# ---------------------------------------------------------------------------

def _corrected_to_dimensional(
    corr: CorrectedOperatingPoint,
    p_01_Pa: float,
    t_01_K: float,
) -> Dict[str, float]:
    """Convert corrected operating-point variables to dimensional SI.

    Convention (Saravanamuttoo et al., "Gas Turbine Theory" 7th ed., Ch. 4,
    eqs. 4.16–4.17; used by NASA benchmarks such as TN D-7508 unless the
    benchmark states otherwise):

        θ = T₀₁ / T_ref
        δ = P₀₁ / P_ref

        ṁ_dim  = ṁ_corr × δ / √θ
        N_dim  = N_corr × √θ

    Both corrected variables are optional; a value of None is passed through
    unchanged (the caller is responsible for ensuring the required keys are
    present before calling the solver).

    Args:
        corr: CorrectedOperatingPoint instance (carries reference conditions).
        p_01_Pa: inlet total pressure [Pa] at the operating point.
        t_01_K: inlet total temperature [K] at the operating point.

    Returns:
        Dict with keys ``mass_flow_kg_per_s`` and/or ``rpm`` (only those that
        were specified as corrected values).
    """
    t_ref = corr.reference_temperature_K
    p_ref = corr.reference_pressure_Pa

    theta = t_01_K / t_ref   # T₀₁ / T_ref
    delta = p_01_Pa / p_ref  # P₀₁ / P_ref
    sqrt_theta = math.sqrt(theta)

    result: Dict[str, float] = {}
    if corr.corrected_mass_flow_kg_s is not None:
        # ṁ_dim = ṁ_corr × δ / √θ
        result["mass_flow_kg_per_s"] = corr.corrected_mass_flow_kg_s * delta / sqrt_theta
    if corr.corrected_rotational_speed_rpm is not None:
        # N_dim = N_corr × √θ
        result["rpm"] = corr.corrected_rotational_speed_rpm * sqrt_theta
    return result


def _check_overconstrained(op_dict: Dict[str, Any], corr: Optional[CorrectedOperatingPoint]) -> None:
    """Raise 422 if both dimensional and corrected operating-point variables are supplied.

    Rules:
    - ``corrected_mass_flow_kg_s`` AND ``mass_flow_kg_per_s`` in operating_point → 422
    - ``corrected_rotational_speed_rpm`` AND ``rpm`` in operating_point → 422
    """
    if corr is None:
        return
    if corr.corrected_mass_flow_kg_s is not None and "mass_flow_kg_per_s" in op_dict:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "OVERCONSTRAINED_OPERATING_POINT",
                "message": (
                    "Both corrected_mass_flow_kg_s and mass_flow_kg_per_s are supplied. "
                    "Supply one form only — either corrected or dimensional."
                ),
                "conflicting_fields": ["corrected_mass_flow_kg_s", "mass_flow_kg_per_s"],
            },
        )
    if corr.corrected_rotational_speed_rpm is not None and "rpm" in op_dict:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "OVERCONSTRAINED_OPERATING_POINT",
                "message": (
                    "Both corrected_rotational_speed_rpm and rpm are supplied. "
                    "Supply one form only — either corrected or dimensional."
                ),
                "conflicting_fields": ["corrected_rotational_speed_rpm", "rpm"],
            },
        )


def _check_inverse_solve_overconstrained(
    op_dict: Dict[str, Any],
    corr: Optional[CorrectedOperatingPoint],
    inverse_solve_pr_ts_target: Optional[float],
    outlet_pressure_static_Pa: Optional[float] = None,
) -> None:
    """Raise 422 if inverse_solve_pr_ts_target is combined with a conflicting input.

    H1 / Item 1: when the inverse-solve mode is active, the solver finds mass flow
    internally. Supplying mass_flow_kg_per_s (or corrected_mass_flow_kg_s) together
    with inverse_solve_pr_ts_target is overconstrained and must be rejected.

    B-02: Supplying both inverse_solve_pr_ts_target AND outlet_pressure_static_Pa
    is also overconstrained. When outlet_pressure_static_Pa is fixed, PR_ts =
    P₀₁ / outlet_pressure_static_Pa is a constant determined only by the inlet
    total pressure — it does not depend on m_dot. The brentq bracket scan will
    find no sign change (the residual is constant or near-constant) and would
    return INVERSE_SOLVE_FAILED. The real cause is not a failed search but an
    overconstrained specification: fixing P₂_static removes the degree of freedom
    that the inverse solve requires.
    """
    if inverse_solve_pr_ts_target is None:
        return

    # B-02: outlet_pressure_static_Pa + inverse_solve together overconstrain PR_ts.
    if outlet_pressure_static_Pa is not None:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "OVERCONSTRAINED_OPERATING_POINT",
                "message": (
                    "Cannot combine inverse_solve_pr_ts_target with "
                    "outlet_pressure_static_Pa. When the outlet static pressure is "
                    "fixed, PR_ts = P₀₁ / P₂_static is determined entirely by the "
                    "inlet total pressure and is independent of mass flow — the "
                    "inverse solve has no degree of freedom. "
                    "Supply one or the other: use inverse_solve_pr_ts_target to find "
                    "the mass flow that achieves a target PR_ts at free-discharge "
                    "conditions, OR supply outlet_pressure_static_Pa to anchor η_ts "
                    "against a known static boundary condition."
                ),
                "conflicting_fields": [
                    "inverse_solve_pr_ts_target",
                    "outlet_pressure_static_Pa",
                ],
            },
        )

    has_dim_mdot = "mass_flow_kg_per_s" in op_dict and op_dict["mass_flow_kg_per_s"] is not None
    has_corr_mdot = (corr is not None and corr.corrected_mass_flow_kg_s is not None)
    if has_dim_mdot or has_corr_mdot:
        conflicting = []
        if has_dim_mdot:
            conflicting.append("mass_flow_kg_per_s")
        if has_corr_mdot:
            conflicting.append("corrected_mass_flow_kg_s")
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "OVERCONSTRAINED_OPERATING_POINT",
                "message": (
                    "inverse_solve_pr_ts_target is active (the solver finds mass flow "
                    "internally to hit the target PR_ts). Do not also supply "
                    "mass_flow_kg_per_s or corrected_mass_flow_kg_s — that is "
                    "overconstrained."
                ),
                "conflicting_fields": ["inverse_solve_pr_ts_target"] + conflicting,
            },
        )


def _inverse_solve_radial_turbine(
    geom_dict: Dict[str, Any],
    op_dict: Dict[str, Any],
    loss_model_name: str,
    pr_ts_target: float,
    outlet_pressure_static_Pa: Optional[float] = None,
) -> Dict[str, Any]:
    """Find mass flow that produces pr_ts_target at given speed (H1 / Item 1).

    Wraps the forward solver with a 1-D root-find (scipy.optimize.brentq) on
    mass flow.  The inlet total state, geometry, and rotational speed are fixed;
    m_dot is the free variable.

    Physical bracket: at fixed RPM and inlet total state, PR_ts increases
    monotonically with m_dot (higher corrected throughflow demands more expansion
    across the stage).  We bracket m_dot from a coarse scan first to avoid calling
    brentq on a sign-flipped or non-monotone range.

    Args:
        geom_dict: geometry parameter dictionary.
        op_dict: operating-point dictionary.  Must contain rpm, pressure_total_Pa,
            temperature_total_K.  mass_flow_kg_per_s is ignored (we solve for it).
        loss_model_name: passed through to _solve_radial_turbine.
        pr_ts_target: the desired total-to-static pressure ratio.
        outlet_pressure_static_Pa: optional outlet static BC (passed through to
            the forward solver; affects the PR_ts reference but not the root-find
            objective — the objective is always pr_ts_target).

    Returns:
        The forward-solver payload dict at the found m_dot, with an extra field
        ``inverse_solve`` containing diagnostic info.

    Raises:
        HTTPException 422 ``INVERSE_SOLVE_FAILED``: if brentq cannot find a root
            (target PR is outside the achievable range, or geometry is infeasible).
    """
    import scipy.optimize

    m_dot_lo = 0.001   # very low but not zero
    m_dot_hi = 500.0   # generous upper bound; brentq will narrow quickly

    def _pr_residual(m_dot: float) -> float:
        """Signed residual: forward_pr_ts(m_dot) − pr_ts_target."""
        op_trial = dict(op_dict)
        op_trial["mass_flow_kg_per_s"] = m_dot
        try:
            r = _solve_radial_turbine(geom_dict, op_trial, loss_model_name,
                                      outlet_pressure_static_Pa=outlet_pressure_static_Pa)
            return r["pressure_ratio_ts"] - pr_ts_target
        except Exception:  # noqa: BLE001
            # Return a sentinel that pushes brentq away from this region
            return 1e6

    # Sample a coarse grid to establish a valid bracket where the residual
    # changes sign.  PR_ts = P₀₁ / P₂_static is monotonically INCREASING
    # with m_dot: higher m_dot raises exit dynamic head, lowers P₂_static,
    # and therefore raises PR_ts (Saravanamuttoo et al. §4, eq. 4.16–4.17).
    # We therefore expect the residual to change sign as m_dot increases.
    import numpy as _np
    m_candidates = list(_np.logspace(
        _np.log10(m_dot_lo), _np.log10(min(m_dot_hi, 100.0)), 30))
    bracket_lo: Optional[float] = None
    bracket_hi: Optional[float] = None
    prev_m, prev_res = None, None
    for m in m_candidates:
        res = _pr_residual(m)
        if res > 1e5:
            prev_m, prev_res = m, res
            continue
        if prev_res is not None and prev_res <= 1e5:
            if prev_res * res < 0.0:
                bracket_lo = prev_m
                bracket_hi = m
                break
        prev_m, prev_res = m, res

    if bracket_lo is None or bracket_hi is None:
        # Try the full range
        res_lo = _pr_residual(m_dot_lo)
        res_hi_val = _pr_residual(m_dot_hi)
        if res_lo * res_hi_val >= 0.0:
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": "INVERSE_SOLVE_FAILED",
                    "message": (
                        f"Cannot find a mass flow that produces PR_ts = {pr_ts_target:.4f} "
                        f"at the given speed and geometry. "
                        f"The achievable PR_ts range (scanned m_dot [{m_dot_lo}, {m_dot_hi}] kg/s) "
                        f"does not bracket the target. "
                        f"PR_ts at m_dot={m_dot_lo} kg/s: {res_lo + pr_ts_target:.3f}; "
                        f"PR_ts at m_dot={m_dot_hi} kg/s: {res_hi_val + pr_ts_target:.3f}."
                    ),
                    "pr_ts_target": pr_ts_target,
                },
            )
        bracket_lo = m_dot_lo
        bracket_hi = m_dot_hi

    try:
        m_dot_found, result_obj = scipy.optimize.brentq(
            _pr_residual, bracket_lo, bracket_hi,
            xtol=1e-7, rtol=1e-6, full_output=True)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "INVERSE_SOLVE_FAILED",
                "message": f"brentq failed to converge: {exc}",
                "pr_ts_target": pr_ts_target,
            },
        ) from exc

    # Run the final forward solve at the found m_dot
    op_final = dict(op_dict)
    op_final["mass_flow_kg_per_s"] = float(m_dot_found)
    payload = _solve_radial_turbine(geom_dict, op_final, loss_model_name,
                                    outlet_pressure_static_Pa=outlet_pressure_static_Pa)
    payload["inverse_solve"] = {
        "mode": "pressure_ratio_ts",
        "pr_ts_target": float(pr_ts_target),
        "pr_ts_achieved": float(payload["pressure_ratio_ts"]),
        "m_dot_found_kg_s": float(m_dot_found),
        "bracket": [float(bracket_lo), float(bracket_hi)],
        "brentq_iterations": int(result_obj.iterations),
        "brentq_converged": bool(result_obj.converged),
    }
    return payload


# ---------------------------------------------------------------------------
# Geometry / operating-point defaults
# ---------------------------------------------------------------------------

# Whitney-Stewart helium RIT (NASA TN D-7508) — canonical RIT-1 case
_RIT_DEFAULTS: Dict[str, Any] = {
    "rotor_inlet_radius": 0.076,
    "rotor_outlet_radius_hub": 0.019,
    "rotor_outlet_radius_tip": 0.0406,
    "blade_height_inlet": 0.012,
    "blade_height_outlet": 0.0216,
    "blade_count": 12,
    "inlet_metal_angle_rad": 0.0,
    "exducer_angle_rad": math.radians(60.0),
    "tip_clearance": 0.00025,
    # Operating point
    "mass_flow_kg_per_s": 0.13,
    "rpm": 79000.0,
    "pressure_total_Pa": 220000.0,
    "temperature_total_K": 1090.0,
    "fluid": "air",  # we present air by default; helium is selected when user picks RIT-1
}

# Eckardt Rotor A (Aungier / Casey & Robinson §8.3.1) — canonical CC-1 case
_CC_DEFAULTS: Dict[str, Any] = {
    "inducer_hub_radius": 0.045,        # 90 mm dia → 45 mm radius
    "inducer_tip_radius": 0.140,        # 280 mm dia → 140 mm radius
    "impeller_outlet_radius": 0.200,    # 400 mm dia → 200 mm radius
    "blade_height_outlet": 0.026,       # b_2 = 26 mm
    "blade_count": 20,
    # 30° back-sweep → β'_from-tang = 60° → in-axial = 30° = π/6
    "beta_2_metal_rad": math.pi / 6,
    "tip_clearance": 0.0003,            # ε ≈ 0.3 mm
    # Operating point — Eckardt design point
    "mass_flow_kg_per_s": 5.31,
    "rpm": 14000.0,
    "pressure_total_Pa": 101325.0,
    "temperature_total_K": 288.15,
    "fluid": "air",
}


def _merge(defaults: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(defaults)
    for k, v in (override or {}).items():
        if v is None:
            continue
        out[k] = v
    return out


def _resolve_machine_class(project: Dict[str, Any], request_class: str) -> str:
    """Resolve the active machine class from the request or topology.

    The request body is authoritative — the user picks the machine in the
    Analysis page sidebar. We only consult the project topology when the
    request leaves the field default. (Defaults to ``radial_turbine`` to
    match the marketing copy / hero demo.)
    """
    if request_class in ("radial_turbine", "centrifugal_compressor"):
        return request_class
    # Fallback: scan components.
    components = project.get("components", []) or []
    kinds = {c.get("kind") for c in components}
    if "Compressor" in kinds and "Turbine" not in kinds:
        return "centrifugal_compressor"
    return "radial_turbine"


# ---------------------------------------------------------------------------
# Result-payload builders
# ---------------------------------------------------------------------------


def _port_state_dict(ps: Any) -> Dict[str, float]:
    return {
        "T_static_K": ps.T_static_K,
        "T_total_K": ps.T_total_K,
        "p_static_Pa": ps.p_static_Pa,
        "p_total_Pa": ps.p_total_Pa,
        "h_static_J_per_kg": ps.h_static_J_per_kg,
        "h_total_J_per_kg": ps.h_total_J_per_kg,
        "s_J_per_kgK": ps.s_J_per_kgK,
        "M": ps.M,
        "rho_kg_per_m3": ps.rho_kg_per_m3,
    }


def _vtriangle_dict(t: Any) -> Dict[str, float]:
    return {
        "U": t.U,
        "V_meridional": t.V_meridional,
        "V_theta": t.V_theta,
        "W_meridional": t.W_meridional,
        "W_theta": t.W_theta,
        "V": t.V,
        "W": t.W,
        "alpha_flow_deg": t.alpha_flow_deg,
        "beta_flow_deg": t.beta_flow_deg,
    }


def _loss_breakdown_records(breakdown: Any, ref_kinetic_J_per_kg: float,
                            citation: str) -> List[Dict[str, Any]]:
    """Convert a `LossBreakdown` into named records suitable for the bar chart.

    Each term is reported in *kJ/kg* (Δh contribution) for legibility, plus
    the kJ/kg value as ``delta_h_J_per_kg`` retained for backward
    compatibility with the existing loss-breakdown component contract.
    """
    out: List[Dict[str, Any]] = []
    for name, zeta in breakdown.terms().items():
        if zeta == 0.0:
            continue
        dh_J_per_kg = float(zeta) * ref_kinetic_J_per_kg
        out.append({
            "name": name,
            "delta_h_J_per_kg": dh_J_per_kg,
            "value_kJ_per_kg": dh_J_per_kg / 1000.0,
            "zeta": float(zeta),
            "citation": citation,
        })
    return out


def _hs_states_radial_turbine(result: Any) -> List[Dict[str, Any]]:
    """h-s diagram station list for a radial turbine.

    Stations: 0 (inlet total), 1 (rotor LE static), 2 (rotor TE static),
    02 (rotor TE total).
    """
    inlet = result.port_states["inlet"]
    exit_ = result.port_states["exit"]
    return [
        {"label": "01", "h_J_per_kg": inlet.h_total_J_per_kg,
         "s_J_per_kgK": 0.0},
        {"label": "1",  "h_J_per_kg": inlet.h_static_J_per_kg,
         "s_J_per_kgK": inlet.s_J_per_kgK},
        {"label": "2",  "h_J_per_kg": exit_.h_static_J_per_kg,
         "s_J_per_kgK": exit_.s_J_per_kgK},
        {"label": "02", "h_J_per_kg": exit_.h_total_J_per_kg,
         "s_J_per_kgK": exit_.s_J_per_kgK},
    ]


def _hs_states_compressor(result: Any) -> List[Dict[str, Any]]:
    """h-s diagram station list for a centrifugal compressor.

    Stations: 01 (inducer total), 1 (LE static), 2 (TE static), 02 (TE total).
    """
    inlet = result.port_states["inlet"]
    exit_ = result.port_states["exit"]
    return [
        {"label": "01", "h_J_per_kg": inlet.h_total_J_per_kg,
         "s_J_per_kgK": 0.0},
        {"label": "1",  "h_J_per_kg": inlet.h_static_J_per_kg,
         "s_J_per_kgK": inlet.s_J_per_kgK},
        {"label": "2",  "h_J_per_kg": exit_.h_static_J_per_kg,
         "s_J_per_kgK": exit_.s_J_per_kgK},
        {"label": "02", "h_J_per_kg": exit_.h_total_J_per_kg,
         "s_J_per_kgK": exit_.s_J_per_kgK},
    ]


def _select_fluid(name: Optional[str]) -> Tuple[Any, str]:
    """Pick a PerfectGas; default to air."""
    from cascade.meanline.fluid import AIR, HELIUM, air_hot

    if not name:
        return AIR, "dry-air-ISA"
    n = name.strip().lower()
    if n in ("he", "helium"):
        return HELIUM, "helium"
    if n in ("hot-air", "air_hot"):
        return air_hot(), "hot-air"
    return AIR, "dry-air-ISA"


# ---------------------------------------------------------------------------
# Solver invocations
# ---------------------------------------------------------------------------


def _solve_radial_turbine(geom_dict: Dict[str, Any], op: Dict[str, Any],
                          loss_model_name: str,
                          outlet_pressure_static_Pa: Optional[float] = None) -> Dict[str, Any]:
    """Run the radial-turbine mean-line and assemble a JSON payload.

    Args:
        geom_dict: geometry parameter dictionary (SI units throughout).
        op: operating-point dictionary. Required keys:
            ``pressure_total_Pa``, ``temperature_total_K``,
            ``mass_flow_kg_per_s``, ``rpm``.  Optional: ``fluid``.
        loss_model_name: string label returned in the result payload.
        outlet_pressure_static_Pa: exducer-exit static pressure [Pa].
            When not None, passed directly to
            ``RadialTurbineMeanline.solve(p_out_static=...)`` so η_ts is
            computed against this externally specified BC rather than the
            free-discharge default.  Enables reproduction of published
            NASA RIT speed-line data (e.g. TN D-7508 Table II).
            See module docstring for the corrected-to-dimensional formula.
    """
    from cascade.meanline import (
        RadialTurbineGeometry,
        RadialTurbineMeanline,
        WhitfieldBainesRadial,
    )
    from cascade.units import Composition, Port, Q, Species

    geom = RadialTurbineGeometry(
        rotor_inlet_radius=float(geom_dict["rotor_inlet_radius"]),
        rotor_outlet_radius_hub=float(geom_dict["rotor_outlet_radius_hub"]),
        rotor_outlet_radius_tip=float(geom_dict["rotor_outlet_radius_tip"]),
        blade_height_inlet=float(geom_dict["blade_height_inlet"]),
        blade_height_outlet=float(geom_dict["blade_height_outlet"]),
        blade_count=int(geom_dict["blade_count"]),
        inlet_metal_angle_rad=float(geom_dict["inlet_metal_angle_rad"]),
        exducer_angle_rad=float(geom_dict["exducer_angle_rad"]),
        tip_clearance=float(geom_dict["tip_clearance"]),
    )
    fluid, fluid_name = _select_fluid(op.get("fluid"))
    composition = (Composition.pure(Species.HE) if fluid_name == "helium"
                   else Composition.air())
    inlet = Port(
        pressure_total=Q(float(op["pressure_total_Pa"]), "Pa"),
        temperature_total=Q(float(op["temperature_total_K"]), "K"),
        mass_flow=Q(float(op["mass_flow_kg_per_s"]), "kg/s"),
        composition=composition,
    )
    solver = RadialTurbineMeanline()
    loss = WhitfieldBainesRadial()
    # Build the optional outlet-static-pressure BC.
    p_out_static_q = (Q(outlet_pressure_static_Pa, "Pa")
                      if outlet_pressure_static_Pa is not None else None)
    result = solver.solve(inlet, Q(float(op["rpm"]), "rpm"), geom, loss, fluid,
                          p_out_static=p_out_static_q)

    # ½ W₂² is the reference kinetic for the Whitfield-Baines ζ values.
    W_2 = result.W_2.to("m/s").magnitude
    ref_ke = 0.5 * W_2 * W_2

    return {
        "machine_class": "radial_turbine",
        "loss_model": loss_model_name or "whitfield-baines-radial-v1",
        "fluid": fluid_name,
        "mass_flow_kg_per_s": float(op["mass_flow_kg_per_s"]),
        "rotor_speed_rpm": float(op["rpm"]),
        "eta_total": result.eta_tt,  # legacy field — UI consumes "eta_total"
        "efficiencies": {
            "eta_tt": float(result.eta_tt),
            "eta_ts": float(result.eta_ts),
            "eta_polytropic": float(result.eta_polytropic),
        },
        "pressure_ratio_tt": float(result.pressure_ratio_tt),
        "pressure_ratio_ts": float(result.pressure_ratio_ts),
        "work_coefficient": float(result.work_coefficient),
        "flow_coefficient": float(result.flow_coefficient),
        "power_W": float(result.power_W.to("W").magnitude),
        "max_M_rel": float(result.max_M_rel),
        "port_states": {
            "inlet": _port_state_dict(result.port_states["inlet"]),
            "exit": _port_state_dict(result.port_states["exit"]),
        },
        "velocity_triangles": {
            "inlet": _vtriangle_dict(result.velocity_triangles["inlet"]),
            "exit": _vtriangle_dict(result.velocity_triangles["exit"]),
        },
        "convergence": {"iterations": result.convergence_history},
        "convergence_history": result.convergence_history,
        "h_s_states": _hs_states_radial_turbine(result),
        "loss_breakdown": _loss_breakdown_records(
            result.loss_breakdown, ref_ke, loss.citation),
        # h_s2_at_p2 surfaced explicitly so the UI can show the ADAPT-022
        # narrative: η_ts denominator = (h_t1 − h_s2_at_p2).
        "h_s2_at_p2_J_per_kg": float(result.h_s2_at_p2_J_per_kg),
    }


def _solve_centrifugal_compressor(geom_dict: Dict[str, Any], op: Dict[str, Any],
                                  loss_model_name: str,
                                  wiesner_calibration_scale: Optional[float] = None) -> Dict[str, Any]:
    """Run the centrifugal-compressor mean-line and assemble a JSON payload.

    Args:
        geom_dict: geometry parameter dictionary (SI units throughout).
        op: operating-point dictionary. Required keys:
            ``pressure_total_Pa``, ``temperature_total_K``,
            ``mass_flow_kg_per_s``, ``rpm``.  Optional: ``fluid``.
        loss_model_name: string label returned in the result payload.
        wiesner_calibration_scale: optional multiplier for the Wiesner (1967)
            slip-factor formula.  When not None, ``WiesnerSlip(calibration_scale=...)``
            is used instead of the production default ``WiesnerSlip(calibration_scale=1.0)``.
            Came & Robinson 1999 §3.2 recommend 1.05 for back-swept Eckardt-class
            wheels (β₂' ~ 60° from tangential).  Default (None) → 1.0.
    """
    from cascade.meanline import (
        AungierCentrifugal,
        CentrifugalCompressorGeometry,
        CentrifugalCompressorMeanline,
        WiesnerSlip,
    )
    from cascade.units import Composition, Port, Q

    geom = CentrifugalCompressorGeometry(
        inducer_hub_radius=float(geom_dict["inducer_hub_radius"]),
        inducer_tip_radius=float(geom_dict["inducer_tip_radius"]),
        impeller_outlet_radius=float(geom_dict["impeller_outlet_radius"]),
        blade_height_outlet=float(geom_dict["blade_height_outlet"]),
        blade_count=int(geom_dict["blade_count"]),
        beta_2_metal_rad=float(geom_dict["beta_2_metal_rad"]),
        tip_clearance=float(geom_dict["tip_clearance"]),
    )
    fluid, fluid_name = _select_fluid(op.get("fluid"))
    inlet = Port(
        pressure_total=Q(float(op["pressure_total_Pa"]), "Pa"),
        temperature_total=Q(float(op["temperature_total_K"]), "K"),
        mass_flow=Q(float(op["mass_flow_kg_per_s"]), "kg/s"),
        composition=Composition.air(),
    )
    # H1 / Item 2: use calibrated slip model when wiesner_calibration_scale is set.
    # The production default is 1.0 (unmodified Wiesner 1967). The calibration
    # scale is an optional, cited, documented override — NOT a benchmark-name branch.
    if wiesner_calibration_scale is not None:
        slip = WiesnerSlip(calibration_scale=float(wiesner_calibration_scale))
        solver = CentrifugalCompressorMeanline(slip_model=slip)
    else:
        solver = CentrifugalCompressorMeanline()
    loss = AungierCentrifugal()
    result = solver.solve(inlet, Q(float(op["rpm"]), "rpm"), geom, loss, fluid)

    U_2 = result.U_2.to("m/s").magnitude
    ref_ke = 0.5 * U_2 * U_2

    return {
        "machine_class": "centrifugal_compressor",
        "loss_model": loss_model_name or "aungier-centrifugal-v1",
        "fluid": fluid_name,
        "mass_flow_kg_per_s": float(op["mass_flow_kg_per_s"]),
        "rotor_speed_rpm": float(op["rpm"]),
        "eta_total": result.eta_tt,  # legacy field
        "efficiencies": {
            "eta_tt": float(result.eta_tt),
            "eta_ts": float(result.eta_ts),
            "eta_polytropic": float(result.eta_polytropic),
        },
        "pressure_ratio_tt": float(result.pressure_ratio_tt),
        "pressure_ratio_ts": float(result.pressure_ratio_ts),
        "work_coefficient": float(result.work_coefficient),
        "flow_coefficient": float(result.flow_coefficient),
        "power_W": float(result.power_W.to("W").magnitude),
        "max_M_rel": float(result.max_M_rel),
        "slip_factor": float(result.slip_factor),
        "port_states": {
            "inlet": _port_state_dict(result.port_states["inlet"]),
            "exit": _port_state_dict(result.port_states["exit"]),
        },
        "velocity_triangles": {
            "inlet": _vtriangle_dict(result.velocity_triangles["inlet"]),
            "exit": _vtriangle_dict(result.velocity_triangles["exit"]),
        },
        "convergence": {"iterations": result.convergence_history},
        "convergence_history": result.convergence_history,
        "h_s_states": _hs_states_compressor(result),
        "loss_breakdown": _loss_breakdown_records(
            result.loss_breakdown, ref_ke, loss.citation),
        "h_s2_at_p2_J_per_kg": float(result.h_s2_at_p2_J_per_kg),
    }


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


def _analysis_worker(project_id: str, req: AnalysisRequest):
    def worker(job: Job) -> Dict[str, Any]:
        project = get_project_or_404(project_id)
        machine_class = _resolve_machine_class(project, req.machine_class or "")

        report_progress(job, 0.10, "Resolving geometry and operating point.")

        # Geometry / operating-point: merge user overrides into the defaults
        # for the chosen machine class. If a candidate is named in the
        # request, pull its parameter vector into the geometry merge.
        if machine_class == "radial_turbine":
            defaults = dict(_RIT_DEFAULTS)
        else:
            defaults = dict(_CC_DEFAULTS)

        candidate = (CANDIDATE_INDEX.get(req.candidate_id)
                     if req.candidate_id else None)
        if candidate:
            for k, v in (candidate.get("params") or {}).items():
                if k in defaults:
                    defaults[k] = v

        merged = _merge(defaults, dict(req.geometry or {}))
        merged = _merge(merged, dict(req.operating_point or {}))

        # Split into geometry vs operating-point keys
        op_keys = {
            "mass_flow_kg_per_s", "rpm",
            "pressure_total_Pa", "temperature_total_K", "fluid",
        }
        geom_dict = {k: v for k, v in merged.items() if k not in op_keys}
        op_dict = {k: v for k, v in merged.items() if k in op_keys}

        # G2 / Item 1: apply corrected → dimensional conversion if the caller
        # supplied corrected operating-point variables. The check for
        # overconstrained inputs is performed first; then the conversion
        # overwrites the relevant keys in op_dict.
        if req.corrected_operating_point is not None:
            _check_overconstrained(dict(req.operating_point or {}), req.corrected_operating_point)
            p_01 = float(op_dict.get("pressure_total_Pa", defaults.get("pressure_total_Pa", 101325.0)))
            t_01 = float(op_dict.get("temperature_total_K", defaults.get("temperature_total_K", 288.15)))
            dim_vals = _corrected_to_dimensional(req.corrected_operating_point, p_01, t_01)
            op_dict.update(dim_vals)
            log.debug(
                "Corrected → dimensional: corr=%r → dim=%r (P₀₁=%.0f Pa, T₀₁=%.2f K)",
                req.corrected_operating_point,
                dim_vals,
                p_01,
                t_01,
            )

        report_progress(job, 0.40,
                        f"Running {machine_class} mean-line solve.")
        t0 = time.perf_counter()
        try:
            if machine_class == "radial_turbine":
                if req.inverse_solve_pr_ts_target is not None:
                    # H1 / Item 1: inverse-solve — find m_dot that achieves pr_ts_target.
                    payload = _inverse_solve_radial_turbine(
                        geom_dict, op_dict, req.loss_model,
                        pr_ts_target=float(req.inverse_solve_pr_ts_target),
                        outlet_pressure_static_Pa=req.outlet_pressure_static_Pa)
                else:
                    payload = _solve_radial_turbine(
                        geom_dict, op_dict, req.loss_model,
                        outlet_pressure_static_Pa=req.outlet_pressure_static_Pa)
            else:
                # H1 / Item 2: thread Wiesner calibration scale into compressor solve.
                payload = _solve_centrifugal_compressor(
                    geom_dict, op_dict, req.loss_model,
                    wiesner_calibration_scale=req.wiesner_calibration_scale)
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            # Surface a structured error in the result — the page renders
            # it as a toast.
            log.exception("analysis solve failed")
            return {
                "machine_class": machine_class,
                "loss_model": req.loss_model,
                # Honest failure envelope (mirrors the cycle worker): flag
                # non-convergence explicitly instead of returning a fabricated
                # eta_total=0.0 that an API-only consumer could read as a real
                # zero-efficiency result. The frontend surfaces `error` as a toast.
                "converged": False,
                "error": f"{type(exc).__name__}: {exc}",
                "loss_breakdown": [],
                "convergence_history": [],
                "h_s_states": [],
            }
        elapsed_s = time.perf_counter() - t0
        payload["elapsed_s"] = elapsed_s

        report_progress(job, 0.85, "Packaging results.")
        # Pass through the candidate ID for round-trip identity in the UI.
        payload["candidate_id"] = req.candidate_id
        return payload

    return worker


@router.post("", response_model=JobAcceptedResponse)
async def analysis_endpoint(project_id: str, req: AnalysisRequest) -> JobAcceptedResponse:
    get_project_or_404(project_id)
    # G2 / Item 1: validate overconstrained inputs synchronously so the caller
    # receives the 422 immediately (before a job is queued).
    _check_overconstrained(dict(req.operating_point or {}), req.corrected_operating_point)
    # H1 / Item 1 + B-02: validate inverse-solve overconstrained inputs synchronously.
    # Also rejects inverse_solve_pr_ts_target + outlet_pressure_static_Pa (B-02).
    _check_inverse_solve_overconstrained(
        dict(req.operating_point or {}),
        req.corrected_operating_point,
        req.inverse_solve_pr_ts_target,
        outlet_pressure_static_Pa=req.outlet_pressure_static_Pa,
    )
    job = register_job(project_id, "analysis")
    publish_event(
        job.id,
        {"job_id": job.id, "status": "queued", "progress": 0.0, "message": "Queued."},
    )
    run_in_worker(job, _analysis_worker(project_id, req))
    return JobAcceptedResponse(job_id=job.id)
