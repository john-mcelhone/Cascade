"""Property-based / family tests for the ideal Brayton cycle closed-form relation.

These tests exercise the INVARIANT, not a single benchmark case. They verify:

    η_th = 1 − PR^(−(γ−1)/γ)

at every point across a family of pressure ratios and inlet conditions, using
Cascade's `IdealGasFluid` (calorically perfect, constant cp and γ).

**Why this matters for trust**: if any test referenced only PR=8 (Çengel 9-5),
a future implementation bug that re-tunes to that single case would go
undetected. Sweeping PR ∈ {2, 3, 5, 8, 10, 15, 20, 30, 50} and T_max over
a range makes silent re-tuning practically impossible.

All tests use IdealGasFluid with Çengel's air-standard defaults (cp = 1005
J/(kg·K), γ = 1.4) unless otherwise noted. The `air_standard=True` flag on
the Burner is mandatory to match the textbook model (no composition shift,
no combustion products).

References
----------
Çengel, Y., Boles, M., *Thermodynamics: An Engineering Approach* 9th ed.,
McGraw-Hill, 2019, §9-5 (simple Brayton).

SPEC_SHEET §12: CYC-1 and CYC-2 pass-gates; §3.4 fluid-model classification.
"""

from __future__ import annotations

import math

import pytest

from cascade.cycle import (
    Burner,
    Compressor,
    IdealGasFluid,
    SimpleBraytonSpec,
    solve_cycle,
)
from cascade.units import Composition, Port, Q


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _closed_form_eta(PR: float, gamma: float = 1.4) -> float:  # noqa: N803
    """Textbook ideal Brayton thermal efficiency for given PR and γ.

    η_th = 1 − 1 / PR^((γ−1)/γ)

    This is the exact closed form for a calorically perfect ideal gas with
    isentropic compressor and turbine (η_c = η_t = 1).
    """
    return 1.0 - 1.0 / (PR ** ((gamma - 1.0) / gamma))


def _make_simple_ideal_brayton_spec(
    PR: float,  # noqa: N803
    T_inlet_K: float = 300.0,  # noqa: N803
    T_max_K: float = 1300.0,  # noqa: N803
    p_inlet_kPa: float = 100.0,
) -> SimpleBraytonSpec:
    """Build an ideal-gas simple Brayton spec with isentropic components.

    Uses air-standard mode (no composition shift across burner) matching the
    textbook assumption: constant-cp, constant-γ throughout the cycle.

    Args:
        PR: Compressor (and turbine) pressure ratio.
        T_inlet_K: Compressor inlet total temperature [K].
        T_max_K: Turbine inlet (burner outlet) total temperature [K].
        p_inlet_kPa: Inlet total pressure [kPa].
    """
    inlet = Port(
        pressure_total=Q(p_inlet_kPa, "kPa"),
        temperature_total=Q(T_inlet_K, "K"),
        mass_flow=Q(1.0, "kg/s"),
        composition=Composition.air(),
    )
    return SimpleBraytonSpec(
        inlet_port=inlet,
        compressor=Compressor(
            name="compressor",
            pressure_ratio=PR,
            efficiency_isentropic=1.0,  # isentropic
        ),
        burner=Burner(
            name="burner",
            pressure_drop_fraction=0.0,  # textbook: no pressure loss
            combustion_efficiency=1.0,
            outlet_temperature=Q(T_max_K, "K"),
            air_standard=True,  # constant-cp, no composition shift
        ),
        turbine=Turbine(
            name="turbine",
            pressure_ratio=PR,
            efficiency_isentropic=1.0,  # isentropic
        ),
        mechanical_efficiency=1.0,
        generator_efficiency=1.0,
    )


# Import Turbine alongside the others for spec construction
from cascade.cycle import Turbine  # noqa: E402


# ---------------------------------------------------------------------------
# Family test: η_th vs closed form across the full PR range
# ---------------------------------------------------------------------------

_PRESSURE_RATIOS = [2.0, 3.0, 5.0, 8.0, 10.0, 15.0, 20.0, 30.0, 50.0]
_ETA_TOLERANCE = 1e-4  # fraction — numerical precision, not engineering tolerance


class TestIdealBraytonEtaThermalMatchesClosedFormAcrossPRRange:
    """η_th = 1 − PR^(−(γ−1)/γ) must hold at every PR ≥ 2 in the valid range.

    This test sweeps PR over an order of magnitude to catch any code path that
    is tuned to reproduce a specific benchmark value rather than the general
    analytical relation.
    """

    @pytest.mark.parametrize("PR", _PRESSURE_RATIOS)
    def test_eta_th_matches_closed_form(self, PR: float) -> None:  # noqa: N803
        """η_th from solver matches 1 − PR^(−(γ−1)/γ) within 1e-4 absolute."""
        fluid = IdealGasFluid(cp=Q(1005.0, "J/(kg*K)"), gamma=1.4)
        spec = _make_simple_ideal_brayton_spec(PR=PR)
        result = solve_cycle(spec, fluid=fluid)

        eta_solver = result.thermal_efficiency
        eta_closed = _closed_form_eta(PR, gamma=1.4)

        assert eta_solver == pytest.approx(eta_closed, abs=_ETA_TOLERANCE), (
            f"PR={PR}: solver η_th={eta_solver:.6f}, "
            f"closed-form η_th={eta_closed:.6f}, "
            f"delta={abs(eta_solver - eta_closed):.2e}"
        )

    @pytest.mark.parametrize("PR", _PRESSURE_RATIOS)
    def test_eta_th_increases_monotonically_with_pr(self, PR: float) -> None:  # noqa: N803
        """η_th must increase as PR increases (property of the ideal Brayton).

        The upper bound is capped at PR_max = 55 to stay within the solver's
        validated envelope (SPEC_SHEET §13: PR > 60 is refused).
        """
        from cascade.cycle.components import PR_REFUSE_HARD

        PR_MAX = min(PR * 1.5, PR_REFUSE_HARD - 5.0)  # noqa: N806
        if PR_MAX <= PR:
            pytest.skip(f"PR={PR} leaves no room for a higher PR within the envelope")
        fluid = IdealGasFluid(cp=Q(1005.0, "J/(kg*K)"), gamma=1.4)
        spec_lo = _make_simple_ideal_brayton_spec(PR=PR)
        spec_hi = _make_simple_ideal_brayton_spec(PR=PR_MAX)
        result_lo = solve_cycle(spec_lo, fluid=fluid)
        result_hi = solve_cycle(spec_hi, fluid=fluid)
        assert result_hi.thermal_efficiency > result_lo.thermal_efficiency, (
            f"η_th should increase with PR: "
            f"η@PR={PR}={result_lo.thermal_efficiency:.6f}, "
            f"η@PR={PR_MAX}={result_hi.thermal_efficiency:.6f}"
        )


class TestIdealBraytonEtaThermalIndependentOfTmax:
    """η_th = 1 − PR^(−(γ−1)/γ) is independent of T_max (ideal Brayton).

    The textbook formula has no T_max dependence — specific work scales with T
    but efficiency does not. Any implementation that tuned η to the Çengel
    example's T_3 = 1300 K would fail this test.
    """

    @pytest.mark.parametrize("T_max_K", [800.0, 1000.0, 1300.0, 1500.0, 1800.0])
    def test_eta_th_independent_of_T_max_at_pr8(self, T_max_K: float) -> None:  # noqa: N803
        """At PR=8, η_th must be 44.79% regardless of T_max."""
        fluid = IdealGasFluid(cp=Q(1005.0, "J/(kg*K)"), gamma=1.4)
        spec = _make_simple_ideal_brayton_spec(PR=8.0, T_max_K=T_max_K)
        result = solve_cycle(spec, fluid=fluid)
        eta_closed = _closed_form_eta(8.0, gamma=1.4)  # = 0.44786
        assert result.thermal_efficiency == pytest.approx(eta_closed, abs=_ETA_TOLERANCE), (
            f"T_max={T_max_K} K: η_th={result.thermal_efficiency:.6f} "
            f"vs closed-form {eta_closed:.6f}"
        )

    @pytest.mark.parametrize("T_max_K", [800.0, 1000.0, 1300.0, 1500.0, 1800.0])
    def test_eta_th_independent_of_T_max_at_pr20(self, T_max_K: float) -> None:  # noqa: N803
        """At PR=20, η_th must be ~57.17% regardless of T_max."""
        fluid = IdealGasFluid(cp=Q(1005.0, "J/(kg*K)"), gamma=1.4)
        spec = _make_simple_ideal_brayton_spec(PR=20.0, T_max_K=T_max_K)
        result = solve_cycle(spec, fluid=fluid)
        eta_closed = _closed_form_eta(20.0, gamma=1.4)
        assert result.thermal_efficiency == pytest.approx(eta_closed, abs=_ETA_TOLERANCE), (
            f"T_max={T_max_K} K, PR=20: η_th={result.thermal_efficiency:.6f} "
            f"vs closed-form {eta_closed:.6f}"
        )


class TestIdealBraytonEtaThermalVaryingGamma:
    """The closed-form relation holds for any γ, not just γ = 1.4 (air).

    Tests that the solver correctly implements the general η_th = 1 − PR^(−(γ−1)/γ)
    formula by varying γ across physically meaningful values (monatomic,
    diatomic, triatomic ranges).
    """

    @pytest.mark.parametrize(
        "gamma, cp_J_per_kgK",
        [
            (1.4, 1005.0),    # standard air
            (1.667, 5193.0),  # monatomic ideal gas (He-like)
            (1.3, 1150.0),    # heavy diatomic / combustion-product-like
        ],
    )
    def test_eta_th_closed_form_holds_for_varied_gamma(
        self, gamma: float, cp_J_per_kgK: float
    ) -> None:
        """η_th = 1 − PR^(−(γ−1)/γ) must hold for any γ at PR=10."""
        fluid = IdealGasFluid(cp=Q(cp_J_per_kgK, "J/(kg*K)"), gamma=gamma)
        spec = _make_simple_ideal_brayton_spec(PR=10.0)
        result = solve_cycle(spec, fluid=fluid)
        eta_closed = _closed_form_eta(10.0, gamma=gamma)
        assert result.thermal_efficiency == pytest.approx(eta_closed, abs=_ETA_TOLERANCE), (
            f"γ={gamma}: η_th={result.thermal_efficiency:.6f} "
            f"vs closed-form {eta_closed:.6f}"
        )


class TestIdealBraytonModeContract:
    """API contract: IdealGasFluid is the required fluid for textbook validation.

    These tests confirm that the mode-switching pathway is explicit and
    testable — a buyer can import these directly and reproduce CYC-1 / CYC-2.
    """

    def test_ideal_gas_fluid_instance_is_required_for_closed_form_match(
        self,
    ) -> None:
        """Constructing IdealGasFluid without arguments gives Çengel's defaults."""
        fluid = IdealGasFluid()
        # cp must be ≈ 1005 J/(kg·K), γ must be 1.4
        cp_val = fluid.cp(
            Q(300.0, "K"), Q(100.0, "kPa"), Composition.air()
        ).to("J/(kg*K)").magnitude
        gamma_val = fluid.gamma(
            Q(300.0, "K"), Q(100.0, "kPa"), Composition.air()
        )
        assert cp_val == pytest.approx(1005.0, rel=1e-6)
        assert gamma_val == pytest.approx(1.4, rel=1e-6)

    def test_nasa_fluid_diverges_from_closed_form_at_high_temperature(
        self,
    ) -> None:
        """NasaFluid (variable cp) must disagree with the ideal-gas closed form.

        This test documents the intentional gap between air-standard (constant
        cp) and real-gas (variable cp, NASA polynomial) modes. At T_max = 1300 K
        the cp difference across the cycle is ~8 %, so η_th differs by several
        percentage points. A buyer should see this and know which mode they need.
        """
        from cascade.cycle import NasaFluid

        nasa_fluid = NasaFluid()
        ideal_fluid = IdealGasFluid(cp=Q(1005.0, "J/(kg*K)"), gamma=1.4)
        spec = _make_simple_ideal_brayton_spec(PR=8.0)

        result_nasa = solve_cycle(spec, fluid=nasa_fluid)
        result_ideal = solve_cycle(spec, fluid=ideal_fluid)

        # They should NOT match closely — document the separation
        delta = abs(result_nasa.thermal_efficiency - result_ideal.thermal_efficiency)
        assert delta > 0.005, (
            "NasaFluid and IdealGasFluid should diverge by >0.5 pt at T_max=1300 K; "
            f"got delta={delta*100:.3f} pt. If they match, the NasaFluid is not using "
            "variable cp or the IdealGasFluid cp is unrealistically high."
        )

    def test_specific_work_scales_linearly_with_T_inlet(self) -> None:
        """Specific work scales linearly with T_inlet for constant-cp ideal gas.

        For isentropic Brayton with constant cp:
            w_net / (cp T_1) = (T3/T1 - T3/T1 * PR^(-(γ-1)/γ) - PR^((γ-1)/γ) + 1)

        The ratio w_net / T_inlet should be constant when T3/T1 is held fixed.
        """
        fluid = IdealGasFluid(cp=Q(1005.0, "J/(kg*K)"), gamma=1.4)
        # Two runs at different T_inlet, keeping T3/T1 = 1300/300 = 4.333 fixed
        T_ratio = 1300.0 / 300.0
        for T1 in [250.0, 300.0, 350.0]:
            T3 = T1 * T_ratio
            spec = _make_simple_ideal_brayton_spec(
                PR=8.0, T_inlet_K=T1, T_max_K=T3
            )
            result = solve_cycle(spec, fluid=fluid)
            w_net_per_T1 = result.specific_work.to("J/kg").magnitude / T1
            # The normalized specific work should be constant across T1
            # (first iteration sets the reference)
            if T1 == 250.0:
                reference_w_per_T1 = w_net_per_T1
            else:
                assert w_net_per_T1 == pytest.approx(reference_w_per_T1, rel=1e-4), (
                    f"T1={T1} K: w_net/T1={w_net_per_T1:.1f} vs reference "
                    f"{reference_w_per_T1:.1f} — specific work is not scaling "
                    "linearly with inlet temperature."
                )
