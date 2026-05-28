"""ADAPT-040: dedupe complex-conjugate eigenpairs before log-dec computation.

The QEP linearization yields 2N eigenvalues that come in N
complex-conjugate pairs ``lambda_k = sigma_k +/- j omega_d_k``. Each
physical mode is represented twice -- once by its upper-half-plane
representative and once by its conjugate. Before ADAPT-040, Cascade
computed the log-decrement on *all* 2N values; for any pure-real
eigenvalue (omega_d = 0, e.g. rigid-body / overdamped mode) the formula
``-2 pi sigma / |omega_d|`` blows up to numerical noise of magnitude 400+.

After ADAPT-040:

- :func:`cascade.rotor.eigenanalysis.run_lateral_analysis` returns
  ``n_modes`` *physical* modes (not 2 * n_modes), via the
  :func:`_dedupe_conjugate_pairs` helper.
- Any mode whose computed |log_dec| exceeds
  ``LOG_DEC_SUSPECT_THRESHOLD = 50`` has its log_decrement set to ``None``
  and emits a ``RuntimeWarning``.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from cascade.rotor import LinearBearing, build_rotor_model, run_lateral_analysis
from cascade.rotor.eigenanalysis import (
    LOG_DEC_SUSPECT_THRESHOLD,
    _dedupe_conjugate_pairs,
)
from cascade.units import LumpedDisk, Q, RotorSection, RotorShape


def _build_damped_jeffcott():
    """A standard damped Jeffcott rotor (so log-dec is meaningful)."""
    sec = RotorSection(
        diameter_outer=Q(0.040, "m"),
        diameter_inner=Q(0.0, "m"),
        length=Q(0.5, "m"),
        density=Q(7850.0, "kg/m^3"),
        axial_position=Q(0.0, "m"),
        material="AISI4340",
    )
    disk = LumpedDisk(
        mass=Q(5.0, "kg"),
        inertia_polar=Q(0.01, "kg*m^2"),
        inertia_diametrical=Q(0.005, "kg*m^2"),
        axial_position=Q(0.25, "m"),
    )
    shape = RotorShape(sections=[sec], disks=[disk])
    K_b = 1.3e7
    brg1 = LinearBearing(
        name="b1",
        axial_position=Q(0.0, "m"),
        K_yy=Q(K_b, "N/m"),
        K_zz=Q(K_b, "N/m"),
        C_yy=Q(200.0, "N*s/m"),
        C_zz=Q(200.0, "N*s/m"),
    )
    brg2 = LinearBearing(
        name="b2",
        axial_position=Q(0.5, "m"),
        K_yy=Q(K_b, "N/m"),
        K_zz=Q(K_b, "N/m"),
        C_yy=Q(200.0, "N*s/m"),
        C_zz=Q(200.0, "N*s/m"),
    )
    return build_rotor_model(shape, [brg1, brg2], elements_per_section=10)


def test_dedupe_returns_only_upper_half_plane() -> None:
    """The deduper drops all eigenvalues with Im(lambda) <= 0."""
    # Build a synthetic conjugate-pair array: [+j 10, -j 10, +j 20, -j 20, 0+0j]
    eigvals = np.array(
        [10j, -10j, 20j, -20j, 0.0 + 0j], dtype=complex
    )
    eigvecs = np.eye(5, dtype=complex)
    kept_vals, kept_vecs = _dedupe_conjugate_pairs(eigvals, eigvecs)
    assert kept_vals.shape == (2,), (
        f"Expected 2 upper-half-plane survivors, got {kept_vals.shape}"
    )
    assert all(np.imag(v) > 0 for v in kept_vals)
    assert kept_vecs.shape == (5, 2)


def test_no_log_dec_exceeds_suspect_threshold() -> None:
    """ADAPT-040: no returned mode has |log_dec| > LOG_DEC_SUSPECT_THRESHOLD.

    Either the value is a sane finite reading (typical journal-bearing log
    decs are in [0.01, 10]), or it has been set to None.
    """
    model = _build_damped_jeffcott()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        modes = run_lateral_analysis(model, rpm=5000.0, n_modes=4)
    for i, m in enumerate(modes):
        if m.log_decrement is None:
            continue  # was flagged + set to None per ADAPT-040
        assert abs(m.log_decrement) <= LOG_DEC_SUSPECT_THRESHOLD, (
            f"Mode {i} returned |log_decrement| = {abs(m.log_decrement):.3e} "
            f"> {LOG_DEC_SUSPECT_THRESHOLD}; expected dedupe to have caught it."
        )


def test_run_lateral_analysis_returns_only_physical_modes() -> None:
    """The function returns only *distinct physical* modes -- no conjugate
    twins and no near-zero rigid-body modes.

    Without ADAPT-040's dedupe, the QEP's 2N eigenvalues would include both
    halves of each conjugate pair. The dedupe collapses these to one per
    physical mode; the returned list may be shorter than ``n_modes`` if the
    rotor has fewer distinct physical modes in the low-frequency range
    (e.g., y/z plane degeneracy collapses two eigenvalues to one mode).
    """
    model = _build_damped_jeffcott()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        modes = run_lateral_analysis(model, rpm=5000.0, n_modes=6)
    # We get *at most* n_modes back; never more
    assert len(modes) <= 6
    assert len(modes) >= 1, "Expected at least one physical mode"
    # Every returned mode has Im(lambda) > 0 (upper-half-plane only,
    # i.e. no conjugate twins).
    for m in modes:
        assert m.omega_d_rad_s > 0, (
            f"Conjugate twin (Im(lambda) <= 0) leaked through dedupe: "
            f"omega_d = {m.omega_d_rad_s}"
        )
    # Frequencies strictly ascending after the dedupe step.
    omegas = [m.omega_d_rad_s for m in modes]
    assert omegas == sorted(omegas), (
        f"Modes should be ascending in omega_d; got {omegas}"
    )
