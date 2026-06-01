"""Independent verification — Sobol' design-space sampling.

Oracles: a seeded low-discrepancy sequence must be deterministic, stay inside
its declared bounds (linear and log scale), differ across seeds, and cover the
unit square roughly uniformly (mean near the box centre, both halves populated).
"""

from __future__ import annotations

import numpy as np

from cascade.explore import ParameterRange, SobolSampler


def _mag(v, unit=None):  # noqa: ANN001, ANN202
    if unit is not None and hasattr(v, "to"):
        return v.to(unit).magnitude
    return v.magnitude if hasattr(v, "magnitude") else v


def test_sampler_is_deterministic_given_seed() -> None:
    pr = {"x": ParameterRange(min=0.0, max=1.0, unit="m"),
          "y": ParameterRange(min=10.0, max=20.0, unit="m")}
    a = SobolSampler(pr, n_samples=64, seed=7).generate()
    b = SobolSampler(pr, n_samples=64, seed=7).generate()
    assert len(a) == len(b) == 64
    assert all(_mag(p["x"], "m") == _mag(q["x"], "m") for p, q in zip(a, b))


def test_samples_respect_linear_bounds() -> None:
    pr = {"x": ParameterRange(min=-2.0, max=5.0, unit="m"),
          "y": ParameterRange(min=10.0, max=20.0, unit="m")}
    for s in SobolSampler(pr, n_samples=128, seed=1).generate():
        assert -2.0 <= _mag(s["x"], "m") <= 5.0
        assert 10.0 <= _mag(s["y"], "m") <= 20.0


def test_different_seeds_give_different_samples() -> None:
    pr = {"x": ParameterRange(min=0.0, max=1.0, unit="m")}
    a = [_mag(s["x"], "m") for s in SobolSampler(pr, n_samples=64, seed=1).generate()]
    b = [_mag(s["x"], "m") for s in SobolSampler(pr, n_samples=64, seed=2).generate()]
    assert a != b


def test_log_scale_samples_within_bounds_and_positive() -> None:
    pr = {"p": ParameterRange(min=1.0, max=1000.0, unit="Pa", scale="log")}
    vals = [_mag(s["p"], "Pa") for s in SobolSampler(pr, n_samples=128, seed=3).generate()]
    assert all(1.0 <= v <= 1000.0 for v in vals)
    assert all(v > 0.0 for v in vals)


def test_sample_count_matches_request() -> None:
    pr = {"x": ParameterRange(min=0.0, max=1.0, unit="m")}
    assert len(SobolSampler(pr, n_samples=256, seed=0).generate()) == 256


def test_two_dimensional_coverage_is_roughly_uniform() -> None:
    pr = {"x": ParameterRange(min=0.0, max=1.0, unit="m"),
          "y": ParameterRange(min=0.0, max=1.0, unit="m")}
    samples = SobolSampler(pr, n_samples=256, seed=0).generate()
    xs = np.array([_mag(s["x"], "m") for s in samples])
    ys = np.array([_mag(s["y"], "m") for s in samples])
    assert abs(xs.mean() - 0.5) < 0.08
    assert abs(ys.mean() - 0.5) < 0.08
    # all four quadrants populated (low-discrepancy property)
    for cx in (xs < 0.5, xs >= 0.5):
        for cy in (ys < 0.5, ys >= 0.5):
            assert np.count_nonzero(cx & cy) > 0
