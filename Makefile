.DEFAULT_GOAL := help
PY := python3
PIP := $(PY) -m pip
VENV := .venv
VENV_PY := $(VENV)/bin/python
PROJECT_ROOT := $(shell pwd)
NODE_BIN := $(PROJECT_ROOT)/nodeenv/bin

.PHONY: help setup api web run stop logs test test-units test-cycle test-meanline test-rotor test-geometry validation regression integration spec-parity check-citations lint typecheck demo clean clean-web

help:
	@echo "Cascade — make targets"
	@echo ""
	@echo "  setup        Install Python deps in .venv"
	@echo ""
	@echo "  api          Start the FastAPI server on :8000 (foreground)"
	@echo "  web          Start the Next.js dev server on :3000 (foreground)"
	@echo "  run          Start BOTH api+web in the background; logs to .logs/"
	@echo "  stop         Stop background api+web"
	@echo "  logs         Tail .logs/api.log and .logs/web.log"
	@echo ""
	@echo "  test         Run Python tests (non-validation)"
	@echo "  validation   Run validation suite vs SPEC_SHEET.md §12"
	@echo "  demo         Run the 3 demo projects via CLI"
	@echo ""
	@echo "  clean        Remove build artifacts and caches (Python + Next)"
	@echo "  clean-web    Just nuke apps/web/.next (fixes vendor-chunks errors)"
	@echo ""
	@echo "Open the app at: http://localhost:3000/projects/microturbine-30kw/flowpath"

$(VENV)/bin/activate: pyproject.toml
	$(PY) -m venv $(VENV)
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -e ".[dev,api]"
	$(VENV_PY) -m pip install fastapi 'uvicorn[standard]' sse-starlette trimesh pygltflib pydantic-settings httpx pytest-asyncio
	@touch $(VENV)/bin/activate

setup: $(VENV)/bin/activate
	@echo "Cascade dev environment ready."
	@echo "Next: 'make run' to start the api + web."

api: setup
	@echo "Starting Cascade API on http://localhost:8000"
	@PYTHONPATH=$(PROJECT_ROOT)/src:$(PROJECT_ROOT)/apps/api \
		$(VENV_PY) -m uvicorn apps.api.main:app --port 8000 --reload

web:
	@if [ ! -d apps/web/node_modules ]; then \
		echo "Installing web dependencies (first time only)..."; \
		cd apps/web && PATH="$(NODE_BIN):$$PATH" npm install --legacy-peer-deps; \
	fi
	@echo "Starting Cascade web app on http://localhost:3000"
	@cd apps/web && PATH="$(NODE_BIN):$$PATH" npm run dev

run: setup
	@mkdir -p .logs
	@if [ ! -d apps/web/node_modules ]; then \
		echo "Installing web dependencies (first time only)..."; \
		cd apps/web && PATH="$(NODE_BIN):$$PATH" npm install --legacy-peer-deps; \
	fi
	@echo "Starting API on :8000..."
	@PYTHONPATH=$(PROJECT_ROOT)/src:$(PROJECT_ROOT)/apps/api \
		nohup $(VENV_PY) -m uvicorn apps.api.main:app --port 8000 \
		> .logs/api.log 2>&1 & \
		echo $$! > .logs/api.pid
	@echo "Starting Web on :3000..."
	@cd apps/web && PATH="$(NODE_BIN):$$PATH" \
		nohup npm run dev > $(PROJECT_ROOT)/.logs/web.log 2>&1 & \
		echo $$! > $(PROJECT_ROOT)/.logs/web.pid
	@sleep 3
	@echo ""
	@echo "Cascade is starting up. Give it ~5 seconds, then visit:"
	@echo "  http://localhost:3000/projects/microturbine-30kw/flowpath  (Flow Path PD — the hero)"
	@echo "  http://localhost:3000/projects/microturbine-30kw/cycle     (Cycle Canvas)"
	@echo "  http://localhost:3000/projects/microturbine-30kw/map       (Performance Map)"
	@echo "  http://localhost:3000/projects/microturbine-30kw/rotor     (Rotor Dynamics)"
	@echo "  http://localhost:3000/docs/validation                      (Public validation report)"
	@echo ""
	@echo "  Logs:  make logs"
	@echo "  Stop:  make stop"

stop:
	@if [ -f .logs/api.pid ]; then \
		kill `cat .logs/api.pid` 2>/dev/null && echo "Stopped API" || echo "API was not running"; \
		rm -f .logs/api.pid; \
	fi
	@if [ -f .logs/web.pid ]; then \
		kill `cat .logs/web.pid` 2>/dev/null && echo "Stopped Web" || echo "Web was not running"; \
		rm -f .logs/web.pid; \
	fi
	@# Belt-and-suspenders: kill anything on :3000 / :8000
	@lsof -ti:8000 | xargs kill -9 2>/dev/null || true
	@lsof -ti:3000 | xargs kill -9 2>/dev/null || true

logs:
	@tail -f .logs/api.log .logs/web.log

test: setup
	@PYTHONPATH=$(PROJECT_ROOT)/src:$(PROJECT_ROOT)/apps/api \
		$(VENV_PY) -m pytest tests/ -m "not validation and not slow" -v

test-units: setup
	@PYTHONPATH=$(PROJECT_ROOT)/src $(VENV_PY) -m pytest tests/units -v

test-cycle: setup
	@PYTHONPATH=$(PROJECT_ROOT)/src $(VENV_PY) -m pytest tests/cycle -v

test-meanline: setup
	@PYTHONPATH=$(PROJECT_ROOT)/src $(VENV_PY) -m pytest tests/meanline -v

test-rotor: setup
	@PYTHONPATH=$(PROJECT_ROOT)/src $(VENV_PY) -m pytest tests/rotor -v

test-geometry: setup
	@PYTHONPATH=$(PROJECT_ROOT)/src $(VENV_PY) -m pytest tests/geometry -v

regression: setup
	@echo "Running regression suite (CI-03)"
	@PYTHONPATH=$(PROJECT_ROOT)/src:$(PROJECT_ROOT)/apps/api \
		$(VENV_PY) -m pytest tests/regression/ -v

integration: setup
	@echo "Running integration tests"
	@PYTHONPATH=$(PROJECT_ROOT)/src:$(PROJECT_ROOT)/apps/api \
		$(VENV_PY) -m pytest tests/integration/ -v

spec-parity: setup
	@echo "Running SPEC §2 parity gate (CI-02)"
	@PYTHONPATH=$(PROJECT_ROOT)/src $(VENV_PY) -m pytest tests/spec_parity/ -v

check-citations: setup
	@echo "Running citation integrity check (CI-01)"
	@PYTHONPATH=$(PROJECT_ROOT)/src $(VENV_PY) scripts/check_citations.py

validation: setup
	@echo "Running public validation suite — see SPEC_SHEET.md §12"
	@PYTHONPATH=$(PROJECT_ROOT)/src $(VENV_PY) -m pytest tests/ -m validation -v --tb=short

lint: setup
	@PYTHONPATH=$(PROJECT_ROOT)/src $(VENV_PY) -m ruff check src tests

typecheck: setup
	@PYTHONPATH=$(PROJECT_ROOT)/src $(VENV_PY) -m mypy src

demo: setup
	@PYTHONPATH=$(PROJECT_ROOT)/src $(VENV_PY) -m cascade.cli demo run

clean:
	rm -rf $(VENV) build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache .logs
	rm -rf apps/web/.next apps/web/.turbo
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Nuke Next.js build cache and restart. Use after a webpack-runtime chunk
# error (vendor-chunks/*.js not found), which happens when `npm run build`
# overlaps with a running dev server.
clean-web:
	@$(MAKE) stop
	@rm -rf apps/web/.next apps/web/.turbo
	@echo "Cleared apps/web/.next and .turbo. Run 'make run' to restart."
