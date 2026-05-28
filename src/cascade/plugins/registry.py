"""PluginRegistry — manages registered LossModel plugins.

The registry is the single source of truth for "what loss models are
available right now in this Python process". It tracks two cohorts:

- **built-in**: classes registered by `cascade.meanline.loss_models_impl`
  at module import (auto-registered via `register_builtins()` invoked
  from `cascade.plugins.__init__`).
- **user**: classes loaded from user-supplied files via the loader.

Both cohorts speak the `LossModel` ABC interface. The built-in classes
are wrapped by a small adapter so they look like plugin-style models
to consumers (the rich `LossBreakdown` protocol stays internal to the
solvers).

Thread-safety: the registry uses a process-local lock around mutating
operations. Reading is lock-free (Python's GIL guarantees atomicity
for `dict.get` and `list(...)`).
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional, Tuple, Type

from cascade.plugins.base import LossContext, LossModel


VALID_MACHINE_CLASSES = frozenset(
    {"radial_turbine", "centrifugal_compressor", "axial_turbine"}
)


class PluginValidationError(ValueError):
    """Raised when a plugin class fails registry validation.

    Carries a human-readable message; the API surface re-formats this
    into a 422 with detail = message.
    """


class PluginNotFoundError(KeyError):
    """Raised when the registry is asked for a plugin name that isn't
    registered. The API surface translates this to 404."""


class PluginRegistry:
    """Manages registered LossModel plugins.

    The registry is process-local; for multi-process API deployments,
    each worker has its own copy. The on-disk plugin store
    (`~/.cascade/plugins/`) is the durable record; the registry is
    repopulated on startup by scanning that directory.
    """

    def __init__(self) -> None:
        self._plugins: Dict[str, Type[LossModel]] = {}
        self._origins: Dict[str, str] = {}  # name → "builtin" | "user"
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Mutating operations
    # ------------------------------------------------------------------

    def register(
        self, plugin: Type[LossModel], *, origin: str = "user"
    ) -> None:
        """Add a plugin class to the registry.

        Validates the class first. On failure raises `PluginValidationError`
        with a human-readable message and the registry is left untouched.

        Args:
            plugin: A class object (NOT an instance). Must be a subclass
                of `cascade.plugins.LossModel` (ABC).
            origin: 'builtin' or 'user'. Built-in plugins cannot be
                overwritten by user plugins of the same name — that
                raises `PluginValidationError`.
        """
        self.validate(plugin)
        name = plugin.name
        with self._lock:
            existing_origin = self._origins.get(name)
            if existing_origin == "builtin" and origin == "user":
                raise PluginValidationError(
                    f"Cannot overwrite built-in plugin {name!r}. "
                    "Choose a different `name` for your plugin."
                )
            self._plugins[name] = plugin
            self._origins[name] = origin

    def unregister(self, name: str) -> None:
        """Remove a plugin from the registry.

        Used by the CLI `cascade plugin remove` command and by test
        fixtures. Silent no-op if the name is not registered (matches
        the idempotent contract).
        """
        with self._lock:
            self._plugins.pop(name, None)
            self._origins.pop(name, None)

    def clear_user(self) -> None:
        """Remove ALL user plugins, leaving the built-ins intact.

        Used by test fixtures and by the API's reset path. The built-in
        cohort is preserved.
        """
        with self._lock:
            to_drop = [
                name for name, origin in self._origins.items()
                if origin == "user"
            ]
            for name in to_drop:
                self._plugins.pop(name, None)
                self._origins.pop(name, None)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[Type[LossModel]]:
        """Return the registered class for ``name`` or None.

        Use `get_or_raise` when missing → 404 semantics is required.
        """
        return self._plugins.get(name)

    def get_or_raise(self, name: str) -> Type[LossModel]:
        cls = self._plugins.get(name)
        if cls is None:
            raise PluginNotFoundError(name)
        return cls

    def list(
        self, machine_class: Optional[str] = None
    ) -> List[Type[LossModel]]:
        """List all plugins, optionally filtered by machine class.

        Args:
            machine_class: One of 'radial_turbine', 'centrifugal_compressor',
                'axial_turbine'. None returns every plugin regardless.

        Returns:
            A list of class objects (sorted by name for stable iteration).
        """
        with self._lock:
            items = list(self._plugins.values())
        if machine_class is None:
            return sorted(items, key=lambda c: c.name)
        return sorted(
            [c for c in items if machine_class in c.applicable_machine_classes],
            key=lambda c: c.name,
        )

    def list_built_in(self) -> List[Type[LossModel]]:
        """Subset of `list()` that came from the built-in cohort."""
        with self._lock:
            names = [n for n, o in self._origins.items() if o == "builtin"]
        return sorted(
            [self._plugins[n] for n in names], key=lambda c: c.name
        )

    def list_user(self) -> List[Type[LossModel]]:
        """Subset of `list()` that came from user-supplied files."""
        with self._lock:
            names = [n for n, o in self._origins.items() if o == "user"]
        return sorted(
            [self._plugins[n] for n in names], key=lambda c: c.name
        )

    def origin(self, name: str) -> Optional[str]:
        """Return 'builtin' / 'user' / None."""
        return self._origins.get(name)

    def names(self) -> List[str]:
        with self._lock:
            return sorted(self._plugins.keys())

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate(plugin: Type[LossModel]) -> None:
        """Validate that ``plugin`` is a well-formed LossModel subclass.

        Checks (in order; the first failure raises with a clear message):

        1. ``plugin`` is a class (not an instance, not a function).
        2. ``plugin`` is a subclass of `LossModel` (the ABC).
        3. ``plugin.name`` exists, is a non-empty string.
        4. ``plugin.applicable_machine_classes`` exists, is a list of
           valid strings from `VALID_MACHINE_CLASSES`.
        5. ``plugin.loss_coefficient`` is callable.
        6. ``plugin`` is instantiable (zero-arg constructor).
        7. A smoke test against a synthetic `LossContext` returns a
           finite float (rejects models that return strings, NaN, etc.).

        Raises:
            PluginValidationError: with a human-readable explanation.
        """
        if not isinstance(plugin, type):
            raise PluginValidationError(
                f"Expected a class, got {type(plugin).__name__}. "
                "Pass `MyLoss` (the class), not `MyLoss()` (an instance)."
            )
        if not issubclass(plugin, LossModel):
            raise PluginValidationError(
                f"{plugin.__name__} must subclass cascade.plugins.LossModel. "
                "Add `class MyLoss(LossModel):` and re-upload."
            )
        # Class-level name check
        name = getattr(plugin, "name", "")
        if not isinstance(name, str) or not name:
            raise PluginValidationError(
                f"{plugin.__name__}.name must be a non-empty string. "
                "Set e.g. `name = 'MyCorrelationV1'` on the class."
            )
        # Machine classes check
        amc = getattr(plugin, "applicable_machine_classes", None)
        if not isinstance(amc, list) or not amc:
            raise PluginValidationError(
                f"{plugin.__name__}.applicable_machine_classes must be a "
                "non-empty list of machine-class strings. "
                f"Valid values: {sorted(VALID_MACHINE_CLASSES)}."
            )
        invalid = [mc for mc in amc if mc not in VALID_MACHINE_CLASSES]
        if invalid:
            raise PluginValidationError(
                f"{plugin.__name__}.applicable_machine_classes contains "
                f"invalid entries: {invalid}. "
                f"Valid values: {sorted(VALID_MACHINE_CLASSES)}."
            )
        # loss_coefficient must be callable
        lc = getattr(plugin, "loss_coefficient", None)
        if not callable(lc):
            raise PluginValidationError(
                f"{plugin.__name__}.loss_coefficient must be a method "
                "(callable). Got "
                f"{type(lc).__name__}."
            )
        # Instantiation smoke test — must work with zero args.
        try:
            instance = plugin()
        except Exception as exc:
            raise PluginValidationError(
                f"{plugin.__name__}() raised on instantiation: {exc!r}. "
                "Plugin classes must have a zero-argument constructor "
                "(or all-default arguments)."
            ) from exc
        # Return-value smoke test
        ctx = _synthetic_context()
        try:
            value = instance.loss_coefficient(ctx)
        except Exception as exc:
            raise PluginValidationError(
                f"{plugin.__name__}.loss_coefficient(synthetic_context) "
                f"raised: {exc!r}. The model must not raise on a well-"
                "formed LossContext."
            ) from exc
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise PluginValidationError(
                f"{plugin.__name__}.loss_coefficient must return a number "
                f"(int or float). Got {type(value).__name__} = {value!r}."
            )
        # NaN / Inf check
        import math
        v = float(value)
        if not math.isfinite(v):
            raise PluginValidationError(
                f"{plugin.__name__}.loss_coefficient returned a "
                f"non-finite value ({value!r}). It must be a real, "
                "finite float."
            )
        if v < 0:
            # ζ < 0 implies entropy destruction — a thermodynamic
            # violation. Reject loudly. (A model can return 0; that
            # means lossless, which is unusual but legal.)
            raise PluginValidationError(
                f"{plugin.__name__}.loss_coefficient returned {value!r} "
                "(< 0). Loss coefficients must be ≥ 0 (entropy "
                "generation is non-negative)."
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _synthetic_context() -> LossContext:
    """Build a representative LossContext for validation smoke tests.

    Values are loosely sized to a Capstone-class radial turbine /
    centrifugal compressor so plugin authors can use these as a sanity
    check during development.
    """
    return LossContext(
        r_tip=0.040,
        r_hub=0.015,
        blade_count=12,
        exit_blade_angle_rad=1.0472,  # 60° from tangential = 30° back-sweep
        U_2=350.0,
        W_2=180.0,
        V_2=220.0,
        M_relative_max=0.85,
        T_1=288.15,
        p_1=101325.0,
        T_2=455.0,
        p_2=325000.0,
        rho_2=2.49,
        mass_flow=0.30,
        rotational_speed_rad_per_s=8377.0,
        Re_inlet=1.5e6,
        Mach_meridional=0.45,
        fluid_name="air",
    )


# ---------------------------------------------------------------------------
# Module-global singleton
# ---------------------------------------------------------------------------

PLUGIN_REGISTRY = PluginRegistry()
"""The process-wide PluginRegistry singleton.

External code should import this from `cascade.plugins` (the package
__init__ re-exports it). Direct access to the singleton from inside
this module is for `register_builtins()` only.
"""
