"""Design-space exploration (Sobol' sampling + filtering + Pareto + UX triad).

v1 ships:

- `SobolSampler` (Joe-Kuo direction numbers via scipy.stats.qmc.Sobol)
- `ParameterRange` (linear / log / categorical)
- `DesignSpace` (candidates + filter API + Pareto + Picked / Best-in-Space /
  Best-in-Filter triad)
- `DesignSpaceExplorer` (sampler -> parallel evaluation -> DesignSpace)
- `Constraint` (user-defined predicate over a `Candidate`)

The "inverse solver" framing is explicitly refused: this is space-filling
DoE plus per-trial forward solves.
"""

from __future__ import annotations

from cascade.explore.design_space import (
    ALL_STATUSES,
    Candidate,
    CandidateStatus,
    Constraint,
    DesignSpace,
    DesignSpaceExplorer,
    EVALUATOR_ERROR,
    INVALID_GEOMETRY,
    NON_CONVERGED,
    REGIME_OUT_OF_VALIDITY,
    VALID,
)
from cascade.explore.sobol_sampler import ParameterRange, SobolSampler

__all__ = [
    "ALL_STATUSES",
    "Candidate",
    "CandidateStatus",
    "Constraint",
    "DesignSpace",
    "DesignSpaceExplorer",
    "EVALUATOR_ERROR",
    "INVALID_GEOMETRY",
    "NON_CONVERGED",
    "ParameterRange",
    "REGIME_OUT_OF_VALIDITY",
    "SobolSampler",
    "VALID",
]
