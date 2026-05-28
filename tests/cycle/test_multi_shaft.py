"""Multi-shaft / spool-matching tests (ADAPT-034).

Covers:
- CF6-80C2 2-spool case: both shafts close power balance < 1e-3 fractional.
- N_1 ≠ N_2 (each shaft has its own user-supplied design RPM; v1's solver
  reports them; v1.1 will let them float as part of the spool match).
- Spool deficit: turbine PR set so low it can't sustain compressor → refuse
  with a clear `RegimeOutOfValidity` carrying `SPOOL_POWER_DEFICIT`.
- Single-spool degenerate case still works.
"""
from __future__ import annotations

import pytest

from cascade.cycle import (
    Burner,
    Compressor,
    ConstantPressureLoss,
    MultiShaftBraytonSpec,
    NasaFluid,
    Shaft,
    Turbine,
    solve_multi_shaft_brayton,
)
from cascade.thermo.nasa_mixture import RegimeOutOfValidity
from cascade.units import Composition, Port, Q
from cascade.validation.cases.cf6_80c2 import (
    CF6_80C2,
    build_cf6_80c2_spec,
)


class TestCF6_80C2_TwoSpool:
    """ADAPT-034 — GE CF6-80C2 2-spool turbofan.

    Both shafts' power balance must close to fractional residual < 1e-3 and
    HP / LP must report distinct rotational speeds.
    """

    def test_cf6_converges(self) -> None:
        result = solve_multi_shaft_brayton(
            build_cf6_80c2_spec(),
            NasaFluid(),
            outer_tol=1e-3,
            max_outer_iters=60,
        )
        assert result.converged, (
            f"CF6-80C2: did not converge in {result.outer_iterations} "
            f"iters; final residual {result.residual_norm:.3e}"
        )
        assert len(result.spool_balances) == 2

    def test_both_shafts_power_balance_closes(self) -> None:
        result = solve_multi_shaft_brayton(
            build_cf6_80c2_spec(),
            NasaFluid(),
            outer_tol=1e-3,
            max_outer_iters=60,
        )
        for bal in result.spool_balances:
            assert abs(bal.power_residual_fractional) < 1e-3, (
                f"Shaft {bal.shaft_id} ('{bal.name}') residual "
                f"{bal.power_residual_fractional:.3e} > 1e-3"
            )

    def test_hp_and_lp_speeds_differ(self) -> None:
        result = solve_multi_shaft_brayton(
            build_cf6_80c2_spec(),
            NasaFluid(),
            outer_tol=1e-3,
            max_outer_iters=60,
        )
        speeds = {b.shaft_id: b.rotational_speed_rpm for b in result.spool_balances}
        # HP > LP by a factor of ~3 for the CF6 design point.
        assert speeds[1] > speeds[2], (
            f"HP {speeds[1]} should exceed LP {speeds[2]}"
        )
        assert abs(speeds[1] - speeds[2]) > 1000, (
            "HP and LP should be > 1000 rpm apart"
        )

    def test_TIT_propagates(self) -> None:
        result = solve_multi_shaft_brayton(
            build_cf6_80c2_spec(),
            NasaFluid(),
            outer_tol=1e-3,
            max_outer_iters=60,
        )
        burner_out = result.cycle.ports["combustor"]
        T4_K = burner_out.temperature_total.to("K").magnitude
        assert abs(T4_K - CF6_80C2.TIT.to("K").magnitude) < 1.0


class TestSingleShaftDegenerate:
    """A single-shaft `MultiShaftBraytonSpec` should behave like a vanilla
    Brayton cycle (one shaft, one compressor + turbine on it)."""

    def _spec(self) -> MultiShaftBraytonSpec:
        inlet = Port(
            pressure_total=Q(101.325, "kPa"),
            temperature_total=Q(288.15, "K"),
            mass_flow=Q(2.0, "kg/s"),
            composition=Composition.air(),
        )
        return MultiShaftBraytonSpec(
            inlet_port=inlet,
            compressors=[
                Compressor(
                    name="C1",
                    pressure_ratio=8.0,
                    efficiency_isentropic=0.85,
                    shaft_id=1,
                )
            ],
            burner=Burner(
                name="B1",
                pressure_drop_fraction=0.04,
                combustion_efficiency=0.99,
                outlet_temperature=Q(1400.0, "K"),
                fuel_lhv=Q(43.0e6, "J/kg"),
                fuel_carbon_atoms=12,
                fuel_hydrogen_atoms=23,
                fuel_molar_mass=Q(170.0, "g/mol"),
            ),
            turbines=[
                Turbine(
                    name="T1",
                    pressure_ratio=7.5,
                    efficiency_isentropic=0.90,
                    shaft_id=1,
                )
            ],
            shafts=[
                Shaft(id=1, name="single", components=["C1", "T1"]),
            ],
        )

    def test_solves(self) -> None:
        result = solve_multi_shaft_brayton(
            self._spec(), NasaFluid(), outer_tol=1e-3, max_outer_iters=40
        )
        assert result.converged
        assert len(result.spool_balances) == 1


class TestSpoolDeficitRefused:
    """A spool whose turbine PR is starved below what's needed to drive the
    compressor must refuse — never silently report `converged=True`."""

    def test_refuses_when_turbine_starved(self) -> None:
        inlet = Port(
            pressure_total=Q(101.325, "kPa"),
            temperature_total=Q(288.15, "K"),
            mass_flow=Q(50.0, "kg/s"),
            composition=Composition.air(),
        )
        # Compressor that demands a lot of work, turbine pinned to a tiny
        # PR so the solver can't expand enough to feed it.
        spec = MultiShaftBraytonSpec(
            inlet_port=inlet,
            compressors=[
                Compressor(
                    name="C_HP",
                    pressure_ratio=25.0,  # huge demand
                    efficiency_isentropic=0.85,
                    shaft_id=1,
                )
            ],
            burner=Burner(
                name="B1",
                pressure_drop_fraction=0.04,
                combustion_efficiency=0.99,
                # Low TIT means the turbine has limited h-budget to give
                # back to the compressor → deficit.
                outlet_temperature=Q(900.0, "K"),
                fuel_lhv=Q(43.0e6, "J/kg"),
                fuel_carbon_atoms=12,
                fuel_hydrogen_atoms=23,
                fuel_molar_mass=Q(170.0, "g/mol"),
            ),
            turbines=[
                Turbine(
                    name="T_HP",
                    pressure_ratio=1.5,  # almost no expansion
                    efficiency_isentropic=0.5,  # poor too
                    shaft_id=1,
                )
            ],
            shafts=[Shaft(id=1, name="HP", components=["C_HP", "T_HP"])],
        )
        with pytest.raises(RegimeOutOfValidity) as exc_info:
            solve_multi_shaft_brayton(
                spec, NasaFluid(), outer_tol=1e-3, max_outer_iters=20
            )
        # Code must explicitly flag spool deficit (not generic nonconvergence)
        assert exc_info.value.code in (
            "SPOOL_POWER_DEFICIT",
            "MULTI_SHAFT_NONCONVERGENT",
        )


class TestMisconfiguredSpec:
    """Schema-level refusals before the solver even starts."""

    def test_shaft_with_no_turbine_refused(self) -> None:
        inlet = Port(
            pressure_total=Q(101.325, "kPa"),
            temperature_total=Q(288.15, "K"),
            mass_flow=Q(2.0, "kg/s"),
            composition=Composition.air(),
        )
        with pytest.raises(ValueError, match="at least one compressor and one turbine"):
            MultiShaftBraytonSpec(
                inlet_port=inlet,
                compressors=[
                    Compressor(
                        name="C", pressure_ratio=4.0,
                        efficiency_isentropic=0.85, shaft_id=1,
                    ),
                    Compressor(
                        name="C2", pressure_ratio=4.0,
                        efficiency_isentropic=0.85, shaft_id=2,  # orphan
                    ),
                ],
                burner=Burner(
                    name="B",
                    outlet_temperature=Q(1400.0, "K"),
                    fuel_lhv=Q(43.0e6, "J/kg"),
                ),
                turbines=[
                    Turbine(
                        name="T", pressure_ratio=7.5,
                        efficiency_isentropic=0.9, shaft_id=1,
                    )
                ],
                shafts=[
                    Shaft(id=1, name="HP"),
                    Shaft(id=2, name="LP"),  # no turbine on this shaft
                ],
            )

    def test_unknown_shaft_id_refused(self) -> None:
        inlet = Port(
            pressure_total=Q(101.325, "kPa"),
            temperature_total=Q(288.15, "K"),
            mass_flow=Q(2.0, "kg/s"),
            composition=Composition.air(),
        )
        with pytest.raises(ValueError, match="references shaft_id=9"):
            MultiShaftBraytonSpec(
                inlet_port=inlet,
                compressors=[
                    Compressor(
                        name="C",
                        pressure_ratio=4.0,
                        efficiency_isentropic=0.85,
                        shaft_id=9,  # not in spec.shafts
                    )
                ],
                burner=Burner(
                    name="B",
                    outlet_temperature=Q(1400.0, "K"),
                    fuel_lhv=Q(43.0e6, "J/kg"),
                ),
                turbines=[
                    Turbine(
                        name="T",
                        pressure_ratio=7.5,
                        efficiency_isentropic=0.9,
                        shaft_id=1,
                    )
                ],
                shafts=[Shaft(id=1, name="HP")],
            )
