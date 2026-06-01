"""Independent verification — centrifugal compressor mean-line.

Oracles: efficiency ordering, slip-factor bounds, blade-speed kinematics,
thermodynamic direction of compression, polytropic/isentropic consistency,
and an off-design monotonic trend (pressure ratio rises with speed).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _inputs import CC_GEOMETRY, CC_INLET, CC_OUTLET_RADIUS_M, CC_RPM  # noqa: E402

from cascade.meanline import (  # noqa: E402
    AungierCentrifugal,
    CentrifugalCompressorMeanline,
)
from cascade.meanline.fluid import AIR  # noqa: E402
from cascade.units import Q  # noqa: E402


def _solve(rpm: Q = CC_RPM):  # noqa: ANN202
    return CentrifugalCompressorMeanline().solve(CC_INLET, rpm, CC_GEOMETRY, AungierCentrifugal(), AIR)


def test_design_point_converges() -> None:
    assert _solve().convergence_info["converged"] is True


def test_efficiencies_are_physical_fractions() -> None:
    r = _solve()
    assert 0.0 < r.eta_tt < 1.0
    assert 0.0 < r.eta_ts < 1.0


def test_total_to_static_below_total_to_total() -> None:
    """Impeller exit carries large dynamic head, so eta_ts < eta_tt."""
    assert _solve().eta_ts < _solve().eta_tt


def test_impeller_efficiency_in_reasonable_band() -> None:
    """Impeller-alone total-to-total efficiency runs ~0.85-0.95."""
    assert 0.80 < _solve().eta_tt < 0.95


def test_slip_factor_is_a_physical_fraction() -> None:
    s = _solve().slip_factor
    assert 0.0 < s < 1.0


def test_outlet_blade_speed_equals_omega_times_radius() -> None:
    r = _solve()
    omega = CC_RPM.to("rad/s").magnitude
    assert r.U_2.to("m/s").magnitude == pytest.approx(omega * CC_OUTLET_RADIUS_M, rel=1e-4)


def test_compression_raises_total_pressure_and_temperature() -> None:
    r = _solve()
    assert r.outlet.pressure_total.to("Pa").magnitude > CC_INLET.pressure_total.to("Pa").magnitude
    assert r.outlet.temperature_total.to("K").magnitude > CC_INLET.temperature_total.to("K").magnitude


def test_pressure_ratio_exceeds_unity_and_in_plausible_band() -> None:
    r = _solve()
    assert r.pressure_ratio_tt > 1.0
    assert 1.3 < r.pressure_ratio_tt < 2.6  # Eckardt-class single stage


def test_polytropic_efficiency_consistent_with_compression() -> None:
    """Compressor: eta_poly = ((g-1)/g) ln(P02/P01) / ln(T02/T01); for a real
    machine eta_poly > eta_tt (the small-stage 'preheat' penalty)."""
    r = _solve()
    g = AIR.gamma
    t1 = CC_INLET.temperature_total.to("K").magnitude
    t2 = r.outlet.temperature_total.to("K").magnitude
    p1 = CC_INLET.pressure_total.to("Pa").magnitude
    p2 = r.outlet.pressure_total.to("Pa").magnitude
    eta_poly_expected = (((g - 1.0) / g) * math.log(p2 / p1)) / math.log(t2 / t1)
    assert 0.0 < r.eta_polytropic < 1.0
    assert r.eta_polytropic > r.eta_tt
    assert r.eta_polytropic == pytest.approx(eta_poly_expected, abs=2e-2)


def test_relative_mach_subsonic_for_eckardt_and_within_envelope() -> None:
    r = _solve()
    assert r.max_M_rel < 2.5
    assert r.max_M_rel < 0.95  # Eckardt Rotor A is a subsonic design


def test_pressure_ratio_increases_with_rotational_speed() -> None:
    """Off-design monotonic trend: more tip speed -> more work -> higher PR."""
    low = _solve(Q(11000, "rpm")).pressure_ratio_tt
    mid = _solve(Q(14000, "rpm")).pressure_ratio_tt
    high = _solve(Q(16000, "rpm")).pressure_ratio_tt
    assert low < mid < high
