"""Centrifugal compressor mean-line solver.

Implements the Aungier (2000) Ch. 6 design analysis with Wiesner (1967)
slip factor and Oh-Yoon-Chung (1997) recirculation loss. Solves a
one-dimensional steady flow through the impeller (LE → impeller exit)
including the velocity triangles, slip, and the canonical Aungier loss set.

The solver enforces SPEC_SHEET §13 refusal envelope: M_rel > 2.5 raises
`RegimeOutOfValidity`.

References (canonical):
- Aungier, R.H., 2000. *Centrifugal Compressors: A Strategy for Aerodynamic
  Design and Analysis*, ASME Press, Ch. 6.
- Wiesner, F.J., 1967. "A Review of Slip Factors for Centrifugal Impellers",
  Trans. ASME J. Eng. Power, 89(4), pp. 558–566.
- Eckardt, D., 1976. "Detailed Flow Investigations Within a High-Speed
  Centrifugal Compressor Impeller", ASME J. Fluids Engineering, 98(3),
  pp. 390–402.
- Dixon, S.L. & Hall, C.A., 7th ed. 2014. *Fluid Mechanics and
  Thermodynamics of Turbomachinery*, Butterworth-Heinemann, Ch. 7.
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
from cascade.meanline.loss_models import LossBreakdown, LossModel, SlipFactor
from cascade.meanline.loss_models_impl import WiesnerSlip
from cascade.meanline.radial_turbine import PortState, VTriangle
from cascade.units import Composition, Port, Q, Quantity


# =============================================================================
# Geometry
# =============================================================================


@dataclass(frozen=True)
class CentrifugalCompressorGeometry:
    """Geometric parameters of a centrifugal compressor impeller.

    Convention (per SPEC_SHEET §3.2):

    - `beta_2_metal_rad`: blade angle at impeller exit, measured **from the
      axial direction** in the canonical Cascade store. For impeller TE this
      is interpreted as "from meridional / radial direction".
      - Radial-bladed (Rotor O): blade points purely radially → π/2 from
        axial (since at impeller exit the meridional direction *is* radial,
        and the blade is aligned with it, this is 0 from meridional. But
        the **literature convention** is from-tangential where a radial
        blade is at 90° from tangential.
      - To remove ambiguity: in the literature, β₂' is from tangential and
        a back-swept blade has β₂' < 90°. The conversion is
        β₂'_from_tan = π/2 - β₂'_from_axial.
      For example: Eckardt Rotor A has 30° back-sweep → β₂'_from_tan = 60°
        = π/3 rad. In the canonical from-axial convention used here, that
        is π/2 - π/3 = π/6 rad.

    All linear dimensions are in metres.
    """

    inducer_hub_radius: float  # r₁_hub [m]
    inducer_tip_radius: float  # r₁_tip [m]
    impeller_outlet_radius: float  # r₂ [m]
    blade_height_outlet: float  # b₂ [m]
    blade_count: int  # Z, includes splitters in effective count
    beta_2_metal_rad: float  # blade angle at TE, *from axial* per SPEC §3.2
    tip_clearance: float  # ε [m]
    # Inducer-tip blade metal angle β₁'_blade measured *from axial*
    # (SPEC §3.2 canonical convention). The default `None` means
    # "auto-derive at design RPM" (the historical zero-incidence
    # assumption); explicit values introduce a finite design incidence
    # (ADAPT-009). For a typical inducer the blade is canted
    # 50–60° from axial at the tip (so β₁_from_axial ≈ π/3); the flow
    # angle β₁_flow_from_axial depends on V_m₁ / U₁_tip and at design is
    # slightly less than the blade angle (positive design incidence ~ 2-4°).
    inducer_tip_blade_metal_rad: Optional[float] = None
    chord_meridional: Optional[float] = None  # if None, defaults to r₂ - r₁_mean
    disc_gap_ratio: float = 0.02  # G/r for disc-friction
    # Axial seal-clearance ratio for the Aungier (2000) eq. 6.66 leakage
    # model (ADAPT-007). This is the **axial gap divided by the impeller
    # exit radius**, ε_axial / r₂. Aungier §6.6 commentary lists
    # 0.0005–0.002 as typical for well-designed shrouded impellers and
    # 0.001–0.003 for unshrouded; the default 0.0001 is a tight modern
    # research-rig value (e.g., Eckardt 1976 measured ε≈0.3 mm / r₂≈0.2 m
    # ≈ 0.0015 absolute, but the seal-specific clearance is smaller).
    # Set to 0 to disable Aungier's seal-flow leakage and fall back to
    # the simpler tip-clearance/blade-height ratio.
    epsilon_clearance: float = 0.0001
    # Blockage at impeller exit (Aungier's recommendation ~0.05 for shrouded,
    # ~0.10–0.15 for unshrouded). The user can override per design.
    blockage_outlet: float = 0.08

    def __post_init__(self) -> None:
        if self.inducer_hub_radius < 0:
            raise InvalidGeometry("inducer_hub_radius must be ≥ 0")
        if self.inducer_tip_radius <= self.inducer_hub_radius:
            raise InvalidGeometry("inducer_tip_radius must exceed hub")
        if self.impeller_outlet_radius <= self.inducer_tip_radius:
            raise InvalidGeometry(
                "impeller_outlet_radius must exceed inducer tip "
                f"({self.impeller_outlet_radius} vs {self.inducer_tip_radius})")
        if self.blade_height_outlet <= 0:
            raise InvalidGeometry("blade_height_outlet must be > 0")
        if self.blade_count < 3:
            raise InvalidGeometry("blade_count must be ≥ 3")
        if self.tip_clearance < 0:
            raise InvalidGeometry("tip_clearance must be ≥ 0")
        if not (0.0 <= self.blockage_outlet < 1.0):
            raise InvalidGeometry("blockage_outlet must be in [0, 1)")

    @property
    def inducer_mean_radius(self) -> float:
        # RMS mean as in Aungier 2000 §5.3
        return math.sqrt(0.5 * (self.inducer_hub_radius ** 2
                                + self.inducer_tip_radius ** 2))


# =============================================================================
# Result
# =============================================================================


@dataclass(frozen=True)
class CentrifugalCompressorResult:
    """The full mean-line result for one centrifugal-compressor design-point
    solve.

    `eta_ts` is computed properly (ADAPT-022): the *numerator* is the
    isentropic work from inlet total to exit STATIC pressure; we never use
    an η_tt − 0.03 shortcut. The kinetic-energy gap is exactly the residual
    ½ V₂² leaving the impeller, which cannot be recovered without a
    downstream diffuser.
    """

    outlet: Port  # impeller-exit total state (Port)
    eta_tt: float  # impeller-to-impeller total-to-total efficiency
    eta_ts: float  # total-to-static (proper formula — ADAPT-022)
    eta_polytropic: float  # polytropic (small-stage) efficiency
    pressure_ratio_tt: float  # P_02 / P_01
    pressure_ratio_ts: float  # P_2_static / P_01
    power_W: Quantity  # impeller work-rate input
    max_M_rel: float
    max_tip_speed: Quantity  # U_2 (m/s)
    U_1_tip: Quantity
    U_2: Quantity
    V_1: Quantity
    V_2: Quantity
    W_1_tip: Quantity
    W_2: Quantity
    slip_factor: float
    work_coefficient: float  # Λ_u ≡ w_shaft / U_2²
    flow_coefficient: float  # φ ≡ V_m1 / U_2 (inlet flow coefficient)
    h_s2_at_p2_J_per_kg: float  # isentropic static enthalpy at exit p (ADAPT-022)
    port_states: dict  # {"inlet": PortState, "exit": PortState}
    velocity_triangles: dict  # {"inlet": VTriangle, "exit": VTriangle}
    loss_breakdown: LossBreakdown
    convergence_history: list
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
class CentrifugalCompressorMeanline:
    """1-D mean-line forward solver for a centrifugal compressor impeller.

    Solve procedure:

    1. Inducer LE (station 1):
       - V_θ₁ = 0 (axial-inlet impeller, no IGV).
       - V_₁ = V_m₁; compute from continuity at the inducer annulus.
       - U₁_tip = ω r₁_tip; W₁_tip from V_m₁ and U₁_tip.
    2. Impeller TE (station 2):
       - U₂ = ω r₂.
       - σ = SlipFactor(blade_count, β₂'_from_tan).
       - V_θ₂ = σ U₂ - V_m₂ · cot(β₂'_from_tan)  (back-swept form;
         Dixon §7.2)
       - V_m₂ from continuity at the exit blade annulus.
       - Continuity iteration until convergence.
    3. Work: w = U₂ · V_θ₂ - U₁ · V_θ₁ = U₂ · V_θ₂ (no inlet swirl).
    4. Losses (Aungier 2000 Ch. 6): incidence, blade-loading, profile,
       mixing, tip-clearance, disc-friction, recirculation, leakage.
    5. Efficiency: η_tt = w_isen / w_actual where w_actual = w + Σ Δh_loss.

    The convention here matches Aungier 2000 §4.4:
    losses *add* to the actual impeller work because the impeller must do
    extra work to compensate for entropy generation.
    """

    max_iterations: int = 200
    tol_relative: float = 1e-6
    relaxation: float = 0.5
    slip_model: Optional[SlipFactor] = None  # default: Wiesner

    def __post_init__(self) -> None:
        if self.slip_model is None:
            object.__setattr__(self, "slip_model", WiesnerSlip())

    def solve(self, inlet: Port, rpm: Quantity,
              geometry: CentrifugalCompressorGeometry,
              loss_model: LossModel,
              fluid: PerfectGas = AIR) -> CentrifugalCompressorResult:
        """Run a forward design-point solve.

        Args:
            inlet: inducer-inlet total state (Port). The rotational_speed
                field is overridden by `rpm`.
            rpm: shaft speed.
            geometry: impeller geometry.
            loss_model: the LossModel (e.g., AungierCentrifugal()).
            fluid: PerfectGas instance (default AIR).

        Returns:
            CentrifugalCompressorResult.

        Raises:
            RegimeOutOfValidity: per SPEC_SHEET §13.
            MeanlineConvergenceError: if continuity does not converge.
        """
        # Inputs
        P_01 = float(inlet.pressure_total.to("Pa").magnitude)
        T_01 = float(inlet.temperature_total.to("K").magnitude)
        m_dot = float(inlet.mass_flow.to("kg/s").magnitude)
        omega = float(rpm.to("rad/s").magnitude)

        cp = fluid.cp_J_per_kgK
        gamma = fluid.gamma
        R = fluid.R_specific
        h_01 = cp * T_01

        # --- Station 1: inducer LE -----------------------------------------
        r_1_hub = geometry.inducer_hub_radius
        r_1_tip = geometry.inducer_tip_radius
        r_1_mean = geometry.inducer_mean_radius
        A_1 = math.pi * (r_1_tip ** 2 - r_1_hub ** 2)
        U_1_tip = omega * r_1_tip
        U_1_mean = omega * r_1_mean

        # --- Station 2: impeller TE ----------------------------------------
        r_2 = geometry.impeller_outlet_radius
        b_2 = geometry.blade_height_outlet
        A_2 = 2.0 * math.pi * r_2 * b_2 * (1.0 - geometry.blockage_outlet)
        U_2 = omega * r_2

        # Convert blade angle: SPEC convention is from-axial; the slip
        # formula uses from-tangential.
        beta_2_blade_from_axial = geometry.beta_2_metal_rad
        beta_2_blade_from_tan = math.pi / 2 - beta_2_blade_from_axial

        # Slip factor (Wiesner default)
        assert self.slip_model is not None
        sigma = self.slip_model.slip_factor(
            blade_count=geometry.blade_count,
            beta_2_from_tangential_rad=beta_2_blade_from_tan,
            radius_ratio_inducer_to_exit=r_1_mean / r_2)

        # --- Initial guesses -----------------------------------------------
        rho_01 = P_01 / (R * T_01)
        V_m1 = m_dot / max(rho_01 * A_1, 1e-9)
        # Estimate V_m2 from continuity using a guessed exit density.
        # Initial guess: exit density a factor (P2/P1)^(1/γ) larger.
        rho_2_guess = rho_01 * 1.5
        V_m2 = m_dot / max(rho_2_guess * A_2, 1e-9)

        converged = False
        iters = 0
        history = []

        # The fixed-point iteration ----------------------------------------
        for iters in range(self.max_iterations):
            # --- Station 1 inducer -------------------------------------
            V_1 = V_m1  # no inlet swirl
            # Relative components at inducer tip (highest W)
            W_theta_1_tip = -U_1_tip  # V_θ₁ = 0
            W_1_tip = math.sqrt(V_m1 * V_m1 + U_1_tip * U_1_tip)
            beta_1_flow_tip_from_tan = math.atan2(V_m1, U_1_tip)
            # Blade metal angle at inducer tip (ADAPT-009): separated from
            # the flow angle so design-point incidence is a finite (small)
            # quantity, NOT identically zero. Two paths:
            # (a) user explicitly supplied `inducer_tip_blade_metal_rad`
            #     → convert that from-axial value to from-tangential.
            # (b) auto-derived: take a small positive design incidence
            #     of `i_design = 3°` such that
            #     β₁_blade_from_tan = β₁_flow_from_tan - i_design.
            #     This is a typical real-world centrifugal design
            #     (Whitfield & Baines 1990 §6.2; Aungier 2000 §6.4) —
            #     a slightly off-flow blade angle reduces sensitivity to
            #     mass-flow upsets at design and yields measurable but
            #     small incidence loss at the design point.
            if geometry.inducer_tip_blade_metal_rad is not None:
                # Convert SPEC §3.2 from-axial → from-tangential
                beta_1_blade_from_tan = (math.pi / 2.0
                                         - geometry.inducer_tip_blade_metal_rad)
            else:
                # Default 3° design incidence (i = β_blade − β_flow > 0
                # corresponds to a blade more tangential than the flow,
                # i.e. flow striking the suction surface — the typical
                # positive-incidence design convention).
                i_design_rad = math.radians(3.0)
                beta_1_blade_from_tan = beta_1_flow_tip_from_tan - i_design_rad

            # Static state at station 1
            h_1 = h_01 - 0.5 * V_1 * V_1
            T_1 = h_1 / cp
            if T_1 <= 0:
                raise RegimeOutOfValidity(
                    f"Station 1 static T <= 0 (T_1={T_1:.2f})",
                    regime_variable="T_1", value=T_1, limit=0.0)
            P_1 = P_01 * (T_1 / T_01) ** (gamma / (gamma - 1))
            rho_1 = P_1 / (R * T_1)
            V_m1_new = m_dot / max(rho_1 * A_1, 1e-9)

            # --- Station 2 impeller exit -------------------------------
            # Back-swept slip-factor velocity-triangle (Dixon §7.2):
            #   V_θ₂ = σ U₂ - V_m₂ · cot(β₂'_from_tan)
            # For a radial-vaned (β₂'_from_tan = π/2) impeller, cot = 0
            # and V_θ₂ = σ U₂.
            cot_beta2 = math.cos(beta_2_blade_from_tan) \
                / max(math.sin(beta_2_blade_from_tan), 1e-9)
            V_theta_2 = sigma * U_2 - V_m2 * cot_beta2
            V_theta_2 = max(0.0, V_theta_2)  # physical floor
            V_2 = math.sqrt(V_m2 * V_m2 + V_theta_2 * V_theta_2)
            W_theta_2 = V_theta_2 - U_2
            W_2 = math.sqrt(V_m2 * V_m2 + W_theta_2 * W_theta_2)
            beta_2_flow_from_tan = math.atan2(V_m2, -W_theta_2) \
                if W_theta_2 < 0 else math.pi / 2
            alpha_2_from_tan = math.atan2(V_m2, V_theta_2) \
                if V_theta_2 > 1e-6 else math.pi / 2

            # Euler work (this is the ideal "delivered" work, no losses)
            w_euler = U_2 * V_theta_2
            T_02_ideal = T_01 + w_euler / cp

            # Static state at station 2 (impeller exit)
            h_02_ideal = h_01 + w_euler
            h_2 = h_02_ideal - 0.5 * V_2 * V_2
            T_2 = h_2 / cp
            if T_2 <= 0:
                raise RegimeOutOfValidity(
                    f"Station 2 static T <= 0 (T_2={T_2:.2f})",
                    regime_variable="T_2", value=T_2, limit=0.0)
            # Estimate P_2 from isentropic compression (will be refined by
            # losses post-iter)
            T_02_at_isen = T_02_ideal  # using ideal for now
            # Use isentropic exit pressure as starting guess:
            P_02_isen = P_01 * (T_02_ideal / T_01) ** (gamma / (gamma - 1.0))
            # Static at impeller exit:
            P_2 = P_02_isen * (T_2 / T_02_ideal) ** (gamma / (gamma - 1.0))
            rho_2 = P_2 / (R * T_2)
            V_m2_new = m_dot / max(rho_2 * A_2, 1e-9)

            # Apply under-relaxation
            r = self.relaxation
            V_m1_next = (1 - r) * V_m1 + r * V_m1_new
            V_m2_next = (1 - r) * V_m2 + r * V_m2_new
            res_1 = abs(V_m1_next - V_m1) / max(abs(V_m1), 1e-9)
            res_2 = abs(V_m2_next - V_m2) / max(abs(V_m2), 1e-9)
            history.append((res_1, res_2))
            V_m1, V_m2 = V_m1_next, V_m2_next
            if max(res_1, res_2) < self.tol_relative:
                converged = True
                break

        if not converged:
            raise MeanlineConvergenceError(
                f"Centrifugal continuity did not converge in "
                f"{self.max_iterations} iters; last residuals = "
                f"({res_1:.3e}, {res_2:.3e})")

        # --- Post-converged evaluation ------------------------------------
        # Re-derive everything once with final V_m's
        V_1 = V_m1
        W_1_tip = math.sqrt(V_m1 * V_m1 + U_1_tip * U_1_tip)
        beta_1_flow_tip_from_tan = math.atan2(V_m1, U_1_tip)
        # Blade metal angle (ADAPT-009): see in-iteration commentary.
        if geometry.inducer_tip_blade_metal_rad is not None:
            beta_1_blade_from_tan = (math.pi / 2.0
                                     - geometry.inducer_tip_blade_metal_rad)
        else:
            i_design_rad = math.radians(3.0)
            beta_1_blade_from_tan = beta_1_flow_tip_from_tan - i_design_rad
        h_1 = h_01 - 0.5 * V_1 * V_1
        T_1 = h_1 / cp
        P_1 = P_01 * (T_1 / T_01) ** (gamma / (gamma - 1))
        rho_1 = P_1 / (R * T_1)
        a_1 = fluid.speed_of_sound(T_1)

        cot_beta2 = math.cos(beta_2_blade_from_tan) \
            / max(math.sin(beta_2_blade_from_tan), 1e-9)
        V_theta_2 = max(0.0, sigma * U_2 - V_m2 * cot_beta2)
        V_2 = math.sqrt(V_m2 * V_m2 + V_theta_2 * V_theta_2)
        W_theta_2 = V_theta_2 - U_2
        W_2 = math.sqrt(V_m2 * V_m2 + W_theta_2 * W_theta_2)
        alpha_2_from_tan = math.atan2(V_m2, max(V_theta_2, 1e-9))
        beta_2_flow_from_tan = math.atan2(V_m2, max(-W_theta_2, 1e-9))

        w_euler = U_2 * V_theta_2
        T_02_ideal = T_01 + w_euler / cp
        h_02_ideal = h_01 + w_euler
        h_2 = h_02_ideal - 0.5 * V_2 * V_2
        T_2 = h_2 / cp
        a_2 = fluid.speed_of_sound(T_2)

        # Diffusion factor (Lieblein 1953 - simplified)
        if W_1_tip > 1e-6:
            DF = 1.0 - W_2 / W_1_tip \
                + 0.5 * V_theta_2 / (max(W_1_tip, 1e-6)
                                     * max(geometry.blade_count, 1))
        else:
            DF = 0.4
        DF = max(0.0, min(DF, 0.7))

        # Mach checks
        M_W1 = W_1_tip / max(a_1, 1e-9)
        M_W2 = W_2 / max(a_2, 1e-9)
        max_M_rel = max(M_W1, M_W2)

        envelope = loss_model.validity_envelope
        if envelope.M_rel_max is not None and max_M_rel > envelope.M_rel_max:
            raise RegimeOutOfValidity(
                f"max relative Mach {max_M_rel:.2f} exceeds the loss-model "
                f"validity envelope ({envelope.M_rel_max:.2f}).",
                regime_variable="M_rel", value=max_M_rel,
                limit=envelope.M_rel_max)

        # Reynolds for disc friction
        nu = fluid.dynamic_viscosity / max(rho_2, 1e-3)
        Re_omega = omega * r_2 * r_2 / max(nu, 1e-9)
        chord_m = geometry.chord_meridional or (r_2 - r_1_mean)

        loss_ctx = dict(
            U_2=U_2, W_1_tip=W_1_tip, W_2=W_2, V_2=V_2,
            beta_1_flow_rad=beta_1_flow_tip_from_tan,
            beta_1_blade_rad=beta_1_blade_from_tan,
            beta_2_blade_rad=beta_2_blade_from_tan,
            alpha_2_rad=alpha_2_from_tan,
            blade_count=geometry.blade_count,
            r_1_tip=r_1_tip, r_1_hub=r_1_hub, r_2=r_2, b_2=b_2,
            tip_clearance=geometry.tip_clearance,
            epsilon_clearance=geometry.epsilon_clearance,
            chord_meridional=chord_m,
            mass_flow=m_dot, rho_2=rho_2, sigma=sigma, DF=DF,
            disc_gap_ratio=geometry.disc_gap_ratio,
            Re_omega=Re_omega,
            # Inlet thermodynamic state — needed by Aungier eq. 6.66
            # leakage (U_leak from Δp across the seal).
            rho_1=rho_1, P_1=P_1, P_2=P_2,
        )
        breakdown = loss_model.loss_coefficient(**loss_ctx)

        # Aungier convention (Aungier 2000 eq. 6.1–6.5):
        # - Internal losses (incidence, blade-loading, profile, mixing,
        #   tip-clearance, trailing-edge): generate entropy in the main flow
        #   *without* adding to shaft work. They are already part of
        #   w_Euler — they convert some Euler work to entropy.
        # - Parasitic losses (disc-friction, recirculation, leakage):
        #   *outside* the main blade-row flow path. They add to shaft work
        #   (the impeller does extra work to drive the windage / leakage)
        #   and also heat the gas (parasitic dissipation re-enters the gas).
        # So:
        #   w_shaft = w_Euler + Σ Δh_parasitic
        #   T₀₂ = T₀₁ + w_shaft/c_p  (full shaft work raises T₀₂)
        #   Δs (impeller) = Σ Δh_internal_loss / T_avg
        #   ln(P₀₂/P₀₁) = (c_p/R)·ln(T₀₂/T₀₁) - Δs/R
        #   η_tt = (T₀₂s − T₀₁) / (T₀₂ − T₀₁)
        ke_U2 = 0.5 * U_2 * U_2
        internal_loss_zeta = (breakdown.incidence + breakdown.blade_loading
                              + breakdown.profile + breakdown.mixing
                              + breakdown.tip_clearance
                              + breakdown.trailing_edge)
        parasitic_loss_zeta = (breakdown.disc_friction
                               + breakdown.recirculation
                               + breakdown.leakage)
        dh_loss_internal = internal_loss_zeta * ke_U2
        dh_loss_parasitic = parasitic_loss_zeta * ke_U2

        # Shaft work and outlet total enthalpy
        w_shaft = w_euler + dh_loss_parasitic
        T_02_actual = T_01 + w_shaft / cp

        # Entropy rise from internal losses
        T_avg = 0.5 * (T_01 + T_02_actual)
        ds = dh_loss_internal / max(T_avg, 1e-3)
        # P_02 from entropy bookkeeping
        ln_pi = (cp * math.log(T_02_actual / T_01) - ds) / R
        P_02 = P_01 * math.exp(ln_pi)
        pressure_ratio_tt = P_02 / P_01

        # Isentropic outlet temperature for the same P_02:
        T_02s = T_01 * (P_02 / P_01) ** ((gamma - 1.0) / gamma)
        w_isen = cp * (T_02s - T_01)
        # w_actual is the shaft work (parasitics included); η_tt definition
        # uses (T_02s − T_01) / (T_02 − T_01) so it normalizes by total
        # temperature rise including parasitics.
        w_actual = w_shaft
        eta_tt = w_isen / max(w_actual, 1e-3)

        # --- Total-to-static η — proper formula (ADAPT-022) ----------------
        # For a compressor, η_ts compares the actual work to the isentropic
        # work that would carry the gas from inlet total state to the EXIT
        # STATIC pressure p_2. The kinetic energy ½ V_2² stays as flow
        # kinetic energy and is "wasted" if there is no diffuser.
        P_2_static = P_02 * (T_2 / T_02_actual) ** (gamma / (gamma - 1.0))
        pressure_ratio_ts = P_2_static / P_01
        T_s2_at_p2 = T_01 * (P_2_static / P_01) ** ((gamma - 1.0) / gamma)
        h_s2_at_p2 = cp * T_s2_at_p2
        w_isen_ts = cp * (T_s2_at_p2 - T_01)
        eta_ts = w_isen_ts / max(w_actual, 1e-3)

        # --- Polytropic efficiency ----------------------------------------
        # For a compressor: η_p = (γ−1)/γ · ln(P_02/P_01) / ln(T_02/T_01)
        # (Cumpsty §1.6). Falls back to η_tt for degenerate cases.
        if P_02 > P_01 and T_02_actual > T_01:
            eta_polytropic = ((gamma - 1.0) / gamma
                              * math.log(P_02 / P_01)
                              / max(math.log(T_02_actual / T_01), 1e-9))
            eta_polytropic = float(eta_polytropic)
        else:
            eta_polytropic = float(eta_tt)
        eta_polytropic = max(0.0, min(eta_polytropic, 1.0))

        # --- Work / flow coefficients --------------------------------------
        work_coefficient = w_actual / max(U_2 * U_2, 1e-9)
        flow_coefficient = V_m1 / max(U_2, 1e-9)

        # --- Entropy at each station (h-s diagram) -------------------------
        def _s(T_K: float, P_Pa: float) -> float:
            return cp * math.log(T_K / T_01) - R * math.log(P_Pa / P_01)
        s_1 = _s(T_1, P_1)
        s_2 = _s(T_2, P_2)

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

        def _from_meridional_deg(V_m: float, V_t: float) -> float:
            return math.degrees(math.atan2(abs(V_t), max(V_m, 1e-9)))

        # Inlet triangle is at the inducer tip (most demanding for Mach)
        v_tri_inlet = VTriangle(
            U=float(U_1_tip),
            V_meridional=float(V_m1), V_theta=0.0,
            W_meridional=float(V_m1), W_theta=float(-U_1_tip),
            V=float(V_1), W=float(W_1_tip),
            alpha_flow_deg=0.0,  # zero swirl at the inducer
            beta_flow_deg=float(_from_meridional_deg(V_m1, -U_1_tip)),
        )
        v_tri_exit = VTriangle(
            U=float(U_2),
            V_meridional=float(V_m2), V_theta=float(V_theta_2),
            W_meridional=float(V_m2), W_theta=float(W_theta_2),
            V=float(V_2), W=float(W_2),
            alpha_flow_deg=float(_from_meridional_deg(V_m2, V_theta_2)),
            beta_flow_deg=float(_from_meridional_deg(V_m2, W_theta_2)),
        )

        full_history = [
            {
                "iter": i,
                "residual": float(max(r1, r2)),
                "max_change": float(max(r1, r2)),
            }
            for i, (r1, r2) in enumerate(history)
        ]

        outlet_port = Port(
            pressure_total=Q(P_02, "Pa"),
            temperature_total=Q(T_02_actual, "K"),
            mass_flow=Q(m_dot, "kg/s"),
            composition=inlet.composition,
            rotational_speed=Q(omega, "rad/s"),
            swirl_ratio=float(V_theta_2 / max(U_2, 1e-9)),
            velocity_meridional=Q(V_m2, "m/s"),
            radius_mean=Q(r_2, "m"),
        )

        return CentrifugalCompressorResult(
            outlet=outlet_port,
            eta_tt=float(eta_tt),
            eta_ts=float(eta_ts),
            eta_polytropic=float(eta_polytropic),
            pressure_ratio_tt=float(pressure_ratio_tt),
            pressure_ratio_ts=float(pressure_ratio_ts),
            power_W=Q(m_dot * w_actual, "W"),
            max_M_rel=float(max_M_rel),
            max_tip_speed=Q(U_2, "m/s"),
            U_1_tip=Q(U_1_tip, "m/s"),
            U_2=Q(U_2, "m/s"),
            V_1=Q(V_1, "m/s"),
            V_2=Q(V_2, "m/s"),
            W_1_tip=Q(W_1_tip, "m/s"),
            W_2=Q(W_2, "m/s"),
            slip_factor=float(sigma),
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
