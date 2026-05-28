"""Cascade — open turbomachinery design environment.

Reading order:
- `cascade.units` — the canonical Quantity / Port / RotorShape / Species types
- `cascade.thermo` — real-gas equations of state (NASA polynomials, CoolProp, REFPROP)
- `cascade.cycle` — 0D thermodynamic cycle solver
- `cascade.network` — 1D thermal-fluid network solver
- `cascade.meanline` — radial / centrifugal / axial preliminary design
- `cascade.loss_models` — pluggable, cited loss correlations
- `cascade.geometry` — B-spline geometry generation + STEP / IGES / STL export
- `cascade.explore` — Sobol' design exploration with filtering
- `cascade.perf_map` — performance map generation
- `cascade.optimize` — single- and multi-objective optimization
- `cascade.rotor` — beam-FEM rotor dynamics + plain-journal bearings
- `cascade.schema` — project file format (TOML with units)
- `cascade.validation` — validation cases against published data

The canonical specification lives at the repository root in SPEC_SHEET.md.
"""

__version__ = "0.1.0"

from cascade.units import (
    Q,
    Port,
    RotorShape,
    RotorSection,
    LumpedDisk,
    Species,
    Composition,
    UnitRegistry,
    ureg,
)

__all__ = [
    "Q",
    "Port",
    "RotorShape",
    "RotorSection",
    "LumpedDisk",
    "Species",
    "Composition",
    "UnitRegistry",
    "ureg",
    "__version__",
]
