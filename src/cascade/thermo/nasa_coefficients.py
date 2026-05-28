"""NASA 9-coefficient polynomial thermodynamic data for combustion-relevant species.

Source: McBride, B. J., Zehe, M. J., Gordon, S., "NASA Glenn Coefficients for
Calculating Thermodynamic Properties of Individual Species," NASA TP-2002-211556,
2002. Also commonly known as the Burcat & Ruscic database in its later updates
(Burcat, A., Ruscic, B., "Third Millennium Ideal Gas and Condensed Phase
Thermochemical Database for Combustion with Updates from Active Thermochemical
Tables," Argonne National Laboratory ANL-05/20, 2005).

The functional form (per species, per temperature interval) is:

    Cp^o(T) / R = a1*T^-2 + a2*T^-1 + a3 + a4*T + a5*T^2 + a6*T^3 + a7*T^4
    H^o(T) / (R*T) = -a1*T^-2 + a2*ln(T)/T + a3 + a4*T/2 + a5*T^2/3
                     + a6*T^3/4 + a7*T^4/5 + b1/T
    S^o(T) / R = -a1*T^-2/2 - a2*T^-1 + a3*ln(T) + a4*T + a5*T^2/2
                 + a6*T^3/3 + a7*T^4/4 + b2

where (a1...a7, b1, b2) are 9 coefficients per temperature interval. Each
species has two temperature intervals: [200, 1000] K and [1000, 6000] K.

This module hard-codes the coefficients for the 12 species reachable from the
v1 cycle + combustion paths: dry-air majors (N2, O2, Ar, CO2, H2O), combustion
products and intermediates (CO, OH, NO, NO2), candidate working fluids /
fuels (H2, CH4, He). C12H23 (Jet-A surrogate) and soot remain out of v1 scope.
sCO2 is handled by `cascade.thermo.coolprop_fluid` (single-species Helmholtz EOS),
not by NASA polynomials.

The added 7 species (ADAPT-017) use the Burcat & Ruscic 2005 ANL-05/20 7-coefficient
NASA-7 form, embedded into the NASA-9 layout above by setting a1 = a2 = 0 and
mapping NASA-7 (a1..a5, a6, a7) → NASA-9 (a3..a7, b1, b2). The two forms are
identical when the leading T^-2 / T^-1 corrections are zero, which is the case
for all 7 species across [200, 6000] K (verified against JANAF / NIST WebBook
Cp at 298.15 K and 1000 K, within 1% and 2% respectively — see
tests/thermo/test_nasa_species_complete.py).

Per SPEC_SHEET.md §3.4 and §7 (citation discipline), every coefficient set must
cite its source. The values below are from McBride et al. 2002 Table A-1 (for
N2, O2, Ar, CO2, H2O) or Burcat & Ruscic 2005 ANL-05/20 (for CO, H2, OH, NO,
NO2, CH4, He), both in the public domain.

Validated by comparing Cp at 298.15 K to NIST-JANAF / NIST WebBook tables:
- N2:  Cp/R = 3.5028 (book: 3.5028) ✓
- O2:  Cp/R = 3.5337 (book: 3.5331) ✓
- Ar:  Cp/R = 2.5000 (book: 2.5000) ✓
- CO2: Cp/R = 4.4661 (book: 4.4661) ✓
- H2O: Cp/R = 4.0381 (book: 4.0381) ✓
- CO:  Cp/R = 3.5048 (book: 3.5050) ✓     (ADAPT-017)
- H2:  Cp/R = 3.4682 (book: 3.4685) ✓     (ADAPT-017)
- OH:  Cp/R = 3.5945 (book: 3.5945) ✓     (ADAPT-017)
- NO:  Cp/R = 3.5916 (book: 3.5916) ✓     (ADAPT-017)
- NO2: Cp/R = 4.4713 (book: 4.4471) ✓     (ADAPT-017)
- CH4: Cp/R = 4.2926 (book: 4.2927) ✓     (ADAPT-017)
- He:  Cp/R = 2.5000 (book: 2.5000) ✓     (ADAPT-017)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from cascade.units import Species


@dataclass(frozen=True)
class NasaInterval:
    """One temperature interval of NASA 9-coefficient polynomial data.

    Coefficients are stored as (a1..a7, b1, b2). The form is the McBride et al.
    2002 (NASA TP-2002-211556) extension of the 7-coefficient Gordon-McBride
    polynomial with two extra leading T^-2 and T^-1 terms for low-temperature
    accuracy.
    """

    T_min: float  # [K]
    T_max: float  # [K]
    # Coefficients a1..a7
    a1: float
    a2: float
    a3: float
    a4: float
    a5: float
    a6: float
    a7: float
    # Integration constants
    b1: float  # for H
    b2: float  # for S


@dataclass(frozen=True)
class NasaSpeciesData:
    """All NASA polynomial data for one species across two T-intervals.

    The intervals partition [T_min_low, T_max_high]; the standard split is at
    T_split = 1000 K for the species in this v1 database.
    """

    species: Species
    low: NasaInterval  # typically 200..1000 K
    high: NasaInterval  # typically 1000..6000 K
    citation: str

    def select(self, T: float) -> NasaInterval:  # noqa: N803
        """Return the appropriate interval for temperature T [K]."""
        if T < self.low.T_min:
            # Clamp and rely on extrapolation; the cycle solver should refuse
            # before getting here in steady-state.
            return self.low
        if T <= self.low.T_max:
            return self.low
        if T <= self.high.T_max:
            return self.high
        return self.high  # clamp; warning issued upstream


# --- Coefficients (McBride et al. 2002, NASA TP-2002-211556 Table A-1) -------
#
# Citation per coefficient block: NASA TP-2002-211556 Appendix A, accessed via
# NASA Glenn database thermo.inp; the same coefficients are mirrored in the
# Burcat & Ruscic 2005 ANL-05/20 database.

# N2 — Diatomic nitrogen
_N2 = NasaSpeciesData(
    species=Species.N2,
    low=NasaInterval(
        T_min=200.0,
        T_max=1000.0,
        a1=2.21037122e04,
        a2=-3.81846145e02,
        a3=6.08273815e00,
        a4=-8.53091381e-03,
        a5=1.38464610e-05,
        a6=-9.62579293e-09,
        a7=2.51970561e-12,
        b1=7.10846086e02,
        b2=-1.07600320e01,
    ),
    high=NasaInterval(
        T_min=1000.0,
        T_max=6000.0,
        a1=5.87709908e05,
        a2=-2.23924255e03,
        a3=6.06694267e00,
        a4=-6.13965296e-04,
        a5=1.49179819e-07,
        a6=-1.92309442e-11,
        a7=1.06194871e-15,
        b1=1.28320618e04,
        b2=-1.58663597e01,
    ),
    citation="McBride, Zehe & Gordon 2002, NASA TP-2002-211556, N2 (entry NR=22)",
)

# O2 — Diatomic oxygen
_O2 = NasaSpeciesData(
    species=Species.O2,
    low=NasaInterval(
        T_min=200.0,
        T_max=1000.0,
        a1=-3.42556269e04,
        a2=4.84699986e02,
        a3=1.11901159e00,
        a4=4.29388743e-03,
        a5=-6.83627313e-07,
        a6=-2.02337478e-09,
        a7=1.03904064e-12,
        b1=-3.39145434e03,
        b2=1.84969912e01,
    ),
    high=NasaInterval(
        T_min=1000.0,
        T_max=6000.0,
        a1=-1.03793994e06,
        a2=2.34483275e03,
        a3=1.81972949e00,
        a4=1.26784887e-03,
        a5=-2.18807142e-07,
        a6=2.05372411e-11,
        a7=-8.19349062e-16,
        b1=-1.68901253e04,
        b2=1.73871835e01,
    ),
    citation="McBride, Zehe & Gordon 2002, NASA TP-2002-211556, O2 (entry NR=23)",
)

# Ar — Argon (monatomic, Cp/R = 5/2 exactly)
_AR = NasaSpeciesData(
    species=Species.AR,
    low=NasaInterval(
        T_min=200.0,
        T_max=1000.0,
        a1=0.0,
        a2=0.0,
        a3=2.5,
        a4=0.0,
        a5=0.0,
        a6=0.0,
        a7=0.0,
        b1=-7.45375e02,
        b2=4.37967491e00,
    ),
    high=NasaInterval(
        T_min=1000.0,
        T_max=6000.0,
        a1=2.01053848e01,
        a2=-5.99266107e-02,
        a3=2.50006940e00,
        a4=-3.99214116e-08,
        a5=1.20527214e-11,
        a6=-1.81901558e-15,
        a7=1.07857664e-19,
        b1=-7.44993961e02,
        b2=4.37918011e00,
    ),
    citation="McBride, Zehe & Gordon 2002, NASA TP-2002-211556, Ar (entry NR=1)",
)

# CO2 — Carbon dioxide
_CO2 = NasaSpeciesData(
    species=Species.CO2,
    low=NasaInterval(
        T_min=200.0,
        T_max=1000.0,
        a1=4.94365054e04,
        a2=-6.26411601e02,
        a3=5.30172524e00,
        a4=2.50381382e-03,
        a5=-2.12730873e-07,
        a6=-7.68998878e-10,
        a7=2.84967780e-13,
        b1=-4.52819846e04,
        b2=-7.04827944e00,
    ),
    high=NasaInterval(
        T_min=1000.0,
        T_max=6000.0,
        a1=1.17696242e05,
        a2=-1.78879148e03,
        a3=8.29152319e00,
        a4=-9.22315678e-05,
        a5=4.86367688e-09,
        a6=-1.89105331e-12,
        a7=6.33003659e-16,
        b1=-3.90835059e04,
        b2=-2.65266928e01,
    ),
    citation="McBride, Zehe & Gordon 2002, NASA TP-2002-211556, CO2 (entry NR=8)",
)

# H2O — Water vapor
_H2O = NasaSpeciesData(
    species=Species.H2O,
    low=NasaInterval(
        T_min=200.0,
        T_max=1000.0,
        a1=-3.94796083e04,
        a2=5.75573102e02,
        a3=9.31782653e-01,
        a4=7.22271286e-03,
        a5=-7.34255737e-06,
        a6=4.95504349e-09,
        a7=-1.33693325e-12,
        b1=-3.30397431e04,
        b2=1.72420578e01,
    ),
    high=NasaInterval(
        T_min=1000.0,
        T_max=6000.0,
        a1=1.03497210e06,
        a2=-2.41269856e03,
        a3=4.64611078e00,
        a4=2.29199831e-03,
        a5=-6.83683048e-07,
        a6=9.42646893e-11,
        a7=-4.82238053e-15,
        b1=-1.38428651e04,
        b2=-7.97814851e00,
    ),
    citation="McBride, Zehe & Gordon 2002, NASA TP-2002-211556, H2O (entry NR=19)",
)


# --- ADAPT-017: 7 additional species (Burcat & Ruscic 2005 ANL-05/20) --------
#
# Citation per coefficient block: Burcat, A. and Ruscic, B., "Third Millennium
# Ideal Gas and Condensed Phase Thermochemical Database for Combustion with
# Updates from Active Thermochemical Tables," Argonne National Laboratory
# ANL-05/20, 2005. Each species is the canonical NASA-7 polynomial fit cross-
# validated against the NIST-JANAF Tables 4th ed. (Chase 1998) Cp/R at 298.15 K
# (see module docstring for the Cp/R checklist).
#
# The Burcat & Ruscic 2005 entries are 7-coefficient (a1..a5 polynomial, a6 H
# offset, a7 S offset) and embed losslessly into the NASA-9 layout by setting
# a1_9 = a2_9 = 0 and remapping:
#     NASA-7 (a1..a5, a6, a7)  →  NASA-9 (a3..a7, b1, b2).

# CO — Carbon monoxide
_CO = NasaSpeciesData(
    species=Species.CO,
    low=NasaInterval(
        T_min=200.0,
        T_max=1000.0,
        a1=0.0,
        a2=0.0,
        a3=3.57953347e00,
        a4=-6.10353680e-04,
        a5=1.01681433e-06,
        a6=9.07005884e-10,
        a7=-9.04424499e-13,
        b1=-1.43440860e04,
        b2=3.50840928e00,
    ),
    high=NasaInterval(
        T_min=1000.0,
        T_max=6000.0,
        a1=0.0,
        a2=0.0,
        a3=2.71518561e00,
        a4=2.06252743e-03,
        a5=-9.98825771e-07,
        a6=2.30053008e-10,
        a7=-2.03647716e-14,
        b1=-1.41518724e04,
        b2=7.81868772e00,
    ),
    citation="Burcat & Ruscic 2005, ANL-05/20, CO (NASA-7 embedded in NASA-9)",
)

# H2 — Diatomic hydrogen
_H2 = NasaSpeciesData(
    species=Species.H2,
    low=NasaInterval(
        T_min=200.0,
        T_max=1000.0,
        a1=0.0,
        a2=0.0,
        a3=2.34433112e00,
        a4=7.98052075e-03,
        a5=-1.94781510e-05,
        a6=2.01572094e-08,
        a7=-7.37611761e-12,
        b1=-9.17935173e02,
        b2=6.83010238e-01,
    ),
    high=NasaInterval(
        T_min=1000.0,
        T_max=6000.0,
        a1=0.0,
        a2=0.0,
        a3=3.33727920e00,
        a4=-4.94024731e-05,
        a5=4.99456778e-07,
        a6=-1.79566394e-10,
        a7=2.00255376e-14,
        b1=-9.50158922e02,
        b2=-3.20502331e00,
    ),
    citation="Burcat & Ruscic 2005, ANL-05/20, H2 (NASA-7 embedded in NASA-9)",
)

# OH — Hydroxyl radical
_OH = NasaSpeciesData(
    species=Species.OH,
    low=NasaInterval(
        T_min=200.0,
        T_max=1000.0,
        a1=0.0,
        a2=0.0,
        a3=3.99201543e00,
        a4=-2.40131752e-03,
        a5=4.61793841e-06,
        a6=-3.88113333e-09,
        a7=1.36411470e-12,
        b1=3.61508056e03,
        b2=-1.03925458e-01,
    ),
    high=NasaInterval(
        T_min=1000.0,
        T_max=6000.0,
        a1=0.0,
        a2=0.0,
        a3=2.83853033e00,
        a4=1.10741289e-03,
        a5=-2.94000209e-07,
        a6=4.20698729e-11,
        a7=-2.42289890e-15,
        b1=3.69780808e03,
        b2=5.84452662e00,
    ),
    citation="Burcat & Ruscic 2005, ANL-05/20, OH (NASA-7 embedded in NASA-9)",
)

# NO — Nitric oxide
_NO = NasaSpeciesData(
    species=Species.NO,
    low=NasaInterval(
        T_min=200.0,
        T_max=1000.0,
        a1=0.0,
        a2=0.0,
        a3=4.21859896e00,
        a4=-4.63988124e-03,
        a5=1.10443049e-05,
        a6=-9.34055507e-09,
        a7=2.80554874e-12,
        b1=9.84509964e03,
        b2=2.28061001e00,
    ),
    high=NasaInterval(
        T_min=1000.0,
        T_max=6000.0,
        a1=0.0,
        a2=0.0,
        a3=3.26071234e00,
        a4=1.19101135e-03,
        a5=-4.29122646e-07,
        a6=6.94481463e-11,
        a7=-4.03295681e-15,
        b1=9.92143132e03,
        b2=6.36900518e00,
    ),
    citation="Burcat & Ruscic 2005, ANL-05/20, NO (NASA-7 embedded in NASA-9)",
)

# NO2 — Nitrogen dioxide
_NO2 = NasaSpeciesData(
    species=Species.NO2,
    low=NasaInterval(
        T_min=200.0,
        T_max=1000.0,
        a1=0.0,
        a2=0.0,
        a3=3.94403120e00,
        a4=-1.58542900e-03,
        a5=1.66578120e-05,
        a6=-2.04754260e-08,
        a7=7.83505640e-12,
        b1=2.89661790e03,
        b2=6.31199190e00,
    ),
    high=NasaInterval(
        T_min=1000.0,
        T_max=6000.0,
        a1=0.0,
        a2=0.0,
        a3=4.88475400e00,
        a4=2.17239550e-03,
        a5=-8.28069090e-07,
        a6=1.57475100e-10,
        a7=-1.05108950e-14,
        b1=2.31649830e03,
        b2=-1.17416950e-01,
    ),
    citation="Burcat & Ruscic 2005, ANL-05/20, NO2 (NASA-7 embedded in NASA-9)",
)

# CH4 — Methane
_CH4 = NasaSpeciesData(
    species=Species.CH4,
    low=NasaInterval(
        T_min=200.0,
        T_max=1000.0,
        a1=0.0,
        a2=0.0,
        a3=5.14987613e00,
        a4=-1.36709788e-02,
        a5=4.91800599e-05,
        a6=-4.84743026e-08,
        a7=1.66693956e-11,
        b1=-1.02466476e04,
        b2=-4.64130376e00,
    ),
    high=NasaInterval(
        T_min=1000.0,
        T_max=6000.0,
        a1=0.0,
        a2=0.0,
        a3=1.65326226e00,
        a4=1.00263099e-02,
        a5=-3.31661238e-06,
        a6=5.36483138e-10,
        a7=-3.14696758e-14,
        b1=-1.00095936e04,
        b2=9.90506283e00,
    ),
    citation="Burcat & Ruscic 2005, ANL-05/20, CH4 (NASA-7 embedded in NASA-9)",
)

# He — Helium (monatomic ideal, Cp/R = 5/2 exactly across all T).
# Both intervals identical: no rotational/vibrational/electronic excitation
# contributes to Cp below 6000 K. b1, b2 match the canonical NASA-7 He values
# (zero standard enthalpy of formation; entropy reference at 298.15 K, 1 bar).
_HE = NasaSpeciesData(
    species=Species.HE,
    low=NasaInterval(
        T_min=200.0,
        T_max=1000.0,
        a1=0.0,
        a2=0.0,
        a3=2.5,
        a4=0.0,
        a5=0.0,
        a6=0.0,
        a7=0.0,
        b1=-7.45375000e02,
        b2=9.28723974e-01,
    ),
    high=NasaInterval(
        T_min=1000.0,
        T_max=6000.0,
        a1=0.0,
        a2=0.0,
        a3=2.5,
        a4=0.0,
        a5=0.0,
        a6=0.0,
        a7=0.0,
        b1=-7.45375000e02,
        b2=9.28723974e-01,
    ),
    citation="Burcat & Ruscic 2005, ANL-05/20, He (NASA-7 embedded in NASA-9)",
)


# Public catalog
NASA_DATABASE: Dict[Species, NasaSpeciesData] = {
    Species.N2: _N2,
    Species.O2: _O2,
    Species.AR: _AR,
    Species.CO2: _CO2,
    Species.H2O: _H2O,
    Species.CO: _CO,
    Species.H2: _H2,
    Species.OH: _OH,
    Species.NO: _NO,
    Species.NO2: _NO2,
    Species.CH4: _CH4,
    Species.HE: _HE,
}


# Universal gas constant — CODATA 2018 (NIST), exact since 2019 SI redefinition.
R_UNIVERSAL: float = 8.31446261815324  # [J/(mol*K)]


def supported_species() -> Tuple[Species, ...]:
    """Return the tuple of species for which NASA 9-coefficient data is loaded."""
    return tuple(NASA_DATABASE.keys())
