"""Curve and surface primitives for impeller / volute mesh generation.

The module is private to :mod:`cascade.geometry`. It collects the B-spline
sampling, blade-camber integration, and lofting helpers so the public
mesh generators read like a recipe.

References:
- Whitfield, A. & Baines, N.C., 1990. *Design of Radial Turbomachines*,
  Longman, §6.5 (blade geometry generation).
- Aungier, R.H., 2000. *Centrifugal Compressors*, ASME Press, §5.3
  (meridional channel B-spline parameterization).
"""

from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np
from scipy.interpolate import splev, splprep


# -----------------------------------------------------------------------------
# B-spline meridional curves (hub + shroud)
# -----------------------------------------------------------------------------


def cubic_bspline_curve(
    control_points: np.ndarray,
    n_samples: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Sample a 2D cubic B-spline through the given control points.

    Args:
        control_points: ``(N, 2)`` array of (z, r) waypoints in meridional plane.
        n_samples: number of sample points returned along the curve.

    Returns:
        Pair ``(z, r)`` of 1D arrays of length ``n_samples``.

    The spline interpolates the first and last control points exactly and
    smooths the interior — exactly the shape needed for a hub/shroud
    meridional curve where the inlet and outlet radii are fixed by the
    velocity-triangle design and the interior bow is a free shape parameter.
    """
    ctrl = np.asarray(control_points, dtype=float)
    if ctrl.shape[1] != 2:
        raise ValueError(
            f"control_points must have shape (N, 2), got {ctrl.shape}",
        )
    if ctrl.shape[0] < 3:
        raise ValueError("need at least 3 control points for a cubic curve")

    # scipy splprep wants axes as separate arrays; degree=min(3, n-1) so the
    # call survives n=3 (degenerates to quadratic) without raising.
    k = min(3, ctrl.shape[0] - 1)
    tck, _u = splprep(
        [ctrl[:, 0], ctrl[:, 1]],
        k=k,
        s=0.0,  # exact interpolation
    )
    u_eval = np.linspace(0.0, 1.0, n_samples)
    z, r = splev(u_eval, tck)
    return np.asarray(z, dtype=float), np.asarray(r, dtype=float)


def default_hub_control_points(
    r_inlet: float,
    r_outlet: float,
    z_axial: float,
    *,
    flow: str = "centrifugal",
) -> np.ndarray:
    """Generate canonical control points for an impeller hub curve.

    The hub is the "inner" meridional boundary. For a centrifugal compressor
    it sweeps from the axial inlet (z=0, r=r_inducer_hub) to the radial
    outlet (z=z_axial, r=r_impeller_outer). The interior bow is a smooth
    S-curve typical of Concepts-NREC / Aungier-style designs.

    For a radial inflow turbine the convention is reversed: flow enters
    radially and exits axially; we generate the same shape with axes
    swapped at the caller.
    """
    if flow == "centrifugal":
        # Concepts-NREC style hub: axial inducer that turns to radial outlet.
        # 5 control points form a smooth knee.
        return np.array(
            [
                [0.0, r_inlet],
                [0.25 * z_axial, r_inlet * 1.05],
                [0.60 * z_axial, 0.35 * (r_inlet + r_outlet)],
                [0.85 * z_axial, 0.85 * r_outlet],
                [z_axial, r_outlet],
            ]
        )
    # radial inflow turbine: mirror direction. Inlet at z=z_axial (radial),
    # outlet at z=0 (axial). Same hub shape, swept the other way.
    return np.array(
        [
            [z_axial, r_inlet],
            [0.75 * z_axial, r_inlet * 0.95],
            [0.40 * z_axial, 0.35 * (r_inlet + r_outlet)],
            [0.15 * z_axial, 0.85 * r_outlet],
            [0.0, r_outlet],
        ]
    )


def default_shroud_control_points(
    r_inlet: float,
    r_outlet: float,
    z_axial: float,
    tip_clearance: float,
    *,
    flow: str = "centrifugal",
) -> np.ndarray:
    """Generate canonical control points for an impeller shroud curve.

    The shroud is offset from the blade tip by ``tip_clearance``. For an
    unshrouded (open) impeller the "shroud" in this mesh generator is the
    virtual casing surface; for a shrouded impeller the curve is the
    actual shroud disc.
    """
    r_in_eff = r_inlet
    r_out_eff = r_outlet - tip_clearance
    if flow == "centrifugal":
        return np.array(
            [
                [0.0, r_in_eff],
                [0.30 * z_axial, r_in_eff * 1.10],
                [0.65 * z_axial, 0.45 * (r_in_eff + r_out_eff)],
                [0.90 * z_axial, 0.92 * r_out_eff],
                [z_axial - tip_clearance, r_out_eff],
            ]
        )
    # radial inflow turbine: mirror.
    return np.array(
        [
            [z_axial - tip_clearance, r_in_eff],
            [0.70 * z_axial, r_in_eff * 0.92],
            [0.35 * z_axial, 0.45 * (r_in_eff + r_out_eff)],
            [0.10 * z_axial, 0.92 * r_out_eff],
            [0.0, r_out_eff],
        ]
    )


# -----------------------------------------------------------------------------
# Blade meanline integration
# -----------------------------------------------------------------------------


def meridional_arc_length(z: np.ndarray, r: np.ndarray) -> np.ndarray:
    """Cumulative meridional arc length along a (z, r) curve."""
    dz = np.diff(z)
    dr = np.diff(r)
    ds = np.hypot(dz, dr)
    s = np.concatenate(([0.0], np.cumsum(ds)))
    return s


def blade_angle_distribution(
    n_stations: int,
    beta_inlet_rad: float,
    beta_outlet_rad: float,
) -> np.ndarray:
    """Smooth blade-angle distribution from inlet to outlet.

    The distribution is a cubic Hermite interpolant: the inlet/outlet
    angles are anchored exactly and the interior curve is a smooth
    transition with zero end-slopes (a "C¹ smooth blade angle ramp" per
    Aungier 2000 §5.3). This is the standard back-swept blade shape.
    """
    t = np.linspace(0.0, 1.0, n_stations)
    # Smooth-step: 3t² - 2t³ (Hermite blending; zero slope at both ends)
    h = 3.0 * t * t - 2.0 * t * t * t
    return beta_inlet_rad + (beta_outlet_rad - beta_inlet_rad) * h


def camber_theta_from_beta(
    s: np.ndarray,
    r: np.ndarray,
    beta_rad: np.ndarray,
) -> np.ndarray:
    """Integrate dθ/dm = tan(β)/r to recover the blade-camber wrap angle.

    Args:
        s: meridional arc length at each station, ``(n,)``.
        r: radius at each station, ``(n,)``.
        beta_rad: blade angle (from axial / meridional) at each station, ``(n,)``.

    Returns:
        Cumulative wrap angle θ(m) starting from 0 at the leading edge.

    The blade-angle convention is "from axial / meridional": when β=0 the
    blade is purely meridional (no wrap), when β=π/2 the blade is purely
    tangential (infinite wrap rate). ``dθ/dm = tan(β)/r`` is the canonical
    radial-machine relation (Whitfield & Baines 1990 eq. 6.15).
    """
    # Guard against r=0 at the centerline.
    r_safe = np.where(r > 1e-9, r, 1e-9)
    integrand = np.tan(beta_rad) / r_safe
    # Trapezoidal integration of θ along arc length s.
    theta = np.zeros_like(s)
    for i in range(1, len(s)):
        ds = s[i] - s[i - 1]
        theta[i] = theta[i - 1] + 0.5 * (integrand[i] + integrand[i - 1]) * ds
    return theta


def blade_thickness_distribution(
    n_stations: int,
    t_max: float,
    *,
    t_le_fraction: float = 0.08,
    t_te_fraction: float = 0.05,
) -> np.ndarray:
    """Bell-curve blade thickness distribution.

    The thickness is small (but nonzero) at the LE and TE — a real blade
    has a finite leading-edge radius and a finite trailing-edge
    thickness for manufacturability — and peaks near the mid-chord.

    Nonzero LE/TE thickness is *mandatory* for a watertight closed-shell
    blade topology: a zero-thickness LE/TE collapses PS and SS onto each
    other and breaks the manifold.

    Args:
        n_stations: number of meridional sample stations.
        t_max: peak thickness [m].
        t_le_fraction: fraction of ``t_max`` at the LE (default 8%).
        t_te_fraction: fraction of ``t_max`` at the TE (default 5%).
    """
    t = np.linspace(0.0, 1.0, n_stations)
    # Bell shape: 4*t*(1-t) peaks at 0.5 with value 1.0. We weight to
    # push the peak forward to ~0.4 for a typical backswept blade.
    bell = 4.0 * (t ** 0.7) * ((1.0 - t) ** 1.0)
    bell = bell / bell.max()
    # Baseline = LE→TE linear ramp so we honor the fraction at both ends.
    base = t_le_fraction + (t_te_fraction - t_le_fraction) * t
    # Scaled bell contributes the remaining thickness above the baseline.
    bell_contribution = (1.0 - max(t_le_fraction, t_te_fraction)) * bell
    return t_max * (base + bell_contribution)


# -----------------------------------------------------------------------------
# 3D blade surface lofting
# -----------------------------------------------------------------------------


def loft_blade_surface(
    z_hub: np.ndarray,
    r_hub: np.ndarray,
    z_shroud: np.ndarray,
    r_shroud: np.ndarray,
    theta_hub: np.ndarray,
    theta_shroud: np.ndarray,
    *,
    n_span: int,
) -> np.ndarray:
    """Loft a single ruled blade surface from hub-to-shroud.

    Linear interpolation across the spanwise direction. Each meridional
    station yields ``n_span`` points along the (hub → shroud) ruled line,
    each at the wrap angle θ(span) linearly interpolated.

    Returns:
        ``(n_meridional, n_span, 3)`` array of (x, y, z) points.
        The 3D Cartesian frame is right-handed with z as the machine axis.
    """
    n_m = len(z_hub)
    if not (len(r_hub) == len(z_shroud) == len(r_shroud) == len(theta_hub)
            == len(theta_shroud) == n_m):
        raise ValueError("inconsistent input lengths in loft_blade_surface")

    pts = np.empty((n_m, n_span, 3), dtype=float)
    span = np.linspace(0.0, 1.0, n_span)
    for i in range(n_m):
        # Ruled-line span interpolation in (z, r, θ).
        z_line = (1.0 - span) * z_hub[i] + span * z_shroud[i]
        r_line = (1.0 - span) * r_hub[i] + span * r_shroud[i]
        th_line = (1.0 - span) * theta_hub[i] + span * theta_shroud[i]
        pts[i, :, 0] = r_line * np.cos(th_line)
        pts[i, :, 1] = r_line * np.sin(th_line)
        pts[i, :, 2] = z_line
    return pts


def triangulate_quad_grid(
    pts: np.ndarray,
    *,
    flip: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """Triangulate a structured (rows × cols × 3) grid of points.

    Returns:
        ``(vertices, faces)`` where ``vertices`` is ``(N, 3)`` and ``faces``
        is ``(M, 3)`` of integer triangle indices.

    Each quad ``(i,j) — (i+1,j) — (i+1,j+1) — (i,j+1)`` is split into two
    triangles with a consistent winding (counter-clockwise when viewed
    from the surface's outward normal).
    """
    rows, cols, _ = pts.shape
    vertices = pts.reshape(-1, 3)
    faces: List[Tuple[int, int, int]] = []
    for i in range(rows - 1):
        for j in range(cols - 1):
            a = i * cols + j
            b = (i + 1) * cols + j
            c = (i + 1) * cols + (j + 1)
            d = i * cols + (j + 1)
            if flip:
                faces.append((a, c, b))
                faces.append((a, d, c))
            else:
                faces.append((a, b, c))
                faces.append((a, c, d))
    return vertices, np.asarray(faces, dtype=np.int64)


# -----------------------------------------------------------------------------
# Surface of revolution (hub disc, back-face, shroud-cup)
# -----------------------------------------------------------------------------


def surface_of_revolution(
    z_curve: np.ndarray,
    r_curve: np.ndarray,
    *,
    n_theta: int,
    theta_start: float = 0.0,
    theta_end: float = 2.0 * math.pi,
) -> Tuple[np.ndarray, np.ndarray]:
    """Sweep a 2D meridional curve about the z-axis to form a 3D surface.

    Returns ``(vertices, faces)``. For a full sweep the start and end
    rings share vertices; we explicitly duplicate them so the resulting
    mesh has matching seam vertices that fuse into a watertight closed
    surface when subsequently merged.
    """
    n_m = len(z_curve)
    theta = np.linspace(theta_start, theta_end, n_theta, endpoint=True)
    pts = np.empty((n_m, n_theta, 3), dtype=float)
    for i in range(n_m):
        pts[i, :, 0] = r_curve[i] * np.cos(theta)
        pts[i, :, 1] = r_curve[i] * np.sin(theta)
        pts[i, :, 2] = z_curve[i]
    return triangulate_quad_grid(pts)


def disc_cap(
    z: float,
    r_inner: float,
    r_outer: float,
    *,
    n_theta: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """A flat annulus (washer) at axial position z. Triangle fan."""
    theta = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=True)
    inner = np.stack(
        [r_inner * np.cos(theta), r_inner * np.sin(theta), np.full_like(theta, z)],
        axis=1,
    )
    outer = np.stack(
        [r_outer * np.cos(theta), r_outer * np.sin(theta), np.full_like(theta, z)],
        axis=1,
    )
    vertices = np.concatenate([inner, outer], axis=0)
    faces: List[Tuple[int, int, int]] = []
    for j in range(n_theta - 1):
        a = j
        b = j + 1
        c = n_theta + j + 1
        d = n_theta + j
        faces.append((a, b, c))
        faces.append((a, c, d))
    return vertices, np.asarray(faces, dtype=np.int64)
