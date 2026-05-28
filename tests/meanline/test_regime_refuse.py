"""SPEC_SHEET §13: the solver must raise `RegimeOutOfValidity` (not
silently extrapolate) when the computed regime exceeds the loss model's
documented envelope. For radial machines the global limit is
relative Mach M_W > 2.5.

This test constructs an operating point that forces M_rel > 2.5 and
asserts that the exception is raised, with the correct cause-code
attribute attached.
"""

from __future__ import annotations

import math

import pytest

from cascade.meanline import (
    AungierCentrifugal,
    CentrifugalCompressorGeometry,
    CentrifugalCompressorMeanline,
    RadialTurbineGeometry,
    RadialTurbineMeanline,
    RegimeOutOfValidity,
    WhitfieldBainesRadial,
    WiesnerSlip,
)
from cascade.meanline.exceptions import MeanlineError
from cascade.units import Composition, Port, Q, Species


class TestRefuseSupersonicRadialTurbine:
    def test_extreme_rpm_triggers_refusal(self) -> None:
        """Driving a radial turbine at extreme tip speed pushes the
        absolute and relative Mach numbers high. At sufficiently high RPM
        the relative Mach at the rotor inlet exceeds 2.5.

        Construction: a small RIT at very high RPM so U₁ > a₁.
        """
        from cascade.meanline.fluid import AIR
        geom = RadialTurbineGeometry(
            rotor_inlet_radius=0.10,  # large enough to make U high
            rotor_outlet_radius_hub=0.02,
            rotor_outlet_radius_tip=0.05,
            blade_height_inlet=0.020,
            blade_height_outlet=0.030,
            blade_count=12,
            inlet_metal_angle_rad=0.0,
            exducer_angle_rad=math.radians(60),
            tip_clearance=0.0003,
        )
        # 200,000 rpm + 100mm radius → U₁ = 2094 m/s. Speed of sound in
        # air at 800 K ≈ 567 m/s → M_rel ≈ 3.7 > 2.5. Triggers refusal.
        inlet = Port(
            pressure_total=Q(500000, "Pa"),
            temperature_total=Q(800.0, "K"),
            mass_flow=Q(0.5, "kg/s"),
            composition=Composition.air(),
        )
        solver = RadialTurbineMeanline()
        loss = WhitfieldBainesRadial()
        with pytest.raises(RegimeOutOfValidity) as exc_info:
            solver.solve(inlet, Q(200000, "rpm"), geom, loss, AIR)

        # Verify cause-code (SPEC §13 contract)
        err = exc_info.value
        assert err.cause_code == "REGIME_OUT_OF_VALIDITY"
        # M_rel must be > 2.5
        assert err.regime_variable in ("M_rel", "T_1", "T_2")
        if err.regime_variable == "M_rel":
            assert err.value > 2.5
            assert err.limit == pytest.approx(2.5)

    def test_normal_operating_point_does_not_refuse(self) -> None:
        """A reasonable RIT operating point must not trigger refusal."""
        from cascade.meanline.fluid import AIR
        geom = RadialTurbineGeometry(
            rotor_inlet_radius=0.05,
            rotor_outlet_radius_hub=0.01,
            rotor_outlet_radius_tip=0.025,
            blade_height_inlet=0.008,
            blade_height_outlet=0.015,
            blade_count=12,
            inlet_metal_angle_rad=0.0,
            exducer_angle_rad=math.radians(60),
            tip_clearance=0.0001,
        )
        inlet = Port(
            pressure_total=Q(300000, "Pa"),
            temperature_total=Q(1000.0, "K"),
            mass_flow=Q(0.1, "kg/s"),
            composition=Composition.air(),
        )
        solver = RadialTurbineMeanline()
        loss = WhitfieldBainesRadial()
        result = solver.solve(inlet, Q(60000, "rpm"), geom, loss, AIR)
        assert result.max_M_rel < 2.5


class TestRefuseSupersonicCentrifugal:
    def test_extreme_rpm_triggers_refusal(self) -> None:
        """Centrifugal at extreme RPM → supersonic inducer."""
        from cascade.meanline.fluid import AIR
        geom = CentrifugalCompressorGeometry(
            inducer_hub_radius=0.030,
            inducer_tip_radius=0.150,  # large inducer
            impeller_outlet_radius=0.25,
            blade_height_outlet=0.020,
            blade_count=20,
            beta_2_metal_rad=math.pi / 6,  # 30° back-sweep
            tip_clearance=0.0003,
        )
        # 100,000 rpm + r₁_tip = 150 mm → U₁_tip = 1571 m/s. Air at 288 K
        # has a = 340 m/s → W_tip ≈ 1602 m/s → M_rel = 4.7. Triggers refusal.
        inlet = Port(
            pressure_total=Q(101325, "Pa"),
            temperature_total=Q(288.0, "K"),
            mass_flow=Q(5.0, "kg/s"),
            composition=Composition.air(),
        )
        solver = CentrifugalCompressorMeanline()
        loss = AungierCentrifugal()
        with pytest.raises(RegimeOutOfValidity) as exc_info:
            solver.solve(inlet, Q(100000, "rpm"), geom, loss, AIR)
        err = exc_info.value
        assert err.cause_code == "REGIME_OUT_OF_VALIDITY"


class TestRefuseAttributes:
    def test_exception_message_includes_regime_variable(self) -> None:
        """The exception message must name the offending regime variable
        (per SPEC_SHEET §13 'with cause code')."""
        err = RegimeOutOfValidity("dummy", regime_variable="M_rel",
                                  value=3.7, limit=2.5)
        assert err.regime_variable == "M_rel"
        assert err.value == 3.7
        assert err.limit == 2.5
        assert err.cause_code == "REGIME_OUT_OF_VALIDITY"

    def test_exception_is_meanline_error(self) -> None:
        """RegimeOutOfValidity is a MeanlineError subclass."""
        err = RegimeOutOfValidity("dummy")
        assert isinstance(err, MeanlineError)
        assert isinstance(err, Exception)
