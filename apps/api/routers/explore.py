"""Design exploration routes.

Uses `cascade.explore.sobol_sampler.SobolSampler` over a 3-D parameter
space by default (rotor radius, blade count, tip clearance) and calls the
real ``CentrifugalCompressorMeanline`` solver for each candidate.

W-01 (§6): `_synthetic_evaluator` has been replaced
with `_meanline_evaluator`, which constructs a real geometry from the Sobol'
sample, calls ``CentrifugalCompressorMeanline.solve()``, and populates the
same Candidate JSON shape the front-end expects.

The public API contract (SSE event shape, candidate dict shape) is unchanged.
Only the values change — from a parabola to real mean-line physics.
"""

from __future__ import annotations

import math
import time
import uuid
import warnings as _warnings
from typing import Any, Dict, List

from fastapi import APIRouter

from deps import get_project_or_404
from jobs import (
    CANDIDATE_INDEX,
    CANDIDATES,
    Job,
    publish_event,
    register_job,
    report_progress,
    run_in_worker,
)
from models import ExploreRequest, JobAcceptedResponse


router = APIRouter(prefix="/api/projects/{project_id}/explore", tags=["explore"])


def _default_parameter_ranges() -> Dict[str, Any]:
    """Sensible default Sobol' ranges for the AT-100 centrifugal compressor."""

    from cascade.explore.sobol_sampler import ParameterRange

    return {
        "rotor_outlet_radius": ParameterRange(
            min=0.015, max=0.045, unit="m", scale="linear"
        ),
        "blade_count": ParameterRange(min=10, max=18, unit="dimensionless", scale="linear"),
        "tip_clearance": ParameterRange(min=1e-4, max=5e-4, unit="m", scale="log"),
    }


def _meanline_evaluator(params: Dict[str, Any]) -> Dict[str, Any]:
    """Real mean-line evaluator for the design-space scatter.

    Constructs a ``CentrifugalCompressorGeometry`` from the Sobol' sample,
    runs ``CentrifugalCompressorMeanline.solve()``, and returns the same
    Candidate-shaped dict the front-end expects.

    Status codes per SPEC §13 taxonomy:
    - ``VALID``: solver converged within the validity envelope.
    - ``REGIME_OUT_OF_VALIDITY``: relative Mach or other regime variable
      exceeds the loss model's validity range (raised by the solver).
    - ``INVALID_GEOMETRY``: geometry dimensions are invalid (raised by
      ``CentrifugalCompressorGeometry.__post_init__``).
    - ``NON_CONVERGED``: solver failed to converge (MeanlineConvergenceError).

    ``eta_ts`` is computed from ``result.h_s2_at_p2_J_per_kg`` inside the
    solver (ADAPT-022), not as a fixed offset from eta_tt.
    ``mass_kg`` is a volume-scaled impeller mass estimate.
    """
    from cascade.meanline import (
        AungierCentrifugal,
        CentrifugalCompressorMeanline,
        RegimeOutOfValidity,
    )
    from cascade.meanline.exceptions import InvalidGeometry, MeanlineConvergenceError
    from cascade.units import Composition, Port, Q
    from routers._meanline_geom import build_cc_geometry, estimate_mass_kg

    try:
        geom, op = build_cc_geometry(sample=params)
    except (InvalidGeometry, ValueError) as exc:
        r2 = float(params.get("rotor_outlet_radius", Q(0.03, "m")).magnitude
                   if hasattr(params.get("rotor_outlet_radius", 0), "magnitude")
                   else params.get("rotor_outlet_radius", 0.03))
        return {
            "objectives": {
                "eta_tt": 0.0,
                "eta_ts": 0.0,
                "power": 0.0,
                "mass": estimate_mass_kg(r2),
                "M_rel": 0.0,
            },
            "constraints": {"M_rel_under_choke": False},
            "status": "INVALID_GEOMETRY",
            "_error": str(exc),
        }

    r2 = geom.impeller_outlet_radius

    inlet = Port(
        pressure_total=Q(op["pressure_total_Pa"], "Pa"),
        temperature_total=Q(op["temperature_total_K"], "K"),
        mass_flow=Q(op["mass_flow_kg_per_s"], "kg/s"),
        composition=Composition.air(),
    )
    rpm_q = Q(op["rpm"], "rpm")

    solver = CentrifugalCompressorMeanline()
    loss = AungierCentrifugal()

    try:
        result = solver.solve(inlet, rpm_q, geom, loss)
    except RegimeOutOfValidity:
        return {
            "objectives": {
                "eta_tt": 0.0,
                "eta_ts": 0.0,
                "power": 0.0,
                "mass": estimate_mass_kg(r2),
                "M_rel": 9.99,  # signals out-of-validity to UI
            },
            "constraints": {"M_rel_under_choke": False},
            "status": "REGIME_OUT_OF_VALIDITY",
        }
    except Exception:
        # G2 / Item 3b (Verifier V): the original `except (MeanlineConvergenceError, Exception)`
        # was redundant — Exception already covers MeanlineConvergenceError. Simplified to a
        # single broad catch. No behavioral change: all solve failures are NON_CONVERGED.
        return {
            "objectives": {
                "eta_tt": 0.0,
                "eta_ts": 0.0,
                "power": 0.0,
                "mass": estimate_mass_kg(r2),
                "M_rel": 0.0,
            },
            "constraints": {"M_rel_under_choke": False},
            "status": "NON_CONVERGED",
        }

    power_kW = float(result.power_W.to("kW").magnitude)
    mass_kg = estimate_mass_kg(r2)
    M_rel = float(result.max_M_rel)

    return {
        "objectives": {
            "eta_tt": float(result.eta_tt),
            "eta_ts": float(result.eta_ts),
            "power": power_kW,
            "mass": mass_kg,
            "M_rel": M_rel,
        },
        "constraints": {"M_rel_under_choke": M_rel < 1.2},
        "status": "VALID",
    }


def _build_parameter_ranges(req: ExploreRequest) -> Dict[str, Any]:
    from cascade.explore.sobol_sampler import ParameterRange

    if not req.parameter_ranges:
        return _default_parameter_ranges()
    ranges: Dict[str, Any] = {}
    for name, pr in req.parameter_ranges.items():
        ranges[name] = ParameterRange(
            min=float(pr.min), max=float(pr.max), unit=pr.unit, scale=pr.scale
        )
    return ranges


def _explore_worker(project_id: str, req: ExploreRequest):
    from jobs import PROJECTS

    def worker(job: Job) -> Dict[str, Any]:
        from cascade.explore.sobol_sampler import SobolSampler

        ranges = _build_parameter_ranges(req)
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            sampler = SobolSampler(
                parameter_ranges=ranges, n_samples=req.n_samples, seed=req.seed
            )
            samples = sampler.generate()

        all_candidates: List[Dict[str, Any]] = []
        batch_size = max(1, len(samples) // 20)
        for i, sample in enumerate(samples):
            if job.cancelled:
                break
            params_serialisable = {
                k: float(v.magnitude) if hasattr(v, "magnitude") else v
                for k, v in sample.items()
            }
            result = _meanline_evaluator(sample)
            cid = uuid.uuid4().hex
            cand = {
                "id": cid,
                "job_id": job.id,
                "project_id": project_id,
                "index": i,
                "params": params_serialisable,
                "objectives": result["objectives"],
                "constraints": result["constraints"],
                "status": result["status"],
            }
            all_candidates.append(cand)
            CANDIDATE_INDEX[cid] = cand
            if (i + 1) % batch_size == 0 or i == len(samples) - 1:
                progress = (i + 1) / max(1, len(samples))
                report_progress(
                    job,
                    progress,
                    f"Evaluated {i + 1}/{len(samples)} candidates.",
                    data={
                        "candidates_batch": all_candidates[-batch_size:],
                        "n_total": len(samples),
                        "n_done": i + 1,
                    },
                )
                # Tiny sleep to keep SSE chatty and exercise the queue.
                time.sleep(0.002)

        CANDIDATES[job.id] = all_candidates
        # Compute best-in-space by the requested primary objective.
        valid = [c for c in all_candidates if c["status"] == "VALID"]
        best = None
        if valid:
            valid_sorted = sorted(
                valid,
                key=lambda c: c["objectives"].get(req.primary_objective, 0.0),
                reverse=not req.minimize_primary,
            )
            best = valid_sorted[0]
        PROJECTS[project_id]["last_run_status"] = "done"
        PROJECTS.save(project_id)
        return {
            "n_candidates": len(all_candidates),
            "n_valid": len(valid),
            "best_id": best["id"] if best else None,
            "primary_objective": req.primary_objective,
            "minimize_primary": req.minimize_primary,
        }

    return worker


@router.post("", response_model=JobAcceptedResponse)
async def explore_endpoint(project_id: str, req: ExploreRequest) -> JobAcceptedResponse:
    get_project_or_404(project_id)
    job = register_job(project_id, "explore")
    publish_event(
        job.id,
        {
            "job_id": job.id,
            "status": "queued",
            "progress": 0.0,
            "message": "Queued exploration.",
        },
    )
    run_in_worker(job, _explore_worker(project_id, req))
    return JobAcceptedResponse(job_id=job.id)
