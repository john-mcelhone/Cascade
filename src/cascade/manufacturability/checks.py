"""Per-machine-class manufacturability checkers.

Each ``check_*`` function:

1. Picks the default rule set for the geometry class.
2. Merges any per-call ``overrides`` (a ``{rule_name: threshold}`` mapping).
3. Walks the rule list, measures the geometry, and returns a
   :class:`ManufacturabilityReport`.

The shared driver lives in :func:`cascade.manufacturability.report.build_report`
so adding new machine classes is one tuple + one wrapper away.

Axial-rotor support is *interface-complete* but data-sparse: Cascade doesn't
have a canonical ``AxialRotorGeometry`` dataclass yet (ADAPT-031 / ADAPT-034
land that as part of the multi-stage axial work). The function accepts a
duck-typed object with optional ``leading_edge_thickness``,
``trailing_edge_thickness``, ``tip_clearance``, and ``root_chord`` fields,
so when the dataclass arrives the check will run with no further changes.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from cascade.manufacturability.report import (
    ManufacturabilityReport,
    build_report,
)
from cascade.manufacturability.rules import (
    AXIAL_ROTOR_RULES,
    IMPELLER_RULES,
    RADIAL_TURBINE_RULES,
)


def check_impeller(
    geometry: Any,
    overrides: Optional[Dict[str, float]] = None,
    *,
    name: Optional[str] = None,
) -> ManufacturabilityReport:
    """Run all impeller manufacturability rules against ``geometry``.

    Args:
        geometry: a :class:`cascade.meanline.CentrifugalCompressorGeometry`
            (or anything with the same field surface).
        overrides: per-rule overrides keyed by rule name. The override value
            replaces the binding edge of the rule's threshold (``default_min``
            for one-sided floor rules, ``default_max`` for ceiling rules).
        name: optional geometry-name label embedded in the report (e.g.
            "Capstone C30 inducer"). Defaults to the dataclass name.

    Returns:
        :class:`ManufacturabilityReport`.
    """
    geometry_name = name or _default_name(geometry, "impeller")
    return build_report(
        geometry_name=geometry_name,
        rules=IMPELLER_RULES,
        geometry=geometry,
        overrides=overrides,
    )


def check_radial_turbine(
    geometry: Any,
    overrides: Optional[Dict[str, float]] = None,
    *,
    name: Optional[str] = None,
) -> ManufacturabilityReport:
    """Run all radial-inflow turbine rotor manufacturability rules."""
    geometry_name = name or _default_name(geometry, "radial_turbine")
    return build_report(
        geometry_name=geometry_name,
        rules=RADIAL_TURBINE_RULES,
        geometry=geometry,
        overrides=overrides,
    )


def check_axial_rotor(
    geometry: Any,
    overrides: Optional[Dict[str, float]] = None,
    *,
    name: Optional[str] = None,
) -> ManufacturabilityReport:
    """Run all axial-rotor manufacturability rules.

    The axial-rotor dataclass is not yet first-class in Cascade (see module
    docstring); the check operates on any object with optional
    ``leading_edge_thickness`` / ``trailing_edge_thickness`` /
    ``tip_clearance`` / ``root_chord`` attributes.
    """
    geometry_name = name or _default_name(geometry, "axial_rotor")
    return build_report(
        geometry_name=geometry_name,
        rules=AXIAL_ROTOR_RULES,
        geometry=geometry,
        overrides=overrides,
    )


def _default_name(geometry: Any, fallback: str) -> str:
    cls = type(geometry).__name__
    return cls if cls != "object" else fallback


__all__ = [
    "check_axial_rotor",
    "check_impeller",
    "check_radial_turbine",
]
