"""W-08: Analysis page smoke test — real solver integration.

Verifies that the analysis router calls the real mean-line solver and
returns physically sensible results (not hardcoded constants).

Acceptance criteria (W-08):
1. Create a test project (uses Whitney-Stewart NASA TN D-7508 geometry)
2. Call the analysis solver equivalent (_solve_radial_turbine directly)
3. Assert h_s_states length > 2
4. Assert 0 < eta_tt < 1
5. Assert convergence_history has >= 3 entries
6. Assert loss_breakdown has >= 4 named terms

References:
- W-08 (Analysis page smoke test)
- ADAPT-020
- apps/api/routers/analysis.py
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


# Whitney-Stewart NASA TN D-7508 radial turbine geometry
# This is the RIT-1 validation case — used here as a known-good analysis input.
_RADIAL_TURBINE_GEOM = {
    "rotor_inlet_radius": 0.076,
    "rotor_outlet_radius_hub": 0.019,
    "rotor_outlet_radius_tip": 0.0406,
    "blade_height_inlet": 0.012,
    "blade_height_outlet": 0.0216,
    "blade_count": 12,
    "inlet_metal_angle_rad": 0.0,
    "exducer_angle_rad": math.radians(60.0),
    "tip_clearance": 0.00025,
}

_RADIAL_TURBINE_OP = {
    "pressure_total_Pa": 220000.0,
    "temperature_total_K": 1090.0,
    "mass_flow_kg_per_s": 0.13,
    "rpm": 79000.0,
    "fluid": "air",
}


@pytest.fixture(scope="module")
def radial_turbine_result():
    """Run the real mean-line solver once for the module."""
    from routers.analysis import _solve_radial_turbine
    return _solve_radial_turbine(
        _RADIAL_TURBINE_GEOM,
        _RADIAL_TURBINE_OP,
        "whitfield-baines-radial-v1",
    )


def test_h_s_states_length_greater_than_2(radial_turbine_result) -> None:
    """AC-3: h_s_states must have > 2 entries.

    The h-s diagram needs at minimum: inlet total, rotor LE static,
    rotor TE static, rotor TE total = 4 stations.
    """
    result = radial_turbine_result
    h_s = result.get("h_s_states", [])
    assert len(h_s) > 2, (
        f"h_s_states has {len(h_s)} entries; need > 2 for a meaningful "
        f"h-s diagram. Hardcoded fallback may be active."
    )
    # Each state should have h and s fields.
    for i, state in enumerate(h_s):
        assert "h_J_per_kg" in state or "h" in state, (
            f"h_s_states[{i}] missing enthalpy field: {state}"
        )


def test_eta_tt_in_physical_range(radial_turbine_result) -> None:
    """AC-4: 0 < eta_tt < 1 (physical efficiency range)."""
    result = radial_turbine_result
    efficiencies = result.get("efficiencies", {})
    eta_tt = efficiencies.get("eta_tt", result.get("eta_total", -1.0))
    assert 0 < eta_tt < 1, (
        f"eta_tt = {eta_tt}. Must be in (0, 1) for a real turbine solve. "
        f"Hardcoded constant or solver failure."
    )


def test_eta_ts_in_physical_range(radial_turbine_result) -> None:
    """eta_ts must also be in (0, 1) and <= eta_tt."""
    result = radial_turbine_result
    efficiencies = result.get("efficiencies", {})
    eta_ts = efficiencies.get("eta_ts", -1.0)
    eta_tt = efficiencies.get("eta_tt", result.get("eta_total", 1.0))
    assert 0 < eta_ts < 1, (
        f"eta_ts = {eta_ts}. Must be in (0, 1)."
    )
    assert eta_ts <= eta_tt + 0.001, (
        f"eta_ts ({eta_ts:.4f}) > eta_tt ({eta_tt:.4f}). "
        f"ADAPT-022 proper eta_ts formula may have regressed."
    )


def test_convergence_history_has_at_least_3_entries(radial_turbine_result) -> None:
    """AC-5: convergence_history must have >= 3 entries (solver iterated)."""
    result = radial_turbine_result
    history = result.get("convergence_history", [])
    assert len(history) >= 3, (
        f"convergence_history has {len(history)} entries; need >= 3. "
        f"The Newton inner loop runs multiple iterations for a real solve."
    )


def test_loss_breakdown_has_at_least_4_named_terms(radial_turbine_result) -> None:
    """AC-6: loss_breakdown must have >= 4 named terms."""
    result = radial_turbine_result
    breakdown = result.get("loss_breakdown", [])
    assert len(breakdown) >= 4, (
        f"loss_breakdown has {len(breakdown)} terms; need >= 4. "
        f"Whitfield-Baines model produces: incidence, profile, secondary, "
        f"trailing_edge, tip_clearance, scroll, exducer."
    )
    # Each entry must have a 'name' field.
    for entry in breakdown:
        assert "name" in entry, f"loss_breakdown entry missing 'name': {entry}"


def test_loss_breakdown_values_are_positive(radial_turbine_result) -> None:
    """All loss_breakdown delta_h values must be >= 0 (entropy production)."""
    result = radial_turbine_result
    breakdown = result.get("loss_breakdown", [])
    for entry in breakdown:
        dh = entry.get("delta_h_J_per_kg", entry.get("value_kJ_per_kg", 0.0))
        assert dh >= 0, (
            f"Loss term '{entry.get('name')}' has negative delta_h = {dh}. "
            f"All losses must increase entropy (positive Δh)."
        )


def test_velocity_triangles_present(radial_turbine_result) -> None:
    """velocity_triangles in result — confirms ADAPT-021 is also wired."""
    result = radial_turbine_result
    vt = result.get("velocity_triangles", {})
    assert "inlet" in vt, (
        "velocity_triangles missing 'inlet'. ADAPT-021 may have regressed."
    )
    assert "exit" in vt, (
        "velocity_triangles missing 'exit'. ADAPT-021 may have regressed."
    )


def test_analysis_deterministic(radial_turbine_result) -> None:
    """Two calls with the same input must produce the same eta_tt."""
    from routers.analysis import _solve_radial_turbine

    result2 = _solve_radial_turbine(
        _RADIAL_TURBINE_GEOM,
        _RADIAL_TURBINE_OP,
        "whitfield-baines-radial-v1",
    )
    r1 = radial_turbine_result
    eta1 = r1.get("efficiencies", {}).get("eta_tt", r1.get("eta_total"))
    eta2 = result2.get("efficiencies", {}).get("eta_tt", result2.get("eta_total"))
    assert abs(eta1 - eta2) < 1e-10, (
        f"Analysis is not deterministic: eta_tt={eta1:.8f} vs {eta2:.8f}. "
        f"Stochastic behavior detected."
    )
