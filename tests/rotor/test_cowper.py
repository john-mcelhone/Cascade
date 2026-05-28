"""ADAPT-004: Cowper 1966 shear-coefficient regression test.

Per Cowper, G. R. (1966), "The Shear Coefficient in Timoshenko's Beam
Theory," ASME J. Appl. Mech. 33(2): 335-340, the solid-round shear
coefficient is::

    kappa = 6 (1 + nu) / (7 + 6 nu)

For ``nu = 0.3`` this is ``6 * 1.3 / (7 + 1.8) = 0.886``. The earlier
implementation substituted ``6 (1+nu)^2 / (7 + 12 nu + 4 nu^2)`` which
returns 0.925 instead -- a 4 % over-prediction of kappa, propagating as
a 4 % under-prediction of bending stiffness for stubby rotor segments.

This test guards against regression to the broken formula.

References:
- Cowper, G. R. (1966). The Shear Coefficient in Timoshenko's Beam Theory.
  ASME J. Appl. Mech. 33(2): 335-340.
- Hutchinson, J. R. (2001). Shear Coefficients for Timoshenko Beam Theory.
  ASME J. Appl. Mech. 68: 87-92 (commentary on Cowper's results).
"""

from __future__ import annotations

import math

import pytest

from cascade.rotor.beam_fem import cowper_shear_coefficient


@pytest.mark.parametrize(
    ("nu", "expected_kappa"),
    [
        (0.0, 6.0 / 7.0),  # 0.857
        (0.1, 6.0 * 1.1 / (7.0 + 0.6)),  # 0.868
        (0.25, 6.0 * 1.25 / (7.0 + 1.5)),  # 0.882
        (0.3, 6.0 * 1.3 / (7.0 + 1.8)),  # 0.886
        (0.33, 6.0 * 1.33 / (7.0 + 1.98)),
        (0.4, 6.0 * 1.4 / (7.0 + 2.4)),  # 0.894
        (0.499, 6.0 * 1.499 / (7.0 + 2.994)),
    ],
)
def test_cowper_solid_round_matches_closed_form(
    nu: float, expected_kappa: float
) -> None:
    """At any valid nu, the solid-round kappa = 6(1+nu)/(7+6nu)."""
    got = cowper_shear_coefficient(0.05, 0.0, nu)
    assert abs(got - expected_kappa) < 1e-9, (
        f"nu={nu}: expected kappa={expected_kappa:.6f}, got {got:.6f}. "
        f"Cowper 1966 eq. (37) solid round."
    )


def test_cowper_solid_round_at_nu_0p3_is_0p886() -> None:
    """Canonical test point: solid round at nu=0.3 gives kappa ~ 0.886."""
    kappa = cowper_shear_coefficient(0.05, 0.0, 0.3)
    assert abs(kappa - 0.886) < 0.001, (
        f"kappa(nu=0.3, solid) = {kappa:.4f}; expected 0.886. "
        f"This is the published Cowper 1966 result."
    )


def test_cowper_solid_at_nu_0p5_is_9_over_10() -> None:
    """nu = 0.5 (incompressible) solid round: kappa = 9/10 = 0.9."""
    # Reading the formula at nu=0.5 directly: 6*1.5/(7+3) = 9/10
    kappa = cowper_shear_coefficient(0.05, 0.0, 0.499)
    expected = 6.0 * 1.499 / (7.0 + 6.0 * 0.499)
    assert abs(kappa - expected) < 1e-9
    # And the limit at nu -> 0.5
    assert abs(expected - 0.9) < 1e-3, f"limit expected ~ 0.9; got {expected}"


def test_cowper_hollow_round_degenerate_m_zero_matches_solid() -> None:
    """At m = 0 (no inner bore) the hollow formula reduces to the solid
    coefficient -- continuity check."""
    nu = 0.3
    kappa_solid = cowper_shear_coefficient(0.05, 0.0, nu)
    # m = 1e-10, essentially zero
    kappa_hollow_small = cowper_shear_coefficient(0.05, 5e-12, nu)
    assert abs(kappa_solid - kappa_hollow_small) < 1e-6, (
        f"Hollow formula at m -> 0 must match solid. Got solid={kappa_solid}, "
        f"hollow={kappa_hollow_small}"
    )


def test_cowper_hollow_round_thin_walled_limit() -> None:
    """At m -> 1 (thin-walled tube) the hollow formula reduces to
    kappa = 2(1+nu)/(4+3nu)."""
    nu = 0.3
    # m = 0.9999: very thin walled
    kappa_thin = cowper_shear_coefficient(0.05, 0.05 * 0.9999, nu)
    expected_tube = 2.0 * (1.0 + nu) / (4.0 + 3.0 * nu)
    assert abs(kappa_thin - expected_tube) < 1e-3, (
        f"Hollow at m -> 1 must approach the thin-tube limit "
        f"{expected_tube:.4f}; got {kappa_thin:.4f}"
    )


def test_cowper_hollow_round_intermediate_m_value() -> None:
    """At m = 0.5, nu = 0.3, the Cowper hollow formula gives a
    well-defined intermediate value.

    Computed by hand using Cowper 1966 eq. (38) / Table 1:
        m = 0.5, m^2 = 0.25, (1+m^2)^2 = 1.5625
        numerator = 6 * 1.3 * 1.5625 = 12.1875
        denom = (7+1.8)*1.5625 + (20+3.6)*0.25
              = 8.8 * 1.5625 + 23.6 * 0.25
              = 13.75 + 5.9 = 19.65
        kappa = 12.1875 / 19.65 = 0.6202

    This is the canonical Cowper Table 1 entry for nu=0.3, m=0.5.
    """
    kappa = cowper_shear_coefficient(0.05, 0.025, 0.3)  # m=0.5
    expected = 12.1875 / 19.65
    assert abs(kappa - expected) < 1e-4, (
        f"Cowper hollow at nu=0.3, m=0.5: expected {expected:.4f}, "
        f"got {kappa:.4f}"
    )


def test_cowper_rejects_invalid_poisson_ratio() -> None:
    """Poisson ratio outside (-1, 0.5) is rejected."""
    with pytest.raises(ValueError, match="Poisson"):
        cowper_shear_coefficient(0.05, 0.0, 0.5)
    with pytest.raises(ValueError, match="Poisson"):
        cowper_shear_coefficient(0.05, 0.0, -1.5)
    with pytest.raises(ValueError, match="Poisson"):
        cowper_shear_coefficient(0.05, 0.0, float("nan"))


def test_cowper_doctest_runs_in_ci() -> None:
    """Smoke test: the docstring asserts kappa(D_o=0.05, D_i=0, nu=0.3)
    is within 0.001 of 0.886. We replicate that here for explicit CI
    coverage (in case doctest collection is not enabled)."""
    kappa = cowper_shear_coefficient(0.05, 0.0, 0.3)
    assert abs(kappa - 0.886) < 0.001


def test_regression_old_quadratic_form_returns_wrong_value() -> None:
    """Regression guard: ensure the new formula does NOT return the old
    incorrect value 0.925.

    Old (broken) formula: ``6(1+nu)^2 / (7 + 12 nu + 4 nu^2)``.
    For nu=0.3 this is ``6 * 1.69 / 10.96 = 0.9252...``
    Correct (Cowper 1966 solid round) is ``0.8864...``.
    """
    kappa = cowper_shear_coefficient(0.05, 0.0, 0.3)
    # The old broken value
    old_broken = 6 * (1.3) ** 2 / (7 + 12 * 0.3 + 4 * 0.09)
    assert abs(kappa - old_broken) > 0.03, (
        f"Cowper kappa = {kappa:.4f} is suspiciously close to the old "
        f"broken value {old_broken:.4f}. The fix may not be applied."
    )
