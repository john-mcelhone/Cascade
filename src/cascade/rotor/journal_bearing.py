"""Plain-journal bearing K-C solver.

Provides two solvers:

1. **Ocvirk short-bearing closed form** (L/D < 0.3 -- per the Ocvirk 1952
   paper's own range-of-validity claim where the eccentricity-direction
   pressure-gradient term dominates).
   Drops the d/dx (h^3 dp/dx) term in Reynolds; closed-form load capacity
   and pressure profile. Lund 1968 perturbation gives the 8 stiffness +
   damping coefficients.

2. **Christopherson PSOR (Projected Successive Over-Relaxation)** for 2D
   finite-bearing Reynolds solve with the Reynolds (Christopherson 1941)
   boundary condition for cavitation. This is the v1 finite-bearing solver
   per SPEC_SHEET §9.

ADAPT-039: the Ocvirk / PSOR dispatch threshold was previously L/D < 0.5,
which silently extrapolated the Ocvirk approximation into the 0.3 -- 0.5
band where both solutions are only approximately valid. The threshold is
now L/D < 0.3, matching Ocvirk 1952's own published range.

ADAPT-044 (W-15): For finite bearings (L/D >= 0.3) the damping tensor C is
now extracted via the eccentricity-rate perturbation method (Lund & Thomsen
1978) instead of the Ocvirk closed-form fallback.  The squeeze-film source
term ``dh/dt = -vy cos(theta) - vz sin(theta)`` is added to the PSOR
right-hand side and the perturbed pressure is integrated to give the full
2x2 C matrix.  Two PSOR passes (one for vy perturbation, one for vz) yield
C_yy, C_yz, C_zy, C_zz.

The Reynolds equation in unwrapped journal-bearing coordinates is

    d/dx [h^3 / (12 mu) dp/dx] + d/dz [h^3 / (12 mu) dp/dz]
        = (U_p / 2) dh/dx + dh/dt

with U_p = Omega * R the surface velocity. We solve for steady-state
(dh/dt = 0). The Christopherson boundary condition is the simple
projected-SOR cavitation BC:

    if p < p_cav: set p := p_cav

applied at each PSOR sweep update. This conservatively enforces p >= p_cav
(no negative pressure) and gives the canonical "Reynolds boundary condition"
result that API 684 references as the steady-state K-C extraction default.

References:
- Christopherson, D. G., 1941. A New Mathematical Method for the Solution
  of Film Lubrication Problems. Proc. Inst. Mech. Engrs. 146: 126-135.
- Ocvirk, F. W., 1952. Short-Bearing Approximation for Full Journal Bearings.
  NACA TN 2808.
- Lund, J. W., 1966. Spring and Damping Coefficients for the Tilting Pad
  Journal Bearing. ASLE Trans. 7: 342-352.
- Lund, J. W. & Thomsen, K. K., 1978. A Calculation Method for Journal
  Bearings, in Fundamentals of the Design of Fluid Film Bearings, ASME,
  pp. 1-28.
- Pinkus, O. & Sternlicht, B., 1961. Theory of Hydrodynamic Lubrication. Ch. 5-6.
- Someya, T., 1989. Journal-Bearing Databook. Springer.
- Childs, D., 1993. Turbomachinery Rotordynamics. Ch. 4-5.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from cascade.rotor.bearings import Bearing
from cascade.units import Q, Quantity


# --- Short-bearing closed form (Ocvirk 1952) -------------------------------


def ocvirk_load_capacity(
    omega_rad_s: float,
    radius_m: float,
    clearance_m: float,
    length_m: float,
    viscosity_pa_s: float,
    eccentricity_ratio: float,
) -> Tuple[float, float]:
    """Ocvirk short-bearing load capacity and attitude angle.

    Returns (W [N], phi_0 [rad]).

    The closed form (Pinkus & Sternlicht 1961 eq. 5.13a):

        W = (mu * Omega * L^3 * R) / (4 * c^2) *
            eps * sqrt(16 eps^2 + pi^2 (1 - eps^2)) / (1 - eps^2)^2

        phi_0 = atan(pi sqrt(1 - eps^2) / (4 eps))

    Eccentricity ratio eps = e_j / c, with c the radial clearance.

    >>> # Sanity: at eps -> 0 we have load -> 0 and phi_0 -> pi/2
    >>> w, p = ocvirk_load_capacity(100.0, 0.025, 5e-5, 0.025, 0.01, 1e-6)
    >>> abs(p - math.pi/2) < 0.01
    True
    """
    if eccentricity_ratio <= 0 or eccentricity_ratio >= 1.0:
        msg = f"Eccentricity ratio must be in (0, 1); got {eccentricity_ratio}"
        raise ValueError(msg)
    eps = eccentricity_ratio
    c = clearance_m
    L = length_m
    R = radius_m
    mu = viscosity_pa_s
    Omega = omega_rad_s
    W = (mu * Omega * L**3 * R) / (4 * c**2)
    W *= eps * math.sqrt(16 * eps**2 + math.pi**2 * (1 - eps**2))
    W /= (1 - eps**2) ** 2
    phi_0 = math.atan(math.pi * math.sqrt(1 - eps**2) / (4 * eps))
    return float(W), float(phi_0)


def ocvirk_stiffness_damping(
    omega_rad_s: float,
    radius_m: float,
    clearance_m: float,
    length_m: float,
    viscosity_pa_s: float,
    eccentricity_ratio: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Ocvirk short-bearing K and C coefficients via Lund 1968 perturbation.

    Returns (K, C), each a (2, 2) numpy array in SI (K [N/m], C [N s/m]).

    K, C are dimensionalized via the load and operating frequency. Lund's
    nondimensional groups are (Childs 1993 eq. 4.115; Pinkus & Sternlicht
    1961 §6.2). The closed-form expressions in terms of eccentricity ratio
    are well-known but algebraically lengthy. We code the Lund 1968 short
    bearing results.

    For the short bearing at eccentricity ratio eps, the dimensionless
    coefficients (k_ij_bar) and (c_ij_bar) are functions of eps only.
    Dimensionalization: K = (W / c) * k_bar; C = (W / (c * Omega)) * c_bar.

    Reference closed-form (Childs 1993 Table 4.4 / Pinkus & Sternlicht
    1961 Table 6-1, short-bearing column):

        h0 = (1 - eps^2)
        K_xx_bar = 4 * (pi^2 (1 + 2 eps^2) + 16 eps^2) / (h0 * D_s)
        K_yy_bar = 4 * (pi^2 (1 + 2 eps^2) - 16 eps^2) / (h0 * D_s)   -- (alt sign)
        K_xy_bar = -pi * (pi^2 (1 - eps^2) + 32 eps^2 + 16 eps^4) / (h0 D_s)
        K_yx_bar =  pi * (pi^2 (1 + eps^2)^2 - 16 eps^4) / (h0 D_s)
        D_s = sqrt(pi^2 (1 - eps^2) + 16 eps^2)

    The damping analog:
        C_xx_bar = 2 pi * sqrt(1 - eps^2) * (pi^2 (1 + 2 eps^2) - 16 eps^2)
                   / (h0 D_s)
        ...

    These match Someya 1989 short-bearing entries within typesetting.

    NOTE: the Lund 1968 paper uses a different attitude-angle reference
    frame than Someya 1989; our K, C are returned in the (y = load
    direction, z = anti-load direction) frame. This is the convention
    used in cascade.rotor.bearings (y horizontal lateral, z vertical
    lateral with the load = gravity along -z).
    """
    eps = eccentricity_ratio
    c = clearance_m
    Omega = omega_rad_s
    W, phi_0 = ocvirk_load_capacity(
        Omega, radius_m, clearance_m, length_m, viscosity_pa_s, eps
    )
    if W <= 0:
        return np.zeros((2, 2)), np.zeros((2, 2))

    h0 = 1 - eps**2
    D_s = math.sqrt(math.pi**2 * (1 - eps**2) + 16 * eps**2)
    # Lund/Childs short-bearing nondim coefficients
    k_xx_bar = 4.0 * (math.pi**2 * (1 + 2 * eps**2) + 16 * eps**2) / (h0 * D_s)
    k_yy_bar = (
        4.0
        * (math.pi**2 * (1 + 2 * eps**2) - 16 * eps**2 + 32 * eps**4 / h0)
        / (h0 * D_s)
    )
    k_xy_bar = (
        math.pi
        * (math.pi**2 * (1 - eps**2) ** 2 - 16 * eps**4)
        / (math.sqrt(1 - eps**2) * h0**2 * D_s)
    )
    k_yx_bar = (
        -math.pi
        * (math.pi**2 * (1 + eps**2) + 32 * eps**2 * (1 + eps**2))
        / (math.sqrt(1 - eps**2) * h0**2 * D_s)
    )
    c_xx_bar = (
        2
        * math.pi
        * math.sqrt(1 - eps**2)
        * (math.pi**2 * (1 + 2 * eps**2) - 16 * eps**2)
        / (h0 * D_s)
    )
    c_yy_bar = (
        2
        * math.pi
        * (math.pi**2 * (1 - eps**2) ** 2 + 48 * eps**2)
        / (math.sqrt(1 - eps**2) * h0**2 * D_s)
    )
    c_xy_bar = -8.0 * (math.pi**2 * (1 + 2 * eps**2) - 16 * eps**2) / (h0 * D_s)
    c_yx_bar = c_xy_bar

    K = (W / c) * np.array(
        [[k_xx_bar, k_xy_bar], [k_yx_bar, k_yy_bar]], dtype=float
    )
    C = (W / (c * Omega)) * np.array(
        [[c_xx_bar, c_xy_bar], [c_yx_bar, c_yy_bar]], dtype=float
    )
    return K, C


# --- Christopherson PSOR finite-bearing Reynolds solver --------------------


def reynolds_film_thickness(
    theta: np.ndarray, eps: float, attitude_phi: float, clearance_m: float
) -> np.ndarray:
    """h(theta) = c (1 + eps cos(theta - phi)) for the unwrapped journal."""
    return clearance_m * (1.0 + eps * np.cos(theta - attitude_phi))


def christopherson_psor_solve(
    omega_rad_s: float,
    radius_m: float,
    clearance_m: float,
    length_m: float,
    viscosity_pa_s: float,
    eccentricity_ratio: float,
    attitude_angle_rad: float = 0.0,
    n_theta: int = 60,
    n_z: int = 30,
    relaxation: float = 1.7,
    p_cav_pa: float = 0.0,
    tol: float = 1e-6,
    max_iter: int = 5000,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Solve the steady-state 2D Reynolds equation with PSOR + cavitation.

    The unwrapped grid is theta in [0, 2 pi] (circumferential, with periodic
    BC) and z in [-L/2, +L/2] (axial, with p = p_cav at the edges).

    Returns (pressure_grid, h_grid, residual). pressure_grid and h_grid have
    shape (n_theta, n_z); residual is the final L2 residual.

    Algorithm (Christopherson 1941, Pinkus & Sternlicht 1961 §6.4):

    1. Discretize Reynolds: at each interior grid point,
        a * (p_{i+1,j} + p_{i-1,j}) + b * (p_{i,j+1} + p_{i,j-1}) - (2a + 2b) p_ij
            = RHS
        where a, b depend on h^3 / mu averaged at faces and grid spacing.

    2. Successive over-relaxation update:
        p_ij_new = (1 - omega_r) p_ij + omega_r * [RHS + a*(...) + b*(...)] / (2a+2b)

    3. Projected step: p_ij_new = max(p_ij_new, p_cav).

    4. Repeat until L2 residual < tol or max_iter exceeded.

    The Christopherson "projected SOR" is the v1 cavitation-BC method per
    SPEC_SHEET §9. Default relaxation 1.7 is
    the canonical value from Pinkus & Sternlicht 1961 Table 6-3 (optimum
    for this grid size at L/D = 0.5-1.0).
    """
    R = radius_m
    L = length_m
    mu = viscosity_pa_s
    U_p = omega_rad_s * R  # journal surface velocity
    eps = eccentricity_ratio

    # Grids
    theta = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=False)
    z = np.linspace(-L / 2.0, +L / 2.0, n_z)
    dtheta = 2.0 * math.pi / n_theta  # circumferential, periodic
    dz = z[1] - z[0]
    # x-coordinate (circumferential length): x = R theta
    dx = R * dtheta

    # Film thickness (function of theta only for a plain journal)
    h_1d = clearance_m * (1.0 + eps * np.cos(theta - attitude_angle_rad))
    h = np.broadcast_to(h_1d[:, None], (n_theta, n_z)).copy()

    # Face-centered h^3 for finite-volume averaging
    h_face_x = 0.5 * (h + np.roll(h, -1, axis=0))  # average i, i+1
    h_face_x_prev = 0.5 * (h + np.roll(h, +1, axis=0))  # average i-1, i

    # RHS = d(h)/dx * U_p / 2 (the wedge term). dh/dx = (h_{i+1} - h_{i-1}) / (2 dx)
    dh_dx = (np.roll(h, -1, axis=0) - np.roll(h, +1, axis=0)) / (2.0 * dx)
    rhs = (U_p / 2.0) * dh_dx
    # Constant in z; broadcast
    rhs = rhs * np.ones((1, n_z))

    # Initial pressure
    p = np.zeros((n_theta, n_z), dtype=float)

    # PSOR iteration
    residual = 1.0
    for it in range(max_iter):
        p_old = p.copy()
        # Update interior points (1 <= j <= n_z - 2 in axial; periodic in
        # theta direction).
        for j in range(1, n_z - 1):
            for i in range(n_theta):
                ip = (i + 1) % n_theta
                im = (i - 1) % n_theta
                h_e = h_face_x[i, j]  # face between i and i+1
                h_w = h_face_x_prev[i, j]  # face between i-1 and i
                h_n = 0.5 * (h[i, j] + h[i, j + 1])  # face between j and j+1
                h_s = 0.5 * (h[i, j] + h[i, j - 1])  # face between j-1 and j

                a_e = h_e**3 / (12.0 * mu * dx * dx)
                a_w = h_w**3 / (12.0 * mu * dx * dx)
                a_n = h_n**3 / (12.0 * mu * dz * dz)
                a_s = h_s**3 / (12.0 * mu * dz * dz)
                a_p = a_e + a_w + a_n + a_s

                # Gauss-Seidel update (read latest p values where available)
                p_new = (
                    a_e * p[ip, j]
                    + a_w * p[im, j]
                    + a_n * p[i, j + 1]
                    + a_s * p[i, j - 1]
                    - rhs[i, j]
                ) / a_p

                # Relaxation
                p_relaxed = (1.0 - relaxation) * p[i, j] + relaxation * p_new
                # Project (Christopherson 1941 cavitation BC)
                if p_relaxed < p_cav_pa:
                    p_relaxed = p_cav_pa
                p[i, j] = p_relaxed
        # Axial BCs: p(z = +/- L/2) = p_cav (ambient)
        p[:, 0] = p_cav_pa
        p[:, -1] = p_cav_pa
        # Residual
        residual = float(np.linalg.norm(p - p_old) / max(np.linalg.norm(p), 1e-12))
        if residual < tol:
            break

    return p, h, residual


def christopherson_psor_solve_with_squeeze(
    omega_rad_s: float,
    radius_m: float,
    clearance_m: float,
    length_m: float,
    viscosity_pa_s: float,
    eccentricity_ratio: float,
    attitude_angle_rad: float = 0.0,
    vy_dot: float = 0.0,
    vz_dot: float = 0.0,
    n_theta: int = 60,
    n_z: int = 30,
    relaxation: float = 1.7,
    p_cav_pa: float = 0.0,
    tol: float = 1e-6,
    max_iter: int = 5000,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Solve the 2D Reynolds equation with PSOR + cavitation + squeeze-film.

    Extends :func:`christopherson_psor_solve` to include the squeeze-film
    source term ``dh/dt`` that arises when the journal centre has a lateral
    velocity ``(vy_dot, vz_dot)`` in the lab frame.

    The complete Reynolds RHS is::

        RHS = (U_p / 2) * dh/dx  +  dh/dt

    where the squeeze-film rate for a journal moving at velocity
    ``(vy_dot, vz_dot)`` is (Lund & Thomsen 1978, eq. 3.4)::

        dh/dt = -vy_dot * cos(theta)  -  vz_dot * sin(theta)

    The sign convention matches the film-thickness definition
    ``h = c (1 + eps cos(theta - phi))``: a journal velocity component
    *toward* the bearing wall (decreasing film) increases the squeeze
    pressure.

    Parameters
    ----------
    vy_dot, vz_dot : float
        Lab-frame journal-centre velocity components [m/s].  Set one at a
        time (with the other = 0) to extract one column of the damping
        matrix C via finite-difference perturbation.
    All other parameters : same as :func:`christopherson_psor_solve`.

    Returns
    -------
    (pressure_grid, h_grid, residual)

    References
    ----------
    Lund, J. W. & Thomsen, K. K., 1978. A Calculation Method for Journal
    Bearings, in Fundamentals of the Design of Fluid Film Bearings, ASME,
    pp. 1-28.  (squeeze-film term for velocity perturbation, eq. 3.4)

    Childs, D., 1993. Turbomachinery Rotordynamics, Ch. 5.4
    (perturbation approach for damping coefficients).
    """
    R = radius_m
    L = length_m
    mu = viscosity_pa_s
    U_p = omega_rad_s * R  # journal surface velocity
    eps = eccentricity_ratio

    # Grids
    theta = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=False)
    z = np.linspace(-L / 2.0, +L / 2.0, n_z)
    dtheta = 2.0 * math.pi / n_theta
    dz = z[1] - z[0]
    dx = R * dtheta  # circumferential arc length per theta step

    # Film thickness
    h_1d = clearance_m * (1.0 + eps * np.cos(theta - attitude_angle_rad))
    h = np.broadcast_to(h_1d[:, None], (n_theta, n_z)).copy()

    # Face-centred h^3
    h_face_x = 0.5 * (h + np.roll(h, -1, axis=0))
    h_face_x_prev = 0.5 * (h + np.roll(h, +1, axis=0))

    # Wedge RHS (steady-state rotation term)
    dh_dx = (np.roll(h, -1, axis=0) - np.roll(h, +1, axis=0)) / (2.0 * dx)
    rhs_wedge = (U_p / 2.0) * dh_dx * np.ones((1, n_z))

    # Squeeze-film RHS: dh/dt = -vy_dot cos(theta) - vz_dot sin(theta)
    # (Lund & Thomsen 1978 eq. 3.4, adapted to lab-frame velocity components)
    dh_dt_1d = -vy_dot * np.cos(theta) - vz_dot * np.sin(theta)
    rhs_squeeze = dh_dt_1d[:, None] * np.ones((1, n_z))

    rhs = rhs_wedge + rhs_squeeze

    # Initial pressure
    p = np.zeros((n_theta, n_z), dtype=float)

    # PSOR iteration
    residual = 1.0
    for it in range(max_iter):
        p_old = p.copy()
        for j in range(1, n_z - 1):
            for i in range(n_theta):
                ip = (i + 1) % n_theta
                im = (i - 1) % n_theta
                h_e = h_face_x[i, j]
                h_w = h_face_x_prev[i, j]
                h_n = 0.5 * (h[i, j] + h[i, j + 1])
                h_s = 0.5 * (h[i, j] + h[i, j - 1])

                a_e = h_e**3 / (12.0 * mu * dx * dx)
                a_w = h_w**3 / (12.0 * mu * dx * dx)
                a_n = h_n**3 / (12.0 * mu * dz * dz)
                a_s = h_s**3 / (12.0 * mu * dz * dz)
                a_p = a_e + a_w + a_n + a_s

                p_new = (
                    a_e * p[ip, j]
                    + a_w * p[im, j]
                    + a_n * p[i, j + 1]
                    + a_s * p[i, j - 1]
                    - rhs[i, j]
                ) / a_p

                p_relaxed = (1.0 - relaxation) * p[i, j] + relaxation * p_new
                if p_relaxed < p_cav_pa:
                    p_relaxed = p_cav_pa
                p[i, j] = p_relaxed
        p[:, 0] = p_cav_pa
        p[:, -1] = p_cav_pa
        residual = float(np.linalg.norm(p - p_old) / max(np.linalg.norm(p), 1e-12))
        if residual < tol:
            break

    return p, h, residual


def integrate_load_from_pressure(
    p: np.ndarray, radius_m: float, length_m: float, attitude_phi: float = 0.0
) -> Tuple[float, float]:
    """Integrate pressure to get the bearing load in the eccentricity frame.

    Returns ``(W_xi, W_eta)`` where xi is along the *eccentricity-frame*
    radial direction (toward +phi) and eta is along the perpendicular
    (tangential) direction at +90 deg from xi.

    These are NOT lab-frame y, z components. Use
    :func:`integrate_load_lab_frame` to get lab-frame forces on the journal.

    Definitions (consistent with the code's
    ``h = c (1 + eps cos(theta - phi))`` convention)::

        W_xi  = -int p cos(theta - phi) R dtheta dz   (radial, along +phi)
        W_eta = -int p sin(theta - phi) R dtheta dz   (tangential)

    Returns ``(W_xi, W_eta)`` in N.

    .. note::

        For backward compatibility the symbols ``W_y`` / ``W_z`` are
        retained in the call sites in this module; they refer to the
        eccentricity-frame components, not the lab frame. The K-C matrix
        computation in :meth:`PlainJournalBearing.coefficients_at_rpm`
        explicitly transforms to the lab frame.
    """
    n_theta, n_z = p.shape
    theta = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=False)
    z = np.linspace(-length_m / 2.0, +length_m / 2.0, n_z)
    dtheta = 2.0 * math.pi / n_theta
    dz = z[1] - z[0]
    cos_t = np.cos(theta - attitude_phi)
    sin_t = np.sin(theta - attitude_phi)
    # Integrate
    W_xi = -np.sum(p * cos_t[:, None]) * radius_m * dtheta * dz
    W_eta = -np.sum(p * sin_t[:, None]) * radius_m * dtheta * dz
    return float(W_xi), float(W_eta)


def integrate_force_lab_frame(
    p: np.ndarray, radius_m: float, length_m: float
) -> Tuple[float, float]:
    """Integrate pressure to get the lab-frame fluid force on the journal.

    The film pressure ``p(theta, z)`` acts on the journal surface. Each
    surface patch at angle theta has outward normal (looking from the
    bearing center) at ``(cos theta, sin theta)`` -- so the differential
    force the bearing fluid exerts on the journal is
    ``dF = -p (cos theta, sin theta) R dtheta dz`` (pressure pushes the
    journal toward the bearing center).

    Returns ``(F_y, F_z)`` in N (lab-frame components of the total fluid
    force on the journal). For a journal at static equilibrium, this is
    minus the static load.
    """
    n_theta, n_z = p.shape
    theta = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=False)
    z = np.linspace(-length_m / 2.0, +length_m / 2.0, n_z)
    dtheta = 2.0 * math.pi / n_theta
    dz = z[1] - z[0]
    cos_t = np.cos(theta)
    sin_t = np.sin(theta)
    F_y = -np.sum(p * cos_t[:, None]) * radius_m * dtheta * dz
    F_z = -np.sum(p * sin_t[:, None]) * radius_m * dtheta * dz
    return float(F_y), float(F_z)


def _journal_position_to_eps_phi(
    y_j: float, z_j: float, clearance_m: float
) -> Tuple[float, float]:
    """Convert lab-frame journal position to ``(eps, phi)`` for the Reynolds
    solver.

    With the code's convention ``h(theta) = c (1 + eps cos(theta - phi))``
    the minimum film thickness occurs at ``theta = phi + pi``, which is the
    direction the journal lies in (the journal touches the bearing wall
    there). So the journal position vector ``(y_j, z_j)`` points along
    ``(cos(phi + pi), sin(phi + pi)) = (-cos phi, -sin phi)``.

    Inverting: ``phi = atan2(-z_j, -y_j) = atan2(z_j, y_j) + pi``, and
    ``eps = sqrt(y_j^2 + z_j^2) / c``.
    """
    e = math.hypot(y_j, z_j)
    eps = e / clearance_m
    if e < 1e-15:
        return 0.0, 0.0
    # phi is the angle of -journal_position vector
    phi = math.atan2(-z_j, -y_j)
    return eps, phi


def _psor_damping_tensor(
    omega_rad_s: float,
    radius_m: float,
    clearance_m: float,
    length_m: float,
    viscosity_pa_s: float,
    eccentricity_ratio: float,
    attitude_angle_rad: float,
    F_y0: float,
    F_z0: float,
    n_theta: int = 60,
    n_z: int = 30,
    relaxation: float = 1.7,
) -> np.ndarray:
    """Extract the 2x2 damping tensor C via eccentricity-rate perturbation.

    Applies a small velocity perturbation ``delta_v`` to the journal centre
    in each of the two lab-frame directions (y, z) and re-solves the
    Reynolds equation with the squeeze-film source term ``dh/dt``.  The
    resulting change in integrated fluid force gives one column of C per
    perturbation direction.

    The damping matrix convention follows Lund & Thomsen 1978 and Someya
    1989: ``C_ij = -d F_i / d(qdot_j)`` where F is the lab-frame fluid
    force on the journal.

    A velocity perturbation ``delta_v`` in the y-direction gives::

        C_yy = -(F_y_perturbed - F_y0) / delta_v
        C_zy = -(F_z_perturbed - F_z0) / delta_v

    A perturbation in the z-direction gives the second column.

    The perturbation amplitude is chosen as ``delta_v = 1% * c * omega``,
    small enough for linearity but large enough to avoid numerical noise.

    Parameters
    ----------
    F_y0, F_z0 : float
        Equilibrium lab-frame fluid forces already computed at the
        equilibrium operating point (avoids re-solving the equilibrium).

    Returns
    -------
    C : np.ndarray, shape (2, 2)
        The 2x2 damping matrix [N s/m].

    References
    ----------
    Lund, J. W. & Thomsen, K. K., 1978. A Calculation Method for Journal
    Bearings, in Fundamentals of the Design of Fluid Film Bearings, ASME,
    pp. 1-28.

    Childs, D., 1993. Turbomachinery Rotordynamics, §5.4. Wiley.

    Someya, T., 1989. Journal-Bearing Databook. Springer.
    """
    R = radius_m
    # Perturbation velocity: 1% of the nominal journal surface speed.
    # This is small enough for linearity and large enough to avoid
    # numerical-differencing noise at double precision.
    delta_v = 0.01 * clearance_m * omega_rad_s
    if delta_v < 1e-9:
        delta_v = 1e-6  # fallback for near-zero speed

    def _force_with_vel(vy_dot: float, vz_dot: float) -> Tuple[float, float]:
        """Solve Reynolds with squeeze-film and return lab-frame forces."""
        p_field, _, _ = christopherson_psor_solve_with_squeeze(
            omega_rad_s=omega_rad_s,
            radius_m=R,
            clearance_m=clearance_m,
            length_m=length_m,
            viscosity_pa_s=viscosity_pa_s,
            eccentricity_ratio=eccentricity_ratio,
            attitude_angle_rad=attitude_angle_rad,
            vy_dot=vy_dot,
            vz_dot=vz_dot,
            n_theta=n_theta,
            n_z=n_z,
            relaxation=relaxation,
        )
        return integrate_force_lab_frame(p_field, R, length_m)

    # Column 1: perturb in y-direction
    F_y_vy, F_z_vy = _force_with_vel(delta_v, 0.0)
    # Column 2: perturb in z-direction
    F_y_vz, F_z_vz = _force_with_vel(0.0, delta_v)

    # C_ij = -dF_i / d(vj)  (the film force opposes journal velocity)
    C = np.array(
        [
            [-(F_y_vy - F_y0) / delta_v, -(F_y_vz - F_y0) / delta_v],
            [-(F_z_vy - F_z0) / delta_v, -(F_z_vz - F_z0) / delta_v],
        ]
    )
    return C


# --- High-level: PlainJournalBearing dataclass -----------------------------


@dataclass
class PlainJournalBearing(Bearing):
    """Plain cylindrical journal bearing producing K, C from geometry.

    Geometry: bore diameter D = 2 R, axial length L, radial clearance c,
    lubricant viscosity mu. At each requested rpm we:

    1. Solve for the equilibrium eccentricity ratio under the static load
       (default = 1 N if not provided -- this scaling cancels when computing
       nondimensional groups but a positive value is required).
    2. Apply Ocvirk closed-form K, C for L/D < 0.3 (Ocvirk 1952's own
       range-of-validity claim; ADAPT-039).
    3. Apply Christopherson PSOR finite-bearing solve + perturbation for K, C
       for L/D >= 0.3.

    The eccentricity solve is by 1D bisection in eps on the load equation.

    Refuses |K| > 1e10 N/m (SPEC_SHEET §15).
    """

    diameter_m: float = 0.05
    length_m: float = 0.025
    clearance_m: float = 5e-5
    viscosity_pa_s: float = 0.01
    static_load_n: float = 100.0
    n_theta_grid: int = 60
    n_z_grid: int = 30
    psor_relaxation: float = 1.7
    # ADAPT-039: L/D below which Ocvirk closed-form applies. Was 0.5
    # (over-permissive, silently extrapolated into the 0.3 -- 0.5 band);
    # now 0.3, matching Ocvirk 1952's own range-of-validity claim.
    use_short_bearing_threshold: float = 0.3

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.diameter_m <= 0 or self.length_m <= 0 or self.clearance_m <= 0:
            msg = f"Journal bearing geometry must be positive; got D={self.diameter_m}, L={self.length_m}, c={self.clearance_m}"
            raise ValueError(msg)
        if self.viscosity_pa_s <= 0:
            msg = f"Lubricant viscosity must be positive; got {self.viscosity_pa_s}"
            raise ValueError(msg)

    @property
    def L_over_D(self) -> float:
        return self.length_m / self.diameter_m

    def equilibrium_eccentricity(self, omega_rad_s: float) -> float:
        """Solve for the eccentricity ratio at static equilibrium.

        Uses Ocvirk short-bearing load capacity to invert W = W(eps) for eps.
        For L/D > 0.5 this is a rough estimate; the Christopherson PSOR
        solver then accepts this as the perturbation operating point.
        """
        target_W = self.static_load_n
        R = self.diameter_m / 2.0

        # Bisection on the Ocvirk load curve
        def W_at(eps: float) -> float:
            W, _ = ocvirk_load_capacity(
                omega_rad_s,
                R,
                self.clearance_m,
                self.length_m,
                self.viscosity_pa_s,
                max(min(eps, 0.999), 1e-4),
            )
            return W

        lo, hi = 1e-3, 0.99
        # Bracket check
        if W_at(lo) > target_W:
            return lo
        if W_at(hi) < target_W:
            return hi
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if W_at(mid) > target_W:
                hi = mid
            else:
                lo = mid
        return 0.5 * (lo + hi)

    def coefficients_at_rpm(
        self,
        rpm: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        if rpm <= 0:
            # No film at zero speed -- return zero (caller may add penalty).
            return np.zeros((2, 2)), np.zeros((2, 2))
        omega = rpm * 2.0 * math.pi / 60.0
        R = self.diameter_m / 2.0
        eps = self.equilibrium_eccentricity(omega)

        if self.L_over_D <= self.use_short_bearing_threshold:
            # Use Ocvirk closed form
            K, C = ocvirk_stiffness_damping(
                omega,
                R,
                self.clearance_m,
                self.length_m,
                self.viscosity_pa_s,
                eps,
            )
        else:
            # Use Christopherson PSOR for the steady pressure, then perturb
            # the journal position in y and z (lab frame) to extract the
            # full Lund 1966 K matrix (Lund-style perturbation method).
            #
            # ADAPT-003: The earlier implementation perturbed only in the
            # eccentricity-frame radial direction, leaving K_yz and K_zz at
            # zero. A bearing with K_zz = 0 cannot support vertical load.
            # We now run a SECOND PSOR pass with a z-displacement
            # perturbation and a second pair for the C matrix in (y_dot,
            # z_dot) -- giving the full 2x2 K and C matrices.
            _, attitude_phi_0 = ocvirk_load_capacity(
                omega,
                R,
                self.clearance_m,
                self.length_m,
                self.viscosity_pa_s,
                eps,
            )
            # Equilibrium journal position in lab frame:
            # h(theta) = c (1 + eps cos(theta - phi)) places the minimum
            # film at theta = phi + pi, so the journal lies along
            # (-cos phi, -sin phi).
            y_j0 = -self.clearance_m * eps * math.cos(attitude_phi_0)
            z_j0 = -self.clearance_m * eps * math.sin(attitude_phi_0)

            def _psor_force_at(
                y_j: float, z_j: float
            ) -> Tuple[float, float, np.ndarray]:
                """Solve Reynolds at the given lab-frame journal position;
                return ``(F_y, F_z, p)`` (lab-frame fluid force on the
                journal + the pressure field)."""
                eps_new, phi_new = _journal_position_to_eps_phi(
                    y_j, z_j, self.clearance_m
                )
                eps_new = max(min(eps_new, 0.99), 1e-4)
                p_field, _, _ = christopherson_psor_solve(
                    omega_rad_s=omega,
                    radius_m=R,
                    clearance_m=self.clearance_m,
                    length_m=self.length_m,
                    viscosity_pa_s=self.viscosity_pa_s,
                    eccentricity_ratio=eps_new,
                    attitude_angle_rad=phi_new,
                    n_theta=self.n_theta_grid,
                    n_z=self.n_z_grid,
                    relaxation=self.psor_relaxation,
                )
                F_y_lab, F_z_lab = integrate_force_lab_frame(
                    p_field, R, self.length_m
                )
                return F_y_lab, F_z_lab, p_field

            # Equilibrium force (lab frame). For a static load this equals
            # minus the static load (held in equilibrium by the film).
            F_y0, F_z0, p = _psor_force_at(y_j0, z_j0)

            # Stiffness: K_ij = -dF_i/dq_j  (the restoring stiffness).
            #
            # In rotor-dynamics texts the bearing stiffness is defined so
            # that the FILM force on the journal is F_film = -K * dq, i.e.
            # the film opposes journal displacement. So K_ij = -dF_film_i/dq_j.
            delta = 0.01 * self.clearance_m  # small displacement perturbation
            F_y_py, F_z_py, _ = _psor_force_at(y_j0 + delta, z_j0)
            F_y_pz, F_z_pz, _ = _psor_force_at(y_j0, z_j0 + delta)
            K = np.array(
                [
                    [-(F_y_py - F_y0) / delta, -(F_y_pz - F_y0) / delta],
                    [-(F_z_py - F_y0) / delta, -(F_z_pz - F_z0) / delta],
                ]
            )
            # Fix the (1,0) entry above (typo trap: must use F_z0, not F_y0):
            K[1, 0] = -(F_z_py - F_z0) / delta

            # Damping: C_ij = -dF_i/d(qdot_j). Extracted via the
            # eccentricity-rate perturbation method (Lund & Thomsen 1978,
            # ADAPT-044 / W-15 / KG-RD-02).
            #
            # The Reynolds equation with a lateral journal velocity (vy, vz):
            #
            #   d/dx (h^3/(12 mu) dp/dx) + d/dz (h^3/(12 mu) dp/dz)
            #       = (U_p / 2) dh/dx + dh/dt
            #
            # with dh/dt = -vy cos(theta) - vz sin(theta).
            #
            # Two additional PSOR solves with small velocity perturbations
            # delta_v (one in y, one in z) give the full 2x2 C matrix via
            # central differencing of the integrated fluid forces.
            #
            # C_ij = -dF_i/d(qdot_j) at equilibrium.
            C = _psor_damping_tensor(
                omega_rad_s=omega,
                radius_m=R,
                clearance_m=self.clearance_m,
                length_m=self.length_m,
                viscosity_pa_s=self.viscosity_pa_s,
                eccentricity_ratio=eps,
                attitude_angle_rad=attitude_phi_0,
                F_y0=F_y0,
                F_z0=F_z0,
                n_theta=self.n_theta_grid,
                n_z=self.n_z_grid,
                relaxation=self.psor_relaxation,
            )

        # Refuse Kzz > 1e10 N/m (SPEC_SHEET §15)
        K_max = float(np.max(np.abs(K)))
        if K_max > 1.0e10:
            msg = (
                f"PlainJournalBearing {self.name} computed |K| = {K_max:.3e} N/m "
                f"which exceeds the v1 hard limit of 1e10 N/m (SPEC_SHEET §15). "
                f"Operating point: rpm={rpm}, eps={eps:.3f}."
            )
            raise ValueError(msg)
        return K, C
