"""F1 / Item 2: air_standard mode via HTTP API — family / property tests.

Tests that the public `air_standard` project setting:
1. Causes the cycle router to use `IdealGasFluid` (confirmed by η_th matching
   the closed-form expression η_th = 1 − PR^(−(γ−1)/γ)).
2. Produces results that DIFFER from the NasaFluid (real-gas) path — confirming
   the mode switch is active.
3. Works across a sweep of PR values (anti-tuning gate — a single PR=8 test
   would pass even if the code secretly special-cased that value).

These tests exercise the HTTP-API path (cycle.py _select_fluid + _build_recuperated_spec),
complementing the Python-SDK tests in tests/cycle/test_ideal_brayton_property.py
which test the same invariant at the solver level.

References
----------
Çengel, Y., Boles, M., Thermodynamics: An Engineering Approach, 9th ed.,
McGraw-Hill 2019, §9-5 (simple Brayton).
SPEC_SHEET §12 CYC-1 / CYC-2 tolerances: ±0.1 pt (simple), ±0.2 pt (recuperated).
cycle.py module docstring — air_standard mode documentation.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
for p in (str(_REPO / "src"), str(_REPO / "apps" / "api")):
    if p not in sys.path:
        sys.path.insert(0, p)


def _closed_form_eta(PR: float, gamma: float = 1.4) -> float:
    """Textbook ideal Brayton thermal efficiency: η_th = 1 − PR^(−(γ−1)/γ)."""
    return 1.0 - 1.0 / (PR ** ((gamma - 1.0) / gamma))


def _build_simple_air_project(PR: float, T_max_K: float = 1300.0) -> dict:
    """Build a minimal SimpleBrayton project dict for use in the cycle router.

    Uses the same parameters as test_ideal_brayton_property.py but exercises
    the HTTP-API path (project dict → _build_recuperated_spec → _select_fluid).
    """
    return {
        "components": [
            {
                "id": "c1", "kind": "Compressor", "name": "C1",
                "params": {
                    "pressure_ratio": PR,
                    "efficiency_isentropic": 1.0,
                },
                "position": {"x": 0, "y": 0},
            },
            {
                "id": "b1", "kind": "Burner", "name": "B1",
                "params": {
                    "outlet_temperature": {"value": T_max_K, "unit": "K"},
                    "pressure_drop_fraction": 0.0,
                    "combustion_efficiency": 1.0,
                    # Note: air_standard is also set at the project level via settings.
                    # The burner flag is redundant here but kept to test that both paths work.
                    "air_standard": True,
                },
                "position": {"x": 200, "y": 0},
            },
            {
                "id": "t1", "kind": "Turbine", "name": "T1",
                "params": {
                    "pressure_ratio": PR,
                    "efficiency_isentropic": 1.0,
                },
                "position": {"x": 400, "y": 0},
            },
        ],
        "edges": [
            {"id": "e1", "source": "c1", "target": "b1",
             "source_port": "out", "target_port": "in"},
            {"id": "e2", "source": "b1", "target": "t1",
             "source_port": "out", "target_port": "in"},
        ],
        "boundary_conditions": {
            "pressure_total": {"value": 100.0, "unit": "kPa"},
            "temperature_total": {"value": 300.0, "unit": "K"},
            "mass_flow": {"value": 1.0, "unit": "kg/s"},
            "composition": "air",
        },
        "settings": {
            "air_standard": True,        # F1 public flag
            "mechanical_efficiency": 1.0,
            "generator_efficiency": 1.0,
        },
    }


def _select_fluid_from_project(project: dict):
    """Call the cycle router's _select_fluid helper directly."""
    from routers.cycle import _select_fluid
    return _select_fluid(project)


def _build_spec_from_project(project: dict):
    """Call the cycle router's _build_recuperated_spec helper directly."""
    from routers.cycle import _build_recuperated_spec
    return _build_recuperated_spec(project)


class TestAirStandardFlagSelectsIdealGasFluid:
    """settings.air_standard=True must cause _select_fluid to return IdealGasFluid."""

    def test_flag_absent_gives_nasa_fluid(self) -> None:
        """Without the flag, _select_fluid must return NasaFluid."""
        from cascade.cycle.fluid_model import NasaFluid

        project = _build_simple_air_project(PR=8.0)
        project["settings"]["air_standard"] = False
        fluid = _select_fluid_from_project(project)
        assert isinstance(fluid, NasaFluid), (
            f"Without air_standard flag, _select_fluid must return NasaFluid; "
            f"got {type(fluid).__name__}."
        )

    def test_flag_true_gives_ideal_gas_fluid(self) -> None:
        """With settings.air_standard=True, _select_fluid must return IdealGasFluid."""
        from cascade.cycle.fluid_model import IdealGasFluid

        project = _build_simple_air_project(PR=8.0)
        fluid = _select_fluid_from_project(project)
        assert isinstance(fluid, IdealGasFluid), (
            f"With air_standard=True, _select_fluid must return IdealGasFluid; "
            f"got {type(fluid).__name__}."
        )

    def test_ideal_gas_fluid_has_correct_cp_and_gamma(self) -> None:
        """IdealGasFluid from air_standard flag must use cp=1005 J/(kg·K), γ=1.4."""
        from cascade.units import Composition, Q

        project = _build_simple_air_project(PR=8.0)
        fluid = _select_fluid_from_project(project)

        cp_val = fluid.cp(
            Q(300.0, "K"), Q(100.0, "kPa"), Composition.air()
        ).to("J/(kg*K)").magnitude
        gamma_val = fluid.gamma(
            Q(300.0, "K"), Q(100.0, "kPa"), Composition.air()
        )
        assert cp_val == pytest.approx(1005.0, rel=1e-6), (
            f"IdealGasFluid cp = {cp_val:.1f} J/(kg·K); expected 1005.0."
        )
        assert gamma_val == pytest.approx(1.4, rel=1e-6), (
            f"IdealGasFluid γ = {gamma_val:.4f}; expected 1.4."
        )


class TestAirStandardEtaThermalMatchesClosedFormHTTPPath:
    """η_th from the cycle router must match 1 − PR^(−(γ−1)/γ) across a PR sweep.

    This tests the HTTP-API code path (_build_recuperated_spec + _select_fluid
    + solve_cycle), not just the Python SDK path. Any code path that is tuned
    to a single PR value (e.g. PR=8) would fail this parametric sweep.
    """

    _PRESSURE_RATIOS = [2.0, 3.0, 5.0, 8.0, 10.0, 15.0, 20.0, 30.0]
    _ETA_TOLERANCE_ABS = 1e-4  # numerical, not engineering

    @pytest.mark.parametrize("PR", _PRESSURE_RATIOS)
    def test_eta_th_matches_closed_form(self, PR: float) -> None:
        """η_th from cycle router matches 1 − PR^(−(γ−1)/γ) within 1e-4 absolute."""
        from cascade.cycle.solver import solve_cycle

        project = _build_simple_air_project(PR=PR)
        spec = _build_spec_from_project(project)
        fluid = _select_fluid_from_project(project)
        result = solve_cycle(spec, fluid=fluid)

        assert result.converged, (
            f"PR={PR}: cycle solver did not converge. "
            f"residual_norm={result.residual_norm:.2e}"
        )

        eta_solver = result.thermal_efficiency
        eta_closed = _closed_form_eta(PR, gamma=1.4)

        assert eta_solver == pytest.approx(eta_closed, abs=self._ETA_TOLERANCE_ABS), (
            f"PR={PR}: HTTP-path η_th = {eta_solver:.6f}, "
            f"closed-form η_th = {eta_closed:.6f}, "
            f"delta = {abs(eta_solver - eta_closed):.2e}"
        )

    @pytest.mark.parametrize("PR", _PRESSURE_RATIOS)
    def test_eta_th_increases_monotonically_with_pr(self, PR: float) -> None:
        """η_th must be strictly increasing with PR across the valid range."""
        from cascade.cycle.solver import solve_cycle
        from cascade.cycle.components import PR_REFUSE_HARD

        PR_hi = min(PR * 1.5, PR_REFUSE_HARD - 5.0)
        if PR_hi <= PR:
            pytest.skip(f"PR={PR} leaves no room for higher value within envelope")

        fluid_lo = _select_fluid_from_project(_build_simple_air_project(PR=PR))
        fluid_hi = _select_fluid_from_project(_build_simple_air_project(PR=PR_hi))
        result_lo = solve_cycle(_build_spec_from_project(_build_simple_air_project(PR=PR)),
                                fluid=fluid_lo)
        result_hi = solve_cycle(_build_spec_from_project(_build_simple_air_project(PR=PR_hi)),
                                fluid=fluid_hi)
        assert result_hi.thermal_efficiency > result_lo.thermal_efficiency, (
            f"η_th must increase with PR: "
            f"η@PR={PR}={result_lo.thermal_efficiency:.4f}, "
            f"η@PR={PR_hi}={result_hi.thermal_efficiency:.4f}"
        )


class TestAirStandardDiffersFromNasaFluid:
    """The air_standard flag must produce results that differ from NasaFluid.

    This is the mode-switch contract: a buyer who uses NasaFluid (real-gas)
    should see a different η_th from a buyer who uses IdealGasFluid
    (constant-cp textbook). If the two modes agree, the mode switch is broken.
    """

    def test_eta_th_differs_between_ideal_and_nasa_at_high_temperature(self) -> None:
        """NasaFluid and IdealGasFluid must disagree by > 0.5 pt at T_max=1300 K.

        At 1300 K the cp difference across the cycle is ~8%, so η_th differs
        by several percentage points. This is documented in
        test_ideal_brayton_property.py::TestIdealBraytonModeContract.
        """
        from cascade.cycle.solver import solve_cycle

        project_ideal = _build_simple_air_project(PR=8.0, T_max_K=1300.0)
        project_nasa = _build_simple_air_project(PR=8.0, T_max_K=1300.0)
        project_nasa["settings"]["air_standard"] = False

        fluid_ideal = _select_fluid_from_project(project_ideal)
        fluid_nasa = _select_fluid_from_project(project_nasa)

        result_ideal = solve_cycle(_build_spec_from_project(project_ideal), fluid=fluid_ideal)
        result_nasa = solve_cycle(_build_spec_from_project(project_nasa), fluid=fluid_nasa)

        delta = abs(result_ideal.thermal_efficiency - result_nasa.thermal_efficiency)
        assert delta > 0.005, (
            f"IdealGasFluid and NasaFluid should disagree by > 0.5 pt at T_max=1300 K; "
            f"delta = {delta * 100:.3f} pt. If they agree, the mode switch may be broken."
        )
