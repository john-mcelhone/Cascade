"""Independent verification — rotor dynamics (beam-FEM lateral + torsional).

Oracles are analytical closed forms from vibration theory:
  - Simply-supported uniform shaft, 1st mode:  w_n = pi^2 * sqrt(EI/(rho A L^4))
  - Higher EB modes scale as n^2
  - Disk-dominated Jeffcott:  w_n = sqrt(k_eff/m),  k_eff = 48 EI / L^3 (central load)
  - Rigid rotor on two equal bearings: bounce w_n = sqrt(2K / m_total)
  - Two-inertia torsional:  w_n = sqrt(k (1/J1 + 1/J2))
  - Gyroscopic effect: forward-whirl criticals rise, backward fall, with speed
  - Critical speeds rise monotonically with support stiffness
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from cascade.rotor import (
    LinearBearing,
    build_rotor_model,
    run_critical_speed_map,
    run_lateral_analysis,
    run_stability,
    run_torsional_analysis,
    run_unbalance_response,
)
from cascade.units import LumpedDisk, Q, RotorSection, RotorShape

E_STEEL = 2.0e11
RHO_STEEL = 7850.0


def _uniform_shaft(d: float, length: float, n_el: int, k_bearing: float,
                   disk: LumpedDisk | None = None,
                   c_bearing: float = 500.0):  # noqa: ANN202
    sec = RotorSection(diameter_outer=Q(d, "m"), diameter_inner=Q(0.0, "m"),
                       length=Q(length, "m"), density=Q(RHO_STEEL, "kg/m^3"),
                       axial_position=Q(0.0, "m"), material="AISI 4340")
    shape = RotorShape(sections=[sec], disks=[disk] if disk else [])
    brgs = [
        LinearBearing(name="b1", axial_position=Q(0.0, "m"),
                      K_yy=Q(k_bearing, "N/m"), K_zz=Q(k_bearing, "N/m"),
                      C_yy=Q(c_bearing, "N*s/m"), C_zz=Q(c_bearing, "N*s/m")),
        LinearBearing(name="b2", axial_position=Q(length, "m"),
                      K_yy=Q(k_bearing, "N/m"), K_zz=Q(k_bearing, "N/m"),
                      C_yy=Q(c_bearing, "N*s/m"), C_zz=Q(c_bearing, "N*s/m")),
    ]
    return build_rotor_model(shape, brgs, elements_per_section=n_el,
                             youngs_modulus=Q(E_STEEL, "Pa"))


def test_simply_supported_uniform_beam_first_mode() -> None:
    d, length = 0.03, 0.6
    model = _uniform_shaft(d, length, n_el=12, k_bearing=1e10)
    modes = run_lateral_analysis(model, rpm=0.0, n_modes=4)
    inertia = math.pi * d ** 4 / 64.0
    area = math.pi * d ** 2 / 4.0
    w1 = math.pi ** 2 * math.sqrt(E_STEEL * inertia / (RHO_STEEL * area * length ** 4))
    assert modes[0].omega_n_rad_s == pytest.approx(w1, rel=0.08)


def test_higher_beam_modes_scale_quadratically() -> None:
    model = _uniform_shaft(0.03, 0.6, n_el=14, k_bearing=1e10)
    modes = run_lateral_analysis(model, rpm=0.0, n_modes=4)
    # EB simply-supported: w_n ∝ n^2, so 2nd ≈ 4 × 1st.
    ratio = modes[1].omega_n_rad_s / modes[0].omega_n_rad_s
    assert ratio == pytest.approx(4.0, rel=0.15)


def test_all_natural_frequencies_positive() -> None:
    model = _uniform_shaft(0.03, 0.6, n_el=10, k_bearing=1e9)
    for m in run_lateral_analysis(model, rpm=0.0, n_modes=6):
        assert m.omega_n_rad_s > 0.0
        assert m.omega_d_rad_s >= 0.0


def test_disk_dominated_jeffcott_natural_frequency() -> None:
    """Heavy central disk on a light shaft, stiff supports:
    w_n -> sqrt(48 EI / L^3 / m_disk)."""
    d, length, m_disk = 0.02, 0.5, 100.0
    disk = LumpedDisk(mass=Q(m_disk, "kg"), inertia_polar=Q(0.02, "kg*m^2"),
                      inertia_diametrical=Q(0.01, "kg*m^2"), axial_position=Q(length / 2, "m"))
    model = _uniform_shaft(d, length, n_el=10, k_bearing=1e10, disk=disk)
    modes = run_lateral_analysis(model, rpm=0.0, n_modes=2)
    inertia = math.pi * d ** 4 / 64.0
    k_eff = 48.0 * E_STEEL * inertia / length ** 3
    w_jeff = math.sqrt(k_eff / m_disk)
    assert modes[0].omega_n_rad_s == pytest.approx(w_jeff, rel=0.06)


def test_rigid_rotor_bounce_mode_on_soft_bearings() -> None:
    """A short thick (rigid) shaft on two soft equal bearings bounces at
    sqrt(2K / m_total)."""
    d, length, k_b = 0.4, 0.3, 5.0e6
    extra = LumpedDisk(mass=Q(40.0, "kg"), inertia_polar=Q(0.5, "kg*m^2"),
                       inertia_diametrical=Q(0.25, "kg*m^2"), axial_position=Q(length / 2, "m"))
    model = _uniform_shaft(d, length, n_el=4, k_bearing=k_b, disk=extra, c_bearing=50.0)
    area = math.pi * d ** 2 / 4.0
    m_total = RHO_STEEL * area * length + 40.0
    w_bounce = math.sqrt(2.0 * k_b / m_total)
    modes = run_lateral_analysis(model, rpm=0.0, n_modes=2)
    assert modes[0].omega_n_rad_s == pytest.approx(w_bounce, rel=0.05)


def test_critical_speed_rises_with_bearing_stiffness() -> None:
    model = _uniform_shaft(0.03, 0.6, n_el=8, k_bearing=1e8)
    csm = run_critical_speed_map(model, n_modes=3, stiffness_min_n_per_m=1e6,
                                 stiffness_max_n_per_m=1e9, n_stiffness=8)
    first_mode = np.array(csm.mode_frequencies_rad_s)
    if first_mode.ndim == 2:
        first_mode = first_mode[:, 0]
    diffs = np.diff(first_mode)
    assert np.all(diffs >= -1e-6)  # monotone non-decreasing
    assert first_mode[-1] > first_mode[0]


def test_gyroscopic_effect_splits_forward_above_backward() -> None:
    """At speed, gyroscopic coupling lifts forward-whirl criticals above
    backward-whirl criticals."""
    d, length = 0.02, 0.5
    disk = LumpedDisk(mass=Q(8.0, "kg"), inertia_polar=Q(0.05, "kg*m^2"),
                      inertia_diametrical=Q(0.025, "kg*m^2"), axial_position=Q(length / 2, "m"))
    model = _uniform_shaft(d, length, n_el=8, k_bearing=1e9, disk=disk)
    modes = run_lateral_analysis(model, rpm=80000.0, n_modes=8)
    fwd = [m.omega_n_rad_s for m in modes if str(m.whirl).lower().endswith("forward")]
    bwd = [m.omega_n_rad_s for m in modes if str(m.whirl).lower().endswith("backward")]
    assert fwd and bwd, "expected both forward and backward whirl modes at speed"
    assert min(fwd) > min(bwd)


def test_two_inertia_torsional_natural_frequency() -> None:
    j1, j2, k = 0.1, 0.2, 5.0e5
    freqs = run_torsional_analysis([j1, j2], [k], n_modes=2)
    nonzero = sorted(f for f in freqs if f > 1.0)
    expected = math.sqrt(k * (1.0 / j1 + 1.0 / j2))
    assert nonzero[0] == pytest.approx(expected, rel=0.02)


def test_unbalance_response_peaks_near_first_critical() -> None:
    d, length = 0.02, 0.5
    disk = LumpedDisk(mass=Q(5.0, "kg"), inertia_polar=Q(0.01, "kg*m^2"),
                      inertia_diametrical=Q(0.005, "kg*m^2"), axial_position=Q(length / 2, "m"))
    model = _uniform_shaft(d, length, n_el=8, k_bearing=1e8, disk=disk, c_bearing=2000.0)
    first = run_lateral_analysis(model, rpm=0.0, n_modes=2)[0].omega_n_rad_s
    rpm_crit = first * 60.0 / (2.0 * math.pi)
    mid = model.n_nodes // 2
    res = run_unbalance_response(model, unbalance_node=mid, unbalance_mass_kg=0.005,
                                 unbalance_radius_m=0.05,
                                 rpm_sweep=np.linspace(rpm_crit * 0.4, rpm_crit * 1.8, 240))
    assert res.amplification_factor, "no amplification factor reported"
    q = next(iter(res.amplification_factor.values()))
    assert q > 1.0  # resonant amplification
    peak = next(iter(res.peak_rpms.values()))
    assert peak == pytest.approx(rpm_crit, rel=0.15)


def test_stability_first_mode_log_decrement_is_finite() -> None:
    """The dominant (first) lateral mode — the API 684 Level I stability mode —
    must yield a finite log decrement across the whole speed sweep."""
    model = _uniform_shaft(0.03, 0.6, n_el=8, k_bearing=1e8, c_bearing=3000.0)
    stab = run_stability(model, rpm_sweep=np.linspace(1000, 30000, 8), n_modes=4)
    logdec = np.array(stab.log_decrements, dtype=float)
    first_mode = logdec[:, 0] if logdec.ndim == 2 else logdec
    assert np.all(np.isfinite(first_mode))
