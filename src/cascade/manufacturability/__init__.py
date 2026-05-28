"""Manufacturability check layer (ADAPT-032).

The Concepts NREC review found that Cascade freely generates geometries the
machine shop refuses to cut: paper-thin leading edges, sub-fillet root radii,
splitter pitches narrower than the smallest 5-axis cutter. This module is the
guardrail.

A :class:`ManufacturabilityReport` is the artefact: a stratified list of rule
checks (``passes`` and ``violations``) plus any user overrides applied. The
default rules live in :mod:`cascade.manufacturability.rules` and cite the
trade-press source for the floor / ceiling we apply.

The three machine-class checks are:

- :func:`check_impeller` for ``CentrifugalCompressorGeometry``
- :func:`check_radial_turbine` for ``RadialTurbineGeometry``
- :func:`check_axial_rotor` placeholder (no canonical Cascade axial-rotor
  dataclass yet; see :mod:`cascade.manufacturability.checks` docstring).

Usage:

    >>> from cascade.manufacturability import check_impeller
    >>> from cascade.meanline import CentrifugalCompressorGeometry
    >>> g = CentrifugalCompressorGeometry(
    ...     inducer_hub_radius=0.018, inducer_tip_radius=0.050,
    ...     impeller_outlet_radius=0.100, blade_height_outlet=0.012,
    ...     blade_count=20, beta_2_metal_rad=1.047, tip_clearance=0.0005)
    >>> report = check_impeller(g)
    >>> report.has_violations
    False

To override a rule for a specific project, pass an ``overrides`` mapping:

    >>> report = check_impeller(g, overrides={"le_thickness_min": 0.05e-3})

The override is **per call**, so the report can record exactly which rules
fired with non-default thresholds.
"""

from __future__ import annotations

from cascade.manufacturability.checks import (
    check_axial_rotor,
    check_impeller,
    check_radial_turbine,
)
from cascade.manufacturability.report import (
    CheckResult,
    ManufacturabilityReport,
    Violation,
)
from cascade.manufacturability.rules import (
    AXIAL_ROTOR_RULES,
    IMPELLER_RULES,
    RADIAL_TURBINE_RULES,
    ManufacturabilityRule,
)

__all__ = [
    "AXIAL_ROTOR_RULES",
    "CheckResult",
    "IMPELLER_RULES",
    "ManufacturabilityRule",
    "ManufacturabilityReport",
    "RADIAL_TURBINE_RULES",
    "Violation",
    "check_axial_rotor",
    "check_impeller",
    "check_radial_turbine",
]
