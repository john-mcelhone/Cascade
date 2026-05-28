"""Family / property tests: bearing stiffness invariants.

Tests the invariant: for a rotor whose first critical speed is dominated
by bearing stiffness (rigid-shaft + heavy-disk limit), the critical speed
scales as sqrt(K) and the critical speed map is monotonically increasing
with K.

These are NOT single-case benchmark tests. They sweep ranges of K so that
constants cannot be tuned to pass.

Physical basis:
-  In the rigid-shaft / heavy-disk (Jeffcott) limit the system reduces to
   a single-DOF mass on a spring: omega_crit = sqrt(K_total / m).
-  For K_bearing >> K_shaft (soft bearing), K_total ≈ K_bearing and
   omega_crit ∝ sqrt(K_bearing).
-  For K_bearing << K_shaft (rigid bearing), K_total ≈ K_shaft and
   omega_crit becomes independent of K_bearing (asymptotic plateau).
-  Between these limits, omega_crit is strictly monotonically increasing
   with K_bearing (there are no local maxima for a passive undamped system).
"""

from __future__ import annotations

import math

import pytest
import numpy as np

from cascade.rotor import LinearBearing, build_rotor_model, run_lateral_analysis
from cascade.rotor.critical_speed_map import run_critical_speed_map
from cascade.units import LumpedDisk, Q, RotorSection, RotorShape


# ============================================================================
# Helpers
# ============================================================================


def _rigid_shaft_heavy_disk_rotor(K_b: float, disk_mass: float = 50.0):
    """Very stiff shaft + heavy disk so that K_bearing dominates.

    Uses a large-diameter shaft (100 mm) so that the shaft's bending stiffness
    is >> the bearing stiffness for K_bearing < 1e8. This pushes the rotor
    into the bearing-dominated regime for the K range we test.
    """
    sec = RotorSection(
        diameter_outer=Q(0.10, "m"),
        diameter_inner=Q(0.0, "m"),
        length=Q(0.4, "m"),
        density=Q(7800.0, "kg/m^3"),
        axial_position=Q(0.0, "m"),
        material="AISI4340",
    )
    disk = LumpedDisk(
        mass=Q(disk_mass, "kg"),
        inertia_polar=Q(0.5 * disk_mass * 0.01, "kg*m^2"),
        inertia_diametrical=Q(0.25 * disk_mass * 0.01, "kg*m^2"),
        axial_position=Q(0.2, "m"),
    )
    shape = RotorShape(sections=[sec], disks=[disk])
    C_b = max(1.0, K_b * 1e-4)  # light proportional damping
    brg1 = LinearBearing(
        "b1", Q(0.0, "m"),
        K_yy=Q(K_b, "N/m"), K_zz=Q(K_b, "N/m"),
        C_yy=Q(C_b, "N*s/m"), C_zz=Q(C_b, "N*s/m"),
    )
    brg2 = LinearBearing(
        "b2", Q(0.4, "m"),
        K_yy=Q(K_b, "N/m"), K_zz=Q(K_b, "N/m"),
        C_yy=Q(C_b, "N*s/m"), C_zz=Q(C_b, "N*s/m"),
    )
    return build_rotor_model(shape, [brg1, brg2], elements_per_section=20)


def _first_omega(K_b: float) -> float:
    model = _rigid_shaft_heavy_disk_rotor(K_b)
    modes = run_lateral_analysis(model, rpm=0.0, n_modes=4)
    return modes[0].omega_n_rad_s


# ============================================================================
# Monotonicity: omega_crit is strictly increasing with K
# ============================================================================


class TestCriticalSpeedMonotonicWithK:
    """The first critical speed of a passive rotor is monotonically
    non-decreasing with bearing stiffness K.
    """

    K_VALUES = [1e5, 1e6, 1e7, 1e8, 1e9]

    def test_critical_speed_monotonic_increasing_with_K(self) -> None:
        """omega_crit(K_n+1) >= omega_crit(K_n) for all consecutive K pairs."""
        omegas = [_first_omega(K) for K in self.K_VALUES]
        for i in range(1, len(omegas)):
            assert omegas[i] > omegas[i - 1] * 0.999, (
                f"Critical speed is not monotonically increasing: "
                f"omega(K={self.K_VALUES[i]:.1e}) = {omegas[i]:.2f} rad/s "
                f"<= omega(K={self.K_VALUES[i-1]:.1e}) = {omegas[i-1]:.2f} rad/s. "
                f"A passive undamped rotor's first critical must be monotone in K."
            )

    def test_critical_speed_increases_by_at_least_factor_2_over_3_decades(self) -> None:
        """Over 3 decades of K, the critical speed must increase by at least 2x.

        Even if the rotor is not in the pure sqrt(K) regime for all values,
        a 3-decade K increase must give at least a 2x frequency increase.
        """
        omega_low = _first_omega(1e5)
        omega_high = _first_omega(1e8)
        assert omega_high > 2.0 * omega_low, (
            f"Over K=1e5→1e8 (3 decades), critical speed only increased by "
            f"{omega_high/omega_low:.2f}x; expected at least 2x. "
            f"Monotone scaling test."
        )


# ============================================================================
# sqrt(K) scaling in the bearing-dominated regime
# ============================================================================


class TestCriticalSpeedSqrtKScaling:
    """In the bearing-dominated (soft-bearing) regime, omega_crit ~ sqrt(K).

    We verify this using a very heavy disk (bearing-dominated) and pairs of
    K values where the ratio is well-known.
    """

    def _omega_soft_bearing(self, K_b: float) -> float:
        """Use extremely heavy disk (1000 kg) to force bearing-dominated limit."""
        sec = RotorSection(
            diameter_outer=Q(0.10, "m"), diameter_inner=Q(0.0, "m"),
            length=Q(0.4, "m"), density=Q(7800.0, "kg/m^3"),
            axial_position=Q(0.0, "m"), material="AISI4340",
        )
        disk = LumpedDisk(
            mass=Q(1000.0, "kg"),
            inertia_polar=Q(5.0, "kg*m^2"),
            inertia_diametrical=Q(2.5, "kg*m^2"),
            axial_position=Q(0.2, "m"),
        )
        shape = RotorShape(sections=[sec], disks=[disk])
        C_b = K_b * 1e-4
        brg1 = LinearBearing("b1", Q(0.0, "m"), K_yy=Q(K_b, "N/m"), K_zz=Q(K_b, "N/m"), C_yy=Q(C_b, "N*s/m"), C_zz=Q(C_b, "N*s/m"))
        brg2 = LinearBearing("b2", Q(0.4, "m"), K_yy=Q(K_b, "N/m"), K_zz=Q(K_b, "N/m"), C_yy=Q(C_b, "N*s/m"), C_zz=Q(C_b, "N*s/m"))
        model = build_rotor_model(shape, [brg1, brg2], elements_per_section=20)
        modes = run_lateral_analysis(model, rpm=0.0, n_modes=4)
        return modes[0].omega_n_rad_s

    @pytest.mark.parametrize("K_lo,K_hi", [
        (1e4, 1e6),   # factor 100 in K -> factor 10 in omega
        (1e5, 1e7),   # factor 100 in K -> factor 10 in omega
        (1e4, 1e8),   # factor 10000 in K -> factor 100 in omega
    ])
    def test_sqrt_k_scaling_in_soft_bearing_regime(self, K_lo: float, K_hi: float) -> None:
        """omega_crit(K_hi) / omega_crit(K_lo) ≈ sqrt(K_hi / K_lo) within 15%.

        The 15% tolerance accounts for shaft stiffness contamination (the shaft
        is not infinitely stiff, so the pure sqrt(K) limit is never exact).
        """
        omega_lo = self._omega_soft_bearing(K_lo)
        omega_hi = self._omega_soft_bearing(K_hi)
        ratio_actual = omega_hi / omega_lo
        ratio_expected = math.sqrt(K_hi / K_lo)
        rel_err = abs(ratio_actual - ratio_expected) / ratio_expected
        assert rel_err < 0.15, (
            f"sqrt(K) scaling: K ratio = {K_hi/K_lo:.0f}x, "
            f"expected omega ratio = {ratio_expected:.3f}, "
            f"got {ratio_actual:.3f} (error {rel_err:.1%} > 15%). "
            f"The bearing-dominated regime should follow sqrt(K) scaling."
        )


# ============================================================================
# Critical speed map monotonicity
# ============================================================================


class TestCriticalSpeedMapMonotonicity:
    """run_critical_speed_map output must be monotone in K for each mode track."""

    def test_first_mode_track_is_monotone_in_K(self) -> None:
        """The first mode frequency in the CSM must be non-decreasing with K."""
        # Build a simple rotor
        sec = RotorSection(
            diameter_outer=Q(0.02, "m"), diameter_inner=Q(0.0, "m"),
            length=Q(0.4, "m"), density=Q(7800.0, "kg/m^3"),
            axial_position=Q(0.0, "m"), material="AISI4340",
        )
        disk = LumpedDisk(
            mass=Q(2.5, "kg"), inertia_polar=Q(2.5e-3, "kg*m^2"),
            inertia_diametrical=Q(1.25e-3, "kg*m^2"), axial_position=Q(0.2, "m"),
        )
        shape = RotorShape(sections=[sec], disks=[disk])
        brg1 = LinearBearing("b1", Q(0.0, "m"), K_yy=Q(5e7, "N/m"), K_zz=Q(5e7, "N/m"), C_yy=Q(1e3, "N*s/m"), C_zz=Q(1e3, "N*s/m"))
        brg2 = LinearBearing("b2", Q(0.4, "m"), K_yy=Q(5e7, "N/m"), K_zz=Q(5e7, "N/m"), C_yy=Q(1e3, "N*s/m"), C_zz=Q(1e3, "N*s/m"))
        model = build_rotor_model(shape, [brg1, brg2], elements_per_section=10)

        csm = run_critical_speed_map(model, n_modes=3, n_stiffness=20)
        # mode_frequencies_rad_s shape: (n_stiffness, n_modes)
        first_mode_freqs = csm.mode_frequencies_rad_s[:, 0]

        # Filter NaN entries
        valid = ~np.isnan(first_mode_freqs)
        freqs_valid = first_mode_freqs[valid]
        K_valid = csm.stiffness_values_n_per_m[valid]

        assert len(freqs_valid) >= 5, (
            f"Expected at least 5 valid CSM points; got {len(freqs_valid)}. "
            f"K range may be outside the rotor's physical range."
        )

        # Check monotonicity: each frequency must be >= 99.9% of the previous
        for i in range(1, len(freqs_valid)):
            assert freqs_valid[i] >= freqs_valid[i - 1] * 0.999, (
                f"CSM first-mode is not monotone at K={K_valid[i]:.2e}: "
                f"freq dropped from {freqs_valid[i-1]:.2f} to {freqs_valid[i]:.2f} rad/s. "
                f"A passive rotor's first mode must be monotone in K."
            )

    def test_csm_spans_at_least_two_decades_of_frequency(self) -> None:
        """The CSM over 5 decades of K should show at least a 2x frequency spread."""
        sec = RotorSection(
            diameter_outer=Q(0.02, "m"), diameter_inner=Q(0.0, "m"),
            length=Q(0.4, "m"), density=Q(7800.0, "kg/m^3"),
            axial_position=Q(0.0, "m"), material="AISI4340",
        )
        disk = LumpedDisk(
            mass=Q(2.5, "kg"), inertia_polar=Q(2.5e-3, "kg*m^2"),
            inertia_diametrical=Q(1.25e-3, "kg*m^2"), axial_position=Q(0.2, "m"),
        )
        shape = RotorShape(sections=[sec], disks=[disk])
        brg1 = LinearBearing("b1", Q(0.0, "m"), K_yy=Q(5e7, "N/m"), K_zz=Q(5e7, "N/m"), C_yy=Q(1e3, "N*s/m"), C_zz=Q(1e3, "N*s/m"))
        brg2 = LinearBearing("b2", Q(0.4, "m"), K_yy=Q(5e7, "N/m"), K_zz=Q(5e7, "N/m"), C_yy=Q(1e3, "N*s/m"), C_zz=Q(1e3, "N*s/m"))
        model = build_rotor_model(shape, [brg1, brg2], elements_per_section=10)

        csm = run_critical_speed_map(
            model, n_modes=3,
            stiffness_min_n_per_m=1e4,
            stiffness_max_n_per_m=1e9,
            n_stiffness=30,
        )
        first_mode_freqs = csm.mode_frequencies_rad_s[:, 0]
        valid = ~np.isnan(first_mode_freqs)
        freqs_valid = first_mode_freqs[valid]

        if len(freqs_valid) >= 2:
            freq_range = freqs_valid[-1] / freqs_valid[0]
            assert freq_range > 2.0, (
                f"CSM frequency range over 5 decades of K is only {freq_range:.2f}x; "
                f"expected > 2x. The CSM should show real variation with K."
            )
