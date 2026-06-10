"""Manufacturability rule dataclasses + defaults.

Each :class:`ManufacturabilityRule` is a small frozen record that ties a
human-readable name and citation to a numeric floor / ceiling. ``checks.py``
walks the rule list, evaluates each rule's ``measure`` function against the
geometry, and emits a ``Violation`` if the result falls outside the rule's
``default_min``/``default_max`` band.

References
----------
- AMRC 5-axis turbomachinery cutter survey (2019). The 0.30 mm LE / 0.20 mm TE
  / 0.5 mm fillet floors are typical for a 5-axis machining cell with 2 mm
  ball-nose cutters, on Inconel / Ti-6Al-4V.
- Concepts NREC, "Compressor Aerodynamic Design — Manufacturability Guidelines
  for Centrifugal Impellers" (2016 webinar deck).
- Boyce, "Gas Turbine Engineering Handbook" 4th ed. §3.4 — Cold tip clearance
  is conventionally 0.25–0.50 mm at room temperature for microturbine-class
  rotors (running 0.05–0.15 mm hot after thermal growth + casing creep).
- Whitfield & Baines 1990 §6.3 (radial turbines) — TE thickness on cast
  Ni-base radial-inflow rotors is routinely 0.10 mm (laser-trimmed) and the
  LE 0.25 mm; cast turbines tolerate thinner edges than machined compressors.
- ANSI/ASME B89.6.2 + shop convention — wrap angle beyond 90° is rare and
  requires a 5-axis swarf cut against a slender tool; we floor at the
  conventional 90° envelope. (Pure microturbine rotors run 70–85°.)

Severity semantics
------------------
``error``  — a standard 5-axis machining cell cannot produce the feature
             (tool access, edge thickness below what a cutter leaves
             standing, wrap beyond the conventional envelope). These gate
             the design-space sweep: violating candidates are statused
             ``MANUFACTURABILITY_FAILED`` (SPEC §13).
``warning`` — shop-practice / assembly envelope (tip clearance, aspect
             ratio, fillet convention). Also gate the sweep by default,
             but represent practice rather than physical impossibility.
Per-project overrides (``settings.manufacturability_overrides``) loosen
either tier for shops with better-than-standard capability.

Thickness floors are shared with the mesh generators via
``manufacturability.limits`` — the geometry Cascade produces is floored to
the machinable minimum BY CONSTRUCTION, so the LE/TE rules only fire when
an explicit (user-supplied) thickness undercuts the floor. The splitter
passage rule reflects the generated geometry's always-present splitter row
(one per main blade, half pitch, from 50 % chord) — for the default design
space it is the binding tool-access passage, tighter than the inducer
throat.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Optional


Severity = Literal["warning", "error"]


@dataclass(frozen=True)
class ManufacturabilityRule:
    """A single manufacturability check.

    Attributes:
        name: stable identifier — also used as the override-key on a project.
        description: one-line human-readable summary.
        default_min: lower bound on the measured value. ``None`` = no floor.
        default_max: upper bound on the measured value. ``None`` = no ceiling.
        units: presentation unit (``"mm"``, ``"deg"``, etc.). The ``measure``
            function returns a value in this unit (so the override threshold is
            also in this unit — no implicit conversions).
        severity: ``"warning"`` (informational, doesn't block save) or
            ``"error"`` (Concepts NREC would refuse to cut it).
        citation: short citation key referencing the rules.py module docstring.
        measure: a callable ``geometry -> float`` that extracts the relevant
            scalar in the rule's ``units``. The dataclass is frozen so we
            attach the callable here directly; this keeps each rule
            self-contained.
    """

    name: str
    description: str
    default_min: Optional[float]
    default_max: Optional[float] = None
    units: str = ""
    severity: Severity = "warning"
    citation: str = ""
    # The callable is attached separately at module level so the rule itself
    # remains a pure data record (no closures over geometry types). It is
    # treated as a non-comparison field for dataclass equality.
    measure: Optional[Callable[..., float]] = None


# =============================================================================
# Measurement helpers — derive geometric quantities not stored explicitly.
# =============================================================================
#
# Cascade's mean-line geometry dataclasses don't carry an explicit leading-edge
# thickness — the blade profile is computed at mesh-generation time. For the
# manufacturability check we estimate the LE thickness from the same
# bell-curve thickness distribution that the mesh generator uses
# (1.5 % of the reference radius peak; the LE / TE values are 30 % of peak).
# Authors of a future "explicit-blade-thickness" field can swap these helpers
# without changing rule definitions.


def _impeller_blade_thickness_max_m(geometry) -> float:  # noqa: ANN001
    """The peak (mid-chord) blade thickness used by the mesh generator.

    Mirrors ``cascade.geometry.impeller._build_single_blade``: 1.5 % of the
    impeller exit radius, floored at the 5-axis milling minimum (both sides
    read ``manufacturability.limits.machinable_blade_peak_thickness_m`` so
    the manufacturability check and the mesh stay in step).
    """
    from cascade.manufacturability.limits import (
        machinable_blade_peak_thickness_m,
    )

    # Optional explicit override on the geometry — added by future revisions
    # of CentrifugalCompressorGeometry once a blade-thickness field exists.
    explicit = getattr(geometry, "blade_thickness_max", None)
    if explicit is not None:
        return float(explicit)
    return machinable_blade_peak_thickness_m(geometry.impeller_outlet_radius)


def _impeller_le_thickness_m(geometry) -> float:  # noqa: ANN001
    """Leading-edge thickness in metres.

    Cascade's bell-curve blade profile (``blade_thickness_distribution`` in
    ``cascade.geometry._curves``) reaches roughly 30 % of the peak at the LE.
    If a future ``leading_edge_thickness`` field is added we honour it.
    """
    explicit = getattr(geometry, "leading_edge_thickness", None)
    if explicit is not None:
        return float(explicit)
    return 0.30 * _impeller_blade_thickness_max_m(geometry)


def _impeller_te_thickness_m(geometry) -> float:  # noqa: ANN001
    explicit = getattr(geometry, "trailing_edge_thickness", None)
    if explicit is not None:
        return float(explicit)
    return 0.30 * _impeller_blade_thickness_max_m(geometry)


def _impeller_root_fillet_m(geometry) -> float:  # noqa: ANN001
    """Blade-root fillet radius. Falls back to a sensible default.

    The default is 1.5 % of the inducer hub radius (matches the proportional
    radius rule used by 5-axis ball-nose cutters in a typical microturbine
    impeller, where the fillet equals one cutter step). Future revisions
    should attach an explicit ``root_fillet`` field to the geometry.
    """
    explicit = getattr(geometry, "root_fillet", None)
    if explicit is not None:
        return float(explicit)
    return max(0.015 * float(geometry.inducer_hub_radius), 0.5e-3)


def _impeller_throat_width_m(geometry) -> float:  # noqa: ANN001
    """Approximate blade-to-blade throat width at the meridional throat.

    For a centrifugal impeller the throat is (2π r / Z) − t_blade evaluated
    at the inducer mean radius (where the blade pitch is smallest and the
    blade thickness is closest to the LE thickness). This is the canonical
    "can a 2 mm cutter fit?" check.
    """
    Z = float(geometry.blade_count)
    r_throat = float(geometry.inducer_mean_radius)
    pitch_m = 2.0 * 3.141592653589793 * r_throat / Z
    t_blade = _impeller_le_thickness_m(geometry)
    # The flow passage width perpendicular to the camber is the pitch minus
    # one blade thickness (a slight over-estimate; the true throat is the
    # normal distance, which is pitch · sin(β_blade) − thickness, but for
    # this manufacturability check the pitch–thickness form is the more
    # conservative and the one the shop quotes against.).
    return max(0.0, pitch_m - t_blade)


def _impeller_splitter_passage_m(geometry) -> float:  # noqa: ANN001
    """Approximate main-to-splitter passage width at the splitter LE.

    Cascade's mesh generator emits one splitter per main blade at half
    pitch, starting at 50 % meridional chord. The passage a cutter must
    finish there is HALF the main-blade pitch minus one blade thickness,
    evaluated at the 50 %-chord radius — for the swept design space this
    is tighter than the inducer throat and is the binding tool-access
    passage. Radius at 50 % chord is approximated as the mean of the
    inducer mean radius and the exit radius (the hub turns smoothly from
    axial to radial across the chord).
    """
    Z = float(geometry.blade_count)
    if Z <= 0:
        return 0.0
    r_50 = 0.5 * (
        float(geometry.inducer_mean_radius)
        + float(geometry.impeller_outlet_radius)
    )
    half_pitch_m = 3.141592653589793 * r_50 / Z
    # At mid-chord the bell-curve thickness is at its peak.
    t_blade = _impeller_blade_thickness_max_m(geometry)
    return max(0.0, half_pitch_m - t_blade)


def _impeller_wrap_angle_deg(geometry) -> float:  # noqa: ANN001
    """Estimated total blade wrap angle Δθ from LE to TE, in degrees.

    The Cascade mesh generator integrates ``dθ/dm = tan(β)/r`` along the
    hub streamline; we replicate the integral in closed form for a constant
    blade-angle distribution:

        Δθ ≈ ∫ tan(β_avg) / r dr ≈ tan(β_avg) · ln(r₂ / r₁_mean)

    where β_avg is the average of the LE and TE blade angles measured from
    tangential. This is the same approximation Whitfield & Baines §6.5 use
    when sizing a wrap angle envelope.
    """
    import math

    r1 = float(geometry.inducer_mean_radius)
    r2 = float(geometry.impeller_outlet_radius)
    # β₂ in from-axial; convert to from-tangential.
    beta_2_from_tan = math.pi / 2.0 - float(geometry.beta_2_metal_rad)
    # LE blade angle from-tangential — use the impeller's stored inducer-tip
    # blade angle when present, else default 60° from axial == 30° from tan
    # (matches the canonical Whitfield 1990 inducer profile).
    beta_1_from_axial = getattr(
        geometry, "inducer_tip_blade_metal_rad", None
    )
    if beta_1_from_axial is None:
        beta_1_from_axial = math.radians(60.0)
    beta_1_from_tan = math.pi / 2.0 - float(beta_1_from_axial)
    beta_avg_from_tan = 0.5 * (beta_1_from_tan + beta_2_from_tan)
    # tan() blows up at π/2; clamp to the same numerical floor the mesh
    # generator uses.
    tan_beta = math.tan(min(max(beta_avg_from_tan, 1e-4), math.pi / 2 - 1e-4))
    if r1 <= 0.0 or r2 <= r1:
        return 0.0
    dtheta_rad = tan_beta * math.log(r2 / r1)
    return abs(math.degrees(dtheta_rad))


def _impeller_b2_over_d2(geometry) -> float:  # noqa: ANN001
    """Outlet blade-height to exit-diameter ratio b₂ / D₂."""
    d2 = 2.0 * float(geometry.impeller_outlet_radius)
    if d2 <= 0:
        return 0.0
    return float(geometry.blade_height_outlet) / d2


def _impeller_tip_clearance_mm(geometry) -> float:  # noqa: ANN001
    return float(geometry.tip_clearance) * 1e3


# =============================================================================
# Radial-turbine helpers
# =============================================================================


def _radial_blade_thickness_max_m(geometry) -> float:  # noqa: ANN001
    """Mirrors ``cascade.geometry.radial_turbine`` (cast-rotor floor)."""
    from cascade.manufacturability.limits import cast_blade_peak_thickness_m

    explicit = getattr(geometry, "blade_thickness_max", None)
    if explicit is not None:
        return float(explicit)
    return cast_blade_peak_thickness_m(geometry.rotor_inlet_radius)


def _radial_le_thickness_m(geometry) -> float:  # noqa: ANN001
    explicit = getattr(geometry, "leading_edge_thickness", None)
    if explicit is not None:
        return float(explicit)
    return 0.30 * _radial_blade_thickness_max_m(geometry)


def _radial_te_thickness_m(geometry) -> float:  # noqa: ANN001
    explicit = getattr(geometry, "trailing_edge_thickness", None)
    if explicit is not None:
        return float(explicit)
    return 0.30 * _radial_blade_thickness_max_m(geometry)


def _radial_root_fillet_m(geometry) -> float:  # noqa: ANN001
    explicit = getattr(geometry, "root_fillet", None)
    if explicit is not None:
        return float(explicit)
    return max(0.015 * float(geometry.rotor_outlet_radius_hub), 0.5e-3)


def _radial_tip_clearance_mm(geometry) -> float:  # noqa: ANN001
    return float(geometry.tip_clearance) * 1e3


# =============================================================================
# Axial-rotor helpers
# =============================================================================


def _axial_le_thickness_m(geometry) -> float:  # noqa: ANN001
    return float(getattr(geometry, "leading_edge_thickness", 0.25e-3))


def _axial_te_thickness_m(geometry) -> float:  # noqa: ANN001
    return float(getattr(geometry, "trailing_edge_thickness", 0.10e-3))


def _axial_tip_clearance_mm(geometry) -> float:  # noqa: ANN001
    return float(getattr(geometry, "tip_clearance", 0.3e-3)) * 1e3


def _axial_root_chord_m(geometry) -> float:  # noqa: ANN001
    return float(getattr(geometry, "root_chord", 0.0))


# =============================================================================
# Default rule sets
# =============================================================================


IMPELLER_RULES: tuple[ManufacturabilityRule, ...] = (
    ManufacturabilityRule(
        name="le_thickness_min",
        description="Leading-edge thickness at inlet (5-axis cutter minimum).",
        default_min=0.30e-3,
        units="m",
        severity="error",
        citation="AMRC 5-axis cutter survey 2019",
        measure=_impeller_le_thickness_m,
    ),
    ManufacturabilityRule(
        name="te_thickness_min",
        description="Trailing-edge thickness at outlet (typical 5-axis / EDM finish).",
        default_min=0.20e-3,
        units="m",
        severity="error",
        citation="AMRC 5-axis cutter survey 2019",
        measure=_impeller_te_thickness_m,
    ),
    ManufacturabilityRule(
        name="blade_root_fillet_min",
        description="Blade-root fillet radius (machinable corner radius).",
        default_min=0.5e-3,
        units="m",
        severity="warning",
        citation="Concepts NREC 2016 webinar",
        measure=_impeller_root_fillet_m,
    ),
    ManufacturabilityRule(
        name="tip_clearance_min",
        description="Tip-to-shroud cold clearance (microturbine minimum).",
        default_min=0.25,
        default_max=2.0,
        units="mm",
        severity="warning",
        citation="Boyce GT Handbook 4th ed. §3.4",
        measure=_impeller_tip_clearance_mm,
    ),
    ManufacturabilityRule(
        name="cutter_accessibility_min",
        description="Blade-to-blade throat width at inducer (≥ 2 mm cutter clearance).",
        default_min=2.0e-3,
        units="m",
        severity="error",
        citation="AMRC 5-axis cutter survey 2019",
        measure=_impeller_throat_width_m,
    ),
    ManufacturabilityRule(
        name="splitter_passage_min",
        description=(
            "Main-to-splitter passage width at the splitter LE "
            "(≥ 2 mm cutter clearance; half pitch at 50% chord)."
        ),
        default_min=2.0e-3,
        units="m",
        severity="error",
        citation="AMRC 5-axis cutter survey 2019",
        measure=_impeller_splitter_passage_m,
    ),
    ManufacturabilityRule(
        name="wrap_angle_max",
        description="Total blade wrap angle from LE to TE (machinability ceiling).",
        default_min=None,
        default_max=90.0,
        units="deg",
        severity="error",
        citation="Whitfield & Baines 1990 §6.5",
        measure=_impeller_wrap_angle_deg,
    ),
    ManufacturabilityRule(
        name="aspect_ratio_b2_over_d2",
        description="Outlet aspect b₂/D₂ — must lie in the typical centrifugal envelope.",
        default_min=0.015,
        default_max=0.15,
        units="-",
        severity="warning",
        citation="Aungier 2000 §6.4",
        measure=_impeller_b2_over_d2,
    ),
)


RADIAL_TURBINE_RULES: tuple[ManufacturabilityRule, ...] = (
    ManufacturabilityRule(
        name="le_thickness_min",
        description="LE thickness (cast Ni-base RIT minimum).",
        default_min=0.25e-3,
        units="m",
        severity="warning",
        citation="Whitfield & Baines 1990 §6.3",
        measure=_radial_le_thickness_m,
    ),
    ManufacturabilityRule(
        name="te_thickness_min",
        description="TE thickness (laser-trim minimum for cast RIT).",
        default_min=0.10e-3,
        units="m",
        severity="warning",
        citation="Whitfield & Baines 1990 §6.3",
        measure=_radial_te_thickness_m,
    ),
    ManufacturabilityRule(
        name="blade_root_fillet_min",
        description="Blade-root fillet radius (machinable corner radius).",
        default_min=0.5e-3,
        units="m",
        severity="warning",
        citation="Concepts NREC 2016 webinar",
        measure=_radial_root_fillet_m,
    ),
    ManufacturabilityRule(
        name="tip_clearance_min",
        description="Wheel-to-housing cold clearance.",
        default_min=0.15,
        default_max=2.0,
        units="mm",
        severity="warning",
        citation="Boyce GT Handbook 4th ed. §3.4",
        measure=_radial_tip_clearance_mm,
    ),
)


AXIAL_ROTOR_RULES: tuple[ManufacturabilityRule, ...] = (
    ManufacturabilityRule(
        name="le_thickness_min",
        description="LE thickness (machined axial blade minimum).",
        default_min=0.25e-3,
        units="m",
        severity="warning",
        citation="Whitfield & Baines 1990 §6.3",
        measure=_axial_le_thickness_m,
    ),
    ManufacturabilityRule(
        name="te_thickness_min",
        description="TE thickness (machined axial blade minimum).",
        default_min=0.10e-3,
        units="m",
        severity="warning",
        citation="Whitfield & Baines 1990 §6.3",
        measure=_axial_te_thickness_m,
    ),
    ManufacturabilityRule(
        name="tip_clearance_min",
        description="Tip-to-casing cold clearance (typical axial-rotor minimum).",
        default_min=0.30,
        default_max=2.5,
        units="mm",
        severity="warning",
        citation="Cumpsty 2003 §3.3",
        measure=_axial_tip_clearance_mm,
    ),
    ManufacturabilityRule(
        name="root_chord_min",
        description="Blade root chord (creep-limited at high T).",
        default_min=5.0e-3,
        units="m",
        severity="warning",
        citation="Cumpsty 2003 §11.3",
        measure=_axial_root_chord_m,
    ),
)


__all__ = [
    "AXIAL_ROTOR_RULES",
    "IMPELLER_RULES",
    "ManufacturabilityRule",
    "RADIAL_TURBINE_RULES",
    "Severity",
]
