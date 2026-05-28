"""Tests for `cascade.perf_map.PerformanceMap.generate` end-to-end.

Per SPEC_SHEET §13 (replaces ambiguous `-1` return code
with explicit per-point codes).
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, Tuple

import numpy as np
import pytest

from cascade.perf_map import (
    ALL_CODES,
    CHOKED,
    CONVERGED,
    GridPoint,
    INFEASIBLE_BC,
    INVALID_GEOMETRY,
    NON_CONVERGED,
    PerformanceMap,
    REGIME_OUT_OF_VALIDITY,
    STALL_SURGE,
    TIMEOUT,
)
from cascade.units import Q


def _synthetic_compressor_evaluator(coords: Dict[str, float]) -> Tuple[str, Dict[str, Any]]:
    """Returns explicit codes across the m_dot domain to exercise each branch.

    The grid axis `m_dot` is in kg/s; `rpm` is the speed group.

    Code map:
    - m_dot < 0.3   -> CHOKED  (right boundary of low-flow region: choke
                                 here is a fake low-flow extreme to keep
                                 the synthetic simple)
    - 0.3 <= m_dot <= 1.8 -> CONVERGED with pi = 2 + 0.5*m_dot - 0.6*m_dot^2 + (rpm-1.0)*0.5
                              and eta = 0.85 - 0.1*(m_dot-1.0)^2
    - 1.8 < m_dot <= 2.0 -> STALL_SURGE  (positive-slope region of map's left)
    - m_dot > 2.0   -> INVALID_GEOMETRY (forced; non-physical)
    """
    m_dot = coords["m_dot"]
    rpm = coords["rpm"]

    if m_dot < 0.3:
        return CHOKED, {"pi": 1.0, "eta": 0.5}
    if m_dot > 2.0:
        return INVALID_GEOMETRY, {}
    if m_dot > 1.8:
        return STALL_SURGE, {"pi": 2.5 - 0.3 * m_dot, "eta": 0.6}
    pi = 2.0 + 0.5 * m_dot - 0.6 * m_dot * m_dot + (rpm - 1.0) * 0.5
    eta = 0.85 - 0.1 * (m_dot - 1.0) ** 2
    return CONVERGED, {"pi": pi, "eta": eta}


def _evaluator_with_all_codes(coords: Dict[str, float]) -> Tuple[str, Dict[str, Any]]:
    """Exercise every single one of the 8 status codes."""
    x = coords["x"]
    # 0 → CONVERGED, 1 → CHOKED, 2 → STALL_SURGE, 3 → NON_CONVERGED,
    # 4 → INVALID_GEOMETRY, 5 → REGIME_OUT_OF_VALIDITY, 6 → TIMEOUT, 7 → INFEASIBLE_BC
    code_map = {
        0.0: (CONVERGED, {"y": 1.0}),
        1.0: (CHOKED, {"y": 2.0}),
        2.0: (STALL_SURGE, {"y": 3.0}),
        3.0: (NON_CONVERGED, {"y": float("nan")}),
        4.0: (INVALID_GEOMETRY, {}),
        5.0: (REGIME_OUT_OF_VALIDITY, {"y": 99.0}),
        6.0: (TIMEOUT, {}),
        7.0: (INFEASIBLE_BC, {}),
    }
    return code_map[float(x)]


class TestStatusCodes:
    def test_all_eight_codes_in_alphabet(self) -> None:
        assert ALL_CODES == frozenset(
            {
                CONVERGED,
                CHOKED,
                STALL_SURGE,
                NON_CONVERGED,
                INVALID_GEOMETRY,
                REGIME_OUT_OF_VALIDITY,
                TIMEOUT,
                INFEASIBLE_BC,
            }
        )

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(ValueError):
            GridPoint(coords={"m_dot": 1.0}, status="MYSTERY_CODE")

    def test_map_assigns_all_eight_codes_correctly(self) -> None:
        grid = {"x": np.arange(8, dtype=float)}
        mp = PerformanceMap.generate(_evaluator_with_all_codes, grid=grid, parallel=1)
        # Check that each point's status matches the input map
        expected = [
            CONVERGED,
            CHOKED,
            STALL_SURGE,
            NON_CONVERGED,
            INVALID_GEOMETRY,
            REGIME_OUT_OF_VALIDITY,
            TIMEOUT,
            INFEASIBLE_BC,
        ]
        # Sort by x coordinate to be safe
        points_by_x = sorted(mp.points, key=lambda p: p.coords["x"])
        actual = [p.status for p in points_by_x]
        assert actual == expected


class TestSyntheticCompressor:
    def test_grid_structure(self) -> None:
        m_dot_grid = np.linspace(0.2, 2.1, 20)
        rpm_grid = np.array([0.9, 1.0, 1.1])
        mp = PerformanceMap.generate(
            _synthetic_compressor_evaluator,
            grid={"rpm": rpm_grid, "m_dot": m_dot_grid},
            parallel=1,
        )
        assert len(mp.points) == 20 * 3
        # The status array should be shaped (3, 20)
        status_grid = mp.status_array()
        assert status_grid.shape == (3, 20)

    def test_codes_assigned_correctly_for_synthetic_map(self) -> None:
        # Use coarse grid so we hit each region cleanly
        m_dot_grid = np.linspace(0.1, 2.1, 21)
        rpm_grid = np.array([1.0])
        mp = PerformanceMap.generate(
            _synthetic_compressor_evaluator,
            grid={"rpm": rpm_grid, "m_dot": m_dot_grid},
            parallel=1,
        )
        # Pull the (1 speedline) speedline
        speedlines = mp.speedlines(group_by="rpm", flow_axis="m_dot")
        assert len(speedlines) == 1
        _, pts = speedlines[0]

        # Low-flow points should be CHOKED
        for p in pts:
            if p.coords["m_dot"] < 0.3:
                assert p.status == CHOKED, f"expected CHOKED at m_dot={p.coords['m_dot']}"

        # Mid-range CONVERGED, with realistic pi/eta
        mid = [p for p in pts if 0.3 <= p.coords["m_dot"] <= 1.8]
        assert all(p.status == CONVERGED for p in mid)
        for p in mid:
            assert isinstance(p.outputs["pi"], float)
            assert 0.0 < p.outputs["pi"] < 5.0
            assert 0.0 < p.outputs["eta"] < 1.0

        # High-flow STALL_SURGE region
        surge = [p for p in pts if 1.8 < p.coords["m_dot"] <= 2.0]
        assert all(p.status == STALL_SURGE for p in surge), [
            (p.coords["m_dot"], p.status) for p in surge
        ]

        # Far high-flow region INVALID_GEOMETRY
        inv = [p for p in pts if p.coords["m_dot"] > 2.0]
        assert all(p.status == INVALID_GEOMETRY for p in inv)

    def test_to_array_correct_shape(self) -> None:
        m_dot_grid = np.linspace(0.5, 1.5, 5)
        rpm_grid = np.array([0.9, 1.0])
        mp = PerformanceMap.generate(
            _synthetic_compressor_evaluator,
            grid={"rpm": rpm_grid, "m_dot": m_dot_grid},
            parallel=1,
        )
        pi_array = mp.to_array("pi")
        assert pi_array.shape == (2, 5)
        # All values finite in the converged region
        assert np.all(np.isfinite(pi_array))

    def test_surge_detection_finds_boundary(self) -> None:
        # Use a fine grid so the cubic spline can find the surge boundary.
        m_dot_grid = np.linspace(0.3, 2.05, 40)
        rpm_grid = np.array([1.0])
        mp = PerformanceMap.generate(
            _synthetic_compressor_evaluator,
            grid={"rpm": rpm_grid, "m_dot": m_dot_grid},
            parallel=1,
        )
        # In the synthetic compressor, the explicit STALL_SURGE flag kicks
        # in at m_dot > 1.8. So the detector should land at the leftmost
        # converged point beyond 1.8 (i.e. just past 1.8).
        surge = mp.detect_surge_line(
            speed_axis="rpm",
            flow_axis="m_dot",
            pi_output="pi",
            pi_design=2.0,
            m_dot_design=1.0,
        )
        assert len(surge) == 1
        speed, m_surge, pi_surge = surge[0]
        # m_surge should be near 1.8 (just into the stall region or just past it)
        assert 1.6 < m_surge < 2.0, f"surge m_dot={m_surge}, expected near 1.8"

    def test_choke_detection_finds_boundary(self) -> None:
        m_dot_grid = np.linspace(0.05, 2.0, 30)
        rpm_grid = np.array([1.0])
        mp = PerformanceMap.generate(
            _synthetic_compressor_evaluator,
            grid={"rpm": rpm_grid, "m_dot": m_dot_grid},
            parallel=1,
        )
        choke = mp.detect_choke_line(
            speed_axis="rpm", flow_axis="m_dot", pi_output="pi"
        )
        assert len(choke) == 1
        speed, m_choke, _ = choke[0]
        # CHOKED region is m_dot < 0.3; rightmost CHOKED should be just below 0.3
        assert m_choke < 0.3
        assert m_choke > 0.05  # not at the very left


class TestExports:
    def test_csv_export(self, tmp_path: Any) -> None:
        m_dot_grid = np.array([0.5, 1.0, 1.5])
        rpm_grid = np.array([1.0])
        mp = PerformanceMap.generate(
            _synthetic_compressor_evaluator,
            grid={"rpm": rpm_grid, "m_dot": m_dot_grid},
            parallel=1,
        )
        csv_path = tmp_path / "map.csv"
        mp.to_csv(str(csv_path))
        text = csv_path.read_text()
        # Header has axis names + status + output names
        assert "rpm" in text
        assert "m_dot" in text
        assert "status" in text
        # Three rows worth of data
        rows = [r for r in text.strip().split("\n") if r]
        assert len(rows) == 1 + 3  # header + 3 data

    def test_json_export(self, tmp_path: Any) -> None:
        m_dot_grid = np.array([0.5, 1.0])
        rpm_grid = np.array([1.0])
        mp = PerformanceMap.generate(
            _synthetic_compressor_evaluator,
            grid={"rpm": rpm_grid, "m_dot": m_dot_grid},
            parallel=1,
        )
        json_path = tmp_path / "map.json"
        mp.to_json(str(json_path))
        import json

        doc = json.loads(json_path.read_text())
        assert "axes" in doc
        assert "points" in doc
        assert len(doc["points"]) == 2

    def test_hdf5_export_skipped_when_unavailable(self, tmp_path: Any) -> None:
        # h5py is optional; if not installed we should fail with a clear error.
        try:
            import h5py  # noqa: F401
            available = True
        except ImportError:
            available = False
        if not available:
            mp = PerformanceMap.generate(
                _synthetic_compressor_evaluator,
                grid={"rpm": np.array([1.0]), "m_dot": np.array([1.0])},
                parallel=1,
            )
            with pytest.raises(ImportError, match="h5py"):
                mp.to_hdf5(str(tmp_path / "x.h5"))
