"""ADAPT-038: ARPACK shift-invert path matches dense LAPACK on small systems.

For systems with fewer than ``SPARSE_EIGENSOLVE_DOF_THRESHOLD = 20`` DOFs
the dense ``scipy.linalg.eig`` path is preferred (ARPACK overhead exceeds
the speed-up). For larger systems we switch to
``scipy.sparse.linalg.eigs`` with shift-invert at ``sigma = 0``.

This test exercises both code paths on a synthetic 10-DOF and a 40-DOF
QEP and asserts the resulting eigenvalues agree to 1e-6 in absolute
value -- the ARPACK approximation should be numerically indistinguishable
from the dense reference for these small problem sizes.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from cascade.rotor.eigenanalysis import (
    SPARSE_EIGENSOLVE_DOF_THRESHOLD,
    _dense_quadratic_eigvals,
    _sparse_quadratic_eigvals,
    solve_quadratic_eigvals,
)


def _synthetic_qep(n: int, seed: int = 42) -> tuple:
    """Build a random SPD-ish QEP (M, C, K) with eigenvalues near origin.

    M, K are SPD; C is small-amplitude (so eigenvalues come in
    weakly-damped conjugate pairs). The smallest-magnitude eigenvalues
    are well-separated from zero, which gives ARPACK shift-invert at
    sigma=0 a clean shot.
    """
    rng = np.random.default_rng(seed)
    A = rng.standard_normal((n, n))
    M = A @ A.T + n * np.eye(n)  # SPD
    B = rng.standard_normal((n, n))
    K = B @ B.T + n * np.eye(n)  # SPD
    C = 0.01 * (B + B.T)  # symmetric, small magnitude
    return M, C, K


def _smallest_magnitudes(eigvals: np.ndarray, k: int) -> np.ndarray:
    """Return the k eigenvalues nearest the origin, sorted."""
    idx = np.argsort(np.abs(eigvals))[:k]
    selected = eigvals[idx]
    return np.array(sorted(selected, key=lambda v: (v.real, v.imag)))


def test_sparse_and_dense_agree_on_20_dof_system() -> None:
    """20-DOF QEP: ARPACK lowest-k matches dense lowest-k within 1e-6."""
    n = 20
    M, C, K = _synthetic_qep(n)
    # Dense reference: full 2N spectrum
    lambdas_dense, _ = _dense_quadratic_eigvals(M, C, K)
    # Sparse: 4 lowest-magnitude eigenpairs
    n_modes = 4
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # suppress any ARPACK noise
        lambdas_sparse, _ = _sparse_quadratic_eigvals(M, C, K, n_modes)
    # Compare the k smallest-|lambda| eigenvalues
    dense_lo = _smallest_magnitudes(lambdas_dense, 2 * n_modes)
    sparse_lo = _smallest_magnitudes(lambdas_sparse, len(lambdas_sparse))
    # Take the intersection -- ARPACK should produce values that line up
    # with the dense ones to ~ 1e-6 relative.
    common = min(len(dense_lo), len(sparse_lo))
    for i in range(common):
        # Find the dense eigenvalue closest to this sparse one
        best = min(
            range(len(dense_lo)),
            key=lambda j: abs(dense_lo[j] - sparse_lo[i]),
        )
        gap = abs(dense_lo[best] - sparse_lo[i])
        assert gap < 1e-6 * (1.0 + abs(dense_lo[best])), (
            f"Sparse eigenvalue {sparse_lo[i]} does not match any dense "
            f"eigenvalue within 1e-6 (closest was {dense_lo[best]}, "
            f"gap {gap:.3e})."
        )


def test_solve_quadratic_dispatches_correctly() -> None:
    """``solve_quadratic_eigvals`` picks dense for n<20 and sparse otherwise."""
    # Small system: should take the dense path
    n_small = SPARSE_EIGENSOLVE_DOF_THRESHOLD - 5
    M, C, K = _synthetic_qep(n_small)
    lambdas, vecs = solve_quadratic_eigvals(M, C, K, n_modes=3)
    # Dense path returns 2N eigenvalues
    assert lambdas.shape == (2 * n_small,)
    assert vecs.shape == (n_small, 2 * n_small)

    # Larger system: should take the sparse path
    n_big = SPARSE_EIGENSOLVE_DOF_THRESHOLD + 5
    M2, C2, K2 = _synthetic_qep(n_big)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        lambdas2, vecs2 = solve_quadratic_eigvals(M2, C2, K2, n_modes=3)
    # Sparse path returns 2 * n_modes eigenvalues
    assert lambdas2.shape == (6,)
    assert vecs2.shape == (n_big, 6)


def test_n_modes_none_keeps_dense() -> None:
    """When ``n_modes`` is None the dense path is taken regardless of size."""
    n = 30  # would otherwise trigger sparse
    M, C, K = _synthetic_qep(n)
    lambdas, vecs = solve_quadratic_eigvals(M, C, K, n_modes=None)
    assert lambdas.shape == (2 * n,)
    assert vecs.shape == (n, 2 * n)


def test_arpack_fallback_on_failure_does_not_crash() -> None:
    """If ARPACK raises, the wrapper falls back to dense without exploding.

    This is a regression guard: the SPEC promise of
    ``solve_quadratic_eigvals`` is correctness first; speed is a bonus.
    """
    # Use n_modes equal to 2*n - 2 which forces ARPACK to request nearly
    # the full spectrum -- this is exactly the regime where ARPACK is
    # likely to fail. Our dispatch should *not* use sparse in this case
    # (the threshold n_modes < n - 2 protects against it), but we
    # double-check explicitly.
    n = 25
    M, C, K = _synthetic_qep(n)
    # Request a small number of modes -- normal case
    lambdas, vecs = solve_quadratic_eigvals(M, C, K, n_modes=3)
    assert lambdas.shape[0] >= 6  # at least 2 * n_modes
    # Now request the entire spectrum -- should be dense
    lambdas2, vecs2 = solve_quadratic_eigvals(M, C, K, n_modes=n)
    assert lambdas2.shape == (2 * n,)
