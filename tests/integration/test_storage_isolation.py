"""The test suite must never touch the user-global project store.

Regression guard for the conftest-level ``CASCADE_PROJECTS_DIR``
baseline: with no per-test override, the resolved store must live
outside ``~/.cascade/projects``. If this fails, some import path
cleared the env var or the conftest stopped loading first.
"""

from __future__ import annotations

import pytest

from cascade.project.persistence import DEFAULT_PROJECTS_DIR, projects_dir


@pytest.mark.integration
def test_default_store_is_not_the_user_global_dir() -> None:
    resolved = projects_dir()
    assert resolved != DEFAULT_PROJECTS_DIR, (
        "Test suite resolved the user-global project store — the "
        "CASCADE_PROJECTS_DIR isolation baseline in tests/conftest.py "
        "is not active."
    )
    assert DEFAULT_PROJECTS_DIR not in resolved.parents
