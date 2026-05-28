"""Pluggable fluid models for the cycle solver.

The cycle solver does not depend on `NasaMixture` directly; instead it talks to
a `FluidModel` protocol that defines the operations the cycle needs. This lets
us swap in:
- `IdealGasFluid`     — the textbook constant-gamma fluid used by CYC-1 (Çengel
  9-5) and CYC-2 (Çengel 9-7); air-standard analysis with γ = 1.4, c_p = 1.005
  kJ/(kg·K).
- `NasaFluid`         — the real-gas (NASA polynomial mixture) workhorse for
  CYC-3 (Capstone C30) and any production microturbine cycle running on air or
  combustion products.
- `CoolPropPureFluid` — a real-gas single-fluid wrapper around CoolProp's
  multi-parameter Helmholtz EOS. The right choice for supercritical CO2, H2,
  He, steam, and any pure working fluid where ideal-gas (NASA polynomial)
  treatment is physically wrong — especially near the critical point, which is
  exactly where sCO2 cycles live.

All three share the same minimal API consumed by the cycle components.

Per SPEC_SHEET §3.4: this is the EOS-handoff abstraction. Each fluid carries an
explicit `Composition` so the cycle can track species changes across burners
(NASA mixture) or stay locked to a single species (CoolProp pure-fluid).

References:
- Çengel & Boles, *Thermodynamics: An Engineering Approach* 9th ed., Ch. 9 for
  the air-standard analysis convention used by `IdealGasFluid`.
- McBride, Zehe & Gordon 2002, NASA TP-2002-211556 for the polynomials behind
  `NasaFluid`.
- Bell, Wronski, Quoilin, Lemort 2014, *Pure and Pseudo-pure Fluid
  Thermophysical Property Evaluation and the Open-Source Thermophysical
  Property Library CoolProp* (Ind. Eng. Chem. Res. 53, 2014, 2498-2508) for
  `CoolPropPureFluid`.
- Span & Wagner 1996, *A New Equation of State for Carbon Dioxide Covering the
  Fluid Region from the Triple-Point Temperature to 1100 K at Pressures up to
  800 MPa* (J. Phys. Chem. Ref. Data 25, 1509) for the CO2 EOS that CoolProp
  invokes for sCO2 cycles.
"""

from __future__ import annotations

import math
from typing import Protocol, Union, runtime_checkable

from scipy.optimize import brentq

from cascade.thermo.coolprop_fluid import CoolPropFluid as _CoolPropPureFluidImpl
from cascade.thermo.nasa_mixture import NasaMixture, RegimeOutOfValidity
from cascade.units import Composition, Q, Quantity, Species


@runtime_checkable
class FluidModel(Protocol):
    """The minimal interface a cycle component requires of a fluid evaluator.

    Pressure is a required argument to every state-function-of-state because
    real fluids near the critical point (sCO2 at T ≈ 305 K, p ≈ 7.4 MPa) have
    cp that varies by an order of magnitude with pressure. The ideal-gas
    implementations (`IdealGasFluid`, `NasaFluid`) accept `p` and ignore it
    — they remain compatible with the protocol but make explicit, via the
    parameter, that the caller knows the local pressure state.

    Per ADAPT-006: previously `cp(T, composition)` and `gamma(T, composition)`
    silently used p_ref = 101325 Pa inside the CoolProp adapter, giving
    19× wrong cp for sCO2 at the critical point. Fix is to thread the local
    pressure through every callsite.
    """

    def h(  # noqa: N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> Quantity:
        ...

    def cp(  # noqa: N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> Quantity:
        """Mass-basis cp at (T, p). For pure real fluids p MATTERS — esp. near critical."""
        ...

    def s(  # noqa: N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> Quantity:
        ...

    def gamma(  # noqa: N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> float:
        """Ratio of specific heats at (T, p). For pure real fluids p MATTERS."""
        ...

    def R_specific(self, composition: Composition) -> Quantity:  # noqa: N802
        ...

    def T_from_h(  # noqa: N802
        self,
        h_target: Quantity,
        p: Quantity,
        composition: Composition,
        T_guess: Quantity,
    ) -> Quantity:
        """Invert h(T, p) to recover T at the given pressure.

        For ideal-gas fluids `p` is ignored (h depends only on T); for
        real-gas fluids (CoolProp / supercritical regimes) `p` is essential —
        h(T, 7 MPa) and h(T, 25 MPa) for sCO2 near the critical point differ
        by tens of kJ/kg. Always pass the actual outlet pressure of the
        component performing the inversion.
        """
        ...

    def T_isentropic(  # noqa: N802
        self,
        T1: Quantity,
        p1: Quantity,
        p2: Quantity,
        composition: Composition,
    ) -> Quantity:
        """Return T_2s such that s(T_2s, p_2) = s(T_1, p_1)."""
        ...


class IdealGasFluid:
    """Calorically perfect ideal-gas fluid (constant γ, constant cp).

    The "air-standard" assumption of every introductory thermodynamics textbook.
    Used for closed-form validation (CYC-1 Çengel 9-5; CYC-2 Çengel 9-7) where
    the expected η_th is derived under this assumption.

    Defaults match Çengel & Boles 9th ed. Ch. 9 air-standard analysis:
    cp = 1.005 kJ/(kg·K), γ = 1.4. R_specific is derived (cp − cp/γ = 0.287
    kJ/(kg·K), the standard dry-air gas constant).

    Per SPEC_SHEET §3.4 this fluid is OPT-IN ONLY — used for textbook validation
    or by users explicitly choosing it. Production microturbine cycles must use
    NasaFluid (or CoolPropFluid for pure working fluids).
    """

    def __init__(
        self,
        cp: Quantity = Q(1005.0, "J/(kg*K)"),  # noqa: B008
        gamma: float = 1.4,
    ) -> None:
        self._cp: float = cp.to("J/(kg*K)").magnitude
        self._gamma: float = gamma
        self._R: float = self._cp * (1.0 - 1.0 / gamma)  # = cp - cv, with cv = cp/γ

    def cp(  # noqa: ARG002, N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> Quantity:
        # p ignored for calorically perfect ideal gas; cp is constant.
        return Q(self._cp, "J/(kg*K)")

    def h(  # noqa: ARG002, N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> Quantity:
        # h = cp * T (reference at T = 0 K, calorically perfect — matches Çengel)
        T_si = T.to("K").magnitude
        return Q(self._cp * T_si, "J/kg")

    def s(  # noqa: ARG002, N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> Quantity:
        # s = cp ln T − R ln p (+ const); the const cancels for any cycle ΔS
        T_si = T.to("K").magnitude
        p_si = p.to("Pa").magnitude
        s_si = self._cp * math.log(T_si) - self._R * math.log(p_si)
        return Q(s_si, "J/(kg*K)")

    def gamma(  # noqa: ARG002, N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> float:
        # p ignored for calorically perfect ideal gas; γ is constant.
        return self._gamma

    def R_specific(self, composition: Composition) -> Quantity:  # noqa: ARG002, N802
        return Q(self._R, "J/(kg*K)")

    def T_from_h(  # noqa: ARG002, N802
        self,
        h_target: Quantity,
        p: Quantity,
        composition: Composition,
        T_guess: Quantity,
    ) -> Quantity:
        # Ideal gas: h depends only on T, so pressure is ignored here.
        h_si = h_target.to("J/kg").magnitude
        return Q(h_si / self._cp, "K")

    def T_isentropic(  # noqa: ARG002, N802
        self,
        T1: Quantity,
        p1: Quantity,
        p2: Quantity,
        composition: Composition,
    ) -> Quantity:
        # Closed-form for calorically perfect ideal gas:
        # T2/T1 = (p2/p1)^((γ-1)/γ)
        T1_si = T1.to("K").magnitude
        p1_si = p1.to("Pa").magnitude
        p2_si = p2.to("Pa").magnitude
        exponent = (self._gamma - 1.0) / self._gamma
        return Q(T1_si * (p2_si / p1_si) ** exponent, "K")


class NasaFluid:
    """Real-gas fluid using NASA 9-coefficient polynomial mixtures.

    Wraps `cascade.thermo.NasaMixture` to match the cycle's `FluidModel` protocol.
    Adds an isentropic helper since the bare NasaMixture only provides the
    underlying T_from_s_p inversion.

    Per SPEC_SHEET §3.4: this is the default fluid for any cycle involving air
    or combustion products (i.e. every Brayton cycle in the v1 scope).
    """

    def __init__(self, mixture: Union[NasaMixture, None] = None) -> None:
        self._mix: NasaMixture = mixture if mixture is not None else NasaMixture()

    def cp(  # noqa: ARG002, N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> Quantity:
        # p ignored for perfect-gas NASA polynomial (cp = cp(T, composition))
        return self._mix.cp(T, composition)

    def h(  # noqa: N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> Quantity:
        return self._mix.h(T, p, composition)

    def s(  # noqa: N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> Quantity:
        return self._mix.s(T, p, composition)

    def gamma(  # noqa: ARG002, N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> float:
        # p ignored for perfect-gas NASA polynomial (γ = cp(T)/cv(T))
        return self._mix.gamma(T, composition)

    def R_specific(self, composition: Composition) -> Quantity:  # noqa: N802
        return self._mix.R_specific(composition)

    def T_from_h(  # noqa: ARG002, N802
        self,
        h_target: Quantity,
        p: Quantity,
        composition: Composition,
        T_guess: Quantity,
    ) -> Quantity:
        # NASA polynomial h depends only on T (ideal-gas mixture); p is ignored.
        return self._mix.T_from_h(h_target, composition, T_guess)

    def T_isentropic(  # noqa: N802
        self,
        T1: Quantity,
        p1: Quantity,
        p2: Quantity,
        composition: Composition,
    ) -> Quantity:
        """Find T2s such that s(T2s, p2) = s(T1, p1).

        Per SPEC_SHEET §15 N-8 (catastrophic cancellation): we evaluate s_1
        directly from the NASA polynomial — never subtract two large entropies.
        The Newton inversion in T_from_s_p uses dsdT = cp/T > 0, so the root
        is unique and convergence is monotone.
        """
        s1 = self._mix.s(T1, p1, composition)
        return self._mix.T_from_s_p(s1, p2, composition, T1)


class CoolPropPureFluid:
    """Real-gas single-fluid model backed by CoolProp's Helmholtz EOS.

    Adds the cycle protocol's `T_from_h` and `T_isentropic` inversions to the
    bare `cascade.thermo.CoolPropFluid` adapter. Both inversions use SciPy's
    Brent (`brentq`) on a bracketed residual; this is more robust than Newton
    near the critical point of CO2 (T_crit = 304.13 K, p_crit = 7.38 MPa)
    where ∂h/∂T and ∂s/∂T undergo strong non-linearities.

    Operating regime (per the underlying `CoolPropFluid` checks):
    - T in roughly [180, 1500] K for CO2;
    - any pressure CoolProp's PropsSI accepts for the species.

    The composition argument is required by the protocol but is always a
    single-species composition for pure-fluid use; mismatches raise
    `ValueError` from the underlying adapter.

    Use this for sCO2 cycles, hydrogen turbines, helium Brayton, water/steam
    bottoming cycles, and any pure-fluid where NASA polynomials would be
    physically wrong. Combustion-products cycles must continue to use
    `NasaFluid`.
    """

    # Temperature search bounds for inversions. CoolProp will refuse states
    # outside its species-specific envelope earlier, so we can safely use a
    # generous bracket here without sacrificing robustness.
    _T_LOWER_K: float = 180.0
    _T_UPPER_K: float = 1500.0

    def __init__(self, species: Species) -> None:
        # The underlying adapter does the species → CoolProp-name mapping and
        # raises early if the species lacks one.
        self._impl: _CoolPropPureFluidImpl = _CoolPropPureFluidImpl(species)
        self.species: Species = species
        self._composition: Composition = Composition.pure(species)

    # --- Pass-through state functions ---------------------------------------

    def cp(  # noqa: N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> Quantity:
        """cp at the *actual* operating (T, p).

        ADAPT-006 fix: previously this passed only T and the underlying
        adapter substituted p = 101325 Pa, giving a 19× cp error for sCO2
        at the critical point (305 K, 7.4 MPa).
        """
        return self._impl.cp(T, p, composition)

    def h(  # noqa: N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> Quantity:
        return self._impl.h(T, p, composition)

    def s(  # noqa: N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> Quantity:
        return self._impl.s(T, p, composition)

    def gamma(  # noqa: N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> float:
        """γ = cp(T,p) / cv(T,p), evaluated at the actual operating state.

        ADAPT-006 fix: previously p was substituted as 101325 Pa, which is
        far from any sCO2 operating point.
        """
        return self._impl.gamma(T, p, composition)

    def R_specific(self, composition: Composition) -> Quantity:  # noqa: N802
        return self._impl.R_specific(composition)

    # --- Inversions needed by the cycle protocol ----------------------------

    def T_from_h(  # noqa: N802
        self,
        h_target: Quantity,
        p: Quantity,
        composition: Composition,
        T_guess: Quantity,
    ) -> Quantity:
        """Invert h(T, p) → T at the *actual* component outlet pressure.

        For real-gas fluids near the critical point the inversion must be
        performed at the cycle's operating pressure, not a generic 1 atm
        reference. The caller (Compressor / Turbine / Recuperator / Burner)
        knows its outlet pressure and passes it; we feed that pressure
        directly to CoolProp's PropsSI for every state evaluation.
        """
        h_target_J: float = h_target.to("J/kg").magnitude
        p_Pa: float = float(p.to("Pa").magnitude)

        # Bound the search tightly around T_guess (which is already the
        # isentropic estimate from the caller). The CoolProp adapter
        # validates each evaluated point and will refuse anything outside
        # its species envelope.
        T_guess_K: float = float(T_guess.to("K").magnitude)
        lo: float = max(self._T_LOWER_K, T_guess_K - 200.0)
        hi: float = min(self._T_UPPER_K, T_guess_K + 200.0)

        def residual(T_K: float) -> float:
            h = self._impl.h(Q(T_K, "K"), Q(p_Pa, "Pa"), composition).to("J/kg").magnitude
            return h - h_target_J

        # Widen the bracket if the initial guess does not straddle the root.
        # We clamp inward of the underlying adapter's envelope so CoolProp
        # never sees a state below the triple point at low pressures.
        for _ in range(3):
            r_lo = residual(lo)
            r_hi = residual(hi)
            if r_lo * r_hi <= 0:
                break
            lo = max(self._T_LOWER_K, lo - 200.0)
            hi = min(self._T_UPPER_K, hi + 200.0)
            if lo <= self._T_LOWER_K and hi >= self._T_UPPER_K:
                break

        T_K: float = brentq(residual, lo, hi, xtol=1e-3)
        return Q(float(T_K), "K")

    def T_isentropic(  # noqa: N802
        self,
        T1: Quantity,
        p1: Quantity,
        p2: Quantity,
        composition: Composition,
    ) -> Quantity:
        """Find T2 such that s(T2, p2) = s(T1, p1).

        Closed-form is unavailable for real-gas EOS; we Brent on the residual
        `s(T, p2) - s_1`. Because CoolProp's entropy increases monotonically
        with T at fixed p (cp/T > 0 everywhere in the validated regime), the
        root is unique. A generous bracket of [T1 / 4, 4·T1] handles even
        large pressure ratios.
        """
        s1: float = self._impl.s(T1, p1, composition).to("J/(kg*K)").magnitude
        T1_K: float = float(T1.to("K").magnitude)
        p2_Pa: float = float(p2.to("Pa").magnitude)

        lo: float = max(self._T_LOWER_K, T1_K * 0.25)
        hi: float = min(self._T_UPPER_K, T1_K * 4.0)

        def residual(T_K: float) -> float:
            s = self._impl.s(Q(T_K, "K"), Q(p2_Pa, "Pa"), composition).to("J/(kg*K)").magnitude
            return s - s1

        # Widen the bracket once if the initial guess does not straddle.
        if residual(lo) * residual(hi) > 0:
            lo = self._T_LOWER_K
            hi = self._T_UPPER_K

        T_K: float = brentq(residual, lo, hi, xtol=1e-3)
        return Q(float(T_K), "K")


__all__ = [
    "FluidModel",
    "IdealGasFluid",
    "NasaFluid",
    "CoolPropPureFluid",
    "RegimeOutOfValidity",  # re-export for cycle callers
]
