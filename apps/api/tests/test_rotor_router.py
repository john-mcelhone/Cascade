"""Tests for the eigensolver-backed rotor router (ADAPT-005 / 013 / 024 / 025).

Verifies the response shape and that:
- ``modes[].mode_shape`` carries (axial_position_m, y, z) per node so the UI
  can render real eigenvectors (ADAPT-005).
- ``campbell`` payload has ``speeds_rpm`` + per-mode ``frequencies_hz_at_speed``
  with whirl classification (ADAPT-013, Campbell half).
- ``critical_speed_map`` payload has ``stiffness_n_per_m`` + per-mode curves
  (ADAPT-013, CSM half).
- ``compliance`` payload lists API 684 §2.7.1.7 criticals with separation
  margin pass/fail (ADAPT-025).
- Anisotropic bearing payload with the K_yy / K_zz / K_yz / K_zy fields
  (ADAPT-024) is consumed without error.
"""

from __future__ import annotations

import asyncio
import sys
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


@pytest.fixture
def app():
    jobs.reset_for_tests()
    return create_app()


async def _wait_for_done(client: httpx.AsyncClient, job_id: str) -> Dict[str, Any]:
    for _ in range(40):
        r = await client.get(f"/api/jobs/{job_id}")
        if r.json()["status"] in ("done", "failed"):
            return r.json()
        await asyncio.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish")


@pytest.mark.asyncio
async def test_rotor_lateral_response_has_full_eigensolver_payload(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        _ = await client.get("/api/health")
        body = {
            "analysis": "lateral",
            "speed_range_rpm": [1000.0, 60000.0],
            "n_modes": 4,
        }
        resp = await client.post(
            "/api/projects/microturbine-30kw/rotor", json=body
        )
        assert resp.status_code == 200, resp.text
        job_id = resp.json()["job_id"]
        final = await _wait_for_done(client, job_id)
        assert final["status"] == "done", final
        result = final["result"]
        assert result is not None

        # Schema check
        assert "modes" in result
        assert "campbell" in result
        assert "critical_speed_map" in result
        assert "compliance" in result
        assert "shape" in result
        assert "bearings_used" in result

        # ADAPT-005: each mode carries a mode_shape array of nodes
        # with (axial_position_m, y, z) triples.
        assert len(result["modes"]) >= 1
        m0 = result["modes"][0]
        assert "mode_shape" in m0
        assert isinstance(m0["mode_shape"], list)
        assert len(m0["mode_shape"]) >= 2
        node0 = m0["mode_shape"][0]
        assert {"axial_position_m", "y", "z"}.issubset(node0.keys())
        # Normalised so the peak amplitude is <= 1.
        peak = max(
            abs(n["y"]) + abs(n["z"]) for n in m0["mode_shape"]
        )
        assert 0 < peak <= 1.001

        # ADAPT-013 Campbell half: speeds_rpm + modes
        c = result["campbell"]
        assert isinstance(c["speeds_rpm"], list) and len(c["speeds_rpm"]) > 4
        assert len(c["modes"]) == 4
        m_camp = c["modes"][0]
        assert "frequencies_hz_at_speed" in m_camp
        assert len(m_camp["frequencies_hz_at_speed"]) == len(c["speeds_rpm"])
        assert m_camp["whirl_classification"] in (
            "forward",
            "backward",
            "planar",
        )

        # ADAPT-013 CSM half: stiffness_n_per_m + modes
        csm = result["critical_speed_map"]
        assert isinstance(csm["stiffness_n_per_m"], list)
        assert len(csm["stiffness_n_per_m"]) > 6
        assert len(csm["modes"]) >= 1
        assert len(csm["modes"][0]["frequencies_hz_at_stiffness"]) == len(
            csm["stiffness_n_per_m"]
        )

        # ADAPT-025: compliance criticals
        comp = result["compliance"]
        assert "criticals" in comp
        for c in comp["criticals"]:
            assert {
                "rpm",
                "mode_id",
                "whirl",
                "amplification_factor",
                "separation_margin_pct",
                "required_margin_pct",
                "passes",
                "api_clause",
                "api_citation",
            }.issubset(c.keys())
            # Pass / fail is consistent with the margin comparison
            assert c["passes"] == (
                c["separation_margin_pct"] >= c["required_margin_pct"]
            )


@pytest.mark.asyncio
async def test_rotor_anisotropic_bearing_payload(app):
    """ADAPT-024: the router must consume the new K_yy / K_zz / ... shape."""

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        _ = await client.get("/api/health")
        body = {
            "analysis": "lateral",
            "speed_range_rpm": [1000.0, 60000.0],
            "n_modes": 3,
            "bearings": [
                {
                    "id": "B1",
                    "axial_position_mm": 0.0,
                    "K_yy_n_per_m": 1.0e8,
                    "K_zz_n_per_m": 2.0e8,
                    "K_yz_n_per_m": -1.0e6,
                    "K_zy_n_per_m": 1.0e6,
                    "C_yy_n_s_per_m": 2.0e3,
                    "C_zz_n_s_per_m": 3.0e3,
                    "C_yz_n_s_per_m": 0.0,
                    "C_zy_n_s_per_m": 0.0,
                },
                {
                    "id": "B2",
                    "axial_position_mm": 400.0,
                    "K_yy_n_per_m": 1.0e8,
                    "K_zz_n_per_m": 2.0e8,
                    "K_yz_n_per_m": 0.0,
                    "K_zy_n_per_m": 0.0,
                    "C_yy_n_s_per_m": 2.0e3,
                    "C_zz_n_s_per_m": 3.0e3,
                    "C_yz_n_s_per_m": 0.0,
                    "C_zy_n_s_per_m": 0.0,
                },
            ],
        }
        resp = await client.post(
            "/api/projects/microturbine-30kw/rotor", json=body
        )
        assert resp.status_code == 200, resp.text
        job_id = resp.json()["job_id"]
        final = await _wait_for_done(client, job_id)
        assert final["status"] == "done", final["error"] or final
        result = final["result"]
        assert result["bearings_used"][0]["kind"] == "LinearBearing"
        assert len(result["modes"]) == 3


@pytest.mark.asyncio
async def test_rotor_legacy_isotropic_bearing_payload_still_works(app):
    """Legacy v1 isotropic shape (stiffness_N_per_m / damping_N_s_per_m)
    must remain accepted so the existing UI keeps compiling."""

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        _ = await client.get("/api/health")
        body = {
            "analysis": "lateral",
            "speed_range_rpm": [1000.0, 50000.0],
            "n_modes": 3,
            "bearings": [
                {
                    "id": "B1",
                    "axial_position_mm": 0.0,
                    "stiffness_N_per_m": 5.0e7,
                    "damping_N_s_per_m": 1.0e3,
                },
                {
                    "id": "B2",
                    "axial_position_mm": 400.0,
                    "stiffness_N_per_m": 5.0e7,
                    "damping_N_s_per_m": 1.0e3,
                },
            ],
        }
        resp = await client.post(
            "/api/projects/microturbine-30kw/rotor", json=body
        )
        assert resp.status_code == 200, resp.text
        final = await _wait_for_done(client, resp.json()["job_id"])
        assert final["status"] == "done"
        assert final["result"] is not None
