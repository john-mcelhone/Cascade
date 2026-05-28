"""Job + SSE bus + TOML-backed project store.

Jobs and SSE queues live in-memory: the worker pool
is a ``concurrent.futures.ThreadPoolExecutor`` and progress events go onto
an ``asyncio.Queue`` per job. Postgres + Celery + Redis are M02-deferred.

**Projects** are now persisted on disk under
``$CASCADE_PROJECTS_DIR`` (default: ``.cascade/projects``) as
``.cascade.toml`` files — see ``cascade.project`` and ADAPT-014. The
``PROJECTS`` symbol exported here is a dict-compatible proxy that
serializes mutations to disk so a server restart preserves user state.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterator, List, Optional, ValuesView

# Make ``cascade.project`` importable when run from ``apps/api`` (no install).
_CASCADE_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_CASCADE_SRC) not in sys.path:
    sys.path.insert(0, str(_CASCADE_SRC))

from cascade.project import (  # noqa: E402  (sys.path tweak above)
    Project,
    delete_project as _disk_delete_project,
    list_projects as _disk_list_projects,
    load_project as _disk_load_project,
    save_project as _disk_save_project,
)

log = logging.getLogger(__name__)

# Bounded so a single runaway job doesn't blow memory.
_MAX_QUEUE_EVENTS = 1024
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cascade-job")


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class Job:
    """In-memory job record."""

    id: str
    project_id: str
    kind: str
    status: str = "queued"
    progress: float = 0.0
    message: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    cancelled: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "kind": self.kind,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "error": self.error,
            "result": self.result,
        }


# Module-level stores.
JOBS: Dict[str, Job] = {}
CANDIDATES: Dict[str, List[Dict[str, Any]]] = {}  # job_id -> candidate dicts
CANDIDATE_INDEX: Dict[str, Dict[str, Any]] = {}  # candidate_id -> candidate dict


class _ProjectStore:
    """dict-compatible proxy over the on-disk TOML store.

    Reads pull from a lazily-warmed in-memory cache (so we don't re-parse a
    file per request). Writes (``__setitem__`` and ``__delitem__``) persist
    through to disk synchronously. In-place mutation of returned dicts
    (``PROJECTS[id]["last_run_status"] = "done"``) updates the cache but
    NOT disk — call :meth:`save` after such mutations to flush.

    The legacy dict API is preserved verbatim so existing routers keep
    working with no changes other than wiring this object in place of the
    plain dict.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._loaded = False
        self._lock = threading.Lock()

    # ---- cache management --------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            for project in _disk_list_projects():
                self._cache[project.id] = project.to_legacy_dict()
            self._loaded = True

    def reload(self) -> None:
        """Drop the cache and re-read everything from disk.

        Called by ``reset_for_tests`` between tests so each test sees a
        fresh on-disk snapshot.
        """

        with self._lock:
            self._cache.clear()
            self._loaded = False

    # ---- dict surface ------------------------------------------------------

    def __getitem__(self, key: str) -> Dict[str, Any]:
        self._ensure_loaded()
        return self._cache[key]

    def __setitem__(self, key: str, value: Dict[str, Any]) -> None:
        self._ensure_loaded()
        # Update cache first so a failed disk-write doesn't leave stale state.
        self._cache[key] = value
        _disk_save_project(Project.from_legacy_dict({**value, "id": key}))

    def __delitem__(self, key: str) -> None:
        self._ensure_loaded()
        if key in self._cache:
            del self._cache[key]
        _disk_delete_project(key)

    def __contains__(self, key: object) -> bool:
        self._ensure_loaded()
        return key in self._cache

    def __len__(self) -> int:
        self._ensure_loaded()
        return len(self._cache)

    def __bool__(self) -> bool:
        self._ensure_loaded()
        return bool(self._cache)

    def __iter__(self) -> Iterator[str]:
        self._ensure_loaded()
        return iter(self._cache)

    def get(self, key: str, default: Any = None) -> Any:
        self._ensure_loaded()
        return self._cache.get(key, default)

    def values(self) -> ValuesView[Dict[str, Any]]:
        self._ensure_loaded()
        return self._cache.values()

    def keys(self):  # noqa: ANN201
        self._ensure_loaded()
        return self._cache.keys()

    def items(self):  # noqa: ANN201
        self._ensure_loaded()
        return self._cache.items()

    def setdefault(self, key: str, default: Any = None) -> Any:
        self._ensure_loaded()
        if key not in self._cache:
            self[key] = default  # routes through __setitem__ -> disk
        return self._cache[key]

    def clear(self) -> None:
        """Wipe the on-disk store AND the cache (used by tests)."""

        self._ensure_loaded()
        for project_id in list(self._cache.keys()):
            try:
                _disk_delete_project(project_id)
            except Exception:  # noqa: BLE001
                pass
        self._cache.clear()
        self._loaded = True  # we just synced; no need to re-read

    # ---- TOML-aware helpers ------------------------------------------------

    def save(self, project_id: str) -> None:
        """Persist a project to disk after an in-place cache mutation.

        Use after touching ``PROJECTS[id][k] = v`` so the change survives a
        restart. Routers that do ``PROJECTS[id] = {...}`` do not need this
        — ``__setitem__`` already writes through.
        """

        self._ensure_loaded()
        d = self._cache.get(project_id)
        if d is None:
            return
        _disk_save_project(Project.from_legacy_dict({**d, "id": project_id}))


PROJECTS: _ProjectStore = _ProjectStore()


# Per-job event queues; the SSE endpoint awaits these. We store the event
# loop along with the queue so the worker thread can use
# loop.call_soon_threadsafe to enqueue events safely.
_JOB_QUEUES: Dict[str, "asyncio.Queue[Dict[str, Any]]"] = {}
_JOB_LOOPS: Dict[str, asyncio.AbstractEventLoop] = {}
_JOB_LOCK = threading.Lock()


def new_job_id() -> str:
    return uuid.uuid4().hex


def new_candidate_id() -> str:
    return uuid.uuid4().hex


def register_job(project_id: str, kind: str, loop: Optional[asyncio.AbstractEventLoop] = None) -> Job:
    """Create + register a Job and its event queue.

    ``loop`` should be the event loop that will consume the SSE queue
    (i.e. the server's main loop). When called from inside a request
    handler this is normally the running loop; sync endpoints invoked
    via FastAPI's worker thread must pass it in explicitly.
    """

    job_id = new_job_id()
    job = Job(id=job_id, project_id=project_id, kind=kind)
    with _JOB_LOCK:
        JOBS[job_id] = job
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                try:
                    loop = asyncio.get_event_loop_policy().get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
        # Bind the queue to the supplied loop so call_soon_threadsafe works
        # from worker threads.
        queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue(maxsize=_MAX_QUEUE_EVENTS)
        _JOB_QUEUES[job_id] = queue
        _JOB_LOOPS[job_id] = loop
    return job


def get_job(job_id: str) -> Optional[Job]:
    return JOBS.get(job_id)


def list_jobs(project_id: Optional[str] = None) -> List[Job]:
    if project_id is None:
        return list(JOBS.values())
    return [j for j in JOBS.values() if j.project_id == project_id]


def cancel_job(job_id: str) -> bool:
    job = JOBS.get(job_id)
    if job is None:
        return False
    if job.status in ("done", "failed", "cancelled"):
        return False
    job.cancelled = True
    job.status = "cancelled"
    job.message = "Cancelled by user."
    job.updated_at = _utcnow()
    job.finished_at = _utcnow()
    publish_event(
        job_id,
        {
            "job_id": job_id,
            "status": "cancelled",
            "progress": job.progress,
            "message": job.message,
        },
        final=True,
    )
    return True


def publish_event(job_id: str, event: Dict[str, Any], final: bool = False) -> None:
    """Push an event onto the job's SSE queue, thread-safe.

    Workers run on a background thread; the asyncio queue lives on the
    server's event loop. We schedule via call_soon_threadsafe so workers
    don't have to touch the loop directly.
    """

    loop = _JOB_LOOPS.get(job_id)
    queue = _JOB_QUEUES.get(job_id)
    if loop is None or queue is None:
        return
    payload = dict(event)
    payload["job_id"] = job_id
    if final:
        payload["final"] = True

    def _enqueue() -> None:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            log.warning("SSE queue full for job %s; dropping event", job_id)

    try:
        loop.call_soon_threadsafe(_enqueue)
    except RuntimeError:
        # Loop closed (e.g. test teardown) — drop silently.
        pass


async def stream_events(job_id: str, heartbeat_interval: float = 15.0):
    """Async generator yielding SSE events until the job finishes.

    Yields a dict for every event. Final events carry `final=True`.
    A keepalive `ping` is emitted every ``heartbeat_interval`` seconds.
    """

    queue = _JOB_QUEUES.get(job_id)
    if queue is None:
        # Job already cleaned up or never registered — emit one terminal
        # event so the client can close.
        job = get_job(job_id)
        if job is not None:
            yield {
                "job_id": job_id,
                "status": job.status,
                "progress": job.progress,
                "message": job.message,
                "result": job.result,
                "final": True,
            }
        return

    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
        except asyncio.TimeoutError:
            yield {"job_id": job_id, "ping": True}
            continue
        yield event
        if event.get("final"):
            break


def run_in_worker(
    job: Job,
    worker: Callable[[Job], Dict[str, Any]],
) -> None:
    """Submit a synchronous worker to the executor with status-tracking."""

    def _wrapper() -> None:
        job.status = "running"
        job.updated_at = _utcnow()
        publish_event(
            job.id,
            {
                "job_id": job.id,
                "status": "running",
                "progress": 0.0,
                "message": "Started.",
            },
        )
        try:
            result = worker(job)
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.error = f"{type(exc).__name__}: {exc}"
            job.message = job.error
            job.updated_at = _utcnow()
            job.finished_at = _utcnow()
            log.exception("Job %s failed", job.id)
            publish_event(
                job.id,
                {
                    "job_id": job.id,
                    "status": "failed",
                    "progress": job.progress,
                    "message": job.error,
                    "error": job.error,
                },
                final=True,
            )
            return
        if job.cancelled:
            # Worker already saw the cancel; do not overwrite.
            return
        job.status = "done"
        job.progress = 1.0
        job.message = "Completed."
        job.result = result
        job.updated_at = _utcnow()
        job.finished_at = _utcnow()
        publish_event(
            job.id,
            {
                "job_id": job.id,
                "status": "done",
                "progress": 1.0,
                "message": "Completed.",
                "result": result,
            },
            final=True,
        )

    _EXECUTOR.submit(_wrapper)


def report_progress(job: Job, progress: float, message: str = "", data: Optional[Dict[str, Any]] = None) -> None:
    """Helper for workers to update job progress + emit an SSE event."""

    job.progress = max(0.0, min(1.0, progress))
    job.message = message or job.message
    job.updated_at = _utcnow()
    payload: Dict[str, Any] = {
        "job_id": job.id,
        "status": "running",
        "progress": job.progress,
        "message": job.message,
    }
    if data is not None:
        payload["data"] = data
    publish_event(job.id, payload)


def reset_for_tests() -> None:
    """Wipe in-memory stores and the project cache. Used by pytest fixtures.

    Note: this does NOT delete the on-disk ``.cascade.toml`` files. Tests
    that need an isolated on-disk store should set ``CASCADE_PROJECTS_DIR``
    to a per-test tempdir; ``PROJECTS.reload()`` then picks up the new
    location on next access.
    """

    JOBS.clear()
    PROJECTS.reload()
    CANDIDATES.clear()
    CANDIDATE_INDEX.clear()
    _JOB_QUEUES.clear()
    _JOB_LOOPS.clear()
