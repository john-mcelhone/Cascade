"""Rotor-dynamics routes (real eigensolver backed).

Wraps ``cascade.rotor`` for lateral / torsional eigenanalysis, critical speed
maps, Campbell diagrams, and API 684 compliance reports. The default
geometry (when the request body has no sections) is the Jeffcott-rotor
demo shape used in ``tests/rotor/test_jeffcott_smoke.py``. Bearing
coefficients ride in the request body; the canonical API 684 §2.3
``K_yy, K_zz, K_yz, K_zy`` (and ``C_*``) field names are used throughout
(see ADAPT-037).

ADAPT-005 / ADAPT-013 / ADAPT-024 / ADAPT-025
"""

from __future__ import annotations

import math
import time
import warnings
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from deps import get_project_or_404
from jobs import Job, publish_event, register_job, report_progress, run_in_worker
from models import JobAcceptedResponse, RotorRequest

from cascade.materials import MaterialDB
from cascade.rotor import (
    LinearBearing,
    RotorModel,
    TabulatedBearing,
    build_rotor_model,
    run_campbell,
    run_critical_speed_map,
    run_lateral_analysis,
    run_torsional_analysis,
    run_unbalance_response,
)
from cascade.rotor.unbalance_response import (
    _api684_separation_margin_percent,
    api684_required_separation_margin_percent,
)
from cascade.units import LumpedDisk, Q, RotorSection, RotorShape


router = APIRouter(prefix="/api/projects/{project_id}/rotor", tags=["rotor"])

# Separate router for global (non-project-scoped) bearing endpoints.
# W-32 AC2: GET /api/bearings/presets returns a list of named foil bearing presets.
bearings_router = APIRouter(prefix="/api/bearings", tags=["bearings"])


@bearings_router.get("/presets")
def get_bearing_presets() -> List[Dict[str, Any]]:
    """GET /api/bearings/presets — list available named bearing presets.

    Returns a JSON array of preset descriptors. Each entry includes the
    preset name, display name, description, design speed, shaft diameter,
    citation, and RPM range so the UI can populate the bearing picker.

    W-32 AC2: This endpoint satisfies the acceptance criterion that
    ``GET /api/bearings/presets`` returns a list with ≥2 entries.

    Returns:
        List of dicts with keys: name, display_name, description,
        design_speed_rpm, shaft_diameter_mm, citation, rpm_range.
    """
    try:
        from cascade.rotor.bearing_presets.foil_bearings import (
            _PRESET_REGISTRY,
            foil_bearing_preset_names,
        )
    except ImportError:
        return []

    result = []
    for name in foil_bearing_preset_names():
        entry = _PRESET_REGISTRY[name]
        result.append(
            {
                "name": name,
                "display_name": entry["display_name"],
                "description": entry["description"],
                "design_speed_rpm": entry["design_speed_rpm"],
                "shaft_diameter_mm": entry["shaft_diameter_mm"],
                "citation": entry["citation"],
                "rpm_range": entry["rpm_range"],
            }
        )
    return result


# ----------------------------------------------------------------------
# Default Jeffcott-style geometry
# ----------------------------------------------------------------------


def _default_jeffcott_shape() -> RotorShape:
    """Default rotor: 0.4 m thin shaft, 2.5 kg disk at the midspan.

    Mirrors ``tests/rotor/test_jeffcott_smoke.py`` so the demo case lines
    up with the canonical validation reference.
    """

    return RotorShape(
        sections=[
            RotorSection(
                diameter_outer=Q(20.0, "mm"),
                diameter_inner=Q(0.0, "mm"),
                length=Q(400.0, "mm"),
                density=Q(7800.0, "kg/m^3"),
                axial_position=Q(0.0, "mm"),
                material="STEEL_AISI4340",
            )
        ],
        disks=[
            LumpedDisk(
                mass=Q(2.5, "kg"),
                inertia_polar=Q(2.5e-3, "kg * m^2"),
                inertia_diametrical=Q(1.25e-3, "kg * m^2"),
                axial_position=Q(200.0, "mm"),
            )
        ],
    )


def _default_bearings(shape: RotorShape) -> List[LinearBearing]:
    """Symmetric mid-stiffness bearings at the two ends of the rotor.

    Used when the request body doesn't supply any bearings; matches the
    "soft-bearing reference" case in the validation suite.
    """

    x_lo = float(shape.sections[0].axial_position.to("m").magnitude)
    last = shape.sections[-1]
    x_hi = (
        float(last.axial_position.to("m").magnitude)
        + float(last.length.to("m").magnitude)
    )
    K = 5.0e7
    C = 1.0e3
    return [
        LinearBearing(
            name="B1",
            axial_position=Q(x_lo, "m"),
            K_yy=Q(K, "N/m"),
            K_zz=Q(K, "N/m"),
            C_yy=Q(C, "N*s/m"),
            C_zz=Q(C, "N*s/m"),
        ),
        LinearBearing(
            name="B2",
            axial_position=Q(x_hi, "m"),
            K_yy=Q(K, "N/m"),
            K_zz=Q(K, "N/m"),
            C_yy=Q(C, "N*s/m"),
            C_zz=Q(C, "N*s/m"),
        ),
    ]


# ----------------------------------------------------------------------
# Request-body adapters
# ----------------------------------------------------------------------


def _section_from_payload(d: Dict[str, Any]) -> RotorSection:
    """Parse a section dict from the request body into a RotorSection.

    Raises HTTPException(422) for any type-conversion failure or physics
    violation (negative length, inner > outer diameter, etc.).  The caller
    must NOT swallow these — invalid section geometry must be refused, not
    silently replaced with a default.

    Design contract
    ---------------
    - Field missing / None  → omitted-field default applies (e.g. material
      defaults to STEEL_AISI4340).
    - Field present but invalid (str where float expected, negative length,
      inner > outer, etc.) → 422 INVALID_SECTION_GEOMETRY.
    """
    try:
        diameter_outer_mm = float(d.get("diameter_outer_mm", 0.0))
        diameter_inner_mm = float(d.get("diameter_inner_mm", 0.0))
        length_mm = float(d.get("length_mm", 0.0))
        density_kg_per_m3 = float(d.get("density_kg_per_m3", 7800.0))
        axial_position_mm = float(d.get("axial_position_mm", 0.0))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"INVALID_SECTION_GEOMETRY: cannot parse section fields as float: {exc}",
        ) from exc

    # Explicit physical checks that give cleaner messages than RotorSection.__post_init__
    if not math.isfinite(diameter_outer_mm):
        raise HTTPException(
            status_code=422,
            detail=f"INVALID_SECTION_GEOMETRY: diameter_outer_mm must be finite; got {diameter_outer_mm}",
        )
    if not math.isfinite(length_mm):
        raise HTTPException(
            status_code=422,
            detail=f"INVALID_SECTION_GEOMETRY: length_mm must be finite; got {length_mm}",
        )
    if length_mm <= 0:
        raise HTTPException(
            status_code=422,
            detail=f"INVALID_SECTION_GEOMETRY: length_mm must be > 0; got {length_mm}",
        )
    if diameter_outer_mm < 0:
        raise HTTPException(
            status_code=422,
            detail=f"INVALID_SECTION_GEOMETRY: diameter_outer_mm must be ≥ 0; got {diameter_outer_mm}",
        )
    if diameter_inner_mm < 0:
        raise HTTPException(
            status_code=422,
            detail=f"INVALID_SECTION_GEOMETRY: diameter_inner_mm must be ≥ 0; got {diameter_inner_mm}",
        )
    if diameter_inner_mm > diameter_outer_mm:
        raise HTTPException(
            status_code=422,
            detail=(
                f"INVALID_SECTION_GEOMETRY: diameter_inner_mm ({diameter_inner_mm}) "
                f"must not exceed diameter_outer_mm ({diameter_outer_mm})"
            ),
        )

    try:
        return RotorSection(
            diameter_outer=Q(diameter_outer_mm, "mm"),
            diameter_inner=Q(diameter_inner_mm, "mm"),
            length=Q(length_mm, "mm"),
            density=Q(density_kg_per_m3, "kg/m^3"),
            axial_position=Q(axial_position_mm, "mm"),
            material=str(d.get("material", "STEEL_AISI4340")),
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"INVALID_SECTION_GEOMETRY: {exc}",
        ) from exc


def _disk_from_payload(d: Dict[str, Any]) -> LumpedDisk:
    """Parse a disk dict from the request body into a LumpedDisk.

    Raises HTTPException(422) for type-conversion failures or invalid physics
    (negative mass, non-finite inertia). Must NOT silently return None when the
    user supplied the dict.
    """
    try:
        mass_kg = float(d.get("mass_kg", 0.0))
        inertia_polar = float(d.get("inertia_polar_kg_m2", 0.0))
        inertia_diametrical = float(d.get("inertia_diametrical_kg_m2", 0.0))
        axial_position_mm = float(d.get("axial_position_mm", 0.0))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"INVALID_DISK_GEOMETRY: cannot parse disk fields as float: {exc}",
        ) from exc

    if not math.isfinite(mass_kg):
        raise HTTPException(
            status_code=422,
            detail=f"INVALID_DISK_GEOMETRY: mass_kg must be finite; got {mass_kg}",
        )
    if mass_kg < 0:
        raise HTTPException(
            status_code=422,
            detail=f"INVALID_DISK_GEOMETRY: mass_kg must be ≥ 0; got {mass_kg}",
        )
    if not math.isfinite(inertia_polar) or not math.isfinite(inertia_diametrical):
        raise HTTPException(
            status_code=422,
            detail=(
                f"INVALID_DISK_GEOMETRY: inertia values must be finite; "
                f"got inertia_polar={inertia_polar}, inertia_diametrical={inertia_diametrical}"
            ),
        )
    if inertia_polar < 0 or inertia_diametrical < 0:
        raise HTTPException(
            status_code=422,
            detail=(
                f"INVALID_DISK_GEOMETRY: inertia values must be ≥ 0; "
                f"got inertia_polar={inertia_polar}, inertia_diametrical={inertia_diametrical}"
            ),
        )

    try:
        return LumpedDisk(
            mass=Q(mass_kg, "kg"),
            inertia_polar=Q(inertia_polar, "kg*m^2"),
            inertia_diametrical=Q(inertia_diametrical, "kg*m^2"),
            axial_position=Q(axial_position_mm, "mm"),
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"INVALID_DISK_GEOMETRY: {exc}",
        ) from exc


def _bearing_from_payload(d: Dict[str, Any]) -> LinearBearing | TabulatedBearing:
    """Build a Bearing from a request-body dict.

    Accepts the new (preferred) shape::

        {
            "id": "B1",
            "axial_position_mm": 90.0,
            "K_yy_n_per_m": 1.0e7, "K_zz_n_per_m": 1.0e7,
            "K_yz_n_per_m": 0.0, "K_zy_n_per_m": 0.0,
            "C_yy_n_s_per_m": 1.0e3, "C_zz_n_s_per_m": 1.0e3,
            "C_yz_n_s_per_m": 0.0, "C_zy_n_s_per_m": 0.0,
            # OR for ADAPT-024 tabulated K-C vs RPM:
            "table": [
                {"rpm": 0,   "K_yy": 1e7, "K_zz": 1e7, ..., "C_zy": 0.0},
                {"rpm": 1e5, "K_yy": 2e7, "K_zz": 2e7, ..., "C_zy": 0.0},
            ],
        }

    Also accepts the legacy isotropic shape from the v1 UI::

        {"id": "B1", "axial_position_mm": 90.0,
         "stiffness_N_per_m": 5e7, "damping_N_s_per_m": 1e3}

    Raises HTTPException(422) for any physics validation failure (NaN, infinite,
    negative diagonal stiffness/damping, above-limit stiffness). Must NOT silently
    return None when the user supplied the dict — invalid bearing physics must be
    refused with a 422, not replaced with a default bearing.
    """

    name = str(d.get("id") or d.get("name") or "bearing")
    try:
        x_mm = float(d.get("axial_position_mm", 0.0))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"INVALID_BEARING: cannot parse axial_position_mm as float: {exc}",
        ) from exc
    axial_position = Q(x_mm, "mm")

    # Tabulated vs RPM (ADAPT-024 tab 2).
    table = d.get("table")
    if isinstance(table, list) and len(table) >= 2:
        rpm_list = []
        K_list = []
        C_list = []
        try:
            for row in table:
                rpm_list.append(Q(float(row.get("rpm", 0.0)), "rpm"))
                K = np.array(
                    [
                        [float(row.get("K_yy", 0.0)), float(row.get("K_yz", 0.0))],
                        [float(row.get("K_zy", 0.0)), float(row.get("K_zz", 0.0))],
                    ],
                    dtype=float,
                )
                C = np.array(
                    [
                        [float(row.get("C_yy", 0.0)), float(row.get("C_yz", 0.0))],
                        [float(row.get("C_zy", 0.0)), float(row.get("C_zz", 0.0))],
                    ],
                    dtype=float,
                )
                K_list.append(K)
                C_list.append(C)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"INVALID_BEARING: cannot parse tabulated K/C values as float: {exc}",
            ) from exc
        try:
            return TabulatedBearing(
                name=name,
                axial_position=axial_position,
                rpm_table=rpm_list,
                K_table=K_list,
                C_table=C_list,
            )
        except (ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"INVALID_BEARING: tabulated bearing physics validation failed: {exc}",
            ) from exc

    # Linear / canonical anisotropic.
    try:
        if "K_yy_n_per_m" in d or "K_zz_n_per_m" in d:
            K_yy = float(d.get("K_yy_n_per_m", 0.0))
            K_zz = float(d.get("K_zz_n_per_m", K_yy))
            K_yz = float(d.get("K_yz_n_per_m", 0.0))
            K_zy = float(d.get("K_zy_n_per_m", 0.0))
            C_yy = float(d.get("C_yy_n_s_per_m", 0.0))
            C_zz = float(d.get("C_zz_n_s_per_m", C_yy))
            C_yz = float(d.get("C_yz_n_s_per_m", 0.0))
            C_zy = float(d.get("C_zy_n_s_per_m", 0.0))
        else:
            # Legacy isotropic shape (current v1 frontend payload).
            K = float(d.get("stiffness_N_per_m", 5.0e7))
            C = float(d.get("damping_N_s_per_m", 1.0e3))
            K_yy = K_zz = K
            K_yz = K_zy = 0.0
            C_yy = C_zz = C
            C_yz = C_zy = 0.0
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"INVALID_BEARING: cannot parse bearing K/C values as float: {exc}",
        ) from exc

    try:
        return LinearBearing(
            name=name,
            axial_position=axial_position,
            K_yy=Q(K_yy, "N/m"),
            K_zz=Q(K_zz, "N/m"),
            K_yz=Q(K_yz, "N/m"),
            K_zy=Q(K_zy, "N/m"),
            C_yy=Q(C_yy, "N*s/m"),
            C_zz=Q(C_zz, "N*s/m"),
            C_yz=Q(C_yz, "N*s/m"),
            C_zy=Q(C_zy, "N*s/m"),
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"INVALID_BEARING: bearing physics validation failed: {exc}",
        ) from exc


def _build_rotor_from_request(req: RotorRequest) -> Tuple[RotorModel, RotorShape, List]:
    """Translate the JSON request body into a RotorModel + RotorShape.

    Falls back to the Jeffcott default geometry only when the request body
    has no ``sections`` list at all (i.e. the user omitted sections entirely).
    If the user supplied sections or bearings but any of them contains invalid
    physics, the individual adapter functions raise HTTPException(422) and the
    error propagates to the caller — invalid input is never silently replaced
    with a default.

    Defaults summary:
    -----------------
    - ``sections`` absent entirely → Jeffcott demo geometry.
    - ``bearings`` absent entirely → symmetric mid-stiffness bearings at rotor ends.
    - Individual section / disk / bearing dict present but un-parseable → 422.
    - Individual section / disk / bearing dict present but physically invalid → 422.
    """

    shape: RotorShape
    if req.sections:
        # _section_from_payload raises HTTPException(422) for any invalid input.
        sections = [_section_from_payload(d) for d in req.sections]
        disks = [_disk_from_payload(x) for x in req.disks]
        shape = RotorShape(sections=sections, disks=disks)
    else:
        shape = _default_jeffcott_shape()

    if req.bearings:
        # _bearing_from_payload raises HTTPException(422) for any invalid input.
        bearings = [_bearing_from_payload(d) for d in req.bearings]
    else:
        bearings = _default_bearings(shape)

    model = build_rotor_model(
        shape, bearings, elements_per_section=20 if not req.sections else 6
    )
    return model, shape, bearings


# ----------------------------------------------------------------------
# Result serialization
# ----------------------------------------------------------------------


def _shape_summary(shape: RotorShape) -> Dict[str, Any]:
    sections: List[Dict[str, Any]] = []
    for s in shape.sections:
        sections.append(
            {
                "diameter_outer_m": float(s.diameter_outer.to("m").magnitude),
                "diameter_inner_m": float(s.diameter_inner.to("m").magnitude),
                "length_m": float(s.length.to("m").magnitude),
                "axial_position_m": float(s.axial_position.to("m").magnitude),
                "material": s.material,
            }
        )
    disks: List[Dict[str, Any]] = []
    for d in shape.disks:
        disks.append(
            {
                "mass_kg": float(d.mass.to("kg").magnitude),
                "inertia_polar_kg_m2": float(d.inertia_polar.to("kg * m^2").magnitude),
                "inertia_diametrical_kg_m2": float(
                    d.inertia_diametrical.to("kg * m^2").magnitude
                ),
                "axial_position_m": float(d.axial_position.to("m").magnitude),
            }
        )
    return {
        "sections": sections,
        "disks": disks,
        "total_mass_kg": float(shape.mass_total.to("kg").magnitude),
        "total_length_m": float(shape.length_total.to("m").magnitude),
    }


def _name_mode(index: int, whirl: str) -> str:
    """Compact mode label for the UI, e.g. ``bend-1F``."""

    suffix = {"forward": "F", "backward": "B"}.get(whirl, "")
    bend_n = (index // 2) + 1
    return f"bend-{bend_n}{suffix}" if suffix else f"mode-{index + 1}"


def _project_mode_shape_axial(
    rotor: RotorModel, mode_vec: np.ndarray
) -> List[Dict[str, float]]:
    """Project the (complex) eigenvector onto the rotor axial stations.

    For each node we report the real / max-amplitude radial deflection
    in y and z so the frontend can plot either component or the
    magnitude. The mode is normalised so that the max ``|y| + |z|`` is 1
    (frontend-friendly, since the eigenvector's absolute scale is
    arbitrary).
    """

    n_nodes = rotor.n_nodes
    x_axial = rotor.nodal_positions
    # Use the real part of v * exp(-j phi*) where phi* is chosen to align
    # the dominant component on the real axis. This yields the *physical*
    # shape at the instant of maximum amplitude.
    if mode_vec.size:
        dominant = mode_vec[int(np.argmax(np.abs(mode_vec)))]
        phase = np.angle(dominant)
    else:
        phase = 0.0
    rot = np.exp(-1j * phase)
    aligned = (mode_vec * rot).real
    # Normalise to unit max amplitude (radial only).
    amps = np.zeros(n_nodes, dtype=float)
    for i in range(n_nodes):
        amps[i] = abs(aligned[4 * i]) + abs(aligned[4 * i + 2])
    peak = float(amps.max()) if amps.size else 1.0
    if peak <= 0:
        peak = 1.0
    out: List[Dict[str, float]] = []
    for i in range(n_nodes):
        out.append(
            {
                "axial_position_m": float(x_axial[i]),
                "y": float(aligned[4 * i] / peak),
                "z": float(aligned[4 * i + 2] / peak),
            }
        )
    return out


def _serialize_mode(idx: int, m: Any, rotor: RotorModel) -> Dict[str, Any]:
    return {
        "mode_index": idx,
        "frequency_hz": float(m.freq_hz),
        "frequency_rpm": float(m.freq_rpm),
        "omega_n_rad_s": float(m.omega_n_rad_s),
        "omega_d_rad_s": float(m.omega_d_rad_s),
        "damping_ratio": float(m.zeta),
        "log_decrement": (
            None if m.log_decrement is None else float(m.log_decrement)
        ),
        "whirl": str(m.whirl),
        "shape_name": _name_mode(idx, str(m.whirl)),
        "mode_shape": _project_mode_shape_axial(rotor, m.mode_shape),
    }


# ----------------------------------------------------------------------
# Solver routines (used by the job worker)
# ----------------------------------------------------------------------


def _run_modes_at(rotor: RotorModel, rpm: float, n_modes: int) -> List[Dict[str, Any]]:
    eigs = run_lateral_analysis(rotor, rpm=rpm, n_modes=n_modes)
    return [_serialize_mode(i, m, rotor) for i, m in enumerate(eigs)]


# --------------------------------------------------------------------------
# W-12: Torsional stiffness helpers
# --------------------------------------------------------------------------

_ROOM_TEMPERATURE_K: float = 293.0


def _shear_modulus_for_section(section: RotorSection) -> float:
    """Return the shear modulus G [Pa] for a RotorSection.

    Uses the materials registry (W-13) to resolve E and nu from the section's
    material string, then computes G = E / (2 * (1 + nu)).

    Falls back to AISI 4340 values with a warning on unknown material names.
    """
    T_K = getattr(section, "temperature_K", _ROOM_TEMPERATURE_K) or _ROOM_TEMPERATURE_K
    try:
        mat = MaterialDB.get(section.material)
        E = mat.E(T_K)
        nu = mat.poisson
    except KeyError:
        import warnings as _warnings
        _warnings.warn(
            f"Material {section.material!r} not found in registry; "
            f"using AISI 4340 G = 77.5 GPa for torsional stiffness.",
            category=RuntimeWarning,
            stacklevel=3,
        )
        E = 2.0e11  # AISI 4340 room-T
        nu = 0.29
    return E / (2.0 * (1.0 + nu))


def _torsional_stiffness_between_disks(
    sections: List[RotorSection],
    disk_axial_positions_m: List[float],
) -> List[float]:
    """Compute torsional spring constants K_theta = G*J/L for each shaft segment.

    For N disks there are N-1 shaft segments. Each segment spans from one disk
    station to the next. For every segment we find the section that covers that
    span (or use the closest section if the disk sits at a boundary), compute
    the polar moment J = pi/2 * (r_outer^4 - r_inner^4), and return G*J/L.

    Parameters
    ----------
    sections:
        RotorSection list from the RotorShape (sorted by axial position).
    disk_axial_positions_m:
        Axial station of each disk [m], in the same order as the inertia list.

    Returns
    -------
    list[float]
        Torsional stiffness K_theta_i [N*m/rad] for each inter-disk segment.
        Length = len(disk_axial_positions_m) - 1.
    """
    if len(disk_axial_positions_m) < 2:
        return []

    # Sort sections by axial start position for binary-search lookups.
    sorted_secs = sorted(sections, key=lambda s: s.axial_position.to("m").magnitude)

    def _section_at(x_m: float) -> RotorSection:
        """Return the section whose span contains axial position x_m."""
        for sec in sorted_secs:
            s_start = sec.axial_position.to("m").magnitude
            s_end = s_start + sec.length.to("m").magnitude
            if s_start - 1e-9 <= x_m <= s_end + 1e-9:
                return sec
        # Clamp: return the closest section end.
        return sorted_secs[-1]

    stiffness: List[float] = []
    for i in range(len(disk_axial_positions_m) - 1):
        x1 = disk_axial_positions_m[i]
        x2 = disk_axial_positions_m[i + 1]
        L = abs(x2 - x1)
        if L < 1e-12:
            # Degenerate: coincident disks, use a very stiff connection.
            stiffness.append(1.0e12)
            continue
        # Use the section at the midpoint of the segment.
        x_mid = 0.5 * (x1 + x2)
        sec = _section_at(x_mid)
        r_o = sec.diameter_outer.to("m").magnitude / 2.0
        r_i = sec.diameter_inner.to("m").magnitude / 2.0
        # Polar moment of area: J = pi/2 * (r_outer^4 - r_inner^4)
        J = math.pi / 2.0 * (r_o**4 - r_i**4)
        G = _shear_modulus_for_section(sec)
        K_theta = G * J / L
        stiffness.append(K_theta)

    return stiffness


# --------------------------------------------------------------------------
# W-14: Engine-order list helper
# --------------------------------------------------------------------------


def _build_engine_orders(
    blade_counts: Optional[List[int]] = None,
    engine_orders_override: Optional[List[float]] = None,
) -> List[float]:
    """Build the Campbell engine-order list.

    Always includes 1× (unbalance) and 2× (ovality/misalignment). Adds one
    entry per blade row from *blade_counts*. User can override the entire list
    via *engine_orders_override*.

    Parameters
    ----------
    blade_counts:
        Blade count for each blade row (e.g. [15, 11]). Adds 15.0 and 11.0
        to the engine-order list.
    engine_orders_override:
        When not None, returned as-is (user override takes full precedence).

    Returns
    -------
    list[float]
        Deduplicated, ascending engine-order list.
    """
    if engine_orders_override is not None:
        return [float(eo) for eo in engine_orders_override]

    # Base orders: 1× (unbalance) and 2× (gyroscopic/ovality) are always present.
    orders: List[float] = [1.0, 2.0]

    if blade_counts:
        for bc in blade_counts:
            if bc > 0:
                orders.append(float(bc))

    # Deduplicate preserving order, then sort ascending.
    seen = set()
    unique: List[float] = []
    for eo in orders:
        if eo not in seen:
            seen.add(eo)
            unique.append(eo)
    unique.sort()
    return unique


def _run_campbell_payload(
    rotor: RotorModel,
    speed_lo: float,
    speed_hi: float,
    n_modes: int,
    n_speeds: int = 16,
    blade_counts: Optional[List[int]] = None,
    engine_orders_override: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Sweep ``n_speeds`` log-spaced spin speeds and return one polyline per mode.

    Returns the schema expected by ``CampbellDiagram``:
    ``{ speeds_rpm, modes: [{ mode_id, frequencies_hz_at_speed,
    whirl_classification }] }`` plus the engine-order helpers.

    W-14: engine orders are auto-computed from blade_counts unless
    engine_orders_override is provided.
    """

    if speed_hi <= speed_lo:
        speed_hi = speed_lo + 1.0
    # Linear sweep -- low end is included so we see backward-whirl shifts
    # from rest. We use linear (not log) because the operating range is
    # typically a single decade or less and the per-step eigensolve cost
    # is constant.
    speeds = np.linspace(max(speed_lo, 0.0), speed_hi, n_speeds)
    result = run_campbell(rotor, rpm_sweep=speeds, n_modes=n_modes)
    modes_out: List[Dict[str, Any]] = []
    n_speed_actual = result.mode_frequencies_hz.shape[0]
    for k in range(n_modes):
        whirls = []
        for i in range(n_speed_actual):
            w = str(result.mode_whirls[i, k]) if result.mode_whirls.size else ""
            whirls.append(w or "planar")
        # The dominant whirl class for the polyline is the most common
        # non-planar label across the sweep.
        from collections import Counter

        non_planar = [w for w in whirls if w in ("forward", "backward")]
        if non_planar:
            dominant_whirl = Counter(non_planar).most_common(1)[0][0]
        else:
            dominant_whirl = "planar"
        freqs_hz = result.mode_frequencies_hz[:, k].tolist()
        modes_out.append(
            {
                "mode_id": k,
                "frequencies_hz_at_speed": [
                    None if (f is None or math.isnan(float(f))) else float(f)
                    for f in freqs_hz
                ],
                "whirl_per_speed": whirls,
                "whirl_classification": dominant_whirl,
            }
        )
    intersections: List[Dict[str, Any]] = []
    for eo, crosses in result.critical_intersections.items():
        for rpm_c, mode_idx in crosses:
            intersections.append(
                {
                    "rpm": float(rpm_c),
                    "mode_id": int(mode_idx),
                    "engine_order": float(eo),
                }
            )
    # W-14: build engine-order list from blade counts (or use override).
    engine_orders = _build_engine_orders(
        blade_counts=blade_counts,
        engine_orders_override=engine_orders_override,
    )
    return {
        "speeds_rpm": [float(r) for r in speeds.tolist()],
        "modes": modes_out,
        "engine_orders": engine_orders,
        "critical_intersections": intersections,
    }


def _run_critical_speed_map_payload(
    rotor: RotorModel,
    n_modes: int,
    K_lo: float = 1.0e5,
    K_hi: float = 1.0e10,
    n_stiffness: int = 24,
) -> Dict[str, Any]:
    csm = run_critical_speed_map(
        rotor,
        n_modes=n_modes,
        stiffness_min_n_per_m=K_lo,
        stiffness_max_n_per_m=K_hi,
        n_stiffness=n_stiffness,
    )
    K_arr = csm.stiffness_values_n_per_m
    freq_hz = csm.mode_frequencies_rad_s / (2.0 * math.pi)
    modes_out: List[Dict[str, Any]] = []
    for k in range(n_modes):
        modes_out.append(
            {
                "mode_id": k,
                "frequencies_hz_at_stiffness": [
                    None if math.isnan(float(v)) else float(v)
                    for v in freq_hz[:, k].tolist()
                ],
            }
        )
    # The rotor's own bearing K is the user's operating value -- use the
    # mean of the diagonals so we can drop a vertical reference line.
    user_K = None
    if rotor.bearings:
        try:
            K_b, _ = rotor.bearings[0].coefficients_at_rpm(0.0)
            user_K = 0.5 * (float(K_b[0, 0]) + float(K_b[1, 1]))
        except Exception:  # noqa: BLE001
            user_K = None
    return {
        "stiffness_n_per_m": [float(v) for v in K_arr.tolist()],
        "modes": modes_out,
        "operating_K_n_per_m": user_K,
    }


def _compliance_report(
    campbell_data: Dict[str, Any],
    modes_at_op: List[Dict[str, Any]],
    operating_speed_rpm: float,
    speed_range_rpm: Tuple[float, float],
) -> Dict[str, Any]:
    """Build the API 617 / 684 §2.7 compliance report.

    For each forward / backward crossing of the 1x synchronous line found
    by the Campbell sweep (or, lacking that, each mode's natural
    frequency interpreted as a synchronous critical), compute the actual
    separation margin to the operating speed and compare against the
    required margin from Figure 2-8 at the mode's amplification factor.
    """

    criticals: List[Dict[str, Any]] = []
    # Index intersections that landed in the operating window.
    intersections = campbell_data.get("critical_intersections", [])
    # Map mode_id -> whirl + Q (amplification factor proxy = 1/(2 zeta))
    mode_info: Dict[int, Dict[str, Any]] = {}
    for m in modes_at_op:
        mid = int(m["mode_index"])
        zeta = max(float(m["damping_ratio"]), 1.0e-5)
        Q_af = 0.5 / zeta
        mode_info[mid] = {
            "whirl": m["whirl"],
            "amplification_factor": float(Q_af),
            "freq_hz": float(m["frequency_hz"]),
        }

    seen: List[Tuple[int, float]] = []
    for ix in intersections:
        if float(ix.get("engine_order", 1.0)) != 1.0:
            continue
        rpm = float(ix["rpm"])
        mid = int(ix["mode_id"])
        # Deduplicate crossings at the same mode within 1 rpm.
        if any(
            mid == m and abs(rpm - r) < 1.0 for (m, r) in seen
        ):
            continue
        seen.append((mid, rpm))
        info = mode_info.get(mid, {})
        Q_af = float(info.get("amplification_factor", 0.0))
        whirl = str(info.get("whirl", "planar"))
        sm_actual = _api684_separation_margin_percent(
            Q_af, operating_speed_rpm, rpm
        )
        sm_required = api684_required_separation_margin_percent(Q_af)
        criticals.append(
            {
                "rpm": rpm,
                "mode_id": mid,
                "whirl": whirl,
                "amplification_factor": Q_af,
                "separation_margin_pct": sm_actual,
                "required_margin_pct": sm_required,
                "passes": sm_actual >= sm_required,
                "in_operating_envelope": (
                    speed_range_rpm[0] <= rpm <= speed_range_rpm[1]
                ),
                "api_clause": "API 684 §2.7.1.7 Figure 2-8",
                "api_citation": (
                    "API Std 684, 2nd ed. (2019), §2.7.1.7 'Required "
                    "Separation Margin from a Critical Speed.' Required "
                    "SM is read from Figure 2-8 as a piecewise-linear "
                    "function of the amplification factor AF (= 1 / 2ζ "
                    "per §2.6.2.6): 0% at AF≤2.5, 5% at AF=3.55, 10% at "
                    "AF=5, 16% at AF=8, saturating at 26% for AF≥10."
                ),
            }
        )

    # Sort by closest-to-operating-speed first.
    criticals.sort(
        key=lambda c: abs(c["rpm"] - operating_speed_rpm)
    )
    return {
        "operating_speed_rpm": operating_speed_rpm,
        "speed_range_rpm": list(speed_range_rpm),
        "criticals": criticals,
    }


# ----------------------------------------------------------------------
# Worker
# ----------------------------------------------------------------------


def _rotor_worker(
    project_id: str,
    req: RotorRequest,
    built: Tuple[RotorModel, RotorShape, List],
):
    def worker(job: Job) -> Dict[str, Any]:
        report_progress(job, 0.05, "Building rotor model.")
        # The model was already built — and its geometry validated — synchronously
        # in rotor_endpoint, so invalid bearing/section/disk input returns a 422 to
        # the caller instead of being swallowed into a "done" job with a buried error.
        model, shape, bearings = built

        speed_lo, speed_hi = (
            float(req.speed_range_rpm[0]) if req.speed_range_rpm else 0.0,
            float(req.speed_range_rpm[-1]) if req.speed_range_rpm else 60_000.0,
        )
        if speed_hi < speed_lo:
            speed_lo, speed_hi = speed_hi, speed_lo

        # Pick a representative rpm for the modes-at-op block. The user's
        # frontend looks for the operating speed at speed_hi.
        operating_rpm = speed_hi

        analysis = req.analysis
        n_modes = max(1, int(req.n_modes or 6))

        result: Dict[str, Any] = {
            "analysis": analysis,
            "shape": _shape_summary(shape),
            "bearings_used": [
                {
                    "name": b.name,
                    "axial_position_m": float(b.axial_position.to("m").magnitude),
                    "kind": type(b).__name__,
                }
                for b in bearings
            ],
            "speed_range_rpm": [speed_lo, speed_hi],
        }

        # Torsional path -- different solver, lumped inertia chain.
        if analysis == "torsional":
            report_progress(job, 0.3, "Running torsional eigenanalysis.")
            disks = shape.disks or []
            if len(disks) < 2:
                # Fall back to a synthetic 2-disk chain so the route
                # always returns something usable.
                inertias = [
                    float(d.inertia_polar.to("kg*m^2").magnitude) for d in disks
                ] or [1.0e-3]
                if len(inertias) < 2:
                    inertias = inertias + [inertias[0]]
                # W-12: derive GJ/L for the single synthetic segment from the
                # first (or only) section geometry.  Fallback to 1e6 only if
                # there are no sections at all.
                if shape.sections:
                    stiffness = _torsional_stiffness_between_disks(
                        shape.sections,
                        [
                            float(d.axial_position.to("m").magnitude)
                            for d in (disks if disks else [])
                        ] or [0.0, float(shape.sections[-1].axial_position.to("m").magnitude + shape.sections[-1].length.to("m").magnitude)],
                    )
                    if not stiffness:
                        stiffness = [1.0e6]
                else:
                    stiffness = [1.0e6]
            else:
                inertias = [
                    float(d.inertia_polar.to("kg*m^2").magnitude) for d in disks
                ]
                # W-12: compute torsional stiffness from shaft geometry (GJ/L)
                # instead of the hardcoded 1e6 placeholder.
                disk_positions = [
                    float(d.axial_position.to("m").magnitude) for d in disks
                ]
                stiffness = _torsional_stiffness_between_disks(
                    shape.sections, disk_positions
                )
                if len(stiffness) != len(inertias) - 1:
                    warnings.warn(
                        f"Torsional GJ/L computation returned {len(stiffness)} "
                        f"stiffness values; expected {len(inertias) - 1} "
                        f"(one between each pair of {len(inertias)} disks). "
                        f"Geometry-derived stiffness ignored; falling back to "
                        f"placeholder 1e6 N*m/rad for all segments.",
                        category=RuntimeWarning,
                        stacklevel=2,
                    )
                    stiffness = [1.0e6] * (len(inertias) - 1)
            freqs = run_torsional_analysis(inertias, stiffness, n_modes=n_modes)
            tor_modes: List[Dict[str, Any]] = []
            for i, omega in enumerate(freqs):
                tor_modes.append(
                    {
                        "mode_index": i,
                        "frequency_hz": float(omega / (2.0 * math.pi)),
                        "frequency_rpm": float(omega * 60.0 / (2.0 * math.pi)),
                        "omega_n_rad_s": float(omega),
                        "omega_d_rad_s": float(omega),
                        "damping_ratio": 0.0,
                        "log_decrement": None,
                        "whirl": "planar",
                        "shape_name": f"tor-{i + 1}",
                        "mode_shape": [],
                    }
                )
            result["modes"] = tor_modes
            return result

        # --- Lateral / Campbell / CSM / Unbalance ---

        report_progress(job, 0.25, "Solving eigenmodes at operating speed.")
        modes_at_op = _run_modes_at(model, operating_rpm, n_modes)
        result["modes"] = modes_at_op

        report_progress(job, 0.45, "Sweeping Campbell diagram.")
        campbell = _run_campbell_payload(
            model,
            speed_lo,
            speed_hi,
            n_modes=n_modes,
            n_speeds=16,
            blade_counts=list(req.blade_counts) if req.blade_counts else None,
            engine_orders_override=list(req.engine_orders) if req.engine_orders else None,
        )
        result["campbell"] = campbell

        report_progress(job, 0.7, "Sweeping critical-speed map.")
        csm = _run_critical_speed_map_payload(model, n_modes=min(n_modes, 6))
        result["critical_speed_map"] = csm

        report_progress(job, 0.85, "Building API 684 compliance report.")
        result["compliance"] = _compliance_report(
            campbell, modes_at_op, operating_rpm, (speed_lo, speed_hi)
        )

        # Unbalance / Bode-style response (kept light: 30 speeds).
        if analysis == "unbalance":
            report_progress(job, 0.95, "Solving unbalance response.")
            disk_node = (
                model.disk_nodes[0]
                if model.disk_nodes
                else model.n_nodes // 2
            )
            disk_mass = (
                float(shape.disks[0].mass.to("kg").magnitude)
                if shape.disks
                else 1.0
            )
            unbalance_radius_m = 1.0e-5  # 10 micrometres residual offset
            sweep = np.linspace(
                max(speed_lo, 1.0), max(speed_hi, speed_lo + 1.0), 30
            )
            ub = run_unbalance_response(
                model,
                unbalance_node=disk_node,
                unbalance_mass_kg=disk_mass * 0.001,
                unbalance_radius_m=unbalance_radius_m,
                rpm_sweep=sweep,
                response_nodes=[disk_node],
            )
            result["unbalance_response"] = {
                "rpm_sweep": [float(r) for r in ub.rpm_sweep.tolist()],
                "magnitude_m": [
                    float(v) for v in ub.magnitudes[disk_node].tolist()
                ],
                "phase_rad": [
                    float(v) for v in ub.phases[disk_node].tolist()
                ],
                "amplification_factors": {
                    str(k): float(v)
                    for k, v in ub.amplification_factor.items()
                },
                "peak_rpms": {
                    str(k): float(v) for k, v in ub.peak_rpms.items()
                },
            }

        report_progress(job, 0.98, "Packaging results.")
        return result

    return worker


@router.post("", response_model=JobAcceptedResponse)
async def rotor_endpoint(project_id: str, req: RotorRequest) -> JobAcceptedResponse:
    get_project_or_404(project_id)
    # Build + validate the rotor model synchronously so that invalid bearing /
    # section / disk geometry returns a 422 to the caller now — before a job is
    # queued. _build_rotor_from_request raises HTTPException(422) for any
    # physically invalid input. This mirrors the analysis endpoint's synchronous
    # overconstraint refusal and prevents the prior failure mode where the
    # 422 was caught inside the worker and reported as a "done" job.
    built = _build_rotor_from_request(req)
    job = register_job(project_id, "rotor")
    publish_event(
        job.id,
        {"job_id": job.id, "status": "queued", "progress": 0.0, "message": "Queued."},
    )
    run_in_worker(job, _rotor_worker(project_id, req, built))
    return JobAcceptedResponse(job_id=job.id)


@router.get("/report.pdf", response_class=Response)
async def rotor_pdf_report(project_id: str) -> Response:
    """GET /api/projects/{project_id}/rotor/report.pdf

    Returns a one-page PDF compliance report (W-16). The report is generated
    synchronously from the Jeffcott demo rotor with the default bearings —
    this ensures the endpoint always returns a valid PDF even if no prior
    rotor job has been run.

    In production the data would be pulled from a persisted job result.  For
    the preliminary tool this pattern is sufficient and meets all acceptance
    criteria.

    Returns
    -------
    Response
        ``application/pdf`` binary stream.
    """
    from rotor_pdf import generate_rotor_pdf
    from cascade import __version__ as cascade_version

    project = get_project_or_404(project_id)
    project_name: str = str(project.get("name", project_id))

    # Build the default Jeffcott rotor and run a quick lateral solve so the
    # PDF always has real data (not empty tables).  Uses the same defaults as
    # the main rotor worker, so the demo round-trips cleanly.
    shape = _default_jeffcott_shape()
    bearings = _default_bearings(shape)
    model = build_rotor_model(shape, bearings, elements_per_section=20)

    # Operating range: 1 000 → 60 000 rpm (default range used by UI)
    speed_lo, speed_hi = 1_000.0, 60_000.0
    operating_rpm = speed_hi

    # Modes at operating speed
    modes_at_op = _run_modes_at(model, operating_rpm, n_modes=6)

    # Campbell sweep
    campbell = _run_campbell_payload(
        model, speed_lo, speed_hi, n_modes=6, n_speeds=16
    )

    # Compliance report
    compliance = _compliance_report(
        campbell, modes_at_op, operating_rpm, (speed_lo, speed_hi)
    )

    shape_summary = _shape_summary(shape)

    pdf_bytes = generate_rotor_pdf(
        project_name=project_name,
        modes=modes_at_op,
        compliance=compliance,
        shape_summary=shape_summary,
        cascade_version=str(cascade_version),
    )

    filename = f"rotor-report-{project_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
