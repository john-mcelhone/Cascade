#!/usr/bin/env python3
"""Run the independent verification suite and emit a DELIBERATELY COARSE report.

Design intent (per the project brief): the report says *which area* needs work
and *what kind of physics* is implicated, but never the exact failing test, the
asserted value, or the assertion diff. This prevents whoever fixes the software
from over-fitting to the tests — they must fix the underlying physics/engineering
issue, not chase a number.

Usage:
    python independent_verification/run_report.py
Writes:
    independent_verification/REPORT.md            (coarse, committed)
    independent_verification/.last_results.json   (detail, git-ignored, private)
"""

from __future__ import annotations

import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = HERE / "tests"
INI = HERE / "pytest.ini"
RESULTS = HERE / ".last_results.json"
REPORT = HERE / "REPORT.md"

# filename stem -> (subsystem label, generic remediation theme)
SUBSYSTEMS: dict[str, tuple[str, str]] = {
    "test_cycle_thermo": (
        "Cycle thermodynamics (0D Brayton)",
        "One or more cycle results disagree with closed-form thermodynamics or "
        "first-law accounting. Revisit how efficiencies and energy flows are "
        "defined and reconciled.",
    ),
    "test_meanline_radial": (
        "Mean-line: radial inflow turbine",
        "One or more derived radial-turbine performance metrics fall outside the "
        "physically-consistent range. Revisit the efficiency definitions "
        "(total-to-total, total-to-static, polytropic) and their consistency with "
        "the computed enthalpy and pressure changes.",
    ),
    "test_meanline_centrifugal": (
        "Mean-line: centrifugal compressor",
        "One or more derived centrifugal-compressor metrics fall outside the "
        "physically-consistent range. Revisit efficiency definitions, slip, and "
        "off-design trends.",
    ),
    "test_slip_factors": (
        "Slip-factor correlations",
        "Slip-factor behaviour at (and below) the edge of its documented validity "
        "envelope is not fully safe. Review how out-of-envelope blade counts are "
        "handled against SPEC_SHEET §13 / §15 (clip to a physical value WITH a "
        "warning; never silently extrapolate to a degenerate result).",
    ),
    "test_rotordynamics": (
        "Rotor dynamics (beam-FEM)",
        "A modal / critical-speed / forced-response result departs from its "
        "analytical reference. Revisit the FEM assembly, eigen-extraction, and "
        "gyroscopic / whirl handling.",
    ),
    "test_journal_bearing": (
        "Journal bearing (hydrodynamic)",
        "A bearing coefficient or equilibrium result departs from expected "
        "hydrodynamic behaviour.",
    ),
    "test_optimization": (
        "Optimization (SLSQP / CMA-ES / NSGA-II)",
        "An optimizer failed to reach a known optimum or a solution-quality metric "
        "is off.",
    ),
    "test_sobol_explore": (
        "Design-space sampling (Sobol')",
        "A sampling result is non-deterministic, out of bounds, or poorly "
        "distributed.",
    ),
    "test_units_quantities": (
        "Units engine",
        "A unit conversion or dimensional guard did not behave exactly.",
    ),
    "test_materials_bounds": (
        "Materials database",
        "A stored material property falls outside its known physical bounds.",
    ),
}


def _subsystem_of(nodeid: str) -> str:
    # nodeid like "tests/test_cycle_thermo.py::test_x[param]"
    stem = Path(nodeid.split("::", 1)[0]).stem
    return stem


def main() -> int:
    # Run the suite. --tb=no keeps even the operator's console coarse.
    subprocess.run(
        [sys.executable, "-m", "pytest", str(TESTS), "-c", str(INI),
         "-p", "no:cacheprovider", "--tb=no", "-q"],
        cwd=str(HERE), check=False,
    )

    if not RESULTS.exists():
        print("ERROR: no results file produced.", file=sys.stderr)
        return 2
    outcomes: dict[str, str] = json.loads(RESULTS.read_text())

    # Aggregate by subsystem. passed / failed / review(=error|skipped)
    agg: dict[str, dict[str, int]] = {}
    for nodeid, outcome in outcomes.items():
        stem = _subsystem_of(nodeid)
        bucket = agg.setdefault(stem, {"passed": 0, "failed": 0, "review": 0})
        if outcome == "passed":
            bucket["passed"] += 1
        elif outcome == "failed":
            bucket["failed"] += 1
        else:  # error / skipped
            bucket["review"] += 1

    total = sum(sum(b.values()) for b in agg.values())
    passed = sum(b["passed"] for b in agg.values())
    failed = sum(b["failed"] for b in agg.values())
    review = sum(b["review"] for b in agg.values())

    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = []
    lines.append("# Independent Verification Report")
    lines.append("")
    lines.append(f"_Generated: {stamp}_")
    lines.append("")
    lines.append(
        "This report is intentionally coarse. It identifies the engineering area "
        "and the kind of physics implicated, but not the specific failing check, "
        "expected value, or assertion. Fix the underlying behaviour, not the test."
    )
    lines.append("")
    verdict = "ALL CHECKS PASS" if (failed == 0 and review == 0) else (
        "ATTENTION REQUIRED" if failed else "REVIEW ITEMS PRESENT")
    lines.append(f"## Headline: {verdict}")
    lines.append("")
    lines.append(f"- Total checks: **{total}**")
    lines.append(f"- Passed: **{passed}**")
    lines.append(f"- Failed (outside accepted bounds): **{failed}**")
    lines.append(f"- Needs review (could not run / skipped): **{review}**")
    lines.append("")
    lines.append("## By subsystem")
    lines.append("")
    lines.append("| Subsystem | Passed | Failed | Review |")
    lines.append("|-----------|-------:|-------:|-------:|")
    for stem in sorted(agg):
        label = SUBSYSTEMS.get(stem, (stem, ""))[0]
        b = agg[stem]
        lines.append(f"| {label} | {b['passed']} | {b['failed']} | {b['review']} |")
    lines.append("")

    flagged = [s for s in sorted(agg) if agg[s]["failed"] or agg[s]["review"]]
    if flagged:
        lines.append("## Areas to investigate")
        lines.append("")
        for stem in flagged:
            label, theme = SUBSYSTEMS.get(stem, (stem, "Investigate this area."))
            lines.append(f"- **{label}** — {theme}")
        lines.append("")
    else:
        lines.append("All implemented-subsystem checks are within their known "
                     "physical and published bounds. No action required.")
        lines.append("")

    REPORT.write_text("\n".join(lines))

    # Coarse console echo
    print("\n" + "=" * 60)
    print(f"INDEPENDENT VERIFICATION — {verdict}")
    print(f"  total={total}  passed={passed}  failed={failed}  review={review}")
    for stem in sorted(agg):
        label = SUBSYSTEMS.get(stem, (stem, ""))[0]
        b = agg[stem]
        flag = "  <-- investigate" if (b["failed"] or b["review"]) else ""
        print(f"  - {label:42s} {b['passed']:>3}P {b['failed']:>3}F {b['review']:>3}R{flag}")
    print("=" * 60)
    print(f"Report written to {REPORT.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
