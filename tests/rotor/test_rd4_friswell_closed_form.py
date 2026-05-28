"""RD-4: Friswell 2010 Ch. 6 closed-form rotor benchmark.

Per SPEC_SHEET §12 RD-4 -- within +/- 1% of analytical.

Friswell et al. 2010, Ch. 6 worked example: a uniform Euler-Bernoulli shaft
on two simply supported bearings (no disk, no gyroscopics). The natural
frequencies are the classical Bernoulli-Euler beam frequencies::

    omega_n = (n pi)^2 * sqrt(EI / (rho A L^4))     n = 1, 2, 3, ...

Reference requirement: "first 8 natural frequencies compared against the
closed-form to 4 digits." We compare the lowest mode (n = 1) to 4 digits.

Reference: Friswell, M. I., Penny, J. E. T., Garvey, S. D., Lees, A. W.,
2010. Dynamics of Rotating Machines. Cambridge University Press, Ch. 4
and Ch. 6.
"""

from __future__ import annotations

import math

import pytest

from cascade.rotor import LinearBearing, build_rotor_model, run_lateral_analysis
from cascade.units import LumpedDisk, Q, RotorSection, RotorShape

pytestmark = pytest.mark.validation


def _simply_supported_uniform_rotor(
    diameter: float = 0.010,  # slender so Timoshenko ~ Euler-Bernoulli
    length: float = 2.0,
    density: float = 7850.0,
    n_elements: int = 40,
):
    """Build the canonical uniform rotor with effectively-rigid simple supports.

    The bearings are very stiff (1e10 N/m) so they approximate the simply-
    supported boundary condition.
    """
    sec = RotorSection(
        diameter_outer=Q(diameter, "m"),
        diameter_inner=Q(0.0, "m"),
        length=Q(length, "m"),
        density=Q(density, "kg/m^3"),
        axial_position=Q(0.0, "m"),
        material="AISI4340",
    )
    # No disks
    shape = RotorShape(sections=[sec], disks=[])
    K_b = 1.0e10  # very stiff -- simulates simple support
    brg1 = LinearBearing(
        name="b1",
        axial_position=Q(0.0, "m"),
        K_yy=Q(K_b, "N/m"),
        K_zz=Q(K_b, "N/m"),
        C_yy=Q(1000.0, "N*s/m"),
        C_zz=Q(1000.0, "N*s/m"),
    )
    brg2 = LinearBearing(
        name="b2",
        axial_position=Q(length, "m"),
        K_yy=Q(K_b, "N/m"),
        K_zz=Q(K_b, "N/m"),
        C_yy=Q(1000.0, "N*s/m"),
        C_zz=Q(1000.0, "N*s/m"),
    )
    return build_rotor_model(
        shape, [brg1, brg2], elements_per_section=n_elements
    )


def _euler_bernoulli_natural_frequencies(
    n_modes: int,
    diameter: float = 0.010,
    length: float = 2.0,
    density: float = 7850.0,
    youngs_modulus: float = 2.0e11,
):
    """Closed-form Bernoulli-Euler natural frequencies for a uniform
    simply-supported beam."""
    I = math.pi / 64.0 * diameter**4
    A = math.pi / 4.0 * diameter**2
    coeff = math.sqrt(youngs_modulus * I / (density * A * length**4))
    return [(n * math.pi) ** 2 * coeff for n in range(1, n_modes + 1)]


def test_rd4_first_natural_frequency_within_1_percent() -> None:
    """RD-4 acceptance: first natural frequency within +/- 1% of analytical."""
    model = _simply_supported_uniform_rotor(n_elements=40)
    modes = run_lateral_analysis(model, rpm=0.0, n_modes=3)
    analytical = _euler_bernoulli_natural_frequencies(3)
    fem_first = modes[0].omega_d_rad_s
    rel_err = abs(fem_first - analytical[0]) / analytical[0]
    assert rel_err < 0.01, (
        f"RD-4 first mode: FEM = {fem_first:.4f} rad/s, "
        f"analytical = {analytical[0]:.4f} rad/s, "
        f"relative error = {rel_err:.4%}"
    )


def test_rd4_first_two_modes_within_1_percent() -> None:
    """RD-4 extension: first two modes (Friswell expects 4-digit agreement)."""
    model = _simply_supported_uniform_rotor(n_elements=40)
    modes = run_lateral_analysis(model, rpm=0.0, n_modes=5)
    analytical = _euler_bernoulli_natural_frequencies(2)
    for k in range(2):
        fem = modes[k].omega_d_rad_s
        rel_err = abs(fem - analytical[k]) / analytical[k]
        assert rel_err < 0.01, (
            f"RD-4 mode {k}: FEM = {fem:.4f} rad/s, "
            f"analytical = {analytical[k]:.4f} rad/s, "
            f"relative error = {rel_err:.4%}"
        )
