"""Regression tests for the `.cascade.toml` project format (ADAPT-014).

The differentiator we sell is *git-diffability*. These tests pin down:

1. Round-trip byte-equality for every demo project (no formatting drift).
2. A one-parameter edit produces a single-line diff (the marketing claim).
3. Corrupted TOML produces a clear error, not a silent partial load.
4. ``CASCADE_PROJECTS_DIR`` redirects all disk I/O — never touches ``~``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make the API-side seed module importable so we can pull the canonical
# demo projects.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
_API = _REPO_ROOT / "apps" / "api"
for p in (str(_SRC), str(_API)):
    if p not in sys.path:
        sys.path.insert(0, p)

from cascade.project import (  # noqa: E402
    Project,
    delete_project,
    ensure_seeded,
    list_projects,
    load_project,
    project_from_toml,
    project_to_toml,
    projects_dir,
    save_project,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_projects_dir(tmp_path, monkeypatch):
    """Redirect ``CASCADE_PROJECTS_DIR`` at the env var level.

    Asserts that *every* disk op lands under ``tmp_path``, never under ``~``.
    """

    target = tmp_path / "cascade_projects"
    monkeypatch.setenv("CASCADE_PROJECTS_DIR", str(target))
    assert projects_dir() == target
    return target


@pytest.fixture
def demo_projects():
    """All four seed project dicts from ``apps/api/seed.py``."""

    from seed import _aero_project, _at100_project, _microturbine_project, _sco2_project

    return [
        Project.from_legacy_dict(_microturbine_project()),
        Project.from_legacy_dict(_sco2_project()),
        Project.from_legacy_dict(_aero_project()),
        Project.from_legacy_dict(_at100_project()),
    ]


# ---------------------------------------------------------------------------
# Round-trip byte-equality
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["microturbine", "sco2", "aero", "at100"])
def test_round_trip_is_byte_equal(name, demo_projects):
    """Serialize -> parse -> serialize must equal serialize."""

    idx = {"microturbine": 0, "sco2": 1, "aero": 2, "at100": 3}[name]
    project = demo_projects[idx]

    s1 = project_to_toml(project)
    parsed = project_from_toml(s1)
    s2 = project_to_toml(parsed)

    assert s1 == s2, f"round-trip drifted on {name}"
    assert s1.endswith("\n"), "file must end with newline"
    assert "\r" not in s1, "no CR characters allowed"


def test_round_trip_preserves_components_and_edges(demo_projects):
    """Component ids, kinds, positions, params, and edge wiring survive."""

    microturbine = demo_projects[0]
    s = project_to_toml(microturbine)
    parsed = project_from_toml(s)

    assert [c.id for c in parsed.components] == [c.id for c in microturbine.components]
    assert [c.kind for c in parsed.components] == [c.kind for c in microturbine.components]
    assert [e.source for e in parsed.edges] == [e.source for e in microturbine.edges]
    assert [e.target for e in parsed.edges] == [e.target for e in microturbine.edges]

    # The pressure_ratio param on the compressor must survive.
    comp = next(c for c in parsed.components if c.id == "compressor")
    assert comp.params["pressure_ratio"] == 4.0


def test_legacy_dict_round_trip(demo_projects):
    """``from_legacy_dict`` -> ``to_legacy_dict`` round-trips the API shape."""

    p = demo_projects[0]
    d = p.to_legacy_dict()
    p2 = Project.from_legacy_dict(d)
    assert project_to_toml(p) == project_to_toml(p2)


# ---------------------------------------------------------------------------
# Git-diffability: the marketing claim
# ---------------------------------------------------------------------------


def test_one_field_edit_is_one_line_diff(demo_projects):
    """Editing compressor.pressure_ratio = 4.0 -> 4.5 = single-line diff."""

    project = demo_projects[0]
    before = project_to_toml(project)

    # Mutate in-place via the Pydantic model.
    compressor = next(c for c in project.components if c.id == "compressor")
    compressor.params["pressure_ratio"] = 4.5

    after = project_to_toml(project)

    before_lines = before.splitlines()
    after_lines = after.splitlines()

    assert len(before_lines) == len(after_lines), (
        "Editing one field changed the line count — formatting drifted!"
    )

    diff_indices = [
        i for i, (a, b) in enumerate(zip(before_lines, after_lines)) if a != b
    ]
    assert len(diff_indices) == 1, (
        f"Expected exactly 1 changed line, got {len(diff_indices)}: "
        f"{[(before_lines[i], after_lines[i]) for i in diff_indices]}"
    )

    # And the changed line must be the pressure_ratio assignment.
    changed_line = after_lines[diff_indices[0]]
    assert "pressure_ratio" in changed_line and "4.5" in changed_line


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_corrupt_toml_raises_clear_error():
    """A malformed TOML body should raise an error, not return a half-built Project."""

    bad = "id = \"x\"\n[meta\nname = 'broken'\n"  # missing closing bracket
    with pytest.raises(Exception) as info:
        project_from_toml(bad)
    msg = str(info.value).lower()
    # tomli/tomllib both mention "expected" / line / column or something
    # human-recognizable. We just want a non-empty message.
    assert msg.strip() != ""


def test_missing_id_raises_value_error():
    """A TOML missing the top-level ``id`` field must refuse to load."""

    bad = "[meta]\nname = 'nameless'\n"
    with pytest.raises(ValueError, match="id"):
        project_from_toml(bad)


# ---------------------------------------------------------------------------
# Persistence: save / load / list / delete
# ---------------------------------------------------------------------------


def test_save_and_load_round_trip(isolated_projects_dir, demo_projects):
    project = demo_projects[0]
    path = save_project(project)

    assert path.exists()
    assert path.parent == isolated_projects_dir
    assert path.name == "microturbine-30kw.cascade.toml"

    on_disk_text = path.read_text(encoding="utf-8")
    assert on_disk_text == project_to_toml(project)

    loaded = load_project(project.id)
    assert loaded is not None
    assert project_to_toml(loaded) == project_to_toml(project)


def test_list_projects_returns_all_saved(isolated_projects_dir, demo_projects):
    for p in demo_projects:
        save_project(p)
    listed = list_projects()
    ids = {p.id for p in listed}
    # All four canonical seeds must be present — if a new seed is added to
    # seed.py, add its id here rather than deleting and re-running.
    expected_ids = {p.id for p in demo_projects}
    assert ids == expected_ids, (
        f"Saved {expected_ids} but listed {ids}. "
        f"Missing: {expected_ids - ids}. Extra: {ids - expected_ids}."
    )


def test_list_projects_skips_unparseable(isolated_projects_dir, demo_projects):
    """A garbage .cascade.toml file must not hide the good ones."""

    save_project(demo_projects[0])
    (isolated_projects_dir / "broken.cascade.toml").write_text("not valid toml [", encoding="utf-8")

    listed = list_projects()
    assert {p.id for p in listed} == {"microturbine-30kw"}


def test_delete_project(isolated_projects_dir, demo_projects):
    save_project(demo_projects[0])
    assert delete_project("microturbine-30kw") is True
    assert load_project("microturbine-30kw") is None
    # Idempotent: deleting again returns False rather than raising.
    assert delete_project("microturbine-30kw") is False


def test_unsafe_project_ids_refused(isolated_projects_dir):
    """Path-traversal-y ids must not be allowed to escape the projects dir."""

    from cascade.project.persistence import _path_for

    for bad in ("../escape", "a/b", "..", ".hidden", "", "win\\dows"):
        with pytest.raises(ValueError):
            _path_for(bad)


def test_ensure_seeded_only_writes_once(isolated_projects_dir, demo_projects):
    n1 = ensure_seeded(demo_projects)
    # n1 must equal the number of seeds passed in — not a hardcoded magic number.
    assert n1 == len(demo_projects), (
        f"ensure_seeded wrote {n1} files, expected {len(demo_projects)}."
    )
    n2 = ensure_seeded(demo_projects)
    assert n2 == 0, "ensure_seeded must be idempotent — no overwrite of user edits"


def test_env_var_redirects_disk_io(isolated_projects_dir, demo_projects):
    """Sanity: with CASCADE_PROJECTS_DIR set, we never touch ``~``."""

    save_project(demo_projects[0])
    # The real home dir's .cascade/projects must not have been created.
    real_default = Path.home() / ".cascade" / "projects"
    # We can't safely assert the dir doesn't exist (developer might have a
    # real one), but we *can* assert our file landed in the override path.
    assert (isolated_projects_dir / "microturbine-30kw.cascade.toml").exists()
    if real_default.exists():
        # If the developer has a real ~/.cascade dir, our file must NOT be in it.
        assert not (real_default / "microturbine-30kw.cascade.toml").read_text(
            encoding="utf-8"
        ).startswith("# .cascade project file v1\n# Generated by Cascade 0.1.0") or (
            real_default / "microturbine-30kw.cascade.toml"
        ).stat().st_mtime < isolated_projects_dir.stat().st_mtime, (
            "test bled into the real .cascade/projects"
        )
