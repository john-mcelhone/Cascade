"""G2 / Item 3a: cycle.py unknown-unit 422 rejection.

Verifier V finding: the `_f()` helper inside `_build_compressor_geometry` and
`_build_turbine_geometry` previously silently fell back to the raw float when
a unit string was unrecognised. After the G2 fix, an unrecognised unit string
must raise a 422 HTTPException with ``error_code == "UNKNOWN_UNIT"``.

These tests use "zorkle" as the unknown unit — not a real unit in any registry.
(Note: "fathom" is a valid imperial unit recognised by pint and would succeed;
we need a string that is genuinely absent from pint's unit registry.)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
for p in (str(_REPO / "src"), str(_REPO / "apps" / "api")):
    if p not in sys.path:
        sys.path.insert(0, p)


class TestCycleUnknownUnitRaises422:
    """Unknown unit strings in geometry_params must raise HTTPException 422."""

    def test_compressor_geometry_unknown_unit_raises(self) -> None:
        """_build_compressor_geometry with 'zorkle' unit raises 422 UNKNOWN_UNIT.

        'zorkle' is a guaranteed-absent unit string (not in pint's registry).
        Note: common imperial units like 'fathom' are in pint and would convert
        silently; we need a string that pint's UndefinedUnitError will reject.
        """
        from fastapi import HTTPException
        from routers.cycle import _build_compressor_geometry

        params = {
            "geometry_params": {
                "inducer_hub_radius": {"value": 0.045, "unit": "zorkle"},  # unknown!
                "inducer_tip_radius": 0.140,
                "impeller_outlet_radius": 0.200,
                "blade_height_outlet": 0.026,
                "blade_count": 20,
                "beta_2_metal_rad": 0.5236,
                "tip_clearance": 0.0003,
            }
        }
        with pytest.raises(HTTPException) as exc_info:
            _build_compressor_geometry(params)
        assert exc_info.value.status_code == 422, (
            f"Expected 422, got {exc_info.value.status_code}"
        )
        detail = exc_info.value.detail
        assert detail["error_code"] == "UNKNOWN_UNIT", (
            f"Expected UNKNOWN_UNIT error_code, got: {detail}"
        )
        assert "zorkle" in detail["unit"], (
            f"Expected 'zorkle' in detail['unit'], got: {detail['unit']!r}"
        )

    def test_turbine_geometry_unknown_unit_raises(self) -> None:
        """_build_turbine_geometry with 'zorkle' unit raises 422 UNKNOWN_UNIT."""
        from fastapi import HTTPException
        from routers.cycle import _build_turbine_geometry

        params = {
            "geometry_params": {
                "rotor_inlet_radius": {"value": 0.076, "unit": "zorkle"},  # unknown!
                "rotor_outlet_radius_hub": 0.019,
                "rotor_outlet_radius_tip": 0.0406,
                "blade_height_inlet": 0.012,
                "blade_height_outlet": 0.0216,
                "blade_count": 12,
                "inlet_metal_angle_rad": 0.0,
                "exducer_angle_rad": 1.0472,
                "tip_clearance": 0.00025,
            }
        }
        with pytest.raises(HTTPException) as exc_info:
            _build_turbine_geometry(params)
        assert exc_info.value.status_code == 422, (
            f"Expected 422, got {exc_info.value.status_code}"
        )
        detail = exc_info.value.detail
        assert detail["error_code"] == "UNKNOWN_UNIT", (
            f"Expected UNKNOWN_UNIT error_code, got: {detail}"
        )

    def test_compressor_geometry_known_unit_succeeds(self) -> None:
        """_build_compressor_geometry with a valid unit ('m') must not raise."""
        from routers.cycle import _build_compressor_geometry

        params = {
            "geometry_params": {
                "inducer_hub_radius": {"value": 0.045, "unit": "m"},
                "inducer_tip_radius": {"value": 0.140, "unit": "m"},
                "impeller_outlet_radius": {"value": 0.200, "unit": "m"},
                "blade_height_outlet": {"value": 0.026, "unit": "m"},
                "blade_count": 20,
                "beta_2_metal_rad": 0.5236,
                "tip_clearance": {"value": 0.0003, "unit": "m"},
            }
        }
        # Must not raise; should return a geometry object.
        geom = _build_compressor_geometry(params)
        assert geom is not None, "Expected a geometry object for valid input."

    def test_compressor_geometry_mm_unit_converts_correctly(self) -> None:
        """_build_compressor_geometry with 'mm' unit must convert to metres."""
        from routers.cycle import _build_compressor_geometry

        params = {
            "geometry_params": {
                "inducer_hub_radius": {"value": 45.0, "unit": "mm"},
                "inducer_tip_radius": {"value": 140.0, "unit": "mm"},
                "impeller_outlet_radius": {"value": 200.0, "unit": "mm"},
                "blade_height_outlet": {"value": 26.0, "unit": "mm"},
                "blade_count": 20,
                "beta_2_metal_rad": 0.5236,
                "tip_clearance": {"value": 0.3, "unit": "mm"},
            }
        }
        geom = _build_compressor_geometry(params)
        assert geom is not None
        # 45 mm → 0.045 m; inducer_hub_radius should be ~0.045 m
        assert abs(geom.inducer_hub_radius - 0.045) < 1e-6, (
            f"mm → m conversion failed: got {geom.inducer_hub_radius}, expected 0.045"
        )

    def test_unknown_unit_error_carries_field_name(self) -> None:
        """The 422 detail must include the field name for actionable debugging."""
        from fastapi import HTTPException
        from routers.cycle import _build_turbine_geometry

        params = {
            "geometry_params": {
                "rotor_inlet_radius": {"value": 76.0, "unit": "zorkle_xyz_bad"},  # unknown!
                "rotor_outlet_radius_hub": 0.019,
                "rotor_outlet_radius_tip": 0.0406,
                "blade_height_inlet": 0.012,
                "blade_height_outlet": 0.0216,
                "blade_count": 12,
                "inlet_metal_angle_rad": 0.0,
                "exducer_angle_rad": 1.0472,
                "tip_clearance": 0.00025,
            }
        }
        with pytest.raises(HTTPException) as exc_info:
            _build_turbine_geometry(params)
        detail = exc_info.value.detail
        assert "field" in detail, f"Detail missing 'field' key: {detail}"
        assert detail["field"] == "rotor_inlet_radius", (
            f"Expected field='rotor_inlet_radius', got: {detail['field']!r}"
        )
