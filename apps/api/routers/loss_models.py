"""Loss model catalogue + plugin management.

Two surfaces live here:

1. **Global catalogue** (`GET /api/loss-models`) — the v1 read-only list
   of built-in loss models with full citation + validity envelope. This
   is preserved for backwards compatibility with the existing UI.

2. **Per-project plugin management** (`POST /api/projects/{id}/loss-models/upload`,
   `GET /api/projects/{id}/loss-models`,
   `POST /api/projects/{id}/loss-models/{name}/select`) — the new
   ADAPT-035 surface. Lets a user upload a Python file with a
   `LossModel` subclass, see it appear in the per-project list, and
   pick it as the active loss model for the project's components.

The on-disk plugin store lives at:

    apps/api/.plugin_store/<project_id>/<filename>.py

(this directory is gitignored). On startup the API scans the store
and re-registers every plugin it finds, so the registry survives
process restarts.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from deps import get_project_or_404
from models import (
    ActiveLossModelResponse,
    LossModelInfo,
    PluginLossModelInfo,
    PluginUploadResponse,
)


log = logging.getLogger("cascade.api.loss_models")


router = APIRouter(prefix="/api", tags=["loss-models"])


# ---------------------------------------------------------------------------
# On-disk plugin store — initialised on first import.
# ---------------------------------------------------------------------------


def _plugin_store_dir() -> Path:
    """Return the on-disk plugin store root.

    Honors CASCADE_PLUGIN_STORE_DIR for ops + test isolation; defaults
    to a path under the apps/api package so the API can be deployed
    standalone.
    """
    env = os.environ.get("CASCADE_PLUGIN_STORE_DIR")
    if env:
        return Path(env)
    # apps/api/.plugin_store/
    here = Path(__file__).resolve().parent.parent
    return here / ".plugin_store"


# Map: project_id → active loss model name (in-memory; persistence
# happens at the project-detail level in a real deployment).
_ACTIVE_PROJECT_LOSS: Dict[str, str] = {}


def _bootstrap_registry_from_disk() -> None:
    """Scan the plugin store and register every file with the registry.

    Idempotent: re-loading an already-registered plugin (same name) is
    a silent no-op as long as the origin matches.
    """
    try:
        from cascade.plugins import (
            PLUGIN_REGISTRY,
            discover_installed_plugins,
            load_plugins_from_file,
        )
    except ImportError as exc:
        log.warning("cascade.plugins not importable: %s", exc)
        return
    root = _plugin_store_dir()
    if not root.exists():
        return
    for path in discover_installed_plugins(root):
        try:
            for cls in load_plugins_from_file(path):
                try:
                    PLUGIN_REGISTRY.register(cls, origin="user")
                except Exception as exc:  # noqa: BLE001
                    log.warning(
                        "Skipping plugin %s from %s: %s", cls.name, path, exc
                    )
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to load plugin file %s: %s", path, exc)


_bootstrap_registry_from_disk()


# ---------------------------------------------------------------------------
# Legacy global catalogue (preserved for backwards compatibility)
# ---------------------------------------------------------------------------


def _validity_envelope_dict(envelope: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for attr in ("M_rel_max", "Re_min", "tip_clearance_ratio_max"):
        val = getattr(envelope, attr, None)
        if val is not None:
            out[attr] = val
    return out


@router.get("/loss-models", response_model=List[LossModelInfo])
def list_loss_models() -> List[LossModelInfo]:
    """Return the global loss-model catalogue with citations.

    Uses the importable model classes from
    `cascade.meanline.loss_models_impl`. This endpoint is the v0
    surface that pre-dated the plugin system; it stays read-only and
    only lists the built-in classes.
    """

    out: List[LossModelInfo] = []

    try:
        from cascade.meanline.loss_models_impl import (
            AungierCentrifugal,
            StanitzSlip,
            StodolaSlip,
            WhitfieldBainesRadial,
            WiesnerSlip,
        )
    except ImportError:
        return out

    for cls in (WhitfieldBainesRadial, AungierCentrifugal):
        try:
            inst = cls()
            envelope = getattr(inst, "validity_envelope", None)
            out.append(
                LossModelInfo(
                    name=inst.name,
                    machine_class=getattr(inst, "machine_class", "unknown"),
                    citation=inst.citation,
                    description=cls.__doc__.split("\n\n")[0] if cls.__doc__ else "",
                    scale_factors=dict(getattr(inst, "scale_factors", {}) or {}),
                    validity_envelope=_validity_envelope_dict(envelope)
                    if envelope is not None
                    else {},
                )
            )
        except Exception as exc:  # noqa: BLE001
            out.append(
                LossModelInfo(
                    name=cls.__name__,
                    machine_class="unknown",
                    citation=f"<not instantiable: {exc}>",
                )
            )

    # Slip-factor closures
    for cls in (StanitzSlip, WiesnerSlip, StodolaSlip):
        try:
            inst = cls()
            out.append(
                LossModelInfo(
                    name=inst.name,
                    machine_class="slip_factor",
                    citation=inst.citation,
                    description=cls.__doc__.split("\n\n")[0] if cls.__doc__ else "",
                )
            )
        except Exception as exc:  # noqa: BLE001
            out.append(
                LossModelInfo(
                    name=cls.__name__,
                    machine_class="slip_factor",
                    citation=f"<not instantiable: {exc}>",
                )
            )

    return out


# ---------------------------------------------------------------------------
# Per-project plugin management (ADAPT-035)
# ---------------------------------------------------------------------------


def _plugin_to_info(cls: Any, origin: str) -> PluginLossModelInfo:
    return PluginLossModelInfo(
        name=getattr(cls, "name", cls.__name__),
        origin=origin,  # type: ignore[arg-type]
        applicable_machine_classes=list(
            getattr(cls, "applicable_machine_classes", []) or []
        ),
        description=getattr(cls, "description", "") or "",
        citation=getattr(cls, "citation", "") or "",
        author=getattr(cls, "author", "") or "",
        version=getattr(cls, "version", "") or "",
    )


@router.get(
    "/projects/{project_id}/loss-models",
    response_model=List[PluginLossModelInfo],
)
def list_project_loss_models(
    project_id: str,
    machine_class: Optional[str] = None,
) -> List[PluginLossModelInfo]:
    """List every loss model available to the project — built-in + user.

    Args:
        project_id: Project identifier (validated to exist; 404 otherwise).
        machine_class: Optional filter ('radial_turbine',
            'centrifugal_compressor', 'axial_turbine').
    """
    get_project_or_404(project_id)
    try:
        from cascade.plugins import PLUGIN_REGISTRY
    except ImportError:
        return []
    classes = PLUGIN_REGISTRY.list(machine_class=machine_class)
    out: List[PluginLossModelInfo] = []
    for cls in classes:
        origin = PLUGIN_REGISTRY.origin(cls.name) or "user"
        out.append(_plugin_to_info(cls, origin))
    return out


@router.post(
    "/projects/{project_id}/loss-models/upload",
    response_model=PluginUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_loss_model(
    project_id: str,
    file: UploadFile = File(...),
) -> PluginUploadResponse:
    """Upload a Python file containing a `LossModel` subclass.

    The file is:
    1. Saved to `<store>/<project_id>/<filename>.py`.
    2. Loaded + validated via `cascade.plugins.load_plugin_from_file`.
    3. Registered in the process-wide PLUGIN_REGISTRY under origin='user'.

    Returns the loaded class metadata. On any error (syntax error,
    invalid class, validation failure) returns 422 with detail = error
    message; the on-disk file is removed.

    SAFETY: This endpoint loads untrusted Python and executes it
    IN-PROCESS. Production deployments MUST gate it behind authentication
    and rate-limit per user. v1.1 will add subprocess isolation.
    """
    get_project_or_404(project_id)

    if not file.filename or not file.filename.endswith(".py"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Upload must be a `.py` file.",
        )

    try:
        from cascade.plugins import (
            PLUGIN_REGISTRY,
            PluginLoadError,
            PluginValidationError,
            install_plugin_file,
            load_plugin_from_file,
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"cascade.plugins is not importable: {exc}",
        ) from exc

    # Write the upload to a temp file first so we can validate before
    # moving it into the durable store.
    body = await file.read()
    if not body:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty.",
        )
    if len(body) > 1_000_000:  # 1 MB hard cap; plugins should be tiny
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Plugin file too large (limit 1 MB).",
        )

    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".py", delete=False
    ) as tmp:
        tmp.write(body)
        tmp_path = Path(tmp.name)

    try:
        try:
            cls = load_plugin_from_file(tmp_path)
        except PluginLoadError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to load plugin: {exc}",
            ) from exc
        except PluginValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Plugin validation failed: {exc}",
            ) from exc

        # Stash the safe-named file under the store.
        store_root = _plugin_store_dir()
        store_root.mkdir(parents=True, exist_ok=True)
        # Reconstitute the user's filename, sanitised.
        safe_name = "".join(
            c if (c.isalnum() or c in "._-") else "_" for c in file.filename
        )
        # Materialize the upload bytes at a destination path inside
        # the store, then re-load from there so the in-memory module
        # path reflects the durable location.
        target_dir = store_root / project_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / safe_name
        shutil.copyfile(tmp_path, target)

        # Re-load from the durable path so the module's __file__ matches
        # the on-disk location (helpful for tracebacks).
        cls = load_plugin_from_file(target)

        try:
            PLUGIN_REGISTRY.register(cls, origin="user")
        except PluginValidationError as exc:
            # Roll back the on-disk write
            target.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc

        log.info(
            "Registered plugin %s for project %s (path=%s)",
            cls.name,
            project_id,
            target,
        )
        return PluginUploadResponse(
            plugin=_plugin_to_info(cls, "user"),
            stored_path=str(target),
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post(
    "/projects/{project_id}/loss-models/{name}/select",
    response_model=ActiveLossModelResponse,
)
def select_loss_model(
    project_id: str,
    name: str,
) -> ActiveLossModelResponse:
    """Set the active loss model for the project's components.

    The name must already be registered (built-in or user). 404 if
    not. The selection is stored in-memory keyed by project_id; a
    production deployment writes it to the project's TOML deck.
    """
    project = get_project_or_404(project_id)
    try:
        from cascade.plugins import PLUGIN_REGISTRY
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"cascade.plugins not importable: {exc}",
        ) from exc
    cls = PLUGIN_REGISTRY.get(name)
    if cls is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Loss model {name!r} not registered.",
        )
    _ACTIVE_PROJECT_LOSS[project_id] = name
    # Mirror into the in-memory project settings so a subsequent
    # GET /projects/{id} surfaces it.
    settings = project.setdefault("settings", {})
    settings["active_loss_model"] = name
    return ActiveLossModelResponse(
        project_id=project_id, active_loss_model=name
    )


class PluginExecuteRequest(BaseModel):
    """Input payload for a sandboxed plugin execution call.

    ``context`` must be a dict with all fields required by ``LossContext``
    (see ``cascade.plugins.base.LossContext``). The ``extra`` field is
    optional; if absent it defaults to ``{}``.
    """

    context: Dict[str, Any]
    timeout: float = 5.0


class PluginExecuteResponse(BaseModel):
    """Result of a sandboxed plugin execution call."""

    zeta: Optional[float] = None
    error: Optional[str] = None
    success: bool


@router.post(
    "/projects/{project_id}/loss-models/{name}/execute",
    response_model=PluginExecuteResponse,
)
def execute_loss_model_sandbox(
    project_id: str,
    name: str,
    body: PluginExecuteRequest,
) -> PluginExecuteResponse:
    """Execute a registered plugin's ``loss_coefficient`` in a subprocess sandbox.

    This is the W-21 isolation path: user plugins run in a forked Python
    process with a hard wall-clock timeout and best-effort resource limits.
    A buggy plugin (infinite loop, ``sys.exit``, OOM) cannot crash the API
    worker process.

    Returns the scalar zeta value on success, or a structured error dict
    on timeout / crash / invalid output.
    """
    get_project_or_404(project_id)
    try:
        from cascade.plugins import PLUGIN_REGISTRY
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"cascade.plugins not importable: {exc}",
        ) from exc

    cls = PLUGIN_REGISTRY.get(name)
    if cls is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Loss model {name!r} not registered.",
        )

    origin = PLUGIN_REGISTRY.origin(name)
    if origin == "builtin":
        # Built-in models are trusted and don't need subprocess isolation.
        # Call them directly for better performance.
        try:
            from cascade.plugins.base import LossContext

            ctx = LossContext(**body.context)
            instance = cls()
            zeta = instance.loss_coefficient(ctx)
        except Exception as exc:
            return PluginExecuteResponse(
                zeta=None,
                error=f"Built-in model execution failed: {exc}",
                success=False,
            )
        return PluginExecuteResponse(zeta=float(zeta), error=None, success=True)

    # User plugin — locate the on-disk file and run in sandbox.
    store_root = _plugin_store_dir() / project_id
    plugin_file: Optional[Path] = None
    if store_root.exists():
        for path in store_root.glob("*.py"):
            try:
                from cascade.plugins import load_plugins_from_file

                for candidate_cls in load_plugins_from_file(path):
                    if candidate_cls.name == name:
                        plugin_file = path
                        break
            except Exception:  # noqa: BLE001
                continue
            if plugin_file is not None:
                break

    if plugin_file is None:
        return PluginExecuteResponse(
            zeta=None,
            error=(
                f"Plugin {name!r} is registered but its on-disk file was not found. "
                "Re-upload the plugin to restore the file."
            ),
            success=False,
        )

    from cascade.plugins.sandbox import run_plugin_in_subprocess

    result = run_plugin_in_subprocess(
        plugin_file,
        body.context,
        timeout=body.timeout,
    )

    if "error" in result:
        return PluginExecuteResponse(
            zeta=None,
            error=result["error"],
            success=False,
        )
    return PluginExecuteResponse(
        zeta=result["zeta"],
        error=None,
        success=True,
    )


@router.delete(
    "/projects/{project_id}/loss-models/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_loss_model(project_id: str, name: str) -> None:
    """Remove a user-installed plugin from the registry + disk.

    Built-in plugins cannot be deleted (409). Idempotent for unknown
    names (204).
    """
    get_project_or_404(project_id)
    try:
        from cascade.plugins import PLUGIN_REGISTRY
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    origin = PLUGIN_REGISTRY.origin(name)
    if origin == "builtin":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete built-in plugin {name!r}.",
        )
    PLUGIN_REGISTRY.unregister(name)
    # Best-effort: remove the on-disk file too.
    store_root = _plugin_store_dir() / project_id
    if store_root.exists():
        for path in store_root.glob("*.py"):
            try:
                from cascade.plugins import load_plugins_from_file

                for cls in load_plugins_from_file(path):
                    if cls.name == name:
                        path.unlink(missing_ok=True)
                        break
            except Exception:  # noqa: BLE001
                continue
    return None
