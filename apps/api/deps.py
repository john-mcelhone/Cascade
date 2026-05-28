"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException, status

from jobs import JOBS, PROJECTS


def get_project_or_404(project_id: str) -> Dict[str, Any]:
    project = PROJECTS.get(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id!r} not found.",
        )
    return project


def get_job_or_404(job_id: str):  # noqa: ANN201 -- dataclass instance
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id!r} not found.",
        )
    return job
