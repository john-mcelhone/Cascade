"""Shared 5-axis machinability limits.

Single source of truth for the numeric floors that BOTH the mesh
generators (`cascade.geometry`) and the manufacturability rules
(`cascade.manufacturability.rules`) consume, so the geometry Cascade
produces and the geometry the rules grade can never drift apart.

The blade-thickness floor exists because the bell-curve thickness default
(1.5 % of the reference radius — KG-G-03) scales below what a 5-axis
cutter can leave standing on small wheels: at r₂ = 15 mm the proportional
rule gives a 0.07 mm leading edge, which would tear or chatter off during
milling. Thickness is a generator default, not a design variable, so the
generator floors it rather than emitting un-millable geometry.

References (see also rules.py module docstring):
- AMRC 5-axis turbomachinery cutter survey (2019) — 0.30 mm LE floor for
  milled Ti/Inconel impeller blades with 2 mm ball-nose cutters; thinner
  edges deflect and tear during finishing.
- Whitfield & Baines 1990 §6.3 — cast Ni-base radial-inflow rotors
  tolerate 0.25 mm LE (casting, not milling, sets the RIT floor).
"""

from __future__ import annotations

# Fraction of the peak (mid-chord) bell-curve thickness present at the
# leading edge — mirrors `blade_thickness_distribution` in
# `cascade.geometry._curves` (8 % LE band ≈ 30 % of peak at the LE station).
LE_THICKNESS_FRACTION_OF_PEAK = 0.30

# Minimum leading-edge thickness a standard 5-axis cell leaves standing
# on a MILLED impeller blade (AMRC 2019).
MIN_MILLED_LE_THICKNESS_M = 0.30e-3

# Minimum leading-edge thickness for a CAST radial-inflow turbine rotor
# (Whitfield & Baines 1990 §6.3).
MIN_CAST_LE_THICKNESS_M = 0.25e-3

# Smallest blade-to-blade passage a 2 mm ball-nose cutter can finish
# (cutter diameter + clearance — AMRC 2019).
MIN_CUTTER_PASSAGE_M = 2.0e-3


def machinable_blade_peak_thickness_m(r_ref_m: float) -> float:
    """Peak (mid-chord) blade thickness for a MILLED impeller.

    The proportional 1.5 %-of-reference-radius default, floored so the
    leading edge (≈30 % of peak) never falls below the 5-axis milling
    minimum. Used by `cascade.geometry.impeller` and by the
    manufacturability LE/TE estimates.
    """
    return max(
        0.015 * float(r_ref_m),
        MIN_MILLED_LE_THICKNESS_M / LE_THICKNESS_FRACTION_OF_PEAK,
    )


def cast_blade_peak_thickness_m(r_ref_m: float) -> float:
    """Peak blade thickness for a CAST radial-inflow turbine rotor."""
    return max(
        0.015 * float(r_ref_m),
        MIN_CAST_LE_THICKNESS_M / LE_THICKNESS_FRACTION_OF_PEAK,
    )
