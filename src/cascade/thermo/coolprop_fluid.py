"""CoolProp adapter for pure-fluid real-gas EOS evaluation.

Wraps CoolProp's `PropsSI` (low-level `AbstractState` would be faster but harder
to install across platforms; `PropsSI` is sufficient for v1 cycle work and
matches the GasTurb / NPSS convention).

Per SPEC_SHEET.md §3.4, CoolProp is the canonical backend for:
- Air (when used as a pure fluid, with the Lemmon-Jacobsen-Penoncello-Friend
  2000 EOS).
- CO2 (sCO₂ cycles, Span-Wagner 1996).
- Helium (Ortiz-Vega 2013).
- Hydrogen (Leachman et al. 2009).
- Water / steam (IAPWS-IF97 industrial formulation).

References:
- Bell, I. H., Wronski, J., Quoilin, S., Lemort, V., "Pure and Pseudo-pure
  Fluid Thermophysical Property Evaluation and the Open-Source Thermophysical
  Property Library CoolProp," Ind. Eng. Chem. Res. 53(6), 2014, pp. 2498–2508.

Lazy import: CoolProp is large; we defer the import until actually used. If
not installed, `CoolPropFluid.__init__` succeeds but the first call raises a
descriptive `ImportError`. This matches the SPEC_SHEET §3.4 contract that
`cascade.thermo` itself imports cleanly even on systems without CoolProp.
"""

from __future__ import annotations

import math
from typing import Optional

from cascade.units import Composition, Q, Quantity, Species

# Map of cascade Species to CoolProp fluid names. Only species that map to a
# pure CoolProp fluid appear; combustion mixtures are handled by NasaMixture.
_SPECIES_TO_COOLPROP: dict[Species, str] = {
    Species.N2: "Nitrogen",
    Species.O2: "Oxygen",
    Species.AR: "Argon",
    Species.CO2: "CO2",
    Species.H2O: "Water",
    Species.HE: "Helium",
    Species.H2: "Hydrogen",
    Species.SCO2: "CO2",  # sCO2 uses the same Span-Wagner CO2 EOS
    Species.CH4: "Methane",
}


def _lazy_import_coolprop():  # noqa: ANN202
    """Import CoolProp.PropsSI on first use.

    On ImportError, raise a clean, actionable message rather than the bare
    Python traceback. Per SPEC_SHEET §3.4: CoolProp is optional for v1; the
    user-facing message must point at installation guidance.
    """
    try:
        from CoolProp.CoolProp import PropsSI  # type: ignore[import-not-found]

        return PropsSI
    except ImportError as exc:
        msg = (
            "CoolProp is not installed. The cascade.thermo.CoolPropFluid backend "
            "requires CoolProp >= 6.6. Install with:\n"
            "    pip install coolprop\n"
            "or use cascade.thermo.NasaMixture for air / combustion products "
            "(no CoolProp required). See SPEC_SHEET §3.4 for the fluid model "
            "selection criteria."
        )
        raise ImportError(msg) from exc


# Reasonable validity envelope; CoolProp itself enforces its own per-fluid
# bounds, but we want a clean refusal at the cascade.thermo boundary.
T_MIN_VALID: float = 50.0
T_MAX_VALID: float = 3000.0


class CoolPropFluid:
    """Single-species (pure fluid) real-gas state evaluator backed by CoolProp.

    Public interface matches `NasaMixture` for substitution at the cycle
    component level. The `composition` argument is accepted for interface
    symmetry but must be a single-species composition matching `self.species`;
    a mismatch raises ValueError.

    Per SPEC_SHEET §3.4: this backend is for pure-fluid working fluids only.
    For air-or-combustion-products use `NasaMixture`.

    Construction is cheap and side-effect-free (no CoolProp import yet); the
    first state-evaluation call triggers the lazy import.

    Example:
        >>> # NOTE: requires CoolProp installed
        >>> co2 = CoolPropFluid(Species.SCO2)  # doctest: +SKIP
        >>> h_t = co2.h(Q(310.0, "K"), Q(8e6, "Pa"),
        ...             Composition.pure(Species.SCO2))  # doctest: +SKIP
    """

    def __init__(self, species: Species) -> None:
        if species not in _SPECIES_TO_COOLPROP:
            msg = (
                f"CoolPropFluid: species {species.name} has no CoolProp "
                f"mapping in v1. Supported: "
                f"{sorted(s.name for s in _SPECIES_TO_COOLPROP)}."
            )
            raise ValueError(msg)
        self.species: Species = species
        self.coolprop_name: str = _SPECIES_TO_COOLPROP[species]
        self._props_si: Optional[object] = None  # lazy
        self._composition: Composition = Composition.pure(species)

    def _props(self):  # noqa: ANN202
        """Return the cached CoolProp.PropsSI callable, lazily imported."""
        if self._props_si is None:
            self._props_si = _lazy_import_coolprop()
        return self._props_si

    def _check_composition(self, composition: Composition) -> None:
        """Refuse a multi-species composition for a pure-fluid backend."""
        if (
            len(composition.mass_fractions) != 1
            or self.species not in composition.mass_fractions
            or abs(composition.get(self.species, 0.0) - 1.0) > 1e-9
        ):
            msg = (
                f"CoolPropFluid({self.species.name}): composition must be "
                f"pure {self.species.name}; got {dict(composition.mass_fractions)}. "
                f"For mixtures, use NasaMixture."
            )
            raise ValueError(msg)

    @staticmethod
    def _check_T(T: float) -> None:  # noqa: N802, N803
        if not math.isfinite(T) or T < T_MIN_VALID:
            msg = (
                f"CoolPropFluid: temperature {T} K below validated minimum "
                f"{T_MIN_VALID} K"
            )
            raise ValueError(msg)
        if T > T_MAX_VALID:
            msg = (
                f"CoolPropFluid: temperature {T} K above validated maximum "
                f"{T_MAX_VALID} K"
            )
            raise ValueError(msg)

    # --- Public interface (mirrors NasaMixture) -----------------------------

    def cp(  # noqa: N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> Quantity:
        """Specific heat cp [J/(kg*K)] at the given (T, p) state.

        For real fluids near the critical point (e.g. sCO2 at 305 K, 7.4 MPa)
        cp is a strong function of *both* T and p — at the critical point it
        diverges. Always evaluate at the actual operating pressure.

        Per ADAPT-006: the previous signature `cp(T, composition)` silently
        substituted p = 101325 Pa, producing a 19× cp error at the sCO2
        critical point. The pressure argument is now required.
        """
        T_si = T.to("K").magnitude
        p_si = p.to("Pa").magnitude
        self._check_T(T_si)
        self._check_composition(composition)
        try:
            cp_si = self._props()(
                "CPMASS", "T", T_si, "P", p_si, self.coolprop_name
            )
        except Exception as exc:  # noqa: BLE001 — CoolProp raises generic Exception
            from cascade.thermo.nasa_mixture import RegimeOutOfValidity
            msg = (
                f"CoolPropFluid.cp({self.species.name}): PropsSI failed at "
                f"T={T_si} K, p={p_si} Pa — likely a state too close to the "
                f"critical point or outside the species envelope. "
                f"CoolProp error: {exc}"
            )
            raise RegimeOutOfValidity(msg, code="COOLPROP_NEAR_CRITICAL") from exc
        cp_si_f = float(cp_si)
        if not math.isfinite(cp_si_f):
            from cascade.thermo.nasa_mixture import RegimeOutOfValidity
            msg = (
                f"CoolPropFluid.cp({self.species.name}): non-finite cp "
                f"({cp_si_f}) at T={T_si} K, p={p_si} Pa — at or beyond the "
                f"critical point. Refusing per SPEC_SHEET §13."
            )
            raise RegimeOutOfValidity(msg, code="COOLPROP_NEAR_CRITICAL")
        return Q(cp_si_f, "J/(kg*K)")

    def h(  # noqa: N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> Quantity:
        """Specific enthalpy [J/kg] at (T, p)."""
        T_si = T.to("K").magnitude
        p_si = p.to("Pa").magnitude
        self._check_T(T_si)
        self._check_composition(composition)
        h_si = self._props()("HMASS", "T", T_si, "P", p_si, self.coolprop_name)
        return Q(float(h_si), "J/kg")

    def s(  # noqa: N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> Quantity:
        """Specific entropy [J/(kg*K)] at (T, p)."""
        T_si = T.to("K").magnitude
        p_si = p.to("Pa").magnitude
        self._check_T(T_si)
        self._check_composition(composition)
        s_si = self._props()("SMASS", "T", T_si, "P", p_si, self.coolprop_name)
        return Q(float(s_si), "J/(kg*K)")

    def gamma(  # noqa: N803
        self,
        T: Quantity,
        p: Quantity,
        composition: Composition,
    ) -> float:
        """Specific heat ratio cp/cv at (T, p).

        Per ADAPT-006: previously evaluated at p = 101325 Pa regardless of
        actual operating pressure, giving the wrong ratio for sCO2 near
        critical (where cp diverges but cv stays finite).
        """
        T_si = T.to("K").magnitude
        p_si = p.to("Pa").magnitude
        self._check_T(T_si)
        self._check_composition(composition)
        try:
            cp_si = self._props()(
                "CPMASS", "T", T_si, "P", p_si, self.coolprop_name
            )
            cv_si = self._props()(
                "CVMASS", "T", T_si, "P", p_si, self.coolprop_name
            )
        except Exception as exc:  # noqa: BLE001
            from cascade.thermo.nasa_mixture import RegimeOutOfValidity
            msg = (
                f"CoolPropFluid.gamma({self.species.name}): PropsSI failed at "
                f"T={T_si} K, p={p_si} Pa — likely a state too close to the "
                f"critical point. CoolProp error: {exc}"
            )
            raise RegimeOutOfValidity(msg, code="COOLPROP_NEAR_CRITICAL") from exc
        cv_f = float(cv_si)
        cp_f = float(cp_si)
        if (
            not math.isfinite(cv_f)
            or not math.isfinite(cp_f)
            or cv_f <= 0.0
        ):
            from cascade.thermo.nasa_mixture import RegimeOutOfValidity
            msg = (
                f"CoolPropFluid.gamma({self.species.name}): non-physical "
                f"cp/cv (cp={cp_f}, cv={cv_f}) at T={T_si} K, p={p_si} Pa. "
                f"State is at or beyond the critical point."
            )
            raise RegimeOutOfValidity(msg, code="COOLPROP_NEAR_CRITICAL")
        return cp_f / cv_f

    def R_specific(self, composition: Composition) -> Quantity:  # noqa: N802
        """Specific gas constant R = R_univ / M."""
        self._check_composition(composition)
        from cascade.thermo.nasa_coefficients import R_UNIVERSAL

        M_kg_per_mol = self.species.molar_mass_g_per_mol * 1e-3
        return Q(R_UNIVERSAL / M_kg_per_mol, "J/(kg*K)")


__all__ = ["CoolPropFluid"]
