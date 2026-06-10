"""Live mean-line surfacing and attribution on the Cycle page (U9).

End-to-end pins for the ADAPT-045 contract, driven through the real HTTP
surface wherever possible (explore → candidate handoff → solve):

- Geometry attached at the candidate's design point (U8 aligned handoff):
  the co-sim converges, the compressor η differs measurably from the
  constant-η run, and the payload attributes it —
  ``efficiency_modes`` / ``requested_efficiency_modes`` /
  ``efficiency_fallbacks`` / ``component_efficiencies``.
- Geometry far off-design (handoff WITHOUT alignment): design-class
  refusal — job ``failed``, ``error`` None, envelope with suggestions,
  cause code in the live-meanline family.
- Live mean-line selected with NO geometry: the solve completes on the
  constant-η fallback, and the payload says so explicitly (requested
  ``live_meanline``, actual ``constant``, fallback flag) — AE4: never an
  unlabelled isentropic number.
- Geometry ATTACHED but missing required keys: design-class refusal
  naming the key(s) (``GEOMETRY_PARAMS_INCOMPLETE``), not a silent
  fallback and not a traceback.
- Unknown unit inside an attached bag: design-class refusal
  (``UNKNOWN_UNIT``), not a bug-class traceback.
- Mode flip back to isentropic: the result matches the original
  constant-η run and ``geometry_params`` is retained in the bag (the
  merge-retention KTD).
- Recuperated + live mean-line (the documented hard case): terminates
  within the iteration cap — converges or refuses, never hangs.

Operating-point note: U8's alignment writes the compressor PR and the
boundary-condition mass flow, but NOT the turbine PR. On the C30 seed the
stored turbine PR is derived from the seed PR's pressure-drop chain, so an
aligned (lower) compressor PR leaves the turbine over-expanding →
``OPEN_CYCLE_SUB_ATMOSPHERIC``. The tests therefore rebalance the turbine
PR from the project's own pressure-drop chain (the same identity
``capstone_c30.turbine_pressure_ratio`` documents, and the same fix the
refusal envelope suggests) before solving.
"""

from __future__ import annotations

import asyncio
import math
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

# Accepted refusal codes for the off-design / hard-case scenarios: the
# mean-line either refuses the operating point outright or the Aitken
# outer loop fails to settle — both are honest design-class outcomes.
_LIVE_MEANLINE_REFUSAL_CODES = {
    "LIVE_MEANLINE_REGIME_REFUSED",
    "LIVE_MEANLINE_OUTER_NONCONVERGENT",
    "LIVE_MEANLINE_ETA_OUT_OF_RANGE",
}

# A complete compressor bag (Eckardt-A scaled to the Capstone regime —
# same numbers as tests/integration/test_cycle_cosim.py) for the
# unknown-unit scenario, which needs every required key present.
_SCALE = math.sqrt(0.31 / 5.31)
_COMPLETE_CC_GEOMETRY: Dict[str, Any] = {
    "inducer_hub_radius": 0.045 * _SCALE,
    "inducer_tip_radius": 0.140 * _SCALE,
    "impeller_outlet_radius": 0.200 * _SCALE,
    "blade_height_outlet": 0.026 * _SCALE,
    "blade_count": 16,
    "beta_2_metal_rad": math.pi / 6,
    "tip_clearance": 1.5e-4,
}


@pytest.fixture
def app():
    jobs.reset_for_tests()
    return create_app()


async def _wait_job(client: httpx.AsyncClient, job_id: str) -> Dict[str, Any]:
    """Bounded wait — the no-hang guard for every scenario below."""
    for _ in range(400):
        r = await client.get(f"/api/jobs/{job_id}")
        if r.json()["status"] in ("done", "failed", "cancelled"):
            return r.json()
        await asyncio.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish within the wait cap")


async def _run_explore(
    client: httpx.AsyncClient, project_id: str, n: int = 8, seed: int = 0
) -> Dict[str, Any]:
    resp = await client.post(
        f"/api/projects/{project_id}/explore",
        json={"n_samples": n, "seed": seed},
    )
    assert resp.status_code == 200, resp.text
    job = await _wait_job(client, resp.json()["job_id"])
    assert job["status"] == "done", job
    return job


async def _component(
    client: httpx.AsyncClient, project_id: str, kind: str
) -> Dict[str, Any]:
    r = await client.get(f"/api/projects/{project_id}/components")
    assert r.status_code == 200, r.text
    return next(c for c in r.json()["components"] if c["kind"] == kind)


async def _patch_params(
    client: httpx.AsyncClient,
    project_id: str,
    component_id: str,
    params: Dict[str, Any],
) -> None:
    r = await client.patch(
        f"/api/projects/{project_id}/components/{component_id}",
        json={"params": params},
    )
    assert r.status_code == 200, r.text


async def _solve(client: httpx.AsyncClient, project_id: str) -> Dict[str, Any]:
    r = await client.post(f"/api/projects/{project_id}/cycle/solve")
    assert r.status_code == 200, r.text
    return await _wait_job(client, r.json()["job_id"])


def _consistent_turbine_pr(components: Any, pr_c: float) -> float:
    """Turbine PR from the project's own pressure-drop chain.

    First-principles oracle (mirrors capstone_c30.turbine_pressure_ratio):
    start at 1 atm, end at 1 atm; the turbine expands across whatever the
    compressor built minus the chain of fractional drops.
    """
    by_kind = {c["kind"]: c.get("params", {}) for c in components}
    pdrop_inlet = float(
        by_kind.get("ConstantPressureLoss", {}).get("pressure_drop_fraction", 0.0)
    )
    recup = by_kind.get("Recuperator", {})
    pdrop_cold = float(recup.get("cold_pressure_drop_fraction", 0.0))
    pdrop_hot = float(recup.get("hot_pressure_drop_fraction", 0.0))
    pdrop_burner = float(by_kind.get("Burner", {}).get("pressure_drop_fraction", 0.0))
    p_burner_out_atm = (
        (1.0 - pdrop_inlet) * pr_c * (1.0 - pdrop_cold) * (1.0 - pdrop_burner)
    )
    p_turbine_out_atm = 1.0 / (1.0 - pdrop_hot)
    return p_burner_out_atm / p_turbine_out_atm


async def _aligned_handoff(client: httpx.AsyncClient) -> Dict[str, Any]:
    """Explore → best candidate → send-to-cycle WITH alignment, then
    rebalance the turbine PR from the pressure-drop chain (see module
    docstring). Returns the send-to-cycle response body."""
    job = await _run_explore(client, MICRO)
    best_id = job["result"]["best_id"]
    assert best_id is not None
    resp = await client.post(
        f"/api/candidates/{best_id}/send-to-cycle",
        json={"project_id": MICRO, "align_operating_point": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["aligned"] is True

    components = (
        await client.get(f"/api/projects/{MICRO}/components")
    ).json()["components"]
    turbine = next(c for c in components if c["kind"] == "Turbine")
    pr_t = _consistent_turbine_pr(components, float(body["pressure_ratio"]))
    await _patch_params(client, MICRO, turbine["id"], {"pressure_ratio": pr_t})
    return body


def _refusal_cause_code_via_worker(project_id: str) -> jobs.JobRefusal:
    """Run the cycle worker directly and return the JobRefusal it raises —
    the only surface that exposes the stable cause code."""
    from routers.cycle import _cycle_worker

    job = jobs.register_job(project_id, "cycle")
    with pytest.raises(jobs.JobRefusal) as exc_info:
        _cycle_worker(project_id)(job)
    return exc_info.value


# ---------------------------------------------------------------------------
# Geometry attached at the design point → converges with attribution;
# mode flip back → matches the constant-η run, geometry retained.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_design_point_live_meanline_converges_and_attributes(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        await _aligned_handoff(client)
        compressor = await _component(client, MICRO, "Compressor")
        comp_name = compressor["name"]
        stored_eta = float(compressor["params"]["efficiency_isentropic"])

        # Baseline: constant-η run at the aligned operating point.
        baseline = await _solve(client, MICRO)
        assert baseline["status"] == "done", baseline
        base_res = baseline["result"]
        assert base_res["converged"] is True
        assert base_res["efficiency_modes"][comp_name] == "constant"
        assert base_res["requested_efficiency_modes"][comp_name] == "constant"
        assert base_res["efficiency_fallbacks"][comp_name] is False
        assert base_res["component_efficiencies"][comp_name] == pytest.approx(
            stored_eta
        )

        # Live mean-line run: same geometry, mode flipped.
        await _patch_params(
            client, MICRO, compressor["id"], {"efficiency_mode": "live_meanline"}
        )
        live = await _solve(client, MICRO)
        assert live["status"] == "done", live
        live_res = live["result"]
        assert live_res["converged"] is True
        assert live_res["efficiency_modes"][comp_name] == "live_meanline"
        assert live_res["requested_efficiency_modes"][comp_name] == "live_meanline"
        assert live_res["efficiency_fallbacks"][comp_name] is False
        # Payload carries per-component η for BOTH rotors.
        eta_live = live_res["component_efficiencies"][comp_name]
        turbine = await _component(client, MICRO, "Turbine")
        assert turbine["name"] in live_res["component_efficiencies"]
        # The geometry-derived η differs measurably from the stored value
        # and is physically plausible.
        assert abs(eta_live - stored_eta) > 1e-4, (
            f"live η {eta_live} indistinguishable from stored {stored_eta}"
        )
        assert 0.5 < eta_live < 0.97
        # ...and the coupling moves the cycle answer.
        assert abs(
            live_res["thermal_efficiency"] - base_res["thermal_efficiency"]
        ) > 1e-4

        # Mode flip back to isentropic: matches the original constant-η run;
        # geometry_params retained in the bag (merge-retention KTD).
        await _patch_params(
            client, MICRO, compressor["id"], {"efficiency_mode": "isentropic"}
        )
        flipback = await _solve(client, MICRO)
        assert flipback["status"] == "done", flipback
        flip_res = flipback["result"]
        assert flip_res["converged"] is True
        assert flip_res["thermal_efficiency"] == pytest.approx(
            base_res["thermal_efficiency"]
        )
        assert flip_res["component_efficiencies"][comp_name] == pytest.approx(
            stored_eta
        )
        assert flip_res["efficiency_modes"][comp_name] == "constant"
        # Flipping the mode never strips the bag — detach is the sanctioned
        # escape hatch, not a side effect.
        compressor = await _component(client, MICRO, "Compressor")
        assert "geometry_params" in compressor["params"]
        assert len(compressor["params"]["geometry_params"]) >= 7
        assert "meanline_rpm_rpm" in compressor["params"]


# ---------------------------------------------------------------------------
# Geometry far off-design (no alignment) → design-class refusal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_off_design_geometry_refuses_design_class(app):
    """Handoff WITHOUT alignment leaves the seed's operating point driving
    a candidate geometry sized for a different design point. The smallest
    VALID candidate makes the mismatch unambiguous; the honest outcome is
    a live-meanline design-class refusal, not a number."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        await _run_explore(client, MICRO)
        cands = (await client.get("/api/candidates")).json()
        valid = [c for c in cands if c["status"] == "VALID"]
        assert valid, "explore produced no VALID candidates"
        smallest = min(valid, key=lambda c: c["params"]["rotor_outlet_radius"])

        resp = await client.post(
            f"/api/candidates/{smallest['id']}/send-to-cycle",
            json={"project_id": MICRO, "align_operating_point": False},
        )
        assert resp.status_code == 200, resp.text

        compressor = await _component(client, MICRO, "Compressor")
        await _patch_params(
            client, MICRO, compressor["id"], {"efficiency_mode": "live_meanline"}
        )

        # U1 refusal contract over HTTP: failed + error None + envelope.
        job = await _solve(client, MICRO)
        assert job["status"] == "failed", job
        assert job["error"] is None
        failure = job["result"]["failure"]
        assert failure["kind"] == "design"
        assert failure["suggestions"], "refusal envelope must carry suggestions"

        # Stable cause code (direct worker — the job dict doesn't carry it).
        refusal = _refusal_cause_code_via_worker(MICRO)
        assert refusal.cause_code in _LIVE_MEANLINE_REFUSAL_CODES, (
            refusal.cause_code
        )


# ---------------------------------------------------------------------------
# Mode selected, no geometry → flagged fallback (AE4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_meanline_without_geometry_falls_back_flagged(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        compressor = await _component(client, MICRO, "Compressor")
        comp_name = compressor["name"]
        assert "geometry_params" not in compressor["params"]
        await _patch_params(
            client, MICRO, compressor["id"], {"efficiency_mode": "live_meanline"}
        )

        job = await _solve(client, MICRO)
        assert job["status"] == "done", job
        res = job["result"]
        assert res["converged"] is True
        # Requested vs actual: the user asked for live mean-line, the solve
        # used constant η — and the payload says so explicitly.
        assert res["requested_efficiency_modes"][comp_name] == "live_meanline"
        assert res["efficiency_modes"][comp_name] == "constant"
        assert res["efficiency_fallbacks"][comp_name] is True
        # The turbine (isentropic) is NOT flagged.
        turbine = await _component(client, MICRO, "Turbine")
        assert res["efficiency_fallbacks"][turbine["name"]] is False
        # The η used is the stored constant value.
        assert res["component_efficiencies"][comp_name] == pytest.approx(
            float(compressor["params"]["efficiency_isentropic"])
        )


# ---------------------------------------------------------------------------
# Geometry attached but missing required keys → GEOMETRY_PARAMS_INCOMPLETE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attached_incomplete_geometry_refuses_naming_keys(app):
    """ADAPT-045 over the wire: a partial bag PATCHed directly onto the
    component (the web form never ships geometry_params; this is the raw
    API path) refuses design-class and names the missing key(s)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        compressor = await _component(client, MICRO, "Compressor")
        await _patch_params(
            client,
            MICRO,
            compressor["id"],
            {
                "efficiency_mode": "live_meanline",
                "geometry_params": {"blade_count": 16},
            },
        )

        job = await _solve(client, MICRO)
        assert job["status"] == "failed", job
        assert job["error"] is None
        failure = job["result"]["failure"]
        assert failure["kind"] == "design", failure
        assert "incomplete" in failure["title"].lower()
        # The envelope names the missing keys, not just "invalid".
        named = failure["plain_english"] + str(failure.get("details", ""))
        assert "impeller_outlet_radius" in named
        assert failure["suggestions"]
        # Stable shape on refusal: the attribution dicts are present, empty.
        assert job["result"]["requested_efficiency_modes"] == {}
        assert job["result"]["efficiency_fallbacks"] == {}

        # Stable cause code.
        refusal = _refusal_cause_code_via_worker(MICRO)
        assert refusal.cause_code == "GEOMETRY_PARAMS_INCOMPLETE"


# ---------------------------------------------------------------------------
# Unknown unit inside an attached bag → design-class, never bug-class
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_unit_in_geometry_classifies_design_not_bug(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        compressor = await _component(client, MICRO, "Compressor")
        bag = dict(_COMPLETE_CC_GEOMETRY)
        # All required keys present; one carries a unit the registry
        # cannot resolve ("zorkle" — guaranteed absent from pint).
        bag["inducer_tip_radius"] = {"value": 0.034, "unit": "zorkle"}
        await _patch_params(
            client,
            MICRO,
            compressor["id"],
            {"efficiency_mode": "live_meanline", "geometry_params": bag},
        )

        job = await _solve(client, MICRO)
        assert job["status"] == "failed", job
        assert job["error"] is None
        failure = job["result"]["failure"]
        assert failure["kind"] == "design", (
            f"unknown unit must classify design-class, got {failure['kind']}: "
            f"{failure['title']}"
        )
        assert "bug_log" not in failure
        assert "unit" in failure["title"].lower()
        # The detail names the offending field and unit string.
        named = str(failure.get("details", "")) + " ".join(
            failure.get("suggestions", [])
        )
        assert "inducer_tip_radius" in named
        assert "zorkle" in named

        refusal = _refusal_cause_code_via_worker(MICRO)
        assert refusal.cause_code == "UNKNOWN_UNIT"


# ---------------------------------------------------------------------------
# Recuperated + live mean-line — the documented hard case never hangs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recuperated_live_meanline_terminates_within_cap(app):
    """The C30 seed is recuperated; pushing the recuperator effectiveness
    above the documented coupling threshold (ε > 0.88 magnifies the
    cycle ↔ mean-line feedback) stresses the Aitken outer loop. The pin:
    the job reaches a terminal state inside the bounded wait — converged,
    non-converged-with-envelope, or refused-with-envelope. Never a hang."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        await _aligned_handoff(client)
        compressor = await _component(client, MICRO, "Compressor")
        recuperator = await _component(client, MICRO, "Recuperator")
        await _patch_params(
            client, MICRO, compressor["id"], {"efficiency_mode": "live_meanline"}
        )
        await _patch_params(
            client, MICRO, recuperator["id"], {"effectiveness": 0.93}
        )

        # _wait_job IS the no-hang assertion (bounded polling).
        job = await _solve(client, MICRO)
        assert job["status"] in ("done", "failed"), job

        res = job["result"]
        assert res is not None
        if job["status"] == "done":
            # Completed: either converged cleanly or carries the
            # non-convergence envelope (class 2 — done + converged False).
            if not res["converged"]:
                assert res["failure"]["kind"] == "design"
        else:
            # Refusal (class 1): error None + design-class envelope with
            # suggestions; outer-nonconvergence or a regime refusal.
            assert job["error"] is None
            assert res["failure"]["kind"] == "design"
            assert res["failure"]["suggestions"]
