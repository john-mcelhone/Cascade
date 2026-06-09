"""Isolate API tests from the user-global project store.

Mirrors ``tests/conftest.py`` (the API tests run as a separate pytest
invocation with their own rootdir, so the root conftest does not load
here). The override binds before collection imports any test module;
see ``cascade.project.persistence.projects_dir()`` for the env-var
contract. Per-test ``monkeypatch.setenv`` still overrides the baseline.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault(
    "CASCADE_PROJECTS_DIR",
    tempfile.mkdtemp(prefix="cascade-api-tests-"),
)
