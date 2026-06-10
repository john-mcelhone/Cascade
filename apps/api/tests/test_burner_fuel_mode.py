"""Burner fuel-mass-flow mode end-to-end (U7).

Pins the spec-mode contract for the Burner params bag:

- The spec builder branches on ``spec_mode`` (default ``outlet_temperature``,
  with legacy default-mode inference when the key is absent) and passes
  EXACTLY one of ``outlet_temperature`` / ``fuel_mass_flow`` to the core
  Burner — the merge-only PATCH means a flipped bag holds both forever.
- Retaining the inactive value is intentional: flipping back restores it
  (the merge-retention KTD).
- Degenerate fuel bags (no value, zero, NaN) refuse design-class — failed
  job + structured envelope, never a traceback.
- A derived TIT above 2100 K refuses via ``RegimeOutOfValidity`` with a
  suggestion that mentions reducing the fuel flow.
- Fuel mode on an air-standard / pure-fluid project refuses SYNCHRONOUSLY
  (HTTP 422 before any job is created).
- Component PATCH is save-through: spec_mode + fuel value survive a
  ``PROJECTS.reload()`` and the solve still branches correctly.
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


MICRO = "microturbine-30kw"
SEED_TIT_K = 1116.0  # Capstone C30 turbine inlet temperature (seed value)


@pytest.fixture
def app():
    jobs.reset_for_tests()
    return create_app()


async def _solve(client: httpx.AsyncClient, project_id: str) -> Dict[str, Any]:
    resp = await client.post(f"/api/projects/{project_id}/cycle/solve")
    assert resp.status_code == 200, resp.text
    job_id = resp.json()["job_id"]
    for _ in range(120):
        r = await client.get(f"/api/jobs/{job_id}")
        if r.json()["status"] in ("done", "failed", "cancelled"):
            break
        await asyncio.sleep(0.05)
    return (await client.get(f"/api/jobs/{job_id}")).json()


async def _component(
    client: httpx.AsyncClient, project_id: str, kind: str
) -> Dict[str, Any]:
    resp = await client.get(f"/api/projects/{project_id}/components")
    for c in resp.json()["components"]:
        if c["kind"] == kind:
            return c
    raise AssertionError(f"No {kind} component in project {project_id}")


async def _patch_burner(
    client: httpx.AsyncClient, project_id: str, params: Dict[str, Any]
) -> Dict[str, Any]:
    burner = await _component(client, project_id, "Burner")
    resp = await client.patch(
        f"/api/projects/{project_id}/components/{burner['id']}",
        json={"params": params},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _burner_tit_K(job: Dict[str, Any], burner_name: str = "B1") -> float:
    """Burner outlet (= turbine inlet) total temperature from the result."""
    port = job["result"]["ports"][burner_name]
    return float(port["temperature_total"]["value"])


def _fuel_flow_kg_s(job: Dict[str, Any]) -> float:
    return float(job["result"]["fuel_mass_flow"]["value"])


def _assert_design_refusal(job: Dict[str, Any]) -> Dict[str, Any]:
    """Refusal contract (U1): failed + envelope, error=None, no traceback."""
    assert job["status"] == "failed", job
    assert job["error"] is None
    failure = job["result"]["failure"]
    assert failure["kind"] == "design", failure
    assert "bug_log" not in failure or failure["bug_log"] is None
    return failure


# ---------------------------------------------------------------------------
# Params-bag matrix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tit_only_bag_solves_in_outlet_temperature_mode(app):
    """(1) TIT only (the seed bag) → solves, burner outlet pinned at TIT."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        job = await _solve(client, MICRO)

        assert job["status"] == "done", job
        assert job["result"]["converged"] is True
        assert _burner_tit_K(job) == pytest.approx(SEED_TIT_K, abs=1e-6)
        # Fuel flow is the back-derived output in this mode.
        assert _fuel_flow_kg_s(job) > 0.0


@pytest.mark.asyncio
async def test_fuel_only_bag_infers_fuel_mode(app):
    """(2) fuel only, no spec_mode → default-mode inference picks fuel mode."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        resp = await client.post(
            "/api/projects",
            json={"name": "fuel-only-bag", "template": "aero"},
        )
        assert resp.status_code == 201, resp.text
        pid = resp.json()["id"]
        for kind, name, params in (
            ("Compressor", "C1", {"pressure_ratio": 4.01, "efficiency_isentropic": 0.78}),
            ("Turbine", "T1", {"pressure_ratio": 3.8, "efficiency_isentropic": 0.84}),
            (
                "Burner",
                "B1",
                {
                    # NO outlet_temperature and NO spec_mode: a legacy
                    # fuel-only bag must infer fuel_mass_flow mode.
                    "fuel_mass_flow": {"value": 0.07, "unit": "kg/s"},
                    "pressure_drop_fraction": 0.04,
                    "combustion_efficiency": 0.99,
                },
            ),
        ):
            r = await client.post(
                f"/api/projects/{pid}/components",
                json={
                    "kind": kind,
                    "name": name,
                    "params": params,
                    "position": {"x": 100, "y": 100},
                },
            )
            assert r.status_code == 201, r.text

        job = await _solve(client, pid)

        assert job["status"] == "done", job
        assert job["result"]["converged"] is True
        # TIT is back-derived: above compressor discharge, below the limit.
        tit = _burner_tit_K(job, "B1")
        assert 500.0 < tit < 2100.0
        # The pinned fuel flow rides through to the result.
        assert _fuel_flow_kg_s(job) == pytest.approx(0.07, rel=1e-6)


@pytest.mark.asyncio
async def test_both_values_with_spec_mode_outlet_temperature(app):
    """(3) both values + spec_mode=outlet_temperature → TIT pinned exactly."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        await _patch_burner(
            client,
            MICRO,
            {
                "spec_mode": "outlet_temperature",
                "fuel_mass_flow": {"value": 0.0023, "unit": "kg/s"},
            },
        )
        # The merge-only PATCH retains BOTH values on the bag.
        burner = await _component(client, MICRO, "Burner")
        assert "outlet_temperature" in burner["params"]
        assert "fuel_mass_flow" in burner["params"]

        job = await _solve(client, MICRO)

        assert job["status"] == "done", job
        assert job["result"]["converged"] is True
        assert _burner_tit_K(job) == pytest.approx(SEED_TIT_K, abs=1e-6)


@pytest.mark.asyncio
async def test_both_values_with_spec_mode_fuel_mass_flow(app):
    """(4) both values + spec_mode=fuel_mass_flow → ṁ_f pinned, TIT derived."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        # Self-calibrate: the baseline TIT-mode solve back-derives the fuel
        # flow that produces exactly 1116 K. Pin 20 % MORE fuel, so the
        # derived TIT must land strictly above the stored 1116 K — proving
        # the solver honoured ṁ_f and not the (still present) TIT value.
        baseline = await _solve(client, MICRO)
        fuel_at_seed_tit = _fuel_flow_kg_s(baseline)
        fuel_pinned = 1.2 * fuel_at_seed_tit

        await _patch_burner(
            client,
            MICRO,
            {
                "spec_mode": "fuel_mass_flow",
                "fuel_mass_flow": {"value": fuel_pinned, "unit": "kg/s"},
            },
        )
        job = await _solve(client, MICRO)

        assert job["status"] == "done", job
        assert job["result"]["converged"] is True
        assert _fuel_flow_kg_s(job) == pytest.approx(fuel_pinned, rel=1e-6)
        assert _burner_tit_K(job) > SEED_TIT_K + 5.0
        # The stale outlet_temperature is retained on the bag but unused.
        burner = await _component(client, MICRO, "Burner")
        assert float(burner["params"]["outlet_temperature"]["value"]) == pytest.approx(
            SEED_TIT_K
        )


@pytest.mark.asyncio
async def test_fuel_mode_with_no_fuel_key_refuses_design_class(app):
    """(5) spec_mode=fuel_mass_flow, no fuel key → design refusal, no traceback."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        # The seed bag has no fuel_mass_flow key; flipping only the mode
        # leaves a degenerate bag.
        await _patch_burner(client, MICRO, {"spec_mode": "fuel_mass_flow"})

        job = await _solve(client, MICRO)

        failure = _assert_design_refusal(job)
        assert "burner" in failure["title"].lower()
        blob = " ".join(failure["suggestions"]).lower()
        assert "fuel" in blob


@pytest.mark.asyncio
async def test_fuel_flow_zero_refuses_not_zerodivision(app):
    """(6) fuel = 0 → design refusal naming the burner, not a ZeroDivision."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        await _patch_burner(
            client,
            MICRO,
            {
                "spec_mode": "fuel_mass_flow",
                "fuel_mass_flow": {"value": 0.0, "unit": "kg/s"},
            },
        )

        job = await _solve(client, MICRO)

        failure = _assert_design_refusal(job)
        # Specifically the burner-spec refusal, not the generic
        # ZeroDivisionError classification ("division by zero").
        assert "burner" in failure["title"].lower()
        assert "division" not in failure["title"].lower()
        assert "positive" in failure["plain_english"].lower()


@pytest.mark.asyncio
async def test_excess_fuel_derived_tit_above_limit_refuses(app):
    """(7) derived TIT > 2100 K → RegimeOutOfValidity, design class,
    suggestion mentions reducing the fuel flow."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        await _patch_burner(
            client,
            MICRO,
            {
                "spec_mode": "fuel_mass_flow",
                # ~0.012 kg/s on 0.31 kg/s air (f/a ≈ 3.9 %, still lean)
                # drives the derived TIT far past the 2100 K refusal line.
                "fuel_mass_flow": {"value": 0.012, "unit": "kg/s"},
            },
        )

        job = await _solve(client, MICRO)

        failure = _assert_design_refusal(job)
        text = (failure["title"] + " " + failure["plain_english"]).lower()
        assert "2100" in text or "material limit" in text
        assert any(
            "fuel" in s.lower() and "reduce" in s.lower()
            for s in failure["suggestions"]
        ), failure["suggestions"]


@pytest.mark.asyncio
async def test_fuel_mode_on_pure_fluid_project_422_synchronously(app):
    """(8a) sCO2 loop (pure fluid + air-standard heater) + fuel mode → 422."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        pid = "sco2-test-loop"
        await _patch_burner(
            client,
            pid,
            {
                "spec_mode": "fuel_mass_flow",
                "fuel_mass_flow": {"value": 0.002, "unit": "kg/s"},
            },
        )

        resp = await client.post(f"/api/projects/{pid}/cycle/solve")

        assert resp.status_code == 422, resp.text
        detail = resp.json()["detail"]
        assert detail["error_code"] == "FUEL_MODE_REQUIRES_COMBUSTION"
        assert "combustion" in detail["message"].lower()
        # Synchronous: no job was created for this refusal.
        jobs_resp = await client.get(f"/api/jobs?project_id={pid}")
        if jobs_resp.status_code == 200:
            assert all(
                j.get("status") != "running" for j in jobs_resp.json()
            )


@pytest.mark.asyncio
async def test_fuel_mode_on_air_standard_flag_project_422(app):
    """(8b) project-level settings.air_standard=true + fuel mode → 422."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        resp = await client.patch(
            f"/api/projects/{MICRO}",
            json={"settings": {"air_standard": True}},
        )
        assert resp.status_code == 200, resp.text
        await _patch_burner(
            client,
            MICRO,
            {
                "spec_mode": "fuel_mass_flow",
                "fuel_mass_flow": {"value": 0.002, "unit": "kg/s"},
            },
        )

        resp = await client.post(f"/api/projects/{MICRO}/cycle/solve")

        assert resp.status_code == 422, resp.text
        detail = resp.json()["detail"]
        assert detail["error_code"] == "FUEL_MODE_REQUIRES_COMBUSTION"
        assert "settings.air_standard" in detail["forced_by"]


# ---------------------------------------------------------------------------
# Mode round-trip (merge-retention KTD)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mode_round_trip_restores_retained_tit(app):
    """Fuel-mode run derives TIT; flipping back to TIT mode restores the
    original behaviour from the retained outlet_temperature value."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        baseline = await _solve(client, MICRO)
        assert baseline["status"] == "done"
        eta_baseline = baseline["result"]["thermal_efficiency"]
        fuel_baseline = _fuel_flow_kg_s(baseline)

        # Flip to fuel mode with deliberately more fuel.
        await _patch_burner(
            client,
            MICRO,
            {
                "spec_mode": "fuel_mass_flow",
                "fuel_mass_flow": {"value": 1.2 * fuel_baseline, "unit": "kg/s"},
            },
        )
        fuel_run = await _solve(client, MICRO)
        assert fuel_run["status"] == "done", fuel_run
        assert _burner_tit_K(fuel_run) > SEED_TIT_K + 5.0

        # Flip back — ONLY the mode. The retained outlet_temperature must
        # restore the original behaviour.
        await _patch_burner(client, MICRO, {"spec_mode": "outlet_temperature"})
        restored = await _solve(client, MICRO)

        assert restored["status"] == "done", restored
        assert _burner_tit_K(restored) == pytest.approx(SEED_TIT_K, abs=1e-6)
        assert restored["result"]["thermal_efficiency"] == pytest.approx(
            eta_baseline, abs=1e-9
        )
        # The fuel value is retained on the bag for the next flip.
        burner = await _component(client, MICRO, "Burner")
        assert float(burner["params"]["fuel_mass_flow"]["value"]) == pytest.approx(
            1.2 * fuel_baseline, rel=1e-9
        )


# ---------------------------------------------------------------------------
# Unit conversion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fuel_flow_unit_conversion_g_per_s(app):
    """PATCH {"value": 2.3, "unit": "g/s"} resolves to 0.0023 kg/s."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        await _patch_burner(
            client,
            MICRO,
            {
                "spec_mode": "fuel_mass_flow",
                "fuel_mass_flow": {"value": 2.3, "unit": "g/s"},
            },
        )

        job = await _solve(client, MICRO)

        assert job["status"] == "done", job
        assert job["result"]["converged"] is True
        assert _fuel_flow_kg_s(job) == pytest.approx(0.0023, rel=1e-6)


# ---------------------------------------------------------------------------
# TOML persistence (save-through PATCH)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spec_mode_and_fuel_survive_reload_and_branch(app):
    """PATCH spec_mode + fuel → PROJECTS.reload() → both survive AND the
    solve still branches to fuel mode. Save-through makes this pass: the
    PATCH itself persists to TOML (previously edits reached disk only when
    some worker happened to save)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        baseline = await _solve(client, MICRO)
        fuel_baseline = _fuel_flow_kg_s(baseline)
        fuel_pinned = 1.2 * fuel_baseline

        await _patch_burner(
            client,
            MICRO,
            {
                "spec_mode": "fuel_mass_flow",
                "fuel_mass_flow": {"value": fuel_pinned, "unit": "kg/s"},
            },
        )

        # Simulate a restart: drop the in-memory cache, re-read from disk.
        jobs.PROJECTS.reload()

        burner = await _component(client, MICRO, "Burner")
        assert burner["params"]["spec_mode"] == "fuel_mass_flow"
        assert float(burner["params"]["fuel_mass_flow"]["value"]) == pytest.approx(
            fuel_pinned, rel=1e-9
        )
        # The retained TIT also survives (merge-retention KTD).
        assert float(burner["params"]["outlet_temperature"]["value"]) == pytest.approx(
            SEED_TIT_K
        )

        job = await _solve(client, MICRO)
        assert job["status"] == "done", job
        assert job["result"]["converged"] is True
        assert _fuel_flow_kg_s(job) == pytest.approx(fuel_pinned, rel=1e-6)
        assert _burner_tit_K(job) > SEED_TIT_K + 5.0
