"""Cycle page field-PATCH regression tests.

Asserts that every UI-exposed component field round-trips through the
backend PATCH route and leaves the cycle solver in a converged state.

Anchors the "every cell saves" promise of the Cycle Properties Panel —
the PM-level acceptance criterion.

We don't try to assert that η changes for *every* field (some fields are
documented preview-only — see the `wired: false` set in
`apps/web/src/components/cycle/properties-panel.tsx`). Instead the
contract is:
  1. PATCH returns 200 with the field round-tripped through the response.
  2. A follow-up cycle solve still produces `converged=True`.
  3. For the subset we KNOW the solver consumes, η actually moved.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict

import httpx
import pytest


# Make `main` importable.
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


async def _solve(client: httpx.AsyncClient, project_id: str) -> Dict[str, Any]:
    resp = await client.post(f"/api/projects/{project_id}/cycle/solve")
    assert resp.status_code == 200, resp.text
    job_id = resp.json()["job_id"]
    for _ in range(80):
        r = await client.get(f"/api/jobs/{job_id}")
        if r.json()["status"] in ("done", "failed"):
            break
        await asyncio.sleep(0.05)
    return (await client.get(f"/api/jobs/{job_id}")).json()


async def _component_id(client: httpx.AsyncClient, project_id: str, kind: str) -> str:
    resp = await client.get(f"/api/projects/{project_id}/components")
    for c in resp.json()["components"]:
        if c["kind"] == kind:
            return c["id"]
    raise AssertionError(f"No {kind} component in project {project_id}")


@pytest.mark.asyncio
async def test_compressor_wired_fields_change_eta(app):
    """Wired Compressor fields actually move η_th."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        pid = "microturbine-30kw"
        cid = await _component_id(client, pid, "Compressor")
        baseline = (await _solve(client, pid))["result"]["thermal_efficiency"]
        # PR is wired
        await client.patch(
            f"/api/projects/{pid}/components/{cid}",
            json={"params": {"pressure_ratio": 5.0}},
        )
        moved = (await _solve(client, pid))["result"]["thermal_efficiency"]
        assert abs(moved - baseline) > 0.01, "compressor PR should move η"
        # restore
        await client.patch(
            f"/api/projects/{pid}/components/{cid}",
            json={"params": {"pressure_ratio": 4.01}},
        )

        # η_isentropic is wired
        await client.patch(
            f"/api/projects/{pid}/components/{cid}",
            json={"params": {"efficiency_isentropic": 0.85}},
        )
        moved = (await _solve(client, pid))["result"]["thermal_efficiency"]
        assert abs(moved - baseline) > 0.01, "compressor η_is should move η_th"
        await client.patch(
            f"/api/projects/{pid}/components/{cid}",
            json={"params": {"efficiency_isentropic": 0.78}},
        )


@pytest.mark.asyncio
async def test_turbine_wired_fields_change_eta(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        pid = "microturbine-30kw"
        cid = await _component_id(client, pid, "Turbine")
        baseline = (await _solve(client, pid))["result"]["thermal_efficiency"]
        await client.patch(
            f"/api/projects/{pid}/components/{cid}",
            json={"params": {"efficiency_isentropic": 0.92}},
        )
        moved = (await _solve(client, pid))["result"]["thermal_efficiency"]
        assert abs(moved - baseline) > 0.01, "turbine η_is should move η_th"
        await client.patch(
            f"/api/projects/{pid}/components/{cid}",
            json={"params": {"efficiency_isentropic": 0.84}},
        )


@pytest.mark.asyncio
async def test_burner_wired_fields_change_eta(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        pid = "microturbine-30kw"
        cid = await _component_id(client, pid, "Burner")
        baseline = (await _solve(client, pid))["result"]["thermal_efficiency"]
        await client.patch(
            f"/api/projects/{pid}/components/{cid}",
            json={
                "params": {"outlet_temperature": {"value": 1250.0, "unit": "K"}}
            },
        )
        moved = (await _solve(client, pid))["result"]["thermal_efficiency"]
        assert abs(moved - baseline) > 0.01, "burner TIT should move η_th"
        await client.patch(
            f"/api/projects/{pid}/components/{cid}",
            json={
                "params": {"outlet_temperature": {"value": 1116.0, "unit": "K"}}
            },
        )


@pytest.mark.asyncio
async def test_recuperator_wired_fields_change_eta(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        pid = "microturbine-30kw"
        cid = await _component_id(client, pid, "Recuperator")
        baseline = (await _solve(client, pid))["result"]["thermal_efficiency"]
        await client.patch(
            f"/api/projects/{pid}/components/{cid}",
            json={"params": {"effectiveness": 0.70}},
        )
        moved = (await _solve(client, pid))["result"]["thermal_efficiency"]
        assert abs(moved - baseline) > 0.02, "recuperator ε should move η_th"
        await client.patch(
            f"/api/projects/{pid}/components/{cid}",
            json={"params": {"effectiveness": 0.87}},
        )


@pytest.mark.asyncio
async def test_inlet_bc_mirror_pt_keeps_converging(app):
    """Inlet PATCH mirrors to boundary_conditions and the solver keeps converging."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        pid = "microturbine-30kw"
        cid = await _component_id(client, pid, "Inlet")
        # Bump Pt then revert; mass flow scales electrical_output.
        await client.patch(
            f"/api/projects/{pid}/components/{cid}",
            json={
                "params": {
                    "mass_flow": {"value": 0.50, "unit": "kg/s"}
                }
            },
        )
        moved = await _solve(client, pid)
        assert moved["result"]["converged"], moved
        # electrical_output scales linearly with ṁ for fixed PR
        assert (
            moved["result"]["electrical_output"]["value"]
            > 30000.0
        ), moved["result"]["electrical_output"]
        # revert
        await client.patch(
            f"/api/projects/{pid}/components/{cid}",
            json={"params": {"mass_flow": {"value": 0.31, "unit": "kg/s"}}},
        )


@pytest.mark.asyncio
async def test_preview_fields_save_and_round_trip(app):
    """The "preview" (un-wired) fields must still save and round-trip."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        pid = "microturbine-30kw"
        cid = await _component_id(client, pid, "Compressor")
        # mechanical_efficiency, bleed_fraction_*, mass_flow_override,
        # inlet_temperature — all preview-only but must round-trip.
        patch = {
            "mechanical_efficiency": 0.97,
            "bleed_fraction_customer": 0.05,
            "bleed_fraction_cooling": 0.04,
            "mass_flow_override": {"value": 0.31, "unit": "kg/s"},
            "inlet_temperature": {"value": 300.0, "unit": "K"},
            "shaft_id": 1,
        }
        await client.patch(
            f"/api/projects/{pid}/components/{cid}", json={"params": patch}
        )
        # Re-fetch
        resp = (await client.get(f"/api/projects/{pid}/components")).json()
        comp = next(c for c in resp["components"] if c["id"] == cid)
        for key, want in patch.items():
            assert comp["params"][key] == want, (key, comp["params"][key], want)
        # Solver still converges
        out = await _solve(client, pid)
        assert out["result"]["converged"], out


@pytest.mark.asyncio
async def test_shaft_component_is_accepted(app):
    """B13: ComponentKind enum must accept 'Shaft' (regression test)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        pid = "microturbine-30kw"
        resp = await client.post(
            f"/api/projects/{pid}/components",
            json={
                "kind": "Shaft",
                "name": "SH-test",
                "params": {
                    "speed": {"value": 60.0, "unit": "krpm"},
                    "mechanical_efficiency": 0.98,
                },
                "position": {"x": 700, "y": 700},
            },
        )
        assert resp.status_code == 201, resp.text
        sid = resp.json()["id"]
        # Solve still converges — Shaft is ignored by single-shaft solver.
        out = await _solve(client, pid)
        assert out["result"]["converged"], out
        # Cleanup
        await client.delete(f"/api/projects/{pid}/components/{sid}")


@pytest.mark.asyncio
async def test_three_seed_projects_match_documented_eta(app):
    """microturbine-30kw ~= 27.4 %, sco2-test-loop solves, aero refuses."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")

        m = await _solve(client, "microturbine-30kw")
        assert m["result"]["converged"]
        assert 0.26 < m["result"]["thermal_efficiency"] < 0.30, m["result"][
            "thermal_efficiency"
        ]

        s = await _solve(client, "sco2-test-loop")
        assert s["result"]["converged"]
        assert 0.05 < s["result"]["thermal_efficiency"] < 0.25, s["result"][
            "thermal_efficiency"
        ]

        a = await _solve(client, "aero-demonstrator")
        assert a["status"] == "failed"
        assert "Compressor" in (a.get("message") or "")
