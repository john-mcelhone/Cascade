"""Component CRUD persistence contract.

Pins three properties of the save-through component routes:

1. **Null-param validation (NON_SERIALIZABLE_PARAM).** ``Dict[str, Any]``
   accepts JSON ``null`` anywhere in ``params``, but the TOML store cannot
   represent ``None``: once merged into the cache, ``tomli_w`` raises
   ``TypeError`` on THIS and every LATER save — the store is poisoned
   until restart. PATCH/POST must reject the null with a structured 422
   naming the key path, BEFORE mutating the cache, so the store still
   saves cleanly afterwards.
2. **Structural edits are save-through.** add/delete component persist to
   the TOML store immediately (survive ``PROJECTS.reload()``) — matching
   the PATCH contract pinned in ``test_burner_fuel_mode.py``.
3. **Save failure surfaces as 503.** A failed disk write must not return
   a 2xx that implies durability while cache and disk silently diverge.
"""

from __future__ import annotations

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


@pytest.fixture
def app():
    jobs.reset_for_tests()
    return create_app()


async def _component(
    client: httpx.AsyncClient, project_id: str, kind: str
) -> Dict[str, Any]:
    resp = await client.get(f"/api/projects/{project_id}/components")
    for c in resp.json()["components"]:
        if c["kind"] == kind:
            return c
    raise AssertionError(f"No {kind} component in project {project_id}")


def _broken_disk_save(project) -> None:  # noqa: ANN001
    raise OSError(28, "No space left on device (injected by test)")


# ---------------------------------------------------------------------------
# Null params → 422 naming the key path; store not poisoned
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_null_param_422_names_key_and_store_stays_clean(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        burner = await _component(client, MICRO, "Burner")

        # Top-level null value.
        resp = await client.patch(
            f"/api/projects/{MICRO}/components/{burner['id']}",
            json={"params": {"fuel_lhv": None}},
        )
        assert resp.status_code == 422, resp.text
        detail = resp.json()["detail"]
        assert detail["error_code"] == "NON_SERIALIZABLE_PARAM"
        assert detail["key_path"] == "params.fuel_lhv"
        assert "params.fuel_lhv" in detail["message"]

        # Nested null value — the key PATH is named, not just the leaf.
        resp = await client.patch(
            f"/api/projects/{MICRO}/components/{burner['id']}",
            json={"params": {"outlet_temperature": {"value": None}}},
        )
        assert resp.status_code == 422, resp.text
        detail = resp.json()["detail"]
        assert detail["error_code"] == "NON_SERIALIZABLE_PARAM"
        assert detail["key_path"] == "params.outlet_temperature.value"

        # The rejected nulls never reached the cache: the bag is unchanged
        # and the store still saves cleanly on the next valid edit.
        burner_now = await _component(client, MICRO, "Burner")
        assert "fuel_lhv" not in burner_now["params"] or (
            burner_now["params"]["fuel_lhv"] is not None
        )
        resp = await client.patch(
            f"/api/projects/{MICRO}/components/{burner['id']}",
            json={"params": {"combustion_efficiency": 0.985}},
        )
        assert resp.status_code == 200, resp.text

        # ... and the valid edit truly reached disk.
        jobs.PROJECTS.reload()
        burner_after = await _component(client, MICRO, "Burner")
        assert burner_after["params"]["combustion_efficiency"] == pytest.approx(0.985)


@pytest.mark.asyncio
async def test_add_component_null_param_422(app):
    """POST validates the same way — a null in a freshly added component
    would poison every later save just the same."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        resp = await client.post(
            f"/api/projects/{MICRO}/components",
            json={
                "kind": "ConstantPressureLoss",
                "name": "Null duct",
                "params": {"pressure_drop_fraction": None},
                "position": {"x": 10, "y": 10},
            },
        )
        assert resp.status_code == 422, resp.text
        detail = resp.json()["detail"]
        assert detail["error_code"] == "NON_SERIALIZABLE_PARAM"
        assert detail["key_path"] == "params.pressure_drop_fraction"
        # Nothing was appended to the canvas.
        comps = (await client.get(f"/api/projects/{MICRO}/components")).json()
        assert all(c["name"] != "Null duct" for c in comps["components"])


# ---------------------------------------------------------------------------
# add/delete are save-through (survive a reload)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_component_survives_reload(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        resp = await client.post(
            f"/api/projects/{MICRO}/components",
            json={
                "kind": "ConstantPressureLoss",
                "name": "Exhaust duct",
                "params": {"pressure_drop_fraction": 0.015},
                "position": {"x": 600, "y": 240},
            },
        )
        assert resp.status_code == 201, resp.text
        new_id = resp.json()["id"]

        # Simulate a restart: drop the cache, re-read from disk.
        jobs.PROJECTS.reload()

        comps = (await client.get(f"/api/projects/{MICRO}/components")).json()
        match = [c for c in comps["components"] if c["id"] == new_id]
        assert match, "added component did not survive PROJECTS.reload()"
        assert match[0]["name"] == "Exhaust duct"
        assert match[0]["params"]["pressure_drop_fraction"] == pytest.approx(0.015)


@pytest.mark.asyncio
async def test_delete_component_survives_reload(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        recup = await _component(client, MICRO, "Recuperator")

        resp = await client.delete(
            f"/api/projects/{MICRO}/components/{recup['id']}"
        )
        assert resp.status_code == 204, resp.text

        # Simulate a restart: the deletion must not resurrect.
        jobs.PROJECTS.reload()

        comps = (await client.get(f"/api/projects/{MICRO}/components")).json()
        assert all(c["id"] != recup["id"] for c in comps["components"])
        # Edges touching the removed component stayed dropped too.
        assert all(
            e["source"] != recup["id"] and e["target"] != recup["id"]
            for e in comps["edges"]
        )


# ---------------------------------------------------------------------------
# Save failure → 503, never a silent cache/disk divergence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_save_failure_returns_503(app, monkeypatch):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        burner = await _component(client, MICRO, "Burner")
        monkeypatch.setattr(jobs, "_disk_save_project", _broken_disk_save)

        resp = await client.patch(
            f"/api/projects/{MICRO}/components/{burner['id']}",
            json={"params": {"combustion_efficiency": 0.97}},
        )

        assert resp.status_code == 503, resp.text
        assert "persisted" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_detach_geometry_save_failure_returns_503(app, monkeypatch):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        compressor = await _component(client, MICRO, "Compressor")
        monkeypatch.setattr(jobs, "_disk_save_project", _broken_disk_save)

        resp = await client.delete(
            f"/api/projects/{MICRO}/components/{compressor['id']}/geometry"
        )

        assert resp.status_code == 503, resp.text
        assert "persisted" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_add_and_delete_save_failure_returns_503(app, monkeypatch):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/health")
        burner = await _component(client, MICRO, "Burner")
        monkeypatch.setattr(jobs, "_disk_save_project", _broken_disk_save)

        resp = await client.post(
            f"/api/projects/{MICRO}/components",
            json={
                "kind": "ConstantPressureLoss",
                "name": "Doomed duct",
                "params": {"pressure_drop_fraction": 0.01},
                "position": {"x": 0, "y": 0},
            },
        )
        assert resp.status_code == 503, resp.text

        resp = await client.delete(
            f"/api/projects/{MICRO}/components/{burner['id']}"
        )
        assert resp.status_code == 503, resp.text
