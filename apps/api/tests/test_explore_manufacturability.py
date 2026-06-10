"""Explore-sweep manufacturability gate (SPEC §13).

The design-space sweep only promotes candidates a standard 5-axis
machining cell can physically produce: a candidate whose merged geometry
violates any manufacturability rule is statused MANUFACTURABILITY_FAILED
(keeping its REAL solved objectives so the scatter can show what the
un-makeable design would have achieved), carries the violated rule names
in error_message, and is excluded from VALID-only surfaces (best-in-space,
send-to-cycle).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = APP_DIR.parent.parent / "src"
for p in (str(APP_DIR), str(SRC_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from routers.explore import _meanline_evaluator  # noqa: E402


# Boundary cases from the Eckardt-scaled sweep space (r2 ∈ [15, 45] mm,
# Z ∈ [10, 18]): the main-to-splitter passage at 50% chord is the binding
# tool-access rule for small wheels.
MAKEABLE = {"rotor_outlet_radius": 0.030, "blade_count": 14, "tip_clearance": 3e-4}
TOO_MANY_BLADES = {"rotor_outlet_radius": 0.015, "blade_count": 18, "tip_clearance": 3e-4}
TOO_TIGHT_CLEARANCE = {"rotor_outlet_radius": 0.030, "blade_count": 12, "tip_clearance": 1.5e-4}


def test_makeable_candidate_is_valid_and_flagged_manufacturable():
    res = _meanline_evaluator(MAKEABLE)
    assert res["status"] == "VALID"
    assert res["constraints"]["manufacturable"] is True


def test_unmillable_blade_count_fails_with_real_objectives():
    res = _meanline_evaluator(TOO_MANY_BLADES)
    assert res["status"] == "MANUFACTURABILITY_FAILED"
    assert res["constraints"]["manufacturable"] is False
    # The mean-line solve succeeded — objectives are real, not zeroed.
    assert res["objectives"]["eta_tt"] > 0.5
    # The violated rule is named for the UI hover / candidate detail.
    assert "splitter_passage_min" in res["_error"]
    assert "5-axis" in res["_error"]


def test_sub_minimum_tip_clearance_fails():
    res = _meanline_evaluator(TOO_TIGHT_CLEARANCE)
    assert res["status"] == "MANUFACTURABILITY_FAILED"
    assert "tip_clearance_min" in res["_error"]


def test_project_overrides_loosen_the_gate():
    res = _meanline_evaluator(
        TOO_MANY_BLADES,
        mfg_overrides={
            "splitter_passage_min": 0.5e-3,
            "cutter_accessibility_min": 0.5e-3,
        },
    )
    assert res["status"] == "VALID"
    assert res["constraints"]["manufacturable"] is True


@pytest.mark.asyncio
async def test_sweep_excludes_failed_from_best_and_blocks_handoff():
    """End-to-end: run a small sweep; every candidate carries the
    manufacturable flag; failures carry rule names and cannot be sent to
    cycle; best-in-space is a manufacturable design."""
    import asyncio

    import httpx

    import jobs
    from main import create_app

    jobs.reset_for_tests()
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        body = {"n_samples": 32, "seed": 7, "primary_objective": "eta_tt"}
        resp = await client.post("/api/projects/microturbine-30kw/explore", json=body)
        assert resp.status_code == 200, resp.text
        job_id = resp.json()["job_id"]
        for _ in range(80):
            r = await client.get(f"/api/jobs/{job_id}")
            if r.json()["status"] in ("done", "failed"):
                break
            await asyncio.sleep(0.05)

        cands = (await client.get(
            "/api/candidates", params={"job_id": job_id, "limit": 1000}
        )).json()
        assert len(cands) == 32
        assert all("manufacturable" in c["constraints"] for c in cands)

        valid = [c for c in cands if c["status"] == "VALID"]
        failed = [c for c in cands if c["status"] == "MANUFACTURABILITY_FAILED"]
        # The default sweep space straddles the feasibility boundary —
        # both populations must exist.
        assert valid, "no manufacturable candidates in the default sweep"
        assert failed, "gate never fired across the default sweep space"
        assert all(c["constraints"]["manufacturable"] for c in valid)
        for c in failed:
            assert c["constraints"]["manufacturable"] is False
            assert c["error_message"] and "violated" in c["error_message"]

        # A failed candidate cannot be handed to the cycle.
        handoff = await client.post(
            f"/api/candidates/{failed[0]['id']}/send-to-cycle",
            json={"project_id": "microturbine-30kw"},
        )
        assert handoff.status_code == 422
        assert handoff.json()["detail"]["error_code"] == "CANDIDATE_NOT_VALID"
