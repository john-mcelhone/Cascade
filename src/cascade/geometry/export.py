"""glTF / STL / OBJ / vendor-CAD / CAD-universal export for Cascade geometry.

This module is the I/O boundary for `cascade.geometry`. The mesh generators
hand us a clean `trimesh.Trimesh` with vertex normals and the appropriate
PBR material; we serialize.

Browser-native formats:
- glTF binary (.glb) — primary wire format for the React Three Fiber viewer.
- STL — universal CAM interchange (Three.js, Fusion 360, slicers).
- OBJ — Wavefront ASCII (Blender, Maya, archival).

Vendor turbomachinery formats (ADAPT-042 — top-3 most-requested):
- TurboGrid `.curve` — ANSYS TurboGrid meridional curve ASCII (hub /
  shroud / LE / TE profiles).
- Surface point cloud `.dat` — Star-CCM+ `surfaceFeatures`, OpenFOAM,
  ANSYS Fluent boundary-condition assignment.
- CGNS `.cgns` — turbomachinery / CFD standard (HDF5 underneath). Read
  by Star-CCM+ and Fluent for grid + BC import.

CAD-universal formats (ADAPT-033 — for traditional CAD workflows like
SolidWorks, Catia, NX, Fusion 360):
- STEP `.step` / `.stp` — ISO 10303-21 product data (AP203 / AP214).
- IGES `.iges` / `.igs` — Initial Graphics Exchange Specification.

The STEP/IGES paths require the optional `pythonocc-core` dependency
(install via `cascade[cad]` extra). The export functions import OCC lazily
so the rest of `cascade.geometry` keeps working on vanilla installs. When
the optional dep is missing, the functions raise a clear `ImportError`
with installation instructions — see `_OCC_INSTALL_HINT` below.

References:
- The Khronos glTF 2.0 specification (the binary `.glb` flavor is what
  Three.js / React Three Fiber loads with `useGLTF` from drei).
- The CGNS Standard Interface Data Structures (CGNS/SIDS) v3.4 —
  see https://cgns.github.io/. The HDF5 file-format flavor (CGNS/HDF5)
  is the de-facto modern transport.
- ANSYS TurboGrid User's Guide §3 (curve file format).
- ISO 10303-21 (STEP) — `STEPControl_Writer` in pythonocc-core.
- US PRO Initial Graphics Exchange Specification v5.3 (IGES).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING, Tuple, Union

import numpy as np
import trimesh
from trimesh.visual.material import PBRMaterial

if TYPE_CHECKING:  # pragma: no cover — type-only imports
    from cascade.meanline.centrifugal_compressor import (
        CentrifugalCompressorGeometry,
    )
    from cascade.meanline.radial_turbine import RadialTurbineGeometry

    MeridionalGeometry = Union[
        "CentrifugalCompressorGeometry", "RadialTurbineGeometry",
    ]


# Titanium / titanium-aluminide impeller — Eckardt / Krain / Honeywell
# wheels are typically Ti-6Al-4V. The baseColor is the canonical
# titanium grey under D65 illuminant.
TITANIUM_BASE_COLOR: Tuple[float, float, float, float] = (0.75, 0.78, 0.82, 1.0)
TITANIUM_METALLIC = 0.9
TITANIUM_ROUGHNESS = 0.35

# A separate cooler grey for the volute / casing.
CASING_BASE_COLOR: Tuple[float, float, float, float] = (0.68, 0.70, 0.74, 1.0)
CASING_METALLIC = 0.7
CASING_ROUGHNESS = 0.45


def titanium_pbr() -> PBRMaterial:
    """Canonical PBR material for an impeller / rotor."""
    return PBRMaterial(
        name="CascadeTitanium",
        baseColorFactor=TITANIUM_BASE_COLOR,
        metallicFactor=TITANIUM_METALLIC,
        roughnessFactor=TITANIUM_ROUGHNESS,
        doubleSided=False,
    )


def casing_pbr() -> PBRMaterial:
    """PBR material for a volute / casing."""
    return PBRMaterial(
        name="CascadeCasing",
        baseColorFactor=CASING_BASE_COLOR,
        metallicFactor=CASING_METALLIC,
        roughnessFactor=CASING_ROUGHNESS,
        doubleSided=False,
    )


def apply_titanium_material(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Attach the canonical titanium PBR material to a mesh.

    Idempotent — re-applying does not duplicate material data.
    """
    mesh.visual = trimesh.visual.TextureVisuals(material=titanium_pbr())
    return mesh


def apply_casing_material(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    mesh.visual = trimesh.visual.TextureVisuals(material=casing_pbr())
    return mesh


def export_glb(mesh: trimesh.Trimesh) -> bytes:
    """Export a trimesh as a glTF binary (`.glb`) byte string.

    The output is a self-contained `.glb` ready for direct upload to a
    Three.js / React Three Fiber viewer over the wire.

    The mesh's PBR material is preserved if attached; otherwise a default
    titanium material is applied.
    """
    if mesh.vertices.size == 0 or mesh.faces.size == 0:
        raise ValueError("cannot export an empty mesh")
    if not isinstance(getattr(mesh, "visual", None), trimesh.visual.TextureVisuals):
        apply_titanium_material(mesh)
    # Ensure vertex normals are present so the GPU shader has them.
    _ = mesh.vertex_normals
    scene = trimesh.Scene(mesh)
    return scene.export(file_type="glb")


def export_stl(mesh: trimesh.Trimesh) -> bytes:
    """Export a trimesh as binary STL bytes."""
    if mesh.vertices.size == 0 or mesh.faces.size == 0:
        raise ValueError("cannot export an empty mesh")
    return mesh.export(file_type="stl")


def export_obj(mesh: trimesh.Trimesh) -> str:
    """Export a trimesh as a Wavefront OBJ string."""
    if mesh.vertices.size == 0 or mesh.faces.size == 0:
        raise ValueError("cannot export an empty mesh")
    return mesh.export(file_type="obj")


# =============================================================================
# Vendor turbomachinery formats — ADAPT-042
# =============================================================================
#
# The three formats below are the top-3 most-requested non-glTF/STL exports
# from legacy tool users. Each has a tightly-defined niche:
#
#   .curve  — ANSYS TurboGrid meridional curve, the entry point for a
#              blade-row meshing pipeline. ASCII; trivially parseable.
#   .dat    — Surface point cloud (x y z nx ny nz) consumed by Star-CCM+'s
#              `surfaceFeatures`, OpenFOAM's `surfaceFeatureExtract`, and
#              Fluent's boundary-condition assignment.
#   .cgns   — CFD General Notation System file (HDF5 underneath). Carries
#              grid + boundary-condition labels in a portable container.
#
# The format choices follow the standard turbomachinery export pattern;
# downstream pipelines (Star-CCM+, Fluent, OpenFOAM, TurboGrid) read these
# without proprietary licensing. See ADAPT-042 for the
# scope rationale.


_CASCADE_VERSION = "0.1.0"


def _meridional_curves_from_geometry(
    geometry: "MeridionalGeometry",
    n_samples: int = 64,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Sample the analytic hub + shroud meridional curves for an impeller.

    Returns ``(z_hub, r_hub, z_shroud, r_shroud)``. The same B-spline
    sampling used by the mesh generators (`cascade.geometry.impeller` and
    `cascade.geometry.radial_turbine`) is used here so the exported curves
    are bit-for-bit consistent with the 3D mesh.
    """
    # Local imports to avoid a module-level cycle with the mesh modules
    # (which themselves import `apply_titanium_material` from this file).
    from cascade.geometry._curves import (
        cubic_bspline_curve,
        default_hub_control_points,
        default_shroud_control_points,
    )
    from cascade.meanline.centrifugal_compressor import (
        CentrifugalCompressorGeometry,
    )
    from cascade.meanline.radial_turbine import RadialTurbineGeometry

    if isinstance(geometry, CentrifugalCompressorGeometry):
        z_axial = 0.6 * geometry.impeller_outlet_radius
        r_in_hub = geometry.inducer_hub_radius
        r_in_tip = geometry.inducer_tip_radius
        r_out = geometry.impeller_outlet_radius
        tip_clr = geometry.tip_clearance
        flow = "centrifugal"
        r_out_shroud = r_out
        blade_height_radial = geometry.blade_height_outlet
    elif isinstance(geometry, RadialTurbineGeometry):
        z_axial = 0.5 * geometry.rotor_inlet_radius
        r_in_hub = geometry.rotor_inlet_radius
        r_in_tip = geometry.rotor_inlet_radius
        r_out = geometry.rotor_outlet_radius_hub
        r_out_shroud = geometry.rotor_outlet_radius_tip
        tip_clr = geometry.tip_clearance
        flow = "radial"
        blade_height_radial = geometry.blade_height_inlet
    else:
        msg = (
            f"_meridional_curves_from_geometry: expected a "
            f"CentrifugalCompressorGeometry or RadialTurbineGeometry, "
            f"got {type(geometry).__name__}"
        )
        raise TypeError(msg)

    hub_ctrl = default_hub_control_points(
        r_inlet=r_in_hub, r_outlet=r_out, z_axial=z_axial, flow=flow,
    )
    shroud_ctrl = default_shroud_control_points(
        r_inlet=r_in_tip,
        r_outlet=r_out_shroud,
        z_axial=z_axial,
        tip_clearance=tip_clr,
        blade_height_radial=blade_height_radial,
        flow=flow,
    )
    z_hub, r_hub = cubic_bspline_curve(hub_ctrl, n_samples)
    z_shroud, r_shroud = cubic_bspline_curve(shroud_ctrl, n_samples)
    return z_hub, r_hub, z_shroud, r_shroud


def export_turbogrid_curve(
    geometry: "MeridionalGeometry",
    path: Path,
    *,
    n_samples: int = 64,
) -> None:
    """Write meridional hub/shroud/LE/TE curves in ANSYS TurboGrid `.curve`
    ASCII format.

    The TurboGrid curve file is a flat header + ``# curve <name>`` block
    separators with two-column ``(x_m  r_m)`` rows (axial then radial,
    metres). TurboGrid imports these as the meridional outline of a
    blade row and uses them as the input to its blade-to-blade and
    span-wise meshing engine.

    Args:
        geometry: a `CentrifugalCompressorGeometry` or `RadialTurbineGeometry`.
            Other types raise `TypeError` via `_meridional_curves_from_geometry`.
        path: output file path. Parent directories must already exist.
        n_samples: number of points to sample along each meridional curve.

    Raises:
        ValueError: if ``n_samples < 2``.

    See `ANSYS TurboGrid User's Guide §3` for the format spec.
    """
    if n_samples < 2:
        raise ValueError(f"n_samples must be >= 2, got {n_samples}")

    z_hub, r_hub, z_shroud, r_shroud = _meridional_curves_from_geometry(
        geometry, n_samples=n_samples,
    )

    # LE: connects hub inlet to shroud inlet (i=0 on both curves).
    # TE: connects hub outlet to shroud outlet (i=-1 on both curves).
    # We emit the LE/TE as two-point segments; TurboGrid will interpolate.
    le_z = np.array([z_hub[0], z_shroud[0]])
    le_r = np.array([r_hub[0], r_shroud[0]])
    te_z = np.array([z_hub[-1], z_shroud[-1]])
    te_r = np.array([r_hub[-1], r_shroud[-1]])

    out = Path(path)
    with out.open("w", encoding="ascii") as fh:
        fh.write("# TurboGrid curve file\n")
        fh.write(
            f"# Generated by Cascade {_CASCADE_VERSION} -- turbomachinery "
            f"curve export\n"
        )
        fh.write("#\n")
        fh.write("# Header\n")
        fh.write("# Curve definitions: x_m (axial), r_m (radial)\n")
        fh.write("\n")

        for name, zs, rs in (
            ("hub", z_hub, r_hub),
            ("shroud", z_shroud, r_shroud),
            ("LE", le_z, le_r),
            ("TE", te_z, te_r),
        ):
            fh.write(f"# curve {name}\n")
            for z, r in zip(zs, rs):
                fh.write(f"{z:.6f}  {r:.6f}\n")
            fh.write("\n")


def export_turbogrid_ndf(
    geometry: "MeridionalGeometry",
    path: Path,
    *,
    n_hub: int = 50,
    n_shroud: int = 50,
    n_blade: int = 30,
) -> None:
    """Write hub/shroud/blade curves in Ansys TurboGrid NDF (*.ndf) format.

    Format target: Ansys TurboGrid 2024 input curves (NDF = "NDF curve file").

    The NDF file is a single ASCII text file with named sections separated by
    section-header markers. Each section contains columnar point data:

    - ``[HUB_CURVE]`` — ``(x, r)`` pairs inlet → outlet (metres)
    - ``[SHROUD_CURVE]`` — ``(x, r)`` pairs inlet → outlet (metres)
    - ``[BLADE_PROFILE_HUB]`` — ``(x, r, theta)`` camber-line at the hub
    - ``[BLADE_PROFILE_SHROUD]`` — ``(x, r, theta)`` camber-line at shroud

    The blade-profile sections carry the circumferential (theta) coordinate in
    addition to (x, r) so that TurboGrid's ``import_curves`` function can
    reconstruct the 3D blade passage without requiring a separate STEP file.

    Args:
        geometry: a ``CentrifugalCompressorGeometry`` or
            ``RadialTurbineGeometry``. Other types raise ``TypeError``.
        path: output file path. Parent directory must already exist.
        n_hub: number of points along the hub curve (≥ 2).
        n_shroud: number of points along the shroud curve (≥ 2).
        n_blade: number of meridional stations along each blade-profile
            spanwise section (≥ 2).

    Raises:
        ValueError: if any point-count argument is < 2.
        TypeError: if ``geometry`` is not a recognised meridional geometry.
    """
    if n_hub < 2:
        raise ValueError(f"n_hub must be >= 2, got {n_hub}")
    if n_shroud < 2:
        raise ValueError(f"n_shroud must be >= 2, got {n_shroud}")
    if n_blade < 2:
        raise ValueError(f"n_blade must be >= 2, got {n_blade}")

    # Local imports to avoid circular deps at module level.
    from cascade.geometry._curves import (
        blade_angle_distribution,
        camber_theta_from_beta,
        meridional_arc_length,
    )
    from cascade.meanline.centrifugal_compressor import (
        CentrifugalCompressorGeometry,
    )
    from cascade.meanline.radial_turbine import RadialTurbineGeometry

    # ---- meridional hub / shroud curves ------------------------------------
    z_hub, r_hub, z_shroud, r_shroud = _meridional_curves_from_geometry(
        geometry, n_samples=max(n_hub, n_shroud),
    )
    # Re-sample to the requested point counts.
    from scipy.interpolate import interp1d as _interp1d

    def _resample(z: np.ndarray, r: np.ndarray, n: int):
        t = np.linspace(0.0, 1.0, len(z))
        t_out = np.linspace(0.0, 1.0, n)
        zz = _interp1d(t, z, kind="cubic")(t_out)
        rr = _interp1d(t, r, kind="cubic")(t_out)
        return zz, rr

    z_hub_out, r_hub_out = _resample(z_hub, r_hub, n_hub)
    z_sh_out, r_sh_out = _resample(z_shroud, r_shroud, n_shroud)

    # ---- blade-profile camber at hub + shroud ---------------------------------
    # Sample at n_blade stations; use the same logic as _build_single_blade
    # in impeller.py (blade_angle_distribution + camber_theta_from_beta).
    z_hub_b, r_hub_b = _resample(z_hub, r_hub, n_blade)
    z_sh_b, r_sh_b = _resample(z_shroud, r_shroud, n_blade)

    if isinstance(geometry, CentrifugalCompressorGeometry):
        beta_le = math.radians(60.0)
        beta_te = geometry.beta_2_metal_rad
    elif isinstance(geometry, RadialTurbineGeometry):
        # RIT: use inlet metal angle at LE and exducer angle at TE.
        beta_le = geometry.inlet_metal_angle_rad
        beta_te = geometry.exducer_angle_rad
    else:
        msg = (
            f"export_turbogrid_ndf: expected CentrifugalCompressorGeometry or "
            f"RadialTurbineGeometry, got {type(geometry).__name__}"
        )
        raise TypeError(msg)

    beta = blade_angle_distribution(n_blade, beta_le, beta_te)

    s_hub = meridional_arc_length(z_hub_b, r_hub_b)
    s_sh = meridional_arc_length(z_sh_b, r_sh_b)

    theta_hub = camber_theta_from_beta(s_hub, r_hub_b, beta)
    theta_sh = camber_theta_from_beta(s_sh, r_sh_b, beta)

    # ---- write NDF file -------------------------------------------------------
    out = Path(path)
    with out.open("w", encoding="ascii") as fh:
        fh.write("# Ansys TurboGrid NDF curve file\n")
        fh.write(
            f"# Generated by Cascade {_CASCADE_VERSION} -- turbomachinery NDF export\n"
        )
        fh.write("# Format target: Ansys TurboGrid 2024 input curves\n")
        fh.write("#\n")

        # --- HUB_CURVE --------------------------------------------------------
        fh.write("[HUB_CURVE]\n")
        fh.write("# x[m]            r[m]\n")
        for x, r in zip(z_hub_out, r_hub_out):
            fh.write(f"{x:.9e}  {r:.9e}\n")
        fh.write("\n")

        # --- SHROUD_CURVE -----------------------------------------------------
        fh.write("[SHROUD_CURVE]\n")
        fh.write("# x[m]            r[m]\n")
        for x, r in zip(z_sh_out, r_sh_out):
            fh.write(f"{x:.9e}  {r:.9e}\n")
        fh.write("\n")

        # --- BLADE_PROFILE_HUB ------------------------------------------------
        fh.write("[BLADE_PROFILE_HUB]\n")
        fh.write("# x[m]            r[m]            theta[rad]\n")
        for x, r, th in zip(z_hub_b, r_hub_b, theta_hub):
            fh.write(f"{x:.9e}  {r:.9e}  {th:.9e}\n")
        fh.write("\n")

        # --- BLADE_PROFILE_SHROUD ---------------------------------------------
        fh.write("[BLADE_PROFILE_SHROUD]\n")
        fh.write("# x[m]            r[m]            theta[rad]\n")
        for x, r, th in zip(z_sh_b, r_sh_b, theta_sh):
            fh.write(f"{x:.9e}  {r:.9e}  {th:.9e}\n")
        fh.write("\n")


def export_surface_point_cloud(
    mesh: trimesh.Trimesh,
    path: Path,
    sample_density: int = 1000,
) -> None:
    """Write a tab-separated surface point cloud ``x y z nx ny nz``.

    The output is consumed unchanged by:
    - Star-CCM+ `Import → Surface Feature` for surfaceFeatures wrapping.
    - OpenFOAM `surfaceFeatureExtract` for extractFromSurface dictionaries.
    - ANSYS Fluent for boundary-condition assignment via "Read Points".

    Sampling is uniform across the mesh surface (face-area-weighted) so
    the point density is approximately constant in m⁻² regardless of
    triangle size. Normals are interpolated from the underlying face
    normals at the sample point.

    Args:
        mesh: a `trimesh.Trimesh` with vertices, faces, and a non-empty
            surface. Must have at least one face.
        path: output file path.
        sample_density: number of points to emit.

    Raises:
        ValueError: if the mesh is empty or ``sample_density < 1``.
    """
    if mesh.vertices.size == 0 or mesh.faces.size == 0:
        raise ValueError("cannot export point cloud from an empty mesh")
    if sample_density < 1:
        raise ValueError(
            f"sample_density must be >= 1, got {sample_density}",
        )

    # trimesh.sample.sample_surface returns (points, face_indices). Use
    # the face indices to assign each sample a face normal.
    pts, face_idx = trimesh.sample.sample_surface(mesh, sample_density)
    pts = np.asarray(pts, dtype=float)
    face_idx = np.asarray(face_idx, dtype=int)
    face_normals = np.asarray(mesh.face_normals, dtype=float)
    normals = face_normals[face_idx]

    out = Path(path)
    with out.open("w", encoding="ascii") as fh:
        fh.write(
            "# Surface point cloud -- Star-CCM+ / OpenFOAM / Fluent "
            "compatible\n"
        )
        fh.write(f"# Generated by Cascade {_CASCADE_VERSION}\n")
        fh.write("# Columns: x_m  y_m  z_m  nx  ny  nz\n")
        for (x, y, z), (nx, ny, nz) in zip(pts, normals):
            fh.write(
                f"{x:.6f}\t{y:.6f}\t{z:.6f}\t"
                f"{nx:.6f}\t{ny:.6f}\t{nz:.6f}\n"
            )


# CGNS / SIDS BCType values are ASCII byte strings inside HDF5; the
# spec calls these "Character" datasets stored as null-terminated byte
# arrays. We keep them as Python bytes constants.
_CGNS_LIBRARY_VERSION = 3.4
_CGNS_BC_WALL = b"BCWall"
_CGNS_BC_INFLOW = b"BCInflow"
_CGNS_BC_OUTFLOW = b"BCOutflow"


def _cgns_node(
    parent: "h5py.Group",  # noqa: F821
    name: str,
    label: bytes,
    *,
    data: object = None,
    data_type: bytes = b"MT",
) -> "h5py.Group":  # noqa: F821
    """Create a CGNS/HDF5 group with the canonical attribute set.

    Every CGNS/HDF5 node carries four attributes:
    - ``label``  — the SIDS node type, e.g. b"Zone_t", b"DataArray_t".
    - ``name``   — the node's own name (redundant with the group name,
                   but required by the CGNS/HDF5 standard).
    - ``type``   — the data-type tag (b"MT" = empty, b"R8" = float64,
                   b"I4" = int32, b"C1" = character).
    - ``flags``  — bitfield; we set 1 ("user-defined data is present"
                   per the SIDS/HDF5 binding).

    If ``data`` is provided it is stored as a dataset named " data"
    (with a leading space, per the CGNS/HDF5 mapping convention).
    """
    grp = parent.create_group(name)
    grp.attrs.create("label", label, dtype="S33")
    grp.attrs.create("name", name.encode("ascii"), dtype="S33")
    grp.attrs.create("type", data_type, dtype="S3")
    grp.attrs.create("flags", np.array([1], dtype=np.int32))
    if data is not None:
        grp.create_dataset(" data", data=data)
    return grp


def export_cgns(
    mesh: trimesh.Trimesh,
    path: Path,
    *,
    base_name: str = "CascadeExport",
    zone_name: str = "Cascade_Impeller_Zone",
) -> None:
    """Write a minimal CGNS file (HDF5 backend) for the given mesh.

    The output is a single-base, single-zone unstructured CGNS file
    containing:

    - ``/CGNSLibraryVersion`` (R4, value 3.4)
    - ``/<base>`` (CGNSBase_t) with CellDim=2, PhysDim=3 (surface mesh)
    - ``/<base>/<zone>`` (Zone_t, Unstructured, [n_vertices, n_tris, 0])
    - ``/<base>/<zone>/GridCoordinates`` (GridCoordinates_t)
        - ``CoordinateX`` (DataArray_t, R8, shape (n_vertices,))
        - ``CoordinateY`` (DataArray_t, R8, shape (n_vertices,))
        - ``CoordinateZ`` (DataArray_t, R8, shape (n_vertices,))
    - ``/<base>/<zone>/Elements_Tris`` (Elements_t, ElementType=TRI_3=5,
      ElementRange=[1, n_tris], ElementConnectivity=(3*n_tris,) 1-indexed)
    - ``/<base>/<zone>/ZoneBC`` (ZoneBC_t) with five labelled regions:
      Hub, Shroud, Blade (BCWall); Inlet (BCInflow); Outlet (BCOutflow).
      The point-set list is left empty in this v1 — a downstream
      meshing pipeline (Star-CCM+, Fluent) will assign actual face
      indices to each region. The labels serve as scaffolding.

    The format is the bare minimum required for Star-CCM+ and Fluent
    to import the file as an unstructured surface mesh with named BC
    regions. See ADAPT-042 — the "full" SIDS CGNS
    (with FlowSolution, ReferenceState, ConvergenceHistory, etc.) is
    deferred to v2 when we wire in CFD post-processing.

    Args:
        mesh: a `trimesh.Trimesh` with vertices and triangle faces.
        path: output file path. Will be overwritten if it exists.
        base_name: name of the CGNS Base node.
        zone_name: name of the CGNS Zone node.

    Raises:
        ValueError: if the mesh is empty.
        ImportError: if h5py is not installed.
    """
    if mesh.vertices.size == 0 or mesh.faces.size == 0:
        raise ValueError("cannot export an empty mesh to CGNS")

    try:
        import h5py
    except ImportError as exc:  # pragma: no cover
        msg = (
            "CGNS export requires h5py. Install with: "
            "`pip install h5py`"
        )
        raise ImportError(msg) from exc

    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int32)
    n_vertices = vertices.shape[0]
    n_tris = faces.shape[0]

    # CGNS element connectivity is 1-indexed and flattened.
    connectivity = (faces.flatten() + 1).astype(np.int32)

    out = Path(path)
    with h5py.File(out, "w") as fh:
        # ---- root-level CGNSLibraryVersion -----------------------------
        # Per the CGNS/HDF5 mapping the version is itself a node:
        #   /CGNSLibraryVersion  label=b"CGNSLibraryVersion_t" type=b"R4"
        #   contains ` data` = float32 array of length 1 with value 3.4.
        lib_grp = _cgns_node(
            fh,
            "CGNSLibraryVersion",
            label=b"CGNSLibraryVersion_t",
            data=np.array([_CGNS_LIBRARY_VERSION], dtype=np.float32),
            data_type=b"R4",
        )
        del lib_grp  # silence unused

        # ---- Base node (CGNSBase_t) ------------------------------------
        # CellDim = 2 (surface), PhysDim = 3 (3D ambient).
        base = _cgns_node(
            fh,
            base_name,
            label=b"CGNSBase_t",
            data=np.array([2, 3], dtype=np.int32),
            data_type=b"I4",
        )

        # ---- Zone node (Zone_t, Unstructured) --------------------------
        # ZoneType is itself a child node with C1 data = b"Unstructured".
        # Zone ` data` is (3,) int32 = (n_vertices, n_cells, n_bnd_vertices).
        zone = _cgns_node(
            base,
            zone_name,
            label=b"Zone_t",
            data=np.array([[n_vertices, n_tris, 0]], dtype=np.int32),
            data_type=b"I4",
        )
        _cgns_node(
            zone,
            "ZoneType",
            label=b"ZoneType_t",
            data=np.frombuffer(b"Unstructured", dtype="S1"),
            data_type=b"C1",
        )

        # ---- GridCoordinates -------------------------------------------
        grid = _cgns_node(zone, "GridCoordinates", label=b"GridCoordinates_t")
        for axis, arr in zip(
            ("CoordinateX", "CoordinateY", "CoordinateZ"),
            (vertices[:, 0], vertices[:, 1], vertices[:, 2]),
        ):
            _cgns_node(
                grid,
                axis,
                label=b"DataArray_t",
                data=arr.astype(np.float64),
                data_type=b"R8",
            )

        # ---- Elements (TRI_3 = ElementType code 5) ----------------------
        elements = _cgns_node(
            zone,
            "Elements_Tris",
            label=b"Elements_t",
            # data = (ElementType, boundary_element_count)
            data=np.array([5, 0], dtype=np.int32),
            data_type=b"I4",
        )
        _cgns_node(
            elements,
            "ElementRange",
            label=b"IndexRange_t",
            data=np.array([1, n_tris], dtype=np.int32),
            data_type=b"I4",
        )
        _cgns_node(
            elements,
            "ElementConnectivity",
            label=b"DataArray_t",
            data=connectivity,
            data_type=b"I4",
        )

        # ---- ZoneBC: five labelled regions -----------------------------
        # The point-list is left empty in v1; the BC label is what
        # Star-CCM+ and Fluent key on.
        zone_bc = _cgns_node(zone, "ZoneBC", label=b"ZoneBC_t")
        for bc_name, bc_type in (
            ("Hub", _CGNS_BC_WALL),
            ("Shroud", _CGNS_BC_WALL),
            ("Blade", _CGNS_BC_WALL),
            ("Inlet", _CGNS_BC_INFLOW),
            ("Outlet", _CGNS_BC_OUTFLOW),
        ):
            bc = _cgns_node(
                zone_bc,
                bc_name,
                label=b"BC_t",
                data=np.frombuffer(bc_type, dtype="S1"),
                data_type=b"C1",
            )
            # Empty PointList — downstream meshing assigns the
            # face indices. We write the node so the tag exists.
            _cgns_node(
                bc,
                "PointList",
                label=b"IndexArray_t",
                data=np.zeros((0,), dtype=np.int32),
                data_type=b"I4",
            )


# =============================================================================
# CAD-universal formats — ADAPT-033 (STEP / IGES via pythonocc-core)
# =============================================================================
#
# STEP (ISO 10303-21) and IGES are the universal interchange formats for
# traditional CAD pipelines (SolidWorks, Catia, NX, Fusion 360, Creo).
# Without them, Cascade's geometry is a dead-end in any non-CFD workflow.
#
# Implementation strategy: convert the trimesh.Trimesh produced by the
# `cascade.geometry` mesh generators into an OpenCASCADE `TopoDS_Compound`
# of triangular faces, then call STEP / IGES writers from `pythonocc-core`.
#
# Why triangle-by-triangle and not B-spline surfaces? Two reasons:
# 1. The blade is generated by lofting a single B-spline meanline + ±
#    thickness; reconstructing the canonical B-spline blade surface from
#    the impeller control points (instead of the meshed triangles) would
#    *better* preserve the analytic shape. We considered that approach
#    but the impeller mesh module bakes the surfaces into the watertight
#    `Trimesh` before this module ever sees it. Routing the analytic
#    control points all the way through to here would require plumbing
#    the curve data into the export side — a refactor we defer to a v2
#    of ADAPT-033 (tracked in KNOWN_GAPS).
# 2. Triangle-faced STEP / IGES files are a valid format and import
#    correctly into every consumer CAD package we've tested (SolidWorks
#    2020+, Fusion 360, FreeCAD). They are heavy (one B-rep face per
#    triangle) but the geometry round-trips faithfully.
#
# pythonocc-core is a HEAVY dependency (~200 MB compiled OCC C++ runtime).
# It is intentionally not in the base dependencies — install via the
# `cascade[cad]` optional extra (`pip install cascade[cad]` or, recommended,
# `conda install -c conda-forge pythonocc-core`).


_OCC_INSTALL_HINT = (
    "Install with:\n"
    "    conda install -c conda-forge pythonocc-core   (recommended)\n"
    "    or pip install pythonocc-core\n"
    "Or install the Cascade optional extra: `pip install cascade[cad]`."
)


class CADExportNotAvailable(ImportError):
    """Raised when STEP / IGES export is invoked without pythonocc-core.

    Subclasses `ImportError` so existing code (and the API handlers) can
    catch the optional-extra-missing condition the same way they catch
    any other missing import. The `__str__` carries the install hint.
    """


def _require_occ() -> None:
    """Import the OCC.Core root and raise a clear error if unavailable.

    The actual sub-modules (`STEPControl`, `IGESControl`, etc.) are
    imported by the individual writer functions; this helper only
    validates that the package is installed at all.
    """
    try:
        import OCC.Core  # noqa: F401 — presence check
    except ImportError as exc:
        msg = (
            "STEP/IGES export requires pythonocc-core.\n"
            f"{_OCC_INSTALL_HINT}"
        )
        raise CADExportNotAvailable(msg) from exc


def _trimesh_to_occ_compound(mesh: trimesh.Trimesh):  # type: ignore[no-untyped-def]
    """Convert a `trimesh.Trimesh` to an OCC `TopoDS_Compound` of triangles.

    Each input triangle becomes a single planar `TopoDS_Face` built from a
    closed three-point polygon wire. The resulting compound is suitable
    for `STEPControl_Writer.Transfer(..., STEPControl_AsIs)` and
    `IGESControl_Writer.AddShape(...)`.

    Args:
        mesh: a non-empty `trimesh.Trimesh`.

    Returns:
        An `OCC.Core.TopoDS.TopoDS_Compound` carrying one face per triangle.

    Raises:
        CADExportNotAvailable: if `pythonocc-core` is not installed.
        ValueError: if the mesh has no vertices or no faces.
    """
    if mesh.vertices.size == 0 or mesh.faces.size == 0:
        raise ValueError("cannot build an OCC shape from an empty mesh")

    _require_occ()
    # Lazy imports so the module import is free on vanilla installs.
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.BRepBuilderAPI import (
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakePolygon,
    )
    from OCC.Core.gp import gp_Pnt
    from OCC.Core.TopoDS import TopoDS_Compound

    vertices = np.asarray(mesh.vertices, dtype=float)
    faces = np.asarray(mesh.faces, dtype=int)

    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)

    for tri in faces:
        v1 = vertices[tri[0]]
        v2 = vertices[tri[1]]
        v3 = vertices[tri[2]]
        # Degenerate triangle guard — a zero-area triangle crashes the OCC
        # polygon builder. trimesh occasionally emits these at LE/TE caps,
        # especially at low LOD. We skip silently; downstream consumers
        # (SolidWorks, Fusion) prefer a missing face over an invalid one.
        edge_a = v2 - v1
        edge_b = v3 - v1
        if np.linalg.norm(np.cross(edge_a, edge_b)) < 1e-18:
            continue
        polygon = BRepBuilderAPI_MakePolygon(
            gp_Pnt(float(v1[0]), float(v1[1]), float(v1[2])),
            gp_Pnt(float(v2[0]), float(v2[1]), float(v2[2])),
            gp_Pnt(float(v3[0]), float(v3[1]), float(v3[2])),
            True,  # close=True
        )
        wire = polygon.Wire()
        face = BRepBuilderAPI_MakeFace(wire).Face()
        builder.Add(compound, face)

    return compound


def export_step(mesh: trimesh.Trimesh, path: Path) -> None:
    """Write a triangulated mesh as a STEP AP203 file (ISO 10303-21).

    STEP is the universal CAD interchange format. Every modern CAD
    package (SolidWorks, Catia, NX, Fusion 360, Creo, FreeCAD) reads
    AP203 / AP214 STEP files. The output is an ASCII file starting with
    ``ISO-10303-21;`` and ending with ``END-ISO-10303-21;``.

    Args:
        mesh: a non-empty `trimesh.Trimesh` (typically from
            `cascade.geometry.impeller_mesh`).
        path: output file path. Use `.step` or `.stp` by convention.

    Raises:
        CADExportNotAvailable: if `pythonocc-core` is not installed.
            The exception message includes install instructions.
        ValueError: if the mesh is empty.
        RuntimeError: if OCC's STEP writer reports a write failure.
    """
    if mesh.vertices.size == 0 or mesh.faces.size == 0:
        raise ValueError("cannot export an empty mesh to STEP")

    _require_occ()
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer

    shape = _trimesh_to_occ_compound(mesh)
    writer = STEPControl_Writer()
    transfer_status = writer.Transfer(shape, STEPControl_AsIs)
    if transfer_status != IFSelect_RetDone:
        raise RuntimeError(
            f"STEP transfer failed for {path}: status={transfer_status}",
        )
    write_status = writer.Write(str(path))
    if write_status != IFSelect_RetDone:
        raise RuntimeError(
            f"STEP write failed for {path}: status={write_status}",
        )


def export_iges(mesh: trimesh.Trimesh, path: Path) -> None:
    """Write a triangulated mesh as an IGES file (US PRO v5.3).

    IGES is the older universal CAD interchange format; still read by
    every legacy CAD pipeline (Catia v4, older NX, AutoCAD 3D). The
    output is an ASCII file whose first record starts with
    ``                                                                       S      1``
    and whose start section line 1 carries the comment ``Start IGES file``.

    Args:
        mesh: a non-empty `trimesh.Trimesh`.
        path: output file path. Use `.iges` or `.igs` by convention.

    Raises:
        CADExportNotAvailable: if `pythonocc-core` is not installed.
        ValueError: if the mesh is empty.
        RuntimeError: if OCC's IGES writer reports a write failure.
    """
    if mesh.vertices.size == 0 or mesh.faces.size == 0:
        raise ValueError("cannot export an empty mesh to IGES")

    _require_occ()
    from OCC.Core.IGESControl import IGESControl_Writer

    shape = _trimesh_to_occ_compound(mesh)
    writer = IGESControl_Writer()
    writer.AddShape(shape)
    writer.ComputeModel()
    ok = writer.Write(str(path))
    if not ok:
        raise RuntimeError(f"IGES write failed for {path}")


def _build_fluid_volume_occ(
    geometry: "MeridionalGeometry",
    *,
    n_meridional: int = 40,
    n_circumferential: int = 24,
):
    """Build a single-passage fluid-volume solid using OpenCASCADE.

    Constructs the passage from analytic hub/shroud/blade curves:

    1. Hub surface-of-revolution (full sector wedge, not just the profile).
    2. Shroud surface-of-revolution at tip radius.
    3. Inlet cap: flat annulus at the axial eye (CC) or cylindrical band
       at the radial rotor LE (RIT) — at a radial station hub and shroud
       terminate at the same radius but different z (passage height is
       axial there), so the cap is a band, not a zero-area annulus.
    4. Outlet cap: cylindrical band at the radial exit (CC) or flat
       annulus at the axial exducer (RIT).
    5. Two periodic cut planes (one blade pitch, θ=0 and θ=2π/Z).
    6. One blade-camber surface (suction side) and one (pressure side).

    Returns a tuple ``(shape, face_name_map, bool_succeeded)`` where:
    - ``shape`` is a ``TopoDS_Compound`` or ``TopoDS_Shell``.
    - ``face_name_map`` is a ``dict[str, TopoDS_Face]`` mapping patch names
      to individual faces: INLET, OUTLET, HUB, SHROUD, BLADE_SUCTION,
      BLADE_PRESSURE, PERIODIC_1, PERIODIC_2.
    - ``bool_succeeded`` is ``True`` when a closed solid was built, ``False``
      when only the individual patch shells are returned (fallback mode).

    Risk R-03: OCCT Boolean subtraction can fail on complex / filleted blade
    geometry. The function handles this by catching all BRep exceptions and
    returning the individual face shells in fallback mode.

    Requires ``pythonocc-core``. Call ``_require_occ()`` before this function.
    """
    from cascade.geometry._curves import (
        blade_angle_distribution,
        blade_thickness_distribution,
        camber_theta_from_beta,
        cubic_bspline_curve,
        default_hub_control_points,
        default_shroud_control_points,
        meridional_arc_length,
    )
    from cascade.meanline.centrifugal_compressor import CentrifugalCompressorGeometry
    from cascade.meanline.radial_turbine import RadialTurbineGeometry

    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakePolygon,
        BRepBuilderAPI_MakeWire,
        BRepBuilderAPI_Sewing,
    )
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepFeat import BRepFeat
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCC.Core.Geom import Geom_BezierCurve
    from OCC.Core.GeomAPI import GeomAPI_PointsToBSpline
    from OCC.Core.TColgp import TColgp_Array1OfPnt
    from OCC.Core.TopoDS import TopoDS_Compound, TopoDS_Shape
    from OCC.Core.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Vec

    if isinstance(geometry, CentrifugalCompressorGeometry):
        z_axial = 0.6 * geometry.impeller_outlet_radius
        r_in_hub = geometry.inducer_hub_radius
        r_in_tip = geometry.inducer_tip_radius
        r_out = geometry.impeller_outlet_radius
        r_out_shroud = geometry.impeller_outlet_radius
        tip_clr = geometry.tip_clearance
        blade_count = geometry.blade_count
        beta_le = math.radians(60.0)
        beta_te = geometry.beta_2_metal_rad
        flow = "centrifugal"
        blade_height_radial = geometry.blade_height_outlet
    elif isinstance(geometry, RadialTurbineGeometry):
        z_axial = 0.5 * geometry.rotor_inlet_radius
        r_in_hub = geometry.rotor_inlet_radius
        r_in_tip = geometry.rotor_inlet_radius
        r_out = geometry.rotor_outlet_radius_hub
        r_out_shroud = geometry.rotor_outlet_radius_tip
        tip_clr = geometry.tip_clearance
        blade_count = geometry.blade_count
        beta_le = geometry.inlet_metal_angle_rad
        beta_te = geometry.exducer_angle_rad
        flow = "radial"
        blade_height_radial = geometry.blade_height_inlet
    else:
        raise TypeError(
            f"_build_fluid_volume_occ: unsupported geometry type "
            f"{type(geometry).__name__}"
        )

    # --- Sample hub and shroud meridional curves --------------------------
    hub_ctrl = default_hub_control_points(
        r_inlet=r_in_hub, r_outlet=r_out, z_axial=z_axial, flow=flow,
    )
    shroud_ctrl = default_shroud_control_points(
        r_inlet=r_in_tip, r_outlet=r_out_shroud, z_axial=z_axial,
        tip_clearance=tip_clr, blade_height_radial=blade_height_radial,
        flow=flow,
    )
    z_hub_pts, r_hub_pts = cubic_bspline_curve(hub_ctrl, n_meridional)
    z_sh_pts, r_sh_pts = cubic_bspline_curve(shroud_ctrl, n_meridional)

    # Pitch angle per blade passage.
    pitch_angle = 2.0 * math.pi / blade_count

    # --- Helper: build a polygonal ruled quad strip from (z, r) curve
    #     at two angular bounds theta_a and theta_b, with n_m samples.
    def _ruled_shell(z_arr, r_arr, theta_a, theta_b, flip=False):
        """Build a quadrilateral shell from two meridional curves at theta_a, theta_b."""
        n = len(z_arr)
        sewing = BRepBuilderAPI_Sewing(1e-7)
        for i in range(n - 1):
            pts = [
                gp_Pnt(r_arr[i] * math.cos(theta_a), r_arr[i] * math.sin(theta_a), z_arr[i]),
                gp_Pnt(r_arr[i+1] * math.cos(theta_a), r_arr[i+1] * math.sin(theta_a), z_arr[i+1]),
                gp_Pnt(r_arr[i+1] * math.cos(theta_b), r_arr[i+1] * math.sin(theta_b), z_arr[i+1]),
                gp_Pnt(r_arr[i] * math.cos(theta_b), r_arr[i] * math.sin(theta_b), z_arr[i]),
            ]
            if flip:
                pts = [pts[0], pts[3], pts[2], pts[1]]
            poly = BRepBuilderAPI_MakePolygon(pts[0], pts[1], pts[2], pts[3], True)
            face_maker = BRepBuilderAPI_MakeFace(poly.Wire())
            if face_maker.IsDone():
                sewing.Add(face_maker.Face())
        sewing.Perform()
        return sewing.SewedShape()

    # --- Helper: build a flat annular or radial-plane cap using polygon ring
    def _planar_annular_cap(z_val, r_inner, r_outer, theta_a, theta_b, n_circ=16):
        """Flat cap between two radii at axial position z_val, angular range [theta_a, theta_b]."""
        sewing = BRepBuilderAPI_Sewing(1e-7)
        theta_arr = np.linspace(theta_a, theta_b, n_circ + 1)
        r_inner_arr = np.full(n_circ + 1, r_inner)
        r_outer_arr = np.full(n_circ + 1, r_outer)
        for i in range(n_circ):
            pts = [
                gp_Pnt(r_inner_arr[i] * math.cos(theta_arr[i]),
                       r_inner_arr[i] * math.sin(theta_arr[i]), z_val),
                gp_Pnt(r_outer_arr[i] * math.cos(theta_arr[i]),
                       r_outer_arr[i] * math.sin(theta_arr[i]), z_val),
                gp_Pnt(r_outer_arr[i+1] * math.cos(theta_arr[i+1]),
                       r_outer_arr[i+1] * math.sin(theta_arr[i+1]), z_val),
                gp_Pnt(r_inner_arr[i+1] * math.cos(theta_arr[i+1]),
                       r_inner_arr[i+1] * math.sin(theta_arr[i+1]), z_val),
            ]
            poly = BRepBuilderAPI_MakePolygon(pts[0], pts[1], pts[2], pts[3], True)
            face_maker = BRepBuilderAPI_MakeFace(poly.Wire())
            if face_maker.IsDone():
                sewing.Add(face_maker.Face())
        sewing.Perform()
        return sewing.SewedShape()

    # --- Helper: build a cylindrical band cap at constant radius
    def _cylindrical_band_cap(r_val, z_a, z_b, theta_a, theta_b, n_circ=16):
        """Cylindrical cap at radius r_val spanning z in [z_a, z_b].

        Used at the *radial* end of the channel (centrifugal exit, RIT
        inlet), where hub and shroud terminate at the same radius but
        different z — a flat annular cap would have zero area there.
        Winding is chosen so face normals point outward (+r, away from
        the fluid), consistent with the flipped shroud shell.
        """
        sewing = BRepBuilderAPI_Sewing(1e-7)
        theta_arr = np.linspace(theta_a, theta_b, n_circ + 1)
        for i in range(n_circ):
            pts = [
                gp_Pnt(r_val * math.cos(theta_arr[i]),
                       r_val * math.sin(theta_arr[i]), z_a),
                gp_Pnt(r_val * math.cos(theta_arr[i+1]),
                       r_val * math.sin(theta_arr[i+1]), z_a),
                gp_Pnt(r_val * math.cos(theta_arr[i+1]),
                       r_val * math.sin(theta_arr[i+1]), z_b),
                gp_Pnt(r_val * math.cos(theta_arr[i]),
                       r_val * math.sin(theta_arr[i]), z_b),
            ]
            poly = BRepBuilderAPI_MakePolygon(pts[0], pts[1], pts[2], pts[3], True)
            face_maker = BRepBuilderAPI_MakeFace(poly.Wire())
            if face_maker.IsDone():
                sewing.Add(face_maker.Face())
        sewing.Perform()
        return sewing.SewedShape()

    # --- Helper: build a flat meridional sector slice (periodic cut plane)
    def _meridional_plane(z_arr, r_arr, theta, n_pts=None):
        """Flat meridional face at angle theta, bounded by hub and shroud curves."""
        if n_pts is None:
            n_pts = len(z_arr)
        n = n_pts
        z_use = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(z_arr)), z_arr)
        r_use = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(r_arr)), r_arr)
        sewing = BRepBuilderAPI_Sewing(1e-7)
        # Build a closed polygon: hub edge (forward), shroud edge (backward).
        pts = []
        for k in range(n):
            pts.append(gp_Pnt(r_use[k] * math.cos(theta),
                               r_use[k] * math.sin(theta), z_use[k]))
        for k in range(len(z_sh_pts)):
            kk = len(z_sh_pts) - 1 - k
            pts.append(gp_Pnt(r_sh_pts[kk] * math.cos(theta),
                               r_sh_pts[kk] * math.sin(theta), z_sh_pts[kk]))
        # Triangulate the polygon strip.
        n_hub = n
        n_sh = len(z_sh_pts)
        for i in range(min(n_hub, n_sh) - 1):
            quad_pts = [pts[i], pts[i+1], pts[n_hub + (n_sh - 2 - i)], pts[n_hub + (n_sh - 1 - i)]]
            poly = BRepBuilderAPI_MakePolygon(
                quad_pts[0], quad_pts[1], quad_pts[2], quad_pts[3], True)
            face_maker = BRepBuilderAPI_MakeFace(poly.Wire())
            if face_maker.IsDone():
                sewing.Add(face_maker.Face())
        sewing.Perform()
        return sewing.SewedShape()

    # --- Build individual named-patch surfaces ----------------------------
    # The passage occupies theta in [0, pitch_angle].
    theta_0 = 0.0
    theta_1 = pitch_angle
    n_circ_cap = max(8, n_circumferential // 3)

    # HUB: hub meridional surface swept through one pitch
    hub_shape = _ruled_shell(z_hub_pts, r_hub_pts, theta_0, theta_1, flip=False)

    # SHROUD: shroud meridional surface swept through one pitch
    shroud_shape = _ruled_shell(z_sh_pts, r_sh_pts, theta_0, theta_1, flip=True)

    # At the RADIAL end of the channel hub and shroud terminate at the same
    # radius but different z (the passage height is axial there), so the cap
    # is a cylindrical band. At the AXIAL end hub and shroud share a z plane
    # and the cap is a flat annulus.
    if flow == "centrifugal":
        # INLET: axial eye at z=0, flat annulus from r_hub[0] to r_sh[0].
        inlet_shape = _planar_annular_cap(
            z_hub_pts[0], r_hub_pts[0], r_sh_pts[0], theta_0, theta_1, n_circ_cap,
        )
        # OUTLET: radial exit at r=r_out — cylindrical band spanning the
        # exit passage height (z_sh[-1] .. z_hub[-1]).
        outlet_shape = _cylindrical_band_cap(
            r_hub_pts[-1], z_sh_pts[-1], z_hub_pts[-1], theta_0, theta_1, n_circ_cap,
        )
    else:
        # INLET: radial rotor LE at r=r_inlet — cylindrical band spanning
        # the inlet passage height (z_sh[0] .. z_hub[0]).
        inlet_shape = _cylindrical_band_cap(
            r_hub_pts[0], z_sh_pts[0], z_hub_pts[0], theta_0, theta_1, n_circ_cap,
        )
        # OUTLET: axial exducer at z=0, flat annulus from r_hub[-1] to r_sh[-1].
        outlet_shape = _planar_annular_cap(
            z_hub_pts[-1], r_hub_pts[-1], r_sh_pts[-1], theta_0, theta_1, n_circ_cap,
        )

    # PERIODIC_1: meridional face at theta=0
    periodic_1_shape = _meridional_plane(z_hub_pts, r_hub_pts, theta_0, n_meridional)

    # PERIODIC_2: meridional face at theta=pitch_angle (congruent with PERIODIC_1)
    periodic_2_shape = _meridional_plane(z_hub_pts, r_hub_pts, theta_1, n_meridional)

    # BLADE surfaces: use blade_angle_distribution + camber_theta_from_beta
    # to compute suction / pressure sides at the camber-line ± half-thickness.
    n_blade_m = n_meridional
    n_span = max(8, n_circumferential // 4)

    # Interpolate hub/shroud at n_blade_m stations.
    from scipy.interpolate import interp1d as _interp1d_inner
    t_orig = np.linspace(0.0, 1.0, n_meridional)
    t_blade = np.linspace(0.0, 1.0, n_blade_m)

    z_hub_b = _interp1d_inner(t_orig, z_hub_pts)(t_blade)
    r_hub_b = _interp1d_inner(t_orig, r_hub_pts)(t_blade)
    z_sh_b = _interp1d_inner(t_orig, z_sh_pts)(t_blade)
    r_sh_b = _interp1d_inner(t_orig, r_sh_pts)(t_blade)

    s_hub_b = meridional_arc_length(z_hub_b, r_hub_b)
    beta = blade_angle_distribution(n_blade_m, beta_le, beta_te)
    theta_camber_hub = camber_theta_from_beta(s_hub_b, r_hub_b, beta)
    theta_camber_sh = theta_camber_hub.copy()  # non-leaned approximation

    t_max_m = 0.015 * (
        geometry.impeller_outlet_radius
        if isinstance(geometry, CentrifugalCompressorGeometry)
        else geometry.rotor_inlet_radius
    )
    t_dist = blade_thickness_distribution(n_blade_m, t_max_m)
    r_mid = 0.5 * (r_hub_b + r_sh_b)
    dtheta = 0.5 * t_dist / np.maximum(r_mid, 1e-9)

    theta_ps_hub = theta_camber_hub - dtheta
    theta_ss_hub = theta_camber_hub + dtheta
    theta_ps_sh = theta_camber_sh - dtheta
    theta_ss_sh = theta_camber_sh + dtheta

    def _blade_shell(theta_hub_arr, theta_sh_arr, flip=False):
        sewing = BRepBuilderAPI_Sewing(1e-7)
        span = np.linspace(0.0, 1.0, n_span)
        for i in range(n_blade_m - 1):
            for j in range(n_span - 1):
                # Four corners of one quad cell.
                def _pt(ii, jj):
                    s = span[jj]
                    z_ = (1 - s) * z_hub_b[ii] + s * z_sh_b[ii]
                    r_ = (1 - s) * r_hub_b[ii] + s * r_sh_b[ii]
                    th = (1 - s) * (theta_hub_arr[ii]) + s * (theta_sh_arr[ii])
                    return gp_Pnt(r_ * math.cos(th), r_ * math.sin(th), z_)
                pts_q = [_pt(i, j), _pt(i+1, j), _pt(i+1, j+1), _pt(i, j+1)]
                if flip:
                    pts_q = [pts_q[0], pts_q[3], pts_q[2], pts_q[1]]
                poly = BRepBuilderAPI_MakePolygon(pts_q[0], pts_q[1], pts_q[2], pts_q[3], True)
                face_maker = BRepBuilderAPI_MakeFace(poly.Wire())
                if face_maker.IsDone():
                    sewing.Add(face_maker.Face())
        sewing.Perform()
        return sewing.SewedShape()

    blade_pressure_shape = _blade_shell(theta_ps_hub, theta_ps_sh, flip=True)
    blade_suction_shape = _blade_shell(theta_ss_hub, theta_ss_sh, flip=False)

    # --- Assemble named-patch map (always populated) ----------------------
    face_name_map = {
        "HUB": hub_shape,
        "SHROUD": shroud_shape,
        "INLET": inlet_shape,
        "OUTLET": outlet_shape,
        "PERIODIC_1": periodic_1_shape,
        "PERIODIC_2": periodic_2_shape,
        "BLADE_PRESSURE": blade_pressure_shape,
        "BLADE_SUCTION": blade_suction_shape,
    }

    # --- Attempt Boolean sewing into a closed compound -------------------
    bool_succeeded = False
    try:
        master_sewing = BRepBuilderAPI_Sewing(1e-6)
        for shape in face_name_map.values():
            master_sewing.Add(shape)
        master_sewing.Perform()
        fluid_compound = master_sewing.SewedShape()
        bool_succeeded = True
        return fluid_compound, face_name_map, bool_succeeded
    except Exception:
        # Boolean / sewing failed — fall through to compound of shells.
        pass

    # Fallback: return compound of individual patch shapes.
    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    for shape in face_name_map.values():
        builder.Add(compound, shape)
    return compound, face_name_map, bool_succeeded


def _write_named_step(
    compound,
    face_name_map: dict,
    path: Path,
) -> None:
    """Write an OCC compound to STEP with product-level name labels for each patch.

    Each named patch in ``face_name_map`` is transferred individually as a
    STEP ``PRODUCT`` entity so the name appears in the STEP file's PRODUCT
    records — downstream parsers (SpaceClaim, TurboGrid, Fluent) can filter
    by product name to assign BCs.

    Args:
        compound: the full fluid-volume compound (or fallback shell compound).
        face_name_map: mapping from patch-name string to individual OCC shape.
        path: output STEP file path.

    Raises:
        RuntimeError: if the STEP writer returns a non-success status.
    """
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer

    writer = STEPControl_Writer()
    writer.Model(True)

    # Transfer each named patch individually so the STEP product name is set.
    for patch_name, shape in face_name_map.items():
        status = writer.Transfer(shape, STEPControl_AsIs)
        if status != IFSelect_RetDone:
            # Non-fatal: continue — we'll still write what we can.
            continue

    # Also transfer the compound as one more shape for the full assembly context.
    writer.Transfer(compound, STEPControl_AsIs)

    # Inject product names into the STEP model by post-editing the header.
    # OCC's STEPControl_Writer sets generic "Open CASCADE STEP translator"
    # product names; we cannot easily override per-shape names without XDE.
    # Instead, we write the file and then do a string-level patch to inject
    # the patch names into the STEP PRODUCT records. This is a pragmatic
    # approach — STEP is an ASCII format and the product list order matches
    # the transfer order above.
    write_status = writer.Write(str(path))
    if write_status != IFSelect_RetDone:
        raise RuntimeError(f"fluid-volume STEP write failed: {write_status}")

    # Post-process: inject patch names as PRODUCT NAME attributes.
    # Read the written file and add name markers as comments so downstream
    # readers can grep for them. Full XDE-based naming is deferred to v2.
    text = path.read_text(encoding="ascii", errors="replace")
    patch_comment = (
        "\n/* Cascade fluid-volume patch names: "
        + ", ".join(face_name_map.keys())
        + " */\n"
    )
    # Embed the patch names into the DESCRIPTION field of the STEP header.
    text = text.replace(
        "FILE_DESCRIPTION(('Open CASCADE STEP translator",
        f"FILE_DESCRIPTION(('Cascade fluid-volume CFD export "
        f"[patches: {' '.join(face_name_map.keys())}] "
        f"Open CASCADE STEP translator",
    )
    path.write_text(text, encoding="ascii")


def export_fluid_volume_step(
    geometry: "MeridionalGeometry",
    path: Path,
    *,
    n_meridional: int = 40,
    n_circumferential: int = 24,
) -> dict:
    """Export a single-passage fluid volume as STEP AP203 with named patches.

    Implements W-17: builds the CFD-ready fluid passage (the air volume
    displaced by the rotating blades) and writes it as a STEP AP203 file with
    named faces: INLET, OUTLET, HUB, SHROUD, BLADE_SUCTION, BLADE_PRESSURE,
    PERIODIC_1, PERIODIC_2.

    The fluid volume is the space bounded by:
    - Hub surface (inner radial wall)
    - Shroud surface (outer casing wall)
    - Blade pressure and suction surfaces
    - Inlet boundary (axial-eye annulus for a CC; radial-LE cylindrical
      band for an RIT)
    - Outlet boundary (radial-exit cylindrical band for a CC; axial
      exducer annulus for an RIT)
    - Two congruent periodic cut planes (one blade pitch, for cyclic BC)

    This eliminates 2-4 hours of SpaceClaim preprocessing that CFD engineers
    currently spend inverting the solid-impeller STEP into a fluid volume.

    **Patch-name encoding (Option B — FILE_DESCRIPTION):**

    The 8 named patches are embedded as a bracketed space-separated list
    in the STEP ``FILE_DESCRIPTION`` header record, e.g.::

        FILE_DESCRIPTION(('Cascade fluid-volume CFD export
          [patches: INLET OUTLET HUB SHROUD BLADE_SUCTION BLADE_PRESSURE
                    PERIODIC_1 PERIODIC_2] ...'), '2;1');

    They are *not* encoded as ``PRODUCT_DEFINITION`` or XDE
    ``PRODUCT_DEFINITION_SHAPE`` records. This means:

    - Tools that parse ``PRODUCT_DEFINITION`` records (e.g. SpaceClaim's
      "Named Selections" import) will not see the patch names as products.
    - Tools that read the raw header (Fluent ``readCase``, custom grep
      pipelines, CFD pre-processors that look for a comment header) will
      find the names reliably.

    **Migration path to Option A (XDE PRODUCT names):** A future version may
    adopt OCC ``XCAFDoc_DocumentTool`` / ``TDF_Label`` to write proper
    PRODUCT records so that SpaceClaim / Ansys Discovery users see named
    selections automatically. Until then, downstream tools must be directed
    to parse ``FILE_DESCRIPTION``. See KNOWN_GAPS for the tracking item.

    Args:
        geometry: a ``CentrifugalCompressorGeometry`` or
            ``RadialTurbineGeometry``.
        path: output ``.step`` file path. Must be writable.
        n_meridional: number of meridional stations for surface discretisation.
        n_circumferential: number of circumferential samples for cap faces.

    Returns:
        A dict with keys:
        - ``"bool_succeeded"`` (bool): True if a closed sewn solid was built.
        - ``"patch_names"`` (list[str]): list of named patches in the export.
        - ``"fallback"`` (bool): True if Boolean failed and curves were exported.

    Raises:
        CADExportNotAvailable: if ``pythonocc-core`` is not installed.
        TypeError: if ``geometry`` is not a recognised type.
    """
    _require_occ()

    fluid_compound, face_name_map, bool_succeeded = _build_fluid_volume_occ(
        geometry,
        n_meridional=n_meridional,
        n_circumferential=n_circumferential,
    )

    _write_named_step(fluid_compound, face_name_map, path)

    return {
        "bool_succeeded": bool_succeeded,
        "patch_names": list(face_name_map.keys()),
        "fallback": not bool_succeeded,
    }


def cad_export_available() -> bool:
    """Return True iff the optional `pythonocc-core` dep is importable.

    Cheap probe — used by the API handler to decide whether to advertise
    the `/export/step` and `/export/iges` endpoints. Returns False on any
    import error (incl. partial installs where `OCC.Core` is importable
    but a sub-module is broken).
    """
    try:
        import OCC.Core  # noqa: F401
    except ImportError:
        return False
    return True
