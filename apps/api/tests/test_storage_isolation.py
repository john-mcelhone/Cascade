"""The API test suite must never touch the user-global project store.

Mirror of ``tests/integration/test_storage_isolation.py`` for the API
suite's separate pytest rootdir: a meta-test guarding the
``CASCADE_PROJECTS_DIR`` baseline set in ``apps/api/tests/conftest.py``.
With no per-test override, the resolved store must live outside
``~/.cascade/projects``. If this fails, some import path cleared the env
var or the conftest stopped loading first — and every API test that
solves or PATCHes would be writing into the developer's real store.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make ``cascade`` importable (same dance as the other API test modules).
SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cascade.project.persistence import (  # noqa: E402
    DEFAULT_PROJECTS_DIR,
    projects_dir,
)


def test_default_store_is_not_the_user_global_dir() -> None:
    resolved = projects_dir()
    assert resolved != DEFAULT_PROJECTS_DIR, (
        "API test suite resolved the user-global project store — the "
        "CASCADE_PROJECTS_DIR isolation baseline in "
        "apps/api/tests/conftest.py is not active."
    )
    assert DEFAULT_PROJECTS_DIR not in resolved.parents
