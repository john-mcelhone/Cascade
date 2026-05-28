"""CYC-2 validation: Çengel & Boles Example 9-7 — recuperated Brayton.

Reference: Çengel, Y., Boles, M., *Thermodynamics: An Engineering Approach*,
9th ed., McGraw-Hill, 2019, Example 9-7 (recuperated Brayton); the original
case is the air-standard simple Brayton from Example 9-5 augmented with a
regenerator of effectiveness ε.

Case (CYC-2 per SPEC_SHEET §12):
- Air-standard analysis, calorically perfect: c_p = 1.005 kJ/(kg·K), γ = 1.4
- Inlet: 300 K, 100 kPa
- Compressor pressure ratio: 8
- Turbine inlet temperature: 1300 K
- η_c = η_t = 1.0 (isentropic)
- Regenerator (recuperator) effectiveness: ε = 0.80
- No pressure drops in recuperator (textbook simplification)

Expected (closed-form):
- T_2 = 543.4 K
- T_5 (cold-side exit of regen) = T_2 + ε(T_4 − T_2) = 682.8 K
- Q_in / ṁ = c_p (T_3 − T_5) = 1.005 × 617.2 = 620.3 kJ/kg
- W_net / ṁ = 340.6 kJ/kg (unchanged from CYC-1)
- η_th = 340.6 / 620.3 ≈ 54.91%

Tolerance per SPEC_SHEET §12 Table: η_th within ±0.2 pt.

Additionally we run a sensitivity check at ε = 0.85 (the Çengel textbook
variant that gives ~55.6% "Cycle efficiency 55.6%").
"""

from __future__ import annotations

import math

import pytest

from cascade.cycle import (
    Burner,
    Compressor,
    IdealGasFluid,
    RecuperatedBraytonSpec,
    Recuperator,
    Turbine,
    solve_cycle,
)
from cascade.units import Composition, Port, Q


def _make_spec(effectiveness: float) -> RecuperatedBraytonSpec:
    """Build Çengel 9-7 spec with a given recuperator effectiveness."""
    inlet = Port(
        pressure_total=Q(100.0, "kPa"),
        temperature_total=Q(300.0, "K"),
        mass_flow=Q(1.0, "kg/s"),
        composition=Composition.air(),
    )
    return RecuperatedBraytonSpec(
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
        recuperator=Recuperator(
            name="recuperator",
            effectiveness=effectiveness,
            cold_pressure_drop_fraction=0.0,
            hot_pressure_drop_fraction=0.0,
        ),
        mechanical_efficiency=1.0,
        generator_efficiency=1.0,
    )


@pytest.fixture
def cengel_97_fluid() -> IdealGasFluid:
    """Çengel air-standard fluid (matches Example 9-5/9-7)."""
    return IdealGasFluid(cp=Q(1005.0, "J/(kg*K)"), gamma=1.4)


class TestCYC2ChannelStates:
    """Per-station closed-form values from Çengel 9-7 (ε = 0.80 variant)."""

    def test_regenerator_cold_outlet_temperature(
        self, cengel_97_fluid: IdealGasFluid
    ) -> None:
        # T_5 = T_2 + ε(T_4 - T_2)
        # = 543.4 + 0.80*(717.7 - 543.4)
        # = 543.4 + 0.80*174.3
        # = 682.8 K
        result = solve_cycle(_make_spec(0.80), fluid=cengel_97_fluid)
        T_5 = (
            result.ports["recuperator_cold_out"]
            .temperature_total.to("K")
            .magnitude
        )
        assert T_5 == pytest.approx(682.8, abs=0.5)

    def test_heat_input_reduction(self, cengel_97_fluid: IdealGasFluid) -> None:
        # Q_in shrinks because the recuperator pre-heats the burner inlet
        result = solve_cycle(_make_spec(0.80), fluid=cengel_97_fluid)
        q_in_per_kg_kJ = result.heat_input.to("W").magnitude / 1000.0
        assert q_in_per_kg_kJ == pytest.approx(620.3, abs=1.0)

    def test_net_work_preserved(self, cengel_97_fluid: IdealGasFluid) -> None:
        # Recuperation doesn't change W_t or W_c (same T_3, T_2); only Q_in
        result = solve_cycle(_make_spec(0.80), fluid=cengel_97_fluid)
        W_net_per_kg = result.specific_work.to("kJ/kg").magnitude
        assert W_net_per_kg == pytest.approx(340.6, abs=1.0)


class TestCYC2ThermalEfficiency:
    """SPEC_SHEET §12: η_th within ±0.2 pt at ε = 0.80."""

    def test_efficiency_at_eps_80(self, cengel_97_fluid: IdealGasFluid) -> None:
        result = solve_cycle(_make_spec(0.80), fluid=cengel_97_fluid)
        eta_pct = result.thermal_efficiency * 100.0
        # Closed-form: η = W_net / Q_in = 340.6 / 620.3 = 0.5491 = 54.91%
        assert eta_pct == pytest.approx(54.91, abs=0.2)

    def test_efficiency_at_eps_85(self, cengel_97_fluid: IdealGasFluid) -> None:
        """Sensitivity at ε = 0.85 (sanity check)."""
        # T_5 = 543.4 + 0.85*(717.7 - 543.4) = 543.4 + 148.2 = 691.6 K
        # Q_in = 1.005 * (1300 - 691.6) = 611.4 kJ/kg
        # η = 340.6 / 611.4 = 0.5571 = 55.71%
        result = solve_cycle(_make_spec(0.85), fluid=cengel_97_fluid)
        eta_pct = result.thermal_efficiency * 100.0
        # Reference value "55.6%"; closed-form is ~55.71%
        assert eta_pct == pytest.approx(55.71, abs=0.2)

    def test_efficiency_improves_with_effectiveness(
        self, cengel_97_fluid: IdealGasFluid
    ) -> None:
        """Sanity: higher ε → higher η (monotonic in this regime)."""
        e_50 = solve_cycle(_make_spec(0.50), fluid=cengel_97_fluid)
        e_80 = solve_cycle(_make_spec(0.80), fluid=cengel_97_fluid)
        e_95 = solve_cycle(_make_spec(0.95), fluid=cengel_97_fluid)
        assert (
            e_50.thermal_efficiency
            < e_80.thermal_efficiency
            < e_95.thermal_efficiency
        )

    def test_no_recuperation_matches_simple_brayton(
        self, cengel_97_fluid: IdealGasFluid
    ) -> None:
        """ε = 0 must reproduce the simple Brayton efficiency (44.79%)."""
        result = solve_cycle(_make_spec(0.0), fluid=cengel_97_fluid)
        eta_pct = result.thermal_efficiency * 100.0
        # Closed-form simple Brayton at PR=8, γ=1.4: 44.79%
        assert eta_pct == pytest.approx(44.79, abs=0.2)


class TestCYC2SolverConvergence:
    """Smoke tests on the Aitken-accelerated fixed-point recycle solver."""

    def test_converges_at_default_tol(self, cengel_97_fluid: IdealGasFluid) -> None:
        result = solve_cycle(_make_spec(0.80), fluid=cengel_97_fluid)
        assert result.converged
        assert result.residual_norm < 1e-5
        assert result.outer_iterations <= 20

    def test_converges_at_high_effectiveness(
        self, cengel_97_fluid: IdealGasFluid
    ) -> None:
        result = solve_cycle(_make_spec(0.95), fluid=cengel_97_fluid)
        assert result.converged
        assert math.isfinite(result.thermal_efficiency)


class TestCYC2RefusalBehavior:
    """SPEC_SHEET §13: refusal behavior at the regime envelope."""

    def test_refuses_effectiveness_above_98(self) -> None:
        with pytest.raises(ValueError, match="effectiveness"):
            _ = Recuperator(name="bad", effectiveness=0.99)

    def test_refuses_negative_effectiveness(self) -> None:
        with pytest.raises(ValueError, match="effectiveness"):
            _ = Recuperator(name="bad", effectiveness=-0.1)
