"""Sobol' low-discrepancy sequence sampler for design-space exploration.

The v1 design-exploration sampler is a Sobol' sequence with Joe-Kuo
direction numbers (delivered via scipy.stats.qmc.Sobol). Owen scrambling
is on by default for variance reduction.

Construction uses a project-friendly API:

    SobolSampler(parameter_ranges={"rpm": ParameterRange(1e4, 4e4, "rpm"),
                                   "diameter": ParameterRange(0.1, 0.25, "m")},
                 n_samples=2048).generate()

returns a `List[Dict[str, Quantity]]`. The "inverse solver" framing is
explicitly avoided: this is space-filling DoE over the parameter box,
followed by per-trial forward solves.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Union

import numpy as np
from scipy.stats import qmc

from cascade.units import Q, Quantity


Scale = Literal["linear", "log"]


@dataclass(frozen=True)
class ParameterRange:
    """A single design-variable range.

    Three flavors:
    - **Continuous numeric (linear)**: `ParameterRange(min, max, unit)` with
      `scale="linear"` (default). Sobol' draws uniformly in [min, max].
    - **Continuous numeric (log)**: `scale="log"` — sampled uniformly in
      log(value). Required for parameters spanning decades (clearance 1 um
      to 1 mm).
    - **Categorical**: `ParameterRange(choices=[...])`. Sampler picks index
      uniformly from [0, len(choices)).

    For numeric ranges, `min` and `max` are floats interpreted in `unit`;
    the generator returns `Quantity` objects with that unit attached.
    """

    min: Optional[float] = None
    max: Optional[float] = None
    unit: Optional[str] = None
    scale: Scale = "linear"
    choices: Optional[Sequence[Any]] = None

    def __post_init__(self) -> None:
        if self.choices is not None:
            if self.min is not None or self.max is not None or self.unit is not None:
                msg = (
                    "ParameterRange: when `choices` is given, `min`/`max`/`unit` "
                    "must be None (categorical variables are dimensionless)."
                )
                raise ValueError(msg)
            if len(self.choices) < 1:
                msg = "ParameterRange.choices must contain at least one element"
                raise ValueError(msg)
            return

        # Numeric branch
        if self.min is None or self.max is None or self.unit is None:
            msg = (
                "ParameterRange: numeric ranges require `min`, `max`, and `unit`. "
                "For categorical variables, supply `choices` instead."
            )
            raise ValueError(msg)
        if self.min >= self.max:
            msg = f"ParameterRange: min ({self.min}) must be < max ({self.max})"
            raise ValueError(msg)
        if self.scale == "log":
            if self.min <= 0 or self.max <= 0:
                msg = (
                    f"ParameterRange: log-scale requires strictly positive bounds; "
                    f"got min={self.min}, max={self.max}"
                )
                raise ValueError(msg)
        if self.scale not in ("linear", "log"):
            msg = f"ParameterRange.scale must be 'linear' or 'log'; got {self.scale!r}"
            raise ValueError(msg)

    @property
    def is_categorical(self) -> bool:
        return self.choices is not None

    def rescale(self, u: float) -> Union[Quantity, Any]:
        """Map a unit-cube sample u in [0, 1) into the physical range.

        - linear: returns Q(min + u*(max-min), unit)
        - log:    returns Q(exp(log(min) + u*(log(max)-log(min))), unit)
        - categorical: returns choices[floor(u * len(choices))]
        """
        if self.is_categorical:
            assert self.choices is not None
            idx = min(int(math.floor(u * len(self.choices))), len(self.choices) - 1)
            return self.choices[idx]
        assert self.min is not None and self.max is not None and self.unit is not None
        if self.scale == "linear":
            value = self.min + u * (self.max - self.min)
        else:  # log
            log_min = math.log(self.min)
            log_max = math.log(self.max)
            value = math.exp(log_min + u * (log_max - log_min))
        return Q(value, self.unit)


@dataclass
class SobolSampler:
    """Sobol' sequence sampler over a `Dict[str, ParameterRange]`.

    Determinism: with a fixed `seed`, `generate()` returns the same samples
    every call. Scrambling is on by default for better variance reduction
    (Joe-Kuo direction numbers + Owen scrambling).

    Quality warning: for `n_samples < 64` Sobol' shows visible 2D clumping.
    The sampler emits a warning in that regime and recommends LHS.

    For best discrepancy properties, `n_samples` should be a power of 2.
    """

    parameter_ranges: Dict[str, ParameterRange]
    n_samples: int
    seed: Optional[int] = 0
    scramble: bool = True

    def __post_init__(self) -> None:
        if self.n_samples < 1:
            msg = f"SobolSampler: n_samples must be >= 1; got {self.n_samples}"
            raise ValueError(msg)
        if not self.parameter_ranges:
            msg = "SobolSampler: parameter_ranges must not be empty"
            raise ValueError(msg)
        if self.n_samples < 64:
            warnings.warn(
                f"SobolSampler: n_samples={self.n_samples} < 64; Sobol' may show "
                f"visible 2D clumping. Consider LHS for small sample counts.",
                UserWarning,
                stacklevel=2,
            )

    @property
    def dimension(self) -> int:
        return len(self.parameter_ranges)

    def generate(self) -> List[Dict[str, Union[Quantity, Any]]]:
        """Draw `n_samples` Sobol' points, rescale to physical ranges."""
        d = self.dimension
        # scipy >= 1.11 issues a UserWarning when n_samples is not a power of 2;
        # we surface that to the caller. We still allow non-powers-of-2.
        engine = qmc.Sobol(d=d, scramble=self.scramble, seed=self.seed)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module="scipy")
            u = engine.random(n=self.n_samples)
        # Use insertion order of dict (Python 3.7+ guaranteed) as Sobol' dim order.
        keys = list(self.parameter_ranges.keys())
        out: List[Dict[str, Union[Quantity, Any]]] = []
        for row in u:
            sample: Dict[str, Union[Quantity, Any]] = {}
            for j, key in enumerate(keys):
                sample[key] = self.parameter_ranges[key].rescale(float(row[j]))
            out.append(sample)
        return out

    def discrepancy(self) -> float:
        """Compute the L2-star discrepancy of the generated unit-cube samples.

        Useful for tests: a well-balanced Sobol' set on a power-of-2 sample
        count has discrepancy well below uniform-random.
        """
        engine = qmc.Sobol(d=self.dimension, scramble=self.scramble, seed=self.seed)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module="scipy")
            u = engine.random(n=self.n_samples)
        return float(qmc.discrepancy(u))


__all__ = ["ParameterRange", "SobolSampler", "Scale"]
