"""Refusal job-taxonomy contract tests (U1).

Pins the three-class job taxonomy:

1. **Refusal** — a run that produces no result (incomplete topology, a
   mid-solve refusal such as sub-atmospheric exhaust, or a classified
   bug-kind envelope) ends ``status="failed"`` with ``error=None`` and the
   structured failure envelope on ``result`` (``result["failure"]``
   present). Raised as ``jobs.JobRefusal`` by the cycle worker.
2. **Non-convergence** — a run that completes and produces a result with
   ``converged=False`` stays ``status="done"`` and retains its failure
   envelope. It is NOT a refusal.
3. **Crash** — an unexpected exception escaping the worker's classify
   scaffolding ends ``status="failed"`` with ``error`` set and no envelope.

The refusal signature is ``error is None`` + ``result["failure"]`` present,
scoped to ``status == "failed"``.

Also pins: the missing-components message names only the kinds actually
absent; canvas edges are decorative (zero edges still solves, and refusal
suggestions never tell the user to wire edges — see KNOWN_GAPS.md
KG-PLAT-02); ``last_run_status`` badges survive ``PROJECTS.reload()`` on
every terminal path.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

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
        if r.json()["status"] in ("done", "failed", "cancelled"):
            break
        await asyncio.sleep(0.05)
    return (await client.get(f"/api/jobs/{job_id}")).json()


async def _create_project(
    client: httpx.AsyncClient, name: str, template: str
) -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "template": template}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _add_component(
    client: httpx.AsyncClient,
    project_id: str,
    kind: str,
    name: str,
    params: Dict[str, Any],
) -> str:
    resp = await client.post(
        f"/api/projects/{project_id}/components",
        json={
            "kind": kind,
            "name": name,
            "params": params,
            "position": {"x": 100, "y": 100},
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


_COMPRESSOR_PARAMS = {"pressure_ratio": 4.01, "efficiency_isentropic": 0.78}
_TURBINE_PARAMS = {"pressure_ratio": 3.8, "efficiency_isentropic": 0.84}
_BURNER_PARAMS = {
    "outlet_temperature": {"value": 1116.0, "unit": "K"},
    "pressure_drop_fraction": 0.04,
    "combustion_efficiency": 0.99,
}


# ---------------------------------------------------------------------------
# Class 1 — refusals
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_canvas_refusal_failed_with_envelope(app):
    """Empty canvas (aero seed) → failed + design envelope, error=None."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        job = await _solve(client, "aero-demonstrator")

        assert job["status"] == "failed"
        assert job["error"] is None
        # Message names ALL the missing kinds for an empty canvas.
        msg = job["message"] or ""
        assert "Compressor" in msg
        assert "Burner" in msg
        assert "Turbine" in msg
        # Envelope intact: result-shaped, failure.kind == design.
        result = job["result"]
        assert result is not None
        assert result["converged"] is False
        failure = result["failure"]
        assert failure["kind"] == "design"
        # Edges are decorative in v1 (KG-PLAT-02): the refusal must not
        # instruct the user to connect anything, and it must disclose the
        # kind-inferred series flow path.
        suggestions = failure["suggestions"]
        assert not any("connect" in s.lower() for s in suggestions), suggestions
        assert any("KG-PLAT-02" in s for s in suggestions), suggestions


@pytest.mark.asyncio
async def test_partial_canvas_names_only_missing_kinds(app):
    """Compressor + Turbine present, no Burner → message names only Burner."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        pid = await _create_project(client, "refusal-partial-canvas", "aero")
        await _add_component(client, pid, "Compressor", "C1", _COMPRESSOR_PARAMS)
        await _add_component(client, pid, "Turbine", "T1", _TURBINE_PARAMS)

        job = await _solve(client, pid)

        assert job["status"] == "failed"
        assert job["error"] is None
        msg = job["message"] or ""
        assert "Burner" in msg
        assert "Compressor" not in msg, msg
        assert "Turbine" not in msg, msg
        assert job["result"]["failure"]["kind"] == "design"


@pytest.mark.asyncio
async def test_components_present_zero_edges_still_solves(app):
    """All required kinds with ZERO edges → solves (edges are decorative)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        pid = await _create_project(client, "refusal-zero-edges", "aero")
        await _add_component(client, pid, "Compressor", "C1", _COMPRESSOR_PARAMS)
        await _add_component(client, pid, "Burner", "B1", _BURNER_PARAMS)
        await _add_component(client, pid, "Turbine", "T1", _TURBINE_PARAMS)
        # No edges added at all.
        comps = (await client.get(f"/api/projects/{pid}/components")).json()
        assert comps["edges"] == []

        job = await _solve(client, pid)

        assert job["status"] == "done", job
        assert job["result"]["converged"] is True, job["result"]
        assert "failure" not in job["result"] or job["result"].get("failure") is None


@pytest.mark.asyncio
async def test_mid_solve_refusal_failed_with_envelope(app):
    """Sub-atmospheric exhaust mid-solve → failed + design envelope."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        pid = await _create_project(client, "refusal-subatm", "microturbine")
        comps = (await client.get(f"/api/projects/{pid}/components")).json()
        cid = next(c["id"] for c in comps["components"] if c["kind"] == "Compressor")
        # Compressor PR far below the turbine PR: the turbine would have to
        # expand below ambient — a physical impossibility the solver refuses.
        await client.patch(
            f"/api/projects/{pid}/components/{cid}",
            json={"params": {"pressure_ratio": 1.2}},
        )

        job = await _solve(client, pid)

        assert job["status"] == "failed"
        assert job["error"] is None
        failure = job["result"]["failure"]
        assert failure["kind"] == "design"
        assert "ambient" in (failure["title"] + failure["plain_english"]).lower()


# ---------------------------------------------------------------------------
# Class 2 — non-convergence stays done and is not a refusal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_converged_run_stays_done_with_envelope(app, monkeypatch):
    """A run that completes without converging is class 2: done + envelope.

    The v1 Aitken-accelerated recuperated solver converges across the
    entire structurally-valid input domain reachable through the API
    (extreme inputs raise — class 1 — rather than oscillate), so this test
    drives the solver's documented non-convergence channel directly: the
    REAL solver, on the REAL microturbine seed, under a tight iteration
    budget (`max_outer_iters=2`, `outer_tol=1e-12`) returns a complete
    result with ``converged=False`` ("don't raise — return
    result.converged=False so caller can decide", solver.py).
    """
    import cascade.cycle.solver as cycle_solver

    real_solve_cycle = cycle_solver.solve_cycle

    def tight_budget_solve(spec, fluid=None, **kwargs):
        return real_solve_cycle(
            spec, fluid=fluid, outer_tol=1e-12, max_outer_iters=2
        )

    monkeypatch.setattr(cycle_solver, "solve_cycle", tight_budget_solve)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        job = await _solve(client, "microturbine-30kw")

        # Non-convergence is NOT a refusal: the job stays done.
        assert job["status"] == "done", job
        assert job["error"] is None
        result = job["result"]
        assert result["converged"] is False
        # ... and it retains its failure envelope for the explanation.
        failure = result["failure"]
        assert failure["kind"] == "design"
        assert "converge" in failure["title"].lower()
        # Badge: non_converged (distinct from a refusal's "failed").
        assert (
            jobs.PROJECTS["microturbine-30kw"]["last_run_status"]
            == "non_converged"
        )


# ---------------------------------------------------------------------------
# Class 1 vs class 3 — refusal-vs-crash signature
# ---------------------------------------------------------------------------


class _BrokenStore:
    """Project store whose lookup crashes — simulates an infrastructure
    fault OUTSIDE the worker's classify scaffolding (class 3)."""

    def __getitem__(self, key: str) -> Dict[str, Any]:
        raise RuntimeError("injected infrastructure crash (test)")


@pytest.mark.asyncio
async def test_refusal_vs_crash_signature(app, monkeypatch):
    """Refusal: error None + result.failure. Crash: error set, no result.

    The crash is injected by breaking the worker's project-store lookup —
    deliberately OUTSIDE the classify path (anything raised inside
    solve_cycle gets classified into a bug-kind envelope and is class 1).
    The endpoint's own 404 guard is unaffected because `deps` binds the
    real store at import time, while the worker resolves `jobs.PROJECTS`
    per solve.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")

        # Refusal arm (class 1).
        refused = await _solve(client, "aero-demonstrator")
        assert refused["status"] == "failed"
        assert refused["error"] is None
        assert refused["result"]["failure"] is not None

        # Crash arm (class 3). Scoped context so the real store is restored
        # before the conftest store-isolation fixture tears down.
        with monkeypatch.context() as patch:
            patch.setattr(jobs, "PROJECTS", _BrokenStore())
            crashed = await _solve(client, "microturbine-30kw")
        assert crashed["status"] == "failed"
        assert crashed["error"] is not None
        assert "RuntimeError" in crashed["error"]
        assert crashed["result"] is None


# ---------------------------------------------------------------------------
# Cancel-then-refuse race
# ---------------------------------------------------------------------------


class _InlineExecutor:
    """Synchronous executor stand-in: makes run_in_worker deterministic."""

    def submit(self, fn, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        fn(*args, **kwargs)


def test_cancel_then_refuse_keeps_cancelled_status(monkeypatch):
    """A job cancelled before the refusal raises keeps status `cancelled`
    and publishes no second final event."""
    jobs.reset_for_tests()
    events: List[Tuple[Dict[str, Any], bool]] = []

    def record_event(job_id: str, event: Dict[str, Any], final: bool = False) -> None:
        events.append((dict(event), final))

    monkeypatch.setattr(jobs, "publish_event", record_event)
    monkeypatch.setattr(jobs, "_EXECUTOR", _InlineExecutor())

    job = jobs.register_job("any-project", "cycle")

    def worker(j: jobs.Job) -> Dict[str, Any]:
        # User cancels mid-run, then the worker hits a refusal.
        jobs.cancel_job(j.id)
        raise jobs.JobRefusal(
            envelope={"converged": False, "failure": {"kind": "design"}},
            message="refused after cancel",
            cause_code="TEST_REFUSAL",
        )

    jobs.run_in_worker(job, worker)

    assert job.status == "cancelled"
    # The refusal must not overwrite the cancelled terminal state.
    assert job.result is None
    assert job.message == "Cancelled by user."
    finals = [ev for ev, final in events if final]
    assert len(finals) == 1, finals
    assert finals[0]["status"] == "cancelled"


def test_cancel_then_crash_keeps_cancelled_status(monkeypatch):
    """A job cancelled before an unexpected crash keeps status `cancelled`
    and publishes no second final event (class-3 mirror of the
    cancel-then-refuse race above)."""
    jobs.reset_for_tests()
    events: List[Tuple[Dict[str, Any], bool]] = []

    def record_event(job_id: str, event: Dict[str, Any], final: bool = False) -> None:
        events.append((dict(event), final))

    monkeypatch.setattr(jobs, "publish_event", record_event)
    monkeypatch.setattr(jobs, "_EXECUTOR", _InlineExecutor())

    job = jobs.register_job("any-project", "cycle")

    def worker(j: jobs.Job) -> Dict[str, Any]:
        # User cancels mid-run, then the worker crashes unexpectedly.
        jobs.cancel_job(j.id)
        raise RuntimeError("late crash after cancel (test)")

    jobs.run_in_worker(job, worker)

    assert job.status == "cancelled"
    # The crash must not overwrite the cancelled terminal state.
    assert job.error is None
    assert job.result is None
    assert job.message == "Cancelled by user."
    finals = [ev for ev, final in events if final]
    assert len(finals) == 1, finals
    assert finals[0]["status"] == "cancelled"


# ---------------------------------------------------------------------------
# Terminal-path badge saves must never reclassify the run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disk_save_failure_does_not_reclassify_terminal_paths(
    app, monkeypatch
):
    """An OSError from the terminal badge save (disk full / permissions)
    must not morph a class-1 design refusal — or a CORRECT converged
    result — into a class-3 crash. The badge not persisting is far less
    harmful than misclassifying the run."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")

        # Break the disk-save seam AFTER seeding so only the terminal
        # worker saves hit it.
        def broken_disk_save(project):  # noqa: ANN001
            raise OSError(28, "No space left on device (injected by test)")

        monkeypatch.setattr(jobs, "_disk_save_project", broken_disk_save)

        # Topology refusal stays class 1: failed, error=None, envelope on.
        refused = await _solve(client, "aero-demonstrator")
        assert refused["status"] == "failed"
        assert refused["error"] is None, refused
        assert refused["result"]["failure"]["kind"] == "design"

        # Converged solve stays class "done" with its full result.
        converged = await _solve(client, "microturbine-30kw")
        assert converged["status"] == "done", converged
        assert converged["error"] is None
        assert converged["result"]["converged"] is True


# ---------------------------------------------------------------------------
# SSE payloads are strict JSON (no NaN/Infinity literals)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sse_event_with_non_finite_floats_serializes_to_strict_json():
    """A non-finite float in a published event (e.g. the failure envelope's
    ``residual_norm = NaN``) must not leak a bare NaN/Infinity literal into
    the SSE data: that is invalid JSON, the browser's JSON.parse rejects
    it, and the client would swallow the final event and hang the Run
    button. The publish seam sanitizes non-finite floats to null."""
    import json

    jobs.reset_for_tests()
    job = jobs.register_job(
        "any-project", "cycle", loop=asyncio.get_running_loop()
    )

    jobs.publish_event(
        job.id,
        {
            "status": "failed",
            "message": "refused",
            "result": {
                "residual_norm": float("nan"),
                "nested": {"pos": float("inf"), "neg": float("-inf")},
                "listed": [1.0, float("nan")],
                "finite": 1.5,
            },
        },
        final=True,
    )

    events = []
    async for event in jobs.stream_events(job.id, heartbeat_interval=1.0):
        events.append(event)
    assert len(events) == 1

    def _reject_constant(name: str) -> None:
        raise AssertionError(
            f"non-finite literal {name!r} leaked into the SSE JSON payload"
        )

    # Same serialization the SSE endpoint applies (main.py event_generator),
    # round-tripped strictly: parse_constant raises on NaN/Infinity.
    data = json.dumps(events[0])
    parsed = json.loads(data, parse_constant=_reject_constant)
    assert parsed["final"] is True
    result = parsed["result"]
    assert result["residual_norm"] is None
    assert result["nested"]["pos"] is None
    assert result["nested"]["neg"] is None
    assert result["listed"] == [1.0, None]
    assert result["finite"] == 1.5


# ---------------------------------------------------------------------------
# Stable cause codes on the JobRefusal exception
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refusal_cause_codes_are_stable(app):
    """JobRefusal carries a stable machine-readable cause code."""
    from routers.cycle import _cycle_worker

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")

        # Topology refusal → MISSING_REQUIRED_COMPONENTS.
        job = jobs.register_job("aero-demonstrator", "cycle")
        with pytest.raises(jobs.JobRefusal) as exc_info:
            _cycle_worker("aero-demonstrator")(job)
        assert exc_info.value.cause_code == "MISSING_REQUIRED_COMPONENTS"
        assert exc_info.value.envelope["failure"]["kind"] == "design"

        # Mid-solve refusal inherits the solver's stable refusal code.
        pid = await _create_project(client, "refusal-cause-code", "microturbine")
        comps = (await client.get(f"/api/projects/{pid}/components")).json()
        cid = next(c["id"] for c in comps["components"] if c["kind"] == "Compressor")
        await client.patch(
            f"/api/projects/{pid}/components/{cid}",
            json={"params": {"pressure_ratio": 1.2}},
        )
        job2 = jobs.register_job(pid, "cycle")
        with pytest.raises(jobs.JobRefusal) as exc_info2:
            _cycle_worker(pid)(job2)
        assert exc_info2.value.cause_code == "OPEN_CYCLE_SUB_ATMOSPHERIC"


# ---------------------------------------------------------------------------
# last_run_status badge persistence (terminal-path save symmetry)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_last_run_status_survives_reload(app):
    """`failed` (refusal) and `done` (converged) badges survive a reload."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")

        refused = await _solve(client, "aero-demonstrator")
        assert refused["status"] == "failed"
        converged = await _solve(client, "microturbine-30kw")
        assert converged["status"] == "done"

        # Drop the in-memory cache: badges must come back from disk.
        jobs.PROJECTS.reload()

        assert jobs.PROJECTS["aero-demonstrator"]["last_run_status"] == "failed"
        assert jobs.PROJECTS["microturbine-30kw"]["last_run_status"] == "done"


# ---------------------------------------------------------------------------
# Valid canvas unchanged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_canvas_unchanged(app):
    """The microturbine seed still solves: done, converged, η ≈ 27 %."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        job = await _solve(client, "microturbine-30kw")

        assert job["status"] == "done"
        assert job["error"] is None
        result = job["result"]
        assert result["converged"] is True
        assert 0.26 < result["thermal_efficiency"] < 0.30, result[
            "thermal_efficiency"
        ]
