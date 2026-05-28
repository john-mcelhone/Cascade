"""
GE CF6-80C2 high-bypass turbofan — canonical 2-spool validation case.

Source of truth for every Cascade file that references the CF6-80C2. Cite this
module instead of hardcoding spool counts, PRs, BPRs, or TIT in CLI demos,
seed data, or tests.

This is the workhorse of the GEnx generation: 50,000-lb-thrust class, 30:1
overall pressure ratio, bypass ratio ~5, with HP and LP spools that solve
to independent rotational speeds when power-balanced (ADAPT-034).

References
----------
* Mattingly, J.D., *Elements of Propulsion: Gas Turbines and Rockets*, 2nd ed.,
  AIAA, 2006. CF6-80C2 cycle data in App. B Table B-1.
* Walsh, P.P. & Fletcher, P., *Gas Turbine Performance*, 2nd ed., Blackwell,
  2004. §6 spool-matching equations.
* FAA Type Certificate Data Sheet E13NE (CF6-80C2 family).
* Saravanamuttoo, Rogers, Cohen, Straznicky, *Gas Turbine Theory*, 6th ed.,
  Pearson, 2009. Ch. 8.2 ("Twin-spool engine") — power-balance form.
* Kurzke, J. *GasTurb 13 reference manual* (commercial reference; cycle data
  comparable to the values below).

Geometry approximations (for the live-meanline coupling demo):
* HPC: 14-stage axial; the v1 cycle solver lumps it into a single 'compressor'
  with an effective PR of ~13.5 between IPC exit and HPC exit. Live-meanline
  coupling for an axial stage is a v1.1 extension — v1 uses lumped η on the HP
  spool unless the user supplies an axial-compressor geometry (not yet
  supported).
* LP fan+booster: combined into one 'compressor' with PR ~2.2.
* HPT: 2-stage; lumped into one turbine, PR ~5.5.
* LPT: 5-stage; lumped into one turbine, PR ~5.4.
"""
from __future__ import annotations

from dataclasses import dataclass

from cascade.units import Q


@dataclass(frozen=True)
class CF6_80C2:
    """Canonical GE CF6-80C2 2-spool turbofan parameters.

    Targets (Mattingly App. B; cruise, M=0.85, 35 kft):
        - Overall PR: ~30 (sea-level static); ~26 at cruise.
        - Bypass ratio: ~5.0.
        - TIT (T4): ~1450 K.
        - HP spool design speed: ~11,000 rpm (N2).
        - LP spool design speed: ~3,500 rpm (N1).
    """

    # --- Boundary conditions (ISO sea-level static, take-off rating) ----
    p_ambient = Q(101.325, "kPa")
    T_ambient = Q(288.15, "K")
    fuel_LHV = Q(43.0, "MJ/kg")  # Jet-A / JP-8
    fuel_carbon_atoms = 12
    fuel_hydrogen_atoms = 23
    fuel_molar_mass = Q(170.0, "g/mol")
    fuel_inlet_temperature = Q(298.15, "K")
    combustion_efficiency = 0.995

    # --- Overall cycle ---------------------------------------------------
    overall_pressure_ratio = 30.0
    bypass_ratio = 5.0
    TIT = Q(1450.0, "K")  # T4 — Mattingly App. B
    core_mass_flow = Q(120.0, "kg/s")  # take-off core flow
    fan_mass_flow_total = Q(720.0, "kg/s")  # core + bypass

    # --- 2-spool decomposition (HP, LP) ----------------------------------
    # The LP spool runs the fan and the booster (low-pressure compressor).
    # In a 2-spool *separate-exhaust* turbofan the fan PR is small (~1.6) and
    # the booster adds another ~1.5. Combined, the "LP compressor" PR is
    # ~2.4 across the core.
    pr_LPC = 2.4
    pr_HPC = 12.5  # gives overall ≈ 2.4 × 12.5 = 30
    pr_HPT_design = 5.0
    pr_LPT_design = 5.0
    # The product OPR_t = pr_HPT · pr_LPT ≈ 25 leaves ~ 20% margin to drive
    # the bypass nozzle exhaust velocity (not modelled in v1's 0D control
    # volume).

    # --- Component efficiencies (Mattingly App. B; modern transport-class) -
    eta_fan_LPC = 0.88
    eta_HPC = 0.86
    eta_HPT = 0.91
    eta_LPT = 0.92
    eta_mech_HP = 0.99
    eta_mech_LP = 0.99
    eta_combustion = 0.995

    # --- Combustor pressure drops ---------------------------------------
    pdrop_inlet = 0.01
    pdrop_burner = 0.04
    pdrop_exhaust = 0.01

    # --- Design rotational speeds (Mattingly App. B) --------------------
    N_HP_rpm_design = 11_000.0
    N_LP_rpm_design = 3_500.0

    # --- Validation targets (publicly cited) ----------------------------
    target_thrust_specific_fuel_consumption_lbhr_per_lbf = 0.317  # cruise
    target_overall_efficiency = 0.36  # propulsive × thermal × combustion


def build_cf6_80c2_spec():
    """Build a `MultiShaftBraytonSpec` for the CF6-80C2.

    Returns a `MultiShaftBraytonSpec` that the cycle solver can consume.
    Mass-flow accounting is for the *core* only — bypass flow is informational.

    Per ADAPT-034 this is the canonical 2-spool reference case: HP and LP
    spools converge to independent N's, and `result.spool_balances` shows
    each closing to fractional residual < 1e-3.
    """
    # Imports are local so this module stays importable from inside the
    # validation/test path without cycling through cascade.cycle on first
    # boot.
    from cascade.cycle import (
        Burner,
        Compressor,
        ConstantPressureLoss,
        MultiShaftBraytonSpec,
        Shaft,
        Turbine,
    )
    from cascade.units import Composition, Port

    c = CF6_80C2

    inlet = Port(
        pressure_total=c.p_ambient,
        temperature_total=c.T_ambient,
        mass_flow=c.core_mass_flow,
        composition=Composition.air(),
    )

    # Spool 2 (LP): fan + LPC → LPT.  Spool 1 (HP): HPC → HPT.
    fan_LPC = Compressor(
        name="fan_LPC",
        pressure_ratio=c.pr_LPC,
        efficiency_isentropic=c.eta_fan_LPC,
        shaft_id=2,  # LP
    )
    HPC = Compressor(
        name="HPC",
        pressure_ratio=c.pr_HPC,
        efficiency_isentropic=c.eta_HPC,
        shaft_id=1,  # HP
    )
    HPT = Turbine(
        name="HPT",
        pressure_ratio=c.pr_HPT_design,
        efficiency_isentropic=c.eta_HPT,
        shaft_id=1,
    )
    LPT = Turbine(
        name="LPT",
        pressure_ratio=c.pr_LPT_design,
        efficiency_isentropic=c.eta_LPT,
        shaft_id=2,
    )
    burner = Burner(
        name="combustor",
        pressure_drop_fraction=c.pdrop_burner,
        combustion_efficiency=c.eta_combustion,
        outlet_temperature=c.TIT,
        fuel_lhv=c.fuel_LHV.to("J/kg"),
        fuel_carbon_atoms=c.fuel_carbon_atoms,
        fuel_hydrogen_atoms=c.fuel_hydrogen_atoms,
        fuel_molar_mass=c.fuel_molar_mass,
        fuel_inlet_temperature=c.fuel_inlet_temperature,
        air_standard=False,
    )

    shafts = [
        Shaft(
            id=1,
            name="HP",
            components=["HPC", "HPT"],
            rotational_speed_rpm=c.N_HP_rpm_design,
            mechanical_efficiency=c.eta_mech_HP,
        ),
        Shaft(
            id=2,
            name="LP",
            components=["fan_LPC", "LPT"],
            rotational_speed_rpm=c.N_LP_rpm_design,
            mechanical_efficiency=c.eta_mech_LP,
        ),
    ]

    return MultiShaftBraytonSpec(
        inlet_port=inlet,
        compressors=[fan_LPC, HPC],
        burner=burner,
        turbines=[HPT, LPT],
        shafts=shafts,
        inlet_loss=ConstantPressureLoss(
            name="inlet_loss", pressure_drop_fraction=c.pdrop_inlet,
        ),
        exhaust_loss=ConstantPressureLoss(
            name="exhaust_loss", pressure_drop_fraction=c.pdrop_exhaust,
        ),
        bypass_ratio=c.bypass_ratio,
        cycle_type="open",
    )
