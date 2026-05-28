"""Regression tests for cascade.materials (ADAPT-031).

Covers:
- All 10 seed materials are registered.
- Each material has a non-empty docstring-style citation.
- Young's modulus interpolation is exact at tabulated stations.
- Mid-interval linear interpolation matches the hand-computed blend.
- Inconel 625 sigma_yield at 1000 K lies in 350-450 MPa per the
  Special Metals datasheet.
- AISI 4340 sigma_yield at 293 K lies in 700-900 MPa per ASM Handbook
  Vol 1 (quenched + tempered).
- Out-of-range temperatures raise ValueError with the supported
  range in the message.
- Unknown material names raise KeyError with the known list.
- Aliases (e.g. STEEL_AISI4340) resolve to the canonical material.
"""

from __future__ import annotations

import pytest

from cascade.materials import Material, MaterialDB
from cascade.materials.base import _interp


EXPECTED_NAMES = {
    "Inconel 625",
    "Inconel 718",
    "Inconel 738",
    "MAR-M 247",
    "Ti-6Al-4V",
    "AISI 4340",
    "17-4PH",
    "A286",
    "Haynes 282",
    "316L",
}


# ---------------------------------------------------------------------------
# Catalogue completeness
# ---------------------------------------------------------------------------


def test_catalogue_has_ten_materials() -> None:
    names = set(MaterialDB.names())
    assert names == EXPECTED_NAMES, (
        f"Materials catalogue diverged. Missing: {EXPECTED_NAMES - names}; "
        f"unexpected: {names - EXPECTED_NAMES}"
    )


def test_every_material_has_a_citation() -> None:
    for m in MaterialDB.list():
        assert m.source.strip(), f"{m.name} missing citation"
        # A citation should mention at least one recognised authority.
        markers = ("ASM", "MMPDS", "NASA", "NIST", "Special Metals", "Haynes",
                   "Outokumpu", "AMS", "ASTM", "Donachie", "AK Steel")
        assert any(s in m.source for s in markers), (
            f"{m.name} citation does not cite a recognised authority: {m.source!r}"
        )


def test_every_material_has_property_tables() -> None:
    for m in MaterialDB.list():
        for attr in (
            "youngs_modulus_GPa",
            "yield_strength_MPa",
            "ultimate_strength_MPa",
            "thermal_expansion_1_per_K",
            "thermal_conductivity_W_per_mK",
            "specific_heat_J_per_kgK",
        ):
            tab = getattr(m, attr)
            assert len(tab) >= 2, f"{m.name}.{attr} has fewer than 2 stations"
            temps = [t for t, _ in tab]
            assert temps == sorted(temps), f"{m.name}.{attr} not sorted by T"
            assert all(v > 0 for _, v in tab), f"{m.name}.{attr} has non-positive value"


def test_density_and_poisson_in_physical_range() -> None:
    for m in MaterialDB.list():
        assert 3000.0 < m.density_kg_per_m3 < 10000.0, m.name
        assert 0.2 < m.poisson < 0.4, m.name


# ---------------------------------------------------------------------------
# Interpolation correctness
# ---------------------------------------------------------------------------


def test_E_exact_at_knot() -> None:
    inco = MaterialDB.get("Inconel 625")
    for T_K, E_GPa in inco.youngs_modulus_GPa:
        assert inco.E(T_K) == pytest.approx(E_GPa * 1e9, rel=1e-12), (
            f"E({T_K}) should be exact at the tabulated value"
        )


def test_E_mid_interval_is_linear_blend() -> None:
    inco = MaterialDB.get("Inconel 625")
    # Use the first two stations of the E table: (293, 207.5) and (700, 184.0)
    T_lo, E_lo = inco.youngs_modulus_GPa[0]
    T_hi, E_hi = inco.youngs_modulus_GPa[1]
    T_mid = 0.5 * (T_lo + T_hi)
    expected = 0.5 * (E_lo + E_hi) * 1e9
    assert inco.E(T_mid) == pytest.approx(expected, rel=1e-12)


def test_interp_at_quarter_point() -> None:
    # Independent of any material — exercise the interpolation core.
    table = [(293.0, 200.0), (1000.0, 100.0)]
    T = 293.0 + 0.25 * (1000.0 - 293.0)
    expected = 200.0 + 0.25 * (100.0 - 200.0)
    assert _interp(table, T) == pytest.approx(expected, rel=1e-12)


def test_inconel718_E_at_373K_matches_smc045() -> None:
    """Inconel 718 E at 373 K (100 °C) must be 196 GPa per SMC-045 station.

    Prior to adding the 373 K station, piecewise-linear interpolation of the
    293–700 K segment over-predicted by 2.1 % (200.1 GPa vs 196 GPa on the
    Special Metals SMC-045 datasheet, Table 'Physical Constants').  The
    station was added as a fix (Closure F3, Item 2).
    """
    inco_718 = MaterialDB.get("Inconel 718")
    E_GPa = inco_718.E(373.0) / 1e9
    assert E_GPa == pytest.approx(196.0, rel=1e-9), (
        f"Inconel 718 E(373 K) = {E_GPa:.2f} GPa; expected 196.0 GPa from SMC-045"
    )
    # The station must exist in the table to guarantee exact-knot behaviour.
    knot_temps = [T for T, _ in inco_718.youngs_modulus_GPa]
    assert 373.0 in knot_temps, (
        "373 K station missing from Inconel 718 youngs_modulus_GPa table"
    )


# ---------------------------------------------------------------------------
# Engineering reasonableness (the citation-grounded checks)
# ---------------------------------------------------------------------------


def test_inconel625_yield_at_1000K_in_range() -> None:
    """Per Special Metals SMC-063 the yield at ~1000 K is ~370-415 MPa."""
    inco = MaterialDB.get("Inconel 625")
    sy_MPa = inco.sigma_yield(1000.0) / 1.0e6
    assert 350.0 <= sy_MPa <= 450.0, sy_MPa


def test_aisi4340_yield_at_293K_in_range() -> None:
    """Per ASM Vol 1 the 4340 Q&T 425C yield is ~825 MPa, in 700-900 MPa."""
    s = MaterialDB.get("AISI 4340")
    sy_MPa = s.sigma_yield(293.0) / 1.0e6
    assert 700.0 <= sy_MPa <= 900.0, sy_MPa


def test_ti6al4v_density() -> None:
    """Ti-6Al-4V should be ~4430 kg/m^3 (MMPDS-13)."""
    ti = MaterialDB.get("Ti-6Al-4V")
    assert 4400.0 <= ti.density_kg_per_m3 <= 4500.0


def test_inconel718_yield_higher_than_inconel625() -> None:
    """Aged 718 is harder than annealed 625 at room temperature."""
    inco_625 = MaterialDB.get("Inconel 625")
    inco_718 = MaterialDB.get("Inconel 718")
    assert inco_718.sigma_yield(293.0) > inco_625.sigma_yield(293.0)


def test_316L_yield_lower_than_17_4PH() -> None:
    """316L annealed is a soft austenitic, 17-4PH H1025 is much stronger."""
    ss = MaterialDB.get("316L")
    ph = MaterialDB.get("17-4PH")
    assert ph.sigma_yield(293.0) > ss.sigma_yield(293.0) * 2.5


# ---------------------------------------------------------------------------
# Out-of-range / unknown-material refusal
# ---------------------------------------------------------------------------


def test_E_below_range_raises_clear_error() -> None:
    inco = MaterialDB.get("Inconel 625")
    with pytest.raises(ValueError) as excinfo:
        inco.E(50.0)
    msg = str(excinfo.value)
    assert "out of range" in msg
    assert "293" in msg  # the lower bound
    assert "Inconel 625" in msg


def test_E_above_range_raises_clear_error() -> None:
    s = MaterialDB.get("AISI 4340")
    with pytest.raises(ValueError) as excinfo:
        s.E(5000.0)
    msg = str(excinfo.value)
    assert "out of range" in msg


def test_nonfinite_temperature_raises() -> None:
    inco = MaterialDB.get("Inconel 625")
    with pytest.raises(ValueError):
        inco.E(float("nan"))
    with pytest.raises(ValueError):
        inco.E(float("inf"))


def test_unknown_material_lists_known() -> None:
    with pytest.raises(KeyError) as excinfo:
        MaterialDB.get("Unobtainium")
    msg = str(excinfo.value)
    assert "Unobtainium" in msg
    # The list of known materials should appear in the message.
    assert "Inconel 625" in msg


# ---------------------------------------------------------------------------
# Aliases and family lookup
# ---------------------------------------------------------------------------


def test_alias_resolves_to_canonical() -> None:
    assert MaterialDB.get("AISI4340").name == "AISI 4340"
    assert MaterialDB.get("STEEL_AISI4340").name == "AISI 4340"
    assert MaterialDB.get("IN625").name == "Inconel 625"
    assert MaterialDB.get("Ti64").name == "Ti-6Al-4V"


def test_by_family_returns_ni_superalloys() -> None:
    ni = MaterialDB.by_family("Ni-based superalloy")
    names = {m.name for m in ni}
    assert {"Inconel 625", "Inconel 718", "Inconel 738", "MAR-M 247",
            "Haynes 282"} <= names


def test_families_distinct_and_sorted() -> None:
    fams = MaterialDB.families()
    assert fams == sorted(fams)
    assert "Ni-based superalloy" in fams
    assert "Ti alloy" in fams


# ---------------------------------------------------------------------------
# JSON serialisation
# ---------------------------------------------------------------------------


def test_as_dict_round_trips() -> None:
    inco = MaterialDB.get("Inconel 625")
    d = inco.as_dict()
    # Required keys present
    for k in ("name", "designation", "family", "density_kg_per_m3",
              "poisson", "youngs_modulus_GPa", "yield_strength_MPa",
              "ultimate_strength_MPa", "thermal_expansion_1_per_K",
              "thermal_conductivity_W_per_mK", "specific_heat_J_per_kgK",
              "source", "notes"):
        assert k in d, k
    # Property tables are lists of [T, v] lists, not tuples
    assert isinstance(d["youngs_modulus_GPa"], list)
    assert isinstance(d["youngs_modulus_GPa"][0], list)


# ---------------------------------------------------------------------------
# AISI 4340 still works as the rotor-FEM default fallback (the v0 path)
# ---------------------------------------------------------------------------


def test_aisi4340_E_at_293K_matches_rotor_default() -> None:
    """The rotor module's DEFAULT_E_PA = 2.0e11 is AISI 4340 at room T.

    Confirm the new catalogue is within 5 % of that default so swapping
    the registry in does not blow up the existing beam-FEM smoke tests.
    """
    s = MaterialDB.get("AISI 4340")
    assert s.E(293.0) == pytest.approx(2.0e11, rel=0.05)


def test_aisi4340_poisson_matches_rotor_default() -> None:
    s = MaterialDB.get("AISI 4340")
    assert s.poisson == pytest.approx(0.30, abs=0.02)
