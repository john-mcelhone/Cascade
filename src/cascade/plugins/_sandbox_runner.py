"""Child-side sandbox runner for loss-model plugins (W-21).

This module is invoked as ``python -m cascade.plugins._sandbox_runner``
by the parent API process.  It must NOT be imported directly by any other
module — it is an executable entry-point only.

Protocol
--------
stdin  → UTF-8 JSON: {"plugin_path": "<abs path>", "context": {<LossContext fields>}}
stdout → UTF-8 JSON: {"zeta": <float>}          (success)
                  OR {"error": "<message>"}      (any failure)
exit 0 on success, exit 1 on any failure.

Resource limits (POSIX only)
-----------------------------
The parent sets resource limits before spawning this process via the
``preexec_fn`` mechanism.  This module *also* attempts to apply limits so
it works when invoked standalone for testing.  Either path is fine.

On Windows the resource-limit block is silently skipped.
"""

from __future__ import annotations

import json
import math
import os
import platform
import sys


def _apply_resource_limits(timeout_seconds: float = 5.0, mem_mb: int = 512) -> None:
    """Apply POSIX resource limits to the current (child) process.

    On non-POSIX platforms (Windows) this is a no-op.
    """
    if platform.system() == "Windows":
        return

    try:
        import resource

        # CPU time: hard limit at ceil(timeout) seconds.
        cpu_hard = math.ceil(timeout_seconds)
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_hard, cpu_hard))

        # Virtual address space: prevent memory bombs.
        mem_bytes = mem_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    except (ImportError, ValueError, resource.error):
        # Best-effort; if it fails, the parent's timeout is the backstop.
        pass


def _main() -> None:
    # Apply resource limits first — before we even try to import the plugin.
    timeout_s = float(os.environ.get("CASCADE_PLUGIN_TIMEOUT_S", "5"))
    mem_mb = int(os.environ.get("CASCADE_PLUGIN_MEM_LIMIT_MB", "512"))
    _apply_resource_limits(timeout_s, mem_mb)

    # Read and parse stdin.
    try:
        raw = sys.stdin.buffer.read()
        payload = json.loads(raw)
    except Exception as exc:
        sys.stdout.write(json.dumps({"error": f"Failed to parse input: {exc}"}))
        sys.stdout.flush()
        sys.exit(1)

    plugin_path_str = payload.get("plugin_path", "")
    context_dict = payload.get("context", {})

    if not plugin_path_str:
        sys.stdout.write(json.dumps({"error": "payload missing 'plugin_path'"}))
        sys.stdout.flush()
        sys.exit(1)

    # Load the plugin file.
    from pathlib import Path

    plugin_path = Path(plugin_path_str)
    try:
        # Use the loader from cascade.plugins.loader — it already handles
        # content-hash module naming, SyntaxError formatting, etc.
        from cascade.plugins.loader import load_plugin_from_file

        cls = load_plugin_from_file(plugin_path)
    except Exception as exc:
        sys.stdout.write(json.dumps({"error": f"Failed to load plugin: {exc}"}))
        sys.stdout.flush()
        sys.exit(1)

    # Reconstruct the LossContext.
    try:
        from cascade.plugins.base import LossContext

        ctx = LossContext(**context_dict)
    except Exception as exc:
        sys.stdout.write(json.dumps({"error": f"Failed to build LossContext: {exc}"}))
        sys.stdout.flush()
        sys.exit(1)

    # Instantiate and call.
    try:
        instance = cls()
        zeta = instance.loss_coefficient(ctx)
    except Exception as exc:
        sys.stdout.write(
            json.dumps({"error": f"{cls.__name__}.loss_coefficient raised: {exc}"})
        )
        sys.stdout.flush()
        sys.exit(1)

    # Validate the return value.
    if not isinstance(zeta, (int, float)) or isinstance(zeta, bool):
        sys.stdout.write(
            json.dumps(
                {
                    "error": (
                        f"{cls.__name__}.loss_coefficient must return a float, "
                        f"got {type(zeta).__name__}"
                    )
                }
            )
        )
        sys.stdout.flush()
        sys.exit(1)

    zeta_f = float(zeta)
    if not math.isfinite(zeta_f):
        sys.stdout.write(
            json.dumps({"error": f"loss_coefficient returned non-finite value: {zeta!r}"})
        )
        sys.stdout.flush()
        sys.exit(1)

    # Success.
    sys.stdout.write(json.dumps({"zeta": zeta_f}))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    _main()
