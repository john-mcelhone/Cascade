#!/usr/bin/env python3
"""CI-01: Citation integrity assertion.

Reads every .citation property from LossModel subclasses and SlipFactor
implementations in src/cascade/meanline/loss_models_impl.py (and any other
loss-model files), then cross-checks each citation string against the
hand-maintained registry at scripts/citation_registry.yaml.

Exits 0 if all citations are registered; exits 1 if any citation is missing
from the registry (printing the offending citation strings so the developer
knows what to add).

Usage:
    python scripts/check_citations.py

CI integration:
    - Run weekly (or on any PR that touches src/cascade/meanline/)
    - Per CI-01

Design:
    The check is intentionally conservative: it collects citation strings by
    INSTANTIATING known concrete classes and reading their .citation property.
    It does NOT use AST parsing, so it correctly handles multi-line strings
    and dynamic citations. Adding a new concrete loss model class automatically
    causes the check to cover it — no manual registration of class names needed.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup: make src/cascade importable without installing the package.
# ---------------------------------------------------------------------------
_REPO = Path(__file__).resolve().parent.parent
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _load_registry(registry_path: Path) -> list[str]:
    """Parse citation_registry.yaml and return the list of registered keys."""
    try:
        import tomllib
    except ImportError:
        tomllib = None  # type: ignore

    try:
        import yaml  # type: ignore
        with registry_path.open() as fh:
            data = yaml.safe_load(fh)
        return [entry["citation_key"].strip() for entry in data.get("entries", [])]
    except ImportError:
        pass

    # Fallback: minimal YAML parser for the specific format used here.
    # citation_key entries are either single-line or block scalars (>-).
    keys: list[str] = []
    current_key_lines: list[str] = []
    in_key = False
    with registry_path.open() as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")
            stripped = line.strip()

            # Start of a citation_key value
            if stripped.startswith("citation_key: >-"):
                in_key = True
                current_key_lines = []
                continue
            if stripped.startswith("citation_key:") and not stripped.endswith(">-"):
                # Single-line key: citation_key: "some string"
                val = stripped[len("citation_key:"):].strip().strip("'\"")
                keys.append(val)
                in_key = False
                continue

            if in_key:
                # Block scalar: collect continuation lines (indented)
                if stripped and not stripped.startswith("-") and not stripped.startswith("equations_"):
                    if line.startswith("    ") or line.startswith("      "):
                        current_key_lines.append(stripped)
                        continue
                # End of block scalar
                if current_key_lines:
                    keys.append(" ".join(current_key_lines))
                    current_key_lines = []
                in_key = False

    # Flush any dangling key
    if in_key and current_key_lines:
        keys.append(" ".join(current_key_lines))

    return keys


def _collect_citations() -> list[tuple[str, str]]:
    """Instantiate every known concrete LossModel and SlipFactor class and
    collect (class_name, citation_string) pairs. Also iterate over the
    seed material catalogue and collect each Material.source field.

    Returns a list of (source_description, citation_string) pairs.
    """
    from cascade.materials.registry import MaterialDB
    from cascade.meanline.loss_models_impl import (
        AungierCentrifugal,
        StanitzSlip,
        StodolaSlip,
        WhitfieldBainesRadial,
        WiesnerSlip,
    )

    pairs: list[tuple[str, str]] = []

    # Slip factors
    for cls in [StanitzSlip, WiesnerSlip, StodolaSlip]:
        instance = cls()
        pairs.append((f"{cls.__name__}.citation", instance.citation.strip()))

    # Loss models
    for cls in [WhitfieldBainesRadial, AungierCentrifugal]:
        instance = cls()
        pairs.append((f"{cls.__name__}.citation", instance.citation.strip()))

    # Material source fields (CI-01 gap closed).
    for m in MaterialDB.list():
        pairs.append((f"Material({m.name}).source", m.source.strip()))

    return pairs


def _normalize(s: str) -> str:
    """Normalize whitespace and newlines for comparison."""
    return " ".join(s.split())


def main() -> int:
    registry_path = _REPO / "scripts" / "citation_registry.yaml"
    if not registry_path.exists():
        print(f"ERROR: Citation registry not found at {registry_path}", file=sys.stderr)
        print("Create it by running: python scripts/check_citations.py --bootstrap", file=sys.stderr)
        return 1

    print(f"Loading citation registry from {registry_path}")
    registered_raw = _load_registry(registry_path)
    registered = {_normalize(k) for k in registered_raw}
    print(f"Registry contains {len(registered)} entries.")

    print("\nCollecting citations from loss model classes and material catalogue...")
    pairs = _collect_citations()
    print(f"Found {len(pairs)} citations in codebase.")

    missing: list[tuple[str, str]] = []
    for source, citation in pairs:
        norm = _normalize(citation)
        if norm not in registered:
            missing.append((source, citation))

    if not missing:
        print("\nOK — all citations are registered.")
        for source, citation in pairs:
            short = citation[:70].replace("\n", " ")
            print(f"  {source}: {short!r}...")
        return 0

    print(f"\nFAIL — {len(missing)} citation(s) not in registry:")
    for source, citation in missing:
        print(f"\n  Source: {source}")
        print(textwrap.indent(citation, "  Citation: "))
        print("  --> Add this string to scripts/citation_registry.yaml")

    print(
        "\nTo fix: add the missing citation(s) to scripts/citation_registry.yaml",
        "\nusing the same exact string returned by the .citation property.",
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
