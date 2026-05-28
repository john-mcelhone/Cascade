"""Surge detection: cubic-spline regression on a known speedline.

Per SPEC_SHEET §13: surge is the leftmost (m_dot_corr, pi)
where dpi/dm >= -1e-3 * (pi_design / m_dot_design).

The test uses a synthetic speedline whose analytical shape we control:

    pi(m) = -10 * (m - 0.5)^2 + 3

The slope is dpi/dm = -20 * (m - 0.5).
With the slope threshold = -1e-3 * (3 / 0.6) = -5e-3 (effectively ~0),
the criterion `dpi/dm >= -5e-3` holds for m <= 0.5 approximately. So
surge_predicted ~ 0.5 to ~0.6 depending on threshold; the analytical
zero-slope point is m = 0.5, and the curve's apex is the surge boundary.

We validate that the cubic-spline regression recovers m_surge within
tolerance.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np
import pytest

from cascade.perf_map import (
    CONVERGED,
    GridPoint,
    PerformanceMap,
)


def _parabolic_compressor(
    m_apex: float = 0.5, pi_apex: float = 3.0, curvature: float = 10.0
):
    """Closure: a parabolic speedline pi(m) = -curvature * (m - m_apex)^2 + pi_apex.

    Returns an evaluator suitable for PerformanceMap.generate.
    """

    def evaluator(coords: Dict[str, float]) -> Tuple[str, Dict[str, Any]]:
        m = coords["m_dot"]
        pi = -curvature * (m - m_apex) ** 2 + pi_apex
        return CONVERGED, {"pi": pi, "eta": 0.85}

    return evaluator


class TestSurgeDetection:
    def test_parabolic_speedline_surge_at_apex(self) -> None:
        """A parabola pi = -10*(m-0.5)^2 + 3 has zero-slope apex at m=0.5.

        The threshold `dpi/dm >= -1e-3 * (pi_d/m_d)` is effectively
        zero, so the surge boundary should be at or just past the apex.
        """
        # Sample densely on m_dot in [0.3, 0.9]
        m_dot_grid = np.linspace(0.3, 0.9, 40)
        rpm_grid = np.array([1.0])

        evaluator = _parabolic_compressor(m_apex=0.5, pi_apex=3.0, curvature=10.0)
        mp = PerformanceMap.generate(
            evaluator,
            grid={"rpm": rpm_grid, "m_dot": m_dot_grid},
            parallel=1,
        )
        surge = mp.detect_surge_line(
            speed_axis="rpm",
            flow_axis="m_dot",
            pi_output="pi",
            pi_design=3.0,
            m_dot_design=0.6,
        )
        assert len(surge) == 1
        _, m_surge, pi_surge = surge[0]
        # Threshold is effectively 0, so first m where slope >= 0 is the apex.
        # The cubic spline has small noise; allow ±0.05 tolerance.
        assert abs(m_surge - 0.5) < 0.05, f"m_surge={m_surge:.4f}, expected ~0.5"
        # pi at m=0.5 should be close to 3
        assert abs(pi_surge - 3.0) < 0.1

    def test_surge_with_explicit_stall_flag(self) -> None:
        """A speedline where the evaluator flags STALL_SURGE for low m_dot.

        The detector should return the boundary just past the stall region,
        per the in-tree convention: leftmost converged point past the stall.
        """
        def evaluator(coords: Dict[str, float]) -> Tuple[str, Dict[str, Any]]:
            m = coords["m_dot"]
            if m < 0.6:
                return "STALL_SURGE", {"pi": 2.0}
            return CONVERGED, {"pi": 2.5 - 0.1 * m, "eta": 0.85}

        m_dot_grid = np.linspace(0.3, 1.5, 25)
        rpm_grid = np.array([1.0])
        mp = PerformanceMap.generate(
            evaluator,
            grid={"rpm": rpm_grid, "m_dot": m_dot_grid},
            parallel=1,
        )
        surge = mp.detect_surge_line(
            speed_axis="rpm",
            flow_axis="m_dot",
            pi_output="pi",
            pi_design=2.0,
            m_dot_design=0.6,
        )
        assert len(surge) == 1
        _, m_surge, _ = surge[0]
        # Should land at the leftmost converged point past the stall (m >= 0.6)
        assert 0.55 <= m_surge < 0.75

    def test_no_surge_when_curve_is_monotonic(self) -> None:
        """A monotonically decreasing pi(m) curve has no positive-slope region.

        With the threshold = -1e-3 * pi_d/m_d very near zero, even a steeply
        decreasing curve never reaches the criterion -- so the detector
        should return no surge for this speedline.
        """
        def evaluator(coords: Dict[str, float]) -> Tuple[str, Dict[str, Any]]:
            m = coords["m_dot"]
            return CONVERGED, {"pi": 3.0 - 1.0 * m, "eta": 0.85}

        m_dot_grid = np.linspace(0.5, 1.5, 30)
        rpm_grid = np.array([1.0])
        mp = PerformanceMap.generate(
            evaluator,
            grid={"rpm": rpm_grid, "m_dot": m_dot_grid},
            parallel=1,
        )
        surge = mp.detect_surge_line(
            speed_axis="rpm",
            flow_axis="m_dot",
            pi_output="pi",
            pi_design=2.0,
            m_dot_design=1.0,
        )
        # Steady negative slope -1.0 << threshold of -2e-3; no surge.
        assert surge == []

    def test_surge_detection_works_across_multiple_speedlines(self) -> None:
        """Two speedlines, each parabolic with different apex m_dot.

        For each, surge should land near the speedline's apex.
        """
        def evaluator(coords: Dict[str, float]) -> Tuple[str, Dict[str, Any]]:
            m = coords["m_dot"]
            rpm = coords["rpm"]
            m_apex = 0.5 if rpm < 1.0 else 0.7
            pi = -10.0 * (m - m_apex) ** 2 + 3.0
            return CONVERGED, {"pi": pi, "eta": 0.85}

        m_dot_grid = np.linspace(0.3, 1.0, 50)
        rpm_grid = np.array([0.9, 1.0])
        mp = PerformanceMap.generate(
            evaluator,
            grid={"rpm": rpm_grid, "m_dot": m_dot_grid},
            parallel=1,
        )
        surge = mp.detect_surge_line(
            speed_axis="rpm",
            flow_axis="m_dot",
            pi_output="pi",
            pi_design=3.0,
            m_dot_design=0.7,
        )
        assert len(surge) == 2
        # Sort by speed
        surge.sort()
        sp1, m1, _ = surge[0]
        sp2, m2, _ = surge[1]
        assert sp1 == pytest.approx(0.9)
        assert sp2 == pytest.approx(1.0)
        assert abs(m1 - 0.5) < 0.05
        assert abs(m2 - 0.7) < 0.05
