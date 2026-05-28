"""Materials catalogue HTTP surface (ADAPT-031).

Exposes ``GET /api/materials`` (list, optionally filtered by family)
and ``GET /api/materials/{name}`` (full record including all
temperature-property tables and the open-literature citation).

The endpoint is a thin wrapper around :class:`cascade.materials.MaterialDB`.
Names are resolved through the alias table so legacy strings like
``STEEL_AISI4340`` keep working.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query


router = APIRouter(prefix="/api/materials", tags=["materials"])


def _safe_db():
    """Late-bound import — keeps the API importable even if the
    cascade.materials package is partially refactored."""
    try:
        from cascade.materials import MaterialDB

        return MaterialDB
    except ImportError as exc:  # pragma: no cover -- import-time only
        raise HTTPException(
            status_code=503,
            detail=f"cascade.materials unavailable: {exc}",
        )


@router.get("", response_model=List[Dict[str, Any]])
def list_materials(
    family: Optional[str] = Query(
        None,
        description=(
            "Filter to a single family. Case-insensitive. "
            "Use /api/materials/_/families to discover families."
        ),
    ),
) -> List[Dict[str, Any]]:
    """List every registered material as a JSON record.

    Each record includes the full temperature-property tables (E,
    sigma_y, sigma_u, alpha, k, cp) and the open-literature citation
    in ``source``. The UI picker uses the lightweight subset
    (name, designation, family) and lazy-loads the rest on selection.
    """
    db = _safe_db()
    materials = db.by_family(family) if family else db.list()
    return [m.as_dict() for m in materials]


@router.get("/_/families", response_model=List[str])
def list_families() -> List[str]:
    """Distinct family strings, sorted, for UI grouping."""
    return _safe_db().families()


@router.get("/{name:path}", response_model=Dict[str, Any])
def get_material(name: str) -> Dict[str, Any]:
    """Return one material's full record."""
    db = _safe_db()
    try:
        m = db.get(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return m.as_dict()
