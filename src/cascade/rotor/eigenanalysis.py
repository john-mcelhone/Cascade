"""Complex generalized eigenvalue analysis for the rotor QEP.

The lateral equation of motion at speed Omega is

    M q_ddot + (C + Omega G) q_dot + K q = 0

which is a quadratic eigenvalue problem (QEP); we linearize to a generalized
eigenvalue problem of order 2N (state-space form). The 2N complex eigenpairs
come in 2N/2 conjugate pairs lambda_k = sigma_k +/- i omega_d_k, from which we
extract:

  - omega_d_k (damped natural frequency, Im(lambda))
  - sigma_k (decay rate, Re(lambda) -- negative => stable)
  - zeta_k = -sigma / sqrt(sigma^2 + omega_d^2) (modal damping ratio)
  - omega_n_k = sqrt(sigma^2 + omega_d^2) (undamped natural frequency)
  - delta_k = -2 pi sigma / |omega_d| (log decrement, API 684 §3)

Whirl direction: forward if the y- and z-components of the mode shape rotate
in the same sense as Omega; backward otherwise.

Per SPEC_SHEET §9: ARPACK shift-invert for the lowest k modes; dense LAPACK
for systems smaller than ~ 500 DOF. Use scipy.linalg.eig for the general
non-symmetric problem.

References:
- API 684 §2.4 (eigensolve discussion); §3 (log decrement criterion).
- Childs 1993, Ch. 5 (eigenanalysis of the rotor QEP).
- Friswell et al. 2010, Ch. 5 (eigenvalue methods).
- Lehoucq, Sorensen, Yang 1998 (ARPACK).
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
import scipy.linalg as la
import scipy.sparse as sp
from scipy.sparse.linalg import ArpackNoConvergence, eigs

from cascade.rotor.beam_fem import RotorModel

# ADAPT-040: above this absolute value, a log-decrement reading is considered
# numerical noise from a near-zero |omega_d| (un-deduped conjugate pair, pure
# real eigenvalue, or rigid-body mode) and is flagged + suppressed.
LOG_DEC_SUSPECT_THRESHOLD: float = 50.0

# ADAPT-041: a damping matrix with Frobenius norm below this threshold is
# treated as undamped (eigenvalues are purely imaginary; log-decrement is
# mathematically zero and the numerical noise of order 1e-15 is meaningless).
UNDAMPED_DAMPING_FROBENIUS_TOL: float = 1.0e-9

# ADAPT-038: below this DOF count, ARPACK's startup overhead exceeds the
# benefit of sparsity; we fall back to the dense LAPACK solver.
SPARSE_EIGENSOLVE_DOF_THRESHOLD: int = 20


@dataclass
class EigenResult:
    """One eigenmode's reduced numerical fingerprint.

    Attributes:
        omega_n_rad_s: undamped natural frequency [rad/s].
        omega_d_rad_s: damped natural frequency [rad/s] (imaginary part).
        sigma_rad_s: decay rate [1/s] (real part; negative = stable).
        zeta: modal damping ratio [-].
        log_decrement: API 684 log decrement [-]. ADAPT-041: returned as
            ``None`` when the rotor has no damping (C = 0), because the
            log-dec is mathematically zero and any computed value is
            numerical noise of order machine epsilon. ADAPT-040: also
            returned as ``None`` when |log_dec| exceeds
            ``LOG_DEC_SUSPECT_THRESHOLD`` (suggests an un-deduped mode).
        whirl: 'forward' / 'backward' / 'planar' / 'unknown'.
        mode_shape: complex eigenvector, shape (n_dof,).
        eigenvalue: complex eigenvalue (sigma + j omega_d).
    """

    omega_n_rad_s: float
    omega_d_rad_s: float
    sigma_rad_s: float
    zeta: float
    log_decrement: Optional[float]
    whirl: str
    mode_shape: np.ndarray
    eigenvalue: complex

    @property
    def freq_hz(self) -> float:
        """Damped natural frequency in Hz."""
        return self.omega_d_rad_s / (2.0 * math.pi)

    @property
    def freq_rpm(self) -> float:
        """Damped natural frequency in rpm."""
        return self.omega_d_rad_s * 60.0 / (2.0 * math.pi)


def _classify_whirl(
    mode: np.ndarray, omega_d: float, omega_spin: float
) -> str:
    """Identify forward / backward whirl from the eigenvector phases.

    Conventions (verified against the project's gyroscopic matrix in
    ``beam_fem.timoshenko_element_matrices`` and ``beam_fem._add_lumped_disk``):

    - DOF ordering per node is ``[y, theta_z, z, theta_y]``.
    - Spin Omega > 0 is right-handed about +x. The shaft surface point at
      (y, z) = (1, 0) rotates toward (0, 1) at a quarter turn, i.e., the
      orbit ``y(t) + j z(t) = e^{j Omega t}``.
    - With the project's time convention ``q(t) = Re[v e^{lambda t}]`` and
      lambda = sigma + j omega_d (omega_d > 0), the orbit traced by a
      forward-whirling mode has ``y(t) + j z(t) ∝ e^{j omega_d t}``. This
      requires the complex eigenvector components to satisfy ``Z = -j Y``,
      i.e., ``arg(z / y) = -pi/2``.
    - For the rotation DOFs (theta_z, theta_y), forward whirl has
      ``arg(theta_y / theta_z) = +pi/2`` (theta_y leads theta_z by 90 deg).

    This matches the disk-only gyroscopic check: with the project's
    ``G_unit[tz_i, ty_i] = -Ip`` / ``G_unit[ty_i, tz_i] = +Ip`` and the beam
    G_block sign pattern, the eigenmode whose damped frequency *increases*
    with Omega is the forward-whirl mode and satisfies ``z = -j y``.

    Earlier versions of this classifier compared ``arg(z/y)`` against
    ``+pi/2`` for forward whirl, which is the convention for the
    time-dependence ``e^{-j omega_d t}``. With ``e^{+j omega_d t}`` that
    inverts the labels. See ADAPT-001.

    We classify using the *largest-amplitude* translational node (avoids
    node-near-zero ambiguity). If translational amplitude
    is degenerate (e.g., a pure conical / disk-rotation mode) we fall back
    to the rotation DOFs ``(theta_z, theta_y)`` where forward whirl
    corresponds to ``arg(theta_y / theta_z) = +pi/2``.

    Reference: Childs 1993 §3.4 (forward / backward whirl definitions);
    Genta 1999 §4.5; API 684 §2.5 (Campbell convention).

    >>> import numpy as np
    >>> # Pure forward whirl: y(t) = cos(omega_d t), z(t) = sin(omega_d t)
    >>> # As complex eigenvector: Y = 1, Z = -j (so q(t) = Re[v e^{j omega_d t}])
    >>> v = np.array([1.0+0j, 0, -1.0j, 0, 1.0+0j, 0, -1.0j, 0])
    >>> _classify_whirl(v, 10.0, 5.0)
    'forward'
    >>> # Backward whirl: Z = +j
    >>> v_back = np.array([1.0+0j, 0, 1.0j, 0, 1.0+0j, 0, 1.0j, 0])
    >>> _classify_whirl(v_back, 10.0, 5.0)
    'backward'
    """
    if abs(omega_spin) < 1e-9:
        # At standstill, no whirl direction is defined.
        return "planar"
    n_dof = mode.shape[0]
    n_nodes = n_dof // 4
    # Find the node with largest |y| + |z| (avoids the node-of-mode ambiguity).
    best_node = 0
    best_amp = -1.0
    for i in range(n_nodes):
        y_i = mode[4 * i]
        z_i = mode[4 * i + 2]
        amp = abs(y_i) + abs(z_i)
        if amp > best_amp:
            best_amp = amp
            best_node = i
    y = mode[4 * best_node]
    z = mode[4 * best_node + 2]
    # Fall back to the rotation DOFs when translational amplitudes are
    # negligible (pure conical / disk-tilt modes).
    use_rotation_dofs = abs(y) < 1e-12 or abs(z) < 1e-12
    if use_rotation_dofs:
        # Find the node with largest |theta_z| + |theta_y|
        best_rot_node = 0
        best_rot_amp = -1.0
        for i in range(n_nodes):
            tz_i = mode[4 * i + 1]
            ty_i = mode[4 * i + 3]
            amp = abs(tz_i) + abs(ty_i)
            if amp > best_rot_amp:
                best_rot_amp = amp
                best_rot_node = i
        tz = mode[4 * best_rot_node + 1]
        ty = mode[4 * best_rot_node + 3]
        if abs(tz) < 1e-14 or abs(ty) < 1e-14:
            return "planar"
        # Forward whirl: arg(ty / tz) = +pi/2 (ty leads tz by 90 deg).
        phase_rot = float(np.angle(ty / tz))
        if phase_rot > 0:
            return "forward" if omega_d * omega_spin >= 0 else "backward"
        if phase_rot < 0:
            return "backward" if omega_d * omega_spin >= 0 else "forward"
        return "planar"
    # Forward whirl: arg(z / y) = -pi/2 with our e^{+j omega_d t} convention.
    phase_diff = float(np.angle(z / y))
    if phase_diff < 0:
        return "forward" if omega_d * omega_spin >= 0 else "backward"
    if phase_diff > 0:
        return "backward" if omega_d * omega_spin >= 0 else "forward"
    return "planar"


def _eigenresult_from_lambda(
    lam: complex,
    vec: np.ndarray,
    omega_spin: float,
    *,
    log_dec_override: Optional[float] = ...,  # type: ignore[assignment]
) -> EigenResult:
    """Build an :class:`EigenResult` from a single eigenpair.

    ADAPT-040: any mode with computed ``|log_dec| > LOG_DEC_SUSPECT_THRESHOLD``
    is flagged with a warning and ``log_decrement`` is set to ``None`` rather
    than returning the gargantuan-magnitude noise from a near-zero
    ``|omega_d|``.

    Parameters
    ----------
    log_dec_override
        Sentinel default ``...`` means "compute log_dec from the eigenvalue
        as usual". Pass ``None`` (or any explicit value) to override -- e.g.
        ADAPT-041 passes ``None`` for an undamped rotor.
    """
    sigma = float(lam.real)
    omega_d = float(lam.imag)
    omega_n = math.sqrt(sigma * sigma + omega_d * omega_d)
    if omega_n > 0:
        zeta = -sigma / omega_n
    else:
        zeta = 0.0
    log_dec: Optional[float]
    if log_dec_override is not ...:
        log_dec = log_dec_override
    else:
        # API 684 log decrement; guard against omega_d = 0
        if abs(omega_d) > 1e-12:
            log_dec_val = -2.0 * math.pi * sigma / abs(omega_d)
            if abs(log_dec_val) > LOG_DEC_SUSPECT_THRESHOLD:
                # ADAPT-040: this magnitude is almost certainly the result
                # of an un-deduped pure-real eigenvalue (omega_d near zero)
                # rather than a physical log-decrement reading.
                warnings.warn(
                    f"Mode at lambda = {lam} produced |log_decrement| = "
                    f"{abs(log_dec_val):.3e} > {LOG_DEC_SUSPECT_THRESHOLD}. "
                    f"This is almost certainly numerical noise from a "
                    f"near-zero |omega_d|, not a physical reading; "
                    f"log_decrement set to None (ADAPT-040).",
                    category=RuntimeWarning,
                    stacklevel=3,
                )
                log_dec = None
            else:
                log_dec = float(log_dec_val)
        else:
            log_dec = 0.0
    whirl = _classify_whirl(vec, omega_d, omega_spin)
    return EigenResult(
        omega_n_rad_s=omega_n,
        omega_d_rad_s=omega_d,
        sigma_rad_s=sigma,
        zeta=zeta,
        log_decrement=log_dec,
        whirl=whirl,
        mode_shape=vec,
        eigenvalue=lam,
    )


def _dedupe_conjugate_pairs(
    eigvals: np.ndarray, eigvecs: np.ndarray, *, im_tol: float = 1.0e-9
) -> Tuple[np.ndarray, np.ndarray]:
    """Return only the upper-half-plane representatives of conjugate pairs.

    The QEP linearization yields 2N eigenvalues that arrive as
    complex-conjugate pairs ``lambda_k = sigma_k +/- j omega_d_k``; each
    physical mode is represented twice. Per ADAPT-040 we discard the
    ``omega_d <= 0`` half (which carries the conjugate, redundant copy of
    each mode and any zero-imaginary spurious modes).

    Pure-real eigenvalues (``|omega_d| < im_tol``) are also dropped --
    these arise from rigid-body / overdamped modes and produce
    indeterminate log-decrement (sigma / 0) when naively retained.
    """
    keep = np.imag(eigvals) > im_tol
    return eigvals[keep], eigvecs[:, keep]


def _dense_quadratic_eigvals(
    M: np.ndarray, C: np.ndarray, K: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Dense LAPACK path -- returns all 2N eigenpairs."""
    n = M.shape[0]
    I_n = np.eye(n)
    A = np.block([[np.zeros((n, n)), I_n], [-K, -C]])
    B = np.block([[I_n, np.zeros((n, n))], [np.zeros((n, n)), M]])
    lambdas, vecs = la.eig(A, B)
    # vecs[:n, :] are the v parts; vecs[n:, :] are lambda * v.
    return lambdas, vecs[:n, :]


def _sparse_quadratic_eigvals(
    M: np.ndarray,
    C: np.ndarray,
    K: np.ndarray,
    n_modes: int,
    sigma: complex = 0.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """ARPACK shift-invert path for the lowest ``n_modes`` modes.

    Per SPEC_SHEET §9 we use ``scipy.sparse.linalg.eigs`` with shift-invert
    around ``sigma`` (default 0+0j -- the lowest frequencies). We request
    ``2 * n_modes`` Ritz values so that, after de-duplication of conjugate
    pairs, ~``n_modes`` physical modes remain.

    Sparse matrices are built as ``csc_matrix`` -- ARPACK requires a fixed
    sparsity pattern but the K, C, M matrices we ship in are already
    dense (FEM assembly fills almost the full block). Conversion is
    constant-time; the win is that the shift-invert step exploits sparsity
    of the LU factorization of ``A - sigma*B``.

    Returns a length-``2*n_modes`` (or fewer, if ARPACK didn't converge for
    every requested mode) ``lambdas`` array and the matching ``(N, 2*n_modes)``
    ``vecs`` array (top half of the companion vector, i.e. v -- *not* lambda*v).
    """
    n = M.shape[0]
    I_n = sp.eye(n, format="csc")
    M_sp = sp.csc_matrix(M)
    K_sp = sp.csc_matrix(K)
    C_sp = sp.csc_matrix(C)
    # Companion form A x = lambda B x, x = [v; lambda v]
    A = sp.bmat(
        [[None, I_n], [-K_sp, -C_sp]], format="csc"
    )
    B = sp.bmat(
        [
            [I_n, sp.csc_matrix((n, n))],
            [sp.csc_matrix((n, n)), M_sp],
        ],
        format="csc",
    )
    # ARPACK NCV (subspace size) must satisfy k < ncv <= n_state where
    # n_state = 2 * n. We request 2 * n_modes eigenpairs (one for each
    # conjugate twin). With shift-invert at sigma the 'LM' which='LM' picks
    # the eigenvalues closest to sigma.
    k = min(2 * n_modes, 2 * n - 2)
    if k < 1:
        # Edge case: tiny system; fall back to dense.
        return _dense_quadratic_eigvals(M, C, K)
    lambdas, vecs_state = eigs(A, k=k, M=B, sigma=sigma, which="LM")
    # vecs_state has shape (2n, k); upper half corresponds to v.
    return lambdas, vecs_state[:n, :]


def solve_quadratic_eigvals(
    M: np.ndarray,
    C: np.ndarray,
    K: np.ndarray,
    n_modes: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Solve the QEP (lambda^2 M + lambda C + K) v = 0 via 2N linearization.

    Companion form (state-space)::

        A = [[0, I], [-K, -C]],   B = [[I, 0], [0, M]]

    so A x = lambda B x, where x = [v; lambda v].

    ADAPT-038: For systems with ``n >= SPARSE_EIGENSOLVE_DOF_THRESHOLD``
    DOFs *and* a requested ``n_modes`` that is small relative to ``n``,
    we use ARPACK shift-invert (scipy.sparse.linalg.eigs) to get only
    the lowest ``n_modes`` modes. For smaller systems (or when essentially
    all modes are wanted), ARPACK overhead exceeds the dense-LAPACK cost
    and we fall through to ``scipy.linalg.eig``.

    Returns
    -------
    lambdas : complex ndarray of length 2N (dense path) or 2*n_modes (sparse).
    vecs : complex (N, 2N) array of right eigenvectors (only the upper half
        of the companion vector, corresponding to v).
    """
    n = M.shape[0]
    use_sparse = (
        n_modes is not None
        and n >= SPARSE_EIGENSOLVE_DOF_THRESHOLD
        and n_modes < n - 2
    )
    if use_sparse:
        assert n_modes is not None  # narrow for type-checker
        try:
            return _sparse_quadratic_eigvals(M, C, K, n_modes)
        except (ArpackNoConvergence, ValueError, RuntimeError):
            # ARPACK can fail (shift-invert singular, convergence, etc).
            # In that case fall through to the dense path -- the SPEC
            # promise is correctness first; the speedup is a bonus.
            warnings.warn(
                "ARPACK shift-invert did not converge; falling back to "
                "dense scipy.linalg.eig (ADAPT-038).",
                category=RuntimeWarning,
                stacklevel=2,
            )
    return _dense_quadratic_eigvals(M, C, K)


def run_lateral_analysis(
    rotor: RotorModel,
    rpm: float,
    n_modes: int = 6,
) -> List[EigenResult]:
    """Compute the n_modes lowest-frequency complex modes at the given speed.

    Parameters
    ----------
    rotor : RotorModel
        Assembled global model. K, C are speed-dependent via the bearings;
        the gyroscopic operator is built from G_unit * Omega.
    rpm : float
        Spin speed in rpm.
    n_modes : int
        Number of modes (sorted by ascending damped frequency) to return.

    Returns
    -------
    list[EigenResult]
        Sorted ascending by |omega_d|, length n_modes.

    Notes
    -----
    ADAPT-041: if the *total* damping (Rayleigh + bearings + gyroscopic)
    has Frobenius norm below ``UNDAMPED_DAMPING_FROBENIUS_TOL``, every
    returned mode has ``log_decrement = None`` and a RuntimeWarning is
    emitted -- the eigenvalues are purely imaginary and the log-dec is
    numerical noise.

    ADAPT-040: conjugate pairs are de-duplicated *before* the log-dec
    computation; any mode with ``|log_dec| > LOG_DEC_SUSPECT_THRESHOLD``
    is flagged and its log-dec set to ``None``.

    ADAPT-038: the underlying eigensolve uses ARPACK shift-invert for
    systems with >= 20 DOFs and dense LAPACK for smaller systems.
    """
    omega_spin = rpm * 2.0 * math.pi / 60.0
    K_total = rotor.K_at(rpm)
    C_total = rotor.C_at(rpm) + omega_spin * rotor.G_unit
    # NOTE on sign convention: in the equation
    #   M q_ddot + (C + Omega G) q_dot + K q = 0
    # the gyroscopic operator enters as part of the damping term.

    # ADAPT-041: detect an undamped rotor before solving. If C_total is
    # numerically zero we will return log_decrement = None and emit a
    # warning -- the log-decs are mathematically zero and any computed
    # value is noise of order 1e-15.
    undamped = (
        float(np.linalg.norm(C_total, "fro"))
        < UNDAMPED_DAMPING_FROBENIUS_TOL
    )
    if undamped:
        warnings.warn(
            "Rotor has no damping -- log-decrement values are not "
            "physically meaningful and will be returned as None. Add a "
            "journal bearing, Rayleigh damping, or material damping "
            "(ADAPT-041).",
            category=RuntimeWarning,
            stacklevel=2,
        )

    # For the eigenproblem we need a non-singular K. If unconstrained (no
    # bearings), K has rigid-body modes (eigenvalue 0). We accept those modes
    # and filter them out below.
    #
    # ADAPT-038: route n_modes through so the solver can pick the sparse
    # path when worthwhile.
    lambdas, vecs = solve_quadratic_eigvals(
        rotor.M, C_total, K_total, n_modes=n_modes
    )

    # ADAPT-040: dedupe conjugate pairs -- keep only Im(lambda) > 0.
    lambdas_dd, vecs_dd = _dedupe_conjugate_pairs(lambdas, vecs)

    # For an isotropic rotor at zero spin, the y-plane and z-plane modes are
    # degenerate; we collapse them to a single "physical" mode using a
    # relative-frequency clustering tolerance.
    results: List[EigenResult] = []
    seen_freqs: List[float] = []
    # Sort by Im part magnitude
    order = np.argsort(np.abs(lambdas_dd.imag))
    # Relative tolerance for treating two close eigenvalues as the same
    # physical mode (y/z plane degeneracy at omega = 0). 1e-3 is generous
    # enough to absorb numerical noise but tight enough to keep distinct
    # modes (which differ by orders of magnitude in real rotors).
    DEDUP_REL_TOL = 1.0e-3
    for idx in order:
        lam = lambdas_dd[idx]
        if not np.isfinite(lam):
            continue
        omega_d = lam.imag
        if omega_d <= 1e-6:
            # Skip near-zero (rigid-body) modes that survived dedupe.
            continue
        # Collapse y/z plane duplicates
        if any(
            abs(omega_d - f) <= DEDUP_REL_TOL * max(f, 1.0)
            for f in seen_freqs
        ):
            continue
        seen_freqs.append(omega_d)
        v = vecs_dd[:, idx]
        # ADAPT-041: force log_decrement = None when the rotor is undamped.
        log_dec_override: object = None if undamped else ...
        results.append(
            _eigenresult_from_lambda(
                lam, v, omega_spin, log_dec_override=log_dec_override  # type: ignore[arg-type]
            )
        )
        if len(results) >= n_modes:
            break
    return results


def run_undamped_analysis(
    rotor: RotorModel,
    rpm: float = 0.0,
    n_modes: int = 6,
) -> List[EigenResult]:
    """Symmetric undamped eigenanalysis (K q = omega^2 M q) at given spin speed.

    With no damping and at Omega = 0 the problem reduces to the symmetric
    generalized eigenvalue problem. For Omega != 0 the gyroscopic term still
    couples the planes; we use this for the in-vacuo / critical-speed map.

    Returns the n_modes lowest natural frequencies sorted ascending.

    Reference: critical-speed undamped in-vacuo analysis.
    """
    omega_spin = rpm * 2.0 * math.pi / 60.0
    K_total = rotor.K_at(rpm)
    if abs(omega_spin) < 1e-9:
        # Pure symmetric eigenvalue problem
        # Add a tiny regularization so K is positive-definite for the rigid-body
        # cases (free-free rotor); we'll filter out modes below the threshold.
        try:
            evals, evecs = la.eigh(K_total, rotor.M)
        except la.LinAlgError:
            # K possibly singular; fall back to la.eig
            evals, evecs = la.eig(K_total, rotor.M)
            evals = np.real(evals)
            evecs = np.real(evecs)
        # eigh returns real ascending; convert to (omega_d = sqrt(eval))
        results: List[EigenResult] = []
        for i in range(len(evals)):
            ev = evals[i]
            if ev <= 1e-3:
                # rigid-body / spurious mode
                continue
            omega_n = math.sqrt(ev)
            v = evecs[:, i].astype(complex)
            lam = complex(0.0, omega_n)
            results.append(_eigenresult_from_lambda(lam, v, omega_spin))
            if len(results) >= n_modes:
                break
        return results
    # Else: gyroscopic-coupled (still undamped). Reduce to the quadratic
    # problem with C = 0. Because the system is undamped per the SPEC
    # promise of this function, we pass log_dec_override=None per ADAPT-041.
    C_gyro = omega_spin * rotor.G_unit
    lambdas, vecs = solve_quadratic_eigvals(
        rotor.M, C_gyro, K_total, n_modes=n_modes
    )
    # ADAPT-040: dedupe conjugate pairs before processing.
    lambdas, vecs = _dedupe_conjugate_pairs(lambdas, vecs)
    results = []
    seen: List[float] = []
    order = np.argsort(np.abs(lambdas.imag))
    DEDUP_REL_TOL = 1.0e-3
    for idx in order:
        lam = lambdas[idx]
        if not np.isfinite(lam):
            continue
        omega_d = lam.imag
        if omega_d <= 1e-6:
            continue
        if any(
            abs(omega_d - f) <= DEDUP_REL_TOL * max(f, 1.0) for f in seen
        ):
            continue
        seen.append(omega_d)
        v = vecs[:, idx]
        results.append(
            _eigenresult_from_lambda(
                lam, v, omega_spin, log_dec_override=None
            )
        )
        if len(results) >= n_modes:
            break
    return results


def run_torsional_analysis(
    rotor_inertias: List[float],
    coupling_stiffness: List[float],
    n_modes: int = 6,
) -> List[float]:
    """Torsional eigenanalysis of a chain-of-inertias rotor.

    A lumped-parameter torsional model: N disks each with inertia J_i,
    connected by torsional springs of stiffness k_i. The eigenvalue problem
    is the symmetric K_theta phi = omega^2 J_theta phi, where J_theta is the
    diagonal inertia matrix and K_theta is the tri-diagonal stiffness matrix.

    Parameters
    ----------
    rotor_inertias : list[float]
        Diametrical inertias J_i [kg m^2].
    coupling_stiffness : list[float]
        Torsional spring constants k_i [N m/rad]. Length should be N-1.

    Returns
    -------
    list[float]
        Lowest n_modes natural frequencies in rad/s. The first frequency is
        zero (rigid-body rotation) by construction.

    Reference: torsional analysis; Vance 1988 §10.4.
    """
    N = len(rotor_inertias)
    if len(coupling_stiffness) != N - 1:
        msg = (
            f"coupling_stiffness must have length N-1 = {N-1}; "
            f"got {len(coupling_stiffness)}"
        )
        raise ValueError(msg)
    J = np.diag(rotor_inertias).astype(float)
    K = np.zeros((N, N), dtype=float)
    for i, k in enumerate(coupling_stiffness):
        K[i, i] += k
        K[i + 1, i + 1] += k
        K[i, i + 1] -= k
        K[i + 1, i] -= k
    evals = la.eigvalsh(K, J)
    omegas = np.sqrt(np.maximum(evals, 0.0))
    omegas = np.sort(omegas)
    return [float(o) for o in omegas[:n_modes]]
