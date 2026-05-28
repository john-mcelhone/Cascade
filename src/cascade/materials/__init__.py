"""Cascade materials database (ADAPT-031).

Open-data materials registry for every Cascade stress, disc, life,
rotor-dynamics and recuperator calculation. Each :class:`Material` has
temperature-dependent E, sigma_y, sigma_u, alpha, k and cp, plus a
named open-literature citation (ASM Handbook, MMPDS-13, NIST, NASA TM,
Special Metals / Haynes datasheets).

The v1 catalogue (see :mod:`cascade.materials.database`) holds:

1. Inconel 625 — high-temperature gas-path, recuperators
2. Inconel 718 — turbine discs (aero engine standard)
3. Inconel 738 — hot-section blading
4. MAR-M 247 — equiaxed polycrystalline turbine blades
5. Ti-6Al-4V — compressor blades
6. AISI 4340 — shafts, bushings
7. 17-4PH — pump / compressor impellers
8. A286 — hot-section fasteners
9. Haynes 282 — modern sCO2 turbine wheels
10. 316L — stainless casings, low-cycle fatigue

Public surface::

    from cascade.materials import Material, MaterialDB
"""

from __future__ import annotations

from cascade.materials.base import Material
from cascade.materials.registry import MaterialDB

__all__ = ["Material", "MaterialDB"]
