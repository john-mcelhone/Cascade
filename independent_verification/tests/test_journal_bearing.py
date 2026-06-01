"""Independent verification — plain-journal (hydrodynamic) bearing.

Oracles are universal hydrodynamic-lubrication facts:
  - The journal rides inside its clearance: eccentricity ratio in [0, 1)
  - Higher load pushes the journal toward the wall (eccentricity rises)
  - Higher speed builds more film lift (eccentricity falls at fixed load)
  - Direct stiffness and damping are positive (restoring / dissipative)
  - Cross-coupled stiffness is asymmetric (K_xy != K_yx): the oil-whirl source
  - Reynolds film pressure is non-negative under the cavitation BC
  - Load capacity grows monotonically with eccentricity
"""

from __future__ import annotations

import math

import numpy as np

from cascade.rotor import PlainJournalBearing
from cascade.rotor.journal_bearing import christopherson_psor_solve, ocvirk_load_capacity
from cascade.units import Q


def _bearing(load_n: float = 500.0) -> PlainJournalBearing:
    return PlainJournalBearing(name="jb", axial_position=Q(0.1, "m"), diameter_m=0.05,
                               length_m=0.025, clearance_m=5e-5, viscosity_pa_s=0.01,
                               static_load_n=load_n)


def test_equilibrium_eccentricity_within_clearance() -> None:
    jb = _bearing()
    for rpm in (1500.0, 3000.0, 6000.0, 12000.0):
        ecc = jb.equilibrium_eccentricity(rpm)
        assert 0.0 < ecc < 1.0


def test_eccentricity_decreases_with_speed() -> None:
    jb = _bearing()
    eccs = [jb.equilibrium_eccentricity(rpm) for rpm in (1500.0, 3000.0, 6000.0, 12000.0)]
    for hi_e, lo_e in zip(eccs, eccs[1:]):
        assert lo_e < hi_e


def test_eccentricity_increases_with_load() -> None:
    eccs = [_bearing(load_n=w).equilibrium_eccentricity(3000.0) for w in (150.0, 400.0, 900.0, 1800.0)]
    for lo_e, hi_e in zip(eccs, eccs[1:]):
        assert hi_e > lo_e


def test_direct_stiffness_and_damping_positive() -> None:
    k, c = _bearing().coefficients_at_rpm(3000.0)
    assert k[0, 0] > 0.0 and k[1, 1] > 0.0
    assert c[0, 0] > 0.0 and c[1, 1] > 0.0


def test_cross_coupled_stiffness_is_asymmetric() -> None:
    """K_xy != K_yx is the destabilizing asymmetry behind oil whirl."""
    k, _ = _bearing().coefficients_at_rpm(6000.0)
    assert abs(k[0, 1] - k[1, 0]) > 1e3


def test_direct_stiffness_in_canonical_range() -> None:
    k, _ = _bearing().coefficients_at_rpm(3000.0)
    assert 1e5 <= abs(k[0, 0]) <= 1e11


def test_reynolds_pressure_is_non_negative() -> None:
    """Christopherson cavitation BC: film pressure cannot go negative."""
    omega = 6000.0 * 2 * math.pi / 60.0
    p, _h, residual = christopherson_psor_solve(
        omega_rad_s=omega, radius_m=0.025, clearance_m=5e-5, length_m=0.025,
        viscosity_pa_s=0.01, eccentricity_ratio=0.5, n_theta=30, n_z=15,
        max_iter=2000, tol=1e-6,
    )
    assert residual < 1e-4
    assert (np.asarray(p) >= -1e-6).all()
    assert np.asarray(p).max() > 1e4  # a real load is being carried


def test_load_capacity_monotonic_in_eccentricity() -> None:
    omega = 3000.0 * 2 * math.pi / 60.0
    loads = [ocvirk_load_capacity(omega, 0.025, 2.5e-5, 0.025, 0.02, eps)[0]
             for eps in (0.1, 0.3, 0.5, 0.7, 0.9)]
    for lo, hi in zip(loads, loads[1:]):
        assert hi > lo
