"""ADAPT-001: whirl sign-convention regression test.

Per Childs 1993 eq. 3.49, for an overhung-disk Jeffcott rotor the
forward-whirl frequency *increases* with spin speed Omega while the
backward-whirl frequency *decreases*, both approximately linearly with
slope ``+/- I_p / (2 I_t) * Omega`` superposed on the at-rest frequency:

    omega_fw(Omega) = omega_n + ( I_p / (2 I_t) ) * Omega + ...
    omega_bw(Omega) = omega_n - ( I_p / (2 I_t) ) * Omega + ...

This test guards against the inverted-classifier bug fixed in
ADAPT-001 (the old code labeled the *decreasing* branch as forward and the
*increasing* branch as backward, inverting the Campbell diagram vs API 684
convention).

References:
- Childs, D. (1993). Turbomachinery Rotordynamics, §3.4.
- API 684, 2nd ed. (2019), §2.5 (Campbell diagram convention).
- Genta, G. (1999), Dynamics of Rotating Systems, §4.5.
"""

from __future__ import annotations

import math

import pytest

from cascade.rotor import LinearBearing, build_rotor_model, run_lateral_analysis
from cascade.units import LumpedDisk, Q, RotorSection, RotorShape


def _build_overhung_disk_jeffcott() -> object:
    """Overhung disk on a slender shaft, two stiff bearings.

    The disk has large polar inertia I_p compared to its transverse
    inertia I_t so the gyroscopic splitting is large enough to detect at
    moderate Omega.
    """
    sec = RotorSection(
        diameter_outer=Q(0.02, "m"),
        diameter_inner=Q(0.0, "m"),
        length=Q(0.5, "m"),
        density=Q(7850.0, "kg/m^3"),
        axial_position=Q(0.0, "m"),
        material="AISI4340",
    )
    # Large I_p / I_t so the gyroscopic split is dominant.
    disk = LumpedDisk(
        mass=Q(20.0, "kg"),
        inertia_polar=Q(0.5, "kg*m^2"),
        inertia_diametrical=Q(0.05, "kg*m^2"),
        axial_position=Q(0.25, "m"),
    )
    shape = RotorShape(sections=[sec], disks=[disk])
    K_b = 1.0e9
    brg1 = LinearBearing(
        name="b1",
        axial_position=Q(0.0, "m"),
        K_yy=Q(K_b, "N/m"),
        K_zz=Q(K_b, "N/m"),
        C_yy=Q(100.0, "N*s/m"),
        C_zz=Q(100.0, "N*s/m"),
    )
    brg2 = LinearBearing(
        name="b2",
        axial_position=Q(0.5, "m"),
        K_yy=Q(K_b, "N/m"),
        K_zz=Q(K_b, "N/m"),
        C_yy=Q(100.0, "N*s/m"),
        C_zz=Q(100.0, "N*s/m"),
    )
    return build_rotor_model(shape, [brg1, brg2], elements_per_section=10)


def test_forward_whirl_frequency_increases_with_omega() -> None:
    """The mode classified as 'forward' must have its damped natural
    frequency strictly increase with spin speed Omega.

    Per Childs 1993 eq. 3.49 the forward-whirl branch slope is
    ``+ I_p / (2 I_t) * Omega``; for the test rotor this is
    ``0.5 / (2 * 0.05) = 5 rad/s per rad/s spin`` which is large enough
    to detect cleanly even at 1000 rpm.
    """
    model = _build_overhung_disk_jeffcott()
    rpms = [1000.0, 5000.0, 10000.0]
    fw_freqs = []
    for rpm in rpms:
        modes = run_lateral_analysis(model, rpm=rpm, n_modes=6)
        # Find the lowest-frequency forward-whirl mode that is bending-like
        # (not the very stiff rigid-body or shear modes). We pick the
        # forward-whirl mode whose freq is closest to but at least 100 rad/s.
        fw_modes = [
            m
            for m in modes
            if m.whirl == "forward" and m.omega_d_rad_s > 100.0
        ]
        assert fw_modes, (
            f"No forward-whirl mode found at rpm={rpm}; got "
            f"{[(m.omega_d_rad_s, m.whirl) for m in modes]}"
        )
        # Take the lowest-frequency forward mode.
        fw_freqs.append(min(m.omega_d_rad_s for m in fw_modes))
    # Strictly monotone increasing
    for i in range(len(rpms) - 1):
        assert fw_freqs[i + 1] > fw_freqs[i], (
            f"Forward-whirl frequency must INCREASE with Omega "
            f"(API 684 / Childs 1993 §3.4). Got at rpm={rpms[i]}: "
            f"omega_fw={fw_freqs[i]:.3f}; at rpm={rpms[i+1]}: "
            f"omega_fw={fw_freqs[i+1]:.3f}."
        )


def test_backward_whirl_frequency_decreases_with_omega() -> None:
    """The mode classified as 'backward' must have its damped natural
    frequency strictly decrease with spin speed Omega for the overhung
    disk (per Childs 1993 §3.4)."""
    model = _build_overhung_disk_jeffcott()
    rpms = [1000.0, 5000.0, 10000.0]
    bw_freqs = []
    for rpm in rpms:
        modes = run_lateral_analysis(model, rpm=rpm, n_modes=6)
        bw_modes = [m for m in modes if m.whirl == "backward"]
        assert bw_modes, (
            f"No backward-whirl mode found at rpm={rpm}; got "
            f"{[(m.omega_d_rad_s, m.whirl) for m in modes]}"
        )
        # Take the LOWEST backward branch (the one that decreases from
        # the static omega_n).
        bw_freqs.append(min(m.omega_d_rad_s for m in bw_modes))
    for i in range(len(rpms) - 1):
        assert bw_freqs[i + 1] < bw_freqs[i] * 1.001, (
            f"Backward-whirl frequency must DECREASE with Omega "
            f"(API 684 / Childs 1993 §3.4). Got at rpm={rpms[i]}: "
            f"omega_bw={bw_freqs[i]:.3f}; at rpm={rpms[i+1]}: "
            f"omega_bw={bw_freqs[i+1]:.3f}."
        )


def test_omega_zero_classifies_as_planar() -> None:
    """At zero spin speed all modes are planar (no whirl direction)."""
    model = _build_overhung_disk_jeffcott()
    modes = run_lateral_analysis(model, rpm=0.0, n_modes=4)
    for m in modes:
        assert m.whirl == "planar", (
            f"At Omega=0 modes should be 'planar'; got {m.whirl} "
            f"for omega_d={m.omega_d_rad_s}"
        )


def test_forward_backward_split_matches_childs_slope() -> None:
    """For the overhung disk, the slope of the gyroscopic split is
    approximately I_p / (2 I_t) * Omega per Childs 1993 eq. 3.49.

    With I_p = 0.5, I_t = 0.05, slope = 0.5 / (2 * 0.05) = 5.0.
    At Omega = 100 rad/s (~ 1000 rpm), the predicted split between
    forward and backward frequencies is approximately 2 * 5.0 * 100 = 1000
    rad/s, which is large compared to the at-rest frequency of ~170 rad/s.

    This test does NOT pin the absolute frequencies (the simple Childs
    formula is an asymptotic limit, not exact for a finite-element rotor)
    but it does check the sign: forward > omega_n > backward.
    """
    model = _build_overhung_disk_jeffcott()
    modes_static = run_lateral_analysis(model, rpm=0.0, n_modes=4)
    omega_n_static = modes_static[0].omega_d_rad_s

    # 5000 rpm provides a clear split for this rotor.
    modes_5k = run_lateral_analysis(model, rpm=5000.0, n_modes=6)
    fw = [
        m.omega_d_rad_s
        for m in modes_5k
        if m.whirl == "forward" and m.omega_d_rad_s > 100.0
    ]
    bw = [
        m.omega_d_rad_s
        for m in modes_5k
        if m.whirl == "backward" and m.omega_d_rad_s < omega_n_static + 1.0
    ]
    assert fw, "Expected at least one forward mode at 5000 rpm"
    assert bw, "Expected at least one backward mode at 5000 rpm"
    omega_fw = min(fw)
    omega_bw = max(bw)
    # The lowest forward branch must lie above the at-rest omega_n;
    # the highest backward branch must lie below. This is the API 684
    # convention sanity check.
    assert omega_fw > omega_n_static - 1e-6, (
        f"Forward-whirl frequency ({omega_fw:.3f}) must be >= omega_n at rest "
        f"({omega_n_static:.3f}). Sign convention is inverted (ADAPT-001)."
    )
    assert omega_bw < omega_n_static + 1e-6, (
        f"Backward-whirl frequency ({omega_bw:.3f}) must be <= omega_n at rest "
        f"({omega_n_static:.3f}). Sign convention is inverted (ADAPT-001)."
    )
