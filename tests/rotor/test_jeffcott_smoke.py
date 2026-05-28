"""Jeffcott rotor smoke test.

The Jeffcott rotor (Jeffcott 1919): a single rigid disk on a flexible
shaft between two rigid bearings. The undamped natural frequency is

    omega_n = sqrt(K_shaft / m_disk)

with K_shaft = 48 EI / L^3 for a simply-supported beam at the midspan.

Per SPEC_SHEET §12, this is the smoke test that must pass first. It is
also the heart of RD-5 (machine-precision validation).

Reference: Jeffcott, H. H., 1919. The Lateral Vibration of Loaded Shafts
in the Neighborhood of a Whirling Speed -- The Effect of Want of Balance.
Philosophical Magazine 37: 304.
"""

from __future__ import annotations

import math

import pytest

from cascade.rotor import LinearBearing, build_rotor_model, run_lateral_analysis
from cascade.units import LumpedDisk, Q, RotorSection, RotorShape

pytestmark = pytest.mark.validation


def _build_thin_shaft_jeffcott(K_b_n_per_m: float = 1.0e9):
    """A thin steel shaft + central disk + nearly-rigid bearings.

    The shaft's bending stiffness is tiny compared to the bearings, so the
    rotor's first mode is the shaft-bending Jeffcott resonance.
    """
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
    brg1 = LinearBearing(
        name="b1",
        axial_position=Q(0.0, "m"),
        K_yy=Q(K_b_n_per_m, "N/m"),
        K_zz=Q(K_b_n_per_m, "N/m"),
        C_yy=Q(100.0, "N*s/m"),
        C_zz=Q(100.0, "N*s/m"),
    )
    brg2 = LinearBearing(
        name="b2",
        axial_position=Q(1.0, "m"),
        K_yy=Q(K_b_n_per_m, "N/m"),
        K_zz=Q(K_b_n_per_m, "N/m"),
        C_yy=Q(100.0, "N*s/m"),
        C_zz=Q(100.0, "N*s/m"),
    )
    return build_rotor_model(shape, [brg1, brg2], elements_per_section=20)


def test_jeffcott_thin_shaft_first_natural_frequency_within_tolerance() -> None:
    """The first natural frequency of a thin-shaft Jeffcott rotor with stiff
    bearings matches the classical 48 EI / L^3 / m formula within 5%."""
    model = _build_thin_shaft_jeffcott(K_b_n_per_m=1.0e9)
    modes = run_lateral_analysis(model, rpm=0.0, n_modes=3)
    # Analytical pure-Jeffcott (shaft simply supported at endpoints, disk
    # at midspan, ignoring shaft mass)
    E = 2.0e11  # Default Young's modulus
    D = 0.005
    I = math.pi / 64 * D**4
    L = 1.0
    K_shaft = 48 * E * I / L**3
    omega_jeffcott = math.sqrt(K_shaft / 10.0)
    omega_fem = modes[0].omega_d_rad_s
    rel_err = abs(omega_fem - omega_jeffcott) / omega_jeffcott
    # 5% tolerance because the shaft has a small but non-zero distributed
    # mass that lowers omega slightly.
    assert rel_err < 0.05, (
        f"Jeffcott first mode: FEM = {omega_fem:.3f} rad/s, "
        f"analytical = {omega_jeffcott:.3f} rad/s, "
        f"relative error = {rel_err:.4%}"
    )


def test_jeffcott_soft_bearing_rigid_shaft_translational_mode() -> None:
    """A rigid-shaft rotor on symmetric soft bearings has its translational
    (cylindrical) mode at omega = sqrt(2 K_b / m_total).
    """
    # Stiff thick shaft + small disk so it's effectively rigid
    sec = RotorSection(
        diameter_outer=Q(0.3, "m"),
        diameter_inner=Q(0.0, "m"),
        length=Q(1.0, "m"),
        density=Q(7850.0, "kg/m^3"),
        axial_position=Q(0.0, "m"),
        material="AISI4340",
    )
    disk = LumpedDisk(
        mass=Q(100.0, "kg"),
        inertia_polar=Q(0.5, "kg*m^2"),
        inertia_diametrical=Q(0.25, "kg*m^2"),
        axial_position=Q(0.5, "m"),
    )
    shape = RotorShape(sections=[sec], disks=[disk])
    K_b = 1.0e6
    brg1 = LinearBearing(
        name="b1",
        axial_position=Q(0.0, "m"),
        K_yy=Q(K_b, "N/m"),
        K_zz=Q(K_b, "N/m"),
        C_yy=Q(100.0, "N*s/m"),
        C_zz=Q(100.0, "N*s/m"),
    )
    brg2 = LinearBearing(
        name="b2",
        axial_position=Q(1.0, "m"),
        K_yy=Q(K_b, "N/m"),
        K_zz=Q(K_b, "N/m"),
        C_yy=Q(100.0, "N*s/m"),
        C_zz=Q(100.0, "N*s/m"),
    )
    model = build_rotor_model(shape, [brg1, brg2], elements_per_section=10)
    modes = run_lateral_analysis(model, rpm=0.0, n_modes=4)
    # Compute total mass
    D = 0.3
    L = 1.0
    rho = 7850
    A = math.pi / 4 * D**2
    m_shaft = rho * A * L
    m_total = m_shaft + 100.0  # disk
    omega_translational = math.sqrt(2 * K_b / m_total)
    omega_fem = modes[0].omega_d_rad_s
    rel_err = abs(omega_fem - omega_translational) / omega_translational
    assert rel_err < 1e-3, (
        f"Rigid-shaft on soft bearings: FEM = {omega_fem:.3f} rad/s, "
        f"analytical = {omega_translational:.3f} rad/s, "
        f"relative error = {rel_err:.6%}"
    )
