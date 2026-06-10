"""Radial inflow turbine rotor mesh generator.

Topologically identical to the centrifugal impeller (hub + shroud
meridional curves with blades), but with reversed flow direction: the
inlet is radial (at large r, small z) and the outlet is axial (at small
r, large z). The blade-angle convention differs accordingly.

Algorithm mirrors `cascade.geometry.impeller.centrifugal_impeller_mesh`;
see that module for the recipe. The differences here are:
- Hub & shroud control points are mirrored in z.
- The LE blade angle is the radial-inflow `inlet_metal_angle_rad` (often
  zero for a "radial" rotor; nonzero for a backswept rotor).
- The TE angle is the `exducer_angle_rad`.
- The "axial face" of the rotor disc is on the upstream side; the
  "back face" is the exducer side.
"""

from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np
import trimesh

from cascade.geometry._curves import (
    blade_angle_distribution,
    blade_thickness_distribution,
    camber_theta_from_beta,
    cubic_bspline_curve,
    default_hub_control_points,
    default_shroud_control_points,
    disc_cap,
    loft_blade_surface,
    meridional_arc_length,
    surface_of_revolution,
    triangulate_quad_grid,
)
from cascade.geometry.export import apply_titanium_material
from cascade.geometry.impeller import LOD_RESOLUTION
from cascade.meanline.radial_turbine import RadialTurbineGeometry


def _meridional_axial_length(geometry: RadialTurbineGeometry) -> float:
    """Heuristic axial length of the rotor passage.

    For an RIT the standard rule (Whitfield 1990 §6.3) is
    ``L_axial ≈ 0.5 × r_inlet`` — slightly more compact than a CC.
    """
    return 0.5 * geometry.rotor_inlet_radius


def _build_meridional_curves(
    geometry: RadialTurbineGeometry,
    n_meridional: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Sample hub and shroud meridional curves for the RIT.

    Convention: flow enters at z=z_axial (radially) and exits at z=0
    (axially). The curves are parameterised so index 0 is at the inlet
    (rotor LE) and index -1 is at the exducer TE.
    """
    z_axial = _meridional_axial_length(geometry)
    r_inlet = geometry.rotor_inlet_radius
    r_out_hub = geometry.rotor_outlet_radius_hub
    r_out_tip = geometry.rotor_outlet_radius_tip
    tip_clr = geometry.tip_clearance

    # The hub starts at (z_axial, r_inlet) (radial inlet) and ends at
    # (0, r_out_hub). The shroud starts at the same radius r_inlet but
    # axially offset by blade_height_inlet + tip_clearance (at the radial
    # LE the passage height and clearance are both axial), and ends at
    # (0, r_out_tip).
    # We use the centrifugal default-hub helper with flow="radial" which
    # gives the mirror shape.
    hub_ctrl = default_hub_control_points(
        r_inlet=r_inlet,
        r_outlet=r_out_hub,
        z_axial=z_axial,
        flow="radial",
    )
    shroud_ctrl = default_shroud_control_points(
        r_inlet=r_inlet,
        r_outlet=r_out_tip,
        z_axial=z_axial,
        tip_clearance=tip_clr,
        blade_height_radial=geometry.blade_height_inlet,
        flow="radial",
    )
    z_hub, r_hub = cubic_bspline_curve(hub_ctrl, n_meridional)
    z_shroud, r_shroud = cubic_bspline_curve(shroud_ctrl, n_meridional)
    return z_hub, r_hub, z_shroud, r_shroud


def _build_single_blade(
    geometry: RadialTurbineGeometry,
    z_hub: np.ndarray,
    r_hub: np.ndarray,
    z_shroud: np.ndarray,
    r_shroud: np.ndarray,
    n_span: int,
    *,
    theta_offset: float = 0.0,
    fractional_chord_start: float = 0.0,
    fractional_chord_end: float = 1.0,
) -> trimesh.Trimesh:
    """Build a single RIT blade as a closed shell."""
    n_m_full = len(z_hub)
    i0 = int(round(fractional_chord_start * (n_m_full - 1)))
    i1 = int(round(fractional_chord_end * (n_m_full - 1)))
    z_hub_b = z_hub[i0:i1 + 1]
    r_hub_b = r_hub[i0:i1 + 1]
    z_sh_b = z_shroud[i0:i1 + 1]
    r_sh_b = r_shroud[i0:i1 + 1]
    n_m = len(z_hub_b)
    if n_m < 3:
        raise ValueError("blade segment too short — increase LOD or chord range")

    s_hub = meridional_arc_length(z_hub_b, r_hub_b)

    # RIT blade-angle distribution: at the radial inlet the canonical
    # design is zero incidence (β₁_blade = 0 from axial → purely radial
    # blade). At the exducer the angle is the metal exducer angle (e.g.
    # 60° from axial).
    beta_le = geometry.inlet_metal_angle_rad
    beta_te = geometry.exducer_angle_rad
    beta = blade_angle_distribution(n_m, beta_le, beta_te)

    theta_hub_camber = camber_theta_from_beta(s_hub, r_hub_b, beta)
    theta_shroud_camber = theta_hub_camber.copy()

    # 1.5% of rotor inlet radius (typical), floored at the casting minimum
    # (RIT rotors are cast, not milled — see manufacturability.limits).
    from cascade.manufacturability.limits import cast_blade_peak_thickness_m

    t_max_m = cast_blade_peak_thickness_m(geometry.rotor_inlet_radius)
    t_distribution = blade_thickness_distribution(n_m, t_max_m)

    theta_hub_camber = theta_hub_camber + theta_offset
    theta_shroud_camber = theta_shroud_camber + theta_offset

    r_mid = 0.5 * (r_hub_b + r_sh_b)
    dtheta = 0.5 * t_distribution / np.maximum(r_mid, 1e-6)

    theta_ps_hub = theta_hub_camber - dtheta
    theta_ss_hub = theta_hub_camber + dtheta
    theta_ps_sh = theta_shroud_camber - dtheta
    theta_ss_sh = theta_shroud_camber + dtheta

    pts_ps = loft_blade_surface(
        z_hub_b, r_hub_b, z_sh_b, r_sh_b,
        theta_ps_hub, theta_ps_sh,
        n_span=n_span,
    )
    pts_ss = loft_blade_surface(
        z_hub_b, r_hub_b, z_sh_b, r_sh_b,
        theta_ss_hub, theta_ss_sh,
        n_span=n_span,
    )

    v_ps, f_ps = triangulate_quad_grid(pts_ps, flip=True)
    v_ss, f_ss = triangulate_quad_grid(pts_ss, flip=False)

    hub_band_pts = np.stack([pts_ps[:, 0, :], pts_ss[:, 0, :]], axis=1)
    v_hub, f_hub = triangulate_quad_grid(hub_band_pts, flip=False)

    tip_band_pts = np.stack([pts_ps[:, -1, :], pts_ss[:, -1, :]], axis=1)
    v_tip, f_tip = triangulate_quad_grid(tip_band_pts, flip=True)

    le_pts = np.stack([pts_ps[0, :, :], pts_ss[0, :, :]], axis=1)
    v_le, f_le = triangulate_quad_grid(le_pts, flip=False)

    te_pts = np.stack([pts_ps[-1, :, :], pts_ss[-1, :, :]], axis=1)
    v_te, f_te = triangulate_quad_grid(te_pts, flip=True)

    v_list = [v_ps, v_ss, v_hub, v_tip, v_le, v_te]
    f_list = [f_ps, f_ss, f_hub, f_tip, f_le, f_te]
    offsets = np.cumsum([0] + [len(v) for v in v_list[:-1]])
    vertices = np.concatenate(v_list, axis=0)
    faces = np.concatenate(
        [f + o for f, o in zip(f_list, offsets)], axis=0
    )

    blade = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    blade.merge_vertices(merge_norm=True)
    return blade


def _build_hub_solid(
    geometry: RadialTurbineGeometry,
    z_hub: np.ndarray,
    r_hub: np.ndarray,
    n_theta: int,
    *,
    include_back_face: bool,
) -> trimesh.Trimesh:
    """Hub solid of revolution for an RIT.

    Topology mirror of `cascade.geometry.impeller._build_hub_solid`. The
    "back face" of an RIT is the disc behind the radial inlet — at the
    +z side of the rotor in our convention.
    """
    n_m = len(z_hub)
    theta = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=True)
    z_back = float(np.max(z_hub))
    z_min = float(np.min(z_hub))
    r_bore = max(0.3 * geometry.rotor_outlet_radius_hub, 1e-3)

    # Top (flow-path) surface: hub curve revolved.
    top_pts = np.empty((n_m, n_theta, 3), dtype=float)
    for i in range(n_m):
        top_pts[i, :, 0] = r_hub[i] * np.cos(theta)
        top_pts[i, :, 1] = r_hub[i] * np.sin(theta)
        top_pts[i, :, 2] = z_hub[i]
    v_top, f_top = triangulate_quad_grid(top_pts, flip=False)

    parts_v = [v_top]
    parts_f = [f_top]

    # Inner bore wall: from z=z_min to z=z_back at r=r_bore.
    n_bore_axial = 4
    z_bore_axial = np.linspace(z_min, z_back, n_bore_axial)
    bore_pts = np.empty((n_bore_axial, n_theta, 3), dtype=float)
    for i in range(n_bore_axial):
        bore_pts[i, :, 0] = r_bore * np.cos(theta)
        bore_pts[i, :, 1] = r_bore * np.sin(theta)
        bore_pts[i, :, 2] = z_bore_axial[i]
    v_bore, f_bore = triangulate_quad_grid(bore_pts, flip=True)
    parts_v.append(v_bore)
    parts_f.append(f_bore)

    # Exducer face: annular ring at z=z_min from r_bore to r_hub_at_outlet.
    r_outlet_hub = r_hub[-1]
    if r_outlet_hub > r_bore + 1e-9:
        exducer_pts = np.empty((2, n_theta, 3), dtype=float)
        exducer_pts[0, :, 0] = r_bore * np.cos(theta)
        exducer_pts[0, :, 1] = r_bore * np.sin(theta)
        exducer_pts[0, :, 2] = z_min
        exducer_pts[1, :, 0] = r_outlet_hub * np.cos(theta)
        exducer_pts[1, :, 1] = r_outlet_hub * np.sin(theta)
        exducer_pts[1, :, 2] = z_min
        v_ex, f_ex = triangulate_quad_grid(exducer_pts, flip=True)
        parts_v.append(v_ex)
        parts_f.append(f_ex)

    # Outer cylindrical wall at the radial-inlet radius from z_hub_LE
    # to z_back.
    z_hub_le = float(z_hub[0])
    r_inlet = geometry.rotor_inlet_radius
    if z_back - z_hub_le > 1e-9:
        n_wall_ax = 3
        z_wall = np.linspace(z_hub_le, z_back, n_wall_ax)
        wall_pts = np.empty((n_wall_ax, n_theta, 3), dtype=float)
        for i in range(n_wall_ax):
            wall_pts[i, :, 0] = r_inlet * np.cos(theta)
            wall_pts[i, :, 1] = r_inlet * np.sin(theta)
            wall_pts[i, :, 2] = z_wall[i]
        v_wall, f_wall = triangulate_quad_grid(wall_pts, flip=False)
        parts_v.append(v_wall)
        parts_f.append(f_wall)

    # Back face: annular disc at z=z_back from r_bore to r_inlet.
    if include_back_face:
        back_pts = np.empty((2, n_theta, 3), dtype=float)
        back_pts[0, :, 0] = r_bore * np.cos(theta)
        back_pts[0, :, 1] = r_bore * np.sin(theta)
        back_pts[0, :, 2] = z_back
        back_pts[1, :, 0] = r_inlet * np.cos(theta)
        back_pts[1, :, 1] = r_inlet * np.sin(theta)
        back_pts[1, :, 2] = z_back
        v_back, f_back = triangulate_quad_grid(back_pts, flip=False)
        parts_v.append(v_back)
        parts_f.append(f_back)

    offsets = np.cumsum([0] + [len(v) for v in parts_v[:-1]])
    vertices = np.concatenate(parts_v, axis=0)
    faces = np.concatenate(
        [f + o for f, o in zip(parts_f, offsets)], axis=0,
    )
    hub = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    hub.merge_vertices(merge_norm=True)
    return hub


def _build_shroud_cup(
    geometry: RadialTurbineGeometry,
    z_shroud: np.ndarray,
    r_shroud: np.ndarray,
    n_theta: int,
) -> trimesh.Trimesh:
    v, f = surface_of_revolution(z_shroud, r_shroud, n_theta=n_theta)
    return trimesh.Trimesh(vertices=v, faces=f, process=False)


def _build_tip_clearance_overlay(
    geometry: RadialTurbineGeometry,
    z_shroud: np.ndarray,
    r_shroud: np.ndarray,
    n_theta: int,
) -> trimesh.Trimesh:
    tip_clr = geometry.tip_clearance
    r_offset = r_shroud + tip_clr
    v, f = surface_of_revolution(z_shroud, r_offset, n_theta=n_theta)
    return trimesh.Trimesh(vertices=v, faces=f, process=False)


def radial_turbine_mesh(
    geometry: RadialTurbineGeometry,
    lod_key: str,
    *,
    with_splitter: bool,
    with_back_face: bool,
    with_shroud: bool,
    with_tip_clearance_overlay: bool,
) -> trimesh.Trimesh:
    """Build the canonical radial-inflow turbine rotor mesh.

    Returns a single `trimesh.Trimesh` with PBR titanium material.
    Vertex count at STANDARD LOD ≈ 3 k for a typical 14-blade rotor.
    """
    if lod_key not in LOD_RESOLUTION:
        raise ValueError(f"unknown LOD {lod_key!r}")
    n_meridional, n_theta = LOD_RESOLUTION[lod_key]
    n_span = max(6, n_theta // 4)

    z_hub, r_hub, z_shroud, r_shroud = _build_meridional_curves(
        geometry, n_meridional,
    )

    main_blade_template = _build_single_blade(
        geometry, z_hub, r_hub, z_shroud, r_shroud, n_span,
    )
    Z = geometry.blade_count
    blades: List[trimesh.Trimesh] = []
    for k in range(Z):
        T = trimesh.transformations.rotation_matrix(
            angle=2.0 * math.pi * k / Z, direction=[0.0, 0.0, 1.0],
        )
        b = main_blade_template.copy()
        b.apply_transform(T)
        blades.append(b)

    if with_splitter and Z >= 6:
        splitter_template = _build_single_blade(
            geometry, z_hub, r_hub, z_shroud, r_shroud, n_span,
            theta_offset=math.pi / Z,
            fractional_chord_start=0.5,
            fractional_chord_end=1.0,
        )
        for k in range(Z):
            T = trimesh.transformations.rotation_matrix(
                angle=2.0 * math.pi * k / Z, direction=[0.0, 0.0, 1.0],
            )
            b = splitter_template.copy()
            b.apply_transform(T)
            blades.append(b)

    parts: List[trimesh.Trimesh] = list(blades)
    parts.append(_build_hub_solid(
        geometry, z_hub, r_hub, n_theta, include_back_face=with_back_face,
    ))
    if with_shroud:
        parts.append(_build_shroud_cup(geometry, z_shroud, r_shroud, n_theta))
    if with_tip_clearance_overlay:
        parts.append(
            _build_tip_clearance_overlay(geometry, z_shroud, r_shroud, n_theta)
        )

    combined: trimesh.Trimesh = trimesh.util.concatenate(parts)
    if combined.vertices.size == 0:
        raise RuntimeError("radial turbine mesh generation produced empty result")
    combined.merge_vertices(merge_norm=True)
    combined.fix_normals()
    _ = combined.vertex_normals

    apply_titanium_material(combined)
    return combined
