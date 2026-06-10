"""Cascade 3D geometry generator.

Mesh generation for centrifugal compressor impellers, radial inflow
turbine rotors, volutes, and rotor shafts. The output meshes are
`trimesh.Trimesh` objects with PBR materials attached; export helpers
turn them into glTF binary (`.glb`), STL, or OBJ for direct consumption
by Three.js / React Three Fiber.

Follows a server-side canonical mesh generation strategy at four LOD
levels, designed to round-trip cleanly to the browser preview.
"""

from __future__ import annotations

from enum import Enum
from typing import Union

import trimesh

from cascade.geometry.export import (
    CADExportNotAvailable,
    cad_export_available,
    export_cgns,
    export_fluid_volume_step,
    export_glb,
    export_iges,
    export_obj,
    export_step,
    export_stl,
    export_surface_point_cloud,
    export_turbogrid_curve,
    export_turbogrid_ndf,
)
from cascade.geometry.impeller import centrifugal_impeller_mesh
from cascade.geometry.radial_turbine import radial_turbine_mesh
from cascade.geometry.rotor import rotor_shaft_mesh_impl
from cascade.geometry.volute import VoluteGeometry, volute_mesh_impl
from cascade.meanline.centrifugal_compressor import CentrifugalCompressorGeometry
from cascade.meanline.radial_turbine import RadialTurbineGeometry
from cascade.units import RotorShape


__all__ = [
    "MeshLOD",
    "VoluteGeometry",
    "impeller_mesh",
    "volute_mesh",
    "rotor_shaft_mesh",
    "export_glb",
    "export_stl",
    "export_obj",
    # ADAPT-042 — vendor turbomachinery formats.
    "export_turbogrid_curve",
    "export_turbogrid_ndf",
    "export_surface_point_cloud",
    "export_cgns",
    # ADAPT-033 — CAD-universal formats (STEP / IGES).
    "CADExportNotAvailable",
    "cad_export_available",
    "export_step",
    "export_iges",
    # W-17 — fluid-volume STEP with named patches.
    "export_fluid_volume_step",
    # Parameter-dict export helpers — library/scripting convenience
    # (raw keys + defaults). The API routers build geometry through the
    # normative candidate merge instead.
    "generate_impeller_glb",
    "generate_impeller_stl",
]


class MeshLOD(Enum):
    """Level-of-detail enumeration.

    The pair is ``(n_meridional, n_blade_to_blade)``; spanwise resolution
    is derived. Vertex counts below are for a canonical 20-blade
    centrifugal impeller without splitters.

    | LOD       | (n_m, n_θ) | V        | Target use         |
    |-----------|------------|----------|--------------------|
    | PREVIEW   | (12, 16)   | ~3 k    | browser preview / drag |
    | STANDARD  | (20, 28)   | ~7 k    | canonical web view |
    | HIGH      | (36, 48)   | ~21 k   | hero render / publication |
    | EXPORT    | (72, 96)   | ~83 k   | STL/STEP for CAM   |
    """

    PREVIEW = "PREVIEW"
    STANDARD = "STANDARD"
    HIGH = "HIGH"
    EXPORT = "EXPORT"


def impeller_mesh(
    geometry: Union[CentrifugalCompressorGeometry, RadialTurbineGeometry],
    lod: MeshLOD = MeshLOD.STANDARD,
    *,
    with_splitter: bool = True,
    with_back_face: bool = True,
    with_shroud: bool = False,
    with_tip_clearance_overlay: bool = False,
) -> trimesh.Trimesh:
    """Generate a photoreal-quality mesh of a centrifugal impeller or radial
    inflow turbine rotor.

    Dispatches on the geometry dataclass type. The returned mesh is a
    `trimesh.Trimesh` carrying:
    - vertices, faces, vertex normals computed
    - PBR titanium material attached
    - all main blades + optional splitter blades (when ``with_splitter``)
    - hub disc surface of revolution
    - optional back face (``with_back_face=True``)
    - optional shroud cup (``with_shroud=True``)
    - optional tip-clearance overlay ring (``with_tip_clearance_overlay``)

    Args:
        geometry: a `CentrifugalCompressorGeometry` (for a CC impeller) or a
            `RadialTurbineGeometry` (for an RIT rotor). Other types raise
            `TypeError`.
        lod: target level of detail. Higher LOD → more triangles, more
            visual fidelity, more wire bytes.
        with_splitter: split the ``blade_count`` budget into half full
            blades and half splitters at half pitch (splitter LE at ~35%
            chord). Only takes effect when ``blade_count`` is even and
            ≥ 8; otherwise all blades render full-length. The TOTAL blade
            count always equals ``blade_count`` — the number the meanline
            correlations were scored with.
        with_back_face: cap the back face of the impeller / rotor disc.
        with_shroud: additionally render the *casing* contour as an open
            surface of revolution over the wheel. Default off: the part
            itself is an open (unshrouded) impeller, and the cup both
            hides the blades in the viewer and leaves non-manifold
            surfaces in STL/STEP exports destined for manufacturing.
        with_tip_clearance_overlay: render a thin clearance band.
    """
    if isinstance(geometry, CentrifugalCompressorGeometry):
        return centrifugal_impeller_mesh(
            geometry,
            lod_key=lod.value,
            with_splitter=with_splitter,
            with_back_face=with_back_face,
            with_shroud=with_shroud,
            with_tip_clearance_overlay=with_tip_clearance_overlay,
        )
    if isinstance(geometry, RadialTurbineGeometry):
        return radial_turbine_mesh(
            geometry,
            lod_key=lod.value,
            with_splitter=with_splitter,
            with_back_face=with_back_face,
            with_shroud=with_shroud,
            with_tip_clearance_overlay=with_tip_clearance_overlay,
        )
    msg = (
        f"impeller_mesh accepts CentrifugalCompressorGeometry or "
        f"RadialTurbineGeometry, got {type(geometry).__name__}"
    )
    raise TypeError(msg)


def volute_mesh(
    geometry: VoluteGeometry,
    lod: MeshLOD = MeshLOD.STANDARD,
) -> trimesh.Trimesh:
    """Generate a mesh for a log-spiral volute / scroll."""
    return volute_mesh_impl(geometry, lod_key=lod.value)


def rotor_shaft_mesh(
    shape: RotorShape,
    lod: MeshLOD = MeshLOD.STANDARD,
) -> trimesh.Trimesh:
    """Generate a mesh of a `RotorShape` (shaft sections + lumped disks)."""
    return rotor_shaft_mesh_impl(shape, lod_key=lod.value)


# ---------------------------------------------------------------------------
# Parameter-dict export helpers
# ---------------------------------------------------------------------------
# Library-level convenience wrappers: build an impeller mesh straight from a
# raw parameter dict (geometry field names, missing keys → AT-100 defaults)
# and serialise it. Scripting/notebook use. The API routers do NOT use
# these — they build geometry through the normative candidate merge
# (`apps/api/routers/_meanline_geom.build_cc_geometry`) so served meshes
# match the candidate's mean-line numbers.
#
# LOD mapping from string keys to MeshLOD enum values:
_LOD_STRING_MAP: dict = {
    "low": MeshLOD.PREVIEW,
    "preview": MeshLOD.PREVIEW,
    "medium": MeshLOD.STANDARD,
    "standard": MeshLOD.STANDARD,
    "hi": MeshLOD.HIGH,
    "high": MeshLOD.HIGH,
    "export": MeshLOD.EXPORT,
}


def generate_impeller_glb(
    params: dict,
    lod: str = "medium",
) -> bytes:
    """Generate a GLB byte string for a centrifugal impeller from a parameter
    dict.

    Library/scripting convenience: calls the full mesh generator at the
    requested LOD and serialises to glTF binary. Missing keys fall back to
    canonical defaults — for candidate-faithful geometry use the API
    routers' normative merge instead.

    Args:
        params: a dict of impeller design-space parameters.  Any missing
            keys fall back to the canonical microturbine-scale defaults
            (AT-100 geometry).  The following keys are recognised:
            ``inducer_hub_radius``, ``inducer_tip_radius``,
            ``impeller_outlet_radius``, ``blade_height_outlet``,
            ``blade_count``, ``beta_2_metal_rad``, ``tip_clearance``.
        lod: level-of-detail string.  Accepted values (case-insensitive):
            ``"low"`` / ``"preview"`` → PREVIEW,
            ``"medium"`` / ``"standard"`` → STANDARD (default),
            ``"hi"`` / ``"high"`` → HIGH,
            ``"export"`` → EXPORT.

    Returns:
        A self-contained ``.glb`` byte string carrying real mesh data with
        a non-empty ``meshes`` array and at least one vertex.

    Raises:
        ValueError: if ``lod`` is not one of the accepted strings.
        ValueError: if the resulting mesh is empty (geometry error).
    """
    import math as _math

    lod_key = lod.lower()
    if lod_key not in _LOD_STRING_MAP:
        raise ValueError(
            f"generate_impeller_glb: unknown lod {lod!r}; "
            f"accepted: {list(_LOD_STRING_MAP)}"
        )
    mesh_lod = _LOD_STRING_MAP[lod_key]

    geometry = CentrifugalCompressorGeometry(
        inducer_hub_radius=float(params.get("inducer_hub_radius", 0.018)),
        inducer_tip_radius=float(params.get("inducer_tip_radius", 0.050)),
        impeller_outlet_radius=float(
            params.get("impeller_outlet_radius", 0.100)
        ),
        blade_height_outlet=float(params.get("blade_height_outlet", 0.012)),
        blade_count=int(params.get("blade_count", 18)),
        beta_2_metal_rad=float(
            params.get("beta_2_metal_rad", _math.pi / 3)
        ),
        tip_clearance=float(params.get("tip_clearance", 0.0005)),
    )
    mesh = impeller_mesh(geometry, lod=mesh_lod, with_splitter=True)
    return export_glb(mesh)


def generate_impeller_stl(
    params: dict,
) -> bytes:
    """Generate a binary STL byte string for a centrifugal impeller from a
    parameter dict.

    Uses EXPORT LOD (highest fidelity) so the file is suitable for CAM /
    3D-printing pipelines that consume STL.

    Args:
        params: same parameter dict as `generate_impeller_glb`.

    Returns:
        A binary STL byte string with a non-zero triangle count.

    Raises:
        ValueError: if the resulting mesh is empty.
    """
    import math as _math

    geometry = CentrifugalCompressorGeometry(
        inducer_hub_radius=float(params.get("inducer_hub_radius", 0.018)),
        inducer_tip_radius=float(params.get("inducer_tip_radius", 0.050)),
        impeller_outlet_radius=float(
            params.get("impeller_outlet_radius", 0.100)
        ),
        blade_height_outlet=float(params.get("blade_height_outlet", 0.012)),
        blade_count=int(params.get("blade_count", 18)),
        beta_2_metal_rad=float(
            params.get("beta_2_metal_rad", _math.pi / 3)
        ),
        tip_clearance=float(params.get("tip_clearance", 0.0005)),
    )
    mesh = impeller_mesh(geometry, lod=MeshLOD.EXPORT, with_splitter=True)
    return export_stl(mesh)
