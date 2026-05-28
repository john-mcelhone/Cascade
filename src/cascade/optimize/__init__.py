"""Single- and multi-objective optimization wrappers.

v1 ships:

- **Single-objective**: SLSQP, BOBYQA, CMA-ES — all wrapping
  `scipy.optimize.minimize` under a consistent API. IPOPT is wrapped only
  when `pyomo` is available; otherwise the constructor raises a clear
  error so callers can branch on capability.
- **Multi-objective**: NSGA-II as a minimal in-tree implementation (Deb,
  Pratap, Agarwal & Meyarivan 2002, *IEEE Trans. Evol. Comp.* 6(2):182).
  Includes fast non-dominated sort, crowding distance, tournament selection,
  simulated binary crossover (SBX), and polynomial mutation. Cited at the
  class docstring.

Common API:

    res = OptimizeSLSQP().minimize(objective, x0, bounds, constraints=None)
    res.x, res.fun, res.history

    res = OptimizeNSGA2(pop_size=100, n_gen=200).minimize(
        objective,  # x -> np.ndarray of objective values
        x0_pop=None,
        bounds=[(0, 1), (0, 1), ...],
        n_obj=2,
    )
    res.pareto_x, res.pareto_f
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

import numpy as np
from scipy.optimize import minimize as scipy_minimize


log = logging.getLogger(__name__)


# --- Result types -----------------------------------------------------------


@dataclass
class OptimizationResult:
    """Single-objective optimization result.

    Attributes:
    - `x`: best-found design vector.
    - `fun`: objective at `x`.
    - `success`: whether the underlying optimizer reported success.
    - `n_evals`: total evaluator calls (including any wrapper-level book-keeping).
    - `n_iter`: outer iterations (where reported by the underlying optimizer).
    - `history`: list of (x, fun) tuples logged during optimization.
    - `message`: human-readable status from the underlying optimizer.
    """

    x: np.ndarray
    fun: float
    success: bool = True
    n_evals: int = 0
    n_iter: int = 0
    message: str = ""
    history: List[Tuple[np.ndarray, float]] = field(default_factory=list)


@dataclass
class MultiObjectiveResult:
    """Multi-objective optimization result.

    `pareto_x` is shape (P, d); `pareto_f` is shape (P, m). `population_x`
    and `population_f` are the entire final population (P_total, d) /
    (P_total, m), useful for diversity analysis.
    """

    pareto_x: np.ndarray
    pareto_f: np.ndarray
    population_x: np.ndarray
    population_f: np.ndarray
    n_evals: int = 0
    n_gen: int = 0


# --- Helpers ----------------------------------------------------------------


def _wrap_with_history(
    objective: Callable[[np.ndarray], float],
    history: List[Tuple[np.ndarray, float]],
    eval_counter: List[int],
) -> Callable[[np.ndarray], float]:
    def wrapped(x: np.ndarray) -> float:
        eval_counter[0] += 1
        val = float(objective(np.asarray(x, dtype=float)))
        history.append((np.array(x, copy=True), val))
        return val

    return wrapped


# --- Single-objective optimizers --------------------------------------------


@dataclass
class OptimizeSLSQP:
    """Sequential Least-Squares Programming (Kraft 1988) via scipy.

    Use for smooth nonlinear programs with mixed equality / inequality
    constraints. scipy's SLSQP is the battle-tested reference
    implementation.
    """

    max_iter: int = 200
    ftol: float = 1e-6

    def minimize(
        self,
        objective: Callable[[np.ndarray], float],
        x0: np.ndarray,
        bounds: Optional[Sequence[Tuple[float, float]]] = None,
        constraints: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> OptimizationResult:
        history: List[Tuple[np.ndarray, float]] = []
        counter = [0]
        wrapped = _wrap_with_history(objective, history, counter)
        res = scipy_minimize(
            wrapped,
            np.asarray(x0, dtype=float),
            method="SLSQP",
            bounds=bounds,
            constraints=constraints or (),
            options={"maxiter": self.max_iter, "ftol": self.ftol},
        )
        return OptimizationResult(
            x=np.asarray(res.x, dtype=float),
            fun=float(res.fun),
            success=bool(res.success),
            n_evals=counter[0],
            n_iter=int(getattr(res, "nit", 0)),
            message=str(res.message),
            history=history,
        )


@dataclass
class OptimizeBOBYQA:
    """Bound-constrained, derivative-free trust-region quadratic (Powell 2009).

    scipy doesn't ship BOBYQA proper, but its `method='trust-constr'` /
    `method='L-BFGS-B'` cover similar ground; we use `Powell` (Powell's
    direction-set method, 1964) which is scipy's actual derivative-free
    bound-constrained option closest to BOBYQA in spirit. The constructor
    name `BOBYQA` is preserved for API parity.

    For genuine BOBYQA-quality behavior on a deeper problem, install
    `Py-BOBYQA` and swap the backend; for the OPT-1 Branin pass-gate (a
    smooth 2D function) Powell converges well within 100 evaluations.
    """

    max_iter: int = 200
    xtol: float = 1e-6

    def minimize(
        self,
        objective: Callable[[np.ndarray], float],
        x0: np.ndarray,
        bounds: Optional[Sequence[Tuple[float, float]]] = None,
        constraints: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> OptimizationResult:
        if constraints:
            log.warning(
                "OptimizeBOBYQA: explicit constraints are not supported in v1; "
                "use OptimizeSLSQP. Ignoring %d constraints.",
                len(constraints),
            )
        history: List[Tuple[np.ndarray, float]] = []
        counter = [0]
        wrapped = _wrap_with_history(objective, history, counter)
        # Use Powell — scipy's derivative-free, bound-constrained workhorse
        # closest to BOBYQA's algorithmic family.
        res = scipy_minimize(
            wrapped,
            np.asarray(x0, dtype=float),
            method="Powell",
            bounds=bounds,
            options={"maxiter": self.max_iter, "xtol": self.xtol, "ftol": self.xtol},
        )
        return OptimizationResult(
            x=np.asarray(res.x, dtype=float),
            fun=float(res.fun),
            success=bool(res.success),
            n_evals=counter[0],
            n_iter=int(getattr(res, "nit", 0)),
            message=str(res.message),
            history=history,
        )


@dataclass
class OptimizeCMAES:
    """Covariance-Matrix Adaptation Evolution Strategy (Hansen & Ostermeier 2001).

    A self-contained, dependency-free CMA-ES sufficient for unimodal /
    moderately rugged d <= 30 problems. The full `cma`
    package is the production-grade alternative; this v1 implementation
    is conservative — single-objective, isotropic step-size, full
    covariance update.

    Reference: Hansen, N. (2016) "The CMA Evolution Strategy: A Tutorial."
    arXiv:1604.00772.
    """

    sigma: float = 0.3
    pop_size: Optional[int] = None  # default lambda = 4 + floor(3 * ln(d))
    max_iter: int = 200
    ftol: float = 1e-9
    seed: Optional[int] = 0

    def minimize(
        self,
        objective: Callable[[np.ndarray], float],
        x0: np.ndarray,
        bounds: Optional[Sequence[Tuple[float, float]]] = None,
        constraints: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> OptimizationResult:
        if constraints:
            log.warning(
                "OptimizeCMAES: explicit constraints are not supported. "
                "Use a penalty in the objective. Ignoring %d constraints.",
                len(constraints),
            )

        rng = np.random.default_rng(self.seed)
        x0 = np.asarray(x0, dtype=float)
        d = x0.size
        lam = self.pop_size or (4 + int(math.floor(3.0 * math.log(d))))
        mu = lam // 2
        # Selection weights (log-uniform, mu best)
        raw_weights = np.log(mu + 0.5) - np.log(np.arange(1, mu + 1))
        weights = raw_weights / raw_weights.sum()
        mueff = 1.0 / np.sum(weights ** 2)

        # Strategy parameters
        cc = (4.0 + mueff / d) / (d + 4.0 + 2.0 * mueff / d)
        cs = (mueff + 2.0) / (d + mueff + 5.0)
        c1 = 2.0 / ((d + 1.3) ** 2 + mueff)
        cmu = min(1.0 - c1, 2.0 * (mueff - 2.0 + 1.0 / mueff) / ((d + 2.0) ** 2 + mueff))
        damps = 1.0 + 2.0 * max(0.0, math.sqrt((mueff - 1.0) / (d + 1.0)) - 1.0) + cs

        # Dynamic state
        mean = x0.copy()
        sigma = self.sigma
        C = np.eye(d)
        pc = np.zeros(d)
        ps = np.zeros(d)
        chiN = math.sqrt(d) * (1.0 - 1.0 / (4.0 * d) + 1.0 / (21.0 * d * d))

        # Bound handling (clip — simple but adequate for v1)
        if bounds is not None:
            lo = np.array([b[0] for b in bounds], dtype=float)
            hi = np.array([b[1] for b in bounds], dtype=float)
        else:
            lo = None
            hi = None

        history: List[Tuple[np.ndarray, float]] = []
        n_evals = 0
        best_x = mean.copy()
        best_f = float("inf")

        for gen in range(self.max_iter):
            # Sample population
            # np.linalg.eigh returns (eigenvalues, eigenvectors).
            try:
                D, B = np.linalg.eigh(C)
            except np.linalg.LinAlgError:
                # Regularize
                C = (C + C.T) / 2.0 + 1e-12 * np.eye(d)
                D, B = np.linalg.eigh(C)
            # Clamp eigenvalues to positive (covariance must be PSD).
            D = np.maximum(D, 1e-20)
            BD = B * np.sqrt(D)  # shape (d, d) — column-wise scaling

            zs = rng.standard_normal((lam, d))
            xs = mean + sigma * (zs @ BD.T)
            if lo is not None:
                xs = np.clip(xs, lo, hi)

            fs = np.empty(lam)
            for k in range(lam):
                fs[k] = float(objective(xs[k]))
                history.append((xs[k].copy(), fs[k]))
                n_evals += 1
                if fs[k] < best_f:
                    best_f = fs[k]
                    best_x = xs[k].copy()

            order = np.argsort(fs)
            x_sel = xs[order[:mu]]
            new_mean = weights @ x_sel

            # Update evolution paths
            invsqrtC = B @ np.diag(1.0 / np.sqrt(D)) @ B.T
            ps = (1.0 - cs) * ps + math.sqrt(cs * (2.0 - cs) * mueff) * invsqrtC @ (
                (new_mean - mean) / sigma
            )
            hsig_threshold = (1.4 + 2.0 / (d + 1.0)) * chiN
            hsig = np.linalg.norm(ps) / math.sqrt(
                1.0 - (1.0 - cs) ** (2.0 * (gen + 1))
            ) < hsig_threshold
            pc = (1.0 - cc) * pc + (
                hsig * math.sqrt(cc * (2.0 - cc) * mueff)
            ) * (new_mean - mean) / sigma

            # Adapt covariance
            artmp = (x_sel - mean) / sigma
            C = (
                (1.0 - c1 - cmu) * C
                + c1 * (np.outer(pc, pc) + (1.0 - hsig) * cc * (2.0 - cc) * C)
                + cmu * artmp.T @ np.diag(weights) @ artmp
            )

            # Adapt step size
            sigma *= math.exp((cs / damps) * (np.linalg.norm(ps) / chiN - 1.0))
            mean = new_mean

            # Convergence: best-objective standard deviation below ftol
            if gen >= 4:
                recent = [h[1] for h in history[-4 * lam :]]
                if np.std(recent) < self.ftol:
                    break

        return OptimizationResult(
            x=best_x,
            fun=best_f,
            success=True,
            n_evals=n_evals,
            n_iter=gen + 1,
            message="cma-es: max-iter or ftol reached",
            history=history,
        )


@dataclass
class OptimizeIPOPT:
    """Interior-point NLP via pyomo + ipopt.

    Only constructible when `pyomo` is importable. Per v1 scope: this is
    a *thin* adapter — large-scale sparse problems benefit, but the demo
    cases (Branin, OPT-1) fit in scipy SLSQP. Documented in KNOWN_GAPS.
    """

    max_iter: int = 200
    tol: float = 1e-6

    def __post_init__(self) -> None:
        try:
            import pyomo.environ  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "OptimizeIPOPT requires the optional `pyomo` dependency "
                "(and an `ipopt` executable on PATH). Install via pip and "
                "see docs/optimization.md."
            ) from exc

    def minimize(
        self,
        objective: Callable[[np.ndarray], float],
        x0: np.ndarray,
        bounds: Optional[Sequence[Tuple[float, float]]] = None,
        constraints: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> OptimizationResult:
        # Lightweight pyomo wrapper — sufficient for the v1 IPOPT-shim slot;
        # production tier passes its own pyomo model.
        import pyomo.environ as pyo  # type: ignore[import-untyped]
        from pyomo.opt import SolverFactory  # type: ignore[import-untyped]

        d = len(x0)
        m = pyo.ConcreteModel()
        m.I = pyo.RangeSet(0, d - 1)
        if bounds is None:
            m.x = pyo.Var(m.I, initialize=lambda _, i: float(x0[i]))
        else:
            m.x = pyo.Var(
                m.I,
                initialize=lambda _, i: float(x0[i]),
                bounds=lambda _, i: bounds[i],
            )

        def obj_rule(model: Any) -> Any:
            arr = np.array([pyo.value(model.x[i]) for i in model.I])
            return float(objective(arr))

        m.obj = pyo.Objective(rule=obj_rule, sense=pyo.minimize)

        solver = SolverFactory("ipopt")
        results = solver.solve(m, tee=False)
        x_final = np.array([pyo.value(m.x[i]) for i in m.I], dtype=float)
        return OptimizationResult(
            x=x_final,
            fun=float(pyo.value(m.obj)),
            success=str(results.solver.termination_condition) == "optimal",
            n_evals=int(results.solver.iterations) if hasattr(results.solver, "iterations") else 0,
            message=str(results.solver.termination_condition),
        )


# --- Multi-objective: NSGA-II (in-tree, Deb et al. 2002) -------------------


@dataclass
class OptimizeNSGA2:
    """NSGA-II multi-objective optimizer (Deb, Pratap, Agarwal & Meyarivan 2002,
    *IEEE Transactions on Evolutionary Computation* 6(2):182-197).

    In-tree implementation with:
    - Fast non-dominated sort (Deb 2002 Algorithm 1)
    - Crowding distance assignment (Deb 2002 §3B)
    - Binary tournament on (rank, crowding) for parent selection
    - Simulated binary crossover (SBX; Deb & Agrawal 1995) for real-valued vars
    - Polynomial mutation (Deb & Goyal 1996)

    Sufficient for the OPT-2 / ZDT2 pass-gate. For production deployments
    on m >= 4 or n_pop >= 500, the pymoo NSGA-III implementation is the
    recommended path (documented in KNOWN_GAPS.md).
    """

    pop_size: int = 100
    n_gen: int = 200
    eta_c: float = 15.0  # SBX distribution index (Deb recommended)
    eta_m: float = 20.0  # polynomial mutation distribution index
    crossover_prob: float = 0.9
    seed: Optional[int] = 0

    def minimize(
        self,
        objective: Callable[[np.ndarray], np.ndarray],
        bounds: Sequence[Tuple[float, float]],
        n_obj: int,
        x0_pop: Optional[np.ndarray] = None,
    ) -> MultiObjectiveResult:
        rng = np.random.default_rng(self.seed)
        d = len(bounds)
        lo = np.array([b[0] for b in bounds], dtype=float)
        hi = np.array([b[1] for b in bounds], dtype=float)
        # Mutation probability per gene (Deb default: 1/d)
        mut_prob = 1.0 / d

        # Initialize population
        if x0_pop is None:
            pop_x = lo + rng.random((self.pop_size, d)) * (hi - lo)
        else:
            pop_x = np.asarray(x0_pop, dtype=float)
            assert pop_x.shape == (self.pop_size, d)

        pop_f = self._eval_pop(objective, pop_x, n_obj)
        n_evals = self.pop_size

        for gen in range(self.n_gen):
            # 1. Selection
            ranks, crowds = self._rank_and_crowd(pop_f)
            parents = self._tournament_selection(pop_x, ranks, crowds, rng)

            # 2. Crossover + mutation
            offspring = self._crossover(parents, lo, hi, rng)
            offspring = self._mutate(offspring, lo, hi, mut_prob, rng)

            # 3. Evaluate offspring
            off_f = self._eval_pop(objective, offspring, n_obj)
            n_evals += offspring.shape[0]

            # 4. Combine and select next generation (elitist)
            combined_x = np.vstack([pop_x, offspring])
            combined_f = np.vstack([pop_f, off_f])
            pop_x, pop_f = self._select_next_generation(combined_x, combined_f, self.pop_size)

        # Extract Pareto front (rank 0)
        ranks, _ = self._rank_and_crowd(pop_f)
        pareto_mask = ranks == 0
        return MultiObjectiveResult(
            pareto_x=pop_x[pareto_mask],
            pareto_f=pop_f[pareto_mask],
            population_x=pop_x,
            population_f=pop_f,
            n_evals=n_evals,
            n_gen=self.n_gen,
        )

    # --- helpers --------------------------------------------------------

    @staticmethod
    def _eval_pop(
        objective: Callable[[np.ndarray], np.ndarray],
        pop: np.ndarray,
        n_obj: int,
    ) -> np.ndarray:
        n = pop.shape[0]
        out = np.empty((n, n_obj), dtype=float)
        for i in range(n):
            f = np.asarray(objective(pop[i]), dtype=float).reshape(-1)
            if f.size != n_obj:
                raise ValueError(
                    f"Objective returned {f.size} values; expected n_obj={n_obj}"
                )
            # Replace NaN with +inf
            out[i] = np.where(np.isfinite(f), f, np.inf)
        return out

    @staticmethod
    def _dominates(a: np.ndarray, b: np.ndarray) -> bool:
        """`a` dominates `b` iff all coords <= and at least one strictly <."""
        le = a <= b
        lt = a < b
        return bool(np.all(le) and np.any(lt))

    def _fast_nondominated_sort(self, F: np.ndarray) -> List[np.ndarray]:
        """Deb 2002 Algorithm 1. Returns fronts as list of index arrays."""
        n = F.shape[0]
        S: List[List[int]] = [[] for _ in range(n)]
        n_dom = np.zeros(n, dtype=int)
        rank = np.full(n, -1, dtype=int)
        fronts: List[List[int]] = [[]]
        for p in range(n):
            for q in range(n):
                if p == q:
                    continue
                if self._dominates(F[p], F[q]):
                    S[p].append(q)
                elif self._dominates(F[q], F[p]):
                    n_dom[p] += 1
            if n_dom[p] == 0:
                rank[p] = 0
                fronts[0].append(p)
        k = 0
        while fronts[k]:
            next_front: List[int] = []
            for p in fronts[k]:
                for q in S[p]:
                    n_dom[q] -= 1
                    if n_dom[q] == 0:
                        rank[q] = k + 1
                        next_front.append(q)
            k += 1
            fronts.append(next_front)
        return [np.array(f, dtype=int) for f in fronts[:-1]]

    @staticmethod
    def _crowding_distance(F: np.ndarray, idx: np.ndarray) -> np.ndarray:
        """Crowding distance (Deb 2002 §3B) for indices `idx`."""
        if idx.size == 0:
            return np.array([], dtype=float)
        if idx.size <= 2:
            return np.full(idx.size, np.inf, dtype=float)
        m = F.shape[1]
        Fsub = F[idx]
        dist = np.zeros(idx.size, dtype=float)
        for j in range(m):
            order = np.argsort(Fsub[:, j])
            dist[order[0]] = np.inf
            dist[order[-1]] = np.inf
            fmin = Fsub[order[0], j]
            fmax = Fsub[order[-1], j]
            denom = fmax - fmin if fmax > fmin else 1.0
            for k in range(1, idx.size - 1):
                dist[order[k]] += (
                    Fsub[order[k + 1], j] - Fsub[order[k - 1], j]
                ) / denom
        return dist

    def _rank_and_crowd(self, F: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        n = F.shape[0]
        fronts = self._fast_nondominated_sort(F)
        ranks = np.zeros(n, dtype=int)
        crowds = np.zeros(n, dtype=float)
        for r, front in enumerate(fronts):
            ranks[front] = r
            crowds[front] = self._crowding_distance(F, front)
        return ranks, crowds

    @staticmethod
    def _tournament_selection(
        pop_x: np.ndarray,
        ranks: np.ndarray,
        crowds: np.ndarray,
        rng: np.random.Generator,
    ) -> np.ndarray:
        n = pop_x.shape[0]
        out = np.empty_like(pop_x)
        for i in range(n):
            a, b = rng.integers(0, n, size=2)
            # Crowded-comparison operator
            if ranks[a] < ranks[b]:
                winner = a
            elif ranks[a] > ranks[b]:
                winner = b
            elif crowds[a] > crowds[b]:
                winner = a
            else:
                winner = b
            out[i] = pop_x[winner]
        return out

    def _crossover(
        self,
        parents: np.ndarray,
        lo: np.ndarray,
        hi: np.ndarray,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Simulated binary crossover (SBX; Deb & Agrawal 1995)."""
        n, d = parents.shape
        offspring = parents.copy()
        eta = self.eta_c
        for i in range(0, n - 1, 2):
            if rng.random() > self.crossover_prob:
                continue
            p1 = parents[i]
            p2 = parents[i + 1]
            for j in range(d):
                if rng.random() > 0.5:
                    continue
                if abs(p1[j] - p2[j]) < 1e-14:
                    continue
                x1 = min(p1[j], p2[j])
                x2 = max(p1[j], p2[j])
                xl, xu = lo[j], hi[j]
                if xu - xl < 1e-14:
                    continue
                beta = 1.0 + 2.0 * (x1 - xl) / (x2 - x1)
                alpha = 2.0 - beta ** (-(eta + 1.0))
                u = rng.random()
                if u <= 1.0 / alpha:
                    betaq = (u * alpha) ** (1.0 / (eta + 1.0))
                else:
                    betaq = (1.0 / (2.0 - u * alpha)) ** (1.0 / (eta + 1.0))
                c1 = 0.5 * ((x1 + x2) - betaq * (x2 - x1))
                beta = 1.0 + 2.0 * (xu - x2) / (x2 - x1)
                alpha = 2.0 - beta ** (-(eta + 1.0))
                if u <= 1.0 / alpha:
                    betaq = (u * alpha) ** (1.0 / (eta + 1.0))
                else:
                    betaq = (1.0 / (2.0 - u * alpha)) ** (1.0 / (eta + 1.0))
                c2 = 0.5 * ((x1 + x2) + betaq * (x2 - x1))
                # Clip + random swap (Deb's reference impl convention)
                c1 = np.clip(c1, xl, xu)
                c2 = np.clip(c2, xl, xu)
                if rng.random() < 0.5:
                    offspring[i, j] = c2
                    offspring[i + 1, j] = c1
                else:
                    offspring[i, j] = c1
                    offspring[i + 1, j] = c2
        return offspring

    def _mutate(
        self,
        pop: np.ndarray,
        lo: np.ndarray,
        hi: np.ndarray,
        mut_prob: float,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Polynomial mutation (Deb & Goyal 1996)."""
        out = pop.copy()
        n, d = out.shape
        eta = self.eta_m
        for i in range(n):
            for j in range(d):
                if rng.random() > mut_prob:
                    continue
                xl, xu = lo[j], hi[j]
                if xu - xl < 1e-14:
                    continue
                x = out[i, j]
                delta1 = (x - xl) / (xu - xl)
                delta2 = (xu - x) / (xu - xl)
                u = rng.random()
                mut_pow = 1.0 / (eta + 1.0)
                if u <= 0.5:
                    xy = 1.0 - delta1
                    val = 2.0 * u + (1.0 - 2.0 * u) * (xy ** (eta + 1.0))
                    deltaq = val ** mut_pow - 1.0
                else:
                    xy = 1.0 - delta2
                    val = 2.0 * (1.0 - u) + 2.0 * (u - 0.5) * (xy ** (eta + 1.0))
                    deltaq = 1.0 - val ** mut_pow
                x = x + deltaq * (xu - xl)
                out[i, j] = float(np.clip(x, xl, xu))
        return out

    def _select_next_generation(
        self,
        combined_x: np.ndarray,
        combined_f: np.ndarray,
        n_target: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        fronts = self._fast_nondominated_sort(combined_f)
        new_x_list: List[np.ndarray] = []
        new_f_list: List[np.ndarray] = []
        for front in fronts:
            if sum(a.shape[0] for a in new_x_list) + front.size <= n_target:
                new_x_list.append(combined_x[front])
                new_f_list.append(combined_f[front])
            else:
                remaining = n_target - sum(a.shape[0] for a in new_x_list)
                if remaining <= 0:
                    break
                dist = self._crowding_distance(combined_f, front)
                order = np.argsort(-dist)  # descending
                chosen = front[order[:remaining]]
                new_x_list.append(combined_x[chosen])
                new_f_list.append(combined_f[chosen])
                break
        return np.vstack(new_x_list), np.vstack(new_f_list)


class OptimizeNSGA3:
    """NSGA-III placeholder — declared, not implemented in v1.

    NSGA-III is required for m >= 4 objectives. v1 ships NSGA-II only;
    a real NSGA-III adapter via
    pymoo lands in v1.1. Calling `minimize` raises NotImplementedError
    with a pointer to KNOWN_GAPS.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def minimize(self, *args: Any, **kwargs: Any) -> MultiObjectiveResult:
        raise NotImplementedError(
            "NSGA-III is not implemented in v1; install pymoo and use its "
            "NSGA3 algorithm directly. See KNOWN_GAPS.md."
        )


# Alias matching the spec's `OptimizeNSGA2Naive` name
OptimizeNSGA2Naive = OptimizeNSGA2


# --- Utility: hypervolume (Deb 2002) -----------------------


def hypervolume_2d(front: np.ndarray, reference: Tuple[float, float]) -> float:
    """Hypervolume of a 2D minimization Pareto front w.r.t. a reference point.

    For m == 2 the closed-form is exact and cheap: sort by f1 ascending,
    walk left-to-right, accumulate rectangles between consecutive front
    points and the reference. Used by tests/optimize/test_opt2_zdt2.py.
    """
    if front.shape[1] != 2:
        raise ValueError(f"hypervolume_2d requires m=2; got m={front.shape[1]}")
    ref = np.asarray(reference, dtype=float)
    # Drop dominated / out-of-bounds points
    keep_mask = np.all(front <= ref, axis=1)
    F = front[keep_mask]
    if F.size == 0:
        return 0.0
    order = np.argsort(F[:, 0])
    F = F[order]
    # Walk left-to-right; accumulate rectangle areas
    hv = 0.0
    prev_x = F[0, 0]
    prev_y = ref[1]
    for i in range(F.shape[0]):
        x, y = F[i, 0], F[i, 1]
        if y < prev_y:
            hv += (ref[0] - x) * (prev_y - y) if i == 0 else 0.0
            # Walk: rectangle width (next_x - x) * (prev_y - y); we'll
            # handle that on next iteration.
            prev_y = y
            prev_x = x
    # Simpler accurate computation:
    hv = 0.0
    F_sorted = F[np.argsort(F[:, 0])]
    last_y = ref[1]
    for x, y in F_sorted:
        if y < last_y:
            hv += (ref[0] - x) * (last_y - y)
            last_y = y
    return float(hv)


__all__ = [
    "MultiObjectiveResult",
    "OptimizationResult",
    "OptimizeBOBYQA",
    "OptimizeCMAES",
    "OptimizeIPOPT",
    "OptimizeNSGA2",
    "OptimizeNSGA2Naive",
    "OptimizeNSGA3",
    "OptimizeSLSQP",
    "hypervolume_2d",
]
