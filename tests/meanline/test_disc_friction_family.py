"""Family / property tests for Daily-Nece disc friction (B-01 fix, 2026-05-27).

Asserts first-principles behavior of the WhitfieldBainesRadial disc friction
term AFTER the B-01 fix: U₁ (rotor inlet tip speed) is used instead of U₂.

Key invariant: P_df = ½ C_M ρ U₁³ r₁² → dh_df ∝ U₁³ when other parameters
are fixed. This is the Daily-Nece (1960) first-principles scaling.

Citation: Daily, J.W. & Nece, R.E., 1960, "Chamber Dimension Effects on
Induced Flow and Frictional Resistance of Enclosed Rotating Disks", Trans.
ASME J. Basic Engineering, 82(1), pp. 217–230, eq. 17–20.
"""
from __future__ import annotations

import math

import pytest

from cascade.meanline.loss_models_impl import WhitfieldBainesRadial


def _disc_friction_from_context(U_1: float, r_1: float = 0.076,
                                 r_2_tip: float = 0.0406) -> float:
    """Run the loss model and return the disc_friction coefficient.

    Uses a minimal context with only the disc-friction relevant fields.
    All other fields are set to physically trivial values so that only
    the disc-friction term is non-zero.
    """
    model = WhitfieldBainesRadial()
    ctx = {
        "W_1": 150.0,
        "W_2": 100.0,
        "V_2": 80.0,
        "beta_1_flow_rad": math.radians(60.0),
        "beta_1_blade_rad": math.radians(60.0),   # zero incidence → min loss
        "alpha_1_rad": math.radians(30.0),
        "blade_count": 12,
        "r_1": r_1,
        "r_2_tip": r_2_tip,
        "r_2_hub": 0.019,
        "b_1": 0.012,
        "b_2": 0.022,
        "tip_clearance_axial": 0.0,
        "tip_clearance_radial": 0.0,
        "U_1": U_1,
        "U_2": U_1 * r_2_tip / r_1,   # consistent ω·r
        "rho_2": 1.2,
        "mass_flow": 0.13,
        "chord_meridional": 0.04,
        "disc_gap_ratio": 0.02,
        "Re_omega": 5e6,
    }
    return model.loss_coefficient(**ctx).disc_friction


class TestDiscFrictionScalesAsU1Cubed:
    """B-01 first-principles check: dh_df ∝ U₁³ (Daily-Nece 1960 eq. 17–20).

    The fix routes disc friction through U₁ = ω·r₁ (inlet-face tip speed)
    rather than U₂ = ω·r₂ (exit tip speed). With U₁ and r₁ both referencing
    the same disc face, the power scales as U₁³·r₁² per Daily-Nece.

    Since r₁ is fixed in this sweep, r₁² is constant and
    dh_df ∝ U₁³ is the expected scaling.
    """

    def test_disc_friction_scales_as_u1_cubed_sweep(self) -> None:
        """Sweep U₁ and verify disc_friction coefficient scales as U₁³.

        Physical: P_df = ½ C_M ρ U₁³ r₁²; dh_df = P_df/ṁ; ζ_df = dh_df/(½W₂²).
        Since W₂, ρ, ṁ, r₁ are fixed, ζ_df ∝ U₁³.
        """
        U_1_values = [100.0, 150.0, 200.0, 250.0, 300.0]
        zetas = [_disc_friction_from_context(U) for U in U_1_values]

        # Verify strict U₁³ scaling between consecutive pairs
        for i in range(1, len(U_1_values)):
            u_ratio = U_1_values[i] / U_1_values[i - 1]
            expected_zeta_ratio = u_ratio ** 3
            actual_zeta_ratio = zetas[i] / max(zetas[i - 1], 1e-12)
            assert abs(actual_zeta_ratio - expected_zeta_ratio) / expected_zeta_ratio < 0.01, (
                f"U₁ ratio = {u_ratio:.3f}; expected ζ ratio = {expected_zeta_ratio:.4f}; "
                f"got {actual_zeta_ratio:.4f}. "
                f"Disc friction must scale as U₁³ per Daily-Nece 1960 eq. 17–20. "
                f"If this fails, the B-01 U₂/U₁ swap may have been reverted."
            )

    def test_disc_friction_increases_with_u1(self) -> None:
        """Disc friction must be monotonically increasing with U₁."""
        U_1_values = [80.0, 120.0, 180.0, 250.0]
        zetas = [_disc_friction_from_context(U) for U in U_1_values]
        for i in range(1, len(zetas)):
            assert zetas[i] > zetas[i - 1], (
                f"ζ_df decreased from U₁={U_1_values[i-1]:.0f} to "
                f"U₁={U_1_values[i]:.0f}. Must be monotonically increasing."
            )

    def test_disc_friction_zero_when_u1_zero(self) -> None:
        """With U₁=0 (stationary disc), disc friction must be zero."""
        zeta = _disc_friction_from_context(U_1=0.0)
        assert zeta == 0.0, (
            f"ζ_df = {zeta:.6e} for U₁=0; expected 0 (stationary disc). "
        )

    def test_b01_fix_uses_u1_not_u2(self) -> None:
        """Verify B-01 fix: disc friction must NOT scale as U₂³ when r₁/r₂ ≠ 1.

        For a typical RIT with r₁/r₂ ≈ 2.5, the pre-fix code used U₂ with r₁,
        giving a ~(r₁/r₂)³ ≈ 15.6× overestimate. The corrected code uses U₁.

        We verify this by checking that the ζ_df at U₁=200 m/s matches the
        analytical formula P_df = ½ C_M ρ U₁³ r₁² / ṁ / (½ W₂²), not
        the wrong P_df = ½ C_M ρ U₂³ r₁² / ṁ / (½ W₂²).
        """
        from cascade.meanline.loss_models_impl import daily_nece_moment_coefficient

        U_1 = 200.0
        r_1 = 0.076
        r_2_tip = 0.0406
        rho_2 = 1.2
        mdot = 0.13
        W_2 = 100.0
        Re_omega = 5e6
        G_over_r = 0.02

        C_M = daily_nece_moment_coefficient(Re_omega, G_over_r)
        # Correct formula: P_df = ½ C_M ρ U₁³ r₁²
        expected_dh = 0.5 * C_M * rho_2 * U_1 ** 3 * r_1 ** 2 / mdot
        expected_zeta = expected_dh / (0.5 * W_2 ** 2)

        actual_zeta = _disc_friction_from_context(U_1=U_1, r_1=r_1, r_2_tip=r_2_tip)

        assert abs(actual_zeta - expected_zeta) / max(expected_zeta, 1e-12) < 0.01, (
            f"ζ_df = {actual_zeta:.6e}; expected = {expected_zeta:.6e}. "
            f"Disc friction formula must use U₁ and r₁ referencing the same "
            f"disc face (Daily-Nece 1960). B-01 fix may have been reverted."
        )
