"""ADAPT-027 regression — cycle solver refuses NaN / Inf / non-positive input.

Previously the solver returned η_th = NaN or 0.30 silently when fed garbage
boundary-port data. This test pins down the refusal contract: any non-finite
or non-positive mass flow, total pressure, or total temperature on the inlet
boundary raises ValueError before any property evaluation.

Each input is constructed via a `Port`-bypassing path because `Port` itself
already refuses some of these via dimension/sign checks. The solver does its
own redundant validation as defense in depth, and that's what we test here.
"""

from __future__ import annotations

import math

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
def air_standard_fluid() -> IdealGasFluid:
    return IdealGasFluid(cp=Q(1005.0, "J/(kg*K)"), gamma=1.4)


def _make_spec(inlet: Port) -> SimpleBraytonSpec:
    """A small valid spec parametrized on the inlet port."""
    return SimpleBraytonSpec(
        inlet_port=inlet,
        compressor=Compressor(
            name="compressor",
            pressure_ratio=4.0,
            efficiency_isentropic=0.85,
        ),
        burner=Burner(
            name="burner",
            pressure_drop_fraction=0.0,
            combustion_efficiency=1.0,
            outlet_temperature=Q(1200.0, "K"),
            air_standard=True,
        ),
        turbine=Turbine(
            name="turbine",
            pressure_ratio=4.0,
            efficiency_isentropic=0.85,
        ),
        cycle_type="open",
    )


def _make_inlet_skipping_post_init(
    *,
    p_t_Pa: float,  # noqa: N803
    T_t_K: float,  # noqa: N803
    mass_flow_kgs: float,
) -> Port:
    """Construct a Port without invoking its own validation.

    The cycle solver's defense-in-depth check exists *because* a Port can be
    constructed via paths the Port's own __post_init__ wouldn't catch (e.g.
    NaN values that satisfy dimensionality but violate physics, or future
    construction paths bypassing the dataclass init). We bypass the
    __post_init__ here by using object.__setattr__ on a Port instance
    constructed from a sentinel.
    """
    # Build a valid Port first, then mutate its frozen fields.
    sentinel = Port(
        pressure_total=Q(101325.0, "Pa"),
        temperature_total=Q(300.0, "K"),
        mass_flow=Q(1.0, "kg/s"),
        composition=Composition.air(),
    )
    object.__setattr__(sentinel, "pressure_total", Q(p_t_Pa, "Pa"))
    object.__setattr__(sentinel, "temperature_total", Q(T_t_K, "K"))
    object.__setattr__(sentinel, "mass_flow", Q(mass_flow_kgs, "kg/s"))
    return sentinel


class TestSolverInputValidation:
    """ADAPT-027: solver-entry boundary-port validation."""

    def test_nan_mass_flow_refused(
        self, air_standard_fluid: IdealGasFluid
    ) -> None:
        inlet = _make_inlet_skipping_post_init(
            p_t_Pa=101325.0,
            T_t_K=288.0,
            mass_flow_kgs=float("nan"),
        )
        with pytest.raises(ValueError, match="mass_flow"):
            solve_cycle(_make_spec(inlet), fluid=air_standard_fluid)

    def test_negative_mass_flow_refused(
        self, air_standard_fluid: IdealGasFluid
    ) -> None:
        inlet = _make_inlet_skipping_post_init(
            p_t_Pa=101325.0,
            T_t_K=288.0,
            mass_flow_kgs=-1.0,
        )
        with pytest.raises(ValueError, match="mass_flow"):
            solve_cycle(_make_spec(inlet), fluid=air_standard_fluid)

    def test_inf_mass_flow_refused(
        self, air_standard_fluid: IdealGasFluid
    ) -> None:
        inlet = _make_inlet_skipping_post_init(
            p_t_Pa=101325.0,
            T_t_K=288.0,
            mass_flow_kgs=math.inf,
        )
        with pytest.raises(ValueError, match="mass_flow"):
            solve_cycle(_make_spec(inlet), fluid=air_standard_fluid)

    def test_zero_pressure_refused(
        self, air_standard_fluid: IdealGasFluid
    ) -> None:
        inlet = _make_inlet_skipping_post_init(
            p_t_Pa=0.0,
            T_t_K=288.0,
            mass_flow_kgs=1.0,
        )
        with pytest.raises(ValueError, match="p_t"):
            solve_cycle(_make_spec(inlet), fluid=air_standard_fluid)

    def test_nan_temperature_refused(
        self, air_standard_fluid: IdealGasFluid
    ) -> None:
        inlet = _make_inlet_skipping_post_init(
            p_t_Pa=101325.0,
            T_t_K=float("nan"),
            mass_flow_kgs=1.0,
        )
        with pytest.raises(ValueError, match="T_t"):
            solve_cycle(_make_spec(inlet), fluid=air_standard_fluid)
