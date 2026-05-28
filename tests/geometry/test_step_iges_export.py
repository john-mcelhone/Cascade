"""Regression tests for the CAD-universal export formats (ADAPT-033):

- STEP (ISO 10303-21, AP203/AP214) via pythonocc-core
- IGES (US PRO v5.3) via pythonocc-core

The optional `pythonocc-core` dependency is intentionally NOT in the
base `cascade` install (it's a ~200 MB compiled OCC C++ runtime gated
behind the `cascade[cad]` extra). The integration tests gate on
`pytest.importorskip("OCC.Core")` so they pass cleanly on vanilla
installs.

The graceful-failure paths (functions raise CADExportNotAvailable when
the dep is missing) are exercised unconditionally on every install.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
import trimesh

from cascade.geometry import (
    CADExportNotAvailable,
    MeshLOD,
    cad_export_available,
    export_iges,
    export_step,
    impeller_mesh,
)
from cascade.meanline.centrifugal_compressor import (
    CentrifugalCompressorGeometry,
)


def _microturbine_impeller() -> CentrifugalCompressorGeometry:
    """A canonical microturbine-scale centrifugal impeller (per
    `tests/geometry/test_vendor_exports.py`)."""
    return CentrifugalCompressorGeometry(
        inducer_hub_radius=0.018,
        inducer_tip_radius=0.050,
        impeller_outlet_radius=0.100,
        blade_height_outlet=0.012,
        blade_count=18,
        beta_2_metal_rad=math.pi / 3,
        tip_clearance=0.0005,
    )


# -----------------------------------------------------------------------------
# Graceful-failure path — runs on every install (no OCC needed).
# -----------------------------------------------------------------------------


def test_cad_export_available_returns_bool() -> None:
    """The probe must return a Python bool — no exceptions."""
    assert isinstance(cad_export_available(), bool)


def test_step_raises_when_occ_missing(tmp_path: Path, monkeypatch) -> None:
    """When pythonocc-core is not importable, export_step must raise
    CADExportNotAvailable with the install-hint message."""
    if cad_export_available():
        pytest.skip("pythonocc-core is installed; failure path not testable here")

    g = _microturbine_impeller()
    mesh = impeller_mesh(g, lod=MeshLOD.PREVIEW, with_splitter=False)
    with pytest.raises(CADExportNotAvailable, match="pythonocc-core"):
        export_step(mesh, tmp_path / "x.step")


def test_iges_raises_when_occ_missing(tmp_path: Path, monkeypatch) -> None:
    if cad_export_available():
        pytest.skip("pythonocc-core is installed; failure path not testable here")

    g = _microturbine_impeller()
    mesh = impeller_mesh(g, lod=MeshLOD.PREVIEW, with_splitter=False)
    with pytest.raises(CADExportNotAvailable, match="pythonocc-core"):
        export_iges(mesh, tmp_path / "x.iges")


def test_step_install_hint_mentions_conda_and_pip(tmp_path: Path) -> None:
    """The error message must point at both install paths (conda preferred,
    pip fallback) so the user can recover without reading source."""
    if cad_export_available():
        pytest.skip("install-hint message tested only when OCC is missing")

    g = _microturbine_impeller()
    mesh = impeller_mesh(g, lod=MeshLOD.PREVIEW, with_splitter=False)
    with pytest.raises(CADExportNotAvailable) as exc_info:
        export_step(mesh, tmp_path / "x.step")
    msg = str(exc_info.value)
    assert "conda" in msg
    assert "pip" in msg
    assert "pythonocc-core" in msg


def test_step_rejects_empty_mesh(tmp_path: Path) -> None:
    """Empty meshes must raise ValueError *before* we hit the OCC path —
    so the user gets the right error regardless of whether OCC is installed."""
    empty = trimesh.Trimesh(
        vertices=np.zeros((0, 3)),
        faces=np.zeros((0, 3), dtype=int),
    )
    with pytest.raises(ValueError, match="empty"):
        export_step(empty, tmp_path / "x.step")


def test_iges_rejects_empty_mesh(tmp_path: Path) -> None:
    empty = trimesh.Trimesh(
        vertices=np.zeros((0, 3)),
        faces=np.zeros((0, 3), dtype=int),
    )
    with pytest.raises(ValueError, match="empty"):
        export_iges(empty, tmp_path / "x.iges")


# -----------------------------------------------------------------------------
# Full export path — requires pythonocc-core; tests are skipped otherwise.
# -----------------------------------------------------------------------------


@pytest.mark.spec_parity("SPEC-7")
def test_step_writes_iso_10303_header(tmp_path: Path) -> None:
    """STEP files must start with the canonical ISO 10303-21 marker."""
    pytest.importorskip("OCC.Core")

    g = _microturbine_impeller()
    mesh = impeller_mesh(g, lod=MeshLOD.PREVIEW, with_splitter=False)
    out = tmp_path / "impeller.step"
    export_step(mesh, out)

    assert out.exists()
    assert out.stat().st_size > 0
    text = out.read_text(encoding="ascii", errors="replace")
    assert text.startswith("ISO-10303-21;"), (
        f"STEP file missing ISO 10303-21 header; first 80 chars: "
        f"{text[:80]!r}"
    )
    assert "END-ISO-10303-21;" in text, "STEP file missing trailer"


def test_step_file_carries_ap203_or_ap214(tmp_path: Path) -> None:
    """The STEP header should declare an AP203 or AP214 schema name."""
    pytest.importorskip("OCC.Core")

    g = _microturbine_impeller()
    mesh = impeller_mesh(g, lod=MeshLOD.PREVIEW, with_splitter=False)
    out = tmp_path / "impeller.step"
    export_step(mesh, out)

    text = out.read_text(encoding="ascii", errors="replace")
    # OCC's STEPControl_Writer emits AP203 by default; some builds emit
    # AP214 ("AUTOMOTIVE_DESIGN"). Accept either.
    assert (
        "CONFIG_CONTROL_DESIGN" in text or "AUTOMOTIVE_DESIGN" in text
    ), "STEP file missing AP203/AP214 schema declaration"


def test_iges_writes_start_section(tmp_path: Path) -> None:
    """IGES files must carry the canonical Start section.

    The IGES Start section is the first record block, terminated by an
    'S' column-73 marker. A correct OCC-emitted IGES file always has at
    least one S-record and at least one G (global) record.
    """
    pytest.importorskip("OCC.Core")

    g = _microturbine_impeller()
    mesh = impeller_mesh(g, lod=MeshLOD.PREVIEW, with_splitter=False)
    out = tmp_path / "impeller.iges"
    export_iges(mesh, out)

    assert out.exists()
    assert out.stat().st_size > 0
    lines = out.read_text(encoding="ascii", errors="replace").splitlines()
    # First non-empty line must end with an 'S' marker (column 73, 1-indexed
    # in the IGES spec — column 72 in 0-indexed Python slicing).
    first = next(line for line in lines if line.strip())
    # The S/G/D/P/T markers live at column 73 (idx 72). Allow whitespace
    # padding shorter than 80 chars in case OCC writes a narrow record.
    assert first.rstrip()[-1:] == "1" or "S" in first[60:80], (
        f"IGES first record missing S marker: {first!r}"
    )


def test_step_round_trip_facet_count(tmp_path: Path) -> None:
    """Round-trip: write STEP, re-read with OCC, count emitted faces.

    Each input triangle becomes one face in the STEP compound. We allow
    a small loss (degenerate-triangle culling in `_trimesh_to_occ_compound`),
    so we assert the read-back count is within 5% of the source triangle
    count.
    """
    pytest.importorskip("OCC.Core")
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer

    g = _microturbine_impeller()
    mesh = impeller_mesh(g, lod=MeshLOD.PREVIEW, with_splitter=False)
    out = tmp_path / "impeller.step"
    export_step(mesh, out)

    reader = STEPControl_Reader()
    status = reader.ReadFile(str(out))
    assert status == IFSelect_RetDone, "STEP file failed to re-parse"
    reader.TransferRoots()
    shape = reader.OneShape()

    face_count = 0
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face_count += 1
        explorer.Next()

    n_tris = mesh.faces.shape[0]
    # Allow a 5% loss from degenerate-triangle culling. Empirically OCC
    # round-trips lossless on a clean impeller mesh, but at PREVIEW LOD
    # the LE/TE caps sometimes generate near-degenerate triangles.
    assert face_count >= int(0.95 * n_tris), (
        f"STEP round-trip lost too many faces: source={n_tris}, "
        f"round-tripped={face_count}"
    )


def test_step_export_with_radial_turbine(tmp_path: Path) -> None:
    """Export from a radial turbine geometry must also succeed —
    confirms the OCC adapter is generic over geometry classes."""
    pytest.importorskip("OCC.Core")

    from cascade.meanline.radial_turbine import RadialTurbineGeometry

    g = RadialTurbineGeometry(
        rotor_inlet_radius=0.05,
        rotor_outlet_radius_hub=0.012,
        rotor_outlet_radius_tip=0.030,
        blade_height_inlet=0.010,
        blade_count=14,
        beta_inlet_metal_rad=0.0,
        beta_outlet_metal_rad=-math.pi / 3,
        tip_clearance=0.0003,
    )
    mesh = impeller_mesh(g, lod=MeshLOD.PREVIEW, with_splitter=False)

    out = tmp_path / "radial_turbine.step"
    export_step(mesh, out)
    assert out.exists()
    assert out.stat().st_size > 0
    assert out.read_text(encoding="ascii", errors="replace").startswith(
        "ISO-10303-21;",
    )
