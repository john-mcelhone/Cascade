"""Centrifugal compressor impeller mesh generator.

Produces a watertight `trimesh.Trimesh` from a
`CentrifugalCompressorGeometry`. The algorithm follows this recipe:

1. Sample tangency-correct quarter-ellipse hub and shroud contours in
   the meridional plane (axial at the inducer, radial at the exit).
2. Build the blade camber surface by integrating ``dθ/dm = tan(β)/r``
   per spanwise streamline, with the LE metal angle twisted from hub to
   shroud (``tan β₁ ∝ r``, the velocity-triangle relation).
3. Offset the camber ± a bell-curve thickness to get pressure / suction
   surfaces.
4. Cap leading and trailing edges; cap pressure-to-suction at hub & tip
   bands.
5. Replicate the blade around the axis. ``blade_count`` is the TOTAL
   blade count: ``Z`` full blades, or ``Z/2`` full + ``Z/2`` splitters
   at half pitch when splitters are requested.
6. Generate hub disc surface of revolution + back-face disc + optional
   shroud cup.
7. Concatenate all components; attach PBR material; compute normals.

Photoreal quality at EXPORT LOD is ~30k triangles per impeller — well
within the 60 fps WebGL budget.
"""

from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np
import trimesh

from cascade.geometry._curves import (
    blade_thickness_distribution,
    grid_to_cartesian,
    meridional_contour,
    passage_camber_grid,
    surface_of_revolution,
    triangulate_quad_grid,
)
from cascade.geometry.export import apply_titanium_material
from cascade.meanline.centrifugal_compressor import CentrifugalCompressorGeometry


# Resolution dictionary: (n_meridional, n_blade_to_blade).
# - n_meridional: number of stations along the hub/shroud streamline.
# - n_blade_to_blade: number of circumferential samples per surface of
#   revolution (hub disc, back face, shroud cup).
# Spanwise (blade height direction) is derived as max(6, n_blade_to_blade // 4).
#
# These values are tuned so STANDARD lands in the 1k-10k vertex range and
# HIGH in the 5k-30k range for a canonical 20-blade impeller (per the
# WebGL budget).
LOD_RESOLUTION: dict = {
    "PREVIEW": (12, 16),
    "STANDARD": (20, 28),
    "HIGH": (36, 48),
    "EXPORT": (72, 96),
}


def _meridional_axial_length(geometry: CentrifugalCompressorGeometry) -> float:
    """Heuristic axial length of the impeller passage.

    Aungier 2000 §5.3 + Concepts-NREC house style: ``L_axial ≈ r_outlet ×
    0.6``. This is the canonical default when the meanline solver does
    not supply an axial dimension.
    """
    return 0.6 * geometry.impeller_outlet_radius


# Bore-to-hub proportionality factor. The shaft bore is conventionally
# 30 % of the inducer hub radius (Aungier 2000 §5.3 + Concepts-NREC house
# style). This is *purely proportional*: there is no absolute floor that
# kicks in for sub-millimetre impellers — applying one (the pre-fix
# ``max(0.3 * r_hub, 1e-3)`` form) silently rendered the bore 1000× larger
# than the design value when the user requested a sub-mm impeller. See
# ADAPT-030.
_BORE_TO_HUB_RATIO: float = 0.3


def _bore_radius(geometry: CentrifugalCompressorGeometry) -> float:
    """Compute the shaft-bore radius for an impeller geometry.

    The bore is the inner cylindrical wall of the hub solid; it has to be
    proportional to the hub radius (so that the impeller scales correctly
    across micro-, milli- and metre-scale machines).

    Raises:
        ValueError: if ``inducer_hub_radius`` is not finite and positive.
            (A zero or NaN hub radius collapses the hub solid to a degenerate
             surface and is also rejected by ``CentrifugalCompressorGeometry``
             itself; this is the second line of defence in the mesh
             generator.)
    """
    r_hub = float(geometry.inducer_hub_radius)
    if not math.isfinite(r_hub) or r_hub <= 0.0:
        msg = (
            f"impeller geometry: inducer_hub_radius must be finite and > 0 "
            f"(got {r_hub!r}); cannot derive a shaft bore radius."
        )
        raise ValueError(msg)
    return _BORE_TO_HUB_RATIO * r_hub


def _build_meridional_curves(
    geometry: CentrifugalCompressorGeometry,
    n_meridional: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Sample hub and shroud meridional curves.

    Both contours are quarter-ellipses with exact end tangency: axial at
    the inducer inlet, radial at the impeller exit (Aungier 2000 §5.3 —
    the canonical centrifugal flow-path shape, also the contour family
    validated in RadialDesigner against built hardware).

    At the radial exit the passage height and the tip-clearance offset
    are both *axial*: the shroud ends at full radius ``r_outlet`` with
    its z offset from the hub exit plane by ``blade_height_outlet +
    tip_clearance``. Blades loft all the way to the shroud curve, so no
    discrete tip gap is modeled — see KG-G-05.

    Returns ``(z_hub, r_hub, z_shroud, r_shroud)`` arrays of length
    ``n_meridional``.
    """
    z_axial = _meridional_axial_length(geometry)
    r_in_hub = geometry.inducer_hub_radius
    r_in_tip = geometry.inducer_tip_radius
    r_out = geometry.impeller_outlet_radius

    z_shroud_exit = z_axial - (
        geometry.blade_height_outlet + geometry.tip_clearance
    )
    # 5% floor, not just > 0: a shroud compressed into a sliver of the
    # axial span produces a near-vertical contour with a degenerate
    # passage — fail loudly instead of lofting garbage blades.
    if z_shroud_exit <= 0.05 * z_axial:
        raise ValueError(
            f"blade_height_outlet + tip_clearance "
            f"({geometry.blade_height_outlet + geometry.tip_clearance:.4g}) "
            f"leaves under 5% of the meridional axial length "
            f"({z_axial:.4g}); degenerate shroud curve"
        )

    z_hub, r_hub = meridional_contour(
        0.0, r_in_hub, z_axial, r_out, n_meridional, start_tangent="axial",
    )
    z_shroud, r_shroud = meridional_contour(
        0.0, r_in_tip, z_shroud_exit, r_out, n_meridional,
        start_tangent="axial",
    )
    return z_hub, r_hub, z_shroud, r_shroud


# Default inducer-tip blade metal angle (from axial) when the meanline
# has not supplied one. ~60° at the shroud is the canonical optimum-
# inlet result (minimum relative Mach inducer lands at 55–62°; Whitfield
# & Baines 1990 §6.2, also RadialDesigner's inducer optimiser).
_DEFAULT_INDUCER_TIP_METAL_RAD: float = math.radians(60.0)


def blade_metal_angles(
    geometry: CentrifugalCompressorGeometry,
) -> Tuple[float, float, float]:
    """LE hub / LE shroud / TE blade metal angles (from meridional), radians.

    The LE tip angle comes from the meanline
    (``inducer_tip_blade_metal_rad``) or the canonical 60° default. The
    LE hub angle follows the velocity-triangle relation ``tan β₁ ∝ r``
    (uniform axial inflow, wheel speed ∝ r): the hub sees a much
    shallower metal angle than the shroud. This spanwise twist is what
    keeps the hub camber from over-wrapping into a corkscrew.

    The TE angle is the exit metal angle ``β₂`` (backsweep, measured from
    radial = from meridional at a radial exit), span-constant across the
    narrow exit per standard practice.
    """
    beta_tip = geometry.inducer_tip_blade_metal_rad
    if beta_tip is None:
        beta_tip = _DEFAULT_INDUCER_TIP_METAL_RAD
    radius_ratio = geometry.inducer_hub_radius / max(
        geometry.inducer_tip_radius, 1e-12
    )
    beta_hub = math.atan(radius_ratio * math.tan(beta_tip))
    return beta_hub, float(beta_tip), float(geometry.beta_2_metal_rad)


def _build_single_blade(
    geometry: CentrifugalCompressorGeometry,
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
    """Build a single blade as a closed shell.

    The blade is a thin lofted body bounded by:
    - pressure side (lower θ; offset = -t/2 from camber)
    - suction side (higher θ; offset = +t/2 from camber)
    - hub-band ribbon (connects pressure & suction along the hub edge)
    - tip-band ribbon (connects pressure & suction along the tip edge)
    - leading-edge cap (closes the LE)
    - trailing-edge cap (closes the TE)

    ``fractional_chord_start/end`` allow cutting the blade short, which
    is what we do for splitters. A splitter is the SAME camber surface as
    the main blade cut short at its LE (it occupies mid-passage all along
    its length), so the camber is always built over the full chord and
    sliced afterwards.
    """
    n_m_full = len(z_hub)

    # Camber surface over the FULL chord: per-streamline wrap integration
    # with the LE metal angle twisted hub → shroud (see blade_metal_angles).
    beta_le_hub, beta_le_tip, beta_te = blade_metal_angles(geometry)
    Z_grid, R_grid, theta_grid = passage_camber_grid(
        z_hub, r_hub, z_shroud, r_shroud,
        beta_le_hub_rad=beta_le_hub,
        beta_le_shroud_rad=beta_le_tip,
        beta_te_hub_rad=beta_te,
        beta_te_shroud_rad=beta_te,
        n_span=n_span,
    )

    # Clip the camber grid to [start, end] fractional chord.
    i0 = int(round(fractional_chord_start * (n_m_full - 1)))
    i1 = int(round(fractional_chord_end * (n_m_full - 1)))
    Z_grid = Z_grid[i0:i1 + 1]
    R_grid = R_grid[i0:i1 + 1]
    theta_grid = theta_grid[i0:i1 + 1] + theta_offset
    n_m = i1 - i0 + 1
    if n_m < 3:
        raise ValueError("blade segment too short — increase LOD or chord range")

    # Blade thickness in radians at each meridional station: convert
    # thickness in metres to a Δθ at the local radius.
    # 1.5% of D₂ (typical), floored at the 5-axis milling minimum so small
    # wheels never get blades thinner than a cutter can leave standing.
    # Shared with the manufacturability rules — see manufacturability.limits.
    from cascade.manufacturability.limits import machinable_blade_peak_thickness_m

    t_max_m = machinable_blade_peak_thickness_m(geometry.impeller_outlet_radius)
    t_distribution = blade_thickness_distribution(n_m, t_max_m)

    # Convert metric thickness → angular at the local radius of every
    # grid point (not a single mid-span radius — small radii would
    # otherwise get blades thinner than designed).
    dtheta = 0.5 * t_distribution[:, None] / np.maximum(R_grid, 1e-9)

    # Pressure & suction surfaces: camber ± half thickness.
    pts_ps = grid_to_cartesian(R_grid, theta_grid - dtheta, Z_grid)
    pts_ss = grid_to_cartesian(R_grid, theta_grid + dtheta, Z_grid)

    # Triangulate the two main surfaces. Use opposite winding so outward
    # normals agree on a closed shell (pressure side faces -θ, suction
    # side faces +θ).
    v_ps, f_ps = triangulate_quad_grid(pts_ps, flip=True)
    v_ss, f_ss = triangulate_quad_grid(pts_ss, flip=False)

    # Hub band: at the hub edge (span index 0) connect pressure → suction.
    # This is a thin strip of two triangle rows along m.
    hub_band_pts = np.stack(
        [pts_ps[:, 0, :], pts_ss[:, 0, :]], axis=1
    )  # shape (n_m, 2, 3)
    v_hub, f_hub = triangulate_quad_grid(hub_band_pts, flip=False)

    # Tip band: at span index -1 connect suction → pressure (flip to keep
    # outward normal pointing outward from the closed shell).
    tip_band_pts = np.stack(
        [pts_ps[:, -1, :], pts_ss[:, -1, :]], axis=1
    )
    v_tip, f_tip = triangulate_quad_grid(tip_band_pts, flip=True)

    # LE cap: at i=0 close the ring (pressure → suction across spanwise
    # interior). The cap is span-wise; small fan.
    le_pts = np.stack(
        [pts_ps[0, :, :], pts_ss[0, :, :]], axis=1
    )  # shape (n_span, 2, 3)
    v_le, f_le = triangulate_quad_grid(le_pts, flip=False)

    # TE cap.
    te_pts = np.stack(
        [pts_ps[-1, :, :], pts_ss[-1, :, :]], axis=1
    )
    v_te, f_te = triangulate_quad_grid(te_pts, flip=True)

    # Combine into one mesh.
    v_list = [v_ps, v_ss, v_hub, v_tip, v_le, v_te]
    f_list = [f_ps, f_ss, f_hub, f_tip, f_le, f_te]
    offsets = np.cumsum([0] + [len(v) for v in v_list[:-1]])
    vertices = np.concatenate(v_list, axis=0)
    faces = np.concatenate(
        [f + o for f, o in zip(f_list, offsets)], axis=0
    )

    blade = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    # Merge nearby duplicate vertices so the blade is a single connected
    # piece (the hub-band's verts coincide with the PS/SS edge verts).
    blade.merge_vertices(merge_norm=True)
    return blade


def _build_hub_solid(
    geometry: CentrifugalCompressorGeometry,
    z_hub: np.ndarray,
    r_hub: np.ndarray,
    n_theta: int,
    *,
    include_back_face: bool,
) -> trimesh.Trimesh:
    """Build the hub region as a closed solid of revolution.

    The solid is bounded by:
    - top surface: the hub meridional curve, swept about z (the flow-path
      side)
    - bottom face: a flat annular disc at z=z_back (the rotor back face)
    - inner cylindrical wall: the shaft bore at r=r_bore (axial direction)
    - outer annular wall at the LE: a thin disc from r=r_bore to
      r=r_inducer_hub at z=0 (the upstream face of the hub)
    - outer cylindrical wall: from the hub outlet radius up to the back-face

    When ``include_back_face=False`` the back face is omitted; the mesh is
    no longer watertight but is visually identical from the flow-path
    side (saves triangles in the preview).
    """
    n_m = len(z_hub)
    theta = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=True)
    z_back = float(np.max(z_hub))
    # Proportional bore radius — see _bore_radius() for the rationale.
    # The pre-ADAPT-030 form was ``max(0.3 * r_hub, 1e-3)``, which silently
    # corrupted geometry for sub-mm impellers by flooring the bore at 1 mm.
    r_bore = _bore_radius(geometry)

    # --- Top surface: hub curve revolved (matches z_hub, r_hub) -----
    top_pts = np.empty((n_m, n_theta, 3), dtype=float)
    for i in range(n_m):
        top_pts[i, :, 0] = r_hub[i] * np.cos(theta)
        top_pts[i, :, 1] = r_hub[i] * np.sin(theta)
        top_pts[i, :, 2] = z_hub[i]
    v_top, f_top = triangulate_quad_grid(top_pts, flip=False)

    parts_v = [v_top]
    parts_f = [f_top]

    # --- Inner bore wall: cylinder at r=r_bore from z=0 to z=z_back -----
    n_bore_axial = 4  # short axial — only the bore wall
    z_bore_axial = np.linspace(0.0, z_back, n_bore_axial)
    bore_pts = np.empty((n_bore_axial, n_theta, 3), dtype=float)
    for i in range(n_bore_axial):
        bore_pts[i, :, 0] = r_bore * np.cos(theta)
        bore_pts[i, :, 1] = r_bore * np.sin(theta)
        bore_pts[i, :, 2] = z_bore_axial[i]
    v_bore, f_bore = triangulate_quad_grid(bore_pts, flip=True)  # inward normal
    parts_v.append(v_bore)
    parts_f.append(f_bore)

    # --- Upstream face: annular ring from r_bore to r_hub[0] at z=0 -----
    r_in_le = r_hub[0]
    if r_in_le > r_bore + 1e-9:
        # Need to discretize the ring radially to match top_pts[0] verts.
        # Use a simple two-ring annulus.
        upstream_pts = np.empty((2, n_theta, 3), dtype=float)
        upstream_pts[0, :, 0] = r_bore * np.cos(theta)
        upstream_pts[0, :, 1] = r_bore * np.sin(theta)
        upstream_pts[0, :, 2] = 0.0
        upstream_pts[1, :, 0] = r_in_le * np.cos(theta)
        upstream_pts[1, :, 1] = r_in_le * np.sin(theta)
        upstream_pts[1, :, 2] = 0.0
        # Outward normal points in -z direction (upstream).
        v_up, f_up = triangulate_quad_grid(upstream_pts, flip=True)
        parts_v.append(v_up)
        parts_f.append(f_up)

    # --- Outer cylindrical wall at the outlet radius from hub-exit z to
    #     back-face z. The hub exits at (z_hub[-1], r_hub[-1] = r_outer).
    z_hub_exit = float(z_hub[-1])
    r_outer = geometry.impeller_outlet_radius
    if z_back - z_hub_exit > 1e-9:
        n_wall_ax = 3
        z_wall = np.linspace(z_hub_exit, z_back, n_wall_ax)
        wall_pts = np.empty((n_wall_ax, n_theta, 3), dtype=float)
        for i in range(n_wall_ax):
            wall_pts[i, :, 0] = r_outer * np.cos(theta)
            wall_pts[i, :, 1] = r_outer * np.sin(theta)
            wall_pts[i, :, 2] = z_wall[i]
        v_wall, f_wall = triangulate_quad_grid(wall_pts, flip=False)
        parts_v.append(v_wall)
        parts_f.append(f_wall)

    # --- Back face: annular disc at z=z_back from r_bore to r_outer ----
    if include_back_face:
        back_pts = np.empty((2, n_theta, 3), dtype=float)
        back_pts[0, :, 0] = r_bore * np.cos(theta)
        back_pts[0, :, 1] = r_bore * np.sin(theta)
        back_pts[0, :, 2] = z_back
        back_pts[1, :, 0] = r_outer * np.cos(theta)
        back_pts[1, :, 1] = r_outer * np.sin(theta)
        back_pts[1, :, 2] = z_back
        # Outward normal points +z.
        v_back, f_back = triangulate_quad_grid(back_pts, flip=False)
        parts_v.append(v_back)
        parts_f.append(f_back)

    offsets = np.cumsum([0] + [len(v) for v in parts_v[:-1]])
    vertices = np.concatenate(parts_v, axis=0)
    faces = np.concatenate(
        [f + o for f, o in zip(parts_f, offsets)], axis=0,
    )
    hub = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    # Merge near-duplicate vertices at seams (the top surface and bore meet
    # at r=r_bore, z=0 and z=z_back; the outer wall meets the back face at
    # r=r_outer, z=z_back; etc.).
    hub.merge_vertices(merge_norm=True)
    return hub


def _build_shroud_cup(
    geometry: CentrifugalCompressorGeometry,
    z_shroud: np.ndarray,
    r_shroud: np.ndarray,
    n_theta: int,
) -> trimesh.Trimesh:
    """Outer shroud surface of revolution (cosmetic / casing surface).

    Most impellers in reality have the shroud as a separate part (the
    "scroll cap"); here it's optional and rendered as the bounding
    surface for visualization.
    """
    v, f = surface_of_revolution(
        z_shroud, r_shroud, n_theta=n_theta,
    )
    return trimesh.Trimesh(vertices=v, faces=f, process=False)


def _build_tip_clearance_overlay(
    geometry: CentrifugalCompressorGeometry,
    z_shroud: np.ndarray,
    r_shroud: np.ndarray,
    n_theta: int,
) -> trimesh.Trimesh:
    """A thin red highlight band at the shroud, used to visualize the tip
    clearance in the UI. Returned as a separate mesh so the renderer can
    apply a distinct material if desired (here we just return geometry;
    the front end colors it).
    """
    tip_clr = geometry.tip_clearance
    r_offset = r_shroud + tip_clr
    v, f = surface_of_revolution(z_shroud, r_offset, n_theta=n_theta)
    return trimesh.Trimesh(vertices=v, faces=f, process=False)


def centrifugal_impeller_mesh(
    geometry: CentrifugalCompressorGeometry,
    lod_key: str,
    *,
    with_splitter: bool,
    with_back_face: bool,
    with_shroud: bool,
    with_tip_clearance_overlay: bool,
) -> trimesh.Trimesh:
    """Build the canonical centrifugal-compressor impeller mesh.

    This is the public construction routine called by
    `cascade.geometry.impeller_mesh`. It returns a single concatenated
    `trimesh.Trimesh` with the PBR titanium material attached and
    vertex normals computed.

    Vertex counts at each LOD (canonical 18-blade impeller, no splitters):
    - PREVIEW: ~1.0 k
    - STANDARD: ~3.5 k
    - HIGH: ~12 k
    - EXPORT: ~45 k
    """
    if lod_key not in LOD_RESOLUTION:
        raise ValueError(f"unknown LOD {lod_key!r}; expected one of {list(LOD_RESOLUTION)}")
    n_meridional, n_theta = LOD_RESOLUTION[lod_key]
    # Spanwise resolution: scale with the blade-to-blade resolution but
    # the blade itself is thin — we don't need n_theta points across span.
    n_span = max(6, n_theta // 4)

    z_hub, r_hub, z_shroud, r_shroud = _build_meridional_curves(
        geometry, n_meridional,
    )

    # --- Blade replication ---------------------------------------------
    # ``blade_count`` is the TOTAL blade count (it is what the meanline
    # slip/loading correlations were scored with — "includes splitters in
    # effective count" per the geometry dataclass). With splitters the
    # budget splits into Z/2 full blades + Z/2 splitters at half pitch —
    # the classic turbocharger configuration. Rendering Z full + Z
    # splitters (the pre-fix behaviour) doubled the metal at the exit and
    # left passages a cutter cannot reach.
    Z = geometry.blade_count
    use_splitters = with_splitter and Z >= 8 and Z % 2 == 0
    n_main = Z // 2 if use_splitters else Z

    main_blade_template = _build_single_blade(
        geometry, z_hub, r_hub, z_shroud, r_shroud, n_span,
    )
    blades: List[trimesh.Trimesh] = []
    for k in range(n_main):
        rotation_angle = 2.0 * math.pi * k / n_main
        T = trimesh.transformations.rotation_matrix(
            angle=rotation_angle, direction=[0.0, 0.0, 1.0],
        )
        b = main_blade_template.copy()
        b.apply_transform(T)
        blades.append(b)

    # --- Splitter blades (optional) ----------------------------------------
    if use_splitters:
        # Splitter LE at ~35% meridional chord (typical turbocharger
        # practice: 30–40%), running to the TE at half pitch.
        splitter_template = _build_single_blade(
            geometry, z_hub, r_hub, z_shroud, r_shroud, n_span,
            theta_offset=math.pi / n_main,  # half pitch
            fractional_chord_start=0.35,
            fractional_chord_end=1.0,
        )
        for k in range(n_main):
            rotation_angle = 2.0 * math.pi * k / n_main
            T = trimesh.transformations.rotation_matrix(
                angle=rotation_angle, direction=[0.0, 0.0, 1.0],
            )
            b = splitter_template.copy()
            b.apply_transform(T)
            blades.append(b)

    # --- Hub region as a closed solid of revolution ------------------------
    parts: List[trimesh.Trimesh] = list(blades)
    hub_solid = _build_hub_solid(
        geometry, z_hub, r_hub, n_theta, include_back_face=with_back_face,
    )
    parts.append(hub_solid)

    # --- Shroud cup --------------------------------------------------------
    if with_shroud:
        parts.append(_build_shroud_cup(geometry, z_shroud, r_shroud, n_theta))

    # --- Tip-clearance overlay --------------------------------------------
    if with_tip_clearance_overlay:
        parts.append(
            _build_tip_clearance_overlay(geometry, z_shroud, r_shroud, n_theta)
        )

    # Concatenate.
    combined: trimesh.Trimesh = trimesh.util.concatenate(parts)
    if combined.vertices.size == 0:
        raise RuntimeError("impeller mesh generation produced an empty result")

    # Merge near-duplicate vertices across blade copies and surfaces so the
    # mesh is one piece (helps with watertight + lighting continuity).
    combined.merge_vertices(merge_norm=True)
    # Ensure outward-consistent face winding.
    combined.fix_normals()
    # Pre-cache vertex normals.
    _ = combined.vertex_normals

    apply_titanium_material(combined)
    return combined
