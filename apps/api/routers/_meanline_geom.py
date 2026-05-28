"""Shared geometry-construction helpers for W-01 (explore) and W-02 (map).

Both the design-space exploration router and the performance-map router need
to convert a project's parameters (plus an optional Sobol' sample dict) into
a ``CentrifugalCompressorGeometry`` or ``RadialTurbineGeometry`` object.
Centralising that here keeps the wiring auditable and avoids duplication.

Design scaling strategy
-----------------------
The explore Sobol' sampler sweeps ``rotor_outlet_radius`` (r2) over
[0.015, 0.045] m. To keep the operating point physically consistent as r2
varies, all geometry and operating-point quantities scale with r2:

- Inducer/blade-height dimensions: scale linearly as r2 / r2_ref.
- RPM: scales as r2_ref / r2 to maintain constant impeller tip speed
  U2 = ω r2.  The reference tip speed is U2_ref ≈ 293 m/s (Eckardt 1976
  Rotor A design point), giving PR_tt ≈ 1.8.  This is deliberately
  conservative to keep every candidate inside the validity envelope.
- Mass flow: scales as (r2/r2_ref)² to maintain the same flow coefficient
  φ = V_m1 / U2 (dimensional similarity, continuity).

The tip-clearance Sobol' variable sweeps in absolute metres. The blade_count
variable sweeps as an integer.  Both drive meaningful variation in the loss
breakdown (tip-clearance loss, profile/secondary loss) which produces a
physically real scatter.

Radial-turbine defaults mirror the Whitney-Stewart NASA TN D-7508 RIT-1
validation geometry (analysis.py _RIT_DEFAULTS) — kept for completeness.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Centrifugal compressor reference geometry (Eckardt Rotor A scaled)
# ---------------------------------------------------------------------------
# Reference point: Eckardt (1976) Rotor A design point (r2=0.200 m, 14000 rpm,
# 5.31 kg/s at sea-level standard). The Sobol' sweep scales all quantities
# proportionally to maintain geometric and aerodynamic similarity.
#
# Rationale for Eckardt as reference (not AT-100's PR≈5 conditions):
#   - The Eckardt geometry is the canonical CC-1 validation case in Cascade
#     (analysis.py _CC_DEFAULTS). The solver is verified at this point.
#   - PR≈1.8 keeps every scaled machine below the RegimeOutOfValidity boundary.
#   - Tip speed U2 ≈ 293 m/s is conservative (far from supersonic relative flow).
#   - The blade_count and tip_clearance Sobol' variables produce 0.84–0.90
#     eta_tt variation across the scatter — physically meaningful range.

_CC_REF: Dict[str, Any] = {
    # Reference geometry (Eckardt Rotor A)
    "inducer_hub_radius": 0.045,       # r1_hub [m]
    "inducer_tip_radius": 0.140,       # r1_tip [m]
    "impeller_outlet_radius": 0.200,   # r2 [m] — reference radius
    "blade_height_outlet": 0.026,      # b2 [m]
    "blade_count": 16,                 # Z (mid-range for Sobol' sweep)
    "beta_2_metal_rad": math.pi / 6,   # 30° back-sweep (β'_from-tang=60° → from axial=30°)
    "tip_clearance": 3e-4,             # ε [m]
    # Reference operating point
    "mass_flow_kg_per_s": 5.31,        # kg/s at reference r2
    "rpm": 14000.0,                    # rpm at reference r2
    "pressure_total_Pa": 101325.0,
    "temperature_total_K": 288.15,
    "fluid": "air",
}

# Explore parameter name mapping: Sobol' sample key → geometry field name.
# The explore.py Sobol' sampler uses these three variables by default.
_EXPLORE_PARAM_MAP: Dict[str, str] = {
    "rotor_outlet_radius": "impeller_outlet_radius",  # legacy name from explore.py
    "blade_count": "blade_count",
    "tip_clearance": "tip_clearance",
}

# ---------------------------------------------------------------------------
# Radial turbine defaults (Whitney-Stewart NASA TN D-7508 RIT-1)
# ---------------------------------------------------------------------------
_RIT_DESIGN_DEFAULTS: Dict[str, Any] = {
    "rotor_inlet_radius": 0.076,
    "rotor_outlet_radius_hub": 0.019,
    "rotor_outlet_radius_tip": 0.0406,
    "blade_height_inlet": 0.012,
    "blade_height_outlet": 0.0216,
    "blade_count": 12,
    "inlet_metal_angle_rad": 0.0,
    "exducer_angle_rad": math.radians(60.0),
    "tip_clearance": 0.00025,
    "mass_flow_kg_per_s": 0.13,
    "rpm": 79000.0,
    "pressure_total_Pa": 220000.0,
    "temperature_total_K": 1090.0,
    "fluid": "air",
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def build_cc_geometry(
    sample: Optional[Dict[str, Any]] = None,
    project_params: Optional[Dict[str, Any]] = None,
):
    """Build a ``CentrifugalCompressorGeometry`` from Sobol' sample + project params.

    Priority (highest to lowest):
      1. ``sample`` — Sobol'-sample dict (explore.py per-candidate parameters).
         Keys are ``rotor_outlet_radius``, ``blade_count``, ``tip_clearance``
         (quantities with ``.magnitude`` attribute from SobolSampler, or plain
         float if called from map.py tests).
      2. ``project_params`` — project-level geometry overrides (plain floats).
      3. ``_CC_REF`` — built-in Eckardt Rotor A reference defaults.

    When ``rotor_outlet_radius`` is supplied in ``sample``, the RPM and mass
    flow are automatically scaled to maintain constant U2 and φ (see module
    docstring). This scaling is bypassed when ``rpm`` or ``mass_flow_kg_per_s``
    appear explicitly in ``project_params``.

    Returns ``(geom, op)`` where ``geom`` is a
    ``CentrifugalCompressorGeometry`` and ``op`` is an operating-point dict
    with keys ``mass_flow_kg_per_s``, ``rpm``, ``pressure_total_Pa``,
    ``temperature_total_K``, ``fluid``.
    """
    from cascade.meanline import CentrifugalCompressorGeometry

    d = dict(_CC_REF)

    # Apply project-level geometry overrides (map.py uses these for geometry variants).
    if project_params:
        for k, v in project_params.items():
            if k in d and v is not None:
                d[k] = v

    # Apply Sobol' sample — extracts rotor_outlet_radius, blade_count, tip_clearance.
    if sample:
        for sobol_key, geom_key in _EXPLORE_PARAM_MAP.items():
            if sobol_key in sample:
                v = sample[sobol_key]
                d[geom_key] = float(v.magnitude) if hasattr(v, "magnitude") else float(v)

    r2_ref = _CC_REF["impeller_outlet_radius"]  # 0.200 m
    r2 = float(d["impeller_outlet_radius"])
    scale = r2 / r2_ref

    # Track which quantities were explicitly provided so we don't clobber them.
    inducer_keys = ("inducer_hub_radius", "inducer_tip_radius", "blade_height_outlet")
    op_keys_fixed = ("mass_flow_kg_per_s", "rpm")
    project_overrides_inducer = project_params and any(k in project_params for k in inducer_keys)
    project_overrides_op = project_params and any(k in project_params for k in op_keys_fixed)
    sample_overrides_inducer = sample and any(k in sample for k in inducer_keys)

    if abs(scale - 1.0) > 1e-9:
        # Geometry scaling (linear in r2).
        if not project_overrides_inducer and not sample_overrides_inducer:
            d["inducer_hub_radius"] = _CC_REF["inducer_hub_radius"] * scale
            d["inducer_tip_radius"] = _CC_REF["inducer_tip_radius"] * scale
            d["blade_height_outlet"] = _CC_REF["blade_height_outlet"] * scale

        # Operating-point scaling (constant U2 and φ).
        if not project_overrides_op:
            d["rpm"] = _CC_REF["rpm"] / scale          # keep U2 = ω r2 = const
            d["mass_flow_kg_per_s"] = _CC_REF["mass_flow_kg_per_s"] * scale ** 2  # keep φ

    # Clamp blade_count to valid integer range.
    blade_count = max(3, int(round(float(d["blade_count"]))))
    tip_clearance = max(0.0, float(d["tip_clearance"]))

    # Ensure geometry sanity: inducer_tip < outlet_radius.
    if d["inducer_tip_radius"] >= d["impeller_outlet_radius"]:
        d["inducer_tip_radius"] = d["impeller_outlet_radius"] * 0.65
        d["inducer_hub_radius"] = d["inducer_tip_radius"] * 0.35

    op = {
        "mass_flow_kg_per_s": float(d["mass_flow_kg_per_s"]),
        "rpm": float(d["rpm"]),
        "pressure_total_Pa": float(d["pressure_total_Pa"]),
        "temperature_total_K": float(d["temperature_total_K"]),
        "fluid": d.get("fluid", "air"),
    }

    geom = CentrifugalCompressorGeometry(
        inducer_hub_radius=float(d["inducer_hub_radius"]),
        inducer_tip_radius=float(d["inducer_tip_radius"]),
        impeller_outlet_radius=float(d["impeller_outlet_radius"]),
        blade_height_outlet=float(d["blade_height_outlet"]),
        blade_count=blade_count,
        beta_2_metal_rad=float(d["beta_2_metal_rad"]),
        tip_clearance=tip_clearance,
    )
    return geom, op


def build_rit_geometry(
    sample: Optional[Dict[str, Any]] = None,
    project_params: Optional[Dict[str, Any]] = None,
):
    """Build a ``RadialTurbineGeometry`` from Sobol' sample + project params.

    Same priority as ``build_cc_geometry``.
    Returns ``(geom, op)``.
    """
    from cascade.meanline import RadialTurbineGeometry

    d = dict(_RIT_DESIGN_DEFAULTS)

    if project_params:
        for k, v in project_params.items():
            if k in d and v is not None:
                d[k] = v

    rit_param_map: Dict[str, str] = {
        "rotor_outlet_radius": "rotor_outlet_radius_tip",
        "blade_count": "blade_count",
        "tip_clearance": "tip_clearance",
    }
    if sample:
        for sobol_key, geom_key in rit_param_map.items():
            if sobol_key in sample:
                v = sample[sobol_key]
                d[geom_key] = float(v.magnitude) if hasattr(v, "magnitude") else float(v)

    op = {
        "mass_flow_kg_per_s": float(d["mass_flow_kg_per_s"]),
        "rpm": float(d["rpm"]),
        "pressure_total_Pa": float(d["pressure_total_Pa"]),
        "temperature_total_K": float(d["temperature_total_K"]),
        "fluid": d.get("fluid", "air"),
    }

    geom = RadialTurbineGeometry(
        rotor_inlet_radius=float(d["rotor_inlet_radius"]),
        rotor_outlet_radius_hub=float(d["rotor_outlet_radius_hub"]),
        rotor_outlet_radius_tip=float(d["rotor_outlet_radius_tip"]),
        blade_height_inlet=float(d["blade_height_inlet"]),
        blade_height_outlet=float(d["blade_height_outlet"]),
        blade_count=max(3, int(round(float(d["blade_count"])))),
        inlet_metal_angle_rad=float(d["inlet_metal_angle_rad"]),
        exducer_angle_rad=float(d["exducer_angle_rad"]),
        tip_clearance=max(0.0, float(d["tip_clearance"])),
    )
    return geom, op


def estimate_mass_kg(r2: float) -> float:
    """Very rough impeller mass estimate from outlet radius.

    Scales as r2³ (volume scaling) with an empirical coefficient for
    aluminium-alloy single-stage impellers. At the Eckardt reference
    r2 = 0.200 m, mass ≈ 4.0 kg (realistic for a 400-mm diameter alloy wheel).
    """
    # 4.0 kg at r2 = 0.200 m → 0.52 kg at r2 = 0.055 m (AT-100 size)
    return 4.0 * (r2 / 0.200) ** 3
