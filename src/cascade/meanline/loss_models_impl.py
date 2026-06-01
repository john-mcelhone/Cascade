"""Concrete loss-model implementations.

Implements the canonical correlations cited in `radial_meanline.md` §4 and
declared in SPEC_SHEET §7. Each class declares its citation, default scale
factors, and validity envelope.

References (canonical):
- Whitfield, A. & Baines, N.C., 1990. *Design of Radial Turbomachines*,
  Longman, Ch. 6 — radial turbine loss models.
- Aungier, R.H., 2000. *Centrifugal Compressors: A Strategy for Aerodynamic
  Design and Analysis*, ASME Press, Ch. 6 — centrifugal compressor loss models.
- Stanitz, J.D., 1952. "Some Theoretical Aerodynamic Investigations of
  Impellers", Trans. ASME, 74, pp. 473–497.
- Wiesner, F.J., 1967. "A Review of Slip Factors for Centrifugal Impellers",
  Trans. ASME J. Eng. Power, 89(4), pp. 558–566.
- Stodola, A., 1924. *Dampf- und Gasturbinen*, Springer, Berlin.
- Glassman, A.J., 1976. *Computer Program for Design Analysis of Radial-Inflow
  Turbines*, NASA TN D-8164.
- Daily, J.W., Nece, R.E., 1960. "Chamber Dimension Effects on Induced Flow
  and Frictional Resistance of Enclosed Rotating Disks", Trans. ASME J. Basic
  Engineering, 82(1), pp. 217–230.
- Oh, H.W., Yoon, E.S., Chung, M.K., 1997. "An optimum set of loss models
  for performance prediction of centrifugal compressors", Proc. IMechE Part A,
  211(4), pp. 331–338.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from cascade.meanline.loss_models import LossBreakdown, ValidityEnvelope


# =============================================================================
# Daily-Nece (1960) disc-friction regime selector  (ADAPT-010)
# =============================================================================
#
# Daily, J.W. & Nece, R.E., 1960, "Chamber Dimension Effects on Induced Flow
# and Frictional Resistance of Enclosed Rotating Disks", Trans. ASME J. Basic
# Engineering, 82(1), pp. 217–230.
#
# Daily-Nece classified the rotating-disc flow into FOUR regimes keyed on
# the rotational Reynolds Re = ω·R²/ν AND the gap-to-radius ratio s/R:
#
#   Regime I:   laminar, merged boundary layers (small gap, low Re)
#   Regime II:  laminar, separate boundary layers (large gap, low Re)
#   Regime III: turbulent, merged boundary layers (small gap, high Re)
#   Regime IV:  turbulent, separate boundary layers (large gap, high Re)
#
# Boundaries (Daily-Nece 1960 Fig. 2 / Table 1; approximations from
# the original figure are widely cited e.g. Owen & Rogers 1989 §2.2 and
# Aungier 2000 §6.5):
#   I → II : Re ≈ 1.04e4 · (s/R)^(-1/2)   [laminar regime boundary]
#   I → III: Re ≈ 1.58e5 · (s/R)^(-1/6)   [merged-flow laminar→turbulent]
#   II → IV: Re ≈ 1.58e4 · (s/R)^(-9/8)   [separated-flow laminar→turbulent]
#   III → IV: at high Re, large s/R → IV; small s/R → III
#
# This module provides `daily_nece_regime(Re, s_over_R)` returning an enum
# and `daily_nece_moment_coefficient(Re, s_over_R)` returning C_M.


from enum import IntEnum


class DailyNeceRegime(IntEnum):
    """Daily-Nece (1960) disc-friction flow regimes."""
    I = 1   # laminar merged
    II = 2  # laminar separate
    III = 3  # turbulent merged
    IV = 4  # turbulent separate


def daily_nece_regime(Re: float, s_over_R: float) -> DailyNeceRegime:
    """Select the Daily-Nece (1960) regime for given Re and gap-ratio.

    Args:
        Re: rotational Reynolds = ω·R²/ν, dimensionless.
        s_over_R: axial gap to disc-radius ratio s/R, dimensionless.

    Returns:
        DailyNeceRegime — one of I, II, III, IV.

    Citation: Daily, J.W. & Nece, R.E., 1960, "Chamber Dimension Effects on
    Induced Flow and Frictional Resistance of Enclosed Rotating Disks",
    Trans. ASME J. Basic Engineering, 82(1), pp. 217–230, Fig. 2 /
    Table 1.

    Implementation note: the original Daily-Nece Fig. 2 lacks closed-form
    boundary fits; the widely-used approximate boundaries from Owen &
    Rogers 1989 §2.2 are adopted here. The boundary curves intersect at
    s/R ≈ 0.013 (the "merged ↔ separate" pivot point).
    """
    if Re <= 0 or s_over_R <= 0:
        raise ValueError(f"daily_nece_regime: Re={Re} and s/R={s_over_R} "
                         "must both be positive")
    # Laminar–turbulent transition
    Re_LT_merged = 1.58e5 * s_over_R ** (-1.0 / 6.0)
    Re_LT_separate = 1.58e4 * s_over_R ** (-9.0 / 8.0)
    # Merged–separate boundary (within each viscous regime)
    Re_MS = 1.04e4 * s_over_R ** (-0.5)

    is_laminar = Re < Re_LT_merged and Re < Re_LT_separate
    is_merged = Re < Re_MS

    if is_laminar and is_merged:
        return DailyNeceRegime.I
    if is_laminar and not is_merged:
        return DailyNeceRegime.II
    if (not is_laminar) and is_merged:
        return DailyNeceRegime.III
    return DailyNeceRegime.IV


def daily_nece_moment_coefficient(Re: float, s_over_R: float) -> float:
    """Compute the Daily-Nece (1960) torque coefficient C_M.

    Args:
        Re: ω·R²/ν, dimensionless.
        s_over_R: axial gap to disc-radius ratio, dimensionless.

    Returns:
        C_M — torque coefficient. Torque = ½ C_M ρ ω² R⁵; power = ½ C_M ρ ω³ R⁵.

    The four correlations (Daily-Nece 1960 Table 1 / eq. 17–20):
        Regime I   (laminar merged):    C_M = 2π / (Re · s/R)
        Regime II  (laminar separate):  C_M = 3.7 · (s/R)^(1/10) · Re^(-1/2)
        Regime III (turbulent merged):  C_M = 0.080 · Re^(-1/6) · (s/R)^(1/6)  ⁠— mid-Re fit
        Regime IV  (turbulent separate):C_M = 0.0102 · (s/R)^(1/10) · Re^(-1/5)

    Citation: Daily-Nece 1960 J. Basic Eng. 82(1):217, Table 1.
    """
    regime = daily_nece_regime(Re, s_over_R)
    if regime is DailyNeceRegime.I:
        # C_M = 2π / (Re · s/R)
        return 2.0 * math.pi / (Re * s_over_R)
    if regime is DailyNeceRegime.II:
        return 3.7 * (s_over_R ** 0.1) * (Re ** -0.5)
    if regime is DailyNeceRegime.III:
        return 0.080 * (Re ** (-1.0 / 6.0)) * (s_over_R ** (1.0 / 6.0))
    # Regime IV (turbulent separate boundary layers)
    return 0.0102 * (s_over_R ** 0.1) * (Re ** -0.2)


# =============================================================================
# Slip factors
# =============================================================================
#
# SPEC_SHEET §13 / §15 — low-blade-count validity edge:
#   §13: "Slip factor at Z < 3 (extrapolated; warning only)"
#   §15: "Slip factor at Z = 1 or Z = 2 (clip with warning; don't extrapolate)"
#
# Below Z = 3 every published slip closure (Stanitz, Wiesner, Stodola) leaves
# its fitted range and degenerates: for a radial-vaned blade (β₂' = 90°) the
# raw formulas give σ ≤ 0 at Z = 1–2 (e.g. Stodola σ(Z=1) = 1 − π = −2.14,
# Stanitz σ(Z=1) = 1 − 0.63π = −0.98, Wiesner σ(Z=1) = 0). A bare
# max(0, σ) then SILENTLY returns the degenerate σ ≈ 0 — i.e. an impeller
# that does essentially zero Euler work, which is non-physical and exactly
# the unsafe extrapolation §13/§15 forbid.
#
# The safe behaviour mandated by the SPEC is: do NOT extrapolate the
# correlation below its envelope; instead evaluate it at the validity floor
# (Z_min = 3, the smallest blade count for which the correlations are
# documented to be physical) and emit a `warnings.warn` so the caller knows
# the result was clipped rather than computed at the requested Z. This yields
# a finite, physical σ (e.g. Wiesner σ(Z=3, β'=90°) ≈ 0.537) instead of a
# degenerate σ ≈ 0.

SLIP_BLADE_COUNT_MIN: int = 3  # SPEC §13/§15 documented validity floor for Z


def _clip_blade_count_with_warning(blade_count: int, model_name: str) -> int:
    """Clip an out-of-envelope blade count to the slip-factor validity floor.

    Per SPEC_SHEET §13 ("Slip factor at Z < 3 (extrapolated; warning only)")
    and §15 ("Slip factor at Z = 1 or Z = 2 (clip with warning; don't
    extrapolate)"), blade counts below :data:`SLIP_BLADE_COUNT_MIN` are
    outside the fitted range of every published slip closure. Rather than
    silently extrapolating to a degenerate σ ≈ 0, we clip Z to the floor and
    emit a :class:`RuntimeWarning`.

    Args:
        blade_count: requested number of blades Z (must be ≥ 1; the geometry
            dataclasses already reject Z < 1 / Z < 3 upstream, but the slip
            closures are also called directly).
        model_name: slip-model name, for an informative warning message.

    Returns:
        The blade count to use in the correlation: ``blade_count`` if it is
        ≥ the floor, otherwise :data:`SLIP_BLADE_COUNT_MIN`.
    """
    if blade_count >= SLIP_BLADE_COUNT_MIN:
        return blade_count
    warnings.warn(
        f"{model_name}: blade_count Z={blade_count} is below the slip-factor "
        f"validity floor Z={SLIP_BLADE_COUNT_MIN} (SPEC_SHEET §13/§15). The "
        f"correlation is not valid for Z < {SLIP_BLADE_COUNT_MIN}; clipping "
        f"to Z={SLIP_BLADE_COUNT_MIN} to return a physical slip factor "
        f"instead of extrapolating to a degenerate value. Treat the result "
        f"as out-of-envelope.",
        category=RuntimeWarning,
        stacklevel=3,
    )
    return SLIP_BLADE_COUNT_MIN


@dataclass(frozen=True)
class StanitzSlip:
    """Stanitz (1952) slip factor: :math:`\\sigma = 1 - 0.63\\pi / Z`.

    Independent of blade angle. Best for radial-vaned (β₂' = 90° from
    tangential) impellers. Per Stanitz 1952 Trans. ASME.

    As Z → ∞ the slip approaches 1 (ideal). At Z = 12, σ = 0.835.

    Citation: Stanitz, J.D., 1952, "Some Theoretical Aerodynamic
    Investigations of Impellers in Radial- and Mixed-Flow Centrifugal
    Compressors", Trans. ASME, 74, pp. 473–497.
    """

    @property
    def name(self) -> str:
        return "stanitz-1952"

    @property
    def citation(self) -> str:
        return ("Stanitz, J.D., 1952, 'Some Theoretical Aerodynamic Investigations "
                "of Impellers in Radial- and Mixed-Flow Centrifugal Compressors', "
                "Trans. ASME, 74, pp. 473–497.")

    def slip_factor(self, blade_count: int, beta_2_from_tangential_rad: float,
                    radius_ratio_inducer_to_exit: float = 0.0) -> float:
        if blade_count < 1:
            raise ValueError(f"blade_count must be >= 1; got {blade_count}")
        # SPEC §13/§15: below the Z=3 validity floor the Stanitz fit
        # degenerates (σ(Z=1) = 1 − 0.63π = −0.98, σ(Z=2) ≈ 0.01). Clip Z to
        # the floor with a warning instead of returning a degenerate σ ≈ 0.
        Z = _clip_blade_count_with_warning(blade_count, self.name)
        sigma = 1.0 - 0.63 * math.pi / Z
        # Clip to physically allowed range (defensive; σ(Z=3) ≈ 0.34 > 0).
        return max(0.0, min(1.0, sigma))


@dataclass(frozen=True)
class WiesnerSlip:
    """Wiesner (1967) slip factor.

    Formula (Wiesner 1967 Eq. 1):

    :math:`\\sigma_{\\rm W} = 1 - \\dfrac{\\sqrt{\\sin\\beta_2'}}{Z^{0.7}}`

    valid for r̄₁/r₂ ≤ ε_W where ε_W = exp(-8.16 cos(β₂')/Z) is the
    **Wiesner geometric limit**. Beyond this limit, a multiplicative
    correction is applied:

    :math:`\\sigma_{\\rm W,corr} = \\sigma_{\\rm W} \\cdot \\big(1 - [(\\bar r_1/r_2 - \\varepsilon_W)/(1-\\varepsilon_W)]^3\\big)`

    Z → ∞ limit: as Z → ∞ the deficit term sqrt(sin β')/Z^0.7
    → 0, so σ → 1. Stanitz σ = 1 - 0.63π/Z also tends to 1 as Z → ∞. Both
    closures share the same physical asymptote (no slip in the limit of
    infinite blades), which is the derived-limit verification. Note
    that the *rate* of convergence differs (Z^0.7 vs Z^1), so the two
    formulas agree precisely only as Z → ∞; at Z = 100 the difference is
    ≈ 0.02 (documented in `tests/meanline/test_slip_factor_limits.py` and
    `KNOWN_GAPS.md`).

    Low-Z validity floor (SPEC_SHEET §13/§15): the Wiesner fit is documented
    only for Z ≥ 3. Below that the deficit term sqrt(sin β')/Z^0.7 grows large
    and σ degenerates (σ(Z=1, β'=90°) = 0). For Z < 3 the closure clips Z to
    the validity floor (Z = 3) and emits a `RuntimeWarning` rather than
    silently extrapolating to a degenerate slip factor — see
    :func:`_clip_blade_count_with_warning`.

    Empirical calibration: Wiesner's published formula is known to be
    conservative for modern back-swept impellers with optimized meridional
    shapes (Came & Robinson 1999 §3.2; Casey & Robinson 2021 §8). For
    Eckardt-class wheels an empirical scale of 1.04–1.06 is sometimes
    applied. The `calibration_scale` parameter exposes this.

    Citation: Wiesner, F.J., 1967, "A Review of Slip Factors for
    Centrifugal Impellers", Trans. ASME J. Eng. Power, 89(4), pp. 558–566.
    """

    calibration_scale: float = 1.0  # multiplies the Wiesner σ; 1.05 for Eckardt-class

    @property
    def name(self) -> str:
        return "wiesner-1967"

    @property
    def citation(self) -> str:
        return ("Wiesner, F.J., 1967, 'A Review of Slip Factors for "
                "Centrifugal Impellers', Trans. ASME J. Eng. Power, "
                "89(4), pp. 558–566.")

    def slip_factor(self, blade_count: int, beta_2_from_tangential_rad: float,
                    radius_ratio_inducer_to_exit: float = 0.0) -> float:
        if blade_count < 1:
            raise ValueError(f"blade_count must be >= 1; got {blade_count}")
        # SPEC §13/§15: below the Z=3 validity floor the Wiesner fit
        # degenerates (for a radial-vaned blade σ(Z=1) = 1 − sqrt(sin90°)/1
        # = 0). Clip Z to the floor with a warning instead of silently
        # returning the degenerate σ ≈ 0; σ(Z=3, β'=90°) ≈ 0.537 is physical.
        Z = _clip_blade_count_with_warning(blade_count, self.name)
        beta = beta_2_from_tangential_rad
        # Wiesner core: σ = 1 - sqrt(sin β2') / Z^0.7
        sin_beta = max(0.0, math.sin(beta))  # clip ≥0 for sqrt
        sigma_core = 1.0 - math.sqrt(sin_beta) / (Z ** 0.7)
        sigma_core = max(0.0, min(1.0, sigma_core))

        # Geometric-limit correction
        if radius_ratio_inducer_to_exit > 0.0:
            cos_beta = math.cos(beta)
            # ε_W can be > 1 (no correction needed) for low-Z or strong
            # back-sweep; expressly accept that case.
            epsilon_W = math.exp(-8.16 * cos_beta / Z)
            if radius_ratio_inducer_to_exit > epsilon_W and epsilon_W < 1.0:
                correction = 1.0 - ((radius_ratio_inducer_to_exit - epsilon_W)
                                    / (1.0 - epsilon_W)) ** 3
                sigma_core *= max(0.0, min(1.0, correction))

        # Optional empirical scale (default 1.0)
        sigma_core *= self.calibration_scale
        return max(0.0, min(1.0, sigma_core))


@dataclass(frozen=True)
class StodolaSlip:
    """Stodola (1924) slip factor: :math:`\\sigma = 1 - \\pi \\sin\\beta_2' / Z`.

    More pessimistic than Stanitz at β₂' = 90° (π·sin90°/Z = π/Z > 0.63π/Z).
    Vanishes (recovers ideal) as β₂' → 0. Historical interest; still cited
    in Aungier 2000 §4.4.

    As Z → ∞ the slip approaches 1.

    Citation: Stodola, A., 1924, *Dampf- und Gasturbinen*, Springer, Berlin.
    English translation: Loewenstein, L.C., 1927, *Steam and Gas Turbines*,
    McGraw-Hill.
    """

    @property
    def name(self) -> str:
        return "stodola-1924"

    @property
    def citation(self) -> str:
        return ("Stodola, A., 1924, *Dampf- und Gasturbinen*, Springer, "
                "Berlin. (English translation: Loewenstein, L.C., 1927, "
                "*Steam and Gas Turbines*, McGraw-Hill.)")

    def slip_factor(self, blade_count: int, beta_2_from_tangential_rad: float,
                    radius_ratio_inducer_to_exit: float = 0.0) -> float:
        if blade_count < 1:
            raise ValueError(f"blade_count must be >= 1; got {blade_count}")
        # SPEC §13/§15: below the Z=3 validity floor the Stodola fit
        # degenerates worst of all (σ(Z=1, β'=90°) = 1 − π = −2.14). Clip Z to
        # the floor with a warning instead of silently extrapolating below the
        # envelope. (Stodola is the most pessimistic closure at β'=90°; even at
        # the Z=3 floor a purely radial blade lands near σ ≈ 0 — that is the
        # documented character of the 1924 correlation, not an extrapolation
        # artefact, so the final max(0, σ) bound applies as before.)
        Z = _clip_blade_count_with_warning(blade_count, self.name)
        sigma = 1.0 - math.pi * math.sin(beta_2_from_tangential_rad) / Z
        return max(0.0, min(1.0, sigma))


# =============================================================================
# Whitfield-Baines radial-turbine loss model
# =============================================================================


@dataclass
class WhitfieldBainesRadial:
    """Loss model for radial-inflow turbines per Whitfield & Baines (1990)
    Ch. 6, with Glassman (1976) tip-clearance and Daily-Nece (1960) disc
    friction.

    Citation: Whitfield, A. & Baines, N.C., 1990, *Design of Radial
    Turbomachines*, Longman, Ch. 6 ("Aerodynamic Design and Performance of
    Radial Turbines"), §6.1–§6.4. ISBN 0-582-49510-5.
    Tip-clearance: Glassman, A.J., 1976, *Computer Program for Design
    Analysis of Radial-Inflow Turbines*, NASA TN D-8164, eq. 11–13.
    Disc friction: Daily, J.W. & Nece, R.E., 1960, "Chamber Dimension
    Effects on Induced Flow and Frictional Resistance of Enclosed Rotating
    Disks", Trans. ASME J. Basic Engineering, 82(1), pp. 217–230.

    Loss terms returned:
    - **incidence**: ζ_inc = sin²(β₁ - β₁_opt). Whitfield 1990 §6.4 with
      β₁_opt from the "1.98" correlation (Glassman 1976).
    - **profile**: ζ_prof = K_p · (W₁² + W₂²) / W₂²  — normalised so the
      breakdown's `total` is multiplied by ½ W₂² to give Δh.
    - **secondary**: ζ_sec = K_s · (r_2t/r_1)² .
    - **trailing_edge**: ζ_te per Wallis (1961) — small contribution.
    - **tip_clearance**: ζ_tip per Glassman (1976) eq. 11.
    - **disc_friction**: ζ_df per Daily-Nece (1960) regime IV (turbulent
      separated; appropriate for most industrial machines).
    - **exducer**: ζ_exd = V₂² / W₂² — recovered partially if downstream
      diffuser, lost otherwise.
    """

    # Skin-friction coefficient (Glassman 1976 recommends 0.005 as default)
    skin_friction_coefficient: float = 0.005
    # Secondary loss empirical constant (Whitfield §6.4 recommends 0.04)
    secondary_loss_constant: float = 0.04
    # Tip-clearance constants (Glassman 1976 eq. 11)
    tip_axial_constant: float = 0.40
    tip_radial_constant: float = 0.75
    tip_cross_constant: float = -0.30
    # Disc-friction empirical (Daily-Nece 1960 regime IV)
    disc_friction_constant: float = 0.0102

    # Per-term scale factors (calibration handle)
    _scale_factors: Dict[str, float] = field(default_factory=lambda: {
        "incidence": 1.0,
        "profile": 1.0,
        "secondary": 1.0,
        "trailing_edge": 1.0,
        "tip_clearance": 1.0,
        "disc_friction": 1.0,
        "exducer": 1.0,
    })

    @property
    def name(self) -> str:
        return "whitfield-baines-radial-v1"

    @property
    def machine_class(self) -> str:
        return "radial_turbine"

    @property
    def citation(self) -> str:
        return ("Whitfield, A. & Baines, N.C., 1990, *Design of Radial "
                "Turbomachines*, Longman, Ch. 6 §6.1–§6.4. "
                "Tip clearance: Glassman 1976 NASA TN D-8164 eq. 11–13. "
                "Disc friction: Daily & Nece 1960 ASME J. Basic Eng. 82(1).")

    @property
    def scale_factors(self) -> Dict[str, float]:
        return dict(self._scale_factors)

    @property
    def validity_envelope(self) -> ValidityEnvelope:
        # SPEC_SHEET §13: radial relative Mach > 2.5 is the global refusal.
        return ValidityEnvelope(M_rel_max=2.5, Re_min=1e4,
                                tip_clearance_ratio_max=0.10)

    def loss_coefficient(self, **context: Any) -> LossBreakdown:
        """Compute the radial-turbine loss breakdown.

        Required context keys:
            W_1: relative velocity at rotor inlet [m/s]
            W_2: relative velocity at rotor exit [m/s]
            V_2: absolute velocity at rotor exit [m/s]
            beta_1_flow_rad: flow angle β₁ (from tangential)
            beta_1_blade_rad: blade metal angle β₁' (from tangential)
            alpha_1_rad: absolute flow angle at rotor inlet (from tangential)
            blade_count: Z, number of blades
            r_1: rotor inlet radius [m]
            r_2_tip: rotor exit tip radius [m]
            r_2_hub: rotor exit hub radius [m]
            b_1: blade height at inlet [m]
            b_2: passage height at exit (≈ r_2_tip - r_2_hub) [m]
            tip_clearance_axial: axial tip clearance [m]
            tip_clearance_radial: radial tip clearance [m]
            U_2: tip speed at rotor exit (mean) [m/s]
            rho_2: static density at exit [kg/m³]
            mass_flow: ṁ [kg/s]
            chord_meridional: meridional chord of rotor passage [m]

        Returns:
            LossBreakdown — each term is dimensionless, normalized so that
            multiplying by ½ W₂² gives the J/kg loss for that term.
        """
        # --- pull context ----------------------------------------------------
        W_1 = float(context["W_1"])
        W_2 = float(context["W_2"])
        V_2 = float(context["V_2"])
        beta_1_flow = float(context["beta_1_flow_rad"])
        beta_1_blade = float(context["beta_1_blade_rad"])
        alpha_1 = float(context["alpha_1_rad"])
        Z = int(context["blade_count"])
        r_1 = float(context["r_1"])
        r_2_tip = float(context["r_2_tip"])
        b_1 = float(context["b_1"])
        b_2 = float(context["b_2"])
        eps_axial = float(context.get("tip_clearance_axial", 0.0))
        eps_radial = float(context.get("tip_clearance_radial", 0.0))
        U_2 = float(context.get("U_2", 0.0))
        chord_m = float(context.get("chord_meridional", max(r_1 - r_2_tip,
                                                            1e-6)))

        # Reference kinetic energy at exit
        ke_W2 = 0.5 * W_2 * W_2  # used as the denominator for nondimensionalization

        # --- Incidence -------------------------------------------------------
        # Whitfield & Baines 1990 §6.2.3 / Glassman 1976 (NASA TN D-8164):
        # The optimum incidence for a radial-inflow turbine is slightly
        # negative; the correlation is:
        #   tan(β₁_opt_from_axial) = 1.98 · tan(α₁_from_axial) / Z
        # In our from-tangential convention:
        #   α₁_from_tan = π/2 - α₁_from_axial
        #   β₁_opt_from_tan = π/2 - β₁_opt_from_axial
        # The incidence loss is the Newtonian form:
        #   Δh_inc = ½ W₁² sin²(β₁_flow - β₁_blade - i_opt)
        # where i_opt = β₁_opt - β₁_radial (i.e. the angle offset from
        # purely radial). For a rotor with a purely radial blade (β₁_blade =
        # π/2 in from-tangential), the loss is sin²(β₁_flow - π/2 - i_opt).
        # The "1.98" coefficient is Whitfield's empirical fit.
        alpha_1_from_axial = math.pi / 2 - alpha_1
        beta_1_opt_from_axial = math.atan(1.98 * math.tan(alpha_1_from_axial)
                                          / max(Z, 1))
        beta_1_opt_from_tan = math.pi / 2 - beta_1_opt_from_axial
        ksi_inc = math.sin(beta_1_flow - beta_1_opt_from_tan) ** 2

        # --- Profile (skin friction in rotor passage) -----------------------
        # K_p = 4 C_f (L_h / D_h) approx; we use the Whitfield form
        # K_p ≈ 0.5 (W1²+W2²)/W2² * 4Cf*(L/Dh).
        # Hydraulic diameter: D_h ≈ 2 b_2 (passage width).
        # Hydraulic length: meridional chord.
        D_h = max(2.0 * b_2, 1e-6)
        L_over_D = chord_m / D_h
        # Profile loss = 4 C_f (L/D_h) · (W1²+W2²)/(2 W2²) — gives ζ that
        # multiplied by ½ W₂² yields the J/kg loss.
        ksi_prof = 4.0 * self.skin_friction_coefficient * L_over_D \
            * (W_1 * W_1 + W_2 * W_2) / max(W_2 * W_2, 1e-6)

        # --- Secondary -------------------------------------------------------
        # ζ_sec = K_s · (r_2t / r_1)²  (Glassman / Whitfield; non-dim by ½W2²)
        ksi_sec = self.secondary_loss_constant * (r_2_tip / max(r_1, 1e-6)) ** 2

        # --- Trailing edge ---------------------------------------------------
        # Small term; per Wallis (1961). We use a conservative 0.005 default
        # (typical 0.3–1% of Δh) without a passage-pitch
        # input.
        ksi_te = 0.005

        # --- Tip clearance (Glassman 1976 eq. 11) ---------------------------
        # Δh_tip = ½ ρ₂ · (U₂³/(8π)) · Z · [Ka·εa·Ca/ba + Kr·εr·Cr/br]
        #        + K_ar · sqrt(εa·εr·Ca·Cr / (ba·br))
        # We normalize by ½ W₂² and ṁ so it stays a coefficient.
        # For the meanline model, use chord_m for Ca, Cr and b_2 for ba, br.
        b_a = b_1  # axial passage width at LE
        b_r = b_2  # radial passage width at TE
        C_a = chord_m
        C_r = chord_m
        # The Glassman formula gives Δh in J/kg per unit mass. We use the
        # simpler dimensionless form: ζ_tip = Z·U₂² · (K_a·ε_a/b_a + K_r·ε_r/b_r)
        # divided by ½ W₂² (capturing the leading order).
        if W_2 > 1e-6 and U_2 > 1e-6:
            tip_term = (self.tip_axial_constant * eps_axial * C_a / max(b_a, 1e-6)
                        + self.tip_radial_constant * eps_radial * C_r
                        / max(b_r, 1e-6))
            # Add the cross term (Glassman; usually negative → couples the two)
            if eps_axial > 0 and eps_radial > 0:
                tip_term += self.tip_cross_constant * math.sqrt(
                    eps_axial * eps_radial * C_a * C_r
                    / max(b_a * b_r, 1e-12))
            ksi_tip = tip_term * Z * U_2 * U_2 / (8.0 * math.pi
                                                  * max(W_2 * W_2, 1e-6))
            ksi_tip = max(0.0, ksi_tip)
        else:
            ksi_tip = 0.0

        # --- Disc friction (Daily-Nece 1960, 4-regime selector) -------------
        # ADAPT-010: dispatch on Re_ω AND s/R rather than hardcoding
        # Regime IV.
        #
        # FIX B-01 (2026-05-27): The Daily-Nece power formula is
        #   P_df = ½ C_M ρ ω³ R⁵
        # where R and U = ω·R must reference the SAME disc face. For a
        # radial-inflow turbine the dominant disc-friction surface is the
        # rotor BACK-FACE at the INLET (radius r₁ — the largest disc radius,
        # highest tip speed). The correct velocity is therefore U₁ = ω·r₁,
        # NOT U₂ = ω·r₂. The previous code used U₂ with r₁, mixing two
        # different radii. For a typical RIT with r₁/r₂ ≈ 2.5 this gives
        # a ~(2.5)³ = 15.6× overestimate when using U₂ instead of U₁.
        #
        # P_df = ½ C_M ρ U₁³ r₁²   (Daily & Nece 1960 J. Basic Eng. 82(1):217,
        #                              eq. 17–20; U = ω·R for the face being
        #                              modelled, here the inlet back-face.)
        #
        # U₁ is carried in context["U_1"] when available (added in B-01 fix);
        # fallback: derive from ω = U₂/r₂·r₁ using U₂ and the radii.
        rho_2 = float(context.get("rho_2", 0.0))
        mdot = float(context.get("mass_flow", 0.0))
        if rho_2 > 0 and mdot > 0:
            # U₁ at the rotor inlet (largest) radius r₁.
            U_1_ctx = float(context.get("U_1", 0.0))
            if U_1_ctx <= 0 and U_2 > 0 and r_1 > 0 and r_2_tip > 0:
                # Derive U₁ from U₂ via ω = U₂/r₂ → U₁ = ω·r₁
                U_1_ctx = U_2 * r_1 / max(r_2_tip, 1e-6)
            if U_1_ctx > 0:
                G_over_r = float(context.get("disc_gap_ratio", 0.02))
                Re_omega = float(context.get("Re_omega", 5e6))
                C_M = daily_nece_moment_coefficient(Re_omega, G_over_r)
                # P_df = ½ C_M ρ U₁³ r₁²  — U and R both reference inlet face.
                Pdf = 0.5 * C_M * rho_2 * U_1_ctx ** 3 * r_1 ** 2
                dh_df = Pdf / max(mdot, 1e-6)
                ksi_df = dh_df / max(0.5 * W_2 * W_2, 1e-6)
            else:
                ksi_df = 0.0
        else:
            ksi_df = 0.0

        # --- Exducer exit kinetic loss --------------------------------------
        # ζ_exd = V₂² / W₂² — if no downstream diffuser, the absolute KE is
        # lost. Otherwise scaled by (1 - C_p) of the exducer diffuser.
        ksi_exd = V_2 * V_2 / max(W_2 * W_2, 1e-6)

        # Apply scale factors
        s = self._scale_factors
        return LossBreakdown(
            incidence=s.get("incidence", 1.0) * ksi_inc,
            profile=s.get("profile", 1.0) * ksi_prof,
            secondary=s.get("secondary", 1.0) * ksi_sec,
            trailing_edge=s.get("trailing_edge", 1.0) * ksi_te,
            tip_clearance=s.get("tip_clearance", 1.0) * ksi_tip,
            disc_friction=s.get("disc_friction", 1.0) * ksi_df,
            exducer=s.get("exducer", 1.0) * ksi_exd,
        )


# =============================================================================
# Aungier centrifugal-compressor loss model
# =============================================================================


@dataclass
class AungierCentrifugal:
    """Loss model for centrifugal compressors per Aungier (2000) Ch. 6.

    Citation: Aungier, R.H., 2000, *Centrifugal Compressors: A Strategy for
    Aerodynamic Design and Analysis*, ASME Press, New York, Ch. 6
    ("Centrifugal Impeller Performance Analysis"). ISBN 0-7918-0093-8.

    Loss terms returned (all dimensionless, normalized to multiply by ½ U₂²):
    - **incidence**: Aungier eq. 6.18 — incidence at impeller leading edge.
      Per ADAPT-009, this is now computed against a *real* blade metal
      angle (no longer forced to vanish at design).
    - **blade_loading**: Aungier eq. 6.34 — diffusion-factor based.
    - **profile**: Aungier eq. 6.41 — skin friction in the impeller passage.
    - **mixing**: Aungier eq. 6.51 — jet-wake mixing at impeller exit.
      Implemented as Δh = ½ (ε_w · W₂)² · sin²(β₂_blade); ε_w is the
      wake-area fraction (Aungier-recommended 0.10–0.30, default 0.15).
      For a purely tangential-discharge impeller β₂'→0° → sin→0 → mixing→0;
      for a radial-bladed impeller β₂'=90° → sin=1 → maximum mixing (the
      meridional velocity deficit is largest). This explicit sin²(β₂')
      dependence follows Aungier 2000 eq. 6.51 directly and replaces the
      previous cos² (B-07 fix, 2026-05-27).
    - **tip_clearance**: Aungier eq. 6.45 — Krylov-style; Jansen-Pampreen form.
    - **disc_friction**: Aungier eq. 6.58 — Daily-Nece 1960 with the
      4-regime selector (Daily-Nece Table 1; ADAPT-010).
    - **recirculation**: Aungier eq. 6.61 — Oh-Yoon-Chung (1997).
    - **leakage**: Aungier eq. 6.66 — orifice-flow seal model. Uses
      Δp_seal = P₂ − P₁, C_d ≈ 0.816, A_clearance = π·2r₂·ε_clearance.
      The previous hand-fit (mdot_leak ~ tip_clearance/b₂ × 0.1) is
      preserved as a fallback when the thermodynamic state is absent.
    """

    # Aungier-recommended empirical constants (Aungier 2000 §6.2)
    # C_f range per Aungier eq. 6.41 commentary is 0.0050–0.0150;
    # default 0.005 is the Re~1e6 reference. For Re~5e6 (typical impeller),
    # C_f closer to 0.0075 is justified. We use 0.0075 as the calibrated
    # default for impeller skin friction at industrial Re.
    skin_friction_coefficient: float = 0.0075
    recirculation_constant: float = 8e-5  # Oh-Yoon-Chung 1997
    disc_friction_constant: float = 0.0102
    # Effective hydraulic length multiplier (back-swept blades have curved
    # meridional paths; the straight radial extent under-counts the wetted
    # length). Aungier 2000 §6.2 commentary: ~1.5x for 30° back-swept wheels.
    hydraulic_length_multiplier: float = 1.5
    # Aungier 2000 eq. 6.51 wake-mixing wake-fraction factor ε_w.
    # Aungier §6.6 notes 0.10–0.30 typical for well-designed impellers;
    # 0.15 is the commonly cited middle-of-the-road value for Eckardt
    # rotors (Casey & Robinson 2021 §8.6). Smaller ε_w = less wake
    # mixing loss (better wheel).
    wake_fraction: float = 0.15
    # Aungier eq. 6.66 leakage discharge coefficient (Cd · √2 factor).
    # 0.816 = √(2/3) is the Aungier-cited orifice flow coefficient
    # for a labyrinth-style seal (Aungier 2000 §6.6).
    leakage_discharge_coefficient: float = 0.816

    _scale_factors: Dict[str, float] = field(default_factory=lambda: {
        "incidence": 1.0,
        "blade_loading": 1.0,
        "profile": 1.0,
        "mixing": 1.0,
        "tip_clearance": 1.0,
        "disc_friction": 1.0,
        "recirculation": 1.0,
        "leakage": 1.0,
    })

    @property
    def name(self) -> str:
        return "aungier-centrifugal-v1"

    @property
    def machine_class(self) -> str:
        return "centrifugal_compressor"

    @property
    def citation(self) -> str:
        return ("Aungier, R.H., 2000, *Centrifugal Compressors: A Strategy "
                "for Aerodynamic Design and Analysis*, ASME Press, Ch. 6 "
                "(eq. 6.18 incidence, 6.34 blade loading, 6.41 skin friction, "
                "6.45 tip clearance, 6.51 mixing, 6.58 disc friction, "
                "6.61 recirculation [Oh-Yoon-Chung 1997], 6.66 leakage).")

    @property
    def scale_factors(self) -> Dict[str, float]:
        return dict(self._scale_factors)

    @property
    def validity_envelope(self) -> ValidityEnvelope:
        # Slip factor extrapolated for Z<3 (warning).
        # Per SPEC_SHEET §13: M_rel > 2.5 is global refusal.
        # Centrifugal-specific: tip-speed Mach typically < 1.2.
        return ValidityEnvelope(M_rel_max=2.5, M_abs_max=1.2, Re_min=1e4,
                                blade_count_min=3,
                                tip_clearance_ratio_max=0.15)

    def loss_coefficient(self, **context: Any) -> LossBreakdown:
        """Compute the centrifugal-compressor loss breakdown.

        All output ζ_i are dimensionless and normalized so that multiplying
        by ½ U₂² gives the Δh_i in J/kg.

        Required context keys:
            U_2: impeller tip speed [m/s]
            W_1_tip: relative velocity at inducer tip [m/s]
            W_2: relative velocity at impeller exit [m/s]
            V_2: absolute velocity at impeller exit [m/s]
            beta_1_flow_rad: flow angle at inducer LE (from tangential)
            beta_1_blade_rad: blade metal angle at inducer LE (from tangential)
            beta_2_blade_rad: blade angle at impeller exit (from tangential)
            alpha_2_rad: absolute flow angle at impeller exit (from tangential)
            blade_count: Z
            r_1_tip: inducer tip radius [m]
            r_1_hub: inducer hub radius [m]
            r_2: impeller exit radius [m]
            b_2: impeller exit blade height [m]
            tip_clearance: tip clearance [m]
            chord_meridional: meridional chord of impeller passage [m]
            mass_flow: ṁ [kg/s]
            rho_2: static density at impeller exit [kg/m³]
            sigma: slip factor (for incidence + recirculation models)
            DF: diffusion factor (for recirculation)
        """
        # Pull context
        U_2 = float(context["U_2"])
        W_1_tip = float(context["W_1_tip"])
        W_2 = float(context["W_2"])
        V_2 = float(context["V_2"])
        beta_1_flow = float(context["beta_1_flow_rad"])
        beta_1_blade = float(context["beta_1_blade_rad"])
        beta_2_blade = float(context["beta_2_blade_rad"])
        alpha_2 = float(context["alpha_2_rad"])
        Z = int(context["blade_count"])
        r_1_tip = float(context["r_1_tip"])
        r_1_hub = float(context["r_1_hub"])
        r_2 = float(context["r_2"])
        b_2 = float(context["b_2"])
        tip_clearance = float(context.get("tip_clearance", 0.0))
        chord_m = float(context.get("chord_meridional",
                                    max(r_2 - 0.5 * (r_1_tip + r_1_hub),
                                        1e-6)))
        mdot = float(context.get("mass_flow", 0.0))
        rho_2 = float(context.get("rho_2", 0.0))
        sigma = float(context.get("sigma", 0.85))
        DF = float(context.get("DF", 0.4))

        ke_U2 = 0.5 * U_2 * U_2  # reference KE
        ke_W2 = 0.5 * W_2 * W_2  # alternative reference

        # --- Incidence -------------------------------------------------------
        # Aungier eq. 6.18: Δh_inc = ½ f_inc W₁² sin²(β₁_blade - β₁_flow)
        # with f_inc ≈ 0.5–0.7 (Aungier recommends 0.6).
        f_inc = 0.6
        dh_inc = 0.5 * f_inc * W_1_tip ** 2 * math.sin(beta_1_blade
                                                       - beta_1_flow) ** 2
        ksi_inc = dh_inc / max(ke_U2, 1e-6)

        # --- Blade loading (Aungier eq. 6.34) -------------------------------
        # Δh_bld = 0.05 * DF² * U₂²
        dh_bld = 0.05 * DF ** 2 * U_2 ** 2
        ksi_bld = dh_bld / max(ke_U2, 1e-6)

        # --- Skin friction (Aungier eq. 6.41) -------------------------------
        # Δh_sf = 4 C_f (L_h / D_h) W_avg²  with W_avg² = (W₁² + W₂²)/2
        # Aungier eq. 6.42: D_h = 2 b_2 (s cos β')/(b_2 + s cos β')
        # using s = 2π r₂ / Z (pitch at exit) and β' = (β₁' + β₂')/2.
        beta_avg = 0.5 * (beta_1_blade + beta_2_blade)
        s_pitch = 2.0 * math.pi * r_2 / max(Z, 1)
        s_cos_beta = s_pitch * abs(math.cos(beta_avg))
        D_h_num = 2.0 * b_2 * s_cos_beta
        D_h_den = max(b_2 + s_cos_beta, 1e-9)
        D_h = max(D_h_num / D_h_den, 1e-6)
        L_h = chord_m * self.hydraulic_length_multiplier
        L_over_D = L_h / D_h
        W_avg_sq = 0.5 * (W_1_tip ** 2 + W_2 ** 2)
        dh_sf = 4.0 * self.skin_friction_coefficient * L_over_D * W_avg_sq
        ksi_sf = dh_sf / max(ke_U2, 1e-6)

        # --- Mixing (Aungier 2000 eq. 6.51 — wake/jet mixing) ---------------
        # ADAPT-007: replace the previous piecewise constant (0.02/0.04)
        # with the real Aungier wake-mixing formula. Physical picture: at
        # the impeller exit the flow is split into a high-momentum "jet"
        # (along the pressure surface) and a low-momentum "wake" (along
        # the suction surface). As they mix out downstream, the velocity
        # discontinuity dissipates kinetic energy ∝ (Δw)².
        #
        # FIX B-07 (2026-05-27): Aungier 2000 §6.6 eq. 6.51 uses sin²(β₂'),
        # NOT cos²(β₂'). The mixing-loss velocity deficit is in the MERIDIONAL
        # direction: the meridional component of W₂ is W₂·sin(β₂') (where β₂'
        # is measured from tangential). For a radial-bladed impeller β₂'=90°
        # → sin(90°)=1 → maximum meridional-plane mixing (jet/wake have
        # maximum meridional shear); for a radial-discharge impeller β₂'→0°
        # → sin→0 → no mixing (pure tangential flow, no meridional deficit).
        # The previous cos² code had the trig direction inverted, giving zero
        # loss precisely where Aungier predicts maximum loss and vice-versa.
        #
        # Aungier 2000 §6.6 (eq. 6.51):
        #   Δh_mix = ½ · (ε_w · W₂)² · sin²(β₂_blade_from_tan)
        # where ε_w is the wake-area fraction (default 0.15, Aungier §6.6).
        #
        # Citation: Aungier, R.H., 2000, *Centrifugal Compressors: A Strategy
        # for Aerodynamic Design and Analysis*, ASME Press, Ch. 6, eq. 6.51.
        eps_w = self.wake_fraction
        sin_beta2 = math.sin(beta_2_blade)
        dh_mix = 0.5 * (eps_w * W_2) ** 2 * sin_beta2 ** 2
        ksi_mix = dh_mix / max(ke_U2, 1e-6)

        # --- Tip clearance (Aungier eq. 6.45 / Jansen-Pampreen) -------------
        # Δh_tip = 0.6 · (ε/b₂) · U₂ · V_θ2  (simplified Jansen-Pampreen)
        if b_2 > 0 and tip_clearance > 0:
            V_theta_2 = sigma * U_2 - W_2 * math.cos(beta_2_blade)  # approx
            V_theta_2 = max(V_theta_2, 0.0)
            dh_tip = 0.6 * (tip_clearance / b_2) * U_2 * V_theta_2
            ksi_tip = dh_tip / max(ke_U2, 1e-6)
        else:
            ksi_tip = 0.0

        # --- Disc friction (Aungier eq. 6.58, Daily-Nece 1960) --------------
        # ADAPT-010: 4-regime selector (laminar I/II + turbulent III/IV)
        # rather than hardcoding Regime IV.
        if rho_2 > 0 and mdot > 0 and U_2 > 0:
            G_over_r = float(context.get("disc_gap_ratio", 0.02))
            Re_omega = float(context.get("Re_omega", 5e6))
            C_M = daily_nece_moment_coefficient(Re_omega, G_over_r)
            Pdf = 0.5 * C_M * rho_2 * U_2 ** 3 * r_2 ** 2
            dh_df = Pdf / max(mdot, 1e-6)
            ksi_df = dh_df / max(ke_U2, 1e-6)
        else:
            ksi_df = 0.0

        # --- Recirculation (Aungier eq. 6.61, Oh-Yoon-Chung 1997) -----------
        # Δh_rec = 8e-5 · sinh(3.5 α₂'³) · DF² · U₂²
        # α₂' = absolute flow angle from radial (= π/2 - α₂ from tangential)
        alpha_2_from_radial = math.pi / 2.0 - alpha_2
        # Clip α to avoid sinh overflow for nonsensical operating points
        a3 = min(max(alpha_2_from_radial, 0.0), 1.3) ** 3
        dh_rec = self.recirculation_constant * math.sinh(3.5 * a3) \
            * DF ** 2 * U_2 ** 2
        ksi_rec = dh_rec / max(ke_U2, 1e-6)

        # --- Leakage (Aungier 2000 eq. 6.66) --------------------------------
        # ADAPT-007: replace the previous hand-fit ratio with the real
        # Aungier orifice-flow leakage model. Physical picture: the seal
        # at the shroud (or hub) allows a small mass flow to bypass the
        # impeller blade row, driven by the static pressure difference
        # across the seal (P_2_static − P_1_static across the shroud).
        # The leakage flow re-enters the main stream and mixes out; its
        # tangential momentum is destroyed → entropy rise.
        #
        # Aungier eq. 6.66:
        #   U_leak = C_d · √(2·Δp_seal / ρ_avg)
        #   ṁ_leak = ρ_avg · U_leak · A_clearance
        #   A_clearance = π · 2·r₂ · ε_clearance
        #   Δh_leak = (ṁ_leak / ṁ_main) · (h₀₂ − h₀₁)
        # where C_d ≈ 0.816 is Aungier's labyrinth discharge coefficient.
        # We use the approximation h₀₂ − h₀₁ ≈ w_Euler ≈ σ·U₂² ·
        # (1 − V_m₂ cot β₂'/U₂); the latter is exactly the Euler work
        # supplied by the impeller, which equals σ U₂² for the radial-
        # bladed case and reduces for back-swept.
        P_1 = float(context.get("P_1", 0.0))
        P_2 = float(context.get("P_2", 0.0))
        rho_1 = float(context.get("rho_1", 0.0))
        eps_clearance = float(context.get("epsilon_clearance", 0.0))
        if (eps_clearance > 0 and rho_2 > 0 and rho_1 > 0 and mdot > 0
                and P_2 > P_1 > 0):
            dp_seal = P_2 - P_1
            rho_avg = 0.5 * (rho_1 + rho_2)
            U_leak = (self.leakage_discharge_coefficient
                      * math.sqrt(2.0 * dp_seal / max(rho_avg, 1e-6)))
            A_clearance = math.pi * 2.0 * r_2 * eps_clearance
            mdot_leak = rho_avg * U_leak * A_clearance
            # Work per unit main-flow mass that goes into leakage:
            # the leakage mass receives the full Euler work but is then
            # dissipated in mixing → it represents a parasitic loss.
            # h₀₂ − h₀₁ ≈ σ U₂² · (1 − V_m₂·cot(β₂')/U₂) but as a robust
            # approximation we use σ·U₂² (this is exact for radial-bladed
            # and an upper bound otherwise).
            dh_total_main = sigma * U_2 ** 2
            dh_lk = (mdot_leak / max(mdot, 1e-9)) * dh_total_main
            ksi_lk = dh_lk / max(ke_U2, 1e-6)
        elif b_2 > 0 and tip_clearance > 0:
            # Fallback when full thermodynamic state is unavailable
            # (e.g., the radial-turbine pathway calls the centrifugal
            # loss model without P_1/P_2). Use a conservative ratio
            # proportional to tip-clearance / blade-height (Aungier
            # §6.6 commentary on simplified leakage estimate).
            mdot_lk_ratio = tip_clearance / b_2 * 0.1
            dh_lk = mdot_lk_ratio * 0.6 * U_2 ** 2
            ksi_lk = dh_lk / max(ke_U2, 1e-6)
        else:
            ksi_lk = 0.0

        s = self._scale_factors
        return LossBreakdown(
            incidence=s.get("incidence", 1.0) * ksi_inc,
            blade_loading=s.get("blade_loading", 1.0) * ksi_bld,
            profile=s.get("profile", 1.0) * ksi_sf,
            mixing=s.get("mixing", 1.0) * ksi_mix,
            tip_clearance=s.get("tip_clearance", 1.0) * ksi_tip,
            disc_friction=s.get("disc_friction", 1.0) * ksi_df,
            recirculation=s.get("recirculation", 1.0) * ksi_rec,
            leakage=s.get("leakage", 1.0) * ksi_lk,
        )
