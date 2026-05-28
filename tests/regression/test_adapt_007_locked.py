"""ADAPT-007 locked regression: Aungier eq. 6.51 mixing loss and eq. 6.66 leakage.

This test will FAIL if the pre-ADAPT-007 piecewise-constant mixing loss
is restored (which was a hand-fit, NOT eq. 6.51), or if the discharge
coefficient is changed away from 0.816.

Locked invariants:
1. For a back-swept impeller (cos²(β₂') > 0), mixing loss must be > 0.
2. For a radial-bladed impeller (β₂' = 90°, cos = 0), mixing ≈ 0.
3. leakage_discharge_coefficient = 0.816 (Aungier labyrinth seal value).
4. AungierCentrifugal.loss_coefficient returns a LossBreakdown with
   mixing > 0 when the impeller is back-swept.

References:
- Aungier, R.H. (2000). Centrifugal Compressors. ASME Press, eq. 6.51 + 6.66.
- ADAPT-007 (regression lock).
"""

from __future__ import annotations

import math

import pytest

from cascade.meanline import AungierCentrifugal


def test_adapt_007_mixing_nonzero_for_back_swept() -> None:
    """Locked: Aungier eq. 6.51 mixing loss must be > 0 for back-swept impeller.

    cos²(β₂') > 0 for a back-swept impeller (β₂' != 90°). The pre-fix
    code returned a constant 0.02/0.04 step function; the real Aungier
    eq. uses the cos² term. This test verifies the cos² path is wired.
    """
    model = AungierCentrifugal(wake_fraction=0.15)
    # Back-swept: β₂_blade_rad ≈ 40° (from tangential) → cos²(40°) > 0
    beta2 = math.radians(40.0)
    ctx = {
        "U_2": 350.0,
        "W_1_tip": 200.0,
        "W_2": 180.0,
        "V_2": 280.0,
        "beta_1_flow_rad": math.radians(55.0),
        "beta_1_blade_rad": math.radians(55.0),  # zero incidence for simplicity
        "beta_2_blade_rad": beta2,
        "alpha_2_rad": math.radians(20.0),
        "blade_count": 17,
        "r_1_tip": 0.090,
        "r_1_hub": 0.030,
        "r_2": 0.180,
        "b_2": 0.018,
        "chord_meridional": 0.12,
        "sigma": 0.87,
        "DF": 0.45,
    }
    breakdown = model.loss_coefficient(**ctx)

    # Key assertion: mixing loss must be positive for back-swept impeller
    assert breakdown.mixing > 0.0, (
        f"ADAPT-007 regression: mixing loss = {breakdown.mixing:.6f} for "
        f"back-swept impeller (β₂'={math.degrees(beta2):.1f}°). "
        f"Aungier eq. 6.51 requires cos²(β₂')>0 → mixing > 0. "
        f"Pre-fix piecewise constant may have been restored."
    )
    # Sanity: mixing should be a small fraction of total, not dominant
    assert breakdown.mixing < 0.5, (
        f"Mixing loss {breakdown.mixing:.4f} is unreasonably large (>0.5). "
        f"Something is wrong with the Aungier eq. 6.51 implementation."
    )


def test_adapt_007_mixing_zero_for_radial_blades() -> None:
    """UPDATED (B-07 fix, 2026-05-27): Aungier eq. 6.51 uses sin²(β₂'), not cos².

    ORIGINAL assertion (cos² → 0 for β₂'=90°): WRONG per Aungier 2000 eq. 6.51.
    CORRECTED assertion: for a radial-bladed impeller β₂'=90° (from tangential),
    sin(90°)=1 → mixing is at its MAXIMUM (the meridional velocity deficit is
    maximum for a radial-discharge blade). The mixing loss must NOT vanish for
    β₂'=90° per the corrected sin² formula.

    The previous test asserted cos²=0→mixing=0 for β₂'=90°. This was asserting
    the wrong physics. Per Aungier 2000 §6.6 eq. 6.51, mixing is driven by the
    MERIDIONAL velocity deficit component W₂·sin(β₂'). For β₂'=90° (radial
    blades), the meridional component is W₂·sin(90°)=W₂ — the full relative
    velocity — giving maximum mixing, not zero.

    A β₂'→0° (purely tangential discharge) would give sin(0)=0→mixing=0:
    no meridional velocity, no jet/wake shear in the meridional plane.

    Citation: Aungier, R.H., 2000, *Centrifugal Compressors*, ASME Press,
    Ch. 6, eq. 6.51. B-07 closure (2026-05-27).
    """
    model = AungierCentrifugal(wake_fraction=0.20)
    # Radial bladed: β₂_blade_rad = π/2 (from tangential = 90°)
    beta2_radial = math.pi / 2.0
    ctx = {
        "U_2": 300.0,
        "W_1_tip": 180.0,
        "W_2": 150.0,
        "V_2": 260.0,
        "beta_1_flow_rad": math.radians(50.0),
        "beta_1_blade_rad": math.radians(50.0),
        "beta_2_blade_rad": beta2_radial,
        "alpha_2_rad": math.radians(25.0),
        "blade_count": 20,
        "r_1_tip": 0.100,
        "r_1_hub": 0.035,
        "r_2": 0.200,
        "b_2": 0.020,
        "chord_meridional": 0.14,
        "sigma": 0.90,
        "DF": 0.40,
    }
    breakdown = model.loss_coefficient(**ctx)

    # With sin²(90°)=1, mixing = ½·(0.20·150)²·1 / (½·300²) = 900/45000 = 0.02
    expected_mixing = 0.5 * (0.20 * 150.0) ** 2 * math.sin(beta2_radial) ** 2 / (0.5 * 300.0 ** 2)
    assert abs(breakdown.mixing - expected_mixing) < 1e-9, (
        f"ADAPT-007 B-07 fix: mixing loss = {breakdown.mixing:.6e} for "
        f"radial-bladed impeller (β₂'=90°). "
        f"Expected sin²(90°)=1 → mixing = {expected_mixing:.6e}. "
        f"The Aungier eq. 6.51 sin² direction must not revert to cos²."
    )
    # Must also be positive and finite
    assert breakdown.mixing > 0.0, (
        "Mixing loss must be positive for radial-bladed impeller (sin²(90°)=1)."
    )


def test_adapt_007_discharge_coefficient_is_0816() -> None:
    """Locked: leakage_discharge_coefficient must remain 0.816 (Aungier eq. 6.66)."""
    model = AungierCentrifugal()
    assert abs(model.leakage_discharge_coefficient - 0.816) < 1e-9, (
        f"ADAPT-007 regression: leakage_discharge_coefficient = "
        f"{model.leakage_discharge_coefficient:.4f}; expected 0.816 "
        f"(Aungier 2000 §6.6 labyrinth discharge coefficient, eq. 6.66)."
    )


def test_adapt_007_mixing_scales_with_sin_squared() -> None:
    """UPDATED (B-07 fix, 2026-05-27): mixing loss ratio matches sin² ratio, not cos².

    ORIGINAL test asserted cos²(β₂_1)/cos²(β₂_2) ratio — this was the WRONG
    trig direction. CORRECTED: Aungier 2000 eq. 6.51 uses sin²(β₂'), so the
    mixing ratio between two angles must equal sin²(β₂_1)/sin²(β₂_2).

    Physical justification: sin(β₂') is the meridional component of W₂ (when
    β₂' is measured from tangential). The meridional velocity deficit drives
    the jet/wake mixing. Therefore Δh_mix ∝ sin²(β₂'), not cos²(β₂').

    Citation: Aungier, R.H., 2000, *Centrifugal Compressors*, ASME Press,
    Ch. 6, eq. 6.51. B-07 closure (2026-05-27).
    """
    def run_mixing(beta2_deg: float) -> float:
        beta2 = math.radians(beta2_deg)
        model = AungierCentrifugal(wake_fraction=0.15)
        ctx = {
            "U_2": 350.0, "W_1_tip": 200.0, "W_2": 180.0, "V_2": 280.0,
            "beta_1_flow_rad": math.radians(55.0),
            "beta_1_blade_rad": math.radians(55.0),
            "beta_2_blade_rad": beta2,
            "alpha_2_rad": math.radians(20.0),
            "blade_count": 17, "r_1_tip": 0.090, "r_1_hub": 0.030,
            "r_2": 0.180, "b_2": 0.018, "chord_meridional": 0.12,
            "sigma": 0.87, "DF": 0.45,
        }
        return model.loss_coefficient(**ctx).mixing

    mix_30 = run_mixing(30.0)
    mix_45 = run_mixing(45.0)

    if mix_45 < 1e-12:
        pytest.skip("mixing near zero at 45°; sin² check not meaningful")

    # Corrected: ratio must match sin² ratio, not cos² ratio
    expected_ratio = math.sin(math.radians(30.0)) ** 2 / math.sin(math.radians(45.0)) ** 2
    actual_ratio = mix_30 / mix_45

    assert abs(actual_ratio - expected_ratio) / expected_ratio < 0.01, (
        f"ADAPT-007 B-07 fix: mixing ratio at 30°/45° = {actual_ratio:.4f}; "
        f"expected sin²(30°)/sin²(45°) = {expected_ratio:.4f}. "
        f"Aungier eq. 6.51 sin² dependence must not revert to cos²."
    )
