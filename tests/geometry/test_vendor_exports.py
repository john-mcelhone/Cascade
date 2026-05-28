"""Regression tests for the three vendor turbomachinery geometry formats
(ADAPT-042):

- ANSYS TurboGrid `.curve`
- Surface point cloud `.dat`
- CGNS `.cgns` (HDF5)

Each test builds a microturbine-scale centrifugal impeller, exports to
the target format, and asserts the file is structurally valid. The CGNS
test re-opens the file with h5py and verifies the canonical group /
dataset layout downstream tools (Star-CCM+, Fluent, TurboGrid) expect.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from cascade.geometry import (
    MeshLOD,
    export_cgns,
    export_surface_point_cloud,
    export_turbogrid_curve,
    impeller_mesh,
)
from cascade.meanline.centrifugal_compressor import (
    CentrifugalCompressorGeometry,
)


def _microturbine_impeller() -> CentrifugalCompressorGeometry:
    """A canonical microturbine-scale centrifugal impeller.

    Sized between the Eckardt Rotor O reference and a Capstone C30 —
    small enough to exercise the proportional-bore code path
    (ADAPT-030) and large enough to give a non-trivial mesh at PREVIEW
    LOD.
    """
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
# TurboGrid `.curve`
# -----------------------------------------------------------------------------


def test_turbogrid_curve_emits_four_curves(tmp_path: Path) -> None:
    """The output must declare exactly four `# curve <name>` blocks:
    hub, shroud, LE, TE.
    """
    g = _microturbine_impeller()
    out = tmp_path / "impeller.curve"
    export_turbogrid_curve(g, out, n_samples=32)

    assert out.exists()
    text = out.read_text(encoding="ascii")
    assert out.stat().st_size > 0

    # Split on the curve header sentinel; we get a leading "header"
    # chunk + one chunk per curve.
    chunks = text.split("# curve ")
    # First chunk is the file header (no `# curve ` prefix); subsequent
    # chunks are one per curve. Total length should be 1 (header) + 4.
    assert len(chunks) == 5, (
        f"expected 1 header + 4 curve blocks, got {len(chunks) - 1} curves"
    )

    # Each curve chunk should start with its name and contain rows of
    # exactly two numeric columns.
    names = [c.splitlines()[0].strip() for c in chunks[1:]]
    assert names == ["hub", "shroud", "LE", "TE"]


def test_turbogrid_curve_rows_are_two_columns(tmp_path: Path) -> None:
    """Every non-comment, non-blank line is two floats: x_m and r_m."""
    g = _microturbine_impeller()
    out = tmp_path / "impeller.curve"
    export_turbogrid_curve(g, out, n_samples=24)

    for line in out.read_text(encoding="ascii").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split()
        assert len(parts) == 2, (
            f"non-comment row must have 2 columns; got {line!r}"
        )
        # Both must parse as floats.
        float(parts[0])
        float(parts[1])


def test_turbogrid_curve_hub_x_monotonic_ish(tmp_path: Path) -> None:
    """The hub curve's x (axial) coordinate must be weakly monotonic
    from inlet to outlet — a degenerate hub with kinks would break
    TurboGrid's blade-to-blade meshing.
    """
    g = _microturbine_impeller()
    out = tmp_path / "impeller.curve"
    export_turbogrid_curve(g, out, n_samples=48)

    text = out.read_text(encoding="ascii")
    # Locate the hub block.
    hub_chunk = text.split("# curve hub", 1)[1].split("# curve", 1)[0]
    hub_xs = [
        float(line.split()[0])
        for line in hub_chunk.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert len(hub_xs) >= 8
    diffs = np.diff(hub_xs)
    # Allow a tiny tolerance for round-trip rounding; require globally
    # non-decreasing (centrifugal flow sweeps z from inlet to outlet).
    assert (diffs >= -1e-6).all(), f"hub axial coord not monotonic: {hub_xs}"


def test_turbogrid_curve_rejects_low_n_samples(tmp_path: Path) -> None:
    g = _microturbine_impeller()
    with pytest.raises(ValueError, match="n_samples"):
        export_turbogrid_curve(g, tmp_path / "x.curve", n_samples=1)


# -----------------------------------------------------------------------------
# Surface point cloud `.dat`
# -----------------------------------------------------------------------------


def test_point_cloud_has_n_lines(tmp_path: Path) -> None:
    """Asserts the file has exactly ``sample_density`` data lines."""
    g = _microturbine_impeller()
    mesh = impeller_mesh(g, lod=MeshLOD.PREVIEW, with_splitter=False)
    out = tmp_path / "impeller.dat"
    export_surface_point_cloud(mesh, out, sample_density=500)

    data_lines = [
        line
        for line in out.read_text(encoding="ascii").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert len(data_lines) == 500


def test_point_cloud_each_line_six_columns(tmp_path: Path) -> None:
    """Each data row is ``x y z nx ny nz`` — six tab-separated floats."""
    g = _microturbine_impeller()
    mesh = impeller_mesh(g, lod=MeshLOD.PREVIEW, with_splitter=False)
    out = tmp_path / "impeller.dat"
    export_surface_point_cloud(mesh, out, sample_density=200)

    for line in out.read_text(encoding="ascii").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split()
        assert len(parts) == 6, (
            f"point-cloud row must have 6 columns; got {len(parts)}: "
            f"{line!r}"
        )
        for tok in parts:
            float(tok)


def test_point_cloud_normals_unit_length(tmp_path: Path) -> None:
    """The face-normal columns must be unit vectors (||n|| ≈ 1).

    Many CFD pre-processors (Star-CCM+ in particular) silently produce
    garbage if any input normal has zero or wildly off-unit length.
    """
    g = _microturbine_impeller()
    mesh = impeller_mesh(g, lod=MeshLOD.PREVIEW, with_splitter=False)
    out = tmp_path / "impeller.dat"
    export_surface_point_cloud(mesh, out, sample_density=150)

    rows = []
    for line in out.read_text(encoding="ascii").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        rows.append([float(x) for x in line.split()])
    arr = np.asarray(rows)
    normals = arr[:, 3:6]
    lengths = np.linalg.norm(normals, axis=1)
    assert np.allclose(lengths, 1.0, atol=1e-3), (
        f"normals not unit length: min={lengths.min():.4f}, "
        f"max={lengths.max():.4f}"
    )


def test_point_cloud_rejects_empty_mesh(tmp_path: Path) -> None:
    import trimesh

    empty = trimesh.Trimesh(vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=int))
    with pytest.raises(ValueError, match="empty"):
        export_surface_point_cloud(empty, tmp_path / "x.dat")


# -----------------------------------------------------------------------------
# CGNS `.cgns` (HDF5)
# -----------------------------------------------------------------------------


def test_cgns_file_has_canonical_groups(tmp_path: Path) -> None:
    """Open the CGNS file with h5py and assert the canonical layout."""
    h5py = pytest.importorskip("h5py")

    g = _microturbine_impeller()
    mesh = impeller_mesh(g, lod=MeshLOD.PREVIEW, with_splitter=False)
    out = tmp_path / "impeller.cgns"
    export_cgns(mesh, out)

    assert out.exists()
    assert out.stat().st_size > 0

    with h5py.File(out, "r") as fh:
        # CGNSLibraryVersion at the root.
        assert "CGNSLibraryVersion" in fh

        # Exactly one Base in the file (besides the version node).
        base_keys = [k for k in fh.keys() if k != "CGNSLibraryVersion"]
        assert len(base_keys) == 1
        base = fh[base_keys[0]]
        assert base.attrs["label"] == b"CGNSBase_t"

        # The Base has exactly one Zone.
        zone_keys = [k for k in base.keys() if base[k].attrs.get("label") == b"Zone_t"]
        assert len(zone_keys) == 1
        zone = base[zone_keys[0]]

        # Zone has GridCoordinates with three coordinate arrays.
        assert "GridCoordinates" in zone
        grid = zone["GridCoordinates"]
        for axis in ("CoordinateX", "CoordinateY", "CoordinateZ"):
            assert axis in grid, f"missing coordinate group {axis}"
            arr = grid[axis][" data"]
            assert arr.dtype == np.float64
            assert arr.shape == (mesh.vertices.shape[0],)

        # Zone has Elements with TRI_3 type and element range covering
        # all triangles.
        assert "Elements_Tris" in zone
        elements = zone["Elements_Tris"]
        type_data = elements[" data"][:]
        assert int(type_data[0]) == 5  # CGNS TRI_3 element type code
        elem_range = elements["ElementRange"][" data"][:]
        assert tuple(elem_range) == (1, mesh.faces.shape[0])

        # Connectivity has 3 * n_tris entries.
        conn = elements["ElementConnectivity"][" data"][:]
        assert conn.shape == (3 * mesh.faces.shape[0],)
        # 1-indexed; max index is n_vertices.
        assert int(conn.min()) >= 1
        assert int(conn.max()) <= mesh.vertices.shape[0]

        # ZoneBC carries the five named regions.
        assert "ZoneBC" in zone
        zbc = zone["ZoneBC"]
        for region in ("Hub", "Shroud", "Blade", "Inlet", "Outlet"):
            assert region in zbc, f"missing BC region {region}"


def test_cgns_coordinates_match_mesh_vertices(tmp_path: Path) -> None:
    """The (X, Y, Z) coordinate datasets must equal the mesh vertices."""
    h5py = pytest.importorskip("h5py")

    g = _microturbine_impeller()
    mesh = impeller_mesh(g, lod=MeshLOD.PREVIEW, with_splitter=False)
    out = tmp_path / "impeller.cgns"
    export_cgns(mesh, out)

    with h5py.File(out, "r") as fh:
        base_key = next(k for k in fh.keys() if k != "CGNSLibraryVersion")
        zone_key = next(
            k for k in fh[base_key].keys()
            if fh[base_key][k].attrs.get("label") == b"Zone_t"
        )
        grid = fh[base_key][zone_key]["GridCoordinates"]
        x = grid["CoordinateX"][" data"][:]
        y = grid["CoordinateY"][" data"][:]
        z = grid["CoordinateZ"][" data"][:]

    np.testing.assert_allclose(x, mesh.vertices[:, 0])
    np.testing.assert_allclose(y, mesh.vertices[:, 1])
    np.testing.assert_allclose(z, mesh.vertices[:, 2])


def test_cgns_rejects_empty_mesh(tmp_path: Path) -> None:
    import trimesh

    empty = trimesh.Trimesh(vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=int))
    with pytest.raises(ValueError, match="empty"):
        export_cgns(empty, tmp_path / "x.cgns")
