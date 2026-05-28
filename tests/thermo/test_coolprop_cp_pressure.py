"""ADAPT-006 regression — CoolPropPureFluid.cp() and .gamma() honour pressure.

Previously, the CoolProp wrapper hardcoded p = 101325 Pa inside its `CPMASS`
and `CVMASS` PropsSI calls regardless of the actual operating pressure. For
sCO2 at the critical point (305 K, 7.4 MPa) this returned cp ≈ 857 J/(kg·K)
when the real value is 16 328 J/(kg·K) — a 19× error.

This regression suite locks the contract that:
1. cp(T, p) at the critical point is huge (≳ 10 kJ/(kg·K)) for sCO2.
2. cp(T, p) far above the critical temperature drops back to a modest value.
3. cp depends explicitly on p for sCO2 (non-ideal Helmholtz EOS).
4. cp for NASA polynomials is independent of p (perfect-gas mixture).
5. The new FluidModel protocol signature is cp(T, p, composition) for both
   `CoolPropPureFluid` and `NasaFluid`.

Reference: ADAPT-006; CoolProp Span-Wagner 1996 CO2 EOS.
"""

from __future__ import annotations

import pytest

from cascade.cycle.fluid_model import CoolPropPureFluid, NasaFluid
from cascade.units import Composition, Q, Species


@pytest.fixture
def sco2_fluid() -> CoolPropPureFluid:
    return CoolPropPureFluid(Species.SCO2)


@pytest.fixture
def sco2_composition() -> Composition:
    return Composition.pure(Species.SCO2)


@pytest.fixture
def nasa_fluid() -> NasaFluid:
    return NasaFluid()


class TestCoolPropCpPressureDependence:
    """ADAPT-006: cp must be evaluated at the actual operating pressure."""

    def test_sco2_cp_at_critical_is_huge(
        self,
        sco2_fluid: CoolPropPureFluid,
        sco2_composition: Composition,
    ) -> None:
        """At T=305 K, p=7.4 MPa (near critical), cp(sCO2) ≈ 16 kJ/(kg·K).

        The pre-ADAPT-006 wrapper returned ~857 J/(kg·K) (cp at 1 atm).
        """
        cp = sco2_fluid.cp(
            Q(305.0, "K"), Q(7.4e6, "Pa"), sco2_composition
        )
        cp_val = cp.to("J/(kg*K)").magnitude
        assert 10_000 < cp_val < 30_000, (
            f"sCO2 near critical cp should be > 10 kJ/(kg·K), got {cp_val:.1f}"
        )

    def test_sco2_cp_far_from_critical_is_modest(
        self,
        sco2_fluid: CoolPropPureFluid,
        sco2_composition: Composition,
    ) -> None:
        """At T=500 K, p=7.4 MPa (T >> T_crit), cp(sCO2) ≈ 1.1 kJ/(kg·K)."""
        cp = sco2_fluid.cp(
            Q(500.0, "K"), Q(7.4e6, "Pa"), sco2_composition
        )
        cp_val = cp.to("J/(kg*K)").magnitude
        assert 1_000 < cp_val < 2_000, (
            f"sCO2 far from critical cp should be ~1 kJ/(kg·K), got {cp_val:.1f}"
        )

    def test_sco2_cp_depends_on_pressure(
        self,
        sco2_fluid: CoolPropPureFluid,
        sco2_composition: Composition,
    ) -> None:
        """cp(T=350 K, p=15 MPa) ≠ cp(T=350 K, p=8 MPa) — sCO2 is highly
        non-ideal in the supercritical regime.
        """
        cp_high_p = sco2_fluid.cp(
            Q(350.0, "K"), Q(15e6, "Pa"), sco2_composition
        ).to("J/(kg*K)").magnitude
        cp_lower_p = sco2_fluid.cp(
            Q(350.0, "K"), Q(8e6, "Pa"), sco2_composition
        ).to("J/(kg*K)").magnitude
        assert abs(cp_high_p - cp_lower_p) > 100, (
            f"sCO2 cp must vary with pressure; got cp(15 MPa)={cp_high_p:.1f}, "
            f"cp(8 MPa)={cp_lower_p:.1f}, diff={abs(cp_high_p - cp_lower_p):.1f}"
        )


class TestCoolPropGammaPressureDependence:
    """ADAPT-006: γ = cp/cv must use actual operating pressure."""

    def test_sco2_gamma_at_critical_is_large(
        self,
        sco2_fluid: CoolPropPureFluid,
        sco2_composition: Composition,
    ) -> None:
        """At T=305 K, p=7.4 MPa, γ(sCO2) >> 1.3 (cp diverges, cv stays finite).

        With the pre-ADAPT-006 wrapper γ at this state came out close to the
        ideal-gas value because both cp and cv were forced to atmospheric.
        """
        gamma = sco2_fluid.gamma(
            Q(305.0, "K"), Q(7.4e6, "Pa"), sco2_composition
        )
        # Real value is ~12.9; pre-fix would have been ~1.3.
        assert gamma > 5.0, (
            f"sCO2 γ at critical point should be much larger than ideal-gas "
            f"value (cp diverges); got γ = {gamma:.3f}"
        )

    def test_sco2_gamma_far_from_critical_is_reasonable(
        self,
        sco2_fluid: CoolPropPureFluid,
        sco2_composition: Composition,
    ) -> None:
        """At T=600 K, p=7.4 MPa, γ(sCO2) returns to a modest value."""
        gamma = sco2_fluid.gamma(
            Q(600.0, "K"), Q(7.4e6, "Pa"), sco2_composition
        )
        assert 1.1 < gamma < 1.5, (
            f"sCO2 γ far above critical should be near ideal-gas value; "
            f"got γ = {gamma:.3f}"
        )


class TestNasaCpPressureIndependent:
    """NASA-polynomial mixtures: cp truly does not depend on p (perfect-gas)."""

    def test_nasa_cp_independent_of_pressure(
        self,
        nasa_fluid: NasaFluid,
    ) -> None:
        """For NASA polynomials cp(T, p) at p=101325 Pa and p=1 MPa must match
        to machine precision: ideal-gas cp depends only on T and composition.
        """
        air = Composition.air()
        cp_lo = nasa_fluid.cp(
            Q(300.0, "K"), Q(101325.0, "Pa"), air
        ).to("J/(kg*K)").magnitude
        cp_hi = nasa_fluid.cp(
            Q(300.0, "K"), Q(1e6, "Pa"), air
        ).to("J/(kg*K)").magnitude
        assert abs(cp_lo - cp_hi) < 0.1, (
            f"NASA cp(T,p) must be independent of p (perfect-gas); "
            f"cp(1 atm)={cp_lo:.3f}, cp(1 MPa)={cp_hi:.3f}"
        )

    def test_nasa_gamma_independent_of_pressure(
        self,
        nasa_fluid: NasaFluid,
    ) -> None:
        """Same invariant for γ on NASA polynomials."""
        air = Composition.air()
        g_lo = nasa_fluid.gamma(Q(300.0, "K"), Q(101325.0, "Pa"), air)
        g_hi = nasa_fluid.gamma(Q(300.0, "K"), Q(1e6, "Pa"), air)
        assert abs(g_lo - g_hi) < 1e-9, (
            f"NASA γ(T,p) must be independent of p (perfect-gas); "
            f"γ(1 atm)={g_lo:.6f}, γ(1 MPa)={g_hi:.6f}"
        )


class TestProtocolSignature:
    """The new FluidModel protocol requires cp(T, p, composition) on all impls."""

    def test_coolprop_cp_requires_pressure(
        self,
        sco2_fluid: CoolPropPureFluid,
        sco2_composition: Composition,
    ) -> None:
        """Calling cp without a pressure argument must raise TypeError now."""
        with pytest.raises(TypeError):
            sco2_fluid.cp(Q(305.0, "K"), sco2_composition)  # type: ignore[call-arg]

    def test_nasa_cp_requires_pressure(self, nasa_fluid: NasaFluid) -> None:
        """Same protocol contract on NasaFluid."""
        with pytest.raises(TypeError):
            nasa_fluid.cp(Q(300.0, "K"), Composition.air())  # type: ignore[call-arg]
