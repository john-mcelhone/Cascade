"""Closure F3, Item 1 — sCO2 seed fluid-routing verification.

Safety-critical check: the sCO2 seed project must route to
``CoolPropPureFluid`` (real CO2 Helmholtz EOS), NOT ``NasaFluid`` (air-
property approximation).

Near the CO2 critical point (7.377 MPa, 304.13 K), Cp can exceed
16 000 J/(kg·K) — roughly 16× air.  Using air properties at these
conditions produces nonsense design-point predictions for near-critical
compressor inlet states.

This module verifies Option A of the F3 closure: the existing
``_select_fluid`` routing in ``apps/api/routers/cycle.py`` already returns
``CoolPropPureFluid`` for the sCO2 seed's ``boundary_conditions.composition
= "sCO2"`` string.  The routing chain is::

    "sCO2" --(case-insensitive Species name match)--> Species.SCO2
    Species.SCO2 --(in _COOLPROP_SPECIES_NAMES)--> CoolPropPureFluid(Species.SCO2)

Tests
-----
test_select_fluid_returns_coolprop_for_sco2_seed
    Primary closure gate.  Failure re-opens the safety defect.

test_coolprop_co2_near_critical_cp_is_anomalous
    CoolProp sanity check: Cp(CO2) >> Cp(air) at seed inlet conditions.

test_sco2_seed_composition_string_resolves_to_coolprop
    Documents the exact string → Species → CoolProp routing chain.

test_sco2_seed_solver_with_real_co2_eos_converges
    End-to-end: the full router path (_build_recuperated_spec + _select_fluid
    + solve_cycle) converges and gives physically plausible results.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup — same pattern as test_cycle_cosim.py
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parents[2]
for _p in (str(_REPO / "src"), str(_REPO / "apps" / "api")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# 1. Primary closure gate: _select_fluid returns CoolPropPureFluid
# ---------------------------------------------------------------------------


def test_select_fluid_returns_coolprop_for_sco2_seed():
    """_select_fluid on the sCO2 seed must return CoolPropPureFluid.

    This is the primary Closure F3 Item 1 gate.  If this test fails:
      - The sCO2 seed silently uses air-property approximation for CO2.
      - Near-critical Cp is off by ~16×.
      - All design-point efficiency and work estimates are wrong.

    Root cause to fix: check boundary_conditions.composition in
    seed._sco2_project() (must be "sCO2", not "co2_supercritical" or
    "CO2") and the _COMPOSITION_SYNONYMS / _COOLPROP_SPECIES_NAMES tables
    in apps/api/routers/cycle.py.
    """
    from apps.api.routers.cycle import _select_fluid
    from cascade.cycle.fluid_model import CoolPropPureFluid
    from seed import _sco2_project

    project = _sco2_project()
    fluid = _select_fluid(project)

    assert isinstance(fluid, CoolPropPureFluid), (
        f"sCO2 seed: _select_fluid returned {type(fluid).__name__!r}, "
        f"expected CoolPropPureFluid.  "
        f"The seed is using air-property approximation for CO2 — "
        f"safety defect F3-Item-1.  "
        f"Check seed.boundary_conditions.composition (must be 'sCO2') "
        f"and _COOLPROP_SPECIES_NAMES in cycle.py."
    )


# ---------------------------------------------------------------------------
# 2. CoolProp CO2 EOS captures the near-critical Cp anomaly
# ---------------------------------------------------------------------------


def test_coolprop_co2_near_critical_cp_is_anomalous():
    """At 305 K / 7.4 MPa (sCO2 seed inlet), Cp(CO2) >> Cp(air).

    Confirms CoolProp is installed and returning real-gas values.

    Reference: NIST Webbook, CO2 at 305 K, 7.4 MPa:
      Cp ≈ 16 000–17 000 J/(kg·K)  (near-critical anomaly)
    Air ideal gas at 305 K: Cp ≈ 1 005 J/(kg·K).
    Ratio: ~16×.

    We assert Cp(CO2) > 3 000 J/(kg·K) — this already discriminates
    real-gas CO2 from air approximation while tolerating minor CoolProp
    version differences near the critical region.
    """
    import CoolProp.CoolProp as CP

    Cp_co2 = CP.PropsSI("Cpmass", "T", 305.0, "P", 7.4e6, "CO2")
    Cp_air = 1005.0

    assert Cp_co2 > 3000.0, (
        f"CoolProp CO2 Cp at 305 K / 7.4 MPa = {Cp_co2:.0f} J/(kg·K).  "
        f"This is implausibly close to air ({Cp_air:.0f} J/(kg·K)).  "
        f"CoolProp may not be installed or may be returning ideal-gas values."
    )

    # Minimum ratio: must be substantially larger than air.
    ratio = Cp_co2 / Cp_air
    assert ratio > 3.0, (
        f"CO2/air Cp ratio = {ratio:.1f}×; should be ~16× at near-critical "
        f"conditions.  A ratio < 3 means the real-gas EOS is not engaged."
    )


# ---------------------------------------------------------------------------
# 3. Composition string routing: "sCO2" -> SCO2 -> CoolProp
# ---------------------------------------------------------------------------


def test_sco2_seed_composition_string_resolves_to_coolprop():
    """Document the routing chain for the 'sCO2' composition string.

    The sCO2 seed sets boundary_conditions.composition = "sCO2".
    Expected routing (in _select_fluid / _resolve_species_name):
      1. "sCO2" -> case-insensitive match -> Species.SCO2 (enum name "SCO2")
      2. "SCO2" is in _COOLPROP_SPECIES_NAMES -> CoolPropPureFluid(Species.SCO2)

    A future change to Species enum names or synonym tables that breaks this
    chain will fail here loudly rather than silently routing to NasaFluid.
    """
    from apps.api.routers.cycle import (
        _COMPOSITION_SYNONYMS,
        _COOLPROP_SPECIES_NAMES,
        _resolve_species_name,
    )
    from cascade.cycle.fluid_model import NasaFluid
    from cascade.units import Species

    # Step 1: string resolution
    resolved = _resolve_species_name("sCO2")
    assert resolved == "SCO2", (
        f"'sCO2' resolved to {resolved!r}, expected 'SCO2'.  "
        f"Check Species enum (value='sCO2' -> name='SCO2') and "
        f"_COMPOSITION_SYNONYMS."
    )

    # Step 2: species in CoolProp set
    assert "SCO2" in _COOLPROP_SPECIES_NAMES, (
        f"'SCO2' not in _COOLPROP_SPECIES_NAMES {_COOLPROP_SPECIES_NAMES}.  "
        f"The sCO2 seed would silently fall through to NasaFluid."
    )

    # Step 3: NasaFluid is NOT returned for the seed
    from apps.api.routers.cycle import _select_fluid
    from seed import _sco2_project

    project = _sco2_project()
    fluid = _select_fluid(project)
    assert not isinstance(fluid, NasaFluid), (
        f"sCO2 seed: _select_fluid returned NasaFluid — "
        f"air-property approximation is active for CO2 (safety defect F3-Item-1)."
    )


# ---------------------------------------------------------------------------
# 4. End-to-end: solver with real CO2 EOS converges + physics plausible
# ---------------------------------------------------------------------------


def test_sco2_seed_solver_with_real_co2_eos_converges():
    """Run the sCO2 seed through the full router path with CoolPropPureFluid.

    Exercises: _build_recuperated_spec -> _select_fluid -> solve_cycle.

    Physical bounds:
      - Solver must converge.
      - Net shaft work > 0 (power cycle).
      - Thermal efficiency in [0.05, 0.65].
        Carnot limit: 1 - T_cold/T_hot = 1 - 305/873 ≈ 0.651.
        Realistic lossy cycle (η_c=0.83, η_t=0.88): 25–45%.
        Lower bound 0.05 allows for partial-PR off-design states.
    """
    from apps.api.routers.cycle import _build_recuperated_spec, _select_fluid
    from cascade.cycle.fluid_model import CoolPropPureFluid
    from cascade.cycle.solver import solve_cycle
    from seed import _sco2_project

    project = _sco2_project()
    spec = _build_recuperated_spec(project)
    fluid = _select_fluid(project)

    assert isinstance(fluid, CoolPropPureFluid), (
        f"Pre-condition failed: fluid is {type(fluid).__name__}, not CoolPropPureFluid.  "
        f"The earlier routing test should have caught this."
    )

    result = solve_cycle(spec, fluid=fluid)

    assert result.converged, (
        f"sCO2 seed with CoolPropPureFluid did not converge.  "
        f"residual={result.residual_norm:.3e}  "
        f"outer_iterations={result.outer_iterations}"
    )

    W_net_kW = result.net_shaft_work.to("kW").magnitude
    assert W_net_kW > 0.0, (
        f"sCO2 seed W_net = {W_net_kW:.3f} kW — power cycle must produce "
        f"positive net work."
    )

    eta_th = result.thermal_efficiency
    assert 0.05 <= eta_th <= 0.65, (
        f"sCO2 seed η_th = {eta_th:.4f} outside [0.05, 0.65].  "
        f"Carnot(305 K, 873 K) = {1 - 305/873:.3f}; a lossy real cycle must "
        f"be below this bound."
    )
