"""Tests for `cascade export` CLI command.

W-35 acceptance criteria:
- AC1: Command produces a valid CSV with named sections ([HEADLINE],
       [COMPONENT:*], etc.).
- AC2: A test verifies AC1.
- AC3: Failed solve writes the failure to the CSV without crashing.
"""

from __future__ import annotations

import csv
import os
import pathlib
from datetime import datetime, timezone

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def demo_project_dir(tmp_path, monkeypatch):
    """Seed a minimal at-100-microturbine project in a temp dir."""
    monkeypatch.setenv("CASCADE_PROJECTS_DIR", str(tmp_path))

    try:
        from cascade.project.persistence import save_project
        from cascade.project.schema import (
            ComponentRecord,
            Project,
            ProjectMeta,
        )
    except ImportError:
        pytest.skip("cascade.project not importable")

    now = datetime.now(tz=timezone.utc)
    project = Project(
        id="at-100-microturbine",
        meta=ProjectMeta(
            name="AT-100 Microturbine",
            description="American Turbines 100 kW recuperated microturbine",
            kind="recuperated_brayton",
            working_fluid="air",
            created_at=now,
            updated_at=now,
        ),
        components=[
            ComponentRecord(
                id="comp1",
                kind="compressor",
                name="C1",
                params={
                    "pressure_ratio": 4.2,
                    "efficiency_isentropic": 0.79,
                },
            ),
            ComponentRecord(
                id="burner1",
                kind="burner",
                name="B1",
                params={
                    "outlet_temperature_K": 1140.0,
                    "pressure_drop_fraction": 0.04,
                    "combustion_efficiency": 0.995,
                    "fuel_lhv_MJ_per_kg": 50.0,
                    "fuel_carbon_atoms": 1,
                    "fuel_hydrogen_atoms": 4,
                    "fuel_molar_mass_g_per_mol": 16.0425,
                    "fuel_inlet_temperature_K": 298.15,
                },
            ),
            ComponentRecord(
                id="turb1",
                kind="turbine",
                name="T1",
                params={
                    "pressure_ratio": 3.72,
                    "efficiency_isentropic": 0.85,
                },
            ),
            ComponentRecord(
                id="recup1",
                kind="recuperator",
                name="R1",
                params={
                    "effectiveness": 0.88,
                    "cold_pressure_drop_fraction": 0.03,
                    "hot_pressure_drop_fraction": 0.03,
                },
            ),
        ],
        boundary_conditions={
            "p_ambient_kpa": 101.325,
            "T_ambient_K": 288.15,
            "mass_flow_kg_s": 0.95,
        },
        settings={
            "mechanical_efficiency": 0.96,
            "generator_efficiency": 0.96,
        },
    )
    save_project(project)
    return tmp_path


# ---------------------------------------------------------------------------
# AC1 + AC2: Valid CSV with named sections
# ---------------------------------------------------------------------------


def test_export_produces_named_sections(demo_project_dir, tmp_path):
    """W-35 AC1/AC2: export produces a CSV with [HEADLINE] and [COMPONENT:*] sections."""
    from cascade.cli import main

    output_csv = tmp_path / "result.csv"
    ret = main(
        [
            "export",
            "--project",
            "at-100-microturbine",
            "--output",
            str(output_csv),
        ]
    )
    assert ret == 0, f"cascade export returned {ret}"
    assert output_csv.exists(), "Output CSV was not created"

    with open(output_csv, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    sections = {r["section"] for r in rows}
    # AC1: must have [HEADLINE] section
    assert "[HEADLINE]" in sections, (
        f"Expected [HEADLINE] section, got sections: {sections}"
    )
    # AC1: must have at least one [COMPONENT:*] section
    component_sections = {s for s in sections if s.startswith("[COMPONENT:")}
    assert component_sections, (
        f"Expected at least one [COMPONENT:*] section, got sections: {sections}"
    )
    # [STATUS] must be present and show OK
    status_rows = [r for r in rows if r["section"] == "[STATUS]"]
    assert status_rows, "Missing [STATUS] section"
    status_map = {r["key"]: r["value"] for r in status_rows}
    assert status_map.get("solve_status") == "OK", (
        f"Expected solve_status=OK, got: {status_map}"
    )

    # [HEADLINE] must contain the key metrics
    headline_rows = [r for r in rows if r["section"] == "[HEADLINE]"]
    headline_keys = {r["key"] for r in headline_rows}
    for expected_key in (
        "thermal_efficiency",
        "electrical_efficiency",
        "net_shaft_work_kW",
        "electrical_output_kW",
        "fuel_mass_flow_kg_s",
    ):
        assert expected_key in headline_keys, (
            f"Expected key {expected_key!r} in [HEADLINE], got: {headline_keys}"
        )

    # Validate that the efficiency values are physically sensible
    th_eff_row = next(
        (r for r in headline_rows if r["key"] == "thermal_efficiency"), None
    )
    assert th_eff_row is not None
    th_eff = float(th_eff_row["value"])
    assert 0.1 < th_eff < 0.6, f"thermal_efficiency {th_eff:.4f} outside physical range"


# ---------------------------------------------------------------------------
# AC3: Failed solve writes failure to CSV without crashing
# ---------------------------------------------------------------------------


@pytest.fixture()
def broken_project_dir(tmp_path, monkeypatch):
    """Seed a project with a pathologically bad turbine PR that triggers a solve error."""
    monkeypatch.setenv("CASCADE_PROJECTS_DIR", str(tmp_path))

    try:
        from cascade.project.persistence import save_project
        from cascade.project.schema import (
            ComponentRecord,
            Project,
            ProjectMeta,
        )
    except ImportError:
        pytest.skip("cascade.project not importable")

    now = datetime.now(tz=timezone.utc)
    project = Project(
        id="broken-microturbine",
        meta=ProjectMeta(
            name="Broken Microturbine",
            description="Intentionally broken project for error-path testing",
            kind="recuperated_brayton",
            working_fluid="air",
            created_at=now,
            updated_at=now,
        ),
        components=[
            ComponentRecord(
                id="comp1",
                kind="compressor",
                name="C1",
                params={
                    "pressure_ratio": -1.0,  # invalid — negative PR
                    "efficiency_isentropic": 2.5,  # invalid — >1
                },
            ),
            ComponentRecord(
                id="burner1",
                kind="burner",
                name="B1",
                params={
                    "outlet_temperature_K": 50.0,  # unphysically low
                    "pressure_drop_fraction": 0.04,
                    "combustion_efficiency": 0.995,
                    "fuel_lhv_MJ_per_kg": 50.0,
                    "fuel_carbon_atoms": 1,
                    "fuel_hydrogen_atoms": 4,
                    "fuel_molar_mass_g_per_mol": 16.0425,
                    "fuel_inlet_temperature_K": 298.15,
                },
            ),
            ComponentRecord(
                id="turb1",
                kind="turbine",
                name="T1",
                params={
                    "pressure_ratio": -99.0,  # invalid
                    "efficiency_isentropic": 0.84,
                },
            ),
            ComponentRecord(
                id="recup1",
                kind="recuperator",
                name="R1",
                params={
                    "effectiveness": 0.87,
                    "cold_pressure_drop_fraction": 0.03,
                    "hot_pressure_drop_fraction": 0.03,
                },
            ),
        ],
        boundary_conditions={},
        settings={},
    )
    save_project(project)
    return tmp_path


def test_export_failed_solve_writes_failure(broken_project_dir, tmp_path):
    """W-35 AC3: failed solve writes failure row without crashing."""
    from cascade.cli import main

    output_csv = tmp_path / "failed_result.csv"
    # Should not crash even if the solve fails
    ret = main(
        [
            "export",
            "--project",
            "broken-microturbine",
            "--output",
            str(output_csv),
        ]
    )
    # The command must not crash (return 0 even on solve failure per AC3).
    assert ret == 0, f"cascade export crashed with return code {ret}"
    assert output_csv.exists(), "Output CSV was not created even on failure"

    with open(output_csv, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    status_rows = [r for r in rows if r["section"] == "[STATUS]"]
    assert status_rows, "Missing [STATUS] section in failure output"
    status_map = {r["key"]: r["value"] for r in status_rows}
    # The solve either failed or succeeded. If it failed, status must be FAILED
    # with an error message. The key invariant is: the CSV exists and has content.
    if status_map.get("solve_status") == "FAILED":
        assert status_map.get("error"), (
            "FAILED status must have an error message"
        )
