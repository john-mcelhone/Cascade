"""SPEC_SHEET §15 / SR-flagged Kzz = 3.8e14 N/m unit-display bug guard.

The legacy tool reported a Kzz = 3.801200e14 N/m bearing stiffness at
Omega = 0. Six orders of magnitude above the high-end
of any real bearing, this is the canonical
unit-display bug we are required to guard against.

This test exercises SPEC_SHEET §17 acceptance criterion (3): every refusal
in §13/§15 is exercised by at least one test.

ADAPT-037: this test exercises the API-684-compliant field names
(``K_yy`` / ``K_zz`` -- with x reserved for axial). Legacy ``K_xx`` calls
also still trip the refusal via the deprecation shim.
"""

from __future__ import annotations

import pytest

from cascade.rotor import LinearBearing, TabulatedBearing
from cascade.units import Q


class TestKzzRefusal:
    def test_linear_bearing_with_3p8e14_refused(self) -> None:
        """LinearBearing with K_yy = 3.8e14 N/m is refused at construction."""
        with pytest.raises(ValueError, match="IMPLAUSIBLE_BEARING_STIFFNESS"):
            LinearBearing(
                name="bad",
                axial_position=Q(0.0, "m"),
                K_yy=Q(3.8e14, "N/m"),
            )

    def test_linear_bearing_at_exactly_1e10_accepted(self) -> None:
        """1e10 N/m is the v1 hard limit; values at or just below are accepted."""
        b = LinearBearing(
            name="rigid_asymptote",
            axial_position=Q(0.0, "m"),
            K_yy=Q(1.0e10, "N/m"),
            K_zz=Q(1.0e10, "N/m"),
        )
        K, _ = b.coefficients_at_rpm(0.0)
        assert K[0, 0] == pytest.approx(1.0e10)

    def test_linear_bearing_just_above_1e10_refused(self) -> None:
        """Just above the hard limit fails."""
        with pytest.raises(ValueError, match="IMPLAUSIBLE_BEARING_STIFFNESS"):
            LinearBearing(
                name="too_stiff",
                axial_position=Q(0.0, "m"),
                K_yy=Q(1.1e10, "N/m"),
            )

    def test_tabulated_bearing_with_one_row_above_limit_refused(self) -> None:
        """A tabulated bearing whose K_table has any row above 1e10 N/m is refused."""
        import numpy as np

        K_table = [
            np.array([[1.0e7, 0.0], [0.0, 1.0e7]]),
            np.array([[1.0e7, 0.0], [0.0, 3.8e14]]),  # bad row
        ]
        C_table = [
            np.array([[1.0e3, 0.0], [0.0, 1.0e3]]),
            np.array([[1.0e3, 0.0], [0.0, 1.0e3]]),
        ]
        with pytest.raises(ValueError, match="IMPLAUSIBLE_BEARING_STIFFNESS"):
            TabulatedBearing(
                name="bad_table",
                axial_position=Q(0.0, "m"),
                rpm_table=[Q(1000.0, "rpm"), Q(10000.0, "rpm")],
                K_table=K_table,
                C_table=C_table,
            )

    def test_negative_stiffness_via_cross_coupling_not_refused_if_bounded(
        self,
    ) -> None:
        """Cross-coupling can legitimately be negative; only |K| is bounded."""
        b = LinearBearing(
            name="cross",
            axial_position=Q(0.0, "m"),
            K_yy=Q(1.0e7, "N/m"),
            K_yz=Q(-5.0e6, "N/m"),
            K_zy=Q(5.0e6, "N/m"),
            K_zz=Q(1.0e7, "N/m"),
        )
        K, _ = b.coefficients_at_rpm(0.0)
        assert K[0, 1] == pytest.approx(-5.0e6)
