"""Rotor API boundary: invalid bearing payloads must be refused, not silently defaulted.

Tests for the fix to _bearing_from_payload, _section_from_payload, and
_disk_from_payload in apps/api/routers/rotor.py.

Before the fix (pre-audit), all three adapter functions caught ValueError
and returned None. The caller then silently dropped the invalid object and
fell back to default bearings/geometry. This means:

  POST /api/projects/.../rotor  with bearings: [{K_yy_n_per_m: NaN}]

would succeed, produce default bearings, and return results with no
indication that the user's bearing specification was ignored.

After the fix, any physics-invalid field raises HTTPException(422) with a
structured error message. This is tested here.

Mandate reference: "Low-level physical refusals must not be swallowed and
replaced with defaults. Defaults are acceptable only when the user omitted
the object entirely, not when the user supplied invalid physics."
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

_REPO = Path(__file__).resolve().parents[2]
for _p in (str(_REPO / "src"), str(_REPO / "apps" / "api")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import HTTPException
from routers.rotor import (
    _bearing_from_payload,
    _build_rotor_from_request,
    _disk_from_payload,
    _section_from_payload,
)
from models import RotorRequest


# ============================================================================
# Bearing payload refusals
# ============================================================================


class TestBearingPayloadRefusal:
    """Invalid bearing payloads must raise HTTPException(422), not return None."""

    def test_nan_kyy_refuses_with_422(self) -> None:
        """NaN K_yy in the request body raises HTTPException(422)."""
        with pytest.raises(HTTPException) as exc_info:
            _bearing_from_payload({"K_yy_n_per_m": float("nan"), "axial_position_mm": 0.0})
        assert exc_info.value.status_code == 422
        assert "INVALID_BEARING" in exc_info.value.detail

    def test_nan_kzz_refuses_with_422(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _bearing_from_payload({"K_yy_n_per_m": 1e7, "K_zz_n_per_m": float("nan"), "axial_position_mm": 0.0})
        assert exc_info.value.status_code == 422

    def test_inf_kyy_refuses_with_422(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _bearing_from_payload({"K_yy_n_per_m": float("inf"), "axial_position_mm": 0.0})
        assert exc_info.value.status_code == 422

    def test_negative_kyy_refuses_with_422(self) -> None:
        """Negative diagonal stiffness is physically impossible for a passive bearing."""
        with pytest.raises(HTTPException) as exc_info:
            _bearing_from_payload({"K_yy_n_per_m": -1.0e6, "axial_position_mm": 0.0})
        assert exc_info.value.status_code == 422
        assert "INVALID_BEARING" in exc_info.value.detail

    def test_negative_kzz_refuses_with_422(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _bearing_from_payload({"K_yy_n_per_m": 1e7, "K_zz_n_per_m": -5e6, "axial_position_mm": 0.0})
        assert exc_info.value.status_code == 422

    def test_negative_cyy_refuses_with_422(self) -> None:
        """Negative diagonal damping is physically impossible for a passive bearing."""
        with pytest.raises(HTTPException) as exc_info:
            _bearing_from_payload({
                "K_yy_n_per_m": 1e7, "K_zz_n_per_m": 1e7,
                "C_yy_n_s_per_m": -100.0, "axial_position_mm": 0.0,
            })
        assert exc_info.value.status_code == 422

    def test_above_limit_stiffness_refuses_with_422(self) -> None:
        """K > 1e10 N/m is refused as implausible (SPEC_SHEET §15 guard)."""
        with pytest.raises(HTTPException) as exc_info:
            _bearing_from_payload({"K_yy_n_per_m": 3.8e14, "axial_position_mm": 0.0})
        assert exc_info.value.status_code == 422

    def test_string_where_float_expected_refuses_with_422(self) -> None:
        """Unparseable field also raises 422, not a silent drop."""
        with pytest.raises(HTTPException) as exc_info:
            _bearing_from_payload({"K_yy_n_per_m": "not-a-number", "axial_position_mm": 0.0})
        assert exc_info.value.status_code == 422

    def test_negative_cross_coupling_still_accepted(self) -> None:
        """K_yz < 0 is allowed — negative cross-coupling is the oil-whirl signature."""
        brg = _bearing_from_payload({
            "K_yy_n_per_m": 1e7, "K_zz_n_per_m": 1e7,
            "K_yz_n_per_m": -5e6, "K_zy_n_per_m": 5e6,
            "axial_position_mm": 0.0,
        })
        K, _ = brg.coefficients_at_rpm(0.0)
        assert K[0, 1] == pytest.approx(-5e6)

    def test_valid_canonical_bearing_accepted(self) -> None:
        """The canonical valid bearing shape constructs without error."""
        brg = _bearing_from_payload({
            "K_yy_n_per_m": 5e7, "K_zz_n_per_m": 5e7,
            "C_yy_n_s_per_m": 1e3, "C_zz_n_s_per_m": 1e3,
            "axial_position_mm": 90.0,
        })
        K, C = brg.coefficients_at_rpm(0.0)
        assert K[0, 0] == pytest.approx(5e7)
        assert C[0, 0] == pytest.approx(1e3)

    def test_legacy_isotropic_valid_bearing_accepted(self) -> None:
        """Legacy isotropic shape (stiffness_N_per_m) still works."""
        brg = _bearing_from_payload({"stiffness_N_per_m": 5e7, "damping_N_s_per_m": 1e3, "axial_position_mm": 0.0})
        K, _ = brg.coefficients_at_rpm(0.0)
        assert K[0, 0] == pytest.approx(5e7)


class TestBearingPayloadTabulated:
    """Tabulated bearing refusals."""

    def _valid_table(self):
        return [
            {"rpm": 1000.0, "K_yy": 1e7, "K_zz": 1e7, "K_yz": 0.0, "K_zy": 0.0,
             "C_yy": 1e3, "C_zz": 1e3, "C_yz": 0.0, "C_zy": 0.0},
            {"rpm": 10000.0, "K_yy": 2e7, "K_zz": 2e7, "K_yz": 0.0, "K_zy": 0.0,
             "C_yy": 2e3, "C_zz": 2e3, "C_yz": 0.0, "C_zy": 0.0},
        ]

    def test_valid_table_accepted(self) -> None:
        brg = _bearing_from_payload({"table": self._valid_table(), "axial_position_mm": 0.0})
        assert brg is not None

    def test_nan_in_table_refuses_with_422(self) -> None:
        table = self._valid_table()
        table[1]["K_yy"] = float("nan")
        with pytest.raises(HTTPException) as exc_info:
            _bearing_from_payload({"table": table, "axial_position_mm": 0.0})
        assert exc_info.value.status_code == 422

    def test_above_limit_in_table_refuses_with_422(self) -> None:
        table = self._valid_table()
        table[0]["K_zz"] = 3.8e14  # Kzz unit-display bug value
        with pytest.raises(HTTPException) as exc_info:
            _bearing_from_payload({"table": table, "axial_position_mm": 0.0})
        assert exc_info.value.status_code == 422


# ============================================================================
# Section payload refusals
# ============================================================================


class TestSectionPayloadRefusal:
    """Invalid section payloads must raise HTTPException(422)."""

    def test_negative_length_refuses_with_422(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _section_from_payload({"length_mm": -10.0, "diameter_outer_mm": 20.0})
        assert exc_info.value.status_code == 422
        assert "INVALID_SECTION_GEOMETRY" in exc_info.value.detail

    def test_zero_length_refuses_with_422(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _section_from_payload({"length_mm": 0.0, "diameter_outer_mm": 20.0})
        assert exc_info.value.status_code == 422

    def test_nan_length_refuses_with_422(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _section_from_payload({"length_mm": float("nan"), "diameter_outer_mm": 20.0})
        assert exc_info.value.status_code == 422

    def test_nan_outer_diameter_refuses_with_422(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _section_from_payload({"length_mm": 100.0, "diameter_outer_mm": float("nan")})
        assert exc_info.value.status_code == 422

    def test_inner_greater_than_outer_refuses_with_422(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _section_from_payload({
                "length_mm": 100.0,
                "diameter_outer_mm": 20.0,
                "diameter_inner_mm": 30.0,
            })
        assert exc_info.value.status_code == 422

    def test_valid_section_accepted(self) -> None:
        sec = _section_from_payload({
            "diameter_outer_mm": 20.0, "diameter_inner_mm": 0.0,
            "length_mm": 100.0, "density_kg_per_m3": 7800.0,
            "axial_position_mm": 0.0, "material": "STEEL_AISI4340",
        })
        assert sec is not None
        assert float(sec.length.to("mm").magnitude) == pytest.approx(100.0)


# ============================================================================
# Disk payload refusals
# ============================================================================


class TestDiskPayloadRefusal:
    """Invalid disk payloads must raise HTTPException(422)."""

    def test_negative_mass_refuses_with_422(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _disk_from_payload({
                "mass_kg": -1.0,
                "inertia_polar_kg_m2": 1e-3,
                "inertia_diametrical_kg_m2": 5e-4,
                "axial_position_mm": 200.0,
            })
        assert exc_info.value.status_code == 422
        assert "INVALID_DISK_GEOMETRY" in exc_info.value.detail

    def test_nan_mass_refuses_with_422(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _disk_from_payload({
                "mass_kg": float("nan"),
                "inertia_polar_kg_m2": 1e-3,
                "inertia_diametrical_kg_m2": 5e-4,
                "axial_position_mm": 200.0,
            })
        assert exc_info.value.status_code == 422

    def test_nan_inertia_refuses_with_422(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _disk_from_payload({
                "mass_kg": 2.5,
                "inertia_polar_kg_m2": float("nan"),
                "inertia_diametrical_kg_m2": 5e-4,
                "axial_position_mm": 200.0,
            })
        assert exc_info.value.status_code == 422

    def test_valid_disk_accepted(self) -> None:
        disk = _disk_from_payload({
            "mass_kg": 2.5,
            "inertia_polar_kg_m2": 2.5e-3,
            "inertia_diametrical_kg_m2": 1.25e-3,
            "axial_position_mm": 200.0,
        })
        assert disk is not None
        assert float(disk.mass.to("kg").magnitude) == pytest.approx(2.5)


# ============================================================================
# End-to-end: _build_rotor_from_request propagates refusals
# ============================================================================


class TestBuildRotorFromRequestRefusal:
    """Invalid bearing/section in the RotorRequest propagates the 422."""

    def test_request_with_nan_bearing_refused(self) -> None:
        """When the user supplies a bearing with NaN K, the request fails with 422.
        NOT silently replaced with default bearings.
        """
        req = RotorRequest(
            analysis="lateral",
            bearings=[
                {"K_yy_n_per_m": float("nan"), "K_zz_n_per_m": 1e7, "axial_position_mm": 0.0},
            ],
        )
        with pytest.raises(HTTPException) as exc_info:
            _build_rotor_from_request(req)
        assert exc_info.value.status_code == 422

    def test_request_with_negative_bearing_k_refused(self) -> None:
        """Negative diagonal K on a provided bearing refuses, not defaults."""
        req = RotorRequest(
            analysis="lateral",
            bearings=[
                {"K_yy_n_per_m": -5e6, "K_zz_n_per_m": 5e6, "axial_position_mm": 0.0},
            ],
        )
        with pytest.raises(HTTPException) as exc_info:
            _build_rotor_from_request(req)
        assert exc_info.value.status_code == 422

    def test_request_with_no_bearings_uses_defaults(self) -> None:
        """When no bearings are supplied at all, the default soft bearings are used."""
        req = RotorRequest(analysis="lateral", bearings=[])
        model, shape, bearings = _build_rotor_from_request(req)
        assert len(bearings) == 2
        # Default bearing K = 5e7 N/m
        K, _ = bearings[0].coefficients_at_rpm(0.0)
        assert K[0, 0] == pytest.approx(5e7)

    def test_request_with_no_sections_uses_jeffcott_default(self) -> None:
        """When sections list is empty, the Jeffcott demo geometry is used."""
        req = RotorRequest(analysis="lateral", sections=[])
        model, shape, bearings = _build_rotor_from_request(req)
        # Jeffcott default: 1 section, 1 disk
        assert len(shape.sections) == 1
        assert len(shape.disks) == 1

    def test_request_with_negative_section_length_refused(self) -> None:
        """Invalid section in the payload propagates 422."""
        req = RotorRequest(
            analysis="lateral",
            sections=[
                {"diameter_outer_mm": 20.0, "length_mm": -50.0, "axial_position_mm": 0.0},
            ],
        )
        with pytest.raises(HTTPException) as exc_info:
            _build_rotor_from_request(req)
        assert exc_info.value.status_code == 422
