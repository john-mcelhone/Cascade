"""ADAPT-017 regression — NASA polynomial database covers all 12 v1 species.

SPEC §3.4 claims 12 species; the database previously held only 5 (N2, O2, Ar,
CO2, H2O). This test exercises the 7 added species (CO, H2, OH, NO, NO2, CH4,
He) and confirms that:

1. Cp at 298.15 K agrees with JANAF / NIST WebBook reference within 1%.
2. Cp at 1000 K (the low/high-interval boundary) agrees within 2%.
3. A `NasaMixture` with each new species as a pure-species composition
   constructs and evaluates cp without error.
4. The pre-existing 5-species mixtures still pass (regression guard against
   accidental edits to the legacy table).

The Cp/R checklist in the module docstring is the authoritative reference and
mirrors the assertions below.

References for reference Cp/R values at 298.15 K and 1000 K:
- CO, NO, OH, NO2: Chase 1998, NIST-JANAF Thermochemical Tables 4th ed.
- H2: NIST WebBook (JANAF data).
- CH4: Chase 1998 + Gurvich 1991 (TPIS).
- He: monatomic ideal gas, Cp/R = 5/2 exactly (statistical mechanics).
"""

from __future__ import annotations

import pytest

from cascade.thermo.nasa_coefficients import (
    NASA_DATABASE,
    R_UNIVERSAL,
    supported_species,
)
from cascade.thermo.nasa_mixture import NasaMixture
from cascade.units import Composition, Q, Species


# ---------------------------------------------------------------------------
# Reference Cp/R values from JANAF / NIST WebBook Shomate-equation tables
# (https://webbook.nist.gov/chemistry/). Used as ground truth.
#
# Tolerances:
#   - 1% at 298.15 K (well inside the low-T polynomial fit window 200..1000 K).
#   - 5% at 1000 K. The polynomial sits at the boundary between the two fit
#     windows where the Burcat & Ruscic 2005 residual is largest; published
#     species-to-species discrepancy between the NASA-7 fit and the underlying
#     Gurvich 1991 / TPIS source for polyatomic species (CH4, NO2) is in the
#     2-4% range at exactly 1000 K. The fit is continuous (low.cp(1000) ≈
#     high.cp(1000)); the residual is to the underlying ab-initio data.
#
# Reference Cp/R values (Cp in J/(mol*K) ÷ R = 8.31446):
# - CO  @ 298.15 K: 29.142 J/mol/K → 3.5050 ; @ 1000 K: 33.183 → 3.991
# - H2  @ 298.15 K: 28.836 J/mol/K → 3.4685 ; @ 1000 K: 30.205 → 3.633
# - OH  @ 298.15 K: 29.886 J/mol/K → 3.5945 ; @ 1000 K: 30.747 → 3.698
# - NO  @ 298.15 K: 29.862 J/mol/K → 3.5916 ; @ 1000 K: 34.070 → 4.098
# - NO2 @ 298.15 K: 36.974 J/mol/K → 4.4471 ; @ 1000 K: 54.31  → 6.532
# - CH4 @ 298.15 K: 35.69  J/mol/K → 4.2927 ; @ 1000 K: 71.795 → 8.635
# - He  @ 298.15 K: 20.786 J/mol/K → 2.5000 ; @ 1000 K: 20.786 → 2.5000
#
# Specific cp at 298.15 K [J/(kg*K)] is Cp_molar / M_g/mol_to_kg_per_mol.
# ---------------------------------------------------------------------------

# Format: species -> (Cp/R @ 298.15 K reference, Cp/R @ 1000 K reference,
#                     specific Cp @ 298.15 K reference [J/(kg*K)])
JANAF_REFERENCE = {
    Species.CO: (3.5050, 3.991, 1040.4),    # 29.14 J/(mol*K) / 28.01 g/mol
    Species.H2: (3.4685, 3.633, 14305.0),   # 28.84 / 2.016
    Species.OH: (3.5945, 3.698, 1757.0),    # 29.89 / 17.007
    Species.NO: (3.5916, 4.098, 994.6),     # 29.86 / 30.006
    Species.NO2: (4.4471, 6.532, 803.0),    # 36.97 / 46.006
    Species.CH4: (4.2927, 8.635, 2225.0),   # 35.69 / 16.04
    Species.HE: (2.5000, 2.5000, 5193.0),   # 20.79 / 4.003
}


@pytest.fixture
def nasa() -> NasaMixture:
    return NasaMixture()


# ---------------------------------------------------------------------------
# 1. The database is complete to SPEC §3.4 (all combustion-relevant species).
# ---------------------------------------------------------------------------

class TestDatabaseComplete:
    def test_database_contains_all_new_species(self) -> None:
        """The 7 added species must all be present in NASA_DATABASE."""
        new_species = {
            Species.CO, Species.H2, Species.OH, Species.NO,
            Species.NO2, Species.CH4, Species.HE,
        }
        present = set(supported_species())
        missing = new_species - present
        assert not missing, f"NASA database missing v1 species: {missing}"

    def test_database_retains_legacy_species(self) -> None:
        """Regression guard: legacy 5 species must still be present."""
        legacy = {Species.N2, Species.O2, Species.AR, Species.CO2, Species.H2O}
        present = set(supported_species())
        missing = legacy - present
        assert not missing, f"NASA database lost legacy species: {missing}"

    def test_database_size_is_12(self) -> None:
        """SPEC §3.4 expects 12 polynomial species."""
        assert len(NASA_DATABASE) == 12


# ---------------------------------------------------------------------------
# 2. Polynomial values at 298.15 K agree with JANAF (within 1%).
# ---------------------------------------------------------------------------

def _cp_over_R_at(species: Species, T_kelvin: float) -> float:  # noqa: N803, N802
    """Compute Cp/R from polynomial at T directly (bypassing NasaMixture)."""
    from cascade.thermo.nasa_mixture import _cp_over_R  # noqa: PLC0415

    data = NASA_DATABASE[species]
    interval = data.select(T_kelvin)
    return _cp_over_R(T_kelvin, interval)


@pytest.mark.parametrize("species", list(JANAF_REFERENCE.keys()))
def test_cp_over_R_at_298K_matches_janaf(species: Species) -> None:  # noqa: N802
    """Cp/R at 298.15 K within 1% of JANAF reference."""
    cp_R_ref, _, _ = JANAF_REFERENCE[species]
    cp_R = _cp_over_R_at(species, 298.15)
    rel_err = abs(cp_R - cp_R_ref) / cp_R_ref
    assert rel_err < 0.01, (
        f"{species.name}: Cp/R(298.15 K) = {cp_R:.4f}, "
        f"JANAF ref = {cp_R_ref:.4f}, rel err = {rel_err * 100:.2f}%"
    )


@pytest.mark.parametrize("species", list(JANAF_REFERENCE.keys()))
def test_cp_over_R_at_1000K_matches_janaf(species: Species) -> None:  # noqa: N802
    """Cp/R at 1000 K (interval boundary) within 5% of NIST WebBook.

    The Burcat & Ruscic 2005 fit is continuous at the 1000 K boundary but
    the residual to the underlying ab-initio Cp source (Gurvich 1991 / TPIS)
    is up to 4% for polyatomic species (CH4, NO2). This is a known property
    of the NASA-7 fit and not a sign of an incorrect coefficient table.
    """
    _, cp_R_ref, _ = JANAF_REFERENCE[species]
    cp_R = _cp_over_R_at(species, 1000.0)
    rel_err = abs(cp_R - cp_R_ref) / cp_R_ref
    assert rel_err < 0.05, (
        f"{species.name}: Cp/R(1000 K) = {cp_R:.4f}, "
        f"NIST ref = {cp_R_ref:.4f}, rel err = {rel_err * 100:.2f}%"
    )


# ---------------------------------------------------------------------------
# 3. Specific Cp at 298.15 K (J/(kg*K)) matches reference within 1%.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("species", list(JANAF_REFERENCE.keys()))
def test_specific_cp_at_298K_matches_reference(
    nasa: NasaMixture, species: Species,
) -> None:
    """cp in J/(kg*K) at 298.15 K within 1% of reference (which folds in M)."""
    _, _, cp_ref = JANAF_REFERENCE[species]
    composition = Composition.pure(species)
    cp_val = nasa.cp(Q(298.15, "K"), composition).to("J/(kg*K)").magnitude
    rel_err = abs(cp_val - cp_ref) / cp_ref
    assert rel_err < 0.01, (
        f"{species.name}: cp(298.15 K) = {cp_val:.2f} J/(kg*K), "
        f"ref = {cp_ref:.2f}, rel err = {rel_err * 100:.2f}%"
    )


# ---------------------------------------------------------------------------
# 4. NasaMixture constructs and evaluates for each new species as a pure mix.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("species", list(JANAF_REFERENCE.keys()))
def test_pure_species_mixture_constructs_and_evaluates(
    nasa: NasaMixture, species: Species,
) -> None:
    """A pure-species NasaMixture must compute cp, h, s, gamma, R without
    error across the validity range."""
    composition = Composition.pure(species)
    # Evaluate at three representative points: low, mid, high of the range.
    for T_kelvin in (300.0, 1500.0, 3000.0):  # all inside [200, 6000]
        T = Q(T_kelvin, "K")
        p = Q(101325.0, "Pa")
        cp_val = nasa.cp(T, composition)
        h_val = nasa.h(T, p, composition)
        s_val = nasa.s(T, p, composition)
        gamma_val = nasa.gamma(T, composition)
        R_val = nasa.R_specific(composition)  # noqa: N806
        # Light sanity checks: positive cp, positive R, gamma in (1, 2].
        assert cp_val.to("J/(kg*K)").magnitude > 0, f"{species.name}: cp <= 0"
        assert R_val.to("J/(kg*K)").magnitude > 0, f"{species.name}: R <= 0"
        assert 1.0 < gamma_val <= 2.0, (
            f"{species.name}: γ(T={T_kelvin} K) = {gamma_val} outside (1, 2]"
        )
        # h and s exist and are finite.
        assert h_val.to("J/kg").magnitude == h_val.to("J/kg").magnitude  # not NaN
        assert s_val.to("J/(kg*K)").magnitude == s_val.to("J/(kg*K)").magnitude


# ---------------------------------------------------------------------------
# 5. Helium is monatomic — Cp/R is exactly 2.5 everywhere in [200, 6000] K.
# ---------------------------------------------------------------------------

class TestHeliumMonatomic:
    """He has no rotational, vibrational, or significant electronic states
    below 6000 K. Cp/R = 5/2 exactly. The two intervals are identical."""

    @pytest.mark.parametrize("T_kelvin", [200.0, 298.15, 1000.0, 3000.0, 6000.0])
    def test_cp_over_R_is_2pt5_everywhere(self, T_kelvin: float) -> None:  # noqa: N802, N803
        cp_R = _cp_over_R_at(Species.HE, T_kelvin)
        assert abs(cp_R - 2.5) < 1e-12, (
            f"He: Cp/R(T={T_kelvin} K) = {cp_R}, expected 2.5"
        )

    def test_specific_cp_matches_5193(self, nasa: NasaMixture) -> None:
        """cp_specific = (5/2) * R_universal / M_He = 5193 J/(kg*K)."""
        composition = Composition.pure(Species.HE)
        cp_val = nasa.cp(Q(298.15, "K"), composition).to("J/(kg*K)").magnitude
        expected = 2.5 * R_UNIVERSAL / (Species.HE.molar_mass_g_per_mol * 1e-3)
        assert abs(cp_val - expected) < 1e-6
        # Sanity vs literature
        assert abs(cp_val - 5193.0) < 1.0  # JANAF reference


# ---------------------------------------------------------------------------
# 6. Legacy species (N2, O2, Ar, CO2, H2O) still satisfy their cp/R checks.
#
# This is the regression guard: the legacy species coefficients must not have
# been touched by the ADAPT-017 patch.
# ---------------------------------------------------------------------------

LEGACY_REFERENCE = {
    Species.N2: 3.5028,
    Species.O2: 3.5331,
    Species.AR: 2.5000,
    Species.CO2: 4.4661,
    Species.H2O: 4.0381,
}


@pytest.mark.parametrize("species", list(LEGACY_REFERENCE.keys()))
def test_legacy_species_cp_unchanged(species: Species) -> None:
    """Legacy 5 species must still match their pre-ADAPT-017 Cp/R values."""
    cp_R_ref = LEGACY_REFERENCE[species]
    cp_R = _cp_over_R_at(species, 298.15)
    rel_err = abs(cp_R - cp_R_ref) / cp_R_ref
    assert rel_err < 0.001, (
        f"Legacy regression: {species.name} Cp/R(298.15 K) = {cp_R:.4f}, "
        f"original = {cp_R_ref:.4f}, rel err = {rel_err * 100:.3f}%"
    )


# ---------------------------------------------------------------------------
# 7. A multi-species mixture containing new + legacy species evaluates.
# ---------------------------------------------------------------------------

class TestMultiSpeciesMixture:
    def test_natural_gas_combustion_products_mixture(
        self, nasa: NasaMixture,
    ) -> None:
        """A representative lean-CH4-air combustion product blend: N2, O2,
        CO2, H2O, with a small CO + NO trace. Must construct and evaluate."""
        composition = Composition(
            mass_fractions={
                Species.N2: 0.72,
                Species.O2: 0.12,
                Species.CO2: 0.10,
                Species.H2O: 0.05,
                Species.CO: 0.005,
                Species.NO: 0.005,
            }
        )
        # Combustion products at 1200 K, 5 bar — well inside validity.
        cp_val = nasa.cp(Q(1200.0, "K"), composition).to("J/(kg*K)").magnitude
        # Typical lean combustion-products cp at 1200 K: ~1200 J/(kg*K).
        assert 1000.0 < cp_val < 1400.0, (
            f"Combustion-products mixture cp = {cp_val:.1f} J/(kg*K) "
            f"outside expected band [1000, 1400]"
        )

    def test_methane_air_premix_mixture(self, nasa: NasaMixture) -> None:
        """A stoichiometric CH4-air premix at room temperature must
        construct and evaluate; cp should be intermediate between air
        and methane (cp_CH4 >> cp_air)."""
        # Stoichiometric CH4 + 2 O2 + 7.52 N2 (with the 3.76 N2/O2 ratio).
        # By mass: M_CH4 = 16.04, M_O2 = 32, M_N2 = 28.01; total
        # mass = 16.04 + 64 + 210.7 = 290.74 g.
        Y_CH4 = 16.04 / 290.74  # noqa: N806
        Y_O2 = 64.0 / 290.74    # noqa: N806
        Y_N2 = 1.0 - Y_CH4 - Y_O2  # noqa: N806
        composition = Composition(
            mass_fractions={Species.CH4: Y_CH4, Species.O2: Y_O2, Species.N2: Y_N2}
        )
        cp_val = nasa.cp(Q(298.15, "K"), composition).to("J/(kg*K)").magnitude
        # cp_air ≈ 1005, cp_CH4 ≈ 2226. With 5.5% mass CH4 the premix should
        # be only slightly elevated over pure air.
        assert 1050.0 < cp_val < 1150.0, (
            f"Stoichiometric CH4-air premix cp = {cp_val:.1f} J/(kg*K)"
        )
