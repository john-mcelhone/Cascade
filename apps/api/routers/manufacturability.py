"""Manufacturability check route (ADAPT-032).

Runs :func:`cascade.manufacturability.check_impeller` (or the radial-turbine
sister) against the active candidate of a project, applying any per-project
overrides stored under ``project.settings.manufacturability_overrides``.

Endpoint:

- ``GET /api/projects/{project_id}/manufacturability`` — run check, return the
  :class:`ManufacturabilityReport` JSON.
- ``PUT /api/projects/{project_id}/manufacturability/overrides`` — set the
  per-project override map; rule overrides persist in the TOML store.

The geometry consulted is the one the Flow Path PD page is currently
showing: the candidate parameters from the latest exploration job merged
into a machine-class-specific default geometry (see ``analysis.py`` for the
same merging pattern; we share its ``_CC_DEFAULTS`` / ``_RIT_DEFAULTS``
tables).
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from deps import get_project_or_404
from jobs import CANDIDATE_INDEX, CANDIDATES, PROJECTS

# Re-use the same defaults table the analysis route uses so the two pages
# agree on "what is the active candidate geometry?"
from routers.analysis import _CC_DEFAULTS, _RIT_DEFAULTS


router = APIRouter(
    prefix="/api/projects/{project_id}/manufacturability",
    tags=["manufacturability"],
)


class OverridesRequest(BaseModel):
    """Body for the PUT /overrides endpoint."""

    overrides: Dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(json_schema_extra={
        "example": {"overrides": {"le_thickness_min": 0.05e-3}},
    })


class ManufacturabilityResponse(BaseModel):
    """JSON shape of a :class:`ManufacturabilityReport` plus context."""

    machine_class: str
    geometry_name: str
    checked_at: str
    violations: list[Dict[str, Any]]
    passes: list[Dict[str, Any]]
    overrides_used: Dict[str, float]
    has_violations: bool
    critical_count: int
    warning_count: int
    rule_count: int
    # Echo back the geometry that was checked — the UI uses this to render
    # a "we measured X mm" tooltip.
    geometry: Dict[str, Any]
    candidate_id: Optional[str] = None


def _resolve_machine_class(project: Dict[str, Any]) -> str:
    """Resolve whether the project's active machine is a compressor or RIT.

    Mirrors :func:`apps.api.routers.analysis._resolve_machine_class` so the
    two endpoints agree on which solver/rule-set to fire.
    """
    components = project.get("components", []) or []
    kinds = {c.get("kind") for c in components}
    if "Compressor" in kinds and "Turbine" not in kinds:
        return "centrifugal_compressor"
    if "Turbine" in kinds and "Compressor" not in kinds:
        return "radial_turbine"
    # Mixed: prefer the compressor by default (the Flow Path PD page is
    # currently centrifugal-only in the hero demo).
    if "Compressor" in kinds:
        return "centrifugal_compressor"
    return "radial_turbine"


def _resolve_geometry(project: Dict[str, Any], machine_class: str) -> tuple[Any, str, Optional[str]]:
    """Build a geometry instance for the active candidate.

    Returns ``(geometry, geometry_name, candidate_id)``. We use the same
    merging strategy as the analysis route: the most-recent VALID candidate
    overrides the machine-class defaults. When no candidates exist we fall
    back to the defaults (this is the case on a fresh project).
    """
    defaults = dict(_CC_DEFAULTS if machine_class == "centrifugal_compressor"
                    else _RIT_DEFAULTS)
    candidate_id: Optional[str] = None
    candidate = None
    # Prefer the project's stored "best candidate" if the front end has
    # pinned one; otherwise pick the latest VALID candidate from the last
    # explore job.
    pinned = (project.get("settings", {}) or {}).get("active_candidate_id")
    if pinned and pinned in CANDIDATE_INDEX:
        candidate = CANDIDATE_INDEX[pinned]
        candidate_id = pinned
    else:
        # Walk the most recent job's candidates in reverse for a VALID one.
        for job_id in reversed(list(CANDIDATES.keys())):
            for cand in reversed(CANDIDATES.get(job_id, [])):
                if cand.get("project_id") == project.get("id") and \
                        cand.get("status") == "VALID":
                    candidate = cand
                    candidate_id = cand["id"]
                    break
            if candidate:
                break
    if candidate:
        for k, v in (candidate.get("params") or {}).items():
            if k in defaults:
                defaults[k] = v

    if machine_class == "centrifugal_compressor":
        from cascade.meanline import CentrifugalCompressorGeometry
        geom = CentrifugalCompressorGeometry(
            inducer_hub_radius=float(defaults["inducer_hub_radius"]),
            inducer_tip_radius=float(defaults["inducer_tip_radius"]),
            impeller_outlet_radius=float(defaults["impeller_outlet_radius"]),
            blade_height_outlet=float(defaults["blade_height_outlet"]),
            blade_count=int(defaults["blade_count"]),
            beta_2_metal_rad=float(defaults["beta_2_metal_rad"]),
            tip_clearance=float(defaults["tip_clearance"]),
        )
    else:
        from cascade.meanline import RadialTurbineGeometry
        geom = RadialTurbineGeometry(
            rotor_inlet_radius=float(defaults["rotor_inlet_radius"]),
            rotor_outlet_radius_hub=float(defaults["rotor_outlet_radius_hub"]),
            rotor_outlet_radius_tip=float(defaults["rotor_outlet_radius_tip"]),
            blade_height_inlet=float(defaults["blade_height_inlet"]),
            blade_height_outlet=float(defaults["blade_height_outlet"]),
            blade_count=int(defaults["blade_count"]),
            inlet_metal_angle_rad=float(defaults["inlet_metal_angle_rad"]),
            exducer_angle_rad=float(defaults["exducer_angle_rad"]),
            tip_clearance=float(defaults["tip_clearance"]),
        )
    name = project.get("name", project.get("id", "geometry"))
    return geom, name, candidate_id


def _geometry_summary(geometry: Any, machine_class: str) -> Dict[str, Any]:
    """Echo a small set of fields from the geometry for the UI panel."""
    if machine_class == "centrifugal_compressor":
        return {
            "inducer_hub_radius_m": float(geometry.inducer_hub_radius),
            "inducer_tip_radius_m": float(geometry.inducer_tip_radius),
            "impeller_outlet_radius_m": float(geometry.impeller_outlet_radius),
            "blade_height_outlet_m": float(geometry.blade_height_outlet),
            "blade_count": int(geometry.blade_count),
            "beta_2_metal_deg": math.degrees(float(geometry.beta_2_metal_rad)),
            "tip_clearance_m": float(geometry.tip_clearance),
        }
    return {
        "rotor_inlet_radius_m": float(geometry.rotor_inlet_radius),
        "rotor_outlet_radius_hub_m": float(geometry.rotor_outlet_radius_hub),
        "rotor_outlet_radius_tip_m": float(geometry.rotor_outlet_radius_tip),
        "blade_height_inlet_m": float(geometry.blade_height_inlet),
        "blade_height_outlet_m": float(geometry.blade_height_outlet),
        "blade_count": int(geometry.blade_count),
        "tip_clearance_m": float(geometry.tip_clearance),
    }


def _resolve_routed_candidate_geometry(
    project: Dict[str, Any], machine_class: str, candidate_id: str
) -> tuple[Any, str]:
    """Build the geometry for an explicitly routed ``candidate_id`` (U8).

    Unlike the active-candidate heuristic above (which key-merges the 3
    sampled params into the machine-class defaults), the routed path uses
    the normative merge helpers from ``_meanline_geom`` — the same rename +
    r2-scaling the explore evaluator and the geometry handoff use — so the
    candidate detail page's verdict is measured on the geometry the
    candidate actually resolves to.
    """
    cand = CANDIDATE_INDEX.get(candidate_id)
    if cand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Candidate {candidate_id!r} not found. Exploration "
                "candidates are held in memory and expire on server "
                "restart — re-run the exploration to regenerate them."
            ),
        )
    if cand.get("project_id") != project.get("id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Candidate {candidate_id!r} not found for project "
                f"{project.get('id')!r}."
            ),
        )
    from routers._meanline_geom import build_cc_geometry, build_rit_geometry

    builder = (
        build_cc_geometry
        if machine_class == "centrifugal_compressor"
        else build_rit_geometry
    )
    try:
        geom, _op = builder(sample=cand.get("params") or {})
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "CANDIDATE_GEOMETRY_INVALID",
                "message": (
                    "The candidate's parameters do not produce a valid "
                    f"geometry: {exc}"
                ),
            },
        ) from exc
    name = project.get("name", project.get("id", "geometry"))
    return geom, name


@router.get("", response_model=ManufacturabilityResponse)
def get_manufacturability(
    project_id: str,
    candidate_id: Optional[str] = Query(
        default=None,
        description=(
            "Check this specific exploration candidate instead of the "
            "pinned/latest-VALID heuristic. 404 when unknown or expired."
        ),
    ),
) -> ManufacturabilityResponse:
    """Run the manufacturability check on the project's active candidate.

    Pulls per-project overrides from
    ``project.settings.manufacturability_overrides`` and merges them into the
    rule set. Returns the report JSON with full violation / pass detail.

    With ``candidate_id`` (U8 — candidate detail page) the check runs on
    that candidate's merged geometry; otherwise the active candidate is
    resolved via ``settings.active_candidate_id`` or the latest VALID
    candidate of the most recent exploration job.
    """
    project = get_project_or_404(project_id)
    machine_class = _resolve_machine_class(project)
    if candidate_id is not None:
        geometry, geometry_name = _resolve_routed_candidate_geometry(
            project, machine_class, candidate_id
        )
    else:
        geometry, geometry_name, candidate_id = _resolve_geometry(
            project, machine_class
        )

    overrides = (project.get("settings", {}) or {}).get(
        "manufacturability_overrides", {}
    ) or {}
    # Make sure overrides are plain {str: float}; reject any malformed entries
    # silently rather than 500-ing the whole endpoint.
    sanitized_overrides: Dict[str, float] = {}
    for k, v in overrides.items():
        try:
            sanitized_overrides[str(k)] = float(v)
        except (TypeError, ValueError):
            continue

    from cascade.manufacturability import (
        check_impeller,
        check_radial_turbine,
    )
    if machine_class == "centrifugal_compressor":
        report = check_impeller(
            geometry, overrides=sanitized_overrides, name=geometry_name,
        )
    else:
        report = check_radial_turbine(
            geometry, overrides=sanitized_overrides, name=geometry_name,
        )

    payload = report.to_json()
    payload["machine_class"] = machine_class
    payload["geometry"] = _geometry_summary(geometry, machine_class)
    payload["candidate_id"] = candidate_id
    return ManufacturabilityResponse.model_validate(payload)


@router.put("/overrides", response_model=ManufacturabilityResponse)
def put_overrides(
    project_id: str,
    req: OverridesRequest = Body(default_factory=OverridesRequest),
) -> ManufacturabilityResponse:
    """Persist a per-project rule-override map and re-run the check."""
    project = get_project_or_404(project_id)
    settings = dict(project.get("settings", {}) or {})
    # Strip out any non-float entries before saving.
    sanitized: Dict[str, float] = {}
    for k, v in (req.overrides or {}).items():
        try:
            sanitized[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    settings["manufacturability_overrides"] = sanitized
    project["settings"] = settings
    PROJECTS.save(project_id)
    return get_manufacturability(project_id)
