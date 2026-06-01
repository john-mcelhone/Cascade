"""Independent verification — optimization (single- and multi-objective).

Oracles:
  - Branin-Hoo function global minimum f* = 0.397887 (three global minima)
  - A convex quadratic has a known analytic minimum
  - Closed-form 2D hypervolume on hand-computed Pareto fronts
  - ZDT2 true Pareto front is f2 = 1 - f1^2; its hypervolume w.r.t. (1.1,1.1)
    is computed here by independent numerical integration
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from cascade.optimize import (
    OptimizeCMAES,
    OptimizeNSGA2,
    OptimizeSLSQP,
    hypervolume_2d,
)

BRANIN_MIN = 0.397887


def _branin(x: np.ndarray) -> float:
    a, b, c = 1.0, 5.1 / (4 * math.pi ** 2), 5.0 / math.pi
    r, s, t = 6.0, 10.0, 1.0 / (8 * math.pi)
    return a * (x[1] - b * x[0] ** 2 + c * x[0] - r) ** 2 + s * (1 - t) * math.cos(x[0]) + s


BOUNDS = [(-5.0, 10.0), (0.0, 15.0)]


def test_slsqp_finds_branin_global_minimum_in_few_evals() -> None:
    res = OptimizeSLSQP().minimize(_branin, np.array([2.5, 7.5]), bounds=BOUNDS)
    assert res.fun == pytest.approx(BRANIN_MIN, abs=1e-2)
    assert res.n_evals < 100


def test_cmaes_finds_branin_global_minimum() -> None:
    res = OptimizeCMAES(seed=0).minimize(_branin, np.array([2.5, 7.5]), bounds=BOUNDS)
    assert res.fun == pytest.approx(BRANIN_MIN, abs=2e-2)


def test_slsqp_minimizes_convex_quadratic() -> None:
    # f = (x-3)^2 + (y+1)^2, min 0 at (3,-1)
    res = OptimizeSLSQP().minimize(lambda x: (x[0] - 3) ** 2 + (x[1] + 1) ** 2,
                                   np.array([0.0, 0.0]))
    assert res.fun == pytest.approx(0.0, abs=1e-6)
    assert res.x[0] == pytest.approx(3.0, abs=1e-3)
    assert res.x[1] == pytest.approx(-1.0, abs=1e-3)


def test_hypervolume_two_point_front_closed_form() -> None:
    hv = hypervolume_2d(np.array([[0.0, 1.0], [1.0, 0.0]]), (2.0, 2.0))
    assert hv == pytest.approx(3.0, abs=1e-9)


def test_hypervolume_single_point() -> None:
    assert hypervolume_2d(np.array([[0.5, 0.5]]), (1.0, 1.0)) == pytest.approx(0.25, abs=1e-9)


def test_hypervolume_three_point_front() -> None:
    hv = hypervolume_2d(np.array([[0.0, 1.0], [0.5, 0.5], [1.0, 0.0]]), (2.0, 2.0))
    assert hv == pytest.approx(3.25, abs=1e-9)


def test_hypervolume_ignores_points_beyond_reference() -> None:
    assert hypervolume_2d(np.array([[0.0, 2.0], [2.0, 0.0]]), (1.0, 1.0)) == pytest.approx(0.0, abs=1e-9)


def _zdt2_true_hypervolume(ref=(1.1, 1.1), n=40001) -> float:
    xs = np.linspace(0.0, 1.0, n)
    f2 = 1.0 - xs ** 2
    hv, last_y = 0.0, ref[1]
    for x, y in zip(xs, f2):
        if y < last_y:
            hv += (ref[0] - x) * (last_y - y)
            last_y = y
    return hv


def test_nsga2_zdt2_hypervolume_within_tolerance() -> None:
    n = 10
    def zdt2(x: np.ndarray) -> np.ndarray:
        f1 = x[0]
        g = 1.0 + 9.0 * np.mean(x[1:])
        return np.array([f1, g * (1.0 - (f1 / g) ** 2)])

    res = OptimizeNSGA2(pop_size=100, n_gen=150, seed=0).minimize(zdt2, bounds=[(0.0, 1.0)] * n, n_obj=2)
    hv = hypervolume_2d(res.pareto_f, (1.1, 1.1))
    hv_true = _zdt2_true_hypervolume()
    assert hv == pytest.approx(hv_true, rel=0.25)


def test_nsga2_pareto_front_is_nondominated() -> None:
    n = 10
    def zdt2(x: np.ndarray) -> np.ndarray:
        f1 = x[0]
        g = 1.0 + 9.0 * np.mean(x[1:])
        return np.array([f1, g * (1.0 - (f1 / g) ** 2)])

    res = OptimizeNSGA2(pop_size=80, n_gen=120, seed=1).minimize(zdt2, bounds=[(0.0, 1.0)] * n, n_obj=2)
    f = res.pareto_f
    for i in range(len(f)):
        for j in range(len(f)):
            if i == j:
                continue
            # No member may strictly dominate another on the reported front.
            assert not (np.all(f[j] <= f[i]) and np.any(f[j] < f[i]))
