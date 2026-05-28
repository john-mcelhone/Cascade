"""Cascade scripting hooks — write custom loss models in Python.

Overview
========

Cascade ships with built-in loss models (Whitfield-Baines, Aungier) that
cover SPEC_SHEET §7's citation-disciplined v1 surface. For users with
proprietary correlations or empirical fits, the `cascade.plugins`
module exposes a stable contract for plugging custom models into
the meanline solvers, the API, and the UI dropdown.

Public surface (re-exported here so a plugin author writes
`from cascade.plugins import LossModel, LossContext`):

- `LossModel` — abstract base class to subclass.
- `LossModelProtocol` — duck-typed Protocol (for static analysis).
- `LossContext` — frozen dataclass of inputs.
- `PluginRegistry`, `PLUGIN_REGISTRY` — the singleton + class.
- `PluginValidationError`, `PluginNotFoundError`, `PluginLoadError`.
- `load_plugin_from_file`, `load_plugins_from_file` — loader entry points.
- `install_plugin_file`, `discover_installed_plugins` — store helpers.

Security
========

**Plugins run in the same process.** They are evaluated as ordinary
Python, with full access to the Cascade runtime and the host operating
system. Cascade v1 does NOT sandbox plugin code.

Treat installing a plugin as equivalent to `from foreign import *`:
only do it for code from sources you trust. The CLI prompts before
loading; the API logs every install with the caller's identity.

A future v1.1 release will add subprocess isolation with a restricted
import set and a wall-clock execution budget. Until then, the
trust boundary is the file path passed to the loader.

Adding a plugin
===============

1. Write a class that subclasses `LossModel`. See
   `cascade.plugins.templates.custom_loss_model` for a starting template.
2. Install via CLI: `cascade plugin install ./my_loss_model.py`
   OR upload via the web UI: Project → Settings → Loss Models →
   Upload Plugin.
3. Select it as the active model: `cascade plugin use MyCorrelationV1`
   OR pick it from the Properties Panel "Loss model" dropdown.
"""

from __future__ import annotations

from pathlib import Path

from cascade.plugins.base import (
    LossContext,
    LossModel,
    LossModelProtocol,
)
from cascade.plugins.loader import (
    PluginLoadError,
    discover_installed_plugins,
    install_plugin_file,
    load_plugin_from_file,
    load_plugins_from_file,
)
from cascade.plugins.sandbox import run_plugin_in_subprocess
from cascade.plugins.registry import (
    PLUGIN_REGISTRY,
    PluginNotFoundError,
    PluginRegistry,
    PluginValidationError,
    VALID_MACHINE_CLASSES,
)


# Default on-disk store: ~/.cascade/plugins/. The CLI uses this; the API
# overrides with its own subdirectory keyed by project_id.
DEFAULT_PLUGIN_STORE_DIR = Path.home() / ".cascade" / "plugins"


def register_built_in_plugins() -> None:
    """Register the built-in adapters in PLUGIN_REGISTRY.

    Called automatically on package import. Exposed publicly so test
    fixtures can re-trigger it after a `PLUGIN_REGISTRY.clear_user()`.
    """
    from cascade.plugins.builtin_adapter import register_builtins

    register_builtins()


# Auto-register the built-ins so `PLUGIN_REGISTRY.list()` returns the
# Whitfield-Baines + Aungier adapters out of the box.
register_built_in_plugins()


__all__ = [
    "DEFAULT_PLUGIN_STORE_DIR",
    "LossContext",
    "LossModel",
    "LossModelProtocol",
    "PLUGIN_REGISTRY",
    "PluginLoadError",
    "PluginNotFoundError",
    "PluginRegistry",
    "PluginValidationError",
    "VALID_MACHINE_CLASSES",
    "discover_installed_plugins",
    "install_plugin_file",
    "load_plugin_from_file",
    "load_plugins_from_file",
    "register_built_in_plugins",
    "run_plugin_in_subprocess",
]
