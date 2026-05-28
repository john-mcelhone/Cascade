"""Closed-form first-principles tests for beam FEM and torsional analysis.

These tests are generated entirely from analytical formulas; no benchmark
database is needed and no constants can be tuned to a single case.

Multiple shaft geometries and torsional configurations are swept so that any
systematic error in dimensional conversion (diameter vs. radius, mm vs. m,
etc.) would produce a consistent offset across the cases.

Physical references:
- Euler-Bernoulli beam:  omega_n = (n*pi/L)^2 * sqrt(EI/(rho*A))
  for a simply-supported beam (n=1,2,...).
  Source: Rao 2011 §8.4; Blevins 1979 Table 8-1.

- Timoshenko correction: For slender beams (L/D >> 10) the Timoshenko
  frequency converges to the Euler-Bernoulli result within ~1% at low modes.
  We use L/D = 50 to ensure the Timoshenko model is in the slender limit.

- Two-inertia torsional: omega_1 = sqrt(K_theta * (I1 + I2) / (I1*I2))
  where K_theta = G*J/L, J = pi*r^4/2 (polar moment using radius).
  Source: Vance 1988 §10.4; Den Hartog 1956 §5.5.

- Cantilever beam (clamped-free):  omega_n = beta_n^2 * sqrt(EI/(rho*A*L^4))
  with beta_1 = 1.8751, beta_2 = 4.6941 (first two eigenvalues).
  Source: Blevins 1979 Table 8-1.
"""

from __future__ import annotations

import math

import pytest

from cascade.rotor import LinearBearing, build_rotor_model, run_lateral_analysis
from cascade.rotor.eigenanalysis import run_torsional_analysis
from cascade.units import LumpedDisk, Q, RotorSection, RotorShape

pytestmark = pytest.mark.validation

# ===========================================================================
# Material constants (room temperature)
# ===========================================================================

# AISI 4340 at 293 K (registry-sourced values also used in beam_fem.py defaults)
E_STEEL_PA = 2.0e11       # Pa
NU_STEEL = 0.29
RHO_STEEL = 7850.0        # kg/m^3
G_STEEL_PA = E_STEEL_PA / (2.0 * (1.0 + NU_STEEL))   # ≈ 77.5 GPa


# ===========================================================================
# Euler-Bernoulli closed-form helper
# ===========================================================================


def _euler_bernoulli_freq_rad_s(n: int, L: float, D: float, E: float, rho: float) -> float:
    """Simply-supported Euler-Bernoulli beam natural frequency [rad/s].

    omega_n = (n*pi/L)^2 * sqrt(EI / (rho*A*L^0))
            = (n*pi)^2 / L^2 * sqrt(EI / (rho*A))

    Uses DIAMETER D, not radius r (I = pi*D^4/64, A = pi*D^2/4).
    """
    I = math.pi / 64.0 * D**4   # m^4, using diameter
    A = math.pi / 4.0 * D**2    # m^2, using diameter
    return (n * math.pi / L) ** 2 * math.sqrt(E * I / (rho * A))


def _build_simply_supported_shaft(
    length: float, diameter: float, n_elements: int = 40
) -> object:
    """Build a shaft with very stiff bearings at both ends (≈ simply-supported BC).

    K_b = 1e10 N/m gives essentially rigid supports for any shaft with
    realistic E and I.
    """
    sec = RotorSection(
        diameter_outer=Q(diameter, "m"), diameter_inner=Q(0.0, "m"),
        length=Q(length, "m"), density=Q(RHO_STEEL, "kg/m^3"),
        axial_position=Q(0.0, "m"), material="AISI4340",
    )
    shape = RotorShape(sections=[sec], disks=[])
    K_b = 1.0e10  # very stiff → simply-supported BC
    brg1 = LinearBearing("b1", Q(0.0, "m"), K_yy=Q(K_b, "N/m"), K_zz=Q(K_b, "N/m"), C_yy=Q(1000.0, "N*s/m"), C_zz=Q(1000.0, "N*s/m"))
    brg2 = LinearBearing("b2", Q(length, "m"), K_yy=Q(K_b, "N/m"), K_zz=Q(K_b, "N/m"), C_yy=Q(1000.0, "N*s/m"), C_zz=Q(1000.0, "N*s/m"))
    return build_rotor_model(shape, [brg1, brg2], elements_per_section=n_elements)


# ===========================================================================
# Simply-supported beam: family of geometries
# ===========================================================================


class TestSimplySupportedBeamFEM:
    """Timoshenko FEM vs Euler-Bernoulli analytical for simply-supported beams.

    Multiple lengths and diameters are tested. All cases use L/D >= 40 so
    Timoshenko and Euler-Bernoulli converge. Tolerance is 1% per SPEC_SHEET §12.
    """

    # (length_m, diameter_m, n_elements)
    # All cases satisfy L/D >= 40 (slender limit).
    TEST_CASES = [
        (2.0, 0.010, 40),   # L/D = 200, baseline case
        (1.0, 0.020, 40),   # L/D =  50, slightly stubbier
        (3.0, 0.015, 60),   # L/D = 200, longer shaft
        (0.5, 0.010, 30),   # L/D =  50, short shaft
        (4.0, 0.020, 80),   # L/D = 200, long and slightly thicker
    ]

    @pytest.mark.parametrize("length,diameter,n_elem", TEST_CASES)
    def test_first_mode_within_1_percent(
        self, length: float, diameter: float, n_elem: int
    ) -> None:
        """FEM first natural frequency matches Euler-Bernoulli within 1%."""
        model = _build_simply_supported_shaft(length, diameter, n_elem)
        modes = run_lateral_analysis(model, rpm=0.0, n_modes=3)
        fem_omega = modes[0].omega_d_rad_s

        analytical = _euler_bernoulli_freq_rad_s(1, length, diameter, E_STEEL_PA, RHO_STEEL)
        rel_err = abs(fem_omega - analytical) / analytical

        assert rel_err < 0.01, (
            f"Simply-supported beam L={length}m D={diameter*1000:.0f}mm: "
            f"FEM omega_n={fem_omega:.4f} rad/s, "
            f"analytical={analytical:.4f} rad/s, "
            f"error={rel_err:.4%} (tolerance 1%). "
            f"Possible dimensional inconsistency: diameter vs radius, mm vs m."
        )

    @pytest.mark.parametrize("length,diameter,n_elem", TEST_CASES)
    def test_second_mode_within_1_percent(
        self, length: float, diameter: float, n_elem: int
    ) -> None:
        """FEM second natural frequency matches Euler-Bernoulli within 1%."""
        model = _build_simply_supported_shaft(length, diameter, n_elem)
        modes = run_lateral_analysis(model, rpm=0.0, n_modes=5)
        fem_omega = modes[1].omega_d_rad_s

        analytical = _euler_bernoulli_freq_rad_s(2, length, diameter, E_STEEL_PA, RHO_STEEL)
        rel_err = abs(fem_omega - analytical) / analytical

        assert rel_err < 0.02, (
            f"Simply-supported beam L={length}m D={diameter*1000:.0f}mm mode 2: "
            f"FEM omega_n={fem_omega:.4f} rad/s, "
            f"analytical={analytical:.4f} rad/s, "
            f"error={rel_err:.4%} (tolerance 2% for mode 2)."
        )

    def test_frequency_ratio_n2_over_n1_near_4(self) -> None:
        """For an E-B simply-supported beam, omega_2 / omega_1 = 4 exactly.

        This tests that the FEM preserves the correct mode-spacing relationship.
        """
        model = _build_simply_supported_shaft(length=2.0, diameter=0.01, n_elements=60)
        modes = run_lateral_analysis(model, rpm=0.0, n_modes=5)
        ratio = modes[1].omega_d_rad_s / modes[0].omega_d_rad_s
        assert abs(ratio - 4.0) < 0.05, (
            f"omega_2/omega_1 = {ratio:.4f}; expected 4.0 for simply-supported E-B beam. "
            f"If this deviates significantly, the stiffness matrix may have a dimensional error."
        )

    def test_stiffness_scales_as_D4(self) -> None:
        """For equal-length beams, omega_1 should scale as D^2.

        E-B: omega_1 = (pi/L)^2 * sqrt(EI/(rhoA)).
        I ∝ D^4, A ∝ D^2, so omega_1 ∝ sqrt(D^4/D^2) = D.
        Wait — that's D not D^2. Let's be precise:
          omega = (pi/L)^2 * sqrt(E * pi/64 * D^4 / (rho * pi/4 * D^2 * L^0))
                = (pi/L)^2 * sqrt(E * D^2 / (rho * 16))
                = (pi^2 / (4 * L^2)) * sqrt(E/rho) * D

        So omega_1 ∝ D (NOT D^2). We test that doubling D doubles omega_1.
        """
        model_thin = _build_simply_supported_shaft(length=2.0, diameter=0.010, n_elements=40)
        model_fat = _build_simply_supported_shaft(length=2.0, diameter=0.020, n_elements=40)
        modes_thin = run_lateral_analysis(model_thin, rpm=0.0, n_modes=3)
        modes_fat = run_lateral_analysis(model_fat, rpm=0.0, n_modes=3)
        ratio_actual = modes_fat[0].omega_d_rad_s / modes_thin[0].omega_d_rad_s
        ratio_expected = 0.020 / 0.010  # = 2.0
        rel_err = abs(ratio_actual - ratio_expected) / ratio_expected
        assert rel_err < 0.02, (
            f"Doubling diameter: omega ratio = {ratio_actual:.4f}, expected {ratio_expected:.4f}. "
            f"For an E-B beam, omega_1 ∝ D. Error {rel_err:.2%} > 2%."
        )


# ===========================================================================
# Two-inertia torsional: family of configurations
# ===========================================================================


class TestTwoInertiaTorsionalAnalytical:
    """Two-inertia torsional system: omega_1 = sqrt(K_theta * (I1+I2) / (I1*I2)).

    Sweep over many (I1, I2, K_theta) triples to verify the formula.
    """

    # (I1, I2, K_theta) triples — units: kg*m^2, kg*m^2, N*m/rad
    TEST_CASES = [
        (1e-3, 1e-3, 1e6),    # symmetric, stiff coupling
        (2e-3, 1e-3, 5e5),    # 2:1 inertia ratio
        (5e-4, 5e-3, 1e5),    # 10:1 inertia ratio (captures I2-dominated limit)
        (1e-2, 1e-2, 1e7),    # heavy disks, stiff coupling
        (3e-3, 7e-3, 2e6),    # arbitrary ratios
        (1e-1, 1e-3, 1e4),    # extreme mass ratio
        (5e-4, 5e-4, 5e3),    # very soft coupling (low frequency)
        (1e-2, 5e-3, 3e7),    # stiff coupling, moderate inertias
    ]

    @pytest.mark.parametrize("I1,I2,K_theta", TEST_CASES)
    def test_first_torsional_frequency_matches_formula(
        self, I1: float, I2: float, K_theta: float
    ) -> None:
        """FEM torsional frequency matches analytical two-inertia formula exactly.

        For a two-inertia lumped torsional system with no damping, the first
        non-zero frequency is:
            omega_1 = sqrt(K_theta * (I1 + I2) / (I1 * I2))
        """
        freqs = run_torsional_analysis([I1, I2], [K_theta], n_modes=2)
        assert len(freqs) >= 2, f"Expected 2 frequencies; got {len(freqs)}"

        omega_fem = freqs[1]  # freqs[0] = 0 (rigid body)
        omega_analytical = math.sqrt(K_theta * (I1 + I2) / (I1 * I2))

        rel_err = abs(omega_fem - omega_analytical) / omega_analytical
        assert rel_err < 1e-9, (
            f"I1={I1:.2e}, I2={I2:.2e}, K_theta={K_theta:.2e}: "
            f"FEM omega_1 = {omega_fem:.6f} rad/s, "
            f"analytical = {omega_analytical:.6f} rad/s, "
            f"relative error = {rel_err:.2e}. "
            f"The torsional eigensolver should be exact for a 2x2 system."
        )

    @pytest.mark.parametrize("I1,I2,K_theta", TEST_CASES)
    def test_first_frequency_is_zero_rigid_body(
        self, I1: float, I2: float, K_theta: float
    ) -> None:
        """The first torsional frequency (rigid-body rotation) must be effectively zero.

        The rigid-body eigenvalue is exactly 0 mathematically, but floating-point
        eigvalsh leaves it at |omega_0| < 1e-3 * omega_1 (numerical noise of
        order machine-epsilon * omega_1 amplified by the condition number of K).
        We test relative to the first non-zero mode, not an absolute floor.
        """
        freqs = run_torsional_analysis([I1, I2], [K_theta], n_modes=2)
        omega_0 = freqs[0]
        omega_1 = freqs[1]
        # Rigid-body mode should be < 0.1% of the first elastic mode.
        # Even 0.1% would indicate a structural problem; numerical noise
        # is typically < 1e-10 * omega_1.
        relative_noise = omega_0 / omega_1 if omega_1 > 0 else omega_0
        assert relative_noise < 1e-3, (
            f"Rigid-body torsional frequency should be ~0; got {omega_0:.6e} rad/s "
            f"({relative_noise:.2e} x omega_1={omega_1:.4f} rad/s). "
            f"I1={I1:.2e}, I2={I2:.2e}, K_theta={K_theta:.2e}."
        )

    def test_frequency_decreases_as_inertia_increases(self) -> None:
        """Increasing both inertias by the same factor decreases omega by sqrt(factor)."""
        I_base = 1e-3
        K_theta = 1e6
        freqs_base = run_torsional_analysis([I_base, I_base], [K_theta], n_modes=2)
        freqs_4x = run_torsional_analysis([4 * I_base, 4 * I_base], [K_theta], n_modes=2)
        # omega_1 = sqrt(K*(2I)/(I*I)) = sqrt(2K/I), so 4x I gives 2x lower omega_1
        ratio = freqs_base[1] / freqs_4x[1]
        assert abs(ratio - 2.0) < 1e-9, (
            f"4x inertia should halve the frequency; ratio = {ratio:.6f}, expected 2.0."
        )

    def test_frequency_increases_as_stiffness_increases(self) -> None:
        """Multiplying K_theta by 4 doubles the torsional frequency."""
        I = 1e-3
        K_base = 1e6
        freqs_base = run_torsional_analysis([I, I], [K_base], n_modes=2)
        freqs_4K = run_torsional_analysis([I, I], [4 * K_base], n_modes=2)
        ratio = freqs_4K[1] / freqs_base[1]
        assert abs(ratio - 2.0) < 1e-9, (
            f"4x stiffness should double the frequency; ratio = {ratio:.6f}, expected 2.0."
        )


# ===========================================================================
# Three-inertia torsional: verify chain formula
# ===========================================================================


class TestThreeInertiaTorsional:
    """Three-inertia chain: verify the two non-zero modes against numerical truth.

    For a symmetric three-inertia system (I1 = I2 = I3 = I, K12 = K23 = K):
        omega_1 = 0 (rigid body)
        omega_2 = sqrt(K/I)            (asymmetric first mode)
        omega_3 = sqrt(3*K/I)          (asymmetric second mode)
    Source: Den Hartog 1956 §5.6, symmetric three-disk system.
    """

    @pytest.mark.parametrize("I,K", [
        (1e-3, 1e6),
        (5e-3, 5e5),
        (1e-2, 1e7),
        (2e-4, 1e4),
    ])
    def test_symmetric_three_inertia_chain_modes(
        self, I: float, K: float
    ) -> None:
        """Symmetric I1=I2=I3=I, K12=K23=K gives omega_2=sqrt(K/I), omega_3=sqrt(3K/I)."""
        freqs = run_torsional_analysis([I, I, I], [K, K], n_modes=3)
        omega_2_expected = math.sqrt(K / I)
        omega_3_expected = math.sqrt(3 * K / I)

        rel_err_2 = abs(freqs[1] - omega_2_expected) / omega_2_expected
        rel_err_3 = abs(freqs[2] - omega_3_expected) / omega_3_expected

        assert rel_err_2 < 1e-9, (
            f"I={I:.1e}, K={K:.1e}: omega_2={freqs[1]:.4f}, "
            f"expected {omega_2_expected:.4f}, error {rel_err_2:.2e}."
        )
        assert rel_err_3 < 1e-9, (
            f"I={I:.1e}, K={K:.1e}: omega_3={freqs[2]:.4f}, "
            f"expected {omega_3_expected:.4f}, error {rel_err_3:.2e}."
        )


# ===========================================================================
# Dimensional consistency: diameter vs. radius spot-check
# ===========================================================================


class TestDimensionalConsistency:
    """Spot-check that I and J formulas use diameter correctly, not radius.

    A systematic factor-of-2 error (treating diameter as radius) would give:
      I_wrong = pi/64 * (D/2)^4 = I_correct / 16   -> 16x lower frequency (4x)
    A factor-of-16 error in I_d vs J: omega ~ sqrt(I_d), so 2x frequency error.

    These tests provide multiple geometries; they would all fail consistently
    if the diameter/radius conversion were wrong.
    """

    def test_FEM_vs_analytical_D50mm_L2m(self) -> None:
        """50mm shaft, 2m long: FEM matches analytical formula within 1%."""
        D = 0.050  # 50 mm
        L = 2.0
        model = _build_simply_supported_shaft(L, D, n_elements=40)
        modes = run_lateral_analysis(model, rpm=0.0, n_modes=3)
        fem_omega = modes[0].omega_d_rad_s
        analytical = _euler_bernoulli_freq_rad_s(1, L, D, E_STEEL_PA, RHO_STEEL)
        rel_err = abs(fem_omega - analytical) / analytical
        assert rel_err < 0.01, (
            f"D=50mm, L=2m: FEM={fem_omega:.2f} rad/s, analytical={analytical:.2f} rad/s, "
            f"error={rel_err:.2%}. Possible diameter/radius confusion in I_d formula."
        )

    def test_FEM_vs_analytical_D20mm_L500mm(self) -> None:
        """20mm shaft, 500mm long: FEM matches analytical within 1%."""
        D = 0.020
        L = 0.50
        model = _build_simply_supported_shaft(L, D, n_elements=30)
        modes = run_lateral_analysis(model, rpm=0.0, n_modes=3)
        fem_omega = modes[0].omega_d_rad_s
        analytical = _euler_bernoulli_freq_rad_s(1, L, D, E_STEEL_PA, RHO_STEEL)
        rel_err = abs(fem_omega - analytical) / analytical
        assert rel_err < 0.01, (
            f"D=20mm, L=500mm: FEM={fem_omega:.2f} rad/s, analytical={analytical:.2f} rad/s, "
            f"error={rel_err:.2%}."
        )

    def test_FEM_vs_analytical_D5mm_L1m(self) -> None:
        """5mm shaft, 1m long: very slender, FEM should match E-B closely."""
        D = 0.005
        L = 1.0
        model = _build_simply_supported_shaft(L, D, n_elements=40)
        modes = run_lateral_analysis(model, rpm=0.0, n_modes=3)
        fem_omega = modes[0].omega_d_rad_s
        analytical = _euler_bernoulli_freq_rad_s(1, L, D, E_STEEL_PA, RHO_STEEL)
        rel_err = abs(fem_omega - analytical) / analytical
        assert rel_err < 0.01, (
            f"D=5mm, L=1m: FEM={fem_omega:.2f} rad/s, analytical={analytical:.2f} rad/s, "
            f"error={rel_err:.2%}."
        )

    def test_inertia_modulus_units_consistency(self) -> None:
        """Verify that the FEM omega is consistent with E in Pa (not GPa).

        If E were accidentally interpreted in GPa instead of Pa, the frequency
        would be sqrt(1e9) ≈ 31623 times too high. We spot-check one geometry
        against a known reasonable value.
        """
        # 10mm shaft, 2m long: analytical omega_1 ≈ 31.14 rad/s = 4.95 Hz
        D = 0.010
        L = 2.0
        model = _build_simply_supported_shaft(L, D)
        modes = run_lateral_analysis(model, rpm=0.0, n_modes=3)
        fem_omega = modes[0].omega_d_rad_s

        # Analytical: ~31.14 rad/s (confirmed by hand calculation)
        analytical = _euler_bernoulli_freq_rad_s(1, L, D, E_STEEL_PA, RHO_STEEL)
        assert 25.0 < fem_omega < 40.0, (
            f"D=10mm, L=2m: FEM omega_1 = {fem_omega:.2f} rad/s. "
            f"Expected ~{analytical:.2f} rad/s (25-40 rad/s range). "
            f"Values >> 100 rad/s suggest E is in GPa not Pa. "
            f"Values << 10 rad/s suggest E is in kPa or J is using radius not diameter."
        )
