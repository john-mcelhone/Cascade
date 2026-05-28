"""Campbell diagram + log-decrement stability assessment.

Per SPEC_SHEET §9.

Campbell diagram: sweep spin speed Omega, eigensolve the QEP at each step,
plot the imaginary part of each complex eigenvalue (the damped natural
frequency) vs Omega. Overlay engine-order lines omega = n * Omega for
n = 1, 2, ... and the blade-pass line omega = N_B * Omega. Intersections
identify the critical-speed crossings.

Stability: At each speed in the sweep we compute the log decrement
delta = -2 pi sigma / |omega_d| for each mode. delta < 0 => the mode is
*unstable*; for API 684 §3 Level I systems delta >= 0.1 is required, and
for Level II (with cross-coupling) delta >= 0.

References:
- API 684 §2.5 (Campbell); §3 (stability).
- Childs 1993 §5.6 (Campbell + stability).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from cascade.rotor.beam_fem import RotorModel
from cascade.rotor.eigenanalysis import EigenResult, run_lateral_analysis


@dataclass
class CampbellResult:
    """Campbell-diagram result.

    Attributes:
        rpm_sweep: array of spin speeds [rpm].
        mode_frequencies_hz: shape (n_rpm, n_modes); damped natural
            frequencies at each speed [Hz].
        mode_whirls: shape (n_rpm, n_modes) of {'forward', 'backward', ...}
        engine_order_lines: dict mapping n -> array of frequencies on the
            EO=n line [Hz].
        critical_intersections: dict mapping engine-order n -> list of
            (rpm, mode_index) tuples where the mode-curve crosses EO=n.
    """

    rpm_sweep: np.ndarray
    mode_frequencies_hz: np.ndarray
    mode_whirls: np.ndarray
    engine_order_lines: dict = field(default_factory=dict)
    critical_intersections: dict = field(default_factory=dict)


@dataclass
class StabilityResult:
    """Per-speed log decrement of each mode.

    Attributes:
        rpm_sweep: array of speeds [rpm].
        log_decrements: shape (n_rpm, n_modes); the API 684 log dec values.
        is_stable: shape (n_rpm, n_modes) of bool (True if delta > 0).
        meets_api684_level_I: shape (n_rpm, n_modes) of bool (delta >= 0.1).
    """

    rpm_sweep: np.ndarray
    log_decrements: np.ndarray
    is_stable: np.ndarray
    meets_api684_level_I: np.ndarray


def run_campbell(
    rotor: RotorModel,
    rpm_sweep: np.ndarray,
    n_modes: int = 6,
    engine_orders: Optional[List[float]] = None,
) -> CampbellResult:
    """Compute the Campbell diagram.

    Parameters
    ----------
    rotor : RotorModel
    rpm_sweep : np.ndarray
        Speeds [rpm] to evaluate.
    n_modes : int
        Number of modes to track.
    engine_orders : list[float] | None
        Engine-order multipliers to overlay (e.g., [1.0, 2.0] for 1x and 2x).
        Defaults to [1.0].
    """
    if engine_orders is None:
        engine_orders = [1.0]
    rpms = np.asarray(rpm_sweep, dtype=float)
    n_rpm = len(rpms)
    mode_freqs_hz = np.full((n_rpm, n_modes), np.nan)
    mode_whirls = np.full((n_rpm, n_modes), "", dtype=object)
    for i, rpm in enumerate(rpms):
        modes = run_lateral_analysis(rotor, rpm=float(rpm), n_modes=n_modes)
        for k, m in enumerate(modes):
            mode_freqs_hz[i, k] = m.freq_hz
            mode_whirls[i, k] = m.whirl

    # Engine-order lines (in Hz; multiplier * rpm / 60)
    eo_lines = {}
    for eo in engine_orders:
        eo_lines[eo] = (eo * rpms / 60.0).astype(float)

    # Critical intersections: where mode_freq_hz crosses the EO line
    intersections = {}
    for eo in engine_orders:
        eo_curve = eo * rpms / 60.0
        crosses = []
        for k in range(n_modes):
            mode_curve = mode_freqs_hz[:, k]
            diff = mode_curve - eo_curve
            for i in range(n_rpm - 1):
                if np.isnan(diff[i]) or np.isnan(diff[i + 1]):
                    continue
                if diff[i] * diff[i + 1] < 0:
                    # Linear interpolate the crossing rpm
                    rpm_c = rpms[i] + (rpms[i + 1] - rpms[i]) * (
                        -diff[i] / (diff[i + 1] - diff[i])
                    )
                    crosses.append((float(rpm_c), k))
        intersections[eo] = crosses

    return CampbellResult(
        rpm_sweep=rpms,
        mode_frequencies_hz=mode_freqs_hz,
        mode_whirls=mode_whirls,
        engine_order_lines=eo_lines,
        critical_intersections=intersections,
    )


def run_stability(
    rotor: RotorModel,
    rpm_sweep: np.ndarray,
    n_modes: int = 6,
) -> StabilityResult:
    """Log-decrement stability across a speed sweep.

    delta = -2 pi sigma / |omega_d| (API 684 §3).
    """
    rpms = np.asarray(rpm_sweep, dtype=float)
    n_rpm = len(rpms)
    log_decs = np.full((n_rpm, n_modes), np.nan)
    is_stable = np.zeros((n_rpm, n_modes), dtype=bool)
    meets_level_I = np.zeros((n_rpm, n_modes), dtype=bool)
    for i, rpm in enumerate(rpms):
        modes = run_lateral_analysis(rotor, rpm=float(rpm), n_modes=n_modes)
        for k, m in enumerate(modes):
            # ADAPT-041 / ADAPT-040: log_decrement may be None when the rotor
            # is undamped or when a spurious near-zero |omega_d| mode would
            # have produced gargantuan numerical noise. Treat None as NaN
            # (unknown) and flag as not-stable / not-meeting-level-I.
            if m.log_decrement is None:
                log_decs[i, k] = float("nan")
                is_stable[i, k] = False
                meets_level_I[i, k] = False
            else:
                log_decs[i, k] = m.log_decrement
                is_stable[i, k] = m.log_decrement > 0
                meets_level_I[i, k] = m.log_decrement >= 0.1
    return StabilityResult(
        rpm_sweep=rpms,
        log_decrements=log_decs,
        is_stable=is_stable,
        meets_api684_level_I=meets_level_I,
    )
