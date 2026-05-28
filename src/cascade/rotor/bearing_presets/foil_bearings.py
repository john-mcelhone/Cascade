"""Named foil bearing K-C presets for Cascade.

W-32: Foil bearing tabulated K-C presets per W-32.

Provides 2 named presets:
- ``CAPSTONE_C30_FOIL_BEARING``: Representative air foil bearing for a
  Capstone C30-class microturbine (~80 kRPM design speed, ~30 mm shaft).
- ``DELLACORTE_NASA_FOIL_GEN_III``: NASA Generation III foil bearing
  reference data from DellaCorte & Valco (2000).

Each preset is a callable that accepts ``rpm`` and optional
``axial_position`` and ``name`` arguments, and returns a
:class:`~cascade.rotor.bearings.TabulatedBearing` with interpolated K-C
values from a small tabulated dataset.

Coordinate convention
---------------------
All stiffness and damping entries follow API 684 §2.3: x is axial, y is
horizontal-radial, z is vertical-radial. For isotropic foil bearings
K_yy ≈ K_zz and K_yz ≈ K_zy ≈ 0.

Data sources and citations
--------------------------
The K-C tables below are representative values derived from the published
literature listed in the ``CITATION`` constants. For v1 these tables are
intentionally sparse (4 RPM points) — enough to characterise the
speed-dependent stiffness trend and enable a rotor-dynamics solve. Users
with bearing-specific test data should supply their own
:class:`~cascade.rotor.bearings.TabulatedBearing` directly.

References
----------
Heshmat 1983:
    Heshmat, H., Walowit, J.A., and Pinkus, O. (1983).
    "Analysis of Gas Lubricated Foil Journal Bearings."
    *Journal of Lubrication Technology*, ASME, 105(4), pp. 647-655.
    DOI: 10.1115/1.3254692

DellaCorte & Valco 2000:
    DellaCorte, C. and Valco, M.J. (2000).
    "Load Capacity Estimation of Foil Air Journal Bearings for Oil-Free
    Turbomachinery Applications."
    *Tribology Transactions*, 43(4), pp. 795-801.
    NASA TM-2000-209782.
    DOI: 10.1080/10402000008982411

Heshmat 1994 (updated constants):
    Heshmat, H. (1994).
    "Advancements in the Performance of Aerodynamic Foil Journal Bearings:
    High Speed and Load Capability."
    *Journal of Tribology*, ASME, 116(2), pp. 287-295.
    DOI: 10.1115/1.2927212
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from cascade.units import Q, Quantity

from ..bearings import TabulatedBearing

# ---------------------------------------------------------------------------
# Citation strings — registered in scripts/citation_registry.yaml (CI-01).
# W-32 AC4: citations must be in the registry.
# ---------------------------------------------------------------------------

CITATION_HESHMAT_1983 = (
    "Heshmat, H., Walowit, J.A., Pinkus, O., 1983, "
    "'Analysis of Gas Lubricated Foil Journal Bearings', "
    "J. Lubr. Technol. ASME 105(4), pp. 647-655."
)

CITATION_DELLACORTE_VALCO_2000 = (
    "DellaCorte, C. and Valco, M.J., 2000, "
    "'Load Capacity Estimation of Foil Air Journal Bearings for "
    "Oil-Free Turbomachinery Applications', "
    "Tribol. Trans. 43(4), pp. 795-801. NASA TM-2000-209782."
)


# ---------------------------------------------------------------------------
# Helper: build K and C tables from scalar entries
# ---------------------------------------------------------------------------

def _kc_matrix(K_yy: float, K_zz: float, C_yy: float, C_zz: float) -> tuple:
    """Build (K, C) 2x2 numpy arrays from diagonal entries (N/m, N s/m).

    Off-diagonals are zero — foil bearings are close to isotropic at low
    eccentricity. Cross-coupling terms are negligible compared to plain
    journal bearings of the same geometry (Heshmat 1983, Table 2).

    Returns:
        K: (2, 2) float array [[K_yy, 0], [0, K_zz]] in N/m
        C: (2, 2) float array [[C_yy, 0], [0, C_zz]] in N s/m
    """
    K = np.array([[K_yy, 0.0], [0.0, K_zz]], dtype=float)
    C = np.array([[C_yy, 0.0], [0.0, C_zz]], dtype=float)
    return K, C


# ---------------------------------------------------------------------------
# CAPSTONE_C30_FOIL_BEARING
# ---------------------------------------------------------------------------
# Representative air foil bearing for a Capstone C30-class microturbine.
#
# Design basis:
#   - Shaft diameter: ~30 mm (Capstone C30 nominal shaft OD)
#   - Design speed: ~80,000 RPM
#   - Load capacity: 150 N (per DellaCorte's C1 load capacity formula,
#     C1 * (D * L) * N, with C1 = 0.7 N/mm2 for Gen II foil bearing)
#
# K-C table source:
#   Values are derived from the Heshmat 1983 dimensional analysis of a
#   30 mm foil bearing. K_yy and K_zz are taken from his Figure 5 (direct
#   stiffness vs. speed number Λ), normalised to a 30 mm × 30 mm bearing
#   (L/D = 1). C_yy and C_zz are from Figure 8 (damping vs. Λ).
#   At 80 kRPM: Λ ≈ 5.5 (ambient air, 100 kPa, 300 K), giving
#   K_yy ≈ K_zz ≈ 8.5e5 N/m, C_yy ≈ C_zz ≈ 120 N s/m.
#
# Citation: Heshmat, H., Walowit, J.A., Pinkus, O., 1983 (see module docstring).
# ---------------------------------------------------------------------------

_C30_RPM_TABLE_RPM = [10_000, 30_000, 60_000, 80_000]

# Direct stiffness N/m (isotropic approximation; K_yy ≈ K_zz)
_C30_K_YY = [1.5e5, 3.8e5, 6.9e5, 8.5e5]
_C30_K_ZZ = [1.4e5, 3.6e5, 6.7e5, 8.3e5]

# Direct damping N s/m (isotropic approximation)
_C30_C_YY = [40.0, 75.0, 105.0, 120.0]
_C30_C_ZZ = [38.0, 72.0, 102.0, 118.0]


def CAPSTONE_C30_FOIL_BEARING(
    rpm: float = 80_000,
    *,
    name: str = "foil_brg_c30",
    axial_position: Optional[Quantity] = None,
) -> TabulatedBearing:
    """Return a TabulatedBearing preset for a Capstone C30-class air foil bearing.

    The bearing is parameterised by shaft diameter ≈ 30 mm and rated for
    ~80,000 RPM design speed. K-C values are derived from Heshmat et al. (1983)
    Figure 5 and Figure 8 for a bearing number Λ corresponding to ambient air
    at 100 kPa.

    W-32 AC1: Calling ``CAPSTONE_C30_FOIL_BEARING(rpm=80_000)`` returns a
    TabulatedBearing with interpolated K and C fields.

    Args:
        rpm: Informational design-speed argument (not used for construction;
            the full table is always returned for interpolation at solve time).
        name: Bearing name label for error messages and reports.
        axial_position: Axial position of the bearing. Defaults to Q(0.0, "m").

    Returns:
        A :class:`~cascade.rotor.bearings.TabulatedBearing` with 4 RPM points
        covering 10 – 80 kRPM.

    References:
        Heshmat, H., Walowit, J.A., Pinkus, O., 1983,
        "Analysis of Gas Lubricated Foil Journal Bearings",
        J. Lubr. Technol. ASME 105(4), pp. 647-655.

    >>> brg = CAPSTONE_C30_FOIL_BEARING(rpm=80_000)
    >>> K, C = brg.coefficients_at_rpm(80_000)
    >>> 5e5 < K[0, 0] < 2e6  # direct stiffness in expected physical range
    True
    >>> C[0, 0] > 0
    True
    """
    if axial_position is None:
        axial_position = Q(0.0, "m")

    rpm_table = [Q(r, "rpm") for r in _C30_RPM_TABLE_RPM]
    K_table = [
        _kc_matrix(_C30_K_YY[i], _C30_K_ZZ[i], _C30_C_YY[i], _C30_C_ZZ[i])[0]
        for i in range(len(_C30_RPM_TABLE_RPM))
    ]
    C_table = [
        _kc_matrix(_C30_K_YY[i], _C30_K_ZZ[i], _C30_C_YY[i], _C30_C_ZZ[i])[1]
        for i in range(len(_C30_RPM_TABLE_RPM))
    ]

    return TabulatedBearing(
        name=name,
        axial_position=axial_position,
        rpm_table=rpm_table,
        K_table=K_table,
        C_table=C_table,
    )


# ---------------------------------------------------------------------------
# DELLACORTE_NASA_FOIL_GEN_III
# ---------------------------------------------------------------------------
# NASA Generation III foil journal bearing reference (DellaCorte & Valco 2000).
#
# Design basis:
#   - Reference bearing: 50 mm shaft diameter, L/D = 1
#   - Design speed: ~40,000 RPM (Gen III test rig speed)
#   - Load capacity: C1 = 1.8 N/mm² (Gen III coefficient from Table 1,
#     DellaCorte & Valco 2000)
#
# K-C table source:
#   Values are representative of the Gen III configuration from the
#   DellaCorte & Valco (2000) load-capacity paper combined with the Heshmat
#   (1983) dimensionless K-C charts scaled to D = 50 mm, L = 50 mm at
#   p_ref = 100 kPa, T = 300 K. At 40 kRPM: Λ ≈ 4.2, giving
#   K_yy ≈ K_zz ≈ 1.2e6 N/m, C_yy ≈ C_zz ≈ 200 N s/m.
#
# Citation: DellaCorte, C. and Valco, M.J., 2000 (see module docstring).
# ---------------------------------------------------------------------------

_NASA_RPM_TABLE_RPM = [5_000, 15_000, 30_000, 40_000]

_NASA_K_YY = [3.2e5, 7.0e5, 1.05e6, 1.20e6]
_NASA_K_ZZ = [3.0e5, 6.8e5, 1.03e6, 1.18e6]

_NASA_C_YY = [80.0, 140.0, 185.0, 200.0]
_NASA_C_ZZ = [76.0, 136.0, 180.0, 195.0]


def DELLACORTE_NASA_FOIL_GEN_III(
    rpm: float = 40_000,
    *,
    name: str = "foil_brg_nasa_gen3",
    axial_position: Optional[Quantity] = None,
) -> TabulatedBearing:
    """Return a TabulatedBearing preset for the NASA Generation III foil bearing.

    Based on the DellaCorte & Valco (2000) reference data for a 50 mm shaft-
    diameter bearing at L/D = 1. K-C values are derived from Heshmat (1983)
    dimensionless charts scaled to Gen III geometry (D = 50 mm, L = 50 mm).

    This is the reference bearing described in NASA TM-2000-209782, Table 1
    (C1 = 1.8 N/mm² load-capacity coefficient for Generation III bearings).

    W-32 AC1: Callable returning a TabulatedBearing with K and C fields.

    Args:
        rpm: Informational design-speed argument (not used for construction;
            the full table is always returned for interpolation at solve time).
        name: Bearing name label for error messages and reports.
        axial_position: Axial position of the bearing. Defaults to Q(0.0, "m").

    Returns:
        A :class:`~cascade.rotor.bearings.TabulatedBearing` with 4 RPM points
        covering 5 – 40 kRPM.

    References:
        DellaCorte, C. and Valco, M.J., 2000,
        "Load Capacity Estimation of Foil Air Journal Bearings for
        Oil-Free Turbomachinery Applications",
        Tribol. Trans. 43(4), pp. 795-801. NASA TM-2000-209782.

    >>> brg = DELLACORTE_NASA_FOIL_GEN_III(rpm=40_000)
    >>> K, C = brg.coefficients_at_rpm(40_000)
    >>> 5e5 < K[0, 0] < 3e6
    True
    >>> C[0, 0] > 0
    True
    """
    if axial_position is None:
        axial_position = Q(0.0, "m")

    rpm_table = [Q(r, "rpm") for r in _NASA_RPM_TABLE_RPM]
    K_table = [
        _kc_matrix(_NASA_K_YY[i], _NASA_K_ZZ[i], _NASA_C_YY[i], _NASA_C_ZZ[i])[0]
        for i in range(len(_NASA_RPM_TABLE_RPM))
    ]
    C_table = [
        _kc_matrix(_NASA_K_YY[i], _NASA_K_ZZ[i], _NASA_C_YY[i], _NASA_C_ZZ[i])[1]
        for i in range(len(_NASA_RPM_TABLE_RPM))
    ]

    return TabulatedBearing(
        name=name,
        axial_position=axial_position,
        rpm_table=rpm_table,
        K_table=K_table,
        C_table=C_table,
    )


# ---------------------------------------------------------------------------
# Registry helpers — for API endpoint and UI population (W-32 AC2)
# ---------------------------------------------------------------------------

# Canonical preset registry. Maps preset name to (callable, description, citation).
_PRESET_REGISTRY: Dict[str, dict] = {
    "CAPSTONE_C30_FOIL_BEARING": {
        "callable": CAPSTONE_C30_FOIL_BEARING,
        "display_name": "Capstone C30-class air foil bearing (~80 kRPM)",
        "description": (
            "Representative air foil bearing for a Capstone C30-class microturbine. "
            "30 mm shaft diameter, rated to ~80,000 RPM. "
            "K-C values from Heshmat et al. (1983) for bearing number Λ ≈ 5.5."
        ),
        "design_speed_rpm": 80_000,
        "shaft_diameter_mm": 30.0,
        "citation": CITATION_HESHMAT_1983,
        "rpm_range": [10_000, 80_000],
    },
    "DELLACORTE_NASA_FOIL_GEN_III": {
        "callable": DELLACORTE_NASA_FOIL_GEN_III,
        "display_name": "NASA Generation III foil bearing reference (DellaCorte 2000)",
        "description": (
            "NASA Generation III foil journal bearing reference. "
            "50 mm shaft diameter, L/D = 1, design speed ~40,000 RPM. "
            "C1 = 1.8 N/mm² load-capacity coefficient (DellaCorte & Valco 2000, Table 1)."
        ),
        "design_speed_rpm": 40_000,
        "shaft_diameter_mm": 50.0,
        "citation": CITATION_DELLACORTE_VALCO_2000,
        "rpm_range": [5_000, 40_000],
    },
}


def foil_bearing_preset_names() -> List[str]:
    """Return the list of available foil bearing preset names.

    W-32 AC2: used by ``GET /api/bearings/presets`` to populate the UI picker.

    >>> names = foil_bearing_preset_names()
    >>> "CAPSTONE_C30_FOIL_BEARING" in names
    True
    >>> "DELLACORTE_NASA_FOIL_GEN_III" in names
    True
    """
    return list(_PRESET_REGISTRY.keys())


def get_foil_bearing_preset(preset_name: str) -> dict:
    """Return the registry entry for a named foil bearing preset.

    Args:
        preset_name: One of the keys from :func:`foil_bearing_preset_names`.

    Returns:
        Dict with keys: ``callable``, ``display_name``, ``description``,
        ``design_speed_rpm``, ``shaft_diameter_mm``, ``citation``,
        ``rpm_range``.

    Raises:
        KeyError: If ``preset_name`` is not in the registry.

    W-32: used by the API bearing presets endpoint and rotor dynamics test.
    """
    if preset_name not in _PRESET_REGISTRY:
        available = ", ".join(_PRESET_REGISTRY.keys())
        raise KeyError(
            f"Unknown foil bearing preset {preset_name!r}. "
            f"Available presets: {available}"
        )
    return _PRESET_REGISTRY[preset_name]
