"""ADAPT-011 regression — Open Brayton refuses PR_turbine > PR_compressor + slack.

The cycle solver previously accepted a project with PR_compressor=4 and
PR_turbine=6, solving to η_th ≈ 52.56% with an exhaust pressure of about
12.5 kPa — sub-atmospheric, physically impossible for an open-cycle Brayton
venting to ambient. The solver now enforces the topological invariant that
the turbine's expansion ends at ambient (within a 1% slack).

This test pins down:
1. A mismatched-PR open cycle is refused.
2. A balanced-PR open cycle solves cleanly.
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


def _make_open_brayton(pr_c: float, pr_t: float) -> SimpleBraytonSpec:
    """Build a textbook simple Brayton with the given compressor/turbine PRs.

    Inlet: 101.325 kPa, 288 K; TIT = 1200 K; air-standard analysis so the
    test is invariant to real-gas effects. The solver sees a feedforward
    topology with a turbine expansion that ends below ambient when
    PR_t > PR_c (no pressure losses to absorb the slack).
    """
    inlet = Port(
        pressure_total=Q(101.325, "kPa"),
        temperature_total=Q(288.0, "K"),
        mass_flow=Q(1.0, "kg/s"),
        composition=Composition.air(),
    )
    return SimpleBraytonSpec(
        inlet_port=inlet,
        compressor=Compressor(
            name="compressor",
            pressure_ratio=pr_c,
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
            pressure_ratio=pr_t,
            efficiency_isentropic=0.85,
        ),
        mechanical_efficiency=1.0,
        generator_efficiency=1.0,
        cycle_type="open",
    )


@pytest.fixture
def air_standard_fluid() -> IdealGasFluid:
    return IdealGasFluid(cp=Q(1005.0, "J/(kg*K)"), gamma=1.4)


class TestOpenCycleSubAtmosphericRefusal:
    """ADAPT-011: refuse open cycles whose exhaust ends below ambient."""

    def test_pr_turbine_greater_than_pr_compressor_refused(
        self, air_standard_fluid: IdealGasFluid
    ) -> None:
        # PR_c = 4, PR_t = 6 → exhaust = 101.325 * 4 / 6 ≈ 67.5 kPa,
        # well below the 1% slack against ambient 101.325 kPa.
        spec = _make_open_brayton(pr_c=4.0, pr_t=6.0)
        with pytest.raises(Exception) as exc_info:
            solve_cycle(spec, fluid=air_standard_fluid)
        # Message must clearly call out the topological violation.
        msg = str(exc_info.value)
        assert ("below ambient" in msg) or ("PR_turbine" in msg)

    def test_balanced_pr_solves_cleanly(
        self, air_standard_fluid: IdealGasFluid
    ) -> None:
        # PR_c = PR_t = 4 → exhaust matches ambient exactly.
        spec = _make_open_brayton(pr_c=4.0, pr_t=4.0)
        result = solve_cycle(spec, fluid=air_standard_fluid)
        # Sanity: efficiency is dimensionless and within sane bounds.
        assert 0.0 < result.thermal_efficiency < 1.0

    def test_closed_cycle_with_pr_mismatch_skipped(
        self, air_standard_fluid: IdealGasFluid
    ) -> None:
        """ADAPT-011: cycle_type='closed' (sCO2 etc) skips the exhaust check.

        A closed cycle has the working fluid recirculating through a cooler
        back to the compressor inlet; the algebra need not end at ambient.
        We don't run a CYC-3-style sCO2 case here — just confirm that the
        same PR mismatch that would refuse an open cycle does not refuse
        when the cycle is declared closed.
        """
        spec = _make_open_brayton(pr_c=4.0, pr_t=6.0)
        spec.cycle_type = "closed"
        # Should not raise the open-cycle exhaust check. The solver may
        # still produce a physically odd result — that's OK; the test is
        # that the open-cycle gate is bypassed.
        result = solve_cycle(spec, fluid=air_standard_fluid)
        assert result is not None
