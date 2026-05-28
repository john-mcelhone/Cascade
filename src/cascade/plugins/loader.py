"""Safe code loading from string / file.

"Safe" here is a layered claim — the loader does the FOLLOWING:

1. Loads a Python module from a file path using `importlib.util.spec_from_file_location`.
2. Catches SyntaxError + any import-time exceptions and re-raises with a
   clear, blameworthy message (file path + line number).
3. Scans the loaded module for `LossModel` subclasses (the ABC).
4. Validates the discovered class via the registry's `validate` method.
5. Returns the class object (the caller decides whether to register it).

What the loader does **NOT** do:

- Sandbox the code. Python's `exec`-based import runs the file's
  top-level statements; a malicious plugin can do whatever Python can
  do (file I/O, network, subprocess). See `cascade.plugins.__doc__`
  for the security disclosure.
- Validate dependencies. If the plugin imports `numpy` or `scipy`, the
  loader trusts the environment to provide them.

Module name disambiguation: every load assigns a fresh, content-hashed
module name (`cascade_user_plugin_<hash>`) so two plugins with the same
class name (but different files) can coexist. This matters because
Python caches modules in `sys.modules` by name; without the hash,
re-uploading an edited plugin would silently keep the old version.
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import List, Tuple, Type

from cascade.plugins.base import LossModel
from cascade.plugins.registry import PluginValidationError


class PluginLoadError(Exception):
    """Raised when a plugin file cannot be loaded for any reason.

    The message is human-readable. The API surface re-formats this into
    a 422 response with detail = message.
    """


def load_plugin_from_file(file_path: Path) -> Type[LossModel]:
    """Load a LossModel subclass from a Python file.

    SAFETY: Plugin code runs in the same process. Only load from trusted
    sources. The Cascade CLI prompts before loading; the API logs every
    load with the calling user's identity.

    Args:
        file_path: Absolute or relative path to a `.py` file.

    Returns:
        The discovered LossModel subclass (a class object, not an
        instance). The caller is responsible for registering it.

    Raises:
        PluginLoadError: if the file cannot be read, has invalid Python
            syntax, raises at import time, contains zero `LossModel`
            subclasses, or contains multiple — in which case the
            ambiguity is flagged. (To bundle several models, use
            `load_plugins_from_file` instead.)
        PluginValidationError: re-raised from `PluginRegistry.validate`
            if the discovered class is structurally invalid.
    """
    plugins = load_plugins_from_file(file_path)
    if not plugins:
        raise PluginLoadError(
            f"No LossModel subclass found in {file_path}. "
            "The file must define at least one class that subclasses "
            "`cascade.plugins.LossModel`."
        )
    if len(plugins) > 1:
        names = ", ".join(c.__name__ for c in plugins)
        raise PluginLoadError(
            f"Multiple LossModel subclasses found in {file_path}: "
            f"{names}. Use `load_plugins_from_file` to load all, or "
            "split into separate files."
        )
    return plugins[0]


def load_plugins_from_file(file_path: Path) -> List[Type[LossModel]]:
    """Load every LossModel subclass from a Python file.

    Like `load_plugin_from_file` but returns a list. Empty list when
    the file is syntactically valid but contains no plugins.

    Args:
        file_path: Absolute or relative path to a `.py` file.

    Returns:
        Sorted list of LossModel subclasses (sorted by class name for
        stable iteration).

    Raises:
        PluginLoadError: file unreadable, syntax error, or import-time
            exception.
        PluginValidationError: re-raised from `validate` for any class
            that fails structural validation. (The loader validates each
            discovered class before returning — so a partially-valid
            bundle is rejected as a whole.)
    """
    path = Path(file_path)
    if not path.exists():
        raise PluginLoadError(f"Plugin file not found: {path}")
    if not path.is_file():
        raise PluginLoadError(f"Plugin path is not a file: {path}")
    if path.suffix != ".py":
        raise PluginLoadError(
            f"Plugin file must have .py suffix, got {path.suffix!r}: {path}"
        )

    # Compute a content hash so each (re-)upload gets a fresh module name.
    try:
        source = path.read_bytes()
    except OSError as exc:
        raise PluginLoadError(f"Cannot read {path}: {exc}") from exc

    content_hash = hashlib.sha256(source).hexdigest()[:12]
    module_name = f"cascade_user_plugin_{content_hash}"

    # Drop any cached version under this exact name (cheap idempotency).
    sys.modules.pop(module_name, None)

    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise PluginLoadError(
            f"importlib could not build a spec for {path}. "
            "The file may be unreadable or have a non-standard encoding."
        )
    module = importlib.util.module_from_spec(spec)
    # Compile from source directly using compile() to bypass Python's
    # bytecode cache (__pycache__/<name>.cpython-XY.pyc). The default
    # SourceFileLoader caches by mtime; when an edited plugin is
    # re-uploaded within the same mtime-second, Python serves the
    # stale .pyc. Compiling from source skips that path entirely.
    try:
        code = compile(source, str(path), "exec")
    except SyntaxError as exc:
        raise PluginLoadError(
            f"Syntax error in {path}: {exc.msg} (line {exc.lineno})"
        ) from exc
    # Make it discoverable by the import system *before* exec'ing the
    # module body so the module can reference itself (e.g. for `from
    # __main__ import` patterns in user code).
    sys.modules[module_name] = module
    try:
        exec(code, module.__dict__)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise PluginLoadError(
            f"Importing {path} raised {type(exc).__name__}: {exc}"
        ) from exc

    # Collect every LossModel subclass defined *in this module* (not
    # imported from elsewhere). Without the `__module__` filter we'd
    # also pick up the `LossModel` ABC itself when the user does
    # `from cascade.plugins import LossModel`.
    discovered: List[Type[LossModel]] = []
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if not issubclass(obj, LossModel):
            continue
        if obj is LossModel:
            continue
        if getattr(obj, "__module__", None) != module_name:
            # Imported, not defined here — skip.
            continue
        # Skip abstract subclasses (a user might define an abstract
        # mixin before the concrete model). `inspect.isabstract` is
        # True iff the class still has unimplemented abstract methods.
        if inspect.isabstract(obj):
            continue
        discovered.append(obj)

    # Validate each. The first failure raises and we drop the module
    # from sys.modules to avoid leaving a stale half-loaded entry.
    from cascade.plugins.registry import PluginRegistry

    for cls in discovered:
        try:
            PluginRegistry.validate(cls)
        except PluginValidationError:
            sys.modules.pop(module_name, None)
            raise

    return sorted(discovered, key=lambda c: c.__name__)


def install_plugin_file(
    file_path: Path, *, store_dir: Path, project_id: str = "default"
) -> Path:
    """Copy a plugin file into the project's plugin store directory.

    Used by the API endpoint and the CLI to persist user uploads. The
    file lives at `<store_dir>/<project_id>/<filename>.py`. Returns the
    absolute path of the stored file (which the caller then passes to
    `load_plugin_from_file` to register it in the runtime registry).

    The store dir is created if it doesn't exist. Existing files at the
    target are overwritten (last-upload-wins; the API records the prior
    file's hash so audit trail isn't lost).

    Args:
        file_path: Source plugin file (the user-supplied file).
        store_dir: Root of the on-disk plugin store. The CLI uses
            `~/.cascade/plugins/`; the API uses `<APP_DATA>/plugins/`.
        project_id: Per-project namespace inside the store. Sanitized
            to alphanumerics + dashes + underscores.

    Returns:
        Absolute path of the stored file.
    """
    safe_project = "".join(
        c if (c.isalnum() or c in "-_") else "_" for c in project_id
    ) or "default"
    target_dir = store_dir / safe_project
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / Path(file_path).name
    target.write_bytes(Path(file_path).read_bytes())
    return target


def discover_installed_plugins(store_dir: Path) -> List[Path]:
    """Return every `.py` file under the store directory.

    Recursive; used by the API + CLI on startup to repopulate the
    in-memory registry from the on-disk store. Returns absolute paths
    sorted lexicographically (so the registry sees a deterministic
    load order).
    """
    if not store_dir.exists():
        return []
    out: List[Path] = []
    for path in sorted(store_dir.rglob("*.py")):
        if path.is_file() and not path.name.startswith("_"):
            out.append(path.resolve())
    return out
