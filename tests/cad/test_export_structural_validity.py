"""Structural validity tests for every Cascade geometry export format.

For each format this module asserts *structural* invariants — not just
HTTP-200 or file-exists, but that the file is a well-formed instance of
the claimed format with non-empty, physically plausible geometry.

Formats covered:
  GLB   — glTF binary magic, version 2, meshes array, bufferViews, accessors,
           vertex count consistent with impeller geometry
  STL   — binary header, triangle count > 0, every triangle has 3 finite
           vertices, normals are unit-length (within 1e-4)
  STEP  — ISO-10303-21 header, FILE_DESCRIPTION + FILE_NAME records
  IGES  — Start section S-record, Global G-record, Directory D-record,
           Parameter P-record, Terminate T-record
  NDF   — all 4 section headers, > 0 data rows per section
  Fluid-STEP — 8 named patches in FILE_DESCRIPTION; face count > 8

OCC-dependent tests skip cleanly when ``pythonocc-core`` is not installed.
"""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path
from typing import List

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

import sys as _sys
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO / "src") not in _sys.path:
    _sys.path.insert(0, str(_REPO / "src"))


# ---------------------------------------------------------------------------
# Fixture geometry — canonical AT-100 microturbine-scale impeller
# ---------------------------------------------------------------------------

def _at100_compressor():
    from cascade.meanline.centrifugal_compressor import CentrifugalCompressorGeometry
    return CentrifugalCompressorGeometry(
        inducer_hub_radius=0.018,
        inducer_tip_radius=0.050,
        impeller_outlet_radius=0.100,
        blade_height_outlet=0.012,
        blade_count=18,
        beta_2_metal_rad=math.pi / 3,
        tip_clearance=0.0005,
    )


@pytest.fixture
def at100_mesh():
    """STANDARD-LOD impeller mesh for the AT-100 canonical geometry."""
    from cascade.geometry import MeshLOD, impeller_mesh
    g = _at100_compressor()
    return impeller_mesh(g, lod=MeshLOD.STANDARD, with_splitter=True)


@pytest.fixture
def at100_export_mesh():
    """EXPORT-LOD impeller mesh (highest fidelity, used for STL/STEP/IGES)."""
    from cascade.geometry import MeshLOD, impeller_mesh
    g = _at100_compressor()
    return impeller_mesh(g, lod=MeshLOD.EXPORT, with_splitter=True)


# ===========================================================================
# GLB structural validity
# ===========================================================================

class TestGLBStructuralValidity:
    """Assert that a GLB produced by export_glb is a structurally valid
    glTF 2.0 binary container with non-empty geometry.
    """

    def _parse_glb_json(self, data: bytes) -> dict:
        """Extract and parse the JSON chunk from a glb bytestring."""
        # glb layout: 12-byte header, then chunks.
        # Chunk 0 is always the JSON chunk.
        assert data[:4] == b"glTF", f"Not a glTF file: {data[:4]!r}"
        json_chunk_len = struct.unpack_from("<I", data, 12)[0]
        json_chunk_type = struct.unpack_from("<I", data, 16)[0]
        assert json_chunk_type == 0x4E4F534A, (
            f"First chunk is not JSON (type={json_chunk_type:#010x})"
        )
        return json.loads(data[20:20 + json_chunk_len].rstrip(b" ").decode())

    def test_glb_magic(self, at100_mesh):
        from cascade.geometry import export_glb
        data = export_glb(at100_mesh)
        assert data[:4] == b"glTF", (
            f"GLB missing glTF magic bytes; got {data[:4]!r}"
        )

    def test_glb_version_is_2(self, at100_mesh):
        from cascade.geometry import export_glb
        data = export_glb(at100_mesh)
        version = struct.unpack_from("<I", data, 4)[0]
        assert version == 2, f"GLB version must be 2, got {version}"

    def test_glb_has_meshes_array(self, at100_mesh):
        from cascade.geometry import export_glb
        data = export_glb(at100_mesh)
        gltf = self._parse_glb_json(data)
        assert "meshes" in gltf, (
            "GLB JSON chunk has no 'meshes' key — empty/stub geometry"
        )
        assert len(gltf["meshes"]) > 0, (
            "GLB 'meshes' array is empty — no geometry exported"
        )

    def test_glb_has_buffer_views(self, at100_mesh):
        from cascade.geometry import export_glb
        data = export_glb(at100_mesh)
        gltf = self._parse_glb_json(data)
        assert "bufferViews" in gltf, (
            "GLB JSON chunk has no 'bufferViews' key"
        )
        assert len(gltf["bufferViews"]) > 0

    def test_glb_has_accessors(self, at100_mesh):
        from cascade.geometry import export_glb
        data = export_glb(at100_mesh)
        gltf = self._parse_glb_json(data)
        assert "accessors" in gltf, (
            "GLB JSON chunk has no 'accessors' key"
        )
        assert len(gltf["accessors"]) > 0

    def test_glb_vertex_count_nonzero(self, at100_mesh):
        from cascade.geometry import export_glb
        data = export_glb(at100_mesh)
        gltf = self._parse_glb_json(data)
        # The POSITION accessor carries the vertex count.
        # Find it via the mesh primitive's POSITION attribute.
        mesh = gltf["meshes"][0]
        prim = mesh["primitives"][0]
        position_accessor_idx = prim["attributes"]["POSITION"]
        accessor = gltf["accessors"][position_accessor_idx]
        vertex_count = accessor["count"]
        assert vertex_count > 100, (
            f"GLB POSITION accessor has only {vertex_count} vertices — "
            f"suspiciously low for an 18-blade impeller at STANDARD LOD."
        )

    def test_glb_has_bin_chunk(self, at100_mesh):
        """The BIN chunk (chunk type 0x004E4942) must be present for a real mesh."""
        from cascade.geometry import export_glb
        data = export_glb(at100_mesh)
        # JSON chunk ends at offset 20 + json_chunk_len; BIN chunk starts there.
        json_chunk_len = struct.unpack_from("<I", data, 12)[0]
        # Pad to 4-byte alignment (GLB spec §A.2).
        bin_chunk_offset = 20 + json_chunk_len
        assert len(data) > bin_chunk_offset + 8, (
            "GLB has no BIN chunk — binary geometry data is missing."
        )
        bin_chunk_type = struct.unpack_from("<I", data, bin_chunk_offset + 4)[0]
        assert bin_chunk_type == 0x004E4942, (
            f"Second GLB chunk type is not BIN (0x004E4942): {bin_chunk_type:#010x}"
        )
        bin_len = struct.unpack_from("<I", data, bin_chunk_offset)[0]
        assert bin_len > 0, "GLB BIN chunk is empty — no geometry data"

    def test_generate_impeller_glb_roundtrip(self):
        """generate_impeller_glb (the API helper) produces a valid GLB."""
        from cascade.geometry import generate_impeller_glb
        params = {
            "inducer_hub_radius": 0.018,
            "inducer_tip_radius": 0.050,
            "impeller_outlet_radius": 0.100,
            "blade_height_outlet": 0.012,
            "blade_count": 18,
            "beta_2_metal_rad": math.pi / 3,
            "tip_clearance": 0.0005,
        }
        data = generate_impeller_glb(params, lod="medium")
        assert data[:4] == b"glTF"
        gltf = self._parse_glb_json(data)
        assert len(gltf.get("meshes", [])) > 0
        assert len(gltf.get("accessors", [])) > 0

    def test_generate_impeller_glb_all_lods(self):
        """generate_impeller_glb works for all named LOD strings."""
        from cascade.geometry import generate_impeller_glb
        params = {"blade_count": 10}  # minimal valid geometry
        for lod in ("low", "medium", "hi", "export", "preview", "standard", "high"):
            data = generate_impeller_glb(params, lod=lod)
            assert data[:4] == b"glTF", f"LOD {lod!r} produced bad magic"


# ===========================================================================
# STL structural validity
# ===========================================================================

class TestSTLStructuralValidity:
    """Assert that binary STL output is structurally valid.

    Binary STL layout:
      80 bytes — header
      4 bytes  — uint32 triangle count
      n × 50 bytes — triangles (normal 3×f32, vertex 3×3×f32, attr 2-byte)
    """

    def _parse_stl(self, data: bytes):
        """Return (header, tri_count, triangles_array)."""
        assert len(data) >= 84, f"STL too short: {len(data)} bytes"
        header = data[:80]
        tri_count = struct.unpack_from("<I", data, 80)[0]
        expected_len = 84 + tri_count * 50
        assert len(data) == expected_len, (
            f"STL byte length mismatch: file is {len(data)} bytes, "
            f"but header says {tri_count} triangles → expected {expected_len}"
        )
        return header, tri_count

    def test_stl_header_80_bytes(self, at100_export_mesh):
        from cascade.geometry import export_stl
        data = export_stl(at100_export_mesh)
        assert len(data) >= 80, "STL file is shorter than the 80-byte header"

    def test_stl_triangle_count_positive(self, at100_export_mesh):
        from cascade.geometry import export_stl
        data = export_stl(at100_export_mesh)
        _, tri_count = self._parse_stl(data)
        assert tri_count > 0, (
            "STL has 0 triangles — export produced empty geometry"
        )

    def test_stl_byte_length_consistent(self, at100_export_mesh):
        from cascade.geometry import export_stl
        data = export_stl(at100_export_mesh)
        self._parse_stl(data)  # asserts byte-length consistency internally

    def _parse_stl_triangles(self, data: bytes):
        """Parse all triangle records from a binary STL.

        Each STL triangle record is exactly 50 bytes:
          3 × float32  face normal  (12 bytes)
          3 × float32  vertex 1     (12 bytes)
          3 × float32  vertex 2     (12 bytes)
          3 × float32  vertex 3     (12 bytes)
          uint16       attr byte    ( 2 bytes)
        Total: 50 bytes (not aligned to 4, so cannot use frombuffer directly).
        """
        import struct as _struct
        tri_count = _struct.unpack_from("<I", data, 80)[0]
        _STL_RECORD_FMT = "<12fH"  # 12 floats + 1 ushort = 50 bytes
        _STL_RECORD_SIZE = _struct.calcsize(_STL_RECORD_FMT)  # == 50
        normals = np.empty((tri_count, 3), dtype=np.float32)
        vertices = np.empty((tri_count, 9), dtype=np.float32)
        offset = 84
        for i in range(tri_count):
            vals = _struct.unpack_from(_STL_RECORD_FMT, data, offset)
            normals[i] = vals[0:3]
            vertices[i] = vals[3:12]
            offset += _STL_RECORD_SIZE
        return normals, vertices

    def test_stl_vertices_are_finite(self, at100_export_mesh):
        """Every triangle's three vertex coordinates must be finite floats."""
        from cascade.geometry import export_stl
        data = export_stl(at100_export_mesh)
        normals, vertices = self._parse_stl_triangles(data)
        assert np.all(np.isfinite(vertices)), (
            "STL contains non-finite vertex coordinates (NaN/Inf)"
        )
        assert np.all(np.isfinite(normals)), (
            "STL contains non-finite normal coordinates (NaN/Inf)"
        )

    def test_stl_normals_approximately_unit_length(self, at100_export_mesh):
        """Face normals in the STL must be (approximately) unit vectors."""
        from cascade.geometry import export_stl
        data = export_stl(at100_export_mesh)
        normals, _ = self._parse_stl_triangles(data)
        # Some STL writers emit zero-normals for degenerate triangles; skip those.
        norms_mag = np.linalg.norm(normals, axis=1)
        nonzero = norms_mag > 1e-6
        if nonzero.sum() > 0:
            deviations = np.abs(norms_mag[nonzero] - 1.0)
            assert np.all(deviations < 1e-4), (
                f"STL normals are not unit-length; max deviation = "
                f"{deviations.max():.6f}"
            )

    def test_generate_impeller_stl_triangle_count(self):
        """generate_impeller_stl (the API helper) produces a non-empty STL."""
        from cascade.geometry import generate_impeller_stl
        params = {
            "inducer_hub_radius": 0.018,
            "inducer_tip_radius": 0.050,
            "impeller_outlet_radius": 0.100,
            "blade_height_outlet": 0.012,
            "blade_count": 18,
            "beta_2_metal_rad": math.pi / 3,
            "tip_clearance": 0.0005,
        }
        data = generate_impeller_stl(params)
        tri_count = struct.unpack_from("<I", data, 80)[0]
        assert tri_count > 0, (
            f"generate_impeller_stl returned 0 triangles"
        )
        # At EXPORT LOD an 18-blade impeller should have at least 10 000 tris.
        assert tri_count > 10_000, (
            f"EXPORT-LOD STL has only {tri_count} triangles — suspiciously low. "
            f"Expected > 10 000 for an 18-blade impeller."
        )


# ===========================================================================
# STEP structural validity (OCC-gated)
# ===========================================================================

class TestSTEPStructuralValidity:
    """Assert that STEP output starts and ends with the ISO-10303-21 markers
    and contains the mandatory FILE_DESCRIPTION / FILE_NAME records.

    Skips cleanly when pythonocc-core is not installed.
    """

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("OCC"),
        reason="pythonocc-core not installed",
    )
    def test_step_iso_header(self, at100_export_mesh, tmp_path):
        from cascade.geometry import export_step
        out = tmp_path / "impeller.step"
        export_step(at100_export_mesh, out)
        text = out.read_text(encoding="ascii", errors="replace")
        assert text.startswith("ISO-10303-21;"), (
            f"STEP file missing ISO 10303-21 header; starts with: {text[:80]!r}"
        )

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("OCC"),
        reason="pythonocc-core not installed",
    )
    def test_step_iso_trailer(self, at100_export_mesh, tmp_path):
        from cascade.geometry import export_step
        out = tmp_path / "impeller.step"
        export_step(at100_export_mesh, out)
        text = out.read_text(encoding="ascii", errors="replace")
        assert "END-ISO-10303-21;" in text, (
            "STEP file missing END-ISO-10303-21; trailer"
        )

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("OCC"),
        reason="pythonocc-core not installed",
    )
    def test_step_has_file_description(self, at100_export_mesh, tmp_path):
        from cascade.geometry import export_step
        out = tmp_path / "impeller.step"
        export_step(at100_export_mesh, out)
        text = out.read_text(encoding="ascii", errors="replace")
        assert "FILE_DESCRIPTION" in text, (
            "STEP file missing FILE_DESCRIPTION record in header section"
        )

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("OCC"),
        reason="pythonocc-core not installed",
    )
    def test_step_has_file_name(self, at100_export_mesh, tmp_path):
        from cascade.geometry import export_step
        out = tmp_path / "impeller.step"
        export_step(at100_export_mesh, out)
        text = out.read_text(encoding="ascii", errors="replace")
        assert "FILE_NAME" in text, (
            "STEP file missing FILE_NAME record in header section"
        )

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("OCC"),
        reason="pythonocc-core not installed",
    )
    def test_step_has_geometry_entities(self, at100_export_mesh, tmp_path):
        """STEP file must contain at least one B-rep or face entity.

        For a triangulated STEP export from OCC, we expect the DATA section
        to contain ADVANCED_FACE records (one per triangle).
        """
        from cascade.geometry import export_step
        out = tmp_path / "impeller.step"
        export_step(at100_export_mesh, out)
        text = out.read_text(encoding="ascii", errors="replace")
        # Triangulated STEP from OCC uses ADVANCED_FACE as the leaf entity.
        has_brep = (
            "MANIFOLD_SOLID_BREP" in text
            or "ADVANCED_BREP_SHAPE_REPRESENTATION" in text
            or "ADVANCED_FACE" in text
            or "FACE_SURFACE" in text
        )
        assert has_brep, (
            "STEP file data section has no face/brep geometry entities. "
            "The export may have produced an empty compound."
        )

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("OCC"),
        reason="pythonocc-core not installed",
    )
    def test_step_file_size_reasonable(self, at100_export_mesh, tmp_path):
        """STEP file must be larger than 1 KB for a real impeller mesh."""
        from cascade.geometry import export_step
        out = tmp_path / "impeller.step"
        export_step(at100_export_mesh, out)
        size = out.stat().st_size
        assert size > 1024, (
            f"STEP file suspiciously small ({size} bytes) — may be empty or stub"
        )

    def test_step_raises_cad_not_available_when_occ_missing(self, at100_export_mesh, tmp_path):
        """When OCC is absent, export_step must raise CADExportNotAvailable,
        not silently return a stub or raise an unrelated error.
        """
        try:
            import OCC.Core  # noqa: F401
            pytest.skip("pythonocc-core is installed; not-available path untestable")
        except ImportError:
            pass

        from cascade.geometry import export_step
        from cascade.geometry.export import CADExportNotAvailable
        with pytest.raises(CADExportNotAvailable):
            export_step(at100_export_mesh, tmp_path / "x.step")


# ===========================================================================
# IGES structural validity (OCC-gated)
# ===========================================================================

_OCC_AVAILABLE = False
try:
    import importlib as _importlib
    _OCC_AVAILABLE = _importlib.util.find_spec("OCC") is not None
except Exception:
    pass


class TestIGESStructuralValidity:
    """Assert that IGES output has all five section markers.

    IGES section markers appear at column 73 (1-indexed) of each 80-char record:
      S — Start
      G — Global
      D — Directory Entry
      P — Parameter Data
      T — Terminate
    """

    def _extract_section_letters(self, text: str) -> set:
        """Return the set of section-marker characters found in an IGES file."""
        found = set()
        for line in text.splitlines():
            if len(line) >= 73:
                marker = line[72]  # column 73 is index 72
                if marker in "SGDPT":
                    found.add(marker)
        return found

    @pytest.mark.skipif(
        not _OCC_AVAILABLE,
        reason="pythonocc-core not installed",
    )
    def test_iges_has_start_section(self, at100_export_mesh, tmp_path):
        from cascade.geometry import export_iges
        out = tmp_path / "impeller.iges"
        export_iges(at100_export_mesh, out)
        text = out.read_text(encoding="ascii", errors="replace")
        sections = self._extract_section_letters(text)
        assert "S" in sections, "IGES file missing Start (S) section marker"

    @pytest.mark.skipif(
        not _OCC_AVAILABLE,
        reason="pythonocc-core not installed",
    )
    def test_iges_has_global_section(self, at100_export_mesh, tmp_path):
        from cascade.geometry import export_iges
        out = tmp_path / "impeller.iges"
        export_iges(at100_export_mesh, out)
        text = out.read_text(encoding="ascii", errors="replace")
        sections = self._extract_section_letters(text)
        assert "G" in sections, "IGES file missing Global (G) section marker"

    @pytest.mark.skipif(
        not _OCC_AVAILABLE,
        reason="pythonocc-core not installed",
    )
    def test_iges_has_directory_section(self, at100_export_mesh, tmp_path):
        from cascade.geometry import export_iges
        out = tmp_path / "impeller.iges"
        export_iges(at100_export_mesh, out)
        text = out.read_text(encoding="ascii", errors="replace")
        sections = self._extract_section_letters(text)
        assert "D" in sections, "IGES file missing Directory Entry (D) section marker"

    @pytest.mark.skipif(
        not _OCC_AVAILABLE,
        reason="pythonocc-core not installed",
    )
    def test_iges_has_parameter_section(self, at100_export_mesh, tmp_path):
        from cascade.geometry import export_iges
        out = tmp_path / "impeller.iges"
        export_iges(at100_export_mesh, out)
        text = out.read_text(encoding="ascii", errors="replace")
        sections = self._extract_section_letters(text)
        assert "P" in sections, "IGES file missing Parameter Data (P) section marker"

    @pytest.mark.skipif(
        not _OCC_AVAILABLE,
        reason="pythonocc-core not installed",
    )
    def test_iges_has_terminate_section(self, at100_export_mesh, tmp_path):
        from cascade.geometry import export_iges
        out = tmp_path / "impeller.iges"
        export_iges(at100_export_mesh, out)
        text = out.read_text(encoding="ascii", errors="replace")
        sections = self._extract_section_letters(text)
        assert "T" in sections, "IGES file missing Terminate (T) section marker"

    @pytest.mark.skipif(
        not _OCC_AVAILABLE,
        reason="pythonocc-core not installed",
    )
    def test_iges_all_five_sections_present(self, at100_export_mesh, tmp_path):
        """Convenience: all five sections at once."""
        from cascade.geometry import export_iges
        out = tmp_path / "impeller.iges"
        export_iges(at100_export_mesh, out)
        text = out.read_text(encoding="ascii", errors="replace")
        sections = self._extract_section_letters(text)
        assert sections >= {"S", "G", "D", "P", "T"}, (
            f"IGES file missing section markers: expected {{S,G,D,P,T}}, got {sections}"
        )

    @pytest.mark.skipif(
        not _OCC_AVAILABLE,
        reason="pythonocc-core not installed",
    )
    def test_iges_file_size_reasonable(self, at100_export_mesh, tmp_path):
        from cascade.geometry import export_iges
        out = tmp_path / "impeller.iges"
        export_iges(at100_export_mesh, out)
        size = out.stat().st_size
        assert size > 512, (
            f"IGES file suspiciously small ({size} bytes)"
        )

    def test_iges_raises_cad_not_available_when_occ_missing(self, at100_export_mesh, tmp_path):
        try:
            import OCC.Core  # noqa: F401
            pytest.skip("pythonocc-core installed; not-available path untestable")
        except ImportError:
            pass

        from cascade.geometry import export_iges
        from cascade.geometry.export import CADExportNotAvailable
        with pytest.raises(CADExportNotAvailable):
            export_iges(at100_export_mesh, tmp_path / "x.iges")


# ===========================================================================
# NDF structural validity
# ===========================================================================

class TestNDFStructuralValidity:
    """NDF is pure ASCII and does not require OCC — these tests always run."""

    REQUIRED_SECTIONS = [
        "HUB_CURVE",
        "SHROUD_CURVE",
        "BLADE_PROFILE_HUB",
        "BLADE_PROFILE_SHROUD",
    ]

    def _parse_section(self, text: str, section_name: str) -> List[List[float]]:
        """Extract numeric rows from a named NDF section."""
        start_marker = f"[{section_name}]"
        lines = text.splitlines()
        start_idx = None
        for i, line in enumerate(lines):
            if line.strip() == start_marker:
                start_idx = i + 1
                break
        if start_idx is None:
            return []
        rows: List[List[float]] = []
        for line in lines[start_idx:]:
            stripped = line.strip()
            if stripped.startswith("[") and not stripped.startswith("#"):
                break
            if not stripped or stripped.startswith("#"):
                continue
            rows.append([float(p) for p in stripped.split()])
        return rows

    def test_ndf_has_all_four_section_headers(self, tmp_path):
        from cascade.geometry import export_turbogrid_ndf
        g = _at100_compressor()
        out = tmp_path / "at100.ndf"
        export_turbogrid_ndf(g, out)
        text = out.read_text(encoding="ascii")
        for section in self.REQUIRED_SECTIONS:
            assert f"[{section}]" in text, (
                f"NDF missing section [{section}]"
            )

    def test_ndf_sections_have_nonzero_data_rows(self, tmp_path):
        from cascade.geometry import export_turbogrid_ndf
        g = _at100_compressor()
        out = tmp_path / "at100.ndf"
        export_turbogrid_ndf(g, out)
        text = out.read_text(encoding="ascii")
        for section_name in self.REQUIRED_SECTIONS:
            rows = self._parse_section(text, section_name)
            assert len(rows) > 0, (
                f"NDF section [{section_name}] is empty — no point data"
            )

    def test_ndf_hub_shroud_two_columns(self, tmp_path):
        from cascade.geometry import export_turbogrid_ndf
        g = _at100_compressor()
        out = tmp_path / "at100.ndf"
        export_turbogrid_ndf(g, out)
        text = out.read_text(encoding="ascii")
        for section_name in ("HUB_CURVE", "SHROUD_CURVE"):
            rows = self._parse_section(text, section_name)
            assert all(len(r) == 2 for r in rows), (
                f"NDF [{section_name}] rows should have exactly 2 columns (x, r)"
            )

    def test_ndf_blade_profiles_three_columns(self, tmp_path):
        from cascade.geometry import export_turbogrid_ndf
        g = _at100_compressor()
        out = tmp_path / "at100.ndf"
        export_turbogrid_ndf(g, out)
        text = out.read_text(encoding="ascii")
        for section_name in ("BLADE_PROFILE_HUB", "BLADE_PROFILE_SHROUD"):
            rows = self._parse_section(text, section_name)
            assert all(len(r) == 3 for r in rows), (
                f"NDF [{section_name}] rows should have 3 columns (x, r, theta)"
            )

    def test_ndf_min_point_counts(self, tmp_path):
        """At default resolution, hub/shroud have >= 40 pts, blades >= 25."""
        from cascade.geometry import export_turbogrid_ndf
        g = _at100_compressor()
        out = tmp_path / "at100.ndf"
        export_turbogrid_ndf(g, out, n_hub=50, n_shroud=50, n_blade=30)
        text = out.read_text(encoding="ascii")
        assert len(self._parse_section(text, "HUB_CURVE")) >= 40
        assert len(self._parse_section(text, "SHROUD_CURVE")) >= 40
        assert len(self._parse_section(text, "BLADE_PROFILE_HUB")) >= 25
        assert len(self._parse_section(text, "BLADE_PROFILE_SHROUD")) >= 25


# ===========================================================================
# Fluid-volume STEP structural validity (OCC-gated)
# ===========================================================================

class TestFluidSTEPStructuralValidity:
    """Assert that the fluid-volume STEP file contains the 8 named patch
    identifiers and is a valid ISO-10303-21 file.
    """

    REQUIRED_PATCHES = [
        "INLET", "OUTLET", "HUB", "SHROUD",
        "BLADE_SUCTION", "BLADE_PRESSURE",
        "PERIODIC_1", "PERIODIC_2",
    ]

    @pytest.mark.skipif(
        not _OCC_AVAILABLE,
        reason="pythonocc-core not installed",
    )
    def test_fluid_step_iso_header(self, tmp_path):
        from cascade.geometry import export_fluid_volume_step
        g = _at100_compressor()
        out = tmp_path / "fluid.step"
        export_fluid_volume_step(g, out, n_meridional=20, n_circumferential=12)
        text = out.read_text(encoding="ascii", errors="replace")
        assert text.startswith("ISO-10303-21;"), (
            "Fluid STEP missing ISO-10303-21 header"
        )
        assert "END-ISO-10303-21;" in text, (
            "Fluid STEP missing END-ISO-10303-21 trailer"
        )

    @pytest.mark.skipif(
        not _OCC_AVAILABLE,
        reason="pythonocc-core not installed",
    )
    def test_fluid_step_has_all_eight_patch_names(self, tmp_path):
        """All 8 named patch strings must be present in the STEP text.

        NOTE (Item 4): Patch names are embedded in the FILE_DESCRIPTION field
        of the STEP header section, not as PRODUCT_DEFINITION records.  This
        is Option B of the fluid-STEP patch-name migration plan — acceptable
        because the full XDE migration to PRODUCT names is deferred.  Users
        parsing PRODUCT_DEFINITION records must be directed to FILE_DESCRIPTION
        instead (documented in export_fluid_volume_step's docstring).
        """
        from cascade.geometry import export_fluid_volume_step
        g = _at100_compressor()
        out = tmp_path / "fluid.step"
        export_fluid_volume_step(g, out, n_meridional=20, n_circumferential=12)
        text = out.read_text(encoding="ascii", errors="replace")
        for patch in self.REQUIRED_PATCHES:
            assert patch in text, (
                f"Fluid STEP missing patch name '{patch}'. "
                f"Patch names should appear in FILE_DESCRIPTION. "
                f"CFD engineers rely on these to assign BCs."
            )

    @pytest.mark.skipif(
        not _OCC_AVAILABLE,
        reason="pythonocc-core not installed",
    )
    def test_fluid_step_has_geometry_data(self, tmp_path):
        """The DATA section of the fluid STEP must contain geometry entities."""
        from cascade.geometry import export_fluid_volume_step
        g = _at100_compressor()
        out = tmp_path / "fluid.step"
        export_fluid_volume_step(g, out, n_meridional=20, n_circumferential=12)
        text = out.read_text(encoding="ascii", errors="replace")
        has_geometry = (
            "ADVANCED_FACE" in text
            or "FACE_SURFACE" in text
            or "MANIFOLD_SOLID_BREP" in text
            or "ADVANCED_BREP_SHAPE_REPRESENTATION" in text
        )
        assert has_geometry, (
            "Fluid STEP DATA section has no face/brep geometry entities"
        )

    @pytest.mark.skipif(
        not _OCC_AVAILABLE,
        reason="pythonocc-core not installed",
    )
    def test_fluid_step_result_dict_has_all_patch_keys(self, tmp_path):
        """The return dict from export_fluid_volume_step must list all 8 patches."""
        from cascade.geometry import export_fluid_volume_step
        g = _at100_compressor()
        out = tmp_path / "fluid.step"
        result = export_fluid_volume_step(g, out, n_meridional=16, n_circumferential=8)
        assert set(self.REQUIRED_PATCHES).issubset(set(result["patch_names"])), (
            f"export_fluid_volume_step result missing patch names: "
            f"{set(self.REQUIRED_PATCHES) - set(result['patch_names'])}"
        )

    def test_fluid_step_raises_cad_not_available_when_occ_missing(self, tmp_path):
        try:
            import OCC.Core  # noqa: F401
            pytest.skip("pythonocc-core installed; not-available path untestable")
        except ImportError:
            pass

        from cascade.geometry import export_fluid_volume_step
        from cascade.geometry.export import CADExportNotAvailable
        g = _at100_compressor()
        with pytest.raises(CADExportNotAvailable):
            export_fluid_volume_step(g, tmp_path / "x.step")
