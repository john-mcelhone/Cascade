"""Cascade custom loss model — template.

This file is the starting point for a user-written loss model. Copy
it to a new location, rename the class, edit `loss_coefficient`, then
install via:

    cascade plugin install ./my_loss_model.py

OR via the web UI: Project → Settings → Loss Models → Upload Plugin.

Security
========

Plugin code runs IN THE SAME PROCESS as Cascade's solvers. There is NO
sandboxing in v1. A plugin can:

- Read any file your Cascade process can read.
- Make network calls.
- Spawn subprocesses.

Do **not** install plugins from sources you do not trust. The Cascade
CLI prompts before loading; the API logs every install with caller
identity. v1.1 will add subprocess isolation.

Authoring tips
==============

- Keep `loss_coefficient` deterministic and fast (it is called inside
  the Newton iteration of the meanline solver — tens of times per
  operating point, thousands of times per performance map).
- Return ζ ≥ 0. Negative loss coefficients imply entropy destruction
  and will be rejected by the registry.
- Use only `context.*` fields. If you need another input, request it
  via the upstream API rather than reaching into solver internals.

References
==========

If you cite a published correlation, include the citation in the
docstring so reviewers can verify the formula. SPEC_SHEET §7 ("open
citation discipline") applies to built-in models; user plugins are
not bound by it, but it's good engineering hygiene.
"""

from __future__ import annotations

from cascade.plugins import LossContext, LossModel


class MyConductivityWeightedLossModel(LossModel):
    """Example custom loss model emphasising conductivity-weighted heat loss.

    This is a deliberately simple correlation; the point of the template
    is to show the shape, not the physics. Replace `loss_coefficient`
    with your model.

    Citation: (none — this is example code; cite your real source here).
    """

    # Shown in the UI dropdown, the API list, and the report.
    name = "MyConductivityWeighted"

    # Must be a non-empty list of:
    # - "radial_turbine"
    # - "centrifugal_compressor"
    # - "axial_turbine" (reserved for v1.1)
    applicable_machine_classes = ["radial_turbine"]

    # Optional metadata — surfaced in the UI / report.
    description = "Conductivity-weighted heat-loss correlation."
    citation = "Author, Y., 20XX. Title, Journal, vol(no), pp–pp."
    author = "You"
    version = "0.1.0"

    def loss_coefficient(self, context: LossContext) -> float:
        """Return ζ — the dimensionless total entropy-generation
        coefficient for one stage.

        Convention: the solver multiplies your ζ by ½ U₂² to get the
        specific-enthalpy loss (J/kg). So a ζ of 0.10 means the stage
        loses 10% of ½ U₂² as entropy generation.

        Args:
            context: A frozen `LossContext` with the local stage state.
                See `cascade.plugins.base.LossContext` for the full
                field list.

        Returns:
            float: ζ ≥ 0.
        """
        # Replace this body with your model. A simple example:
        # ζ = baseline + Mach-squared correction.
        baseline = 0.05
        mach_term = 0.02 * (context.M_relative_max ** 2)
        return baseline + mach_term


# At module import, Cascade's loader scans for any LossModel subclass
# defined in this file. There is no explicit registration step.
#
# If you want to be explicit (e.g. you're publishing a library that
# self-registers when imported), call:
#
#     from cascade.plugins import PLUGIN_REGISTRY
#     PLUGIN_REGISTRY.register(MyConductivityWeightedLossModel)
