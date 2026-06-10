"""Candidate geometry wiring tests (Bug A regression).

Pins the single-source-of-truth contract: the mesh served by the geometry
and export endpoints is built from the SAME normative merge
(`build_cc_geometry`) that scored the candidate — not from raw parameter
keys with hardcoded defaults. Historically every candidate rendered as the
same r2=0.100 m default wheel because the Sobol params use the legacy
``rotor_outlet_radius`` key.

Also pins the stub policy: stub only when ``cascade.geometry`` is
unimportable; 422 ``CANDIDATE_GEOMETRY_INVALID`` for refusing parameters;
500 with detail for real generation failures.
"""

from __future__ import annotations

import io
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

import httpx
import pytest

APP_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = APP_DIR.parent.parent / "src"
for p in (str(APP_DIR), str(SRC_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from main import create_app  # noqa: E402
import jobs  # noqa: E402


def _seed_candidate(
    rotor_outlet_radius: float,
    blade_count: int,
    tip_clearance: float = 3e-4,
    project_id: str = "microturbine-30kw",
) -> str:
    cid = uuid.uuid4().hex
    jobs.CANDIDATE_INDEX[cid] = {
        "id": cid,
        "job_id": "test-job",
        "project_id": project_id,
        "index": 0,
        "params": {
            "rotor_outlet_radius": rotor_outlet_radius,
            "blade_count": blade_count,
            "tip_clearance": tip_clearance,
        },
        "objectives": {"eta_tt": 0.88, "eta_ts": 0.5, "power": 10.0,
                       "mass": 0.02, "M_rel": 0.6},
        "constraints": {"M_rel_under_choke": True},
        "status": "VALID",
    }
    return cid


@pytest.fixture
def app():
    jobs.reset_for_tests()
    return create_app()


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        yield c


def _radial_extent_of_glb(payload: bytes) -> float:
    import numpy as np
    import trimesh

    scene = trimesh.load(io.BytesIO(payload), file_type="glb")
    mesh = (
        trimesh.util.concatenate(list(scene.geometry.values()))
        if hasattr(scene, "geometry")
        else scene
    )
    v = mesh.vertices
    return float(np.hypot(v[:, 0], v[:, 1]).max())


@pytest.mark.asyncio
async def test_glb_bbox_scales_with_rotor_outlet_radius(client):
    cid_a = _seed_candidate(rotor_outlet_radius=0.020, blade_count=12)
    cid_b = _seed_candidate(rotor_outlet_radius=0.040, blade_count=16)

    extents = {}
    for cid, r2 in ((cid_a, 0.020), (cid_b, 0.040)):
        resp = await client.get(f"/api/candidates/{cid}/geometry")
        assert resp.status_code == 200, resp.text
        assert resp.headers["X-Cascade-Stub"] == "false"
        extent = _radial_extent_of_glb(resp.content)
        # The mesh's outer radius must be the candidate's r2, not the
        # historical 0.100 m default.
        assert extent == pytest.approx(r2, rel=0.15)
        extents[cid] = extent
    assert extents[cid_b] / extents[cid_a] == pytest.approx(2.0, rel=0.1)


@pytest.mark.asyncio
async def test_two_candidates_yield_different_meshes(client):
    cid_a = _seed_candidate(rotor_outlet_radius=0.020, blade_count=12)
    cid_b = _seed_candidate(rotor_outlet_radius=0.040, blade_count=16)
    a = await client.get(f"/api/candidates/{cid_a}/geometry")
    b = await client.get(f"/api/candidates/{cid_b}/geometry")
    assert a.status_code == b.status_code == 200
    assert a.content != b.content


@pytest.mark.asyncio
async def test_mesh_geometry_equals_merged_geometry_endpoint(client, monkeypatch):
    """The served mesh is built from exactly the merged geometry."""
    import dataclasses

    from cascade import geometry as cascade_geometry

    cid = _seed_candidate(rotor_outlet_radius=0.030, blade_count=14)

    captured: Dict[str, Any] = {}
    real_impeller_mesh = cascade_geometry.impeller_mesh

    def spy(geometry, *args, **kwargs):
        captured["geometry"] = geometry
        return real_impeller_mesh(geometry, *args, **kwargs)

    monkeypatch.setattr(cascade_geometry, "impeller_mesh", spy)

    resp = await client.get(f"/api/candidates/{cid}/geometry")
    assert resp.status_code == 200
    assert "geometry" in captured

    merged = await client.get(
        f"/api/candidates/{cid}/merged-geometry",
        params={"project_id": "microturbine-30kw"},
    )
    assert merged.status_code == 200, merged.text
    geometry_params = merged.json()["geometry_params"]

    served = {
        f.name: getattr(captured["geometry"], f.name)
        for f in dataclasses.fields(captured["geometry"])
        if getattr(captured["geometry"], f.name) is not None
    }
    for key, value in geometry_params.items():
        assert served[key] == pytest.approx(value, rel=1e-9), key


@pytest.mark.asyncio
async def test_merged_geometry_carries_meridional_polylines(client):
    """The merged-geometry response carries the meshed hub/shroud contours,
    and the exit passage height between them equals b2 + tip clearance."""
    import math

    cid = _seed_candidate(rotor_outlet_radius=0.030, blade_count=14)
    resp = await client.get(
        f"/api/candidates/{cid}/merged-geometry",
        params={"project_id": "microturbine-30kw"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    meridional = body["meridional"]
    assert len(meridional["hub"]) >= 50
    assert len(meridional["shroud"]) >= 50

    gp = body["geometry_params"]
    z_hub, r_hub = meridional["hub"][-1]
    z_sh, r_sh = meridional["shroud"][-1]
    te_gap = math.hypot(z_hub - z_sh, r_hub - r_sh)
    expected = gp["blade_height_outlet"] + gp["tip_clearance"]
    assert te_gap == pytest.approx(expected, rel=1e-6)


@pytest.mark.asyncio
async def test_invalid_candidate_geometry_is_422(client):
    cid = _seed_candidate(rotor_outlet_radius=-0.01, blade_count=12)
    resp = await client.get(f"/api/candidates/{cid}/geometry")
    assert resp.status_code == 422
    assert resp.json()["detail"]["error_code"] == "CANDIDATE_GEOMETRY_INVALID"


@pytest.mark.asyncio
async def test_generation_failure_is_500_not_stub(client, monkeypatch):
    from cascade import geometry as cascade_geometry

    cid = _seed_candidate(rotor_outlet_radius=0.030, blade_count=14)

    def boom(*args, **kwargs):
        raise RuntimeError("synthetic mesh failure")

    monkeypatch.setattr(cascade_geometry, "impeller_mesh", boom)
    resp = await client.get(f"/api/candidates/{cid}/geometry")
    assert resp.status_code == 500
    assert "mesh generation failed" in resp.text


@pytest.mark.asyncio
async def test_export_glb_serves_export_lod(client):
    """/export.glb is the EXPORT-LOD download — materially denser than the
    HIGH-LOD preview cap of the same candidate."""
    cid = _seed_candidate(rotor_outlet_radius=0.030, blade_count=14)
    preview_high = await client.get(
        f"/api/candidates/{cid}/geometry", params={"lod": "high"}
    )
    export = await client.get(f"/api/candidates/{cid}/export.glb")
    assert preview_high.status_code == export.status_code == 200
    assert len(export.content) > 1.5 * len(preview_high.content)


@pytest.mark.asyncio
async def test_lod_export_and_bogus_are_422(client):
    cid = _seed_candidate(rotor_outlet_radius=0.030, blade_count=14)
    for lod in ("export", "bogus"):
        resp = await client.get(
            f"/api/candidates/{cid}/geometry", params={"lod": lod}
        )
        assert resp.status_code == 422, lod


@pytest.mark.asyncio
async def test_stub_only_when_geometry_unimportable(client, monkeypatch):
    cid = _seed_candidate(rotor_outlet_radius=0.030, blade_count=14)
    # Simulate the cascade-absent dev environment: importing
    # cascade.geometry raises.
    monkeypatch.setitem(sys.modules, "cascade.geometry", None)
    resp = await client.get(f"/api/candidates/{cid}/geometry")
    assert resp.status_code == 200
    assert resp.headers["X-Cascade-Stub"] == "true"
    assert resp.content[:4] == b"glTF"


@pytest.mark.asyncio
async def test_manufacturability_panel_grades_the_picked_wheel(client):
    """The heuristic (no candidateId) manufacturability path must grade the
    candidate's merged geometry, not the machine-class defaults."""
    r2 = 0.030
    cid = _seed_candidate(rotor_outlet_radius=r2, blade_count=14)
    # Pin the candidate so the heuristic path selects it.
    pin = await client.post(
        f"/api/candidates/{cid}/pin", json={"project_id": "microturbine-30kw"}
    )
    assert pin.status_code == 200, pin.text

    resp = await client.get(
        "/api/projects/microturbine-30kw/manufacturability"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    geom = body.get("geometry") or {}
    assert geom.get("impeller_outlet_radius_m") == pytest.approx(r2, rel=1e-6)
