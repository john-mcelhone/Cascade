"""Public validation report data.

Parses `VALIDATION_REPORT.md` into structured `ValidationCase` records
so the public `/docs/validation` page can render them cleanly.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from fastapi import APIRouter

from models import ValidationCase


router = APIRouter(prefix="/api/validation", tags=["validation"])


# Find VALIDATION_REPORT.md by walking up from this file's directory.
def _find_report() -> Path:
    here = Path(__file__).resolve()
    for parent in (here.parent, *here.parents):
        candidate = parent / "VALIDATION_REPORT.md"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("VALIDATION_REPORT.md not found")


_TABLE_HEADER_RE = re.compile(r"^\|\s*Case\s*\|", re.IGNORECASE)
_SECTION_RE = re.compile(r"^###\s+(.+)")


def _parse_cases() -> List[ValidationCase]:
    try:
        path = _find_report()
    except FileNotFoundError:
        return []

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    cases: List[ValidationCase] = []
    section = ""
    in_table = False
    sep_seen = False

    for line in lines:
        sec = _SECTION_RE.match(line)
        if sec is not None:
            section = sec.group(1).strip()
            in_table = False
            sep_seen = False
            continue
        if _TABLE_HEADER_RE.match(line):
            in_table = True
            sep_seen = False
            continue
        if in_table:
            # Markdown table separator row e.g. |---|---|
            if not sep_seen and re.match(r"^\|\s*-+", line):
                sep_seen = True
                continue
            if not line.startswith("|"):
                in_table = False
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 5:
                continue
            case_id, source, tol, result, status_label = cells[:5]
            if not case_id or case_id.lower() == "case":
                continue
            cases.append(
                ValidationCase(
                    id=case_id,
                    source=source,
                    tolerance=tol,
                    result=result,
                    status=status_label,
                    category=section,
                )
            )

    return cases


@router.get("/cases", response_model=List[ValidationCase])
def list_validation_cases() -> List[ValidationCase]:
    return _parse_cases()
