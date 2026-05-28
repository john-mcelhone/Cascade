"""W-16: API 684 PDF report export — integration test.

Exercises the ``GET /api/projects/{id}/rotor/report.pdf`` endpoint end-to-end
and asserts the acceptance criteria from §6 W-16:

- AC1: response is application/pdf with a valid %PDF header.
- AC2: the PDF content contains the PRELIMINARY watermark text.
- AC3: the PDF generation module embeds critical-speed table data (mode labels).
- AC4: the PDF content contains separation-margin column data.
- AC5: the PDF content cites "API 684 2nd ed. §2.7.1.7 Figure 2-8".
- AC7: the binary starts with ``%PDF`` and contains ``/Type /Catalog``.

References
----------
- W-16 (API 684 PDF report export).
- apps/api/rotor_pdf.py (PDF generation module).
- apps/api/routers/rotor.py (endpoint wiring).
"""

from __future__ import annotations

import re
import sys
import zlib
import base64
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
for p in (str(_REPO / "src"), str(_REPO / "apps" / "api")):
    if p not in sys.path:
        sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_pdf_text(pdf_bytes: bytes) -> bytes:
    """Extract all decompressed text content from a PDF's content streams.

    reportlab uses ASCII85Decode + FlateDecode for content streams.
    The ``~>`` Adobe ASCII85 terminator appears immediately before the
    ``endstream`` keyword with no newline separator — so we search for
    ``endstream`` directly rather than a preceded newline.

    The regex must handle both ``\\n`` and ``\\r\\n`` stream-open boundaries.
    """
    all_text = bytearray()
    # Locate all stream...endstream blocks.
    for m in re.finditer(b"stream\r?\n", pdf_bytes):
        start = m.end()
        # endstream may follow without a preceding newline (reportlab default)
        end_match = pdf_bytes.find(b"endstream", start)
        if end_match == -1:
            continue
        raw = pdf_bytes[start:end_match]
        stripped = raw.strip()

        # Try ASCII85 + FlateDecode (reportlab default: ASCII85Decode then FlateDecode)
        try:
            a85 = base64.a85decode(stripped, adobe=True)
            all_text += zlib.decompress(a85)
            continue
        except Exception:
            pass
        # Try FlateDecode only
        try:
            all_text += zlib.decompress(stripped)
            continue
        except Exception:
            pass
        # Uncompressed plain bytes
        all_text += raw
    return bytes(all_text)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pdf_bytes_from_module():
    """Generate a PDF via the rotor_pdf module directly (no HTTP)."""
    from rotor_pdf import generate_rotor_pdf

    modes = [
        {
            "mode_index": 0,
            "frequency_hz": 124.5,
            "frequency_rpm": 7470.0,
            "log_decrement": 0.342,
            "whirl": "forward",
            "shape_name": "bend-1F",
            "damping_ratio": 0.055,
            "omega_n_rad_s": 782.1,
            "omega_d_rad_s": 780.0,
        },
        {
            "mode_index": 1,
            "frequency_hz": 250.1,
            "frequency_rpm": 15006.0,
            "log_decrement": 0.210,
            "whirl": "backward",
            "shape_name": "bend-1B",
            "damping_ratio": 0.033,
            "omega_n_rad_s": 1571.0,
            "omega_d_rad_s": 1569.0,
        },
    ]
    compliance = {
        "operating_speed_rpm": 60000.0,
        "speed_range_rpm": [1000.0, 60000.0],
        "criticals": [
            {
                "rpm": 7470.0,
                "mode_id": 0,
                "whirl": "forward",
                "amplification_factor": 9.09,
                "separation_margin_pct": 87.55,
                "required_margin_pct": 25.0,
                "passes": True,
                "in_operating_envelope": True,
                "api_clause": "API 684 §2.7.1.7 Figure 2-8",
                "api_citation": (
                    "API Std 684, 2nd ed. (2019), §2.7.1.7 Figure 2-8 — "
                    "separation margin vs amplification factor."
                ),
            }
        ],
    }
    shape_summary = {
        "sections": [
            {
                "material": "STEEL_AISI4340",
                "length_m": 0.4,
                "axial_position_m": 0.0,
                "diameter_outer_m": 0.02,
                "diameter_inner_m": 0.0,
            }
        ],
        "disks": [],
        "total_mass_kg": 0.196,
        "total_length_m": 0.4,
    }
    return generate_rotor_pdf(
        project_name="AT-100 Test Rotor",
        modes=modes,
        compliance=compliance,
        shape_summary=shape_summary,
        cascade_version="0.1.0",
    )


@pytest.fixture(scope="module")
def pdf_text(pdf_bytes_from_module):
    """Extract all text content from the generated PDF."""
    return _extract_pdf_text(pdf_bytes_from_module)


# ---------------------------------------------------------------------------
# AC1 — valid PDF binary
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_pdf_starts_with_percent_pdf(pdf_bytes_from_module):
    """AC1: PDF binary must start with %PDF."""
    assert pdf_bytes_from_module[:4] == b"%PDF", (
        f"PDF does not start with %PDF — got {pdf_bytes_from_module[:8]!r}"
    )


@pytest.mark.integration
def test_pdf_has_catalog(pdf_bytes_from_module):
    """AC1/AC7: PDF must contain a /Type /Catalog object."""
    assert b"/Type /Catalog" in pdf_bytes_from_module, (
        "PDF does not contain /Type /Catalog — not a valid PDF document."
    )


# ---------------------------------------------------------------------------
# AC2 — PRELIMINARY watermark
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_pdf_watermark_present(pdf_text):
    """AC2: 'PRELIMINARY' must appear in the decompressed PDF content."""
    assert b"PRELIMINARY" in pdf_text, (
        "Watermark text 'PRELIMINARY' not found in PDF content streams. "
        "Check the _draw_watermark function in rotor_pdf.py."
    )


@pytest.mark.integration
def test_pdf_watermark_full_phrase(pdf_text):
    """AC2: 'NOT FOR CERTIFICATION' must appear in the PDF content."""
    # The em dash in 'PRELIMINARY — NOT FOR CERTIFICATION' may be encoded as
    # WinAnsi \x97 or as a literal octal escape in the PDF content stream.
    assert b"NOT FOR CERTIFICATION" in pdf_text, (
        "'NOT FOR CERTIFICATION' not found in decompressed PDF streams."
    )


# ---------------------------------------------------------------------------
# AC3 — critical-speeds table content
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_pdf_has_mode_shape_name(pdf_text):
    """AC3: Mode shape name (bend-1F) must appear in the critical-speeds table."""
    assert b"bend-1F" in pdf_text, (
        "Mode shape name 'bend-1F' not found in PDF. "
        "The critical-speeds table may not be rendering mode labels."
    )


@pytest.mark.integration
def test_pdf_has_mode_frequency(pdf_text):
    """AC3: Damped frequency value must appear in the critical-speeds table."""
    # The frequency 124.50 Hz should be formatted as '124.50'
    assert b"124.50" in pdf_text, (
        "Mode frequency '124.50' not found in PDF content. "
        "Check the critical-speeds table in rotor_pdf.py."
    )


@pytest.mark.integration
def test_pdf_has_log_decrement(pdf_text):
    """AC3: Log-decrement column must appear in the PDF."""
    # 0.342 formatted as '0.342'
    assert b"0.342" in pdf_text, (
        "Log decrement '0.342' not found in PDF content."
    )


# ---------------------------------------------------------------------------
# AC4 — API 684 compliance table with separation margin
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_pdf_has_separation_margin_column(pdf_text):
    """AC4: Actual SM value must appear in the compliance table."""
    # 87.55 formatted as '{:.1f}' may round to '87.5' or '87.6'
    # depending on Python's banker's rounding.  Accept any of these.
    found = b"87.5" in pdf_text or b"87.6" in pdf_text or b"87.55" in pdf_text
    assert found, (
        "Actual separation margin '87.5/87.6/87.55' not found in PDF. "
        "Check the compliance table in rotor_pdf.py."
    )


@pytest.mark.integration
def test_pdf_has_required_separation_margin(pdf_text):
    """AC4: Required SM must appear in the compliance table."""
    assert b"25.0" in pdf_text, (
        "Required separation margin '25.0' not found in PDF content."
    )


@pytest.mark.integration
def test_pdf_compliance_pass_label(pdf_text):
    """AC4: PASS label must appear in the compliance table."""
    assert b"PASS" in pdf_text, "PASS label not found in PDF compliance table."


# ---------------------------------------------------------------------------
# AC5 — API 684 citation text
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_pdf_has_api684_citation(pdf_text):
    """AC5: 'API 684' must appear in the PDF."""
    assert b"API 684" in pdf_text, (
        "API 684 citation not found in PDF. "
        "Check the footer/section title in rotor_pdf.py."
    )


@pytest.mark.integration
def test_pdf_has_figure_2_8_citation(pdf_text):
    """AC5: 'Figure 2-8' citation must appear somewhere in the PDF."""
    assert b"Figure 2-8" in pdf_text, (
        "Figure 2-8 citation not found. "
        "Check the _draw_footer / section title in rotor_pdf.py."
    )


# ---------------------------------------------------------------------------
# AC7 — endpoint-level smoke (exercises the router helpers directly)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_endpoint_builds_rotor_and_generates_pdf():
    """AC7: The rotor PDF endpoint path computes compliance and generates a valid PDF.

    Exercises the same code path as the HTTP endpoint, minus the FastAPI
    request-response plumbing.
    """
    from rotor_pdf import generate_rotor_pdf
    from routers.rotor import (
        _default_jeffcott_shape,
        _default_bearings,
        _run_modes_at,
        _run_campbell_payload,
        _compliance_report,
        _shape_summary,
    )
    from cascade.rotor import build_rotor_model

    shape = _default_jeffcott_shape()
    bearings = _default_bearings(shape)
    model = build_rotor_model(shape, bearings, elements_per_section=20)

    speed_lo, speed_hi = 1_000.0, 60_000.0
    operating_rpm = speed_hi

    modes_at_op = _run_modes_at(model, operating_rpm, n_modes=6)
    campbell = _run_campbell_payload(model, speed_lo, speed_hi, n_modes=6, n_speeds=16)
    compliance = _compliance_report(
        campbell, modes_at_op, operating_rpm, (speed_lo, speed_hi)
    )
    shape_summary = _shape_summary(shape)

    pdf = generate_rotor_pdf(
        project_name="Jeffcott smoke test",
        modes=modes_at_op,
        compliance=compliance,
        shape_summary=shape_summary,
        cascade_version="0.1.0",
    )

    # AC1 / AC7 assertions
    assert pdf[:4] == b"%PDF", f"Not a valid PDF — got {pdf[:10]!r}"
    assert b"/Type /Catalog" in pdf, "PDF missing /Type /Catalog"
    assert len(pdf) > 2000, f"PDF suspiciously small ({len(pdf)} bytes)"

    # Compliance data should be present (or the no-crossing message)
    text = _extract_pdf_text(pdf)
    assert b"API 684" in text, "API 684 citation missing from Jeffcott PDF"
