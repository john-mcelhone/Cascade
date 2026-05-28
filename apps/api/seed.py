"""Seed three demo projects into the in-memory store.

The microturbine demo mirrors the Capstone C30 case from
`cascade.validation.cases.capstone_c30` — the canonical Capstone C30 source
of truth shared with the CYC-3 validation test and the CLI demo. All three
report identical η_e ≈ 26 %, ~28 kW net. (ADAPT-018.)
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from jobs import PROJECTS

# Cascade source isn't installed as a package in the API dev environment;
# add `src/` to sys.path so we can pull the canonical Capstone case.
_CASCADE_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_CASCADE_SRC) not in sys.path:
    sys.path.insert(0, str(_CASCADE_SRC))

from cascade.validation.cases.capstone_c30 import CapstoneC30  # noqa: E402


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _microturbine_project() -> Dict[str, Any]:
    """Capstone C30 recuperated Brayton — pulled from the canonical case."""

    c = CapstoneC30
    p_amb_kPa = c.p_ambient.to("kPa").magnitude  # noqa: N806
    T_amb_K = c.T_ambient.to("K").magnitude  # noqa: N806
    m_dot = c.mass_flow.to("kg/s").magnitude
    TIT_K = c.TIT.to("K").magnitude  # noqa: N806
    LHV_J_per_kg = c.fuel_LHV.to("J/kg").magnitude  # noqa: N806
    fuel_M = c.fuel_molar_mass.to("g/mol").magnitude  # noqa: N806

    components: List[Dict[str, Any]] = [
        {
            "id": "inlet",
            "kind": "Inlet",
            "name": "Inlet",
            "position": {"x": 40, "y": 240},
            "params": {
                "pressure_total": {"value": p_amb_kPa, "unit": "kPa"},
                "temperature_total": {"value": T_amb_K, "unit": "K"},
                "mass_flow": {"value": m_dot, "unit": "kg/s"},
                "composition": "air",
            },
        },
        {
            "id": "inlet_loss",
            "kind": "ConstantPressureLoss",
            "name": "Inlet duct",
            "position": {"x": 200, "y": 240},
            "params": {"pressure_drop_fraction": c.pdrop_inlet},
        },
        {
            "id": "compressor",
            "kind": "Compressor",
            "name": "C1",
            "position": {"x": 360, "y": 240},
            "params": {
                "pressure_ratio": c.pressure_ratio,
                "efficiency_isentropic": c.eta_compressor_isen,
            },
        },
        {
            "id": "recuperator",
            "kind": "Recuperator",
            "name": "R1",
            "position": {"x": 520, "y": 320},
            "params": {
                "effectiveness": c.recuperator_effectiveness,
                "cold_pressure_drop_fraction": c.pdrop_recup_cold,
                "hot_pressure_drop_fraction": c.pdrop_recup_hot,
            },
        },
        {
            "id": "burner",
            "kind": "Burner",
            "name": "B1",
            "position": {"x": 680, "y": 240},
            "params": {
                "outlet_temperature": {"value": TIT_K, "unit": "K"},
                "pressure_drop_fraction": c.pdrop_burner,
                "combustion_efficiency": c.combustion_efficiency,
                "fuel_lhv": {"value": LHV_J_per_kg, "unit": "J/kg"},
                "fuel_carbon_atoms": c.fuel_carbon_atoms,
                "fuel_hydrogen_atoms": c.fuel_hydrogen_atoms,
                "fuel_molar_mass": {"value": fuel_M, "unit": "g/mol"},
            },
        },
        {
            "id": "turbine",
            "kind": "Turbine",
            "name": "T1",
            "position": {"x": 840, "y": 240},
            "params": {
                "pressure_ratio": c.turbine_pressure_ratio(),
                "efficiency_isentropic": c.eta_turbine_isen,
            },
        },
        {
            "id": "outlet",
            "kind": "Outlet",
            "name": "Exhaust",
            "position": {"x": 1000, "y": 240},
            "params": {},
        },
    ]

    edges: List[Dict[str, Any]] = [
        {
            "id": "e1",
            "source": "inlet",
            "target": "inlet_loss",
            "source_port": "out",
            "target_port": "in",
        },
        {
            "id": "e2",
            "source": "inlet_loss",
            "target": "compressor",
            "source_port": "out",
            "target_port": "in",
        },
        {
            "id": "e3",
            "source": "compressor",
            "target": "recuperator",
            "source_port": "out",
            "target_port": "cold_in",
        },
        {
            "id": "e4",
            "source": "recuperator",
            "target": "burner",
            "source_port": "cold_out",
            "target_port": "in",
        },
        {
            "id": "e5",
            "source": "burner",
            "target": "turbine",
            "source_port": "out",
            "target_port": "in",
        },
        {
            "id": "e6",
            "source": "turbine",
            "target": "recuperator",
            "source_port": "out",
            "target_port": "hot_in",
        },
        {
            "id": "e7",
            "source": "recuperator",
            "target": "outlet",
            "source_port": "hot_out",
            "target_port": "in",
        },
    ]

    target_eta_pct = c.target_eta_electric * 100.0
    nameplate_kW = c.target_power_nameplate.to("kW").magnitude  # noqa: N806
    return {
        "id": "microturbine-30kw",
        "name": f"Microturbine {nameplate_kW:.0f} kW",
        "kind": "microturbine",
        "working_fluid": "air",
        "description": (
            f"Recuperated Brayton cycle matched to the Capstone C30 published "
            f"spec: {c.pressure_ratio:.0f}:1 PR, {TIT_K:.0f} K TIT, "
            f"{c.recuperator_effectiveness:.0%} recuperator effectiveness, "
            f"{target_eta_pct:.0f}% electrical efficiency. "
            f"Sourced from cascade.validation.cases.capstone_c30."
        ),
        "created_at": _now(),
        "updated_at": _now(),
        "last_run_status": None,
        "components": components,
        "edges": edges,
        "boundary_conditions": {
            "pressure_total": {"value": p_amb_kPa, "unit": "kPa"},
            "temperature_total": {"value": T_amb_K, "unit": "K"},
            "mass_flow": {"value": m_dot, "unit": "kg/s"},
            "composition": "air",
        },
        "settings": {
            "mechanical_efficiency": c.eta_mechanical,
            "generator_efficiency": c.eta_generator,
        },
    }


def _sco2_project() -> Dict[str, Any]:
    """Simple sCO2 Brayton: inlet -> compressor -> burner -> turbine -> outlet."""

    components: List[Dict[str, Any]] = [
        {
            "id": "inlet",
            "kind": "Inlet",
            "name": "Inlet",
            "position": {"x": 40, "y": 240},
            "params": {
                "pressure_total": {"value": 7.4, "unit": "MPa"},
                "temperature_total": {"value": 305.0, "unit": "K"},
                "mass_flow": {"value": 1.0, "unit": "kg/s"},
                "composition": "sCO2",
            },
        },
        {
            "id": "compressor",
            "kind": "Compressor",
            "name": "C1",
            "position": {"x": 240, "y": 240},
            "params": {"pressure_ratio": 3.0, "efficiency_isentropic": 0.83},
        },
        {
            "id": "burner",
            "kind": "Burner",
            "name": "Heater",
            "position": {"x": 440, "y": 240},
            "params": {
                "outlet_temperature": {"value": 873.0, "unit": "K"},
                "pressure_drop_fraction": 0.02,
                "combustion_efficiency": 1.0,
                "air_standard": True,
            },
        },
        {
            "id": "turbine",
            "kind": "Turbine",
            "name": "T1",
            "position": {"x": 640, "y": 240},
            "params": {"pressure_ratio": 2.9, "efficiency_isentropic": 0.88},
        },
        {
            "id": "outlet",
            "kind": "Outlet",
            "name": "Exhaust",
            "position": {"x": 840, "y": 240},
            "params": {},
        },
    ]
    edges: List[Dict[str, Any]] = [
        {"id": "e1", "source": "inlet", "target": "compressor", "source_port": "out", "target_port": "in"},
        {"id": "e2", "source": "compressor", "target": "burner", "source_port": "out", "target_port": "in"},
        {"id": "e3", "source": "burner", "target": "turbine", "source_port": "out", "target_port": "in"},
        {"id": "e4", "source": "turbine", "target": "outlet", "source_port": "out", "target_port": "in"},
    ]

    return {
        "id": "sco2-test-loop",
        "name": "sCO2 Test Loop",
        "kind": "sco2",
        "working_fluid": "co2_supercritical",
        "description": "Simple supercritical-CO2 Brayton cycle for prototype testing.",
        "created_at": _now(),
        "updated_at": _now(),
        "last_run_status": None,
        "components": components,
        "edges": edges,
        "boundary_conditions": {
            "pressure_total": {"value": 7.4, "unit": "MPa"},
            "temperature_total": {"value": 305.0, "unit": "K"},
            "mass_flow": {"value": 1.0, "unit": "kg/s"},
            "composition": "sCO2",
        },
        "settings": {
            "mechanical_efficiency": 0.98,
            "generator_efficiency": 0.97,
        },
    }


def _at100_project() -> Dict[str, Any]:
    """American Turbines 100 kW prototype — recuperated Brayton on natural gas.

    Combustor design targets from internal MVP review (Frank, 5/20/26):
      * Fuel: natural gas (modelled here as CH4 surrogate)
      * Combustion efficiency: 99 %
      * Outlet temperature (TIT): 1800 °F = 1255.37 K
      * Burner pressure drop: ≤ 6 %  (sized to 5 % here)
      * Liner temperature ≤ 1500 °F (informational; not a solver field)
      * Premixed, lean — required to meet CARB 2007 single-digit NOx
      * Turndown 3:1, > XXX,000 h MTBO  (informational)

    Cycle parameters around the combustor are engineering placeholders
    sized to land ~100 kW electrical. Tune on the Cycle page.
    """

    # Targets from the combustor PPTX (verbatim where given).
    TIT_F = 1800.0  # °F  (combustor outlet)  # noqa: N806
    TIT_K = (TIT_F - 32.0) * 5.0 / 9.0 + 273.15  # noqa: N806  → 1255.37 K
    BURNER_PDROP = 0.05  # 5 % (spec: ≤ 6 %)
    COMB_EFF = 0.99  # spec: 99 %
    LINER_T_K = (1500.0 - 32.0) * 5.0 / 9.0 + 273.15  # 1088.71 K, informational  # noqa: N806

    # Natural-gas surrogate = CH4. Pipeline-grade NG runs LHV ≈ 47–50 MJ/kg
    # depending on composition; methane proper is 50.0 MJ/kg.
    LHV_J_per_kg = 50.0e6  # noqa: N806
    fuel_M = 16.0425  # g/mol  # noqa: N806

    # Engineering choices for a 100 kW recuperated microturbine on NG.
    # PR is higher than Capstone's 4:1 because the much hotter TIT lets us
    # extract more work per stage. Recuperator effectiveness assumes a
    # printed / brazed Inconel HX (consistent with the PPTX's "Hyliion prints
    # their entire recuperator" reference). Compressor / turbine η are
    # representative single-stage centrifugal / radial values.
    m_dot = 0.625  # kg/s — sized so W_electrical lands at ≈ 100 kW
    pressure_ratio = 5.0
    eta_c_isen = 0.79
    eta_t_isen = 0.85
    recup_eff = 0.87
    recup_pdrop_cold = 0.03
    recup_pdrop_hot = 0.03
    inlet_pdrop = 0.02
    eta_mech = 0.99
    eta_gen = 0.95

    # Turbine PR derived from pressure-drop chain (same formula as
    # `CapstoneC30.turbine_pressure_ratio()` in cascade.validation.cases):
    #   p_t_burner_out / p_amb = (1 − ΔP_inlet) × PR_c × (1 − ΔP_cold) × (1 − ΔP_burner)
    #   p_t_turbine_out / p_amb = 1 / (1 − ΔP_hot)
    #   PR_t = p_t_burner_out / p_t_turbine_out
    p_t_burner_out_atm = (
        (1.0 - inlet_pdrop)
        * pressure_ratio
        * (1.0 - recup_pdrop_cold)
        * (1.0 - BURNER_PDROP)
    )
    p_t_turbine_out_atm = 1.0 / (1.0 - recup_pdrop_hot)
    pressure_ratio_t = p_t_burner_out_atm / p_t_turbine_out_atm

    components: List[Dict[str, Any]] = [
        {
            "id": "inlet",
            "kind": "Inlet",
            "name": "Inlet",
            "position": {"x": 40, "y": 240},
            "params": {
                "pressure_total": {"value": 101.325, "unit": "kPa"},
                "temperature_total": {"value": 288.15, "unit": "K"},
                "mass_flow": {"value": m_dot, "unit": "kg/s"},
                "composition": "air",
            },
        },
        {
            "id": "inlet_loss",
            "kind": "ConstantPressureLoss",
            "name": "Inlet duct",
            "position": {"x": 200, "y": 240},
            "params": {"pressure_drop_fraction": inlet_pdrop},
        },
        {
            "id": "compressor",
            "kind": "Compressor",
            "name": "C1",
            "position": {"x": 360, "y": 240},
            "params": {
                "pressure_ratio": pressure_ratio,
                "efficiency_isentropic": eta_c_isen,
            },
        },
        {
            "id": "recuperator",
            "kind": "Recuperator",
            "name": "R1",
            "position": {"x": 520, "y": 320},
            "params": {
                "effectiveness": recup_eff,
                "cold_pressure_drop_fraction": recup_pdrop_cold,
                "hot_pressure_drop_fraction": recup_pdrop_hot,
            },
        },
        {
            "id": "burner",
            "kind": "Burner",
            "name": "Combustor",
            "position": {"x": 680, "y": 240},
            "params": {
                "outlet_temperature": {"value": TIT_K, "unit": "K"},
                "pressure_drop_fraction": BURNER_PDROP,
                "combustion_efficiency": COMB_EFF,
                "fuel_lhv": {"value": LHV_J_per_kg, "unit": "J/kg"},
                "fuel_carbon_atoms": 1,
                "fuel_hydrogen_atoms": 4,
                "fuel_molar_mass": {"value": fuel_M, "unit": "g/mol"},
            },
        },
        {
            "id": "turbine",
            "kind": "Turbine",
            "name": "T1",
            "position": {"x": 840, "y": 240},
            "params": {
                "pressure_ratio": pressure_ratio_t,
                "efficiency_isentropic": eta_t_isen,
            },
        },
        {
            "id": "outlet",
            "kind": "Outlet",
            "name": "Exhaust",
            "position": {"x": 1000, "y": 240},
            "params": {},
        },
    ]

    edges: List[Dict[str, Any]] = [
        {"id": "e1", "source": "inlet", "target": "inlet_loss",
         "source_port": "out", "target_port": "in"},
        {"id": "e2", "source": "inlet_loss", "target": "compressor",
         "source_port": "out", "target_port": "in"},
        {"id": "e3", "source": "compressor", "target": "recuperator",
         "source_port": "out", "target_port": "cold_in"},
        {"id": "e4", "source": "recuperator", "target": "burner",
         "source_port": "cold_out", "target_port": "in"},
        {"id": "e5", "source": "burner", "target": "turbine",
         "source_port": "out", "target_port": "in"},
        {"id": "e6", "source": "turbine", "target": "recuperator",
         "source_port": "out", "target_port": "hot_in"},
        {"id": "e7", "source": "recuperator", "target": "outlet",
         "source_port": "hot_out", "target_port": "in"},
    ]

    return {
        "id": "at-100kw-prototype",
        "name": "AT-100 kW Prototype",
        "kind": "microturbine",
        "working_fluid": "air",
        "description": (
            "American Turbines 100 kW recuperated Brayton prototype. "
            f"Combustor sized to the 5/20/26 MVP targets: TIT = {TIT_K:.0f} K "
            f"({TIT_F:.0f} °F), ΔP ≤ 6 %, η_combustion = 99 %, natural-gas "
            f"fuel (CH4 surrogate, LHV 50 MJ/kg), liner T cap "
            f"{LINER_T_K:.0f} K ({1500} °F, informational). Cycle PR, "
            "recuperator ε, and compressor/turbine η are engineering "
            "placeholders — tune them on the Cycle page until W_elec lands "
            "near 100 kW."
        ),
        "created_at": _now(),
        "updated_at": _now(),
        "last_run_status": None,
        "components": components,
        "edges": edges,
        "boundary_conditions": {
            "pressure_total": {"value": 101.325, "unit": "kPa"},
            "temperature_total": {"value": 288.15, "unit": "K"},
            "mass_flow": {"value": m_dot, "unit": "kg/s"},
            "composition": "air",
        },
        "settings": {
            "mechanical_efficiency": eta_mech,
            "generator_efficiency": eta_gen,
        },
    }


def _aero_project() -> Dict[str, Any]:
    """Empty cycle — placeholder for an aero demonstrator."""

    return {
        "id": "aero-demonstrator",
        "name": "Aero Demonstrator",
        "kind": "aero",
        "working_fluid": "air",
        "description": (
            "Blank aero turbomachinery project — drop components onto the "
            "Cycle Canvas to start designing."
        ),
        "created_at": _now(),
        "updated_at": _now(),
        "last_run_status": None,
        "components": [],
        "edges": [],
        "boundary_conditions": {
            "pressure_total": {"value": 101.325, "unit": "kPa"},
            "temperature_total": {"value": 288.15, "unit": "K"},
            "mass_flow": {"value": 5.0, "unit": "kg/s"},
            "composition": "air",
        },
        "settings": {
            "mechanical_efficiency": 0.99,
            "generator_efficiency": 1.0,
        },
    }


def seed_projects() -> None:
    """Populate the project store with the three demos.

    Writes only if the on-disk store is empty (idempotent). Once we've
    seeded, user edits survive — we never clobber them on subsequent
    startups. Mirrors the contract of
    :func:`cascade.project.ensure_seeded`.
    """

    from cascade.project import Project, ensure_seeded

    seeds = [
        Project.from_legacy_dict(_microturbine_project()),
        Project.from_legacy_dict(_sco2_project()),
        Project.from_legacy_dict(_at100_project()),
        Project.from_legacy_dict(_aero_project()),
    ]
    ensure_seeded(seeds)
    # `ensure_seeded` is no-op when the projects dir already has *any* file
    # in it, so adding a new seed to this list won't appear on existing
    # installs. Fall through: for each seed whose ID is missing on disk,
    # write it. Existing files are NEVER overwritten — user edits survive.
    from cascade.project.persistence import (
        load_project,
        save_project,
        projects_dir,
        PROJECT_FILE_SUFFIX,
    )

    root = projects_dir()
    existing_ids: set[str] = set()
    for path in root.glob(f"*{PROJECT_FILE_SUFFIX}"):
        try:
            existing_ids.add(load_project(path).id)
        except Exception:
            pass
    for p in seeds:
        if p.id not in existing_ids:
            save_project(p)
    # Drop and re-warm the cache so the API sees whatever's on disk
    # (whether we just wrote it or it was already there).
    PROJECTS.reload()
