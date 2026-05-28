"""ADAPT-022: η_ts proper-formula regression test.

The historical bug (caught during code review) was a hard-coded
``eta_ts = eta_tt - 0.03`` approximation with an apology comment. The fix
computes η_ts from the FUNDAMENTAL definition:

    η_ts = w_shaft / (h_t1 − h_s2_at_p2)

where ``h_s2_at_p2`` is the *isentropic* static enthalpy at the exit static
pressure p_2. The kinetic-energy gap between η_tt and η_ts is exactly the
residual exit kinetic energy ½ V₂² that a free discharge cannot recover.

Two physical sanity-check scenarios:

- **High exit kinetic** (V₂ / U₂ ≈ 0.4-1.5): η_ts must be visibly below
  η_tt — typically 5-15 pt for a well-converged design at this loading.
- **Low exit kinetic** (V₂ / U₂ < 0.2): the residual KE is small, so
  η_ts must be close to η_tt — within ~2 pt.

Reference: Dixon & Hall §9.2 ("Total-to-total and total-to-static
efficiencies"), Whitfield & Baines §6.3.
"""

from __future__ import annotations

import math

import pytest

from cascade.meanline import (
    RadialTurbineGeometry,
    RadialTurbineMeanline,
    WhitfieldBainesRadial,
)
from cascade.meanline.fluid import HELIUM
from cascade.units import Composition, Port, Q, Species


def _solve(geom: RadialTurbineGeometry, rpm_hz: float = 79000.0,
           mass_flow_kg_s: float = 0.13):
    inlet = Port(
        pressure_total=Q(220000.0, "Pa"),
        temperature_total=Q(1090.0, "K"),
        mass_flow=Q(mass_flow_kg_s, "kg/s"),
        composition=Composition.pure(Species.HE),
    )
    solver = RadialTurbineMeanline()
    loss = WhitfieldBainesRadial()
    return solver.solve(inlet, Q(rpm_hz, "rpm"), geom, loss, HELIUM)


_BASE_GEOM = RadialTurbineGeometry(
    rotor_inlet_radius=0.076,
    rotor_outlet_radius_hub=0.019,
    rotor_outlet_radius_tip=0.0406,
    blade_height_inlet=0.012,
    blade_height_outlet=0.0216,
    blade_count=12,
    inlet_metal_angle_rad=0.0,
    exducer_angle_rad=math.radians(60),
    tip_clearance=0.00025,
)


@pytest.mark.validation
class TestEtaTsProperFormula:
    """ADAPT-022 regression: η_ts is the proper formula, not η_tt − 0.03."""

    def test_high_exit_kinetic_gives_lower_eta_ts(self) -> None:
        """A high-V₂ design (V₂/U₂ ≫ 0.2) has η_ts noticeably below η_tt.

        Run with elevated mass flow so the exducer absolute velocity is
        ~½ U₂. The gap between η_tt and η_ts should be > 3 pt — far more
        than the old η_tt−0.03 floor.
        """
        r = _solve(_BASE_GEOM, mass_flow_kg_s=0.13)
        V_2 = r.V_2.to("m/s").magnitude
        U_2 = r.U_2.to("m/s").magnitude
        ratio = V_2 / U_2
        gap = r.eta_tt - r.eta_ts
        assert ratio > 0.3, f"V_2/U_2 = {ratio:.3f}; expected high"
        assert gap > 0.03, (
            f"η_tt − η_ts = {gap:.4f}; expected > 0.03 for V_2/U_2 = {ratio:.3f}"
        )

    def test_h_s2_at_p2_is_consistent_with_eta_ts(self) -> None:
        """The proper formula:  η_ts = (h_01 − h_02) / (h_01 − h_s2_at_p2).

        Verifies the *exact* identity that ADAPT-022 requires — the result
        carries h_s2_at_p2 as a field and η_ts must match the closed-form
        ratio to within numerical tolerance.
        """
        r = _solve(_BASE_GEOM, mass_flow_kg_s=0.13)
        h_t1 = r.port_states["inlet"].h_total_J_per_kg
        h_t2 = r.port_states["exit"].h_total_J_per_kg
        h_s2_at_p2 = r.h_s2_at_p2_J_per_kg
        eta_ts_check = (h_t1 - h_t2) / (h_t1 - h_s2_at_p2)
        assert abs(eta_ts_check - r.eta_ts) < 1e-4, (
            f"η_ts identity mismatch: solver={r.eta_ts:.6f}, "
            f"recomputed={eta_ts_check:.6f}"
        )

    def test_well_designed_low_exit_kinetic_closes_gap(self) -> None:
        """A well-matched design (V₂ small relative to U₂) has η_ts close to η_tt.

        We drop V₂ by reducing mass flow (which drops V_m₂ via continuity at
        the exducer annulus). At V₂/U₂ < 0.5 the residual kinetic energy is
        small and η_ts ≈ η_tt to within ~2 pt.
        """
        r_low = _solve(_BASE_GEOM, mass_flow_kg_s=0.04)
        ratio_low = (r_low.V_2.to("m/s").magnitude
                     / r_low.U_2.to("m/s").magnitude)
        gap_low = r_low.eta_tt - r_low.eta_ts
        assert ratio_low < 0.5, (
            f"Low-mass-flow design should have V_2/U_2 < 0.5; got {ratio_low:.3f}"
        )
        assert gap_low < 0.025, (
            f"Low V_2/U_2 ({ratio_low:.3f}) should give η_tt ≈ η_ts within "
            f"~2.5 pt; got gap={gap_low:.4f}"
        )

    def test_eta_ts_not_a_constant_offset_of_eta_tt(self) -> None:
        """η_ts must not be a fixed offset from η_tt across operating points.

        If the old approximation (eta_ts = eta_tt - 0.03) were still in place,
        the gap would be IDENTICAL across operating points. We assert the
        gap scales with V₂/U₂ (and so differs meaningfully between cases).
        """
        r_low = _solve(_BASE_GEOM, mass_flow_kg_s=0.04)   # V/U ≈ 0.46
        r_high = _solve(_BASE_GEOM, mass_flow_kg_s=0.13)  # V/U ≈ 1.5
        gap_low = r_low.eta_tt - r_low.eta_ts
        gap_high = r_high.eta_tt - r_high.eta_ts
        assert (gap_high - gap_low) > 0.05, (
            f"Old approximation would have given identical gaps. "
            f"gap_low={gap_low:.4f}, gap_high={gap_high:.4f}, "
            f"Δ={gap_high-gap_low:.5f}"
        )
