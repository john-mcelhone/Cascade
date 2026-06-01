"""Independent verification — 0D Brayton cycle thermodynamics.

Oracles are textbook closed-form relations, not Cascade internals:
  - Ideal (cold-air-standard) Brayton:  eta = 1 - PR^-((g-1)/g)   [depends ONLY on PR]
  - Non-ideal air-standard Brayton with component isentropic efficiencies
  - Ideal recuperated Brayton with effectiveness eps
  - Carnot upper bound: eta < 1 - T_min/T_max
  - First-law accounting: eta == W_net / Q_in

References: Cengel & Boles, Thermodynamics: An Engineering Approach, Ch. 9;
Saravanamuttoo, Rogers & Cohen, Gas Turbine Theory, Ch. 2.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _inputs import air_inlet  # noqa: E402

from cascade.cycle import (  # noqa: E402
    Burner,
    Compressor,
    IdealGasFluid,
    NasaFluid,
    Recuperator,
    RecuperatedBraytonSpec,
    SimpleBraytonSpec,
    Turbine,
    solve_cycle,
    solve_recuperated_brayton,
)
from cascade.units import Composition, Port, Q  # noqa: E402

GAMMA = 1.4
CP = 1005.0
FLUID = IdealGasFluid(cp=Q(CP, "J/(kg*K)"), gamma=GAMMA)


def _simple_spec(pr: float, t3: float, eta_c: float = 1.0, eta_t: float = 1.0) -> SimpleBraytonSpec:
    return SimpleBraytonSpec(
        inlet_port=air_inlet(t_k=300.0),
        compressor=Compressor(name="c", pressure_ratio=pr, efficiency_isentropic=eta_c),
        burner=Burner(
            name="b", pressure_drop_fraction=0.0, combustion_efficiency=1.0,
            outlet_temperature=Q(t3, "K"), air_standard=True,
        ),
        turbine=Turbine(name="t", pressure_ratio=pr, efficiency_isentropic=eta_t),
    )


def _closed_simple(pr: float, t1: float, t3: float, eta_c: float, eta_t: float) -> float:
    k = pr ** ((GAMMA - 1.0) / GAMMA)
    t2 = t1 + (t1 * k - t1) / eta_c
    t4 = t3 - eta_t * (t3 - t3 / k)
    w_net = CP * ((t3 - t4) - (t2 - t1))
    q_in = CP * (t3 - t2)
    return w_net / q_in


# --- Ideal Brayton: closed form depends only on PR -------------------------


@pytest.mark.parametrize("pr", [4.0, 8.0, 16.0, 25.0])
def test_ideal_brayton_efficiency_matches_closed_form(pr: float) -> None:
    """Isentropic Brayton: eta == 1 - PR^-((g-1)/g), exact for an ideal gas."""
    eta_expected = 1.0 - pr ** (-(GAMMA - 1.0) / GAMMA)
    res = solve_cycle(_simple_spec(pr, t3=1300.0), fluid=FLUID)
    assert res.converged
    assert res.thermal_efficiency == pytest.approx(eta_expected, abs=2e-3)


def test_ideal_brayton_efficiency_independent_of_turbine_inlet_temperature() -> None:
    """A fundamental property: ideal Brayton eta is a function of PR alone."""
    eta_a = solve_cycle(_simple_spec(10.0, t3=1100.0), fluid=FLUID).thermal_efficiency
    eta_b = solve_cycle(_simple_spec(10.0, t3=1600.0), fluid=FLUID).thermal_efficiency
    assert eta_a == pytest.approx(eta_b, abs=2e-3)


def test_ideal_brayton_efficiency_increases_with_pressure_ratio() -> None:
    etas = [solve_cycle(_simple_spec(pr, 1300.0), fluid=FLUID).thermal_efficiency
            for pr in (3.0, 6.0, 12.0, 24.0)]
    for lo, hi in zip(etas, etas[1:]):
        assert hi > lo


# --- Non-ideal Brayton ------------------------------------------------------


@pytest.mark.parametrize(
    ("pr", "t3", "eta_c", "eta_t"),
    [(10.0, 1400.0, 0.85, 0.88), (6.0, 1200.0, 0.82, 0.86), (15.0, 1500.0, 0.88, 0.90)],
)
def test_nonideal_brayton_matches_air_standard_closed_form(
    pr: float, t3: float, eta_c: float, eta_t: float
) -> None:
    expected = _closed_simple(pr, 300.0, t3, eta_c, eta_t)
    res = solve_cycle(_simple_spec(pr, t3, eta_c, eta_t), fluid=FLUID)
    assert res.thermal_efficiency == pytest.approx(expected, abs=3e-3)


# --- Carnot bound (safety invariant) ---------------------------------------


@pytest.mark.parametrize(
    ("pr", "t3", "eta_c", "eta_t"),
    [(8.0, 1300.0, 1.0, 1.0), (10.0, 1400.0, 0.85, 0.88), (20.0, 1600.0, 0.9, 0.9)],
)
def test_thermal_efficiency_below_carnot(pr: float, t3: float, eta_c: float, eta_t: float) -> None:
    res = solve_cycle(_simple_spec(pr, t3, eta_c, eta_t), fluid=FLUID)
    carnot = 1.0 - 300.0 / t3
    assert 0.0 < res.thermal_efficiency < carnot


# --- First-law accounting consistency --------------------------------------


def test_thermal_efficiency_equals_net_work_over_heat_input() -> None:
    res = solve_cycle(_simple_spec(12.0, 1450.0, 0.86, 0.89), fluid=FLUID)
    q_in = res.heat_input.to("W").magnitude
    w_net = res.net_shaft_work.to("W").magnitude
    assert q_in > 0
    assert res.thermal_efficiency == pytest.approx(w_net / q_in, rel=1e-3)


def test_specific_work_consistent_with_net_work_and_massflow() -> None:
    res = solve_cycle(_simple_spec(10.0, 1400.0, 0.85, 0.88), fluid=FLUID)
    # inlet mass flow is 1 kg/s, so specific work == net shaft work numerically
    w_net = res.net_shaft_work.to("W").magnitude
    w_sp = res.specific_work.to("J/kg").magnitude
    assert w_sp == pytest.approx(w_net, rel=2e-2)
    assert w_sp > 0  # a viable power cycle does net positive work


# --- Recuperated Brayton ----------------------------------------------------


def _recup_spec(pr: float, t3: float, eps: float) -> RecuperatedBraytonSpec:
    return RecuperatedBraytonSpec(
        inlet_port=air_inlet(t_k=300.0),
        compressor=Compressor(name="c", pressure_ratio=pr, efficiency_isentropic=1.0),
        burner=Burner(name="b", pressure_drop_fraction=0.0, combustion_efficiency=1.0,
                      outlet_temperature=Q(t3, "K"), air_standard=True),
        turbine=Turbine(name="t", pressure_ratio=pr, efficiency_isentropic=1.0),
        recuperator=Recuperator(name="r", effectiveness=eps,
                                cold_pressure_drop_fraction=0.0, hot_pressure_drop_fraction=0.0),
    )


def _closed_recup(pr: float, t1: float, t3: float, eps: float) -> float:
    k = pr ** ((GAMMA - 1.0) / GAMMA)
    t2 = t1 * k
    t4 = t3 / k
    w_net = CP * ((t3 - t4) - (t2 - t1))
    q_in = CP * (t3 - t2 - eps * (t4 - t2))
    return w_net / q_in


@pytest.mark.parametrize(("pr", "t3", "eps"), [(4.0, 1300.0, 0.8), (5.0, 1400.0, 0.7), (3.0, 1200.0, 0.85)])
def test_recuperated_matches_closed_form(pr: float, t3: float, eps: float) -> None:
    expected = _closed_recup(pr, 300.0, t3, eps)
    res = solve_recuperated_brayton(_recup_spec(pr, t3, eps), FLUID)
    assert res.thermal_efficiency == pytest.approx(expected, abs=3e-3)
    assert res.thermal_efficiency < 1.0 - 300.0 / t3  # still below Carnot


def test_recuperation_raises_efficiency_at_low_pressure_ratio() -> None:
    """At a low PR where T4 > T2, regeneration must raise thermal efficiency."""
    pr, t3 = 4.0, 1300.0
    eta_simple = solve_cycle(_simple_spec(pr, t3), fluid=FLUID).thermal_efficiency
    eta_recup = solve_recuperated_brayton(_recup_spec(pr, t3, 0.8), FLUID).thermal_efficiency
    assert eta_recup > eta_simple


def test_recuperator_efficiency_monotonic_in_effectiveness() -> None:
    etas = [solve_recuperated_brayton(_recup_spec(4.0, 1300.0, eps), FLUID).thermal_efficiency
            for eps in (0.2, 0.5, 0.8, 0.95)]
    for lo, hi in zip(etas, etas[1:]):
        assert hi > lo


# --- Real-combustion path: conservation laws (air_standard=False) -----------

LHV = 50.0e6
ETA_COMB = 0.99


def _combustion_spec() -> SimpleBraytonSpec:
    inlet = Port(pressure_total=Q(101.325, "kPa"), temperature_total=Q(288.15, "K"),
                 mass_flow=Q(2.0, "kg/s"), composition=Composition.air())
    return SimpleBraytonSpec(
        inlet_port=inlet,
        compressor=Compressor(name="c", pressure_ratio=10.0, efficiency_isentropic=0.85),
        burner=Burner(name="b", pressure_drop_fraction=0.03, combustion_efficiency=ETA_COMB,
                      outlet_temperature=Q(1400.0, "K"), air_standard=False,
                      fuel_lhv=Q(LHV, "J/kg")),
        turbine=Turbine(name="t", pressure_ratio=10.0 / 1.03, efficiency_isentropic=0.88),
    )


@pytest.mark.parametrize("fluid", [IdealGasFluid(), NasaFluid()])
def test_combustion_conserves_mass(fluid) -> None:  # noqa: ANN001
    """Conservation of mass across the burner: turbine flow = air + fuel."""
    r = solve_cycle(_combustion_spec(), fluid=fluid)
    m_fuel = r.fuel_mass_flow.to("kg/s").magnitude
    m_turbine = r.ports["t"].mass_flow.to("kg/s").magnitude
    assert m_fuel > 0.0
    assert m_turbine == pytest.approx(2.0 + m_fuel, rel=1e-6)


@pytest.mark.parametrize("fluid", [IdealGasFluid(), NasaFluid()])
def test_combustion_heat_input_matches_fuel_energy(fluid) -> None:  # noqa: ANN001
    """First law at the burner: Q_in = m_fuel * LHV * combustion_efficiency."""
    r = solve_cycle(_combustion_spec(), fluid=fluid)
    m_fuel = r.fuel_mass_flow.to("kg/s").magnitude
    q_in = r.heat_input.to("W").magnitude
    assert q_in == pytest.approx(m_fuel * LHV * ETA_COMB, rel=1e-3)


@pytest.mark.parametrize("fluid", [IdealGasFluid(), NasaFluid()])
def test_combustion_products_composition_normalized(fluid) -> None:  # noqa: ANN001
    """Mass fractions of the combustion products must be a valid distribution."""
    r = solve_cycle(_combustion_spec(), fluid=fluid)
    comp = r.ports["t"].composition
    fracs = comp.mass_fractions if hasattr(comp, "mass_fractions") else comp
    values = list(fracs.values())
    assert all(-1e-9 <= v <= 1.0 + 1e-9 for v in values)
    assert sum(values) == pytest.approx(1.0, abs=1e-6)
