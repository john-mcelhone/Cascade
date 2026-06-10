"""Cycle component CRUD routes."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status

from deps import get_project_or_404
from jobs import PROJECTS
from models import (
    ComponentCreateRequest,
    ComponentModel,
    ComponentUpdateRequest,
    ComponentsResponse,
    EdgeModel,
)

router = APIRouter(prefix="/api/projects/{project_id}/components", tags=["components"])


def _find_null_param(value: Any, path: str = "params") -> Optional[str]:
    """Return the key path of the first ``None`` anywhere in a params tree.

    ``Dict[str, Any]`` happily accepts JSON ``null``, but the TOML store
    cannot represent it: once a ``None`` is merged into the cached project,
    ``tomli_w`` raises ``TypeError`` on THIS and every LATER save — the
    store is poisoned until restart. Reject before mutating the cache.
    """
    if value is None:
        return path
    if isinstance(value, dict):
        for k, v in value.items():
            found = _find_null_param(v, f"{path}.{k}")
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            found = _find_null_param(v, f"{path}[{i}]")
            if found is not None:
                return found
    return None


def _reject_null_params(params: Dict[str, Any]) -> None:
    """422 (NON_SERIALIZABLE_PARAM) if the params tree holds any null."""
    null_path = _find_null_param(params)
    if null_path is not None:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "NON_SERIALIZABLE_PARAM",
                "message": (
                    f"Component parameter '{null_path}' is null. The TOML "
                    "project store cannot serialize null values — remove "
                    "the key or send a concrete value."
                ),
                "key_path": null_path,
            },
        )


def _save_or_503(project_id: str) -> None:
    """Persist a project after a CRUD mutation, surfacing IO failure.

    A failed write-through must never be silent: the cache and disk have
    diverged, so the caller gets a 503 naming the problem instead of a
    2xx that implies the edit is durable.
    """
    try:
        PROJECTS.save(project_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Project {project_id!r} was updated in memory but could "
                f"not be persisted to disk ({exc}). The edit will be lost "
                "on restart — check disk space and permissions on the "
                "projects directory, then retry."
            ),
        ) from exc


@router.get("", response_model=ComponentsResponse)
def list_components(project_id: str) -> ComponentsResponse:
    proj = get_project_or_404(project_id)
    components = [ComponentModel.model_validate(c) for c in proj.get("components", [])]
    edges = [EdgeModel.model_validate(e) for e in proj.get("edges", [])]
    return ComponentsResponse(components=components, edges=edges)


@router.post("", response_model=ComponentModel, status_code=status.HTTP_201_CREATED)
def add_component(project_id: str, req: ComponentCreateRequest) -> ComponentModel:
    proj = get_project_or_404(project_id)
    # Validate BEFORE mutating: a null merged into the cache would wedge
    # this and every later save (see _find_null_param).
    _reject_null_params(req.params)
    component: Dict[str, Any] = {
        "id": uuid.uuid4().hex[:12],
        "kind": req.kind,
        "name": req.name,
        "params": dict(req.params),
        "position": dict(req.position),
    }
    proj.setdefault("components", []).append(component)
    # Save-through: structural edits must persist NOW, not whenever some
    # job's worker happens to call PROJECTS.save (mirrors update_component).
    _save_or_503(project_id)
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
    # Validate BEFORE mutating: Dict[str, Any] accepts JSON null anywhere,
    # but a None merged into the cache wedges tomli_w on this and every
    # later save, poisoning the store until restart.
    if req.params is not None:
        _reject_null_params(req.params)
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
            # Save-through (U7): persist the edit to the TOML store NOW.
            # Without this, component edits reached disk only when some
            # job's worker happened to call PROJECTS.save — persistence
            # was incidental, and edits survived a restart only by luck.
            # Known side effect: save() flushes the WHOLE cached project
            # (acceptable for the single-user TOML store).
            _save_or_503(project_id)
            return ComponentModel.model_validate(comp)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Component {component_id!r} not found in project {project_id!r}.",
    )


@router.delete(
    "/{component_id}/geometry", status_code=status.HTTP_204_NO_CONTENT
)
def detach_component_geometry(project_id: str, component_id: str) -> None:
    """Detach hand-off geometry from a component (U8).

    Removes ``geometry_params`` and ``meanline_rpm_rpm`` from the
    component's params bag entirely and saves through to the TOML store.
    This is the sanctioned escape hatch alongside switching the efficiency
    mode back to fixed-isentropic: after a detach the live-meanline path
    falls back to constant-η (no geometry → graceful fallback) and a future
    handoff starts from a clean bag.
    """
    proj = get_project_or_404(project_id)
    for comp in proj.setdefault("components", []):
        if comp["id"] == component_id:
            params: Dict[str, Any] = comp.setdefault("params", {})
            params.pop("geometry_params", None)
            params.pop("meanline_rpm_rpm", None)
            # The provenance marker must not outlive the geometry it labels.
            params.pop("geometry_source_candidate_id", None)
            _save_or_503(project_id)
            return None
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
            # Save-through: a deletion that only lives in the cache would
            # resurrect the component on restart (mirrors update_component).
            _save_or_503(project_id)
            return None
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Component {component_id!r} not found in project {project_id!r}.",
    )
