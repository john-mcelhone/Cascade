# Cascade API

FastAPI service powering the Cascade web app. Wraps the `cascade` Python
package and exposes a REST + SSE surface for project management, cycle
solving, design exploration, performance maps, mean-line analysis, rotor
dynamics, and glTF geometry streaming.

## Run

```sh
cd apps/api
PYTHONPATH=../../src \
  ../../.venv/bin/uvicorn main:app --reload --port 8000
```

Then:

```sh
curl http://localhost:8000/api/health
curl http://localhost:8000/api/projects
curl -X POST http://localhost:8000/api/projects/microturbine-30kw/cycle/solve
```

## Tests

```sh
cd apps/api
PYTHONPATH=../../src:. \
  ../../.venv/bin/pytest tests/
```

## Notes

- In-memory state only. Postgres is M02-deferred.
- Long-running jobs run on a `ThreadPoolExecutor` (Celery is M02-deferred).
- The geometry endpoints return a stub `.glb` until `cascade.geometry`
  lands; the response carries `X-Cascade-Stub: true` so the frontend can
  show a wireframe placeholder.
