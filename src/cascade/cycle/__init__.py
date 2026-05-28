"""0D Brayton-cycle solver for Cascade.

Per SPEC_SHEET.md §3 the cycle solver consumes and produces `Port` objects.
Components compute outlet from inlet given typed parameters. The top-level
solvers (`solve_simple_brayton`, `solve_recuperated_brayton`) are recipe-based
APIs covering CYC-1, CYC-2, CYC-3 (SPEC_SHEET §12).

Reading order:
- `cascade.cycle.fluid_model` — IdealGasFluid (textbook) and NasaFluid (real-gas)
- `cascade.cycle.components`  — Compressor, Turbine, Burner, Recuperator, ...
- `cascade.cycle.solver`      — SimpleBraytonSpec, RecuperatedBraytonSpec, solve_cycle

Refusal behavior (SPEC_SHEET §13):
- Compressor / turbine PR > 60 → RegimeOutOfValidity.
- Burner outlet T > 2100 K     → RegimeOutOfValidity (uncooled material limit).
- Recuperator ε > 0.98         → ValueError (pinch divergence).

Numerical conventions (SPEC_SHEET §3.3):
- Inner solver tolerance: 1e-6 relative.
- Outer (recycle) tolerance: 1e-5 relative.
- Aitken Δ²-accelerated fixed-point for recuperator recycle.
"""

from __future__ import annotations

from cascade.cycle.components import (
    EFFECTIVENESS_REFUSE_HIGH,
    PR_REFUSE_HARD,
    PR_WARN_HIGH,
    T_BURNER_REFUSE,
    Burner,
    Compressor,
    ConstantPressureLoss,
    EfficiencyMode,
    Intercooler,
    Mixer,
    Recuperator,
    Shaft,
    Splitter,
    Turbine,
)
from cascade.cycle.fluid_model import FluidModel, IdealGasFluid, NasaFluid
from cascade.cycle.solver import (
    ENERGY_CONVENTION_LABEL,
    INNER_TOL_DEFAULT,
    MAX_OUTER_ITERS_DEFAULT,
    OUTER_TOL_DEFAULT,
    P_REF_SENSIBLE_PA,
    T_REF_SENSIBLE_K,
    CycleResult,
    CycleSpec,
    EnergyBalanceReport,
    MultiShaftBraytonSpec,
    MultiShaftResult,
    RecuperatedBraytonSpec,
    SimpleBraytonSpec,
    SpoolBalance,
    energy_balance_report,
    solve_cycle,
    solve_multi_shaft_brayton,
    solve_recuperated_brayton,
    solve_simple_brayton,
)

__all__ = [
    # Components
    "Compressor",
    "Turbine",
    "Burner",
    "Recuperator",
    "Intercooler",
    "Mixer",
    "Splitter",
    "ConstantPressureLoss",
    "Shaft",
    "EfficiencyMode",
    # Fluid models
    "FluidModel",
    "IdealGasFluid",
    "NasaFluid",
    # Solver
    "CycleResult",
    "CycleSpec",
    "SimpleBraytonSpec",
    "RecuperatedBraytonSpec",
    "MultiShaftBraytonSpec",
    "MultiShaftResult",
    "SpoolBalance",
    "solve_cycle",
    "solve_simple_brayton",
    "solve_recuperated_brayton",
    "solve_multi_shaft_brayton",
    # Energy-balance reporting (ADAPT-012)
    "EnergyBalanceReport",
    "energy_balance_report",
    "ENERGY_CONVENTION_LABEL",
    "T_REF_SENSIBLE_K",
    "P_REF_SENSIBLE_PA",
    # Constants
    "PR_REFUSE_HARD",
    "PR_WARN_HIGH",
    "T_BURNER_REFUSE",
    "EFFECTIVENESS_REFUSE_HIGH",
    "INNER_TOL_DEFAULT",
    "OUTER_TOL_DEFAULT",
    "MAX_OUTER_ITERS_DEFAULT",
]
