"""ADAPT-029 regression — NasaMixture refuses negative mass fractions.

Previously, a composition like Y_N2=1.1, Y_O2=-0.1 passed the existing
sum-to-1 check (its components do sum to 1.0) and the resulting mixture
silently produced wrong cp/h/s. Mass fractions are physical quantities
and must be ≥ 0.

The fix lives in `cascade.thermo.nasa_mixture._check_composition`; this
test drives it through the public NasaMixture interface.
"""

from __future__ import annotations

import pytest

from cascade.thermo.nasa_mixture import NasaMixture
from cascade.units import Composition, Q, Species


@pytest.fixture
def nasa() -> NasaMixture:
    return NasaMixture()


class TestNasaMixtureNegativeFractionRefusal:
    def test_negative_fraction_with_unit_sum_refused(
        self, nasa: NasaMixture
    ) -> None:
        """The original failing case: Y_N2=1.1, Y_O2=-0.1 sums to 1 but
        is unphysical."""
        # Composition itself sums to 1, so its own check passes — that is
        # exactly why we need the NasaMixture-level guard.
        bad = Composition(
            mass_fractions={Species.N2: 1.1, Species.O2: -0.1}
        )
        with pytest.raises(ValueError, match="negative mass fraction"):
            nasa.cp(Q(300.0, "K"), bad)

    def test_pure_n2_works(self, nasa: NasaMixture) -> None:
        comp = Composition(mass_fractions={Species.N2: 1.0})
        cp_val = nasa.cp(Q(300.0, "K"), comp)
        # N2 cp ≈ 1040 J/(kg*K) near room temp
        assert 900.0 < cp_val.to("J/(kg*K)").magnitude < 1200.0

    def test_air_works(self, nasa: NasaMixture) -> None:
        """Y_N2=0.79, Y_O2=0.21 sums to 1, all non-negative — valid."""
        comp = Composition(
            mass_fractions={Species.N2: 0.79, Species.O2: 0.21}
        )
        cp_val = nasa.cp(Q(300.0, "K"), comp)
        # Air cp ≈ 1005 J/(kg*K)
        assert 900.0 < cp_val.to("J/(kg*K)").magnitude < 1100.0

    def test_sum_not_one_refused_at_composition_construction(self) -> None:
        """Y_N2=0.5, Y_O2=0.4 sums to 0.9 — caught at Composition init."""
        with pytest.raises(ValueError, match="sum to 1"):
            Composition(
                mass_fractions={Species.N2: 0.5, Species.O2: 0.4}
            )
