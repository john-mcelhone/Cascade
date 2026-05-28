"""ADAPT-003 locked regression: PSOR K matrix second column non-zero.

This test will FAIL if the pre-ADAPT-003 implementation is restored
(which left K[:, 1] = 0, making K_zz = K_yz = 0 for finite bearings).

Locked invariant: for L/D = 0.7 (a plain journal bearing), the full
2x2 stiffness matrix K must have all 4 entries non-zero. A bearing with
K_zz = 0 cannot support vertical load.

References:
- Lund, J.W. (1966). Spring and Damping Coefficients for the Tilting Pad
  Journal Bearing. ASLE Trans. 7: 342-352.
- ADAPT-003 (regression lock).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from cascade.rotor.journal_bearing import PlainJournalBearing
from cascade.units import Q


def test_adapt_003_k_matrix_second_column_nonzero_ld07() -> None:
    """Locked: K[1,0] and K[1,1] (second column) must be non-zero for L/D=0.7.

    Before ADAPT-003 the second column was hard-coded zero — the y-perturbation
    was applied but the z-perturbation was never done. This test fails
    immediately if column 2 is reverted to zero.
    """
    brg = PlainJournalBearing(
        name="adapt003_regression",
        axial_position=Q(0.0, "m"),
        diameter_m=0.05,
        length_m=0.035,   # L/D = 0.7
        clearance_m=5.0e-5,
        viscosity_pa_s=0.01,
        static_load_n=50.0,
        n_theta_grid=30,
        n_z_grid=20,
    )
    K, C = brg.coefficients_at_rpm(3000.0)

    assert K.shape == (2, 2), f"K must be 2x2; got shape {K.shape}"

    # Primary test: K[1, 0] must be non-zero (this is the element that
    # was explicitly fixed at journal_bearing.py:605 per the ADAPT-003 fix).
    assert abs(K[1, 0]) > 1.0e3, (
        f"ADAPT-003 regression: K[1,0] = {K[1, 0]:.3e}. "
        f"Should be non-zero (L/D=0.7 bearing has full 2x2 K matrix). "
        f"Pre-fix code hard-coded K[1,:] = 0."
    )
    assert K[1, 1] > 0.0, (
        f"ADAPT-003 regression: K[1,1] = {K[1, 1]:.3e}. "
        f"Direct stiffness K_zz must be positive. Pre-fix returned 0."
    )
    assert K[0, 0] > 0.0, f"K_yy must be positive; got {K[0, 0]:.3e}"

    # Cross-coupling check: K[0, 1] and K[1, 0] should have opposite signs
    # (canonical Lund / Someya asymmetry for plain journal bearings).
    assert K[0, 1] * K[1, 0] < 0, (
        f"K[0,1] * K[1,0] must be negative (oil-whirl cross-coupling); "
        f"got K[0,1]={K[0, 1]:.3e}, K[1,0]={K[1, 0]:.3e}. ADAPT-003."
    )


def test_adapt_003_all_K_entries_nonzero_at_ld05() -> None:
    """Locked: at L/D=0.5 (the PSOR threshold) all 4 K entries are non-zero."""
    brg = PlainJournalBearing(
        name="adapt003_ld05",
        axial_position=Q(0.0, "m"),
        diameter_m=0.05,
        length_m=0.025,  # L/D = 0.5
        clearance_m=5.0e-5,
        viscosity_pa_s=0.01,
        static_load_n=50.0,
        n_theta_grid=30,
        n_z_grid=15,
    )
    K, _ = brg.coefficients_at_rpm(3000.0)
    for i in range(2):
        for j in range(2):
            assert abs(K[i, j]) > 0.0, (
                f"ADAPT-003 regression: K[{i},{j}] = 0. All 4 entries of K "
                f"must be non-zero for a finite bearing (L/D=0.5). "
                f"Pre-fix hard-coded column 2 to zero."
            )
