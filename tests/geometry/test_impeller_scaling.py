"""Regression tests for ADAPT-030 — sub-millimetre impeller scaling.

The original bore-radius formula was

    r_bore = max(0.3 * r_hub, 1e-3)

which silently injected a 1 mm absolute floor. For a sub-mm impeller
(microturbine, MEMS-scale prototype, etc.) the floor kicked in and the bore
was rendered ~1000× larger than the intended 30 % proportional value —
corrupting the geometry without raising. The fix replaces the absolute floor
with a strictly-proportional 30 % rule and an explicit ``r_hub > 0`` /
``finite`` check.

See ADAPT-030.
"""

from __future__ import annotations

import math

import pytest

from cascade.geometry.impeller import _bore_radius
from cascade.meanline.centrifugal_compressor import CentrifugalCompressorGeometry
from cascade.meanline.exceptions import InvalidGeometry


def _scaled_geom(
    r_tip: float,
    r_hub: float,
    *,
    r_outlet_mult: float = 2.0,
    blade_height_mult: float = 0.25,
    tip_clearance_mult: float = 0.01,
) -> CentrifugalCompressorGeometry:
    """Build a self-similar impeller at the requested length scale.

    ``CentrifugalCompressorGeometry`` requires
    ``impeller_outlet_radius > inducer_tip_radius`` and a positive blade
    height. All sizes scale with ``r_tip`` so the same geometry is exercised
    at every scale.
    """
    return CentrifugalCompressorGeometry(
        inducer_hub_radius=r_hub,
        inducer_tip_radius=r_tip,
        impeller_outlet_radius=r_outlet_mult * r_tip,
        blade_height_outlet=blade_height_mult * r_tip,
        blade_count=12,
        beta_2_metal_rad=math.pi / 3,  # 30° backsweep
        tip_clearance=tip_clearance_mult * r_tip,
    )


class TestImpellerBoreScalesProportionally:
    """The bore radius must always be 30 % of ``inducer_hub_radius``,
    independent of length scale.

    Each test uses a fresh self-similar geometry; the expected bore is
    exactly ``0.3 * r_hub`` to within floating-point round-off.
    """

    def test_metre_scale_impeller(self) -> None:
        # Industrial centrifugal compressor scale.
        geom = _scaled_geom(r_tip=1.0, r_hub=0.3)
        r_bore = _bore_radius(geom)
        assert r_bore == pytest.approx(0.09, rel=1e-12)

    def test_millimetre_scale_impeller(self) -> None:
        # Small turbocharger / microturbine scale (typical wearable / drone).
        geom = _scaled_geom(r_tip=1.0e-3, r_hub=0.3e-3)
        r_bore = _bore_radius(geom)
        assert r_bore == pytest.approx(0.09e-3, rel=1e-12)
        # And crucially: NOT silently floored at the legacy 1 mm value.
        assert r_bore < 1e-3, (
            "r_bore was clamped at the legacy 1 mm absolute floor — the "
            "pre-ADAPT-030 bug regressed."
        )

    def test_micrometre_scale_impeller(self) -> None:
        # MEMS-scale / micro-turbomachinery research prototype.
        geom = _scaled_geom(r_tip=1.0e-6, r_hub=0.3e-6)
        r_bore = _bore_radius(geom)
        assert r_bore == pytest.approx(0.09e-6, rel=1e-12)
        # The pre-fix bug would have returned 1e-3 (1 mm), i.e. 10_000× the
        # entire impeller size. Make sure that catastrophe is gone.
        assert r_bore < 1e-3
        assert r_bore < geom.inducer_hub_radius


class TestImpellerBoreRefusesDegenerate:
    """Catch degenerate inputs *before* they pollute the mesh."""

    def test_refuses_nan_hub_radius(self) -> None:
        # CentrifugalCompressorGeometry itself doesn't currently NaN-check
        # (``NaN < 0`` is False), so the impeller mesh stage must be its
        # own line of defence.
        try:
            geom = CentrifugalCompressorGeometry(
                inducer_hub_radius=float("nan"),
                inducer_tip_radius=0.05,
                impeller_outlet_radius=0.10,
                blade_height_outlet=0.012,
                blade_count=12,
                beta_2_metal_rad=math.pi / 3,
                tip_clearance=0.0005,
            )
        except InvalidGeometry:
            # If upstream now refuses NaN too, that's also acceptable —
            # both layers fail closed, the regression target is met.
            return
        with pytest.raises(ValueError, match=r"inducer_hub_radius.*finite"):
            _bore_radius(geom)

    def test_refuses_zero_hub_radius(self) -> None:
        # r_hub = 0 collapses the hub solid to a single axial line;
        # CentrifugalCompressorGeometry currently allows it (the guard is
        # `< 0`), so the mesh layer must catch it.
        geom = CentrifugalCompressorGeometry(
            inducer_hub_radius=0.0,
            inducer_tip_radius=0.05,
            impeller_outlet_radius=0.10,
            blade_height_outlet=0.012,
            blade_count=12,
            beta_2_metal_rad=math.pi / 3,
            tip_clearance=0.0005,
        )
        with pytest.raises(ValueError, match=r"inducer_hub_radius.*finite.*> 0"):
            _bore_radius(geom)

    def test_refuses_negative_hub_radius(self) -> None:
        # Belt-and-braces — upstream rejects negative r_hub, but the bore
        # helper must also fail safe if called directly.
        try:
            geom = CentrifugalCompressorGeometry(
                inducer_hub_radius=-0.001,
                inducer_tip_radius=0.05,
                impeller_outlet_radius=0.10,
                blade_height_outlet=0.012,
                blade_count=12,
                beta_2_metal_rad=math.pi / 3,
                tip_clearance=0.0005,
            )
        except InvalidGeometry:
            # Upstream already refuses — nothing more to do.
            return
        with pytest.raises(ValueError, match=r"inducer_hub_radius"):
            _bore_radius(geom)


class TestImpellerScalingPropertyTransitivity:
    """If r_hub scales by k, r_bore must scale by exactly k."""

    def test_linear_scaling(self) -> None:
        base = _scaled_geom(r_tip=0.05, r_hub=0.018)
        bore_base = _bore_radius(base)
        for k in (1e-4, 1e-2, 1e-1, 1.0, 10.0, 1e3):
            scaled = _scaled_geom(r_tip=0.05 * k, r_hub=0.018 * k)
            bore_scaled = _bore_radius(scaled)
            assert bore_scaled == pytest.approx(k * bore_base, rel=1e-12), (
                f"bore scaling broken at k={k}: "
                f"expected {k * bore_base!r}, got {bore_scaled!r}"
            )
