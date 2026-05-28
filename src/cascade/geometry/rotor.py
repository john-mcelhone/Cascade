"""Rotor shaft + lumped disk mesh generator.

A `RotorShape` (per SPEC_SHEET §3.5) is a list of cylindrical
`RotorSection`s plus a list of `LumpedDisk`s. The visual representation
is straightforward: each section is a hollow cylinder, each disk is a
flat thick disc, both about the shared rotation axis (the z-axis in our
canonical frame).

This module is intentionally simple — the rotor is just a stack of
cylinders. The point isn't artistic; it's that the user sees the same
rotor that the rotor-dynamics beam-FEM is solving.
"""

from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np
import trimesh

from cascade.geometry.export import apply_titanium_material
from cascade.geometry.impeller import LOD_RESOLUTION
from cascade.units import LumpedDisk, RotorSection, RotorShape


def _hollow_cylinder(
    z_start: float,
    z_end: float,
    r_outer: float,
    r_inner: float,
    *,
    n_theta: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """A hollow cylinder between z=z_start and z=z_end.

    Returns ``(vertices, faces)``. The mesh comprises:
    - outer wall (cylinder of radius r_outer)
    - inner wall (cylinder of radius r_inner; only if r_inner > 0)
    - two annular end caps at z_start and z_end
    """
    if z_end <= z_start:
        raise ValueError("hollow cylinder requires z_end > z_start")
    theta = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=True)

    # Outer wall ring at start, ring at end.
    outer_start = np.stack(
        [r_outer * np.cos(theta), r_outer * np.sin(theta),
         np.full_like(theta, z_start)], axis=1,
    )
    outer_end = np.stack(
        [r_outer * np.cos(theta), r_outer * np.sin(theta),
         np.full_like(theta, z_end)], axis=1,
    )

    vertices_list: List[np.ndarray] = []
    faces_list: List[np.ndarray] = []
    offset = 0

    # Outer wall (4 vertices per quad, 2 triangles).
    outer_pts = np.stack([outer_start, outer_end], axis=0)  # (2, n_theta, 3)
    rows, cols, _ = outer_pts.shape
    outer_verts = outer_pts.reshape(-1, 3)
    outer_faces: List[Tuple[int, int, int]] = []
    for j in range(cols - 1):
        a = j
        b = cols + j
        c = cols + j + 1
        d = j + 1
        outer_faces.append((a, b, c))
        outer_faces.append((a, c, d))
    vertices_list.append(outer_verts)
    faces_list.append(np.asarray(outer_faces, dtype=np.int64) + offset)
    offset += len(outer_verts)

    if r_inner > 1e-9:
        inner_start = np.stack(
            [r_inner * np.cos(theta), r_inner * np.sin(theta),
             np.full_like(theta, z_start)], axis=1,
        )
        inner_end = np.stack(
            [r_inner * np.cos(theta), r_inner * np.sin(theta),
             np.full_like(theta, z_end)], axis=1,
        )
        inner_pts = np.stack([inner_start, inner_end], axis=0)
        rows, cols, _ = inner_pts.shape
        inner_verts = inner_pts.reshape(-1, 3)
        inner_faces: List[Tuple[int, int, int]] = []
        # Reverse winding so the inner wall normal points inward.
        for j in range(cols - 1):
            a = j
            b = cols + j
            c = cols + j + 1
            d = j + 1
            inner_faces.append((a, c, b))
            inner_faces.append((a, d, c))
        vertices_list.append(inner_verts)
        faces_list.append(np.asarray(inner_faces, dtype=np.int64) + offset)
        offset += len(inner_verts)

        # Annular end cap at z_start: outer ring → inner ring.
        cap_start_outer = outer_start
        cap_start_inner = inner_start
        cap_start_pts = np.concatenate([cap_start_outer, cap_start_inner], axis=0)
        cap_start_faces: List[Tuple[int, int, int]] = []
        for j in range(n_theta - 1):
            a = j  # outer j
            b = j + 1  # outer j+1
            c = n_theta + j + 1  # inner j+1
            d = n_theta + j  # inner j
            # Winding: outward normal = -z at z_start
            cap_start_faces.append((a, d, c))
            cap_start_faces.append((a, c, b))
        vertices_list.append(cap_start_pts)
        faces_list.append(np.asarray(cap_start_faces, dtype=np.int64) + offset)
        offset += len(cap_start_pts)

        # Annular end cap at z_end:
        cap_end_pts = np.concatenate([outer_end, inner_end], axis=0)
        cap_end_faces: List[Tuple[int, int, int]] = []
        for j in range(n_theta - 1):
            a = j
            b = j + 1
            c = n_theta + j + 1
            d = n_theta + j
            cap_end_faces.append((a, b, c))
            cap_end_faces.append((a, c, d))
        vertices_list.append(cap_end_pts)
        faces_list.append(np.asarray(cap_end_faces, dtype=np.int64) + offset)
        offset += len(cap_end_pts)
    else:
        # Solid cylinder: caps are full discs (triangle fan).
        for z_cap, flip in ((z_start, True), (z_end, False)):
            ring = np.stack(
                [r_outer * np.cos(theta), r_outer * np.sin(theta),
                 np.full_like(theta, z_cap)], axis=1,
            )
            center = np.array([[0.0, 0.0, z_cap]])
            cap_verts = np.concatenate([center, ring], axis=0)
            cap_faces: List[Tuple[int, int, int]] = []
            for j in range(n_theta - 1):
                if flip:
                    cap_faces.append((0, 1 + j + 1, 1 + j))
                else:
                    cap_faces.append((0, 1 + j, 1 + j + 1))
            vertices_list.append(cap_verts)
            faces_list.append(np.asarray(cap_faces, dtype=np.int64) + offset)
            offset += len(cap_verts)

    return (
        np.concatenate(vertices_list, axis=0),
        np.concatenate(faces_list, axis=0),
    )


def _section_mesh(section: RotorSection, n_theta: int) -> trimesh.Trimesh:
    z_start = float(section.axial_position.to("m").magnitude)
    z_end = z_start + float(section.length.to("m").magnitude)
    r_outer = 0.5 * float(section.diameter_outer.to("m").magnitude)
    r_inner = 0.5 * float(section.diameter_inner.to("m").magnitude)
    v, f = _hollow_cylinder(z_start, z_end, r_outer, r_inner, n_theta=n_theta)
    return trimesh.Trimesh(vertices=v, faces=f, process=False)


def _disk_mesh(
    disk: LumpedDisk,
    shaft_diameter: float,
    n_theta: int,
) -> trimesh.Trimesh:
    """Render a lumped disk as a thick washer.

    Without a stored "disk geometry" we infer reasonable visuals:
    - The disk radius is computed from the polar inertia: ``I_p = ½ m r²``
      → ``r = sqrt(2 I_p / m)``.
    - The disk thickness is computed from the mass: ``m = ρ π r² t``
      with ρ = 4500 kg/m³ (titanium-ish) and r as above. Floor at 1 mm
      so a tiny disk is still visible.

    The disk is centered at ``axial_position`` and rendered as a hollow
    washer with a small bore (matching the shaft).
    """
    mass = float(disk.mass.to("kg").magnitude)
    Ip = float(disk.inertia_polar.to("kg * m^2").magnitude)
    z_center = float(disk.axial_position.to("m").magnitude)

    if mass > 1e-9 and Ip > 1e-12:
        r_outer = math.sqrt(2.0 * Ip / mass)
    else:
        r_outer = max(0.5 * shaft_diameter * 1.5, 5e-3)
    # Floor radius at 1.5× shaft radius so it's actually visible.
    r_outer = max(r_outer, 0.5 * shaft_diameter * 1.2)

    density = 4500.0  # kg/m³ (titanium-ish)
    thickness = mass / max(density * math.pi * r_outer * r_outer, 1e-9)
    thickness = max(thickness, 1.0e-3)

    z_start = z_center - 0.5 * thickness
    z_end = z_center + 0.5 * thickness
    r_inner = 0.5 * shaft_diameter
    v, f = _hollow_cylinder(z_start, z_end, r_outer, r_inner, n_theta=n_theta)
    return trimesh.Trimesh(vertices=v, faces=f, process=False)


def rotor_shaft_mesh_impl(
    shape: RotorShape,
    lod_key: str,
) -> trimesh.Trimesh:
    """Build the canonical rotor mesh from a `RotorShape`.

    The mesh comprises one hollow cylinder per `RotorSection` and one
    thick washer per `LumpedDisk`. All parts are along the +z axis.
    """
    if lod_key not in LOD_RESOLUTION:
        raise ValueError(f"unknown LOD {lod_key!r}")
    _, n_theta = LOD_RESOLUTION[lod_key]
    n_theta = max(n_theta, 16)

    if not shape.sections and not shape.disks:
        raise ValueError("RotorShape has no sections or disks")

    parts: List[trimesh.Trimesh] = []
    for sec in shape.sections:
        parts.append(_section_mesh(sec, n_theta))

    # For each disk we need a representative shaft diameter (use the
    # nearest section's outer diameter; fall back to a 20 mm bore).
    def _shaft_diameter_at(z: float) -> float:
        if not shape.sections:
            return 0.020
        # Pick the section whose [start, end] interval contains z; else
        # nearest.
        best = shape.sections[0]
        best_d = float("inf")
        for s in shape.sections:
            z0 = float(s.axial_position.to("m").magnitude)
            z1 = z0 + float(s.length.to("m").magnitude)
            if z0 <= z <= z1:
                return float(s.diameter_outer.to("m").magnitude)
            d = min(abs(z - z0), abs(z - z1))
            if d < best_d:
                best_d = d
                best = s
        return float(best.diameter_outer.to("m").magnitude)

    for d in shape.disks:
        shaft_diameter = _shaft_diameter_at(
            float(d.axial_position.to("m").magnitude)
        )
        parts.append(_disk_mesh(d, shaft_diameter, n_theta))

    combined = trimesh.util.concatenate(parts)
    if combined.vertices.size == 0:
        raise RuntimeError("rotor mesh generation produced empty result")
    combined.merge_vertices(merge_norm=True)
    combined.fix_normals()
    _ = combined.vertex_normals

    apply_titanium_material(combined)
    return combined
