"""Regression tests for the centrifugal-impeller manufacturability layer.

The canonical "all-pass" geometry here is the Eckardt-Rotor-O impeller
(200 mm exit dia, 20 blades, 30° backsweep) — the largest of the validation
cases shipped with Cascade, and the closest match for a microturbine-class
machined impeller.

Default (generator) thicknesses are FLOORED at the 5-axis machinable
minimum (``manufacturability.limits``), so the bell-curve LE/TE estimates
can no longer violate their rules by construction — the LE/TE rules fire
only for explicit, user-supplied thicknesses below the floor. Tool-access
rules (inducer throat, main-to-splitter passage) are the binding limits
for small wheels and are exercised directly.
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


def _bad_impeller_le_thin() -> "_CapstoneLikeImpeller":
    """An impeller whose EXPLICIT LE thickness falls below the 0.30 mm floor.

    The generator's bell-curve default is floored at the machinable minimum
    (``machinable_blade_peak_thickness_m``), so only an explicit
    user-supplied thickness can undercut the rule.
    """
    bad = _CapstoneLikeImpeller()
    bad.leading_edge_thickness = 0.10e-3  # 0.10 mm — well below 0.30 mm
    return bad


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
        # LE thickness below the milling floor is a hard refusal, not a
        # shop-practice warning.
        assert le.severity == "error"

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
    """Explicit thin edges + tight pitch stack independent violations."""

    @staticmethod
    def _bad() -> "_CapstoneLikeImpeller":
        bad = _CapstoneLikeImpeller()
        bad.leading_edge_thickness = 0.10e-3   # below 0.30 mm floor
        bad.trailing_edge_thickness = 0.05e-3  # below 0.20 mm floor
        # Tight enough that even the inducer full-pitch throat (pitch −
        # LE thickness, ~1.7 mm at Z=72 on this ~21 mm mean radius) falls
        # below the 2 mm cutter floor — not just the splitter passage.
        bad.blade_count = 72
        return bad

    def test_violations_stack(self) -> None:
        report = check_impeller(self._bad())
        names = {v.rule_name for v in report.violations}
        # LE & TE thicknesses both fall below their floors.
        assert "le_thickness_min" in names
        assert "te_thickness_min" in names
        # The tight pitch fails both tool-access rules.
        assert "cutter_accessibility_min" in names
        assert "splitter_passage_min" in names
        # And the violations stack — at least four distinct rules fire.
        assert len(report.violations) >= 4
        assert report.has_violations
        assert report.critical_count >= 4  # all of these are severity=error

    def test_independent_overrides(self) -> None:
        """Overriding only one rule clears that rule but leaves others."""
        report = check_impeller(
            self._bad(),
            overrides={"le_thickness_min": 0.05e-3},
        )
        names = {v.rule_name for v in report.violations}
        assert "le_thickness_min" not in names
        # TE and the tool-access rules still flag.
        assert "te_thickness_min" in names
        assert "cutter_accessibility_min" in names
        assert "splitter_passage_min" in names


class TestThicknessFloorByConstruction:
    """Generator-default thicknesses are floored at the machinable minimum."""

    def test_small_wheel_le_te_pass_by_construction(self) -> None:
        # r2 = 15 mm: the proportional rule alone would give a 0.07 mm LE.
        small = CentrifugalCompressorGeometry(
            inducer_hub_radius=0.0034,
            inducer_tip_radius=0.0105,
            impeller_outlet_radius=0.015,
            blade_height_outlet=0.0020,
            blade_count=8,
            beta_2_metal_rad=math.radians(30.0),
            tip_clearance=0.0003,
        )
        report = check_impeller(small)
        names = {v.rule_name for v in report.violations}
        assert "le_thickness_min" not in names
        assert "te_thickness_min" not in names

    def test_rules_and_mesh_share_the_floor(self) -> None:
        """The rules' thickness estimate IS the mesh generator's thickness."""
        from cascade.manufacturability.limits import (
            machinable_blade_peak_thickness_m,
        )
        from cascade.manufacturability.rules import (
            _impeller_blade_thickness_max_m,
        )

        small = CentrifugalCompressorGeometry(
            inducer_hub_radius=0.0034,
            inducer_tip_radius=0.0105,
            impeller_outlet_radius=0.015,
            blade_height_outlet=0.0020,
            blade_count=8,
            beta_2_metal_rad=math.radians(30.0),
            tip_clearance=0.0003,
        )
        assert _impeller_blade_thickness_max_m(small) == pytest.approx(
            machinable_blade_peak_thickness_m(0.015)
        )
        # The floor binds for small wheels (1.5% rule would give 0.225 mm).
        assert machinable_blade_peak_thickness_m(0.015) == pytest.approx(1.0e-3)
        # ...and yields exactly the 0.30 mm LE minimum.
        assert 0.30 * machinable_blade_peak_thickness_m(0.015) == pytest.approx(
            0.30e-3
        )
        # The proportional rule still governs large wheels.
        assert machinable_blade_peak_thickness_m(0.100) == pytest.approx(1.5e-3)


class TestSplitterPassageRule:
    """Main-to-splitter passage gates blade count on small wheels."""

    @staticmethod
    def _wheel(r2_m: float, blade_count: int) -> CentrifugalCompressorGeometry:
        # Eckardt-proportioned wheel at the requested scale (the same
        # scaling the explore sweep uses).
        scale = r2_m / 0.200
        return CentrifugalCompressorGeometry(
            inducer_hub_radius=0.045 * scale,
            inducer_tip_radius=0.140 * scale,
            impeller_outlet_radius=r2_m,
            blade_height_outlet=0.026 * scale,
            blade_count=blade_count,
            beta_2_metal_rad=math.pi / 6,
            tip_clearance=0.0003,
        )

    def test_small_wheel_high_blade_count_fails(self) -> None:
        report = check_impeller(self._wheel(0.015, 18))
        names = {v.rule_name for v in report.violations}
        assert "splitter_passage_min" in names

    def test_small_wheel_low_blade_count_passes(self) -> None:
        report = check_impeller(self._wheel(0.015, 10))
        names = {v.rule_name for v in report.violations}
        assert "splitter_passage_min" not in names

    def test_large_wheel_unconstrained(self) -> None:
        report = check_impeller(self._wheel(0.045, 18))
        names = {v.rule_name for v in report.violations}
        assert "splitter_passage_min" not in names

    def test_splitter_passage_tighter_than_inducer_throat(self) -> None:
        """For the swept design space the splitter passage is the binding
        tool-access dimension — the reason the rule exists."""
        from cascade.manufacturability.rules import (
            _impeller_splitter_passage_m,
            _impeller_throat_width_m,
        )

        wheel = self._wheel(0.020, 16)
        assert _impeller_splitter_passage_m(wheel) < _impeller_throat_width_m(
            wheel
        )


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
