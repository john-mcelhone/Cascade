"""LossModel ABC + Protocol + LossContext — the public contract every
custom-loss-model plugin implements.

This module deliberately keeps a SMALL surface so user-written code can
target a stable interface without depending on internals of the meanline
solvers. The Cascade built-in loss models (`WhitfieldBainesRadial`,
`AungierCentrifugal`) speak the richer `cascade.meanline.loss_models.LossModel`
Protocol from the solver layer; this module defines an *adapter* protocol
+ ABC tailored for plugin authors who want a single scalar entropy-
generation coefficient ζ for one stage.

The two surfaces coexist:

- `cascade.meanline.loss_models.LossModel` (Protocol) — used inside the
  meanline solvers; returns a `LossBreakdown` with per-term coefficients.
- `cascade.plugins.LossModel` (ABC) — used by plugin authors; returns a
  single scalar ζ from a `LossContext`. The registry wraps plugins so
  they can be dispatched the same way.

The signatures, naming and conventions match SPEC_SHEET §7 (citation
discipline) and §13 (validity envelope), but plugins are not required
to declare an envelope — they get a permissive default.

SAFETY NOTE
-----------
Plugins execute Python code IN-PROCESS. Treat plugin authors as you would
the maintainer of any unpinned dependency: only install plugins from
sources you trust. Cascade v1 does **not** sandbox plugin code. Future
v1.1 will add subprocess isolation; until then, plugin installs are
equivalent to `from foreign import *` and must be audited.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover
    from typing import Dict, List


# ---------------------------------------------------------------------------
# LossContext — the immutable input bag passed to every plugin
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LossContext:
    """Inputs available to a plugin loss model. Read-only — plugins
    cannot mutate (the dataclass is frozen).

    These are computed by the meanline solver and passed in. Plugin
    authors should NOT assume any other field exists; if you need
    something else, request it via the `extra` dict (set by the solver
    when assembling the context).

    Conventions:
    - All angles are in **radians** measured **from tangential** (Wiesner /
      Aungier convention; not the Cascade canonical store, which uses
      radians-from-axial — the solver converts at the boundary).
    - All lengths in metres, velocities in m/s, temperatures in K,
      pressures in Pa.
    - `M_relative_max` is the *peak* relative Mach observed anywhere
      along the stage flow path (typically inducer tip for a centrifugal
      compressor, rotor inlet tip for a radial turbine).
    """

    # ---- Geometry --------------------------------------------------------
    r_tip: float                       # impeller / rotor exit tip radius [m]
    r_hub: float                       # impeller / rotor exit hub radius [m]
    blade_count: int                   # Z (includes splitters in effective)
    exit_blade_angle_rad: float        # β'_2 from tangential [rad]

    # ---- State / velocity-triangle output --------------------------------
    U_2: float                         # impeller exit tip speed [m/s]
    W_2: float                         # exit relative velocity [m/s]
    V_2: float                         # exit absolute velocity [m/s]
    M_relative_max: float              # peak relative Mach [-]
    T_1: float                         # inlet stagnation T [K]
    p_1: float                         # inlet stagnation p [Pa]
    T_2: float                         # exit stagnation T [K]
    p_2: float                         # exit stagnation p [Pa]
    rho_2: float                       # exit static density [kg/m^3]
    mass_flow: float                   # ṁ [kg/s]
    rotational_speed_rad_per_s: float  # ω [rad/s]

    # ---- Derived ---------------------------------------------------------
    Re_inlet: float                    # Reynolds number based on inlet [-]
    Mach_meridional: float             # meridional Mach [-]

    # ---- Misc ------------------------------------------------------------
    fluid_name: str = "air"            # working fluid identifier

    # Optional escape hatch — solver-injected extras keyed by name.
    # Plugins should `context.extra.get(key, default)` defensively.
    extra: "Dict[str, Any]" = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        # frozen dataclasses can't assign in __init__, but we can use
        # object.__setattr__ in __post_init__ to swap None → {}.
        if self.extra is None:
            object.__setattr__(self, "extra", {})


# ---------------------------------------------------------------------------
# LossModelProtocol — duck-typed contract (no inheritance required)
# ---------------------------------------------------------------------------


@runtime_checkable
class LossModelProtocol(Protocol):
    """Protocol that custom loss models must implement.

    Compatible with the built-in `WhitfieldBainesRadial`,
    `AungierCentrifugal` etc. via the `LossModelAdapter` in
    `cascade.plugins.builtin_adapter` (those built-ins use the richer
    breakdown protocol; the adapter collapses them to scalar ζ).
    """

    name: str
    applicable_machine_classes: "List[str]"

    def loss_coefficient(self, context: LossContext) -> float:
        """Return total entropy-generation coefficient ζ for one stage.

        ζ = Δs · T_reference / (½ U₂²)

        Equivalent to the dimensionless total enthalpy loss coefficient
        used internally by `LossBreakdown.total` × (½ W₂² / ½ U₂²).
        """
        ...


# ---------------------------------------------------------------------------
# LossModel ABC — the recommended base class for plugin authors
# ---------------------------------------------------------------------------


class LossModel(ABC):
    """Subclass this to write a custom loss model.

    Required class attributes:
        name (str):
            Human-readable identifier. Shown in UI dropdown + report.
            Must be unique within the registry.
        applicable_machine_classes (list[str]):
            List of machine classes this model applies to. Valid values:
            'radial_turbine', 'centrifugal_compressor', 'axial_turbine'
            (axial is reserved; v1 ships only radial + centrifugal).

    Required methods:
        loss_coefficient(context: LossContext) -> float

    Example:
        ```python
        from cascade.plugins import LossModel, LossContext

        class MyConductivityWeightedLoss(LossModel):
            name = "MyConductivityWeighted"
            applicable_machine_classes = ["radial_turbine"]

            def loss_coefficient(self, context: LossContext) -> float:
                # ζ = 0.05 + 0.02 · M_rel,max²
                return 0.05 + 0.02 * (context.M_relative_max ** 2)
        ```

    Safety:
        Plugin code runs in-process. Do NOT load untrusted code. Cascade
        v1 does not sandbox plugins. See `cascade.plugins.__doc__`.
    """

    # These are class attributes the registry inspects. Subclasses must
    # override them (the registry's `validate` enforces this).
    name: str = ""
    applicable_machine_classes: "List[str]" = []

    # Optional metadata — used in UI / report. Subclasses may override.
    description: str = ""
    citation: str = ""
    author: str = ""
    version: str = "0.1.0"

    @abstractmethod
    def loss_coefficient(self, context: LossContext) -> float:
        """Compute the scalar entropy-generation coefficient ζ.

        Args:
            context: A frozen `LossContext` with the local stage state.

        Returns:
            ζ — dimensionless. The solver multiplies by ½ U₂² to convert
            to a specific-enthalpy loss (J/kg).

        Raises:
            Any exception your model considers fatal. The solver catches
            and re-raises with a clear `PluginError` wrapper.
        """
        ...
