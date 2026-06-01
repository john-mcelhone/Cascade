"""Pytest configuration for the INDEPENDENT verification suite.

This suite is intentionally separate from the in-repo `tests/` directory. The
assertions here are derived from first-principles physics, published closed-form
results, conservation laws, and textbook property bounds — NOT from the Cascade
implementation. See README.md for the methodology and the firewall rationale.

This conftest does two things:

1. Makes `import cascade` work regardless of how pytest is launched, by putting
   the repository `src/` on `sys.path`.
2. Records per-test outcomes to `.last_results.json` so `run_report.py` can
   produce a deliberately COARSE report (subsystem counts + generic themes,
   never exact values, test names, or assertion diffs). The detailed JSON is
   git-ignored and is never shown to whoever is fixing the code — that is the
   anti-overfitting firewall.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_OUTCOMES: dict[str, str] = {}


def pytest_runtest_logreport(report) -> None:  # noqa: ANN001
    """Capture the most meaningful outcome per test node."""
    nid = report.nodeid
    if report.when == "call":
        # passed / failed / skipped during the test body
        _OUTCOMES[nid] = report.outcome
    elif report.when == "setup":
        if report.outcome == "skipped":
            _OUTCOMES.setdefault(nid, "skipped")
        elif report.outcome == "failed":
            # An exception during setup means the test could not run at all.
            _OUTCOMES[nid] = "error"


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ANN001, ARG001
    out = Path(__file__).resolve().parent / ".last_results.json"
    try:
        out.write_text(json.dumps(_OUTCOMES, indent=2))
    except OSError:
        pass
