"""H1 / Item 2: wiesner_calibration_scale API exposure — property tests.

Tests that ``wiesner_calibration_scale`` is a genuine independent variable
that actually reaches the solver (WiesnerSlip.calibration_scale), and that
the effect is physically consistent (higher calibration_scale → higher slip
factor → more work → higher PR_tt).

Property tests (not single-benchmark assertions):
1. Schema field round-trips through Pydantic without being silently dropped.
2. The flag produces a result that differs from the default (proves it is
   consumed, not silently ignored).
3. Monotonicity: higher wiesner_calibration_scale → higher PR_tt (more slip →
   more Euler work → higher pressure rise).
4. The result at calibration_scale=1.0 matches the default (None) result exactly
   (proves the default is consistently 1.0).

Why property tests: a single calibration-scale value would pass even if the
flag were silently ignored (the solver would return a plausible result). The
monotonicity invariant can only pass if the flag actually flows through to the
slip factor computation.

References
----------
Wiesner, F.J., 1967, "A Review of Slip Factors for Centrifugal Impellers",
  Trans. ASME J. Eng. Power, 89(4), pp. 558–566.
Came, P.R., Robinson, C.J., 1999, "Centrifugal compressor design", Proc.
  IMechE Part C, 213(2), pp. 139–155, §3.2 — calibration for back-swept wheels.
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
# Geometry / operating-point (Eckardt Rotor A approximate defaults, air,
# ISA inlet — matches _CC_DEFAULTS in analysis router).
# -----------------------------------------------------------------------

_GEOM = {
    "inducer_hub_radius": 0.045,
    "inducer_tip_radius": 0.140,
    "impeller_outlet_radius": 0.200,
    "blade_height_outlet": 0.026,
    "blade_count": 20,
    "beta_2_metal_rad": math.pi / 6,   # 30° back-sweep
    "tip_clearance": 0.0003,
}

_OP = {
    "pressure_total_Pa": 101325.0,
    "temperature_total_K": 288.15,
    "mass_flow_kg_per_s": 5.31,
    "rpm": 14000.0,
    "fluid": "air",
}

# Calibration-scale sweep including the default (1.0) and the Came-Robinson
# recommended value for Eckardt-class wheels (1.05).
_CALIBRATION_SCALES = [1.0, 1.02, 1.05, 1.10]


class TestWiesnerCalibrationSchemaParity:
    """Schema-level checks: fields exist and are typed correctly."""

    def test_wiesner_calibration_scale_defaults_to_none(self) -> None:
        """AnalysisRequest.wiesner_calibration_scale must default to None."""
        from models import AnalysisRequest

        req = AnalysisRequest()
        assert req.wiesner_calibration_scale is None, (
            "wiesner_calibration_scale must default to None "
            "(production default: calibration_scale=1.0 inside WiesnerSlip)."
        )

    def test_wiesner_calibration_scale_accepts_float(self) -> None:
        """AnalysisRequest accepts a float for wiesner_calibration_scale."""
        from models import AnalysisRequest

        req = AnalysisRequest(
            machine_class="centrifugal_compressor",
            wiesner_calibration_scale=1.05,
        )
        assert req.wiesner_calibration_scale == pytest.approx(1.05)


class TestWiesnerCalibrationIsPlumbedThrough:
    """Verify wiesner_calibration_scale actually reaches the WiesnerSlip object."""

    def test_calibration_scale_1_05_differs_from_default(self) -> None:
        """PR_tt with calibration_scale=1.05 must differ from calibration_scale=None.

        If the flag were silently dropped, both calls would produce identical PR_tt.
        The fact that they differ proves the flag is consumed.
        """
        from routers.analysis import _solve_centrifugal_compressor

        result_default = _solve_centrifugal_compressor(
            _GEOM, _OP, "aungier-centrifugal-v1",
            wiesner_calibration_scale=None,
        )
        result_calibrated = _solve_centrifugal_compressor(
            _GEOM, _OP, "aungier-centrifugal-v1",
            wiesner_calibration_scale=1.05,
        )
        pr_default = result_default["pressure_ratio_tt"]
        pr_calibrated = result_calibrated["pressure_ratio_tt"]
        assert abs(pr_calibrated - pr_default) > 0.01, (
            f"PR_tt with default={pr_default:.4f}; "
            f"PR_tt with scale=1.05={pr_calibrated:.4f}. "
            f"Values are too close — wiesner_calibration_scale may be silently dropped."
        )

    def test_calibration_scale_1_0_matches_default(self) -> None:
        """calibration_scale=1.0 must produce the same result as None (the default).

        This proves the default really is 1.0.
        """
        from routers.analysis import _solve_centrifugal_compressor

        result_none = _solve_centrifugal_compressor(
            _GEOM, _OP, "aungier-centrifugal-v1",
            wiesner_calibration_scale=None,
        )
        result_one = _solve_centrifugal_compressor(
            _GEOM, _OP, "aungier-centrifugal-v1",
            wiesner_calibration_scale=1.0,
        )
        assert abs(result_none["pressure_ratio_tt"] - result_one["pressure_ratio_tt"]) < 1e-9, (
            f"calibration_scale=None ({result_none['pressure_ratio_tt']:.6f}) should "
            f"match calibration_scale=1.0 ({result_one['pressure_ratio_tt']:.6f})."
        )


class TestWiesnerCalibrationMonotonicity:
    """Physics check: higher calibration_scale → higher PR_tt (more slip = more work)."""

    @pytest.fixture(scope="class")
    def pr_tt_vs_scale(self):
        """Sweep calibration scales and collect PR_tt values."""
        from routers.analysis import _solve_centrifugal_compressor

        pairs = []
        for scale in sorted(_CALIBRATION_SCALES):
            result = _solve_centrifugal_compressor(
                _GEOM, _OP, "aungier-centrifugal-v1",
                wiesner_calibration_scale=scale,
            )
            pairs.append((scale, result["pressure_ratio_tt"]))
        return pairs  # sorted ascending in calibration_scale

    def test_pr_tt_increases_with_calibration_scale(self, pr_tt_vs_scale) -> None:
        """Higher Wiesner calibration scale → higher PR_tt.

        Physical reasoning: higher calibration_scale → higher slip factor σ →
        higher tangential velocity V_θ₂ = σ U₂ - ... → more Euler work →
        more pressure rise.
        """
        prev_scale, prev_pr = pr_tt_vs_scale[0]
        for scale, pr in pr_tt_vs_scale[1:]:
            assert pr >= prev_pr - 1e-6, (
                f"PR_tt should increase as calibration_scale increases: "
                f"scale={prev_scale:.2f} → PR_tt={prev_pr:.4f}; "
                f"scale={scale:.2f} → PR_tt={pr:.4f}. "
                f"The flag may not be reaching the slip factor."
            )
            prev_scale, prev_pr = scale, pr

    def test_pr_tt_range_is_non_trivial(self, pr_tt_vs_scale) -> None:
        """PR_tt must vary meaningfully across the sweep."""
        pr_values = [pr for _, pr in pr_tt_vs_scale]
        pr_range = max(pr_values) - min(pr_values)
        assert pr_range > 0.01, (
            f"PR_tt range across calibration-scale sweep = {pr_range:.4f} — too small. "
            f"The flag may not be reaching the solver."
        )

    def test_all_pr_tt_values_are_physical(self, pr_tt_vs_scale) -> None:
        """All PR_tt values must be > 1 (compressor) and finite."""
        import math as _math
        for scale, pr in pr_tt_vs_scale:
            assert pr > 1.0, (
                f"PR_tt = {pr:.4f} at scale={scale} must be > 1 for a compressor."
            )
            assert _math.isfinite(pr), (
                f"PR_tt = {pr} at scale={scale} must be finite."
            )
