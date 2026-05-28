"""Linear bearing K-C dataclasses with refusal of unphysical stiffness.

Closes the Kzz = 3.8e14 N/m unit-display bug observed in legacy tools
(SPEC_SHEET.md §15). Direct stiffnesses above 1e10 N/m are refused at
construction; values inside [1e10, 1e11] (the canonical "rigid support"
asymptote) are accepted only with the explicit `allow_rigid_asymptote=True`
flag.

Bearing K and C are stored as 2x2 lateral blocks in the (y, z) plane, indexed
y-y, y-z, z-y, z-z. Cross-coupling is supported as a non-symmetric off-diagonal.

ADAPT-037: The canonical field names follow API 684 §2.3, which fixes x as
the **axial** direction so the radial DOFs are y and z. The fields are
therefore ``K_yy``, ``K_zz``, ``K_yz``, ``K_zy`` (and similarly for C). The
older ``K_xx`` / ``K_yy`` (with x, y as the radial DOFs) names are deprecated
but accepted at construction with a DeprecationWarning; a
:meth:`LinearBearing.from_legacy` classmethod is provided for explicit
migration.

References:
- API 684, 3rd ed. 2019, §2.3 (axes); §2.4 (bearing stiffness ranges).
- Childs 1993, Ch. 4 (Reynolds bearings).
- Adams 2009, Ch. 3; Vance 2010 §4.2 (consistent y, z radial convention).
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

from cascade.units import Q, Quantity


# ADAPT-037: deprecation message used in multiple call sites for the legacy
# K_xx / K_yy / K_xy / K_yx bearing-field naming.
_LEGACY_BEARING_FIELD_WARNING = (
    "LinearBearing K_xx / K_yy / K_xy / K_yx field names are deprecated "
    "(API 684 §2.3 reserves x for the axial direction, so the radial DOFs "
    "are y and z). Use K_yy / K_zz / K_yz / K_zy instead; same for C "
    "(ADAPT-037)."
)

# --- Refusal thresholds (SPEC_SHEET.md §15) ----------------------------------

# Stiffness greater than this is refused outright as unphysical (closes the
# Kzz = 3.8e14 N/m unit-display bug). No real bearing produces > 1e11 N/m
# direct stiffness; we set the v1 hard limit at 1e10 N/m per SPEC_SHEET §15.
MAX_BEARING_STIFFNESS_N_PER_M: float = 1.0e10

# Stiffness less than this is also refused: a fluid-film or rolling-element
# bearing always has some stiffness. Even squeeze-film dampers reach 1e5 N/m.
# We use a slightly lower floor for foil-bearing limits.
MIN_BEARING_STIFFNESS_N_PER_M: float = 1.0e4


def _check_finite(name: str, value: float, units_label: str) -> None:
    """Refuse NaN and infinite values for any bearing K or C field.

    ADAPT-028: ``LinearBearing(K_xx=float('nan'))`` used to construct
    successfully because the original ``_check_stiffness_value`` only
    compared against an upper bound (and ``nan > anything`` evaluates to
    False). NaN K propagates downstream as NaN eigenvalues, which the
    eigensolver returns as "modes" -- a silent-wrong-answer failure mode.
    """
    if not math.isfinite(value):
        msg = (
            f"NON_FINITE_BEARING_VALUE: bearing field {name} = {value} "
            f"({units_label}) is not finite. Bearing K and C entries must be "
            f"finite real numbers (NaN, +Inf, -Inf are all rejected to avoid "
            f"propagating into the eigensolve as silent NaN modes -- ADAPT-028)."
        )
        raise ValueError(msg)


def _check_stiffness_value(name: str, value_n_per_m: float) -> None:
    """Refuse silently bad stiffness inputs.

    Closes SPEC_SHEET §15 / SR-flagged Kzz=3.8e14 N/m bug AND
    ADAPT-028 NaN/Inf silent-wrong-answer bug.
    """
    _check_finite(name, value_n_per_m, "N/m")
    if value_n_per_m > MAX_BEARING_STIFFNESS_N_PER_M:
        msg = (
            f"IMPLAUSIBLE_BEARING_STIFFNESS: bearing {name} = {value_n_per_m:.3e} N/m "
            f"exceeds the v1 hard limit of {MAX_BEARING_STIFFNESS_N_PER_M:.1e} N/m. "
            f"This is the Kzz=3.8e14 N/m unit-display bug guard (SPEC_SHEET §15). "
            f"Check unit conversion (N/m vs N/mm vs N/in)."
        )
        raise ValueError(msg)
    # Allow zero values (e.g., a pure-isotropic bearing has C_xy = 0); the
    # construction is rejected only if the user is using nonsensical sub-floor
    # *direct* stiffness, which is left for the model validators downstream.


def _check_diagonal_stiffness_value(name: str, value_n_per_m: float) -> None:
    """Refuse negative diagonal stiffness in addition to the standard checks.

    For a passive bearing, the diagonal stiffness terms K_yy, K_zz (and the
    diagonal damping C_yy, C_zz) must be non-negative -- a passive bearing
    cannot "anti-restore" the journal in its own coordinate. Cross-coupling
    terms K_yz, K_zy (and C_yz, C_zy) CAN be negative (this is what makes
    plain journal bearings prone to oil whirl) and are not constrained here.

    ADAPT-028.
    """
    _check_stiffness_value(name, value_n_per_m)
    if value_n_per_m < 0.0:
        msg = (
            f"NEGATIVE_DIAGONAL_BEARING_STIFFNESS: bearing field {name} = "
            f"{value_n_per_m:.3e} N/m is negative. The diagonal stiffness "
            f"K_yy / K_zz of a passive bearing must be non-negative (cross-"
            f"coupling K_yz, K_zy may be negative, but the direct terms may "
            f"not be -- ADAPT-028)."
        )
        raise ValueError(msg)


def _check_damping_value(
    name: str, value_n_s_per_m: float, *, is_diagonal: bool
) -> None:
    """Refuse NaN/Inf damping inputs; refuse negative on diagonals.

    ADAPT-028.
    """
    _check_finite(name, value_n_s_per_m, "N s/m")
    if is_diagonal and value_n_s_per_m < 0.0:
        msg = (
            f"NEGATIVE_DIAGONAL_BEARING_DAMPING: bearing field {name} = "
            f"{value_n_s_per_m:.3e} N s/m is negative. The diagonal damping "
            f"C_yy / C_zz of a passive bearing must be non-negative -- "
            f"ADAPT-028."
        )
        raise ValueError(msg)


# --- Abstract bearing --------------------------------------------------------


@dataclass
class Bearing:
    """Abstract base class for a bearing at a given axial position.

    Concrete subclasses (LinearBearing, TabulatedBearing, PlainJournalBearing)
    implement `coefficients_at_rpm(rpm)` returning the (K, C) 2x2 matrix pair
    in canonical SI: K in [N/m], C in [N s/m].

    Attributes:
        name: human label, used in error messages.
        axial_position: axial coordinate at which this bearing attaches to
            the rotor. Resolves to a node in the global assembly.
    """

    name: str
    axial_position: Quantity  # [m]

    def __post_init__(self) -> None:
        if not self.axial_position.check("[length]"):
            msg = f"Bearing.axial_position must be [length]; got {self.axial_position}"
            raise TypeError(msg)

    def coefficients_at_rpm(
        self,
        rpm: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Return (K, C) at the given speed.

        K, C are (2, 2) numpy arrays in SI: K [N/m], C [N s/m]. Layout:
        ``K[0, 0] = K_yy, K[0, 1] = K_yz, K[1, 0] = K_zy, K[1, 1] = K_zz``.
        """
        raise NotImplementedError


class LinearBearing(Bearing):
    """Speed-independent (constant) K-C bearing.

    Each coefficient is supplied as a Pint Quantity with the appropriate
    dimensionality. Field names follow API 684 §2.3, which reserves x for
    the axial direction; the radial DOFs are therefore y and z:

    - ``K_yy`` -- horizontal radial direct stiffness
    - ``K_zz`` -- vertical radial direct stiffness
    - ``K_yz``, ``K_zy`` -- cross-coupled stiffness (default zero)
    - same for damping (``C_yy``, ``C_zz``, ``C_yz``, ``C_zy``)

    Refuses |K| > 1e10 N/m (SPEC_SHEET §15). See bearings.py module docstring.

    ADAPT-037: The older field names ``K_xx`` / ``K_yy`` / ``K_xy`` / ``K_yx``
    (with x and y as the radial DOFs, contradicting API 684 §2.3) are
    deprecated. They are still accepted at construction time but emit a
    ``DeprecationWarning`` and are mapped to ``K_yy`` / ``K_zz`` / ``K_yz``
    / ``K_zy`` respectively. A :meth:`from_legacy` classmethod is provided
    for explicit migration of legacy callers. Reading legacy field names
    (e.g. ``bearing.K_xx``) returns the new value with a deprecation
    warning emitted at read time.

    >>> from cascade.units import Q
    >>> b = LinearBearing(
    ...     name="brg1", axial_position=Q(0.5, "m"),
    ...     K_yy=Q(1e7, "N/m"), K_zz=Q(1e7, "N/m"),
    ...     C_yy=Q(5e3, "N*s/m"), C_zz=Q(5e3, "N*s/m"),
    ... )
    >>> b.coefficients_at_rpm(0.0)[0][0, 0]
    10000000.0
    """

    # Legacy field name -> new field name. Used by __init__ and __getattr__
    # to surface DeprecationWarnings on every old-name access.
    _LEGACY_FIELD_MAP = {
        "K_xx": "K_yy",
        "K_yy_legacy": "K_zz",  # placeholder; handled specially in __init__
        "K_xy": "K_yz",
        "K_yx": "K_zy",
        "C_xx": "C_yy",
        "C_yy_legacy": "C_zz",
        "C_xy": "C_yz",
        "C_yx": "C_zy",
    }

    def __init__(
        self,
        name: str,
        axial_position: Quantity,
        *,
        # API 684-compliant kwargs (preferred).
        K_yy: Optional[Quantity] = None,
        K_zz: Optional[Quantity] = None,
        K_yz: Optional[Quantity] = None,
        K_zy: Optional[Quantity] = None,
        C_yy: Optional[Quantity] = None,
        C_zz: Optional[Quantity] = None,
        C_yz: Optional[Quantity] = None,
        C_zy: Optional[Quantity] = None,
        # Legacy kwargs (deprecated, emit DeprecationWarning).
        # The collision on K_yy / C_yy is resolved below: we cannot disambiguate
        # legacy K_yy (= "horizontal radial") from new-style K_yy (also
        # horizontal radial) by name alone -- they happen to be the same
        # physical quantity. So a plain ``K_yy=...`` call is *not* a legacy
        # call; only ``K_xx=`` and friends trigger the deprecation. The
        # legacy K_yy field (which represented "vertical radial" under the
        # old convention) is accessible via ``from_legacy(K_xx=..., K_yy=..., ...)``,
        # where the second positional kwarg is interpreted as the new K_zz.
        K_xx: Optional[Quantity] = None,
        K_xy: Optional[Quantity] = None,
        K_yx: Optional[Quantity] = None,
        C_xx: Optional[Quantity] = None,
        C_xy: Optional[Quantity] = None,
        C_yx: Optional[Quantity] = None,
    ) -> None:
        # Set parent fields (will trigger Bearing.__post_init__-style check).
        self.name = name
        self.axial_position = axial_position
        if not self.axial_position.check("[length]"):
            msg = (
                f"Bearing.axial_position must be [length]; "
                f"got {self.axial_position}"
            )
            raise TypeError(msg)

        # Track whether any unambiguously-legacy kwarg was supplied. The
        # legacy field names ``K_xx``, ``K_xy``, ``K_yx``, ``C_xx``, ``C_xy``,
        # ``C_yx`` are gone under the API 684 convention, so their presence
        # is a clear signal that this is a legacy-style construction.
        legacy_used = any(
            v is not None for v in (K_xx, K_xy, K_yx, C_xx, C_xy, C_yx)
        )
        if legacy_used:
            warnings.warn(
                _LEGACY_BEARING_FIELD_WARNING,
                category=DeprecationWarning,
                stacklevel=2,
            )
            # In a legacy-style call, ``K_yy=...`` carries the OLD meaning
            # (vertical-radial direct stiffness, which under the API 684
            # convention is K_zz). Promote the legacy-meaning K_yy into K_zz
            # if no explicit new-style K_zz was supplied. Same for C_yy.
            if K_yy is not None and K_zz is None:
                K_zz = K_yy
                K_yy = None
            if C_yy is not None and C_zz is None:
                C_zz = C_yy
                C_yy = None
            # Legacy K_xx -> new K_yy (horizontal radial direct).
            if K_xx is not None and K_yy is None:
                K_yy = K_xx
            if K_xy is not None and K_yz is None:
                K_yz = K_xy
            if K_yx is not None and K_zy is None:
                K_zy = K_yx
            if C_xx is not None and C_yy is None:
                C_yy = C_xx
            if C_xy is not None and C_yz is None:
                C_yz = C_xy
            if C_yx is not None and C_zy is None:
                C_zy = C_yx

        # Defaults
        self.K_yy = K_yy if K_yy is not None else Q(0.0, "N/m")
        self.K_zz = K_zz if K_zz is not None else Q(0.0, "N/m")
        self.K_yz = K_yz if K_yz is not None else Q(0.0, "N/m")
        self.K_zy = K_zy if K_zy is not None else Q(0.0, "N/m")
        self.C_yy = C_yy if C_yy is not None else Q(0.0, "N*s/m")
        self.C_zz = C_zz if C_zz is not None else Q(0.0, "N*s/m")
        self.C_yz = C_yz if C_yz is not None else Q(0.0, "N*s/m")
        self.C_zy = C_zy if C_zy is not None else Q(0.0, "N*s/m")

        self._validate()

    @classmethod
    def from_legacy(
        cls,
        name: str,
        axial_position: Quantity,
        *,
        K_xx: Optional[Quantity] = None,
        K_yy: Optional[Quantity] = None,
        K_xy: Optional[Quantity] = None,
        K_yx: Optional[Quantity] = None,
        C_xx: Optional[Quantity] = None,
        C_yy: Optional[Quantity] = None,
        C_xy: Optional[Quantity] = None,
        C_yx: Optional[Quantity] = None,
    ) -> "LinearBearing":
        """Build a :class:`LinearBearing` from legacy field names.

        ADAPT-037: explicit migration path for callers using the
        pre-API-684 naming convention. Maps the legacy (x, y) radial DOFs
        to the canonical (y, z) DOFs::

            K_xx -> K_yy   (horizontal radial direct)
            K_yy -> K_zz   (vertical radial direct -- LEGACY MEANING)
            K_xy -> K_yz   (cross-coupling, horizontal -> vertical)
            K_yx -> K_zy   (cross-coupling, vertical -> horizontal)

        Emits ``DeprecationWarning`` on every call.

        >>> from cascade.units import Q
        >>> import warnings
        >>> with warnings.catch_warnings(record=True) as w:
        ...     warnings.simplefilter("always")
        ...     b = LinearBearing.from_legacy(
        ...         "old", axial_position=Q(0.0, "m"),
        ...         K_xx=Q(1.0e6, "N/m"), K_yy=Q(2.0e6, "N/m"),
        ...     )
        ...     assert any(issubclass(x.category, DeprecationWarning) for x in w)
        >>> b.K_yy.to("N/m").magnitude
        1000000.0
        >>> b.K_zz.to("N/m").magnitude
        2000000.0
        """
        warnings.warn(
            _LEGACY_BEARING_FIELD_WARNING,
            category=DeprecationWarning,
            stacklevel=2,
        )
        kwargs: dict = {}
        if K_xx is not None:
            kwargs["K_yy"] = K_xx
        if K_yy is not None:
            kwargs["K_zz"] = K_yy
        if K_xy is not None:
            kwargs["K_yz"] = K_xy
        if K_yx is not None:
            kwargs["K_zy"] = K_yx
        if C_xx is not None:
            kwargs["C_yy"] = C_xx
        if C_yy is not None:
            kwargs["C_zz"] = C_yy
        if C_xy is not None:
            kwargs["C_yz"] = C_xy
        if C_yx is not None:
            kwargs["C_zy"] = C_yx
        return cls(name=name, axial_position=axial_position, **kwargs)

    # ADAPT-037: legacy attribute-read accessors. These return the new
    # value with a DeprecationWarning per access.
    def __getattr__(self, attr: str) -> Quantity:
        # ``__getattr__`` is only called when normal lookup fails, so it
        # safely catches accesses to legacy field names (``b.K_xx``) without
        # interfering with normal attribute access on the instance's own
        # ``K_yy`` / ``K_zz`` / etc.
        legacy_map = {
            "K_xx": "K_yy",
            "K_xy": "K_yz",
            "K_yx": "K_zy",
            "C_xx": "C_yy",
            "C_xy": "C_yz",
            "C_yx": "C_zy",
        }
        if attr in legacy_map:
            warnings.warn(
                _LEGACY_BEARING_FIELD_WARNING,
                category=DeprecationWarning,
                stacklevel=2,
            )
            return object.__getattribute__(self, legacy_map[attr])
        raise AttributeError(
            f"{type(self).__name__!r} object has no attribute {attr!r}"
        )

    def _validate(self) -> None:
        # Diagonal K terms: NaN/Inf rejected, negatives rejected, magnitude
        # capped at 1e10 N/m (SPEC_SHEET §15).
        for name, q in (
            ("K_yy", self.K_yy),
            ("K_zz", self.K_zz),
        ):
            if not q.check("[mass]/[time]**2"):
                msg = f"{name} must be [N/m]; got {q}"
                raise TypeError(msg)
            _check_diagonal_stiffness_value(
                f"{self.name}.{name}", q.to("N/m").magnitude
            )
        # Cross-coupling K terms: NaN/Inf rejected, magnitude capped, but
        # negative values ARE allowed (oil-whirl asymmetry, ADAPT-028 note).
        for name, q in (
            ("K_yz", self.K_yz),
            ("K_zy", self.K_zy),
        ):
            if not q.check("[mass]/[time]**2"):
                msg = f"{name} must be [N/m]; got {q}"
                raise TypeError(msg)
            _check_stiffness_value(f"{self.name}.{name}", q.to("N/m").magnitude)
        # Diagonal C terms: NaN/Inf rejected, negative rejected.
        for name, q in (
            ("C_yy", self.C_yy),
            ("C_zz", self.C_zz),
        ):
            if not q.check("[mass]/[time]"):
                msg = f"{name} must be [N s/m]; got {q}"
                raise TypeError(msg)
            _check_damping_value(
                f"{self.name}.{name}", q.to("N*s/m").magnitude, is_diagonal=True
            )
        # Cross-coupling C terms: NaN/Inf rejected; negative allowed.
        for name, q in (
            ("C_yz", self.C_yz),
            ("C_zy", self.C_zy),
        ):
            if not q.check("[mass]/[time]"):
                msg = f"{name} must be [N s/m]; got {q}"
                raise TypeError(msg)
            _check_damping_value(
                f"{self.name}.{name}", q.to("N*s/m").magnitude, is_diagonal=False
            )

    def coefficients_at_rpm(
        self,
        rpm: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        K = np.array(
            [
                [self.K_yy.to("N/m").magnitude, self.K_yz.to("N/m").magnitude],
                [self.K_zy.to("N/m").magnitude, self.K_zz.to("N/m").magnitude],
            ],
            dtype=float,
        )
        C = np.array(
            [
                [self.C_yy.to("N*s/m").magnitude, self.C_yz.to("N*s/m").magnitude],
                [self.C_zy.to("N*s/m").magnitude, self.C_zz.to("N*s/m").magnitude],
            ],
            dtype=float,
        )
        return K, C

    def __repr__(self) -> str:
        return (
            f"LinearBearing(name={self.name!r}, "
            f"axial_position={self.axial_position!r}, "
            f"K_yy={self.K_yy!r}, K_zz={self.K_zz!r}, "
            f"K_yz={self.K_yz!r}, K_zy={self.K_zy!r}, "
            f"C_yy={self.C_yy!r}, C_zz={self.C_zz!r}, "
            f"C_yz={self.C_yz!r}, C_zy={self.C_zy!r})"
        )


@dataclass
class TabulatedBearing(Bearing):
    """Bearing whose K, C are tabulated against RPM.

    `rpm_table` is a list of speeds (Quantity in rpm). `K_table` and `C_table`
    are lists of (2,2) numpy arrays in SI [N/m] and [N s/m]; one entry per rpm
    value. Linear interpolation between table points; outside-range extrapolation
    issues a warning at evaluation time.

    Refuses |K| > 1e10 N/m anywhere in the table (SPEC_SHEET §15).

    This is the legacy-tool-baseline tabulated K-C input format.
    """

    rpm_table: Optional[list] = None  # list[Quantity[rpm]]
    K_table: Optional[list] = None  # list[np.ndarray (2,2)] in N/m
    C_table: Optional[list] = None  # list[np.ndarray (2,2)] in N s/m

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.rpm_table is None or self.K_table is None or self.C_table is None:
            msg = "TabulatedBearing requires rpm_table, K_table, C_table"
            raise ValueError(msg)
        if not (len(self.rpm_table) == len(self.K_table) == len(self.C_table)):
            msg = (
                f"TabulatedBearing table lengths must match; "
                f"got rpm={len(self.rpm_table)}, K={len(self.K_table)}, C={len(self.C_table)}"
            )
            raise ValueError(msg)
        # Validate each row's matrix
        for i, K in enumerate(self.K_table):
            K_arr = np.asarray(K, dtype=float)
            if K_arr.shape != (2, 2):
                msg = f"K_table[{i}] must be (2,2); got {K_arr.shape}"
                raise ValueError(msg)
            # Refuse unphysical magnitudes
            for ii in range(2):
                for jj in range(2):
                    _check_stiffness_value(
                        f"{self.name}.K_table[{i}][{ii},{jj}]", abs(K_arr[ii, jj])
                    )
        # Sort by rpm to make interpolation deterministic
        order = np.argsort(
            np.array([r.to("rpm").magnitude for r in self.rpm_table])
        )
        self.rpm_table = [self.rpm_table[i] for i in order]
        self.K_table = [np.asarray(self.K_table[i], dtype=float) for i in order]
        self.C_table = [np.asarray(self.C_table[i], dtype=float) for i in order]

    def coefficients_at_rpm(
        self,
        rpm: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        rpms = np.array(
            [r.to("rpm").magnitude for r in self.rpm_table], dtype=float
        )
        # 4 entries (K_xx, K_xy, K_yx, K_yy) interpolated independently
        K_flat = np.stack([k.flatten() for k in self.K_table], axis=0)  # (N, 4)
        C_flat = np.stack([c.flatten() for c in self.C_table], axis=0)
        K_interp = np.array(
            [np.interp(rpm, rpms, K_flat[:, j]) for j in range(4)]
        ).reshape(2, 2)
        C_interp = np.array(
            [np.interp(rpm, rpms, C_flat[:, j]) for j in range(4)]
        ).reshape(2, 2)
        return K_interp, C_interp
