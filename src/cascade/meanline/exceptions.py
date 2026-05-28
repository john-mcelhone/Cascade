"""Mean-line solver exceptions.

Per SPEC_SHEET §13 ("Validity regions and refusal behavior"): when the
computed regime falls outside the documented validity envelope of the loss
model or the solver, we explicitly raise rather than silently extrapolating.
"""

from __future__ import annotations


class MeanlineError(Exception):
    """Base class for all mean-line solver exceptions."""


class RegimeOutOfValidity(MeanlineError):
    """Raised when the converged operating point exceeds the loss model's
    validity envelope (e.g. relative Mach > 2.5 for radial machines per
    SPEC_SHEET §13).

    Per SPEC_SHEET §13: "Refusal triggers explicit RefuseToCompute exception
    with cause code (REGIME_OUT_OF_VALIDITY)." We carry the cause string
    on the exception for downstream UI rendering.
    """

    cause_code: str = "REGIME_OUT_OF_VALIDITY"

    def __init__(self, message: str, *, regime_variable: str = "", value: float = 0.0,
                 limit: float = 0.0) -> None:
        super().__init__(message)
        self.regime_variable = regime_variable
        self.value = value
        self.limit = limit


class MeanlineConvergenceError(MeanlineError):
    """Raised when the inner mean-line Newton/fixed-point fails to converge
    within the iteration budget. Per SPEC_SHEET §3.3 the inner tolerance is
    1e-6 relative.
    """


class InvalidGeometry(MeanlineError):
    """Raised when the requested geometry is dimensionally invalid (e.g.
    negative blade height, inducer hub > tip)."""
