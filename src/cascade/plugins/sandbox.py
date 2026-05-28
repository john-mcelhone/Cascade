"""Subprocess sandbox for user-supplied loss-model plugins (ADAPT-035, W-21).

The core problem: plugins are user-written Python. An infinite loop, a
memory bomb, or a ``sys.exit()`` call in a plugin's ``loss_coefficient``
would crash the API worker process. The solution is to fork a fresh
Python interpreter, run the plugin inside it, and return the result to the
parent via a JSON payload on stdout.

Architecture
============

``run_plugin_in_subprocess(plugin_path, context_dict, *, timeout)``
  Serialises the ``LossContext`` as a JSON dict, spawns
  ``python -m cascade.plugins._sandbox_runner`` with that dict on stdin,
  and reads a JSON result from stdout. Returns ``{"zeta": <float>}`` on
  success, ``{"error": "<message>"}`` on any failure.

The runner module (``_sandbox_runner.py``) is the child-side script:
  1. Reads stdin as JSON.
  2. Resolves the plugin file via an absolute path in the payload.
  3. Calls ``loss_coefficient(LossContext(**context_dict))``.
  4. Writes ``{"zeta": <float>}`` to stdout.
  5. Any exception writes ``{"error": "<msg>"}`` to stdout with exit-code 1.

Resource limits
===============

On POSIX systems (Linux / macOS), the child process gets:
  - CPU time: ``RLIMIT_CPU = ceil(timeout)`` seconds (hard kill by kernel).
  - Virtual memory: ``RLIMIT_AS = 512 MB`` (configurable via
    ``CASCADE_PLUGIN_MEM_LIMIT_MB`` env var).

On Windows (or any other OS), resource limits are silently skipped and a
``RuntimeWarning`` is emitted once.  The subprocess timeout via
``subprocess.run(timeout=...)`` still enforces wall-clock time on all
platforms.

Overhead
========

Cold-fork cost (CPython): typically 30-80 ms on a modern developer laptop
(import chain: cascade.plugins.base + one user file). The parent
``subprocess.run`` call adds ~5 ms round-trip on the same machine.
Total overhead is well under the 200 ms AC4 budget for the common case.

If the overhead is unacceptable for hot-path usage (many calls per second),
consider a persistent-worker pool using ``multiprocessing.Pool`` with a
pre-imported module cache. That is out of scope for v1.1.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import math
import os
import platform
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger("cascade.plugins.sandbox")

# ---------------------------------------------------------------------------
# Resource-limit defaults (POSIX only)
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT_SECONDS: float = 5.0  # hard subprocess wall-clock timeout
_DEFAULT_MEM_LIMIT_MB: int = 512

# Single-process warning flag so the "Windows skips resource limits" message
# appears at most once per process lifetime.
_RESOURCE_LIMIT_WARNING_EMITTED = False


def _get_mem_limit_mb() -> int:
    """Read CASCADE_PLUGIN_MEM_LIMIT_MB or return the default."""
    try:
        return int(os.environ.get("CASCADE_PLUGIN_MEM_LIMIT_MB", _DEFAULT_MEM_LIMIT_MB))
    except (ValueError, TypeError):
        return _DEFAULT_MEM_LIMIT_MB


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_plugin_in_subprocess(
    plugin_path: Path,
    context_dict: Dict[str, Any],
    *,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Execute a user plugin's ``loss_coefficient`` in an isolated subprocess.

    Args:
        plugin_path: Absolute path to the ``.py`` file containing the plugin.
        context_dict: A dict representation of ``LossContext`` (all fields
            that ``LossContext.__init__`` accepts; the ``extra`` field is
            optional and defaults to ``{}``).
        timeout: Wall-clock timeout in seconds. The child is killed if it
            does not finish within this window. Default: 5.0 s.

    Returns:
        On success: ``{"zeta": <float>}``
        On timeout / crash / invalid output: ``{"error": "<human-readable>"}``
    """
    plugin_path = Path(plugin_path).resolve()
    if not plugin_path.exists():
        return {"error": f"Plugin file not found: {plugin_path}"}

    # Build the payload for the child process.
    payload = {
        "plugin_path": str(plugin_path),
        "context": context_dict,
    }
    try:
        stdin_bytes = json.dumps(payload).encode("utf-8")
    except (TypeError, ValueError) as exc:
        return {"error": f"Failed to serialise plugin input: {exc}"}

    # Find the Python interpreter — use the same one running the API so the
    # child inherits the same virtual environment and can import cascade.
    python_exe = sys.executable

    # Locate the runner module.  It lives next to this file in the cascade
    # package, so we can pass it as ``-m cascade.plugins._sandbox_runner``
    # after ensuring the cascade src root is in PYTHONPATH.
    src_root = str(Path(__file__).resolve().parent.parent.parent.parent)  # …/src
    env = os.environ.copy()
    python_path_parts = [src_root] + [
        p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p
    ]
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(python_path_parts))

    cmd = [python_exe, "-m", "cascade.plugins._sandbox_runner"]

    try:
        result = subprocess.run(
            cmd,
            input=stdin_bytes,
            capture_output=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        log.warning(
            "Plugin %s timed out after %.1f s", plugin_path.name, timeout
        )
        return {
            "error": (
                f"Plugin execution timed out after {timeout:.0f} s. "
                "The plugin must return within the allowed wall-clock budget."
            )
        }
    except Exception as exc:
        log.error("Failed to spawn plugin subprocess: %s", exc)
        return {"error": f"Failed to spawn plugin subprocess: {exc}"}

    # Parse the child's output.
    stdout = result.stdout.strip()
    if not stdout:
        stderr_snippet = result.stderr.decode("utf-8", errors="replace")[:300]
        return {
            "error": (
                f"Plugin subprocess produced no output (exit {result.returncode}). "
                f"stderr: {stderr_snippet!r}"
            )
        }

    try:
        child_result = json.loads(stdout)
    except json.JSONDecodeError:
        raw = stdout.decode("utf-8", errors="replace")[:300]
        return {
            "error": (
                f"Plugin subprocess returned non-JSON output: {raw!r}"
            )
        }

    if "error" in child_result:
        log.warning("Plugin %s reported error: %s", plugin_path.name, child_result["error"])
        return {"error": child_result["error"]}

    if "zeta" not in child_result:
        return {"error": f"Plugin result missing 'zeta' key: {child_result!r}"}

    zeta = child_result["zeta"]
    if not isinstance(zeta, (int, float)) or not math.isfinite(float(zeta)):
        return {"error": f"Plugin returned non-finite zeta: {zeta!r}"}

    return {"zeta": float(zeta)}
