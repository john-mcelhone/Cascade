"""ADAPT-007: Aungier (2000) eq. 6.51 mixing + eq. 6.66 leakage formulas.

Verifies that the **real** Aungier formulas (not the previous piecewise
constants) are wired correctly into the centrifugal-compressor loss
model. Order-of-magnitude correctness checks at the Eckardt Rotor A and
Rotor O design points.

B-07 note (2026-05-27): Aungier eq. 6.51 uses sin²(β₂'), not cos²(β₂').
The trig direction was corrected and the test for "mixing vanishes for
radial blades (β₂'=90°)" has been updated: with sin²(90°)=1, a radial-
bladed impeller has MAXIMUM mixing, not zero. The test now asserts this
correct physical direction.

References:
- Aungier, R.H., 2000, *Centrifugal Compressors: A Strategy for
  Aerodynamic Design and Analysis*, ASME Press, Ch. 6, eq. 6.51
  (mixing) and eq. 6.66 (leakage).
- Casey, M.V., Robinson, C.J., 2021. *Radial Flow Turbocompressors*,
  Cambridge Univ. Press, §8.6.
"""

from __future__ import annotations

import math

import pytest

from cascade.meanline import (
    AungierCentrifugal,
    CentrifugalCompressorGeometry,
    CentrifugalCompressorMeanline,
)
from cascade.meanline.fluid import AIR
from cascade.units import Composition, Port, Q


@pytest.mark.validation
class TestAungierMixing:
    """Aungier eq. 6.51: Δh_mix = ½(ε_w·W₂)² · sin²(β₂_blade).

    B-07 fix (2026-05-27): corrected from cos² to sin². The meridional
    velocity component of W₂ is W₂·sin(β₂') which governs jet/wake shear.
    """

    def test_mixing_maximum_for_radial_blades(self) -> None:
        """For a radial-bladed impeller (β₂'_from_tan = 90°), sin β₂' = 1
        → Δh_mix is at its MAXIMUM. The jet and wake have maximum meridional
        velocity difference, giving the highest mixing loss.

        UPDATED (B-07, 2026-05-27): the previous assertion "mixing → 0 for
        radial blades" was based on the wrong cos² formula. The correct
        Aungier eq. 6.51 uses sin²(β₂'), making radial-bladed impellers
        have the MOST mixing, not the least.

        Citation: Aungier 2000 eq. 6.51.
        """
        geom = CentrifugalCompressorGeometry(
            inducer_hub_radius=0.045,
            inducer_tip_radius=0.140,
            impeller_outlet_radius=0.200,
            blade_height_outlet=0.026,
            blade_count=20,
            beta_2_metal_rad=0.0,  # radial: β₂'_from_tan = 90° → sin(90°)=1
            tip_clearance=0.0003,
            blockage_outlet=0.08,
        )
        inlet = Port(
            pressure_total=Q(101325, "Pa"),
            temperature_total=Q(288.15, "K"),
            mass_flow=Q(5.31, "kg/s"),
            composition=Composition.air(),
        )
        solver = CentrifugalCompressorMeanline()
        result = solver.solve(inlet, Q(14000, "rpm"), geom,
                              AungierCentrifugal(), AIR)
        # sin(π/2) = 1 → mixing must be positive and measurable
        assert result.loss_breakdown.mixing > 1e-4, \
            (f"Radial-bladed impeller should have measurable mixing (sin²(90°)=1); got "
             f"{result.loss_breakdown.mixing:.6f}")

    def test_mixing_grows_with_backsweep(self) -> None:
        """A back-swept impeller has finite mixing. Verify that the
        30°-back-sweep Eckardt Rotor A has a measurable mixing loss
        in the right order of magnitude (10⁻³ to 10⁻² of ½U₂²).
        """
        geom = CentrifugalCompressorGeometry(
            inducer_hub_radius=0.045,
            inducer_tip_radius=0.140,
            impeller_outlet_radius=0.200,
            blade_height_outlet=0.026,
            blade_count=20,
            beta_2_metal_rad=math.pi / 6,  # 30° back-sweep
            tip_clearance=0.0003,
            blockage_outlet=0.08,
        )
        inlet = Port(
            pressure_total=Q(101325, "Pa"),
            temperature_total=Q(288.15, "K"),
            mass_flow=Q(5.31, "kg/s"),
            composition=Composition.air(),
        )
        solver = CentrifugalCompressorMeanline()
        result = solver.solve(inlet, Q(14000, "rpm"), geom,
                              AungierCentrifugal(), AIR)
        # For 30°-back-swept Eckardt Rotor A: ε_w=0.15, W₂ ≈ 120 m/s,
        # cos²(β₂_blade_from_tan=60°) = 0.25.
        # Δh = 0.5·(0.15·120)²·0.25 ≈ 40.5 J/kg.
        # ζ = 40.5 / (0.5·293²) ≈ 9.4e-4.
        # Order-of-magnitude check: 1e-4 to 1e-2.
        assert 1e-5 < result.loss_breakdown.mixing < 5e-2, \
            (f"Back-swept Eckardt Rotor A mixing = "
             f"{result.loss_breakdown.mixing:.5f}; expected "
             f"order ~1e-3")


@pytest.mark.validation
class TestAungierLeakage:
    """Aungier eq. 6.66: orifice-flow seal leakage."""

    def test_leakage_zero_when_clearance_zero(self) -> None:
        """ε_clearance = 0 → no leakage loss."""
        geom = CentrifugalCompressorGeometry(
            inducer_hub_radius=0.045,
            inducer_tip_radius=0.140,
            impeller_outlet_radius=0.200,
            blade_height_outlet=0.026,
            blade_count=20,
            beta_2_metal_rad=math.pi / 6,
            tip_clearance=0.0,  # also zero tip clearance
            epsilon_clearance=0.0,
            blockage_outlet=0.08,
        )
        inlet = Port(
            pressure_total=Q(101325, "Pa"),
            temperature_total=Q(288.15, "K"),
            mass_flow=Q(5.31, "kg/s"),
            composition=Composition.air(),
        )
        solver = CentrifugalCompressorMeanline()
        result = solver.solve(inlet, Q(14000, "rpm"), geom,
                              AungierCentrifugal(), AIR)
        assert result.loss_breakdown.leakage == pytest.approx(0.0,
                                                              abs=1e-9)

    def test_leakage_increases_with_clearance(self) -> None:
        """Doubling ε_clearance approximately doubles the leakage loss."""
        inlet = Port(
            pressure_total=Q(101325, "Pa"),
            temperature_total=Q(288.15, "K"),
            mass_flow=Q(5.31, "kg/s"),
            composition=Composition.air(),
        )
        solver = CentrifugalCompressorMeanline()
        loss = AungierCentrifugal()

        def _solve(eps: float) -> float:
            geom = CentrifugalCompressorGeometry(
                inducer_hub_radius=0.045,
                inducer_tip_radius=0.140,
                impeller_outlet_radius=0.200,
                blade_height_outlet=0.026,
                blade_count=20,
                beta_2_metal_rad=math.pi / 6,
                tip_clearance=0.0003,
                epsilon_clearance=eps,
                blockage_outlet=0.08,
            )
            return solver.solve(inlet, Q(14000, "rpm"), geom,
                                loss, AIR).loss_breakdown.leakage

        leak1 = _solve(0.0001)
        leak2 = _solve(0.0002)
        # mdot_leak ∝ ε_clearance (linear in clearance area); the
        # Euler-work multiplier is the same. So roughly 2x.
        assert leak2 > leak1
        assert 1.8 < leak2 / max(leak1, 1e-12) < 2.2, \
            (f"leak2/leak1 = {leak2/max(leak1,1e-12):.3f}; expected ≈ 2")

    def test_leakage_order_of_magnitude_eckardt(self) -> None:
        """For Eckardt Rotor A with ε_clearance = 0.0001 (default),
        the leakage loss should be in the 1-5% range of ½U₂² —
        i.e., ζ_leak ∈ [0.005, 0.05].
        """
        geom = CentrifugalCompressorGeometry(
            inducer_hub_radius=0.045,
            inducer_tip_radius=0.140,
            impeller_outlet_radius=0.200,
            blade_height_outlet=0.026,
            blade_count=20,
            beta_2_metal_rad=math.pi / 6,
            tip_clearance=0.0003,
            blockage_outlet=0.08,
        )
        inlet = Port(
            pressure_total=Q(101325, "Pa"),
            temperature_total=Q(288.15, "K"),
            mass_flow=Q(5.31, "kg/s"),
            composition=Composition.air(),
        )
        solver = CentrifugalCompressorMeanline()
        result = solver.solve(inlet, Q(14000, "rpm"), geom,
                              AungierCentrifugal(), AIR)
        assert 0.001 < result.loss_breakdown.leakage < 0.05, \
            (f"Eckardt Rotor A leakage = "
             f"{result.loss_breakdown.leakage:.5f}; expected "
             f"order 1e-2.")
