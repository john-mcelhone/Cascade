"""G2 / Item 1: Corrected operating-point API — round-trip identity and refusal tests.

Tests:
1. Corrected-flow round-trip identity: supplying corrected mass flow and
   corrected speed produces the same η_ts as the equivalent dimensional inputs
   (within floating-point round-trip tolerance).
2. Multiple reference temperatures (288.15, 298.15, 273.15 K) — verify the
   convention is respected (different references produce different dimensional
   equivalents, which produce different η_ts values unless the corrections happen
   to coincide numerically).
3. OVERCONSTRAINED_OPERATING_POINT 422 — both dimensional and corrected supplied.
4. CorrectedOperatingPoint schema validation.

References
----------
Saravanamuttoo et al., "Gas Turbine Theory" 7th ed., Ch. 4, eqs. 4.16–4.17.
NASA TN D-7508 Whitney & Stewart (1974) — RIT-1 benchmark geometry used here.
SPEC_SHEET §12 RIT-1 / CC-1 validation cases.
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
# Whitney-Stewart RIT-1 geometry (NASA TN D-7508) — used throughout
# ---------------------------------------------------------------------------

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

# Dimensional operating point
_P_01 = 220_000.0   # Pa
_T_01 = 1090.0      # K
_MDOT_DIM = 0.13    # kg/s
_RPM_DIM = 79_000.0


# ---------------------------------------------------------------------------
# Conversion helpers (mirroring the production formula for test verification)
# ---------------------------------------------------------------------------

def _dim_to_corr(mdot: float, rpm: float, p01: float, t01: float,
                 t_ref: float = 288.15, p_ref: float = 101_325.0) -> tuple[float, float]:
    """Dimensional → corrected (for constructing test inputs)."""
    theta = t01 / t_ref
    delta = p01 / p_ref
    sqrt_theta = math.sqrt(theta)
    mdot_corr = mdot * sqrt_theta / delta   # ṁ_dim × √θ / δ
    rpm_corr = rpm / sqrt_theta              # N_dim / √θ
    return mdot_corr, rpm_corr


def _corr_to_dim(mdot_corr: float, rpm_corr: float, p01: float, t01: float,
                 t_ref: float = 288.15, p_ref: float = 101_325.0) -> tuple[float, float]:
    """Corrected → dimensional (mirrors _corrected_to_dimensional in analysis.py)."""
    theta = t01 / t_ref
    delta = p01 / p_ref
    sqrt_theta = math.sqrt(theta)
    mdot_dim = mdot_corr * delta / sqrt_theta
    rpm_dim = rpm_corr * sqrt_theta
    return mdot_dim, rpm_dim


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestCorrectedOperatingPointSchema:
    def test_schema_defaults(self) -> None:
        from models import CorrectedOperatingPoint

        cop = CorrectedOperatingPoint()
        assert cop.corrected_mass_flow_kg_s is None
        assert cop.corrected_rotational_speed_rpm is None
        assert cop.reference_temperature_K == pytest.approx(288.15)
        assert cop.reference_pressure_Pa == pytest.approx(101_325.0)

    def test_schema_accepts_values(self) -> None:
        from models import CorrectedOperatingPoint

        mdot_c, rpm_c = _dim_to_corr(_MDOT_DIM, _RPM_DIM, _P_01, _T_01)
        cop = CorrectedOperatingPoint(
            corrected_mass_flow_kg_s=mdot_c,
            corrected_rotational_speed_rpm=rpm_c,
        )
        assert cop.corrected_mass_flow_kg_s == pytest.approx(mdot_c)
        assert cop.corrected_rotational_speed_rpm == pytest.approx(rpm_c)

    def test_analysis_request_accepts_corrected_op(self) -> None:
        from models import AnalysisRequest, CorrectedOperatingPoint

        mdot_c, rpm_c = _dim_to_corr(_MDOT_DIM, _RPM_DIM, _P_01, _T_01)
        req = AnalysisRequest(
            operating_point={"pressure_total_Pa": _P_01, "temperature_total_K": _T_01},
            corrected_operating_point=CorrectedOperatingPoint(
                corrected_mass_flow_kg_s=mdot_c,
                corrected_rotational_speed_rpm=rpm_c,
            ),
        )
        assert req.corrected_operating_point is not None
        assert req.corrected_operating_point.corrected_mass_flow_kg_s == pytest.approx(mdot_c)


# ---------------------------------------------------------------------------
# Round-trip identity: corrected input → same η_ts as dimensional input
# ---------------------------------------------------------------------------

class TestCorrectedFlowRoundTrip:
    """Supplying corrected flow must produce identical η_ts to the dimensional equivalent."""

    @pytest.fixture(scope="class")
    def eta_ts_dimensional(self) -> float:
        from routers.analysis import _solve_radial_turbine

        op = {
            "pressure_total_Pa": _P_01,
            "temperature_total_K": _T_01,
            "mass_flow_kg_per_s": _MDOT_DIM,
            "rpm": _RPM_DIM,
            "fluid": "air",
        }
        result = _solve_radial_turbine(_GEOM, op, "whitfield-baines-radial-v1")
        return result["efficiencies"]["eta_ts"]

    def _eta_ts_via_corrected(
        self,
        mdot_corr: float,
        rpm_corr: float,
        t_ref: float = 288.15,
        p_ref: float = 101_325.0,
    ) -> float:
        """Run the solver via the corrected → dimensional conversion path."""
        from models import CorrectedOperatingPoint
        from routers.analysis import _corrected_to_dimensional, _solve_radial_turbine

        cop = CorrectedOperatingPoint(
            corrected_mass_flow_kg_s=mdot_corr,
            corrected_rotational_speed_rpm=rpm_corr,
            reference_temperature_K=t_ref,
            reference_pressure_Pa=p_ref,
        )
        dim = _corrected_to_dimensional(cop, _P_01, _T_01)
        op = {
            "pressure_total_Pa": _P_01,
            "temperature_total_K": _T_01,
            "mass_flow_kg_per_s": dim["mass_flow_kg_per_s"],
            "rpm": dim["rpm"],
            "fluid": "air",
        }
        result = _solve_radial_turbine(_GEOM, op, "whitfield-baines-radial-v1")
        return result["efficiencies"]["eta_ts"]

    def test_round_trip_isa_reference(self, eta_ts_dimensional: float) -> None:
        """Corrected → dimensional → solver → η_ts must equal the dimensional result.

        Reference convention: T_ref = 288.15 K, P_ref = 101 325 Pa (ISA).
        """
        mdot_c, rpm_c = _dim_to_corr(_MDOT_DIM, _RPM_DIM, _P_01, _T_01, 288.15, 101_325.0)
        eta_corr = self._eta_ts_via_corrected(mdot_c, rpm_c, 288.15, 101_325.0)
        assert abs(eta_corr - eta_ts_dimensional) < 1e-9, (
            f"Round-trip identity failed (ISA ref): "
            f"η_ts(dim)={eta_ts_dimensional:.8f} vs η_ts(corr)={eta_corr:.8f}, "
            f"diff={abs(eta_corr - eta_ts_dimensional):.2e}"
        )

    def test_round_trip_25c_reference(self, eta_ts_dimensional: float) -> None:
        """Round-trip identity with T_ref = 298.15 K, P_ref = 101 325 Pa."""
        mdot_c, rpm_c = _dim_to_corr(_MDOT_DIM, _RPM_DIM, _P_01, _T_01, 298.15, 101_325.0)
        eta_corr = self._eta_ts_via_corrected(mdot_c, rpm_c, 298.15, 101_325.0)
        assert abs(eta_corr - eta_ts_dimensional) < 1e-9, (
            f"Round-trip identity failed (298.15 K ref): "
            f"η_ts(dim)={eta_ts_dimensional:.8f} vs η_ts(corr)={eta_corr:.8f}"
        )

    def test_round_trip_0c_reference(self, eta_ts_dimensional: float) -> None:
        """Round-trip identity with T_ref = 273.15 K, P_ref = 101 325 Pa."""
        mdot_c, rpm_c = _dim_to_corr(_MDOT_DIM, _RPM_DIM, _P_01, _T_01, 273.15, 101_325.0)
        eta_corr = self._eta_ts_via_corrected(mdot_c, rpm_c, 273.15, 101_325.0)
        assert abs(eta_corr - eta_ts_dimensional) < 1e-9, (
            f"Round-trip identity failed (273.15 K ref): "
            f"η_ts(dim)={eta_ts_dimensional:.8f} vs η_ts(corr)={eta_corr:.8f}"
        )

    def test_different_reference_temperatures_give_different_corrected_values(self) -> None:
        """Different reference temperatures must produce different corrected values.

        This guards against a convention-collapse bug where the conversion
        is applied uniformly regardless of the supplied reference.
        """
        mdot_c_isa, rpm_c_isa = _dim_to_corr(
            _MDOT_DIM, _RPM_DIM, _P_01, _T_01, 288.15, 101_325.0
        )
        mdot_c_25c, rpm_c_25c = _dim_to_corr(
            _MDOT_DIM, _RPM_DIM, _P_01, _T_01, 298.15, 101_325.0
        )
        mdot_c_0c, rpm_c_0c = _dim_to_corr(
            _MDOT_DIM, _RPM_DIM, _P_01, _T_01, 273.15, 101_325.0
        )
        # Corrected values must differ numerically when the reference differs.
        assert abs(mdot_c_isa - mdot_c_25c) > 1e-6, (
            "ISA and 25°C reference must produce different corrected mass flows."
        )
        assert abs(rpm_c_isa - rpm_c_0c) > 1, (
            "ISA and 0°C reference must produce different corrected RPM."
        )

    def test_corrected_flow_sweep_gives_same_eta_ts_ordering_as_dimensional(self) -> None:
        """η_ts ordering must be preserved when sweeping via corrected form.

        Sweep three corrected mass-flow values; the resulting η_ts must match
        those produced by the equivalent dimensional inputs.
        """
        from models import CorrectedOperatingPoint
        from routers.analysis import _corrected_to_dimensional, _solve_radial_turbine

        mdot_factors = [0.8, 1.0, 1.2]
        t_ref, p_ref = 288.15, 101_325.0

        eta_ts_dim_list = []
        eta_ts_corr_list = []

        for factor in mdot_factors:
            mdot = _MDOT_DIM * factor

            # Dimensional path
            op_dim = {
                "pressure_total_Pa": _P_01,
                "temperature_total_K": _T_01,
                "mass_flow_kg_per_s": mdot,
                "rpm": _RPM_DIM,
                "fluid": "air",
            }
            res_dim = _solve_radial_turbine(_GEOM, op_dim, "whitfield-baines-radial-v1")
            eta_ts_dim_list.append(res_dim["efficiencies"]["eta_ts"])

            # Corrected path
            mdot_c, rpm_c = _dim_to_corr(mdot, _RPM_DIM, _P_01, _T_01, t_ref, p_ref)
            cop = CorrectedOperatingPoint(
                corrected_mass_flow_kg_s=mdot_c,
                corrected_rotational_speed_rpm=rpm_c,
                reference_temperature_K=t_ref,
                reference_pressure_Pa=p_ref,
            )
            dim = _corrected_to_dimensional(cop, _P_01, _T_01)
            op_corr = {
                "pressure_total_Pa": _P_01,
                "temperature_total_K": _T_01,
                "mass_flow_kg_per_s": dim["mass_flow_kg_per_s"],
                "rpm": dim["rpm"],
                "fluid": "air",
            }
            res_corr = _solve_radial_turbine(_GEOM, op_corr, "whitfield-baines-radial-v1")
            eta_ts_corr_list.append(res_corr["efficiencies"]["eta_ts"])

        # Each corrected result must match the dimensional result exactly.
        for i, (eta_d, eta_c) in enumerate(zip(eta_ts_dim_list, eta_ts_corr_list)):
            assert abs(eta_d - eta_c) < 1e-9, (
                f"Factor={mdot_factors[i]}: η_ts(dim)={eta_d:.8f} vs "
                f"η_ts(corr)={eta_c:.8f}, diff={abs(eta_d-eta_c):.2e}"
            )


# ---------------------------------------------------------------------------
# Overconstrained rejection
# ---------------------------------------------------------------------------

class TestOverconstrainedRejection:
    """Supplying both dimensional and corrected raises 422 OVERCONSTRAINED."""

    def test_both_mass_flow_raises(self) -> None:
        """Supplying mass_flow_kg_per_s AND corrected_mass_flow_kg_s must raise 422."""
        from fastapi import HTTPException
        from models import AnalysisRequest, CorrectedOperatingPoint
        from routers.analysis import _check_overconstrained

        op = {"mass_flow_kg_per_s": 0.13}
        cop = CorrectedOperatingPoint(corrected_mass_flow_kg_s=0.10)
        with pytest.raises(HTTPException) as exc_info:
            _check_overconstrained(op, cop)
        assert exc_info.value.status_code == 422
        detail = exc_info.value.detail
        assert detail["error_code"] == "OVERCONSTRAINED_OPERATING_POINT"
        assert "corrected_mass_flow_kg_s" in detail["conflicting_fields"]
        assert "mass_flow_kg_per_s" in detail["conflicting_fields"]

    def test_both_rpm_raises(self) -> None:
        """Supplying rpm AND corrected_rotational_speed_rpm must raise 422."""
        from fastapi import HTTPException
        from models import AnalysisRequest, CorrectedOperatingPoint
        from routers.analysis import _check_overconstrained

        op = {"rpm": 79000.0}
        cop = CorrectedOperatingPoint(corrected_rotational_speed_rpm=70000.0)
        with pytest.raises(HTTPException) as exc_info:
            _check_overconstrained(op, cop)
        assert exc_info.value.status_code == 422
        detail = exc_info.value.detail
        assert detail["error_code"] == "OVERCONSTRAINED_OPERATING_POINT"
        assert "corrected_rotational_speed_rpm" in detail["conflicting_fields"]
        assert "rpm" in detail["conflicting_fields"]

    def test_corrected_only_does_not_raise(self) -> None:
        """Corrected-only (no dimensional) must not raise."""
        from models import CorrectedOperatingPoint
        from routers.analysis import _check_overconstrained

        op: dict = {}
        cop = CorrectedOperatingPoint(
            corrected_mass_flow_kg_s=0.10,
            corrected_rotational_speed_rpm=70000.0,
        )
        # Should not raise — corrected-only is valid.
        _check_overconstrained(op, cop)

    def test_none_corrected_does_not_raise(self) -> None:
        """No corrected operating point (None) must not raise."""
        from routers.analysis import _check_overconstrained

        op = {"mass_flow_kg_per_s": 0.13, "rpm": 79000.0}
        _check_overconstrained(op, None)

    def test_map_both_speedline_raises(self) -> None:
        """MapRequest: both speedline_rpms and corrected_speedline_rpms raises 422."""
        from fastapi import HTTPException
        from models import MapRequest
        from routers.map import _expand_corrected_map_inputs

        req = MapRequest(
            speedline_rpms=[14000.0],
            corrected_speedline_rpms=[12000.0],
            inlet_total_pressure_Pa=101325.0,
            inlet_total_temperature_K=288.15,
        )
        with pytest.raises(HTTPException) as exc_info:
            _expand_corrected_map_inputs(req)
        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["error_code"] == "OVERCONSTRAINED_OPERATING_POINT"

    def test_map_both_mass_flows_raises(self) -> None:
        """MapRequest: both mass_flows and corrected_mass_flows raises 422."""
        from fastapi import HTTPException
        from models import MapRequest
        from routers.map import _expand_corrected_map_inputs

        req = MapRequest(
            speedline_rpms=[],       # empty dimensional speedlines — OK
            mass_flows=[5.0],
            corrected_mass_flows=[4.0],
            inlet_total_pressure_Pa=101325.0,
            inlet_total_temperature_K=288.15,
        )
        with pytest.raises(HTTPException) as exc_info:
            _expand_corrected_map_inputs(req)
        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["error_code"] == "OVERCONSTRAINED_OPERATING_POINT"

    def test_map_corrected_without_inlet_conditions_raises(self) -> None:
        """MapRequest: corrected flows without inlet conditions raises 422."""
        from fastapi import HTTPException
        from models import MapRequest
        from routers.map import _expand_corrected_map_inputs

        req = MapRequest(
            speedline_rpms=[],
            corrected_speedline_rpms=[12000.0],
            # No inlet_total_pressure_Pa / inlet_total_temperature_K
        )
        with pytest.raises(HTTPException) as exc_info:
            _expand_corrected_map_inputs(req)
        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["error_code"] == "MISSING_INLET_CONDITIONS"


# ---------------------------------------------------------------------------
# Map corrected → dimensional round-trip
# ---------------------------------------------------------------------------

class TestMapCorrectedExpansion:
    """Corrected speedline / mass-flow inputs must expand to correct dimensional values."""

    def test_corrected_expansion_round_trip(self) -> None:
        """_expand_corrected_map_inputs must produce values consistent with the formula."""
        from models import MapRequest
        from routers.map import _expand_corrected_map_inputs

        p_01 = 101_325.0
        t_01 = 288.15
        t_ref = 288.15
        p_ref = 101_325.0
        # At reference conditions θ = δ = 1, so corrected == dimensional.
        rpm_corr = [7000.0, 14000.0]
        m_corr = [3.0, 5.31]

        req = MapRequest(
            speedline_rpms=[],
            mass_flows=[],
            corrected_speedline_rpms=rpm_corr,
            corrected_mass_flows=m_corr,
            inlet_total_pressure_Pa=p_01,
            inlet_total_temperature_K=t_01,
            reference_temperature_K=t_ref,
            reference_pressure_Pa=p_ref,
        )
        rpms, m_dots = _expand_corrected_map_inputs(req)
        # At T₀₁ = T_ref, P₀₁ = P_ref → θ = δ = 1 → dimensional = corrected
        for n_c, n_d in zip(rpm_corr, rpms):
            assert abs(n_c - n_d) < 1e-6, f"Expected {n_c}, got {n_d}"
        for m_c, m_d in zip(m_corr, m_dots):
            assert abs(m_c - m_d) < 1e-6, f"Expected {m_c}, got {m_d}"

    def test_corrected_expansion_off_reference(self) -> None:
        """Corrected values at non-reference conditions must expand correctly."""
        from models import MapRequest
        from routers.map import _expand_corrected_map_inputs

        p_01 = 200_000.0   # 2× reference pressure
        t_01 = 400.0       # higher than 288.15 K reference
        t_ref = 288.15
        p_ref = 101_325.0

        theta = t_01 / t_ref
        delta = p_01 / p_ref
        sqrt_theta = math.sqrt(theta)

        rpm_corr = [10000.0]
        m_corr = [2.0]

        req = MapRequest(
            speedline_rpms=[],
            mass_flows=[],
            corrected_speedline_rpms=rpm_corr,
            corrected_mass_flows=m_corr,
            inlet_total_pressure_Pa=p_01,
            inlet_total_temperature_K=t_01,
            reference_temperature_K=t_ref,
            reference_pressure_Pa=p_ref,
        )
        rpms, m_dots = _expand_corrected_map_inputs(req)
        expected_rpm = rpm_corr[0] * sqrt_theta
        expected_mdot = m_corr[0] * delta / sqrt_theta
        assert abs(rpms[0] - expected_rpm) < 1e-6, f"RPM: expected {expected_rpm}, got {rpms[0]}"
        assert abs(m_dots[0] - expected_mdot) < 1e-6, f"ṁ: expected {expected_mdot}, got {m_dots[0]}"
