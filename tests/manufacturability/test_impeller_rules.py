"""Regression tests for the centrifugal-impeller manufacturability layer.

The canonical "all-pass" geometry here is the Eckardt-Rotor-O impeller
(200 mm exit dia, 20 blades, 30° backsweep) — the largest of the validation
cases shipped with Cascade, and the closest match for a microturbine-class
machined impeller. A real Capstone C30 inducer (≈110 mm dia) needs explicit
``leading_edge_thickness`` / ``trailing_edge_thickness`` fields to clear the
default LE/TE floors; we cover that variant with a second test fixture that
supplies the explicit thicknesses.
"""

from __future__ import annotations

import math

import pytest

from cascade.manufacturability import (
    IMPELLER_RULES,
    check_impeller,
)
from cascade.manufacturability.rules import ManufacturabilityRule
from cascade.meanline.centrifugal_compressor import CentrifugalCompressorGeometry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _eckardt_rotor_o() -> CentrifugalCompressorGeometry:
    """Canonical Eckardt Rotor-O impeller — should pass all default rules."""
    return CentrifugalCompressorGeometry(
        inducer_hub_radius=0.018,
        inducer_tip_radius=0.050,
        impeller_outlet_radius=0.100,
        blade_height_outlet=0.012,
        blade_count=20,
        # 30° backsweep — π/6 in canonical from-axial convention.
        beta_2_metal_rad=math.pi / 6,
        tip_clearance=0.0005,  # 0.5 mm — comfortably above the 0.25 mm floor
    )


class _CapstoneLikeImpeller:
    """A Capstone C30-scale impeller with explicit thicknesses.

    Subclasses ``CentrifugalCompressorGeometry`` is impossible (it is a frozen
    dataclass) so we synthesise a duck-typed object that carries every field
    the rule helpers touch. The explicit ``leading_edge_thickness`` etc.
    attributes are picked up by ``rules._impeller_le_thickness_m`` (which
    prefers explicit fields over the bell-curve estimate).
    """

    def __init__(self) -> None:
        # ≈110 mm OD typical for a 30-kW microturbine compressor.
        self.inducer_hub_radius = 0.010
        self.inducer_tip_radius = 0.028
        self.impeller_outlet_radius = 0.055
        self.blade_height_outlet = 0.0050
        self.blade_count = 15
        self.beta_2_metal_rad = math.radians(30.0)
        self.tip_clearance = 0.00030  # 0.3 mm
        self.leading_edge_thickness = 0.45e-3  # 0.45 mm — passes 0.30 mm floor
        self.trailing_edge_thickness = 0.25e-3  # 0.25 mm — passes 0.20 mm floor
        self.root_fillet = 0.6e-3  # 0.6 mm — passes 0.5 mm floor
        self.inducer_tip_blade_metal_rad = math.radians(60.0)

    @property
    def inducer_mean_radius(self) -> float:
        return math.sqrt(
            0.5
            * (self.inducer_hub_radius ** 2 + self.inducer_tip_radius ** 2)
        )


def _bad_impeller_le_thin() -> CentrifugalCompressorGeometry:
    """An impeller scaled so the bell-curve LE thickness falls below 0.30 mm."""
    # impeller_outlet_radius = 0.030 m → t_max = 1.5 % × 0.030 = 0.45 mm
    # LE thickness = 30 % × t_max = 0.135 mm < 0.30 mm floor.
    return CentrifugalCompressorGeometry(
        inducer_hub_radius=0.006,
        inducer_tip_radius=0.015,
        impeller_outlet_radius=0.030,
        blade_height_outlet=0.0030,
        blade_count=12,
        beta_2_metal_rad=math.radians(30.0),
        tip_clearance=0.0003,
    )


# ---------------------------------------------------------------------------
# Pass / fail tests
# ---------------------------------------------------------------------------


class TestEckardtRotorOPasses:
    """The canonical large research impeller passes every default rule."""

    def test_no_violations(self) -> None:
        report = check_impeller(_eckardt_rotor_o())
        violation_names = [v.rule_name for v in report.violations]
        assert report.violations == [], (
            f"Eckardt Rotor-O should pass all default rules, but failed: "
            f"{violation_names}\n{report.format_text()}"
        )
        assert not report.has_violations
        assert report.critical_count == 0

    def test_all_rules_evaluated(self) -> None:
        report = check_impeller(_eckardt_rotor_o())
        # Every rule with a measure function should appear in passes.
        n_measurable = sum(1 for r in IMPELLER_RULES if r.measure is not None)
        assert len(report.passes) == n_measurable

    def test_capstone_like_with_explicit_thicknesses_passes(self) -> None:
        """A microturbine-scale impeller passes when LE/TE are stated."""
        report = check_impeller(
            _CapstoneLikeImpeller(),
            name="Capstone C30 impeller (synthetic)",
        )
        assert not report.has_violations, report.format_text()


class TestThinLEFails:
    """An impeller whose bell-curve LE falls below 0.30 mm flags a violation."""

    def test_le_violation_present(self) -> None:
        report = check_impeller(_bad_impeller_le_thin())
        names = [v.rule_name for v in report.violations]
        assert "le_thickness_min" in names

    def test_le_violation_direction(self) -> None:
        report = check_impeller(_bad_impeller_le_thin())
        le = next(v for v in report.violations
                  if v.rule_name == "le_thickness_min")
        assert le.direction == "below_min"
        assert le.measured < 0.30e-3
        assert le.threshold_min == pytest.approx(0.30e-3)

    def test_override_le_to_clear_violation(self) -> None:
        """Override the LE floor to 0.05 mm; the violation disappears."""
        report = check_impeller(
            _bad_impeller_le_thin(),
            overrides={"le_thickness_min": 0.05e-3},
        )
        names = [v.rule_name for v in report.violations]
        assert "le_thickness_min" not in names
        # The override is recorded.
        assert report.overrides_used["le_thickness_min"] == pytest.approx(0.05e-3)


class TestMultipleViolationsStack:
    """A small impeller violates LE, TE, and root-fillet rules."""

    def test_three_violations(self) -> None:
        # r_outlet 0.020 m → t_max = 0.30 mm → LE/TE = 0.090 mm (both fail).
        # r_hub_inducer 0.005 m → default fillet = max(1.5 % × 0.005,
        #   0.5e-3) = 0.5 mm (passes).
        # Construct one that fails LE + TE + cutter accessibility too:
        bad = CentrifugalCompressorGeometry(
            inducer_hub_radius=0.004,
            inducer_tip_radius=0.010,
            impeller_outlet_radius=0.020,
            blade_height_outlet=0.0020,
            blade_count=30,  # tight pitch → cutter accessibility fails
            beta_2_metal_rad=math.radians(30.0),
            tip_clearance=0.0003,
        )
        report = check_impeller(bad)
        names = {v.rule_name for v in report.violations}
        # LE & TE thicknesses both fall below their floors.
        assert "le_thickness_min" in names
        assert "te_thickness_min" in names
        # The 30-blade tight pitch should also fail cutter accessibility.
        assert "cutter_accessibility_min" in names
        # And the violations stack — at least three distinct rules fire.
        assert len(report.violations) >= 3
        assert report.has_violations

    def test_independent_overrides(self) -> None:
        """Overriding only one rule clears that rule but leaves others."""
        bad = CentrifugalCompressorGeometry(
            inducer_hub_radius=0.004,
            inducer_tip_radius=0.010,
            impeller_outlet_radius=0.020,
            blade_height_outlet=0.0020,
            blade_count=30,
            beta_2_metal_rad=math.radians(30.0),
            tip_clearance=0.0003,
        )
        report = check_impeller(
            bad,
            overrides={"le_thickness_min": 0.05e-3},
        )
        names = {v.rule_name for v in report.violations}
        assert "le_thickness_min" not in names
        # TE and cutter accessibility still flag.
        assert "te_thickness_min" in names
        assert "cutter_accessibility_min" in names


class TestReportShape:
    """Report JSON / format helpers behave."""

    def test_json_round_trip_shape(self) -> None:
        report = check_impeller(_eckardt_rotor_o())
        payload = report.to_json()
        assert payload["geometry_name"] == "CentrifugalCompressorGeometry"
        assert isinstance(payload["passes"], list)
        assert isinstance(payload["violations"], list)
        assert payload["has_violations"] is False
        assert payload["critical_count"] == 0
        # Every pass carries its citation and units.
        for p in payload["passes"]:
            assert "citation" in p and p["citation"] != ""
            assert "units" in p

    def test_format_text_runs(self) -> None:
        report = check_impeller(_bad_impeller_le_thin())
        text = report.format_text()
        assert "Manufacturability" in text
        assert "le_thickness_min" in text

    def test_rule_namespace_unique(self) -> None:
        """Sanity check: rule names are unique within a rule set."""
        names = [r.name for r in IMPELLER_RULES]
        assert len(names) == len(set(names))


class TestRuleDataclass:
    """The ``ManufacturabilityRule`` dataclass behaves like the spec demands."""

    def test_frozen(self) -> None:
        rule = IMPELLER_RULES[0]
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            rule.default_min = 0.0  # type: ignore[misc]

    def test_has_citation(self) -> None:
        for rule in IMPELLER_RULES:
            assert isinstance(rule, ManufacturabilityRule)
            assert rule.citation != "", (
                f"Rule {rule.name!r} is missing a citation"
            )
