"""FastAPI entry point for the Cascade web app.

Run with:

    cd apps/api
    PYTHONPATH=../../src \
        ../../.venv/bin/uvicorn main:app --reload --port 8000

Mounts every router under ``/api`` and serves SSE under
``/api/jobs/:job_id/events``. The in-memory project store is seeded
with three demo projects on startup.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from deps import get_job_or_404
from jobs import PROJECTS, cancel_job, list_jobs, stream_events
from models import JobModel
from routers import (
    analysis,
    candidates,
    components,
    cycle,
    explore,
    loss_models,
    manufacturability,
    map as map_router,
    materials,
    projects,
    rotor,
    validation,
)
from routers.rotor import bearings_router
from seed import seed_projects


log = logging.getLogger("cascade.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Idempotent — re-seed if the store is empty.
    if not PROJECTS:
        seed_projects()
        log.info("Cascade API ready; seeded %d projects", len(PROJECTS))
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Cascade API",
        version="0.1.0",
        description=(
            "REST + SSE API powering the Cascade web app. Wraps the cascade "
            "Python package; serves design exploration, cycle solves, "
            "performance maps, rotor dynamics, and glTF geometry."
        ),
        lifespan=lifespan,
    )

    # CORS — allow the Next.js dev server with credentials.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Cascade-Stub"],
    )

    # Seed eagerly too so test clients that don't trigger lifespan still
    # see the seeded data. Idempotent.
    if not PROJECTS:
        seed_projects()

    @app.get("/api/health")
    def health() -> Dict[str, Any]:
        from cascade import __version__ as cascade_version

        return {
            "status": "ok",
            "version": "0.1.0",
            "cascade_version": cascade_version,
            "service": "cascade-api",
        }

    @app.get("/api/health/cad")
    def health_cad() -> Dict[str, Any]:
        """Probe whether the server has the optional ``cascade[cad]`` extra.

        Returns ``{"cad_available": true/false, "occt_version": "..."}``
        so the UI can disable STEP/IGES buttons proactively rather than
        discovering the gap only after a click (W-19, AC1).

        When ``pythonocc-core`` is installed ``occt_version`` is a
        human-readable version string; when not installed it is ``null``.
        This endpoint always returns 200 — the caller reads ``cad_available``
        to decide whether to render enabled buttons.
        """
        try:
            from OCC.Core.BRep import BRep_Builder  # type: ignore[import]

            try:
                from OCC.Core import VERSION as _occ_version  # type: ignore[import]
                occt_version: Any = _occ_version
            except ImportError:
                try:
                    from OCC import VERSION as _occ_version2  # type: ignore[import]
                    occt_version = _occ_version2
                except ImportError:
                    occt_version = "unknown"
            return {"cad_available": True, "occt_version": str(occt_version)}
        except ImportError:
            return {"cad_available": False, "occt_version": None}

    # Routers
    app.include_router(projects.router)
    app.include_router(components.router)
    app.include_router(cycle.router)
    app.include_router(explore.router)
    app.include_router(map_router.router)
    app.include_router(analysis.router)
    app.include_router(rotor.router)
    app.include_router(bearings_router)
    app.include_router(candidates.router)
    app.include_router(loss_models.router)
    app.include_router(manufacturability.router)
    app.include_router(materials.router)
    app.include_router(validation.router)

    # ---- Jobs surface (defined here because it spans projects) ----

    @app.get("/api/jobs", response_model=List[JobModel])
    def get_jobs(project_id: Optional[str] = None) -> List[JobModel]:
        """List jobs, optionally scoped to one project (U8 runs page).

        Newest first — the runs page reads top-down.
        """
        jobs_list = sorted(
            list_jobs(project_id), key=lambda j: j.created_at, reverse=True
        )
        return [JobModel.model_validate(j.to_dict()) for j in jobs_list]

    @app.get("/api/jobs/{job_id}", response_model=JobModel)
    def get_job_endpoint(job_id: str) -> JobModel:
        job = get_job_or_404(job_id)
        return JobModel.model_validate(job.to_dict())

    @app.get("/api/jobs/{job_id}/events")
    async def job_events(job_id: str) -> EventSourceResponse:
        # Validate existence eagerly so the SSE stream doesn't open for a
        # nonexistent job. We still allow streaming finished jobs (returns
        # one terminal event).
        get_job_or_404(job_id)

        async def event_generator():
            async for event in stream_events(job_id):
                if event.get("ping"):
                    yield {"event": "ping", "data": "{}"}
                    continue
                import json as _json

                yield {"event": "message", "data": _json.dumps(event)}
                if event.get("final"):
                    break

        return EventSourceResponse(event_generator())

    @app.delete("/api/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
    def cancel_job_endpoint(job_id: str) -> None:
        get_job_or_404(job_id)
        if not cancel_job(job_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Job already finished or cancelled.",
            )
        return None

    return app


app = create_app()
