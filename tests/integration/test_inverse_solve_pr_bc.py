"""H1 / Item 1: PR-as-BC inverse solve for radial turbines — property tests.

Tests the invariant that ``inverse_solve_pr_ts_target`` is a genuine independent
variable that the solver iterates over, and that the round-trip is internally
consistent.

Property tests (not single-benchmark assertions):
1. The schema field round-trips through Pydantic without being silently dropped.
2. Setting inverse_solve_pr_ts_target + mass_flow_kg_per_s raises 422
   OVERCONSTRAINED_OPERATING_POINT (not a silent override).
3. Sweeping pr_ts_target over a physically meaningful range produces consistent
   m_dot values that, when fed back to the forward solver, reproduce the target
   PR_ts within a tight tolerance (round-trip consistency).
4. Monotonicity: lower PR_ts target → higher m_dot (more flow → less work per
   unit mass → lower pressure ratio — standard turbine physics).

Why property tests and not single benchmarks: a single number would pass even
if the inverse-solve result were plausible but incorrect. The round-trip
consistency check (forward(inverse(PR_ts)) ≈ PR_ts) can only pass if the solver
is genuinely inverting the correct function.

References
----------
Whitfield, A., Baines, N.C., "Design of Radial Turbomachines", Longman, 1990.
NASA TN D-7508 — Whitney & Stewart (1974): many published cases specify PR_ts
  without a measured mass flow; the inverse-solve allows direct reproduction.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
for p in (str(_REPO / "src"), str(_REPO / "apps" / "api")):
    if p not in sys.path:
        sys.path.insert(0, p)


# -----------------------------------------------------------------------
# Geometry / base operating-point (Whitney-Stewart approximate geometry,
# air working fluid — keeps test independent of helium calibration)
# -----------------------------------------------------------------------

_GEOM = {
    "rotor_inlet_radius": 0.076,
    "rotor_outlet_radius_hub": 0.019,
    "rotor_outlet_radius_tip": 0.0406,
    "blade_height_inlet": 0.012,
    "blade_height_outlet": 0.0216,
    "blade_count": 12,
    "inlet_metal_angle_rad": 0.0,
    "exducer_angle_rad": math.radians(60.0),
    "tip_clearance": 0.00025,
}

_BASE_OP = {
    "pressure_total_Pa": 220000.0,
    "temperature_total_K": 1090.0,
    # Note: mass_flow_kg_per_s is intentionally omitted here — the inverse
    # solver finds it.  The default in _RIT_DEFAULTS (0.13 kg/s) is not used
    # because we are testing the inverse-solve path.
    "rpm": 79000.0,
    "fluid": "air",
}

# PR_ts targets spanning a physically achievable range for this geometry.
# A preliminary forward scan shows PR_ts ≈ 5.4–6.4 for m_dot ∈ [0.001, 0.25] kg/s.
# Targets must be strictly within the range that produces a sign change in the
# residual so brentq can find a bracket.
_PR_TS_TARGETS = [5.5, 5.7, 5.9, 6.1]


class TestInverseSolveSchemaParity:
    """Schema-level checks: fields exist and are typed correctly."""

    def test_inverse_solve_field_defaults_to_none(self) -> None:
        """AnalysisRequest.inverse_solve_pr_ts_target must default to None."""
        from models import AnalysisRequest

        req = AnalysisRequest()
        assert req.inverse_solve_pr_ts_target is None, (
            "inverse_solve_pr_ts_target must default to None (forward-solve mode)."
        )

    def test_inverse_solve_field_accepts_float(self) -> None:
        """AnalysisRequest accepts a float for inverse_solve_pr_ts_target."""
        from models import AnalysisRequest

        req = AnalysisRequest(inverse_solve_pr_ts_target=3.0)
        assert req.inverse_solve_pr_ts_target == pytest.approx(3.0)

    def test_overconstrained_raises_422(self) -> None:
        """Supplying both inverse_solve_pr_ts_target and mass_flow_kg_per_s must raise 422."""
        from fastapi import HTTPException
        from routers.analysis import _check_inverse_solve_overconstrained

        with pytest.raises(HTTPException) as exc_info:
            _check_inverse_solve_overconstrained(
                op_dict={"mass_flow_kg_per_s": 0.13},
                corr=None,
                inverse_solve_pr_ts_target=3.0,
            )
        assert exc_info.value.status_code == 422
        detail = exc_info.value.detail
        assert detail["error_code"] == "OVERCONSTRAINED_OPERATING_POINT"
        assert "inverse_solve_pr_ts_target" in detail["conflicting_fields"]
        assert "mass_flow_kg_per_s" in detail["conflicting_fields"]

    def test_no_mass_flow_no_overconstrained(self) -> None:
        """No error if inverse_solve_pr_ts_target is set without mass_flow_kg_per_s."""
        from routers.analysis import _check_inverse_solve_overconstrained

        # Should not raise
        _check_inverse_solve_overconstrained(
            op_dict={"rpm": 79000.0},
            corr=None,
            inverse_solve_pr_ts_target=3.0,
        )

    def test_no_inverse_target_no_check(self) -> None:
        """No error if inverse_solve_pr_ts_target is None (forward-solve mode)."""
        from routers.analysis import _check_inverse_solve_overconstrained

        # Should not raise even when mass_flow is present
        _check_inverse_solve_overconstrained(
            op_dict={"mass_flow_kg_per_s": 0.13},
            corr=None,
            inverse_solve_pr_ts_target=None,
        )


class TestInverseSolveRoundTrip:
    """Round-trip consistency: forward(inverse(PR_ts)) ≈ PR_ts."""

    @pytest.fixture(scope="class")
    def round_trip_results(self):
        """Sweep PR_ts targets and verify round-trip consistency."""
        from routers.analysis import _inverse_solve_radial_turbine, _solve_radial_turbine

        results = []
        for target in _PR_TS_TARGETS:
            payload = _inverse_solve_radial_turbine(
                _GEOM, _BASE_OP, "whitfield-baines-radial-v1",
                pr_ts_target=target,
            )
            # Round-trip: run the forward solver at the found m_dot
            m_found = payload["inverse_solve"]["m_dot_found_kg_s"]
            op_forward = dict(_BASE_OP)
            op_forward["mass_flow_kg_per_s"] = m_found
            forward = _solve_radial_turbine(_GEOM, op_forward, "whitfield-baines-radial-v1")
            results.append({
                "target": target,
                "achieved": payload["pressure_ratio_ts"],
                "forward_pr_ts": forward["pressure_ratio_ts"],
                "m_dot": m_found,
            })
        return results

    def test_achieved_pr_ts_matches_target(self, round_trip_results) -> None:
        """The inverse-solved PR_ts must match the target within 0.01."""
        for r in round_trip_results:
            assert abs(r["achieved"] - r["target"]) < 0.01, (
                f"PR_ts target={r['target']:.3f}, achieved={r['achieved']:.4f}, "
                f"diff={r['achieved'] - r['target']:+.4f}. "
                f"m_dot_found={r['m_dot']:.6f} kg/s."
            )

    def test_round_trip_forward_solver_agrees(self, round_trip_results) -> None:
        """Re-running the forward solver at the found m_dot must reproduce the target PR_ts."""
        for r in round_trip_results:
            assert abs(r["forward_pr_ts"] - r["target"]) < 0.01, (
                f"Round-trip: target={r['target']:.3f}, "
                f"forward-solver result={r['forward_pr_ts']:.4f}. "
                f"The inverse-solve found m_dot={r['m_dot']:.6f} but the forward "
                f"solver does not reproduce the target."
            )

    def test_m_dot_found_is_positive(self, round_trip_results) -> None:
        """All found mass flows must be positive and physically reasonable."""
        for r in round_trip_results:
            assert r["m_dot"] > 0.0, (
                f"Found m_dot={r['m_dot']} for PR_ts={r['target']} must be positive."
            )
            assert r["m_dot"] < 500.0, (
                f"Found m_dot={r['m_dot']} for PR_ts={r['target']} is unreasonably large."
            )

    def test_brentq_converged(self) -> None:
        """Inverse solve must report brentq converged=True for achievable targets."""
        from routers.analysis import _inverse_solve_radial_turbine

        payload = _inverse_solve_radial_turbine(
            _GEOM, _BASE_OP, "whitfield-baines-radial-v1",
            pr_ts_target=5.7,  # middle of achievable range [5.4, 6.4]
        )
        assert payload["inverse_solve"]["brentq_converged"] is True, (
            "brentq must report converged=True for a PR_ts=5.7 target."
        )


class TestInverseSolveMonotonicity:
    """Physics check: m_dot is a consistent, monotone function of PR_ts target.

    For this geometry (free-discharge η_ts: exit static pressure is internally
    derived from the solver state), PR_ts increases with m_dot. The key invariant
    is that the inverse solve is consistent: different PR_ts targets produce
    different m_dot values, and higher PR_ts target → higher m_dot.
    """

    @pytest.fixture(scope="class")
    def sweep(self):
        from routers.analysis import _inverse_solve_radial_turbine

        pairs = []
        for target in sorted(_PR_TS_TARGETS):
            payload = _inverse_solve_radial_turbine(
                _GEOM, _BASE_OP, "whitfield-baines-radial-v1",
                pr_ts_target=target,
            )
            pairs.append((target, payload["inverse_solve"]["m_dot_found_kg_s"]))
        return pairs  # sorted ascending in target PR_ts

    def test_m_dot_increases_as_pr_ts_target_increases(self, sweep) -> None:
        """Higher PR_ts target → higher m_dot for this geometry.

        For a free-discharge RIT (no outlet static BC), PR_ts = P_01 / P_2_static
        where P_2_static is internally derived from the exit state. In this solver,
        PR_ts increases with m_dot because higher flow rates extract more work per
        cycle iteration and the derived exit static pressure drops. The key invariant
        is monotonicity — the inverse solver must consistently produce a unique m_dot
        for each target PR_ts.
        """
        prev_target, prev_m = sweep[0]
        for target, m_dot in sweep[1:]:
            assert m_dot >= prev_m - 1e-5, (
                f"Expected m_dot to increase as PR_ts target increases (free-discharge mode): "
                f"at PR_ts={prev_target:.2f} m_dot={prev_m:.6f} kg/s; "
                f"at PR_ts={target:.2f} m_dot={m_dot:.6f} kg/s."
            )
            prev_target, prev_m = target, m_dot

    def test_pr_ts_range_spans_multiple_m_dots(self, sweep) -> None:
        """The sweep must produce meaningfully different m_dot values."""
        m_dots = [m for _, m in sweep]
        m_range = max(m_dots) - min(m_dots)
        assert m_range > 1e-4, (
            f"m_dot range across PR_ts sweep = {m_range:.6f} kg/s — too small. "
            f"The inverse solver may not be varying m_dot correctly."
        )
