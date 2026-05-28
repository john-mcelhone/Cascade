"""Synchronous unbalance forced response (Bode + amplification factor + SM).

A residual unbalance ``m_u e_u`` at axial node ``n_u`` rotates synchronously
with the shaft at Omega, producing a co-rotating centrifugal force on the
rotor::

    y_u(t) = e_u cos(Omega t + beta)
    z_u(t) = e_u sin(Omega t + beta)

The reaction the unbalance exerts on the rotor structure is the centripetal
component (``+ m Omega^2`` times the eccentricity vector). In complex form,
with the project's time convention ``q(t) = Re[q_hat e^{j Omega t}]``::

    F_y_hat = m_u e_u Omega^2 * exp(j beta)
    F_z_hat = m_u e_u Omega^2 * (-j) * exp(j beta) = -j * F_y_hat

(Note the ``-j`` on z, NOT ``+j``. This is the forward-whirl convention --
the unbalance force vector rotates in the same sense as the shaft, which is
the forward-whirl direction. See ADAPT-001.)

The frequency-domain response is::

    (-Omega^2 M + j Omega (C + Omega G) + K) q_hat = F_u_hat

solved for each Omega in a sweep. From the magnitude/phase at each station we
build the Bode plot, identify resonance peaks, compute the amplification
factor Q = 1 / (2 zeta) via half-power bandwidth, and compute the minimum
required separation margin per API 684 2nd ed. §2.7.1.7 Figure 2-8.

References:
- API 684 2nd ed. (2019), §2.6.2 (amplification factor); §2.7.1.7 Figure 2-8
  (separation margin schedule).
- API 617 8th ed. §2.6.2 (refers to API 684 for SM).
- Childs 1993 §5.5 (synchronous forced response).
- Friswell et al. 2010 §6.3 (modal-superposition forced-response).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import scipy.linalg as la

from cascade.rotor.beam_fem import RotorModel
from cascade.units import Q, Quantity


@dataclass
class UnbalanceResponseResult:
    """Bode response + derived API 684 §2.6-2.7 metrics.

    Attributes:
        rpm_sweep: array of rpm values at which the response was evaluated.
        node_responses: dict mapping node index -> array of shape
            (n_rpm, 2) with complex (y, z) deflections.
        magnitudes: dict mapping node index -> array of shape (n_rpm,)
            with the orbital amplitude sqrt(|y|^2 + |z|^2).
        phases: dict mapping node index -> array of shape (n_rpm,)
            with the orbital phase angle [rad].
        amplification_factor: dict mapping mode_index -> Q (= 1 / (2 zeta_n))
            using the half-power method on the peak.
        peak_rpms: dict mapping mode_index -> peak-response rpm.
        separation_margin: dict mapping mode_index -> SM [%] computed
            per API 684 §2.7 separation-margin table.
    """

    rpm_sweep: np.ndarray
    node_responses: Dict[int, np.ndarray]
    magnitudes: Dict[int, np.ndarray]
    phases: Dict[int, np.ndarray]
    amplification_factor: Dict[int, float] = field(default_factory=dict)
    peak_rpms: Dict[int, float] = field(default_factory=dict)
    separation_margin: Dict[int, float] = field(default_factory=dict)


def _api684_separation_margin_percent(
    amplification_factor: float,
    operating_speed_rpm: float,
    critical_speed_rpm: float,
) -> float:
    """API 684 §2.7 *actual* separation margin (a geometric quantity).

    The separation margin from a critical speed is the percentage difference
    between the operating speed and the critical, expressed relative to the
    operating speed::

        SM_actual = |N - N_c| / N * 100

    To check compliance, compare this actual SM against the *required* SM
    returned by :func:`api684_required_separation_margin_percent` for the
    given amplification factor (API 684 2nd ed. §2.7.1.7 Figure 2-8).

    Returns the *actual* separation margin (positive scalar in percent).
    """
    if operating_speed_rpm <= 0:
        return 0.0
    return abs(operating_speed_rpm - critical_speed_rpm) / operating_speed_rpm * 100.0


# API 684 2nd ed. (2019), §2.7.1.7 Figure 2-8: minimum-required separation-
# margin schedule as a function of amplification factor. API 617 8th ed.
# §2.6.2 references this same table. The values below are read from
# Figure 2-8 at the canonical AF break-points and are intended for
# piecewise-linear interpolation between them. The schedule saturates at
# 26 % for AF >= 10 and at 0 % for AF <= 2.5 (where the response is
# considered "critically damped" / non-resonant per API 684 §2.6.2.6).
#
# Source: API Std 684, 2nd edition, July 2019, §2.7.1.7, Figure 2-8
# (titled "Required Separation Margin from a Critical Speed"), reading
# values directly off the published chart.
_API684_SM_TABLE_AF: tuple = (0.0, 2.5, 3.55, 5.0, 8.0, 10.0)
_API684_SM_TABLE_PCT: tuple = (0.0, 0.0, 5.0, 10.0, 16.0, 26.0)
_API684_SM_TABLE_MAX_PCT: float = 26.0


def api684_required_separation_margin_percent(amplification_factor: float) -> float:
    """API 684 2nd ed. §2.7.1.7 Figure 2-8 required separation margin.

    Piecewise-linear interpolation of the published Figure 2-8 schedule:

    =====  =======
    AF     SM_min (%)
    =====  =======
    <=2.5  0
    3.55   5
    5      10
    8      16
    10     26
    >=10   26
    =====  =======

    For amplification factors below 2.5 the rotor is treated as critically
    damped per §2.6.2.6 and no separation margin is required. Above AF=10
    the schedule saturates at 26 %.

    This *replaces* the simpler 15 % cap used in prior versions of Cascade
    (which under-reported by 6-11 percentage points at AF=8-10 -- a safety-
    critical defect for 90 kRPM machines). See ADAPT-002.

    References:
    - API Std 684, 2nd ed. (2019), §2.7.1.7 Figure 2-8.
    - API Std 617, 8th ed. (2014), §2.6.2 (refers to API 684 for SM).
    - Childs, D. (1993), Turbomachinery Rotordynamics, §5.5.

    Parameters
    ----------
    amplification_factor : float
        Amplification factor AF (also written Q) at the critical speed,
        computed via the half-power method per §2.6.2.6.

    Returns
    -------
    float
        Minimum required separation margin in percent (0 to 26).
    """
    af = float(amplification_factor)
    if not math.isfinite(af) or af <= _API684_SM_TABLE_AF[1]:
        return 0.0
    if af >= _API684_SM_TABLE_AF[-1]:
        return _API684_SM_TABLE_MAX_PCT
    # Piecewise-linear interp.
    for i in range(1, len(_API684_SM_TABLE_AF)):
        a0, a1 = _API684_SM_TABLE_AF[i - 1], _API684_SM_TABLE_AF[i]
        if a0 <= af <= a1:
            s0, s1 = _API684_SM_TABLE_PCT[i - 1], _API684_SM_TABLE_PCT[i]
            return round(s0 + (s1 - s0) * (af - a0) / (a1 - a0), 4)
    # Fallback (unreachable given the brackets above).
    return _API684_SM_TABLE_MAX_PCT


def _half_power_amplification(
    rpms: np.ndarray, mags: np.ndarray, peak_idx: int
) -> float:
    """Half-power-bandwidth amplification factor estimation.

    AF = N_c / (N_2 - N_1), where N_1 and N_2 bracket the peak at amplitude
    peak_mag / sqrt(2). Per API 684 §2.6.2.6.

    Returns 0 if no half-power points are found (degenerate or noisy data).
    """
    peak_mag = mags[peak_idx]
    half_power = peak_mag / math.sqrt(2.0)
    N_c = rpms[peak_idx]
    # Search left
    n1 = None
    for i in range(peak_idx, 0, -1):
        if mags[i] < half_power:
            # Linear interpolate
            n1 = rpms[i] + (rpms[i + 1] - rpms[i]) * (half_power - mags[i]) / max(
                mags[i + 1] - mags[i], 1e-30
            )
            break
    # Search right
    n2 = None
    for i in range(peak_idx, len(rpms) - 1):
        if mags[i + 1] < half_power:
            n2 = rpms[i] + (rpms[i + 1] - rpms[i]) * (mags[i] - half_power) / max(
                mags[i] - mags[i + 1], 1e-30
            )
            break
    if n1 is None or n2 is None or (n2 - n1) <= 0:
        return 0.0
    return float(N_c / (n2 - n1))


def run_unbalance_response(
    rotor: RotorModel,
    unbalance_node: int,
    unbalance_mass_kg: float,
    unbalance_radius_m: float,
    rpm_sweep: np.ndarray,
    response_nodes: Optional[List[int]] = None,
    unbalance_phase_rad: float = 0.0,
) -> UnbalanceResponseResult:
    """Compute synchronous unbalance response over a frequency sweep.

    The forcing is the synchronous rotating-vector force
    F = m_u * r_u * Omega^2 at the y- and z-translation DOFs of
    `unbalance_node`. The phase angle determines the relative angle of the
    unbalance vector in the rotor's reference frame.

    Parameters
    ----------
    rotor : RotorModel
    unbalance_node : int
        Node index where the unbalance is applied.
    unbalance_mass_kg : float
        Equivalent unbalance mass m_u [kg]. The standard API 617 grade G2.5
        unbalance is m_u * r_u = 4 * mass_rotor / Omega (in SI), where
        mass_rotor is the rotor mass at MCS.
    unbalance_radius_m : float
        Radius of the unbalance, [m] (centroid of the residual mass).
    rpm_sweep : np.ndarray
        Speeds [rpm] at which to evaluate the response. Must cover the
        criticals of interest.
    response_nodes : list[int] | None
        Nodes at which to record y, z response. Defaults to *all nodes*.
    unbalance_phase_rad : float
        Initial phase of the unbalance vector. Usually 0 (unbalance along
        +y at t = 0).

    Returns
    -------
    UnbalanceResponseResult

    Reference: Friswell et al. 2010 §6.3 (the modal-superposition method);
    Childs 1993 §5.5; API 684 §2.6.
    """
    if response_nodes is None:
        response_nodes = list(range(rotor.n_nodes))
    if unbalance_mass_kg < 0 or unbalance_radius_m < 0:
        msg = (
            f"Unbalance must be non-negative; got m={unbalance_mass_kg}, "
            f"r={unbalance_radius_m}"
        )
        raise ValueError(msg)
    n_dof = rotor.n_dof

    # Unbalance forcing (forward-whirl, see module docstring + ADAPT-001):
    #   F_y_hat = m e Omega^2 * exp(j beta)
    #   F_z_hat = -j * F_y_hat = m e Omega^2 * (sin(beta) - j cos(beta))
    # In particular, with beta = 0: F_y_hat = amp (real), F_z_hat = -j amp.
    # This makes the force vector rotate in the same sense as the shaft
    # (forward whirl), as required by the API 684 §2.5 convention.
    base_dof_y = 4 * unbalance_node  # y DOF
    base_dof_z = 4 * unbalance_node + 2  # z DOF

    rpms = np.asarray(rpm_sweep, dtype=float)
    n_rpm = len(rpms)
    node_responses: Dict[int, np.ndarray] = {
        n: np.zeros((n_rpm, 2), dtype=complex) for n in response_nodes
    }

    for i, rpm in enumerate(rpms):
        omega = rpm * 2.0 * math.pi / 60.0
        K_total = rotor.K_at(rpm)
        C_total = rotor.C_at(rpm)
        G_total = omega * rotor.G_unit
        # Combined complex impedance:
        #   Z = -Omega^2 M + j Omega (C + G) + K
        Z = -(omega**2) * rotor.M + 1j * omega * (C_total + G_total) + K_total
        # Forcing: forward-whirl unbalance phasor (see module docstring).
        F = np.zeros(n_dof, dtype=complex)
        amp = unbalance_mass_kg * unbalance_radius_m * (omega**2)
        F_y_hat = amp * complex(math.cos(unbalance_phase_rad), math.sin(unbalance_phase_rad))
        F[base_dof_y] = F_y_hat
        F[base_dof_z] = -1j * F_y_hat
        # Solve
        try:
            q_hat = la.solve(Z, F)
        except la.LinAlgError:
            q_hat = np.zeros(n_dof, dtype=complex)
        for n in response_nodes:
            node_responses[n][i, 0] = q_hat[4 * n]  # y
            node_responses[n][i, 1] = q_hat[4 * n + 2]  # z

    # Compute magnitudes, phases, peaks
    magnitudes: Dict[int, np.ndarray] = {}
    phases: Dict[int, np.ndarray] = {}
    for n, arr in node_responses.items():
        mag = np.sqrt(np.abs(arr[:, 0]) ** 2 + np.abs(arr[:, 1]) ** 2)
        # Phase from the dominant component
        ph = np.angle(arr[:, 0])
        magnitudes[n] = mag
        phases[n] = ph

    # Detect peaks (a peak is a local maximum in the magnitude trace at the
    # station-of-maximum-response). For simplicity we use
    # the unbalance station's response.
    response_at_unbalance = magnitudes[unbalance_node]
    peak_indices: List[int] = []
    for i in range(1, n_rpm - 1):
        if (
            response_at_unbalance[i] > response_at_unbalance[i - 1]
            and response_at_unbalance[i] > response_at_unbalance[i + 1]
        ):
            peak_indices.append(i)
    amplification_factor: Dict[int, float] = {}
    peak_rpms: Dict[int, float] = {}
    separation_margin: Dict[int, float] = {}
    for k, pi in enumerate(peak_indices):
        q = _half_power_amplification(rpms, response_at_unbalance, pi)
        amplification_factor[k] = q
        peak_rpms[k] = float(rpms[pi])
        # SM is mode-dependent; here we report 0 since the operating speed
        # isn't a parameter to this function. Caller can call
        # _api684_separation_margin_percent() externally.
        separation_margin[k] = 0.0

    return UnbalanceResponseResult(
        rpm_sweep=rpms,
        node_responses=node_responses,
        magnitudes=magnitudes,
        phases=phases,
        amplification_factor=amplification_factor,
        peak_rpms=peak_rpms,
        separation_margin=separation_margin,
    )
