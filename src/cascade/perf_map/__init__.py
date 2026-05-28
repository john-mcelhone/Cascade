"""Performance map generator: parametric grid + surge / choke detection.

Legacy desktop tools used an ambiguous `Returned code = -1` for any
non-converged point. v1 replaces that with explicit, distinct codes:

- `CONVERGED`           — solution found, all outputs in physical range
- `NON_CONVERGED`       — iteration limit hit, residual above tolerance
- `CHOKED`              — throat M >= 1 or mass-flow saturation
- `STALL_SURGE`         — positive-slope speedline or explicit stall flag
- `INVALID_GEOMETRY`    — geometry constraint violated
- `REGIME_OUT_OF_VALIDITY` — loss-model validity check failed
- `TIMEOUT`             — per-evaluation wall-clock exceeded
- `INFEASIBLE_BC`       — BCs inconsistent (e.g. outlet P > inlet P)

Surge-line detection: per speedline, fit a cubic spline
through (m_dot_corr, pi); the surge line is the leftmost point where
the slope drops to `-1e-3 * (pi_design / m_dot_design)` or steeper toward
zero (i.e. dpi/dm >= -1e-3 * pi_d / m_d).

Choke detection: rightmost point on a speedline where evaluator returned
`CHOKED`.

Exports: CSV, JSON, HDF5 (HDF5 only if h5py is installed; otherwise raises).
"""

from __future__ import annotations

import csv
import dataclasses
import itertools
import json
import logging
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)

import numpy as np
from scipy.interpolate import CubicSpline

from cascade.units import Q, Quantity


log = logging.getLogger(__name__)


# --- Status codes -----------------------------------------------------------

# String codes (not Enum) so they serialize to JSON / CSV / HDF5 trivially.
CONVERGED = "CONVERGED"
CHOKED = "CHOKED"
STALL_SURGE = "STALL_SURGE"
NON_CONVERGED = "NON_CONVERGED"
INVALID_GEOMETRY = "INVALID_GEOMETRY"
REGIME_OUT_OF_VALIDITY = "REGIME_OUT_OF_VALIDITY"
TIMEOUT = "TIMEOUT"
INFEASIBLE_BC = "INFEASIBLE_BC"

ALL_CODES = frozenset(
    {
        CONVERGED,
        CHOKED,
        STALL_SURGE,
        NON_CONVERGED,
        INVALID_GEOMETRY,
        REGIME_OUT_OF_VALIDITY,
        TIMEOUT,
        INFEASIBLE_BC,
    }
)


# --- Grid point data ---------------------------------------------------------


@dataclass(frozen=True)
class GridPoint:
    """A single (grid-coordinates -> output) cell of the map.

    `coords` carries the input vector at this point (e.g. {m_dot, rpm}).
    `outputs` carries the derived quantities (pi, eta, power, ...).
    `status` is the explicit per-point code.
    """

    coords: Dict[str, float]
    outputs: Dict[str, Union[Quantity, float]] = field(default_factory=dict)
    status: str = CONVERGED
    error_message: Optional[str] = None

    def __post_init__(self) -> None:
        if self.status not in ALL_CODES:
            msg = f"GridPoint.status must be in {sorted(ALL_CODES)}; got {self.status!r}"
            raise ValueError(msg)

    @property
    def is_converged(self) -> bool:
        return self.status == CONVERGED


@dataclass
class PerformanceMap:
    """A structured performance map: grid-axis names + a flat list of points.

    Provides:
    - `to_array(name)`: reshape a scalar output into an N-D ndarray aligned
      with the grid axes.
    - `speedlines(group_by)`: yield per-group sequences sorted by m_dot.
    - `detect_surge_line(...)` and `detect_choke_line(...)`.
    - CSV / JSON / HDF5 export.
    """

    axes: Dict[str, np.ndarray]  # ordered (insertion order)
    points: List[GridPoint] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # --- Construction ------------------------------------------------------

    @classmethod
    def generate(
        cls,
        evaluator: Callable[[Dict[str, float]], Any],
        grid: Dict[str, np.ndarray],
        parallel: int = 1,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "PerformanceMap":
        """Evaluate `evaluator` over the Cartesian product of `grid`.

        `evaluator(coords)` returns one of:
        - a `GridPoint` directly,
        - a `dict` with keys {outputs, status, error_message},
        - a 2-tuple `(status, outputs_dict)`,
        - a 3-tuple `(status, outputs_dict, error_message)`.

        Parallelism: `parallel >= 2` -> ProcessPoolExecutor. One failing
        cell does not abort the map; it lands with status `NON_CONVERGED`
        plus an `error_message`.
        """
        # Preserve axis insertion order; numpy arrays go through unchanged.
        axes = {k: np.asarray(v, dtype=float) for k, v in grid.items()}
        if not axes:
            msg = "PerformanceMap.generate: grid must contain at least one axis"
            raise ValueError(msg)
        coord_keys = list(axes.keys())
        coord_arrays = [axes[k] for k in coord_keys]
        all_coords: List[Dict[str, float]] = [
            dict(zip(coord_keys, tup))
            for tup in itertools.product(*coord_arrays)
        ]

        if parallel <= 1:
            points = [_evaluate_grid_point((evaluator, c)) for c in all_coords]
        else:
            points = [None] * len(all_coords)  # type: ignore[assignment]
            with ProcessPoolExecutor(max_workers=parallel) as pool:
                futures = {
                    pool.submit(_evaluate_grid_point, (evaluator, c)): i
                    for i, c in enumerate(all_coords)
                }
                for fut in as_completed(futures):
                    i = futures[fut]
                    try:
                        points[i] = fut.result()
                    except Exception as exc:  # noqa: BLE001
                        points[i] = GridPoint(
                            coords=all_coords[i],
                            status=NON_CONVERGED,
                            error_message=f"{type(exc).__name__}: {exc}",
                        )
            points = list(points)  # type: ignore[assignment]

        return cls(axes=axes, points=points, metadata=dict(metadata or {}))

    # --- Array view --------------------------------------------------------

    def to_array(self, output_name: str, fill: float = float("nan")) -> np.ndarray:
        """Reshape `output_name` into an N-D array aligned with `axes`.

        Non-converged or missing-output cells get `fill` (default NaN).
        Quantity outputs are reduced to their base-SI magnitude.
        """
        shape = tuple(len(v) for v in self.axes.values())
        out = np.full(shape, fill, dtype=float)
        # Build a coords-tuple -> index map for stable assignment regardless
        # of point insertion order
        axis_index: Dict[str, Dict[float, int]] = {
            name: {float(v): i for i, v in enumerate(arr)}
            for name, arr in self.axes.items()
        }
        for p in self.points:
            if output_name not in p.outputs:
                continue
            try:
                idx = tuple(axis_index[name][float(p.coords[name])] for name in self.axes)
            except KeyError:
                # Coordinate not on the registered grid; skip.
                continue
            val = p.outputs[output_name]
            if isinstance(val, Quantity):
                out[idx] = float(val.to_base_units().magnitude)
            else:
                out[idx] = float(val)
        return out

    def status_array(self) -> np.ndarray:
        """N-D object array of status codes aligned with `axes`."""
        shape = tuple(len(v) for v in self.axes.values())
        out = np.full(shape, "MISSING", dtype=object)
        axis_index: Dict[str, Dict[float, int]] = {
            name: {float(v): i for i, v in enumerate(arr)}
            for name, arr in self.axes.items()
        }
        for p in self.points:
            try:
                idx = tuple(axis_index[name][float(p.coords[name])] for name in self.axes)
            except KeyError:
                continue
            out[idx] = p.status
        return out

    # --- Speedline grouping ------------------------------------------------

    def speedlines(
        self,
        group_by: str,
        flow_axis: str,
    ) -> List[Tuple[float, List[GridPoint]]]:
        """Group grid points by `group_by` axis value, sort within group by `flow_axis`.

        Returns: [(group_value, [points sorted by flow_axis]), ...]

        Useful for surge/choke detection: feed the (m_dot, pi) speedline
        through `detect_surge_line_for_speedline`.
        """
        if group_by not in self.axes:
            msg = f"speedlines: group_by {group_by!r} not in axes {list(self.axes)}"
            raise KeyError(msg)
        if flow_axis not in self.axes:
            msg = f"speedlines: flow_axis {flow_axis!r} not in axes {list(self.axes)}"
            raise KeyError(msg)

        groups: Dict[float, List[GridPoint]] = {}
        for p in self.points:
            key = float(p.coords[group_by])
            groups.setdefault(key, []).append(p)
        out: List[Tuple[float, List[GridPoint]]] = []
        for key in sorted(groups.keys()):
            pts = sorted(groups[key], key=lambda x: float(x.coords[flow_axis]))
            out.append((key, pts))
        return out

    # --- Surge / choke detection ------------------------------------------

    def detect_surge_line(
        self,
        speed_axis: str,
        flow_axis: str = "m_dot",
        pi_output: str = "pi",
        pi_design: float = 1.0,
        m_dot_design: float = 1.0,
        slope_threshold: float = -1e-3,
    ) -> List[Tuple[float, float, float]]:
        """Surge line per speedline, via cubic-spline regression on (m_dot, pi).

        Per SPEC_SHEET §13:
            surge = leftmost (m_dot_corr, pi) where
                dpi/dm >= slope_threshold * (pi_design / m_dot_design).

        Returns a list of `(speed_value, m_dot_surge, pi_surge)` tuples,
        one per speedline. Speedlines with too few converged points to
        fit a spline are skipped.

        Notes:
        - Points with `status == STALL_SURGE` are honored as immediate
          surge candidates and override the spline regression for that
          speedline.
        - The spline is fit to converged points only (CONVERGED or
          STALL_SURGE on the right side of the surge boundary).
        """
        results: List[Tuple[float, float, float]] = []
        threshold = slope_threshold * (pi_design / m_dot_design)
        for speed, pts in self.speedlines(speed_axis, flow_axis):
            surge = _detect_surge_for_speedline(
                pts, flow_axis, pi_output, threshold=threshold
            )
            if surge is not None:
                results.append((speed, surge[0], surge[1]))
        return results

    def detect_choke_line(
        self,
        speed_axis: str,
        flow_axis: str = "m_dot",
        pi_output: str = "pi",
    ) -> List[Tuple[float, float, float]]:
        """Choke line per speedline: rightmost CHOKED point.

        Returns `[(speed_value, m_dot_choke, pi_at_choke), ...]`.
        """
        results: List[Tuple[float, float, float]] = []
        for speed, pts in self.speedlines(speed_axis, flow_axis):
            choked = [p for p in pts if p.status == CHOKED]
            if not choked:
                continue
            # Rightmost (highest m_dot) choked point
            rightmost = max(choked, key=lambda x: float(x.coords[flow_axis]))
            m_dot = float(rightmost.coords[flow_axis])
            pi_val = rightmost.outputs.get(pi_output)
            if isinstance(pi_val, Quantity):
                pi_num = float(pi_val.to_base_units().magnitude)
            elif pi_val is None:
                pi_num = float("nan")
            else:
                pi_num = float(pi_val)
            results.append((speed, m_dot, pi_num))
        return results

    # --- Export ------------------------------------------------------------

    def to_csv(self, path: str) -> None:
        """Flat-row CSV export.

        Schema: one row per grid point. Columns: every axis name, then
        `status`, then every output name (sorted) at base-SI magnitude.
        """
        # Collect output names across all points (sorted, deterministic)
        output_names = sorted({k for p in self.points for k in p.outputs})
        axis_names = list(self.axes.keys())
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow([*axis_names, "status", *output_names, "error_message"])
            for p in self.points:
                row: List[Any] = [p.coords.get(a, "") for a in axis_names]
                row.append(p.status)
                for name in output_names:
                    v = p.outputs.get(name)
                    if isinstance(v, Quantity):
                        row.append(float(v.to_base_units().magnitude))
                    elif v is None:
                        row.append("")
                    else:
                        row.append(v)
                row.append(p.error_message or "")
                w.writerow(row)

    def to_json(self, path: str) -> None:
        """JSON export. Quantities serialize as {"value": ..., "unit": ...}."""
        doc: Dict[str, Any] = {
            "metadata": self.metadata,
            "axes": {k: v.tolist() for k, v in self.axes.items()},
            "points": [],
        }
        for p in self.points:
            outputs_ser: Dict[str, Any] = {}
            for k, v in p.outputs.items():
                if isinstance(v, Quantity):
                    outputs_ser[k] = {
                        "value": float(v.magnitude),
                        "unit": str(v.units),
                    }
                else:
                    outputs_ser[k] = v
            doc["points"].append(
                {
                    "coords": p.coords,
                    "outputs": outputs_ser,
                    "status": p.status,
                    "error_message": p.error_message,
                }
            )
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)

    def to_hdf5(self, path: str) -> None:
        """HDF5 export. Requires `h5py`; raises ImportError otherwise."""
        try:
            import h5py
        except ImportError as exc:
            raise ImportError(
                "HDF5 export requires the optional `h5py` dependency. "
                "Install with `pip install h5py`."
            ) from exc

        axis_names = list(self.axes.keys())
        with h5py.File(path, "w") as f:
            grp_axes = f.create_group("axes")
            for k, v in self.axes.items():
                grp_axes.create_dataset(k, data=np.asarray(v, dtype=float))

            # Status as fixed-length strings
            status = np.array([p.status for p in self.points], dtype="S64")
            f.create_dataset("status", data=status)

            # Coords table: (N, len(axes))
            coords = np.array(
                [[p.coords.get(a, float("nan")) for a in axis_names] for p in self.points],
                dtype=float,
            )
            ds = f.create_dataset("coords", data=coords)
            ds.attrs["columns"] = ",".join(axis_names)

            # Output columns
            output_names = sorted({k for p in self.points for k in p.outputs})
            out_grp = f.create_group("outputs")
            for name in output_names:
                arr = np.full(len(self.points), float("nan"), dtype=float)
                unit_str = ""
                for i, p in enumerate(self.points):
                    v = p.outputs.get(name)
                    if isinstance(v, Quantity):
                        arr[i] = float(v.to_base_units().magnitude)
                        if not unit_str:
                            unit_str = str(v.to_base_units().units)
                    elif v is not None:
                        arr[i] = float(v)
                d = out_grp.create_dataset(name, data=arr)
                if unit_str:
                    d.attrs["unit"] = unit_str

            # Metadata
            md = f.create_group("metadata")
            for k, v in self.metadata.items():
                try:
                    md.attrs[k] = v
                except (TypeError, ValueError):
                    md.attrs[k] = repr(v)


# --- Worker entry-point + status coercion -----------------------------------


def _evaluate_grid_point(
    args: Tuple[Callable[[Dict[str, float]], Any], Dict[str, float]],
) -> GridPoint:
    evaluator, coords = args
    try:
        result = evaluator(coords)
    except Exception as exc:  # noqa: BLE001
        return GridPoint(
            coords=coords,
            status=NON_CONVERGED,
            error_message=f"{type(exc).__name__}: {exc}",
        )
    return _coerce_to_grid_point(coords, result)


def _coerce_to_grid_point(coords: Dict[str, float], result: Any) -> GridPoint:
    if isinstance(result, GridPoint):
        # Override coords with the canonical ones in case evaluator dropped them.
        return replace(result, coords=coords)
    if isinstance(result, tuple):
        if len(result) == 2:
            status, outputs = result
            return GridPoint(coords=coords, outputs=dict(outputs), status=status)
        if len(result) == 3:
            status, outputs, error = result
            return GridPoint(
                coords=coords,
                outputs=dict(outputs),
                status=status,
                error_message=error,
            )
    if isinstance(result, dict):
        return GridPoint(
            coords=coords,
            outputs=dict(result.get("outputs", {})),
            status=result.get("status", CONVERGED),
            error_message=result.get("error_message"),
        )
    raise TypeError(
        f"Evaluator returned unsupported type {type(result).__name__}; "
        "expected GridPoint, tuple (status, outputs[, error]), or dict."
    )


# --- Surge detection helpers ------------------------------------------------


def _detect_surge_for_speedline(
    pts: Sequence[GridPoint],
    flow_axis: str,
    pi_output: str,
    threshold: float,
) -> Optional[Tuple[float, float]]:
    """Surge candidate for one speedline.

    Strategy:
    1. If any point has status `STALL_SURGE`, take the rightmost of those
       (highest m_dot among stall-flagged points) as the surge boundary.
    2. Else, fit a cubic spline through the converged-only (m_dot, pi)
       set. Sweep from the lowest m_dot rightward; the surge point is the
       first m_dot where dpi/dm >= threshold (i.e. slope is flat-to-positive).

    Returns `(m_dot_surge, pi_surge)` or None if no surge can be detected.
    """
    # Step 1: explicit STALL_SURGE points
    stall = [p for p in pts if p.status == STALL_SURGE]
    if stall:
        # The surge boundary sits between the rightmost stall and the
        # leftmost converged. We return the m_dot at the leftmost-converged
        # if available (i.e. just past the stall region); otherwise the
        # rightmost stall.
        converged_right = [
            p
            for p in pts
            if p.status == CONVERGED
            and float(p.coords[flow_axis]) > max(float(s.coords[flow_axis]) for s in stall)
        ]
        if converged_right:
            anchor = min(converged_right, key=lambda x: float(x.coords[flow_axis]))
        else:
            anchor = max(stall, key=lambda x: float(x.coords[flow_axis]))
        m_dot = float(anchor.coords[flow_axis])
        pi_val = anchor.outputs.get(pi_output)
        if isinstance(pi_val, Quantity):
            pi_num = float(pi_val.to_base_units().magnitude)
        elif pi_val is None:
            pi_num = float("nan")
        else:
            pi_num = float(pi_val)
        return (m_dot, pi_num)

    # Step 2: spline regression on converged points
    conv = [p for p in pts if p.status == CONVERGED and pi_output in p.outputs]
    if len(conv) < 4:
        return None

    m_dots = []
    pis = []
    for p in conv:
        m_dots.append(float(p.coords[flow_axis]))
        pi_val = p.outputs[pi_output]
        if isinstance(pi_val, Quantity):
            pis.append(float(pi_val.to_base_units().magnitude))
        else:
            pis.append(float(pi_val))
    order = np.argsort(m_dots)
    m_arr = np.asarray(m_dots, dtype=float)[order]
    pi_arr = np.asarray(pis, dtype=float)[order]

    # Drop duplicate m_dot values (spline rejects them)
    if not np.all(np.diff(m_arr) > 0):
        uniq_idx = np.concatenate([[True], np.diff(m_arr) > 0])
        m_arr = m_arr[uniq_idx]
        pi_arr = pi_arr[uniq_idx]
        if len(m_arr) < 4:
            return None

    spline = CubicSpline(m_arr, pi_arr, bc_type="natural", extrapolate=False)
    # Dense sample on the regression interval
    n_dense = max(200, 5 * len(m_arr))
    m_dense = np.linspace(m_arr[0], m_arr[-1], n_dense)
    pi_dense = spline(m_dense)
    slope = spline(m_dense, 1)  # first derivative

    # Compressor speedline shape:
    # - High m_dot (right): operating region, slope dpi/dm < 0 (safely
    #   negative).
    # - Decreasing m_dot (moving left): the slope rises toward zero.
    # - At the surge boundary the slope crosses the threshold and stays
    #   above it (i.e. >= threshold, where threshold ~ 0 from below).
    # The surge line is the *transition point* — the rightmost m where
    # slope < threshold, plus one sample. Equivalently: scan right-to-left
    # and pick the first m where the slope rises to >= threshold from a
    # below-threshold neighbor.
    mask = slope >= threshold
    if not np.any(mask):
        return None
    if np.all(mask):
        # Entire curve is flat-to-positive (no operating region detected).
        # By spec, leftmost point is the surge boundary.
        return (float(m_dense[0]), float(pi_dense[0]))

    # Find the transition: walk right-to-left, find the rightmost index
    # where mask transitions from True (slope >= threshold) below to
    # False (slope < threshold) above. That index is the surge boundary
    # — the leftmost m of the operating region.
    # Equivalent operation: the last True index when scanning left-to-right
    # before a transition; or more simply, the index where:
    #   mask[i] == True and (i+1 == n or mask[i+1] == False is False)
    # Cleanest expression: surge index = the index that is True and lies
    # adjacent to a False on its right.
    n_d = len(mask)
    surge_idx: Optional[int] = None
    # Scan left-to-right; surge transition is the last True in the
    # initial all-True prefix.
    for i in range(n_d - 1):
        if mask[i] and not mask[i + 1]:
            surge_idx = i
            break
    if surge_idx is None:
        # mask starts False; first True after a False is the surge transition
        for i in range(1, n_d):
            if mask[i] and not mask[i - 1]:
                surge_idx = i
                break
    if surge_idx is None:
        # Fall back: leftmost True (shouldn't happen given above branches)
        surge_idx = int(np.argmax(mask))
    return (float(m_dense[surge_idx]), float(pi_dense[surge_idx]))


__all__ = [
    "ALL_CODES",
    "CHOKED",
    "CONVERGED",
    "GridPoint",
    "INFEASIBLE_BC",
    "INVALID_GEOMETRY",
    "NON_CONVERGED",
    "PerformanceMap",
    "REGIME_OUT_OF_VALIDITY",
    "STALL_SURGE",
    "TIMEOUT",
]
