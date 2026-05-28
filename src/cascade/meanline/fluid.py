"""Minimal perfect-gas / thermally-perfect-gas fluid model used by the
mean-line solvers.

This is a stand-alone shim that lets the mean-line module not depend on the
(not-yet-written) `cascade.thermo` package. When `cascade.thermo` lands, the
mean-line module will accept a `NasaMixture` or `CoolPropFluid` object that
provides the same interface; this `PerfectGas` is the calibrated default for
ideal-gas validation cases (Eckardt: air; Whitney-Stewart: helium-substitute
or air-substitute; Glassman: air).

References:
- NIST RP-Air-1985 polynomials (γ, cp, R for air)
- Reid, Prausnitz, Poling: *The Properties of Gases and Liquids*, 5th ed.,
  McGraw-Hill 2001, App. A.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PerfectGas:
    """Calorically perfect ideal gas. Constant cp, γ.

    Defaults are dry air at ISA: cp = 1004.5 J/kg/K, γ = 1.4.
    Helium override: cp = 5193 J/kg/K, γ = 1.667 (Whitney-Stewart RIT-1).

    Citation: NIST SP 968 (Lemmon et al. 2000); Reid-Prausnitz-Poling
    5th ed. (2001) App. A.
    """

    cp_J_per_kgK: float = 1004.5
    gamma: float = 1.4
    name: str = "dry-air-ISA"
    dynamic_viscosity: float = 1.81e-5  # kg/m/s at 288 K

    @property
    def R_specific(self) -> float:
        return self.cp_J_per_kgK * (self.gamma - 1.0) / self.gamma

    def cv(self) -> float:
        return self.cp_J_per_kgK / self.gamma

    def static_from_total(self, P_total: float, T_total: float,
                          mach: float) -> "tuple[float, float, float]":
        """Return (P_static, T_static, rho_static) given total state + Mach."""
        T_static = T_total / (1.0 + 0.5 * (self.gamma - 1.0) * mach * mach)
        P_static = P_total * (T_static / T_total) ** (self.gamma
                                                      / (self.gamma - 1.0))
        rho = P_static / (self.R_specific * T_static)
        return P_static, T_static, rho

    def total_from_static(self, P_static: float, T_static: float,
                          velocity: float) -> "tuple[float, float]":
        """Return (P_total, T_total) given static state + velocity magnitude."""
        T_total = T_static + 0.5 * velocity * velocity / self.cp_J_per_kgK
        P_total = P_static * (T_total / T_static) ** (self.gamma
                                                      / (self.gamma - 1.0))
        return P_total, T_total

    def density(self, P: float, T: float) -> float:
        return P / (self.R_specific * T)

    def speed_of_sound(self, T: float) -> float:
        return math.sqrt(self.gamma * self.R_specific * T)


# Canonical instances
AIR = PerfectGas(cp_J_per_kgK=1004.5, gamma=1.4, name="dry-air-ISA",
                 dynamic_viscosity=1.81e-5)
"""Standard dry air at ISA conditions."""

HELIUM = PerfectGas(cp_J_per_kgK=5193.0, gamma=1.667, name="helium",
                    dynamic_viscosity=1.99e-5)
"""Helium (Whitney-Stewart RIT-1 working fluid). Reid-Prausnitz-Poling App. A."""


def air_hot(T_ref: float = 1100.0) -> PerfectGas:
    """Hot-air approximation (Whitney-Stewart point, T~1100 K).
    γ drops slightly with temperature, cp rises. NASA SP-273 polynomials
    give γ(1100K) ≈ 1.349, cp(1100K) ≈ 1162 J/kg/K. We use the
    constant-property approximation around T_ref."""
    # Linear interpolation between 288 K (γ=1.4, cp=1004.5) and 1500 K
    # (γ=1.32, cp=1190).
    f = max(0.0, min(1.0, (T_ref - 288.0) / (1500.0 - 288.0)))
    cp = 1004.5 + f * (1190.0 - 1004.5)
    g = 1.4 + f * (1.32 - 1.4)
    return PerfectGas(cp_J_per_kgK=cp, gamma=g, name=f"hot-air-T{T_ref:.0f}",
                      dynamic_viscosity=4e-5)
