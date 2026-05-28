"""Rotor-dynamics + plain-journal bearing module for Cascade.

Implements SPEC_SHEET.md §3.5 (RotorShape consumption), §9 (Christopherson PSOR
for journal bearings, ARPACK eigenanalysis), §12 (validation cases RD-3, RD-4,
RD-5), §15 (Kzz > 1e10 N/m refusal).

Reading order:
- `beam_fem` -- Timoshenko beam-rotor element + global assembly
- `bearings` -- LinearBearing / TabulatedBearing dataclasses with refusal
- `journal_bearing` -- PlainJournalBearing (Ocvirk short + Christopherson PSOR)
- `eigenanalysis` -- complex QEP linearization and eigensolve
- `critical_speed_map` -- bearing-stiffness sweep
- `unbalance_response` -- synchronous forced response (Bode, Q, separation margin)
- `campbell_stability` -- Campbell diagram + log decrement stability

Canonical references (cited throughout):
- API 684, 3rd ed. 2019 -- separation margin / amplification factor / stability
- Childs, D., 1993 -- Turbomachinery Rotordynamics
- Friswell et al., 2010 -- Dynamics of Rotating Machines (closed-form benchmarks)
- Genta, G., 1999 -- Dynamics of Rotating Systems (FEM derivation)
- Nelson, H. D. & McVaugh, J. M., 1976 -- consistent rotor finite element
- Nelson, H. D., 1980 -- Timoshenko extension of the rotor element
- Christopherson, D. G., 1941 -- Reynolds boundary condition for cavitation
- Lund, J. W., 1966 -- perturbation method for bearing K-C
- Someya, T., 1989 -- Journal-Bearing Databook
"""

from __future__ import annotations

from cascade.rotor.bearings import Bearing, LinearBearing, TabulatedBearing
from cascade.rotor.beam_fem import RotorModel, build_rotor_model
from cascade.rotor.campbell_stability import (
    CampbellResult,
    StabilityResult,
    run_campbell,
    run_stability,
)
from cascade.rotor.critical_speed_map import CriticalSpeedMap, run_critical_speed_map
from cascade.rotor.eigenanalysis import (
    EigenResult,
    run_lateral_analysis,
    run_torsional_analysis,
)
from cascade.rotor.journal_bearing import PlainJournalBearing
from cascade.rotor.unbalance_response import (
    UnbalanceResponseResult,
    run_unbalance_response,
)

__all__ = [
    # Core model + bearings
    "RotorModel",
    "build_rotor_model",
    "Bearing",
    "LinearBearing",
    "TabulatedBearing",
    "PlainJournalBearing",
    # Analyses
    "run_lateral_analysis",
    "run_torsional_analysis",
    "run_critical_speed_map",
    "run_unbalance_response",
    "run_campbell",
    "run_stability",
    # Results
    "EigenResult",
    "CriticalSpeedMap",
    "UnbalanceResponseResult",
    "CampbellResult",
    "StabilityResult",
]
