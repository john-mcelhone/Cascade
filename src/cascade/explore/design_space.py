"""DesignSpace: container for candidate designs + filter / Pareto API.

The v1 design-exploration module produces a `DesignSpace` of `Candidate`
objects each carrying:

- `params`: the input parameter dict (Sobol' sample)
- `objectives`: a dict of named output objectives (η_tt, mass, power, ...)
- `constraints`: a dict mapping constraint-name -> satisfied?
- `status`: one of {VALID, INVALID_GEOMETRY, REGIME_OUT_OF_VALIDITY, NON_CONVERGED}

UX triad: Picked / Best in Space / Best in Filter. These are first-class
on `DesignSpace`.

Parallel evaluation uses `concurrent.futures.ProcessPoolExecutor`. The
performance target is 2000 candidates in 30 s on 8 cores.
"""

from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple, Union

import numpy as np

from cascade.units import Quantity

from cascade.explore.sobol_sampler import SobolSampler


log = logging.getLogger(__name__)


# Candidate statuses. Mirror the perf-map codes where applicable; the
# design-space subset is what a meanline forward solve can report.
CandidateStatus = str  # one of:
VALID = "VALID"
INVALID_GEOMETRY = "INVALID_GEOMETRY"
REGIME_OUT_OF_VALIDITY = "REGIME_OUT_OF_VALIDITY"
NON_CONVERGED = "NON_CONVERGED"
EVALUATOR_ERROR = "EVALUATOR_ERROR"

ALL_STATUSES = frozenset(
    {VALID, INVALID_GEOMETRY, REGIME_OUT_OF_VALIDITY, NON_CONVERGED, EVALUATOR_ERROR}
)


# A Candidate's value type is intentionally permissive: objectives may be
# Quantity (with units) or plain floats (dimensionless metrics like η).
ObjectiveValue = Union[Quantity, float, int]


@dataclass(frozen=True)
class Candidate:
    """A single design candidate.

    `objectives` and `constraints` may be empty if the evaluation failed
    before producing any output; `status` will reflect that.
    """

    params: Dict[str, Any]
    objectives: Dict[str, ObjectiveValue] = field(default_factory=dict)
    constraints: Dict[str, bool] = field(default_factory=dict)
    status: CandidateStatus = VALID
    error_message: Optional[str] = None

    def __post_init__(self) -> None:
        if self.status not in ALL_STATUSES:
            msg = (
                f"Candidate.status must be one of {sorted(ALL_STATUSES)}; "
                f"got {self.status!r}"
            )
            raise ValueError(msg)

    @property
    def is_valid(self) -> bool:
        return self.status == VALID

    @property
    def all_constraints_satisfied(self) -> bool:
        return all(self.constraints.values()) if self.constraints else True

    def objective_value(self, name: str) -> float:
        """Numeric magnitude of an objective in its canonical SI unit.

        Quantity values are converted to their base SI dimension via Pint's
        `.to_base_units()` so optimizer comparisons are unit-consistent.
        """
        v = self.objectives.get(name)
        if v is None:
            raise KeyError(f"Candidate has no objective {name!r}")
        if isinstance(v, Quantity):
            return float(v.to_base_units().magnitude)
        return float(v)


@dataclass
class Constraint:
    """A user-defined inequality constraint over a Candidate.

    `name` labels the constraint in the Candidate's `constraints` dict.
    `predicate(candidate) -> bool` returns True iff satisfied.

    Constraints are applied *after* evaluation by `DesignSpaceExplorer.run`.
    Candidates with status != VALID pass through unchanged (no constraints
    evaluated on them).
    """

    name: str
    predicate: Callable[[Candidate], bool]


@dataclass
class DesignSpace:
    """Container of evaluated candidates with filter + Pareto + UX-triad API."""

    candidates: List[Candidate] = field(default_factory=list)
    # User-selected designs — the "Picked / Best in Space / Best in Filter" triad.
    picked_index: Optional[int] = None
    primary_objective: Optional[str] = None
    minimize_primary: bool = False

    def __len__(self) -> int:
        return len(self.candidates)

    def __iter__(self) -> Iterator[Candidate]:
        return iter(self.candidates)

    def __getitem__(self, idx: int) -> Candidate:
        return self.candidates[idx]

    def append(self, candidate: Candidate) -> None:
        self.candidates.append(candidate)

    # --- Filter API ---------------------------------------------------------

    def filter(self, predicate: Callable[[Candidate], bool]) -> "DesignSpace":
        """Return a new DesignSpace containing only candidates matching predicate.

        The returned space shares the parent's primary-objective config so
        Best-in-Filter can be computed without reconfiguration.
        """
        kept = [c for c in self.candidates if predicate(c)]
        return DesignSpace(
            candidates=kept,
            picked_index=None,  # picks don't transfer across filters
            primary_objective=self.primary_objective,
            minimize_primary=self.minimize_primary,
        )

    def valid_only(self) -> "DesignSpace":
        """Convenience: filter to status==VALID and all constraints satisfied."""
        return self.filter(lambda c: c.is_valid and c.all_constraints_satisfied)

    # --- Picked / Best in Space / Best in Filter ---------------------------

    def pick(self, index: int) -> None:
        if not (0 <= index < len(self.candidates)):
            msg = f"pick: index {index} out of range [0, {len(self.candidates)})"
            raise IndexError(msg)
        self.picked_index = index

    @property
    def picked(self) -> Optional[Candidate]:
        if self.picked_index is None:
            return None
        return self.candidates[self.picked_index]

    def best(
        self,
        objective: Optional[str] = None,
        minimize: Optional[bool] = None,
    ) -> Optional[Candidate]:
        """The best candidate by `objective`; uses `primary_objective` as default.

        Returns None if no valid candidate is available.
        """
        obj = objective or self.primary_objective
        if obj is None:
            msg = "DesignSpace.best: no objective given and no primary_objective set"
            raise ValueError(msg)
        mn = self.minimize_primary if minimize is None else minimize

        valid = [c for c in self.candidates if c.is_valid and obj in c.objectives]
        if not valid:
            return None
        valid.sort(key=lambda c: c.objective_value(obj), reverse=not mn)
        return valid[0]

    def best_in_space(self) -> Optional[Candidate]:
        """Best valid candidate over the entire space (no filter applied)."""
        return self.best()

    def best_in_filter(
        self,
        predicate: Callable[[Candidate], bool],
    ) -> Optional[Candidate]:
        """Best valid candidate in the subset selected by predicate."""
        sub = self.filter(predicate)
        return sub.best()

    # --- Pareto identification ---------------------------------------------

    def pareto_front(
        self,
        objectives: Sequence[Tuple[str, bool]],
    ) -> List[Candidate]:
        """Non-dominated front for a sequence of (objective_name, minimize) pairs.

        Naive O(N^2) dominance check — fine for v1 / N <= 10000.
        Point a dominates b iff f_i(a) <= f_i(b) for all i with strict
        inequality somewhere.

        Only VALID candidates with all named objectives populated are considered.
        """
        valid = [
            c
            for c in self.candidates
            if c.is_valid and all(o in c.objectives for o, _ in objectives)
        ]
        if not valid:
            return []

        # Pre-extract numeric arrays for speed
        m = len(objectives)
        arr = np.empty((len(valid), m), dtype=float)
        sign = np.empty(m, dtype=float)
        for j, (name, minimize) in enumerate(objectives):
            sign[j] = 1.0 if minimize else -1.0
            for i, c in enumerate(valid):
                arr[i, j] = sign[j] * c.objective_value(name)

        n = arr.shape[0]
        is_pareto = np.ones(n, dtype=bool)
        for i in range(n):
            if not is_pareto[i]:
                continue
            for k in range(n):
                if i == k:
                    continue
                # k dominates i?
                diff = arr[k] - arr[i]
                if np.all(diff <= 0) and np.any(diff < 0):
                    is_pareto[i] = False
                    break
        return [valid[i] for i in range(n) if is_pareto[i]]


# --- Worker entry-point for parallel evaluation -------------------------------


def _evaluate_one(
    args: Tuple[Callable[[Dict[str, Any]], Dict[str, Any]], Dict[str, Any]],
) -> Candidate:
    """Module-level worker so ProcessPoolExecutor can pickle it.

    The evaluator may return a Candidate directly, or a `dict` with keys
    {objectives, constraints, status}. On exception we wrap in
    `status=EVALUATOR_ERROR`.
    """
    evaluator, params = args
    try:
        result = evaluator(params)
    except Exception as exc:  # noqa: BLE001
        return Candidate(
            params=params,
            status=EVALUATOR_ERROR,
            error_message=f"{type(exc).__name__}: {exc}",
        )
    return _coerce_to_candidate(params, result)


def _coerce_to_candidate(params: Dict[str, Any], result: Any) -> Candidate:
    if isinstance(result, Candidate):
        # Re-bind params in case evaluator dropped them
        return replace(result, params=params)
    if isinstance(result, dict):
        return Candidate(
            params=params,
            objectives=dict(result.get("objectives", {})),
            constraints=dict(result.get("constraints", {})),
            status=result.get("status", VALID),
            error_message=result.get("error_message"),
        )
    # Fallback: treat result as a single objective named "y"
    return Candidate(
        params=params,
        objectives={"y": float(result)},
        status=VALID,
    )


# --- Top-level explorer -------------------------------------------------------


@dataclass
class DesignSpaceExplorer:
    """The main entry point: sampler -> parallel evaluation -> DesignSpace.

    Usage:

        explorer = DesignSpaceExplorer()
        space = explorer.run(
            evaluator=my_evaluator,
            sampler=SobolSampler(...),
            constraints=[Constraint("tip_speed", lambda c: c.objectives["U_tip"].magnitude < 450)],
            parallel=8,
        )

    Set `primary_objective` after to enable `best_in_space()`:

        space.primary_objective = "eta_tt"
        space.minimize_primary = False  # maximize η
        space.best_in_space()  # the "Best in Space" of the triad
    """

    def run(
        self,
        evaluator: Callable[[Dict[str, Any]], Any],
        sampler: SobolSampler,
        constraints: Optional[List[Constraint]] = None,
        parallel: int = 1,
        primary_objective: Optional[str] = None,
        minimize_primary: bool = False,
    ) -> DesignSpace:
        """Generate samples, evaluate, apply constraints, return DesignSpace.

        Parallelism: `parallel >= 2` uses a ProcessPoolExecutor; `parallel == 1`
        runs in-process for reproducibility (no fork). One failing candidate
        does not crash the run; the failed Candidate carries
        `status=EVALUATOR_ERROR` and an `error_message`.
        """
        samples = sampler.generate()
        candidates = self._evaluate(evaluator, samples, parallel=parallel)
        if constraints:
            candidates = [self._apply_constraints(c, constraints) for c in candidates]
        space = DesignSpace(
            candidates=candidates,
            primary_objective=primary_objective,
            minimize_primary=minimize_primary,
        )
        return space

    @staticmethod
    def _evaluate(
        evaluator: Callable[[Dict[str, Any]], Any],
        samples: List[Dict[str, Any]],
        parallel: int = 1,
    ) -> List[Candidate]:
        if parallel <= 1:
            results: List[Candidate] = []
            for s in samples:
                results.append(_evaluate_one((evaluator, s)))
            return results

        # Parallel: order-preserving via index
        results = [None] * len(samples)  # type: ignore[assignment]
        with ProcessPoolExecutor(max_workers=parallel) as pool:
            futures = {
                pool.submit(_evaluate_one, (evaluator, s)): i
                for i, s in enumerate(samples)
            }
            for fut in as_completed(futures):
                i = futures[fut]
                try:
                    results[i] = fut.result()
                except Exception as exc:  # noqa: BLE001
                    log.warning("worker raised: %s", exc)
                    results[i] = Candidate(
                        params=samples[i],
                        status=EVALUATOR_ERROR,
                        error_message=f"{type(exc).__name__}: {exc}",
                    )
        return list(results)  # type: ignore[arg-type]

    @staticmethod
    def _apply_constraints(c: Candidate, constraints: List[Constraint]) -> Candidate:
        if c.status != VALID:
            # Don't evaluate constraints on failed candidates.
            return c
        sat: Dict[str, bool] = dict(c.constraints)
        for con in constraints:
            try:
                sat[con.name] = bool(con.predicate(c))
            except Exception as exc:  # noqa: BLE001
                log.debug("constraint %s raised: %s", con.name, exc)
                sat[con.name] = False
        return replace(c, constraints=sat)


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
    "REGIME_OUT_OF_VALIDITY",
    "VALID",
    "ObjectiveValue",
]
