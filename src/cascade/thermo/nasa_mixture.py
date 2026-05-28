"""NASA 9-coefficient polynomial mixture state evaluator.

Implements the workhorse real-gas property model for air and combustion products
specified in SPEC_SHEET.md §3.4. The fluid is treated as an ideal gas in p-v
(p = ρ R_specific T) but with full temperature dependence of cp, h, s through
the NASA polynomial.

Mixture rule: mass-fraction weighted (additive ideal-gas mixing). For a mixture
with mass fractions Y_k:

    cp_mix(T) = Σ_k Y_k * cp_k(T)
    h_mix(T)  = Σ_k Y_k * h_k(T)
    s_mix(T, p) = Σ_k Y_k * (s_k(T) − (R_k) * ln(p / p_ref))
                  + (mixing entropy term, optional)
    R_mix = R_universal / M_bar
    γ_mix(T) = cp_mix / (cp_mix − R_mix)

For an ideal-gas mixture, the standard practice (Walsh & Fletcher 2004 §2 and
NPSS / GasTurb conventions) ignores the mixing-entropy term because every cycle
calculation works with the *change* in entropy of a stream of fixed composition,
where the mixing term cancels. We adopt the same convention.

References:
- McBride, Zehe & Gordon 2002, NASA TP-2002-211556 (coefficients).
- Walsh & Fletcher 2004, *Gas Turbine Performance* 2nd ed., Ch. 2 (mixture rules).
- Goodwin et al. 2017, *Cantera* user manual §5 (validated reference for mixture
  thermodynamics with NASA polynomials).
"""

from __future__ import annotations

import math
from typing import Mapping

from cascade.thermo.nasa_coefficients import NASA_DATABASE, R_UNIVERSAL, NasaInterval
from cascade.units import Composition, Q, Quantity, Species


# Reference pressure for entropy (1 atm = 101325 Pa) per NASA convention,
# McBride et al. 2002 §2.2.
P_REF_ENTROPY: float = 101325.0  # [Pa]

# Validity range — outside, raise RegimeOutOfValidity (SPEC_SHEET §13).
# Floor at 200 K matches the low-T polynomial bound; ceiling at 6000 K matches
# high-T polynomial bound. Combustion-product use case rarely exceeds 2500 K.
T_MIN_VALID: float = 200.0
T_MAX_VALID: float = 6000.0


class RegimeOutOfValidity(Exception):
    """Raised when an input falls outside the validated regime of a model.

    Per SPEC_SHEET §13: refusal-not-extrapolation for regime-out-of-validity
    inputs. The cause code is recorded in the .code attribute.
    """

    def __init__(self, message: str, code: str = "REGIME_OUT_OF_VALIDITY") -> None:
        super().__init__(message)
        self.code = code


def _cp_over_R(T: float, intv: NasaInterval) -> float:  # noqa: N802, N803
    """Cp/R from one NASA interval at temperature T [K].

    Form: Cp/R = a1*T^-2 + a2*T^-1 + a3 + a4*T + a5*T^2 + a6*T^3 + a7*T^4
    (McBride et al. 2002 Eq. 2-1).
    """
    return (
        intv.a1 / (T * T)
        + intv.a2 / T
        + intv.a3
        + intv.a4 * T
        + intv.a5 * T * T
        + intv.a6 * T**3
        + intv.a7 * T**4
    )


def _h_over_RT(T: float, intv: NasaInterval) -> float:  # noqa: N802, N803
    """H/(R*T) from one NASA interval at temperature T [K].

    Form: H/(RT) = -a1*T^-2 + a2*ln(T)/T + a3 + a4*T/2 + a5*T^2/3 + a6*T^3/4
                   + a7*T^4/5 + b1/T
    (McBride et al. 2002 Eq. 2-2).
    """
    return (
        -intv.a1 / (T * T)
        + intv.a2 * math.log(T) / T
        + intv.a3
        + intv.a4 * T / 2.0
        + intv.a5 * T * T / 3.0
        + intv.a6 * T**3 / 4.0
        + intv.a7 * T**4 / 5.0
        + intv.b1 / T
    )


def _s_over_R(T: float, intv: NasaInterval) -> float:  # noqa: N802, N803
    """S°(T)/R from one NASA interval at temperature T [K], at p = p_ref.

    Form: S°/R = -a1*T^-2/2 - a2*T^-1 + a3*ln(T) + a4*T + a5*T^2/2 + a6*T^3/3
                  + a7*T^4/4 + b2
    (McBride et al. 2002 Eq. 2-3).
    """
    return (
        -intv.a1 / (2.0 * T * T)
        - intv.a2 / T
        + intv.a3 * math.log(T)
        + intv.a4 * T
        + intv.a5 * T * T / 2.0
        + intv.a6 * T**3 / 3.0
        + intv.a7 * T**4 / 4.0
        + intv.b2
    )


def _check_T(T: float) -> None:  # noqa: N802, N803
    if not math.isfinite(T) or T < T_MIN_VALID:
        msg = (
            f"NASA-mixture: temperature {T} K is below the validated lower "
            f"bound {T_MIN_VALID} K. Polynomial extrapolation refused per "
            f"SPEC_SHEET §13."
        )
        raise RegimeOutOfValidity(msg)
    if T > T_MAX_VALID:
        msg = (
            f"NASA-mixture: temperature {T} K is above the validated upper "
            f"bound {T_MAX_VALID} K. Polynomial extrapolation refused per "
            f"SPEC_SHEET §13."
        )
        raise RegimeOutOfValidity(msg)


def _check_composition(composition: Composition) -> None:
    """Refuse compositions containing species without NASA data in v1,
    or compositions with physically meaningless negative mass fractions
    (ADAPT-029).
    """
    # ADAPT-029: a sum-to-1 check alone admits compositions like
    # Y_N2=1.1, Y_O2=-0.1. Mass fractions must be non-negative; tiny
    # numerical noise around zero is allowed.
    for species, Y in composition.mass_fractions.items():
        if Y < -1e-9:
            msg = (
                f"NasaMixture: species {species.name} has negative mass "
                f"fraction Y={Y}. Must be >= 0."
            )
            raise ValueError(msg)

    unsupported = [
        s.name for s in composition.mass_fractions if s not in NASA_DATABASE
    ]
    if unsupported:
        msg = (
            f"NASA-mixture: composition contains species not in v1 NASA "
            f"database: {unsupported}. v1 supports {sorted(s.name for s in NASA_DATABASE)}. "
            f"Add coefficients in cascade.thermo.nasa_coefficients before using."
        )
        raise RegimeOutOfValidity(msg, code="UNSUPPORTED_SPECIES")


class NasaMixture:
    """Real-gas state evaluator for ideal-gas mixtures using NASA polynomials.

    Public interface (every method returns a `Quantity` from cascade.units):
        h(T, p, composition)    -> [J/kg]            (total specific enthalpy)
        cp(T, composition)      -> [J/(kg*K)]        (specific heat at constant p)
        s(T, p, composition)    -> [J/(kg*K)]        (specific entropy)
        gamma(T, composition)   -> float             (cp/cv ratio, dimensionless)
        R_specific(composition) -> [J/(kg*K)]        (specific gas constant)

    State variables:
        h depends on T only (ideal gas; p does not enter via polynomial but is
          carried for interface symmetry with future real-gas variants).
        s depends on (T, p): s(T, p) = s°(T) - R * ln(p / p_ref).

    Cross-component composition mixing is by mass fraction (Walsh & Fletcher
    2004 §2.4). Sums:
        cp_mix(T)   = Σ_k Y_k cp_k(T)
        h_mix(T)    = Σ_k Y_k h_k(T)
        s_mix(T, p) = Σ_k Y_k [s_k°(T) - R_k ln(p / p_ref)]
    where R_k = R_univ / M_k is the per-species gas constant.

    Per SPEC_SHEET §3.4 and §7: this implementation is the canonical fluid model
    upstream and downstream of any burner; CoolProp is reserved for pure-fluid
    backends only.
    """

    def __init__(self) -> None:  # noqa: D401
        """Construct a NASA-mixture evaluator (stateless; reusable per process)."""

    # --- Pure-species property evaluation -----------------------------------

    def _cp_species(self, T: float, species: Species) -> float:  # noqa: N803
        """Cp [J/(kg*K)] of one species at temperature T [K]."""
        data = NASA_DATABASE[species]
        intv = data.select(T)
        cp_over_R = _cp_over_R(T, intv)
        M_kg = species.molar_mass_g_per_mol * 1e-3
        R_specific = R_UNIVERSAL / M_kg
        return cp_over_R * R_specific

    def _h_species(self, T: float, species: Species) -> float:  # noqa: N803
        """h [J/kg] of one species at temperature T [K]. NASA-zero reference."""
        data = NASA_DATABASE[species]
        intv = data.select(T)
        h_over_RT = _h_over_RT(T, intv)
        M_kg = species.molar_mass_g_per_mol * 1e-3
        R_specific = R_UNIVERSAL / M_kg
        return h_over_RT * R_specific * T

    def _s_species(self, T: float, p: float, species: Species) -> float:  # noqa: N803
        """s [J/(kg*K)] of one species at (T, p)."""
        data = NASA_DATABASE[species]
        intv = data.select(T)
        s_over_R = _s_over_R(T, intv)
        M_kg = species.molar_mass_g_per_mol * 1e-3
        R_specific = R_UNIVERSAL / M_kg
        # s = s°(T) - R * ln(p / p_ref)
        return s_over_R * R_specific - R_specific * math.log(p / P_REF_ENTROPY)

    # --- Public mixture interface ------------------------------------------

    def cp(self, T: Quantity, composition: Composition) -> Quantity:  # noqa: N803
        """Specific heat at constant pressure of the mixture at temperature T.

        Composition is mass-fraction weighted: cp_mix = Σ_k Y_k cp_k(T).
        """
        T_si = T.to("K").magnitude
        _check_T(T_si)
        _check_composition(composition)
        result = sum(
            Y * self._cp_species(T_si, sp)
            for sp, Y in composition.mass_fractions.items()
        )
        return Q(result, "J/(kg*K)")

    def h(  # noqa: D401, N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> Quantity:
        """Total specific enthalpy of the mixture at (T, p).

        Ideal-gas → h depends on T only; p is retained for interface symmetry
        and forward-compatibility with future Helmholtz-EOS variants.
        """
        T_si = T.to("K").magnitude
        _check_T(T_si)
        _check_composition(composition)
        # Validate p has correct dimension and is positive (raises early on
        # silent unit mismatch — SPEC_SHEET §3 refusal contract).
        p_si = p.to("Pa").magnitude
        if p_si <= 0:
            msg = f"NasaMixture.h: pressure must be > 0 Pa; got {p}"
            raise ValueError(msg)
        result = sum(
            Y * self._h_species(T_si, sp)
            for sp, Y in composition.mass_fractions.items()
        )
        return Q(result, "J/kg")

    def s(  # noqa: D401, N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> Quantity:
        """Specific entropy of the mixture at (T, p).

        s_mix(T, p) = Σ_k Y_k [s°_k(T) - R_k * ln(p / p_ref)]
        where R_k = R_universal / M_k.
        """
        T_si = T.to("K").magnitude
        _check_T(T_si)
        _check_composition(composition)
        p_si = p.to("Pa").magnitude
        if p_si <= 0:
            msg = f"NasaMixture.s: pressure must be > 0 Pa; got {p}"
            raise ValueError(msg)
        result = sum(
            Y * self._s_species(T_si, p_si, sp)
            for sp, Y in composition.mass_fractions.items()
        )
        return Q(result, "J/(kg*K)")

    def gamma(self, T: Quantity, composition: Composition) -> float:  # noqa: N803
        """Specific-heat ratio cp/cv of the mixture at temperature T.

        For an ideal gas mixture: cv = cp − R_mix, hence γ = cp / (cp − R_mix).
        """
        cp_mix = self.cp(T, composition).to("J/(kg*K)").magnitude
        R_mix = self.R_specific(composition).to("J/(kg*K)").magnitude
        cv_mix = cp_mix - R_mix
        if cv_mix <= 0:
            msg = f"NasaMixture.gamma: cv ≤ 0 at T = {T}; numerical failure"
            raise RegimeOutOfValidity(msg)
        return cp_mix / cv_mix

    def R_specific(self, composition: Composition) -> Quantity:  # noqa: N802
        """Specific gas constant R = R_universal / M_bar for the mixture.

        M_bar (mean molar mass) is the mass-fraction weighted reciprocal:
            1/M_bar = Σ_k Y_k / M_k
        (Walsh & Fletcher 2004 §2.4 Eq. 2.18.)
        """
        _check_composition(composition)
        # Mean molar mass [kg/mol] (composition stores in g/mol)
        M_kg_per_mol = composition.mean_molar_mass_g_per_mol * 1e-3
        return Q(R_UNIVERSAL / M_kg_per_mol, "J/(kg*K)")

    # --- Convenience: state changes commonly needed by cycle solvers --------

    def T_from_h(  # noqa: N802
        self,
        h_target: Quantity,
        composition: Composition,
        T_guess: Quantity,
        tol: float = 1e-6,
        max_iter: int = 50,
    ) -> Quantity:
        """Invert h(T) for T given h_target [J/kg]. Newton's method.

        Used by the cycle solver: given the result of an isentropic state
        change, the new T is the unique root of h(T) = h_target. NASA
        polynomials guarantee dh/dT = cp > 0, so the root is unique and Newton
        converges from any positive T_guess inside the validity range.

        Convergence tolerance is the inner-solver bound from SPEC_SHEET §3.3:
        1e-6 relative on |h(T) - h_target| / h_target.
        """
        h_t_si = h_target.to("J/kg").magnitude
        T_si = T_guess.to("K").magnitude

        # Mass-fraction weighted h and cp for this composition; precompute once.
        for _ in range(max_iter):
            _check_T(T_si)
            h_now = sum(
                Y * self._h_species(T_si, sp)
                for sp, Y in composition.mass_fractions.items()
            )
            err = h_now - h_t_si
            if abs(err) < max(tol * abs(h_t_si), tol * abs(h_now), 1e-3):
                return Q(T_si, "K")
            cp_now = sum(
                Y * self._cp_species(T_si, sp)
                for sp, Y in composition.mass_fractions.items()
            )
            if cp_now <= 0:
                msg = f"T_from_h: cp ≤ 0 at T={T_si}"
                raise RegimeOutOfValidity(msg)
            # Newton step with simple under-relaxation when far from solution
            dT = -err / cp_now
            # Clip to avoid overshoot outside validity (SPEC_SHEET §15 N-4)
            if dT > 500.0:
                dT = 500.0
            elif dT < -500.0:
                dT = -500.0
            T_si += dT
            if T_si < T_MIN_VALID:
                T_si = T_MIN_VALID + 1.0
        msg = (
            f"T_from_h: failed to converge in {max_iter} iters; "
            f"last T={T_si} K, residual={err:.3e}"
        )
        raise RuntimeError(msg)

    def T_from_s_p(  # noqa: N802
        self,
        s_target: Quantity,
        p: Quantity,
        composition: Composition,
        T_guess: Quantity,
        tol: float = 1e-6,
        max_iter: int = 50,
    ) -> Quantity:
        """Invert s(T, p) for T given (s_target, p). Newton's method.

        Used to compute isentropic states: s(T_2s, p_2) = s(T_1, p_1).
        The partial ∂s/∂T = cp/T > 0 ensures a unique root.
        """
        s_t_si = s_target.to("J/(kg*K)").magnitude
        p_si = p.to("Pa").magnitude
        T_si = T_guess.to("K").magnitude
        for _ in range(max_iter):
            _check_T(T_si)
            s_now = sum(
                Y * self._s_species(T_si, p_si, sp)
                for sp, Y in composition.mass_fractions.items()
            )
            err = s_now - s_t_si
            if abs(err) < tol * max(abs(s_t_si), 1.0):
                return Q(T_si, "K")
            cp_now = sum(
                Y * self._cp_species(T_si, sp)
                for sp, Y in composition.mass_fractions.items()
            )
            # ∂s/∂T = cp/T
            dsdT = cp_now / T_si
            dT = -err / dsdT
            if dT > 500.0:
                dT = 500.0
            elif dT < -500.0:
                dT = -500.0
            T_si += dT
            if T_si < T_MIN_VALID:
                T_si = T_MIN_VALID + 1.0
        msg = (
            f"T_from_s_p: failed to converge in {max_iter} iters; "
            f"last T={T_si} K, residual={err:.3e}"
        )
        raise RuntimeError(msg)


def burn_mass_balance(
    air_composition: Composition,
    fuel_mass_fraction: float,
    fuel_carbon_atoms: int,
    fuel_hydrogen_atoms: int,
    fuel_molar_mass_g_per_mol: float,
) -> Composition:
    """Compute the products-side composition after complete combustion.

    Inputs:
        air_composition: the upstream-of-burner mass-fraction composition.
        fuel_mass_fraction: f = ṁ_fuel / (ṁ_air + ṁ_fuel) — i.e. fuel mass
            divided by total mass downstream of burner.
        fuel_carbon_atoms, fuel_hydrogen_atoms: per-molecule atom count for
            the fuel (used to compute products of complete combustion).
        fuel_molar_mass_g_per_mol: fuel molar mass.

    Output:
        Composition of products (mass fractions).

    Assumes:
        - Complete combustion to CO2 and H2O only.
        - All fuel oxygen demand is taken from the inlet O2 (lean operation).
        - Nitrogen, argon, and any pre-existing CO2/H2O in air pass through.
        - No dissociation (T < ~1700 K typical microturbine; the
          frozen-products approximation is appropriate).

    For stoichiometric CH4-air: CH4 + 2 O2 → CO2 + 2 H2O; this routine
    parameterizes the same arithmetic for arbitrary C_x H_y fuel.
    """
    if not (0.0 <= fuel_mass_fraction < 1.0):
        msg = (
            f"burn_mass_balance: fuel_mass_fraction must be in [0,1); "
            f"got {fuel_mass_fraction}"
        )
        raise ValueError(msg)

    # Treat per kg of total products downstream
    Y_air = 1.0 - fuel_mass_fraction
    Y_fuel = fuel_mass_fraction

    # Per kg of fuel: moles of fuel, of O2 consumed, of CO2 + H2O produced
    n_fuel_per_kg_fuel = 1000.0 / fuel_molar_mass_g_per_mol  # mol
    # CxHy + (x + y/4) O2 → x CO2 + (y/2) H2O
    o2_demand_mol_per_kg_fuel = n_fuel_per_kg_fuel * (
        fuel_carbon_atoms + fuel_hydrogen_atoms / 4.0
    )
    co2_produced_mol_per_kg_fuel = n_fuel_per_kg_fuel * fuel_carbon_atoms
    h2o_produced_mol_per_kg_fuel = n_fuel_per_kg_fuel * (fuel_hydrogen_atoms / 2.0)

    M_O2 = Species.O2.molar_mass_g_per_mol  # noqa: N806
    M_CO2 = Species.CO2.molar_mass_g_per_mol  # noqa: N806
    M_H2O = Species.H2O.molar_mass_g_per_mol  # noqa: N806

    o2_demand_kg_per_kg_fuel = o2_demand_mol_per_kg_fuel * M_O2 / 1000.0
    co2_produced_kg_per_kg_fuel = co2_produced_mol_per_kg_fuel * M_CO2 / 1000.0
    h2o_produced_kg_per_kg_fuel = h2o_produced_mol_per_kg_fuel * M_H2O / 1000.0

    # Per kg of products (Y_fuel is the kg of fuel per kg of products):
    o2_consumed_per_kg_prod = Y_fuel * o2_demand_kg_per_kg_fuel
    co2_added_per_kg_prod = Y_fuel * co2_produced_kg_per_kg_fuel
    h2o_added_per_kg_prod = Y_fuel * h2o_produced_kg_per_kg_fuel

    # Resulting product mass fractions
    products: dict[Species, float] = {}
    for sp, Y in air_composition.mass_fractions.items():
        products[sp] = Y_air * Y  # carry through with air-side scaling

    # Subtract consumed O2 (per kg of products downstream)
    old_o2 = products.get(Species.O2, 0.0)
    new_o2 = old_o2 - o2_consumed_per_kg_prod
    if new_o2 < 0:
        msg = (
            f"burn_mass_balance: fuel mass fraction {fuel_mass_fraction} "
            f"exceeds stoichiometric availability of O2 in air; "
            f"need {o2_consumed_per_kg_prod:.4f}, have {old_o2:.4f}. "
            f"This is rich combustion which is outside the v1 lean-burn scope."
        )
        raise RegimeOutOfValidity(msg, code="RICH_COMBUSTION")
    products[Species.O2] = new_o2

    # Add produced CO2 and H2O
    products[Species.CO2] = products.get(Species.CO2, 0.0) + co2_added_per_kg_prod
    products[Species.H2O] = products.get(Species.H2O, 0.0) + h2o_added_per_kg_prod

    # Renormalize (sums to 1 within numerical noise, but defensive)
    total = sum(products.values())
    if abs(total - 1.0) > 1e-6:
        # Renormalize against numerical drift
        products = {sp: Y / total for sp, Y in products.items()}

    # Filter zero entries to keep composition tidy
    products = {sp: Y for sp, Y in products.items() if Y > 1e-12}

    return Composition(mass_fractions=products)


__all__ = [
    "NasaMixture",
    "RegimeOutOfValidity",
    "burn_mass_balance",
    "P_REF_ENTROPY",
    "T_MIN_VALID",
    "T_MAX_VALID",
]
