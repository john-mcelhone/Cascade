"""Smoke tests for the Cascade API.

Verifies:
- /api/health returns 200
- /api/projects returns the 3 seeded projects
- /api/projects/microturbine-30kw/cycle/solve schedules a job
- /api/jobs/:id returns the job
- /api/jobs/:id/events streams >=3 events, ending in `done`
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import List

import httpx
import pytest


# Make `main` importable from this test file.
APP_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = APP_DIR.parent.parent / "src"
for p in (str(APP_DIR), str(SRC_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from main import create_app  # noqa: E402
import jobs  # noqa: E402


@pytest.fixture
def app():
    jobs.reset_for_tests()
    return create_app()


@pytest.fixture
async def lifespan_client(app):
    """Yield an httpx AsyncClient with FastAPI's lifespan started.

    Starlette's lifespan must run for the on_event("startup") seed hook
    to populate the project store.
    """

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        # Trigger lifespan startup via ASGI
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as _bootstrap:
            pass  # noqa: PIE790
        yield client


@pytest.mark.asyncio
async def test_health(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # The Starlette lifespan needs to run for seed_projects to fire.
        # ASGITransport will execute startup when first request is made.
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "cascade-api"
    assert "version" in body


@pytest.mark.asyncio
async def test_lists_seeded_projects(app):
    """All canonical seed projects must be present after startup.

    The project count is not asserted as a magic number — instead we
    check that every project that seed.py is documented as seeding is
    present.  Adding a new seed project to seed.py without updating this
    list is intentional (new seed) not an error; removing a project from
    this list IS an error (regression against buyer-facing demo surface).
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # First request triggers startup
        _ = await client.get("/api/health")
        resp = await client.get("/api/projects")
    assert resp.status_code == 200
    projects = resp.json()
    # The four canonical seeds as of seed.py v1.
    # If a seed is added, add it here; never remove without a deprecation plan.
    required_ids = {
        "microturbine-30kw",  # Capstone C30 recuperated Brayton
        "sco2-test-loop",     # sCO2 Brayton prototype
        "at-100kw-prototype",  # AT-100 American Turbines target
        "aero-demonstrator",  # blank canvas template
    }
    ids = {p["id"] for p in projects}
    missing = required_ids - ids
    assert not missing, (
        f"Seeded project(s) missing from /api/projects response: {missing}. "
        f"Buyer-facing demo projects must always be present on startup."
    )
    assert len(projects) >= len(required_ids), (
        f"Expected at least {len(required_ids)} projects, got {len(projects)}."
    )


@pytest.mark.asyncio
async def test_project_detail_has_components(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        _ = await client.get("/api/health")
        resp = await client.get("/api/projects/microturbine-30kw")
    assert resp.status_code == 200
    proj = resp.json()
    assert proj["id"] == "microturbine-30kw"
    assert len(proj["components"]) > 0
    kinds = {c["kind"] for c in proj["components"]}
    assert "Compressor" in kinds
    assert "Turbine" in kinds
    assert "Burner" in kinds
    assert "Recuperator" in kinds


@pytest.mark.asyncio
async def test_cycle_solve_returns_job_id_and_streams(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        _ = await client.get("/api/health")
        resp = await client.post("/api/projects/microturbine-30kw/cycle/solve")
        assert resp.status_code == 200, resp.text
        job_id = resp.json()["job_id"]
        assert isinstance(job_id, str) and len(job_id) > 0

        # Job lookup
        for _ in range(20):
            r = await client.get(f"/api/jobs/{job_id}")
            assert r.status_code == 200
            if r.json()["status"] in ("done", "failed"):
                break
            await asyncio.sleep(0.05)

        # Stream events — collect at least 3 and assert "done" arrives.
        events: List[dict] = []
        async with client.stream("GET", f"/api/jobs/{job_id}/events") as stream:
            async for raw in stream.aiter_lines():
                if not raw:
                    continue
                if raw.startswith("event:"):
                    continue
                if raw.startswith("data:"):
                    payload = raw[len("data:"):].strip()
                    if not payload or payload == "{}":
                        continue
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    events.append(event)
                    if event.get("status") in ("done", "failed", "cancelled"):
                        break

        # We require >= 3 events and a terminal `done` event.
        statuses = [e.get("status") for e in events]
        assert len(events) >= 3, f"only {len(events)} events: {statuses}"
        assert any(s == "done" for s in statuses), f"no done event: {statuses}"

        # Final job state must be done with non-None result.
        r = await client.get(f"/api/jobs/{job_id}")
        body = r.json()
        assert body["status"] == "done"
        assert body["result"] is not None
        assert body["result"]["converged"] is True
        # ADAPT-012: every cycle solve must carry an energy_balance object so
        # the UI / auditor can see the Walsh-Fletcher convention end-to-end.
        eb = body["result"]["energy_balance"]
        assert eb is not None
        assert "sensible" in eb["convention"].lower()
        # Both residuals close to numerical precision (kW, <1e-3 of total flux)
        assert abs(eb["sensible_balance_residual_kW"]) < 1.0
        assert abs(eb["absolute_balance_residual_kW"]) < 1.0
        # Cycle-defining numbers are present and non-zero
        assert eb["compressor_work_in_kW"] > 0.0
        assert eb["turbine_work_out_kW"] > 0.0
        assert eb["burner_chemical_input_kW"] > 0.0


@pytest.mark.asyncio
async def test_loss_models_catalogue(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        _ = await client.get("/api/health")
        resp = await client.get("/api/loss-models")
    assert resp.status_code == 200
    models = resp.json()
    assert any("whitfield" in m["name"].lower() for m in models)
    assert any("citation" in m and m["citation"] for m in models)


@pytest.mark.asyncio
async def test_validation_cases(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        _ = await client.get("/api/health")
        resp = await client.get("/api/validation/cases")
    assert resp.status_code == 200
    cases = resp.json()
    assert len(cases) > 0
    case_ids = {c["id"] for c in cases}
    assert any("CYC-1" in cid or "CYC-3" in cid for cid in case_ids)


@pytest.mark.asyncio
async def test_analysis_endpoint_returns_real_solver_payload(app):
    """ADAPT-020: POST /api/projects/:id/analysis runs the real solver.

    The returned result must carry the structural fields the Analysis page
    binds to: efficiencies (η_tt, η_ts, η_polytropic), pressure ratios,
    velocity_triangles {inlet, exit}, port_states {inlet, exit},
    convergence_history, loss_breakdown with citations.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        _ = await client.get("/api/health")
        body = {
            "machine_class": "radial_turbine",
            "loss_model": "whitfield-baines-radial-v1",
            "geometry": {},
            "operating_point": {},
        }
        resp = await client.post(
            "/api/projects/microturbine-30kw/analysis", json=body
        )
        assert resp.status_code == 200, resp.text
        job_id = resp.json()["job_id"]
        for _ in range(40):
            r = await client.get(f"/api/jobs/{job_id}")
            if r.json()["status"] in ("done", "failed"):
                break
            await asyncio.sleep(0.05)
        final = (await client.get(f"/api/jobs/{job_id}")).json()
        assert final["status"] == "done", final
        result = final["result"]
        # No solver error
        assert "error" not in result, result.get("error")
        # Required structural fields
        assert "efficiencies" in result
        eta = result["efficiencies"]
        for k in ("eta_tt", "eta_ts", "eta_polytropic"):
            assert k in eta, k
        assert 0 < eta["eta_tt"] <= 1.0
        # η_ts must be the proper formula — generally below η_tt by more
        # than 1 pt for this Whitney-Stewart-class design at its design
        # operating point.
        assert eta["eta_ts"] < eta["eta_tt"]
        # Pressure ratios
        assert result["pressure_ratio_tt"] > 1.0
        assert result["pressure_ratio_ts"] > 1.0
        # Port states
        ps = result["port_states"]
        assert "inlet" in ps and "exit" in ps
        for side in ("inlet", "exit"):
            for k in ("T_static_K", "T_total_K", "p_static_Pa",
                     "p_total_Pa", "M", "s_J_per_kgK"):
                assert k in ps[side], (side, k)
        # Velocity triangles
        vt = result["velocity_triangles"]
        assert "inlet" in vt and "exit" in vt
        for side in ("inlet", "exit"):
            for k in ("U", "V", "W", "V_meridional", "V_theta",
                     "W_meridional", "W_theta", "alpha_flow_deg",
                     "beta_flow_deg"):
                assert k in vt[side], (side, k)
        # Convergence history
        assert len(result["convergence_history"]) > 0
        first = result["convergence_history"][0]
        for k in ("iter", "residual", "max_change"):
            assert k in first, k
        # Loss breakdown — each record carries a citation
        assert len(result["loss_breakdown"]) > 0
        loss = result["loss_breakdown"][0]
        for k in ("name", "delta_h_J_per_kg", "value_kJ_per_kg",
                  "citation"):
            assert k in loss, k
        assert loss["citation"]


@pytest.mark.asyncio
async def test_analysis_endpoint_centrifugal_compressor_path(app):
    """Smoke-test the centrifugal-compressor analysis path."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        _ = await client.get("/api/health")
        body = {
            "machine_class": "centrifugal_compressor",
            "loss_model": "aungier-centrifugal-v1",
            "geometry": {},
            "operating_point": {},
        }
        resp = await client.post(
            "/api/projects/microturbine-30kw/analysis", json=body
        )
        assert resp.status_code == 200, resp.text
        job_id = resp.json()["job_id"]
        for _ in range(40):
            r = await client.get(f"/api/jobs/{job_id}")
            if r.json()["status"] in ("done", "failed"):
                break
            await asyncio.sleep(0.05)
        final = (await client.get(f"/api/jobs/{job_id}")).json()
        assert final["status"] == "done"
        result = final["result"]
        assert "error" not in result, result.get("error")
        assert result["machine_class"] == "centrifugal_compressor"
        # Centrifugal-specific
        assert "slip_factor" in result
        assert 0 < result["slip_factor"] <= 1.0
        assert result["pressure_ratio_tt"] > 1.0


@pytest.mark.asyncio
async def test_candidate_geometry_returns_real_glb(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        _ = await client.get("/api/health")
        # Run a tiny exploration so we have a candidate to fetch.
        body = {"n_samples": 16, "seed": 7, "primary_objective": "eta_tt"}
        resp = await client.post("/api/projects/microturbine-30kw/explore", json=body)
        assert resp.status_code == 200, resp.text
        job_id = resp.json()["job_id"]
        # Wait for completion.
        for _ in range(40):
            r = await client.get(f"/api/jobs/{job_id}")
            if r.json()["status"] in ("done", "failed"):
                break
            await asyncio.sleep(0.05)

        # Grab candidate list and pick a VALID candidate (an
        # INVALID_GEOMETRY one is a 422 by contract, not a mesh).
        clist = await client.get("/api/candidates", params={"job_id": job_id})
        assert clist.status_code == 200
        candidates = clist.json()
        valid = [c for c in candidates if c.get("status") == "VALID"]
        assert len(valid) > 0
        cid = valid[0]["id"]

        # Real geometry: cascade.geometry is importable in the test env,
        # so the stub fallback must NOT be taken.
        geom = await client.get(f"/api/candidates/{cid}/geometry")
        assert geom.status_code == 200
        assert geom.headers.get("X-Cascade-Stub") == "false"
        # glTF binary magic
        assert geom.content[:4] == b"glTF"
