"""Timoshenko beam-rotor finite-element assembly.

Per SPEC_SHEET §3.5 / §9. Each `RotorSection` from the `RotorShape`
mean-line handoff becomes one or more beam elements. Each node
carries 4 lateral DOFs: lateral translations ``y, z`` and bending rotations
``theta_y, theta_z``. DOF ordering at node ``i`` is::

    [y_i, theta_z_i, z_i, theta_y_i]

This pairs the bending plane (y, theta_z) on indices 0,1 and the bending
plane (z, theta_y) on indices 2,3. The gyroscopic coupling between the two
planes is the off-diagonal block.

The equation of motion is the API 684 §2.5 / Childs 1993 Ch. 3 form:

    M q_ddot + (C + Omega * G) q_dot + K q = F(t)

Element matrices follow the consistent-Timoshenko derivation of
Nelson & McVaugh 1976 (Euler-Bernoulli rotor element), extended to
Timoshenko by Nelson 1980. The closed forms used here are taken from
Friswell, Penny, Garvey & Lees 2010, Ch. 4, eqs. (4.55)-(4.61). The shear
coefficient kappa follows Cowper 1966.

Citations:
- Nelson, H. D. & McVaugh, J. M., 1976. The Dynamics of Rotor-Bearing
  Systems Using Finite Elements. ASME J. Eng. Industry 98(2): 593-600.
- Nelson, H. D., 1980. A Finite Rotating Shaft Element Using Timoshenko
  Beam Theory. ASME J. Mech. Design 102: 793-803.
- Friswell, M. I., Penny, J. E. T., Garvey, S. D., Lees, A. W., 2010.
  Dynamics of Rotating Machines. Cambridge University Press, Ch. 4.
- Genta, G., 1999. Dynamics of Rotating Systems. Springer, Ch. 4.
- Cowper, G. R., 1966. The Shear Coefficient in Timoshenko's Beam Theory.
  ASME J. Appl. Mech. 33: 335-340.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

import warnings

from cascade.materials import MaterialDB
from cascade.rotor.bearings import Bearing
from cascade.units import (
    LumpedDisk,
    Q,
    Quantity,
    RotorSection,
    RotorShape,
)

# --- Material defaults ------------------------------------------------------

# Default structural steel: AISI 4340. Used as fallback when a
# `RotorSection.material` string is unrecognised.
DEFAULT_E_PA: float = 2.0e11  # Young's modulus, AISI 4340 [Pa]
DEFAULT_NU: float = 0.29  # Poisson's ratio, AISI 4340 (registry value)
DEFAULT_RAYLEIGH_ALPHA: float = 0.0  # Mass-proportional damping
DEFAULT_RAYLEIGH_BETA: float = 0.0  # Stiffness-proportional damping

# Room-temperature reference used when a section has no temperature_K field.
_ROOM_TEMPERATURE_K: float = 293.0


def _material_properties(
    material_name: str, temperature_K: float = _ROOM_TEMPERATURE_K
) -> tuple[float, float]:
    """Look up (E_Pa, nu) for a material at the given temperature.

    Uses the :class:`~cascade.materials.MaterialDB` registry.  If the
    material name is unrecognised a :class:`RuntimeWarning` is emitted and
    AISI 4340 room-temperature values are returned (W-13: explicit failure
    preferred over silent wrong-material fallback).

    Parameters
    ----------
    material_name:
        Canonical material name or recognised alias (e.g. ``"STEEL_AISI4340"``
        resolves to ``"AISI 4340"`` via the ALIASES map).
    temperature_K:
        Query temperature in Kelvin. Defaults to 293 K (room temperature).

    Returns
    -------
    (E_Pa, nu) : tuple[float, float]
        Young's modulus in Pa and Poisson's ratio (dimensionless).
    """
    try:
        mat = MaterialDB.get(material_name)
        E_pa = mat.E(temperature_K)
        nu = mat.poisson
        return E_pa, nu
    except KeyError:
        warnings.warn(
            f"Material {material_name!r} is not in the Cascade materials "
            f"registry. Falling back to AISI 4340 room-temperature values "
            f"(E = {DEFAULT_E_PA:.3g} Pa, nu = {DEFAULT_NU}). "
            f"This is almost certainly wrong for a non-steel section. "
            f"Add the material to cascade.materials.database to fix this.",
            category=RuntimeWarning,
            stacklevel=4,
        )
        return DEFAULT_E_PA, DEFAULT_NU


def cowper_shear_coefficient(diameter_outer: float, diameter_inner: float, nu: float) -> float:
    """Cowper 1966 shear coefficient kappa for circular cross-section.

    Closed forms from Cowper, G. R. (1966), "The Shear Coefficient in
    Timoshenko's Beam Theory," ASME J. Appl. Mech. 33(2): 335-340,
    equation (37) (solid round) and equation (38) / Table 1 (hollow round).

    For a solid round rod (``D_inner = 0``)::

        kappa = 6 (1 + nu) / (7 + 6 nu)

    For a hollow round (``m = D_inner / D_outer``)::

        kappa = 6 (1 + nu) (1 + m^2)^2 /
                ( (7 + 6 nu) (1 + m^2)^2 + (20 + 12 nu) m^2 )

    The hollow formula reduces to the solid result at m=0 and to the
    thin-walled limit ``kappa = 2 (1 + nu) / (4 + 3 nu)`` at m -> 1.

    Reference: Cowper 1966, eqs. (37) and (38) / Table 1. For ``nu = 0.3``
    and solid section, ``kappa = 6 * 1.3 / (7 + 6 * 0.3) = 0.886``.

    .. note::

        Pre-ADAPT-004 versions of this function substituted the
        ``6(1+nu)^2 / (7 + 12 nu + 4 nu^2)`` form (which is *not* the
        Cowper solid-round coefficient -- it appears in some texts as a
        circular-tube approximation but is not what Cowper 1966 §3
        derives for the solid section). At ``nu = 0.3`` that form returns
        ``0.925`` instead of the correct ``0.886``, which propagates as a
        4 % under-estimate of the bending stiffness for stubby rotor
        segments.

    >>> abs(cowper_shear_coefficient(0.05, 0.0, 0.3) - 0.886) < 0.001
    True
    >>> # Thin-walled limit: m -> 1 gives the tube coefficient
    >>> abs(cowper_shear_coefficient(0.05, 0.04999, 0.3) - 2 * 1.3 / 4.9) < 0.001
    True
    >>> # nu = 0: solid round gives 6/7
    >>> abs(cowper_shear_coefficient(0.05, 0.0, 0.0) - 6/7) < 1e-9
    True
    """
    if not math.isfinite(nu):
        msg = f"Poisson ratio nu must be finite; got {nu}"
        raise ValueError(msg)
    if nu < -1.0 or nu >= 0.5:
        # Physically nu in (-1, 0.5); we keep a slightly tighter check
        # to catch obvious user errors but allow nu = 0 (cork).
        msg = f"Poisson ratio nu must be in (-1, 0.5); got {nu}"
        raise ValueError(msg)
    if diameter_outer <= 0:
        # Default to solid coefficient when geometry is degenerate.
        return 6.0 * (1.0 + nu) / (7.0 + 6.0 * nu)
    ratio = diameter_inner / diameter_outer if diameter_outer > 0 else 0.0
    if ratio <= 1e-9:
        # Solid round (Cowper 1966 eq. 37)
        return 6.0 * (1.0 + nu) / (7.0 + 6.0 * nu)
    if ratio >= 1.0 - 1e-9:
        # Thin-walled tube limit
        return 2.0 * (1.0 + nu) / (4.0 + 3.0 * nu)
    # Hollow round, full Cowper 1966 formula (eq. 38 / Table 1).
    m = ratio
    m2 = m * m
    one_plus_m2 = 1.0 + m2
    numerator = 6.0 * (1.0 + nu) * one_plus_m2 * one_plus_m2
    denominator = (7.0 + 6.0 * nu) * one_plus_m2 * one_plus_m2 + (
        20.0 + 12.0 * nu
    ) * m2
    return float(numerator / denominator)


# --- Element matrices -------------------------------------------------------


def timoshenko_element_matrices(
    L: float,
    rho: float,
    E: float,
    G_s: float,
    A: float,
    I_d: float,
    I_p: float,
    kappa: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Consistent Timoshenko rotor beam-element matrices (8x8 each).

    Parameters
    ----------
    L : float
        Element length [m].
    rho : float
        Density [kg/m^3].
    E : float
        Young's modulus [Pa].
    G_s : float
        Shear modulus [Pa] = E / (2 (1 + nu)).
    A : float
        Cross-section area [m^2].
    I_d : float
        Diametrical second moment of area [m^4].
    I_p : float
        Polar second moment of area [m^4] (for a circular section,
        I_p = 2 I_d).
    kappa : float
        Cowper shear coefficient [-].

    Returns
    -------
    (M_e, K_e, G_e) : tuple of (8, 8) numpy arrays.
        Element mass, stiffness, gyroscopic matrices in the 8-DOF ordering
        [y1, theta_z1, z1, theta_y1, y2, theta_z2, z2, theta_y2].

    Reference: Friswell et al. 2010 §4.4 (eqs. 4.55-4.61); the symbolic
    closed-form for the Timoshenko rotor element including bending,
    shear, rotary inertia, gyroscopic coupling. We code the y-plane (y, theta_z)
    and z-plane (z, theta_y) blocks explicitly. Phi = 12 E I_d / (kappa A G L^2)
    is the shear parameter.
    """
    if L <= 0 or A <= 0 or I_d <= 0:
        msg = f"Element parameters must be positive; got L={L} A={A} I_d={I_d}"
        raise ValueError(msg)

    Phi = 12.0 * E * I_d / (kappa * A * G_s * L * L)

    # --- Stiffness in one bending plane (4x4) (y, theta_z) -----------------
    # Standard Timoshenko stiffness matrix per Friswell et al. eq. (4.61),
    # Nelson 1980, and ANSYS Theory Reference §14.16.
    k_factor = E * I_d / (L**3 * (1.0 + Phi))
    K_plane_y = k_factor * np.array(
        [
            [12.0, 6 * L, -12.0, 6 * L],
            [6 * L, (4 + Phi) * L**2, -6 * L, (2 - Phi) * L**2],
            [-12.0, -6 * L, 12.0, -6 * L],
            [6 * L, (2 - Phi) * L**2, -6 * L, (4 + Phi) * L**2],
        ]
    )
    # The z-plane stiffness has the same magnitudes but the sign on the
    # rotation-rotation couplings flips because theta_y produces a positive
    # bending moment when z is positive (right-hand rule). The classical
    # Nelson 1980 form uses:
    K_plane_z = k_factor * np.array(
        [
            [12.0, -6 * L, -12.0, -6 * L],
            [-6 * L, (4 + Phi) * L**2, 6 * L, (2 - Phi) * L**2],
            [-12.0, 6 * L, 12.0, 6 * L],
            [-6 * L, (2 - Phi) * L**2, 6 * L, (4 + Phi) * L**2],
        ]
    )

    # --- Mass: translational + rotary contributions ------------------------
    # Friswell et al. eq. (4.58)-(4.59). Translational and rotary parts each
    # have separate scaling by rho*A*L and rho*I_d/L respectively.
    Phi2 = Phi * Phi
    denom_T = 420.0 * (1.0 + Phi) ** 2
    # Translational coefficients (consistent mass) -- y-plane
    M_T_y_factor = rho * A * L / denom_T
    M_T_y = M_T_y_factor * np.array(
        [
            [
                156 + 294 * Phi + 140 * Phi2,
                (22 + 38.5 * Phi + 17.5 * Phi2) * L,
                54 + 126 * Phi + 70 * Phi2,
                -(13 + 31.5 * Phi + 17.5 * Phi2) * L,
            ],
            [
                (22 + 38.5 * Phi + 17.5 * Phi2) * L,
                (4 + 7 * Phi + 3.5 * Phi2) * L**2,
                (13 + 31.5 * Phi + 17.5 * Phi2) * L,
                -(3 + 7 * Phi + 3.5 * Phi2) * L**2,
            ],
            [
                54 + 126 * Phi + 70 * Phi2,
                (13 + 31.5 * Phi + 17.5 * Phi2) * L,
                156 + 294 * Phi + 140 * Phi2,
                -(22 + 38.5 * Phi + 17.5 * Phi2) * L,
            ],
            [
                -(13 + 31.5 * Phi + 17.5 * Phi2) * L,
                -(3 + 7 * Phi + 3.5 * Phi2) * L**2,
                -(22 + 38.5 * Phi + 17.5 * Phi2) * L,
                (4 + 7 * Phi + 3.5 * Phi2) * L**2,
            ],
        ]
    )
    # The z-plane translational mass is identical in shape (the off-diagonal
    # sign pattern differs but the bilinear form is the same; for a balanced
    # rotor the translational mass has the same y-plane / z-plane block).
    M_T_z_factor = rho * A * L / denom_T
    M_T_z = M_T_z_factor * np.array(
        [
            [
                156 + 294 * Phi + 140 * Phi2,
                -(22 + 38.5 * Phi + 17.5 * Phi2) * L,
                54 + 126 * Phi + 70 * Phi2,
                (13 + 31.5 * Phi + 17.5 * Phi2) * L,
            ],
            [
                -(22 + 38.5 * Phi + 17.5 * Phi2) * L,
                (4 + 7 * Phi + 3.5 * Phi2) * L**2,
                -(13 + 31.5 * Phi + 17.5 * Phi2) * L,
                -(3 + 7 * Phi + 3.5 * Phi2) * L**2,
            ],
            [
                54 + 126 * Phi + 70 * Phi2,
                -(13 + 31.5 * Phi + 17.5 * Phi2) * L,
                156 + 294 * Phi + 140 * Phi2,
                (22 + 38.5 * Phi + 17.5 * Phi2) * L,
            ],
            [
                (13 + 31.5 * Phi + 17.5 * Phi2) * L,
                -(3 + 7 * Phi + 3.5 * Phi2) * L**2,
                (22 + 38.5 * Phi + 17.5 * Phi2) * L,
                (4 + 7 * Phi + 3.5 * Phi2) * L**2,
            ],
        ]
    )
    # Rotary contribution (small but matters for slender rotors)
    denom_R = 30.0 * L * (1.0 + Phi) ** 2
    M_R_y_factor = rho * I_d / denom_R
    M_R_y = M_R_y_factor * np.array(
        [
            [36.0, (3 - 15 * Phi) * L, -36.0, (3 - 15 * Phi) * L],
            [
                (3 - 15 * Phi) * L,
                (4 + 5 * Phi + 10 * Phi2) * L**2,
                -(3 - 15 * Phi) * L,
                -(1 + 5 * Phi - 5 * Phi2) * L**2,
            ],
            [-36.0, -(3 - 15 * Phi) * L, 36.0, -(3 - 15 * Phi) * L],
            [
                (3 - 15 * Phi) * L,
                -(1 + 5 * Phi - 5 * Phi2) * L**2,
                -(3 - 15 * Phi) * L,
                (4 + 5 * Phi + 10 * Phi2) * L**2,
            ],
        ]
    )
    M_R_z = M_R_y_factor * np.array(
        [
            [36.0, -(3 - 15 * Phi) * L, -36.0, -(3 - 15 * Phi) * L],
            [
                -(3 - 15 * Phi) * L,
                (4 + 5 * Phi + 10 * Phi2) * L**2,
                (3 - 15 * Phi) * L,
                -(1 + 5 * Phi - 5 * Phi2) * L**2,
            ],
            [-36.0, (3 - 15 * Phi) * L, 36.0, (3 - 15 * Phi) * L],
            [
                -(3 - 15 * Phi) * L,
                -(1 + 5 * Phi - 5 * Phi2) * L**2,
                (3 - 15 * Phi) * L,
                (4 + 5 * Phi + 10 * Phi2) * L**2,
            ],
        ]
    )
    M_y = M_T_y + M_R_y
    M_z = M_T_z + M_R_z

    # --- Gyroscopic matrix -------------------------------------------------
    # G is skew-symmetric, coupling y-plane to z-plane. From the rotary
    # inertia coupling; the polar inertia (I_p = 2 I_d for circular section)
    # is the natural coefficient (Genta 1999 eq. 4.114). Reduces to the
    # Nelson 1976 form in Euler-Bernoulli limit (Phi=0).
    G_factor = rho * I_p / (15.0 * L * (1.0 + Phi) ** 2)
    # Use the standard form. G has the (y -> z) coupling = -(z -> y) coupling.
    # The 4x4 block (in y-plane DOFs paired with z-plane DOFs):
    G_block = G_factor * np.array(
        [
            [36.0, (3 - 15 * Phi) * L, -36.0, (3 - 15 * Phi) * L],
            [
                (3 - 15 * Phi) * L,
                (4 + 5 * Phi + 10 * Phi2) * L**2,
                -(3 - 15 * Phi) * L,
                -(1 + 5 * Phi - 5 * Phi2) * L**2,
            ],
            [-36.0, -(3 - 15 * Phi) * L, 36.0, -(3 - 15 * Phi) * L],
            [
                (3 - 15 * Phi) * L,
                -(1 + 5 * Phi - 5 * Phi2) * L**2,
                -(3 - 15 * Phi) * L,
                (4 + 5 * Phi + 10 * Phi2) * L**2,
            ],
        ]
    )

    # --- Assemble into 8x8 (full element with both planes interleaved) ----
    # DOF ordering at each node: [y, theta_z, z, theta_y]. The element has
    # two nodes, so DOFs are
    #   [y1, theta_z1, z1, theta_y1, y2, theta_z2, z2, theta_y2].
    # K and M are block-diagonal in the planes (no plane coupling for
    # symmetric isotropic shaft). G is skew-symmetric off-diagonal block.
    M_e = np.zeros((8, 8))
    K_e = np.zeros((8, 8))
    G_e = np.zeros((8, 8))

    # Plane-y DOF indices (y1, theta_z1, y2, theta_z2) in the 8-DOF vector:
    iy = [0, 1, 4, 5]
    # Plane-z DOF indices (z1, theta_y1, z2, theta_y2):
    iz = [2, 3, 6, 7]
    for a in range(4):
        for b in range(4):
            M_e[iy[a], iy[b]] += M_y[a, b]
            M_e[iz[a], iz[b]] += M_z[a, b]
            K_e[iy[a], iy[b]] += K_plane_y[a, b]
            K_e[iz[a], iz[b]] += K_plane_z[a, b]
            # G couples z-plane DOFs into y-plane equations and vice-versa.
            # G is skew: G[y, z] = G_block[a, b]; G[z, y] = -G_block.T[a, b]
            G_e[iy[a], iz[b]] += G_block[a, b]
            G_e[iz[a], iy[b]] += -G_block[b, a]

    return M_e, K_e, G_e


# --- Rotor model assembly ---------------------------------------------------


@dataclass
class RotorModel:
    """Assembled rotor finite-element model.

    Stores the global mass M, stiffness K_struct, gyroscopic G (per Omega),
    and bearing K_b(Omega), C_b(Omega) coefficients. The total dynamic
    matrices at a given speed are::

        K_total(Omega) = K_struct + K_bearings(Omega)
        C_total(Omega) = C_rayleigh + C_bearings(Omega)
        M is speed-independent

    Attributes:
        n_nodes: number of nodes in the mesh.
        n_dof: 4 * n_nodes (lateral DOF count).
        nodal_positions: axial coordinate of each node [m].
        M, K_struct: global mass and structural stiffness, dense (n_dof, n_dof).
        G_unit: gyroscopic matrix at unit Omega (full matrix = Omega * G_unit).
        bearings: list of `Bearing` objects, each at a specific axial position.
        bearing_nodes: list[int], the node index for each bearing.
        rayleigh_alpha, rayleigh_beta: structural damping coefficients.
        disks: list of `LumpedDisk` objects in canonical SI.
        disk_nodes: list[int], the node index for each disk.
    """

    n_nodes: int
    n_dof: int
    nodal_positions: np.ndarray
    M: np.ndarray
    K_struct: np.ndarray
    G_unit: np.ndarray
    bearings: List[Bearing] = field(default_factory=list)
    bearing_nodes: List[int] = field(default_factory=list)
    rayleigh_alpha: float = DEFAULT_RAYLEIGH_ALPHA
    rayleigh_beta: float = DEFAULT_RAYLEIGH_BETA
    disks: List[LumpedDisk] = field(default_factory=list)
    disk_nodes: List[int] = field(default_factory=list)

    def node_dofs(self, node: int) -> List[int]:
        """DOF indices for node `node` in the global vector.

        Returns [y, theta_z, z, theta_y] global DOF indices.
        """
        base = 4 * node
        return [base, base + 1, base + 2, base + 3]

    def K_at(self, rpm: float) -> np.ndarray:
        """Total stiffness K_struct + K_bearings at the given rpm."""
        K = self.K_struct.copy()
        for brg, node in zip(self.bearings, self.bearing_nodes):
            K_b, _ = brg.coefficients_at_rpm(rpm)
            dofs = self.node_dofs(node)
            # Map (y, z) bearing block into the (y, z) global DOFs (skipping
            # the rotation DOFs).
            translation_dofs = [dofs[0], dofs[2]]
            for a in range(2):
                for b in range(2):
                    K[translation_dofs[a], translation_dofs[b]] += K_b[a, b]
        return K

    def C_at(self, rpm: float) -> np.ndarray:
        """Total damping = Rayleigh C_R + Bearing C at the given rpm."""
        omega = rpm * 2 * math.pi / 60.0
        C = self.rayleigh_alpha * self.M + self.rayleigh_beta * self.K_struct
        for brg, node in zip(self.bearings, self.bearing_nodes):
            _, C_b = brg.coefficients_at_rpm(rpm)
            dofs = self.node_dofs(node)
            translation_dofs = [dofs[0], dofs[2]]
            for a in range(2):
                for b in range(2):
                    C[translation_dofs[a], translation_dofs[b]] += C_b[a, b]
        return C

    def G_at_omega(self, omega: float) -> np.ndarray:
        """Gyroscopic operator at angular speed omega [rad/s]."""
        return omega * self.G_unit


def _add_lumped_disk(
    M: np.ndarray, G_unit: np.ndarray, disk: LumpedDisk, node: int
) -> None:
    """Add a lumped disk's mass and gyroscopic contribution to the global M, G.

    The disk contributes::

        M_disk[y, y] = m, M_disk[z, z] = m
        M_disk[theta_z, theta_z] = I_d, M_disk[theta_y, theta_y] = I_d
        G_disk[theta_z, theta_y] = -I_p, G_disk[theta_y, theta_z] = +I_p
        (skew gyroscopic on the rotation DOFs)

    Per Friswell et al. 2010 §4.5 (lumped disk on a rotating shaft).
    """
    m = disk.mass.to("kg").magnitude
    Id = disk.inertia_diametrical.to("kg*m^2").magnitude
    Ip = disk.inertia_polar.to("kg*m^2").magnitude
    base = 4 * node
    y_i = base
    tz_i = base + 1
    z_i = base + 2
    ty_i = base + 3
    M[y_i, y_i] += m
    M[z_i, z_i] += m
    M[tz_i, tz_i] += Id
    M[ty_i, ty_i] += Id
    # Gyroscopic skew block on the rotation DOFs (per Omega)
    G_unit[tz_i, ty_i] += -Ip
    G_unit[ty_i, tz_i] += +Ip


def build_rotor_model(
    rotor_shape: RotorShape,
    bearings: Optional[List[Bearing]] = None,
    *,
    elements_per_section: int = 1,
    youngs_modulus: Optional[Quantity] = None,
    poissons_ratio: Optional[float] = None,
    rayleigh_alpha: float = DEFAULT_RAYLEIGH_ALPHA,
    rayleigh_beta: float = DEFAULT_RAYLEIGH_BETA,
) -> RotorModel:
    """Assemble a `RotorModel` from a `RotorShape` and a bearing list.

    Each section in `rotor_shape.sections` becomes `elements_per_section`
    Timoshenko elements (default 1). Lumped disks attach to the nearest
    existing node by axial position; the same applies to bearings.

    **Material properties** are resolved per-section from the
    :class:`~cascade.materials.MaterialDB` registry using the
    ``RotorSection.material`` string.  Temperature-dependent E is evaluated
    at ``RotorSection.temperature_K`` when that attribute exists, otherwise at
    room temperature (293 K). The optional ``youngs_modulus`` and
    ``poissons_ratio`` keyword arguments override the per-section registry
    lookup and apply a *uniform* value across all elements — useful for
    analytical benchmarks where you want to freeze E and nu.

    >>> # Smoke construction with a single uniform section + a single disk
    >>> from cascade.units import RotorSection, LumpedDisk, RotorShape, Q
    >>> sec = RotorSection(
    ...     diameter_outer=Q(0.05, "m"), diameter_inner=Q(0.0, "m"),
    ...     length=Q(1.0, "m"), density=Q(7850.0, "kg/m^3"),
    ...     axial_position=Q(0.0, "m"), material="AISI4340",
    ... )
    >>> disk = LumpedDisk(
    ...     mass=Q(10.0, "kg"), inertia_polar=Q(0.05, "kg*m^2"),
    ...     inertia_diametrical=Q(0.025, "kg*m^2"), axial_position=Q(0.5, "m"),
    ... )
    >>> shape = RotorShape(sections=[sec], disks=[disk])
    >>> model = build_rotor_model(shape, [])
    >>> model.n_nodes
    2
    """
    if not rotor_shape.sections:
        msg = "RotorShape must have at least one section to build a rotor model"
        raise ValueError(msg)
    bearings = bearings or []

    # Global override kept for backward-compat with tests that pass explicit E.
    _global_E: Optional[float] = (
        youngs_modulus.to("Pa").magnitude if youngs_modulus is not None else None
    )
    _global_nu: Optional[float] = poissons_ratio

    # Build node list. Each section spans [axial_start, axial_start + length];
    # internal sub-elements split that span uniformly.
    node_positions: List[float] = []
    # First node: the start of the first section
    sorted_sections = sorted(
        rotor_shape.sections, key=lambda s: s.axial_position.to("m").magnitude
    )
    first_start = sorted_sections[0].axial_position.to("m").magnitude
    node_positions.append(first_start)

    # Walk sections; for each, add `elements_per_section` interior nodes.
    section_elements: List[Tuple[int, int, RotorSection]] = []  # (n1, n2, section)
    cursor_x = first_start
    for sec in sorted_sections:
        sec_start = sec.axial_position.to("m").magnitude
        sec_length = sec.length.to("m").magnitude
        if abs(sec_start - cursor_x) > 1e-9:
            # Gap between sections; in v1 we don't bridge gaps -- enforce
            # contiguous mean-line geometry.
            msg = (
                f"RotorShape sections must be contiguous; gap of "
                f"{sec_start - cursor_x:.4g} m between sections"
            )
            raise ValueError(msg)
        for k in range(elements_per_section):
            x_end = sec_start + sec_length * (k + 1) / elements_per_section
            node_positions.append(x_end)
            n1 = len(node_positions) - 2
            n2 = len(node_positions) - 1
            section_elements.append((n1, n2, sec))
        cursor_x = sec_start + sec_length

    n_nodes = len(node_positions)
    n_dof = 4 * n_nodes
    M = np.zeros((n_dof, n_dof))
    K = np.zeros((n_dof, n_dof))
    G_unit = np.zeros((n_dof, n_dof))

    # Assemble elements
    for n1, n2, sec in section_elements:
        L_e = node_positions[n2] - node_positions[n1]
        D_o = sec.diameter_outer.to("m").magnitude
        D_i = sec.diameter_inner.to("m").magnitude
        rho = sec.density.to("kg/m^3").magnitude
        A = math.pi / 4.0 * (D_o**2 - D_i**2)
        I_d = math.pi / 64.0 * (D_o**4 - D_i**4)
        I_p = 2 * I_d  # solid / hollow circular

        # Resolve material properties: global override > registry > warning+fallback
        if _global_E is not None and _global_nu is not None:
            E = _global_E
            nu = _global_nu
        else:
            T_K = getattr(sec, "temperature_K", _ROOM_TEMPERATURE_K) or _ROOM_TEMPERATURE_K
            E_reg, nu_reg = _material_properties(sec.material, temperature_K=T_K)
            E = _global_E if _global_E is not None else E_reg
            nu = _global_nu if _global_nu is not None else nu_reg

        G_s = E / (2.0 * (1.0 + nu))
        kappa = cowper_shear_coefficient(D_o, D_i, nu)
        M_e, K_e, G_e = timoshenko_element_matrices(
            L=L_e, rho=rho, E=E, G_s=G_s, A=A, I_d=I_d, I_p=I_p, kappa=kappa
        )
        # Map element DOFs into global DOFs
        dofs = []
        for n in (n1, n2):
            dofs.extend([4 * n, 4 * n + 1, 4 * n + 2, 4 * n + 3])
        for a in range(8):
            for b in range(8):
                M[dofs[a], dofs[b]] += M_e[a, b]
                K[dofs[a], dofs[b]] += K_e[a, b]
                G_unit[dofs[a], dofs[b]] += G_e[a, b]

    # Attach lumped disks at nearest nodes
    disk_nodes: List[int] = []
    for disk in rotor_shape.disks:
        x_d = disk.axial_position.to("m").magnitude
        node_idx = int(
            np.argmin(np.abs(np.array(node_positions) - x_d))
        )
        _add_lumped_disk(M, G_unit, disk, node_idx)
        disk_nodes.append(node_idx)

    # Attach bearings
    bearing_nodes: List[int] = []
    for brg in bearings:
        x_b = brg.axial_position.to("m").magnitude
        node_idx = int(np.argmin(np.abs(np.array(node_positions) - x_b)))
        bearing_nodes.append(node_idx)

    return RotorModel(
        n_nodes=n_nodes,
        n_dof=n_dof,
        nodal_positions=np.array(node_positions),
        M=M,
        K_struct=K,
        G_unit=G_unit,
        bearings=list(bearings),
        bearing_nodes=bearing_nodes,
        rayleigh_alpha=rayleigh_alpha,
        rayleigh_beta=rayleigh_beta,
        disks=list(rotor_shape.disks),
        disk_nodes=disk_nodes,
    )
