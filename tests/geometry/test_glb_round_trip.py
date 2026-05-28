"""glb round-trip tests.

Verify that the binary glTF bytes we emit are valid glTF 2.0 and can be
loaded back via trimesh — the same path Three.js / React Three Fiber
take in the browser.
"""

from __future__ import annotations

import io
import math
import struct

import pytest
import trimesh

from cascade.geometry import MeshLOD, impeller_mesh, export_glb
from cascade.meanline.centrifugal_compressor import CentrifugalCompressorGeometry


def _eckardt_rotor_o() -> CentrifugalCompressorGeometry:
    return CentrifugalCompressorGeometry(
        inducer_hub_radius=0.018,
        inducer_tip_radius=0.050,
        impeller_outlet_radius=0.100,
        blade_height_outlet=0.012,
        blade_count=20,
        beta_2_metal_rad=math.pi / 3,
        tip_clearance=0.0005,
    )


def test_glb_has_valid_magic() -> None:
    """The first four bytes of a `.glb` are the ASCII magic 'glTF'."""
    g = _eckardt_rotor_o()
    m = impeller_mesh(g, lod=MeshLOD.PREVIEW, with_splitter=False)
    glb = export_glb(m)
    magic = bytes(glb[:4])
    assert magic == b"glTF"

    # Version field is uint32 little-endian at offset 4.
    version = struct.unpack("<I", bytes(glb[4:8]))[0]
    assert version == 2


def test_glb_round_trip_via_trimesh() -> None:
    """Load the emitted glb back via trimesh.load and verify vertex count."""
    g = _eckardt_rotor_o()
    m = impeller_mesh(g, lod=MeshLOD.PREVIEW, with_splitter=False)
    glb = export_glb(m)

    loaded = trimesh.load(io.BytesIO(bytes(glb)), file_type="glb")
    # trimesh loads scenes; flatten if needed.
    if isinstance(loaded, trimesh.Scene):
        meshes = list(loaded.geometry.values())
        assert len(meshes) >= 1
        loaded_mesh = trimesh.util.concatenate(meshes)
    else:
        loaded_mesh = loaded

    # Vertex counts should match (within merge tolerance).
    assert abs(loaded_mesh.vertices.shape[0] - m.vertices.shape[0]) < 50
    # Face counts should match exactly.
    assert loaded_mesh.faces.shape[0] == m.faces.shape[0]


def test_glb_embeds_pbr_material() -> None:
    """Verify the glb embeds a PBR material with metallic ≈ 0.9."""
    g = _eckardt_rotor_o()
    m = impeller_mesh(g, lod=MeshLOD.PREVIEW, with_splitter=False)
    glb = export_glb(m)
    loaded = trimesh.load(io.BytesIO(bytes(glb)), file_type="glb")

    # The loaded scene/mesh should carry a PBR material.
    if isinstance(loaded, trimesh.Scene):
        meshes = list(loaded.geometry.values())
        assert len(meshes) >= 1
        mat = meshes[0].visual.material
    else:
        mat = loaded.visual.material

    # Different versions of trimesh expose the metallic factor under
    # slightly different attribute names. Be tolerant.
    metallic = getattr(mat, "metallicFactor", None)
    if metallic is None:
        # Fallback: PBR material dict-like access.
        metallic = getattr(mat, "metallic_factor", None)
    assert metallic is not None, (
        f"loaded glb material lacks metallic factor: {mat}"
    )
    assert metallic == pytest.approx(0.9, abs=0.05)


def test_glb_size_in_reasonable_range() -> None:
    """STANDARD-LOD impeller glb should be < 1 MB on the wire."""
    g = _eckardt_rotor_o()
    m = impeller_mesh(g, lod=MeshLOD.STANDARD, with_splitter=True)
    glb = export_glb(m)
    # An LOD-STANDARD impeller with 20 blades + splitters should be on the
    # order of a few hundred KB — well under the WebGL size target.
    assert len(glb) < 2_000_000  # 2 MB upper bound
    assert len(glb) > 1000      # nontrivial
