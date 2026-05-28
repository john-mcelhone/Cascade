"""ADAPT-020 locked regression: analysis solver returns real h_s_states.

This test will FAIL if the analysis router is reverted to returning
hardcoded JSX constants or a fake result (the pre-ADAPT-020 state).

Locked invariant: calling the analysis solver for a radial turbine returns
a dict with:
  - h_s_states: list with > 2 entries (h-s diagram stations)
  - efficiencies.eta_tt: float in (0, 1)
  - efficiencies.eta_ts: float in (0, 1)
  - convergence_history: list with >= 3 entries
  - loss_breakdown: list with >= 4 named terms

References:
- ADAPT-020 (regression lock).
- apps/api/routers/analysis.py:230 (_solve_radial_turbine).
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


# Canonical test geometry (radial turbine, air, design point)
_GEOM = {
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

_OP = {
    "pressure_total_Pa": 220000.0,
    "temperature_total_K": 1090.0,
    "mass_flow_kg_per_s": 0.13,
    "rpm": 79000.0,
    "fluid": "air",
}


def test_adapt_020_analysis_returns_real_h_s_states() -> None:
    """Locked: _solve_radial_turbine must return h_s_states with > 2 entries.

    Pre-ADAPT-020: the analysis page returned hardcoded JSX string literals;
    no solver was called. This test will fail immediately if the solver is
    bypassed and h_s_states is returned as an empty list or single entry.
    """
    from routers.analysis import _solve_radial_turbine

    result = _solve_radial_turbine(_GEOM, _OP, "whitfield-baines-radial-v1")

    h_s_states = result.get("h_s_states", [])
    assert isinstance(h_s_states, list), (
        f"h_s_states must be a list; got {type(h_s_states)}"
    )
    assert len(h_s_states) > 2, (
        f"ADAPT-020 regression: h_s_states has {len(h_s_states)} entry/entries. "
        f"Real solver must return > 2 h-s diagram states (at minimum: "
        f"inlet, rotor inlet, rotor exit, diffuser exit). "
        f"Pre-fix returned hardcoded constants here."
    )


def test_adapt_020_efficiency_is_physical() -> None:
    """Locked: analysis result must have eta_tt and eta_ts in (0, 1)."""
    from routers.analysis import _solve_radial_turbine

    result = _solve_radial_turbine(_GEOM, _OP, "whitfield-baines-radial-v1")

    efficiencies = result.get("efficiencies", {})
    eta_tt = efficiencies.get("eta_tt", result.get("eta_total", 0.0))
    eta_ts = efficiencies.get("eta_ts", 0.0)

    assert 0 < eta_tt < 1, (
        f"ADAPT-020 regression: eta_tt = {eta_tt}. Must be in (0, 1). "
        f"A hardcoded constant or divide-by-zero error may be present."
    )
    assert 0 < eta_ts < 1, (
        f"ADAPT-020 regression: eta_ts = {eta_ts}. Must be in (0, 1)."
    )
    # Physical sanity: eta_ts must be <= eta_tt (static vs total ideal work)
    assert eta_ts <= eta_tt + 0.001, (
        f"eta_ts ({eta_ts:.4f}) must be <= eta_tt ({eta_tt:.4f}). "
        f"ADAPT-022 formula may be broken."
    )


def test_adapt_020_convergence_history_has_multiple_iterations() -> None:
    """Locked: convergence_history must have >= 3 entries (solver iterated)."""
    from routers.analysis import _solve_radial_turbine

    result = _solve_radial_turbine(_GEOM, _OP, "whitfield-baines-radial-v1")

    history = result.get("convergence_history", [])
    assert len(history) >= 3, (
        f"ADAPT-020 regression: convergence_history has {len(history)} entries. "
        f"The mean-line solver must iterate (Newton inner loop). "
        f"A hardcoded result would have 0 entries."
    )


def test_adapt_020_loss_breakdown_has_named_terms() -> None:
    """Locked: loss_breakdown must have >= 4 named terms from the real solver."""
    from routers.analysis import _solve_radial_turbine

    result = _solve_radial_turbine(_GEOM, _OP, "whitfield-baines-radial-v1")

    breakdown = result.get("loss_breakdown", [])
    assert isinstance(breakdown, list), (
        f"loss_breakdown must be a list; got {type(breakdown)}"
    )
    assert len(breakdown) >= 4, (
        f"ADAPT-020 regression: loss_breakdown has {len(breakdown)} terms. "
        f"Whitfield-Baines radial turbine model produces >= 4 named losses "
        f"(incidence, profile, secondary, trailing_edge, tip_clearance, ...). "
        f"A hardcoded result would have fewer or no entries."
    )
    names = [t.get("name", t.get("term", "")) for t in breakdown]
    assert any(names), (
        f"Loss breakdown entries have no 'name' field: {breakdown[:3]}"
    )
