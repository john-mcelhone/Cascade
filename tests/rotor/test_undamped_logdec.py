"""ADAPT-041: undamped rotors must return ``log_decrement = None`` and warn.

For an undamped rotor (C = 0, no Rayleigh damping, no journal bearings),
the QEP eigenvalues are purely imaginary; the API 684 log decrement is
mathematically zero. Before ADAPT-041 the eigensolver returned a tiny
numerical-noise reading (~1e-15) without indicating it was meaningless.

This test asserts that for an undamped rotor:

1. Every returned mode has ``log_decrement is None``.
2. A ``RuntimeWarning`` is emitted from :func:`run_lateral_analysis`.
3. The accompanying frequencies are still physically valid (the warning
   does not zero out ``omega_d_rad_s`` -- only ``log_decrement``).
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from cascade.rotor import LinearBearing, build_rotor_model, run_lateral_analysis
from cascade.units import LumpedDisk, Q, RotorSection, RotorShape


def _build_undamped_jeffcott() -> "object":
    """Thin-shaft Jeffcott with zero bearing and zero Rayleigh damping."""
    sec = RotorSection(
        diameter_outer=Q(0.005, "m"),
        diameter_inner=Q(0.0, "m"),
        length=Q(1.0, "m"),
        density=Q(7850.0, "kg/m^3"),
        axial_position=Q(0.0, "m"),
        material="AISI4340",
    )
    disk = LumpedDisk(
        mass=Q(10.0, "kg"),
        inertia_polar=Q(0.001, "kg*m^2"),
        inertia_diametrical=Q(0.0005, "kg*m^2"),
        axial_position=Q(0.5, "m"),
    )
    shape = RotorShape(sections=[sec], disks=[disk])
    K_b = 1.0e9
    brg1 = LinearBearing(
        name="b1",
        axial_position=Q(0.0, "m"),
        K_yy=Q(K_b, "N/m"),
        K_zz=Q(K_b, "N/m"),
        # No bearing damping, and we'll also zero Rayleigh below.
    )
    brg2 = LinearBearing(
        name="b2",
        axial_position=Q(1.0, "m"),
        K_yy=Q(K_b, "N/m"),
        K_zz=Q(K_b, "N/m"),
    )
    return build_rotor_model(
        shape,
        [brg1, brg2],
        elements_per_section=10,
        rayleigh_alpha=0.0,
        rayleigh_beta=0.0,
    )


def test_undamped_rotor_log_decrement_is_none() -> None:
    """ADAPT-041 regression: undamped log-dec returned as None, not noise."""
    model = _build_undamped_jeffcott()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        modes = run_lateral_analysis(model, rpm=0.0, n_modes=3)
    assert all(m.log_decrement is None for m in modes), (
        "Every mode of an undamped rotor must have log_decrement = None; "
        f"got log_decrements = {[m.log_decrement for m in modes]}"
    )
    # The frequencies themselves should still be physical
    assert all(m.omega_d_rad_s > 0 for m in modes)
    # A RuntimeWarning about no damping must have been emitted
    runtime_warnings = [
        w for w in caught if issubclass(w.category, RuntimeWarning)
    ]
    assert any(
        "no damping" in str(w.message).lower()
        or "not physically meaningful" in str(w.message).lower()
        for w in runtime_warnings
    ), (
        "Expected a RuntimeWarning about undamped rotor; "
        f"got warnings: {[str(w.message) for w in caught]}"
    )


def test_undamped_rotor_does_not_return_epsilon_noise() -> None:
    """Defensive: even if a future bug breaks the None-return path, ensure
    we never return |log_dec| < 1e-3 (the canonical epsilon-noise signature)
    without flagging it as None."""
    model = _build_undamped_jeffcott()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        modes = run_lateral_analysis(model, rpm=0.0, n_modes=3)
    for i, m in enumerate(modes):
        if m.log_decrement is not None:
            assert abs(m.log_decrement) > 1e-3, (
                f"Mode {i} returned log_decrement = {m.log_decrement} "
                f"(epsilon-noise) without being flagged as None -- ADAPT-041 "
                f"regression."
            )
