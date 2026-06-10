"""0D cycle components. Each takes an inlet `Port` and configuration parameters
and returns an outlet `Port` plus optional auxiliary data (work, heat, fuel).

Every inter-component handoff is a `Port`. Internal numerics (isentropic
states, mixture composition shifts) are computed locally via the
`FluidModel` protocol.

Components implemented for v1:
- `Compressor`        — isentropic-efficiency-based; total-to-total.
- `Turbine`           — isentropic-efficiency-based; total-to-total.
- `Burner`            — ideal T-rise model; user gives T_t_out or fuel mass flow.
  Composition shift via stoichiometric balance (lean only).
- `Recuperator`       — ε-NTU (effectiveness specified); hot and cold ports.
- `Intercooler`       — ε-NTU; one side specified coolant temperature.
- `Mixer`             — mass/energy conservation; mass-fraction averaged composition.
- `Splitter`          — mass fraction extracted; composition preserved on both.
- `ConstantPressureLoss` — duct with no work/heat; lumped Δp/p coefficient.

Refusal behavior (SPEC_SHEET §13):
- π_compressor > 60          → warning, allow.
- T_combustor_exit > 2100 K  → refuse (raise `RegimeOutOfValidity`).
- ε ∉ [0, 0.98]              → refuse.

Citations are in each component docstring per SPEC_SHEET §7.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple

from cascade.cycle.fluid_model import FluidModel
from cascade.thermo.nasa_mixture import RegimeOutOfValidity, burn_mass_balance
from cascade.units import Composition, Port, Q, Quantity, Species


# --- Efficiency mode literal (ADAPT-036) -----------------------------------
# Cycle components can derive their isentropic efficiency in three ways:
#   - "constant"      — use the user-specified `efficiency_isentropic` value.
#   - "polytropic"    — reserved for future multi-stage axials (interpreted
#                       as constant for v1; the polytropic conversion has
#                       not yet been wired through the FluidModel API).
#   - "live_meanline" — run the meanline solver inside the cycle iteration
#                       so η is a function of the current (ṁ, P_t, T_t, π)
#                       operating point. Replaces the lumped η — the
#                       co-simulation behavior of legacy tools.
EfficiencyMode = Literal["constant", "polytropic", "live_meanline"]


# Refusal-envelope constants per SPEC_SHEET §13.
PR_REFUSE_HARD: float = 60.0
PR_WARN_HIGH: float = 30.0
T_BURNER_REFUSE: float = 2100.0  # [K] — uncooled material limit
EFFECTIVENESS_REFUSE_HIGH: float = 0.98


def _refuse_high_pr(pr: float, component_name: str) -> None:
    """Refuse or warn on high pressure-ratio per SPEC_SHEET §13."""
    if pr > PR_REFUSE_HARD:
        msg = (
            f"{component_name}: pressure ratio {pr} > {PR_REFUSE_HARD} is "
            f"outside the validated envelope (SPEC_SHEET §13). Refusing."
        )
        raise RegimeOutOfValidity(msg, code="PR_OUT_OF_VALIDITY")
    if pr > PR_WARN_HIGH:
        msg = (
            f"{component_name}: pressure ratio {pr} > {PR_WARN_HIGH} is "
            f"uncommon for single-stage machines; results are uncalibrated."
        )
        warnings.warn(msg, stacklevel=3)


def _refuse_high_burner_T(T_K: float) -> None:  # noqa: N802, N803
    """Refuse burner exit T > 2100 K (uncooled material limit, SPEC_SHEET §13)."""
    if T_K > T_BURNER_REFUSE:
        msg = (
            f"Burner exit temperature {T_K} K exceeds the uncooled material "
            f"limit {T_BURNER_REFUSE} K (SPEC_SHEET §13). Enable the cooled-row "
            f"plugin (deferred to v1.1) or lower the temperature."
        )
        raise RegimeOutOfValidity(msg, code="T_BURNER_OUT_OF_VALIDITY")


# --- Compressor --------------------------------------------------------------


@dataclass(frozen=True)
class Compressor:
    """Single-stage or lumped compressor with isentropic efficiency.

    Inputs:
        - inlet Port (p_t_in, T_t_in, ṁ, composition).
        - pressure_ratio π_c = p_t_out / p_t_in.
        - isentropic efficiency η_c (total-to-total).
        - shaft_id (ADAPT-034): which spool this compressor sits on. v1 default
          is 1 for single-shaft cycles; multi-spool (e.g. CF6-80C2 with HP+LP)
          uses 1, 2, 3.
        - efficiency_mode (ADAPT-036): "constant" uses `efficiency_isentropic`
          as the lumped η. "live_meanline" runs the centrifugal/axial mean-line
          solver inside each cycle iteration so η reacts to the operating
          point. `meanline_geometry` must then be supplied (cycle solver pulls
          a `CentrifugalCompressorGeometry`).

    Algebra:
        p_t_out = π_c · p_t_in
        T_2s satisfies s(T_2s, p_t_out) = s(T_t_in, p_t_in)            (isentropic)
        h_t_out = h_t_in + (h_t_2s − h_t_in) / η_c                      (Eq. 2.2-3)
        Ẇ_c = ṁ · (h_t_out − h_t_in)

    Per SPEC_SHEET §13: PR > 60 refused; PR > 30 warned. No refusal on η ∈ (0,1].
    """

    name: str
    pressure_ratio: float
    efficiency_isentropic: float
    shaft_id: int = 1
    efficiency_mode: EfficiencyMode = "constant"
    # When efficiency_mode == "live_meanline", the cycle solver consults this
    # geometry (a CentrifugalCompressorGeometry) and an RPM guess to build a
    # CentrifugalCompressorMeanline and read η from the result. Stored as
    # `Any` to avoid a hard import dependency from cycle → meanline.
    meanline_geometry: Optional[Any] = None
    meanline_rpm: Optional[Quantity] = None

    def __post_init__(self) -> None:
        if self.pressure_ratio < 1.0:
            msg = (
                f"Compressor '{self.name}': pressure_ratio {self.pressure_ratio} "
                f"< 1.0 is not a compressor"
            )
            raise ValueError(msg)
        if not (0.0 < self.efficiency_isentropic <= 1.0):
            msg = (
                f"Compressor '{self.name}': efficiency must be in (0, 1]; "
                f"got {self.efficiency_isentropic}"
            )
            raise ValueError(msg)
        if self.shaft_id < 1:
            msg = (
                f"Compressor '{self.name}': shaft_id must be ≥ 1; "
                f"got {self.shaft_id}"
            )
            raise ValueError(msg)
        if self.efficiency_mode == "live_meanline" and self.meanline_geometry is None:
            msg = (
                f"Compressor '{self.name}': efficiency_mode='live_meanline' "
                f"requires meanline_geometry to be set."
            )
            raise ValueError(msg)

    def solve(
        self,
        inlet: Port,
        fluid: FluidModel,
        eta_override: Optional[float] = None,
    ) -> Tuple[Port, Quantity]:
        """Compute outlet Port and shaft work [W] for this compressor.

        Returns: (outlet_port, W_c)

        `eta_override` lets the cycle solver inject a per-iteration η from the
        live mean-line solver (ADAPT-036). When None, falls back to the lumped
        `efficiency_isentropic` value stored on the component.
        """
        _refuse_high_pr(self.pressure_ratio, f"Compressor '{self.name}'")
        eta = eta_override if eta_override is not None else self.efficiency_isentropic

        p_in = inlet.pressure_total
        T_in = inlet.temperature_total
        comp = inlet.composition
        m_dot = inlet.mass_flow

        p_out = p_in * self.pressure_ratio

        # Isentropic outlet temperature
        T_out_s = fluid.T_isentropic(T_in, p_in, p_out, comp)

        h_in = fluid.h(T_in, p_in, comp)
        h_out_s = fluid.h(T_out_s, p_out, comp)

        # h_out = h_in + (h_out_s - h_in) / η_c  (eta_override threaded for
        # the live-meanline path, ADAPT-036)
        delta_h_isentropic = h_out_s - h_in
        h_out = h_in + delta_h_isentropic / eta

        # Solve for actual T_out
        T_out = fluid.T_from_h(h_out, p_out, comp, T_out_s)

        # Power (positive = work input into the fluid by the compressor)
        W_c = (m_dot * (h_out - h_in)).to("W")

        outlet = Port(
            pressure_total=p_out,
            temperature_total=T_out,
            mass_flow=m_dot,
            composition=comp,
            rotational_speed=inlet.rotational_speed,
            swirl_ratio=0.0,
            velocity_meridional=Q(0.0, "m/s"),
            radius_mean=Q(0.0, "m"),
        )
        return outlet, W_c


# --- Turbine -----------------------------------------------------------------


@dataclass(frozen=True)
class Turbine:
    """Single-stage or lumped turbine with isentropic efficiency.

    Algebra:
        p_t_out = p_t_in / π_t
        T_5s satisfies s(T_5s, p_t_out) = s(T_t_in, p_t_in)
        h_t_out = h_t_in − η_t · (h_t_in − h_t_5s)
        Ẇ_t = ṁ · (h_t_in − h_t_out)

    `shaft_id` (ADAPT-034) identifies which spool this turbine sits on. For a
    2-spool turbofan, the HPT lives on shaft 1 with the HPC and the LPT lives
    on shaft 2 with the fan + LPC.

    `efficiency_mode` + `meanline_geometry` (ADAPT-036) mirror the Compressor:
    "live_meanline" runs `RadialTurbineMeanline` inside each cycle iteration.
    """

    name: str
    pressure_ratio: float  # π_t = p_in / p_out (i.e., > 1 for an expansion)
    efficiency_isentropic: float
    shaft_id: int = 1
    efficiency_mode: EfficiencyMode = "constant"
    meanline_geometry: Optional[Any] = None
    meanline_rpm: Optional[Quantity] = None

    def __post_init__(self) -> None:
        if self.pressure_ratio < 1.0:
            msg = (
                f"Turbine '{self.name}': pressure_ratio {self.pressure_ratio} "
                f"< 1.0 is not a turbine (should be p_in / p_out > 1)"
            )
            raise ValueError(msg)
        if not (0.0 < self.efficiency_isentropic <= 1.0):
            msg = (
                f"Turbine '{self.name}': efficiency must be in (0, 1]; "
                f"got {self.efficiency_isentropic}"
            )
            raise ValueError(msg)
        if self.shaft_id < 1:
            msg = (
                f"Turbine '{self.name}': shaft_id must be ≥ 1; "
                f"got {self.shaft_id}"
            )
            raise ValueError(msg)
        if self.efficiency_mode == "live_meanline" and self.meanline_geometry is None:
            msg = (
                f"Turbine '{self.name}': efficiency_mode='live_meanline' "
                f"requires meanline_geometry to be set."
            )
            raise ValueError(msg)

    def solve(
        self,
        inlet: Port,
        fluid: FluidModel,
        eta_override: Optional[float] = None,
    ) -> Tuple[Port, Quantity]:
        """Compute outlet Port and shaft work [W] (positive = power output).

        `eta_override` injects the live-meanline η from the cycle solver
        (ADAPT-036). When None, the lumped `efficiency_isentropic` is used.
        """
        _refuse_high_pr(self.pressure_ratio, f"Turbine '{self.name}'")
        eta = eta_override if eta_override is not None else self.efficiency_isentropic

        p_in = inlet.pressure_total
        T_in = inlet.temperature_total
        comp = inlet.composition
        m_dot = inlet.mass_flow

        p_out = p_in / self.pressure_ratio

        T_out_s = fluid.T_isentropic(T_in, p_in, p_out, comp)

        h_in = fluid.h(T_in, p_in, comp)
        h_out_s = fluid.h(T_out_s, p_out, comp)

        delta_h_isentropic = h_in - h_out_s  # positive
        h_out = h_in - eta * delta_h_isentropic
        T_out = fluid.T_from_h(h_out, p_out, comp, T_out_s)

        # Positive = power extracted from the fluid
        W_t = (m_dot * (h_in - h_out)).to("W")

        outlet = Port(
            pressure_total=p_out,
            temperature_total=T_out,
            mass_flow=m_dot,
            composition=comp,
        )
        return outlet, W_t


# --- Burner ------------------------------------------------------------------


@dataclass(frozen=True)
class Burner:
    """Ideal-burner (T-rise) model.

    Two specification modes (exactly one required):
      - `outlet_temperature` — user-specified T_t,out. Fuel flow is back-derived
        from the energy balance.
      - `fuel_mass_flow`     — user-specified ṁ_fuel. T_t,out is back-derived.

    Algebra:
        Mass:     ṁ_4 = ṁ_3 + ṁ_fuel
        Energy:   ṁ_3 h_3 + ṁ_fuel (h_fuel + LHV · η_comb) = ṁ_4 h_4
        Pressure: p_4 = p_3 · (1 − Δp_b/p_3)
        Composition: stoichiometric C_x H_y combustion (lean only).

    The fuel enters at `inlet_temperature_fuel` (default 298.15 K). Its sensible
    enthalpy contribution at that temperature is small relative to LHV; we
    include it for completeness (Walsh & Fletcher 2004 §5.10).

    Per SPEC_SHEET §13: T_t,out > 2100 K → refusal (RegimeOutOfValidity).
    """

    name: str
    pressure_drop_fraction: float = 0.04  # Δp/p, default 4% (mid of W&F 3-6%)
    combustion_efficiency: float = 0.99
    # Default fuel: methane (CH4) — the standard microturbine fuel
    fuel_lhv: Quantity = field(default_factory=lambda: Q(50.0e6, "J/kg"))
    fuel_carbon_atoms: int = 1
    fuel_hydrogen_atoms: int = 4
    fuel_molar_mass: Quantity = field(default_factory=lambda: Q(16.0425, "g/mol"))
    fuel_inlet_temperature: Quantity = field(default_factory=lambda: Q(298.15, "K"))
    # One of the two below must be set
    outlet_temperature: Optional[Quantity] = None
    fuel_mass_flow: Optional[Quantity] = None
    # Air-standard mode: skip mass + composition update; only heat-rise.
    # Used for textbook validation (CYC-1, CYC-2 — Çengel air-standard analysis).
    air_standard: bool = False

    def __post_init__(self) -> None:
        if not (0.0 <= self.pressure_drop_fraction < 0.5):
            msg = (
                f"Burner '{self.name}': pressure_drop_fraction must be in "
                f"[0, 0.5); got {self.pressure_drop_fraction}"
            )
            raise ValueError(msg)
        if not (0.0 < self.combustion_efficiency <= 1.0):
            msg = (
                f"Burner '{self.name}': combustion_efficiency must be in "
                f"(0, 1]; got {self.combustion_efficiency}"
            )
            raise ValueError(msg)
        if (self.outlet_temperature is None) == (self.fuel_mass_flow is None):
            msg = (
                f"Burner '{self.name}': exactly one of outlet_temperature or "
                f"fuel_mass_flow must be set"
            )
            raise ValueError(msg)

    def solve(
        self,
        inlet: Port,
        fluid: FluidModel,
    ) -> Tuple[Port, Quantity]:
        """Compute outlet Port and fuel mass flow [kg/s].

        Returns: (outlet_port, fuel_mass_flow_actual).

        If the user specified outlet_temperature, fuel flow is solved by Newton
        on the energy balance with composition update.
        If the user specified fuel_mass_flow, outlet temperature is solved by
        Newton on the energy balance with composition update.

        Air-standard mode: composition is unchanged, mass flow is unchanged,
        fuel mass flow returned as the *equivalent* heat-equivalent quantity
        (Q_dot / LHV) for downstream η accounting. This matches Çengel & Boles
        Ch. 9 air-standard analysis (CYC-1, CYC-2).
        """
        p_in = inlet.pressure_total
        T_in = inlet.temperature_total
        comp_in = inlet.composition
        m_dot_air = inlet.mass_flow

        # Outlet pressure
        p_out = p_in * (1.0 - self.pressure_drop_fraction)
        if p_out.to("Pa").magnitude <= 0:
            msg = f"Burner '{self.name}': pressure_drop_fraction yields p_out ≤ 0"
            raise ValueError(msg)

        # Air-standard mode: simple heat-addition with constant ṁ and
        # unchanged composition. The "fuel_mass_flow" returned is the
        # equivalent Q̇/LHV used for accounting.
        if self.air_standard:
            if self.outlet_temperature is None:
                msg = (
                    f"Burner '{self.name}': air_standard=True requires "
                    f"outlet_temperature (textbook spec is T-rise)."
                )
                raise ValueError(msg)
            T_out_K = self.outlet_temperature.to("K").magnitude
            _refuse_high_burner_T(T_out_K)
            h_in_si = fluid.h(T_in, p_in, comp_in).to("J/kg").magnitude
            h_out_si = (
                fluid.h(self.outlet_temperature, p_out, comp_in)
                .to("J/kg")
                .magnitude
            )
            Q_dot = m_dot_air.to("kg/s").magnitude * (h_out_si - h_in_si)
            m_equiv_fuel = Q_dot / (
                self.fuel_lhv.to("J/kg").magnitude * self.combustion_efficiency
            )
            outlet = Port(
                pressure_total=p_out,
                temperature_total=self.outlet_temperature,
                mass_flow=m_dot_air,
                composition=comp_in,
            )
            return outlet, Q(m_equiv_fuel, "kg/s")

        # Helper: sensible enthalpy at given (T, p, composition)
        # Sensible = h(T,p,comp) - h(T_ref, p, comp). The LHV convention assumes
        # reactants and products at the same reference T_ref before LHV release;
        # this is the Walsh-Fletcher §5.10 / GasTurb energy-balance form, which
        # avoids the formation-enthalpy double-count that arises when full NASA
        # absolute enthalpies are used with LHV.
        T_ref_K = self.fuel_inlet_temperature.to("K").magnitude  # noqa: N806

        def h_sensible(
            T_K: float, p_Pa: float, comp: Composition  # noqa: N803
        ) -> float:
            T_Q = Q(T_K, "K")
            p_Q = Q(p_Pa, "Pa")
            try:
                h_T = fluid.h(T_Q, p_Q, comp).to("J/kg").magnitude
                h_ref = fluid.h(Q(T_ref_K, "K"), p_Q, comp).to("J/kg").magnitude
                return h_T - h_ref
            except RegimeOutOfValidity:
                # Fall through to cp-based approximation if either eval refuses.
                # Pass the local pressure: cp for real fluids depends on p as
                # well as T (ADAPT-006).
                cp_avg = fluid.cp(
                    Q(0.5 * (T_K + T_ref_K), "K"),
                    Q(p_Pa, "Pa"),
                    comp,
                ).to("J/(kg*K)").magnitude
                return cp_avg * (T_K - T_ref_K)

        def energy_balance(  # noqa: N802
            T_out_K: float, m_dot_fuel_kgs: float
        ) -> Tuple[float, Composition]:
            """Return (residual, products_composition) for given T_out and ṁ_f.

            Sensible-enthalpy form (Walsh-Fletcher §5.10):
              Residual = ṁ_air · h_sens_in + ṁ_fuel · LHV · η_comb
                       − (ṁ_air + ṁ_fuel) · h_sens_out

            Fuel sensible enthalpy is zero at the reference (it enters at T_ref).
            """
            m_dot_total = (
                m_dot_air.to("kg/s").magnitude + m_dot_fuel_kgs
            )
            Y_fuel = m_dot_fuel_kgs / m_dot_total
            products = burn_mass_balance(
                air_composition=comp_in,
                fuel_mass_fraction=Y_fuel,
                fuel_carbon_atoms=self.fuel_carbon_atoms,
                fuel_hydrogen_atoms=self.fuel_hydrogen_atoms,
                fuel_molar_mass_g_per_mol=self.fuel_molar_mass.to(
                    "g/mol"
                ).magnitude,
            )

            p_in_Pa = p_in.to("Pa").magnitude  # noqa: N806
            p_out_Pa = p_out.to("Pa").magnitude  # noqa: N806
            T_in_K = T_in.to("K").magnitude  # noqa: N806

            h_sens_in = h_sensible(T_in_K, p_in_Pa, comp_in)
            h_sens_out = h_sensible(T_out_K, p_out_Pa, products)

            lhv_si = self.fuel_lhv.to("J/kg").magnitude

            energy_in = (
                m_dot_air.to("kg/s").magnitude * h_sens_in
                + m_dot_fuel_kgs * lhv_si * self.combustion_efficiency
            )
            energy_out = m_dot_total * h_sens_out
            return energy_in - energy_out, products

        if self.outlet_temperature is not None:
            T_out_K = self.outlet_temperature.to("K").magnitude
            _refuse_high_burner_T(T_out_K)
            # Newton on ṁ_fuel to satisfy energy balance.
            # Initial guess: stoichiometric heuristic. Energy needed:
            # m_dot_air * cp * (T_out - T_in); fuel delivers LHV·η per kg.
            # Pass the local burner inlet pressure: cp for real fluids
            # depends on p as well as T (ADAPT-006).
            cp_avg = fluid.cp(
                Q((T_in.to("K").magnitude + T_out_K) / 2.0, "K"),
                p_in,
                comp_in,
            ).to("J/(kg*K)").magnitude
            Q_needed = (
                m_dot_air.to("kg/s").magnitude
                * cp_avg
                * (T_out_K - T_in.to("K").magnitude)
            )
            m_dot_f = Q_needed / (
                self.fuel_lhv.to("J/kg").magnitude * self.combustion_efficiency
            )
            if m_dot_f < 0:
                m_dot_f = 0.0

            # Newton converge ṁ_fuel against the energy residual; the products
            # composition is recomputed each iter (the Y_fuel shift is small).
            products: Composition = comp_in
            for _it in range(80):
                R, products = energy_balance(T_out_K, m_dot_f)
                # ∂R / ∂(ṁ_f) ≈ LHV·η − h_4 + h_fuel (close to LHV since
                # LHV >> h_4); use as Newton derivative.
                # Forward-difference is more robust.
                eps = max(1e-7, abs(m_dot_f) * 1e-5)
                R_plus, _ = energy_balance(T_out_K, m_dot_f + eps)
                dR_dm = (R_plus - R) / eps
                if abs(dR_dm) < 1e-30:
                    break
                step = -R / dR_dm
                # Damping (SPEC_SHEET §9 — Armijo-style relaxation)
                m_dot_f_new = m_dot_f + step
                if m_dot_f_new < 0:
                    m_dot_f_new = m_dot_f * 0.5
                m_dot_f = m_dot_f_new
                if abs(R) < 1e-3 * max(1.0, abs(Q_needed)):
                    break

            m_dot_total = m_dot_air.to("kg/s").magnitude + m_dot_f
            outlet = Port(
                pressure_total=p_out,
                temperature_total=Q(T_out_K, "K"),
                mass_flow=Q(m_dot_total, "kg/s"),
                composition=products,
            )
            return outlet, Q(m_dot_f, "kg/s")
        else:
            assert self.fuel_mass_flow is not None
            m_dot_f = self.fuel_mass_flow.to("kg/s").magnitude
            # Newton on T_out to satisfy energy balance
            T_out_guess = T_in.to("K").magnitude + 800.0
            T_out_K = T_out_guess
            products = comp_in
            for _it in range(80):
                R, products = energy_balance(T_out_K, m_dot_f)
                eps = max(0.1, abs(T_out_K) * 1e-5)
                R_plus, _ = energy_balance(T_out_K + eps, m_dot_f)
                dR_dT = (R_plus - R) / eps
                if abs(dR_dT) < 1e-30:
                    break
                step = -R / dR_dT
                T_out_K_new = T_out_K + step
                if T_out_K_new < T_in.to("K").magnitude:
                    T_out_K_new = (T_out_K + T_in.to("K").magnitude) / 2.0
                T_out_K = T_out_K_new
                if abs(R) < 1e-3:
                    break
            _refuse_high_burner_T(T_out_K)
            m_dot_total = m_dot_air.to("kg/s").magnitude + m_dot_f
            outlet = Port(
                pressure_total=p_out,
                temperature_total=Q(T_out_K, "K"),
                mass_flow=Q(m_dot_total, "kg/s"),
                composition=products,
            )
            return outlet, Q(m_dot_f, "kg/s")


# --- Recuperator -------------------------------------------------------------


@dataclass(frozen=True)
class Recuperator:
    """Counterflow recuperator, ε-NTU effectiveness model.

    Connects two streams: cold (compressor discharge → burner) and hot (turbine
    exhaust → exhaust). The cold-side outlet temperature is raised toward the
    hot-side inlet; the hot-side outlet falls toward the cold-side inlet, with
    energy conservation linking them.

    Definitions:
        ε = (T_cold_out − T_cold_in) / (T_hot_in − T_cold_in)         (cold-side)
        ṁ_cold cp_cold ΔT_cold = ṁ_hot cp_hot ΔT_hot                  (energy)

    With equal mass flow and *equal* cp (gross approximation): T_cold_out is
    determined by ε; T_hot_out follows by energy balance. With variable cp, we
    iterate: assume T_cold_out from ε, evaluate cp_cold(T̄_cold), compute
    Q_transferred = ṁ_cold ⟨cp⟩ ΔT_cold, then back-out T_hot_out.

    Pressure drops on both sides (2-4% per side typical).

    Per SPEC_SHEET §13: ε ∈ [0, 0.98]. ε > 0.98 refused (pinch divergence).
    """

    name: str
    effectiveness: float
    cold_pressure_drop_fraction: float = 0.03  # 3% typical
    hot_pressure_drop_fraction: float = 0.03

    def __post_init__(self) -> None:
        if not (0.0 <= self.effectiveness <= EFFECTIVENESS_REFUSE_HIGH):
            msg = (
                f"Recuperator '{self.name}': effectiveness must be in "
                f"[0, {EFFECTIVENESS_REFUSE_HIGH}]; got {self.effectiveness}. "
                f"Per SPEC_SHEET §13 high effectiveness can drive pinch "
                f"divergence."
            )
            raise ValueError(msg)
        for name, val in [
            ("cold_pressure_drop_fraction", self.cold_pressure_drop_fraction),
            ("hot_pressure_drop_fraction", self.hot_pressure_drop_fraction),
        ]:
            if not (0.0 <= val < 0.5):
                msg = (
                    f"Recuperator '{self.name}': {name} must be in [0, 0.5); "
                    f"got {val}"
                )
                raise ValueError(msg)

    def solve(
        self,
        cold_in: Port,
        hot_in: Port,
        fluid: FluidModel,
    ) -> Tuple[Port, Port]:
        """Compute (cold_out, hot_out) Ports from (cold_in, hot_in).

        Variable-cp iteration: assume T_cold_out ≈ T_cold_in + ε(T_hot_in -
        T_cold_in) (constant-cp first guess), then refine using actual h
        differences from the fluid model. Convergence in 3-5 iterations.
        """
        T_cold_in = cold_in.temperature_total
        T_hot_in = hot_in.temperature_total
        p_cold_in = cold_in.pressure_total
        p_hot_in = hot_in.pressure_total
        comp_cold = cold_in.composition
        comp_hot = hot_in.composition
        m_cold = cold_in.mass_flow
        m_hot = hot_in.mass_flow

        # Second-law check: hot_in must be above cold_in,
        # otherwise the recuperator would violate the 2nd Law.
        if T_hot_in.to("K").magnitude <= T_cold_in.to("K").magnitude:
            msg = (
                f"Recuperator '{self.name}': T_hot_in "
                f"{T_hot_in.to('K').magnitude:.1f} K must exceed "
                f"T_cold_in {T_cold_in.to('K').magnitude:.1f} K (2nd Law)."
            )
            raise ValueError(msg)

        # Cold-side outlet T from definition of ε (this is the canonical
        # cold-side ε definition).
        T_hot_K = T_hot_in.to("K").magnitude
        T_cold_K = T_cold_in.to("K").magnitude
        T_cold_out_K = T_cold_K + self.effectiveness * (T_hot_K - T_cold_K)
        T_cold_out = Q(T_cold_out_K, "K")

        # Energy balance to get T_hot_out — variable cp iteration
        h_cold_in = fluid.h(T_cold_in, p_cold_in, comp_cold).to("J/kg").magnitude
        h_cold_out = (
            fluid.h(T_cold_out, p_cold_in, comp_cold).to("J/kg").magnitude
        )
        # Heat transferred to cold side, [W]
        Q_dot = m_cold.to("kg/s").magnitude * (h_cold_out - h_cold_in)
        # Hot-side outlet h such that hot side loses the same Q:
        h_hot_in = fluid.h(T_hot_in, p_hot_in, comp_hot).to("J/kg").magnitude
        h_hot_out_target = h_hot_in - Q_dot / m_hot.to("kg/s").magnitude
        # Invert h(T, p) on hot-side composition at the hot-side inlet
        # pressure (the small hot-side Δp drop is applied below; using
        # p_hot_in here is accurate to a fraction of a kelvin even for
        # real-gas fluids near the critical point).
        T_hot_out = fluid.T_from_h(
            Q(h_hot_out_target, "J/kg"), p_hot_in, comp_hot, T_hot_in
        )

        # Pressure drops
        p_cold_out = p_cold_in * (1.0 - self.cold_pressure_drop_fraction)
        p_hot_out = p_hot_in * (1.0 - self.hot_pressure_drop_fraction)

        # Sanity: hot_out must remain ≥ cold_in (else 2nd Law violation)
        if T_hot_out.to("K").magnitude < T_cold_in.to("K").magnitude - 1.0:
            msg = (
                f"Recuperator '{self.name}': solved T_hot_out "
                f"{T_hot_out.to('K').magnitude:.1f} K < T_cold_in "
                f"{T_cold_in.to('K').magnitude:.1f} K. "
                f"Effectiveness {self.effectiveness} too high for these flows; "
                f"reduce ε."
            )
            raise RegimeOutOfValidity(msg, code="RECUPERATOR_PINCH")

        cold_out = Port(
            pressure_total=p_cold_out,
            temperature_total=T_cold_out,
            mass_flow=m_cold,
            composition=comp_cold,
        )
        hot_out = Port(
            pressure_total=p_hot_out,
            temperature_total=T_hot_out,
            mass_flow=m_hot,
            composition=comp_hot,
        )
        return cold_out, hot_out


# --- Intercooler -------------------------------------------------------------


@dataclass(frozen=True)
class Intercooler:
    """Air-air intercooler between two compressors, ε-NTU model.

    Inputs: hot-stream inlet Port (the gas being cooled) + coolant temperature.
    Algebra:
        T_out = T_in − ε · (T_in − T_coolant)
    """

    name: str
    effectiveness: float
    coolant_temperature: Quantity
    pressure_drop_fraction: float = 0.02  # 2% typical

    def __post_init__(self) -> None:
        if not (0.0 <= self.effectiveness <= EFFECTIVENESS_REFUSE_HIGH):
            msg = (
                f"Intercooler '{self.name}': effectiveness must be in "
                f"[0, {EFFECTIVENESS_REFUSE_HIGH}]; got {self.effectiveness}"
            )
            raise ValueError(msg)

    def solve(
        self,
        inlet: Port,
        fluid: FluidModel,
    ) -> Port:  # noqa: ARG002
        T_in_K = inlet.temperature_total.to("K").magnitude
        T_cool_K = self.coolant_temperature.to("K").magnitude
        T_out_K = T_in_K - self.effectiveness * (T_in_K - T_cool_K)
        p_out = inlet.pressure_total * (1.0 - self.pressure_drop_fraction)
        return Port(
            pressure_total=p_out,
            temperature_total=Q(T_out_K, "K"),
            mass_flow=inlet.mass_flow,
            composition=inlet.composition,
        )


# --- Mixer -------------------------------------------------------------------


@dataclass(frozen=True)
class Mixer:
    """Two-stream mixer with mass and energy conservation.

    Algebra:
        ṁ_out = ṁ_a + ṁ_b
        h_out = (ṁ_a h_a + ṁ_b h_b) / ṁ_out
        Y_out,k = (ṁ_a Y_a,k + ṁ_b Y_b,k) / ṁ_out
        p_out = min(p_a, p_b)  (worst-case; v1.1 will use momentum form)
    """

    name: str

    def solve(self, a: Port, b: Port, fluid: FluidModel) -> Port:
        m_a = a.mass_flow.to("kg/s").magnitude
        m_b = b.mass_flow.to("kg/s").magnitude
        m_tot = m_a + m_b
        if m_tot <= 0:
            msg = f"Mixer '{self.name}': total mass flow ≤ 0"
            raise ValueError(msg)

        # Composition is mass-weighted on each species
        all_sp: Dict[Species, float] = {}
        for sp, Y in a.composition.mass_fractions.items():
            all_sp[sp] = all_sp.get(sp, 0.0) + Y * m_a
        for sp, Y in b.composition.mass_fractions.items():
            all_sp[sp] = all_sp.get(sp, 0.0) + Y * m_b
        Y_out = {sp: m / m_tot for sp, m in all_sp.items() if m > 1e-12}
        # Renormalize
        total = sum(Y_out.values())
        Y_out = {sp: Y / total for sp, Y in Y_out.items()}
        comp_out = Composition(mass_fractions=Y_out)

        # Energy balance: solve for T_out such that mixed h = average
        h_a = fluid.h(a.temperature_total, a.pressure_total, a.composition)
        h_b = fluid.h(b.temperature_total, b.pressure_total, b.composition)
        h_out_si = (
            m_a * h_a.to("J/kg").magnitude + m_b * h_b.to("J/kg").magnitude
        ) / m_tot

        # Use min pressure as outlet (conservative, momentum-balance neutral)
        p_out_Pa = min(  # noqa: N806
            a.pressure_total.to("Pa").magnitude,
            b.pressure_total.to("Pa").magnitude,
        )
        p_out = Q(p_out_Pa, "Pa")

        # Invert h(T) on the mixed composition
        T_guess = Q(
            (a.temperature_total.to("K").magnitude + b.temperature_total.to("K").magnitude)
            / 2.0,
            "K",
        )
        T_out = fluid.T_from_h(Q(h_out_si, "J/kg"), p_out, comp_out, T_guess)

        return Port(
            pressure_total=p_out,
            temperature_total=T_out,
            mass_flow=Q(m_tot, "kg/s"),
            composition=comp_out,
        )


# --- Splitter ----------------------------------------------------------------


@dataclass(frozen=True)
class Splitter:
    """Mass-fraction splitter (bleed extraction).

    Algebra:
        ṁ_main = (1 − β) ṁ_in
        ṁ_bleed = β ṁ_in
        composition, T, p unchanged on both branches.
    """

    name: str
    bleed_fraction: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.bleed_fraction < 1.0):
            msg = (
                f"Splitter '{self.name}': bleed_fraction must be in [0, 1); "
                f"got {self.bleed_fraction}"
            )
            raise ValueError(msg)

    def solve(self, inlet: Port) -> Tuple[Port, Port]:
        m_in = inlet.mass_flow.to("kg/s").magnitude
        m_bleed = m_in * self.bleed_fraction
        m_main = m_in - m_bleed
        main = Port(
            pressure_total=inlet.pressure_total,
            temperature_total=inlet.temperature_total,
            mass_flow=Q(m_main, "kg/s"),
            composition=inlet.composition,
        )
        bleed = Port(
            pressure_total=inlet.pressure_total,
            temperature_total=inlet.temperature_total,
            mass_flow=Q(m_bleed, "kg/s"),
            composition=inlet.composition,
        )
        return main, bleed


# --- ConstantPressureLoss ---------------------------------------------------


@dataclass(frozen=True)
class ConstantPressureLoss:
    """Duct with lumped Δp/p loss. No work, no heat, no composition change.

    Used to model inlet ducts (1-3% loss per W&F §5), exhaust ducts, manifolds.
    """

    name: str
    pressure_drop_fraction: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.pressure_drop_fraction < 1.0):
            msg = (
                f"ConstantPressureLoss '{self.name}': pressure_drop_fraction "
                f"must be in [0, 1); got {self.pressure_drop_fraction}"
            )
            raise ValueError(msg)

    def solve(self, inlet: Port) -> Port:
        return Port(
            pressure_total=inlet.pressure_total
            * (1.0 - self.pressure_drop_fraction),
            temperature_total=inlet.temperature_total,
            mass_flow=inlet.mass_flow,
            composition=inlet.composition,
        )


# --- Shaft (ADAPT-034) -----------------------------------------------------


@dataclass(frozen=True)
class Shaft:
    """A mechanical shaft (spool) coupling one or more compressors to one or
    more turbines. Cycle solver enforces power balance on each shaft:

        Σ_t Ẇ_turbine_on_shaft · η_mech = Σ_c Ẇ_compressor_on_shaft

    Real aero engines have a separate shaft per pressure level:

      - Single-shaft microturbine (Capstone C30): one shaft.
      - 2-spool turbofan (CFM56 / CF6-80C2):  HPC ↔ HPT, fan+LPC ↔ LPT.
      - 3-spool (Trent-class): HPC ↔ HPT, IPC ↔ IPT, fan+LPC ↔ LPT.

    `mechanical_efficiency` lumps bearing + gear losses (Walsh & Fletcher
    §5; typical 0.97–0.99 per shaft). The cycle solver multiplies turbine
    work by this factor before comparing to compressor work.

    `components` is the list of `Compressor.name` / `Turbine.name` strings
    sitting on this shaft. Used for diagnostics and post-solve reports.

    `rotational_speed_rpm` is solved by the multi-shaft solver; the user
    supplies it as an initial guess. After convergence the result holds the
    matched speed.
    """

    id: int  # 1, 2, 3 (HP, IP, LP convention — but you do you)
    name: str
    components: List[str] = field(default_factory=list)
    rotational_speed_rpm: float = 0.0  # initial guess; solver updates
    mechanical_efficiency: float = 0.98

    def __post_init__(self) -> None:
        if self.id < 1:
            raise ValueError(f"Shaft '{self.name}': id must be ≥ 1; got {self.id}")
        if not (0.0 < self.mechanical_efficiency <= 1.0):
            raise ValueError(
                f"Shaft '{self.name}': mechanical_efficiency must be in (0, 1]; "
                f"got {self.mechanical_efficiency}"
            )
        if self.rotational_speed_rpm < 0:
            raise ValueError(
                f"Shaft '{self.name}': rotational_speed_rpm must be ≥ 0; "
                f"got {self.rotational_speed_rpm}"
            )


__all__ = [
    "Compressor",
    "Turbine",
    "Burner",
    "Recuperator",
    "Intercooler",
    "Mixer",
    "Splitter",
    "ConstantPressureLoss",
    "Shaft",
    "EfficiencyMode",
    "PR_REFUSE_HARD",
    "PR_WARN_HIGH",
    "T_BURNER_REFUSE",
    "EFFECTIVENESS_REFUSE_HIGH",
]
