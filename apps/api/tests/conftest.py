"""Isolate API tests from the user-global project store.

Mirrors ``tests/conftest.py`` (the API tests run as a separate pytest
invocation with their own rootdir, so the root conftest does not load
here). The override binds before collection imports any test module;
see ``cascade.project.persistence.projects_dir()`` for the env-var
contract. Per-test ``monkeypatch.setenv`` still overrides the baseline.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Session-level baseline: binds before collection imports any test module.
os.environ.setdefault(
    "CASCADE_PROJECTS_DIR",
    tempfile.mkdtemp(prefix="cascade-api-tests-"),
)

# Make `jobs` importable from the fixture below (the test modules do the
# same dance at import time; conftest loads first).
_APP_DIR = Path(__file__).resolve().parent.parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))


@pytest.fixture(autouse=True)
def _fresh_projects_store(tmp_path, monkeypatch):
    """Give every test its own on-disk project store.

    The cycle worker persists ``last_run_status`` (and therefore the whole
    cached project) on every terminal solve path, so tests that PATCH a
    component, solve, and PATCH it back would otherwise leak mid-test
    parameter state to a shared on-disk store and pollute later tests.
    Each test gets a pristine dir; the per-file ``app`` fixtures re-seed it
    via ``create_app()``. ``projects_dir()`` resolves the env var per call,
    so no production code is touched.
    """
    import jobs

    monkeypatch.setenv("CASCADE_PROJECTS_DIR", str(tmp_path / "projects"))
    jobs.PROJECTS.reload()
    yield
    # Drop cache entries pointing at this test's (about-to-vanish) tmp dir.
    jobs.PROJECTS.reload()
