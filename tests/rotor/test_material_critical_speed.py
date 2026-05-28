"""W-13: Materials registry into beam-FEM.

Verifies that RotorSection.material is resolved to real E / nu via the
MaterialDB registry so that different materials produce different critical
speeds.

Acceptance criteria tested here:
- AC1: Ti-6Al-4V rotor first critical < AISI 4340 first critical for the
  same geometry (Ti has lower E -> lower stiffness -> lower omega_n).
- AC2: The ratio of critical speeds matches sqrt(E_Ti / E_steel) within 5%
  (Euler-Bernoulli shaft bending: omega_n ~ sqrt(E)).
- AC3: An unrecognised material string emits a RuntimeWarning and falls back
  to AISI 4340 (NOT silently wrong material, NOT ValueError -- the plan
  calls for a warning+fallback per AC3).
- AC4: A section with temperature_K=500 uses the 500 K property value, not
  293 K (verifiable because Ti-6Al-4V E drops measurably from 293 to 500 K).
"""

from __future__ import annotations

import math
import warnings

import pytest

from cascade.materials import MaterialDB
from cascade.rotor import LinearBearing, build_rotor_model, run_lateral_analysis
from cascade.units import LumpedDisk, Q, RotorSection, RotorShape

pytestmark = pytest.mark.validation


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _build_rotor(material: str, *, temperature_K: float | None = None) -> object:
    """Thin shaft, single central disk -- identical geometry, different material."""
    sec_kwargs: dict = {}
    if temperature_K is not None:
        sec_kwargs["temperature_K"] = temperature_K

    sec = RotorSection(
        diameter_outer=Q(0.05, "m"),
        diameter_inner=Q(0.0, "m"),
        length=Q(1.0, "m"),
        density=Q(7850.0, "kg/m^3"),  # same density for both so mass is identical
        axial_position=Q(0.0, "m"),
        material=material,
        **sec_kwargs,
    )
    disk = LumpedDisk(
        mass=Q(5.0, "kg"),
        inertia_polar=Q(2.5e-3, "kg*m^2"),
        inertia_diametrical=Q(1.25e-3, "kg*m^2"),
        axial_position=Q(0.5, "m"),
    )
    shape = RotorShape(sections=[sec], disks=[disk])
    # Stiff bearings so critical speed is dominated by shaft bending.
    K_b = 1.0e9
    brg1 = LinearBearing(
        name="b1", axial_position=Q(0.0, "m"),
        K_yy=Q(K_b, "N/m"), K_zz=Q(K_b, "N/m"),
        C_yy=Q(500.0, "N*s/m"), C_zz=Q(500.0, "N*s/m"),
    )
    brg2 = LinearBearing(
        name="b2", axial_position=Q(1.0, "m"),
        K_yy=Q(K_b, "N/m"), K_zz=Q(K_b, "N/m"),
        C_yy=Q(500.0, "N*s/m"), C_zz=Q(500.0, "N*s/m"),
    )
    return build_rotor_model(shape, [brg1, brg2], elements_per_section=10)


# ---------------------------------------------------------------------------
# AC1: Ti-6Al-4V rotor first critical is BELOW AISI 4340 rotor first critical
# ---------------------------------------------------------------------------


def test_ti64_critical_speed_lower_than_steel() -> None:
    """AC1: Ti-6Al-4V first critical < AISI 4340 first critical (same geometry)."""
    model_steel = _build_rotor("STEEL_AISI4340")
    model_ti = _build_rotor("Ti-6Al-4V")

    modes_steel = run_lateral_analysis(model_steel, rpm=0.0, n_modes=3)
    modes_ti = run_lateral_analysis(model_ti, rpm=0.0, n_modes=3)

    omega_steel = modes_steel[0].omega_n_rad_s
    omega_ti = modes_ti[0].omega_n_rad_s

    assert omega_ti < omega_steel, (
        f"Ti-6Al-4V first critical ({omega_ti:.2f} rad/s) should be less than "
        f"AISI 4340 ({omega_steel:.2f} rad/s) because E_Ti < E_steel."
    )


# ---------------------------------------------------------------------------
# AC2: The frequency ratio matches sqrt(E_Ti / E_steel) within 5 %
# ---------------------------------------------------------------------------


def test_ti64_to_steel_frequency_ratio_matches_e_ratio() -> None:
    """AC2: omega_n(Ti) / omega_n(steel) ≈ sqrt(E_Ti / E_steel) within 5%."""
    model_steel = _build_rotor("STEEL_AISI4340")
    model_ti = _build_rotor("Ti-6Al-4V")

    modes_steel = run_lateral_analysis(model_steel, rpm=0.0, n_modes=3)
    modes_ti = run_lateral_analysis(model_ti, rpm=0.0, n_modes=3)

    omega_steel = modes_steel[0].omega_n_rad_s
    omega_ti = modes_ti[0].omega_n_rad_s

    # E values from the registry at room temperature (293 K)
    E_steel = MaterialDB.get("AISI 4340").E(293.0)   # Pa
    E_ti = MaterialDB.get("Ti-6Al-4V").E(293.0)       # Pa

    # For shaft bending: omega_n ~ sqrt(EI/m). I and m are identical across
    # the two rotors (same geometry + same density override), so the ratio is:
    expected_ratio = math.sqrt(E_ti / E_steel)
    actual_ratio = omega_ti / omega_steel

    rel_error = abs(actual_ratio - expected_ratio) / expected_ratio
    assert rel_error < 0.05, (
        f"Frequency ratio {actual_ratio:.4f} deviates from sqrt(E_Ti/E_steel) = "
        f"{expected_ratio:.4f} by {rel_error:.1%} (tolerance 5%)."
    )


# ---------------------------------------------------------------------------
# AC3: Unknown material string raises RuntimeWarning and falls back gracefully
# ---------------------------------------------------------------------------


def test_unknown_material_emits_warning_and_runs() -> None:
    """AC3: An unrecognised material name emits RuntimeWarning; solve still completes."""
    sec = RotorSection(
        diameter_outer=Q(0.05, "m"),
        diameter_inner=Q(0.0, "m"),
        length=Q(1.0, "m"),
        density=Q(7850.0, "kg/m^3"),
        axial_position=Q(0.0, "m"),
        material="FICTIONAL_UNOBTAINIUM",
    )
    disk = LumpedDisk(
        mass=Q(5.0, "kg"),
        inertia_polar=Q(2.5e-3, "kg*m^2"),
        inertia_diametrical=Q(1.25e-3, "kg*m^2"),
        axial_position=Q(0.5, "m"),
    )
    shape = RotorShape(sections=[sec], disks=[disk])
    K_b = 1.0e9
    brg1 = LinearBearing(
        name="b1", axial_position=Q(0.0, "m"),
        K_yy=Q(K_b, "N/m"), K_zz=Q(K_b, "N/m"),
        C_yy=Q(500.0, "N*s/m"), C_zz=Q(500.0, "N*s/m"),
    )
    brg2 = LinearBearing(
        name="b2", axial_position=Q(1.0, "m"),
        K_yy=Q(K_b, "N/m"), K_zz=Q(K_b, "N/m"),
        C_yy=Q(500.0, "N*s/m"), C_zz=Q(500.0, "N*s/m"),
    )
    # Should emit a RuntimeWarning but NOT raise an exception.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model = build_rotor_model(shape, [brg1, brg2], elements_per_section=5)
        modes = run_lateral_analysis(model, rpm=0.0, n_modes=2)

    # At least one warning must mention the unknown material name.
    warning_msgs = [str(w.message) for w in caught if issubclass(w.category, RuntimeWarning)]
    assert any("FICTIONAL_UNOBTAINIUM" in msg for msg in warning_msgs), (
        f"Expected a RuntimeWarning about 'FICTIONAL_UNOBTAINIUM'; got: {warning_msgs}"
    )

    # The solve should have produced at least one mode.
    assert len(modes) >= 1, "Expected at least one mode even after unknown-material fallback."


# ---------------------------------------------------------------------------
# AC4: temperature_K field causes lookup at that temperature, not 293 K
# ---------------------------------------------------------------------------


def test_temperature_K_affects_material_lookup() -> None:
    """AC4: section.temperature_K=500 uses 500 K E, not 293 K E."""
    # Ti-6Al-4V: E(293) = 113.8 GPa, E(500) = 104.0 GPa (from registry).
    # With a lower E at 500 K the critical speed should be lower than at 293 K.
    model_cold = _build_rotor("Ti-6Al-4V", temperature_K=293.0)
    model_hot = _build_rotor("Ti-6Al-4V", temperature_K=500.0)

    modes_cold = run_lateral_analysis(model_cold, rpm=0.0, n_modes=2)
    modes_hot = run_lateral_analysis(model_hot, rpm=0.0, n_modes=2)

    omega_cold = modes_cold[0].omega_n_rad_s
    omega_hot = modes_hot[0].omega_n_rad_s

    assert omega_hot < omega_cold, (
        f"Ti-6Al-4V at 500 K first critical ({omega_hot:.2f} rad/s) should be "
        f"less than at 293 K ({omega_cold:.2f} rad/s) because E drops with temperature."
    )

    # Verify the ratio roughly matches sqrt(E_500 / E_293)
    E_cold = MaterialDB.get("Ti-6Al-4V").E(293.0)
    E_hot = MaterialDB.get("Ti-6Al-4V").E(500.0)
    expected_ratio = math.sqrt(E_hot / E_cold)
    actual_ratio = omega_hot / omega_cold
    rel_error = abs(actual_ratio - expected_ratio) / expected_ratio
    assert rel_error < 0.05, (
        f"Frequency ratio {actual_ratio:.4f} deviates from sqrt(E_500/E_293) = "
        f"{expected_ratio:.4f} by {rel_error:.1%} (tolerance 5%)."
    )
