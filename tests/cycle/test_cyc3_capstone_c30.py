"""CYC-3 validation: Capstone C30 microturbine — recuperated Brayton.

Reference: Capstone Turbine Corporation, "Capstone C30 Technical Data Sheets,"
2002–2024 (publicly available). Additional cycle-parameter context from:
- McDonald, C. F., "Recuperator development trends for high efficiency small
  gas turbines," ASME paper GT2003-38570, 2003 (citing C30 ε ≈ 0.87).
- McDonald, C. F., Rodgers, C., "Small recuperated ceramic microturbine
  demonstrator concept," Applied Thermal Engineering 28, 2008, pp. 60-74.
- Boyce, M. P., *Gas Turbine Engineering Handbook* 4th ed. Ch. 18 (microturbine
  chapter; documents 95% generator efficiency for Capstone-class PMAs).

Case (the customer regime):
- ISO sea-level inlet: 288.15 K, 101.325 kPa, dry air.
- Compressor pressure ratio: 4.0 (single-stage centrifugal).
- Turbine inlet temperature: 1116 K (843 °C) — McDonald 2003 estimate.
- Recuperator effectiveness: 0.87 (McDonald 2003 GT-2003-38570).
- Component efficiencies (microturbine class):
  - Centrifugal compressor: η = 0.78 (high end of microturbine range).
  - Radial turbine: η = 0.84 (0.86 is upper bound).
  - Mechanical: η_mech = 0.95.
  - Generator (PMA): η_gen = 0.95 (Boyce §18).
- Pressure drops: inlet 2%, recup cold/hot 3% each, burner 4% (Walsh &
  Fletcher §5.10).
- Fuel: methane (CH4), LHV = 50 MJ/kg, η_comb = 99.5%.

Capstone published spec:
- Electrical output: 28 kW net.
- Electrical efficiency: 26% (LHV).
- Mass flow: 0.31 kg/s.
- TIT: 843 °C (= 1116 K).

Expected (this cycle code, the spec above):
- η_electrical = 26.09% (within ±1.5 pt of 26%)
- η_thermal    = 27.46% (within ±1.5 pt of 27.4% = 26%/0.95)
- W_electrical = 29.7 kW (within ±2 kW of 28 kW)

Tolerance per SPEC_SHEET §12 (revised per SR-002): η_th within ±1.5 pt absolute.

This test is marked `validation` per SPEC_SHEET §12 — it's part of the public
pass-gate suite.
"""

from __future__ import annotations

import pytest

from cascade.cycle import (
    Burner,
    Compressor,
    ConstantPressureLoss,
    NasaFluid,
    RecuperatedBraytonSpec,
    Recuperator,
    Turbine,
    solve_cycle,
)
from cascade.units import Composition, Port, Q
from cascade.validation.cases.capstone_c30 import CapstoneC30


# Pressure drops (re-exported from CapstoneC30 for downstream refusal-test reuse)
PDROP_INLET: float = CapstoneC30.pdrop_inlet
PDROP_COLD: float = CapstoneC30.pdrop_recup_cold
PDROP_BURNER: float = CapstoneC30.pdrop_burner
PDROP_HOT: float = CapstoneC30.pdrop_recup_hot


def _build_c30_spec() -> RecuperatedBraytonSpec:
    """Build the Capstone C30 recuperated-Brayton specification.

    All parameters are pulled from `cascade.validation.cases.capstone_c30`,
    the canonical Capstone C30 source of truth (ADAPT-018).
    """
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
            air_standard=False,  # real-gas composition shift across burner
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


@pytest.fixture
def c30_spec() -> RecuperatedBraytonSpec:
    return _build_c30_spec()


@pytest.fixture
def real_gas_fluid() -> NasaFluid:
    """Real-gas NASA-polynomial mixture (default for combustion products)."""
    return NasaFluid()


@pytest.mark.validation
class TestCYC3CapstoneC30:
    """SPEC_SHEET §12 pass-gate: Capstone C30 within ±1.5 pt η_th.

    This is the load-bearing validation case for the American Turbines
    microturbine customer profile.
    """

    def test_solver_converges(
        self,
        c30_spec: RecuperatedBraytonSpec,
        real_gas_fluid: NasaFluid,
    ) -> None:
        """Solver must converge to default tolerance."""
        result = solve_cycle(c30_spec, fluid=real_gas_fluid)
        assert result.converged, (
            f"solver did not converge: residual={result.residual_norm:.3e}, "
            f"iters={result.outer_iterations}"
        )
        assert result.outer_iterations <= 20

    def test_thermal_efficiency_within_tolerance(
        self,
        c30_spec: RecuperatedBraytonSpec,
        real_gas_fluid: NasaFluid,
    ) -> None:
        """SPEC_SHEET §12 CYC-3: η_th within ±1.5 pt of Capstone-derived target.

        Capstone publishes η_electrical = 26% (LHV). With η_generator = 0.95
        (Boyce §18), the corresponding thermal efficiency is 26/0.95 = 27.4%.
        Tolerance per SR-002 revision: ±1.5 pt absolute.
        """
        result = solve_cycle(c30_spec, fluid=real_gas_fluid)
        eta_th_pct = result.thermal_efficiency * 100.0
        target = CapstoneC30.target_eta_thermal * 100.0
        tol_pct = CapstoneC30.tolerance_eta_pt * 100.0
        assert eta_th_pct == pytest.approx(target, abs=tol_pct)

    def test_electrical_efficiency_within_tolerance(
        self,
        c30_spec: RecuperatedBraytonSpec,
        real_gas_fluid: NasaFluid,
    ) -> None:
        """η_electrical = 26% ± 1.5 pt (Capstone published value)."""
        result = solve_cycle(c30_spec, fluid=real_gas_fluid)
        eta_e_pct = result.electrical_efficiency * 100.0
        target = CapstoneC30.target_eta_electric * 100.0
        tol_pct = CapstoneC30.tolerance_eta_pt * 100.0
        assert eta_e_pct == pytest.approx(target, abs=tol_pct)

    def test_electrical_output_within_tolerance(
        self,
        c30_spec: RecuperatedBraytonSpec,
        real_gas_fluid: NasaFluid,
    ) -> None:
        """Capstone C30 net output: 28 kW (informational; ±2.5 kW tolerance)."""
        result = solve_cycle(c30_spec, fluid=real_gas_fluid)
        W_e_kW = result.electrical_output.to("kW").magnitude  # noqa: N806
        target_kW = CapstoneC30.target_power_net.to("kW").magnitude  # noqa: N806
        assert W_e_kW == pytest.approx(target_kW, abs=CapstoneC30.tolerance_power_kW)

    def test_tit_preserved(
        self,
        c30_spec: RecuperatedBraytonSpec,
        real_gas_fluid: NasaFluid,
    ) -> None:
        """Turbine inlet (= burner outlet) T = 1116 K as specified."""
        result = solve_cycle(c30_spec, fluid=real_gas_fluid)
        T_4 = result.ports["burner"].temperature_total.to("K").magnitude
        TIT_K = CapstoneC30.TIT.to("K").magnitude  # noqa: N806
        assert T_4 == pytest.approx(TIT_K, abs=1.0)

    def test_recuperator_pinch_safe(
        self,
        c30_spec: RecuperatedBraytonSpec,
        real_gas_fluid: NasaFluid,
    ) -> None:
        """Recuperator hot-out T must exceed cold-in T (2nd Law)."""
        result = solve_cycle(c30_spec, fluid=real_gas_fluid)
        T_cold_in = (
            result.ports["compressor"].temperature_total.to("K").magnitude
        )
        T_hot_out = (
            result.ports["recuperator_hot_out"]
            .temperature_total.to("K")
            .magnitude
        )
        assert T_hot_out > T_cold_in, (
            f"2nd Law violation: T_hot_out={T_hot_out} K ≤ T_cold_in={T_cold_in} K"
        )

    def test_combustion_products_composition_shift(
        self,
        c30_spec: RecuperatedBraytonSpec,
        real_gas_fluid: NasaFluid,
    ) -> None:
        """Burner outlet composition contains CO2 and H2O (combustion products)."""
        from cascade.units import Species

        result = solve_cycle(c30_spec, fluid=real_gas_fluid)
        prod_comp = result.ports["burner"].composition
        # Combustion of CH4: CH4 + 2 O2 → CO2 + 2 H2O. Products should contain
        # nonzero CO2 and H2O (vs. trace amounts in inlet air).
        assert prod_comp.get(Species.CO2) > 0.005  # ≥ 0.5% (lean burn)
        assert prod_comp.get(Species.H2O) > 0.003  # ≥ 0.3%
        # O2 must drop relative to inlet (air ~23.1% by mass)
        assert prod_comp.get(Species.O2) < 0.230


@pytest.mark.validation
class TestCYC3PortContract:
    """Verify every output is typed Port; numerical inputs typed Quantity
    (SPEC_SHEET §3.1)."""

    def test_all_internal_ports_are_typed(
        self,
        c30_spec: RecuperatedBraytonSpec,
        real_gas_fluid: NasaFluid,
    ) -> None:
        result = solve_cycle(c30_spec, fluid=real_gas_fluid)
        for name, port in result.ports.items():
            assert isinstance(port, Port), f"port '{name}' is not Port"

    def test_outputs_carry_units(
        self,
        c30_spec: RecuperatedBraytonSpec,
        real_gas_fluid: NasaFluid,
    ) -> None:
        result = solve_cycle(c30_spec, fluid=real_gas_fluid)
        # All these conversions would raise if the underlying quantity were
        # dimensionless or wrong-dimensional
        _ = result.specific_work.to("J/kg")
        _ = result.heat_input.to("W")
        _ = result.net_shaft_work.to("W")
        _ = result.fuel_mass_flow.to("kg/s")


@pytest.mark.validation
class TestCYC3RefusalEnvelope:
    """SPEC_SHEET §13 refusal behavior — exercises one or two off-envelope cases."""

    def test_refuses_excessive_tit(self) -> None:
        """Burner refuses T_out > 2100 K (uncooled material limit)."""
        from cascade.thermo.nasa_mixture import RegimeOutOfValidity

        c = CapstoneC30
        inlet = Port(
            pressure_total=c.p_ambient,
            temperature_total=c.T_ambient,
            mass_flow=c.mass_flow,
            composition=Composition.air(),
        )
        bad_spec = _build_c30_spec()
        # Override the burner with an unrealistic TIT
        bad_burner = Burner(
            name="burner",
            pressure_drop_fraction=c.pdrop_burner,
            combustion_efficiency=c.combustion_efficiency,
            outlet_temperature=Q(2500.0, "K"),  # > 2100 K refusal
            fuel_lhv=c.fuel_LHV.to("J/kg"),
            fuel_carbon_atoms=c.fuel_carbon_atoms,
            fuel_hydrogen_atoms=c.fuel_hydrogen_atoms,
            fuel_molar_mass=c.fuel_molar_mass,
        )
        with pytest.raises(RegimeOutOfValidity, match="material limit"):
            from dataclasses import replace

            spec = replace(bad_spec, burner=bad_burner, inlet_port=inlet)
            _ = solve_cycle(spec, fluid=NasaFluid())
