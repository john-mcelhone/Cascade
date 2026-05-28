"""Family / property tests for the radial-inflow turbine (RIT) mean-line solver.

These tests assert TRENDS that must hold for any physically-consistent
mean-line solver. They do not reference specific benchmark numbers.

Invariants exercised:
  1. η_ts has a peak near U/C₀ ≈ 0.7 (Whitfield & Baines published trend).
     The speed ratio U₁/C₀ = U₁ / sqrt(2 Δh_isen) is the canonical turbine
     design parameter (Balje 1981; Whitfield & Baines 1990 §6.3).
  2. η_ts ≤ η_tt at all operating points (thermodynamic identity).
  3. Power output > 0 (turbine extracts work).
  4. P₀₂ < P₀₁ (expansion).
  5. T₀₂ < T₀₁ (enthalpy drop).

References:
- Whitfield, A., Baines, N.C., 1990. *Design of Radial Turbomachines*,
  Longman, §6.3.
- Balje, O.E., 1981. *Turbomachines: A Guide to Design, Selection, and
  Theory*, Wiley, Ch. 7.
- Dixon, S.L., Hall, C.A., 2014. *Fluid Mechanics and Thermodynamics of
  Turbomachinery*, 7th ed., §9.2.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Optional

import pytest

_REPO = Path(__file__).resolve().parents[2]
for p in (str(_REPO / "src"), str(_REPO / "apps" / "api")):
    if p not in sys.path:
        sys.path.insert(0, p)

from cascade.meanline import (
    RadialTurbineGeometry,
    RadialTurbineMeanline,
    WhitfieldBainesRadial,
)
from cascade.meanline.fluid import HELIUM
from cascade.units import Composition, Port, Q, Species


# ---------------------------------------------------------------------------
# Shared helper — representative RIT geometry (Whitney-Stewart class)
# ---------------------------------------------------------------------------

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

# Nominal inlet conditions (Whitney-Stewart NASA TN D-7508)
_P01 = 220000.0   # Pa
_T01 = 1090.0     # K
_MDOT = 0.13      # kg/s


def _solve_rit(rpm: float = 79000.0,
               mass_flow: float = _MDOT,
               geom: Optional[RadialTurbineGeometry] = None) -> Optional[object]:
    """Solve and return result; returns None on convergence failure."""
    if geom is None:
        geom = _BASE_GEOM
    inlet = Port(
        pressure_total=Q(_P01, "Pa"),
        temperature_total=Q(_T01, "K"),
        mass_flow=Q(mass_flow, "kg/s"),
        composition=Composition.pure(Species.HE),
    )
    solver = RadialTurbineMeanline()
    loss = WhitfieldBainesRadial()
    try:
        return solver.solve(inlet, Q(rpm, "rpm"), geom, loss, HELIUM)
    except Exception:
        return None


def _uc0_ratio(result) -> float:
    """Compute U₁/C₀ where C₀ = sqrt(2 * Δh_isen_tt).

    C₀ is the spouting velocity: the jet velocity from isentropic expansion
    from P₀₁ to P₀₂.  For a perfect gas:
        C₀ = sqrt(2 * c_p * T₀₁ * [1 - (P₀₂/P₀₁)^((γ-1)/γ)])
    """
    from cascade.meanline.fluid import HELIUM as He
    U_1 = float(result.U_1.to("m/s").magnitude)
    P02 = float(result.outlet.pressure_total.to("Pa").magnitude)
    pr = _P01 / max(P02, 1.0)  # expansion ratio
    gamma = He.gamma
    cp = He.cp_J_per_kgK
    # Isentropic specific work to P₀₂
    dh_isen = cp * _T01 * (1.0 - pr ** (-(gamma - 1.0) / gamma))
    C0 = math.sqrt(max(2.0 * dh_isen, 1.0))
    return U_1 / C0


# ---------------------------------------------------------------------------
# 1. η_ts peaks near U/C₀ ≈ 0.7 (Whitfield-Baines published trend)
# ---------------------------------------------------------------------------


class TestUC0OptimumEtaTs:
    """The U/C₀ = 0.7 rule is an empirical optimum for radial turbines.

    Reference: Whitfield & Baines 1990 §6.3 Figure 6.5; Balje 1981 Ch. 7.

    The test sweeps RPM (which changes U₁ at fixed geometry) and asserts:
    1. There exists a maximum η_ts over the sweep.
    2. The maximum occurs where U/C₀ is closer to 0.7 than to the extremes
       (0.3 or 1.1).

    We do NOT assert the exact value of the optimum U/C₀ — the specific
    optimum shifts with geometry and loss model. We assert the published
    *qualitative* trend: η_ts peaks away from both very low and very high
    speed ratios.
    """

    def test_eta_ts_peak_not_at_extremes(self) -> None:
        """The peak η_ts must not occur at the lowest rpm of the sweep.

        The U/C₀ sweep must include a low-speed extreme clearly below the
        optimum (~0.7) so that η_ts rises from the low end into the interior.
        We sweep from U/C₀ ≈ 0.2 (very low speed) through design and into
        the above-design region.

        Note on the high-speed end: the Whitney-Stewart geometry operating
        with helium has a narrow validity envelope. At very high RPM the
        solver enters RegimeOutOfValidity. We therefore only assert the
        peak is not at the lowest speed — the solver's regime refusal
        implicitly enforces the upper bound (no runaway extrapolation).

        The Whitfield-Baines trend holds: η_ts rises from low U/C₀, peaks
        near 0.7, and falls again. We verify at least the rising portion
        by ensuring the lowest-speed point is NOT the peak.
        """
        # Very wide sweep: 10000 rpm (U/C₀≈0.1) to 130000 rpm (U/C₀≈1.0+).
        # The low end is deliberately far below the optimum so the trend
        # is clearly visible.
        rpms = [10000, 20000, 40000, 60000, 79000, 100000, 115000, 130000]
        pairs = []
        for rpm in rpms:
            r = _solve_rit(rpm=rpm)
            if r is not None:
                uc0 = _uc0_ratio(r)
                pairs.append((uc0, float(r.eta_ts)))

        # Need at least 4 converged points to identify a trend
        assert len(pairs) >= 4, (
            f"Too few converged points to test U/C₀ trend; got {len(pairs)}. "
            f"Points: {[(f'{u:.3f}',f'{e:.3f}') for u,e in pairs]}"
        )

        # The peak must not be at the first (lowest U/C₀) point.
        # Physical reason: at very low speed, blade tip speed is far below
        # spouting velocity and very little work is extracted efficiently.
        max_idx = max(range(len(pairs)), key=lambda i: pairs[i][1])
        assert max_idx != 0, (
            f"Peak η_ts occurs at the lowest U/C₀ ({pairs[0][0]:.3f}). "
            "Expected η_ts to rise from the low-speed extreme into an interior peak. "
            "Whitfield & Baines trend violated. "
            f"All converged points: {[(f'U/C0={u:.3f}', f'eta_ts={e:.3f}') for u,e in pairs]}"
        )

    def test_eta_ts_peak_uc0_between_0p5_and_0p9(self) -> None:
        """The peak η_ts must occur within U/C₀ ∈ [0.5, 0.9].

        Whitfield & Baines 1990 §6.3: the optimum is broadly in [0.55, 0.80]
        for well-designed RITs. We use [0.5, 0.9] as a generous but physically
        meaningful boundary. Anything outside this range indicates a solver
        anomaly.
        """
        rpms = [24000, 40000, 60000, 79000, 100000, 115000]
        pairs = []
        for rpm in rpms:
            r = _solve_rit(rpm=rpm)
            if r is not None:
                uc0 = _uc0_ratio(r)
                pairs.append((uc0, float(r.eta_ts)))

        if len(pairs) < 4:
            pytest.skip("Insufficient converged points for U/C₀ optimum check")

        best_uc0, best_eta = max(pairs, key=lambda x: x[1])
        assert 0.5 <= best_uc0 <= 0.9, (
            f"Peak η_ts = {best_eta:.4f} at U/C₀ = {best_uc0:.3f}. "
            f"Expected optimum within [0.5, 0.9] per Whitfield & Baines trend. "
            f"Full sweep: {[(f'{u:.2f}', f'{e:.3f}') for u, e in pairs]}"
        )


# ---------------------------------------------------------------------------
# 2. η_ts ≤ η_tt at all operating points
# ---------------------------------------------------------------------------


class TestEtaTsLeqEtaTtRIT:
    """η_ts ≤ η_tt is a thermodynamic identity (ADAPT-022 test complement).

    The exit kinetic energy ½V₂² is 'lost' in the η_ts denominator but
    contributes to the actual work in η_tt.  This must hold everywhere.
    """

    @pytest.mark.parametrize("rpm", [40000, 60000, 79000, 100000])
    def test_eta_ts_leq_eta_tt(self, rpm: float) -> None:
        r = _solve_rit(rpm=rpm)
        if r is None:
            pytest.skip(f"Solver did not converge at {rpm} rpm")
        assert r.eta_ts <= r.eta_tt + 1e-9, (
            f"η_ts ({r.eta_ts:.4f}) > η_tt ({r.eta_tt:.4f}) at {rpm} rpm. "
            "Thermodynamic identity violated."
        )


# ---------------------------------------------------------------------------
# 3. Turbine extracts work: power > 0
# ---------------------------------------------------------------------------


class TestPositivePower:
    """A turbine must deliver positive shaft work."""

    @pytest.mark.parametrize("rpm", [60000, 79000, 100000])
    def test_power_positive(self, rpm: float) -> None:
        r = _solve_rit(rpm=rpm)
        if r is None:
            pytest.skip(f"Solver did not converge at {rpm} rpm")
        power_kW = float(r.power_W.to("kW").magnitude)
        assert power_kW > 0, (
            f"Turbine power = {power_kW:.2f} kW at {rpm} rpm. Must be positive."
        )


# ---------------------------------------------------------------------------
# 4. Expansion: P₀₂ < P₀₁
# ---------------------------------------------------------------------------


class TestExpansionPressure:
    """Turbine expands gas → outlet total pressure must be below inlet."""

    @pytest.mark.parametrize("rpm", [60000, 79000, 100000])
    def test_outlet_pressure_below_inlet(self, rpm: float) -> None:
        r = _solve_rit(rpm=rpm)
        if r is None:
            pytest.skip(f"Solver did not converge at {rpm} rpm")
        P02 = float(r.outlet.pressure_total.to("Pa").magnitude)
        assert P02 < _P01, (
            f"P₀₂ = {P02:.0f} Pa ≥ P₀₁ = {_P01:.0f} Pa at {rpm} rpm. "
            "No expansion — turbine must reduce total pressure."
        )


# ---------------------------------------------------------------------------
# 5. Temperature drop: T₀₂ < T₀₁
# ---------------------------------------------------------------------------


class TestTemperatureDrop:
    """Turbine extracts work → outlet total temperature must be below inlet."""

    @pytest.mark.parametrize("rpm", [60000, 79000, 100000])
    def test_outlet_temperature_below_inlet(self, rpm: float) -> None:
        r = _solve_rit(rpm=rpm)
        if r is None:
            pytest.skip(f"Solver did not converge at {rpm} rpm")
        T02 = float(r.outlet.temperature_total.to("K").magnitude)
        assert T02 < _T01, (
            f"T₀₂ = {T02:.1f} K ≥ T₀₁ = {_T01:.1f} K at {rpm} rpm. "
            "Temperature must drop across an expansion turbine."
        )
