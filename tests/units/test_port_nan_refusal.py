"""Regression tests for ADAPT-026 — Port must refuse NaN / ±Inf physical
quantities.

The original ``Port.__post_init__`` guarded with ``if x.magnitude <= 0:``,
which silently lets ``NaN`` through (NaN is neither ``<= 0`` nor ``> 0``).
That contaminates every downstream solver (residual norms, Mach
calculations, etc.) with NaN poison. The fix requires ``math.isfinite``
on every Port quantity that must be a real number.

See also: ADAPT-026.
"""

from __future__ import annotations

import math

import pytest

from cascade.units import Composition, Port, Q


def _valid_port_kwargs() -> dict:
    """A baseline of valid arguments — tests override individual fields."""
    return {
        "pressure_total": Q(206.770, "kPa"),
        "temperature_total": Q(530.0, "K"),
        "mass_flow": Q(6.66537, "kg/s"),
        "composition": Composition.air(),
    }


class TestPortRefusesNaN:
    """A valid Port should construct fine; NaN/Inf in any physical quantity
    must raise ValueError immediately at construction.

    The pre-fix bug: ``NaN <= 0`` is ``False`` AND ``NaN > 0`` is ``False``,
    so a guard of the form ``if x <= 0: raise`` silently lets NaN pass.
    """

    def test_baseline_valid_port_constructs(self) -> None:
        # Sanity: the baseline kwargs construct without complaint.
        p = Port(**_valid_port_kwargs())
        assert p.pressure_total.to("Pa").magnitude == pytest.approx(206_770.0)

    def test_refuses_nan_pressure(self) -> None:
        kw = _valid_port_kwargs()
        kw["pressure_total"] = Q(float("nan"), "Pa")
        with pytest.raises(ValueError, match=r"pressure_total.*finite"):
            _ = Port(**kw)

    def test_refuses_positive_inf_pressure(self) -> None:
        kw = _valid_port_kwargs()
        kw["pressure_total"] = Q(float("inf"), "Pa")
        with pytest.raises(ValueError, match=r"pressure_total.*finite"):
            _ = Port(**kw)

    def test_refuses_negative_inf_pressure(self) -> None:
        kw = _valid_port_kwargs()
        kw["pressure_total"] = Q(float("-inf"), "Pa")
        with pytest.raises(ValueError, match=r"pressure_total.*finite"):
            _ = Port(**kw)

    def test_refuses_nan_temperature(self) -> None:
        kw = _valid_port_kwargs()
        kw["temperature_total"] = Q(float("nan"), "K")
        with pytest.raises(ValueError, match=r"temperature_total.*finite"):
            _ = Port(**kw)

    def test_refuses_inf_temperature(self) -> None:
        kw = _valid_port_kwargs()
        kw["temperature_total"] = Q(float("inf"), "K")
        with pytest.raises(ValueError, match=r"temperature_total.*finite"):
            _ = Port(**kw)

    def test_refuses_nan_mass_flow(self) -> None:
        # mass_flow is signed (positive=downstream) so only finite is required.
        kw = _valid_port_kwargs()
        kw["mass_flow"] = Q(float("nan"), "kg/s")
        with pytest.raises(ValueError, match=r"mass_flow.*finite"):
            _ = Port(**kw)

    def test_refuses_inf_mass_flow(self) -> None:
        kw = _valid_port_kwargs()
        kw["mass_flow"] = Q(float("inf"), "kg/s")
        with pytest.raises(ValueError, match=r"mass_flow.*finite"):
            _ = Port(**kw)

    def test_refuses_nan_rotational_speed(self) -> None:
        kw = _valid_port_kwargs()
        kw["rotational_speed"] = Q(float("nan"), "rad/s")
        with pytest.raises(ValueError, match=r"rotational_speed.*finite"):
            _ = Port(**kw)

    def test_refuses_nan_velocity_meridional(self) -> None:
        kw = _valid_port_kwargs()
        kw["velocity_meridional"] = Q(float("nan"), "m/s")
        with pytest.raises(ValueError, match=r"velocity_meridional.*finite"):
            _ = Port(**kw)

    def test_refuses_nan_radius_mean(self) -> None:
        kw = _valid_port_kwargs()
        kw["radius_mean"] = Q(float("nan"), "m")
        with pytest.raises(ValueError, match=r"radius_mean.*finite"):
            _ = Port(**kw)

    def test_refuses_nan_swirl_ratio(self) -> None:
        kw = _valid_port_kwargs()
        kw["swirl_ratio"] = float("nan")
        with pytest.raises(ValueError, match=r"swirl_ratio.*finite"):
            _ = Port(**kw)

    def test_zero_pressure_still_refused(self) -> None:
        # The pre-existing > 0 guard must remain active after the NaN fix.
        kw = _valid_port_kwargs()
        kw["pressure_total"] = Q(0.0, "Pa")
        with pytest.raises(ValueError, match=r"must be > 0 Pa"):
            _ = Port(**kw)

    def test_negative_temperature_still_refused(self) -> None:
        kw = _valid_port_kwargs()
        kw["temperature_total"] = Q(-1.0, "K")
        with pytest.raises(ValueError, match=r"must be > 0 K"):
            _ = Port(**kw)

    def test_finite_values_in_alternate_units_accepted(self) -> None:
        # Final guard: the validator must not over-reject finite quantities
        # given in non-SI units.
        p = Port(
            pressure_total=Q(30.0, "psi"),
            temperature_total=Q(540.0, "degR"),
            mass_flow=Q(1.0, "lb/s"),
            composition=Composition.air(),
        )
        assert math.isfinite(p.pressure_total.to("Pa").magnitude)
        assert math.isfinite(p.temperature_total.to("K").magnitude)
