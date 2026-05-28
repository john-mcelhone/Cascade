"""Closes SR-006: Wiesner slip-factor with derived Z → ∞ limit.

Tests:
1. Wiesner and Stanitz both approach σ = 1 as Z → ∞ (the inviscid Euler
   limit; no slip).
2. The two formulas converge to within 1e-3 at very large Z (10⁶).
3. Wiesner clips to σ ≥ 0 at low Z (would otherwise go negative for very
   small Z with large β').
4. The Wiesner geometric correction (r̄₁/r₂ > ε_W) is applied correctly.

Note on SPEC tolerance: the user's task spec writes
"|σ_Wiesner(Z=100, β=45°) - σ_Stanitz(Z=100)| < 0.001". This is not
achievable with the published formulas (Wiesner uses Z^0.7 in the
denominator; Stanitz uses Z^1). At Z = 100 the difference is ≈ 0.014;
the formulas only converge to 0 difference at Z → ∞. The SR-006 derived
limit is the shared σ → 1 asymptote, which the tests below verify.
This deviation from the user's literal tolerance is documented in
`KNOWN_GAPS.md`.
"""

from __future__ import annotations

import math

import pytest

from cascade.meanline import StanitzSlip, StodolaSlip, WiesnerSlip


class TestSlipFactorAsymptotes:
    """SR-006: derived Z → ∞ limit for Wiesner and Stanitz both → 1."""

    @pytest.mark.parametrize("beta_deg", [30.0, 45.0, 60.0, 75.0, 90.0])
    def test_wiesner_approaches_unity_at_infinite_Z(self, beta_deg: float) -> None:
        """As Z → ∞, σ_Wiesner → 1 (no slip).

        For Z = 1e6, σ_Wiesner = 1 - sqrt(sin β)/Z^0.7 ≈ 1 - sqrt(sinβ)/63095
        which is within 1e-4 of unity for any reasonable β.
        """
        w = WiesnerSlip()
        beta_rad = math.radians(beta_deg)
        sigma = w.slip_factor(blade_count=1_000_000,
                              beta_2_from_tangential_rad=beta_rad)
        assert abs(sigma - 1.0) < 1e-3, \
            f"Wiesner at Z=1e6, β={beta_deg}°: σ={sigma:.6f}, expected ≈ 1"

    @pytest.mark.parametrize("Z_pow", [3, 4, 5, 6])
    def test_stanitz_approaches_unity_at_infinite_Z(self, Z_pow: int) -> None:
        """As Z → ∞, σ_Stanitz = 1 - 0.63π/Z → 1."""
        s = StanitzSlip()
        Z = 10 ** Z_pow
        sigma = s.slip_factor(blade_count=Z,
                              beta_2_from_tangential_rad=math.pi / 2)
        expected = 1.0 - 0.63 * math.pi / Z
        assert abs(sigma - expected) < 1e-9
        # Both must approach 1
        if Z >= 1000:
            assert abs(sigma - 1.0) < 1e-2

    def test_wiesner_stanitz_converge_at_infinite_Z(self) -> None:
        """SR-006 closure: both formulas → 1 as Z → ∞. At Z = 10⁶ the
        difference is < 1e-3.

        This is the **derived shared asymptote** for the Wiesner and
        Stanitz closures — both describe the "no slip with infinite
        blades" limit. The convergence rate differs (Wiesner Z^0.7,
        Stanitz Z^1), so the formulas agree at finite Z only at very
        large blade counts.
        """
        w = WiesnerSlip()
        s = StanitzSlip()
        beta = math.radians(45.0)
        Z = 1_000_000
        sigma_w = w.slip_factor(Z, beta)
        sigma_s = s.slip_factor(Z, beta)
        assert abs(sigma_w - sigma_s) < 1e-3, \
            (f"|Wiesner - Stanitz| at Z={Z}, β=45° = "
             f"{abs(sigma_w - sigma_s):.6e}; both should ≈ 1.0")
        assert sigma_w > 0.999 and sigma_s > 0.999

    def test_wiesner_stanitz_finite_Z_published_difference(self) -> None:
        """At finite Z = 100, the published Wiesner and Stanitz formulas
        do *not* agree to 1e-3. They agree only as Z → ∞. This locks the
        known difference in published correlations for documentation
        purposes.

        At Z = 100, β = 45°:
        - σ_Wiesner = 1 - sqrt(sin 45°) / 100^0.7 = 1 - 0.841/25.12 ≈ 0.9665
        - σ_Stanitz = 1 - 0.63π/100 ≈ 0.9802
        - |W − S| ≈ 0.0137

        The user-task SPEC nominal "<0.001 at Z=100" is not achievable
        with the published formulas; the derived shared limit holds only
        as Z → ∞ (see test_wiesner_stanitz_converge_at_infinite_Z).
        """
        w = WiesnerSlip()
        s = StanitzSlip()
        beta = math.radians(45.0)
        sigma_w = w.slip_factor(100, beta)
        sigma_s = s.slip_factor(100, beta)
        # Lock published behavior — difference ≈ 0.014
        assert 0.01 < abs(sigma_w - sigma_s) < 0.02


class TestSlipFactorPhysicalClips:
    def test_wiesner_clips_to_zero_at_very_low_Z(self) -> None:
        """At Z = 1, β' = 90°: σ = 1 - sqrt(1)/1 = 0. Z < 4 is
        outside the slip-factor framework's validity, but
        the formula must not return a negative or > 1 value (we clip)."""
        w = WiesnerSlip()
        sigma = w.slip_factor(blade_count=1,
                              beta_2_from_tangential_rad=math.pi / 2)
        assert 0.0 <= sigma <= 1.0
        assert sigma == pytest.approx(0.0, abs=1e-9)

    def test_wiesner_geometric_limit_correction(self) -> None:
        """The Wiesner geometric correction kicks in when r̄₁/r₂ > ε_W
        where ε_W = exp(-8.16·cos(β')/Z). For Z=12, β'=80°tang
        (10° back-sweep), cos(80°)=0.174 → ε_W = exp(-0.118) = 0.889.
        A high-hub geometry r̄₁/r₂ = 0.95 > 0.889 triggers the correction.
        """
        w = WiesnerSlip()
        beta = math.radians(80.0)  # 10° back-sweep
        sigma_uncorrected = w.slip_factor(12, beta, radius_ratio_inducer_to_exit=0.0)
        sigma_corrected = w.slip_factor(12, beta, radius_ratio_inducer_to_exit=0.95)
        assert 0.0 <= sigma_corrected <= sigma_uncorrected
        # Correction must be strictly smaller for high r-ratio
        assert sigma_corrected < sigma_uncorrected

    def test_stanitz_independent_of_blade_angle(self) -> None:
        """Stanitz formula has no β' dependence."""
        s = StanitzSlip()
        sigma_radial = s.slip_factor(20, math.pi / 2)
        sigma_back = s.slip_factor(20, math.pi / 3)
        assert sigma_radial == pytest.approx(sigma_back, abs=1e-12)

    def test_stodola_vanishes_as_beta_approaches_radial_tangent(self) -> None:
        """Stodola: σ = 1 - π·sin(β')/Z. At β' → 0 (purely radial inflow
        blade — not physical for an impeller, but the limit), σ → 1."""
        st = StodolaSlip()
        sigma = st.slip_factor(20, 0.0)
        assert sigma == pytest.approx(1.0, abs=1e-12)


class TestSlipFactorPublishedValues:
    """Published Stanitz reference values."""

    def test_stanitz_Z12(self) -> None:
        """Reference: 'Z=12 → σ_Stanitz = 0.835'."""
        s = StanitzSlip()
        sigma = s.slip_factor(12, math.pi / 2)
        # σ = 1 - 0.63π/12 = 1 - 0.16493 = 0.83507
        assert sigma == pytest.approx(0.835, abs=1e-3)

    def test_stanitz_Z18(self) -> None:
        """Reference: 'Z=18 → σ_Stanitz = 0.890'."""
        s = StanitzSlip()
        sigma = s.slip_factor(18, math.pi / 2)
        # σ = 1 - 0.63π/18 = 1 - 0.10996 = 0.890
        assert sigma == pytest.approx(0.890, abs=1e-3)

    def test_stanitz_Z24(self) -> None:
        """Reference: 'Z=24 → σ_Stanitz = 0.918'."""
        s = StanitzSlip()
        sigma = s.slip_factor(24, math.pi / 2)
        # σ = 1 - 0.63π/24 = 1 - 0.08247 = 0.9175
        assert sigma == pytest.approx(0.918, abs=1e-3)

    def test_wiesner_eckardt_rotor_a(self) -> None:
        """Eckardt Rotor A: Z=20, β2'=60°tang.
        Wiesner: σ = 1 - sqrt(sin 60°)/20^0.7 = 1 - 0.931/8.14 = 0.886.
        This is the canonical reference for Eckardt-class wheels.
        """
        w = WiesnerSlip()
        sigma = w.slip_factor(20, math.radians(60.0))
        assert sigma == pytest.approx(0.886, abs=1e-3)
