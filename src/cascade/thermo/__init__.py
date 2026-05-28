"""Real-gas thermodynamic state evaluation for Cascade.

Per SPEC_SHEET.md §3.4, every cycle ↔ meanline handoff in v1 uses one of two
backends, both exposed here:

- `NasaMixture`: NASA 9-coefficient polynomial mixture (McBride, Zehe & Gordon
  2002, NASA TP-2002-211556 for the air majors; Burcat & Ruscic 2005 ANL-05/20
  for the combustion / fuel additions per ADAPT-017). The default for air
  upstream of any burner and combustion-products downstream. Ideal-gas in p-v,
  temperature-dependent cp/h/s via the polynomial. v1 species (12 total):
  N2, O2, Ar, CO2, H2O, CO, H2, OH, NO, NO2, CH4, He. (C12H23 + soot remain
  out of v1 scope; sCO2 goes through CoolPropFluid.)

- `CoolPropFluid`: Wraps CoolProp's `PropsSI` for pure fluids only (sCO2, He,
  H2, Water, Air-as-pure-fluid, etc.). Lazy-imports CoolProp on first use so
  `cascade.thermo` itself imports cleanly even without CoolProp installed.

Selection rule (SPEC_SHEET §3.4):
- If the cycle/network is multi-species (air + combustion products) → NasaMixture.
- If the cycle/network is single-species pure fluid → CoolPropFluid.

Both classes implement the same minimal interface:
    h(T, p, composition)     -> Quantity[J/kg]
    cp(T, composition)       -> Quantity[J/(kg*K)]
    s(T, p, composition)     -> Quantity[J/(kg*K)]
    gamma(T, composition)    -> float
    R_specific(composition)  -> Quantity[J/(kg*K)]

Refusal behavior per SPEC_SHEET §13:
- T < 200 K or T > 6000 K → RegimeOutOfValidity (NasaMixture).
- Pressure ≤ 0 → ValueError immediately (also Port-level check).
- Unsupported species in mixture → RegimeOutOfValidity with code
  `UNSUPPORTED_SPECIES`.
"""

from __future__ import annotations

from cascade.thermo.coolprop_fluid import CoolPropFluid
from cascade.thermo.nasa_mixture import (
    P_REF_ENTROPY,
    T_MAX_VALID,
    T_MIN_VALID,
    NasaMixture,
    RegimeOutOfValidity,
    burn_mass_balance,
)

__all__ = [
    "NasaMixture",
    "CoolPropFluid",
    "RegimeOutOfValidity",
    "burn_mass_balance",
    "P_REF_ENTROPY",
    "T_MIN_VALID",
    "T_MAX_VALID",
]
