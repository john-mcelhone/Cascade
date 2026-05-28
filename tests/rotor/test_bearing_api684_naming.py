"""ADAPT-037: API 684 §2.3-compliant bearing field naming.

Cascade previously used ``K_xx`` / ``K_yy`` / ``K_xy`` / ``K_yx`` with x
and y as the radial DOFs. API 684 §2.3 (followed by Childs 1993, Adams
2009, Vance 2010) reserves x for the **axial** direction, so the radial
DOFs are y and z, and the bearing stiffness fields are ``K_yy`` / ``K_zz``
/ ``K_yz`` / ``K_zy``.

The renaming-compatibility shim (:meth:`LinearBearing.from_legacy` and the
fallback handling in :meth:`LinearBearing.__init__`) accepts the legacy
names but emits a ``DeprecationWarning`` and maps the legacy DOFs to the
new ones::

    K_xx -> K_yy   (horizontal radial direct)
    K_yy -> K_zz   (vertical radial direct  -- LEGACY meaning)
    K_xy -> K_yz   (cross-coupling)
    K_yx -> K_zy

A direct read of a legacy attribute (e.g. ``b.K_xx``) returns the new
value with a DeprecationWarning per access.
"""

from __future__ import annotations

import warnings

import pytest

from cascade.rotor import LinearBearing
from cascade.units import Q


class TestFromLegacyClassmethod:
    def test_from_legacy_emits_deprecation_warning(self) -> None:
        """``from_legacy`` must always emit DeprecationWarning."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            LinearBearing.from_legacy(
                "legacy",
                axial_position=Q(0.0, "m"),
                K_xx=Q(1.0e6, "N/m"),
                K_yy=Q(2.0e6, "N/m"),
            )
        deps = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert deps, "from_legacy must emit DeprecationWarning"

    def test_from_legacy_maps_K_xx_to_K_yy(self) -> None:
        """Legacy K_xx (horizontal radial direct) -> new K_yy."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            b = LinearBearing.from_legacy(
                "legacy",
                axial_position=Q(0.0, "m"),
                K_xx=Q(1.0e6, "N/m"),
                K_yy=Q(2.0e6, "N/m"),
            )
        assert b.K_yy.to("N/m").magnitude == pytest.approx(1.0e6)
        assert b.K_zz.to("N/m").magnitude == pytest.approx(2.0e6)

    def test_from_legacy_maps_cross_couplings(self) -> None:
        """Legacy K_xy/K_yx -> new K_yz/K_zy."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            b = LinearBearing.from_legacy(
                "legacy",
                axial_position=Q(0.0, "m"),
                K_xx=Q(1.0e7, "N/m"),
                K_yy=Q(1.0e7, "N/m"),
                K_xy=Q(-3.0e5, "N/m"),
                K_yx=Q(+3.0e5, "N/m"),
            )
        assert b.K_yz.to("N/m").magnitude == pytest.approx(-3.0e5)
        assert b.K_zy.to("N/m").magnitude == pytest.approx(+3.0e5)

    def test_from_legacy_maps_damping_fields(self) -> None:
        """Legacy C_xx/C_yy/C_xy/C_yx -> new C_yy/C_zz/C_yz/C_zy."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            b = LinearBearing.from_legacy(
                "legacy",
                axial_position=Q(0.0, "m"),
                C_xx=Q(10.0, "N*s/m"),
                C_yy=Q(20.0, "N*s/m"),
                C_xy=Q(-1.0, "N*s/m"),
                C_yx=Q(+1.0, "N*s/m"),
            )
        assert b.C_yy.to("N*s/m").magnitude == pytest.approx(10.0)
        assert b.C_zz.to("N*s/m").magnitude == pytest.approx(20.0)
        assert b.C_yz.to("N*s/m").magnitude == pytest.approx(-1.0)
        assert b.C_zy.to("N*s/m").magnitude == pytest.approx(+1.0)


class TestLegacyKwargsInDirectConstructor:
    """Passing legacy kwargs directly to :class:`LinearBearing` still works,
    with a DeprecationWarning, for source-compatibility."""

    def test_legacy_K_xx_kwarg_emits_warning(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            LinearBearing(
                name="b",
                axial_position=Q(0.0, "m"),
                K_xx=Q(1.0e6, "N/m"),
            )
        deps = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert deps, "Passing K_xx must emit DeprecationWarning (ADAPT-037)"

    def test_legacy_kwarg_combination_maps_correctly(self) -> None:
        """A legacy-style ``K_xx=`` + ``K_yy=`` call maps to ``K_yy=`` + ``K_zz=``."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            b = LinearBearing(
                name="b",
                axial_position=Q(0.0, "m"),
                K_xx=Q(1.0e6, "N/m"),
                K_yy=Q(2.0e6, "N/m"),
            )
        assert b.K_yy.to("N/m").magnitude == pytest.approx(1.0e6)
        assert b.K_zz.to("N/m").magnitude == pytest.approx(2.0e6)

    def test_canonical_kwargs_do_not_emit_warning(self) -> None:
        """Using the new API-684 kwargs must NOT emit a deprecation warning."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            LinearBearing(
                name="b",
                axial_position=Q(0.0, "m"),
                K_yy=Q(1.0e6, "N/m"),
                K_zz=Q(2.0e6, "N/m"),
            )
        deps = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert not deps, (
            "Canonical K_yy/K_zz kwargs must not emit DeprecationWarning; "
            f"got {[str(w.message) for w in deps]}"
        )


class TestLegacyAttributeAccess:
    """Reading a legacy attribute returns the corresponding new value with
    a DeprecationWarning per access."""

    def test_K_xx_read_returns_K_yy_value(self) -> None:
        b = LinearBearing(
            name="b",
            axial_position=Q(0.0, "m"),
            K_yy=Q(1.0e6, "N/m"),
            K_zz=Q(2.0e6, "N/m"),
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            val = b.K_xx
        assert val.to("N/m").magnitude == pytest.approx(1.0e6)
        deps = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert deps, "Reading legacy K_xx must emit DeprecationWarning"

    def test_unknown_attribute_still_raises_AttributeError(self) -> None:
        b = LinearBearing(
            name="b",
            axial_position=Q(0.0, "m"),
            K_yy=Q(1.0e6, "N/m"),
        )
        with pytest.raises(AttributeError):
            _ = b.K_qq  # nonsense attribute


class TestCoefficientsMatchAPI684Layout:
    """The 2x2 matrix returned by :meth:`coefficients_at_rpm` uses (y, z)
    layout: ``[K_yy, K_yz; K_zy, K_zz]``."""

    def test_diagonal_K_layout(self) -> None:
        b = LinearBearing(
            name="b",
            axial_position=Q(0.0, "m"),
            K_yy=Q(1.0e6, "N/m"),
            K_zz=Q(2.0e6, "N/m"),
            K_yz=Q(-3.0e5, "N/m"),
            K_zy=Q(+3.0e5, "N/m"),
        )
        K, _ = b.coefficients_at_rpm(0.0)
        assert K[0, 0] == pytest.approx(1.0e6)  # K_yy at index [0,0]
        assert K[1, 1] == pytest.approx(2.0e6)  # K_zz at index [1,1]
        assert K[0, 1] == pytest.approx(-3.0e5)  # K_yz at index [0,1]
        assert K[1, 0] == pytest.approx(+3.0e5)  # K_zy at index [1,0]
