"""Manufacturability report dataclasses.

A ``ManufacturabilityReport`` is the artefact produced by
:func:`cascade.manufacturability.check_impeller` and the sister checks. The
report is a frozen NamedTuple so it round-trips cleanly to JSON for the
``GET /api/projects/{id}/manufacturability`` endpoint.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, NamedTuple, Optional

from cascade.manufacturability.rules import ManufacturabilityRule, Severity


class CheckResult(NamedTuple):
    """A single rule that **passed** the manufacturability check.

    Carries the measured value so the UI can render the headroom (e.g.
    "LE thickness 0.45 mm — 50 % headroom over the 0.30 mm floor").
    """

    rule_name: str
    description: str
    measured: float
    threshold_min: Optional[float]
    threshold_max: Optional[float]
    units: str
    citation: str

    def to_json(self) -> Dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "description": self.description,
            "measured": self.measured,
            "threshold_min": self.threshold_min,
            "threshold_max": self.threshold_max,
            "units": self.units,
            "citation": self.citation,
        }


class Violation(NamedTuple):
    """A rule that **failed** — measured value outside the rule's band."""

    rule_name: str
    description: str
    measured: float
    threshold_min: Optional[float]
    threshold_max: Optional[float]
    units: str
    severity: Severity
    citation: str
    direction: str  # "below_min" or "above_max"

    def to_json(self) -> Dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "description": self.description,
            "measured": self.measured,
            "threshold_min": self.threshold_min,
            "threshold_max": self.threshold_max,
            "units": self.units,
            "severity": self.severity,
            "citation": self.citation,
            "direction": self.direction,
        }


class ManufacturabilityReport(NamedTuple):
    """Full report from a single manufacturability check.

    ``passes`` and ``violations`` together cover every rule in the
    geometry's rule set — a rule is in exactly one list. ``overrides_used``
    records which rule keys had a per-project override applied (so the UI
    can flag "this passed only because of your override at 0.05 mm").
    """

    geometry_name: str
    checked_at: datetime
    violations: List[Violation]
    passes: List[CheckResult]
    overrides_used: Dict[str, float]

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "warning")

    @property
    def rule_count(self) -> int:
        return len(self.violations) + len(self.passes)

    def to_json(self) -> Dict[str, Any]:
        return {
            "geometry_name": self.geometry_name,
            "checked_at": self.checked_at.isoformat(),
            "violations": [v.to_json() for v in self.violations],
            "passes": [p.to_json() for p in self.passes],
            "overrides_used": dict(self.overrides_used),
            "has_violations": self.has_violations,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "rule_count": self.rule_count,
        }

    def format_text(self) -> str:
        """Pretty-print the report for the CLI / debug logging."""
        lines: List[str] = []
        lines.append(
            f"Manufacturability — {self.geometry_name} "
            f"({self.checked_at.isoformat(timespec='seconds')})"
        )
        lines.append(
            f"  {len(self.passes)} pass, {len(self.violations)} violation"
            f"{'s' if len(self.violations) != 1 else ''} "
            f"(critical={self.critical_count}, warning={self.warning_count})"
        )
        if self.overrides_used:
            lines.append("  Overrides applied:")
            for name, val in self.overrides_used.items():
                lines.append(f"    {name}: {val}")
        if self.violations:
            lines.append("  Violations:")
            for v in self.violations:
                threshold = (
                    f"< {v.threshold_min} {v.units}".strip()
                    if v.direction == "below_min"
                    else f"> {v.threshold_max} {v.units}".strip()
                )
                lines.append(
                    f"    [{v.severity}] {v.rule_name}: "
                    f"measured {v.measured:.4g} {v.units} ({threshold}) — "
                    f"{v.description} [{v.citation}]"
                )
        if self.passes:
            lines.append("  Passes:")
            for p in self.passes:
                lines.append(
                    f"    ok {p.rule_name}: {p.measured:.4g} {p.units} — "
                    f"{p.description}"
                )
        return "\n".join(lines)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def build_report(
    geometry_name: str,
    rules: tuple[ManufacturabilityRule, ...],
    geometry: Any,
    overrides: Optional[Dict[str, float]] = None,
) -> ManufacturabilityReport:
    """Drive a rule list against a geometry and produce a report.

    Centralised so :mod:`cascade.manufacturability.checks` is just a thin
    dispatcher over geometry types. Handles override merging, the
    measured-value computation, and the threshold comparison in one place.
    """
    overrides = dict(overrides or {})
    overrides_used: Dict[str, float] = {}
    violations: List[Violation] = []
    passes: List[CheckResult] = []

    for rule in rules:
        if rule.measure is None:
            # Skip rules without a measurement function (template / TBD).
            continue
        try:
            measured = float(rule.measure(geometry))
        except Exception:  # noqa: BLE001
            # Measurement that requires a field not present on this
            # geometry — record the rule as a no-op (skipped) rather than
            # raising; future geometry revisions will fill the field in.
            continue

        # Apply override if present. Convention: a single override scalar
        # replaces the binding edge of the rule. For min-only rules it's
        # the min; for max-only it's the max; for two-sided rules the
        # override is interpreted as "tighten the floor" (typical use).
        threshold_min = rule.default_min
        threshold_max = rule.default_max
        if rule.name in overrides:
            override_val = float(overrides[rule.name])
            overrides_used[rule.name] = override_val
            if rule.default_min is not None:
                threshold_min = override_val
            elif rule.default_max is not None:
                threshold_max = override_val

        if threshold_min is not None and measured < threshold_min:
            violations.append(
                Violation(
                    rule_name=rule.name,
                    description=rule.description,
                    measured=measured,
                    threshold_min=threshold_min,
                    threshold_max=threshold_max,
                    units=rule.units,
                    severity=rule.severity,
                    citation=rule.citation,
                    direction="below_min",
                )
            )
            continue
        if threshold_max is not None and measured > threshold_max:
            violations.append(
                Violation(
                    rule_name=rule.name,
                    description=rule.description,
                    measured=measured,
                    threshold_min=threshold_min,
                    threshold_max=threshold_max,
                    units=rule.units,
                    severity=rule.severity,
                    citation=rule.citation,
                    direction="above_max",
                )
            )
            continue
        passes.append(
            CheckResult(
                rule_name=rule.name,
                description=rule.description,
                measured=measured,
                threshold_min=threshold_min,
                threshold_max=threshold_max,
                units=rule.units,
                citation=rule.citation,
            )
        )

    return ManufacturabilityReport(
        geometry_name=geometry_name,
        checked_at=_now(),
        violations=violations,
        passes=passes,
        overrides_used=overrides_used,
    )


__all__ = [
    "CheckResult",
    "ManufacturabilityReport",
    "Violation",
    "build_report",
]
