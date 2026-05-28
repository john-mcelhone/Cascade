"""ADAPT-002: API 684 §2.7.1.7 separation-margin regression test.

API Std 684, 2nd ed. (2019), §2.7.1.7 Figure 2-8 prescribes the minimum
required separation margin from a critical speed as a function of the
amplification factor AF (= Q):

    AF <= 2.5: SM_min = 0
    AF = 3.55: SM_min = 5%
    AF = 5:    SM_min = 10%
    AF = 8:    SM_min = 16%
    AF = 10:   SM_min = 26%
    AF >= 10:  SM_min = 26% (saturates)

Prior versions of Cascade capped SM_min at 15 % for AF >= 5, under-reporting
the required margin by 6-11 percentage points at the design points typical
of 90 kRPM single-stage radial machines. This test guards against
regression to the under-reporting formula.

References:
- API Std 684, 2nd ed. (2019), §2.7.1.7, Figure 2-8.
- API Std 617, 8th ed. (2014), §2.6.2 (defers to API 684 for SM schedule).
"""

from __future__ import annotations

import pytest

from cascade.rotor.unbalance_response import (
    _api684_separation_margin_percent,
    api684_required_separation_margin_percent,
)


@pytest.mark.parametrize(
    ("af", "expected_sm_pct"),
    [
        (0.5, 0.0),
        (1.0, 0.0),
        (2.0, 0.0),
        (2.5, 0.0),
        (3.55, 5.0),
        (5.0, 10.0),
        (8.0, 16.0),
        (10.0, 26.0),
        (12.0, 26.0),
        (15.0, 26.0),
        (100.0, 26.0),
    ],
)
def test_api684_required_sm_at_table_points(af: float, expected_sm_pct: float) -> None:
    """At the API 684 Figure 2-8 break-points, the required SM matches the
    published table within 0.5 percentage points."""
    got = api684_required_separation_margin_percent(af)
    assert abs(got - expected_sm_pct) <= 0.5, (
        f"AF={af}: expected SM_min={expected_sm_pct}%, got {got:.2f}%. "
        f"API 684 2nd ed. §2.7.1.7 Figure 2-8."
    )


@pytest.mark.parametrize(
    ("af",),
    [(3.0,), (4.0,), (6.0,), (7.0,), (9.0,), (9.5,)],
)
def test_api684_required_sm_monotone(af: float) -> None:
    """Between break-points the schedule is monotone non-decreasing in AF."""
    sm_here = api684_required_separation_margin_percent(af)
    sm_lower = api684_required_separation_margin_percent(af - 0.1)
    sm_higher = api684_required_separation_margin_percent(af + 0.1)
    assert sm_lower <= sm_here + 1e-9, (
        f"SM at AF={af-0.1} ({sm_lower}) must be <= SM at AF={af} ({sm_here})"
    )
    assert sm_here <= sm_higher + 1e-9, (
        f"SM at AF={af} ({sm_here}) must be <= SM at AF={af+0.1} ({sm_higher})"
    )


def test_actual_sm_geometric_formula() -> None:
    """The *actual* (geometric) SM is |N - N_c| / N * 100 per the
    definition in API 684 §2.7."""
    # Operating at 20000 rpm; critical at 14000 rpm => actual SM = 30 %.
    sm = _api684_separation_margin_percent(
        amplification_factor=8.0,
        operating_speed_rpm=20000.0,
        critical_speed_rpm=14000.0,
    )
    assert abs(sm - 30.0) < 1e-9, f"Expected 30% actual SM; got {sm}"


def test_actual_sm_handles_zero_operating_speed() -> None:
    """Zero operating speed returns 0 (avoid division by zero)."""
    sm = _api684_separation_margin_percent(
        amplification_factor=10.0,
        operating_speed_rpm=0.0,
        critical_speed_rpm=14000.0,
    )
    assert sm == 0.0


def test_af_below_threshold_returns_zero_even_at_high_response() -> None:
    """For AF < 2.5 the rotor is considered critically damped and no
    separation margin is required (API 684 §2.6.2.6 / §2.7.1.7)."""
    assert api684_required_separation_margin_percent(0.0) == 0.0
    assert api684_required_separation_margin_percent(1.0) == 0.0
    assert api684_required_separation_margin_percent(2.499) == 0.0


def test_af_at_or_above_ten_saturates_at_26_percent() -> None:
    """At AF >= 10 the schedule saturates at 26 % (Figure 2-8 plateau)."""
    for af in [10.0, 15.0, 20.0, 50.0, 100.0]:
        sm = api684_required_separation_margin_percent(af)
        assert abs(sm - 26.0) < 1e-9, f"AF={af}: expected 26%, got {sm}"


def test_regression_old_15_percent_cap_is_gone() -> None:
    """Regression guard: the OLD implementation capped at 15 %.

    A non-trivial value above 15 % is now returned for AF=8 and AF=10,
    confirming the new schedule replaced the under-reporting formula.
    """
    sm8 = api684_required_separation_margin_percent(8.0)
    sm10 = api684_required_separation_margin_percent(10.0)
    assert sm8 > 15.0, (
        f"AF=8 used to return 15 % under the old (broken) formula; "
        f"correct API 684 value is 16 %. Got {sm8}"
    )
    assert sm10 > 15.0, (
        f"AF=10 used to return 15 % under the old (broken) formula; "
        f"correct API 684 value is 26 %. Got {sm10}"
    )
