"""CYC-1 validation: Çengel & Boles Example 9-5 — simple Brayton cycle.

Reference: Çengel, Y., Boles, M., *Thermodynamics: An Engineering Approach*,
9th ed., McGraw-Hill, 2019, Example 9-5 (p. 506-507 in the 9th edition;
the same example appears in editions 7-9 with identical numbers).

Case:
- Air-standard analysis (single fluid, no composition shift across burner)
- Inlet: 300 K, 100 kPa
- Compressor pressure ratio: 8
- Turbine inlet temperature: 1300 K
- Isentropic compressor and turbine (η = 1.0)
- Calorically perfect ideal gas: c_p = 1.005 kJ/(kg·K), γ = 1.4

Expected (closed-form, Çengel published):
- T_2 = 543.4 K
- T_3 = 1300 K (input)
- T_4 = 717.7 K
- W_c / ṁ = 244.6 kJ/kg
- W_t / ṁ = 585.2 kJ/kg
- W_net / ṁ = 340.6 kJ/kg
- Q_in / ṁ = 760.5 kJ/kg
- η_th ≈ 44.84% (Çengel published; closed-form 1 − 1/8^0.2857 = 44.79%)

Tolerance per SPEC_SHEET §12 Table: η_th within ±0.1 pt.
"""

from __future__ import annotations

import pytest

from cascade.cycle import (
    Burner,
    Compressor,
    IdealGasFluid,
    SimpleBraytonSpec,
    Turbine,
    solve_cycle,
)
from cascade.units import Composition, Port, Q


@pytest.fixture
def cengel_95_spec() -> SimpleBraytonSpec:
    """Build the Çengel 9-5 specification."""
    inlet = Port(
        pressure_total=Q(100.0, "kPa"),
        temperature_total=Q(300.0, "K"),
        mass_flow=Q(1.0, "kg/s"),
        composition=Composition.air(),
    )
    return SimpleBraytonSpec(
        inlet_port=inlet,
        compressor=Compressor(
            name="compressor",
            pressure_ratio=8.0,
            efficiency_isentropic=1.0,
        ),
        burner=Burner(
            name="burner",
            pressure_drop_fraction=0.0,
            combustion_efficiency=1.0,
            outlet_temperature=Q(1300.0, "K"),
            air_standard=True,
        ),
        turbine=Turbine(
            name="turbine",
            pressure_ratio=8.0,
            efficiency_isentropic=1.0,
        ),
        mechanical_efficiency=1.0,
        generator_efficiency=1.0,
    )


@pytest.fixture
def cengel_95_fluid() -> IdealGasFluid:
    """Çengel's air-standard fluid: c_p = 1.005 kJ/(kg·K), γ = 1.4."""
    return IdealGasFluid(cp=Q(1005.0, "J/(kg*K)"), gamma=1.4)


class TestCYC1ChannelStates:
    """Per-station temperature and work — the textbook closed-form values."""

    def test_compressor_exit_temperature(
        self,
        cengel_95_spec: SimpleBraytonSpec,
        cengel_95_fluid: IdealGasFluid,
    ) -> None:
        # T_2 = T_1 * (PR)^((γ-1)/γ) = 300 * 8^0.2857 = 543.4 K
        result = solve_cycle(cengel_95_spec, fluid=cengel_95_fluid)
        T_2 = result.ports["compressor"].temperature_total.to("K").magnitude
        assert T_2 == pytest.approx(543.4, abs=0.5)

    def test_turbine_exit_temperature(
        self,
        cengel_95_spec: SimpleBraytonSpec,
        cengel_95_fluid: IdealGasFluid,
    ) -> None:
        # T_4 = T_3 / (PR)^((γ-1)/γ) = 1300 / 1.8114 = 717.7 K
        result = solve_cycle(cengel_95_spec, fluid=cengel_95_fluid)
        T_4 = result.ports["turbine"].temperature_total.to("K").magnitude
        assert T_4 == pytest.approx(717.7, abs=0.5)

    def test_compressor_work(
        self,
        cengel_95_spec: SimpleBraytonSpec,
        cengel_95_fluid: IdealGasFluid,
    ) -> None:
        # W_c = c_p * (T_2 - T_1) = 1.005 * (543.4 - 300) = 244.6 kJ/kg
        result = solve_cycle(cengel_95_spec, fluid=cengel_95_fluid)
        # W_c stored as negative (input). Magnitude on per-kg basis:
        W_c_si = -result.shaft_work_components["compressor"].to("W").magnitude
        W_c_per_kg = W_c_si / 1.0  # ṁ = 1 kg/s
        assert W_c_per_kg / 1000.0 == pytest.approx(244.6, abs=1.0)

    def test_turbine_work(
        self,
        cengel_95_spec: SimpleBraytonSpec,
        cengel_95_fluid: IdealGasFluid,
    ) -> None:
        # W_t = c_p * (T_3 - T_4) = 1.005 * (1300 - 717.7) = 585.2 kJ/kg
        result = solve_cycle(cengel_95_spec, fluid=cengel_95_fluid)
        W_t_si = result.shaft_work_components["turbine"].to("W").magnitude
        W_t_per_kg = W_t_si / 1.0
        assert W_t_per_kg / 1000.0 == pytest.approx(585.2, abs=1.0)

    def test_net_work(
        self,
        cengel_95_spec: SimpleBraytonSpec,
        cengel_95_fluid: IdealGasFluid,
    ) -> None:
        # W_net = W_t - W_c = 585.2 - 244.6 = 340.6 kJ/kg
        result = solve_cycle(cengel_95_spec, fluid=cengel_95_fluid)
        assert result.specific_work.to("J/kg").magnitude / 1000.0 == pytest.approx(
            340.6, abs=1.0
        )

    def test_heat_input(
        self,
        cengel_95_spec: SimpleBraytonSpec,
        cengel_95_fluid: IdealGasFluid,
    ) -> None:
        # Q_in = c_p * (T_3 - T_2) = 1.005 * (1300 - 543.4) = 760.4 kJ/kg
        result = solve_cycle(cengel_95_spec, fluid=cengel_95_fluid)
        q_in_per_kg = result.heat_input.to("W").magnitude / 1.0
        assert q_in_per_kg / 1000.0 == pytest.approx(760.5, abs=1.0)


class TestCYC1ThermalEfficiency:
    """SPEC_SHEET §12: η_th within ±0.1 pt of Çengel's published 44.84%."""

    def test_thermal_efficiency_within_tolerance(
        self,
        cengel_95_spec: SimpleBraytonSpec,
        cengel_95_fluid: IdealGasFluid,
    ) -> None:
        result = solve_cycle(cengel_95_spec, fluid=cengel_95_fluid)
        eta_th_percent = result.thermal_efficiency * 100.0

        # SPEC_SHEET §12 tolerance: ±0.1 pt absolute.
        # Closed-form value is 44.79% (1 - 1/8^0.2857); Çengel's published
        # rounded value is 44.84%. Both lie within the ±0.1 pt envelope of
        # our prediction.
        assert eta_th_percent == pytest.approx(44.79, abs=0.1)

    def test_thermal_efficiency_against_closed_form(
        self,
        cengel_95_spec: SimpleBraytonSpec,
        cengel_95_fluid: IdealGasFluid,
    ) -> None:
        """Closed-form: η = 1 - 1/PR^((γ-1)/γ) for isentropic Brayton."""
        import math

        PR = 8.0  # noqa: N806
        gamma = 1.4
        eta_closed = 1.0 - 1.0 / (PR ** ((gamma - 1.0) / gamma))
        result = solve_cycle(cengel_95_spec, fluid=cengel_95_fluid)
        # Should match the closed form to numerical precision
        assert result.thermal_efficiency == pytest.approx(eta_closed, abs=1e-3)
        assert math.isclose(eta_closed, 0.4479, abs_tol=1e-3)


class TestCYC1PortContract:
    """SPEC_SHEET §3.1: every output is a typed `Port`."""

    def test_all_ports_typed(
        self,
        cengel_95_spec: SimpleBraytonSpec,
        cengel_95_fluid: IdealGasFluid,
    ) -> None:
        result = solve_cycle(cengel_95_spec, fluid=cengel_95_fluid)
        for name, port in result.ports.items():
            assert isinstance(port, Port), f"port '{name}' is not a Port"
            # All quantities are dimensioned (would raise if not)
            _ = port.pressure_total.to("Pa")
            _ = port.temperature_total.to("K")
            _ = port.mass_flow.to("kg/s")

    def test_efficiency_is_dimensionless(
        self,
        cengel_95_spec: SimpleBraytonSpec,
        cengel_95_fluid: IdealGasFluid,
    ) -> None:
        result = solve_cycle(cengel_95_spec, fluid=cengel_95_fluid)
        assert isinstance(result.thermal_efficiency, float)
        assert 0.0 < result.thermal_efficiency < 1.0

    def test_specific_work_carries_units(
        self,
        cengel_95_spec: SimpleBraytonSpec,
        cengel_95_fluid: IdealGasFluid,
    ) -> None:
        result = solve_cycle(cengel_95_spec, fluid=cengel_95_fluid)
        # Must be a Quantity convertible to J/kg
        _ = result.specific_work.to("J/kg")
        _ = result.specific_work.to("kJ/kg")
