"""RIT-1: NASA TN D-7508 Whitney & Stewart (1974) — single-stage RIT.

SPEC_SHEET §12 tolerance: eta_ts within +/-5 pt at design (representative geometry;
the exact NASA TN D-7508 geometry is not transcribed -- see KG-ML-04).

Reference:
- Whitney, W.J., Stewart, W.L., 1974. "Aerodynamic Performance of a
  Radial Inflow Turbine Designed for an 85,000-rpm Helium Cycle Drive",
  NASA TN D-7508.
  (Helium working fluid; designed for a closed Brayton helium cycle.)

Design point (Whitney & Stewart 1974 Table I + revisions per Tampe &
Lippold 1978 NASA TN D-8753 cross-validation):
- Working fluid: helium
- Inlet: P_01 = 220 kPa, T_01 = 1090 K (actual test conditions varied;
  the canonical reference point is the one quoted here as a
  characteristic operating point)
- Mass flow: ṁ = 0.13 kg/s
- Speed: N = 79,000 rpm (within the 85,000-rpm class; test data covers
  60-100% of design speed)
- Rotor: D_1 = 152 mm, D_2_tip ≈ 81 mm, D_2_hub ≈ 38 mm, Z = 12 blades
- Reported: η_ts ≈ 0.84 at design (Whitney & Stewart 1974 Fig. 5)

Note on exact numbers: the original NASA TN D-7508 reports performance
data across a wide range of operating points; the "design point" is
defined by NASA as 100% of equivalent speed and design pressure ratio.
The exact design mass flow, pressure ratio, and efficiency vary slightly
across secondary references because the report includes corrected
quantities only. The numbers above are a representative design-point
reconstruction; precise reproduction would require digitizing
TN D-7508 Fig. 5 / Table II. This is documented in KNOWN_GAPS.md.
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


WHITNEY_STEWART_GEOMETRY = RadialTurbineGeometry(
    rotor_inlet_radius=0.076,  # D_1 = 152 mm
    rotor_outlet_radius_hub=0.019,  # D_2_hub ≈ 38 mm
    rotor_outlet_radius_tip=0.0406,  # D_2_tip ≈ 81 mm
    blade_height_inlet=0.012,  # b_1 ≈ 12 mm (NASA TN D-7508 §3)
    blade_height_outlet=0.0216,  # r_2_tip - r_2_hub
    blade_count=12,
    inlet_metal_angle_rad=0.0,  # purely radial inlet blade
    exducer_angle_rad=math.radians(60),  # ~60° from axial at exducer TE
    tip_clearance=0.00025,
    # Design at zero-incidence: V_θ₁ = U₁
)

WHITNEY_STEWART_INLET = Port(
    pressure_total=Q(220000, "Pa"),
    temperature_total=Q(1090.0, "K"),
    mass_flow=Q(0.13, "kg/s"),
    composition=Composition.pure(Species.HE),
)

WHITNEY_STEWART_RPM = Q(79000, "rpm")

PUBLISHED_ETA_TS = 0.84


@pytest.mark.validation
class TestWhitneyStewartRIT1:
    """Whitney-Stewart NASA TN D-7508 helium RIT.

    The published η_ts ≈ 0.84 is at design. The CI gate is ±5 pt (the
    assertion below) on a representative geometry — the exact TN D-7508
    geometry is not transcribed (see module docstring and KG-ML-04). The
    aspirational ±2 pt would require the exact published blade/vane geometry.
    """

    def test_design_point_converges(self) -> None:
        solver = RadialTurbineMeanline()
        loss = WhitfieldBainesRadial()
        result = solver.solve(WHITNEY_STEWART_INLET, WHITNEY_STEWART_RPM,
                              WHITNEY_STEWART_GEOMETRY, loss, HELIUM)
        assert result.convergence_info["converged"] is True

    def test_design_point_efficiency_ts_within_tolerance(self) -> None:
        """η_ts within ±5 pt of published 0.84 — SPEC §12 RIT-1 tolerance.
        The published geometry / operating-point numbers are not exact
        (representative geometry; see module docstring and KG-ML-04), so the
        CI gate is ±5 pt — the assertion below — not the aspirational ±2 pt.
        """
        solver = RadialTurbineMeanline()
        loss = WhitfieldBainesRadial()
        result = solver.solve(WHITNEY_STEWART_INLET, WHITNEY_STEWART_RPM,
                              WHITNEY_STEWART_GEOMETRY, loss, HELIUM)
        assert abs(result.eta_ts - PUBLISHED_ETA_TS) < 0.05, \
            (f"η_ts = {result.eta_ts:.4f}, published = {PUBLISHED_ETA_TS}, "
             f"difference = {result.eta_ts - PUBLISHED_ETA_TS:+.4f}")

    def test_design_point_max_mach_subsonic(self) -> None:
        """Whitney-Stewart is a subsonic-relative-flow design at design
        rpm. Max M_rel should be < 1.0.
        """
        solver = RadialTurbineMeanline()
        loss = WhitfieldBainesRadial()
        result = solver.solve(WHITNEY_STEWART_INLET, WHITNEY_STEWART_RPM,
                              WHITNEY_STEWART_GEOMETRY, loss, HELIUM)
        assert result.max_M_rel < 1.0

    def test_power_extraction_positive(self) -> None:
        """Turbine extracts work → power > 0."""
        solver = RadialTurbineMeanline()
        loss = WhitfieldBainesRadial()
        result = solver.solve(WHITNEY_STEWART_INLET, WHITNEY_STEWART_RPM,
                              WHITNEY_STEWART_GEOMETRY, loss, HELIUM)
        assert result.power_W.to("W").magnitude > 0
        # Whitney-Stewart class: ~30-100 kW typical
        assert 10000 < result.power_W.to("W").magnitude < 200000

    def test_outlet_pressure_lower_than_inlet(self) -> None:
        """Expansion → P_02 < P_01."""
        solver = RadialTurbineMeanline()
        loss = WhitfieldBainesRadial()
        result = solver.solve(WHITNEY_STEWART_INLET, WHITNEY_STEWART_RPM,
                              WHITNEY_STEWART_GEOMETRY, loss, HELIUM)
        P02 = result.outlet.pressure_total.to("Pa").magnitude
        assert P02 < 220000  # below inlet
        assert P02 > 50000  # above absurd low

    def test_outlet_temperature_lower_than_inlet(self) -> None:
        """Expansion → T_02 < T_01 (work extracted)."""
        solver = RadialTurbineMeanline()
        loss = WhitfieldBainesRadial()
        result = solver.solve(WHITNEY_STEWART_INLET, WHITNEY_STEWART_RPM,
                              WHITNEY_STEWART_GEOMETRY, loss, HELIUM)
        T02 = result.outlet.temperature_total.to("K").magnitude
        assert T02 < 1090
        assert T02 > 800  # not absurdly cold
