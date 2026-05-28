"""ADAPT-028: LinearBearing K/C field validation regression test.

Before ADAPT-028, ``LinearBearing(K_yy=float('nan'))`` constructed
successfully (the original ``_check_stiffness_value`` only enforced an
upper bound, and ``nan > anything`` is False). A NaN bearing stiffness
propagates downstream as NaN eigenvalues -- the eigensolver returns
"modes" that look numerically valid but encode nothing. This is the
canonical silent-wrong-answer failure mode.

The fix rejects:

- NaN, +Inf, -Inf on any K_yy, K_zz, K_yz, K_zy, C_yy, C_zz, C_yz, C_zy
- Negative diagonals (K_yy, K_zz, C_yy, C_zz)

Negative cross-couplings (K_yz, K_zy, C_yz, C_zy) ARE allowed because
they are the canonical destabilizing-asymmetry signature of plain journal
bearings (Lund 1966 / Childs 1993 §4.3 / API 684 §2.4.2.4).

ADAPT-037: this test exercises the API-684-compliant field names
(``K_yy`` / ``K_zz`` / etc., with y, z as the radial DOFs). The legacy
``K_xx`` / ``K_yy`` (with x, y as radial DOFs) names remain accepted via
a deprecation shim -- see ``test_bearing_api684_naming.py``.
"""

from __future__ import annotations

import pytest

from cascade.rotor import LinearBearing
from cascade.units import Q


class TestLinearBearingNaNRefusal:
    def test_nan_K_yy_rejected(self) -> None:
        with pytest.raises(ValueError, match="NON_FINITE_BEARING_VALUE"):
            LinearBearing(
                name="nan_kyy",
                axial_position=Q(0.0, "m"),
                K_yy=Q(float("nan"), "N/m"),
            )

    def test_nan_K_zz_rejected(self) -> None:
        with pytest.raises(ValueError, match="NON_FINITE_BEARING_VALUE"):
            LinearBearing(
                name="nan_kzz",
                axial_position=Q(0.0, "m"),
                K_zz=Q(float("nan"), "N/m"),
            )

    def test_nan_K_yz_rejected(self) -> None:
        """Even cross-coupling NaN is rejected (NaN never makes physical sense)."""
        with pytest.raises(ValueError, match="NON_FINITE_BEARING_VALUE"):
            LinearBearing(
                name="nan_kyz",
                axial_position=Q(0.0, "m"),
                K_yz=Q(float("nan"), "N/m"),
            )

    def test_nan_C_yy_rejected(self) -> None:
        with pytest.raises(ValueError, match="NON_FINITE_BEARING_VALUE"):
            LinearBearing(
                name="nan_cyy",
                axial_position=Q(0.0, "m"),
                C_yy=Q(float("nan"), "N*s/m"),
            )

    def test_nan_C_yz_rejected(self) -> None:
        with pytest.raises(ValueError, match="NON_FINITE_BEARING_VALUE"):
            LinearBearing(
                name="nan_cyz",
                axial_position=Q(0.0, "m"),
                C_yz=Q(float("nan"), "N*s/m"),
            )


class TestLinearBearingInfRefusal:
    def test_positive_inf_K_rejected(self) -> None:
        # +Inf K is also unphysical; the 1e10 cap normally catches this,
        # but we also check the finite-check is firing.
        with pytest.raises(ValueError):
            LinearBearing(
                name="posinf_K",
                axial_position=Q(0.0, "m"),
                K_yy=Q(float("inf"), "N/m"),
            )

    def test_negative_inf_K_yy_rejected(self) -> None:
        with pytest.raises(ValueError, match="NON_FINITE_BEARING_VALUE"):
            LinearBearing(
                name="neginf_K",
                axial_position=Q(0.0, "m"),
                K_yy=Q(float("-inf"), "N/m"),
            )

    def test_negative_inf_K_yz_rejected(self) -> None:
        """Cross-coupling -Inf is also rejected (Inf is never finite, even for
        cross terms which may be negative)."""
        with pytest.raises(ValueError, match="NON_FINITE_BEARING_VALUE"):
            LinearBearing(
                name="neginf_Kyz",
                axial_position=Q(0.0, "m"),
                K_yz=Q(float("-inf"), "N/m"),
            )

    def test_negative_inf_C_yy_rejected(self) -> None:
        with pytest.raises(ValueError, match="NON_FINITE_BEARING_VALUE"):
            LinearBearing(
                name="neginf_C",
                axial_position=Q(0.0, "m"),
                C_yy=Q(float("-inf"), "N*s/m"),
            )


class TestLinearBearingNegativeDiagonalRefusal:
    def test_negative_K_yy_rejected(self) -> None:
        with pytest.raises(
            ValueError, match="NEGATIVE_DIAGONAL_BEARING_STIFFNESS"
        ):
            LinearBearing(
                name="neg_kyy",
                axial_position=Q(0.0, "m"),
                K_yy=Q(-1.0e6, "N/m"),
            )

    def test_negative_K_zz_rejected(self) -> None:
        with pytest.raises(
            ValueError, match="NEGATIVE_DIAGONAL_BEARING_STIFFNESS"
        ):
            LinearBearing(
                name="neg_kzz",
                axial_position=Q(0.0, "m"),
                K_zz=Q(-1.0e6, "N/m"),
            )

    def test_negative_C_yy_rejected(self) -> None:
        with pytest.raises(
            ValueError, match="NEGATIVE_DIAGONAL_BEARING_DAMPING"
        ):
            LinearBearing(
                name="neg_cyy",
                axial_position=Q(0.0, "m"),
                C_yy=Q(-100.0, "N*s/m"),
            )

    def test_negative_C_zz_rejected(self) -> None:
        with pytest.raises(
            ValueError, match="NEGATIVE_DIAGONAL_BEARING_DAMPING"
        ):
            LinearBearing(
                name="neg_czz",
                axial_position=Q(0.0, "m"),
                C_zz=Q(-100.0, "N*s/m"),
            )


class TestLinearBearingNegativeCrossCouplingAllowed:
    """Negative cross-couplings are NOT rejected (oil-whirl asymmetry)."""

    def test_negative_K_yz_accepted(self) -> None:
        b = LinearBearing(
            name="neg_kyz",
            axial_position=Q(0.0, "m"),
            K_yy=Q(1.0e7, "N/m"),
            K_yz=Q(-5.0e6, "N/m"),
            K_zy=Q(5.0e6, "N/m"),
            K_zz=Q(1.0e7, "N/m"),
        )
        K, _ = b.coefficients_at_rpm(0.0)
        assert K[0, 1] == pytest.approx(-5.0e6)

    def test_negative_C_yz_accepted(self) -> None:
        b = LinearBearing(
            name="neg_cyz",
            axial_position=Q(0.0, "m"),
            C_yz=Q(-50.0, "N*s/m"),
            C_zy=Q(50.0, "N*s/m"),
        )
        _, C = b.coefficients_at_rpm(0.0)
        assert C[0, 1] == pytest.approx(-50.0)


class TestLinearBearingValidValuesAccepted:
    def test_valid_bearing_constructs(self) -> None:
        """The canonical valid bearing constructs cleanly."""
        b = LinearBearing(
            name="valid",
            axial_position=Q(0.0, "m"),
            K_yy=Q(1.0e6, "N/m"),
            K_zz=Q(1.0e6, "N/m"),
            C_yy=Q(100.0, "N*s/m"),
            C_zz=Q(100.0, "N*s/m"),
        )
        K, C = b.coefficients_at_rpm(0.0)
        assert K[0, 0] == pytest.approx(1.0e6)
        assert C[0, 0] == pytest.approx(100.0)

    def test_zero_diagonal_is_accepted(self) -> None:
        """K = 0 is degenerate but technically allowed (the rotor would
        be unstable but that's the model validator's job, not the
        bearing constructor)."""
        b = LinearBearing(
            name="zero",
            axial_position=Q(0.0, "m"),
            K_yy=Q(0.0, "N/m"),
            K_zz=Q(0.0, "N/m"),
        )
        K, _ = b.coefficients_at_rpm(0.0)
        assert K[0, 0] == 0.0
