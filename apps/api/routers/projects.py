"""Project CRUD routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, status

from deps import get_project_or_404
from jobs import PROJECTS
from models import (
    ProjectCreateRequest,
    ProjectDetail,
    ProjectSummary,
    ProjectUpdateRequest,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _slugify(name: str) -> str:
    """Generate a URL-safe id from a name. Falls back to a UUID hex."""

    s = "".join(ch.lower() if ch.isalnum() else "-" for ch in name.strip())
    while "--" in s:
        s = s.replace("--", "-")
    s = s.strip("-")
    if not s:
        s = uuid.uuid4().hex[:12]
    # Disambiguate if collision.
    base = s
    i = 1
    while s in PROJECTS:
        i += 1
        s = f"{base}-{i}"
    return s


@router.get("", response_model=List[ProjectSummary])
def list_projects() -> List[ProjectSummary]:
    summaries: List[ProjectSummary] = []
    for proj in PROJECTS.values():
        summaries.append(
            ProjectSummary(
                id=proj["id"],
                name=proj["name"],
                kind=proj["kind"],
                working_fluid=proj["working_fluid"],
                description=proj.get("description", ""),
                created_at=datetime.fromisoformat(proj["created_at"]),
                updated_at=datetime.fromisoformat(proj["updated_at"]),
                last_run_status=proj.get("last_run_status"),
            )
        )
    summaries.sort(key=lambda s: s.created_at)
    return summaries


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str) -> ProjectDetail:
    proj = get_project_or_404(project_id)
    return ProjectDetail.model_validate(
        {
            **proj,
            "created_at": datetime.fromisoformat(proj["created_at"]),
            "updated_at": datetime.fromisoformat(proj["updated_at"]),
        }
    )


@router.post("", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
def create_project(req: ProjectCreateRequest) -> ProjectDetail:
    project_id = _slugify(req.name)
    now_str = _now().isoformat()
    if req.template == "microturbine":
        from seed import _microturbine_project

        proj = _microturbine_project()
    elif req.template == "sco2":
        from seed import _sco2_project

        proj = _sco2_project()
    elif req.template == "aero":
        from seed import _aero_project

        proj = _aero_project()
    else:
        proj = {
            "kind": "blank",
            "working_fluid": "air",
            "components": [],
            "edges": [],
            "boundary_conditions": {},
            "settings": {},
        }
    # Override identity + name from the request.
    proj["id"] = project_id
    proj["name"] = req.name
    proj["description"] = req.description or proj.get("description", "")
    proj["created_at"] = now_str
    proj["updated_at"] = now_str
    proj["last_run_status"] = None
    PROJECTS[project_id] = proj
    return ProjectDetail.model_validate(
        {
            **proj,
            "created_at": _now(),
            "updated_at": _now(),
        }
    )


@router.patch("/{project_id}", response_model=ProjectDetail)
def update_project(project_id: str, req: ProjectUpdateRequest) -> ProjectDetail:
    proj = get_project_or_404(project_id)
    if req.name is not None:
        proj["name"] = req.name
    if req.description is not None:
        proj["description"] = req.description
    if req.settings is not None:
        proj.setdefault("settings", {}).update(req.settings)
    if req.boundary_conditions is not None:
        proj["boundary_conditions"] = req.boundary_conditions
    proj["updated_at"] = _now().isoformat()
    return ProjectDetail.model_validate(
        {
            **proj,
            "created_at": datetime.fromisoformat(proj["created_at"]),
            "updated_at": datetime.fromisoformat(proj["updated_at"]),
        }
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str) -> None:
    if project_id not in PROJECTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    del PROJECTS[project_id]
    return None
