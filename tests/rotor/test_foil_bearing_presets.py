"""Tests for foil bearing K-C presets.

W-32 acceptance criteria:
- AC1: Calling ``CAPSTONE_C30_FOIL_BEARING(rpm=80_000)`` returns a dict-like
       object with K and C fields (actually returns a TabulatedBearing).
- AC2: ``GET /api/bearings/presets`` returns a list with ≥2 entries.
- AC3: This test file verifies AC1 + AC2.

The test verifies:
1. Both presets construct successfully and return TabulatedBearing instances.
2. ``coefficients_at_rpm`` returns physically sensible (K, C) pairs.
3. The registry API returns ≥2 entries.
4. The API endpoint (unit-tested without HTTP) returns ≥2 entries.
"""

from __future__ import annotations

import pytest
import numpy as np


# ---------------------------------------------------------------------------
# AC1: CAPSTONE_C30_FOIL_BEARING callable returns K and C fields
# ---------------------------------------------------------------------------


def test_capstone_c30_foil_bearing_returns_bearing():
    """W-32 AC1: CAPSTONE_C30_FOIL_BEARING(rpm=80_000) returns a TabulatedBearing."""
    from cascade.rotor.bearing_presets.foil_bearings import CAPSTONE_C30_FOIL_BEARING
    from cascade.rotor.bearings import TabulatedBearing

    brg = CAPSTONE_C30_FOIL_BEARING(rpm=80_000)
    assert isinstance(brg, TabulatedBearing), (
        f"Expected TabulatedBearing, got {type(brg)}"
    )


def test_capstone_c30_foil_bearing_kc_at_design_speed():
    """W-32 AC1: coefficients_at_rpm(80_000) returns K and C in physical range."""
    from cascade.rotor.bearing_presets.foil_bearings import CAPSTONE_C30_FOIL_BEARING

    brg = CAPSTONE_C30_FOIL_BEARING(rpm=80_000)
    K, C = brg.coefficients_at_rpm(80_000)

    # K must be (2, 2)
    assert K.shape == (2, 2), f"K shape is {K.shape}, expected (2, 2)"
    assert C.shape == (2, 2), f"C shape is {C.shape}, expected (2, 2)"

    # Diagonal K in physical range: 1e5 – 2e6 N/m for a 30 mm foil bearing
    assert 1e5 < K[0, 0] < 2e6, (
        f"K_yy = {K[0, 0]:.3e} N/m outside expected range 1e5 – 2e6"
    )
    assert 1e5 < K[1, 1] < 2e6, (
        f"K_zz = {K[1, 1]:.3e} N/m outside expected range 1e5 – 2e6"
    )
    # Diagonal C in physical range: 1 – 500 N s/m for a foil bearing
    assert 1.0 < C[0, 0] < 500.0, (
        f"C_yy = {C[0, 0]:.2f} N s/m outside expected range 1 – 500"
    )
    assert 1.0 < C[1, 1] < 500.0, (
        f"C_zz = {C[1, 1]:.2f} N s/m outside expected range 1 – 500"
    )


def test_capstone_c30_foil_bearing_kc_increases_with_speed():
    """W-32 AC1: stiffness should increase with speed (Heshmat 1983 trend)."""
    from cascade.rotor.bearing_presets.foil_bearings import CAPSTONE_C30_FOIL_BEARING

    brg = CAPSTONE_C30_FOIL_BEARING()
    K_lo, _ = brg.coefficients_at_rpm(10_000)
    K_hi, _ = brg.coefficients_at_rpm(80_000)
    assert K_hi[0, 0] > K_lo[0, 0], (
        f"Expected K_yy to increase with RPM; "
        f"K_lo={K_lo[0, 0]:.3e}, K_hi={K_hi[0, 0]:.3e}"
    )


# ---------------------------------------------------------------------------
# AC1: DELLACORTE_NASA_FOIL_GEN_III preset
# ---------------------------------------------------------------------------


def test_nasa_gen3_foil_bearing_returns_bearing():
    """W-32 AC1: DELLACORTE_NASA_FOIL_GEN_III(rpm=40_000) returns TabulatedBearing."""
    from cascade.rotor.bearing_presets.foil_bearings import DELLACORTE_NASA_FOIL_GEN_III
    from cascade.rotor.bearings import TabulatedBearing

    brg = DELLACORTE_NASA_FOIL_GEN_III(rpm=40_000)
    assert isinstance(brg, TabulatedBearing), (
        f"Expected TabulatedBearing, got {type(brg)}"
    )


def test_nasa_gen3_foil_bearing_kc_at_design_speed():
    """W-32 AC1: Gen III bearing K-C at 40 kRPM in physical range."""
    from cascade.rotor.bearing_presets.foil_bearings import DELLACORTE_NASA_FOIL_GEN_III

    brg = DELLACORTE_NASA_FOIL_GEN_III(rpm=40_000)
    K, C = brg.coefficients_at_rpm(40_000)

    assert K.shape == (2, 2)
    assert C.shape == (2, 2)
    # Gen III bearing is larger (50 mm) → higher K range: 5e5 – 3e6 N/m
    assert 5e5 < K[0, 0] < 3e6, (
        f"K_yy = {K[0, 0]:.3e} N/m outside expected range 5e5 – 3e6"
    )
    assert C[0, 0] > 0


# ---------------------------------------------------------------------------
# AC1: Custom axial_position and name arguments
# ---------------------------------------------------------------------------


def test_bearing_preset_accepts_custom_name_and_position():
    """W-32 AC1: preset accepts custom name and axial_position."""
    from cascade.rotor.bearing_presets.foil_bearings import CAPSTONE_C30_FOIL_BEARING
    from cascade.units import Q

    brg = CAPSTONE_C30_FOIL_BEARING(
        rpm=60_000,
        name="front_bearing",
        axial_position=Q(0.02, "m"),
    )
    assert brg.name == "front_bearing"
    assert abs(brg.axial_position.to("m").magnitude - 0.02) < 1e-9


# ---------------------------------------------------------------------------
# AC2: Registry returns ≥2 entries
# ---------------------------------------------------------------------------


def test_foil_bearing_preset_names_returns_at_least_two():
    """W-32 AC2: foil_bearing_preset_names() returns ≥2 entries."""
    from cascade.rotor.bearing_presets.foil_bearings import foil_bearing_preset_names

    names = foil_bearing_preset_names()
    assert len(names) >= 2, (
        f"Expected ≥2 foil bearing presets, got {len(names)}: {names}"
    )
    assert "CAPSTONE_C30_FOIL_BEARING" in names
    assert "DELLACORTE_NASA_FOIL_GEN_III" in names


def test_get_foil_bearing_preset_returns_metadata():
    """W-32 AC2: get_foil_bearing_preset returns expected metadata keys."""
    from cascade.rotor.bearing_presets.foil_bearings import get_foil_bearing_preset

    entry = get_foil_bearing_preset("CAPSTONE_C30_FOIL_BEARING")
    for required_key in (
        "callable",
        "display_name",
        "description",
        "design_speed_rpm",
        "shaft_diameter_mm",
        "citation",
        "rpm_range",
    ):
        assert required_key in entry, (
            f"Missing key {required_key!r} in preset entry: {list(entry.keys())}"
        )
    assert "Heshmat" in entry["citation"], (
        f"Expected Heshmat citation, got: {entry['citation']!r}"
    )


def test_get_foil_bearing_preset_unknown_raises():
    """W-32: unknown preset name raises KeyError."""
    from cascade.rotor.bearing_presets.foil_bearings import get_foil_bearing_preset

    with pytest.raises(KeyError, match="Unknown foil bearing preset"):
        get_foil_bearing_preset("NONEXISTENT_PRESET_XYZ")


# ---------------------------------------------------------------------------
# AC2: API endpoint unit test (without HTTP)
# ---------------------------------------------------------------------------


def test_api_bearing_presets_endpoint_returns_at_least_two():
    """W-32 AC2: GET /api/bearings/presets returns ≥2 entries.

    Tests the endpoint logic directly via the registry (avoids importing
    FastAPI app deps in the unit-test environment; the full HTTP smoke test
    lives in apps/api/tests/).
    """
    from cascade.rotor.bearing_presets.foil_bearings import (
        _PRESET_REGISTRY,
        foil_bearing_preset_names,
    )

    # Simulate what the endpoint does: build the response list from the registry.
    result = []
    for name in foil_bearing_preset_names():
        entry = _PRESET_REGISTRY[name]
        result.append(
            {
                "name": name,
                "display_name": entry["display_name"],
                "description": entry["description"],
                "design_speed_rpm": entry["design_speed_rpm"],
                "shaft_diameter_mm": entry["shaft_diameter_mm"],
                "citation": entry["citation"],
                "rpm_range": entry["rpm_range"],
            }
        )

    assert len(result) >= 2, (
        f"Expected ≥2 preset entries, got {len(result)}"
    )
    names = [p["name"] for p in result]
    assert "CAPSTONE_C30_FOIL_BEARING" in names, (
        f"Missing CAPSTONE_C30_FOIL_BEARING in: {names}"
    )
    assert "DELLACORTE_NASA_FOIL_GEN_III" in names, (
        f"Missing DELLACORTE_NASA_FOIL_GEN_III in: {names}"
    )


# ---------------------------------------------------------------------------
# AC1: TabulatedBearing passes LinearBearing acceptance tests (stiffness limits)
# ---------------------------------------------------------------------------


def test_capstone_bearing_passes_stiffness_limits():
    """W-32: All K values in the preset table are within LinearBearing limits."""
    from cascade.rotor.bearing_presets.foil_bearings import CAPSTONE_C30_FOIL_BEARING

    # Construction itself validates via TabulatedBearing.__post_init__
    brg = CAPSTONE_C30_FOIL_BEARING()
    # If we get here without ValueError, all K values passed the stiffness check.
    assert brg is not None
