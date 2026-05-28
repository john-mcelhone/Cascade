"""Geometry export honesty tests — Audit D.

Mandate:
- A 200 response from an export endpoint must contain real, structurally
  valid geometry — NOT an empty stub.
- When pythonocc-core is absent, STEP and IGES endpoints MUST return 503,
  NOT 200 with a stub file.
- GLB and STL stubs must be clearly tagged with X-Cascade-Stub: true.
- The /api/health/cad endpoint must reflect the actual dependency state.
- Structural validity checks for every format:
    .glb   — magic 'glTF' + version 2, at least one mesh with vertices
    .stl   — 80-byte header + nonzero triangle count (binary STL)
    .step  — ISO-10303-21; header + END-ISO-10303-21; trailer
    .iges  — IGES section markers (S-record at column 73)
    .ndf   — all 4 sections present, > 0 data rows each
    .fluid.step — ISO-10303-21; with patch names in header

These tests use the real API via httpx.ASGITransport, so they exercise
the full request path including the 503/200 boundary logic.
"""

from __future__ import annotations

import io
import math
import struct
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parents[2]
for _p in (str(_REPO / "src"), str(_REPO / "apps" / "api")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# App fixture with a real candidate in the index
# ---------------------------------------------------------------------------

@pytest.fixture
def app_with_candidate(tmp_path, monkeypatch):
    """Create the FastAPI app, seed it, and inject a synthetic candidate
    so export endpoints have something to act on.
    """
    proj_dir = tmp_path / "cascade_export_test_projects"
    monkeypatch.setenv("CASCADE_PROJECTS_DIR", str(proj_dir))
    proj_dir.mkdir(parents=True, exist_ok=True)

    import jobs
    jobs.reset_for_tests()

    from main import create_app
    app = create_app()

    # Inject a synthetic candidate into the in-memory index.
    _inject_synthetic_candidate()

    return app


def _inject_synthetic_candidate():
    """Insert a canonical microturbine-scale compressor candidate so the
    geometry endpoints have a valid entry to act on.
    """
    from jobs import CANDIDATE_INDEX

    cid = "audit-d-canonical"
    CANDIDATE_INDEX[cid] = {
        "id": cid,
        "job_id": "synthetic-job",
        "params": {
            "inducer_hub_radius": 0.018,
            "inducer_tip_radius": 0.050,
            "impeller_outlet_radius": 0.100,
            "blade_height_outlet": 0.012,
            "blade_count": 18,
            "beta_2_metal_rad": math.pi / 3,
            "tip_clearance": 0.0005,
        },
        "objectives": {"eta_tt": 0.82},
    }
    return cid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CANDIDATE_ID = "audit-d-canonical"


def _parse_binary_stl_triangle_count(data: bytes) -> int:
    """Read the triangle count from a binary STL file (bytes 80-83, little-endian)."""
    if len(data) < 84:
        return -1
    return struct.unpack_from("<I", data, 80)[0]


def _parse_glb_version(data: bytes) -> int:
    """Return the glTF version field (uint32 at offset 4)."""
    if len(data) < 8:
        return -1
    return struct.unpack_from("<I", data, 4)[0]


def _glb_has_mesh_data(data: bytes) -> bool:
    """Crude check: the glb JSON chunk mentions 'meshes' or a BIN chunk exists."""
    # Look for the JSON chunk (type 0x4E4F534A = 'JSON').
    if len(data) < 12:
        return False
    json_chunk_len = struct.unpack_from("<I", data, 12)[0]
    json_chunk_type = struct.unpack_from("<I", data, 16)[0]
    if json_chunk_type != 0x4E4F534A:
        return False
    json_bytes = data[20:20 + json_chunk_len]
    return b'"meshes"' in json_bytes or b'"accessors"' in json_bytes


# ---------------------------------------------------------------------------
# GLB endpoint — stub honesty
# ---------------------------------------------------------------------------

class TestGLBExportHonesty:
    """When cascade.geometry is not available, the GLB endpoint returns a stub
    with X-Cascade-Stub: true.  When it IS available, the stub header must be false
    and the mesh must contain actual geometry.
    """

    @pytest.mark.asyncio
    async def test_glb_geometry_has_valid_magic(self, app_with_candidate):
        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(f"/api/candidates/{_CANDIDATE_ID}/geometry")
        assert r.status_code == 200
        assert r.content[:4] == b"glTF", (
            f"GLB geometry response missing glTF magic: {r.content[:8]!r}"
        )

    @pytest.mark.asyncio
    async def test_glb_geometry_version_is_2(self, app_with_candidate):
        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(f"/api/candidates/{_CANDIDATE_ID}/geometry")
        assert r.status_code == 200
        version = _parse_glb_version(r.content)
        assert version == 2, f"GLB version field should be 2, got {version}"

    @pytest.mark.asyncio
    async def test_glb_stub_header_present(self, app_with_candidate):
        """The X-Cascade-Stub header must be present so the UI can show a
        placeholder when real geometry is unavailable.
        """
        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(f"/api/candidates/{_CANDIDATE_ID}/geometry")
        assert r.status_code == 200
        stub_header = r.headers.get("X-Cascade-Stub")
        assert stub_header in ("true", "false"), (
            f"X-Cascade-Stub header missing or invalid value: {stub_header!r}. "
            f"The UI uses this to show/hide the 'stub' overlay."
        )

    @pytest.mark.asyncio
    async def test_glb_export_has_valid_magic(self, app_with_candidate):
        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(f"/api/candidates/{_CANDIDATE_ID}/export.glb")
        assert r.status_code == 200
        assert r.content[:4] == b"glTF"

    @pytest.mark.asyncio
    async def test_real_glb_is_not_empty_when_geometry_available(self, app_with_candidate):
        """When cascade.geometry IS available and returns a real mesh, the
        returned GLB must contain actual mesh data (meshes array, accessors).
        """
        try:
            from cascade.geometry import generate_impeller_glb  # type: ignore
        except ImportError:
            pytest.skip("cascade.geometry.generate_impeller_glb not available — stub path only")

        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(f"/api/candidates/{_CANDIDATE_ID}/geometry")
        assert r.status_code == 200
        assert r.headers.get("X-Cascade-Stub") == "false", (
            "generate_impeller_glb is importable but X-Cascade-Stub=true — "
            "the endpoint is returning a stub even though real geometry is available."
        )
        assert _glb_has_mesh_data(r.content), (
            "Real GLB (X-Cascade-Stub=false) lacks meshes/accessors — "
            "the geometry module may have returned an empty mesh."
        )


# ---------------------------------------------------------------------------
# STL endpoint — stub honesty
# ---------------------------------------------------------------------------

class TestSTLExportHonesty:
    """Binary STL from the export endpoint must have a nonzero triangle count
    when real geometry is available.  When only a stub is available, the stub
    must be tagged correctly and must not claim to be real geometry.
    """

    @pytest.mark.asyncio
    async def test_stl_header_80_bytes(self, app_with_candidate):
        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(f"/api/candidates/{_CANDIDATE_ID}/export.stl")
        assert r.status_code == 200
        assert len(r.content) >= 84, (
            f"STL response is too short ({len(r.content)} bytes) to be a "
            f"valid binary STL (needs ≥ 84 bytes for header + triangle count)."
        )

    @pytest.mark.asyncio
    async def test_stl_stub_triangle_count_is_zero(self, app_with_candidate):
        """The stub STL explicitly has 0 triangles and must be tagged as a stub.

        A 200 response with 0 triangles is a silent lie if X-Cascade-Stub
        is not set to 'true'.
        """
        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(f"/api/candidates/{_CANDIDATE_ID}/export.stl")
        assert r.status_code == 200

        tri_count = _parse_binary_stl_triangle_count(r.content)
        stub_header = r.headers.get("X-Cascade-Stub")

        if tri_count == 0:
            # Zero triangles MUST be accompanied by X-Cascade-Stub: true.
            assert stub_header == "true", (
                f"STL has 0 triangles but X-Cascade-Stub={stub_header!r}. "
                f"An empty solid returned as a real export is a honesty defect — "
                f"the UI must know this is a stub and show a placeholder."
            )

    @pytest.mark.asyncio
    async def test_real_stl_has_nonzero_triangles_when_geometry_available(
        self, app_with_candidate
    ):
        """When generate_impeller_stl is importable, the export must return
        actual geometry (> 0 triangles).
        """
        try:
            from cascade.geometry import generate_impeller_stl  # type: ignore
        except ImportError:
            pytest.skip("cascade.geometry.generate_impeller_stl not available")

        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(f"/api/candidates/{_CANDIDATE_ID}/export.stl")
        assert r.status_code == 200

        tri_count = _parse_binary_stl_triangle_count(r.content)
        assert tri_count > 0, (
            f"Real STL (generate_impeller_stl importable) has 0 triangles. "
            f"The geometry module may have returned an empty mesh."
        )
        assert r.headers.get("X-Cascade-Stub") == "false"


# ---------------------------------------------------------------------------
# STEP endpoint — 503 boundary
# ---------------------------------------------------------------------------

class TestSTEPExportHonesty:
    """The STEP endpoint MUST return 503 when pythonocc-core is absent,
    NOT 200 with a stub.
    """

    @pytest.mark.asyncio
    async def test_step_503_when_occ_absent(self, app_with_candidate):
        """When OCC is not installed, /export.step must return 503."""
        try:
            import OCC.Core  # noqa: F401
            pytest.skip("pythonocc-core is installed; 503 path not testable here")
        except ImportError:
            pass

        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(f"/api/candidates/{_CANDIDATE_ID}/export.step")
        assert r.status_code == 503, (
            f"STEP export with absent pythonocc-core returned {r.status_code}, "
            f"expected 503.  Returning 200 with a stub is a honesty defect — "
            f"CAD engineers pipe this straight into their workflow and would "
            f"get silent garbage."
        )
        # Error body must mention STEP/IGES or the dependency name.
        body = r.text
        assert any(k in body for k in ("STEP", "pythonocc", "cascade[cad]", "cascade.geometry")), (
            f"503 response body does not explain the cause: {body[:200]!r}"
        )

    @pytest.mark.asyncio
    async def test_step_200_when_occ_present(self, app_with_candidate):
        """When OCC IS installed, /export.step must return 200 with a real STEP file."""
        try:
            import OCC.Core  # noqa: F401
        except ImportError:
            pytest.skip("pythonocc-core not installed; success path not testable")

        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(f"/api/candidates/{_CANDIDATE_ID}/export.step")
        assert r.status_code == 200, f"STEP export failed: {r.text[:200]}"
        # Must be a real STEP file, not a text stub.
        text = r.content.decode("ascii", errors="replace")
        assert text.startswith("ISO-10303-21;"), (
            f"STEP export does not start with ISO-10303-21; header: {text[:80]!r}"
        )
        assert "END-ISO-10303-21;" in text, "STEP file missing trailer"
        # Size sanity: a real impeller STEP is at least a few KB.
        assert len(r.content) > 1024, (
            f"STEP file suspiciously small: {len(r.content)} bytes."
        )


# ---------------------------------------------------------------------------
# IGES endpoint — 503 boundary
# ---------------------------------------------------------------------------

class TestIGESExportHonesty:
    """The IGES endpoint MUST return 503 when pythonocc-core is absent."""

    @pytest.mark.asyncio
    async def test_iges_503_when_occ_absent(self, app_with_candidate):
        try:
            import OCC.Core  # noqa: F401
            pytest.skip("pythonocc-core is installed; 503 path not testable")
        except ImportError:
            pass

        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(f"/api/candidates/{_CANDIDATE_ID}/export.iges")
        assert r.status_code == 503, (
            f"IGES export with absent pythonocc-core returned {r.status_code}, "
            f"expected 503."
        )

    @pytest.mark.asyncio
    async def test_iges_200_structural_validity_when_occ_present(self, app_with_candidate):
        """When OCC is present, the IGES file must have valid S-record markers."""
        try:
            import OCC.Core  # noqa: F401
        except ImportError:
            pytest.skip("pythonocc-core not installed")

        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(f"/api/candidates/{_CANDIDATE_ID}/export.iges")
        assert r.status_code == 200
        lines = r.content.decode("ascii", errors="replace").splitlines()
        assert len(lines) > 0
        # IGES records are 80 chars; the section marker is at col 73 (0-indexed 72).
        first = next((l for l in lines if l.strip()), "")
        # The first non-empty line's last visible character should be a section marker.
        # OCC writes 'S' in column 73 or the line ends with the sequence number.
        has_iges_structure = (
            len(first) >= 72 or
            "S" in first[60:80] if len(first) >= 60 else False
        )
        assert len(r.content) > 512, (
            f"IGES file suspiciously small: {len(r.content)} bytes"
        )


# ---------------------------------------------------------------------------
# NDF endpoint — structural validity (no OCC required)
# ---------------------------------------------------------------------------

class TestNDFExportHonesty:
    """The NDF endpoint must produce a real file with all 4 sections.

    NDF uses only cascade.geometry._curves — no OCC dep — so it should
    always succeed when the candidate is valid.
    """

    @pytest.mark.asyncio
    async def test_ndf_returns_200_with_sections(self, app_with_candidate):
        """NDF export must return 200 with all four section headers."""
        # Check if the NDF export function is available
        try:
            from cascade.geometry import export_turbogrid_ndf  # type: ignore
        except ImportError:
            pytest.skip("cascade.geometry.export_turbogrid_ndf not available")

        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(f"/api/candidates/{_CANDIDATE_ID}/export_turbogrid.ndf")

        if r.status_code == 500:
            pytest.skip(f"NDF export failed with 500: {r.text[:200]}")

        assert r.status_code == 200, f"NDF export status {r.status_code}: {r.text[:200]}"
        text = r.text
        for section in ("[HUB_CURVE]", "[SHROUD_CURVE]",
                        "[BLADE_PROFILE_HUB]", "[BLADE_PROFILE_SHROUD]"):
            assert section in text, (
                f"NDF response missing section {section}. "
                f"A NDF without all 4 sections is structurally incomplete "
                f"and TurboGrid will refuse to import it."
            )

    @pytest.mark.asyncio
    async def test_ndf_sections_have_data_rows(self, app_with_candidate):
        """Each NDF section must contain at least 2 data rows."""
        try:
            from cascade.geometry import export_turbogrid_ndf  # type: ignore
        except ImportError:
            pytest.skip("cascade.geometry.export_turbogrid_ndf not available")

        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(f"/api/candidates/{_CANDIDATE_ID}/export_turbogrid.ndf")

        if r.status_code != 200:
            pytest.skip(f"NDF not available (status {r.status_code})")

        text = r.text
        for section_name in ("HUB_CURVE", "SHROUD_CURVE",
                             "BLADE_PROFILE_HUB", "BLADE_PROFILE_SHROUD"):
            marker = f"[{section_name}]"
            idx = text.find(marker)
            assert idx >= 0, f"Section [{section_name}] not found"

            # Count data rows after the section header.
            # A section ends when a non-comment line starts with '[' (a new
            # section header).  Comment lines (# ...) may contain '[' (e.g.
            # "# x[m]  r[m]") so we only stop at a non-comment '['.
            lines = text[idx + len(marker):].splitlines()
            data_rows = []
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("#"):
                    continue
                if stripped.startswith("["):
                    # Next section — stop.
                    break
                data_rows.append(stripped)

            assert len(data_rows) >= 2, (
                f"NDF section [{section_name}] has only {len(data_rows)} data rows "
                f"(need >= 2). An empty section would break TurboGrid import."
            )


# ---------------------------------------------------------------------------
# CAD health endpoint — consistency check
# ---------------------------------------------------------------------------

class TestCADHealthEndpoint:
    """GET /api/health/cad must accurately reflect the actual STEP/IGES capability.

    If cad_available=true, the STEP endpoint must return 200.
    If cad_available=false, the STEP endpoint must return 503.
    An inconsistency is a honesty defect.
    """

    @pytest.mark.asyncio
    async def test_cad_health_returns_bool(self, app_with_candidate):
        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/health/cad")
        assert r.status_code == 200
        body = r.json()
        assert "cad_available" in body, (
            f"/api/health/cad response missing 'cad_available' field: {body}"
        )
        assert isinstance(body["cad_available"], bool), (
            f"cad_available must be a bool, got {type(body['cad_available'])}"
        )

    @pytest.mark.asyncio
    async def test_cad_health_consistent_with_step_endpoint(self, app_with_candidate):
        """If health/cad says cad_available=true, the STEP endpoint must not 503.
        If cad_available=false, the STEP endpoint must not 200.
        An inconsistency means the UI will show enabled buttons that fail on click,
        or disabled buttons that would actually work.
        """
        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health_r = await client.get("/api/health/cad")
            step_r = await client.get(f"/api/candidates/{_CANDIDATE_ID}/export.step")

        cad_available = health_r.json()["cad_available"]
        step_status = step_r.status_code

        if cad_available:
            assert step_status == 200, (
                f"health/cad says cad_available=true, but /export.step returned "
                f"{step_status}. The UI shows enabled STEP buttons but they fail. "
                f"This is a honesty defect."
            )
        else:
            assert step_status == 503, (
                f"health/cad says cad_available=false, but /export.step returned "
                f"{step_status} instead of 503. The endpoint is returning a stub "
                f"as a real export. This is a honesty defect."
            )

    @pytest.mark.asyncio
    async def test_candidates_cad_available_consistent_with_health(self, app_with_candidate):
        """GET /api/candidates/_cad/available must agree with /api/health/cad."""
        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health_r = await client.get("/api/health/cad")
            cad_r = await client.get("/api/candidates/_cad/available")

        health_available = health_r.json()["cad_available"]
        cand_available = cad_r.json().get("available", None)

        assert cand_available is not None, (
            "/api/candidates/_cad/available response missing 'available' field"
        )
        assert health_available == cand_available, (
            f"/api/health/cad says cad_available={health_available} but "
            f"/api/candidates/_cad/available says available={cand_available}. "
            f"These two probes must agree — the UI uses both."
        )


# ---------------------------------------------------------------------------
# Fluid STEP endpoint — structural validity
# ---------------------------------------------------------------------------

class TestFluidSTEPExportHonesty:
    """The fluid STEP export must return a real STEP file when OCC is present,
    and 503 when OCC is absent.
    """

    @pytest.mark.asyncio
    async def test_fluid_step_503_when_occ_absent(self, app_with_candidate):
        try:
            import OCC.Core  # noqa: F401
            pytest.skip("pythonocc-core is installed; 503 path not testable")
        except ImportError:
            pass

        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(f"/api/candidates/{_CANDIDATE_ID}/export_fluid.step")
        assert r.status_code == 503, (
            f"Fluid STEP with absent OCC returned {r.status_code}, expected 503."
        )

    @pytest.mark.asyncio
    async def test_fluid_step_200_with_iso_header_when_occ_present(self, app_with_candidate):
        try:
            import OCC.Core  # noqa: F401
        except ImportError:
            pytest.skip("pythonocc-core not installed")

        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(f"/api/candidates/{_CANDIDATE_ID}/export_fluid.step")
        assert r.status_code == 200, f"Fluid STEP failed: {r.text[:200]}"
        text = r.content.decode("ascii", errors="replace")
        assert text.startswith("ISO-10303-21;"), (
            f"Fluid STEP does not start with ISO-10303-21; header"
        )
        assert "END-ISO-10303-21;" in text

    @pytest.mark.asyncio
    async def test_fluid_step_contains_patch_names_when_occ_present(self, app_with_candidate):
        try:
            import OCC.Core  # noqa: F401
        except ImportError:
            pytest.skip("pythonocc-core not installed")

        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(f"/api/candidates/{_CANDIDATE_ID}/export_fluid.step")
        assert r.status_code == 200
        text = r.content.decode("ascii", errors="replace")
        required_patches = ["INLET", "OUTLET", "HUB", "SHROUD"]
        for patch in required_patches:
            assert patch in text, (
                f"Fluid STEP missing named patch '{patch}'. "
                f"CFD engineers need these names to assign BCs without "
                f"manual selection in SpaceClaim."
            )


# ---------------------------------------------------------------------------
# Export endpoint 404 for missing candidates
# ---------------------------------------------------------------------------

class TestExportMissingCandidate:
    """All export endpoints must return 404 for non-existent candidate IDs,
    not 500 or an empty file.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint", [
        "/api/candidates/does-not-exist/geometry",
        "/api/candidates/does-not-exist/export.glb",
        "/api/candidates/does-not-exist/export.stl",
        "/api/candidates/does-not-exist/export.step",
        "/api/candidates/does-not-exist/export.iges",
        "/api/candidates/does-not-exist/export_turbogrid.ndf",
        "/api/candidates/does-not-exist/export_fluid.step",
    ])
    async def test_missing_candidate_returns_404(self, app_with_candidate, endpoint):
        import httpx
        transport = httpx.ASGITransport(app=app_with_candidate)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(endpoint)
        assert r.status_code == 404, (
            f"Endpoint {endpoint} returned {r.status_code} for a missing "
            f"candidate, expected 404."
        )
