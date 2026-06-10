"""Curve and surface primitives for impeller / volute mesh generation.

The module is private to :mod:`cascade.geometry`. It collects the
meridional-contour sampling, blade-camber integration, and grid helpers
so the public mesh generators read like a recipe.

References:
- Whitfield, A. & Baines, N.C., 1990. *Design of Radial Turbomachines*,
  Longman, §6.5 (blade geometry generation).
- Aungier, R.H., 2000. *Centrifugal Compressors*, ASME Press, §5.3
  (meridional channel parameterization).
"""

from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np


# -----------------------------------------------------------------------------
# Meridional contours (hub + shroud)
# -----------------------------------------------------------------------------


def meridional_contour(
    z_start: float,
    r_start: float,
    z_end: float,
    r_end: float,
    n_samples: int,
    *,
    start_tangent: str,
) -> Tuple[np.ndarray, np.ndarray]:
    """Sample a quarter-ellipse meridional contour with exact end tangency.

    This is the canonical industry shape for a radial-machine flow path
    (Aungier 2000 §5.3): the curve leaves the start point tangent to one
    principal direction and arrives at the end point tangent to the other,
    with monotonic z and r and a single curvature sign — no interpolation
    wiggle, no inflection ripples.

    Args:
        z_start, r_start: contour start point (the blade LE end).
        z_end, r_end: contour end point (the blade TE end).
        n_samples: number of points returned along the curve.
        start_tangent: ``"axial"`` for a centrifugal-compressor channel
            (axial inducer inlet turning to a radial exit) or ``"radial"``
            for a radial-inflow-turbine channel (radial rotor inlet
            turning to an axial exducer).

    Returns:
        Pair ``(z, r)`` of 1D arrays of length ``n_samples`` running from
        the start point to the end point.
    """
    t = np.linspace(0.0, 0.5 * math.pi, n_samples)
    if start_tangent == "axial":
        # dr/dt = 0 at t=0 (axial inlet); dz/dt = 0 at t=pi/2 (radial exit).
        z = z_start + (z_end - z_start) * np.sin(t)
        r = r_start + (r_end - r_start) * (1.0 - np.cos(t))
    elif start_tangent == "radial":
        # dz/dt = 0 at t=0 (radial inlet); dr/dt = 0 at t=pi/2 (axial exit).
        z = z_end + (z_start - z_end) * np.cos(t)
        r = r_start + (r_end - r_start) * np.sin(t)
    else:
        raise ValueError(
            f"start_tangent must be 'axial' or 'radial', got {start_tangent!r}"
        )
    return z, r


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


def passage_camber_grid(
    z_hub: np.ndarray,
    r_hub: np.ndarray,
    z_shroud: np.ndarray,
    r_shroud: np.ndarray,
    *,
    beta_le_hub_rad: float,
    beta_le_shroud_rad: float,
    beta_te_hub_rad: float,
    beta_te_shroud_rad: float,
    n_span: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Blade camber surface from per-streamline wrap integration.

    This is how production blade generators (and validated open tools
    like RadialDesigner) build the camber: every spanwise streamline gets
    its OWN meridional arc length and its OWN blade-angle distribution,
    and the wrap angle is integrated per streamline via
    ``dθ/dm = tan(β)/r``. The result is the physically correct twisted
    inducer — the hub sees a shallow metal angle (low wheel speed), the
    shroud a steep one — instead of one streamline's wrap copied across
    the span (which over-wraps the blade into an un-millable corkscrew).

    Args:
        z_hub, r_hub: hub meridional curve, ``(n_m,)`` each.
        z_shroud, r_shroud: shroud meridional curve, ``(n_m,)`` each.
        beta_le_hub_rad / beta_le_shroud_rad: LE metal angle at hub / shroud
            (from meridional).
        beta_te_hub_rad / beta_te_shroud_rad: TE metal angle at hub / shroud.
            Equal for a centrifugal impeller (β₂ is span-constant across the
            narrow exit); radius-scaled for an RIT exducer.
        n_span: number of spanwise stations (hub → shroud).

    Returns:
        ``(Z, R, theta)`` grids, each ``(n_m, n_span)``. ``theta`` starts
        at 0 on every streamline's LE.
    """
    n_m = len(z_hub)
    if not (len(r_hub) == len(z_shroud) == len(r_shroud) == n_m):
        raise ValueError("inconsistent input lengths in passage_camber_grid")

    span = np.linspace(0.0, 1.0, n_span)
    Z = np.outer(z_hub, 1.0 - span) + np.outer(z_shroud, span)
    R = np.outer(r_hub, 1.0 - span) + np.outer(r_shroud, span)

    beta_le = beta_le_hub_rad + span * (beta_le_shroud_rad - beta_le_hub_rad)
    beta_te = beta_te_hub_rad + span * (beta_te_shroud_rad - beta_te_hub_rad)

    # Per-streamline meridional arc length and normalized chord fraction.
    ds = np.hypot(np.diff(Z, axis=0), np.diff(R, axis=0))  # (n_m-1, n_span)
    s = np.vstack([np.zeros((1, n_span)), np.cumsum(ds, axis=0)])
    m_frac = s / np.maximum(s[-1, :], 1e-30)

    # Smooth-step β blend LE → TE per streamline (same Hermite ramp as
    # blade_angle_distribution, here against true arc fraction).
    blend = 3.0 * m_frac**2 - 2.0 * m_frac**3
    beta = beta_le[None, :] + (beta_te - beta_le)[None, :] * blend
    # Keep tan(β) finite if a caller hands in a near-tangential angle.
    beta = np.clip(beta, -1.48, 1.48)

    integrand = np.tan(beta) / np.maximum(R, 1e-9)
    theta = np.zeros_like(R)
    theta[1:, :] = np.cumsum(
        0.5 * (integrand[1:, :] + integrand[:-1, :]) * ds, axis=0
    )
    return Z, R, theta


def grid_to_cartesian(
    R: np.ndarray,
    theta: np.ndarray,
    Z: np.ndarray,
) -> np.ndarray:
    """Convert cylindrical (R, θ, Z) grids to an ``(..., 3)`` Cartesian array."""
    return np.stack(
        [R * np.cos(theta), R * np.sin(theta), Z], axis=-1
    )


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
# Structured-grid triangulation
# -----------------------------------------------------------------------------


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
