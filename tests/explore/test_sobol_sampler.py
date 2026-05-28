"""Tests for `cascade.explore.sobol_sampler.SobolSampler`.

Per SPEC_SHEET §9 (Sobol' with Joe-Kuo direction numbers via scipy).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from cascade.explore.sobol_sampler import ParameterRange, SobolSampler
from cascade.units import Q, Quantity


class TestParameterRange:
    def test_construct_linear(self) -> None:
        r = ParameterRange(min=10000.0, max=40000.0, unit="rpm")
        assert r.scale == "linear"
        assert not r.is_categorical
        q = r.rescale(0.5)
        assert isinstance(q, Quantity)
        assert q.to("rpm").magnitude == pytest.approx(25000.0)

    def test_construct_log(self) -> None:
        r = ParameterRange(min=1e-6, max=1e-3, unit="m", scale="log")
        # u=0 -> min; u=1 -> max; u=0.5 -> geometric mean
        assert r.rescale(0.5).to("m").magnitude == pytest.approx(math.sqrt(1e-6 * 1e-3))

    def test_construct_categorical(self) -> None:
        r = ParameterRange(choices=["A", "B", "C"])
        assert r.is_categorical
        assert r.rescale(0.0) == "A"
        assert r.rescale(0.4) == "B"
        # u=0.99999 -> last index
        assert r.rescale(0.999) == "C"

    def test_refuse_invalid_bounds(self) -> None:
        with pytest.raises(ValueError):
            ParameterRange(min=10.0, max=5.0, unit="rpm")

    def test_refuse_log_nonpositive(self) -> None:
        with pytest.raises(ValueError):
            ParameterRange(min=-1.0, max=10.0, unit="m", scale="log")

    def test_refuse_mixed_categorical_numeric(self) -> None:
        with pytest.raises(ValueError):
            ParameterRange(min=0.0, max=1.0, unit="rpm", choices=["A"])


class TestSobolSampler:
    def test_generate_2d_yields_correct_shape(self) -> None:
        sampler = SobolSampler(
            parameter_ranges={
                "rpm": ParameterRange(10000.0, 40000.0, "rpm"),
                "diameter": ParameterRange(0.1, 0.25, "m"),
            },
            n_samples=1024,
            seed=42,
        )
        samples = sampler.generate()
        assert len(samples) == 1024
        for s in samples:
            assert set(s.keys()) == {"rpm", "diameter"}
            assert isinstance(s["rpm"], Quantity)
            assert isinstance(s["diameter"], Quantity)
            rpm_val = s["rpm"].to("rpm").magnitude
            assert 10000.0 <= rpm_val <= 40000.0
            d_val = s["diameter"].to("m").magnitude
            assert 0.1 <= d_val <= 0.25

    def test_discrepancy_below_threshold(self) -> None:
        """Sobol' with 1024 points in 2D should have very low star discrepancy.

        The L2-star discrepancy of Sobol' is
        O((log n)^d / n). For n=1024, d=2 we expect discrepancy << 0.01.
        scipy's `qmc.discrepancy` returns the L2-star variant by default.
        """
        sampler = SobolSampler(
            parameter_ranges={
                "x1": ParameterRange(0.0, 1.0, "dimensionless"),
                "x2": ParameterRange(0.0, 1.0, "dimensionless"),
            },
            n_samples=1024,
            seed=42,
        )
        disc = sampler.discrepancy()
        # Empirically scipy returns ~1e-4 to 1e-3 for n=1024, d=2.
        assert disc < 5e-3, f"L2-star discrepancy {disc} above threshold"

    def test_deterministic_with_fixed_seed(self) -> None:
        sampler_a = SobolSampler(
            parameter_ranges={
                "rpm": ParameterRange(10000.0, 40000.0, "rpm"),
                "diameter": ParameterRange(0.1, 0.25, "m"),
            },
            n_samples=512,
            seed=12345,
        )
        sampler_b = SobolSampler(
            parameter_ranges={
                "rpm": ParameterRange(10000.0, 40000.0, "rpm"),
                "diameter": ParameterRange(0.1, 0.25, "m"),
            },
            n_samples=512,
            seed=12345,
        )
        s_a = sampler_a.generate()
        s_b = sampler_b.generate()
        for a, b in zip(s_a, s_b):
            assert a["rpm"].to("rpm").magnitude == pytest.approx(
                b["rpm"].to("rpm").magnitude
            )
            assert a["diameter"].to("m").magnitude == pytest.approx(
                b["diameter"].to("m").magnitude
            )

    def test_different_seeds_yield_different_samples(self) -> None:
        sampler_a = SobolSampler(
            parameter_ranges={"x": ParameterRange(0.0, 1.0, "dimensionless")},
            n_samples=128,
            seed=1,
        )
        sampler_b = SobolSampler(
            parameter_ranges={"x": ParameterRange(0.0, 1.0, "dimensionless")},
            n_samples=128,
            seed=2,
        )
        s_a = [s["x"].magnitude for s in sampler_a.generate()]
        s_b = [s["x"].magnitude for s in sampler_b.generate()]
        # The two scrambled sequences shouldn't be identical
        assert not all(a == pytest.approx(b) for a, b in zip(s_a, s_b))

    def test_small_n_warns_about_clumping(self) -> None:
        with pytest.warns(UserWarning, match="clumping"):
            SobolSampler(
                parameter_ranges={"x": ParameterRange(0.0, 1.0, "dimensionless")},
                n_samples=16,
                seed=0,
            )

    def test_log_scale_distribution(self) -> None:
        """Log-scale samples in [1e-6, 1e-3] should populate all decades."""
        sampler = SobolSampler(
            parameter_ranges={
                "clearance": ParameterRange(1e-6, 1e-3, "m", scale="log"),
            },
            n_samples=256,
            seed=0,
        )
        samples = sampler.generate()
        log_values = np.array(
            [math.log10(s["clearance"].to("m").magnitude) for s in samples]
        )
        # Should span at least decade boundaries -6 to -3
        assert log_values.min() < -5.5
        assert log_values.max() > -3.5

    def test_categorical(self) -> None:
        sampler = SobolSampler(
            parameter_ranges={
                "material": ParameterRange(choices=["Inconel718", "TiAl", "MarM247"]),
            },
            n_samples=128,
            seed=0,
        )
        samples = sampler.generate()
        materials = {s["material"] for s in samples}
        # With 128 well-distributed samples on 3 categories we expect all 3
        assert materials == {"Inconel718", "TiAl", "MarM247"}
