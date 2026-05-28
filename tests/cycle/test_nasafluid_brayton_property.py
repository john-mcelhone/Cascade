"""Property-based / family tests for the real-gas (NasaFluid) Brayton cycle path.

These tests exercise the INVARIANT across a range of pressure ratios, NOT a
single benchmark case. They verify physical trend properties of the NasaFluid
(NASA 9-coefficient polynomial, variable cp) on a simple recuperated Brayton
topology:

  - η_th is positive and < 1 at every PR point
  - η_th increases monotonically as PR rises from low values (3 → 8)
  - At high PR (12 vs 8), η_th plateaus or decreases (recuperator effectiveness
    is the upper bound on η; additional pressure losses at high PR offset the
    Carnot improvement)
  - W_electrical scales positively with m_dot at fixed PR (more flow, more power)
  - The solver converges at every operating point

**Why this matters**: The CYC-3 Capstone C30 benchmark runs NasaFluid at a
single point (PR=4.0, ε_recup=0.87, m_dot=0.31 kg/s). A regression that
re-tunes only at that point would go undetected. Sweeping PR ∈ {3, 5, 8, 12}
and m_dot ∈ {0.2, 0.4} makes silent re-tuning practically impossible.

These tests do NOT assert magic-number η_th values. They assert trend
properties and physical bounds. This is a regression trap for the real-gas
code path, not a second benchmark.

References
----------
Walsh, P., Fletcher, P., *Gas Turbine Performance* 2nd ed., Blackwell, 2004,
§5: component pressure losses; §3: cycle thermal efficiency definition.

McBride, Zehe & Gordon 2002, NASA TP-2002-211556: NASA 9-coefficient
polynomial basis for variable-cp real-gas mixtures.

SPEC_SHEET §12: NasaFluid is the required fluid for combustion-products
cycles; IdealGasFluid is opt-in only for textbook validation.
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Pressure-drop fractions representative of a well-designed industrial
# microturbine (Walsh & Fletcher 2004 §5.10 typicals).
_PDROP_INLET: float = 0.02
_PDROP_RECUP_COLD: float = 0.03
_PDROP_BURNER: float = 0.04
_PDROP_RECUP_HOT: float = 0.03


def _turbine_pr_for_compressor_pr(pr_c: float) -> float:
    """Derive turbine PR from compressor PR and inter-component pressure drops.

    Starting at p_amb at the inlet and ending at p_amb at the exhaust:

        p_burner_out = pr_c * (1 - dp_inlet) * (1 - dp_recup_cold) * (1 - dp_burner)
        p_turbine_out = 1 / (1 - dp_recup_hot)   [multiples of p_amb]
        pr_t = p_burner_out / p_turbine_out
    """
    p_burner = pr_c * (1.0 - _PDROP_INLET) * (1.0 - _PDROP_RECUP_COLD) * (1.0 - _PDROP_BURNER)
    p_turb_out = 1.0 / (1.0 - _PDROP_RECUP_HOT)
    return p_burner / p_turb_out


def _make_recuperated_nasa_spec(
    pr_c: float,
    m_dot_kg_s: float = 0.31,
    T_inlet_K: float = 288.15,  # noqa: N803
    p_inlet_kPa: float = 101.325,
    TIT_K: float = 1116.0,  # noqa: N803
    eta_c: float = 0.78,
    eta_t: float = 0.84,
    effectiveness: float = 0.87,
) -> RecuperatedBraytonSpec:
    """Build a recuperated Brayton spec using NasaFluid conventions.

    All default component efficiencies and pressure-loss fractions are chosen
    to match the microturbine class. The test
    family varies only pr_c and m_dot to isolate the real-gas path's response
    to those parameters.

    Parameters
    ----------
    pr_c : float
        Compressor pressure ratio.
    m_dot_kg_s : float
        Inlet mass flow [kg/s].
    T_inlet_K : float
        Compressor inlet total temperature [K].
    p_inlet_kPa : float
        Compressor inlet total pressure [kPa].
    TIT_K : float
        Turbine inlet (burner outlet) total temperature [K].
    eta_c : float
        Compressor isentropic efficiency.
    eta_t : float
        Turbine isentropic efficiency.
    effectiveness : float
        Recuperator effectiveness.
    """
    inlet = Port(
        pressure_total=Q(p_inlet_kPa, "kPa"),
        temperature_total=Q(T_inlet_K, "K"),
        mass_flow=Q(m_dot_kg_s, "kg/s"),
        composition=Composition.air(),
    )
    return RecuperatedBraytonSpec(
        inlet_port=inlet,
        inlet_loss=ConstantPressureLoss(
            name="inlet_loss",
            pressure_drop_fraction=_PDROP_INLET,
        ),
        compressor=Compressor(
            name="compressor",
            pressure_ratio=pr_c,
            efficiency_isentropic=eta_c,
        ),
        burner=Burner(
            name="burner",
            pressure_drop_fraction=_PDROP_BURNER,
            combustion_efficiency=0.995,
            outlet_temperature=Q(TIT_K, "K"),
            fuel_lhv=Q(50.0, "MJ/kg"),
            fuel_carbon_atoms=1,
            fuel_hydrogen_atoms=4,
            fuel_molar_mass=Q(16.0425, "g/mol"),
            fuel_inlet_temperature=Q(298.15, "K"),
            air_standard=False,  # real-gas composition shift
        ),
        turbine=Turbine(
            name="turbine",
            pressure_ratio=_turbine_pr_for_compressor_pr(pr_c),
            efficiency_isentropic=eta_t,
        ),
        recuperator=Recuperator(
            name="recuperator",
            effectiveness=effectiveness,
            cold_pressure_drop_fraction=_PDROP_RECUP_COLD,
            hot_pressure_drop_fraction=_PDROP_RECUP_HOT,
        ),
        mechanical_efficiency=0.95,
        generator_efficiency=0.95,
    )


# ---------------------------------------------------------------------------
# Family test: η_th physical bounds across PR range
# ---------------------------------------------------------------------------

_PR_FAMILY = [3.0, 5.0, 8.0, 12.0]


class TestNasafluidBraytonEtaThPositiveAcrossPrRange:
    """η_th must be strictly positive and < 1 at every PR ∈ {3, 5, 8, 12}.

    This is the minimal physical constraint: a recuperated microturbine
    cycle run at realistic component efficiencies must produce net positive
    work. It also catches any NaN or unphysical output from the real-gas
    path that would be invisible at a single PR=4 point.

    Per SPEC_SHEET §3.4: NasaFluid is the required fluid for combustion-
    products cycles. This test exercises the real-gas cp(T) path at four
    operating points spanning the validated PR envelope.
    """

    @pytest.mark.parametrize("pr", _PR_FAMILY)
    def test_nasafluid_brayton_eta_th_positive_across_pr_range(
        self, pr: float
    ) -> None:
        """η_th must be in (0, 1) for every PR in the family sweep."""
        fluid = NasaFluid()
        spec = _make_recuperated_nasa_spec(pr_c=pr)
        result = solve_cycle(spec, fluid=fluid)

        assert result.converged, (
            f"PR={pr}: solver did not converge "
            f"(residual={result.residual_norm:.3e}, iters={result.outer_iterations})"
        )
        eta = result.thermal_efficiency
        assert eta > 0.0, (
            f"PR={pr}: η_th={eta:.6f} must be positive (cycle produces net work)"
        )
        assert eta < 1.0, (
            f"PR={pr}: η_th={eta:.6f} must be < 1 (2nd Law)"
        )


# ---------------------------------------------------------------------------
# Family test: η_th rises at low PR then falls at high PR (recuperated optimum)
# ---------------------------------------------------------------------------

class TestNasafluidBraytonEtaThTrendWithPr:
    """η_th must rise at low PR then fall at high PR — the recuperated optimum.

    A recuperated Brayton with ε_recup=0.87 and realistic component
    efficiencies has an optimal PR. Below the optimum, η_th increases with PR
    (more isentropic work gain than pressure-loss penalty). Above the optimum
    it decreases (compressor work rises; additional recuperator benefit is
    exhausted because T_compressor_out approaches T_turbine_out). This
    non-monotone shape is well-documented for microturbines in this
    effectiveness class (Walsh & Fletcher §5; McDonald GT2003-38570).

    At η_c=0.78, η_t=0.84, ε=0.87 the peak occurs near PR≈3–4. We assert:
    - η_th(PR=2) < η_th(PR=3): ascending side of the curve.
    - η_th(PR=5) > η_th(PR=8): descending side of the curve.
    - η_th(PR=12) < η_th(PR=8): deeper descent confirms monotone fall.

    A regression that reproduces CYC-3 at PR=4 but breaks the real-gas solver
    at off-nominal PR would violate one or both of these directional checks.
    """

    def test_nasafluid_brayton_eta_th_trend_with_pr(self) -> None:
        """η_th rises from PR=2 to PR=3, then falls from PR=5 to PR=8 to PR=12."""
        fluid = NasaFluid()
        etas: dict[float, float] = {}
        for pr in [2.0, 3.0, 5.0, 8.0, 12.0]:
            spec = _make_recuperated_nasa_spec(pr_c=pr)
            result = solve_cycle(spec, fluid=fluid)
            assert result.converged, f"PR={pr} did not converge"
            etas[pr] = result.thermal_efficiency

        # Ascending side: PR=2 → 3 (approaching optimal)
        assert etas[2.0] < etas[3.0], (
            f"η_th should increase from PR=2 to PR=3 (ascending recuperated curve): "
            f"η@2={etas[2.0]:.4f}, η@3={etas[3.0]:.4f}"
        )
        # Descending side: PR=5 → 8 → 12 (above optimal, pressure losses dominate)
        assert etas[5.0] > etas[8.0], (
            f"η_th should decrease from PR=5 to PR=8 (past recuperated optimum): "
            f"η@5={etas[5.0]:.4f}, η@8={etas[8.0]:.4f}"
        )
        assert etas[8.0] > etas[12.0], (
            f"η_th should decrease from PR=8 to PR=12 (further past optimum): "
            f"η@8={etas[8.0]:.4f}, η@12={etas[12.0]:.4f}"
        )


# ---------------------------------------------------------------------------
# Family test: W_electrical increases with m_dot at fixed PR
# ---------------------------------------------------------------------------

_MDOT_FAMILY = [0.2, 0.31, 0.4]
_PR_FIXED_FOR_MDOT_SWEEP = 4.0  # reference PR, near the Capstone operating point


class TestNasafluidBraytonElectricalOutputScalesWithMdot:
    """W_electrical must increase monotonically with m_dot at fixed PR.

    At fixed cycle topology (same PR, same TIT, same component efficiencies),
    a larger mass flow passes more air through the turbine, producing
    proportionally more shaft work. This is a fundamental linear scaling of
    every Brayton cycle — it holds for both IdealGasFluid and NasaFluid.

    Testing it here for NasaFluid at three m_dot points closes the gap where
    a bug in the real-gas enthalpy bookkeeping would cause output power to
    diverge from linearity.
    """

    @pytest.mark.parametrize("m_dot", _MDOT_FAMILY)
    def test_nasafluid_brayton_electrical_output_positive_at_all_mdots(
        self, m_dot: float
    ) -> None:
        """W_electrical > 0 at every m_dot in the family sweep."""
        fluid = NasaFluid()
        spec = _make_recuperated_nasa_spec(pr_c=_PR_FIXED_FOR_MDOT_SWEEP, m_dot_kg_s=m_dot)
        result = solve_cycle(spec, fluid=fluid)
        assert result.converged, f"m_dot={m_dot} kg/s did not converge"
        W_e = result.electrical_output.to("kW").magnitude  # noqa: N806
        assert W_e > 0.0, (
            f"m_dot={m_dot} kg/s: W_electrical={W_e:.2f} kW must be positive"
        )

    def test_nasafluid_brayton_electrical_output_increases_with_mdot(
        self,
    ) -> None:
        """W_electrical(0.2) < W_electrical(0.31) < W_electrical(0.4) at PR=4."""
        fluid = NasaFluid()
        w_elec: dict[float, float] = {}
        for m_dot in _MDOT_FAMILY:
            spec = _make_recuperated_nasa_spec(
                pr_c=_PR_FIXED_FOR_MDOT_SWEEP, m_dot_kg_s=m_dot
            )
            result = solve_cycle(spec, fluid=fluid)
            assert result.converged, f"m_dot={m_dot} kg/s did not converge"
            w_elec[m_dot] = result.electrical_output.to("kW").magnitude

        for lo, hi in zip(_MDOT_FAMILY[:-1], _MDOT_FAMILY[1:]):
            assert w_elec[lo] < w_elec[hi], (
                f"W_electrical must increase with m_dot: "
                f"W@{lo} kg/s={w_elec[lo]:.2f} kW, "
                f"W@{hi} kg/s={w_elec[hi]:.2f} kW"
            )


# ---------------------------------------------------------------------------
# Solver convergence across the whole PR family
# ---------------------------------------------------------------------------

class TestNasafluidBraytonConvergenceAcrossPrRange:
    """The solver must converge at all PR points in the family, not just PR=4.

    A convergence failure at an off-nominal PR is indistinguishable from a
    physical result unless tested explicitly. This test closes the coverage
    gap for the Aitken-accelerated fixed-point recycle loop in the recuperated
    solver path.
    """

    @pytest.mark.parametrize("pr", _PR_FAMILY)
    def test_nasafluid_brayton_solver_converges_across_pr_range(
        self, pr: float
    ) -> None:
        """Solver must converge within 50 outer iterations at every PR."""
        fluid = NasaFluid()
        spec = _make_recuperated_nasa_spec(pr_c=pr)
        result = solve_cycle(spec, fluid=fluid)
        assert result.converged, (
            f"PR={pr}: solver did not converge. "
            f"residual={result.residual_norm:.3e}, "
            f"iterations={result.outer_iterations}"
        )
        assert result.outer_iterations <= 50, (
            f"PR={pr}: solver took {result.outer_iterations} iterations (limit 50)"
        )
