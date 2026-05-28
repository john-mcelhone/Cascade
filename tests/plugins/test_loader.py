"""Loader-contract tests for `cascade.plugins.load_plugin_from_file`.

Covers:
- Loading a syntactically-broken file raises with a clear message.
- A file with no LossModel subclass raises (with an actionable message).
- A file with two LossModel subclasses → `load_plugin_from_file` fails
  (ambiguous) but `load_plugins_from_file` returns both.
- A nonexistent file raises.
- A non-.py file is rejected.
- Re-uploading an edited file (same name, different content) loads the
  new content (we content-hash the module name so sys.modules can't
  cache the old version).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from cascade.plugins import (
    LossModel,
    PluginLoadError,
    PluginValidationError,
    load_plugin_from_file,
    load_plugins_from_file,
)


def _write_plugin(tmp_path: Path, name: str, body: str) -> Path:
    target = tmp_path / name
    target.write_text(textwrap.dedent(body), encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_load_single_valid_plugin(tmp_path: Path) -> None:
    path = _write_plugin(
        tmp_path,
        "good.py",
        """
        from cascade.plugins import LossContext, LossModel


        class Good(LossModel):
            name = "GoodModel"
            applicable_machine_classes = ["radial_turbine"]

            def loss_coefficient(self, ctx: LossContext) -> float:
                return 0.07
        """,
    )
    cls = load_plugin_from_file(path)
    assert issubclass(cls, LossModel)
    assert cls.name == "GoodModel"


def test_load_plugins_returns_all_from_bundle(tmp_path: Path) -> None:
    path = _write_plugin(
        tmp_path,
        "bundle.py",
        """
        from cascade.plugins import LossContext, LossModel


        class A(LossModel):
            name = "ABundle"
            applicable_machine_classes = ["radial_turbine"]

            def loss_coefficient(self, ctx: LossContext) -> float:
                return 0.05


        class B(LossModel):
            name = "BBundle"
            applicable_machine_classes = ["centrifugal_compressor"]

            def loss_coefficient(self, ctx: LossContext) -> float:
                return 0.06
        """,
    )
    classes = load_plugins_from_file(path)
    names = {c.name for c in classes}
    assert names == {"ABundle", "BBundle"}


# ---------------------------------------------------------------------------
# Error paths — every failure mode must produce a clear message.
# ---------------------------------------------------------------------------


def test_syntax_error_raises_clearly(tmp_path: Path) -> None:
    path = _write_plugin(
        tmp_path,
        "broken.py",
        """
        from cascade.plugins import LossModel


        class Broken(LossModel
            name = "Broken"
            applicable_machine_classes = ["radial_turbine"]
        """,
    )
    with pytest.raises(PluginLoadError, match="Syntax error"):
        load_plugin_from_file(path)


def test_no_loss_model_subclass_raises(tmp_path: Path) -> None:
    path = _write_plugin(
        tmp_path,
        "empty.py",
        """
        # A perfectly valid Python file with no LossModel subclass.
        x = 1 + 1
        """,
    )
    with pytest.raises(PluginLoadError, match="No LossModel subclass"):
        load_plugin_from_file(path)


def test_multiple_subclasses_in_single_loader_raises(tmp_path: Path) -> None:
    path = _write_plugin(
        tmp_path,
        "bundle.py",
        """
        from cascade.plugins import LossContext, LossModel


        class A(LossModel):
            name = "AA"
            applicable_machine_classes = ["radial_turbine"]

            def loss_coefficient(self, ctx: LossContext) -> float:
                return 0.05


        class B(LossModel):
            name = "BB"
            applicable_machine_classes = ["radial_turbine"]

            def loss_coefficient(self, ctx: LossContext) -> float:
                return 0.06
        """,
    )
    with pytest.raises(PluginLoadError, match="Multiple LossModel"):
        load_plugin_from_file(path)


def test_nonexistent_file_raises() -> None:
    with pytest.raises(PluginLoadError, match="not found"):
        load_plugin_from_file(Path("/this/path/does/not/exist.py"))


def test_non_python_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "not_a_plugin.txt"
    path.write_text("hello", encoding="utf-8")
    with pytest.raises(PluginLoadError, match=".py suffix"):
        load_plugin_from_file(path)


def test_import_time_exception_raises(tmp_path: Path) -> None:
    path = _write_plugin(
        tmp_path,
        "boom.py",
        """
        from cascade.plugins import LossModel
        raise RuntimeError("module-level boom")
        """,
    )
    with pytest.raises(PluginLoadError, match="boom"):
        load_plugin_from_file(path)


def test_invalid_class_raises_validation_error(tmp_path: Path) -> None:
    path = _write_plugin(
        tmp_path,
        "bad.py",
        """
        from cascade.plugins import LossContext, LossModel


        class Bad(LossModel):
            name = "BadModel"
            applicable_machine_classes = ["radial_turbine"]

            def loss_coefficient(self, ctx: LossContext) -> float:
                return -1.0  # Negative ζ → entropy destruction, illegal.
        """,
    )
    with pytest.raises(PluginValidationError, match="≥ 0"):
        load_plugin_from_file(path)


# ---------------------------------------------------------------------------
# Re-upload behavior: content-hashed module names mean an edited file
# replaces the prior version cleanly.
# ---------------------------------------------------------------------------


def test_reupload_replaces_prior_version(tmp_path: Path) -> None:
    body_v1 = """
        from cascade.plugins import LossContext, LossModel


        class Versioned(LossModel):
            name = "Versioned"
            applicable_machine_classes = ["radial_turbine"]

            def loss_coefficient(self, ctx: LossContext) -> float:
                return 0.10
        """
    body_v2 = """
        from cascade.plugins import LossContext, LossModel


        class Versioned(LossModel):
            name = "Versioned"
            applicable_machine_classes = ["radial_turbine"]

            def loss_coefficient(self, ctx: LossContext) -> float:
                return 0.20
        """
    path = _write_plugin(tmp_path, "versioned.py", body_v1)
    cls1 = load_plugin_from_file(path)
    from cascade.plugins.registry import _synthetic_context

    v1_value = cls1().loss_coefficient(_synthetic_context())
    assert v1_value == pytest.approx(0.10)

    # Overwrite + re-load. The loader uses a content hash for the
    # module name so sys.modules can't return the cached v1.
    path.write_text(textwrap.dedent(body_v2), encoding="utf-8")
    cls2 = load_plugin_from_file(path)
    v2_value = cls2().loss_coefficient(_synthetic_context())
    assert v2_value == pytest.approx(0.20)


# ---------------------------------------------------------------------------
# Abstract subclasses are skipped (don't trip validation).
# ---------------------------------------------------------------------------


def test_abstract_mixin_is_skipped(tmp_path: Path) -> None:
    path = _write_plugin(
        tmp_path,
        "with_mixin.py",
        """
        from abc import abstractmethod
        from cascade.plugins import LossContext, LossModel


        class _Base(LossModel):
            # Abstract intermediate — has no concrete loss_coefficient.
            @abstractmethod
            def loss_coefficient(self, ctx: LossContext) -> float: ...


        class Concrete(_Base):
            name = "ConcreteFromMixin"
            applicable_machine_classes = ["radial_turbine"]

            def loss_coefficient(self, ctx: LossContext) -> float:
                return 0.04
        """,
    )
    cls = load_plugin_from_file(path)
    assert cls.name == "ConcreteFromMixin"
