"""ADAPT-001 locked regression: forward-whirl sign convention.

This test will FAIL if the ADAPT-001 fix is reverted (i.e., if
_classify_whirl returns 'forward' for a mode whose frequency DECREASES
with spin speed, or 'backward' for one whose frequency INCREASES).

The locked invariant (API 684 §2.5 convention):
  - Forward whirl: eigenvector satisfies Z = -j*Y (orbit e^{j omega_d t}).
    Frequency INCREASES with spin speed.
  - Backward whirl: Z = +j*Y. Frequency DECREASES with spin speed.

Regression vector: overhung-disk Jeffcott rotor with I_p >> I_t so the
gyroscopic split is visually clear. At 1000 rpm and 10000 rpm the sign of
the slope is unambiguous.

References:
- Childs, D. (1993). Turbomachinery Rotordynamics, §3.4.
- API 684, 2nd ed. (2019), §2.5.
- ADAPT-001 (regression lock).
"""

from __future__ import annotations

import pytest

from cascade.rotor import LinearBearing, build_rotor_model, run_lateral_analysis
from cascade.units import LumpedDisk, Q, RotorSection, RotorShape


def _overhung_jeffcott():
    """Overhung disk, large I_p / I_t so gyroscopic split is large."""
    sec = RotorSection(
        diameter_outer=Q(0.02, "m"),
        diameter_inner=Q(0.0, "m"),
        length=Q(0.5, "m"),
        density=Q(7850.0, "kg/m^3"),
        axial_position=Q(0.0, "m"),
        material="AISI4340",
    )
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


def test_adapt_001_forward_whirl_increases_with_spin() -> None:
    """Locked: forward-whirl mode frequency must INCREASE with spin speed.

    This test will FAIL if _classify_whirl reverts to the pre-ADAPT-001
    convention (which incorrectly labelled the decreasing branch as forward).
    """
    model = _overhung_jeffcott()
    fw_freqs = []
    for rpm in [1000.0, 5000.0, 10000.0]:
        modes = run_lateral_analysis(model, rpm=rpm, n_modes=6)
        fw = [m for m in modes if m.whirl == "forward" and m.omega_d_rad_s > 100.0]
        assert fw, f"No forward-whirl mode at rpm={rpm} — ADAPT-001 may be reverted"
        fw_freqs.append(min(m.omega_d_rad_s for m in fw))

    assert fw_freqs[1] > fw_freqs[0], (
        f"Forward-whirl must INCREASE from 1000→5000 rpm; "
        f"got {fw_freqs[0]:.2f} → {fw_freqs[1]:.2f} rad/s. ADAPT-001 regressed."
    )
    assert fw_freqs[2] > fw_freqs[1], (
        f"Forward-whirl must INCREASE from 5000→10000 rpm; "
        f"got {fw_freqs[1]:.2f} → {fw_freqs[2]:.2f} rad/s. ADAPT-001 regressed."
    )


def test_adapt_001_backward_whirl_decreases_with_spin() -> None:
    """Locked: backward-whirl mode frequency must DECREASE with spin speed."""
    model = _overhung_jeffcott()
    bw_freqs = []
    for rpm in [1000.0, 5000.0, 10000.0]:
        modes = run_lateral_analysis(model, rpm=rpm, n_modes=6)
        bw = [m for m in modes if m.whirl == "backward"]
        assert bw, f"No backward-whirl mode at rpm={rpm}"
        bw_freqs.append(min(m.omega_d_rad_s for m in bw))

    assert bw_freqs[1] < bw_freqs[0] * 1.001, (
        f"Backward-whirl must DECREASE 1000→5000 rpm; "
        f"got {bw_freqs[0]:.2f} → {bw_freqs[1]:.2f} rad/s. ADAPT-001 regressed."
    )
    assert bw_freqs[2] < bw_freqs[1] * 1.001, (
        f"Backward-whirl must DECREASE 5000→10000 rpm; "
        f"got {bw_freqs[1]:.2f} → {bw_freqs[2]:.2f} rad/s. ADAPT-001 regressed."
    )


def test_adapt_001_classify_whirl_forward_vector() -> None:
    """Locked: Z = -j*Y eigenvector is classified as 'forward'.

    If reverted the function would return 'backward' or flip the label.
    """
    import numpy as np
    from cascade.rotor.eigenanalysis import _classify_whirl

    # Pure forward whirl: Y=1, Z=-j (orbit e^{j omega_d t})
    v = np.array([1.0 + 0j, 0, -1.0j, 0, 1.0 + 0j, 0, -1.0j, 0])
    result = _classify_whirl(v, omega_d=10.0, omega_spin=5.0)
    assert result == "forward", (
        f"_classify_whirl(Z=-j*Y) returned '{result}'; expected 'forward'. "
        f"ADAPT-001 regression: sign convention inverted."
    )

    # Pure backward whirl: Y=1, Z=+j
    v_back = np.array([1.0 + 0j, 0, 1.0j, 0, 1.0 + 0j, 0, 1.0j, 0])
    result_back = _classify_whirl(v_back, omega_d=10.0, omega_spin=5.0)
    assert result_back == "backward", (
        f"_classify_whirl(Z=+j*Y) returned '{result_back}'; expected 'backward'. "
        f"ADAPT-001 regression."
    )
