"""Candidate detail + geometry routes.

The geometry endpoints depend on `cascade.geometry` which is being
written by a sibling agent. Until that lands we return a *stub* glTF —
an empty mesh wrapped in a minimal glb container — and tag the response
with `X-Cascade-Stub: true` so the front-end can show the wireframe
placeholder.
"""

from __future__ import annotations

import io
import struct
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Response, status

from jobs import CANDIDATE_INDEX, CANDIDATES, PROJECTS
from models import (
    CandidateModel,
    MergedGeometryResponse,
    PinCandidateRequest,
    PinCandidateResponse,
    SendToCycleRequest,
    SendToCycleResponse,
)


router = APIRouter(prefix="/api/candidates", tags=["candidates"])


# ---- Stub mesh authoring ---------------------------------------------------


def _stub_glb() -> bytes:
    """Build a valid minimal glb (glTF binary) containing an empty mesh.

    Returns a self-contained `.glb` byte string with header + JSON chunk
    only. Real meshes will be served once `cascade.geometry` is ready.
    """

    # Minimal glTF 2.0 JSON: one scene, one node, no mesh data.
    gltf_json = (
        b'{"asset":{"version":"2.0","generator":"cascade-api stub"},'
        b'"scene":0,"scenes":[{"nodes":[0]}],"nodes":[{"name":"stub"}]}'
    )
    # JSON chunk must be padded to 4-byte alignment with spaces (0x20).
    pad = (-len(gltf_json)) % 4
    if pad:
        gltf_json += b" " * pad
    json_chunk_len = len(gltf_json)
    # glb header: magic (4), version (4), length (4)
    chunk_header_len = 8
    total_len = 12 + chunk_header_len + json_chunk_len
    out = io.BytesIO()
    out.write(b"glTF")
    out.write(struct.pack("<I", 2))
    out.write(struct.pack("<I", total_len))
    out.write(struct.pack("<I", json_chunk_len))
    out.write(b"JSON")
    out.write(gltf_json)
    return out.getvalue()


def _stub_stl() -> bytes:
    """Empty binary STL — 80-byte header + uint32(0) triangle count."""

    return b"cascade-api stub STL".ljust(80, b"\0") + struct.pack("<I", 0)


# ---- Candidate routes ------------------------------------------------------


@router.get("", response_model=List[CandidateModel])
def list_candidates(
    job_id: Optional[str] = Query(default=None, description="Filter to one job's candidates."),
    limit: int = Query(default=500, ge=1, le=10000),
) -> List[CandidateModel]:
    """List candidates produced by exploration jobs.

    Without ``job_id`` returns the latest job's candidates (the design
    space currently in scope for the UI). With ``job_id`` returns that
    job's candidates.
    """

    if job_id is not None:
        cands = CANDIDATES.get(job_id, [])
    elif CANDIDATES:
        # Pick the most recently produced job.
        latest_job_id = list(CANDIDATES.keys())[-1]
        cands = CANDIDATES[latest_job_id]
    else:
        cands = []
    out = [CandidateModel.model_validate(c) for c in cands[:limit]]
    return out


@router.get("/{candidate_id}", response_model=CandidateModel)
def get_candidate(candidate_id: str) -> CandidateModel:
    cand = CANDIDATE_INDEX.get(candidate_id)
    if cand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate {candidate_id!r} not found.",
        )
    return CandidateModel.model_validate(cand)


# ---- Geometry handoff (U8) -------------------------------------------------
#
# One writer, one canonical location: "Send to cycle" is the product's only
# writer for cycle-component geometry. It serializes the result of
# ``build_cc_geometry(sample=candidate.params)`` — the same normative merge
# the explore evaluator ran (key rename, r2-scaling of inducer dimensions,
# candidate-scaled rpm) — and REPLACES the Compressor component's
# ``params.geometry_params`` subtree wholesale (never key-merge: under the
# refusal contract a stale partial bag would otherwise be permanently
# poisoned with no documented escape). The endpoint saves through
# ``PROJECTS.save`` because component PATCH-style in-place cache mutation
# does not flush to disk on its own.
#
# No project-level mirror is written (the project schema's to_legacy_dict
# drops a top-level geometry_params key — see the plan's KTD); the map path
# is intentionally unchanged.


def _candidate_scoped_or_404(candidate_id: str, project_id: str) -> Dict[str, Any]:
    """Resolve a candidate, guarding project scope.

    Cross-project access presents as not-found (the candidate does not
    exist *for this project*) — mirrors the detail page's route guard.
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
    if cand.get("project_id") != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Candidate {candidate_id!r} not found for project "
                f"{project_id!r}."
            ),
        )
    return cand


def _merged_cc_geometry(cand: Dict[str, Any]):
    """Run the normative merge for a candidate.

    Returns ``(geom, op, geometry_params)`` where ``geometry_params`` is the
    geometry dataclass serialized to plain SI floats (``None`` optionals are
    skipped — TOML cannot hold null, and the cycle builder treats absent
    keys as "use the solver default", which is exactly what ``None`` means
    on the dataclass).
    """
    import dataclasses as _dc

    from routers._meanline_geom import build_cc_geometry

    try:
        geom, op = build_cc_geometry(sample=cand.get("params", {}))
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "CANDIDATE_GEOMETRY_INVALID",
                "message": (
                    "The candidate's parameters do not produce a valid "
                    f"impeller geometry: {exc}"
                ),
            },
        ) from exc
    geometry_params: Dict[str, float] = {}
    for f in _dc.fields(geom):
        v = getattr(geom, f.name)
        if v is None:
            continue
        geometry_params[f.name] = float(v)
    return geom, op, geometry_params


def _design_point_solve(geom, op):  # type: ignore[no-untyped-def]
    """Solve the mean-line at the candidate's design point.

    Mirrors the explore evaluator's solve exactly (same solver, same loss
    model, same inlet construction) so the design-point pressure ratio used
    for alignment is the one the scatter point was scored at.
    """
    from cascade.meanline import AungierCentrifugal, CentrifugalCompressorMeanline
    from cascade.units import Composition, Port, Q

    inlet = Port(
        pressure_total=Q(op["pressure_total_Pa"], "Pa"),
        temperature_total=Q(op["temperature_total_K"], "K"),
        mass_flow=Q(op["mass_flow_kg_per_s"], "kg/s"),
        composition=Composition.air(),
    )
    solver = CentrifugalCompressorMeanline()
    return solver.solve(inlet, Q(op["rpm"], "rpm"), geom, AungierCentrifugal())


@router.get(
    "/{candidate_id}/merged-geometry", response_model=MergedGeometryResponse
)
def candidate_merged_geometry(
    candidate_id: str,
    project_id: str = Query(description="Project the candidate belongs to."),
) -> MergedGeometryResponse:
    """Return the full merged geometry set the candidate resolves to.

    This is the exact key set "Send to cycle" would write — the detail
    page renders it as the merged parameter table so the user sees the
    geometry actually used, not just the 3 sampled params.
    """
    from routers._meanline_geom import _EXPLORE_PARAM_MAP

    cand = _candidate_scoped_or_404(candidate_id, project_id)
    _geom, op, geometry_params = _merged_cc_geometry(cand)
    sampled_keys = [
        geom_key
        for sobol_key, geom_key in _EXPLORE_PARAM_MAP.items()
        if sobol_key in (cand.get("params") or {})
    ]
    return MergedGeometryResponse(
        candidate_id=candidate_id,
        machine_class="centrifugal_compressor",
        geometry_params=geometry_params,
        operating_point=dict(op),
        sampled_keys=sampled_keys,
        meanline_rpm_rpm=float(op["rpm"]),
    )


@router.post("/{candidate_id}/send-to-cycle", response_model=SendToCycleResponse)
def send_candidate_to_cycle(
    candidate_id: str, req: SendToCycleRequest
) -> SendToCycleResponse:
    """Write the candidate's merged geometry onto the project's Compressor.

    Replaces ``params.geometry_params`` WHOLESALE and sets
    ``params.meanline_rpm_rpm`` from the candidate-scaled rpm, then saves
    the project to the TOML store so the handoff survives a restart.

    With ``align_operating_point`` (default on) the endpoint also sets the
    compressor's ``pressure_ratio`` and the project boundary-condition mass
    flow to the candidate's design point, mirroring the Inlet component's
    params so the canvas chips stay truthful.
    """
    cand = _candidate_scoped_or_404(candidate_id, req.project_id)
    project = PROJECTS.get(req.project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {req.project_id!r} not found.",
        )
    if cand.get("status") != "VALID":
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "CANDIDATE_NOT_VALID",
                "message": (
                    f"Candidate {candidate_id!r} has status "
                    f"{cand.get('status')!r} — its own design point refused, "
                    "so its geometry cannot honestly drive the cycle "
                    "co-simulation."
                ),
                "suggestions": [
                    "Pick a VALID candidate from the scatter.",
                    "Re-run the exploration with narrower parameter ranges.",
                ],
            },
        )
    compressor = next(
        (
            c
            for c in project.get("components", []) or []
            if c.get("kind") == "Compressor"
        ),
        None,
    )
    if compressor is None:
        # Synchronous design-class refusal: a blank canvas can legitimately
        # host candidates, but there is nothing to write geometry onto.
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "NO_COMPRESSOR_COMPONENT",
                "message": (
                    "This project's cycle canvas has no Compressor "
                    "component to receive the candidate's geometry."
                ),
                "suggestions": [
                    "Add a Compressor to the cycle canvas, then send the candidate again.",
                    "The microturbine-30kw seed project is a working example you can copy from.",
                ],
            },
        )

    geom, op, geometry_params = _merged_cc_geometry(cand)
    params = compressor.setdefault("params", {})
    # REPLACE, never merge — a stale extra key from an earlier handoff (or
    # hand edit) must not survive into the new bag.
    params["geometry_params"] = geometry_params
    params["meanline_rpm_rpm"] = float(op["rpm"])

    aligned = False
    pressure_ratio: Optional[float] = None
    mass_flow: Optional[float] = None
    if req.align_operating_point:
        try:
            result = _design_point_solve(geom, op)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": "ALIGNMENT_SOLVE_FAILED",
                    "message": (
                        "Could not solve the candidate's design point to "
                        f"derive the cycle pressure ratio: {exc}"
                    ),
                    "suggestions": [
                        "Send without operating-point alignment (the cycle keeps its current PR and mass flow).",
                    ],
                },
            ) from exc
        pressure_ratio = float(result.pressure_ratio_tt)
        mass_flow = float(op["mass_flow_kg_per_s"])
        params["pressure_ratio"] = pressure_ratio
        bc = project.setdefault("boundary_conditions", {})
        bc["mass_flow"] = {"value": mass_flow, "unit": "kg/s"}
        # Mirror onto the Inlet component (the canvas node renders its own
        # params, and component PATCH mirrors the other way — keep the two
        # representations consistent).
        for comp in project.get("components", []) or []:
            if comp.get("kind") == "Inlet":
                comp.setdefault("params", {})["mass_flow"] = {
                    "value": mass_flow,
                    "unit": "kg/s",
                }
        aligned = True

    # Save-through: component-level cache mutation does not flush on its
    # own; an unsaved handoff would die on restart.
    PROJECTS.save(req.project_id)
    return SendToCycleResponse(
        project_id=req.project_id,
        candidate_id=candidate_id,
        component_id=str(compressor.get("id")),
        geometry_params=geometry_params,
        meanline_rpm_rpm=float(op["rpm"]),
        aligned=aligned,
        pressure_ratio=pressure_ratio,
        mass_flow_kg_per_s=mass_flow,
    )


@router.post("/{candidate_id}/pin", response_model=PinCandidateResponse)
def pin_candidate(
    candidate_id: str, req: PinCandidateRequest
) -> PinCandidateResponse:
    """Pin a candidate as the project's active candidate, persisted to TOML.

    Candidates are ephemeral (in-memory, die on restart); pins persist.
    Writes ``settings.active_candidate_id`` plus a full params snapshot
    under ``settings.pinned_candidates[cid]`` so the pinned design survives
    a server restart even after the candidate index is gone.
    """
    cand = _candidate_scoped_or_404(candidate_id, req.project_id)
    project = PROJECTS.get(req.project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {req.project_id!r} not found.",
        )
    # Snapshot only TOML-representable values (no None anywhere in the
    # candidate dict shape the explore worker builds).
    snapshot: Dict[str, Any] = {
        "id": cand["id"],
        "job_id": cand.get("job_id", ""),
        "index": int(cand.get("index", 0)),
        "params": dict(cand.get("params") or {}),
        "objectives": dict(cand.get("objectives") or {}),
        "constraints": dict(cand.get("constraints") or {}),
        "status": str(cand.get("status", "VALID")),
    }
    settings = project.setdefault("settings", {})
    settings["active_candidate_id"] = candidate_id
    pinned = settings.setdefault("pinned_candidates", {})
    pinned[candidate_id] = snapshot
    PROJECTS.save(req.project_id)
    return PinCandidateResponse(
        project_id=req.project_id,
        active_candidate_id=candidate_id,
        snapshot=snapshot,
    )


@router.get(
    "/{candidate_id}/geometry",
    responses={200: {"content": {"model/gltf-binary": {}}}},
)
def candidate_geometry(
    candidate_id: str,
    lod: str = Query(default="medium", description="One of: low, medium, hi"),
) -> Response:
    """Stream a browser-preview GLB for a candidate at the requested LOD.

    This endpoint is for in-browser visualisation only (``Content-Disposition:
    inline``).  The LOD is capped to HIGH — lower fidelity, faster transfer.
    For production export (full EXPORT-LOD GLB, ``Content-Disposition:
    attachment``), use GET ``/{candidate_id}/export.glb``.
    """
    if candidate_id not in CANDIDATE_INDEX:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")

    # Defer to cascade.geometry if available; otherwise emit a stub glb.
    payload, is_stub = _resolve_glb(candidate_id, lod)
    headers = {
        "X-Cascade-Stub": "true" if is_stub else "false",
        # Explicit inline disposition — this is a *preview*, not a download.
        "Content-Disposition": "inline",
    }
    return Response(content=payload, media_type="model/gltf-binary", headers=headers)


@router.get("/{candidate_id}/export.glb")
def candidate_export_glb(candidate_id: str) -> Response:
    if candidate_id not in CANDIDATE_INDEX:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    payload, is_stub = _resolve_glb(candidate_id, "hi")
    headers = {
        "Content-Disposition": f'attachment; filename="{candidate_id}.glb"',
        "X-Cascade-Stub": "true" if is_stub else "false",
    }
    return Response(content=payload, media_type="model/gltf-binary", headers=headers)


@router.get("/{candidate_id}/export.stl")
def candidate_export_stl(candidate_id: str) -> Response:
    if candidate_id not in CANDIDATE_INDEX:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    payload, is_stub = _resolve_stl(candidate_id)
    headers = {
        "Content-Disposition": f'attachment; filename="{candidate_id}.stl"',
        "X-Cascade-Stub": "true" if is_stub else "false",
    }
    return Response(content=payload, media_type="model/stl", headers=headers)


# ---------------------------------------------------------------------------
# CAD-universal exports — ADAPT-033 (STEP / IGES).
#
# These routes require the optional `cascade[cad]` extra (pythonocc-core).
# When the dep is missing we return HTTP 503 with a clear error body so
# the front-end can show the "STEP export not available — server needs
# `cascade[cad]` extra" toast described in ADAPT-033.
# ---------------------------------------------------------------------------


@router.get("/{candidate_id}/export_turbogrid.ndf")
def candidate_export_turbogrid_ndf(candidate_id: str) -> Response:
    """Download hub/shroud/blade curves in Ansys TurboGrid NDF format.

    Does NOT require ``cascade[cad]`` — the NDF is a pure ASCII point-data
    format that uses only the B-spline curve generators already in
    ``cascade.geometry``.

    Returns a single NDF text file with sections:
      [HUB_CURVE], [SHROUD_CURVE], [BLADE_PROFILE_HUB], [BLADE_PROFILE_SHROUD]

    Each blade-profile section carries (x, r, theta) columns so that
    TurboGrid can reconstruct the 3-D blade passage directly.
    """
    if candidate_id not in CANDIDATE_INDEX:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found",
        )

    import io

    try:
        from cascade.geometry import export_turbogrid_ndf  # type: ignore[attr-defined]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"failed to import cascade.geometry: {exc}",
        ) from exc

    cand = CANDIDATE_INDEX[candidate_id]
    params = cand.get("params", {})
    try:
        geometry = _geometry_from_candidate_params(params)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"failed to build geometry from candidate params: {exc}",
        ) from exc

    import tempfile
    from pathlib import Path as _Path

    with tempfile.TemporaryDirectory() as tdir:
        tmp_path = _Path(tdir) / f"{candidate_id}.ndf"
        try:
            export_turbogrid_ndf(
                geometry,
                tmp_path,
                n_hub=50,
                n_shroud=50,
                n_blade=30,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"NDF export failed: {exc}",
            ) from exc
        payload = tmp_path.read_text(encoding="ascii")

    return Response(
        content=payload,
        media_type="text/plain; charset=ascii",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{candidate_id}.ndf"'
            ),
        },
    )


@router.get("/{candidate_id}/export_fluid.step")
def candidate_export_fluid_step(candidate_id: str) -> Response:
    """Download the single-passage fluid volume as STEP AP203 with named patches.

    Implements W-17: returns the CFD-ready fluid passage (the air passage
    displaced by the impeller), not the solid impeller. Named faces
    (INLET, OUTLET, HUB, SHROUD, BLADE_SUCTION, BLADE_PRESSURE,
    PERIODIC_1, PERIODIC_2) are embedded in the STEP product metadata.

    Returns 503 Service Unavailable when ``pythonocc-core`` is not installed.

    When the Boolean sewing fails for complex geometry (Risk R-03), returns
    HTTP 200 with header ``X-Cascade-Warning: fluid-volume Boolean failed;
    shells exported instead`` and the individual named patch shells as fallback.
    """
    if candidate_id not in CANDIDATE_INDEX:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found",
        )

    import tempfile
    from pathlib import Path as _Path

    try:
        from cascade.geometry import (  # type: ignore[attr-defined]
            CADExportNotAvailable,
            export_fluid_volume_step,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Fluid-volume STEP export requires the cascade.geometry module. "
                f"Import failed: {exc}"
            ),
        ) from exc

    cand = CANDIDATE_INDEX[candidate_id]
    params = cand.get("params", {})

    try:
        geometry = _geometry_from_candidate_params(params)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"failed to build geometry from candidate params: {exc}",
        ) from exc

    with tempfile.TemporaryDirectory() as tdir:
        tmp_path = _Path(tdir) / f"{candidate_id}_fluid.step"
        try:
            result_meta = export_fluid_volume_step(geometry, tmp_path)
        except CADExportNotAvailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"Fluid-volume STEP export not available on this server. {exc}"
                ),
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"fluid-volume STEP export failed: {exc}",
            ) from exc

        payload = tmp_path.read_bytes()

    headers: Dict[str, Any] = {
        "Content-Disposition": (
            f'attachment; filename="{candidate_id}_fluid.step"'
        ),
    }
    if result_meta.get("fallback"):
        headers["X-Cascade-Warning"] = (
            "fluid-volume Boolean failed; shells exported instead"
        )

    return Response(
        content=payload,
        media_type="model/step",
        headers=headers,
    )


@router.get("/{candidate_id}/export.step")
def candidate_export_step(candidate_id: str) -> Response:
    """Download the candidate's geometry as STEP (ISO 10303-21).

    Returns 503 Service Unavailable with a plain-text install hint when
    the server does not have `pythonocc-core` installed.
    """
    if candidate_id not in CANDIDATE_INDEX:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found",
        )
    return _cad_export_response(candidate_id, fmt="step")


@router.get("/{candidate_id}/export.iges")
def candidate_export_iges(candidate_id: str) -> Response:
    """Download the candidate's geometry as IGES (US PRO v5.3)."""
    if candidate_id not in CANDIDATE_INDEX:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found",
        )
    return _cad_export_response(candidate_id, fmt="iges")


@router.get("/_cad/available")
def cad_export_capability() -> Dict[str, Any]:
    """Probe whether the server can fulfil STEP / IGES export requests.

    The web UI calls this once on page load to decide whether to render
    the STEP / IGES buttons as enabled or as "install the cad extra"
    tooltips.
    """
    try:
        from cascade.geometry import cad_export_available  # type: ignore[attr-defined]

        return {"available": bool(cad_export_available())}
    except Exception:
        return {"available": False}


def _cad_export_response(candidate_id: str, fmt: str) -> Response:
    """Resolve a CAD export (STEP or IGES) for the picked candidate.

    Returns 503 with a plain-text install hint when `pythonocc-core` is
    missing or the export raises a `CADExportNotAvailable` ImportError.
    Returns 500 with the error text for any other failure (so the
    front-end can show a useful message instead of a silent broken
    download).
    """
    import tempfile
    from pathlib import Path

    try:
        from cascade.geometry import (  # type: ignore[attr-defined]
            CADExportNotAvailable,
            MeshLOD,
            export_iges,
            export_step,
            impeller_mesh,
        )
    except Exception as exc:
        # cascade.geometry itself is broken/unavailable — degrade to a
        # clear server error rather than silently returning a stub.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "STEP/IGES export requires the cascade.geometry module. "
                f"Import failed: {exc}"
            ),
        ) from exc

    cand = CANDIDATE_INDEX[candidate_id]
    params = cand.get("params", {})

    # Build a Cascade geometry from the candidate's parameters. The
    # candidates currently in scope for this UI are centrifugal-impeller
    # design-space points (see jobs.py); the resolver below maps the
    # parameter dict to a `CentrifugalCompressorGeometry`.
    try:
        geometry = _geometry_from_candidate_params(params)
        mesh = impeller_mesh(geometry, lod=MeshLOD.EXPORT, with_splitter=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"failed to build mesh from candidate params: {exc}",
        ) from exc

    with tempfile.TemporaryDirectory() as tdir:
        tmp_path = Path(tdir) / f"{candidate_id}.{fmt}"
        try:
            if fmt == "step":
                export_step(mesh, tmp_path)
                media_type = "model/step"
            elif fmt == "iges":
                export_iges(mesh, tmp_path)
                media_type = "model/iges"
            else:  # pragma: no cover — guarded by the caller
                raise ValueError(f"unknown CAD format: {fmt}")
        except CADExportNotAvailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"STEP/IGES export not available on this server. {exc}"
                ),
            ) from exc
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

        payload = tmp_path.read_bytes()

    return Response(
        content=payload,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{candidate_id}.{fmt}"'
            ),
        },
    )


def _geometry_from_candidate_params(params: Dict[str, Any]):  # type: ignore[no-untyped-def]
    """Build a `CentrifugalCompressorGeometry` from a candidate dict.

    Mirrors the resolver used by `_resolve_glb` — accepts the loose
    parameter names emitted by the current Sobol exploration jobs and
    falls back to sane microturbine defaults for missing keys.
    """
    import math

    from cascade.meanline.centrifugal_compressor import (
        CentrifugalCompressorGeometry,
    )

    return CentrifugalCompressorGeometry(
        inducer_hub_radius=float(
            params.get("inducer_hub_radius", 0.018),
        ),
        inducer_tip_radius=float(
            params.get("inducer_tip_radius", 0.050),
        ),
        impeller_outlet_radius=float(
            params.get("impeller_outlet_radius", 0.100),
        ),
        blade_height_outlet=float(
            params.get("blade_height_outlet", 0.012),
        ),
        blade_count=int(params.get("blade_count", 18)),
        beta_2_metal_rad=float(
            params.get("beta_2_metal_rad", math.pi / 3),
        ),
        tip_clearance=float(params.get("tip_clearance", 0.0005)),
    )


def _resolve_glb(candidate_id: str, lod: str):
    """Try the real generator; fall back to stub. Returns (bytes, is_stub)."""

    try:
        from cascade.geometry import generate_impeller_glb  # type: ignore[attr-defined]
    except Exception:
        return _stub_glb(), True
    try:
        cand = CANDIDATE_INDEX[candidate_id]
        payload = generate_impeller_glb(params=cand.get("params", {}), lod=lod)
        return payload, False
    except Exception:
        return _stub_glb(), True


def _resolve_stl(candidate_id: str):
    try:
        from cascade.geometry import generate_impeller_stl  # type: ignore[attr-defined]
    except Exception:
        return _stub_stl(), True
    try:
        cand = CANDIDATE_INDEX[candidate_id]
        payload = generate_impeller_stl(params=cand.get("params", {}))
        return payload, False
    except Exception:
        return _stub_stl(), True
