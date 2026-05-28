"""Registry contract tests for `cascade.plugins.PluginRegistry`.

Covers:
- Registering a valid LossModel; it appears in `list()`.
- `loss_coefficient` is invoked on the registered class.
- Invalid plugins (no `name`, wrong return type, NaN, negative ζ) are
  rejected with PluginValidationError + a clear message.
- The shipped template file is loadable + valid.
- Built-in plugins (WhitfieldBainesRadial, AungierCentrifugal) appear
  in `list_built_in()` out of the box.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from cascade.plugins import (
    PLUGIN_REGISTRY,
    LossContext,
    LossModel,
    PluginNotFoundError,
    PluginRegistry,
    PluginValidationError,
    load_plugin_from_file,
)
from cascade.plugins.registry import _synthetic_context


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_registry() -> PluginRegistry:
    """A clean PluginRegistry for tests that mutate state."""
    reg = PluginRegistry()
    return reg


@pytest.fixture
def reset_global_registry():
    """Clear user plugins from the global registry before + after the test.

    Used by tests that touch the package-level PLUGIN_REGISTRY so they
    don't leak state into subsequent tests.
    """
    PLUGIN_REGISTRY.clear_user()
    yield
    PLUGIN_REGISTRY.clear_user()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class _ValidPlugin(LossModel):
    name = "TestModelV1"
    applicable_machine_classes = ["centrifugal_compressor"]
    description = "Synthetic test plugin."
    citation = "Test fixture, 2026."

    def loss_coefficient(self, context: LossContext) -> float:
        # A deliberately distinctive value the test asserts on.
        return 0.1234


def test_register_then_list(fresh_registry: PluginRegistry) -> None:
    fresh_registry.register(_ValidPlugin)
    assert _ValidPlugin in fresh_registry.list()
    assert fresh_registry.get("TestModelV1") is _ValidPlugin
    assert fresh_registry.origin("TestModelV1") == "user"


def test_list_filters_by_machine_class(fresh_registry: PluginRegistry) -> None:
    class RadialOnly(LossModel):
        name = "RadialOnly"
        applicable_machine_classes = ["radial_turbine"]

        def loss_coefficient(self, ctx: LossContext) -> float:
            return 0.05

    fresh_registry.register(_ValidPlugin)
    fresh_registry.register(RadialOnly)
    radial = fresh_registry.list(machine_class="radial_turbine")
    assert RadialOnly in radial
    assert _ValidPlugin not in radial
    centrifugal = fresh_registry.list(machine_class="centrifugal_compressor")
    assert _ValidPlugin in centrifugal
    assert RadialOnly not in centrifugal


def test_loss_coefficient_called_on_registered_instance(
    fresh_registry: PluginRegistry,
) -> None:
    fresh_registry.register(_ValidPlugin)
    cls = fresh_registry.get_or_raise("TestModelV1")
    value = cls().loss_coefficient(_synthetic_context())
    assert value == pytest.approx(0.1234)


def test_get_or_raise_missing(fresh_registry: PluginRegistry) -> None:
    with pytest.raises(PluginNotFoundError):
        fresh_registry.get_or_raise("NotInstalled")


def test_unregister_is_idempotent(fresh_registry: PluginRegistry) -> None:
    fresh_registry.register(_ValidPlugin)
    fresh_registry.unregister("TestModelV1")
    fresh_registry.unregister("TestModelV1")  # second call is a no-op
    assert fresh_registry.get("TestModelV1") is None


def test_clear_user_preserves_builtins(reset_global_registry) -> None:
    PLUGIN_REGISTRY.register(_ValidPlugin)
    # The global registry has the built-in adapters pre-registered.
    builtin_names_before = {c.name for c in PLUGIN_REGISTRY.list_built_in()}
    PLUGIN_REGISTRY.clear_user()
    builtin_names_after = {c.name for c in PLUGIN_REGISTRY.list_built_in()}
    assert builtin_names_before == builtin_names_after
    # User cohort is empty
    assert PLUGIN_REGISTRY.list_user() == []


# ---------------------------------------------------------------------------
# Validation: reject malformed plugins
# ---------------------------------------------------------------------------


def test_reject_not_a_class() -> None:
    with pytest.raises(PluginValidationError, match="Expected a class"):
        PluginRegistry.validate(lambda ctx: 0.1)  # type: ignore[arg-type]


def test_reject_not_a_subclass() -> None:
    class NotALossModel:
        name = "X"
        applicable_machine_classes = ["radial_turbine"]

        def loss_coefficient(self, ctx):
            return 0.05

    with pytest.raises(PluginValidationError, match="must subclass"):
        PluginRegistry.validate(NotALossModel)  # type: ignore[arg-type]


def test_reject_missing_name() -> None:
    class _NoName(LossModel):
        name = ""
        applicable_machine_classes = ["radial_turbine"]

        def loss_coefficient(self, ctx: LossContext) -> float:
            return 0.05

    with pytest.raises(PluginValidationError, match="name must be"):
        PluginRegistry.validate(_NoName)


def test_reject_invalid_machine_class() -> None:
    class _Invalid(LossModel):
        name = "Invalid"
        applicable_machine_classes = ["banana_compressor"]

        def loss_coefficient(self, ctx: LossContext) -> float:
            return 0.05

    with pytest.raises(PluginValidationError, match="invalid entries"):
        PluginRegistry.validate(_Invalid)


def test_reject_returns_string() -> None:
    class _ReturnsString(LossModel):
        name = "ReturnsString"
        applicable_machine_classes = ["radial_turbine"]

        def loss_coefficient(self, ctx: LossContext):  # type: ignore[override]
            return "not a number"

    with pytest.raises(PluginValidationError, match="must return a number"):
        PluginRegistry.validate(_ReturnsString)


def test_reject_returns_nan() -> None:
    class _ReturnsNaN(LossModel):
        name = "ReturnsNaN"
        applicable_machine_classes = ["radial_turbine"]

        def loss_coefficient(self, ctx: LossContext) -> float:
            return float("nan")

    with pytest.raises(PluginValidationError, match="non-finite"):
        PluginRegistry.validate(_ReturnsNaN)


def test_reject_negative_loss() -> None:
    class _Negative(LossModel):
        name = "Negative"
        applicable_machine_classes = ["radial_turbine"]

        def loss_coefficient(self, ctx: LossContext) -> float:
            return -0.1

    with pytest.raises(PluginValidationError, match="≥ 0"):
        PluginRegistry.validate(_Negative)


def test_reject_raising_constructor() -> None:
    class _Boom(LossModel):
        name = "Boom"
        applicable_machine_classes = ["radial_turbine"]

        def __init__(self) -> None:
            raise RuntimeError("kaboom")

        def loss_coefficient(self, ctx: LossContext) -> float:
            return 0.05

    with pytest.raises(PluginValidationError, match="raised on instantiation"):
        PluginRegistry.validate(_Boom)


def test_reject_overwriting_builtin(reset_global_registry) -> None:
    """A user plugin must not be able to take over a built-in name."""

    builtins = PLUGIN_REGISTRY.list_built_in()
    assert builtins, "Built-ins should be registered on import"
    target_name = builtins[0].name

    class _SquatBuiltin(LossModel):
        name = target_name  # collide with the built-in
        applicable_machine_classes = ["radial_turbine"]

        def loss_coefficient(self, ctx: LossContext) -> float:
            return 0.01

    with pytest.raises(PluginValidationError, match="Cannot overwrite"):
        PLUGIN_REGISTRY.register(_SquatBuiltin, origin="user")


# ---------------------------------------------------------------------------
# Built-ins are registered
# ---------------------------------------------------------------------------


def test_builtins_are_registered() -> None:
    """The package import should have registered the Whitfield-Baines +
    Aungier adapters under origin='builtin'."""
    built_in_names = {c.name for c in PLUGIN_REGISTRY.list_built_in()}
    assert "WhitfieldBainesRadial" in built_in_names
    assert "AungierCentrifugal" in built_in_names


def test_builtin_returns_finite_zeta() -> None:
    cls = PLUGIN_REGISTRY.get_or_raise("AungierCentrifugal")
    zeta = cls().loss_coefficient(_synthetic_context())
    assert math.isfinite(zeta)
    assert zeta >= 0


# ---------------------------------------------------------------------------
# Template file is valid
# ---------------------------------------------------------------------------


def test_template_file_loads_cleanly() -> None:
    """The shipped template at
    `src/cascade/plugins/templates/custom_loss_model.py` must be valid
    Python and pass registry validation."""
    template = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "cascade"
        / "plugins"
        / "templates"
        / "custom_loss_model.py"
    )
    assert template.exists(), f"Template missing at {template}"
    cls = load_plugin_from_file(template)
    assert issubclass(cls, LossModel)
    assert cls.name == "MyConductivityWeighted"
    assert "radial_turbine" in cls.applicable_machine_classes
    # The example formula returns a non-negative ζ
    ctx = _synthetic_context()
    zeta = cls().loss_coefficient(ctx)
    assert zeta >= 0
    assert math.isfinite(zeta)
