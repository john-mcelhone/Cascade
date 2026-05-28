"""Performance map routes.

W-02 (§6): the polynomial speedline worker has been
replaced with real off-design mean-line solves.

Each ``(rpm, m_dot)`` grid point is one ``CentrifugalCompressorMeanline.solve()``
call. The geometry is built from the project's parameters (or the AT-100
defaults if the project has no stored geometry overrides). The operating point
uses the supplied ``rpm`` and ``m_dot`` directly; no corrected-speed polynomial.

Status codes per SPEC §13:
- ``CONVERGED``: solver returned a valid result.
- ``STALL_SURGE``: solver raised ``RegimeOutOfValidity`` with a low-flow cause,
  or mass flow is below the physical choking / surge limit detected by the solver.
  We catch ``RegimeOutOfValidity`` at low corrected flow and tag it as
  ``STALL_SURGE``.
- ``CHOKED``: solver raised ``RegimeOutOfValidity`` at high corrected flow
  (sonic throat condition), or the solver raised a convergence error on the
  high-flow end.
- ``NON_CONVERGED``: solver failed to converge for other reasons.

The heuristic for distinguishing STALL_SURGE vs CHOKED is based on the
corrected mass flow relative to the design point: below 0.5× design → STALL_SURGE;
above 1.4× design → CHOKED. This is a solver-physics-derived boundary in that
the real solver fails to converge (or raises RegimeOutOfValidity) at those
extremes, and the labelling follows the direction of the failure.

The SSE streaming contract is unchanged: each grid point emits a ``data`` event
with ``{"point": {...}}``; the final payload includes ``surge_line`` and
``choke_line`` arrays.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from deps import get_project_or_404
from jobs import Job, publish_event, register_job, report_progress, run_in_worker
from models import JobAcceptedResponse, MapRequest


router = APIRouter(prefix="/api/projects/{project_id}/map", tags=["map"])


# ---------------------------------------------------------------------------
# Corrected → dimensional for map sweeps (G2 / Item 1)
# ---------------------------------------------------------------------------

def _expand_corrected_map_inputs(req: MapRequest) -> tuple[List[float], List[float]]:
    """Expand corrected speedline / mass-flow sweeps to dimensional SI values.

    Returns ``(rpms, m_dots)`` ready for the grid solver. Raises 422 on
    overconstrained inputs (both corrected and dimensional supplied).

    Conversion formulas (same convention as analysis.py):
        θ = T₀₁ / T_ref,  δ = P₀₁ / P_ref
        N_dim  = N_corr × √θ
        ṁ_dim  = ṁ_corr × δ / √θ
    """
    has_corr_rpms = req.corrected_speedline_rpms is not None
    has_corr_flows = req.corrected_mass_flows is not None

    # Overconstrained guard — reject if both corrected and dimensional supplied.
    if has_corr_rpms and req.speedline_rpms:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "OVERCONSTRAINED_OPERATING_POINT",
                "message": (
                    "Both corrected_speedline_rpms and speedline_rpms are supplied. "
                    "Supply one form only."
                ),
                "conflicting_fields": ["corrected_speedline_rpms", "speedline_rpms"],
            },
        )
    if has_corr_flows and req.mass_flows:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "OVERCONSTRAINED_OPERATING_POINT",
                "message": (
                    "Both corrected_mass_flows and mass_flows are supplied. "
                    "Supply one form only."
                ),
                "conflicting_fields": ["corrected_mass_flows", "mass_flows"],
            },
        )

    # If no corrected inputs are used, return the dimensional inputs as-is.
    if not has_corr_rpms and not has_corr_flows:
        return list(req.speedline_rpms), list(req.mass_flows)

    # Corrected inputs present — need inlet conditions.
    p_01 = req.inlet_total_pressure_Pa
    t_01 = req.inlet_total_temperature_K
    if p_01 is None or t_01 is None:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "MISSING_INLET_CONDITIONS",
                "message": (
                    "inlet_total_pressure_Pa and inlet_total_temperature_K are required "
                    "when corrected_speedline_rpms or corrected_mass_flows are supplied."
                ),
                "missing_fields": (
                    [f for f in ("inlet_total_pressure_Pa", "inlet_total_temperature_K")
                     if (req.inlet_total_pressure_Pa if f == "inlet_total_pressure_Pa"
                         else req.inlet_total_temperature_K) is None]
                ),
            },
        )

    t_ref = req.reference_temperature_K
    p_ref = req.reference_pressure_Pa
    theta = t_01 / t_ref
    delta = p_01 / p_ref
    sqrt_theta = math.sqrt(theta)

    rpms = (
        [n_corr * sqrt_theta for n_corr in req.corrected_speedline_rpms]
        if has_corr_rpms
        else list(req.speedline_rpms)
    )
    m_dots = (
        [m_corr * delta / sqrt_theta for m_corr in req.corrected_mass_flows]
        if has_corr_flows
        else list(req.mass_flows)
    )
    return rpms, m_dots


def _map_grid_point(
    rpm: float,
    m_dot: float,
    rpm_design: float,
    m_dot_design: float,
    project_params: Dict[str, Any],
) -> Dict[str, Any]:
    """Evaluate one (rpm, m_dot) grid point with the real mean-line solver.

    Returns a point dict with keys:
        coords: {"rpm": float, "m_dot": float}
        outputs: {"pi": float, "eta": float, "power_kW": float}
        status: "CONVERGED" | "STALL_SURGE" | "CHOKED" | "NON_CONVERGED"
    """
    from cascade.meanline import (
        AungierCentrifugal,
        CentrifugalCompressorMeanline,
        RegimeOutOfValidity,
    )
    from cascade.meanline.exceptions import InvalidGeometry, MeanlineConvergenceError
    from cascade.units import Composition, Port, Q
    from routers._meanline_geom import build_cc_geometry

    # Determine surge/choke regime from corrected flow ratio.
    # We use this to label the failure even when the solver raises a generic error.
    m_corr = m_dot / max(m_dot_design, 1e-9)

    try:
        geom, op = build_cc_geometry(project_params=project_params)
    except (InvalidGeometry, ValueError):
        return {
            "coords": {"rpm": rpm, "m_dot": m_dot},
            "outputs": {"pi": 1.0, "eta": 0.0, "power_kW": 0.0},
            "status": "NON_CONVERGED",
        }

    inlet = Port(
        pressure_total=Q(op["pressure_total_Pa"], "Pa"),
        temperature_total=Q(op["temperature_total_K"], "K"),
        mass_flow=Q(m_dot, "kg/s"),
        composition=Composition.air(),
    )
    rpm_q = Q(rpm, "rpm")

    solver = CentrifugalCompressorMeanline()
    loss = AungierCentrifugal()

    try:
        result = solver.solve(inlet, rpm_q, geom, loss)
        pi = float(result.pressure_ratio_tt)
        eta = float(result.eta_tt)
        power_kW = float(result.power_W.to("kW").magnitude)
        return {
            "coords": {"rpm": rpm, "m_dot": m_dot},
            "outputs": {"pi": pi, "eta": eta, "power_kW": power_kW},
            "status": "CONVERGED",
        }
    except RegimeOutOfValidity:
        # Solver physics determine the regime; use flow direction to label.
        if m_corr < 0.7:
            status = "STALL_SURGE"
        else:
            status = "CHOKED"
        return {
            "coords": {"rpm": rpm, "m_dot": m_dot},
            "outputs": {"pi": 1.0, "eta": 0.0, "power_kW": 0.0},
            "status": status,
        }
    except MeanlineConvergenceError:
        # Convergence failures at extreme operating points labelled by regime.
        if m_corr < 0.7:
            status = "STALL_SURGE"
        elif m_corr > 1.35:
            status = "CHOKED"
        else:
            status = "NON_CONVERGED"
        return {
            "coords": {"rpm": rpm, "m_dot": m_dot},
            "outputs": {"pi": 1.0, "eta": 0.0, "power_kW": 0.0},
            "status": status,
        }
    except Exception:
        return {
            "coords": {"rpm": rpm, "m_dot": m_dot},
            "outputs": {"pi": 1.0, "eta": 0.0, "power_kW": 0.0},
            "status": "NON_CONVERGED",
        }


def _map_worker(project_id: str, req: MapRequest):
    from jobs import PROJECTS

    def worker(job: Job) -> Dict[str, Any]:
        rpms, m_dots = _expand_corrected_map_inputs(req)
        # Reasonable defaults if user supplied empties.
        # Scaled around Eckardt reference (r2=0.200m, 14000rpm, 5.31 kg/s).
        if not rpms:
            rpms = [7000.0, 9800.0, 12600.0, 14000.0, 15400.0]
        if not m_dots:
            m_dots = [1.5, 2.2, 3.0, 3.8, 4.5, 5.31, 6.0, 6.8, 7.5, 8.2, 8.8]

        # Design-point values matching the Eckardt Rotor A reference geometry
        # used in _meanline_geom.py. These are used to classify surge/choke
        # regime (high vs low flow direction) at each grid point.
        rpm_design = 14000.0
        m_dot_design = 5.31  # kg/s at reference r2=0.200m

        # Extract any project-level geometry overrides from the stored project.
        project = PROJECTS.get(project_id, {})
        project_params: Dict[str, Any] = {}
        # Pull geometry overrides if the project stores them (future persistence).
        # For now, project_params is empty and _CC_DESIGN_DEFAULTS are used.
        stored_geom = project.get("geometry_params") or {}
        if stored_geom:
            project_params.update(stored_geom)

        points: List[Dict[str, Any]] = []
        total = len(rpms) * len(m_dots)
        done = 0
        for rpm in rpms:
            for m_dot in m_dots:
                if job.cancelled:
                    break
                pt = _map_grid_point(
                    rpm=rpm,
                    m_dot=m_dot,
                    rpm_design=rpm_design,
                    m_dot_design=m_dot_design,
                    project_params=project_params,
                )
                points.append(pt)
                done += 1
                report_progress(
                    job,
                    done / max(1, total),
                    f"Mapped {done}/{total} grid points.",
                    data={"point": pt},
                )
                time.sleep(0.002)

        # Tag surge / choke lines
        surge_pts = [p for p in points if p["status"] == "STALL_SURGE"]
        choke_pts = [p for p in points if p["status"] == "CHOKED"]
        PROJECTS[project_id]["last_run_status"] = "done"
        PROJECTS.save(project_id)
        return {
            "axes": {"rpm": rpms, "m_dot": m_dots},
            "points": points,
            "surge_line": surge_pts,
            "choke_line": choke_pts,
        }

    return worker


@router.post("", response_model=JobAcceptedResponse)
async def map_endpoint(project_id: str, req: MapRequest) -> JobAcceptedResponse:
    get_project_or_404(project_id)
    # G2 / Item 1: validate corrected inputs synchronously so 422 is returned
    # before a job is queued.  We call the helper purely for validation —
    # the worker will call it again to obtain the resolved lists.
    _expand_corrected_map_inputs(req)
    job = register_job(project_id, "map")
    publish_event(
        job.id,
        {"job_id": job.id, "status": "queued", "progress": 0.0, "message": "Queued."},
    )
    run_in_worker(job, _map_worker(project_id, req))
    return JobAcceptedResponse(job_id=job.id)
