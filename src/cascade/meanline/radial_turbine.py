"""Radial-inflow turbine mean-line solver.

Implements the Whitfield & Baines (1990) Ch. 6 design procedure with
Glassman (1976) tip-clearance and Daily-Nece (1960) disc friction.
Solves a one-dimensional steady flow through the rotor with the
Euler turbomachinery equation, velocity triangles at the rotor LE and
exducer TE, and the loss-summation efficiency definition.

The solver enforces SPEC_SHEET §13 refusal envelope: relative Mach > 2.5
at any station raises `RegimeOutOfValidity`.

References (canonical):
- Whitfield, A. & Baines, N.C., 1990. *Design of Radial Turbomachines*,
  Longman, Ch. 6 ("Aerodynamic Design and Performance of Radial Turbines").
- Glassman, A.J., 1976. *Computer Program for Design Analysis of
  Radial-Inflow Turbines*, NASA TN D-8164.
- Dixon, S.L. & Hall, C.A., 7th ed. 2014. *Fluid Mechanics and
  Thermodynamics of Turbomachinery*, Butterworth-Heinemann, Ch. 9
  ("Radial Flow Gas Turbines").
- Whitney, W.J., Stewart, W.L., 1974. "Aerodynamic Performance of a
  Radial Inflow Turbine Designed for an 85,000-rpm Helium Cycle Drive",
  NASA TN D-7508.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from cascade.meanline.exceptions import (
    InvalidGeometry,
    MeanlineConvergenceError,
    RegimeOutOfValidity,
)
from cascade.meanline.fluid import PerfectGas, AIR
from cascade.meanline.loss_models import LossBreakdown, LossModel
from cascade.units import Composition, Port, Q, Quantity


# =============================================================================
# Geometry
# =============================================================================


@dataclass(frozen=True)
class RadialTurbineGeometry:
    """Geometric parameters of a radial-inflow turbine rotor.

    Convention (per SPEC_SHEET §3.2, canonical store is radians from axial):

    - `inlet_metal_angle_rad`: blade angle at rotor inlet (LE), measured from
      the axial direction. For a typical radial inflow rotor at design,
      the LE is purely radial → 0 rad from axial (the legacy-tool
      "90.000000 tan.deg" convention).
    - `exducer_angle_rad`: blade angle at rotor exit (TE), from axial.
      Typical 55°–75° from axial (i.e., the relative flow is strongly
      tangential at the TE because the wheel rotation contributes).

    All linear dimensions are in metres.
    """

    rotor_inlet_radius: float  # r₁ [m]
    rotor_outlet_radius_hub: float  # r₂_hub [m]
    rotor_outlet_radius_tip: float  # r₂_tip [m]
    blade_height_inlet: float  # b₁ [m]
    blade_height_outlet: float  # b₂ = r₂_tip - r₂_hub [m]
    blade_count: int  # Z (number of full blades; ignores splitters for now)
    inlet_metal_angle_rad: float  # β₁' from axial [rad]; 0 = purely radial
    exducer_angle_rad: float  # β₂' from axial [rad]; ~π/3 to 4π/9 typical
    tip_clearance: float  # ε [m]
    nozzle_angle_rad: Optional[float] = None  # α₁ from axial [rad]; if None,
    # derived from design swirl_ratio (V_θ₁/U₁ = swirl_ratio_design).
    design_swirl_ratio: float = 1.0  # V_θ₁/U₁ at design (1.0 = zero incidence)
    chord_meridional: Optional[float] = None  # if None, defaults to (r₁ - r₂_tip)
    disc_gap_ratio: float = 0.02  # G/r for disc-friction

    def __post_init__(self) -> None:
        if self.rotor_inlet_radius <= 0:
            raise InvalidGeometry("rotor_inlet_radius must be > 0")
        if self.rotor_outlet_radius_hub < 0:
            raise InvalidGeometry("rotor_outlet_radius_hub must be ≥ 0")
        if self.rotor_outlet_radius_tip <= self.rotor_outlet_radius_hub:
            raise InvalidGeometry("rotor_outlet_radius_tip must exceed hub")
        if self.rotor_outlet_radius_tip >= self.rotor_inlet_radius:
            raise InvalidGeometry("rotor_outlet_radius_tip must be < inlet "
                                  "radius for an inflow turbine")
        if self.blade_height_inlet <= 0 or self.blade_height_outlet <= 0:
            raise InvalidGeometry("blade heights must be > 0")
        if self.blade_count < 3:
            raise InvalidGeometry("blade_count must be ≥ 3")
        if self.tip_clearance < 0:
            raise InvalidGeometry("tip_clearance must be ≥ 0")


# =============================================================================
# Result
# =============================================================================


@dataclass(frozen=True)
class PortState:
    """A station's thermodynamic + kinematic snapshot for diagnostics / UI.

    Used in `RadialTurbineResult.port_states` and the centrifugal-compressor
    sister type. Unlike the canonical :class:`cascade.units.Port`, this carries
    static-and-total state plus Mach so downstream panels can render the
    h–s diagram and velocity triangle without back-computing.
    """

    T_static_K: float
    T_total_K: float
    p_static_Pa: float
    p_total_Pa: float
    h_static_J_per_kg: float
    h_total_J_per_kg: float
    s_J_per_kgK: float
    M: float
    rho_kg_per_m3: float


@dataclass(frozen=True)
class VTriangle:
    """Per-station velocity triangle from the mean-line solve.

    All velocities in m/s; angles in degrees (UI-friendly). Sign convention:
    positive tangential ≡ in the direction of blade rotation. `W` is the
    rotor-frame relative velocity (V − U·\\hat{θ}).
    """

    U: float                    # blade speed
    V_meridional: float         # meridional component of absolute V
    V_theta: float              # tangential component of absolute V
    W_meridional: float         # meridional component of relative W
    W_theta: float              # tangential component of relative W
    V: float                    # |V|
    W: float                    # |W|
    alpha_flow_deg: float       # absolute flow angle from meridional
    beta_flow_deg: float        # relative flow angle from meridional


@dataclass(frozen=True)
class RadialTurbineResult:
    """The full mean-line result for a single design-point solve.

    `outlet` is the canonical Port (SPEC_SHEET §3.1) for downstream co-sim.

    `eta_ts` is computed properly (ADAPT-022): the denominator is the
    isentropic expansion *from the inlet total state to the exit static
    pressure* — not a hard-coded η_tt − 0.03 offset. The residual exit
    kinetic energy ½V₂² is exactly the gap between η_tt and η_ts (it cannot
    be recovered without a downstream diffuser).
    """

    outlet: Port
    eta_tt: float  # total-to-total efficiency
    eta_ts: float  # total-to-static efficiency (proper formula — ADAPT-022)
    eta_polytropic: float  # polytropic (small-stage) efficiency
    power_W: Quantity  # work rate [W]
    pressure_ratio_tt: float  # P_01 / P_02
    pressure_ratio_ts: float  # P_01 / P_2_static
    max_M_rel: float  # maximum relative Mach across stations
    max_tip_speed: Quantity  # U_1 (m/s) — the inlet tip is fastest
    U_1: Quantity
    U_2: Quantity
    V_1: Quantity
    V_2: Quantity
    W_1: Quantity
    W_2: Quantity
    work_coefficient: float  # Λ_u = Δh_0 / U_1²
    flow_coefficient: float  # φ = V_m2 / U_2
    h_s2_at_p2_J_per_kg: float  # isentropic static enthalpy at exit static p (ADAPT-022)
    port_states: dict  # {"inlet": PortState, "exit": PortState}
    velocity_triangles: dict  # {"inlet": VTriangle, "exit": VTriangle}
    loss_breakdown: LossBreakdown
    convergence_history: list  # list of {"iter": int, "residual": float, "max_change": float}
    convergence_info: dict
    fluid_name: str

    @property
    def efficiency_tt(self) -> float:
        return self.eta_tt

    @property
    def efficiency_ts(self) -> float:
        return self.eta_ts


# =============================================================================
# Solver
# =============================================================================


@dataclass
class RadialTurbineMeanline:
    """1-D mean-line forward solver for a radial-inflow turbine.

    Solve procedure:

    1. Velocity triangle at rotor inlet (station 1):
       - U₁ = ω r₁
       - V_θ₁ from nozzle angle and continuity (initial guess: V_θ₁ = U₁
         for optimum incidence)
       - V_m₁ from continuity (ρ₁ V_m₁ A₁ = ṁ)
       - W₁ from V₁ - U_e_θ
    2. Velocity triangle at rotor exit (station 2):
       - U₂ = ω r₂_mean
       - β₂ from exducer metal angle and deviation (zero for now)
       - V_θ₂ from rothalpy or design assumption (V_θ₂ = 0)
       - V_m₂ from continuity at exit (ρ₂ V_m₂ A₂ = ṁ)
       - Rothalpy invariance: h₁ + W₁²/2 - U₁²/2 = h₂ + W₂²/2 - U₂²/2
    3. Loss bookkeeping: incidence, profile, secondary, tip, disc-friction,
       exducer kinetic — all from the chosen loss model.
    4. Efficiency: η_tt = Δh_actual / (Δh_actual + Σ Δh_loss).

    Implementation note: we use a perfect-gas fluid model (γ, cp). The
    solver accepts any `PerfectGas` instance. A future upgrade will accept
    `NasaMixture` or `CoolPropFluid` for real-gas working fluids
    (SPEC_SHEET §3.4).

    Convergence: inner fixed-point iteration on (V_m₁, V_m₂) until the
    continuity residual norm is < 1e-6 relative (SPEC §3.3).
    Max iterations: 200.
    """

    max_iterations: int = 200
    tol_relative: float = 1e-6
    relaxation: float = 0.6  # under-relaxation for fixed-point

    def solve(self, inlet: Port, rpm: Quantity,
              geometry: RadialTurbineGeometry, loss_model: LossModel,
              fluid: PerfectGas = AIR,
              p_out_static: Optional[Quantity] = None) -> RadialTurbineResult:
        """Run a forward design-point solve.

        Args:
            inlet: rotor-inlet total state (Port). Carries P_t, T_t, ṁ,
                composition, and the rotational speed is overridden by `rpm`.
            rpm: shaft speed.
            geometry: rotor geometric parameters.
            loss_model: the LossModel (e.g., WhitfieldBainesRadial()).
            fluid: PerfectGas instance (default AIR).
            p_out_static: optional static pressure BC at exducer exit.
                If None, η_ts is computed against a free-discharge static
                pressure equal to P_01 / 3 as a placeholder (the engine
                lets the user supply it; not strictly required for η_tt).

        Returns:
            RadialTurbineResult with all derived quantities.

        Raises:
            RegimeOutOfValidity: if any station's relative Mach > 2.5
                (SPEC_SHEET §13).
            MeanlineConvergenceError: if continuity does not converge.
        """
        # --- pull inputs in SI ----------------------------------------------
        P_01 = float(inlet.pressure_total.to("Pa").magnitude)
        T_01 = float(inlet.temperature_total.to("K").magnitude)
        m_dot = float(inlet.mass_flow.to("kg/s").magnitude)
        omega = float(rpm.to("rad/s").magnitude)

        cp = fluid.cp_J_per_kgK
        gamma = fluid.gamma
        R = fluid.R_specific

        h_01 = cp * T_01  # reference: zero of enthalpy at T = 0

        # --- station 1: rotor inlet ----------------------------------------
        r_1 = geometry.rotor_inlet_radius
        U_1 = omega * r_1
        A_1 = 2.0 * math.pi * r_1 * geometry.blade_height_inlet

        # The standard radial-inflow turbine design constraint is
        # V_θ₁ = swirl_ratio · U₁ (Whitfield 1990 §6.3).
        # - swirl_ratio = 1.0: zero-incidence design (β₁_flow = β₁_blade =
        #   purely radial → relative velocity is purely meridional).
        # - swirl_ratio < 1: slight positive incidence (off-design).
        # The nozzle exit angle is derived from V_θ₁ and V_m₁:
        #   tan(α₁_from_tan) = V_m₁ / V_θ₁
        # When the user explicitly provides `nozzle_angle_rad`, we use that
        # angle instead (off-design / specified-stator case).
        V_theta_1_design = geometry.design_swirl_ratio * U_1
        if geometry.nozzle_angle_rad is not None:
            alpha_1_from_tan = math.pi / 2 - geometry.nozzle_angle_rad
            use_specified_nozzle = True
        else:
            alpha_1_from_tan = None  # derived in iteration below
            use_specified_nozzle = False

        # --- station 2: rotor exit -----------------------------------------
        r_2_tip = geometry.rotor_outlet_radius_tip
        r_2_hub = geometry.rotor_outlet_radius_hub
        r_2_mean = 0.5 * (r_2_tip + r_2_hub)
        U_2 = omega * r_2_mean
        A_2 = math.pi * (r_2_tip ** 2 - r_2_hub ** 2)

        # Exducer metal angle. Convention: from axial in the geometry.
        # For the relative-frame velocity triangle: β₂ from axial means the
        # blade leans backward from axial — at the TE, the meridional is
        # axial and tangential is perpendicular. So β₂_from_axial small =
        # nearly axial flow; β₂_from_axial = π/2 = purely tangential.
        # The convention adopted here matches Cascade SPEC §3.2.
        beta_2_from_axial = geometry.exducer_angle_rad
        # Design assumption: V_θ₂ = 0 (no exit swirl). With this:
        #   W_θ₂ = -U₂ (tangential component of W₂ opposes rotation)
        #   tan(β₂_from_axial) = |W_θ| / W_m = U₂ / V_m₂
        # → V_m₂ = U₂ / tan(β₂_from_axial)
        # This is the design constraint imposed by the exducer angle.
        # We will iterate V_m₂ to satisfy continuity, taking the metal angle
        # as informational (deviation = 0).
        # An alternative path is to enforce ṁ from continuity at station 2
        # and back-solve β₂. We adopt the deviation = 0 convention here for
        # simplicity; β₂ is then *derived* from the V_m₂ that closes
        # continuity.

        # --- initial guess for V_m₁, V_m₂ ----------------------------------
        # Use static density ≈ stagnation density as initial guess
        rho_01 = P_01 / (R * T_01)
        V_m1 = m_dot / max(rho_01 * A_1, 1e-9)
        V_m2 = m_dot / max(rho_01 * A_2 * 0.5, 1e-9)  # static likely lower ρ

        converged = False
        iters = 0
        history = []
        for iters in range(self.max_iterations):
            # Station 1
            if use_specified_nozzle:
                cot_a1 = 1.0 / max(math.tan(alpha_1_from_tan), 1e-9)
                V_theta_1 = V_m1 * cot_a1
            else:
                V_theta_1 = V_theta_1_design
                alpha_1_from_tan = math.atan2(V_m1, max(V_theta_1, 1e-9))
            V_1 = math.sqrt(V_m1 * V_m1 + V_theta_1 * V_theta_1)
            # Relative components
            W_theta_1 = V_theta_1 - U_1
            W_1 = math.sqrt(V_m1 * V_m1 + W_theta_1 * W_theta_1)
            # Flow angle β₁ from tangential (literature) = atan(V_m/(V_θ-U))
            # Avoid signed-issue: use full atan2.
            beta_1_from_tan = math.atan2(V_m1, W_theta_1) if abs(W_theta_1) > 1e-9 \
                else math.pi / 2
            # Blade angle β₁' from tangential — converted from axial input
            beta_1_blade_from_tan = math.pi / 2 - geometry.inlet_metal_angle_rad

            # Static state at station 1 from total energy:
            h_1 = h_01 - 0.5 * V_1 * V_1
            T_1 = h_1 / cp
            if T_1 <= 0:
                raise RegimeOutOfValidity(
                    f"Station 1 static T <= 0 (T_1={T_1:.2f}); inlet velocity "
                    f"exceeds total enthalpy budget. V_1={V_1:.2f} m/s",
                    regime_variable="T_1", value=T_1, limit=0.0)
            # Static pressure from isentropic from total state (ignoring nozzle
            # loss in this first pass; the nozzle loss is captured in the
            # loss-breakdown as part of the overall efficiency definition).
            P_1 = P_01 * (T_1 / T_01) ** (gamma / (gamma - 1))
            rho_1 = P_1 / (R * T_1)
            # Update V_m1 from continuity
            V_m1_new = m_dot / max(rho_1 * A_1, 1e-9)

            # --- Station 2 -------------------------------------------------
            # Take V_θ₂ = 0 (zero exit swirl, design assumption).
            V_theta_2 = 0.0
            V_2 = V_m2  # since V_θ₂ = 0
            W_theta_2 = V_theta_2 - U_2
            W_2 = math.sqrt(V_m2 * V_m2 + W_theta_2 * W_theta_2)
            beta_2_from_tan = math.atan2(V_m2, -W_theta_2)  # use -W_θ for positive

            # Rothalpy invariance: I = h + W²/2 - U²/2  (Dixon §9.1)
            # I₁ = I₂  → h_2 = h_1 + W_1²/2 - W_2²/2 - U_1²/2 + U_2²/2
            h_2 = h_1 + 0.5 * (W_1 * W_1 - W_2 * W_2) - 0.5 * (U_1 * U_1
                                                               - U_2 * U_2)
            T_2 = h_2 / cp
            if T_2 <= 0:
                raise RegimeOutOfValidity(
                    f"Station 2 static T <= 0 (T_2={T_2:.2f})",
                    regime_variable="T_2", value=T_2, limit=0.0)
            # Static pressure at 2: use the loss model to estimate, but for
            # the inner iteration we'll use isentropic-from-1 as a starting
            # point. The loss correction below will adjust P_02 after η_tt.
            # P_2 / P_1 = (T_2/T_1)^(γ/(γ-1)) for isentropic; in reality
            # entropy rises, so P_2 actual < P_2_isentropic.
            P_2_isen = P_1 * (T_2 / T_1) ** (gamma / (gamma - 1.0))
            rho_2 = P_2_isen / (R * T_2)
            V_m2_new = m_dot / max(rho_2 * A_2, 1e-9)

            # Apply under-relaxation
            r = self.relaxation
            V_m1_next = (1 - r) * V_m1 + r * V_m1_new
            V_m2_next = (1 - r) * V_m2 + r * V_m2_new

            # Continuity residual
            res_1 = abs(V_m1_next - V_m1) / max(abs(V_m1), 1e-9)
            res_2 = abs(V_m2_next - V_m2) / max(abs(V_m2), 1e-9)
            history.append((res_1, res_2))

            V_m1, V_m2 = V_m1_next, V_m2_next
            if max(res_1, res_2) < self.tol_relative:
                converged = True
                break

        if not converged:
            raise MeanlineConvergenceError(
                f"Radial-turbine continuity did not converge in "
                f"{self.max_iterations} iters; last residuals = "
                f"V_m1={res_1:.3e}, V_m2={res_2:.3e}")

        # --- post-converged quantities -------------------------------------
        # Re-evaluate state at both stations once with final V_m's
        if use_specified_nozzle:
            cot_a1 = 1.0 / max(math.tan(alpha_1_from_tan), 1e-9)
            V_theta_1 = V_m1 * cot_a1
        else:
            V_theta_1 = V_theta_1_design
            alpha_1_from_tan = math.atan2(V_m1, max(V_theta_1, 1e-9))
        V_1 = math.sqrt(V_m1 * V_m1 + V_theta_1 * V_theta_1)
        W_theta_1 = V_theta_1 - U_1
        W_1 = math.sqrt(V_m1 * V_m1 + W_theta_1 * W_theta_1)
        beta_1_from_tan = math.atan2(V_m1, W_theta_1) if abs(W_theta_1) > 1e-9 \
            else math.pi / 2
        beta_1_blade_from_tan = math.pi / 2 - geometry.inlet_metal_angle_rad

        h_1 = h_01 - 0.5 * V_1 * V_1
        T_1 = h_1 / cp
        P_1 = P_01 * (T_1 / T_01) ** (gamma / (gamma - 1))
        rho_1 = P_1 / (R * T_1)
        a_1 = fluid.speed_of_sound(T_1)

        V_theta_2 = 0.0
        V_2 = V_m2
        W_theta_2 = V_theta_2 - U_2
        W_2 = math.sqrt(V_m2 * V_m2 + W_theta_2 * W_theta_2)
        h_2 = h_1 + 0.5 * (W_1 * W_1 - W_2 * W_2) - 0.5 * (U_1 * U_1
                                                           - U_2 * U_2)
        T_2 = h_2 / cp
        P_2 = P_1 * (T_2 / T_1) ** (gamma / (gamma - 1))
        rho_2 = P_2 / (R * T_2)
        a_2 = fluid.speed_of_sound(T_2)

        # --- Euler work (ideal) -------------------------------------------
        # w_Euler = U₁·V_θ₁ - U₂·V_θ₂  (per Dixon §9.2)
        w_euler = U_1 * V_theta_1 - U_2 * V_theta_2
        T_02_ideal = T_01 - w_euler / cp  # ideal total T at exit

        # --- Mach checks --------------------------------------------------
        M_W1 = W_1 / max(a_1, 1e-9)
        M_W2 = W_2 / max(a_2, 1e-9)
        M_V1 = V_1 / max(a_1, 1e-9)
        M_V2 = V_2 / max(a_2, 1e-9)
        max_M_rel = max(M_W1, M_W2)

        envelope = loss_model.validity_envelope
        if envelope.M_rel_max is not None and max_M_rel > envelope.M_rel_max:
            raise RegimeOutOfValidity(
                f"max relative Mach {max_M_rel:.2f} exceeds the loss-model "
                f"validity envelope ({envelope.M_rel_max:.2f}). SPEC_SHEET "
                f"§13 forbids silent extrapolation.",
                regime_variable="M_rel", value=max_M_rel,
                limit=envelope.M_rel_max)

        # --- Loss-model evaluation -----------------------------------------
        # Reynolds (rotor) — for disc friction we use ω r²/ν
        nu = fluid.dynamic_viscosity / max(rho_2, 1e-3)
        Re_omega = omega * r_1 * r_1 / max(nu, 1e-9)

        chord_m = geometry.chord_meridional or max(r_1 - r_2_tip, 1e-4)

        loss_ctx = dict(
            W_1=W_1, W_2=W_2, V_2=V_2,
            beta_1_flow_rad=beta_1_from_tan,
            beta_1_blade_rad=beta_1_blade_from_tan,
            alpha_1_rad=alpha_1_from_tan,
            blade_count=geometry.blade_count,
            r_1=r_1, r_2_tip=r_2_tip, r_2_hub=r_2_hub,
            b_1=geometry.blade_height_inlet, b_2=geometry.blade_height_outlet,
            tip_clearance_axial=geometry.tip_clearance,
            tip_clearance_radial=geometry.tip_clearance,
            U_2=U_2, rho_2=rho_2, mass_flow=m_dot,
            chord_meridional=chord_m,
            disc_gap_ratio=geometry.disc_gap_ratio,
            Re_omega=Re_omega,
        )
        breakdown = loss_model.loss_coefficient(**loss_ctx)

        # Total enthalpy loss: each ζ_i is normalized to ½ W₂², so:
        # The exducer term is handled specifically — it captures the
        # absolute KE V₂² leaving the rotor.
        # Other terms scale by ½W₂².
        ke_W2 = 0.5 * W_2 * W_2

        # Per Whitfield 1990 §6.4: the loss decomposition for an RIT.
        #
        # Internal losses (raise entropy in the rotor; these reduce the
        # actual work extracted): incidence, profile, secondary,
        # trailing-edge, tip-clearance.
        # Parasitic losses (outside the main flow path, *subtract* from
        # shaft work output; the rotor must extract extra work to overcome
        # them, equivalently the gas does extra work on the disc): disc
        # friction.
        # Exducer kinetic energy: V₂² / 2. This appears as a *separate*
        # accounting line for total-to-static η (the absolute KE at the
        # exducer exit is "lost" if there's no downstream diffuser; for
        # total-to-total, this energy stays in the gas and h₀₂ already
        # includes it).
        rotor_internal_zeta = (breakdown.incidence + breakdown.profile
                               + breakdown.secondary
                               + breakdown.trailing_edge
                               + breakdown.tip_clearance)
        rotor_parasitic_zeta = breakdown.disc_friction
        dh_loss_internal = rotor_internal_zeta * ke_W2
        dh_loss_parasitic = rotor_parasitic_zeta * ke_W2
        dh_exducer_ke = breakdown.exducer * ke_W2  # for η_ts only

        # Shaft work delivered by gas to rotor:
        #   w_shaft = w_Euler − Δh_parasitic
        # Total enthalpy drop in the gas:
        #   h₀₁ − h₀₂_actual = w_shaft  (since parasitics are extracted
        #   from gas by the disc-friction torque on the back face)
        w_shaft = w_euler - dh_loss_parasitic
        T_02_actual = T_01 - w_shaft / cp

        # Internal losses generate entropy in the main flow → raise P₀₂
        # above the value that would obtain with isentropic expansion to
        # T₀₂_actual.
        # ds = dh_loss_internal / T_avg  (small-Δs limit)
        T_avg = 0.5 * (T_01 + T_02_actual)
        ds = dh_loss_internal / max(T_avg, 1e-3)
        # Entropy bookkeeping: ds = cp·ln(T₀₂/T₀₁) - R·ln(P₀₂/P₀₁)
        # → ln(P₀₂/P₀₁) = [cp·ln(T₀₂/T₀₁) - ds]/R
        ln_pi = (cp * math.log(T_02_actual / T_01) - ds) / R
        P_02 = P_01 * math.exp(ln_pi)
        pressure_ratio_tt = P_01 / max(P_02, 1e-3)

        # Isentropic outlet temperature at P_02 (for η_tt definition):
        T_02s = T_01 * (P_02 / P_01) ** ((gamma - 1.0) / gamma)
        # Turbine work convention: η_tt = (h_01 - h_02) / (h_01 - h_02s)
        # The actual work delivered to the shaft = w_shaft.
        # The maximum (isentropic) work for the same P_02 = cp·(T_01 - T_02s).
        eta_tt = w_shaft / max(cp * (T_01 - T_02s), 1e-3)

        # --- η_ts: proper formula (ADAPT-022) -----------------------------
        # Total-to-static efficiency is the ratio of actual specific work
        # delivered to the *isentropic* work between the inlet stagnation
        # state and the EXIT STATIC pressure p_2:
        #
        #     η_ts = (h_t1 − h_t2)              w_shaft
        #            ─────────────── =  ────────────────────────────
        #            (h_t1 − h_s2,p2)    cp · (T_01 − T_s2_at_p2)
        #
        # where h_s2_at_p2 is the isentropic STATIC enthalpy at p_2. It is
        # NOT η_tt − 0.03. The gap between η_tt and η_ts is the residual
        # exit kinetic energy ½ V_2² that a free discharge cannot recover.
        #
        # We compute it by:
        #  1. isentropic expansion from inlet (P_01, T_01) to p_2,
        #     yielding T_s2_at_p2;
        #  2. h_s2_at_p2 = cp · T_s2_at_p2 (perfect gas).
        if p_out_static is not None:
            P_2_static = float(p_out_static.to("Pa").magnitude)
        else:
            # No BC: derive from the static state at exducer exit
            P_2_static = P_02 * (T_2 / T_02_actual) ** (gamma / (gamma - 1))
        pressure_ratio_ts = P_01 / max(P_2_static, 1e-3)
        T_s2_at_p2 = T_01 * (P_2_static / P_01) ** ((gamma - 1.0) / gamma)
        h_s2_at_p2 = cp * T_s2_at_p2
        # Isentropic work to exit STATIC pressure:
        w_isen_ts = cp * (T_01 - T_s2_at_p2)
        eta_ts = w_shaft / max(w_isen_ts, 1e-3)
        # Cross-check (sanity): the *kinetic* gap that distinguishes η_ts
        # from η_tt is ½ V_2² / w_isen_ts (this is the unrecoverable
        # residual that a downstream diffuser would convert to pressure).
        # We do not surface this as a field but it is the engineering
        # narrative behind the formula.
        w_actual = w_shaft

        # --- Polytropic (small-stage) efficiency --------------------------
        # For a turbine, η_p = (γ−1)/γ · ln(T_01/T_02_actual) / ln(P_01/P_02)
        # (Cumpsty, "Compressor Aerodynamics" §1.6; flipped sign for turbine).
        if P_02 > 0 and T_02_actual > 0 and P_01 != P_02:
            ratio_T = T_01 / T_02_actual
            ratio_P = P_01 / P_02
            if ratio_T > 0 and ratio_P > 1.0:
                eta_polytropic = (math.log(ratio_P)
                                  / max(math.log(ratio_T), 1e-9)
                                  * (gamma - 1.0) / gamma)
                eta_polytropic = float(eta_polytropic)
            else:
                eta_polytropic = float(eta_tt)
        else:
            eta_polytropic = float(eta_tt)
        eta_polytropic = max(0.0, min(eta_polytropic, 1.0))

        # --- Work / flow coefficients --------------------------------------
        # Λ_u ≡ Δh_0 / U_1²  (radial-turbine canonical loading)
        # φ   ≡ V_m2 / U_2   (flow coefficient at exducer)
        work_coefficient = w_shaft / max(U_1 * U_1, 1e-9)
        flow_coefficient = V_m2 / max(U_2, 1e-9)

        # --- Entropy at each station (h–s diagram) -------------------------
        # Reference: s=0 at (T_ref, P_ref) = inlet total state.
        # ds = cp ln(T/T_ref) − R ln(P/P_ref). Inlet total state: s = 0.
        # Use ABSOLUTE states (static T, static P) so the h–s diagram
        # shows the irreversible expansion path correctly.
        def _s(T_K: float, P_Pa: float) -> float:
            return cp * math.log(T_K / T_01) - R * math.log(P_Pa / P_01)

        # Station 1 static
        s_1 = _s(T_1, P_1)
        # Station 2 static (the real exducer-exit static state)
        s_2 = _s(T_2, P_2)
        # Inlet total
        s_01 = 0.0
        # Exit total
        s_02 = _s(T_02_actual, P_02)

        # Mach numbers
        M_1 = V_1 / max(a_1, 1e-9)
        M_2 = V_2 / max(a_2, 1e-9)

        port_state_inlet = PortState(
            T_static_K=float(T_1), T_total_K=float(T_01),
            p_static_Pa=float(P_1), p_total_Pa=float(P_01),
            h_static_J_per_kg=float(cp * T_1), h_total_J_per_kg=float(cp * T_01),
            s_J_per_kgK=float(s_1), M=float(M_1), rho_kg_per_m3=float(rho_1),
        )
        port_state_exit = PortState(
            T_static_K=float(T_2), T_total_K=float(T_02_actual),
            p_static_Pa=float(P_2), p_total_Pa=float(P_02),
            h_static_J_per_kg=float(cp * T_2),
            h_total_J_per_kg=float(cp * T_02_actual),
            s_J_per_kgK=float(s_2), M=float(M_2), rho_kg_per_m3=float(rho_2),
        )

        # Velocity triangles (degrees, from meridional — UI-friendly)
        def _from_meridional_deg(V_m: float, V_t: float) -> float:
            return math.degrees(math.atan2(abs(V_t), max(V_m, 1e-9)))

        v_tri_inlet = VTriangle(
            U=float(U_1),
            V_meridional=float(V_m1), V_theta=float(V_theta_1),
            W_meridional=float(V_m1), W_theta=float(W_theta_1),
            V=float(V_1), W=float(W_1),
            alpha_flow_deg=float(_from_meridional_deg(V_m1, V_theta_1)),
            beta_flow_deg=float(_from_meridional_deg(V_m1, W_theta_1)),
        )
        v_tri_exit = VTriangle(
            U=float(U_2),
            V_meridional=float(V_m2), V_theta=float(V_theta_2),
            W_meridional=float(V_m2), W_theta=float(W_theta_2),
            V=float(V_2), W=float(W_2),
            alpha_flow_deg=float(_from_meridional_deg(V_m2, V_theta_2)),
            beta_flow_deg=float(_from_meridional_deg(V_m2, W_theta_2)),
        )

        # Build per-iter convergence history (max of res_1, res_2 per iter).
        full_history = [
            {
                "iter": i,
                "residual": float(max(r1, r2)),
                "max_change": float(max(r1, r2)),
            }
            for i, (r1, r2) in enumerate(history)
        ]

        # --- Build outlet Port --------------------------------------------
        outlet_port = Port(
            pressure_total=Q(P_02, "Pa"),
            temperature_total=Q(T_02_actual, "K"),
            mass_flow=Q(m_dot, "kg/s"),
            composition=inlet.composition,
            rotational_speed=Q(omega, "rad/s"),
            swirl_ratio=0.0,
            velocity_meridional=Q(V_m2, "m/s"),
            radius_mean=Q(r_2_mean, "m"),
        )

        return RadialTurbineResult(
            outlet=outlet_port,
            eta_tt=float(eta_tt),
            eta_ts=float(eta_ts),
            eta_polytropic=float(eta_polytropic),
            power_W=Q(m_dot * w_actual, "W"),
            pressure_ratio_tt=float(pressure_ratio_tt),
            pressure_ratio_ts=float(pressure_ratio_ts),
            max_M_rel=float(max_M_rel),
            max_tip_speed=Q(U_1, "m/s"),
            U_1=Q(U_1, "m/s"),
            U_2=Q(U_2, "m/s"),
            V_1=Q(V_1, "m/s"),
            V_2=Q(V_2, "m/s"),
            W_1=Q(W_1, "m/s"),
            W_2=Q(W_2, "m/s"),
            work_coefficient=float(work_coefficient),
            flow_coefficient=float(flow_coefficient),
            h_s2_at_p2_J_per_kg=float(h_s2_at_p2),
            port_states={"inlet": port_state_inlet, "exit": port_state_exit},
            velocity_triangles={"inlet": v_tri_inlet, "exit": v_tri_exit},
            loss_breakdown=breakdown,
            convergence_history=full_history,
            convergence_info=dict(iterations=iters + 1, converged=converged,
                                  residual_history=history[-5:]),
            fluid_name=fluid.name,
        )
