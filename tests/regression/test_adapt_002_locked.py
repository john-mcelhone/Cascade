"""ADAPT-002 locked regression: API 684 separation-margin table.

This test will FAIL if the pre-ADAPT-002 formula is restored (which
capped required SM at 15% for AF >= 5, under-reporting by 6-11 pt).

Locked invariants (API 684 2nd ed. §2.7.1.7 Figure 2-8):
  - AF = 10.0  →  SM_min = 26%  (old code returned 15%)
  - AF = 3.55  →  SM_min = 5%
  - AF <= 2.5  →  SM_min = 0%

References:
- API Std 684, 2nd ed. (2019), §2.7.1.7, Figure 2-8.
- ADAPT-002 (regression lock).
"""

from __future__ import annotations

import pytest

from cascade.rotor.unbalance_response import api684_required_separation_margin_percent


def test_adapt_002_af10_returns_26_percent() -> None:
    """Locked: AF=10 must return 26%, not the old broken 15%.

    This is the primary regression guard for ADAPT-002. If the old
    under-reporting formula is restored, this test fails immediately.
    """
    sm = api684_required_separation_margin_percent(10.0)
    assert abs(sm - 26.0) < 0.5, (
        f"AF=10: expected 26% (API 684 Figure 2-8); got {sm:.2f}%. "
        f"ADAPT-002 regression: old code returned 15% here."
    )


def test_adapt_002_af3p55_returns_5_percent() -> None:
    """Locked: AF=3.55 must return 5% per API 684 Figure 2-8."""
    sm = api684_required_separation_margin_percent(3.55)
    assert abs(sm - 5.0) < 0.5, (
        f"AF=3.55: expected 5% (API 684 Figure 2-8); got {sm:.2f}%. "
        f"ADAPT-002 regression."
    )


def test_adapt_002_af8_returns_16_percent() -> None:
    """Locked: AF=8 must return 16%, not the old broken 15%."""
    sm = api684_required_separation_margin_percent(8.0)
    assert abs(sm - 16.0) < 0.5, (
        f"AF=8: expected 16% (API 684 Figure 2-8); got {sm:.2f}%. "
        f"ADAPT-002 regression: old code used a simpler formula that returned ~15% here."
    )


def test_adapt_002_old_15_percent_cap_is_gone() -> None:
    """Locked: the old 15% cap must not be present.

    The old (broken) implementation saturated the required SM at 15%
    for AF > some threshold, under-reporting by 6-11 pt at AF=8-10.
    AF=10 must now return > 15%.
    """
    sm_at_10 = api684_required_separation_margin_percent(10.0)
    assert sm_at_10 > 15.0, (
        f"ADAPT-002 regression: SM at AF=10 is {sm_at_10:.2f}%, which is "
        f"<= the old broken 15% cap. API 684 requires 26%."
    )
    sm_at_8 = api684_required_separation_margin_percent(8.0)
    assert sm_at_8 > 15.0, (
        f"ADAPT-002 regression: SM at AF=8 is {sm_at_8:.2f}%, which is "
        f"<= the old broken 15% cap. API 684 requires 16%."
    )


@pytest.mark.parametrize("af,expected", [
    (2.5, 0.0),
    (3.55, 5.0),
    (5.0, 10.0),
    (8.0, 16.0),
    (10.0, 26.0),
])
def test_adapt_002_table_points(af: float, expected: float) -> None:
    """Locked: all API 684 Figure 2-8 break-points return correct SM."""
    got = api684_required_separation_margin_percent(af)
    assert abs(got - expected) <= 0.5, (
        f"AF={af}: expected {expected}%, got {got:.2f}%. "
        f"API 684 2nd ed. §2.7.1.7 Figure 2-8. ADAPT-002."
    )
