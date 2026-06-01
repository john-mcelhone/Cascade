"""Independent verification — units engine.

Oracles are NIST/SI exact definitions:
  1 atm = 101325 Pa, 1 bar = 1e5 Pa, 0 degC = 273.15 K, 1 ft = 0.3048 m,
  1 in = 0.0254 m, 1 hp ~ 745.70 W. Conversions must round-trip to machine
  precision, dimensionless ratios must be exact, and silent dimensional
  mismatches must be refused.
"""

from __future__ import annotations

import math

import pytest

from cascade.units import Composition, Port, Q


def test_pressure_round_trip_to_machine_precision() -> None:
    assert Q(1.0, "psi").to("Pa").to("psi").magnitude == pytest.approx(1.0, abs=1e-12)


def test_standard_atmosphere_exact() -> None:
    assert Q(1.0, "atm").to("Pa").magnitude == pytest.approx(101325.0, rel=1e-9)


def test_bar_exact() -> None:
    assert Q(1.0, "bar").to("Pa").magnitude == pytest.approx(1.0e5, rel=1e-12)


def test_celsius_to_kelvin_offset() -> None:
    assert Q(0.0, "degC").to("K").magnitude == pytest.approx(273.15, abs=1e-9)
    assert Q(100.0, "degC").to("K").magnitude == pytest.approx(373.15, abs=1e-9)


def test_length_conversions_exact() -> None:
    assert Q(1.0, "ft").to("m").magnitude == pytest.approx(0.3048, rel=1e-9)
    assert Q(1.0, "inch").to("m").magnitude == pytest.approx(0.0254, rel=1e-9)


def test_horsepower_to_watt() -> None:
    assert Q(1.0, "hp").to("W").magnitude == pytest.approx(745.7, abs=0.5)


def test_dimensionless_pressure_ratio_is_exact() -> None:
    ratio = (Q(8.0, "bar") / Q(2.0, "bar")).to("dimensionless").magnitude
    assert ratio == pytest.approx(4.0, rel=1e-12)


def test_energy_power_time_consistency() -> None:
    assert (Q(1.0, "W") * Q(1.0, "s")).to("J").magnitude == pytest.approx(1.0, rel=1e-12)


def test_port_refuses_dimensionally_wrong_inputs() -> None:
    """A Port must not silently accept a temperature where a pressure goes."""
    with pytest.raises(Exception):  # noqa: B017, PT011
        Port(
            pressure_total=Q(300.0, "K"),       # wrong dimension
            temperature_total=Q(300.0, "K"),
            mass_flow=Q(1.0, "kg/s"),
            composition=Composition.air(),
        )


def test_valid_port_accepts_correct_dimensions() -> None:
    p = Port(pressure_total=Q(101325.0, "Pa"), temperature_total=Q(288.15, "K"),
             mass_flow=Q(1.0, "kg/s"), composition=Composition.air())
    assert p.pressure_total.to("kPa").magnitude == pytest.approx(101.325, rel=1e-9)
