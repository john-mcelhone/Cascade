"""Rotor shaft mesh tests."""

from __future__ import annotations

import pytest

from cascade.geometry import MeshLOD, rotor_shaft_mesh, export_glb
from cascade.units import LumpedDisk, Q, RotorSection, RotorShape


def _canonical_shape() -> RotorShape:
    """A representative microturbine rotor: one shaft section + one disk
    (the impeller). Mirrors the canonical test fixture in
    `tests/units/test_units.py`."""
    s1 = RotorSection(
        diameter_outer=Q(20.0, "mm"),
        diameter_inner=Q(0.0, "mm"),
        length=Q(150.0, "mm"),
        density=Q(7800.0, "kg/m^3"),
        axial_position=Q(0.0, "mm"),
        material="STEEL_AISI4340",
    )
    s2 = RotorSection(
        diameter_outer=Q(15.0, "mm"),
        diameter_inner=Q(0.0, "mm"),
        length=Q(50.0, "mm"),
        density=Q(7800.0, "kg/m^3"),
        axial_position=Q(150.0, "mm"),
        material="STEEL_AISI4340",
    )
    impeller = LumpedDisk(
        mass=Q(0.5, "kg"),
        inertia_polar=Q(1.0e-3, "kg * m^2"),
        inertia_diametrical=Q(5.0e-4, "kg * m^2"),
        axial_position=Q(75.0, "mm"),
    )
    return RotorShape(sections=[s1, s2], disks=[impeller])


class TestRotorMeshBasics:
    def test_produces_nonempty_mesh(self) -> None:
        shape = _canonical_shape()
        m = rotor_shaft_mesh(shape, lod=MeshLOD.STANDARD)
        assert m.vertices.shape[0] > 0
        assert m.faces.shape[0] > 0

    def test_axial_length_matches_shape(self) -> None:
        shape = _canonical_shape()
        m = rotor_shaft_mesh(shape, lod=MeshLOD.STANDARD)
        bb_min, bb_max = m.bounds
        z_ext = bb_max[2] - bb_min[2]
        expected_z = shape.length_total.to("m").magnitude
        assert z_ext == pytest.approx(expected_z, rel=0.1)

    def test_lod_affects_resolution(self) -> None:
        shape = _canonical_shape()
        m_preview = rotor_shaft_mesh(shape, lod=MeshLOD.PREVIEW)
        m_high = rotor_shaft_mesh(shape, lod=MeshLOD.HIGH)
        assert m_high.vertices.shape[0] > m_preview.vertices.shape[0]


class TestRotorMeshExports:
    def test_export_glb_nonempty(self) -> None:
        shape = _canonical_shape()
        m = rotor_shaft_mesh(shape, lod=MeshLOD.PREVIEW)
        glb = export_glb(m)
        assert len(glb) > 100


class TestRotorMeshDiskVisible:
    def test_disk_extends_beyond_shaft(self) -> None:
        """The lumped disk should produce a larger outer radius than the
        bare shaft."""
        # Shape with just one section, no disk:
        shape_no_disk = RotorShape(
            sections=[
                RotorSection(
                    diameter_outer=Q(20.0, "mm"),
                    diameter_inner=Q(0.0, "mm"),
                    length=Q(100.0, "mm"),
                    density=Q(7800.0, "kg/m^3"),
                    axial_position=Q(0.0, "mm"),
                    material="STEEL",
                )
            ],
            disks=[],
        )
        # With a hefty disk:
        shape_disk = RotorShape(
            sections=shape_no_disk.sections,
            disks=[
                LumpedDisk(
                    mass=Q(2.0, "kg"),
                    inertia_polar=Q(5.0e-3, "kg * m^2"),
                    inertia_diametrical=Q(2.5e-3, "kg * m^2"),
                    axial_position=Q(50.0, "mm"),
                )
            ],
        )
        m1 = rotor_shaft_mesh(shape_no_disk, lod=MeshLOD.STANDARD)
        m2 = rotor_shaft_mesh(shape_disk, lod=MeshLOD.STANDARD)
        # Radial extent must be larger with the disk.
        r1 = max(m1.bounds[1][0], -m1.bounds[0][0])
        r2 = max(m2.bounds[1][0], -m2.bounds[0][0])
        assert r2 > r1
