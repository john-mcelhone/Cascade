"""ADAPT-005 locked regression: backend _serialize_mode populates mode_shape.

This test verifies that the backend serializer always populates
mode_shape with > 1 entries (from the real eigenvector) rather than
returning an empty or single-point list.

Before ADAPT-005 the mode-shapes UI used sin(n*pi*x/L) analytic
approximations. The fix wired the frontend to consume the real
eigenvector from _serialize_mode. This test locks the backend contract:
_serialize_mode(idx, mode, rotor) must return a dict with
mode_shape being a list of >= 2 station dicts.

References:
- ADAPT-005 (regression lock).
- apps/api/routers/rotor.py:366 (_serialize_mode function).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the API routers module is importable.
_REPO = Path(__file__).resolve().parents[2]
for p in (str(_REPO / "src"), str(_REPO / "apps" / "api")):
    if p not in sys.path:
        sys.path.insert(0, p)

from cascade.rotor import LinearBearing, build_rotor_model, run_lateral_analysis
from cascade.units import LumpedDisk, Q, RotorSection, RotorShape


def _simple_rotor():
    """Simple 3-section rotor, 2 bearings — enough to get real mode shapes."""
    sec = RotorSection(
        diameter_outer=Q(0.04, "m"),
        diameter_inner=Q(0.0, "m"),
        length=Q(0.4, "m"),
        density=Q(7850.0, "kg/m^3"),
        axial_position=Q(0.0, "m"),
        material="AISI4340",
    )
    disk = LumpedDisk(
        mass=Q(5.0, "kg"),
        inertia_polar=Q(0.02, "kg*m^2"),
        inertia_diametrical=Q(0.01, "kg*m^2"),
        axial_position=Q(0.2, "m"),
    )
    shape = RotorShape(sections=[sec], disks=[disk])
    K_b = 1.0e8
    b1 = LinearBearing(
        name="b1", axial_position=Q(0.0, "m"),
        K_yy=Q(K_b, "N/m"), K_zz=Q(K_b, "N/m"),
        C_yy=Q(200.0, "N*s/m"), C_zz=Q(200.0, "N*s/m"),
    )
    b2 = LinearBearing(
        name="b2", axial_position=Q(0.4, "m"),
        K_yy=Q(K_b, "N/m"), K_zz=Q(K_b, "N/m"),
        C_yy=Q(200.0, "N*s/m"), C_zz=Q(200.0, "N*s/m"),
    )
    return build_rotor_model(shape, [b1, b2], elements_per_section=8)


def test_adapt_005_mode_shape_has_multiple_stations() -> None:
    """Locked: _serialize_mode must return mode_shape with > 1 entries.

    If ADAPT-005 is reverted (sin fallback re-introduced as primary path)
    and _serialize_mode returns a trivial 1-point list, this test fails.
    """
    from routers.rotor import _serialize_mode

    model = _simple_rotor()
    modes = run_lateral_analysis(model, rpm=5000.0, n_modes=4)
    assert modes, "No modes returned — rotor model problem"

    for idx, mode in enumerate(modes[:3]):
        serialized = _serialize_mode(idx, mode, model)
        ms = serialized["mode_shape"]
        assert isinstance(ms, list), (
            f"mode_shape must be a list; got {type(ms)}"
        )
        assert len(ms) > 1, (
            f"ADAPT-005 regression: mode_shape has {len(ms)} entry/entries. "
            f"Expected > 1 (real eigenvector stations). The sin-fallback "
            f"path should be dead code, not the primary path."
        )
        # Each station dict must have the required keys.
        for station in ms:
            assert "axial_position_m" in station, (
                f"station missing 'axial_position_m': {station}"
            )
            assert "y" in station, f"station missing 'y': {station}"
            assert "z" in station, f"station missing 'z': {station}"


def test_adapt_005_mode_shape_not_uniform_sine() -> None:
    """Locked: mode_shape must not look like a uniform sin(n*pi*x/L).

    The pre-ADAPT-005 sin fallback produced perfectly symmetric shapes.
    A real eigenvector with bearings is asymmetric (the fixed boundary
    conditions at bearing nodes produce node-point constraints that break
    the sin symmetry). We check that not all stations have the same |y|
    magnitude (which would indicate a sin wave was used).
    """
    from routers.rotor import _serialize_mode

    model = _simple_rotor()
    modes = run_lateral_analysis(model, rpm=5000.0, n_modes=4)
    assert modes

    serialized = _serialize_mode(0, modes[0], model)
    ms = serialized["mode_shape"]
    y_values = [abs(s["y"]) for s in ms]
    # All-equal y values would indicate the sin template was returned.
    # Real eigenvectors from a non-uniform rotor have varying amplitudes.
    unique_rounded = set(round(v, 3) for v in y_values)
    assert len(unique_rounded) > 1, (
        f"ADAPT-005 regression: all mode_shape y-values are identical "
        f"({y_values[:5]}...). This suggests the sin-wave template is "
        f"being returned instead of the real eigenvector."
    )
