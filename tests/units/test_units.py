"""Unit tests for the cascade.units module — the canonical interface every
other module imports. Per SPEC_SHEET.md §17, these are part of the v1
green-light criteria (interfaces round-trip cleanly).
"""

from __future__ import annotations

import math

import pytest

from cascade.units import (
    Composition,
    LumpedDisk,
    Port,
    Q,
    RotorSection,
    RotorShape,
    Species,
    deg_from_tangential_to_rad_from_axial,
    port_residual_norm,
    rad_from_axial_to_deg_from_tangential,
)


class TestQuantity:
    def test_construct_pressure(self) -> None:
        p = Q(206.770, "kPa")
        assert p.to("Pa").magnitude == pytest.approx(206770.0)

    def test_construct_temperature(self) -> None:
        t = Q(530.0, "K")
        assert t.magnitude == 530.0

    def test_si_round_trip(self) -> None:
        # The canonical NIST SP 811 round-trip: 1 psi → Pa → psi.
        psi = Q(1.0, "psi")
        pa = psi.to("Pa")
        back = pa.to("psi")
        assert back.magnitude == pytest.approx(1.0, rel=1e-12)

    def test_dimensional_failure(self) -> None:
        # Pint refuses incompatible operations
        with pytest.raises(Exception):  # noqa: B017
            _ = Q(1.0, "kg") + Q(1.0, "m")


class TestSpecies:
    def test_molar_masses(self) -> None:
        assert Species.N2.molar_mass_g_per_mol == pytest.approx(28.0134, abs=1e-3)
        assert Species.O2.molar_mass_g_per_mol == pytest.approx(31.9988, abs=1e-3)
        assert Species.H2O.molar_mass_g_per_mol == pytest.approx(18.01528, abs=1e-3)


class TestComposition:
    def test_air_mean_molar_mass(self) -> None:
        air = Composition.air()
        # Standard dry-air mean molar mass ≈ 28.965 g/mol
        assert air.mean_molar_mass_g_per_mol == pytest.approx(28.965, rel=2e-3)

    def test_pure_argon(self) -> None:
        ar = Composition.pure(Species.AR)
        assert ar.mean_molar_mass_g_per_mol == pytest.approx(39.948, abs=1e-3)

    def test_refuses_non_normalized(self) -> None:
        with pytest.raises(ValueError, match="sum to 1.0"):
            _ = Composition(mass_fractions={Species.N2: 0.5})

    def test_get_default(self) -> None:
        air = Composition.air()
        assert air.get(Species.CO) == 0.0
        assert air.get(Species.N2) > 0.7


class TestPort:
    def test_valid_construction(self) -> None:
        port = Port(
            pressure_total=Q(206.770, "kPa"),
            temperature_total=Q(530.0, "K"),
            mass_flow=Q(6.66537, "kg/s"),
            composition=Composition.air(),
        )
        # Defaults
        assert port.rotational_speed.to("rad/s").magnitude == 0.0
        assert port.swirl_ratio == 0.0

    def test_dimension_error_on_pressure(self) -> None:
        with pytest.raises(TypeError, match="pressure_total expected"):
            _ = Port(
                pressure_total=Q(206.770, "kg"),  # wrong dimension
                temperature_total=Q(530.0, "K"),
                mass_flow=Q(6.66537, "kg/s"),
                composition=Composition.air(),
            )

    def test_dimension_error_on_temperature(self) -> None:
        with pytest.raises(TypeError, match="temperature_total expected"):
            _ = Port(
                pressure_total=Q(206.770, "kPa"),
                temperature_total=Q(530.0, "m"),  # wrong dimension
                mass_flow=Q(6.66537, "kg/s"),
                composition=Composition.air(),
            )

    def test_refuses_zero_pressure(self) -> None:
        with pytest.raises(ValueError, match="must be > 0 Pa"):
            _ = Port(
                pressure_total=Q(0.0, "Pa"),
                temperature_total=Q(530.0, "K"),
                mass_flow=Q(6.66537, "kg/s"),
                composition=Composition.air(),
            )

    def test_si_tuple(self) -> None:
        port = Port(
            pressure_total=Q(206.770, "kPa"),
            temperature_total=Q(530.0, "K"),
            mass_flow=Q(6.66537, "kg/s"),
            composition=Composition.air(),
        )
        p, t, m, w, s = port.to_si_tuple()
        assert p == pytest.approx(206770.0)
        assert t == pytest.approx(530.0)
        assert m == pytest.approx(6.66537)
        assert w == 0.0
        assert s == 0.0


class TestPortResidualNorm:
    """Canonical co-simulation criterion per SPEC_SHEET §3.3."""

    def _design_port(self) -> Port:
        return Port(
            pressure_total=Q(200.0, "kPa"),
            temperature_total=Q(500.0, "K"),
            mass_flow=Q(1.0, "kg/s"),
            composition=Composition.air(),
        )

    def test_identical_ports_zero_residual(self) -> None:
        p = self._design_port()
        norm = port_residual_norm([p], [p], [p])
        assert norm == pytest.approx(0.0, abs=1e-15)

    def test_one_percent_pressure_mismatch(self) -> None:
        design = self._design_port()
        a = design
        b = Port(
            pressure_total=Q(202.0, "kPa"),  # +1%
            temperature_total=Q(500.0, "K"),
            mass_flow=Q(1.0, "kg/s"),
            composition=Composition.air(),
        )
        norm = port_residual_norm([a], [b], [design])
        # Single delta of 0.01 (1% of design) → L2 norm = 0.01
        assert norm == pytest.approx(0.01, abs=1e-10)

    def test_unequal_lengths_raises(self) -> None:
        p = self._design_port()
        with pytest.raises(ValueError, match="equal-length lists"):
            port_residual_norm([p, p], [p], [p])

    def test_convergence_at_1e_minus_4(self) -> None:
        """The canonical default co-sim tolerance from SPEC_SHEET §3.3."""
        design = self._design_port()
        a = design
        # Construct a port with deltas just under 1e-4 in each of 5 components
        # 5 deltas of 2e-5 → norm = sqrt(5)*2e-5 ≈ 4.47e-5 < 1e-4
        eps = 2e-5
        b = Port(
            pressure_total=Q(200.0 * (1 + eps), "kPa"),
            temperature_total=Q(500.0 * (1 + eps), "K"),
            mass_flow=Q(1.0 * (1 + eps), "kg/s"),
            composition=Composition.air(),
        )
        norm = port_residual_norm([a], [b], [design])
        assert norm < 1e-4


class TestAngleConvention:
    """SPEC_SHEET §3.2: closes SR-001.

    The legacy tool convention is degrees from tangential. Cascade's
    canonical store is radians from axial.
    """

    def test_90_deg_tangential_is_zero_axial(self) -> None:
        # Pure radial inflow (the typical RIT inlet): 90° from tangential = 0 rad from axial
        assert deg_from_tangential_to_rad_from_axial(90.0) == pytest.approx(0.0, abs=1e-12)

    def test_0_deg_tangential_is_half_pi_axial(self) -> None:
        # Pure tangential flow: 0° from tangential = π/2 rad from axial
        assert deg_from_tangential_to_rad_from_axial(0.0) == pytest.approx(math.pi / 2, abs=1e-12)

    def test_round_trip(self) -> None:
        for angle_deg in (0.0, 30.0, 45.0, 60.0, 90.0, 135.0):
            rad = deg_from_tangential_to_rad_from_axial(angle_deg)
            back = rad_from_axial_to_deg_from_tangential(rad)
            assert back == pytest.approx(angle_deg, abs=1e-10)


class TestRotorShape:
    def test_construct_simple_shaft(self) -> None:
        s1 = RotorSection(
            diameter_outer=Q(50.0, "mm"),
            diameter_inner=Q(0.0, "mm"),
            length=Q(100.0, "mm"),
            density=Q(7800.0, "kg/m^3"),
            axial_position=Q(0.0, "mm"),
            material="STEEL_AISI4340",
        )
        d1 = LumpedDisk(
            mass=Q(0.5, "kg"),
            inertia_polar=Q(1.0e-4, "kg * m^2"),
            inertia_diametrical=Q(5.0e-5, "kg * m^2"),
            axial_position=Q(50.0, "mm"),
        )
        shape = RotorShape(sections=[s1], disks=[d1])
        assert shape.length_total.to("mm").magnitude == pytest.approx(100.0)
        # section mass = pi/4 * (0.05^2 - 0^2) * 0.1 * 7800 = 1.531 kg ; total = 2.031
        assert shape.mass_total.to("kg").magnitude == pytest.approx(2.031, abs=0.01)

    def test_section_refuses_inner_greater_than_outer(self) -> None:
        with pytest.raises(ValueError, match="not exceed diameter_outer"):
            _ = RotorSection(
                diameter_outer=Q(50.0, "mm"),
                diameter_inner=Q(60.0, "mm"),
                length=Q(100.0, "mm"),
                density=Q(7800.0, "kg/m^3"),
                axial_position=Q(0.0, "mm"),
                material="STEEL",
            )

    def test_section_refuses_zero_length(self) -> None:
        with pytest.raises(ValueError, match="length must be > 0"):
            _ = RotorSection(
                diameter_outer=Q(50.0, "mm"),
                diameter_inner=Q(0.0, "mm"),
                length=Q(0.0, "mm"),
                density=Q(7800.0, "kg/m^3"),
                axial_position=Q(0.0, "mm"),
                material="STEEL",
            )

    def test_disk_refuses_dimension_error(self) -> None:
        with pytest.raises(TypeError, match="inertia_polar expected"):
            _ = LumpedDisk(
                mass=Q(0.5, "kg"),
                inertia_polar=Q(1.0, "kg * m"),  # wrong dimension
                inertia_diametrical=Q(5.0e-5, "kg * m^2"),
                axial_position=Q(50.0, "mm"),
            )
