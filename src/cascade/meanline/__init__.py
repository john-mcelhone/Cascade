"""Mean-line solvers for radial-inflow turbines and centrifugal compressors.

Implements SPEC_SHEET.md §3 (Port-based handoff), §7 (citation discipline),
§12 RIT-1/2/CC-1/2 (validation cases), §13 (validity envelope).

Reading order:
- `loss_models` — the `LossModel` Protocol, `LossBreakdown`, `ValidityEnvelope`
  dataclasses + the slip-factor closures (Stanitz / Wiesner / Stodola).
- `loss_models_impl` — concrete `WhitfieldBainesRadial` + `AungierCentrifugal`
  loss models.
- `radial_turbine` — `RadialTurbineMeanline` solver per Whitfield & Baines
  (1990) Ch. 6.
- `centrifugal_compressor` — `CentrifugalCompressorMeanline` solver per
  Aungier (2000) Ch. 6.

All public APIs consume / produce `cascade.units.Port`; all numeric quantities
carry units via `cascade.units.Q`.

Validity envelope refusal: `RegimeOutOfValidity` is raised when the
computed regime exceeds the loss model's documented validity (SPEC §13).
"""

from __future__ import annotations

from cascade.meanline.exceptions import RegimeOutOfValidity
from cascade.meanline.loss_models import (
    LossBreakdown,
    LossModel,
    SlipFactor,
    ValidityEnvelope,
)
from cascade.meanline.loss_models_impl import (
    AungierCentrifugal,
    DailyNeceRegime,
    StanitzSlip,
    StodolaSlip,
    WhitfieldBainesRadial,
    WiesnerSlip,
    daily_nece_moment_coefficient,
    daily_nece_regime,
)
from cascade.meanline.radial_turbine import (
    PortState,
    RadialTurbineGeometry,
    RadialTurbineMeanline,
    RadialTurbineResult,
    VTriangle,
)
from cascade.meanline.centrifugal_compressor import (
    CentrifugalCompressorGeometry,
    CentrifugalCompressorMeanline,
    CentrifugalCompressorResult,
)

__all__ = [
    "AungierCentrifugal",
    "CentrifugalCompressorGeometry",
    "CentrifugalCompressorMeanline",
    "CentrifugalCompressorResult",
    "DailyNeceRegime",
    "LossBreakdown",
    "LossModel",
    "PortState",
    "RadialTurbineGeometry",
    "RadialTurbineMeanline",
    "RadialTurbineResult",
    "RegimeOutOfValidity",
    "SlipFactor",
    "StanitzSlip",
    "StodolaSlip",
    "ValidityEnvelope",
    "VTriangle",
    "WhitfieldBainesRadial",
    "WiesnerSlip",
    "daily_nece_moment_coefficient",
    "daily_nece_regime",
]
