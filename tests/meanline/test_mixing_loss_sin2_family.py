"""Family / property tests for Aungier eq. 6.51 mixing loss (B-07 fix, 2026-05-27).

Asserts that the corrected sin²(β₂') formula produces the right qualitative
behavior:
- Mixing is maximum for radial blades (β₂'=90°, sin=1) and decreases as
  back-sweep increases (β₂' moves away from 90° toward smaller angles).
- Mixing is zero only for purely tangential discharge (β₂'→0°, sin→0).

Citation: Aungier, R.H., 2000, *Centrifugal Compressors: A Strategy for
Aerodynamic Design and Analysis*, ASME Press, Ch. 6, eq. 6.51.
"""
from __future__ import annotations

import math

import pytest

from cascade.meanline.loss_models_impl import AungierCentrifugal


def _run_mixing(beta2_blade_deg: float, wake_fraction: float = 0.15) -> float:
    """Return mixing loss coefficient for a given blade exit angle.

    All other context parameters are fixed to isolate the β₂' effect.
    """
    beta2 = math.radians(beta2_blade_deg)
    model = AungierCentrifugal(wake_fraction=wake_fraction)
    ctx = {
        "U_2": 350.0,
        "W_1_tip": 200.0,
        "W_2": 180.0,
        "V_2": 280.0,
        "beta_1_flow_rad": math.radians(55.0),
        "beta_1_blade_rad": math.radians(55.0),
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
    return model.loss_coefficient(**ctx).mixing


class TestMixingLossMonotonicWithBacksweep:
    """B-07 first-principles check: mixing decreases as back-sweep increases.

    'Back-sweep' means β₂' (from tangential) decreases from 90° (radial)
    toward smaller angles. With the corrected sin²(β₂') formula:
    - β₂'=90° → sin²=1 → maximum mixing (purely radial blades)
    - β₂'=60° → sin²=0.75 → less mixing (30° back-sweep from radial)
    - β₂'=30° → sin²=0.25 → even less mixing (60° back-sweep)
    - β₂'→0° → sin²→0 → approaching zero mixing

    This is the correct physical direction per Aungier 2000 eq. 6.51.
    """

    def test_mixing_maximum_at_radial_blades(self) -> None:
        """β₂'=90° (radial blade) must give the highest mixing loss.

        sin(90°)=1 is the maximum of sin over (0°, 90°].
        """
        mix_radial = _run_mixing(90.0)
        mix_back_swept = _run_mixing(60.0)  # 30° back-sweep from radial
        assert mix_radial > mix_back_swept, (
            f"Radial blade mixing = {mix_radial:.5f} must be > "
            f"30°-back-swept mixing = {mix_back_swept:.5f}. "
            f"B-07: sin²(90°)=1 > sin²(60°)=0.75."
        )

    def test_mixing_monotone_decreasing_with_backsweep(self) -> None:
        """Mixing must decrease monotonically as back-sweep increases.

        Back-sweep: β₂' from tangential decreasing from 90° → 10°.
        sin²(β₂') is monotonically decreasing in this range.
        """
        angles = [90.0, 75.0, 60.0, 45.0, 30.0, 15.0]
        mixings = [_run_mixing(a) for a in angles]
        for i in range(1, len(mixings)):
            assert mixings[i] < mixings[i - 1], (
                f"Mixing did not decrease from β₂'={angles[i-1]:.0f}° "
                f"({mixings[i-1]:.6f}) to β₂'={angles[i]:.0f}° ({mixings[i]:.6f}). "
                f"B-07: sin²(β₂') must be monotonically decreasing as β₂' decreases "
                f"from 90° (radial) toward 0° (tangential)."
            )

    def test_mixing_near_zero_at_tangential_discharge(self) -> None:
        """β₂'→0° (tangential discharge) → mixing → 0.

        sin(0°)=0 → no meridional velocity deficit → no jet/wake mixing.
        """
        mix_tangential = _run_mixing(1.0)  # 1° from tangential → sin≈0.017
        mix_typical = _run_mixing(60.0)
        assert mix_tangential < 0.01 * mix_typical, (
            f"Near-tangential mixing = {mix_tangential:.6e} should be <<1% of "
            f"typical mixing {mix_typical:.6e}. "
            f"B-07: sin²(1°)≈0.0003 should give near-zero mixing."
        )

    def test_mixing_sin2_ratio_between_angles(self) -> None:
        """Mixing ratio between two angles must match sin²(β₂_1)/sin²(β₂_2).

        This directly tests the sin² functional form (not cos²).
        """
        angle_1 = 30.0
        angle_2 = 60.0
        mix_1 = _run_mixing(angle_1)
        mix_2 = _run_mixing(angle_2)

        expected_ratio = math.sin(math.radians(angle_1)) ** 2 / math.sin(math.radians(angle_2)) ** 2
        actual_ratio = mix_1 / max(mix_2, 1e-12)

        assert abs(actual_ratio - expected_ratio) / expected_ratio < 0.01, (
            f"Mixing ratio at {angle_1}°/{angle_2}° = {actual_ratio:.4f}; "
            f"expected sin²({angle_1}°)/sin²({angle_2}°) = {expected_ratio:.4f}. "
            f"B-07 fix: Aungier eq. 6.51 uses sin², not cos². "
            f"If this fails, the trig direction may have been reverted to cos²."
        )

    def test_mixing_positive_for_all_typical_angles(self) -> None:
        """Mixing must be positive (>0) for all practical back-sweep angles > 0."""
        for angle in [30.0, 45.0, 60.0, 75.0, 90.0]:
            mix = _run_mixing(angle)
            assert mix > 0.0, (
                f"Mixing = {mix:.6e} for β₂'={angle}°. "
                f"sin({angle}°) > 0, so mixing must be positive."
            )
