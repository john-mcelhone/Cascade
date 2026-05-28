"""Test parallel evaluation paths in explore + perf_map.

These tests use small worker pools (2 workers) and ensure determinism +
correctness in the parallel branch, which goes through
`ProcessPoolExecutor` and pickling.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np
import pytest

from cascade.explore import (
    DesignSpaceExplorer,
    ParameterRange,
    SobolSampler,
    VALID,
)
from cascade.perf_map import CONVERGED, PerformanceMap


# Module-level evaluators (must be picklable)
def _square_eval(params: Dict[str, Any]) -> Dict[str, Any]:
    x = float(params["x"].magnitude)
    return {"objectives": {"y": x * x}, "status": VALID}


def _identity_grid_eval(coords: Dict[str, float]) -> Tuple[str, Dict[str, Any]]:
    return CONVERGED, {"y": float(coords["x"])}


class TestParallelExplorer:
    def test_parallel_matches_serial(self) -> None:
        sampler = SobolSampler(
            parameter_ranges={"x": ParameterRange(-2.0, 2.0, "dimensionless")},
            n_samples=64,
            seed=0,
        )
        explorer = DesignSpaceExplorer()
        serial = explorer.run(_square_eval, sampler, parallel=1)
        parallel = explorer.run(_square_eval, sampler, parallel=2)
        assert len(serial) == len(parallel)
        # Order is preserved through both code paths
        for cs, cp in zip(serial, parallel):
            assert cs.objective_value("y") == pytest.approx(cp.objective_value("y"))


class TestParallelPerfMap:
    def test_parallel_perf_map(self) -> None:
        grid = {"x": np.linspace(0.0, 10.0, 16)}
        mp_serial = PerformanceMap.generate(_identity_grid_eval, grid=grid, parallel=1)
        mp_parallel = PerformanceMap.generate(_identity_grid_eval, grid=grid, parallel=2)
        assert len(mp_parallel.points) == 16
        # Both should produce all-converged points
        assert all(p.status == CONVERGED for p in mp_parallel.points)
        # Same y values (mp_serial is sorted, parallel may be unordered;
        # to_array reshapes by coord lookup, so should match)
        a_serial = mp_serial.to_array("y")
        a_parallel = mp_parallel.to_array("y")
        np.testing.assert_array_equal(a_serial, a_parallel)
