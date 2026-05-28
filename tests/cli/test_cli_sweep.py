"""Tests for `cascade sweep` CLI command.

W-26 acceptance criteria:
- AC1: Command produces a valid CSV with ≥6 columns and N rows for an N-point sweep.
- AC2: Invalid --param path raises a clear error before the loop runs.
- AC3: Failed solves write a row with status=FAILED and reason, not a crash.
"""

from __future__ import annotations

import csv
import os
import pathlib
import textwrap
from datetime import datetime, timezone

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def demo_project_dir(tmp_path, monkeypatch):
    """Seed a minimal capstone-c30-microturbine project in a temp dir.

    Uses the real Capstone C30 parameters from the validation cases module so
    the solve actually converges. W-26 AC1 depends on a working project.
    """
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
        id="capstone-c30-microturbine",
        meta=ProjectMeta(
            name="Capstone C30 Microturbine",
            description="Canonical validation case",
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
                    "pressure_ratio": 4.0,
                    "efficiency_isentropic": 0.78,
                },
            ),
            ComponentRecord(
                id="burner1",
                kind="burner",
                name="B1",
                params={
                    "outlet_temperature_K": 1116.0,
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
                    "pressure_ratio": 3.535,
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
        boundary_conditions={
            "p_ambient_kpa": 101.325,
            "T_ambient_K": 288.15,
            "mass_flow_kg_s": 0.31,
        },
        settings={
            "mechanical_efficiency": 0.95,
            "generator_efficiency": 0.95,
        },
    )
    save_project(project)
    return tmp_path


# ---------------------------------------------------------------------------
# AC1: valid CSV with ≥6 columns and N rows for an N-point sweep
# ---------------------------------------------------------------------------


def test_sweep_produces_valid_csv(demo_project_dir, tmp_path):
    """W-26 AC1: sweep over compressor.pressure_ratio produces N rows, ≥6 cols."""
    from cascade.cli import main

    output_csv = tmp_path / "sweep.csv"
    ret = main(
        [
            "sweep",
            "--project",
            "capstone-c30-microturbine",
            "--param",
            "compressor.pressure_ratio",
            "--range",
            "3:7:5",
            "--output",
            str(output_csv),
        ]
    )
    assert ret == 0, f"cascade sweep returned {ret}"
    assert output_csv.exists(), "Output CSV was not created"

    with open(output_csv, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    # AC1: ≥6 columns
    assert len(fieldnames) >= 6, (
        f"Expected ≥6 columns, got {len(fieldnames)}: {fieldnames}"
    )
    # AC1: exactly N rows (5 in this case)
    assert len(rows) == 5, f"Expected 5 data rows, got {len(rows)}"
    # AC1: at least some rows should succeed (not all fail)
    ok_rows = [r for r in rows if r.get("status") == "OK"]
    assert ok_rows, (
        f"Expected at least 1 successful row in range 3:7:5 but all failed: "
        f"{[(r.get('param_value'), r.get('reason')) for r in rows]}"
    )
    # All rows must have all CSV fields (regardless of status)
    for row in rows:
        for col in ("param_value", "thermal_efficiency", "electrical_efficiency",
                    "specific_work_kJ_per_kg", "fuel_flow_kg_s",
                    "net_shaft_work_kW", "electrical_output_kW"):
            assert col in row, f"Missing column {col!r} in row: {row}"


# ---------------------------------------------------------------------------
# AC3: Failed solves write status=FAILED, no crash
# ---------------------------------------------------------------------------


def test_sweep_failed_solve_writes_failed_row(demo_project_dir, tmp_path):
    """W-26 AC3: a pressure_ratio of 0.1 should cause the solver to fail;
    the row must have status=FAILED and a reason, not a crash.
    """
    from cascade.cli import main

    output_csv = tmp_path / "sweep_fail.csv"
    # Sweep over a pathological range (sub-unity PR) — solver will fail or
    # return non-physical results. Either way we must get FAILED rows, not a crash.
    ret = main(
        [
            "sweep",
            "--project",
            "capstone-c30-microturbine",
            "--param",
            "compressor.pressure_ratio",
            "--range",
            "0.01:0.1:3",
            "--output",
            str(output_csv),
        ]
    )
    # The command must not crash regardless of solve outcome.
    assert ret == 0, f"cascade sweep crashed with return code {ret}"
    assert output_csv.exists()

    with open(output_csv, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}"
    # At least some rows should be FAILED for sub-unity PR
    failed = [r for r in rows if r.get("status") == "FAILED"]
    assert failed, (
        "Expected at least one FAILED row for sub-unity pressure_ratio, "
        f"but all rows have status={[r.get('status') for r in rows]}"
    )
    # Every FAILED row must have a non-empty reason
    for row in failed:
        assert row.get("reason"), (
            f"FAILED row has empty reason: {row}"
        )


# ---------------------------------------------------------------------------
# AC2: Invalid --param path raises clear error before the loop
# ---------------------------------------------------------------------------


def test_sweep_invalid_param_errors_before_loop(demo_project_dir, tmp_path, capsys):
    """W-26 AC2: bad --param path returns non-zero with a clear error message."""
    from cascade.cli import main

    output_csv = tmp_path / "should_not_exist.csv"
    ret = main(
        [
            "sweep",
            "--project",
            "capstone-c30-microturbine",
            "--param",
            "compressor.nonexistent_field_xyz",
            "--range",
            "3:7:5",
            "--output",
            str(output_csv),
        ]
    )
    captured = capsys.readouterr()
    assert ret != 0, "Expected non-zero return for invalid --param"
    assert "nonexistent_field_xyz" in captured.out or "Invalid" in captured.out, (
        f"Expected error message about invalid param, got: {captured.out!r}"
    )
    # The output file should not have been created (error before loop)
    assert not output_csv.exists(), "Output CSV was created despite invalid --param"
