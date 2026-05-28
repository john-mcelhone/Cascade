"""Material dataclass + temperature-property interpolation.

The :class:`Material` is the canonical record consumed by every Cascade
stress, disc, life and rotor calculation. Properties that vary
appreciably with temperature (Young's modulus, yield, CTE, k, cp) are
stored as ``list[tuple[T_K, value]]`` and looked up by piecewise-linear
interpolation between tabulated stations. Properties that vary weakly
with temperature (density at the reference state, Poisson's ratio) are
stored as scalars.

The interpolator refuses out-of-range queries with a
``ValueError`` that includes the supported temperature range -- this is
the contract the SPEC_SHEET §15 refusal envelope relies on. Calling
``E(T_K)`` outside the table range raises rather than silently
extrapolating, because high-T extrapolation of yield / ultimate is
where the most dangerous design errors hide (cf. Concepts NREC review).

Citations: each material's :class:`Material` instance carries a
``source`` string and (optionally) more detail in ``notes``. The source
must be a real open reference -- typically ASM Handbook Vol 1, MMPDS-13,
NIST Cryogenic Materials Database, NASA TM, or a vendor data sheet
(Special Metals, Haynes International).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Interpolation core
# ---------------------------------------------------------------------------


def _interp(table: list[tuple[float, float]], T_K: float, *, name: str = "property") -> float:
    """Piecewise-linear interpolation of ``(T_K, value)`` pairs.

    Tables must be non-empty and sorted by temperature (ascending). At a
    tabulated station the returned value is exact; between stations it
    is the linear blend. *Out-of-range temperatures raise* ``ValueError``
    so that downstream stress / life code never silently uses an
    extrapolated yield strength (the Concepts NREC review specifically
    flagged extrapolation as the failure mode to refuse).

    Parameters
    ----------
    table:
        Sorted list of (T_K, value) tuples. Length >= 1.
    T_K:
        Query temperature, kelvin.
    name:
        Human-readable property name for the error message.

    Raises
    ------
    ValueError
        If ``T_K`` is non-finite, the table is empty, or ``T_K`` is
        outside ``[table[0][0], table[-1][0]]``.

    Examples
    --------
    >>> _interp([(293.0, 200.0), (1000.0, 150.0)], 293.0)
    200.0
    >>> _interp([(293.0, 200.0), (1000.0, 150.0)], 1000.0)
    150.0
    >>> abs(_interp([(293.0, 200.0), (1000.0, 150.0)], 646.5) - 175.0) < 1e-9
    True
    """
    if not math.isfinite(T_K):
        msg = f"Temperature must be finite for {name}; got {T_K}"
        raise ValueError(msg)
    if not table:
        msg = f"Empty table for {name}"
        raise ValueError(msg)

    T_min = table[0][0]
    T_max = table[-1][0]
    # A *tiny* tolerance lets callers pass the integer end-points (293
    # K, 1300 K) without a one-bit FP miss.
    eps = 1e-9 * max(1.0, abs(T_max))
    if T_K < T_min - eps or T_K > T_max + eps:
        msg = (
            f"Temperature {T_K:.2f} K out of range for {name}: "
            f"supported [{T_min:.2f}, {T_max:.2f}] K"
        )
        raise ValueError(msg)

    # Clamp the FP-noise overshoot so we don't trip the endpoint case.
    T = max(T_min, min(T_max, T_K))

    # Exact match? Return the tabulated value verbatim so 'at-knot'
    # queries are bit-exact (regression tests rely on this).
    for T_i, v_i in table:
        if abs(T - T_i) < eps:
            return v_i

    # Linear blend across the bracketing interval. Tables are short
    # (4-7 entries), so a linear scan is faster than bisect.
    for (T_lo, v_lo), (T_hi, v_hi) in zip(table[:-1], table[1:]):
        if T_lo <= T <= T_hi:
            if T_hi == T_lo:  # pragma: no cover -- guarded by sort + dedupe at construction
                return v_lo
            frac = (T - T_lo) / (T_hi - T_lo)
            return v_lo + frac * (v_hi - v_lo)

    # Should be unreachable thanks to the range check above.
    raise ValueError(f"Interpolation failed for {name} at T={T_K} K")  # pragma: no cover


# ---------------------------------------------------------------------------
# Material dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Material:
    """Engineering material with temperature-dependent properties.

    All temperature-dependent fields are sorted ``(T_K, value)`` tables
    with at least two stations spanning the material's intended service
    range. The accessors (``E``, ``sigma_yield``, etc.) return SI base
    units (Pa, K^-1, W/(m·K), J/(kg·K)) and refuse out-of-range queries.

    The ``source`` and ``notes`` fields document where the numbers came
    from. Cascade requires an explicit citation -- silently using a
    cargo-culted value is not acceptable for stress / life calculations
    that feed customer-facing reports.
    """

    name: str
    """Display name, e.g. ``"Inconel 625"``."""

    designation: str
    """Standards designation, e.g. ``"UNS N06625"`` or ``"AMS 5662"``."""

    family: str
    """Family / class string. Common values: ``"Ni-based superalloy"``,
    ``"Ti alloy"``, ``"Alloy steel"``, ``"Stainless steel"``,
    ``"Precipitation-hardening steel"``."""

    density_kg_per_m3: float
    """Density at 293 K [kg/m^3]. Temperature dependence (<1 % over the
    typical operating range) is neglected; if you need it, compute
    rho(T) = rho_293 / (1 + 3 alpha (T - 293))."""

    poisson: float
    """Poisson's ratio [-]. Approximately constant with T for all
    listed families (0.28–0.35)."""

    youngs_modulus_GPa: list[tuple[float, float]]
    """Young's modulus E [GPa] as ``(T_K, E_GPa)`` tuples."""

    yield_strength_MPa: list[tuple[float, float]]
    """0.2% offset yield strength [MPa] as ``(T_K, sigma_y)`` tuples."""

    ultimate_strength_MPa: list[tuple[float, float]]
    """Ultimate tensile strength [MPa] as ``(T_K, sigma_u)`` tuples."""

    thermal_expansion_1_per_K: list[tuple[float, float]]
    """Linear thermal-expansion coefficient alpha as ``(T_K, alpha)``
    tuples in units of K^-1 (not the 1e-6/K convention)."""

    thermal_conductivity_W_per_mK: list[tuple[float, float]]
    """Thermal conductivity k [W/(m·K)] as ``(T_K, k)`` tuples."""

    specific_heat_J_per_kgK: list[tuple[float, float]]
    """Specific heat cp [J/(kg·K)] as ``(T_K, cp)`` tuples."""

    source: str
    """Open-literature citation for the numbers in this record."""

    fatigue_S_N_curve: Optional[list[tuple[int, float]]] = None
    """Optional fatigue S-N curve as ``(cycles_to_failure, alternating
    stress_MPa)`` tuples. For high-cycle fatigue at the reference
    surface finish and load ratio noted in the citation."""

    notes: str = ""
    """Application notes (e.g., "DS columnar grain, [001]" or
    "Solution treated + aged")."""

    max_service_temperature_K: Optional[float] = field(default=None)
    """Recommended upper service temperature [K]. Independent of the
    property-table upper bound; queries above it are *allowed* (so
    short-excursion analysis works) but the UI / report layer flags
    them as out-of-spec."""

    # -- Accessors (SI units) ------------------------------------------------

    def E(self, T_K: float) -> float:
        """Young's modulus in Pa at temperature T_K (linear interp)."""
        return _interp(self.youngs_modulus_GPa, T_K, name=f"E({self.name})") * 1.0e9

    def sigma_yield(self, T_K: float) -> float:
        """0.2% offset yield strength in Pa at T_K."""
        return _interp(self.yield_strength_MPa, T_K, name=f"sigma_y({self.name})") * 1.0e6

    def sigma_ultimate(self, T_K: float) -> float:
        """Ultimate tensile strength in Pa at T_K."""
        return _interp(self.ultimate_strength_MPa, T_K, name=f"sigma_u({self.name})") * 1.0e6

    def alpha_thermal(self, T_K: float) -> float:
        """Linear CTE alpha in K^-1 at T_K."""
        return _interp(self.thermal_expansion_1_per_K, T_K, name=f"alpha({self.name})")

    def thermal_conductivity(self, T_K: float) -> float:
        """Thermal conductivity k in W/(m·K) at T_K."""
        return _interp(
            self.thermal_conductivity_W_per_mK, T_K, name=f"k({self.name})"
        )

    def specific_heat(self, T_K: float) -> float:
        """Specific heat cp in J/(kg·K) at T_K."""
        return _interp(self.specific_heat_J_per_kgK, T_K, name=f"cp({self.name})")

    # -- Convenience: a serialisable summary for the JSON API ---------------

    def as_dict(self) -> dict:
        """Return a JSON-friendly dict (lists, not tuples)."""
        return {
            "name": self.name,
            "designation": self.designation,
            "family": self.family,
            "density_kg_per_m3": self.density_kg_per_m3,
            "poisson": self.poisson,
            "youngs_modulus_GPa": [list(p) for p in self.youngs_modulus_GPa],
            "yield_strength_MPa": [list(p) for p in self.yield_strength_MPa],
            "ultimate_strength_MPa": [list(p) for p in self.ultimate_strength_MPa],
            "thermal_expansion_1_per_K": [list(p) for p in self.thermal_expansion_1_per_K],
            "thermal_conductivity_W_per_mK": [
                list(p) for p in self.thermal_conductivity_W_per_mK
            ],
            "specific_heat_J_per_kgK": [list(p) for p in self.specific_heat_J_per_kgK],
            "fatigue_S_N_curve": (
                [list(p) for p in self.fatigue_S_N_curve]
                if self.fatigue_S_N_curve is not None
                else None
            ),
            "source": self.source,
            "notes": self.notes,
            "max_service_temperature_K": self.max_service_temperature_K,
        }
