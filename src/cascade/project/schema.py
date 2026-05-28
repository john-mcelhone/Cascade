"""Pydantic schema for a Cascade project (`.cascade.toml` v1).

This mirrors the dict-shape that today lives in ``apps/api/jobs.PROJECTS``.
The schema is intentionally tolerant about ``params`` / ``boundary_conditions``
/ ``settings`` payloads — the cycle solver validates strict types at solve
time, and we don't want to fail-load a project just because a UI added a new
free-form field.

The TOML file format is described as ADAPT-014 and pinned to
``schema_version = 1``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1
CASCADE_VERSION = "0.1.0"


class ProjectMeta(BaseModel):
    """Top-of-file metadata; round-trips byte-for-byte."""

    name: str
    description: str = ""
    kind: str = "blank"
    working_fluid: str = "air"
    created_at: datetime
    updated_at: datetime
    last_run_status: Optional[str] = None
    cascade_version: str = CASCADE_VERSION
    schema_version: int = SCHEMA_VERSION

    model_config = ConfigDict(extra="allow")


class ComponentRecord(BaseModel):
    """A cycle-canvas component. ``params`` is intentionally free-form."""

    id: str
    kind: str
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    position: Dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "y": 0.0})

    model_config = ConfigDict(extra="allow")


class EdgeRecord(BaseModel):
    """A wire between two component ports."""

    id: str
    source: str
    target: str
    source_port: str = "out"
    target_port: str = "in"

    model_config = ConfigDict(extra="allow")


class Project(BaseModel):
    """Full in-memory project.

    The ``id`` field is the slug used as both the dict key and the on-disk
    filename (``<id>.cascade.toml``). ``meta`` carries the human-facing
    description and timestamps; everything else lives in dedicated sections so
    a one-line edit produces a one-line diff.
    """

    id: str
    meta: ProjectMeta
    components: List[ComponentRecord] = Field(default_factory=list)
    edges: List[EdgeRecord] = Field(default_factory=list)
    boundary_conditions: Dict[str, Any] = Field(default_factory=dict)
    settings: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")

    # ---- legacy-dict bridge -------------------------------------------------

    @classmethod
    def from_legacy_dict(cls, d: Dict[str, Any]) -> "Project":
        """Construct from the legacy in-memory dict shape used by jobs.PROJECTS.

        The legacy dict flattens what TOML wants in sub-tables (``meta``).
        This adapter is the only place that knows about the old layout.
        """

        def _parse_dt(v: Any) -> datetime:
            if isinstance(v, datetime):
                return v
            if isinstance(v, str):
                # Tolerate trailing Z which fromisoformat() pre-3.11 rejects.
                s = v.replace("Z", "+00:00") if v.endswith("Z") else v
                return datetime.fromisoformat(s)
            return datetime.now(tz=timezone.utc)

        created_at = _parse_dt(d.get("created_at", datetime.now(tz=timezone.utc)))
        updated_at = _parse_dt(d.get("updated_at", created_at))
        meta = ProjectMeta(
            name=d.get("name", d.get("id", "untitled")),
            description=d.get("description", "") or "",
            kind=d.get("kind", "blank"),
            working_fluid=d.get("working_fluid", "air"),
            created_at=created_at,
            updated_at=updated_at,
            last_run_status=d.get("last_run_status"),
            cascade_version=CASCADE_VERSION,
            schema_version=SCHEMA_VERSION,
        )
        return cls(
            id=d["id"],
            meta=meta,
            components=[ComponentRecord.model_validate(c) for c in d.get("components", [])],
            edges=[EdgeRecord.model_validate(e) for e in d.get("edges", [])],
            boundary_conditions=dict(d.get("boundary_conditions", {})),
            settings=dict(d.get("settings", {})),
        )

    def to_legacy_dict(self) -> Dict[str, Any]:
        """Render back to the legacy dict shape the API routes consume."""

        return {
            "id": self.id,
            "name": self.meta.name,
            "description": self.meta.description,
            "kind": self.meta.kind,
            "working_fluid": self.meta.working_fluid,
            "created_at": self.meta.created_at.isoformat(),
            "updated_at": self.meta.updated_at.isoformat(),
            "last_run_status": self.meta.last_run_status,
            "components": [c.model_dump() for c in self.components],
            "edges": [e.model_dump() for e in self.edges],
            "boundary_conditions": dict(self.boundary_conditions),
            "settings": dict(self.settings),
        }
