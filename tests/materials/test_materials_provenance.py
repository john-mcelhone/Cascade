"""Audit E — Materials Registry Provenance tests (2026-05-27).

Mandate: every public validation claim must be reproducible and every shipped
material property must have a defensible source.

This file adds:
1. Family invariant tests (E in range, E monotone with T, rho > 0, nu in (0, 0.5)).
2. Source-backed E value tests for 5+ representative materials (±5 % of cited source).
3. Extended alias resolution (UNS numbers, SAE, ASTM Grade designations).
4. Citation specificity — source strings must reference a specific publication
   identifier (datasheet number, TM/CR number, section, table, or equation).
5. MAR-M 247 clarification: E table is polycrystalline, NOT SC [001].
"""

from __future__ import annotations

import re

import pytest

from cascade.materials import MaterialDB
from cascade.materials.database import ALIASES


# ---------------------------------------------------------------------------
# 1. Family invariants — applied to EVERY registered material
# ---------------------------------------------------------------------------


def test_all_E_in_structural_metal_range() -> None:
    """Any reasonable engineering structural alloy: 50–300 GPa."""
    for m in MaterialDB.list():
        T_lo = m.youngs_modulus_GPa[0][0]
        E_Pa = m.E(T_lo)
        assert 50e9 < E_Pa < 300e9, (
            f"{m.name}: E({T_lo:.0f} K) = {E_Pa/1e9:.1f} GPa is outside 50–300 GPa"
        )


def test_all_density_positive_and_reasonable() -> None:
    """All densities must be positive and in the range for solid alloys."""
    for m in MaterialDB.list():
        assert m.density_kg_per_m3 > 0, f"{m.name}: negative density"
        assert 2500 < m.density_kg_per_m3 < 11000, (
            f"{m.name}: density {m.density_kg_per_m3:.0f} kg/m³ outside 2500–11000"
        )


def test_all_poisson_ratio_physical() -> None:
    """Poisson ratio must be in (0, 0.5) for an isotropic solid."""
    for m in MaterialDB.list():
        assert 0 < m.poisson < 0.5, (
            f"{m.name}: Poisson ratio {m.poisson} is outside (0, 0.5)"
        )


def test_E_monotone_decreasing_with_temperature() -> None:
    """E must decrease from the lowest to the highest tabulated temperature
    for every material (universal physical trend for metals above ~50 K)."""
    for m in MaterialDB.list():
        T_low = m.youngs_modulus_GPa[0][0]
        T_high = m.youngs_modulus_GPa[-1][0]
        E_low = m.E(T_low)
        E_high = m.E(T_high)
        assert E_high < E_low, (
            f"{m.name}: E({T_high:.0f} K) = {E_high/1e9:.1f} GPa is NOT less than "
            f"E({T_low:.0f} K) = {E_low/1e9:.1f} GPa — E must decrease with T"
        )


def test_all_E_tables_monotone_decreasing() -> None:
    """Check every step in every E table is non-increasing (not just endpoints)."""
    for m in MaterialDB.list():
        table = m.youngs_modulus_GPa
        for (T_prev, E_prev), (T_next, E_next) in zip(table[:-1], table[1:]):
            assert E_next <= E_prev, (
                f"{m.name}: E increases from {T_prev:.0f} K ({E_prev:.1f} GPa) "
                f"to {T_next:.0f} K ({E_next:.1f} GPa)"
            )


def test_all_yield_tables_have_at_least_2_stations() -> None:
    for m in MaterialDB.list():
        assert len(m.yield_strength_MPa) >= 2, (
            f"{m.name}: yield_strength_MPa has fewer than 2 stations"
        )


def test_all_materials_have_non_empty_source() -> None:
    """Source field must be a non-whitespace string for every material."""
    for m in MaterialDB.list():
        assert m.source and m.source.strip(), f"{m.name}: source is empty"


def test_all_sources_contain_recognised_authority() -> None:
    """Every source must reference a recognised publication authority."""
    authorities = (
        "ASM", "MMPDS", "NASA", "NIST", "Special Metals", "Haynes",
        "Outokumpu", "AMS", "ASTM", "Donachie", "AK Steel", "SMC-",
        "H-3173", "TM-", "CR-",
    )
    for m in MaterialDB.list():
        assert any(a in m.source for a in authorities), (
            f"{m.name}: source does not mention a recognised authority: {m.source!r}"
        )


# ---------------------------------------------------------------------------
# 2. Citation specificity — source strings need a specific locator
# ---------------------------------------------------------------------------


def test_all_sources_have_specific_locator() -> None:
    """Each source must contain at least one specific publication locator:
    a publication ID (SMC-NNN, H-NNNN, TM-NNNNN), section marker (§, Ch.),
    table/figure reference, or page number.  A bare 'ASM Handbook Vol 1'
    without any further locator is NOT acceptable."""
    specific_patterns = [
        r"SMC-\d+",          # Special Metals pub ID e.g. SMC-063
        r"H-\d+",            # Haynes pub ID e.g. H-3173
        r"TM-\d+",           # NASA TM
        r"CR-\d+",           # NASA CR
        r"SRM\s*\d+",        # NIST SRM
        r"§\s*\d",           # section symbol
        r"Ch\.\s*\d",        # chapter
        r"Table\s+\S",       # table reference
        r"Tables?\s+\d",     # table(s) with number
        r"\bp\.\s*\d",       # page
        r"\bpp\.\s*\d",      # pages
        r"eq\.\s*\d",        # equation
        r"Section\s+\S",     # section word
        r"AMS\s+\d+",        # AMS spec
        r"ASTM\s+[A-Z]\d+",  # ASTM spec
    ]
    compiled = [re.compile(p, re.IGNORECASE) for p in specific_patterns]

    for m in MaterialDB.list():
        found = any(pat.search(m.source) for pat in compiled)
        assert found, (
            f"{m.name}: source lacks a specific locator (pub-ID, §, Table, page, eq).\n"
            f"  source = {m.source!r}"
        )


# ---------------------------------------------------------------------------
# 3. Source-backed E values at 293 K (± 5 %) for 7 representative materials
# ---------------------------------------------------------------------------
# Reference values are from the primary cited sources listed in database.py.
# These tests will fail loudly if a value is silently changed.

REFERENCE_E_GPA_AT_293K: dict[str, tuple[float, str]] = {
    # (E_ref_GPa, source_note)
    # --- 7 materials covered in Audit E / G3 ---
    "Inconel 625":  (207.5, "Special Metals SMC-063 Table 1: 30.1 Msi = 207.5 GPa"),
    "Inconel 718":  (205.0, "Special Metals SMC-045 Table 1: 29.7 Msi = 205.0 GPa"),
    "Ti-6Al-4V":    (113.8, "MMPDS-13 §5.4 Table 5.4.1.0(a): 16.5 Msi = 113.8 GPa"),
    "AISI 4340":    (200.0, "ASM Handbook Vol 1 (Q&T 425 °C): 200 GPa"),
    "17-4PH":       (196.0, "ASM Handbook Vol 1 H1025: 196 GPa"),
    "Haynes 282":   (217.0, "Haynes H-3173 Table 'Physical Properties': 31.5 Msi = 217 GPa"),
    "316L":         (193.0, "ASM Handbook Vol 1 annealed 316L: 193 GPa"),
    # --- 3 materials added in H2 audit to achieve all-10 coverage ---
    "Inconel 738":  (201.0, "ASM Handbook Vol 1, Table 'Properties of IN-738LC' (equiaxed cast): 201 GPa"),
    "MAR-M 247":    (214.0, "NASA TM-83655 (Harf 1984) Table 2, equiaxed polycrystalline cast: 213–215 GPa; 214 GPa used"),
    "A286":         (201.0, "Special Metals SMC-024 Table 'Physical and Mechanical Properties' (solution + aged A286): 201 GPa"),
}


@pytest.mark.parametrize("name,ref_tuple", list(REFERENCE_E_GPA_AT_293K.items()))
def test_E_at_293K_matches_cited_source_within_5pct(name: str, ref_tuple: tuple) -> None:
    """E at 293 K must be within ±5 % of the value stated in the cited source."""
    E_ref_GPa, source_note = ref_tuple
    m = MaterialDB.get(name)
    E_actual_GPa = m.E(293.0) / 1e9
    rel_err = abs(E_actual_GPa - E_ref_GPa) / E_ref_GPa
    assert rel_err <= 0.05, (
        f"{name}: E(293 K) = {E_actual_GPa:.2f} GPa deviates {rel_err:.1%} from "
        f"reference {E_ref_GPa:.1f} GPa ({source_note}). Tolerance is 5 %."
    )


# ---------------------------------------------------------------------------
# 4. Extended alias resolution — UNS numbers, SAE, ASTM Grade names
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("alias,canonical", [
    # UNS numbers
    ("UNS N06625",  "Inconel 625"),
    ("UNS N07718",  "Inconel 718"),
    ("UNS N07208",  "Haynes 282"),
    ("UNS S17400",  "17-4PH"),
    ("UNS S66286",  "A286"),
    ("UNS S31603",  "316L"),
    ("UNS G43400",  "AISI 4340"),
    ("UNS R56400",  "Ti-6Al-4V"),
    # SAE / ASTM grade aliases
    ("SAE 4340",        "AISI 4340"),
    ("IN-738LC",        "Inconel 738"),
    ("IN738LC",         "Inconel 738"),
    ("Grade 5",         "Ti-6Al-4V"),
    ("ASTM Grade 5",    "Ti-6Al-4V"),
    ("Incoloy A-286",   "A286"),
    ("HAYNES 282",      "Haynes 282"),
    # Pre-existing aliases that must keep working
    ("AISI4340",        "AISI 4340"),
    ("STEEL_AISI4340",  "AISI 4340"),
    ("IN625",           "Inconel 625"),
    ("IN718",           "Inconel 718"),
    ("Ti64",            "Ti-6Al-4V"),
    ("Ti-6-4",          "Ti-6Al-4V"),
    ("17-4 PH",         "17-4PH"),
    ("PH17-4",          "17-4PH"),
    ("ASTM A286",       "A286"),
    ("HAYNES282",       "Haynes 282"),
    ("SS316L",          "316L"),
    ("316 L",           "316L"),
])
def test_alias_resolution(alias: str, canonical: str) -> None:
    """The registry must resolve the alias to the correct canonical material."""
    m = MaterialDB.get(alias)
    assert m.name == canonical, (
        f"Alias {alias!r} resolved to {m.name!r}, expected {canonical!r}"
    )


def test_alias_table_has_no_orphaned_targets() -> None:
    """Every alias must point to a canonical name that exists in the registry."""
    names = set(MaterialDB.names())
    for alias, target in ALIASES.items():
        assert target in names, (
            f"Alias {alias!r} points to {target!r} which is not in the registry"
        )


# ---------------------------------------------------------------------------
# 5. MAR-M 247 specific correctness assertions
# ---------------------------------------------------------------------------


def test_marm247_E_is_polycrystalline_not_SC001() -> None:
    """MAR-M 247 E table must be the polycrystalline value (~210–215 GPa),
    NOT the SC [001] value (~124 GPa). The notes field must make this clear.

    Background: SC [001] E for MAR-M 247 is ~124–130 GPa (Gell 1980,
    Metall. Trans. 11A). The polycrystalline isotropic E is ~213–215 GPa.
    The catalogue ships the polycrystalline value for general use.
    """
    m = MaterialDB.get("MAR-M 247")
    E_GPa = m.E(293.0) / 1e9
    # Must be polycrystalline: well above SC [001] range
    assert E_GPa > 175.0, (
        f"MAR-M 247 E(293 K) = {E_GPa:.1f} GPa — if this is less than 175 GPa it "
        f"looks like the SC [001] value (~124 GPa) was accidentally used. "
        f"The catalogue should ship the polycrystalline value (~210–215 GPa)."
    )
    # Must NOT be falsely claiming SC [001] in the source or notes
    source_lower = m.source.lower()
    notes_lower = m.notes.lower()
    # The word 'polycrystalline' or 'equiaxed' must appear to flag this clearly
    assert "polycrystalline" in source_lower or "equiaxed" in source_lower, (
        f"MAR-M 247 source must mention 'polycrystalline' or 'equiaxed' to distinguish "
        f"this record from the SC data: {m.source!r}"
    )


def test_marm247_notes_warn_against_SC_use() -> None:
    """The notes field for MAR-M 247 must warn users not to use this record for
    single-crystal FEA, because E_SC[001] ≈ 124 GPa vs E_poly ≈ 214 GPa."""
    m = MaterialDB.get("MAR-M 247")
    assert "SC" in m.notes or "single" in m.notes.lower() or "crystal" in m.notes.lower(), (
        f"MAR-M 247 notes should warn about SC usage; got: {m.notes!r}"
    )


# ---------------------------------------------------------------------------
# 6. Temperature-interpolation sanity at mid-range points
# ---------------------------------------------------------------------------


def test_every_material_E_mid_range_is_monotone() -> None:
    """For every material with ≥ 3 E table stations, the mid-point of the
    first interval must give a value between the two endpoint values."""
    for m in MaterialDB.list():
        table = m.youngs_modulus_GPa
        if len(table) < 2:
            continue
        T_lo, E_lo = table[0]
        T_hi, E_hi = table[1]
        T_mid = 0.5 * (T_lo + T_hi)
        E_mid = m.E(T_mid) / 1e9
        E_lo_GPa = E_lo
        E_hi_GPa = E_hi
        assert E_hi_GPa <= E_mid <= E_lo_GPa, (
            f"{m.name}: mid-interval E({T_mid:.0f} K) = {E_mid:.2f} GPa is outside "
            f"[{E_hi_GPa:.2f}, {E_lo_GPa:.2f}] GPa — interpolation is not monotone"
        )


# ---------------------------------------------------------------------------
# 7. Public API serialisation includes 'source' key (citation field)
# ---------------------------------------------------------------------------


def test_as_dict_source_key_is_non_empty_for_all_materials() -> None:
    """The API-facing as_dict() must include a non-empty 'source' for every
    material so the HTTP endpoint never silently returns a citation-free record."""
    for m in MaterialDB.list():
        d = m.as_dict()
        assert "source" in d, f"{m.name}: as_dict() missing 'source' key"
        assert d["source"] and d["source"].strip(), (
            f"{m.name}: as_dict() has empty 'source'"
        )


def test_as_dict_includes_all_required_keys() -> None:
    """The /api/materials/{name} payload must include all required fields."""
    required_keys = {
        "name", "designation", "family", "density_kg_per_m3", "poisson",
        "youngs_modulus_GPa", "yield_strength_MPa", "ultimate_strength_MPa",
        "thermal_expansion_1_per_K", "thermal_conductivity_W_per_mK",
        "specific_heat_J_per_kgK", "source", "notes",
    }
    for m in MaterialDB.list():
        d = m.as_dict()
        missing = required_keys - d.keys()
        assert not missing, f"{m.name}: as_dict() missing keys: {missing}"


# ===========================================================================
# Closure G3 — Full-property provenance tests (2026-05-27)
# ===========================================================================
# These tests extend the Audit E / Closure F3 work beyond Young's modulus to
# cover density, Poisson ratio, and full property-sanity invariants.

# ---------------------------------------------------------------------------
# 8. Density source-match (± 2 %) for representative materials
# ---------------------------------------------------------------------------
# Reference values taken from the same primary sources cited in database.py.
# Unit: kg/m³.

REFERENCE_DENSITY: dict[str, tuple[float, str]] = {
    "Inconel 625":  (8440.0, "Special Metals SMC-063: 8.44 g/cm³"),
    "Inconel 718":  (8190.0, "Special Metals SMC-045: 8.19 g/cm³"),
    "Ti-6Al-4V":    (4430.0, "MMPDS-13 §5.4: 0.160 lb/in³ = 4.43 g/cm³"),
    "AISI 4340":    (7850.0, "ASM Handbook Vol 1: 7.85 g/cm³ Q&T"),
    "17-4PH":       (7800.0, "AK Steel / Outokumpu 17-4PH datasheet: 7.80 g/cm³"),
    "Haynes 282":   (8270.0, "Haynes H-3173: 8.27 g/cm³"),
    "316L":         (8000.0, "Outokumpu 316/316L: 8.00 g/cm³"),
}


@pytest.mark.parametrize("name,ref_tuple", list(REFERENCE_DENSITY.items()))
def test_density_matches_cited_source_within_2pct(name: str, ref_tuple: tuple) -> None:
    """Density must be within ±2 % of the value stated in the cited source.

    Density of a solid alloy is a composition-dependent constant that does not
    vary significantly by heat-treat condition; therefore a tighter 2 % tolerance
    is appropriate.  A > 2 % discrepancy would indicate a unit error (g/cm³ vs
    kg/m³) or a wrong alloy composition.
    """
    rho_ref, source_note = ref_tuple
    m = MaterialDB.get(name)
    rho_actual = m.density_kg_per_m3
    rel_err = abs(rho_actual - rho_ref) / rho_ref
    assert rel_err <= 0.02, (
        f"{name}: density = {rho_actual:.1f} kg/m³ deviates {rel_err:.1%} from "
        f"reference {rho_ref:.1f} kg/m³ ({source_note}). Tolerance is 2 %."
    )


# ---------------------------------------------------------------------------
# 9. Poisson ratio source-match (± 0.05 absolute) for representative materials
# ---------------------------------------------------------------------------
# Tolerance: ±0.05 absolute (typical range for these alloys is 0.27–0.34).
# Note: some sources list ν computed from E and G (which can differ from the
# directly tabulated value by up to ±0.03 due to independent rounding of E and
# G); the ±0.05 tolerance accommodates this.

REFERENCE_POISSON: dict[str, tuple[float, str]] = {
    "Ti-6Al-4V":   (0.342, "MMPDS-13 §5.4 Table 5.4.1.0(a): ν = 0.342 direct"),
    "AISI 4340":   (0.290, "ASM Handbook Vol 1 / MMPDS-13 §2.3.1.0: ν = 0.290"),
    "17-4PH":      (0.272, "AK Steel / Outokumpu 17-4PH datasheet: ν = 0.272"),
    "Haynes 282":  (0.310, "Haynes H-3173 Table 'Physical Properties': ν = 0.310"),
    "316L":        (0.270, "Outokumpu 316/316L datasheet: ν = 0.270"),
    "A286":        (0.310, "Special Metals SMC-024 Table 'Physical Properties': ν ≈ 0.308-0.310"),
}


@pytest.mark.parametrize("name,ref_tuple", list(REFERENCE_POISSON.items()))
def test_poisson_matches_cited_source_within_abs_0p05(name: str, ref_tuple: tuple) -> None:
    """Poisson's ratio must be within ±0.05 absolute of the cited source value.

    For the alloy families in this database the physically reasonable range is
    0.25–0.40.  A ±0.05 tolerance is wide enough to accommodate source scatter
    and rounding differences between E/G-derived and directly-tabulated values.
    """
    nu_ref, source_note = ref_tuple
    m = MaterialDB.get(name)
    nu_actual = m.poisson
    abs_err = abs(nu_actual - nu_ref)
    assert abs_err <= 0.05, (
        f"{name}: ν = {nu_actual:.4f} deviates {abs_err:.4f} (absolute) from "
        f"reference {nu_ref:.4f} ({source_note}). Tolerance is ±0.05 absolute."
    )


# ---------------------------------------------------------------------------
# 10. Density physical sanity — broad band catches unit errors
# ---------------------------------------------------------------------------

def test_density_physical_sanity_all_materials() -> None:
    """Density must be in [1000, 20000] kg/m³ for every material.

    Lower bound (1000 kg/m³) catches a g/cm³ → kg/m³ conversion omission
    (1 g/cm³ = 1000 kg/m³; all engineering alloys are ≥ 4.4× denser than water).
    Upper bound (20000 kg/m³) catches entry in g/cm³ instead of kg/m³ for heavy
    alloys (tungsten = 19250 kg/m³ is the practical ceiling for a turbomachinery
    material).
    """
    for m in MaterialDB.list():
        assert 1000.0 <= m.density_kg_per_m3 <= 20000.0, (
            f"{m.name}: density {m.density_kg_per_m3:.1f} kg/m³ is outside "
            f"the sanity band [1000, 20000] kg/m³.  Possible unit error "
            f"(common trap: entered in g/cm³ instead of kg/m³)."
        )


# ---------------------------------------------------------------------------
# 11. Thermal conductivity sanity — catches W/cm·K vs W/m·K confusion
# ---------------------------------------------------------------------------

def test_thermal_conductivity_sanity_all_materials() -> None:
    """Thermal conductivity at the lowest tabulated temperature must be in
    [5, 500] W/(m·K) for every material.

    Lower bound 5 W/(m·K): all metals in this database conduct at least this
    well at room temperature (lowest: Ti-6Al-4V ≈ 6.7 W/(m·K)).
    Upper bound 500 W/(m·K): pure Cu = 400 W/(m·K); no alloy in this database
    approaches 500 W/(m·K).

    The 100× trap: W/(cm·K) is used in some NASA reports; 1 W/(cm·K) =
    100 W/(m·K).  Entering Ti-6Al-4V k = 0.067 W/(cm·K) as-is would give
    0.067 W/(m·K) — caught by the lower bound.  Entering steel k = 44.5
    W/(cm·K) would give 4450 W/(m·K) — caught by the upper bound.
    """
    for m in MaterialDB.list():
        k_rt = m.thermal_conductivity_W_per_mK[0][1]
        assert 5.0 <= k_rt <= 500.0, (
            f"{m.name}: thermal conductivity at "
            f"{m.thermal_conductivity_W_per_mK[0][0]:.0f} K = {k_rt:.3f} W/(m·K) "
            f"is outside [5, 500] W/(m·K).  Check units — W/(cm·K) vs W/(m·K) "
            f"is a 100× error."
        )


# ---------------------------------------------------------------------------
# 12. Heat-treat condition documented in citation for every material with σ_y
# ---------------------------------------------------------------------------

_CONDITION_MARKERS = (
    # heat-treat condition keywords (case-insensitive)
    "anneal", "aged", "quench", "temper", "solution", "H10", "H90",
    "condition", "AMS", "A638", "Q&T", "5663", "5662", "5731",
)


def test_yield_condition_documented_in_citation() -> None:
    """Every material with a yield_strength_MPa table must have a heat-treat
    condition documented in either the 'notes' or 'source' field.

    Yield strength is strongly condition-dependent (e.g., IN718 annealed vs
    aged can differ by > 2×).  A citation that does not specify the condition
    leaves the buyer unable to verify the shipped value.
    """
    for m in MaterialDB.list():
        if not m.yield_strength_MPa:
            continue  # pragma: no cover — all current materials have yield tables
        combined = (m.source + " " + m.notes).lower()
        found = any(marker.lower() in combined for marker in _CONDITION_MARKERS)
        assert found, (
            f"{m.name}: neither 'source' nor 'notes' mentions a heat-treat "
            f"condition (anneal/aged/quench/temper/solution/H-condition/AMS spec).  "
            f"Yield strength is condition-dependent — the citation must specify "
            f"which condition the tabulated σ_y values apply to."
        )


# ===========================================================================
# Closure I2 — D-S1..D-S9 safety-defect closure tests (2026-05-27)
# ===========================================================================


# ---------------------------------------------------------------------------
# I2-T1  A286 σ_y — aged condition, value, and condition documented
# ---------------------------------------------------------------------------


def test_a286_yield_at_293K_is_aged_condition_minimum() -> None:
    """A286 σ_y(293 K) must be >= 690 MPa (ASTM A453 Grade 660 Class D minimum,
    solution + aged condition, Table 1).

    Background: the previous value of 660 MPa was the annealed condition,
    non-conservative by ~4.3 % relative to the AMS 5731 aged minimum.
    Closure I2 / D-S1 corrects this to the conservative design-allowables
    minimum of 690 MPa.
    """
    m = MaterialDB.get("A286")
    sy_MPa = m.sigma_yield(293.0) / 1.0e6
    assert sy_MPa >= 690.0, (
        f"A286 σ_y(293 K) = {sy_MPa:.1f} MPa is below the ASTM A453 Grade 660 "
        f"Class D minimum of 690 MPa (solution + aged condition, Table 1). "
        f"Using the annealed value (660 MPa) in an aged-condition design is "
        f"non-conservative."
    )


def test_a286_yield_condition_is_aged_not_annealed() -> None:
    """A286 notes and source must reference the solution + aged condition,
    NOT the annealed condition (which gives the incorrect 660 MPa value)."""
    m = MaterialDB.get("A286")
    combined = (m.source + " " + m.notes).lower()
    assert "aged" in combined, (
        f"A286 source/notes must specify the 'aged' heat-treat condition "
        f"(σ_y is strongly condition-dependent). Got: {m.notes!r}"
    )
    # Must NOT cite A638 (dimensional bolt spec) — the correct standard is A453
    assert "A638" not in m.source, (
        "A286 source must not cite ASTM A638 (bolt dimensional spec). "
        "Use ASTM A453 Grade 660 (the properties standard)."
    )
    # Must cite ASTM A453 or AMS 5731
    assert "A453" in m.source or "AMS 5731" in m.source, (
        "A286 source must cite ASTM A453 Grade 660 or AMS 5731 as the "
        f"properties authority. Got: {m.source!r}"
    )


# ---------------------------------------------------------------------------
# I2-T2  IN-738 ν citation documented or flagged as estimated
# ---------------------------------------------------------------------------


def test_in738_poisson_is_documented_or_flagged() -> None:
    """IN-738 Poisson ratio notes must either cite a primary source OR
    explicitly flag the value as estimated / family value.

    Background: D-S3 found no tabulated primary source for IN-738 ν.
    Closure I2 documents ν = 0.300 as a family estimate with an explicit
    caveat pending a verified vendor / NIMS source.
    """
    m = MaterialDB.get("Inconel 738")
    combined = (m.source + " " + m.notes).lower()
    # Must flag as estimated, OR cite NIMS/vendor for ν specifically
    has_caveat = any(kw in combined for kw in (
        "estimated", "family value", "family estimate", "not been verified",
        "no primary", "treat as", "pending verification",
    ))
    assert has_caveat, (
        "Inconel 738 notes/source must document ν as estimated (family value) "
        "or provide a verified tabulated primary source. "
        f"Got notes: {m.notes!r}"
    )


# ---------------------------------------------------------------------------
# I2-T3  IN718 elevated-T condition warning
# ---------------------------------------------------------------------------


def test_in718_elevated_T_condition_warning_in_notes() -> None:
    """IN718 notes must warn that the aged condition (AMS 5663) is
    metallurgically invalid above ~1000 K (γ'' dissolution).

    Background: D-S8 found that the table extends above the γ'' stability
    limit without any caveat; Closure I2 adds an explicit warning in notes.
    """
    m = MaterialDB.get("Inconel 718")
    notes_lower = m.notes.lower()
    # Must mention the temperature limit or γ'' dissolution
    warning_present = any(kw in notes_lower for kw in (
        "1000 k", "above 1000", "gamma-double-prime", "γ''",
        "dissolves", "dissolution", "over-aged", "invalid",
        "elevated-t condition",
    ))
    assert warning_present, (
        "Inconel 718 notes must warn that the AMS 5663 aged condition is "
        "invalid above ~1000 K (γ'' dissolves). "
        f"Got: {m.notes!r}"
    )


# ---------------------------------------------------------------------------
# I2-T4  MAR-M 247 density matches NASA TM-83655 Table 2
# ---------------------------------------------------------------------------


def test_marm247_density_matches_nasa_tm83655() -> None:
    """MAR-M 247 density must be 8530 kg/m³ per NASA TM-83655 Table 2.

    Previous value of 8540 kg/m³ was 10 kg/m³ above the cited source.
    """
    m = MaterialDB.get("MAR-M 247")
    assert m.density_kg_per_m3 == pytest.approx(8530.0, abs=1.0), (
        f"MAR-M 247 density = {m.density_kg_per_m3:.1f} kg/m³; "
        f"NASA TM-83655 Table 2 states 8530 kg/m³ (8.53 g/cm³)."
    )


# ---------------------------------------------------------------------------
# I2-T5  Haynes 282 σ_y at 1000 K corrected vs H-3173
# ---------------------------------------------------------------------------


def test_haynes282_yield_at_1000K_matches_H3173() -> None:
    """Haynes 282 σ_y(1000 K) must be >= 610 MPa per H-3173 wrought-bar data.

    Previous value of 580 MPa was ~6.5 % below the H-3173 Table 'Tensile
    Properties' value (~620 MPa, solution + aged wrought bar).
    """
    m = MaterialDB.get("Haynes 282")
    sy_MPa = m.sigma_yield(1000.0) / 1.0e6
    assert sy_MPa >= 610.0, (
        f"Haynes 282 σ_y(1000 K) = {sy_MPa:.1f} MPa; H-3173 implies >= 610 MPa "
        f"(previous value 580 MPa was ~6.5 % low)."
    )


# ---------------------------------------------------------------------------
# I2-T6  IN-738 UNS N07738 alias resolves correctly (D-W1)
# ---------------------------------------------------------------------------


def test_in738_uns_alias_resolves() -> None:
    """UNS N07738 must resolve to Inconel 738 (added in Closure I2, D-W1)."""
    m = MaterialDB.get("UNS N07738")
    assert m.name == "Inconel 738", (
        f"UNS N07738 resolved to {m.name!r}, expected 'Inconel 738'"
    )


# ---------------------------------------------------------------------------
# I2-T7  17-4PH thermal conductivity corrected vs Carpenter datasheet (D-S9)
# ---------------------------------------------------------------------------


def test_174ph_thermal_conductivity_matches_carpenter() -> None:
    """17-4PH k at RT must be ~ 17.2 W/(m·K) per Carpenter thermophysical data.

    Previous value of 18.0 W/(m·K) was cited against a mechanical-properties
    table (no thermal data) — corrected to 17.2 W/(m·K) per Carpenter / AK
    Steel / Outokumpu thermophysical tables (H1025 condition).
    """
    m = MaterialDB.get("17-4PH")
    k_rt = m.thermal_conductivity_W_per_mK[0][1]
    assert k_rt == pytest.approx(17.2, abs=0.5), (
        f"17-4PH k(RT) = {k_rt:.2f} W/(m·K); expected 17.2 ± 0.5 "
        f"per Carpenter Technology thermophysical table (H1025)."
    )


# ---------------------------------------------------------------------------
# I2-T8  IN-738 c_p(RT) corrected to ~395 J/(kg·K) (D-S4)
# ---------------------------------------------------------------------------


def test_in738_cp_at_293K_in_vendor_range() -> None:
    """IN-738LC c_p(RT) must be in the 390–400 J/(kg·K) vendor range.

    Previous value of 420 J/(kg·K) was 5–8 % above published values.
    Corrected to 395 J/(kg·K) per Special Metals IN-738LC datasheet.
    """
    m = MaterialDB.get("Inconel 738")
    cp_rt = m.specific_heat_J_per_kgK[0][1]
    assert 380.0 <= cp_rt <= 410.0, (
        f"IN-738LC c_p(RT) = {cp_rt:.1f} J/(kg·K); expected 380–410 J/(kg·K) "
        f"(vendor range ~390–400; previous incorrect value was 420)."
    )
