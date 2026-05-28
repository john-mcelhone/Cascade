"""On-disk store for Cascade projects.

Default location: ``~/.cascade/projects/<project_id>.cascade.toml``.

Override the root with the ``CASCADE_PROJECTS_DIR`` env var — required for
tests so we never touch the developer's real ``~/.cascade`` tree.

This module is deliberately filesystem-only (no sqlite, no locking yet). A
future migration to a postgres-backed store can keep the same surface:
``load_project``, ``save_project``, ``list_projects``, ``delete_project``.
"""

from __future__ import annotations

import logging
import os
import pathlib
import tempfile
from typing import List, Optional

from .schema import Project
from .serializer import project_from_toml, project_to_toml

log = logging.getLogger(__name__)

PROJECT_FILE_SUFFIX = ".cascade.toml"
DEFAULT_PROJECTS_DIR = pathlib.Path.home() / ".cascade" / "projects"


def projects_dir() -> pathlib.Path:
    """Return the active projects directory (env var > default).

    Resolved each call so tests can monkey-patch the env var per-fixture.
    """

    override = os.environ.get("CASCADE_PROJECTS_DIR")
    if override:
        return pathlib.Path(override).expanduser()
    return DEFAULT_PROJECTS_DIR


def _path_for(project_id: str) -> pathlib.Path:
    if not project_id or "/" in project_id or "\\" in project_id or project_id.startswith("."):
        raise ValueError(f"invalid project_id: {project_id!r}")
    return projects_dir() / f"{project_id}{PROJECT_FILE_SUFFIX}"


def list_projects() -> List[Project]:
    """Load every ``*.cascade.toml`` file in the projects dir.

    Files that fail to parse are skipped with a warning rather than crashing
    the whole list — one corrupted file should never hide the others.
    """

    root = projects_dir()
    if not root.exists():
        return []
    out: List[Project] = []
    for path in sorted(root.glob(f"*{PROJECT_FILE_SUFFIX}")):
        try:
            out.append(project_from_toml(path.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001
            log.warning("Skipping unparseable project %s: %s", path.name, exc)
    return out


def load_project(project_id: str) -> Optional[Project]:
    """Load a single project by id. Returns ``None`` if absent."""

    path = _path_for(project_id)
    if not path.exists():
        return None
    return project_from_toml(path.read_text(encoding="utf-8"))


def save_project(project: Project) -> pathlib.Path:
    """Write a project atomically and return its path.

    Atomicity: we dump to a sibling tempfile and ``os.replace`` it into
    place. That guarantees a half-written file never appears under the
    project id — important because the API may load this file during the
    next request.
    """

    root = projects_dir()
    root.mkdir(parents=True, exist_ok=True)
    path = _path_for(project.id)
    text = project_to_toml(project)

    # Write to a tempfile in the same directory (so os.replace is atomic on
    # POSIX) and then rename. Suffix kept so editors recognize the type if
    # something crashes mid-write.
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{project.id}.", suffix=PROJECT_FILE_SUFFIX + ".tmp", dir=str(root)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return path


def delete_project(project_id: str) -> bool:
    """Remove a project's TOML file. Returns ``True`` if it existed."""

    path = _path_for(project_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def ensure_seeded(seed_projects: List[Project]) -> int:
    """Write seed projects to disk if the projects dir is empty.

    Returns the number of files actually written. Idempotent — once disk has
    at least one project we never overwrite (so user edits survive restarts).
    """

    root = projects_dir()
    root.mkdir(parents=True, exist_ok=True)
    if any(root.glob(f"*{PROJECT_FILE_SUFFIX}")):
        return 0
    n = 0
    for p in seed_projects:
        save_project(p)
        n += 1
    return n
