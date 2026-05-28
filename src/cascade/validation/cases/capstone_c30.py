"""
Capstone C30 microturbine — canonical validation case.

Source of truth for every Cascade file that references the Capstone C30. Cite
this module instead of hardcoding numbers in CLI demos, seed data, or tests.

The values below are the empirical set that the CYC-3 pass-gate test in
`tests/cycle/test_cyc3_capstone_c30.py` uses to reproduce Capstone's published
26 % LHV electric efficiency end-to-end through the Cascade cycle solver.
Three call sites (CLI demo, validation test, API seed) share these exact
numbers via this module, so they cannot drift apart.

References
----------
* Capstone Turbine Corporation, "C30 Performance Specification" (2010).
* Cohen, Rogers, Saravanamuttoo, "Gas Turbine Theory" 5th ed., Example 2.5.
* NREL TP-560-37250, "Capstone C30 Microturbine CHP System Performance
  Evaluation".
* McDonald, C. F., "Recuperator development trends for high efficiency small
  gas turbines," ASME paper GT2003-38570, 2003 (ε ≈ 0.87 citation).
* Boyce, M. P., *Gas Turbine Engineering Handbook* 4th ed., Ch. 18
  (95 % PMA generator efficiency for Capstone-class machines).
"""
from __future__ import annotations

from dataclasses import dataclass

from cascade.units import Q


@dataclass(frozen=True)
class CapstoneC30:
    """Canonical Capstone C30 microturbine parameters.

    Targets (published):
        - Net electric power: 30 kW (28 kW typical sustained)
        - Electric efficiency (LHV): 26 % ± 1.5 pt
        - Exhaust temperature: ~580 K
    """

    # --- Boundary conditions (ISO sea-level dry air) ---------------------
    p_ambient = Q(101.325, "kPa")
    T_ambient = Q(288.15, "K")
    fuel_LHV = Q(50.0, "MJ/kg")  # natural gas, CH4-rich
    fuel_carbon_atoms = 1
    fuel_hydrogen_atoms = 4
    fuel_molar_mass = Q(16.0425, "g/mol")
    fuel_inlet_temperature = Q(298.15, "K")
    combustion_efficiency = 0.995

    # --- Cycle topology --------------------------------------------------
    pressure_ratio = 4.0  # compressor pressure ratio
    TIT = Q(1116.0, "K")  # turbine inlet (= burner outlet) total T
    mass_flow = Q(0.31, "kg/s")
    recuperator_effectiveness = 0.87  # McDonald 2003

    # Pressure-loss factors (Walsh & Fletcher 2004 §5.10 typicals)
    pdrop_inlet = 0.02
    pdrop_recup_cold = 0.03
    pdrop_burner = 0.04
    pdrop_recup_hot = 0.03
    # Aggregate combustor pressure-loss factor (informational, ≈3 %).
    combustor_dp_ratio = 0.03

    # --- Component efficiencies (microturbine class) -------
    eta_compressor_isen = 0.78  # centrifugal, high end of microturbine range
    eta_turbine_isen = 0.84  # radial inflow

    # --- Mechanical / electrical ----------------------------------------
    eta_mechanical = 0.95
    eta_generator = 0.95  # Boyce §18 PMA generator
    aux_loss_fraction = 0.03  # auxiliary (cooling/electronics) loss

    # --- Validation targets ---------------------------------------------
    target_power_net = Q(28.0, "kW")
    target_power_nameplate = Q(30.0, "kW")
    target_eta_electric = 0.26  # 26 % LHV
    target_eta_thermal = 0.274  # = 0.26 / 0.95
    tolerance_eta_pt = 0.015  # ±1.5 percentage points
    tolerance_power_kW = 2.5  # ±2.5 kW on electrical output

    # --- Derived (kept here so all three call-sites compute identically) -
    @classmethod
    def turbine_pressure_ratio(cls) -> float:
        """Turbine PR derived from inter-component pressure drops.

        Starting at 1 atm at the inlet and ending at 1 atm at the exhaust:

            p_t_burner_out_atm = (1 - pdrop_inlet) * PR_c
                                   * (1 - pdrop_recup_cold)
                                   * (1 - pdrop_burner)
            p_t_turbine_out_atm = 1 / (1 - pdrop_recup_hot)
            PR_t = p_t_burner_out_atm / p_t_turbine_out_atm

        Returns the ratio as a dimensionless float (~3.535).
        """
        p_t_burner_out_atm = (
            (1.0 - cls.pdrop_inlet)
            * cls.pressure_ratio
            * (1.0 - cls.pdrop_recup_cold)
            * (1.0 - cls.pdrop_burner)
        )
        p_t_turbine_out_atm = 1.0 / (1.0 - cls.pdrop_recup_hot)
        return p_t_burner_out_atm / p_t_turbine_out_atm
