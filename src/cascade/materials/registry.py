"""MaterialDB registry — lookup + listing.

The UI and any solver code that needs a material by name should go
through :class:`MaterialDB` rather than importing from
:mod:`cascade.materials.database` directly. The registry layer also
normalises legacy shorthand keys (``"AISI4340"`` → ``"AISI 4340"``).
"""

from __future__ import annotations

from cascade.materials.base import Material
from cascade.materials.database import ALIASES, MATERIALS


class MaterialDB:
    """Registry for the seed materials catalogue.

    Usage::

        from cascade.materials import MaterialDB

        inco = MaterialDB.get("Inconel 625")
        E_at_900K = inco.E(900.0)        # Pa
        sigma_y_at_900K = inco.sigma_yield(900.0)  # Pa

        for m in MaterialDB.list():
            print(m.name, m.family)

    The catalogue is *frozen* at import time. To extend it, add the
    :class:`Material` to :mod:`cascade.materials.database` (with a real
    open-literature citation) and re-import.
    """

    @classmethod
    def get(cls, name: str) -> Material:
        """Look up a material by canonical name or recognised alias.

        Raises
        ------
        KeyError
            If the name is unknown. The error message lists the
            available canonical names so the caller can recover.
        """
        if name in MATERIALS:
            return MATERIALS[name]
        if name in ALIASES:
            return MATERIALS[ALIASES[name]]
        known = ", ".join(sorted(MATERIALS.keys()))
        msg = f"Unknown material {name!r}. Known: {known}"
        raise KeyError(msg)

    @classmethod
    def list(cls) -> list[Material]:
        """Return every registered material, in insertion order."""
        return list(MATERIALS.values())

    @classmethod
    def names(cls) -> list[str]:
        """Return every canonical material name."""
        return list(MATERIALS.keys())

    @classmethod
    def by_family(cls, family: str) -> list[Material]:
        """All materials in the given family (case-insensitive)."""
        f = family.lower()
        return [m for m in MATERIALS.values() if m.family.lower() == f]

    @classmethod
    def families(cls) -> list[str]:
        """Distinct family strings, sorted for stable UI rendering."""
        return sorted({m.family for m in MATERIALS.values()})
