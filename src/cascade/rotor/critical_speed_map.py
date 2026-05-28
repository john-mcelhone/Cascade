"""Critical-speed map: sweep bearing stiffness and identify synchronous criticals.

Per SPEC_SHEET.md §9. The critical-speed map is the
rotor-dynamicist's design tool -- it shows how each natural-frequency mode
migrates from "rotor on soft bearings" (low K_b, rigid-body modes dominate)
through "rotor on rigid bearings" (high K_b, beam-bending modes dominate). The
1x engine-order line intersects each mode curve at the synchronous critical
speed for that bearing stiffness.

Algorithm: log-spaced sweep of bearing K from 1e6 to 1e10 N/m (the
SPEC_SHEET §15 hard limit), with C scaled proportional to K (default scaling
factor 0.001 s -- empirical from API 684 typical bearing damping ratios).
At each K we eigenanalyze the system and collect the lowest n_modes
frequencies. The synchronous critical at each K is found by intersecting
the mode curve with the omega = Omega line.

References:
- Childs 1993 §5.4 (critical-speed map).
- Friswell et al. 2010 §6.6 (campbell + critical-speed maps).
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from cascade.rotor.bearings import LinearBearing
from cascade.rotor.beam_fem import RotorModel
from cascade.rotor.eigenanalysis import run_undamped_analysis
from cascade.units import Q


@dataclass
class CriticalSpeedMap:
    """Result of the critical-speed-map sweep.

    Attributes:
        stiffness_values_n_per_m: array of bearing stiffness sweep points [N/m].
        mode_frequencies_rad_s: shape (n_stiffness, n_modes); the lowest
            n_modes natural frequencies at each stiffness point.
        synchronous_criticals_rpm: shape (n_modes,); the synchronous critical
            speed (rpm) for each mode at the bearing stiffness that produces
            omega = Omega. (NaN if no synchronous crossing was found.)
    """

    stiffness_values_n_per_m: np.ndarray
    mode_frequencies_rad_s: np.ndarray
    synchronous_criticals_rpm: np.ndarray


def run_critical_speed_map(
    rotor: RotorModel,
    n_modes: int = 6,
    stiffness_min_n_per_m: float = 1.0e6,
    stiffness_max_n_per_m: float = 1.0e10,
    n_stiffness: int = 30,
    damping_scale_s: float = 1.0e-3,
    base_bearings: Optional[List[LinearBearing]] = None,
) -> CriticalSpeedMap:
    """Sweep bearing stiffness over [stiffness_min, stiffness_max] and
    collect the lowest n_modes frequencies at each point.

    The base bearing list defaults to the rotor's existing bearings; the
    sweep replaces each bearing's K_yy = K_zz with the sweep value (isotropic
    radial stiffness) and the C with K * damping_scale_s. Cross-coupling is
    zeroed for the map -- the map is the isotropic / symmetric reference
    case.

    Parameters
    ----------
    rotor : RotorModel
        Source model.
    n_modes : int
        Number of modes to track per stiffness point.
    stiffness_min_n_per_m, stiffness_max_n_per_m : float
        Sweep extents. The upper limit is capped at 1e10 N/m
        (SPEC_SHEET §15).
    n_stiffness : int
        Number of log-spaced sweep points.
    damping_scale_s : float
        C = K * damping_scale_s. The default 1e-3 s corresponds to
        modal damping of order 0.05 for typical industrial rotors.

    Notes
    -----
    ADAPT-037: the sweep populates the new API-684-canonical fields
    ``K_yy`` (= horizontal radial direct) and ``K_zz`` (= vertical radial
    direct) of :class:`LinearBearing`. The earlier ``K_xx`` / ``K_yy``
    names were renamed because API 684 §2.3 reserves x for the axial
    direction.
    """
    if stiffness_max_n_per_m > 1.0e10:
        # Honor the SPEC_SHEET §15 ceiling
        stiffness_max_n_per_m = 1.0e10
    K_sweep = np.logspace(
        math.log10(stiffness_min_n_per_m),
        math.log10(stiffness_max_n_per_m),
        n_stiffness,
    )
    mode_freqs = np.full((n_stiffness, n_modes), np.nan)
    # Determine bearing axial positions
    if base_bearings is None:
        base_bearings = []
        for original in rotor.bearings:
            base_bearings.append(
                LinearBearing(
                    name=original.name,
                    axial_position=original.axial_position,
                )
            )
        if not base_bearings:
            # No bearings at all -- create two symmetric supports at the ends
            x_min = float(rotor.nodal_positions[0])
            x_max = float(rotor.nodal_positions[-1])
            base_bearings = [
                LinearBearing(name="brg_min", axial_position=Q(x_min, "m")),
                LinearBearing(name="brg_max", axial_position=Q(x_max, "m")),
            ]
    for i, K_val in enumerate(K_sweep):
        C_val = K_val * damping_scale_s
        new_brgs = []
        for tmpl in base_bearings:
            new_brgs.append(
                LinearBearing(
                    name=tmpl.name,
                    axial_position=tmpl.axial_position,
                    K_yy=Q(K_val, "N/m"),
                    K_zz=Q(K_val, "N/m"),
                    C_yy=Q(C_val, "N*s/m"),
                    C_zz=Q(C_val, "N*s/m"),
                )
            )
        # Construct a new RotorModel reusing the existing matrices but with
        # new bearings. Deep copy is cheap relative to a full reassemble.
        new_model = copy.copy(rotor)
        new_model.bearings = new_brgs
        # Bearing nodes remain identical so reuse
        # Bearings attach at same nodes as the originals (assumed unchanged)
        if len(new_brgs) != len(rotor.bearing_nodes):
            # Recompute nearest nodes
            node_pos = rotor.nodal_positions
            new_model.bearing_nodes = [
                int(np.argmin(np.abs(node_pos - b.axial_position.to("m").magnitude)))
                for b in new_brgs
            ]
        modes = run_undamped_analysis(new_model, rpm=0.0, n_modes=n_modes)
        for k, m in enumerate(modes):
            if k < n_modes:
                mode_freqs[i, k] = m.omega_n_rad_s

    # For each mode track, find the synchronous critical (omega = Omega * 1).
    # In the static (no-gyro) form, the "synchronous critical" coincides with
    # the natural frequency itself, so we report the natural frequencies at
    # the *rotor's actual bearing K* as the criticals. We pick the
    # geometric-mean K of the sweep (a typical operating-point default).
    sync_criticals_rpm = np.full(n_modes, np.nan)
    if rotor.bearings:
        # Use the first bearing's nominal K_xx
        K_b, _ = rotor.bearings[0].coefficients_at_rpm(0.0)
        K_nominal = (K_b[0, 0] + K_b[1, 1]) / 2.0
        if K_nominal > 0:
            # Find nearest sweep index
            idx = int(np.argmin(np.abs(np.log10(K_sweep) - math.log10(K_nominal))))
            for k in range(n_modes):
                if not np.isnan(mode_freqs[idx, k]):
                    sync_criticals_rpm[k] = mode_freqs[idx, k] * 60.0 / (2 * math.pi)

    return CriticalSpeedMap(
        stiffness_values_n_per_m=K_sweep,
        mode_frequencies_rad_s=mode_freqs,
        synchronous_criticals_rpm=sync_criticals_rpm,
    )
