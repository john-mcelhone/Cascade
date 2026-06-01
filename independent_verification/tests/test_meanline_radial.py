"""Independent verification — radial inflow turbine mean-line.

Oracles: efficiency-definition ordering, blade-speed kinematics (U = omega*r),
thermodynamic direction of an expansion, isentropic/polytropic consistency,
solver determinism, and the documented validity envelope. No Cascade output
value is used to set an expected number.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _inputs import RIT_GEOMETRY, RIT_INLET, RIT_INLET_RADIUS_M, RIT_RPM  # noqa: E402

from cascade.meanline import (  # noqa: E402
    RadialTurbineMeanline,
    RegimeOutOfValidity,
    WhitfieldBainesRadial,
)
from cascade.meanline.fluid import HELIUM  # noqa: E402
from cascade.units import Composition, Port, Q, Species  # noqa: E402


def _solve():  # noqa: ANN202
    return RadialTurbineMeanline().solve(RIT_INLET, RIT_RPM, RIT_GEOMETRY, WhitfieldBainesRadial(), HELIUM)


def test_design_point_converges() -> None:
    assert _solve().convergence_info["converged"] is True


def test_efficiencies_are_physical_fractions() -> None:
    r = _solve()
    assert 0.0 < r.eta_ts < 1.0
    assert 0.0 < r.eta_tt < 1.0


def test_total_to_static_below_total_to_total() -> None:
    """eta_ts charges the exit kinetic energy as a loss, so eta_ts < eta_tt."""
    r = _solve()
    assert r.eta_ts < r.eta_tt


def test_total_to_total_efficiency_below_physical_ceiling() -> None:
    """A real (lossy) rotor cannot reach unity total-to-total efficiency."""
    r = _solve()
    assert r.eta_tt < 0.97


def test_efficiency_in_reasonable_band_for_a_well_designed_rit() -> None:
    """Well-designed radial inflow turbines run eta_ts ~ 0.75-0.90."""
    r = _solve()
    assert 0.65 < r.eta_ts < 0.95


def test_inlet_blade_speed_equals_omega_times_radius() -> None:
    """Pure kinematics: U1 = omega * r1. Catches any rpm<->rad/s unit error."""
    r = _solve()
    omega = RIT_RPM.to("rad/s").magnitude
    assert r.U_1.to("m/s").magnitude == pytest.approx(omega * RIT_INLET_RADIUS_M, rel=1e-4)


def test_expansion_reduces_total_pressure_and_temperature() -> None:
    r = _solve()
    assert r.outlet.pressure_total.to("Pa").magnitude < RIT_INLET.pressure_total.to("Pa").magnitude
    assert r.outlet.temperature_total.to("K").magnitude < RIT_INLET.temperature_total.to("K").magnitude


def test_power_extraction_positive_and_in_class_band() -> None:
    r = _solve()
    p_w = r.power_W.to("W").magnitude
    assert p_w > 0
    assert 5e3 < p_w < 5e5  # Whitney-Stewart-class machine


def test_pressure_ratio_total_to_static_exceeds_unity() -> None:
    assert _solve().pressure_ratio_ts > 1.0


def test_polytropic_efficiency_consistent_with_expansion() -> None:
    """For a turbine, eta_poly = ln(T02/T01) / [((g-1)/g) ln(P02/P01)],
    and for a lossy machine eta_poly must be < 1 and < eta_tt.
    A reported eta_poly of exactly 1.0 while eta_tt < 1 is unphysical."""
    r = _solve()
    g = HELIUM.gamma
    t1 = RIT_INLET.temperature_total.to("K").magnitude
    t2 = r.outlet.temperature_total.to("K").magnitude
    p1 = RIT_INLET.pressure_total.to("Pa").magnitude
    p2 = r.outlet.pressure_total.to("Pa").magnitude
    eta_poly_expected = math.log(t2 / t1) / (((g - 1.0) / g) * math.log(p2 / p1))
    assert 0.0 < r.eta_polytropic < 1.0
    assert r.eta_polytropic < r.eta_tt
    assert r.eta_polytropic == pytest.approx(eta_poly_expected, abs=2e-2)


def test_relative_mach_within_validity_envelope() -> None:
    """A converged mean-line result must satisfy M_rel <= 2.5 (SPEC validity)."""
    r = _solve()
    assert r.max_M_rel < 2.5


def test_solver_is_deterministic() -> None:
    a, b = _solve(), _solve()
    assert a.eta_ts == b.eta_ts
    assert a.pressure_ratio_ts == b.pressure_ratio_ts


def test_extreme_speed_is_refused_not_silently_extrapolated() -> None:
    """Driving the rotor far past its envelope must raise, not return garbage."""
    geo = RIT_GEOMETRY
    hot = Port(pressure_total=Q(400000, "Pa"), temperature_total=Q(1200, "K"),
               mass_flow=Q(0.3, "kg/s"), composition=Composition.air())
    with pytest.raises((RegimeOutOfValidity, ValueError)):
        RadialTurbineMeanline().solve(hot, Q(300000, "rpm"), geo, WhitfieldBainesRadial())
