"""W-18: TurboGrid NDF export tests.

Acceptance criteria:
- AC1: endpoint/function returns a text file with sections for hub, shroud,
  and blade curves.
- AC2: each section contains the expected column structure (verifiable by
  parsing).
- AC3: hub and shroud have >= 40 points each; blade has >= 25 points per
  spanwise section.
- AC4: the blade curve includes theta (circumferential) in addition to x and r.
- AC5: test verifies AC1-AC4 (this file).

Does NOT require ``cascade[cad]`` — NDF is pure point-data, no OCCT needed.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from cascade.geometry import export_turbogrid_ndf
from cascade.meanline.centrifugal_compressor import CentrifugalCompressorGeometry
from cascade.meanline.radial_turbine import RadialTurbineGeometry


# ---------------------------------------------------------------------------
# Shared fixture geometry — AT-100 default microturbine-scale impeller
# ---------------------------------------------------------------------------

def _at100_compressor() -> CentrifugalCompressorGeometry:
    """AT-100 default centrifugal compressor geometry (seed project)."""
    return CentrifugalCompressorGeometry(
        inducer_hub_radius=0.018,
        inducer_tip_radius=0.050,
        impeller_outlet_radius=0.100,
        blade_height_outlet=0.012,
        blade_count=18,
        beta_2_metal_rad=math.pi / 3,
        tip_clearance=0.0005,
    )


def _at100_turbine() -> RadialTurbineGeometry:
    """AT-100 default radial inflow turbine geometry."""
    return RadialTurbineGeometry(
        rotor_inlet_radius=0.050,
        rotor_outlet_radius_hub=0.012,
        rotor_outlet_radius_tip=0.030,
        blade_height_inlet=0.010,
        blade_height_outlet=0.018,  # r2_tip - r2_hub
        blade_count=14,
        inlet_metal_angle_rad=0.0,
        exducer_angle_rad=math.pi / 3,
        tip_clearance=0.0003,
    )


# ---------------------------------------------------------------------------
# AC1 — file has correct sections
# ---------------------------------------------------------------------------

def test_ndf_has_all_four_sections(tmp_path: Path) -> None:
    """AC1: NDF file contains [HUB_CURVE], [SHROUD_CURVE],
    [BLADE_PROFILE_HUB], [BLADE_PROFILE_SHROUD] sections."""
    g = _at100_compressor()
    out = tmp_path / "at100.ndf"
    export_turbogrid_ndf(g, out)

    assert out.exists()
    text = out.read_text(encoding="ascii")
    assert len(text) > 1000, "NDF file is suspiciously small"

    for section in ("[HUB_CURVE]", "[SHROUD_CURVE]",
                    "[BLADE_PROFILE_HUB]", "[BLADE_PROFILE_SHROUD]"):
        assert section in text, f"missing NDF section: {section}"


def test_ndf_turbine_has_all_four_sections(tmp_path: Path) -> None:
    """AC1 for radial turbine geometry."""
    g = _at100_turbine()
    out = tmp_path / "at100_rit.ndf"
    export_turbogrid_ndf(g, out)

    text = out.read_text(encoding="ascii")
    for section in ("[HUB_CURVE]", "[SHROUD_CURVE]",
                    "[BLADE_PROFILE_HUB]", "[BLADE_PROFILE_SHROUD]"):
        assert section in text, f"missing NDF section for RIT: {section}"


# ---------------------------------------------------------------------------
# AC2 — correct column structure
# ---------------------------------------------------------------------------

def _parse_section(text: str, section_name: str) -> list[list[float]]:
    """Extract numeric rows from a named section in the NDF text.

    Sections are delimited by lines that start with ``[`` (not inside
    comments). The column-header comment ``# x[m]   r[m]`` contains a
    ``[`` character — we must only treat a ``[`` at the start of a
    non-comment line as a section delimiter.
    """
    start_marker = f"[{section_name}]"
    lines = text.splitlines()
    # Find the section start line.
    start_idx = None
    for i, line in enumerate(lines):
        if line.strip() == start_marker:
            start_idx = i + 1
            break
    if start_idx is None:
        return []
    rows: list[list[float]] = []
    for line in lines[start_idx:]:
        stripped = line.strip()
        # Stop at the next section header (non-comment line starting with '[').
        if stripped.startswith("[") and not stripped.startswith("#"):
            break
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        rows.append([float(p) for p in parts])
    return rows


def test_hub_curve_two_columns(tmp_path: Path) -> None:
    """AC2: [HUB_CURVE] rows have exactly 2 columns (x, r)."""
    g = _at100_compressor()
    out = tmp_path / "test.ndf"
    export_turbogrid_ndf(g, out)
    rows = _parse_section(out.read_text(), "HUB_CURVE")
    assert all(len(row) == 2 for row in rows), (
        f"HUB_CURVE has rows with != 2 columns: "
        f"{[len(r) for r in rows if len(r) != 2][:5]}"
    )


def test_shroud_curve_two_columns(tmp_path: Path) -> None:
    """AC2: [SHROUD_CURVE] rows have exactly 2 columns (x, r)."""
    g = _at100_compressor()
    out = tmp_path / "test.ndf"
    export_turbogrid_ndf(g, out)
    rows = _parse_section(out.read_text(), "SHROUD_CURVE")
    assert all(len(row) == 2 for row in rows)


def test_blade_profile_hub_three_columns(tmp_path: Path) -> None:
    """AC2 + AC4: [BLADE_PROFILE_HUB] rows have exactly 3 columns
    (x, r, theta) — theta is the circumferential coordinate."""
    g = _at100_compressor()
    out = tmp_path / "test.ndf"
    export_turbogrid_ndf(g, out)
    rows = _parse_section(out.read_text(), "BLADE_PROFILE_HUB")
    assert all(len(row) == 3 for row in rows), (
        f"BLADE_PROFILE_HUB has rows with != 3 columns"
    )


def test_blade_profile_shroud_three_columns(tmp_path: Path) -> None:
    """AC2 + AC4: [BLADE_PROFILE_SHROUD] rows have exactly 3 columns."""
    g = _at100_compressor()
    out = tmp_path / "test.ndf"
    export_turbogrid_ndf(g, out)
    rows = _parse_section(out.read_text(), "BLADE_PROFILE_SHROUD")
    assert all(len(row) == 3 for row in rows)


# ---------------------------------------------------------------------------
# AC3 — point-count requirements
# ---------------------------------------------------------------------------

def test_hub_has_at_least_40_points(tmp_path: Path) -> None:
    """AC3: hub curve has >= 40 points at default n_hub=50."""
    g = _at100_compressor()
    out = tmp_path / "test.ndf"
    export_turbogrid_ndf(g, out, n_hub=50)
    rows = _parse_section(out.read_text(), "HUB_CURVE")
    assert len(rows) >= 40, f"hub has only {len(rows)} points, need >= 40"


def test_shroud_has_at_least_40_points(tmp_path: Path) -> None:
    """AC3: shroud curve has >= 40 points at default n_shroud=50."""
    g = _at100_compressor()
    out = tmp_path / "test.ndf"
    export_turbogrid_ndf(g, out, n_shroud=50)
    rows = _parse_section(out.read_text(), "SHROUD_CURVE")
    assert len(rows) >= 40, f"shroud has only {len(rows)} points, need >= 40"


def test_blade_hub_has_at_least_25_points(tmp_path: Path) -> None:
    """AC3: blade hub profile has >= 25 points at default n_blade=30."""
    g = _at100_compressor()
    out = tmp_path / "test.ndf"
    export_turbogrid_ndf(g, out, n_blade=30)
    rows = _parse_section(out.read_text(), "BLADE_PROFILE_HUB")
    assert len(rows) >= 25, f"BLADE_PROFILE_HUB has only {len(rows)} points"


def test_blade_shroud_has_at_least_25_points(tmp_path: Path) -> None:
    """AC3: blade shroud profile has >= 25 points."""
    g = _at100_compressor()
    out = tmp_path / "test.ndf"
    export_turbogrid_ndf(g, out, n_blade=30)
    rows = _parse_section(out.read_text(), "BLADE_PROFILE_SHROUD")
    assert len(rows) >= 25, f"BLADE_PROFILE_SHROUD has only {len(rows)} points"


# ---------------------------------------------------------------------------
# AC4 — theta (circumferential) is present and physically meaningful
# ---------------------------------------------------------------------------

def test_blade_profile_theta_is_nonzero_and_monotonic(tmp_path: Path) -> None:
    """AC4: theta values in blade profile start near zero and increase
    (centrifugal compressor wraps in the positive-theta direction)."""
    g = _at100_compressor()
    out = tmp_path / "test.ndf"
    export_turbogrid_ndf(g, out, n_blade=30)
    rows = _parse_section(out.read_text(), "BLADE_PROFILE_HUB")
    thetas = [row[2] for row in rows]
    # First theta should be at or very near zero (LE camber starts at 0).
    assert abs(thetas[0]) < 1e-9, f"theta[0] != 0: {thetas[0]}"
    # Theta should be monotonically non-decreasing (camber wraps positively).
    diffs = np.diff(thetas)
    assert (diffs >= -1e-12).all(), (
        f"blade hub theta is not monotonically non-decreasing: "
        f"min diff = {diffs.min():.3e}"
    )
    # Total wrap should be > 0 and < 2*pi (physically plausible for a
    # back-swept centrifugal impeller — typically 0.2 – 0.8 rad).
    total_wrap = thetas[-1] - thetas[0]
    assert 0.0 < total_wrap < 2 * math.pi, (
        f"implausible total blade wrap angle: {total_wrap:.3f} rad"
    )


def test_blade_profile_theta_column_distinct_from_r(tmp_path: Path) -> None:
    """AC4: theta (col 3) is distinct from r (col 2) — they are not the
    same physical quantity and must differ throughout the profile."""
    g = _at100_compressor()
    out = tmp_path / "test.ndf"
    export_turbogrid_ndf(g, out, n_blade=30)
    rows = _parse_section(out.read_text(), "BLADE_PROFILE_HUB")
    r_vals = np.array([row[1] for row in rows])
    theta_vals = np.array([row[2] for row in rows])
    # r is in metres (order of magnitude ~0.02-0.1 for a microturbine);
    # theta is in radians (order of magnitude ~0-0.8).  They should not
    # be equal arrays.
    assert not np.allclose(r_vals, theta_vals), (
        "theta column looks identical to r column — theta not exported"
    )


# ---------------------------------------------------------------------------
# Edge-case / error tests
# ---------------------------------------------------------------------------

def test_ndf_rejects_n_hub_below_2(tmp_path: Path) -> None:
    g = _at100_compressor()
    with pytest.raises(ValueError, match="n_hub"):
        export_turbogrid_ndf(g, tmp_path / "x.ndf", n_hub=1)


def test_ndf_rejects_n_shroud_below_2(tmp_path: Path) -> None:
    g = _at100_compressor()
    with pytest.raises(ValueError, match="n_shroud"):
        export_turbogrid_ndf(g, tmp_path / "x.ndf", n_shroud=1)


def test_ndf_rejects_n_blade_below_2(tmp_path: Path) -> None:
    g = _at100_compressor()
    with pytest.raises(ValueError, match="n_blade"):
        export_turbogrid_ndf(g, tmp_path / "x.ndf", n_blade=1)


def test_ndf_rejects_unsupported_geometry(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        export_turbogrid_ndf("not-a-geometry", tmp_path / "x.ndf")


def test_hub_x_monotonic(tmp_path: Path) -> None:
    """Hub axial coordinate must increase from inlet to outlet
    (a non-monotonic hub would break TurboGrid meshing)."""
    g = _at100_compressor()
    out = tmp_path / "test.ndf"
    export_turbogrid_ndf(g, out)
    rows = _parse_section(out.read_text(), "HUB_CURVE")
    xs = np.array([row[0] for row in rows])
    diffs = np.diff(xs)
    assert (diffs >= -1e-9).all(), (
        f"hub x not monotonic: first bad diff {diffs[diffs < -1e-9][:3]}"
    )


def test_ndf_header_present(tmp_path: Path) -> None:
    """File should open with a comment header identifying it as a Cascade NDF."""
    g = _at100_compressor()
    out = tmp_path / "test.ndf"
    export_turbogrid_ndf(g, out)
    first_line = out.read_text().splitlines()[0]
    assert first_line.startswith("#"), (
        f"NDF first line not a comment: {first_line!r}"
    )
    assert "TurboGrid" in first_line or "Cascade" in out.read_text(), (
        "NDF header doesn't mention TurboGrid or Cascade"
    )
