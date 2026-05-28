"""ADAPT-003: Christopherson PSOR finite-bearing K matrix regression test.

Before ADAPT-003, the PSOR finite-bearing K matrix had K_zz = K_yz = 0
(only column 1 from a y-perturbation was computed; column 2 was hard-coded
to zero). A bearing with K_zz = 0 cannot support vertical load -- this is
not a stiffness matrix, and the eigensolver downstream produces nonsense
frequencies for vertical mode shapes.

This test guards against regression to the zeroed-column-2 implementation.

References:
- Lund, J. W. (1966). Spring and Damping Coefficients for the Tilting Pad
  Journal Bearing. ASLE Trans. 7: 342-352.
- Someya, T. (1989). Journal-Bearing Databook. Springer.
- Childs, D. (1993), Turbomachinery Rotordynamics, Table 4.4.
- Pinkus, O. & Sternlicht, B. (1961), Theory of Hydrodynamic Lubrication.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from cascade.rotor.journal_bearing import (
    _journal_position_to_eps_phi,
    christopherson_psor_solve,
    integrate_force_lab_frame,
    ocvirk_load_capacity,
)


def _build_K_psor_direct(
    D: float,
    L: float,
    c: float,
    mu: float,
    rpm: float,
    eps_eq: float,
    n_theta: int = 60,
    n_z: int = 30,
    delta_frac: float = 0.005,
) -> tuple:
    """Compute the full 2x2 K matrix directly via PSOR + finite-difference
    perturbation in y and z (Lund 1966).

    This bypasses ``PlainJournalBearing.coefficients_at_rpm`` so we can
    test the PSOR path at any operating point without tripping the
    SPEC_SHEET §15 |K| < 1e10 N/m guard.
    """
    R = D / 2
    omega = rpm * 2.0 * math.pi / 60.0
    # Use Ocvirk closed form to estimate attitude angle at equilibrium.
    W_static_oc, phi_eq = ocvirk_load_capacity(omega, R, c, L, mu, eps_eq)
    # Equilibrium journal position (lab frame): h = c (1 + eps cos(theta-phi))
    # places minimum film at theta = phi + pi, so the journal lies along
    # (-cos phi, -sin phi).
    y_j0 = -c * eps_eq * math.cos(phi_eq)
    z_j0 = -c * eps_eq * math.sin(phi_eq)

    def force(y_j: float, z_j: float) -> tuple:
        eps_new, phi_new = _journal_position_to_eps_phi(y_j, z_j, c)
        eps_new = max(min(eps_new, 0.99), 1e-4)
        p, _, _ = christopherson_psor_solve(
            omega_rad_s=omega,
            radius_m=R,
            clearance_m=c,
            length_m=L,
            viscosity_pa_s=mu,
            eccentricity_ratio=eps_new,
            attitude_angle_rad=phi_new,
            n_theta=n_theta,
            n_z=n_z,
            relaxation=1.7,
            max_iter=5000,
        )
        return integrate_force_lab_frame(p, R, L)

    F_y0, F_z0 = force(y_j0, z_j0)
    delta = delta_frac * c
    F_y_py, F_z_py = force(y_j0 + delta, z_j0)
    F_y_pz, F_z_pz = force(y_j0, z_j0 + delta)
    K = np.array(
        [
            [-(F_y_py - F_y0) / delta, -(F_y_pz - F_y0) / delta],
            [-(F_z_py - F_z0) / delta, -(F_z_pz - F_z0) / delta],
        ]
    )
    return K, F_y0, F_z0, W_static_oc, phi_eq


def test_psor_K_matrix_has_no_zero_entries_at_l_d_half() -> None:
    """At L/D=0.5, eps=0.5 the K matrix has 4 non-zero entries.

    Regression guard: the old implementation hard-coded K[:, 1] = 0,
    leaving the bearing with no vertical-direction stiffness. This test
    fails immediately if column 2 is zeroed.
    """
    D = 0.05
    L = 0.025  # L/D = 0.5
    c = 2.5e-5
    mu = 0.02
    rpm = 6000.0
    eps_eq = 0.5
    K, _, _, _, _ = _build_K_psor_direct(D, L, c, mu, rpm, eps_eq)
    # Direct stiffnesses must be positive (restoring).
    assert K[0, 0] > 0, f"K_yy must be positive; got {K[0, 0]:.3e}"
    assert K[1, 1] > 0, f"K_zz must be positive; got {K[1, 1]:.3e}"
    # Cross-couplings must be non-zero (the destabilizing asymmetry source).
    assert abs(K[0, 1]) > 1.0e6, (
        f"K_yz must be non-zero (cross-coupling is the oil-whirl source); "
        f"got {K[0, 1]:.3e}"
    )
    assert abs(K[1, 0]) > 1.0e6, f"K_zy must be non-zero; got {K[1, 0]:.3e}"


def test_psor_K_matrix_cross_couplings_have_opposite_sign() -> None:
    """K_yz and K_zy have opposite signs in a plain journal bearing.

    This is the canonical Lund 1966 / Childs 1993 §4.3 destabilizing
    asymmetry: ``K_yz != -K_zy`` in general (the asymmetry is what makes
    plain journals subject to oil whirl), but in particular the two have
    *opposite signs* for the synchronous-rotation operating point.
    """
    D = 0.05
    L = 0.025
    c = 2.5e-5
    mu = 0.02
    rpm = 6000.0
    eps_eq = 0.5
    K, _, _, _, _ = _build_K_psor_direct(D, L, c, mu, rpm, eps_eq)
    assert K[0, 1] * K[1, 0] < 0, (
        f"K_yz and K_zy must have opposite signs (Lund 1966 / Childs 1993); "
        f"got K_yz={K[0, 1]:.3e}, K_zy={K[1, 0]:.3e}"
    )


def test_psor_K_matrix_direct_terms_within_someya_band() -> None:
    """At L/D=0.5, eps=0.5 the nondimensional direct K terms are in the
    Someya 1989 / Childs 1993 / Lund 1966 published band.

    Someya 1989 Table 1 (L/D=0.5, eps=0.5) reports K_bar_yy roughly in
    the band [1.5, 3.0] depending on the boundary-condition convention
    (Reynolds / Gümbel / pi-film). The Christopherson PSOR uses the
    Reynolds (full-film, p >= 0) boundary condition; literature values
    for this BC at the test point span ~ 1.9 to 3.0.

    The PSOR-computed dimensional K is normalized by the *PSOR-static
    load* (NOT the Ocvirk reference, which overpredicts the load by
    ~15-20 % at L/D=0.5). This is the convention used by Someya.
    """
    D = 0.05
    L = 0.025
    c = 2.5e-5
    mu = 0.02
    rpm = 6000.0
    eps_eq = 0.5
    K, F_y0, F_z0, _, _ = _build_K_psor_direct(D, L, c, mu, rpm, eps_eq)
    # Static load magnitude from PSOR
    W_psor = math.hypot(F_y0, F_z0)
    assert W_psor > 1.0, f"PSOR static load too small: {W_psor:.3e}"
    K_bar_yy = abs(K[0, 0]) * c / W_psor
    K_bar_zz = abs(K[1, 1]) * c / W_psor
    # Per spec / Someya 1989: K_bar_yy ~ 1.94 (Reynolds BC, L/D=0.5, eps=0.5).
    # Allow a wide band [1.0, 3.5] to cover the literature spread.
    assert 1.0 <= K_bar_yy <= 3.5, (
        f"K_bar_yy = {K_bar_yy:.3f} outside Someya 1989 / Childs 1993 band "
        f"[1.0, 3.5] for L/D=0.5, eps=0.5."
    )
    assert 1.0 <= K_bar_zz <= 3.5, (
        f"K_bar_zz = {K_bar_zz:.3f} outside Someya 1989 / Childs 1993 band "
        f"[1.0, 3.5] for L/D=0.5, eps=0.5."
    )


def test_plain_journal_bearing_K_matrix_has_no_zero_column() -> None:
    """The high-level PlainJournalBearing class also returns a K matrix
    with all 4 entries populated for L/D >= 0.5.

    This is the end-to-end test of the bearing API. The bearing geometry
    is chosen so |K| stays below the 1e10 N/m SPEC_SHEET §15 ceiling.
    """
    from cascade.rotor.journal_bearing import PlainJournalBearing
    from cascade.units import Q

    # Use a higher viscosity / lower rpm to keep K below the 1e10 limit.
    brg = PlainJournalBearing(
        name="psor_validation",
        axial_position=Q(0.0, "m"),
        diameter_m=0.05,
        length_m=0.025,  # L/D = 0.5
        clearance_m=5.0e-5,  # larger clearance => lower K
        viscosity_pa_s=0.01,  # lower visc => lower K
        static_load_n=100.0,
        n_theta_grid=30,
        n_z_grid=15,
    )
    K, C = brg.coefficients_at_rpm(3000.0)
    assert K.shape == (2, 2)
    assert np.all(np.abs(K) > 0.0), (
        f"K matrix must have all 4 entries non-zero; got K=\n{K}"
    )
    assert K[0, 0] > 0, f"K_yy must be positive; got {K[0, 0]:.3e}"
    assert K[1, 1] > 0, f"K_zz must be positive; got {K[1, 1]:.3e}"
    # Cross-coupling opposite-sign (oil-whirl signature)
    assert K[0, 1] * K[1, 0] < 0, (
        f"K_yz * K_zy < 0 required (oil-whirl asymmetry); "
        f"got K_yz={K[0, 1]:.3e}, K_zy={K[1, 0]:.3e}"
    )
    # C matrix also needs all 4 entries
    assert C.shape == (2, 2)
    assert C[0, 0] > 0, f"C_yy must be positive (damping); got {C[0, 0]:.3e}"
    assert C[1, 1] > 0, f"C_zz must be positive (damping); got {C[1, 1]:.3e}"
