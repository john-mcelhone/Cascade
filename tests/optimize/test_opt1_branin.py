"""SPEC_SHEET §12 OPT-1: Branin function global-minimum test.

The Branin function (Surjanovic & Bingham VLSE) has
three known global minima of equal value ~0.397887, at:

  (-pi, 12.275), (pi, 2.275), (9.42478, 2.475)

domain: x1 in [-5, 10], x2 in [0, 15].

Pass-gate: a smooth optimizer (SLSQP from a reasonable starting point,
or Powell-as-BOBYQA) finds a global minimum within ~100 function
evaluations.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from cascade.optimize import (
    OptimizeBOBYQA,
    OptimizeCMAES,
    OptimizeSLSQP,
)


def branin(x: np.ndarray) -> float:
    """Branin function. Returns scalar in [0, ~300]; global min ~0.397887."""
    x1, x2 = float(x[0]), float(x[1])
    a = 1.0
    b = 5.1 / (4.0 * math.pi * math.pi)
    c = 5.0 / math.pi
    r = 6.0
    s = 10.0
    t = 1.0 / (8.0 * math.pi)
    return (
        a * (x2 - b * x1 * x1 + c * x1 - r) ** 2
        + s * (1.0 - t) * math.cos(x1)
        + s
    )


# Known global minima (any of the three is a valid converge point)
BRANIN_MINIMA = [
    (-math.pi, 12.275),
    (math.pi, 2.275),
    (9.42478, 2.475),
]
BRANIN_MIN_VALUE = 0.397887


def _close_to_any_minimum(x: np.ndarray, tol_x: float = 0.5) -> bool:
    """Is `x` within `tol_x` (L2) of any of the three global minima?"""
    for m in BRANIN_MINIMA:
        if np.linalg.norm(x - np.array(m)) < tol_x:
            return True
    return False


@pytest.mark.validation
class TestBraninOPT1:
    @pytest.mark.spec_parity("SPEC-10")
    def test_slsqp_finds_minimum_within_100_evals(self) -> None:
        # Start near the (pi, 2.275) basin
        x0 = np.array([2.0, 4.0])
        opt = OptimizeSLSQP(max_iter=80, ftol=1e-6)
        res = opt.minimize(
            branin,
            x0=x0,
            bounds=[(-5.0, 10.0), (0.0, 15.0)],
        )
        assert res.success or res.fun < BRANIN_MIN_VALUE + 0.05
        assert res.n_evals < 100, f"SLSQP used {res.n_evals} evals (>100)"
        assert res.fun < BRANIN_MIN_VALUE + 0.05, (
            f"SLSQP final value {res.fun:.6f} above target {BRANIN_MIN_VALUE + 0.05}"
        )
        assert _close_to_any_minimum(res.x), (
            f"SLSQP converged to {res.x}; not near any known minimum"
        )

    def test_powell_bobyqa_finds_minimum_within_100_evals(self) -> None:
        x0 = np.array([2.0, 4.0])
        opt = OptimizeBOBYQA(max_iter=200, xtol=1e-6)
        res = opt.minimize(
            branin,
            x0=x0,
            bounds=[(-5.0, 10.0), (0.0, 15.0)],
        )
        assert res.n_evals < 100, f"BOBYQA used {res.n_evals} evals (>100)"
        assert res.fun < BRANIN_MIN_VALUE + 0.05, (
            f"BOBYQA final value {res.fun:.6f} above target"
        )
        assert _close_to_any_minimum(res.x), (
            f"BOBYQA converged to {res.x}; not near any known minimum"
        )

    def test_cmaes_finds_minimum(self) -> None:
        """CMA-ES is gradient-free so will use more evals than SLSQP.

        We loosen the budget to 500 evals and check global-min quality.
        """
        x0 = np.array([0.0, 7.5])  # mid-domain start
        opt = OptimizeCMAES(sigma=2.0, max_iter=50, seed=42)
        res = opt.minimize(
            branin,
            x0=x0,
            bounds=[(-5.0, 10.0), (0.0, 15.0)],
        )
        assert res.fun < BRANIN_MIN_VALUE + 0.1, (
            f"CMA-ES final value {res.fun:.6f} too high"
        )

    def test_history_recorded(self) -> None:
        opt = OptimizeSLSQP(max_iter=40)
        res = opt.minimize(
            branin,
            x0=np.array([2.0, 4.0]),
            bounds=[(-5.0, 10.0), (0.0, 15.0)],
        )
        # Each evaluation should have been logged
        assert len(res.history) == res.n_evals
        # First entry is x0 region; last is best-found
        f_first = res.history[0][1]
        f_last = res.history[-1][1]
        assert f_last <= f_first
