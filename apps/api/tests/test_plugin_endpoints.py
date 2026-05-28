"""End-to-end tests for the per-project plugin endpoints (ADAPT-035).

Covers:
- GET /api/projects/{id}/loss-models returns built-in + user plugins.
- POST .../loss-models/upload accepts a valid .py file and registers it.
- POST .../loss-models/upload rejects a syntactically invalid file (422).
- POST .../loss-models/upload rejects a class with a wrong return type (422).
- POST .../loss-models/{name}/select sets the active loss model.
- DELETE .../loss-models/{name} removes a user plugin but refuses a builtin.
"""

from __future__ import annotations

import os
import sys
import tempfile
import textwrap
from pathlib import Path

import httpx
import pytest


# Make `main` importable from this test file (mirrors test_smoke).
APP_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = APP_DIR.parent.parent / "src"
for p in (str(APP_DIR), str(SRC_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Isolate the plugin store so tests don't share state with dev runs.
_TEST_STORE = Path(tempfile.mkdtemp(prefix="cascade-plugin-tests-"))
os.environ["CASCADE_PLUGIN_STORE_DIR"] = str(_TEST_STORE)


from main import create_app  # noqa: E402
import jobs  # noqa: E402


@pytest.fixture
def app():
    jobs.reset_for_tests()
    # Clear user plugins so each test starts fresh; built-ins survive
    # because they re-register on module import.
    from cascade.plugins import PLUGIN_REGISTRY

    PLUGIN_REGISTRY.clear_user()
    return create_app()


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        # Trigger lifespan startup so the project store is seeded.
        await c.get("/api/health")
        yield c


@pytest.mark.asyncio
async def test_list_project_loss_models_includes_builtins(client):
    resp = await client.get(
        "/api/projects/microturbine-30kw/loss-models"
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()
    names = {x["name"] for x in items}
    assert "WhitfieldBainesRadial" in names
    assert "AungierCentrifugal" in names
    # Origin tag present
    for item in items:
        assert item["origin"] in ("builtin", "user")


@pytest.mark.asyncio
async def test_list_filters_by_machine_class(client):
    resp = await client.get(
        "/api/projects/microturbine-30kw/loss-models"
        "?machine_class=centrifugal_compressor"
    )
    assert resp.status_code == 200, resp.text
    names = {x["name"] for x in resp.json()}
    assert "AungierCentrifugal" in names
    assert "WhitfieldBainesRadial" not in names


@pytest.mark.asyncio
async def test_upload_valid_plugin_registers_it(client):
    body = textwrap.dedent(
        """
        from cascade.plugins import LossContext, LossModel


        class MyCustom(LossModel):
            name = "MyCustomUpload"
            applicable_machine_classes = ["radial_turbine"]

            def loss_coefficient(self, ctx: LossContext) -> float:
                return 0.12
        """
    ).encode("utf-8")
    files = {"file": ("my_custom.py", body, "text/x-python")}
    resp = await client.post(
        "/api/projects/microturbine-30kw/loss-models/upload",
        files=files,
    )
    assert resp.status_code == 201, resp.text
    plugin = resp.json()["plugin"]
    assert plugin["name"] == "MyCustomUpload"
    assert plugin["origin"] == "user"
    assert plugin["applicable_machine_classes"] == ["radial_turbine"]

    # The list endpoint should now include it.
    list_resp = await client.get(
        "/api/projects/microturbine-30kw/loss-models"
    )
    assert "MyCustomUpload" in {x["name"] for x in list_resp.json()}


@pytest.mark.asyncio
async def test_upload_rejects_syntax_error(client):
    body = b"class Bad(  # missing close paren + colon\n    pass\n"
    files = {"file": ("broken.py", body, "text/x-python")}
    resp = await client.post(
        "/api/projects/microturbine-30kw/loss-models/upload",
        files=files,
    )
    assert resp.status_code == 422, resp.text
    assert "syntax" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_rejects_wrong_return_type(client):
    body = textwrap.dedent(
        """
        from cascade.plugins import LossContext, LossModel


        class StringReturn(LossModel):
            name = "StringReturn"
            applicable_machine_classes = ["radial_turbine"]

            def loss_coefficient(self, ctx: LossContext):
                return "oops"
        """
    ).encode("utf-8")
    files = {"file": ("bad.py", body, "text/x-python")}
    resp = await client.post(
        "/api/projects/microturbine-30kw/loss-models/upload",
        files=files,
    )
    assert resp.status_code == 422, resp.text
    assert "number" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_select_loss_model_sets_active(client):
    resp = await client.post(
        "/api/projects/microturbine-30kw/loss-models/"
        "AungierCentrifugal/select"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["active_loss_model"] == "AungierCentrifugal"
    assert body["project_id"] == "microturbine-30kw"


@pytest.mark.asyncio
async def test_select_unknown_returns_404(client):
    resp = await client.post(
        "/api/projects/microturbine-30kw/loss-models/NopeNever/select"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_user_plugin(client):
    body = textwrap.dedent(
        """
        from cascade.plugins import LossContext, LossModel


        class ToDelete(LossModel):
            name = "ToDelete"
            applicable_machine_classes = ["radial_turbine"]

            def loss_coefficient(self, ctx: LossContext) -> float:
                return 0.13
        """
    ).encode("utf-8")
    files = {"file": ("td.py", body, "text/x-python")}
    up = await client.post(
        "/api/projects/microturbine-30kw/loss-models/upload",
        files=files,
    )
    assert up.status_code == 201, up.text

    del_resp = await client.delete(
        "/api/projects/microturbine-30kw/loss-models/ToDelete"
    )
    assert del_resp.status_code == 204
    list_resp = await client.get(
        "/api/projects/microturbine-30kw/loss-models"
    )
    assert "ToDelete" not in {x["name"] for x in list_resp.json()}


@pytest.mark.asyncio
async def test_delete_builtin_refused(client):
    resp = await client.delete(
        "/api/projects/microturbine-30kw/loss-models/AungierCentrifugal"
    )
    assert resp.status_code == 409
