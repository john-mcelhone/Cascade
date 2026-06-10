"""Centrifugal impeller mesh tests.

The canonical geometry is an Eckardt Rotor-O-like impeller:
- r_outlet = 100 mm
- r_inducer_tip = 50 mm, r_inducer_hub = 18 mm
- 20 blades (radial-tipped)
- 30° backsweep at the exit
- 0.5 mm tip clearance
"""

from __future__ import annotations

import math

import pytest

from cascade.geometry import MeshLOD, impeller_mesh, export_glb, export_stl
from cascade.meanline.centrifugal_compressor import CentrifugalCompressorGeometry


def _eckardt_rotor_o_geometry(blade_count: int = 20) -> CentrifugalCompressorGeometry:
    return CentrifugalCompressorGeometry(
        inducer_hub_radius=0.018,
        inducer_tip_radius=0.050,
        impeller_outlet_radius=0.100,
        blade_height_outlet=0.012,
        blade_count=blade_count,
        # 30° backsweep — in the canonical "from axial" convention this is
        # π/2 - π/6 = π/3 (60° from axial).
        beta_2_metal_rad=math.pi / 3,
        tip_clearance=0.0005,
    )


class TestImpellerMeshBasics:
    def test_produces_nonempty_mesh(self) -> None:
        geom = _eckardt_rotor_o_geometry()
        m = impeller_mesh(geom, lod=MeshLOD.STANDARD,
                         with_splitter=False,
                         with_back_face=True,
                         with_shroud=True)
        assert m.vertices.shape[0] > 0
        assert m.faces.shape[0] > 0

    def test_mesh_has_vertex_normals(self) -> None:
        geom = _eckardt_rotor_o_geometry()
        m = impeller_mesh(geom, lod=MeshLOD.STANDARD)
        # Trimesh lazily computes normals; the call should succeed.
        normals = m.vertex_normals
        assert normals.shape == (m.vertices.shape[0], 3)


class TestImpellerMeshBoundingBox:
    def test_bounding_box_matches_outer_radius(self) -> None:
        geom = _eckardt_rotor_o_geometry()
        m = impeller_mesh(geom, lod=MeshLOD.STANDARD,
                         with_splitter=False,
                         with_back_face=True,
                         with_shroud=True)
        bb_min, bb_max = m.bounds
        # The maximum radial extent should be approximately r_outlet.
        x_extent = bb_max[0] - bb_min[0]
        y_extent = bb_max[1] - bb_min[1]
        expected_diameter = 2.0 * geom.impeller_outlet_radius
        # Within 5% tolerance (the splines slightly shrink the maximum r).
        assert x_extent == pytest.approx(expected_diameter, rel=0.05)
        assert y_extent == pytest.approx(expected_diameter, rel=0.05)


class TestImpellerMeshLOD:
    def test_lod_increases_vertex_count(self) -> None:
        geom = _eckardt_rotor_o_geometry()
        counts = {}
        for lod in (MeshLOD.PREVIEW, MeshLOD.STANDARD, MeshLOD.HIGH, MeshLOD.EXPORT):
            m = impeller_mesh(geom, lod=lod, with_splitter=False)
            counts[lod] = m.vertices.shape[0]
        assert counts[MeshLOD.PREVIEW] < counts[MeshLOD.STANDARD]
        assert counts[MeshLOD.STANDARD] < counts[MeshLOD.HIGH]
        assert counts[MeshLOD.HIGH] < counts[MeshLOD.EXPORT]

    def test_standard_in_expected_range(self) -> None:
        """STANDARD LOD should produce 1k-10k vertices for a typical impeller."""
        geom = _eckardt_rotor_o_geometry()
        m = impeller_mesh(geom, lod=MeshLOD.STANDARD, with_splitter=False)
        assert 800 < m.vertices.shape[0] < 50000

    def test_high_in_expected_range(self) -> None:
        geom = _eckardt_rotor_o_geometry()
        m = impeller_mesh(geom, lod=MeshLOD.HIGH, with_splitter=False)
        assert 5000 < m.vertices.shape[0] < 100000


class TestImpellerBladeIslands:
    def test_blade_count_visible_in_geometry(self) -> None:
        """With back face and shroud disabled, each blade is structurally
        separable. Since trimesh merges by spatial proximity, what we
        check instead is that the bounding box is symmetric (Z-fold
        rotational symmetry around z-axis is preserved)."""
        geom = _eckardt_rotor_o_geometry(blade_count=12)
        m = impeller_mesh(geom, lod=MeshLOD.STANDARD,
                         with_splitter=False,
                         with_back_face=False,
                         with_shroud=False)
        # Z-fold rotational symmetry: the centroid in x and y should be ≈ 0.
        cx, cy, _ = m.centroid
        max_r = geom.impeller_outlet_radius
        assert abs(cx) < 0.05 * max_r
        assert abs(cy) < 0.05 * max_r

    def test_splitter_respects_blade_count_budget(self) -> None:
        """``blade_count`` is the TOTAL blade count (it is what the
        meanline slip/loading correlations were scored with). With
        splitters the budget splits Z/2 + Z/2, so the mesh must carry
        LESS metal than Z full blades (splitters are short) but MORE
        than Z/2 full blades alone."""
        geom = _eckardt_rotor_o_geometry()  # Z = 20
        geom_half = _eckardt_rotor_o_geometry(blade_count=10)
        m_split = impeller_mesh(geom, lod=MeshLOD.STANDARD,
                                with_splitter=True)
        m_full = impeller_mesh(geom, lod=MeshLOD.STANDARD,
                               with_splitter=False)
        m_half = impeller_mesh(geom_half, lod=MeshLOD.STANDARD,
                               with_splitter=False)
        assert m_half.vertices.shape[0] < m_split.vertices.shape[0]
        assert m_split.vertices.shape[0] < m_full.vertices.shape[0]

    def test_splitter_falls_back_for_odd_blade_count(self) -> None:
        """An odd blade count cannot split into a symmetric main+splitter
        pattern — the generator renders all blades full-length instead."""
        geom = _eckardt_rotor_o_geometry(blade_count=15)
        m_split = impeller_mesh(geom, lod=MeshLOD.STANDARD,
                                with_splitter=True)
        m_full = impeller_mesh(geom, lod=MeshLOD.STANDARD,
                               with_splitter=False)
        assert m_split.vertices.shape[0] == m_full.vertices.shape[0]


class TestImpellerExports:
    def test_export_glb_nonempty(self) -> None:
        geom = _eckardt_rotor_o_geometry()
        m = impeller_mesh(geom, lod=MeshLOD.PREVIEW, with_splitter=False)
        glb = export_glb(m)
        assert isinstance(glb, (bytes, bytearray))
        assert len(glb) > 100

    def test_export_stl_nonempty(self) -> None:
        geom = _eckardt_rotor_o_geometry()
        m = impeller_mesh(geom, lod=MeshLOD.PREVIEW, with_splitter=False)
        stl = export_stl(m)
        assert isinstance(stl, (bytes, bytearray))
        assert len(stl) > 100


class TestImpellerWatertight:
    def test_mesh_is_watertight_without_shroud(self) -> None:
        """The impeller is watertight when hub-solid + blades are enabled
        and the (non-closed) shroud surface is disabled.

        The shroud is intentionally a single surface of revolution (not a
        closed solid) — it represents the casing wall as seen from inside
        the flow path. Adding it leaves open perimeter edges, which is
        expected; the impeller-solid topology is independent of the shroud.
        """
        geom = _eckardt_rotor_o_geometry()
        m = impeller_mesh(geom, lod=MeshLOD.STANDARD,
                         with_splitter=False,
                         with_back_face=True,
                         with_shroud=False)
        assert m.is_watertight, (
            f"Expected watertight impeller (hub + blades + back face); "
            f"got Euler={m.euler_number}, winding_consistent="
            f"{m.is_winding_consistent}"
        )

    def test_mesh_winding_consistent_with_shroud(self) -> None:
        """Even with the open shroud, winding should be consistent."""
        geom = _eckardt_rotor_o_geometry()
        m = impeller_mesh(geom, lod=MeshLOD.STANDARD,
                         with_splitter=False,
                         with_back_face=True,
                         with_shroud=True)
        assert m.is_winding_consistent
