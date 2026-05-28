"""Cascade project (.cascade.toml) format — schema, serializer, on-disk store.

The format is documented as ADAPT-014. The core promise is
*git-diffability*: a one-parameter edit produces a one-line diff.

Public surface
--------------

* ``Project``, ``ProjectMeta`` — Pydantic schema for the in-memory shape.
* ``project_to_toml(p) -> str`` — deterministic, sorted-keys TOML dump.
* ``project_from_toml(s) -> Project`` — parse + validate.
* ``load_project(id)``, ``save_project(p)``, ``list_projects()``,
  ``delete_project(id)`` — filesystem CRUD against
  ``$CASCADE_PROJECTS_DIR`` (default: ``~/.cascade/projects``).
* ``ensure_seeded(seeds)`` — write the demo projects on first startup.
"""

from __future__ import annotations

from .persistence import (
    DEFAULT_PROJECTS_DIR,
    PROJECT_FILE_SUFFIX,
    delete_project,
    ensure_seeded,
    list_projects,
    load_project,
    projects_dir,
    save_project,
)
from .schema import (
    CASCADE_VERSION,
    SCHEMA_VERSION,
    ComponentRecord,
    EdgeRecord,
    Project,
    ProjectMeta,
)
from .serializer import project_from_toml, project_to_toml

__all__ = [
    "DEFAULT_PROJECTS_DIR",
    "CASCADE_VERSION",
    "PROJECT_FILE_SUFFIX",
    "SCHEMA_VERSION",
    "ComponentRecord",
    "EdgeRecord",
    "Project",
    "ProjectMeta",
    "delete_project",
    "ensure_seeded",
    "list_projects",
    "load_project",
    "project_from_toml",
    "project_to_toml",
    "projects_dir",
    "save_project",
]
