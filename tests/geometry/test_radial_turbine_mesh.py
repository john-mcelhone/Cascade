"""Radial inflow turbine mesh tests.

Canonical geometry: Whitney & Stewart (1974) helium-cycle RIT analog.
- r_inlet (rotor LE) = 90 mm
- r_outlet_hub = 12 mm, r_outlet_tip = 50 mm
- 14 blades, radial-inlet (β₁_metal = 0)
- exducer angle ≈ 60° from axial
"""

from __future__ import annotations

import math

import pytest

from cascade.geometry import MeshLOD, impeller_mesh, export_glb, export_stl
from cascade.meanline.radial_turbine import RadialTurbineGeometry


def _whitney_stewart_geometry(blade_count: int = 14) -> RadialTurbineGeometry:
    return RadialTurbineGeometry(
        rotor_inlet_radius=0.090,
        rotor_outlet_radius_hub=0.012,
        rotor_outlet_radius_tip=0.050,
        blade_height_inlet=0.012,
        blade_height_outlet=0.038,
        blade_count=blade_count,
        inlet_metal_angle_rad=0.0,  # radial-inlet
        exducer_angle_rad=math.radians(60.0),
        tip_clearance=0.0005,
    )


class TestRadialTurbineMeshBasics:
    def test_produces_nonempty_mesh(self) -> None:
        g = _whitney_stewart_geometry()
        m = impeller_mesh(g, lod=MeshLOD.STANDARD,
                         with_splitter=False,
                         with_back_face=True,
                         with_shroud=True)
        assert m.vertices.shape[0] > 0
        assert m.faces.shape[0] > 0

    def test_bounding_box_radial_extent(self) -> None:
        g = _whitney_stewart_geometry()
        m = impeller_mesh(g, lod=MeshLOD.STANDARD)
        bb_min, bb_max = m.bounds
        # Max radial extent ≈ 2 × r_inlet = 0.18 m.
        x_extent = bb_max[0] - bb_min[0]
        expected = 2.0 * g.rotor_inlet_radius
        assert x_extent == pytest.approx(expected, rel=0.10)


class TestRadialTurbineLOD:
    def test_lod_monotonic(self) -> None:
        g = _whitney_stewart_geometry()
        counts = {}
        for lod in (MeshLOD.PREVIEW, MeshLOD.STANDARD, MeshLOD.HIGH, MeshLOD.EXPORT):
            m = impeller_mesh(g, lod=lod, with_splitter=False)
            counts[lod] = m.vertices.shape[0]
        assert counts[MeshLOD.PREVIEW] < counts[MeshLOD.STANDARD]
        assert counts[MeshLOD.STANDARD] < counts[MeshLOD.HIGH]
        assert counts[MeshLOD.HIGH] < counts[MeshLOD.EXPORT]

    def test_standard_vertex_range(self) -> None:
        g = _whitney_stewart_geometry()
        m = impeller_mesh(g, lod=MeshLOD.STANDARD, with_splitter=False)
        n = m.vertices.shape[0]
        assert 800 < n < 50000


class TestRadialTurbineExports:
    def test_glb_nonempty(self) -> None:
        g = _whitney_stewart_geometry()
        m = impeller_mesh(g, lod=MeshLOD.PREVIEW, with_splitter=False)
        glb = export_glb(m)
        assert isinstance(glb, (bytes, bytearray))
        assert len(glb) > 100

    def test_stl_nonempty(self) -> None:
        g = _whitney_stewart_geometry()
        m = impeller_mesh(g, lod=MeshLOD.PREVIEW, with_splitter=False)
        stl = export_stl(m)
        assert len(stl) > 100


class TestRadialTurbineFlowDirection:
    def test_flow_direction_axial_outlet(self) -> None:
        """For an RIT the outlet is at low z, the inlet at high z."""
        g = _whitney_stewart_geometry()
        m = impeller_mesh(g, lod=MeshLOD.STANDARD,
                         with_back_face=False,
                         with_shroud=False)
        bb_min, bb_max = m.bounds
        z_min, z_max = bb_min[2], bb_max[2]
        z_extent = z_max - z_min
        # Axial length is roughly 0.5 × r_inlet = 45 mm.
        assert z_extent == pytest.approx(0.5 * g.rotor_inlet_radius, rel=0.30)
