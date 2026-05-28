"""HTTP-boundary refusal for the rotor endpoint (market-readiness pass).

Regression guard for a silent-failure defect. Previously ``rotor_endpoint``
dispatched the job immediately, and ``_rotor_worker`` caught the
``HTTPException(422)`` raised by ``_build_rotor_from_request`` inside a bare
``except Exception`` and *returned* a dict. ``jobs.py`` then marked the job
``status="done"`` -- so an invalid bearing / section / disk produced an HTTP
200 "done" job with a buried error string instead of a 422 refusal.

The helper-level tests in ``tests/rotor/test_bearing_payload_refusal.py``
could not catch this because they exercise ``_bearing_from_payload`` /
``_build_rotor_from_request`` in isolation -- never the endpoint. The fix
builds + validates the rotor model synchronously inside ``rotor_endpoint``
(before a job is registered), mirroring the analysis endpoint's synchronous
overconstraint refusal. These tests exercise that HTTP boundary directly so
the refusal cannot silently regress again.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
for _p in (str(_REPO / "src"), str(_REPO / "apps" / "api")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import HTTPException  # noqa: E402
from models import RotorRequest  # noqa: E402
from routers import rotor as rotor_router  # noqa: E402


def _patch(monkeypatch) -> dict:
    """Stub the project lookup + SSE publish, and capture whether a job is
    ever dispatched. Returns the dispatch-flag dict."""
    monkeypatch.setattr(rotor_router, "get_project_or_404", lambda pid: {"id": pid})
    monkeypatch.setattr(rotor_router, "publish_event", lambda *a, **k: None)
    dispatched = {"called": False}
    monkeypatch.setattr(
        rotor_router,
        "run_in_worker",
        lambda job, worker: dispatched.__setitem__("called", True),
    )
    return dispatched


def test_invalid_bearing_returns_422_before_dispatch(monkeypatch) -> None:
    """Negative bearing stiffness must produce a 422 at the endpoint, and no
    job may be dispatched."""
    dispatched = _patch(monkeypatch)
    req = RotorRequest(bearings=[{"K_yy_n_per_m": -1.0e8, "axial_position_mm": 0.0}])
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(rotor_router.rotor_endpoint("test-project", req))
    assert exc_info.value.status_code == 422
    assert "INVALID_BEARING" in exc_info.value.detail
    assert dispatched["called"] is False, "endpoint must refuse before dispatching a job"


def test_nan_bearing_returns_422(monkeypatch) -> None:
    dispatched = _patch(monkeypatch)
    req = RotorRequest(bearings=[{"K_yy_n_per_m": float("nan"), "axial_position_mm": 0.0}])
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(rotor_router.rotor_endpoint("test-project", req))
    assert exc_info.value.status_code == 422
    assert dispatched["called"] is False


def test_above_limit_stiffness_returns_422(monkeypatch) -> None:
    _patch(monkeypatch)
    req = RotorRequest(bearings=[{"K_yy_n_per_m": 3.8e14, "axial_position_mm": 0.0}])
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(rotor_router.rotor_endpoint("test-project", req))
    assert exc_info.value.status_code == 422


def test_valid_request_dispatches_job(monkeypatch) -> None:
    """A request that omits sections/bearings uses the validated Jeffcott
    default geometry and must dispatch a job without raising."""
    dispatched = _patch(monkeypatch)
    resp = asyncio.run(rotor_router.rotor_endpoint("test-project", RotorRequest()))
    assert dispatched["called"] is True, "valid request must dispatch a job"
    assert getattr(resp, "job_id", None), "endpoint must return a job id"
