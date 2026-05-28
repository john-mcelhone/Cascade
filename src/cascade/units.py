"""Canonical units engine for Cascade.

Implements SPEC_SHEET.md §3 — the cross-cutting interface every other module
imports. The canonical *store* is SI; conversion happens at I/O boundaries
(project file → in-memory state) and at the display layer.

Key types:
- `Q` (`Quantity`): a typed quantity carrying value + unit. Built on Pint.
- `Port`: the canonical thermodynamic state at every component boundary.
- `RotorShape`, `RotorSection`, `LumpedDisk`: the mean-line → rotor-dyn
  geometry handoff (SPEC_SHEET §3.5).
- `Species`, `Composition`: composition tracking through cycles + networks.

Design choices:
- Angle convention: canonical store is radians-from-axial. The legacy
  `from-tangential` convention is converted at the boundary.
- Canonical Port type: declared here, imported by every other module.
- Convergence criterion: co-simulation residual uses the L₂-norm defined
  in `port_residual_norm()`.
- Meanline → rotor-dyn handoff: RotorShape declared here.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import numpy as np
import pint

# --- Pint registry -----------------------------------------------------------

# We use a single application-wide Pint registry. Pint objects from different
# registries are not interoperable; sharing one registry is mandatory.
ureg = pint.UnitRegistry()
# Pint 0.22+ uses ureg.formatter.default_format; older versions use ureg.default_format.
try:
    ureg.formatter.default_format = "~P"
except AttributeError:
    ureg.default_format = "~P"  # pragma: no cover
UnitRegistry = pint.UnitRegistry  # re-export for type hints
Quantity = ureg.Quantity


def Q(value: float | int, unit: str) -> Quantity:
    """Construct a Cascade quantity from a numeric value and a unit string.

    >>> Q(206.770, "kPa").to("Pa").magnitude
    206770.0
    >>> Q(530.0, "K").magnitude
    530.0
    """
    return ureg.Quantity(value, unit)


# --- Species + Composition ---------------------------------------------------


class Species(str, Enum):
    """The species catalog. Mass fractions are tracked per Port."""

    N2 = "N2"
    O2 = "O2"
    AR = "Ar"
    CO2 = "CO2"
    H2O = "H2O"
    CO = "CO"
    H2 = "H2"
    OH = "OH"
    NO = "NO"
    NO2 = "NO2"
    CH4 = "CH4"
    C12H23 = "C12H23"  # Jet-A surrogate
    SOOT = "soot"
    HE = "He"
    SCO2 = "sCO2"  # treated as a single-species pure fluid

    @property
    def molar_mass_g_per_mol(self) -> float:
        """Molar mass in g/mol — canonical reference for mixture conversions."""
        return _MOLAR_MASS_G_PER_MOL[self]


_MOLAR_MASS_G_PER_MOL: dict[Species, float] = {
    Species.N2: 28.0134,
    Species.O2: 31.9988,
    Species.AR: 39.948,
    Species.CO2: 44.0095,
    Species.H2O: 18.01528,
    Species.CO: 28.0101,
    Species.H2: 2.01588,
    Species.OH: 17.00734,
    Species.NO: 30.0061,
    Species.NO2: 46.0055,
    Species.CH4: 16.0425,
    Species.C12H23: 167.31,
    Species.SOOT: 12.011,
    Species.HE: 4.002602,
    Species.SCO2: 44.0095,
}


# Standard dry-air composition (sea level, ISA), mass fractions
STANDARD_DRY_AIR: dict[Species, float] = {
    Species.N2: 0.7553,
    Species.O2: 0.2314,
    Species.AR: 0.0129,
    Species.CO2: 0.0004,
}


@dataclass(frozen=True)
class Composition:
    """A mass-fraction composition. Sum must be ≈ 1.

    Use `Composition.air()` for the canonical dry-air composition.
    Use `Composition.pure(species)` for a single-species working fluid.
    """

    mass_fractions: Mapping[Species, float]

    def __post_init__(self) -> None:
        s = sum(self.mass_fractions.values())
        if not (0.999 <= s <= 1.001):
            msg = (
                f"Composition mass fractions must sum to 1.0 "
                f"(±0.001); got {s:.6f}. Fractions: {dict(self.mass_fractions)}"
            )
            raise ValueError(msg)

    @classmethod
    def air(cls) -> Composition:
        return cls(mass_fractions=dict(STANDARD_DRY_AIR))

    @classmethod
    def pure(cls, species: Species) -> Composition:
        return cls(mass_fractions={species: 1.0})

    @property
    def mean_molar_mass_g_per_mol(self) -> float:
        """Mass-weighted mean molar mass."""
        # Mean molar mass for mixture: 1/M_bar = sum(y_i / M_i)
        inv_m = sum(y / s.molar_mass_g_per_mol for s, y in self.mass_fractions.items())
        return 1.0 / inv_m

    def get(self, species: Species, default: float = 0.0) -> float:
        return self.mass_fractions.get(species, default)


# --- Port: the canonical inter-component thermodynamic state -----------------


@dataclass(frozen=True)
class Port:
    """Canonical thermodynamic state at any component boundary.

    Per SPEC_SHEET §3.1, every co-sim handoff in Cascade goes through `Port`.
    All SI units. Mass flow is signed (positive = downstream).

    Internal solver variables (Mach, velocity triangles, etc.) are derived
    locally from Port; the inter-component contract is Port only.
    """

    pressure_total: Quantity  # [Pa]
    temperature_total: Quantity  # [K]
    mass_flow: Quantity  # [kg/s] — signed
    composition: Composition
    rotational_speed: Quantity = field(default_factory=lambda: Q(0.0, "rad/s"))
    swirl_ratio: float = 0.0  # V_theta / (omega * r_mean) — dimensionless
    velocity_meridional: Quantity = field(default_factory=lambda: Q(0.0, "m/s"))
    radius_mean: Quantity = field(default_factory=lambda: Q(0.0, "m"))

    def __post_init__(self) -> None:
        # Validate dimensions; refuse silent unit mismatches.
        _require_dim(self.pressure_total, "[mass] / [length] / [time] ** 2", "pressure_total")
        _require_dim(self.temperature_total, "[temperature]", "temperature_total")
        _require_dim(self.mass_flow, "[mass] / [time]", "mass_flow")
        _require_dim(self.rotational_speed, "1 / [time]", "rotational_speed")
        _require_dim(self.velocity_meridional, "[length] / [time]", "velocity_meridional")
        _require_dim(self.radius_mean, "[length]", "radius_mean")

        # Reasonability bounds — catches Kzz=3.8e14 / maxW2=5.4 / negative T issues
        # at the interface boundary.
        # NOTE: `<= 0` alone lets NaN through (NaN is neither <= 0 nor > 0). We
        # must explicitly require math.isfinite for every positive physical
        # quantity, otherwise NaN/Inf silently propagates through downstream
        # solvers (residual norms, Mach calculations, etc.).
        _require_finite_positive(self.pressure_total, "Pa", "pressure_total")
        _require_finite_positive(self.temperature_total, "K", "temperature_total")
        # mass_flow is signed (positive = downstream); we only require finite.
        _require_finite(self.mass_flow, "kg/s", "mass_flow")
        # The remaining quantities (rotational_speed, velocity_meridional,
        # radius_mean) are also kept finite — NaN would silently corrupt the
        # 5-vector returned by to_si_tuple() and any L2 residual built from it.
        _require_finite(self.rotational_speed, "rad/s", "rotational_speed")
        _require_finite(self.velocity_meridional, "m/s", "velocity_meridional")
        _require_finite(self.radius_mean, "m", "radius_mean")
        if not math.isfinite(self.swirl_ratio):
            msg = (
                f"Port.swirl_ratio must be finite; got {self.swirl_ratio!r}"
            )
            raise ValueError(msg)

    def to_si_tuple(self) -> tuple[float, float, float, float, float]:
        """The 5-vector (P_t, T_t, ṁ, ω, swirl) in canonical SI for residual computation."""
        return (
            self.pressure_total.to("Pa").magnitude,
            self.temperature_total.to("K").magnitude,
            self.mass_flow.to("kg/s").magnitude,
            self.rotational_speed.to("rad/s").magnitude,
            self.swirl_ratio,
        )


# --- Port residual norm (SPEC_SHEET §3.3) ------------------------------------


def port_residual_norm(
    ports_a: list[Port],
    ports_b: list[Port],
    design_reference: list[Port],
) -> float:
    """L₂-norm of the 5-vector Port-delta between two sides of a co-sim boundary,
    normalized by design-point values.

    Per SPEC_SHEET §3.3. The co-simulation criterion uses this norm. Converged
    when ‖Δ‖₂ < tol (default tol = 1e-4 for co-sim, see cascade.numerics.tolerances).
    """
    if not (len(ports_a) == len(ports_b) == len(design_reference)):
        msg = (
            f"port_residual_norm requires equal-length lists; "
            f"got {len(ports_a)}/{len(ports_b)}/{len(design_reference)}"
        )
        raise ValueError(msg)

    deltas: list[float] = []
    for a, b, ref in zip(ports_a, ports_b, design_reference):
        a_si = a.to_si_tuple()
        b_si = b.to_si_tuple()
        ref_si = ref.to_si_tuple()
        for ai, bi, ri in zip(a_si, b_si, ref_si):
            denom = abs(ri) if abs(ri) > 1e-12 else 1.0  # avoid 0-div for unset swirl
            deltas.append((ai - bi) / denom)
    return float(np.linalg.norm(deltas))


# --- RotorShape: meanline → rotor-dyn handoff (SPEC_SHEET §3.5) --------------


@dataclass(frozen=True)
class RotorSection:
    """A cylindrical shell of rotor with material and axial location.

    Used by the rotor-dynamics beam-FEM to build per-element mass + stiffness.
    """

    diameter_outer: Quantity  # [m]
    diameter_inner: Quantity  # [m]
    length: Quantity  # [m]
    density: Quantity  # [kg/m^3]
    axial_position: Quantity  # [m], measured from canonical datum (upstream-most face)
    material: str  # MaterialID — registered in cascade.materials
    # W-13: optional operating temperature for temperature-dependent material lookup.
    # When None or omitted, room temperature (293 K) is used.
    temperature_K: Optional[float] = None  # [K]

    def __post_init__(self) -> None:
        _require_dim(self.diameter_outer, "[length]", "diameter_outer")
        _require_dim(self.diameter_inner, "[length]", "diameter_inner")
        _require_dim(self.length, "[length]", "length")
        _require_dim(self.density, "[mass] / [length] ** 3", "density")
        _require_dim(self.axial_position, "[length]", "axial_position")
        if self.diameter_inner > self.diameter_outer:
            msg = (
                f"RotorSection.diameter_inner must not exceed diameter_outer; "
                f"got inner={self.diameter_inner}, outer={self.diameter_outer}"
            )
            raise ValueError(msg)
        if self.length.magnitude <= 0:
            msg = f"RotorSection.length must be > 0; got {self.length}"
            raise ValueError(msg)


@dataclass(frozen=True)
class LumpedDisk:
    """A point-mass / inertia at an axial position. Models impellers, discs, volutes.

    inertia_polar (Ip) is the moment of inertia about the rotation axis.
    inertia_diametrical (Id) is the moment of inertia about a transverse axis.
    """

    mass: Quantity  # [kg]
    inertia_polar: Quantity  # [kg·m^2]
    inertia_diametrical: Quantity  # [kg·m^2]
    axial_position: Quantity  # [m]

    def __post_init__(self) -> None:
        _require_dim(self.mass, "[mass]", "mass")
        _require_dim(self.inertia_polar, "[mass] * [length] ** 2", "inertia_polar")
        _require_dim(self.inertia_diametrical, "[mass] * [length] ** 2", "inertia_diametrical")
        _require_dim(self.axial_position, "[length]", "axial_position")
        if self.mass.magnitude < 0:
            msg = f"LumpedDisk.mass must be ≥ 0; got {self.mass}"
            raise ValueError(msg)


@dataclass(frozen=True)
class RotorShape:
    """The mean-line → rotor-dyn artifact (SPEC_SHEET §3.5).

    Produced deterministically by the geometry adapter; consumed by the
    beam-FEM rotor-dyn solver. The conversion is one-way; rotor-dyn does
    not iterate back into the meanline.
    """

    sections: list[RotorSection]
    disks: list[LumpedDisk]
    canonical_datum: str = "upstream-most face of upstream-most station"

    @property
    def length_total(self) -> Quantity:
        if not self.sections:
            return Q(0.0, "m")
        positions = [s.axial_position + s.length for s in self.sections]
        return max(positions)

    @property
    def mass_total(self) -> Quantity:
        section_mass = sum(
            (
                np.pi
                / 4
                * (s.diameter_outer ** 2 - s.diameter_inner ** 2)
                * s.length
                * s.density
                for s in self.sections
            ),
            start=Q(0.0, "kg"),
        )
        disk_mass = sum((d.mass for d in self.disks), start=Q(0.0, "kg"))
        return section_mass + disk_mass


# --- Angle convention helpers (SPEC_SHEET §3.2) ------------------------------


def deg_from_tangential_to_rad_from_axial(angle_from_tangential_deg: float) -> float:
    """Convert the legacy angle convention to Cascade canonical.

    Legacy tools store blade and flow angles measured *from the
    tangential direction*. Cascade's canonical store is *from the axial direction*
    in radians. They differ by π/2.

    >>> import math
    >>> # 90° from tangential = 0 rad from axial (pure-radial inflow / axial outflow)
    >>> abs(deg_from_tangential_to_rad_from_axial(90.0)) < 1e-12
    True
    >>> # 0° from tangential = π/2 rad from axial (pure-tangential)
    >>> abs(deg_from_tangential_to_rad_from_axial(0.0) - math.pi/2) < 1e-12
    True
    """
    import math

    return math.pi / 2 - math.radians(angle_from_tangential_deg)


def rad_from_axial_to_deg_from_tangential(angle_from_axial_rad: float) -> float:
    """The inverse of `deg_from_tangential_to_rad_from_axial`. Used at the display layer."""
    import math

    return math.degrees(math.pi / 2 - angle_from_axial_rad)


# --- Private helpers ---------------------------------------------------------


def _require_dim(value: Any, expected_dim: str, name: str) -> None:
    """Refuse silent unit mismatches: every Port and RotorShape field is
    dimension-checked at construction. The error message names the field so a
    user sees `port.temperature_total expected [temperature], got [length]`.
    """
    if not isinstance(value, Quantity):
        msg = f"{name} must be a Pint Quantity (got {type(value).__name__})"
        raise TypeError(msg)
    # Pint's `.check()` accepts a dimensionality string like "[length]"
    if not value.check(expected_dim):
        msg = (
            f"{name} expected dimension {expected_dim}; "
            f"got {value.dimensionality} (value = {value})"
        )
        raise TypeError(msg)


def _require_finite(value: Quantity, unit: str, name: str) -> None:
    """Refuse NaN / ±Inf magnitudes for a positively-signed Quantity.

    NaN is the silent killer: ``NaN <= 0`` is False *and* ``NaN > 0`` is False,
    so any guard of the form ``if x <= 0: raise`` silently lets NaN through
    and the bad value propagates through every downstream solver. Apply this
    on every Port quantity that must be a real number.
    """
    mag = value.to(unit).magnitude
    if not math.isfinite(float(mag)):
        msg = (
            f"Port.{name}={value} must be finite "
            f"(got magnitude {mag!r} in {unit})"
        )
        raise ValueError(msg)


def _require_finite_positive(value: Quantity, unit: str, name: str) -> None:
    """Refuse NaN / ±Inf / non-positive magnitudes for a strictly-positive Quantity."""
    mag = float(value.to(unit).magnitude)
    if not math.isfinite(mag):
        msg = (
            f"Port.{name} must be finite (and > 0 {unit}); "
            f"got {value} (magnitude={mag!r})"
        )
        raise ValueError(msg)
    if mag <= 0:
        msg = f"Port.{name} must be > 0 {unit}; got {value}"
        raise ValueError(msg)
