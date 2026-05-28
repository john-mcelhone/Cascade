"""Integration tests: seed project reproducibility and drift protection.

Mandate (Audit D):
- Each shipped seed must produce deterministic, physically-bounded outputs when
  run through the cycle solver.
- Tolerances are derived from published design intent, NOT from the current
  solver output.  If the solver drifts, these tests must fail loudly.
- No magic numbers.  All bounds come from the seed's documented target and a
  physically-justified tolerance.
- Tests isolate themselves from ~/.cascade with CASCADE_PROJECTS_DIR.

Seeds covered:
  microturbine-30kw  (Capstone C30, sourced from CapstoneC30 canonical case)
  sco2-test-loop     (prototype sCO2 Brayton; assertion based on thermodynamic
                      first-principles only — net work must be positive)
  at-100kw-prototype (AT-100; design intent = ~100 kW electrical from the
                      seed's own stated target, tolerance ±15 kW)
  aero-demonstrator  (empty canvas; solver must not crash or raise)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup — allow running from repo root or the apps/api dir
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parents[2]
for _p in (str(_REPO / "src"), str(_REPO / "apps" / "api")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_seed_as_legacy_dict(seed_fn):
    """Call a seed builder function and return the legacy-dict representation."""
    return seed_fn()


def _run_cycle_solve(project_dict: dict):
    """Run the cascade cycle solver on a legacy-dict project.

    Returns the result object from solve_cycle, or None if the project has
    no components (blank canvas).
    """
    from cascade.cycle import (
        Burner,
        Compressor,
        ConstantPressureLoss,
        NasaFluid,
        RecuperatedBraytonSpec,
        Recuperator,
        Turbine,
        solve_cycle,
    )
    from cascade.units import Composition, Port, Q

    components = project_dict.get("components", [])
    if not components:
        return None  # blank canvas — nothing to solve

    # Build a mapping from component id to component dict.
    comp_map = {c["id"]: c for c in components}

    # Extract inlet parameters.
    inlet_comp = comp_map.get("inlet", {})
    inlet_params = inlet_comp.get("params", {})

    def _q(d, key, default_val, default_unit):
        v = d.get(key)
        if v is None:
            return Q(default_val, default_unit)
        if isinstance(v, dict):
            return Q(float(v["value"]), v["unit"])
        return Q(float(v), default_unit)

    p0 = _q(inlet_params, "pressure_total", 101.325, "kPa")
    T0 = _q(inlet_params, "temperature_total", 288.15, "K")
    mdot = _q(inlet_params, "mass_flow", 1.0, "kg/s")

    inlet_port = Port(
        pressure_total=p0,
        temperature_total=T0,
        mass_flow=mdot,
        composition=Composition.air(),
    )

    # --- Compressor ---
    cc = comp_map.get("compressor", {}).get("params", {})
    pr_c = float(cc.get("pressure_ratio", 4.0))
    eta_c = float(cc.get("efficiency_isentropic", 0.78))
    compressor = Compressor(
        name="compressor",
        pressure_ratio=pr_c,
        efficiency_isentropic=eta_c,
    )

    # --- Inlet loss ---
    il = comp_map.get("inlet_loss", {}).get("params", {})
    pdrop_inlet = float(il.get("pressure_drop_fraction", 0.0)) if il else 0.0
    inlet_loss = ConstantPressureLoss(
        name="inlet_loss",
        pressure_drop_fraction=pdrop_inlet,
    )

    # --- Burner / heater ---
    bp = comp_map.get("burner", {}).get("params", {})
    T_out = _q(bp, "outlet_temperature", 1116.0, "K")
    pdrop_burner = float(bp.get("pressure_drop_fraction", 0.04))
    comb_eff = float(bp.get("combustion_efficiency", 1.0))
    fuel_lhv = _q(bp, "fuel_lhv", 50e6, "J/kg")
    fc = int(bp.get("fuel_carbon_atoms", 1))
    fh = int(bp.get("fuel_hydrogen_atoms", 4))
    fm = _q(bp, "fuel_molar_mass", 16.0425, "g/mol")
    air_standard = bool(bp.get("air_standard", False))
    burner = Burner(
        name="burner",
        pressure_drop_fraction=pdrop_burner,
        combustion_efficiency=comb_eff,
        outlet_temperature=T_out,
        fuel_lhv=fuel_lhv,
        fuel_carbon_atoms=fc,
        fuel_hydrogen_atoms=fh,
        fuel_molar_mass=fm,
        air_standard=air_standard,
    )

    # --- Turbine ---
    tp = comp_map.get("turbine", {}).get("params", {})
    pr_t = float(tp.get("pressure_ratio", 3.5))
    eta_t = float(tp.get("efficiency_isentropic", 0.84))
    turbine = Turbine(
        name="turbine",
        pressure_ratio=pr_t,
        efficiency_isentropic=eta_t,
    )

    # --- Recuperator (optional) ---
    rp = comp_map.get("recuperator", {}).get("params", {})
    recup = None
    if rp:
        effectiveness = float(rp.get("effectiveness", 0.85))
        pdrop_cold = float(rp.get("cold_pressure_drop_fraction", 0.03))
        pdrop_hot = float(rp.get("hot_pressure_drop_fraction", 0.03))
        recup = Recuperator(
            name="recuperator",
            effectiveness=effectiveness,
            cold_pressure_drop_fraction=pdrop_cold,
            hot_pressure_drop_fraction=pdrop_hot,
        )

    settings = project_dict.get("settings", {})
    eta_mech = float(settings.get("mechanical_efficiency", 0.99))
    eta_gen = float(settings.get("generator_efficiency", 0.97))

    if recup is not None:
        spec = RecuperatedBraytonSpec(
            inlet_port=inlet_port,
            inlet_loss=inlet_loss,
            compressor=compressor,
            burner=burner,
            turbine=turbine,
            recuperator=recup,
            mechanical_efficiency=eta_mech,
            generator_efficiency=eta_gen,
        )
    else:
        # Simple (non-recuperated) Brayton: sCO2 test loop or open-cycle.
        from cascade.cycle import SimpleBraytonSpec

        # Detect cycle type from working fluid.
        wf = project_dict.get("working_fluid", "air")
        cycle_type = "closed" if "co2" in wf.lower() else "open"
        spec = SimpleBraytonSpec(
            inlet_port=inlet_port,
            compressor=compressor,
            burner=burner,
            turbine=turbine,
            mechanical_efficiency=eta_mech,
            generator_efficiency=eta_gen,
            cycle_type=cycle_type,
        )
    return solve_cycle(spec, fluid=NasaFluid())


# ---------------------------------------------------------------------------
# Fixture: isolated project dir
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_projects(tmp_path, monkeypatch):
    """Never touch ~/.cascade in these tests."""
    proj_dir = tmp_path / "cascade_seed_tests"
    monkeypatch.setenv("CASCADE_PROJECTS_DIR", str(proj_dir))
    proj_dir.mkdir(parents=True, exist_ok=True)
    yield proj_dir


# ---------------------------------------------------------------------------
# Seed version field
# ---------------------------------------------------------------------------


class TestSeedVersionFields:
    """Every seed project returned by seed.py must carry schema_version = 1.

    This field is the migration anchor.  A file without it cannot be
    automatically migrated and would silently produce incorrect physics
    if the schema changes.
    """

    @pytest.mark.parametrize("seed_name", [
        "_microturbine_project",
        "_sco2_project",
        "_at100_project",
        "_aero_project",
    ])
    def test_seed_has_schema_version_via_project_model(self, seed_name):
        import importlib
        seed_mod = importlib.import_module("seed")
        seed_fn = getattr(seed_mod, seed_name)
        d = seed_fn()
        from cascade.project.schema import Project, SCHEMA_VERSION

        project = Project.from_legacy_dict(d)
        assert project.meta.schema_version == SCHEMA_VERSION, (
            f"Seed '{seed_name}' produced schema_version="
            f"{project.meta.schema_version!r}, expected {SCHEMA_VERSION}. "
            f"Older files cannot be migrated."
        )

    @pytest.mark.parametrize("seed_name", [
        "_microturbine_project",
        "_sco2_project",
        "_at100_project",
        "_aero_project",
    ])
    def test_seed_has_cascade_version_in_toml(self, seed_name):
        import importlib
        seed_mod = importlib.import_module("seed")
        seed_fn = getattr(seed_mod, seed_name)
        d = seed_fn()
        from cascade.project.schema import Project
        from cascade.project.serializer import project_to_toml

        project = Project.from_legacy_dict(d)
        toml_text = project_to_toml(project)
        assert "cascade_version" in toml_text, (
            f"Seed '{seed_name}' TOML does not contain cascade_version — "
            f"drift detection will be silently broken."
        )
        assert "schema_version" in toml_text, (
            f"Seed '{seed_name}' TOML does not contain schema_version."
        )


# ---------------------------------------------------------------------------
# Capstone C30 / microturbine-30kw seed
# ---------------------------------------------------------------------------


class TestMicroturbineSeedReproducibility:
    """The microturbine-30kw seed uses CapstoneC30 canonical parameters.

    Pass-gate: solver output must match Capstone's published spec within
    the tolerances stored in CapstoneC30 itself.  These are the SAME
    tolerances used by test_cyc3_capstone_c30.py — no additional magic.
    """

    def test_solver_converges(self):
        from seed import _microturbine_project
        d = _microturbine_project()
        result = _run_cycle_solve(d)
        assert result is not None
        assert result.converged, (
            f"microturbine-30kw seed: solver did not converge. "
            f"residual={result.residual_norm:.3e}"
        )

    def test_electrical_efficiency_within_published_tolerance(self):
        """η_electrical must be within ±1.5 pt of Capstone's 26%.

        Tolerance from CapstoneC30.tolerance_eta_pt — not tuned to the
        current solver output.
        """
        import pytest
        from cascade.validation.cases.capstone_c30 import CapstoneC30
        from seed import _microturbine_project

        d = _microturbine_project()
        result = _run_cycle_solve(d)
        eta_e_pct = result.electrical_efficiency * 100.0
        target_pct = CapstoneC30.target_eta_electric * 100.0
        tol_pct = CapstoneC30.tolerance_eta_pt * 100.0

        assert eta_e_pct == pytest.approx(target_pct, abs=tol_pct), (
            f"microturbine-30kw seed: η_electrical={eta_e_pct:.2f}% "
            f"outside [{target_pct - tol_pct:.1f}%, {target_pct + tol_pct:.1f}%]. "
            f"Capstone published spec: {target_pct:.0f}%."
        )

    def test_electrical_output_within_published_tolerance(self):
        """Net electrical output within ±2.5 kW of Capstone's 28 kW.

        Tolerance from CapstoneC30.tolerance_power_kW.
        """
        import pytest
        from cascade.validation.cases.capstone_c30 import CapstoneC30
        from seed import _microturbine_project

        d = _microturbine_project()
        result = _run_cycle_solve(d)
        W_e_kW = result.electrical_output.to("kW").magnitude
        target_kW = CapstoneC30.target_power_net.to("kW").magnitude
        tol_kW = CapstoneC30.tolerance_power_kW

        assert W_e_kW == pytest.approx(target_kW, abs=tol_kW), (
            f"microturbine-30kw seed: W_electrical={W_e_kW:.1f} kW "
            f"outside [{target_kW - tol_kW:.1f}, {target_kW + tol_kW:.1f}] kW. "
            f"Capstone published spec: {target_kW:.0f} kW."
        )

    def test_parameters_match_canonical_case(self):
        """The seed's cycle parameters must equal CapstoneC30 exactly.

        If a developer 'tunes' the seed to hit a marketing number by
        changing the parameters, this test fails.  The seed must reflect
        published design intent; the solver produces what the physics says.
        """
        from cascade.validation.cases.capstone_c30 import CapstoneC30
        from seed import _microturbine_project

        d = _microturbine_project()
        comp_map = {c["id"]: c for c in d["components"]}

        cc_params = comp_map["compressor"]["params"]
        assert float(cc_params["pressure_ratio"]) == pytest.approx(
            CapstoneC30.pressure_ratio, abs=0.01
        ), "seed compressor PR diverged from CapstoneC30"

        tt_params = comp_map["turbine"]["params"]
        expected_turbine_pr = CapstoneC30.turbine_pressure_ratio()
        assert float(tt_params["pressure_ratio"]) == pytest.approx(
            expected_turbine_pr, rel=0.001
        ), "seed turbine PR diverged from CapstoneC30.turbine_pressure_ratio()"

        # TIT must match CapstoneC30.TIT
        burner_params = comp_map["burner"]["params"]
        tit = burner_params["outlet_temperature"]
        if isinstance(tit, dict):
            from cascade.units import Q
            tit_val = Q(tit["value"], tit["unit"]).to("K").magnitude
        else:
            tit_val = float(tit)
        expected_tit = CapstoneC30.TIT.to("K").magnitude
        assert tit_val == pytest.approx(expected_tit, abs=1.0), (
            f"seed TIT {tit_val:.1f} K diverged from CapstoneC30 {expected_tit:.1f} K"
        )


# ---------------------------------------------------------------------------
# sCO2 seed — first-principles only
# ---------------------------------------------------------------------------


class TestSCO2SeedReproducibility:
    """The sCO2-test-loop seed has no published reference.

    We assert first-principles constraints only:
    - Solver converges.
    - Net shaft work is positive (thermodynamic cycle produces work).
    - Thermal efficiency is in the physically plausible range (0.05–0.60
      for a simple Brayton without recuperation).

    These bounds do NOT depend on the current solver output.
    """

    def test_solver_converges(self):
        from seed import _sco2_project
        d = _sco2_project()
        result = _run_cycle_solve(d)
        assert result is not None
        assert result.converged, (
            "sCO2-test-loop seed: solver did not converge. "
            f"residual={result.residual_norm:.3e}"
        )

    def test_net_shaft_work_is_positive(self):
        from seed import _sco2_project
        d = _sco2_project()
        result = _run_cycle_solve(d)
        W_net = result.net_shaft_work.to("kW").magnitude
        assert W_net > 0, (
            f"sCO2 seed: net shaft work = {W_net:.2f} kW (must be > 0 for a "
            f"power cycle — check PR and efficiency parameters)."
        )

    def test_thermal_efficiency_physically_plausible(self):
        """Simple Brayton without recuperation: η_th between 5% and 60%.

        Lower bound: a real cycle that produces any net work.
        Upper bound: Carnot for T_cold=305 K, T_hot=873 K is ~65%;
                     a lossy real cycle cannot exceed ~60%.
        """
        from seed import _sco2_project
        d = _sco2_project()
        result = _run_cycle_solve(d)
        eta_th = result.thermal_efficiency
        assert 0.05 <= eta_th <= 0.60, (
            f"sCO2 seed: η_th = {eta_th:.4f} outside physically plausible "
            f"[0.05, 0.60] for simple Brayton (T_cold=305 K, T_hot=873 K)."
        )


# ---------------------------------------------------------------------------
# AT-100 seed — design-intent bounds
# ---------------------------------------------------------------------------


class TestAT100SeedReproducibility:
    """AT-100 seed design intent: ~100 kW electrical.

    Published target in seed.py: "sized so W_electrical lands at ≈ 100 kW".
    Tolerance: ±15 kW (15%).  This is deliberately generous because the seed
    description explicitly calls the cycle parameters "engineering placeholders".
    The tolerance ensures gross divergence (a factor-of-two error) is caught
    even if the user tunes the parameters.

    IMPORTANT: the tolerance is derived from the design intent documented in
    the seed's own description, NOT from running the solver first.
    """

    # Design-intent parameters from seed.py (stable; do NOT tune these to
    # match the solver).
    _TIT_K_EXPECTED = (1800.0 - 32.0) * 5.0 / 9.0 + 273.15  # 1255.37 K
    _PR_EXPECTED = 5.0
    _MDOT_EXPECTED = 0.625  # kg/s

    # Power target and tolerance (from design intent description in seed.py)
    _W_ELEC_TARGET_KW = 100.0
    _W_ELEC_TOL_KW = 15.0  # ±15 kW (15% of target)

    def test_solver_converges(self):
        from seed import _at100_project
        d = _at100_project()
        result = _run_cycle_solve(d)
        assert result is not None
        assert result.converged, (
            f"AT-100 seed: solver did not converge. "
            f"residual={result.residual_norm:.3e}"
        )

    def test_electrical_output_near_100kw(self):
        """W_electrical must be within ±15 kW of the 100 kW design intent.

        This assertion is derived from the seed description's stated design
        intent ('sized so W_electrical lands at ≈ 100 kW'), NOT from
        running the solver first.  If the solver output drifts outside
        [85, 115] kW, the seed parameters are broken.
        """
        import pytest
        from seed import _at100_project

        d = _at100_project()
        result = _run_cycle_solve(d)
        W_e_kW = result.electrical_output.to("kW").magnitude

        assert W_e_kW == pytest.approx(
            self._W_ELEC_TARGET_KW, abs=self._W_ELEC_TOL_KW
        ), (
            f"AT-100 seed: W_electrical = {W_e_kW:.1f} kW outside "
            f"[{self._W_ELEC_TARGET_KW - self._W_ELEC_TOL_KW:.0f}, "
            f"{self._W_ELEC_TARGET_KW + self._W_ELEC_TOL_KW:.0f}] kW. "
            f"Seed description claims ≈ 100 kW — either the seed parameters "
            f"were tuned to a wrong value, or the solver regressed."
        )

    def test_tit_matches_combustor_spec(self):
        """TIT in the seed must equal 1800 °F = 1255.37 K (MVP target).

        This is the combustor design specification from the seed docstring.
        If someone changes m_dot or other parameters to 'tune' the output,
        the TIT must stay at 1255.37 K.
        """
        import pytest
        from seed import _at100_project

        d = _at100_project()
        comp_map = {c["id"]: c for c in d["components"]}
        burner_params = comp_map["burner"]["params"]
        tit = burner_params["outlet_temperature"]
        if isinstance(tit, dict):
            from cascade.units import Q
            tit_val = Q(tit["value"], tit["unit"]).to("K").magnitude
        else:
            tit_val = float(tit)

        assert tit_val == pytest.approx(self._TIT_K_EXPECTED, abs=0.5), (
            f"AT-100 seed TIT = {tit_val:.2f} K, expected "
            f"{self._TIT_K_EXPECTED:.2f} K (1800 °F). "
            f"The combustor spec is fixed; tuning TIT to hit a power target "
            f"is a data-provenance defect."
        )

    def test_seed_parameters_not_tuned_to_exact_100kw(self):
        """Guard against 'tuning' the seed so solver output is exactly 100 kW.

        If W_electrical is within 0.1 kW of the target AND the mass flow
        is a round number (e.g. exactly 0.625), that's suspicious.
        This test checks that we haven't hardcoded the result by verifying
        that the mass flow is not an implausibly exact value tuned to a target.

        A mass flow set to more decimal places than the natural engineering
        precision (3 sig-figs for a prototype) is a red flag.
        """
        from seed import _at100_project
        import math

        d = _at100_project()
        comp_map = {c["id"]: c for c in d["components"]}
        inlet_params = comp_map["inlet"]["params"]
        mdot = inlet_params.get("mass_flow", {})
        if isinstance(mdot, dict):
            mdot_val = float(mdot["value"])
        else:
            mdot_val = float(mdot)

        # The m_dot in the seed is 0.625 kg/s — an engineering round number.
        # We assert it has no more than 4 significant figures (i.e., not tuned
        # to 0.6251234 to make the output exactly 100.000 kW).
        # Round to 4 sig figs and compare; large deviation = suspiciously tuned.
        significant_digits = 4
        rounded = round(mdot_val, significant_digits)
        assert abs(mdot_val - rounded) < 1e-6, (
            f"AT-100 seed mass flow {mdot_val} has more than {significant_digits} "
            f"significant figures — this may indicate the value was tuned to "
            f"hit an exact output target (data-provenance defect)."
        )


# ---------------------------------------------------------------------------
# Aero demonstrator — blank canvas must not crash
# ---------------------------------------------------------------------------


class TestAeroDemonstratorSeed:
    def test_blank_canvas_returns_none_gracefully(self):
        """An empty project has no components; the solver must not be called."""
        from seed import _aero_project
        d = _aero_project()
        result = _run_cycle_solve(d)
        assert result is None, (
            "aero-demonstrator (blank canvas) should return None — "
            f"unexpected result: {result}"
        )

    def test_blank_canvas_has_no_components(self):
        from seed import _aero_project
        d = _aero_project()
        assert d["components"] == [], "aero-demonstrator must have no components"
        assert d["edges"] == [], "aero-demonstrator must have no edges"


# ---------------------------------------------------------------------------
# Seed TOML round-trip stability (drift protection)
# ---------------------------------------------------------------------------


class TestSeedDriftProtection:
    """If the solver changes so that a seed's output shifts materially,
    the tests above fail loudly.

    These tests additionally verify that the TOML representation of each
    seed is stable across serialise -> parse -> serialise cycles — a
    condition for git-diffability.
    """

    @pytest.mark.parametrize("seed_name,project_id", [
        ("_microturbine_project", "microturbine-30kw"),
        ("_sco2_project", "sco2-test-loop"),
        ("_at100_project", "at-100kw-prototype"),
        ("_aero_project", "aero-demonstrator"),
    ])
    def test_toml_round_trip_stable(self, seed_name, project_id):
        import importlib
        seed_mod = importlib.import_module("seed")
        seed_fn = getattr(seed_mod, seed_name)
        d = seed_fn()
        from cascade.project.schema import Project
        from cascade.project.serializer import project_from_toml, project_to_toml

        project = Project.from_legacy_dict(d)
        s1 = project_to_toml(project)
        parsed = project_from_toml(s1)
        s2 = project_to_toml(parsed)

        assert s1 == s2, (
            f"Seed '{seed_name}' TOML round-trip is not stable — "
            f"serialise -> parse -> serialise produced a diff. "
            f"This means on-disk files will drift on each save."
        )

    @pytest.mark.parametrize("seed_name,project_id", [
        ("_microturbine_project", "microturbine-30kw"),
        ("_sco2_project", "sco2-test-loop"),
        ("_at100_project", "at-100kw-prototype"),
        ("_aero_project", "aero-demonstrator"),
    ])
    def test_seed_id_matches_expected(self, seed_name, project_id):
        import importlib
        seed_mod = importlib.import_module("seed")
        seed_fn = getattr(seed_mod, seed_name)
        d = seed_fn()
        assert d["id"] == project_id, (
            f"Seed '{seed_name}' has id={d['id']!r}, "
            f"expected {project_id!r}. Changing a seed ID is a breaking "
            f"change for any user who has that project on disk."
        )


# ---------------------------------------------------------------------------
# Migration: legacy .plenum.toml / pre-schema_version files
# ---------------------------------------------------------------------------


class TestLegacyProjectMigration:
    """Verify that legacy project files (pre-schema_version) load cleanly.

    A legacy file is one that pre-dates the [meta] section — all top-level
    fields, no schema_version.  The serialiser's `project_from_toml` must
    hoist these fields into [meta] and not raise.
    """

    def test_legacy_file_without_meta_section_loads(self):
        """A file with top-level name/kind (no [meta]) loads into a valid Project."""
        from cascade.project.serializer import project_from_toml

        legacy_toml = (
            'id = "legacy-001"\n'
            'name = "Legacy Project"\n'
            'kind = "microturbine"\n'
            'working_fluid = "air"\n'
            'created_at = "2025-01-01T00:00:00Z"\n'
            'updated_at = "2025-01-01T00:00:00Z"\n'
            '\n'
            '[boundary_conditions]\n'
            '\n'
            '[settings]\n'
            'mechanical_efficiency = 0.99\n'
        )
        project = project_from_toml(legacy_toml)
        assert project.id == "legacy-001"
        assert project.meta.name == "Legacy Project"
        assert project.meta.kind == "microturbine"
        # schema_version should be set to the current version
        from cascade.project.schema import SCHEMA_VERSION
        assert project.meta.schema_version == SCHEMA_VERSION, (
            f"Legacy file migration must set schema_version to {SCHEMA_VERSION}, "
            f"got {project.meta.schema_version}"
        )

    def test_legacy_file_without_schema_version_loads(self):
        """A file that has [meta] but no schema_version loads with default version."""
        from cascade.project.serializer import project_from_toml
        from cascade.project.schema import SCHEMA_VERSION

        legacy_toml = (
            'id = "legacy-002"\n'
            '\n'
            '[meta]\n'
            'name = "Legacy With Meta"\n'
            'kind = "microturbine"\n'
            'working_fluid = "air"\n'
            'created_at = "2025-06-01T12:00:00Z"\n'
            'updated_at = "2025-06-01T12:00:00Z"\n'
            '\n'
            '[boundary_conditions]\n'
            '[settings]\n'
        )
        project = project_from_toml(legacy_toml)
        assert project.id == "legacy-002"
        # schema_version was not in the file; from_legacy_dict sets it to SCHEMA_VERSION.
        assert project.meta.schema_version == SCHEMA_VERSION

    def test_corrupted_toml_raises_clearly(self):
        """Corrupted TOML must raise an error, not return a partial project."""
        from cascade.project.serializer import project_from_toml

        with pytest.raises(Exception) as exc_info:
            project_from_toml("id = 'x'\n[meta\nname = 'broken'")
        assert str(exc_info.value).strip() != ""

    def test_missing_id_raises_value_error(self):
        from cascade.project.serializer import project_from_toml

        with pytest.raises(ValueError, match="id"):
            project_from_toml("[meta]\nname = 'nameless'\n")

    def test_legacy_dict_round_trip(self):
        """from_legacy_dict -> to_legacy_dict round-trips without loss."""
        from cascade.project.schema import Project
        from cascade.project.serializer import project_from_toml, project_to_toml
        from seed import _microturbine_project

        d = _microturbine_project()
        p = Project.from_legacy_dict(d)
        d2 = p.to_legacy_dict()
        p2 = Project.from_legacy_dict(d2)

        assert project_to_toml(p) == project_to_toml(p2), (
            "from_legacy_dict -> to_legacy_dict round-trip produced a TOML diff"
        )
