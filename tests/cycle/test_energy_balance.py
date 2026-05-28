"""Regression tests for the cycle energy-balance report (ADAPT-012).

Documents the sensible-enthalpy convention used by the Cascade cycle solver
and verifies that both the sensible AND the absolute balance close to
numerical precision for the canonical Capstone C30 case. Without these tests
an auditor summing absolute enthalpies across the cycle would see a phantom
~115 kW mismatch on Capstone — see `cascade.cycle.solver` module docstring
for the full Walsh-Fletcher (2004 §3) explanation.
"""

from __future__ import annotations

import pytest

from cascade.cycle import (
    NasaFluid,
    RecuperatedBraytonSpec,
    SimpleBraytonSpec,
    energy_balance_report,
    solve_cycle,
)
from cascade.cycle.components import (
    Burner,
    Compressor,
    ConstantPressureLoss,
    Recuperator,
    Turbine,
)
from cascade.units import Composition, Port, Q
from cascade.validation.cases.capstone_c30 import CapstoneC30


def _build_capstone_spec() -> RecuperatedBraytonSpec:
    """Build the Capstone C30 spec from the canonical source of truth."""
    c = CapstoneC30
    inlet = Port(
        pressure_total=c.p_ambient,
        temperature_total=c.T_ambient,
        mass_flow=c.mass_flow,
        composition=Composition.air(),
    )
    return RecuperatedBraytonSpec(
        inlet_port=inlet,
        inlet_loss=ConstantPressureLoss(
            name="inlet_loss",
            pressure_drop_fraction=c.pdrop_inlet,
        ),
        compressor=Compressor(
            name="compressor",
            pressure_ratio=c.pressure_ratio,
            efficiency_isentropic=c.eta_compressor_isen,
        ),
        burner=Burner(
            name="burner",
            pressure_drop_fraction=c.pdrop_burner,
            combustion_efficiency=c.combustion_efficiency,
            outlet_temperature=c.TIT,
            fuel_lhv=c.fuel_LHV.to("J/kg"),
            fuel_carbon_atoms=c.fuel_carbon_atoms,
            fuel_hydrogen_atoms=c.fuel_hydrogen_atoms,
            fuel_molar_mass=c.fuel_molar_mass,
            fuel_inlet_temperature=c.fuel_inlet_temperature,
            air_standard=False,
        ),
        turbine=Turbine(
            name="turbine",
            pressure_ratio=c.turbine_pressure_ratio(),
            efficiency_isentropic=c.eta_turbine_isen,
        ),
        recuperator=Recuperator(
            name="recuperator",
            effectiveness=c.recuperator_effectiveness,
            cold_pressure_drop_fraction=c.pdrop_recup_cold,
            hot_pressure_drop_fraction=c.pdrop_recup_hot,
        ),
        mechanical_efficiency=c.eta_mechanical,
        generator_efficiency=c.eta_generator,
    )


def test_capstone_sensible_balance_closes() -> None:
    """Sensible-enthalpy balance closes to < 1e-3 kW for the canonical Capstone case."""
    spec = _build_capstone_spec()
    fluid = NasaFluid()
    result = solve_cycle(spec, fluid=fluid)
    rpt = energy_balance_report(spec, result, fluid=fluid)
    # Sensible balance: every joule accounted for
    assert abs(rpt.sensible_balance_residual) < 1e-3, (
        f"sensible residual = {rpt.sensible_balance_residual}"
    )
    # Absolute balance: also closes (LHV correctly attributed to the burner)
    assert abs(rpt.absolute_balance_residual) < 1e-3, (
        f"absolute residual = {rpt.absolute_balance_residual}"
    )
    # Sanity: net fluid-side work matches the result's reported net shaft work
    # AFTER accounting for mechanical efficiency (shaft-side correction is
    # applied to W_t before subtracting W_c in the solver — see
    # `solve_recuperated_brayton`).
    net_work_fluid_side = (
        rpt.turbine_work_out * spec.mechanical_efficiency
        - rpt.compressor_work_in
    )
    assert abs(net_work_fluid_side - result.net_shaft_work.to("kW").magnitude) < 0.1
    # Sanity: report includes the convention name
    assert "sensible" in rpt.convention.lower()


def test_capstone_report_str_contains_capstone_magnitudes() -> None:
    """The __str__ representation surfaces the customer-visible numbers."""
    spec = _build_capstone_spec()
    fluid = NasaFluid()
    result = solve_cycle(spec, fluid=fluid)
    rpt = energy_balance_report(spec, result, fluid=fluid)
    s = str(rpt)
    # Convention is named so an auditor can look it up
    assert "Walsh-Fletcher" in s
    # Layout names every column
    for label in (
        "Inlet sensible",
        "Compressor work in",
        "Burner chemical input",
        "Recuperator transfer",
        "Turbine work out",
        "Exhaust sensible",
        "Sensible residual",
        "Absolute residual",
    ):
        assert label in s, f"Report __str__ missing label: {label!r}"
    # Capstone chemical input is ~115 kW (30 kW / 0.26 thermal efficiency).
    # Use the report's own field rather than parsing the string.
    assert 100.0 < rpt.burner_chemical_input < 130.0, (
        f"chemical input out of range: {rpt.burner_chemical_input}"
    )


def test_capstone_recuperator_transfer_is_positive_and_significant() -> None:
    """The recuperator must actually transfer heat — Capstone runs hot at the
    turbine exit (>800 K) and pre-heats compressor discharge to >800 K."""
    spec = _build_capstone_spec()
    fluid = NasaFluid()
    result = solve_cycle(spec, fluid=fluid)
    rpt = energy_balance_report(spec, result, fluid=fluid)
    # Should be tens of kW for a microturbine of this size (Q_recup ~ 113 kW
    # for the canonical case — comparable to the heat input itself).
    assert rpt.recuperator_heat_xfer > 50.0
    assert rpt.recuperator_heat_xfer < 200.0


def test_simple_brayton_balance_closes() -> None:
    """The same convention applies to SimpleBraytonSpec (no recuperator)."""
    c = CapstoneC30
    inlet = Port(
        pressure_total=c.p_ambient,
        temperature_total=c.T_ambient,
        mass_flow=c.mass_flow,
        composition=Composition.air(),
    )
    spec = SimpleBraytonSpec(
        inlet_port=inlet,
        compressor=Compressor(
            name="compressor",
            pressure_ratio=c.pressure_ratio,
            efficiency_isentropic=c.eta_compressor_isen,
        ),
        burner=Burner(
            name="burner",
            pressure_drop_fraction=c.pdrop_burner,
            combustion_efficiency=c.combustion_efficiency,
            outlet_temperature=c.TIT,
            fuel_lhv=c.fuel_LHV.to("J/kg"),
            fuel_carbon_atoms=c.fuel_carbon_atoms,
            fuel_hydrogen_atoms=c.fuel_hydrogen_atoms,
            fuel_molar_mass=c.fuel_molar_mass,
            fuel_inlet_temperature=c.fuel_inlet_temperature,
            air_standard=False,
        ),
        turbine=Turbine(
            name="turbine",
            # SimpleBrayton has no recuperator/inlet pressure losses, so
            # PR_t = PR_c · (1 − pdrop_burner) ≈ 3.84 for this case.
            pressure_ratio=c.pressure_ratio * (1.0 - c.pdrop_burner),
            efficiency_isentropic=c.eta_turbine_isen,
        ),
        mechanical_efficiency=1.0,
        generator_efficiency=1.0,
    )
    fluid = NasaFluid()
    result = solve_cycle(spec, fluid=fluid)
    rpt = energy_balance_report(spec, result, fluid=fluid)
    assert abs(rpt.sensible_balance_residual) < 1e-3
    assert abs(rpt.absolute_balance_residual) < 1e-3
    # SimpleBrayton has no recuperator
    assert rpt.recuperator_heat_xfer == 0.0
