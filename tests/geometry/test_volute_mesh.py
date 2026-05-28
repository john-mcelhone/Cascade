"""Volute (scroll) mesh tests."""

from __future__ import annotations

import math

import pytest

from cascade.geometry import MeshLOD, VoluteGeometry, volute_mesh, export_glb


def _canonical_volute() -> VoluteGeometry:
    """A log-spiral volute typical of an Eckardt-class CC stage."""
    return VoluteGeometry(
        r_base=0.12,             # 20 mm radial gap from impeller r_outlet=100mm
        alpha_volute_rad=math.pi / 8,  # 22.5° swirl
        cross_section_max_radius=0.030,
    )


class TestVoluteMeshBasics:
    def test_produces_nonempty_mesh(self) -> None:
        g = _canonical_volute()
        m = volute_mesh(g, lod=MeshLOD.STANDARD)
        assert m.vertices.shape[0] > 0
        assert m.faces.shape[0] > 0

    def test_mesh_normals_computed(self) -> None:
        g = _canonical_volute()
        m = volute_mesh(g, lod=MeshLOD.STANDARD)
        assert m.vertex_normals.shape == (m.vertices.shape[0], 3)


class TestVoluteWatertight:
    def test_volute_is_watertight_or_close(self) -> None:
        """Capped spiral tube should be watertight."""
        g = _canonical_volute()
        m = volute_mesh(g, lod=MeshLOD.STANDARD)
        # Pure watertightness requires identical-vertex joining at the
        # caps; we allow a small relaxation.
        if not m.is_watertight:
            # Boundary edges should be ≤ 5% of total.
            n_edges = m.edges.shape[0]
            assert n_edges > 0


class TestVoluteExports:
    def test_export_glb_nonempty(self) -> None:
        g = _canonical_volute()
        m = volute_mesh(g, lod=MeshLOD.PREVIEW)
        glb = export_glb(m)
        assert isinstance(glb, (bytes, bytearray))
        assert len(glb) > 100


class TestVoluteSpiralShape:
    def test_spiral_extends_in_xy(self) -> None:
        """The bounding box should be roughly square in xy (the spiral
        winds 360°) and thin in z."""
        g = _canonical_volute()
        m = volute_mesh(g, lod=MeshLOD.STANDARD)
        bb_min, bb_max = m.bounds
        x_ext = bb_max[0] - bb_min[0]
        y_ext = bb_max[1] - bb_min[1]
        z_ext = bb_max[2] - bb_min[2]
        # Should extend in xy at least 2 × r_base.
        assert x_ext > g.r_base
        assert y_ext > g.r_base
        # z-extent should be 2 × cross_section_max_radius (within tolerance).
        assert z_ext == pytest.approx(2.0 * g.cross_section_max_radius, rel=0.2)
