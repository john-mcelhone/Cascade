"""Suite-wide isolation from the user-global project store.

Production resolves the project store to ``~/.cascade/projects`` via
``cascade.project.persistence.projects_dir()``, which reads
``CASCADE_PROJECTS_DIR`` per call. Without an override, any test that
exercises the API job/store path writes seed and result files into the
developer's real store — every run polluted ``~/.cascade/projects`` with
duplicate project files.

The override is set at conftest import (before collection imports any
test module) so even module-level app construction binds the temp dir.
Tests that need their own store still win: a function-scoped
``monkeypatch.setenv`` overrides this baseline for that test only.

An explicitly exported ``CASCADE_PROJECTS_DIR`` is respected so a
developer can intentionally point the suite at a fixture store.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault(
    "CASCADE_PROJECTS_DIR",
    tempfile.mkdtemp(prefix="cascade-tests-"),
)
