"""ADAPT-014 locked regression: TOML project persistence survives reload.

This test will FAIL if the TOML persistence layer is removed and projects
revert to in-memory only (the pre-ADAPT-014 state where a server restart
would wipe all projects).

Locked invariant: a project written via _ProjectStore.__setitem__ must
be readable back via _ProjectStore after a reload() call, with all
parameters preserved.

References:
- ADAPT-014 (regression lock).
- apps/api/jobs.py:91 (_ProjectStore class).
- src/cascade/project/persistence.py (on-disk TOML store).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
for p in (str(_REPO / "src"), str(_REPO / "apps" / "api")):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture()
def isolated_store(tmp_path, monkeypatch):
    """Isolate the project store to a temp dir; wipe it after the test."""
    from jobs import _ProjectStore

    proj_dir = tmp_path / "cascade_projects"
    monkeypatch.setenv("CASCADE_PROJECTS_DIR", str(proj_dir))
    store = _ProjectStore()
    yield store
    # Cleanup: wipe any lingering on-disk state.
    if proj_dir.exists():
        for f in proj_dir.glob("*.cascade.toml"):
            f.unlink(missing_ok=True)


def test_adapt_014_project_survives_reload(isolated_store) -> None:
    """Locked: a project written to the store persists after reload().

    Pre-ADAPT-014 state: projects were stored in a plain dict; reload()
    would wipe all state. This test verifies that:
    1. A project is written with __setitem__.
    2. reload() drops the cache.
    3. The project is readable back with the same parameters.
    """
    store = isolated_store

    project_id = "adapt014-regression-test"
    project_data = {
        "id": project_id,
        "name": "ADAPT-014 Regression Test",
        "kind": "recuperated_brayton",
        "working_fluid": "air",
        "components": [],
        "edges": [],
        "boundary_conditions": {"test_param": 42.0},
        "settings": {"pressure_ratio": 3.5},
    }

    # Write to store (should persist to disk via __setitem__)
    store[project_id] = project_data

    # Simulate a server restart: drop the in-memory cache.
    store.reload()

    # Now read back — must reconstruct from disk.
    assert project_id in store, (
        f"ADAPT-014 regression: project '{project_id}' not found after "
        f"reload(). The in-memory dict was dropped but the project was "
        f"not re-read from disk. TOML persistence is broken."
    )

    recovered = store[project_id]
    assert recovered["name"] == "ADAPT-014 Regression Test", (
        f"Project name not preserved: got '{recovered['name']}'"
    )
    assert recovered["settings"]["pressure_ratio"] == 3.5, (
        f"ADAPT-014 regression: settings not persisted. "
        f"Got: {recovered.get('settings')}"
    )


def test_adapt_014_deletion_removes_from_disk(isolated_store, tmp_path) -> None:
    """Locked: deleting a project removes it from disk."""
    store = isolated_store
    pid = "adapt014-delete-test"
    store[pid] = {"id": pid, "name": "del-test", "kind": "blank",
                  "working_fluid": "air", "components": [], "edges": [],
                  "boundary_conditions": {}, "settings": {}}

    # File must exist on disk
    proj_dir = tmp_path / "cascade_projects"
    toml_files = list(proj_dir.glob(f"{pid}.cascade.toml"))
    assert toml_files, f"TOML file not created on disk for project '{pid}'"

    # Delete and confirm gone
    del store[pid]
    assert pid not in store, "Project still in cache after del"

    store.reload()
    assert pid not in store, (
        f"ADAPT-014 regression: deleted project '{pid}' still present after "
        f"reload(). Deletion did not remove the TOML file from disk."
    )


def test_adapt_014_multiple_projects_all_recovered(isolated_store) -> None:
    """Locked: multiple projects are all recovered after reload()."""
    store = isolated_store
    ids = ["proj-a", "proj-b", "proj-c"]

    for pid in ids:
        store[pid] = {
            "id": pid, "name": f"Project {pid}", "kind": "blank",
            "working_fluid": "air", "components": [], "edges": [],
            "boundary_conditions": {}, "settings": {"tag": pid},
        }

    store.reload()

    for pid in ids:
        assert pid in store, (
            f"ADAPT-014 regression: project '{pid}' missing after reload(). "
            f"Multi-project persistence broken."
        )
        assert store[pid]["settings"]["tag"] == pid, (
            f"Project '{pid}': tag not preserved after reload"
        )
