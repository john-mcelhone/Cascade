"""Tests for `cascade.explore.design_space.DesignSpace` and `DesignSpaceExplorer`.

Per SPEC_SHEET §11. Verifies:
- Round-trip from sampler -> evaluator -> DesignSpace.
- Filter API.
- Picked / Best in Space / Best in Filter triad.
- Pareto front identification.
- Robust handling of evaluator errors.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from cascade.explore import (
    Candidate,
    Constraint,
    DesignSpace,
    DesignSpaceExplorer,
    EVALUATOR_ERROR,
    INVALID_GEOMETRY,
    ParameterRange,
    SobolSampler,
    VALID,
)
from cascade.units import Q


# --- Module-level evaluators (must be picklable for ProcessPoolExecutor) ----


def _quad_evaluator(params: Dict[str, Any]) -> Dict[str, Any]:
    """Synthetic evaluator: r^2 of (x, y)."""
    x = float(params["x"].magnitude)
    y = float(params["y"].magnitude)
    return {
        "objectives": {"r2": x * x + y * y},
        "status": VALID,
    }


def _tradeoff_evaluator(params: Dict[str, Any]) -> Dict[str, Any]:
    """A bi-objective evaluator for Pareto tests.

    Minimize f1 = x; minimize f2 = (x-1)^2 + y^2. The Pareto front sits
    along x in [0, 1].
    """
    x = float(params["x"].magnitude)
    y = float(params["y"].magnitude)
    return {
        "objectives": {
            "f1": x,
            "f2": (x - 1.0) ** 2 + y ** 2,
        },
        "status": VALID,
    }


def _flaky_evaluator(params: Dict[str, Any]) -> Dict[str, Any]:
    """Raises for x < 0.1; succeeds otherwise."""
    x = float(params["x"].magnitude)
    if x < 0.1:
        raise RuntimeError("forced failure for low x")
    return {"objectives": {"y": x * 2.0}, "status": VALID}


def _mixed_status_evaluator(params: Dict[str, Any]) -> Dict[str, Any]:
    x = float(params["x"].magnitude)
    if x > 0.9:
        return {"objectives": {}, "status": INVALID_GEOMETRY}
    return {"objectives": {"y": x}, "status": VALID}


# --- Tests ----------------------------------------------------------------


class TestDesignSpaceBasics:
    def test_filter_returns_subspace(self) -> None:
        cs = [
            Candidate(params={"i": i}, objectives={"y": float(i)}, status=VALID)
            for i in range(10)
        ]
        space = DesignSpace(candidates=cs, primary_objective="y", minimize_primary=False)
        big = space.filter(lambda c: c.objective_value("y") >= 5.0)
        assert len(big) == 5
        assert big.candidates[0].objective_value("y") == 5.0

    def test_best_in_space_minimize(self) -> None:
        cs = [
            Candidate(params={"i": i}, objectives={"y": float(i)}, status=VALID)
            for i in range(10)
        ]
        space = DesignSpace(candidates=cs, primary_objective="y", minimize_primary=True)
        assert space.best_in_space().objective_value("y") == 0.0

    def test_best_in_space_maximize(self) -> None:
        cs = [
            Candidate(params={"i": i}, objectives={"y": float(i)}, status=VALID)
            for i in range(10)
        ]
        space = DesignSpace(candidates=cs, primary_objective="y", minimize_primary=False)
        assert space.best_in_space().objective_value("y") == 9.0

    def test_best_skips_invalid(self) -> None:
        cs = [
            Candidate(params={"i": 0}, objectives={"y": -100.0}, status=INVALID_GEOMETRY),
            Candidate(params={"i": 1}, objectives={"y": 5.0}, status=VALID),
            Candidate(params={"i": 2}, objectives={"y": 0.0}, status=VALID),
        ]
        space = DesignSpace(candidates=cs, primary_objective="y", minimize_primary=True)
        # invalid candidate has lower y but is filtered out
        assert space.best_in_space().objective_value("y") == 0.0

    def test_best_in_filter(self) -> None:
        cs = [
            Candidate(params={"i": i}, objectives={"y": float(i)}, status=VALID)
            for i in range(10)
        ]
        space = DesignSpace(candidates=cs, primary_objective="y", minimize_primary=False)
        best_lt5 = space.best_in_filter(lambda c: c.objective_value("y") < 5.0)
        assert best_lt5.objective_value("y") == 4.0

    def test_picked(self) -> None:
        cs = [
            Candidate(params={"i": i}, objectives={"y": float(i)}, status=VALID)
            for i in range(5)
        ]
        space = DesignSpace(candidates=cs)
        space.pick(3)
        assert space.picked is cs[3]
        with pytest.raises(IndexError):
            space.pick(99)

    def test_valid_only(self) -> None:
        cs = [
            Candidate(params={"i": 0}, status=VALID, constraints={"c1": True}),
            Candidate(params={"i": 1}, status=VALID, constraints={"c1": False}),
            Candidate(params={"i": 2}, status=INVALID_GEOMETRY),
        ]
        space = DesignSpace(candidates=cs)
        assert len(space.valid_only()) == 1

    def test_pareto_2d(self) -> None:
        # 4 candidates with known dominance:
        #   A=(1,4), B=(2,3), C=(3,2), D=(4,1) — all non-dominated minimizing both
        #   E=(3,3) is dominated by B and C
        cs = [
            Candidate(params={"i": 0}, objectives={"f1": 1.0, "f2": 4.0}, status=VALID),
            Candidate(params={"i": 1}, objectives={"f1": 2.0, "f2": 3.0}, status=VALID),
            Candidate(params={"i": 2}, objectives={"f1": 3.0, "f2": 2.0}, status=VALID),
            Candidate(params={"i": 3}, objectives={"f1": 4.0, "f2": 1.0}, status=VALID),
            Candidate(params={"i": 4}, objectives={"f1": 3.0, "f2": 3.0}, status=VALID),
        ]
        space = DesignSpace(candidates=cs)
        pareto = space.pareto_front([("f1", True), ("f2", True)])
        # 4 non-dominated, E excluded
        assert len(pareto) == 4
        ids = sorted(c.params["i"] for c in pareto)
        assert ids == [0, 1, 2, 3]


class TestExplorerRoundTrip:
    def test_synthetic_2d_quadratic(self) -> None:
        sampler = SobolSampler(
            parameter_ranges={
                "x": ParameterRange(-2.0, 2.0, "dimensionless"),
                "y": ParameterRange(-2.0, 2.0, "dimensionless"),
            },
            n_samples=128,
            seed=7,
        )
        explorer = DesignSpaceExplorer()
        space = explorer.run(
            _quad_evaluator,
            sampler,
            constraints=[
                Constraint("within_unit_disk", lambda c: c.objective_value("r2") <= 1.0),
            ],
            parallel=1,
            primary_objective="r2",
            minimize_primary=True,
        )
        assert len(space) == 128
        # All should evaluate cleanly
        assert all(c.is_valid for c in space)
        # Best in space minimizes r^2 -> very small number
        best = space.best_in_space()
        assert best is not None
        assert best.objective_value("r2") < 0.5
        # Filter API still works
        unit_disk = space.filter(lambda c: c.constraints.get("within_unit_disk", False))
        assert len(unit_disk) > 0
        # Each filtered candidate satisfies the constraint
        for c in unit_disk:
            assert c.objective_value("r2") <= 1.0

    def test_evaluator_error_does_not_crash(self) -> None:
        sampler = SobolSampler(
            parameter_ranges={"x": ParameterRange(0.0, 1.0, "dimensionless")},
            n_samples=64,
            seed=0,
        )
        explorer = DesignSpaceExplorer()
        space = explorer.run(_flaky_evaluator, sampler, parallel=1)
        n_err = sum(1 for c in space if c.status == EVALUATOR_ERROR)
        n_ok = sum(1 for c in space if c.is_valid)
        assert n_err > 0  # some samples have x < 0.1
        assert n_ok > 0  # most don't
        assert n_err + n_ok == len(space)

    def test_pareto_via_explorer(self) -> None:
        sampler = SobolSampler(
            parameter_ranges={
                "x": ParameterRange(0.0, 1.0, "dimensionless"),
                "y": ParameterRange(-0.5, 0.5, "dimensionless"),
            },
            n_samples=256,
            seed=0,
        )
        explorer = DesignSpaceExplorer()
        space = explorer.run(_tradeoff_evaluator, sampler, parallel=1)
        pareto = space.pareto_front([("f1", True), ("f2", True)])
        # Pareto front should be nontrivial (>5 points) for 256 samples
        assert len(pareto) > 5
        # Front points should respect dominance: no two strictly dominate
        for a in pareto:
            for b in pareto:
                if a is b:
                    continue
                # b should not dominate a
                f1a = a.objective_value("f1")
                f1b = b.objective_value("f1")
                f2a = a.objective_value("f2")
                f2b = b.objective_value("f2")
                strictly_dominated = (f1b <= f1a and f2b <= f2a) and (
                    f1b < f1a or f2b < f2a
                )
                assert not strictly_dominated

    def test_mixed_statuses_preserved(self) -> None:
        sampler = SobolSampler(
            parameter_ranges={"x": ParameterRange(0.0, 1.0, "dimensionless")},
            n_samples=64,
            seed=0,
        )
        explorer = DesignSpaceExplorer()
        space = explorer.run(_mixed_status_evaluator, sampler, parallel=1)
        statuses = {c.status for c in space}
        assert VALID in statuses
        assert INVALID_GEOMETRY in statuses
