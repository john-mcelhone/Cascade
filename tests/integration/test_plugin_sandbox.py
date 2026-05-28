"""Integration tests for W-21: Python loss-model plugin subprocess isolation.

Covers:
  AC1 — A plugin with ``time.sleep(60)`` is killed after the timeout and
        returns a structured error (not a hung test process).
  AC2 — A plugin that raises in module scope does NOT crash the parent
        Python process; the error is returned cleanly.
  AC3 — A correctly-implemented plugin produces the correct numeric output
        through the subprocess channel.
  AC4 (partial) — The execution time of a well-behaved plugin is measured
        and logged; the test is informational rather than a hard gate
        because subprocess overhead varies across CI environments.
  AC5 — This file itself is the AC5 deliverable.

These tests exercise ``cascade.plugins.sandbox.run_plugin_in_subprocess``
directly, plus the new
``POST /api/projects/{id}/loss-models/{name}/execute`` endpoint.
"""

from __future__ import annotations

import os
import sys
import tempfile
import textwrap
import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path wiring (mirrors apps/api tests structure)
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
_SRC = _REPO_ROOT / "src"
for _p in (str(_REPO_ROOT / "apps" / "api"), str(_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Isolate plugin store
_TEST_STORE = Path(tempfile.mkdtemp(prefix="cascade-sandbox-tests-"))
os.environ["CASCADE_PLUGIN_STORE_DIR"] = str(_TEST_STORE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_plugin(tmpdir: Path, filename: str, source: str) -> Path:
    """Write plugin source to a temp file and return the path."""
    p = tmpdir / filename
    p.write_text(textwrap.dedent(source), encoding="utf-8")
    return p


_SYNTHETIC_CONTEXT: dict = {
    "r_tip": 0.040,
    "r_hub": 0.015,
    "blade_count": 12,
    "exit_blade_angle_rad": 1.0472,
    "U_2": 350.0,
    "W_2": 180.0,
    "V_2": 220.0,
    "M_relative_max": 0.85,
    "T_1": 288.15,
    "p_1": 101325.0,
    "T_2": 455.0,
    "p_2": 325000.0,
    "rho_2": 2.49,
    "mass_flow": 0.30,
    "rotational_speed_rad_per_s": 8377.0,
    "Re_inlet": 1.5e6,
    "Mach_meridional": 0.45,
    "fluid_name": "air",
}


# ---------------------------------------------------------------------------
# Unit-level sandbox tests (no HTTP server required)
# ---------------------------------------------------------------------------

class TestSubprocessSandbox:
    """Direct tests for ``run_plugin_in_subprocess``."""

    def setup_method(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="cascade-sandbox-unit-"))

    def teardown_method(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ---- AC3: correct output -----------------------------------------------

    def test_correct_plugin_returns_expected_zeta(self) -> None:
        """A well-formed plugin returns the right numeric value via subprocess."""
        from cascade.plugins.sandbox import run_plugin_in_subprocess

        plugin_path = _write_plugin(
            self.tmpdir,
            "good_plugin.py",
            """
            from cascade.plugins import LossModel, LossContext

            class GoodPlugin(LossModel):
                name = "GoodPlugin"
                applicable_machine_classes = ["radial_turbine"]

                def loss_coefficient(self, ctx: LossContext) -> float:
                    # Deterministic: returns a function of a known input.
                    return 0.05 + 0.01 * ctx.M_relative_max
            """,
        )

        result = run_plugin_in_subprocess(plugin_path, _SYNTHETIC_CONTEXT)

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert "zeta" in result
        expected = 0.05 + 0.01 * _SYNTHETIC_CONTEXT["M_relative_max"]
        assert abs(result["zeta"] - expected) < 1e-9, (
            f"Expected {expected}, got {result['zeta']}"
        )

    # ---- AC1: timeout kills the plugin -------------------------------------

    def test_sleeping_plugin_is_killed_after_timeout(self) -> None:
        """A plugin that sleeps forever is killed within the timeout window."""
        from cascade.plugins.sandbox import run_plugin_in_subprocess

        plugin_path = _write_plugin(
            self.tmpdir,
            "sleep_plugin.py",
            """
            from cascade.plugins import LossModel, LossContext

            class SleepPlugin(LossModel):
                name = "SleepPlugin"
                applicable_machine_classes = ["radial_turbine"]

                def loss_coefficient(self, ctx: LossContext) -> float:
                    import time
                    time.sleep(60)  # longer than any sane timeout
                    return 0.0
            """,
        )

        timeout_s = 3.0  # 3-second budget for the test
        t0 = time.monotonic()
        result = run_plugin_in_subprocess(
            plugin_path, _SYNTHETIC_CONTEXT, timeout=timeout_s
        )
        elapsed = time.monotonic() - t0

        # The call must return with an error — not hang.
        assert "error" in result, (
            f"Expected timeout error, got result: {result}"
        )
        assert "timed out" in result["error"].lower(), (
            f"Error message should mention timeout: {result['error']}"
        )
        # The wall-clock time must be close to the timeout (within 5 s of slack).
        assert elapsed < timeout_s + 5.0, (
            f"Timeout took too long: {elapsed:.1f} s"
        )

    # ---- AC2: import-time crash does not kill the parent -------------------

    def test_module_scope_crash_does_not_kill_parent(self) -> None:
        """A plugin that raises at import time returns an error, not a crash."""
        from cascade.plugins.sandbox import run_plugin_in_subprocess

        plugin_path = _write_plugin(
            self.tmpdir,
            "crash_import.py",
            """
            from cascade.plugins import LossModel, LossContext

            # Crash at module-scope BEFORE the class is even defined.
            raise RuntimeError("Simulated malicious import-time crash")

            class NeverDefined(LossModel):
                name = "NeverDefined"
                applicable_machine_classes = ["radial_turbine"]
                def loss_coefficient(self, ctx: LossContext) -> float:
                    return 0.0
            """,
        )

        result = run_plugin_in_subprocess(plugin_path, _SYNTHETIC_CONTEXT)

        # The call returns an error dict — the parent process is still alive.
        assert "error" in result, (
            f"Expected an error response, got: {result}"
        )
        # The parent process is demonstrably alive (the assertion is this
        # test continuing to execute; no explicit check needed).

    def test_compute_time_plugin_within_200ms(self) -> None:
        """AC4: Measure per-call latency of a trivial well-formed plugin.

        This is informational — not a hard fail gate — because subprocess
        fork cost varies significantly on CI vs. developer machines.  The
        test logs the measurement and issues a warning if above 200 ms.
        """
        from cascade.plugins.sandbox import run_plugin_in_subprocess

        plugin_path = _write_plugin(
            self.tmpdir,
            "fast_plugin.py",
            """
            from cascade.plugins import LossModel, LossContext

            class FastPlugin(LossModel):
                name = "FastPlugin"
                applicable_machine_classes = ["radial_turbine"]

                def loss_coefficient(self, ctx: LossContext) -> float:
                    return 0.07
            """,
        )

        t0 = time.monotonic()
        result = run_plugin_in_subprocess(plugin_path, _SYNTHETIC_CONTEXT)
        elapsed_ms = (time.monotonic() - t0) * 1000

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert result["zeta"] == pytest.approx(0.07)

        # Log the measurement.
        print(f"\n[AC4] Subprocess overhead: {elapsed_ms:.1f} ms")
        if elapsed_ms > 200:
            import warnings
            warnings.warn(
                f"Plugin subprocess overhead is {elapsed_ms:.0f} ms "
                "(> 200 ms AC4 budget). Consider a persistent worker pool "
                "for high-throughput use.",
                RuntimeWarning,
                stacklevel=2,
            )

    def test_missing_plugin_file_returns_error(self) -> None:
        """Graceful error when the plugin file does not exist."""
        from cascade.plugins.sandbox import run_plugin_in_subprocess

        result = run_plugin_in_subprocess(
            self.tmpdir / "nonexistent.py", _SYNTHETIC_CONTEXT
        )
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_plugin_returning_invalid_type_returns_error(self) -> None:
        """A plugin returning a string is caught in the child and reported."""
        from cascade.plugins.sandbox import run_plugin_in_subprocess

        plugin_path = _write_plugin(
            self.tmpdir,
            "bad_return.py",
            """
            from cascade.plugins import LossModel, LossContext

            class BadReturn(LossModel):
                name = "BadReturnSandbox"
                applicable_machine_classes = ["radial_turbine"]

                def loss_coefficient(self, ctx: LossContext) -> float:
                    return "not a float"  # type: ignore[return-value]
            """,
        )

        # The registry validation will catch this before the subprocess is
        # even called — but the sandbox itself also guards against it.
        # We bypass validation by calling the runner directly.
        result = run_plugin_in_subprocess(plugin_path, _SYNTHETIC_CONTEXT)
        assert "error" in result


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------

class TestPluginExecuteEndpoint:
    """Tests for ``POST /api/projects/{id}/loss-models/{name}/execute``."""

    @pytest.fixture(autouse=True)
    def setup_app(self, tmp_path):
        import jobs

        # Point the plugin store at a per-test temp dir.
        os.environ["CASCADE_PLUGIN_STORE_DIR"] = str(tmp_path / "plugin_store")
        jobs.reset_for_tests()
        from cascade.plugins import PLUGIN_REGISTRY
        PLUGIN_REGISTRY.clear_user()
        from main import create_app
        import httpx

        transport = httpx.ASGITransport(app=create_app())
        import asyncio

        self.client_ctx = httpx.AsyncClient(
            transport=transport, base_url="http://test"
        )

    @pytest.mark.asyncio
    async def test_execute_builtin_model_returns_zeta(self) -> None:
        """Built-in models execute directly (no subprocess) and return zeta."""
        async with self.client_ctx as client:
            resp = await client.post(
                "/api/projects/microturbine-30kw/loss-models/AungierCentrifugal/execute",
                json={"context": _SYNTHETIC_CONTEXT},
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is True
        assert body["error"] is None
        assert isinstance(body["zeta"], float)
        assert body["zeta"] >= 0.0

    @pytest.mark.asyncio
    async def test_execute_unknown_model_returns_404(self) -> None:
        """Requesting execution of a non-existent model returns 404."""
        async with self.client_ctx as client:
            resp = await client.post(
                "/api/projects/microturbine-30kw/loss-models/NoSuchModel/execute",
                json={"context": _SYNTHETIC_CONTEXT},
            )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_then_execute_user_plugin(self, tmp_path) -> None:
        """Upload a user plugin, then execute it in the subprocess sandbox."""
        import httpx

        body = textwrap.dedent(
            """
            from cascade.plugins import LossModel, LossContext

            class MyE2ESandboxPlugin(LossModel):
                name = "MyE2ESandboxPlugin"
                applicable_machine_classes = ["radial_turbine"]

                def loss_coefficient(self, ctx: LossContext) -> float:
                    # Deterministic for easy assertion.
                    return 0.042 + 0.001 * ctx.blade_count
            """
        ).encode("utf-8")

        os.environ["CASCADE_PLUGIN_STORE_DIR"] = str(tmp_path / "plugin_store")
        import jobs

        jobs.reset_for_tests()
        from cascade.plugins import PLUGIN_REGISTRY
        PLUGIN_REGISTRY.clear_user()
        from main import create_app

        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            # 1. Upload the plugin.
            up = await client.post(
                "/api/projects/microturbine-30kw/loss-models/upload",
                files={"file": ("e2e_sandbox.py", body, "text/x-python")},
            )
            assert up.status_code == 201, up.text

            # 2. Execute it via the sandbox endpoint.
            exec_resp = await client.post(
                "/api/projects/microturbine-30kw/loss-models/"
                "MyE2ESandboxPlugin/execute",
                json={"context": _SYNTHETIC_CONTEXT},
            )
            assert exec_resp.status_code == 200, exec_resp.text
            result = exec_resp.json()
            assert result["success"] is True, result
            expected = 0.042 + 0.001 * _SYNTHETIC_CONTEXT["blade_count"]
            assert abs(result["zeta"] - expected) < 1e-9, (
                f"Expected {expected}, got {result['zeta']}"
            )
