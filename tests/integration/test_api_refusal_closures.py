"""Integration tests for Closure I1 API refusal defects (2026-05-27).

Tests: C-1, C-2, C-3, B-02.

- C-1: air_standard=true + efficiency_mode=live_meanline → 422 INCOMPATIBLE_SETTINGS
- C-2: wiesner_calibration_scale out of (0, 2] → 422 (Pydantic validation error)
- C-3: reference_temperature_K=0 or negative → 422 (Pydantic validation error)
- B-02: inverse_solve_pr_ts_target + outlet_pressure_static_Pa → 422 OVERCONSTRAINED

All refusals are synchronous (checked before job dispatch).
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


# ---------------------------------------------------------------------------
# C-1: air_standard + live_meanline incompatibility
# ---------------------------------------------------------------------------


class TestC1AirStandardLiveMeanlineConflict:
    """C-1: air_standard=true + efficiency_mode=live_meanline must fire 422.

    Physical rationale: air_standard=true uses IdealGasFluid (constant
    cp/γ = 1.4) for the entire cycle deck. live_meanline co-simulation
    runs the mean-line solver with its own thermodynamic model. Running
    both simultaneously produces thermodynamically inconsistent state
    exchanges across the Aitken outer loop.

    Citation: cycle.py module docstring (F1 flag documentation).
    """

    def _make_project_with_air_standard_and_live_meanline(
        self,
        comp_mode: str = "live_meanline",
        turb_mode: str = "isentropic",
    ) -> dict:
        """Build a minimal project dict that triggers C-1."""
        return {
            "settings": {"air_standard": True},
            "components": [
                {
                    "id": "c1",
                    "kind": "Compressor",
                    "name": "C1",
                    "params": {
                        "pressure_ratio": 3.0,
                        "efficiency_isentropic": 0.80,
                        "efficiency_mode": comp_mode,
                    },
                },
                {
                    "id": "t1",
                    "kind": "Turbine",
                    "name": "T1",
                    "params": {
                        "pressure_ratio": 3.0,
                        "efficiency_isentropic": 0.85,
                        "efficiency_mode": turb_mode,
                    },
                },
            ],
        }

    def test_air_standard_plus_comp_live_meanline_raises_422(self) -> None:
        """Compressor with live_meanline + air_standard must raise 422."""
        from fastapi import HTTPException
        from routers.cycle import _check_air_standard_live_meanline_conflict

        project = self._make_project_with_air_standard_and_live_meanline(
            comp_mode="live_meanline", turb_mode="isentropic"
        )
        with pytest.raises(HTTPException) as exc_info:
            _check_air_standard_live_meanline_conflict(project)
        assert exc_info.value.status_code == 422
        detail = exc_info.value.detail
        assert detail["error_code"] == "INCOMPATIBLE_SETTINGS"
        assert "C1" in detail["conflicting_components"]

    def test_air_standard_plus_turb_live_meanline_raises_422(self) -> None:
        """Turbine with live_meanline + air_standard must raise 422."""
        from fastapi import HTTPException
        from routers.cycle import _check_air_standard_live_meanline_conflict

        project = self._make_project_with_air_standard_and_live_meanline(
            comp_mode="isentropic", turb_mode="live_meanline"
        )
        with pytest.raises(HTTPException) as exc_info:
            _check_air_standard_live_meanline_conflict(project)
        assert exc_info.value.status_code == 422
        detail = exc_info.value.detail
        assert detail["error_code"] == "INCOMPATIBLE_SETTINGS"
        assert "T1" in detail["conflicting_components"]

    def test_no_air_standard_live_meanline_ok(self) -> None:
        """Without air_standard=true, live_meanline is permitted."""
        from routers.cycle import _check_air_standard_live_meanline_conflict

        project = {
            "settings": {"air_standard": False},
            "components": [
                {
                    "id": "c1", "kind": "Compressor", "name": "C1",
                    "params": {
                        "pressure_ratio": 3.0,
                        "efficiency_isentropic": 0.80,
                        "efficiency_mode": "live_meanline",
                    },
                }
            ],
        }
        # Should not raise
        _check_air_standard_live_meanline_conflict(project)

    def test_air_standard_isentropic_ok(self) -> None:
        """air_standard=true with isentropic mode (no live_meanline) is permitted."""
        from routers.cycle import _check_air_standard_live_meanline_conflict

        project = {
            "settings": {"air_standard": True},
            "components": [
                {
                    "id": "c1", "kind": "Compressor", "name": "C1",
                    "params": {
                        "pressure_ratio": 3.0,
                        "efficiency_isentropic": 0.80,
                        "efficiency_mode": "isentropic",
                    },
                }
            ],
        }
        # Should not raise
        _check_air_standard_live_meanline_conflict(project)

    def test_no_air_standard_flag_ok(self) -> None:
        """Project without air_standard key must not raise."""
        from routers.cycle import _check_air_standard_live_meanline_conflict

        project = {
            "settings": {},
            "components": [
                {
                    "id": "c1", "kind": "Compressor", "name": "C1",
                    "params": {"efficiency_mode": "live_meanline"},
                }
            ],
        }
        # Should not raise (air_standard absent → defaults False)
        _check_air_standard_live_meanline_conflict(project)


# ---------------------------------------------------------------------------
# C-2: wiesner_calibration_scale Pydantic constraint
# ---------------------------------------------------------------------------


class TestC2WiesnerCalibrationScaleBoundary:
    """C-2: wiesner_calibration_scale must be in (0, 2].

    Zero, negative, and absurd values (e.g. 100.0) must all 422.
    Values within range must be accepted.

    Citation: Came & Robinson 1999 §3.2 reports values in [1.0, 1.10].
    The broader (0, 2] range allows experimental calibration.
    """

    def test_negative_value_raises_validation_error(self) -> None:
        """wiesner_calibration_scale=-0.5 must raise Pydantic validation error."""
        from pydantic import ValidationError
        from models import AnalysisRequest

        with pytest.raises(ValidationError) as exc_info:
            AnalysisRequest(
                machine_class="centrifugal_compressor",
                wiesner_calibration_scale=-0.5,
            )
        errors = exc_info.value.errors()
        assert any(
            "wiesner_calibration_scale" in str(e.get("loc", "")) or
            "wiesner_calibration_scale" in str(e)
            for e in errors
        ), f"Expected wiesner_calibration_scale in errors; got {errors}"

    def test_zero_raises_validation_error(self) -> None:
        """wiesner_calibration_scale=0 must raise Pydantic validation error."""
        from pydantic import ValidationError
        from models import AnalysisRequest

        with pytest.raises(ValidationError):
            AnalysisRequest(
                machine_class="centrifugal_compressor",
                wiesner_calibration_scale=0.0,
            )

    def test_absurd_large_value_raises_validation_error(self) -> None:
        """wiesner_calibration_scale=100.0 must raise Pydantic validation error."""
        from pydantic import ValidationError
        from models import AnalysisRequest

        with pytest.raises(ValidationError):
            AnalysisRequest(
                machine_class="centrifugal_compressor",
                wiesner_calibration_scale=100.0,
            )

    def test_exceeds_upper_bound_raises_validation_error(self) -> None:
        """wiesner_calibration_scale=2.001 (just above upper bound) must raise."""
        from pydantic import ValidationError
        from models import AnalysisRequest

        with pytest.raises(ValidationError):
            AnalysisRequest(
                machine_class="centrifugal_compressor",
                wiesner_calibration_scale=2.001,
            )

    def test_valid_value_accepted(self) -> None:
        """wiesner_calibration_scale=1.05 (Came-Robinson) must be accepted."""
        from models import AnalysisRequest

        req = AnalysisRequest(
            machine_class="centrifugal_compressor",
            wiesner_calibration_scale=1.05,
        )
        assert req.wiesner_calibration_scale == pytest.approx(1.05)

    def test_upper_bound_accepted(self) -> None:
        """wiesner_calibration_scale=2.0 (at upper bound) must be accepted."""
        from models import AnalysisRequest

        req = AnalysisRequest(
            machine_class="centrifugal_compressor",
            wiesner_calibration_scale=2.0,
        )
        assert req.wiesner_calibration_scale == pytest.approx(2.0)

    def test_small_positive_accepted(self) -> None:
        """wiesner_calibration_scale=0.1 (small but positive) must be accepted."""
        from models import AnalysisRequest

        req = AnalysisRequest(
            machine_class="centrifugal_compressor",
            wiesner_calibration_scale=0.1,
        )
        assert req.wiesner_calibration_scale == pytest.approx(0.1)

    def test_none_still_accepted(self) -> None:
        """wiesner_calibration_scale=None (default, no constraint) must be accepted."""
        from models import AnalysisRequest

        req = AnalysisRequest()
        assert req.wiesner_calibration_scale is None


# ---------------------------------------------------------------------------
# C-3: reference_temperature_K synchronous refusal
# ---------------------------------------------------------------------------


class TestC3ReferenceTemperatureRefusal:
    """C-3: reference_temperature_K=0 or negative must raise synchronously.

    The constraint is on CorrectedOperatingPoint.reference_temperature_K
    and reference_pressure_Pa (gt=0). Zero or negative causes ZeroDivisionError
    in _corrected_to_dimensional() inside the worker — the constraint converts
    this to a synchronous 422 before the job is dispatched.
    """

    def test_zero_temperature_raises_pydantic_error(self) -> None:
        """reference_temperature_K=0 must raise Pydantic ValidationError."""
        from pydantic import ValidationError
        from models import CorrectedOperatingPoint

        with pytest.raises(ValidationError):
            CorrectedOperatingPoint(
                corrected_mass_flow_kg_s=0.13,
                reference_temperature_K=0.0,
                reference_pressure_Pa=101325.0,
            )

    def test_negative_temperature_raises_pydantic_error(self) -> None:
        """reference_temperature_K=-100 must raise Pydantic ValidationError."""
        from pydantic import ValidationError
        from models import CorrectedOperatingPoint

        with pytest.raises(ValidationError):
            CorrectedOperatingPoint(
                corrected_mass_flow_kg_s=0.13,
                reference_temperature_K=-100.0,
                reference_pressure_Pa=101325.0,
            )

    def test_zero_pressure_raises_pydantic_error(self) -> None:
        """reference_pressure_Pa=0 must raise Pydantic ValidationError."""
        from pydantic import ValidationError
        from models import CorrectedOperatingPoint

        with pytest.raises(ValidationError):
            CorrectedOperatingPoint(
                corrected_mass_flow_kg_s=0.13,
                reference_temperature_K=288.15,
                reference_pressure_Pa=0.0,
            )

    def test_negative_pressure_raises_pydantic_error(self) -> None:
        """reference_pressure_Pa=-1 must raise Pydantic ValidationError."""
        from pydantic import ValidationError
        from models import CorrectedOperatingPoint

        with pytest.raises(ValidationError):
            CorrectedOperatingPoint(
                corrected_mass_flow_kg_s=0.13,
                reference_temperature_K=288.15,
                reference_pressure_Pa=-1.0,
            )

    def test_valid_reference_conditions_accepted(self) -> None:
        """Standard ISA reference conditions must be accepted."""
        from models import CorrectedOperatingPoint

        cop = CorrectedOperatingPoint(
            corrected_mass_flow_kg_s=0.13,
            reference_temperature_K=288.15,
            reference_pressure_Pa=101325.0,
        )
        assert cop.reference_temperature_K == pytest.approx(288.15)
        assert cop.reference_pressure_Pa == pytest.approx(101325.0)

    def test_alternative_reference_conditions_accepted(self) -> None:
        """Non-standard but positive reference conditions must be accepted."""
        from models import CorrectedOperatingPoint

        cop = CorrectedOperatingPoint(
            corrected_mass_flow_kg_s=0.13,
            reference_temperature_K=1090.0,  # hot-gas inlet temperature
            reference_pressure_Pa=220000.0,   # high-pressure inlet
        )
        assert cop.reference_temperature_K == pytest.approx(1090.0)


# ---------------------------------------------------------------------------
# B-02: inverse_solve + outlet_pressure_static overconstrained refusal
# ---------------------------------------------------------------------------


class TestB02InverseSolvePlusOutletPressureRefusal:
    """B-02: inverse_solve_pr_ts_target + outlet_pressure_static_Pa → 422.

    When outlet_pressure_static_Pa is fixed, PR_ts = P₀₁ / P₂_static is
    determined by inlet conditions alone and is independent of mass flow.
    The inverse solve's residual function is constant → brentq finds no
    sign change → returns INVERSE_SOLVE_FAILED. The real cause is an
    overconstrained specification, not a solver failure.

    The fix returns 422 OVERCONSTRAINED_OPERATING_POINT synchronously,
    with a clear explanation.
    """

    def test_inverse_solve_plus_outlet_pressure_raises_422(self) -> None:
        """Combining inverse_solve_pr_ts_target and outlet_pressure_static_Pa must raise 422."""
        from fastapi import HTTPException
        from routers.analysis import _check_inverse_solve_overconstrained

        with pytest.raises(HTTPException) as exc_info:
            _check_inverse_solve_overconstrained(
                op_dict={"rpm": 79000.0},
                corr=None,
                inverse_solve_pr_ts_target=5.5,
                outlet_pressure_static_Pa=80000.0,
            )
        assert exc_info.value.status_code == 422
        detail = exc_info.value.detail
        assert detail["error_code"] == "OVERCONSTRAINED_OPERATING_POINT"
        assert "inverse_solve_pr_ts_target" in detail["conflicting_fields"]
        assert "outlet_pressure_static_Pa" in detail["conflicting_fields"]

    def test_inverse_solve_alone_ok(self) -> None:
        """inverse_solve_pr_ts_target alone (no outlet pressure) must not raise."""
        from routers.analysis import _check_inverse_solve_overconstrained

        # Should not raise
        _check_inverse_solve_overconstrained(
            op_dict={"rpm": 79000.0},
            corr=None,
            inverse_solve_pr_ts_target=5.5,
            outlet_pressure_static_Pa=None,
        )

    def test_outlet_pressure_alone_ok(self) -> None:
        """outlet_pressure_static_Pa alone (no inverse_solve) must not raise."""
        from routers.analysis import _check_inverse_solve_overconstrained

        # Should not raise
        _check_inverse_solve_overconstrained(
            op_dict={"rpm": 79000.0, "mass_flow_kg_per_s": 0.13},
            corr=None,
            inverse_solve_pr_ts_target=None,
            outlet_pressure_static_Pa=80000.0,
        )

    def test_error_detail_explains_physics(self) -> None:
        """The 422 detail message must explain why the combination is overconstrained."""
        from fastapi import HTTPException
        from routers.analysis import _check_inverse_solve_overconstrained

        with pytest.raises(HTTPException) as exc_info:
            _check_inverse_solve_overconstrained(
                op_dict={},
                corr=None,
                inverse_solve_pr_ts_target=4.0,
                outlet_pressure_static_Pa=50000.0,
            )
        detail = exc_info.value.detail
        # The message must explain the degree-of-freedom removal
        msg = detail.get("message", "")
        assert "independent" in msg.lower() or "degree of freedom" in msg.lower() or "fixed" in msg.lower(), (
            f"Error message should explain why fixing P₂ removes the inverse solve's "
            f"degree of freedom. Got: {msg!r}"
        )

    def test_both_mass_flow_and_outlet_pressure_with_inverse_solve(self) -> None:
        """mass_flow + outlet_pressure + inverse_solve: B-02 check fires first."""
        from fastapi import HTTPException
        from routers.analysis import _check_inverse_solve_overconstrained

        # B-02 check fires before the mass-flow check when outlet_pressure is set
        with pytest.raises(HTTPException) as exc_info:
            _check_inverse_solve_overconstrained(
                op_dict={"mass_flow_kg_per_s": 0.13},
                corr=None,
                inverse_solve_pr_ts_target=5.0,
                outlet_pressure_static_Pa=70000.0,
            )
        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["error_code"] == "OVERCONSTRAINED_OPERATING_POINT"
        assert "outlet_pressure_static_Pa" in exc_info.value.detail["conflicting_fields"]
