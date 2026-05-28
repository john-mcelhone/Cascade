"""Cascade rotor bearing presets package.

Exports named bearing presets for common turbomachinery bearing types.
Use these as starting points when digitizing bearing tables is not yet feasible.

Available presets
-----------------
- :data:`CAPSTONE_C30_FOIL_BEARING` — Capstone C30-class air foil bearing (~80 kRPM rated)
- :data:`DELLACORTE_NASA_FOIL_GEN_III` — NASA DellaCorte Generation III foil bearing reference

W-32: foil bearing K-C presets per W-32.
"""

from __future__ import annotations

from .foil_bearings import (
    CAPSTONE_C30_FOIL_BEARING,
    DELLACORTE_NASA_FOIL_GEN_III,
    foil_bearing_preset_names,
    get_foil_bearing_preset,
)

__all__ = [
    "CAPSTONE_C30_FOIL_BEARING",
    "DELLACORTE_NASA_FOIL_GEN_III",
    "foil_bearing_preset_names",
    "get_foil_bearing_preset",
]
