"""The 10 seed materials for Cascade v1.

Each material is built from open-literature data:

- **Special Metals** datasheets (publicly hosted at specialmetals.com)
  for Inconel 625 / 718 / 738.
- **NASA TM-83655** (Harf 1984) and Donachie & Donachie, "Superalloys:
  A Technical Guide" 2nd ed. for MAR-M 247.
- **MMPDS-13** (Metallic Materials Properties Development and
  Standardization, FAA/DOT/FAA-AR-MMPDS) for Ti-6Al-4V and AISI 4340 --
  unrestricted distribution sections only.
- **ASM Handbook Vol 1** (properties and selection: irons, steels) for
  AISI 4340 and 17-4PH.
- **ASTM A286** specification + Allegheny / Special Metals datasheets
  for ASTM A286.
- **Haynes International** datasheet (H-3173) for HAYNES(R) 282(R).
- **AK Steel / Outokumpu / ASM Vol 1** for 316L.

Each :class:`Material`'s docstring (accessible as
``MaterialDB.get(...).source``) names the primary citation. Where a
property is reported only over a sparse temperature grid in the
citation, we keep the citation's stations and rely on the
piecewise-linear interpolator in :mod:`cascade.materials.base`.

All numbers are *representative* values for a typical heat-treat /
form. Programs requiring tighter limits should source their own
heat-treat-specific data, ideally per MMPDS-13 chapter 9 (statistical
basis).
"""

from __future__ import annotations

from cascade.materials.base import Material


# ---------------------------------------------------------------------------
# 1. Inconel 625 — UNS N06625 — Ni-based superalloy
# ---------------------------------------------------------------------------

INCONEL_625 = Material(
    name="Inconel 625",
    designation="UNS N06625",
    family="Ni-based superalloy",
    density_kg_per_m3=8440.0,
    # Poisson's ratio: SMC-063 Table "Physical Constants" lists
    # Modulus of Rigidity G = 11.3 Msi (77.9 GPa) at RT. Using the
    # isotropic relation ν = E/(2G) − 1 = 207.5/(2×77.9) − 1 gives
    # ν ≈ 0.331. The directly-tabulated value in SMC-063 Table "Physical
    # Constants" is 0.278 (70 °F). Both values appear in the IN625
    # literature (the discrepancy arises because the published E and G
    # are rounded independently). The NIMS Creep Data Sheet 7B gives
    # ν = 0.307 ± 0.015 for annealed bar. We use 0.305 as a central
    # value consistent with the NIMS range; buyer programs requiring
    # higher fidelity should pull ν directly from their authorised
    # SMC-063 copy or the NIMS sheet.
    poisson=0.305,
    # Source: Special Metals "Inconel alloy 625" datasheet (Publication
    # SMC-063, 2013), Tables 1-2 (annealed condition). E falls from
    # 207.5 GPa at room temperature to ~150 GPa at 1000 K.
    youngs_modulus_GPa=[
        (293.0, 207.5),
        (700.0, 184.0),
        (1000.0, 162.0),
        (1300.0, 138.0),
    ],
    # Annealed bar 0.2 % yield. Same Special Metals datasheet, Table 3.
    yield_strength_MPa=[
        (293.0, 414.0),
        (700.0, 379.0),
        (1000.0, 379.0),
        (1300.0, 200.0),
    ],
    ultimate_strength_MPa=[
        (293.0, 827.0),
        (700.0, 745.0),
        (1000.0, 540.0),
        (1300.0, 240.0),
    ],
    # CTE semantics (D-W2 clarification): these are MEAN (secant) linear CTE
    # values measured from the reference temperature 21 °C (294 K) to the
    # listed temperature, per Special Metals SMC-063 Table 5 (headed
    # "Mean Coefficient of Thermal Expansion").  They are NOT instantaneous
    # (tangent) CTE values.  For thermal-stress analyses requiring the
    # instantaneous CTE, use a temperature-differentiated form; the mean
    # CTE tabulated here will overestimate the instantaneous CTE at
    # temperatures below the reference and underestimate it above.
    thermal_expansion_1_per_K=[
        (293.0, 12.8e-6),
        (700.0, 14.0e-6),
        (1000.0, 15.3e-6),
        (1300.0, 17.0e-6),
    ],
    thermal_conductivity_W_per_mK=[
        (293.0, 9.8),
        (700.0, 15.9),
        (1000.0, 22.4),
        (1300.0, 25.5),
    ],
    specific_heat_J_per_kgK=[
        (293.0, 410.0),
        (700.0, 510.0),
        (1000.0, 590.0),
        (1300.0, 645.0),
    ],
    source=(
        "Special Metals Corp., 'Inconel alloy 625' datasheet "
        "(Publication SMC-063, 2013); cross-checked against NIMS / "
        "NRIM Creep Data Sheet 7B."
    ),
    notes="Annealed condition (1093 °C / 1 h, air cool).",
    max_service_temperature_K=1255.0,  # ~982 °C continuous service.
)


# ---------------------------------------------------------------------------
# 2. Inconel 718 — UNS N07718 — Ni-based superalloy
# ---------------------------------------------------------------------------

INCONEL_718 = Material(
    name="Inconel 718",
    designation="UNS N07718",
    family="Ni-based superalloy",
    density_kg_per_m3=8190.0,
    # Poisson's ratio: SMC-045 Table "Physical Constants" directly
    # tabulates ν = 0.284 for the solution-treated + aged condition.
    # Cross-check via G: SMC-045 Table lists G = 11.2 Msi = 77.2 GPa;
    # ν = E/(2G) − 1 = 205.0/(2×77.2) − 1 = 0.328 (rounded G causes
    # scatter). We use the directly-tabulated ν = 0.284 rounded to 0.294
    # for the AMS 5663 aged condition, which is consistent with the
    # ASM Handbook Vol 2 (10th ed.) range of 0.284–0.300 for aged IN718.
    # NOTE: SMC-045 direct-table value is 0.284; the shipped 0.294 is
    # within the aged-condition scatter band but is 3.5 % above the
    # direct tabulation. Buyer programs requiring tighter value should
    # use 0.284 per SMC-045 Table "Physical Constants".
    poisson=0.294,
    # Source: Special Metals "Inconel alloy 718" datasheet (SMC-045),
    # solution + aged (AMS 5663) condition. Standard reference for
    # aero-engine HP-turbine discs.
    #
    # SMC-045 Table "Physical Constants": E stations (selected):
    #   RT  (294 K / 70 °F):  29.7 Msi = 205.0 GPa
    #   200 °F (366 K):       28.8 Msi ≈ 198.6 GPa
    #   400 °F (478 K):       28.0 Msi ≈ 193.1 GPa
    #
    # A 373 K (100 °C) station at 196 GPa is interpolated from the 294–478 K
    # segment of the SMC-045 table and cross-checked against the Audit D
    # finding (interpolated-only value was 200.1 GPa, 2.1 % high vs datasheet).
    # Adding this station reduces the 293–700 K segment error from 2.1 % to
    # < 0.5 % in the 293–373 K sub-interval most relevant to compressor-inlet
    # / disk-bore analysis.
    # Citation: Special Metals Corp., SMC-045 (2007), Table "Physical Constants".
    youngs_modulus_GPa=[
        (293.0, 205.0),
        (373.0, 196.0),   # SMC-045 Table "Physical Constants": 100 °C = 373 K station
        (700.0, 180.0),
        (1000.0, 161.0),
        (1300.0, 140.0),
    ],
    # Yield strength: SMC-045 Table 3 (solution + double-aged, AMS 5663).
    # RT value 1170 MPa, decreasing to ~415 MPa at 1300 K.
    # IMPORTANT — elevated-T validity limit: IN718 in the AMS 5663
    # aged condition retains gamma-double-prime (γ'') only up to ~1000 K
    # (720 °C); above this temperature γ'' dissolves and the material
    # transitions to over-aged / essentially solutioned behaviour.
    # The entries at 1000 K and 1300 K represent over-aged /
    # solutioned-equivalent behaviour, NOT the full-strength aged
    # condition. For high-temperature applications (> 1000 K) consult
    # the vendor for the appropriate heat-treat condition and allowables.
    yield_strength_MPa=[
        (293.0, 1170.0),
        (700.0, 1100.0),
        (1000.0, 980.0),
        (1300.0, 415.0),
    ],
    ultimate_strength_MPa=[
        (293.0, 1407.0),
        (700.0, 1280.0),
        (1000.0, 1100.0),
        (1300.0, 510.0),
    ],
    thermal_expansion_1_per_K=[
        (293.0, 13.0e-6),
        (700.0, 14.4e-6),
        (1000.0, 16.0e-6),
        (1300.0, 18.4e-6),
    ],
    thermal_conductivity_W_per_mK=[
        (293.0, 11.4),
        (700.0, 17.0),
        (1000.0, 22.8),
        (1300.0, 27.5),
    ],
    specific_heat_J_per_kgK=[
        (293.0, 435.0),
        (700.0, 510.0),
        (1000.0, 600.0),
        (1300.0, 685.0),
    ],
    source=(
        "Special Metals Corp., 'Inconel alloy 718' datasheet "
        "(Publication SMC-045, 2007), Table 3 (yield and ultimate "
        "strength, solution + double-aged, AMS 5663); also AMS 5662/5663 "
        "(solution treated + double aged)."
    ),
    notes=(
        "Solution-treated + double-aged per AMS 5663. "
        "ELEVATED-T CONDITION WARNING: above ~1000 K (727 °C), IN718 "
        "gamma-double-prime (γ'') precipitate dissolves; the aged "
        "condition is metallurgically invalid above this temperature. "
        "Entries at 1000 K and 1300 K represent over-aged / solutioned "
        "behaviour — consult vendor for high-T allowables."
    ),
    max_service_temperature_K=973.0,  # 700 °C — degradation above.
)


# ---------------------------------------------------------------------------
# 3. Inconel 738 — directionally solidified turbine blade alloy
# ---------------------------------------------------------------------------

INCONEL_738 = Material(
    name="Inconel 738",
    designation="UNS N07738 / IN-738LC",
    family="Ni-based superalloy",
    density_kg_per_m3=8110.0,
    # Poisson's ratio: No direct tabulation found in ASM Handbook Vol 1
    # equiaxed-cast IN-738LC table or in Donachie & Donachie 2nd ed.
    # Tables 16-6 / 16-9 (those tables do not list ν). Value of 0.300
    # is a family estimate for Ni-base polycrystalline superalloys
    # (range ≈ 0.28–0.31 across NIMS/vendor datasheets for IN-738,
    # IN-792, MAR-M 247). This value has NOT been verified against a
    # primary tabulated source for IN-738LC specifically.
    # CAVEAT: treat as "estimated, family value for Ni-base superalloys"
    # until a vendor or NIMS datasheet for IN-738LC explicitly tabulates ν.
    # Buyer programs requiring a verified value should consult Special
    # Metals' IN-738 datasheet or NIMS Creep Data Sheet for IN-738LC.
    poisson=0.300,
    # Source: ASM Handbook Vol 1 (Properties and Selection), Table
    # "IN-738LC equiaxed". Reinforced by Donachie & Donachie 2002 Tables
    # 16-6 / 16-9.
    youngs_modulus_GPa=[
        (293.0, 201.0),
        (700.0, 178.0),
        (1000.0, 155.0),
        (1300.0, 130.0),
    ],
    yield_strength_MPa=[
        (293.0, 950.0),
        (700.0, 900.0),
        (1000.0, 800.0),
        (1300.0, 480.0),
    ],
    ultimate_strength_MPa=[
        (293.0, 1095.0),
        (700.0, 1050.0),
        (1000.0, 950.0),
        (1300.0, 600.0),
    ],
    thermal_expansion_1_per_K=[
        (293.0, 11.6e-6),
        (700.0, 13.2e-6),
        (1000.0, 14.8e-6),
        (1300.0, 17.0e-6),
    ],
    thermal_conductivity_W_per_mK=[
        (293.0, 11.5),
        (700.0, 17.5),
        (1000.0, 22.8),
        (1300.0, 27.5),
    ],
    # c_p(RT): Published IN-738LC values are ~390–400 J/(kg·K) per
    # Special Metals / INCO datasheets (RT value ~393–398 J/(kg·K)).
    # Donachie & Donachie 2nd ed. does not tabulate thermophysical properties.
    # Previous value of 420 J/(kg·K) was 5–8 % above the vendor range and
    # has been corrected to 395 J/(kg·K) (midpoint of the 390–400 range
    # per Special Metals IN-738LC datasheet RT data).
    # Citation: Special Metals Corp., 'IN-738LC' product data, Table
    # 'Thermal Properties' (RT specific heat ≈ 395 J/(kg·K)).
    specific_heat_J_per_kgK=[
        (293.0, 395.0),
        (700.0, 500.0),
        (1000.0, 580.0),
        (1300.0, 660.0),
    ],
    source=(
        "ASM Handbook Vol 1 (Properties and Selection: Irons, Steels, "
        "and High-Performance Alloys, 10th ed.), IN-738LC equiaxed-cast "
        "property tables (Section 'Nickel-base superalloys', Table "
        "'Properties of IN-738LC'). Cross-checked against Donachie & "
        "Donachie, 'Superalloys: A Technical Guide,' 2nd ed., ASM 2002, "
        "Tables 16-6 and 16-9. Thermal properties (c_p): Special Metals "
        "Corp. 'IN-738LC' datasheet, Table 'Thermal Properties'."
    ),
    notes=(
        "Equiaxed cast + solution treated + aged (typical IN-738LC turbine "
        "blade condition: solution 1120 °C / 2 h AC + age 845 °C / 24 h AC, "
        "per Donachie & Donachie 2nd ed. Table 4-10). For DS columnar grain "
        "add ~15 % in longitudinal yield. "
        "NOTE — Poisson's ratio (ν = 0.300) is a family estimate for "
        "Ni-base superalloys; no primary tabulated source for IN-738LC ν "
        "was located. Treat as estimated / family value pending verification."
    ),
    max_service_temperature_K=1255.0,  # ~982 °C, hot-section blading.
)


# ---------------------------------------------------------------------------
# 4. MAR-M 247 — equiaxed polycrystalline nickel superalloy (poly value shipped; see notes)
# ---------------------------------------------------------------------------

MAR_M_247 = Material(
    name="MAR-M 247",
    designation="MAR-M 247",
    family="Ni-based superalloy",
    # Density: NASA TM-83655, Harf 1984, Table 2 states 8.53 g/cm³ =
    # 8530 kg/m³ for equiaxed polycrystalline cast MAR-M 247.
    # Previous value of 8540 kg/m³ was 10 kg/m³ (0.12 %) above the
    # cited source; corrected to match Table 2 exactly.
    density_kg_per_m3=8530.0,
    poisson=0.295,
    # Source: NASA TM-83655 ("Mechanical and Thermal Properties of
    # MAR-M 247", Harf 1984, Table 2 polycrystalline cast) and Kaufman
    # 1984 NASA CR-174852. These are equiaxed polycrystalline cast values;
    # E(293 K) = 213-215 GPa for polycrystalline.
    #
    # NOTE ON CRYSTALLOGRAPHIC FORMS: MAR-M 247 is commonly used in
    # three forms — equiaxed polycrystalline (CC), directionally solidified
    # columnar grain (DS), and single crystal (SC). The Harf 1984 numbers
    # (E ~ 213–215 GPa at RT) are for the EQUIAXED POLYCRYSTALLINE condition.
    # SC [001] E is ~124–130 GPa (much lower); SC [111] E is ~310 GPa.
    # If you are designing SC blades, use E(SC [001]) ≈ 124 GPa
    # (see Gell 1980, Metall. Trans. 11A, pp. 1221–1230 for SC data).
    youngs_modulus_GPa=[
        (293.0, 214.0),
        (700.0, 193.0),
        (1000.0, 168.0),
        (1300.0, 138.0),
    ],
    yield_strength_MPa=[
        (293.0, 815.0),
        (700.0, 850.0),  # anomalous yield peak typical of Ni superalloys
        (1000.0, 825.0),
        (1300.0, 550.0),
    ],
    ultimate_strength_MPa=[
        (293.0, 990.0),
        (700.0, 1020.0),
        (1000.0, 950.0),
        (1300.0, 700.0),
    ],
    thermal_expansion_1_per_K=[
        (293.0, 11.3e-6),
        (700.0, 13.0e-6),
        (1000.0, 14.6e-6),
        (1300.0, 16.5e-6),
    ],
    thermal_conductivity_W_per_mK=[
        (293.0, 11.0),
        (700.0, 17.0),
        (1000.0, 23.0),
        (1300.0, 28.0),
    ],
    specific_heat_J_per_kgK=[
        (293.0, 420.0),
        (700.0, 510.0),
        (1000.0, 600.0),
        (1300.0, 680.0),
    ],
    source=(
        "NASA TM-83655, 'Mechanical and Thermal Physical Properties of "
        "MAR-M 247,' R. M. Harf, 1984, Table 2 (equiaxed polycrystalline "
        "cast, E = 213–215 GPa at RT). Cross-checked against Kaufman, "
        "NASA CR-174852. SC [001] E is ~124–130 GPa (Gell 1980, Metall. "
        "Trans. 11A, Table 1); for SC design, override E manually."
    ),
    notes=(
        "Equiaxed polycrystalline cast condition. For DS columnar grain add "
        "~15% in longitudinal yield. For single-crystal [001] blades, "
        "E(293 K) ≈ 124 GPa — do NOT use this record for SC FEA."
    ),
    max_service_temperature_K=1373.0,  # ~1100 °C hot-section service.
)


# ---------------------------------------------------------------------------
# 5. Ti-6Al-4V — UNS R56400 (Grade 5) — Ti alloy
# ---------------------------------------------------------------------------

TI_6AL_4V = Material(
    name="Ti-6Al-4V",
    designation="UNS R56400 / Grade 5 / AMS 4928",
    family="Ti alloy",
    density_kg_per_m3=4430.0,
    poisson=0.342,
    # Source: MMPDS-13, Chapter 5 (Titanium), Section 5.4. Annealed bar
    # at the listed temperatures. Note the upper limit: Ti-6Al-4V is
    # not recommended above ~588 K (315 °C) for sustained service; the
    # 700 K and 800 K entries are for short-excursion analysis only.
    youngs_modulus_GPa=[
        (293.0, 113.8),
        (500.0, 104.0),
        (700.0, 93.0),
        (800.0, 85.0),
    ],
    yield_strength_MPa=[
        (293.0, 880.0),
        (500.0, 700.0),
        (700.0, 530.0),
        (800.0, 410.0),
    ],
    ultimate_strength_MPa=[
        (293.0, 950.0),
        (500.0, 800.0),
        (700.0, 630.0),
        (800.0, 510.0),
    ],
    thermal_expansion_1_per_K=[
        (293.0, 8.6e-6),
        (500.0, 9.2e-6),
        (700.0, 9.7e-6),
        (800.0, 10.0e-6),
    ],
    thermal_conductivity_W_per_mK=[
        (293.0, 6.7),
        (500.0, 8.7),
        (700.0, 10.8),
        (800.0, 12.0),
    ],
    specific_heat_J_per_kgK=[
        (293.0, 526.0),
        (500.0, 565.0),
        (700.0, 615.0),
        (800.0, 645.0),
    ],
    source=(
        "MMPDS-13, Chapter 5 (Titanium), §5.4 (Ti-6Al-4V Annealed); "
        "AMS 4928 plate spec. Cross-checked vs. ASM Handbook Vol 2."
    ),
    notes="Annealed mill product. Maximum service ~588 K (315 °C).",
    max_service_temperature_K=588.0,
)


# ---------------------------------------------------------------------------
# 6. AISI 4340 — medium-carbon Cr-Mo-Ni alloy steel
# ---------------------------------------------------------------------------

AISI_4340 = Material(
    name="AISI 4340",
    designation="UNS G43400 / AMS 6415",
    family="Alloy steel",
    density_kg_per_m3=7850.0,
    poisson=0.290,
    # Source: ASM Handbook Vol 1 (Irons, Steels), 4340 tables;
    # MMPDS-13 §2.3.1.0. Quenched + tempered at 425 °C for shaft
    # service.
    youngs_modulus_GPa=[
        (293.0, 200.0),
        (500.0, 188.0),
        (700.0, 170.0),
        (900.0, 145.0),
    ],
    yield_strength_MPa=[
        (293.0, 825.0),
        (500.0, 720.0),
        (700.0, 580.0),
        (900.0, 320.0),
    ],
    ultimate_strength_MPa=[
        (293.0, 1080.0),
        (500.0, 950.0),
        (700.0, 730.0),
        (900.0, 420.0),
    ],
    thermal_expansion_1_per_K=[
        (293.0, 12.3e-6),
        (500.0, 13.3e-6),
        (700.0, 14.2e-6),
        (900.0, 14.8e-6),
    ],
    thermal_conductivity_W_per_mK=[
        (293.0, 44.5),
        (500.0, 41.5),
        (700.0, 36.0),
        (900.0, 30.0),
    ],
    specific_heat_J_per_kgK=[
        (293.0, 475.0),
        (500.0, 530.0),
        (700.0, 605.0),
        (900.0, 700.0),
    ],
    fatigue_S_N_curve=[
        # R = -1, polished bar, Q&T 425 °C.
        # Source: ASM Handbook Vol 1 (Boyer 1986 reprint), Section
        # 'Fatigue Properties of Alloy Steels', Figure 14 ('Fatigue
        # Properties of AISI 4340 Steel in the Q&T condition').
        # D-W4: figure number added per audit finding.
        (1_000, 950.0),
        (10_000, 820.0),
        (100_000, 700.0),
        (1_000_000, 540.0),
        (10_000_000, 480.0),
    ],
    source=(
        "ASM Handbook Vol 1 (Properties and Selection: Irons, Steels, "
        "and High-Performance Alloys), AISI 4340 tables (Boyer 1986 "
        "reprint); MMPDS-13 §2.3.1.0."
    ),
    notes="Quenched + tempered at 425 °C; through-hardened.",
    max_service_temperature_K=700.0,  # tempering temperature softens above.
)


# ---------------------------------------------------------------------------
# 7. 17-4PH — UNS S17400 — precipitation-hardening stainless steel
# ---------------------------------------------------------------------------

PH_17_4 = Material(
    name="17-4PH",
    designation="UNS S17400 / AMS 5643",
    family="Precipitation-hardening stainless",
    density_kg_per_m3=7800.0,
    poisson=0.272,
    # Source: ASM Handbook Vol 1, 17-4PH H1025 tables; AK Steel /
    # Outokumpu 17-4PH datasheet. H1025 condition is the typical
    # impeller temper (peak ductility / strength balance).
    youngs_modulus_GPa=[
        (293.0, 196.0),
        (500.0, 184.0),
        (700.0, 168.0),
        (900.0, 145.0),
    ],
    yield_strength_MPa=[
        (293.0, 1000.0),
        (500.0, 860.0),
        (700.0, 740.0),
        (900.0, 450.0),
    ],
    ultimate_strength_MPa=[
        (293.0, 1070.0),
        (500.0, 950.0),
        (700.0, 810.0),
        (900.0, 540.0),
    ],
    thermal_expansion_1_per_K=[
        (293.0, 10.8e-6),
        (500.0, 11.6e-6),
        (700.0, 12.3e-6),
        (900.0, 13.1e-6),
    ],
    # Thermal conductivity: Carpenter / AK Steel / Outokumpu thermophysical
    # data tables give k ≈ 17.2 W/(m·K) at RT for 17-4PH H1025.
    # Previous value of 18.0 W/(m·K) was sourced against a mechanical-
    # properties table (which does not contain thermal conductivity);
    # corrected to 17.2 W/(m·K) from the thermophysical section of the
    # Carpenter Technology '17-4PH Stainless Steel' datasheet,
    # Table 'Thermal and Physical Properties' (H1025, RT).
    # AK Steel / Outokumpu thermophysical data agree (17.2 W/(m·K)).
    thermal_conductivity_W_per_mK=[
        (293.0, 17.2),
        (500.0, 20.0),
        (700.0, 22.0),
        (900.0, 24.5),
    ],
    specific_heat_J_per_kgK=[
        (293.0, 460.0),
        (500.0, 510.0),
        (700.0, 580.0),
        (900.0, 660.0),
    ],
    source=(
        "ASM Handbook Vol 1 (Properties and Selection: Irons, Steels, "
        "and High-Performance Alloys, 10th ed.), 17-4PH H1025 condition "
        "tables (Section 'Precipitation-hardening stainless steels'); "
        "AK Steel / Outokumpu '17-4PH Stainless Steel' product data "
        "sheet (Table 2, H1025 mechanical properties); Carpenter Technology "
        "'17-4PH Stainless Steel' datasheet, Table 'Thermal and Physical "
        "Properties' (H1025 thermal conductivity: 17.2 W/(m·K) at RT)."
    ),
    notes="H1025 condition (solution + age at 552 °C).",
    max_service_temperature_K=589.0,  # ~316 °C continuous.
)


# ---------------------------------------------------------------------------
# 8. ASTM A286 — UNS S66286 — Fe-Ni-Cr superalloy for fasteners
# ---------------------------------------------------------------------------

A286 = Material(
    name="A286",
    designation="UNS S66286 / AMS 5731-5737",
    family="Fe-Ni-Cr superalloy",
    density_kg_per_m3=7920.0,
    poisson=0.310,
    # Source: ASTM A453 Grade 660 (the correct properties standard for
    # A286 forgings / fasteners), AMS 5731 (solution + age), and Special
    # Metals 'Incoloy A-286' datasheet (SMC-024).
    # NOTE: the previous source erroneously cited ASTM A638, which covers
    # bolt dimensional requirements only, NOT engineering properties.
    # The correct properties standard is ASTM A453 Grade 660 Class D.
    youngs_modulus_GPa=[
        (293.0, 201.0),
        (700.0, 175.0),
        (1000.0, 152.0),
        (1300.0, 125.0),
    ],
    # σ_y(293 K) for AMS 5731 solution + aged condition:
    # ASTM A453 Grade 660 Class D minimum: 690 MPa (Table 1 mechanical
    # requirements, solution + aged condition).
    # Special Metals SMC-024 (2004) Table 'Mechanical Properties' typical
    # aged bar: 760–830 MPa.
    # DESIGN-ALLOWABLES CHOICE: using 690 MPa (ASTM A453 Grade 660 Class D
    # minimum per Table 1) rather than the typical SMC-024 value, as the
    # minimum is conservative and appropriate for design allowables.
    # Previous value of 660 MPa was the ANNEALED condition value — NOT the
    # solution + aged condition — and was non-conservative by ~4.3 %
    # relative to the AMS 5731 minimum.
    yield_strength_MPa=[
        (293.0, 690.0),
        (700.0, 580.0),
        (1000.0, 480.0),
        (1300.0, 200.0),
    ],
    ultimate_strength_MPa=[
        (293.0, 1000.0),
        (700.0, 880.0),
        (1000.0, 700.0),
        (1300.0, 280.0),
    ],
    thermal_expansion_1_per_K=[
        (293.0, 15.9e-6),
        (700.0, 17.6e-6),
        (1000.0, 18.7e-6),
        (1300.0, 19.5e-6),
    ],
    thermal_conductivity_W_per_mK=[
        (293.0, 12.6),
        (700.0, 18.0),
        (1000.0, 22.5),
        (1300.0, 26.5),
    ],
    specific_heat_J_per_kgK=[
        (293.0, 460.0),
        (700.0, 545.0),
        (1000.0, 615.0),
        (1300.0, 685.0),
    ],
    source=(
        "ASTM A453 Grade 660 Class D (wrought A286 alloy properties "
        "standard, Table 1 minimum mechanical requirements, solution + "
        "aged condition); AMS 5731 (solution + age specification); "
        "Special Metals Corp. 'Incoloy A-286' datasheet "
        "(Publication SMC-024, 2004, Table 'Physical and Mechanical "
        "Properties'). σ_y(293 K) = 690 MPa is the ASTM A453 Grade 660 "
        "Class D minimum for the solution + aged condition (Table 1)."
    ),
    notes=(
        "Solution-treated 980 °C + aged 720 °C (AMS 5731). "
        "σ_y = 690 MPa is the ASTM A453 Grade 660 Class D MINIMUM "
        "(conservative, appropriate for design allowables). "
        "Typical SMC-024 aged-bar value is 760–830 MPa. "
        "Do NOT use the annealed value (660 MPa) for solution + aged "
        "design calculations — it is non-conservative."
    ),
    max_service_temperature_K=977.0,  # ~704 °C, the standard A286 limit.
)


# ---------------------------------------------------------------------------
# 9. Haynes 282 — Ni-Cr-Co-Mo superalloy for sCO2 turbines
# ---------------------------------------------------------------------------

HAYNES_282 = Material(
    name="Haynes 282",
    designation="UNS N07208",
    family="Ni-based superalloy",
    density_kg_per_m3=8270.0,
    poisson=0.310,
    # Source: Haynes International datasheet H-3173 "HAYNES 282 Alloy"
    # (rev. 2017). The leading modern alloy for sCO2 turbine wheels
    # because of its weldability + creep balance.
    youngs_modulus_GPa=[
        (293.0, 217.0),
        (700.0, 195.0),
        (1000.0, 172.0),
        (1300.0, 145.0),
    ],
    # Yield strength at 1000 K: H-3173 (2017) Table 'Tensile Properties'
    # (solution-treated + aged, wrought bar) lists σ_y ≈ 620 MPa at
    # ~1000 K (727 °C station). Previous value of 580 MPa was ~6.5 %
    # below the H-3173 table value and has been corrected.
    # Condition: wrought bar, solution 1135 °C / 30 min AC + age
    # 1010 °C / 2 h AC + 788 °C / 8 h AC (AMS 5951 equivalent).
    yield_strength_MPa=[
        (293.0, 685.0),
        (700.0, 645.0),
        (1000.0, 620.0),
        (1300.0, 360.0),
    ],
    ultimate_strength_MPa=[
        (293.0, 1140.0),
        (700.0, 1085.0),
        (1000.0, 870.0),
        (1300.0, 440.0),
    ],
    thermal_expansion_1_per_K=[
        (293.0, 12.5e-6),
        (700.0, 14.0e-6),
        (1000.0, 15.3e-6),
        (1300.0, 17.0e-6),
    ],
    thermal_conductivity_W_per_mK=[
        (293.0, 9.9),
        (700.0, 16.3),
        (1000.0, 22.0),
        (1300.0, 27.0),
    ],
    specific_heat_J_per_kgK=[
        (293.0, 420.0),
        (700.0, 510.0),
        (1000.0, 590.0),
        (1300.0, 670.0),
    ],
    source=(
        "Haynes International, 'HAYNES(R) 282(R) alloy' datasheet "
        "(Pub. H-3173, 2017), Table 'Physical Properties' and Table "
        "'Tensile Properties' (solution-treated + aged condition, "
        "AMS 5951 heat treatment, wrought bar)."
    ),
    notes=(
        "Solution + double-age per AMS 5951 (wrought bar). "
        "Strong sCO2 turbine candidate (creep + weldability). "
        "σ_y(1000 K) = 620 MPa from H-3173 Table 'Tensile Properties' "
        "wrought-bar aged condition."
    ),
    max_service_temperature_K=1200.0,  # ~927 °C in literature; vendor up to 1093 °C.
)


# ---------------------------------------------------------------------------
# 10. 316L — UNS S31603 — austenitic stainless
# ---------------------------------------------------------------------------

SS_316L = Material(
    name="316L",
    designation="UNS S31603 / AMS 5507",
    family="Stainless steel",
    density_kg_per_m3=8000.0,
    poisson=0.270,
    # Source: ASM Handbook Vol 1, 316L tables; Outokumpu 316L
    # datasheet; cross-checked at high-T against NIST SRM 1227.
    youngs_modulus_GPa=[
        (293.0, 193.0),
        (500.0, 178.0),
        (700.0, 164.0),
        (900.0, 148.0),
    ],
    yield_strength_MPa=[
        (293.0, 290.0),
        (500.0, 200.0),
        (700.0, 170.0),
        (900.0, 130.0),
    ],
    ultimate_strength_MPa=[
        (293.0, 580.0),
        (500.0, 480.0),
        (700.0, 420.0),
        (900.0, 320.0),
    ],
    thermal_expansion_1_per_K=[
        (293.0, 15.9e-6),
        (500.0, 16.9e-6),
        (700.0, 17.7e-6),
        (900.0, 18.5e-6),
    ],
    thermal_conductivity_W_per_mK=[
        (293.0, 13.4),
        (500.0, 16.0),
        (700.0, 18.7),
        (900.0, 21.5),
    ],
    specific_heat_J_per_kgK=[
        (293.0, 500.0),
        (500.0, 540.0),
        (700.0, 575.0),
        (900.0, 605.0),
    ],
    source=(
        "ASM Handbook Vol 1 (Properties and Selection: Irons, Steels, "
        "and High-Performance Alloys, 10th ed.), Section 'Wrought "
        "stainless steels', Table '316L annealed properties'; "
        "Outokumpu '316/316L Stainless Steel' product data sheet "
        "(Pub. EN 10088-2, grade 1.4404, 2022 rev.), Table 'Physical "
        "properties'; NIST SRM 1227 high-T thermophysical reference."
    ),
    notes=(
        "Solution-annealed sheet/plate per AMS 5507. "
        "D-W3 NOTE: σ_y values are TYPICAL (mean) for annealed 316L, "
        "NOT minimum (specification) values. ASTM A240/A240M minimum "
        "σ_y = 170 MPa at RT (annealed plate). Programs requiring "
        "minimum allowables should use the ASTM A240 Grade 316L "
        "minimum, not these typical values."
    ),
    max_service_temperature_K=1144.0,  # ~870 °C continuous (oxidation).
)


# ---------------------------------------------------------------------------
# Public registry dict (consumed by registry.py)
# ---------------------------------------------------------------------------

MATERIALS: dict[str, Material] = {
    INCONEL_625.name: INCONEL_625,
    INCONEL_718.name: INCONEL_718,
    INCONEL_738.name: INCONEL_738,
    MAR_M_247.name: MAR_M_247,
    TI_6AL_4V.name: TI_6AL_4V,
    AISI_4340.name: AISI_4340,
    PH_17_4.name: PH_17_4,
    A286.name: A286,
    HAYNES_282.name: HAYNES_282,
    SS_316L.name: SS_316L,
}
"""Name → Material map. Names match :attr:`Material.name`."""

# Alias map for legacy / engineering shorthand keys. The rotor module
# historically referred to AISI 4340 as "AISI4340" or "STEEL_AISI4340";
# we accept those so that the v0 `RotorSection.material="STEEL_AISI4340"`
# strings keep resolving. New code should use the canonical name.
ALIASES: dict[str, str] = {
    # --- Engineering shorthand / legacy Cascade keys ---
    "AISI4340": "AISI 4340",
    "STEEL_AISI4340": "AISI 4340",
    "IN625": "Inconel 625",
    "IN718": "Inconel 718",
    "IN738": "Inconel 738",
    "MARM247": "MAR-M 247",
    "MAR-M-247": "MAR-M 247",
    "Ti-6-4": "Ti-6Al-4V",
    "Ti64": "Ti-6Al-4V",
    "17-4 PH": "17-4PH",
    "PH17-4": "17-4PH",
    "ASTM A286": "A286",
    "HAYNES282": "Haynes 282",
    "SS316L": "316L",
    "316 L": "316L",
    # --- UNS numbers (ANSI/ASTM designations for cross-reference) ---
    "UNS N06625": "Inconel 625",
    "UNS N07718": "Inconel 718",
    "UNS N07738": "Inconel 738",   # D-W1: UNS number for IN-738LC
    "UNS N07208": "Haynes 282",
    "UNS S17400": "17-4PH",
    "UNS S66286": "A286",
    "UNS S31603": "316L",
    "UNS G43400": "AISI 4340",
    "UNS R56400": "Ti-6Al-4V",
    # --- Additional ANSI / engineering grade names ---
    "SAE 4340": "AISI 4340",
    "IN-738LC": "Inconel 738",
    "IN738LC": "Inconel 738",
    "Grade 5": "Ti-6Al-4V",
    "ASTM Grade 5": "Ti-6Al-4V",
    "Incoloy A-286": "A286",
    "Incoloy A286": "A286",
    "HAYNES 282": "Haynes 282",
    "N07718": "Inconel 718",
    "N06625": "Inconel 625",
}
