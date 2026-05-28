"""Cycle component CRUD routes."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, status

from deps import get_project_or_404
from models import (
    ComponentCreateRequest,
    ComponentModel,
    ComponentUpdateRequest,
    ComponentsResponse,
    EdgeModel,
)

router = APIRouter(prefix="/api/projects/{project_id}/components", tags=["components"])


@router.get("", response_model=ComponentsResponse)
def list_components(project_id: str) -> ComponentsResponse:
    proj = get_project_or_404(project_id)
    components = [ComponentModel.model_validate(c) for c in proj.get("components", [])]
    edges = [EdgeModel.model_validate(e) for e in proj.get("edges", [])]
    return ComponentsResponse(components=components, edges=edges)


@router.post("", response_model=ComponentModel, status_code=status.HTTP_201_CREATED)
def add_component(project_id: str, req: ComponentCreateRequest) -> ComponentModel:
    proj = get_project_or_404(project_id)
    component: Dict[str, Any] = {
        "id": uuid.uuid4().hex[:12],
        "kind": req.kind,
        "name": req.name,
        "params": dict(req.params),
        "position": dict(req.position),
    }
    proj.setdefault("components", []).append(component)
    return ComponentModel.model_validate(component)


# Boundary-condition keys mirrored from an Inlet component onto the project.
# The cycle solver reads inlet stagnation P/T/ṁ + composition from
# `project["boundary_conditions"]`, not from the Inlet component params, so
# without this mirror an "edit pressure_total on the inlet node → Save"
# would silently no-op on the next solve.
_INLET_BC_KEYS = {
    "pressure_total",
    "temperature_total",
    "mass_flow",
    "composition",
}


@router.patch("/{component_id}", response_model=ComponentModel)
def update_component(
    project_id: str, component_id: str, req: ComponentUpdateRequest
) -> ComponentModel:
    proj = get_project_or_404(project_id)
    components: List[Dict[str, Any]] = proj.setdefault("components", [])
    for comp in components:
        if comp["id"] == component_id:
            if req.name is not None:
                comp["name"] = req.name
            if req.params is not None:
                comp.setdefault("params", {}).update(req.params)
                # Mirror Inlet edits onto the project boundary conditions
                # so a "change Pt on the Inlet node → Save" actually feeds
                # the next cycle solve. Without this the solver reads
                # stale BC values and the user's edit appears silent.
                if comp.get("kind") == "Inlet":
                    bc = proj.setdefault("boundary_conditions", {})
                    for k, v in req.params.items():
                        if k in _INLET_BC_KEYS:
                            bc[k] = v
            if req.position is not None:
                comp["position"] = dict(req.position)
            return ComponentModel.model_validate(comp)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Component {component_id!r} not found in project {project_id!r}.",
    )


@router.delete("/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_component(project_id: str, component_id: str) -> None:
    proj = get_project_or_404(project_id)
    components: List[Dict[str, Any]] = proj.setdefault("components", [])
    for i, comp in enumerate(components):
        if comp["id"] == component_id:
            del components[i]
            # Drop edges touching the removed component
            proj["edges"] = [
                e for e in proj.get("edges", [])
                if e["source"] != component_id and e["target"] != component_id
            ]
            return None
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Component {component_id!r} not found in project {project_id!r}.",
    )
