"""ADAPT-004 locked regression: Cowper 1966 solid-round shear coefficient.

This test will FAIL if the pre-ADAPT-004 formula is restored:
  Old (broken): kappa = 6(1+nu)^2 / (7 + 12nu + 4nu^2) = 0.9252 at nu=0.3
  Correct:      kappa = 6(1+nu) / (7 + 6nu)             = 0.8864 at nu=0.3

The 4% over-prediction of kappa in the old code propagated as a 4%
under-prediction of shear-deflection bending stiffness for stubby
rotor segments, shifting critical-speed predictions.

References:
- Cowper, G.R. (1966). The Shear Coefficient in Timoshenko's Beam Theory.
  ASME J. Appl. Mech. 33(2): 335-340. Eq. (37) for solid round section.
- ADAPT-004 (regression lock).
"""

from __future__ import annotations

import pytest

from cascade.rotor.beam_fem import cowper_shear_coefficient


def test_adapt_004_solid_round_nu03_is_0886_not_0925() -> None:
    """Locked: solid round at nu=0.3 must return ~0.886, NOT the old 0.925.

    This is the primary regression guard for ADAPT-004. If the old broken
    formula (circular-tube approximation) is restored, this test fails.
    """
    kappa = cowper_shear_coefficient(0.05, 0.0, 0.3)

    # Must be close to the correct value
    assert abs(kappa - 0.886) < 0.001, (
        f"Cowper solid round kappa(nu=0.3) = {kappa:.4f}; "
        f"expected ~0.886 (Cowper 1966 eq. 37). ADAPT-004 regression."
    )

    # Must NOT be close to the old broken value
    old_broken = 6.0 * (1.3 ** 2) / (7.0 + 12.0 * 0.3 + 4.0 * 0.09)
    assert abs(kappa - old_broken) > 0.02, (
        f"Cowper kappa = {kappa:.4f} matches the old BROKEN value "
        f"{old_broken:.4f} (circular-tube approximation, not the solid-round "
        f"eq. 37 result). ADAPT-004 was reverted."
    )


def test_adapt_004_formula_matches_cowper_eq37() -> None:
    """Locked: kappa = 6(1+nu)/(7+6nu) for solid round at several nu values."""
    for nu in [0.0, 0.1, 0.25, 0.3, 0.4]:
        expected = 6.0 * (1.0 + nu) / (7.0 + 6.0 * nu)
        got = cowper_shear_coefficient(0.05, 0.0, nu)
        assert abs(got - expected) < 1e-9, (
            f"nu={nu}: expected {expected:.6f} (Cowper 1966 eq. 37), "
            f"got {got:.6f}. ADAPT-004 regression."
        )
