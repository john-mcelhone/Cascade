"""W-06 / CI-05: TOML persistence restart-survival integration test.

Verifies that a project parameter change survives a simulated API restart
(i.e., PROJECTS.reload() drops the cache and re-reads from disk, and the
modified parameter is still present).

Acceptance criteria (W-06):
1. Set CASCADE_PROJECTS_DIR to a pytest tmp_path
2. POST a new project (via _ProjectStore directly); set a parameter
3. Call PROJECTS.reload() to simulate a server restart
4. Read the project back
5. Assert the parameter persisted

References:
- CI-05: TOML Round-Trip Test (§5)
- ADAPT-014: TOML persistence
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
for p in (str(_REPO / "src"), str(_REPO / "apps" / "api")):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture()
def tmp_store(tmp_path, monkeypatch):
    """Create an isolated _ProjectStore backed by tmp_path."""
    from jobs import _ProjectStore

    proj_dir = tmp_path / "cascade_test_projects"
    monkeypatch.setenv("CASCADE_PROJECTS_DIR", str(proj_dir))
    yield _ProjectStore()

    # Cleanup
    if proj_dir.exists():
        for f in proj_dir.glob("*.cascade.toml"):
            f.unlink(missing_ok=True)


def test_persistence_parameter_survives_restart(tmp_store) -> None:
    """Core CI-05 test: parameter written to TOML survives reload().

    This is the primary restart-survival test. The CASCADE_PROJECTS_DIR is
    set to a tmp directory so the real ~/.cascade directory is never touched.
    """
    store = tmp_store
    project_id = "persist-test-001"

    # Step 1: Create and write a project with a known parameter.
    initial_data = {
        "id": project_id,
        "name": "Persistence Test Project",
        "kind": "recuperated_brayton",
        "working_fluid": "air",
        "components": [],
        "edges": [],
        "boundary_conditions": {},
        "settings": {
            "pressure_ratio": 3.75,
            "turbine_inlet_temperature_K": 1050.0,
            "test_marker": "adapt014-ci05",
        },
    }
    store[project_id] = initial_data

    # Step 2: Simulate a server restart by calling reload().
    store.reload()

    # Step 3: Read the project back (must reconstruct from disk).
    assert project_id in store, (
        f"Project '{project_id}' not found after reload(). "
        f"TOML persistence may be broken (ADAPT-014)."
    )

    recovered = store[project_id]

    # Step 4: Assert parameter values match.
    settings = recovered.get("settings", {})
    assert settings.get("pressure_ratio") == 3.75, (
        f"pressure_ratio not preserved. Got: {settings.get('pressure_ratio')}"
    )
    assert settings.get("turbine_inlet_temperature_K") == 1050.0, (
        f"turbine_inlet_temperature_K not preserved. "
        f"Got: {settings.get('turbine_inlet_temperature_K')}"
    )
    assert settings.get("test_marker") == "adapt014-ci05", (
        f"test_marker not preserved. Got: {settings.get('test_marker')}"
    )
    assert recovered.get("name") == "Persistence Test Project", (
        f"Project name not preserved. Got: {recovered.get('name')}"
    )


def test_persistence_in_place_mutation_saved(tmp_store, tmp_path) -> None:
    """In-place mutation + save() also persists after reload().

    Some routers do PROJECTS[id]["field"] = value + PROJECTS.save(id).
    This test verifies that pathway also survives a restart.
    """
    store = tmp_store
    project_id = "persist-test-mutate"

    store[project_id] = {
        "id": project_id, "name": "Mutate Test", "kind": "blank",
        "working_fluid": "air", "components": [], "edges": [],
        "boundary_conditions": {}, "settings": {"status": "initial"},
    }

    # Mutate in-place and save explicitly
    store[project_id]["settings"]["status"] = "mutated"
    store[project_id]["settings"]["extra_param"] = 99.9
    store.save(project_id)

    # Simulate restart
    store.reload()

    assert project_id in store
    recovered_settings = store[project_id].get("settings", {})
    assert recovered_settings.get("status") == "mutated", (
        f"In-place mutation not persisted after save()+reload(). "
        f"Got status='{recovered_settings.get('status')}'"
    )
    assert recovered_settings.get("extra_param") == 99.9, (
        f"extra_param not persisted. Got: {recovered_settings.get('extra_param')}"
    )


def test_persistence_temp_dir_isolation(tmp_store, tmp_path) -> None:
    """Test isolation: the store must use tmp_path, not ~/.cascade."""
    import os
    proj_dir = os.environ.get("CASCADE_PROJECTS_DIR", "")
    assert str(tmp_path) in proj_dir, (
        f"CASCADE_PROJECTS_DIR is not pointing at tmp_path. "
        f"Got: {proj_dir}. The real ~/.cascade directory would be contaminated."
    )


def test_persistence_project_count_after_reload(tmp_store) -> None:
    """All projects written before reload() must be present after reload()."""
    store = tmp_store
    ids = [f"batch-test-{i}" for i in range(5)]

    for pid in ids:
        store[pid] = {
            "id": pid, "name": f"Batch {pid}", "kind": "blank",
            "working_fluid": "air", "components": [], "edges": [],
            "boundary_conditions": {}, "settings": {"batch_id": pid},
        }

    count_before = len(store)
    store.reload()
    count_after = len(store)

    assert count_after == count_before, (
        f"Project count changed after reload: {count_before} → {count_after}. "
        f"Some projects were not persisted to disk."
    )

    for pid in ids:
        assert pid in store, (
            f"Project '{pid}' missing after reload. Persistence failed."
        )
