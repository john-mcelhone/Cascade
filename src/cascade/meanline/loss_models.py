"""Loss-model framework for mean-line turbomachinery solvers.

This module declares the canonical `LossModel` Protocol that every mean-line
loss closure implements, plus the supporting `LossBreakdown` and
`ValidityEnvelope` dataclasses, and the `SlipFactor` Protocol (the Wiesner
slip factor must converge to Stanitz as Z → ∞ and be clipped at the Wiesner
geometric limit).

The Protocol mirrors SPEC_SHEET §3 ("Port-based handoff") and §7
("Constitutive models and citation requirement"):

- Every concrete loss model declares an **open citation** (book + edition +
  chapter, OR paper + journal + DOI).
- Every concrete loss model declares its **scale factors** (default = 1.0)
  to allow per-project calibration without modifying source.
- Every concrete loss model declares its **validity envelope** so the
  solver can raise `RegimeOutOfValidity` outside the documented domain.

References (canonical):

- Whitfield, A. & Baines, N.C., 1990. *Design of Radial Turbomachines*,
  Longman, Ch. 6 — radial turbine loss models.
- Aungier, R.H., 2000. *Centrifugal Compressors: A Strategy for Aerodynamic
  Design and Analysis*, ASME Press, Ch. 6 — centrifugal compressor loss models.
- Wiesner, F.J., 1967. "A Review of Slip Factors for Centrifugal Impellers",
  Trans. ASME J. Eng. Power, 89(4), pp. 558–566.
- Stanitz, J.D., 1952. "Some Theoretical Aerodynamic Investigations of
  Impellers in Radial- and Mixed-Flow Centrifugal Compressors",
  Trans. ASME, 74, pp. 473–497.
- Stodola, A., 1924. *Dampf- und Gasturbinen*, Springer, Berlin.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

try:  # pragma: no cover — Protocol is in typing on 3.9
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing_extensions import Protocol, runtime_checkable  # type: ignore[assignment]


# --- LossBreakdown -----------------------------------------------------------


@dataclass(frozen=True)
class LossBreakdown:
    """A named decomposition of the entropy / enthalpy loss in a stage.

    Each entry is a **dimensionless enthalpy-loss coefficient** :math:`\\zeta_i`
    such that ``Δh_loss_i = ζ_i · (½ W_ref²)`` with W_ref the natural reference
    velocity for the loss (typically W₂ for rotor-exit losses, V₁ for nozzle
    losses; the loss-model convention is documented per term below).

    For both the radial turbine and the centrifugal compressor we track the
    union of loss-term names that appear in either machine class.
    Unused terms default to 0.0.

    The total enthalpy loss for the stage is ``sum(getattr(self, k) for k in
    self.terms())`` and provides the input to the actual outlet total
    temperature via the rothalpy / energy bookkeeping in the solver.
    """

    incidence: float = 0.0
    profile: float = 0.0  # skin friction (rotor passage, blade profile)
    secondary: float = 0.0
    trailing_edge: float = 0.0
    tip_clearance: float = 0.0
    disc_friction: float = 0.0
    leakage: float = 0.0
    recirculation: float = 0.0  # centrifugal: Oh-Yoon-Chung 1997
    mixing: float = 0.0  # centrifugal: jet-wake mixing at impeller exit
    scroll: float = 0.0  # volute / scroll loss
    blade_loading: float = 0.0  # centrifugal: Aungier eq. 6.34
    nozzle: float = 0.0  # radial turbine: nozzle / vaneless space
    exducer: float = 0.0  # radial turbine: exducer exit kinetic loss

    def terms(self) -> Dict[str, float]:
        """Return the loss term name → value mapping."""
        return {
            "incidence": self.incidence,
            "profile": self.profile,
            "secondary": self.secondary,
            "trailing_edge": self.trailing_edge,
            "tip_clearance": self.tip_clearance,
            "disc_friction": self.disc_friction,
            "leakage": self.leakage,
            "recirculation": self.recirculation,
            "mixing": self.mixing,
            "scroll": self.scroll,
            "blade_loading": self.blade_loading,
            "nozzle": self.nozzle,
            "exducer": self.exducer,
        }

    @property
    def total(self) -> float:
        """Sum of all loss coefficients. The solver multiplies by the
        appropriate reference kinetic energy to get the J/kg loss."""
        return sum(self.terms().values())


# --- ValidityEnvelope --------------------------------------------------------


@dataclass(frozen=True)
class ValidityEnvelope:
    """The regime where a loss model is known to be accurate.

    Per SPEC_SHEET §13, refusal triggers an explicit `RegimeOutOfValidity`
    exception with cause code; the solver checks each entry that is not None.

    Conventions:

    - `M_rel_max`: relative Mach at *any* station. SPEC §13 sets 2.5 for
      radial turbines globally.
    - `M_abs_max`: absolute Mach at impeller / rotor inlet.
    - `Re_min`: minimum Reynolds (typical = 1e4; below is laminar regime).
    - `psi_max`: stage loading coefficient.
    - `phi_max` / `phi_min`: flow coefficient bounds.
    - `tip_clearance_ratio_max`: ε/b ≤ this fraction (cap on tip-clearance
      correlation extrapolation).
    - `blade_count_min`: slip-factor low-blade-count warning (SPEC §13 sets
      Z < 3 as extrapolated; warning only).
    """

    M_rel_max: Optional[float] = None
    M_abs_max: Optional[float] = None
    Re_min: Optional[float] = None
    psi_max: Optional[float] = None
    phi_max: Optional[float] = None
    phi_min: Optional[float] = None
    tip_clearance_ratio_max: Optional[float] = None
    blade_count_min: Optional[int] = None


# --- LossModel Protocol ------------------------------------------------------


@runtime_checkable
class LossModel(Protocol):
    """The canonical loss-model interface.

    Implementations follow SPEC_SHEET §7 citation discipline: they declare
    an open citation (book + chapter, or paper + DOI), a default set of
    scale factors (1.0 per term, user-overridable), and a validity envelope.

    The `loss_coefficient` method returns a `LossBreakdown` given the local
    flow / geometry context as a kwargs dict. The convention is that the
    solver builds the context (velocity triangles + densities + geometry +
    fluid props) and passes it in; the model returns the per-term ζ values.

    The signature uses a context dict rather than a long positional list so
    that loss-model authors can request only the fields they need without
    forcing every concrete implementation to consume every possible field.
    Required keys are documented per-method.
    """

    @property
    def name(self) -> str:
        """Short identifier (e.g. 'whitfield-baines-radial-v1')."""
        ...

    @property
    def machine_class(self) -> str:
        """One of 'radial_turbine', 'centrifugal_compressor'."""
        ...

    @property
    def citation(self) -> str:
        """Open citation — book + edition + chapter, or paper + journal + DOI.
        SPEC_SHEET §7 forbids closed citations in v1 builtin models."""
        ...

    @property
    def scale_factors(self) -> Dict[str, float]:
        """Per-term scale factors. Default 1.0 per term; users override per
        project. Multiplies the corresponding LossBreakdown field."""
        ...

    @property
    def validity_envelope(self) -> ValidityEnvelope:
        """The regime where the model is documented to be accurate."""
        ...

    def loss_coefficient(self, **context: Any) -> LossBreakdown:
        """Compute the loss breakdown for one operating point.

        Required context keys are documented per concrete implementation;
        unknown keys are silently ignored to allow forward-compatible solver
        extensions.
        """
        ...


# --- Slip-factor Protocol + closures ----------------------------------------


@runtime_checkable
class SlipFactor(Protocol):
    """A slip-factor closure for centrifugal compressor impeller exit.

    The slip factor :math:`\\sigma` is the ratio of the actual tangential
    velocity to the blade-relative ideal tangential
    velocity at impeller exit. All three canonical closures (Stanitz,
    Wiesner, Stodola) are pluggable.
    """

    @property
    def name(self) -> str:
        ...

    @property
    def citation(self) -> str:
        ...

    def slip_factor(self, blade_count: int, beta_2_from_tangential_rad: float,
                    radius_ratio_inducer_to_exit: float = 0.0) -> float:
        """Return the slip factor σ ∈ (0, 1].

        Args:
            blade_count: Z, number of blades (includes splitters in the
                effective count).
            beta_2_from_tangential_rad: blade angle at impeller exit measured
                *from the tangential direction*. For a radial-vaned impeller
                this is π/2; for a back-swept impeller with 30° back-sweep
                from radial, this is 60° = π/3.
                Note: this is the convention from Wiesner 1967 and Aungier
                2000; the Cascade canonical store is from-axial, so callers
                must convert at the boundary (the literature convention is
                preserved internally for the slip-factor formulas).
            radius_ratio_inducer_to_exit: r₁_mean / r₂ — used by Wiesner's
                geometric-limit correction. Optional (defaults to 0 → no
                limit correction applied).
        """
        ...


# --- Note on canonical-direction convention ----------------------------------
#
# Per SPEC_SHEET §3.2, the Cascade canonical store is **radians from axial**.
# But every published slip-factor formula in the literature (Stanitz, Wiesner,
# Stodola, Busemann) uses *radians from tangential*. We preserve the
# literature convention in the formulas and document the conversion clearly.
# A back-swept blade with 30° back-sweep has β_from_tangential = 60°
# = π/3 rad. (See Wiesner 1967 Fig. 1.)
#
# The conversion utility is `cascade.units.deg_from_tangential_to_rad_from_axial`.
