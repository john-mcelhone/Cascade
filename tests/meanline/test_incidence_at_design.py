"""ADAPT-009: design-point incidence loss must be > 0 (but small).

The pre-ADAPT-009 code set β_blade = β_flow exactly at the inducer tip,
forcing incidence loss to vanish identically at design. Real
centrifugal impellers are designed with a small (1-3°) positive design
incidence so the wheel has measurable but small incidence loss at
design, growing rapidly off-design. This test exercises the new
behavior on the Eckardt Rotor A geometry.

References:
- Aungier, R.H., 2000. *Centrifugal Compressors: A Strategy for
  Aerodynamic Design and Analysis*, ASME Press, eq. 6.18.
- Whitfield, A. & Baines, N.C., 1990. *Design of Radial Turbomachines*,
  Longman, §6.2.
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


def _eckardt_rotor_a_geom(
        inducer_tip_blade_metal_rad: float = None,
) -> CentrifugalCompressorGeometry:
    return CentrifugalCompressorGeometry(
        inducer_hub_radius=0.045,
        inducer_tip_radius=0.140,
        impeller_outlet_radius=0.200,
        blade_height_outlet=0.026,
        blade_count=20,
        beta_2_metal_rad=math.pi / 6,
        tip_clearance=0.0003,
        blockage_outlet=0.08,
        inducer_tip_blade_metal_rad=inducer_tip_blade_metal_rad,
    )


_inlet = Port(
    pressure_total=Q(101325, "Pa"),
    temperature_total=Q(288.15, "K"),
    mass_flow=Q(5.31, "kg/s"),
    composition=Composition.air(),
)
_rpm = Q(14000, "rpm")


@pytest.mark.validation
class TestIncidenceAtDesign:
    """ADAPT-009: design incidence loss is finite but small."""

    def test_incidence_finite_at_design_default(self) -> None:
        """With the default (auto-derived 3° design incidence), the
        loss model returns ζ_inc > 0 — no longer identically zero.
        """
        solver = CentrifugalCompressorMeanline()
        result = solver.solve(_inlet, _rpm, _eckardt_rotor_a_geom(),
                              AungierCentrifugal(), AIR)
        # Strict > 0 — the pre-ADAPT-009 code returned ζ_inc == 0
        # exactly because β_blade = β_flow.
        assert result.loss_breakdown.incidence > 0.0, \
            (f"Design incidence must be > 0 (ADAPT-009); got "
             f"{result.loss_breakdown.incidence:.6f}")

    def test_incidence_below_5pct_inlet_KE(self) -> None:
        """Per the design-incidence spec: ζ_inc at design should be
        less than ~5% of the inlet kinetic head. The reference
        kinetic energy is ½ U₂² (the loss-coefficient denominator);
        the inlet kinetic head is ½ V₁². For Eckardt Rotor A,
        V₁ ≈ 80 m/s and U₂ ≈ 293 m/s, so V₁² / U₂² ≈ 0.075.

        With 3° design incidence at the inducer tip:
            Δh_inc ≈ 0.5·0.6·W₁²·sin²(3°) ≈ 40 J/kg
            ζ_inc = Δh_inc / (½U₂²) ≈ 9e-4
            ratio Δh_inc / (½V₁²) ≈ 40 / 3267 ≈ 1.2%
        Well under the 5% threshold.
        """
        solver = CentrifugalCompressorMeanline()
        result = solver.solve(_inlet, _rpm, _eckardt_rotor_a_geom(),
                              AungierCentrifugal(), AIR)
        U_2 = float(result.U_2.to("m/s").magnitude)
        V_1 = float(result.V_1.to("m/s").magnitude)
        dh_inc = result.loss_breakdown.incidence * 0.5 * U_2 ** 2
        ke_inlet = 0.5 * V_1 ** 2
        ratio = dh_inc / max(ke_inlet, 1.0)
        assert 0.0 < ratio < 0.05, \
            (f"Δh_inc / (½V₁²) = {ratio:.4f}; expected (0, 0.05). "
             f"Δh_inc = {dh_inc:.2f} J/kg, ½V₁² = {ke_inlet:.2f} J/kg")

    def test_incidence_grows_offdesign(self) -> None:
        """If we move the mass flow far from design, V_m₁ shifts and
        the inducer flow angle β₁_flow_from_tan also changes, while
        β₁_blade stays at the design value → larger |β_blade − β_flow|
        → larger incidence loss.

        With the OLD behavior (β_blade = β_flow always), ζ_inc would
        stay zero. With ADAPT-009 it must grow.

        Note: at small off-design (e.g., 0.7 m_design), β_flow shifts
        by only ~6° while the design incidence is 3°. The sin² of the
        new vs original angle ends up similar (3° design + 6° shift =
        +3° → |sin² = 0.0027|, almost equal to the design |sin² = 0.0027|).
        To see clear growth, move to ≥30% off-design (1.5× m_design)
        so |i| ≈ 12° → sin²(i) ≈ 0.044 ≫ design 0.0027.
        """
        solver = CentrifugalCompressorMeanline()
        loss = AungierCentrifugal()

        # Design-point solve with default 3° design incidence
        result_dp = solver.solve(_inlet, _rpm, _eckardt_rotor_a_geom(),
                                 loss, AIR)
        zeta_dp = result_dp.loss_breakdown.incidence

        # Pin blade angle to the design-flow direction minus 3° so
        # off-design clearly diverges from this metal angle.
        V_m1_dp = float(result_dp.V_1.to("m/s").magnitude)
        U_1_tip = float(_rpm.to("rad/s").magnitude) * 0.140
        beta_1_flow_from_tan_dp = math.atan2(V_m1_dp, U_1_tip)
        beta_1_blade_from_tan = beta_1_flow_from_tan_dp - math.radians(3.0)
        beta_1_blade_from_axial = math.pi / 2 - beta_1_blade_from_tan

        # Off-design: 50% of design mass flow → V_m₁ ~50% → β_flow much
        # steeper → blade is at the +ve incidence side → big growth.
        inlet_off = Port(
            pressure_total=Q(101325, "Pa"),
            temperature_total=Q(288.15, "K"),
            mass_flow=Q(5.31 * 0.5, "kg/s"),
            composition=Composition.air(),
        )
        geom_off = _eckardt_rotor_a_geom(
            inducer_tip_blade_metal_rad=beta_1_blade_from_axial)
        result_off = solver.solve(inlet_off, _rpm, geom_off, loss, AIR)
        zeta_off = result_off.loss_breakdown.incidence
        # At 50% mdot the expected growth is ≈ 6× (sin²(7.4°)/sin²(3°)).
        assert zeta_off > zeta_dp * 3.0, \
            (f"Off-design (50% m̃) incidence ζ_inc = {zeta_off:.5f} "
             f"should be > 3× design ζ_inc = {zeta_dp:.5f}")

    def test_user_provided_blade_angle_used(self) -> None:
        """User can override the auto-derived blade metal angle. With
        an explicit β_blade_from_axial set to a value far from the
        design flow angle, the incidence loss grows accordingly.
        """
        solver = CentrifugalCompressorMeanline()
        loss = AungierCentrifugal()
        # Auto-derived
        result_auto = solver.solve(_inlet, _rpm, _eckardt_rotor_a_geom(),
                                   loss, AIR)
        # Forced 70° from axial = 20° from tangential — likely a much
        # bigger incidence offset than 3° from the design flow angle
        result_user = solver.solve(
            _inlet, _rpm,
            _eckardt_rotor_a_geom(inducer_tip_blade_metal_rad=math.radians(40.0)),
            loss, AIR)
        # User's choice diverges from flow angle ⇒ bigger ζ_inc
        # (40° blade from axial = 50° from tangential, vs ~18° flow
        # from tangential at design → ~32° incidence).
        assert result_user.loss_breakdown.incidence \
            > result_auto.loss_breakdown.incidence * 5.0
