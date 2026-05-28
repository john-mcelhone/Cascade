"""W-12: Torsional stiffness from RotorSection beam geometry.

Verifies that the torsional analysis computes K_theta = G*J/L from the shaft
geometry (outer radius, inner radius, length, material) rather than using the
old hardcoded 1.0e6 N*m/rad placeholder.

Acceptance criteria tested here:
- AC1: A shaft segment with outer_radius=0.025m (D=50mm), inner_radius=0m,
  length=0.1m, material=STEEL_AISI4340 produces K_theta close to the
  hand-calculated value:
    G = E/(2*(1+nu)) = 200e9/(2*1.29) ≈ 77.5 GPa (AISI 4340 room T)
    J = pi/2 * r_o^4 = pi/2 * 0.025^4 ≈ 6.136e-7 m^4
    K_theta = G*J/L = 77.5e9 * 6.136e-7 / 0.1 ≈ 4.76e6 N*m/rad
  (the precise value depends on registry nu; within 10% of 4.9e6)

- AC2: Changing the shaft outer diameter changes the torsional natural
  frequency: the fat shaft has a higher torsional frequency than the thin shaft
  because K_theta ~ D^4.

- AC3: The hardcoded 1.0e6 placeholder is NOT returned for a real shaft
  geometry (K_theta for the 50mm-diameter shaft is well above 1e6).
"""

from __future__ import annotations

import math

import pytest

from cascade.materials import MaterialDB
from cascade.rotor.eigenanalysis import run_torsional_analysis
from cascade.units import LumpedDisk, Q, RotorSection, RotorShape

# Import the helper directly for unit-testing the function itself.
from routers.rotor import _torsional_stiffness_between_disks

pytestmark = pytest.mark.validation


# ---------------------------------------------------------------------------
# Helper: build a two-disk torsional model with given shaft diameter
# ---------------------------------------------------------------------------


def _build_two_disk_torsional(outer_radius_m: float, inner_radius_m: float = 0.0) -> tuple:
    """Build a two-disk rotor and return (inertias, stiffness) for run_torsional_analysis."""
    outer_diameter_m = 2.0 * outer_radius_m
    inner_diameter_m = 2.0 * inner_radius_m
    length_m = 0.10  # 100 mm inter-disk segment

    sec = RotorSection(
        diameter_outer=Q(outer_diameter_m, "m"),
        diameter_inner=Q(inner_diameter_m, "m"),
        length=Q(length_m, "m"),
        density=Q(7850.0, "kg/m^3"),
        axial_position=Q(0.0, "m"),
        material="STEEL_AISI4340",
    )
    disk1 = LumpedDisk(
        mass=Q(1.0, "kg"),
        inertia_polar=Q(5.0e-4, "kg*m^2"),
        inertia_diametrical=Q(2.5e-4, "kg*m^2"),
        axial_position=Q(0.0, "m"),
    )
    disk2 = LumpedDisk(
        mass=Q(1.0, "kg"),
        inertia_polar=Q(5.0e-4, "kg*m^2"),
        inertia_diametrical=Q(2.5e-4, "kg*m^2"),
        axial_position=Q(length_m, "m"),
    )
    shape = RotorShape(sections=[sec], disks=[disk1, disk2])

    disk_positions = [0.0, length_m]
    stiffness = _torsional_stiffness_between_disks(shape.sections, disk_positions)
    inertias = [
        float(d.inertia_polar.to("kg*m^2").magnitude)
        for d in [disk1, disk2]
    ]
    return inertias, stiffness, shape


# ---------------------------------------------------------------------------
# AC1: Hand-computed K_theta sanity check for a 50mm solid shaft
# ---------------------------------------------------------------------------


def test_torsional_stiffness_hand_calc_within_10_percent() -> None:
    """AC1: K_theta for D=50mm, L=100mm, AISI 4340 matches GJ/L within 10%."""
    outer_radius = 0.025  # 25mm -> D=50mm
    length = 0.10

    sec = RotorSection(
        diameter_outer=Q(2 * outer_radius, "m"),
        diameter_inner=Q(0.0, "m"),
        length=Q(length, "m"),
        density=Q(7850.0, "kg/m^3"),
        axial_position=Q(0.0, "m"),
        material="STEEL_AISI4340",
    )
    stiffness = _torsional_stiffness_between_disks([sec], [0.0, length])
    assert len(stiffness) == 1, "Expected exactly one stiffness value for one segment."
    K_computed = stiffness[0]

    # Hand calculation using registry values
    mat = MaterialDB.get("AISI 4340")
    E = mat.E(293.0)
    nu = mat.poisson
    G = E / (2.0 * (1.0 + nu))
    J = math.pi / 2.0 * outer_radius**4
    K_hand = G * J / length

    rel_error = abs(K_computed - K_hand) / K_hand
    assert rel_error < 0.01, (
        f"K_theta = {K_computed:.4e} N*m/rad, hand = {K_hand:.4e} N*m/rad, "
        f"relative error = {rel_error:.2%} (tolerance 1%)."
    )


# ---------------------------------------------------------------------------
# AC2: Larger shaft diameter -> higher torsional natural frequency
# ---------------------------------------------------------------------------


def test_larger_diameter_gives_higher_torsional_frequency() -> None:
    """AC2: Fat shaft has higher torsional frequency than thin shaft (K ~ D^4)."""
    inertias_thin, stiffness_thin, _ = _build_two_disk_torsional(outer_radius_m=0.010)
    inertias_fat, stiffness_fat, _ = _build_two_disk_torsional(outer_radius_m=0.030)

    freqs_thin = run_torsional_analysis(inertias_thin, stiffness_thin, n_modes=3)
    freqs_fat = run_torsional_analysis(inertias_fat, stiffness_fat, n_modes=3)

    # Index 0 is zero (rigid body); index 1 is the first torsional mode.
    omega_thin = freqs_thin[1]
    omega_fat = freqs_fat[1]

    assert omega_fat > omega_thin, (
        f"Fat shaft first torsional freq ({omega_fat:.1f} rad/s) should exceed "
        f"thin shaft ({omega_thin:.1f} rad/s) because K_theta ~ D^4."
    )

    # Sanity-check the D^4 scaling: ratio should be ~ (D_fat/D_thin)^2
    # because omega ~ sqrt(K/J) and K ~ D^4 (J_inertia is the same for both
    # by construction), so omega_fat/omega_thin ~ (D_fat/D_thin)^2.
    D_ratio = 0.030 / 0.010  # = 3.0
    expected_freq_ratio = D_ratio**2  # = 9.0
    actual_freq_ratio = omega_fat / omega_thin
    rel_error = abs(actual_freq_ratio - expected_freq_ratio) / expected_freq_ratio
    assert rel_error < 0.05, (
        f"Freq ratio {actual_freq_ratio:.3f} should be ~{expected_freq_ratio:.1f} "
        f"(D_fat/D_thin)^2 for identical inertias; error {rel_error:.2%}."
    )


# ---------------------------------------------------------------------------
# AC3: K_theta for a real geometry is NOT the hardcoded 1e6 placeholder
# ---------------------------------------------------------------------------


def test_torsional_stiffness_is_not_hardcoded_1e6() -> None:
    """AC3: K_theta for a 50mm solid steel shaft is well above the 1e6 placeholder.

    For D=50mm (r_o=25mm), L=100mm, AISI 4340 (G≈77.5 GPa):
        J = pi/2 * (0.025)^4 ≈ 6.14e-7 m^4
        K = G*J/L = 77.5e9 * 6.14e-7 / 0.1 ≈ 4.76e5 N*m/rad

    The old hardcode (1e6) is approximately 2x this value, confirming geometry matters.
    This test verifies:
      (a) the result is NOT 1e6 (within 1% would suggest hardcode)
      (b) the result is within 10% of the hand-calculated 4.76e5 N*m/rad.
    """
    _, stiffness, _ = _build_two_disk_torsional(outer_radius_m=0.025)
    K_theta = stiffness[0]

    # Computed hand value for D=50mm, L=100mm, AISI 4340 at 293K:
    K_expected = 4.76e5  # N*m/rad (see docstring)

    # Not the hardcoded placeholder: result should be close to hand calculation.
    assert abs(K_theta - K_expected) / K_expected < 0.05, (
        f"K_theta = {K_theta:.4e} N*m/rad deviates from expected ~{K_expected:.2e} "
        f"by more than 5%; the geometry-derived path may not be active."
    )

    # Explicitly not exactly 1e6 (to within 1%): proves the hardcode is gone.
    assert abs(K_theta - 1.0e6) / 1.0e6 > 0.01, (
        f"K_theta = {K_theta:.4e} is suspiciously close to the old 1e6 hardcode; "
        f"the GJ/L path may not be used."
    )


# ---------------------------------------------------------------------------
# Hollow shaft: J_polar = pi/2 * (r_o^4 - r_i^4) is less than solid
# ---------------------------------------------------------------------------


def test_hollow_shaft_has_lower_stiffness_than_solid() -> None:
    """Hollow shaft (same outer diameter) is less stiff than a solid shaft in torsion."""
    outer_r = 0.025
    inner_r = 0.020  # thick wall

    _, stiffness_solid, _ = _build_two_disk_torsional(outer_radius_m=outer_r, inner_radius_m=0.0)
    _, stiffness_hollow, _ = _build_two_disk_torsional(outer_radius_m=outer_r, inner_radius_m=inner_r)

    K_solid = stiffness_solid[0]
    K_hollow = stiffness_hollow[0]

    assert K_hollow < K_solid, (
        f"Hollow shaft K_theta={K_hollow:.4e} should be less than solid K_theta={K_solid:.4e}."
    )

    # Verify the ratio matches (r_o^4 - r_i^4) / r_o^4
    expected_ratio = (outer_r**4 - inner_r**4) / outer_r**4
    actual_ratio = K_hollow / K_solid
    rel_error = abs(actual_ratio - expected_ratio) / expected_ratio
    assert rel_error < 0.01, (
        f"K_hollow/K_solid = {actual_ratio:.4f}, expected {expected_ratio:.4f} "
        f"from J_polar ratio; error {rel_error:.2%}."
    )
