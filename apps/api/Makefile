.PHONY: dev test

PY ?= ../../.venv/bin/python
UVICORN ?= ../../.venv/bin/uvicorn
PYTEST ?= ../../.venv/bin/pytest

dev:
	PYTHONPATH=../../src:. $(UVICORN) main:app --reload --port 8000

test:
	PYTHONPATH=../../src:. $(PYTEST) tests/ -v
