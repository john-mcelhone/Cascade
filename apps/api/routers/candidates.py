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

from jobs import CANDIDATE_INDEX, CANDIDATES
from models import CandidateModel


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
