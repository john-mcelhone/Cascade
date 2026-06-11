import type { Metadata } from "next";
import Link from "next/link";
import { CodeBlock, DocPage, ParamRow, ParamTable } from "@/components/docs";
import { Callout, Section } from "@/components/learn/content";

export const metadata: Metadata = { title: "Mean-line design" };

export default function MeanlinePage() {
  return (
    <DocPage slug="meanline">
      <Section id="what" title="What mean-line design is">
        <p>
          Between “the cycle wants a 4:1 compressor” and “here is a CAD model”
          sits mean-line design: solve the flow along one representative
          streamline through the machine, using velocity triangles,
          conservation laws, and published loss correlations. It’s how every
          real machine starts — fast enough to evaluate thousands of
          geometries, accurate enough to be worth trusting when the loss
          models are honest about their pedigree.
        </p>
        <p>Cascade v0.1.0 ships two mean-line solvers:</p>
        <ul className="ml-5 list-disc space-y-2">
          <li>
            <strong>Radial inflow turbine</strong> —{" "}
            <code className="font-mono text-[13px]">RadialTurbineMeanline</code>
          </li>
          <li>
            <strong>Centrifugal compressor</strong> —{" "}
            <code className="font-mono text-[13px]">CentrifugalCompressorMeanline</code>
          </li>
        </ul>
        <Callout kind="note" title="Scope, stated plainly">
          Axial machines (Kacker-Okapuu, Koch-Smith) are the v1.1 trajectory,
          not shipped (<code className="font-mono text-[13px]">KG-AXT-01</code>).
          The mean-line currently solves with a perfect-gas model — the cycle
          solver has real gas, the mean-line doesn&apos;t yet (
          <code className="font-mono text-[13px]">KG-ML-07</code>), so sCO₂
          mean-line work is deferred.
        </Callout>
      </Section>

      <Section id="geometry" title="Describing a machine">
        <p>
          A mean-line machine is a handful of radii, heights, angles, and
          counts. The centrifugal compressor, for example:
        </p>
        <ParamTable title="CentrifugalCompressorGeometry">
          <ParamRow name="inducer_hub_radius / inducer_tip_radius" type="float [m]" required>
            The eye of the impeller — where air enters axially.
          </ParamRow>
          <ParamRow name="impeller_outlet_radius" type="float [m]" required>
            The tip radius at exit. With rpm, this sets the tip speed — the
            single biggest lever on pressure ratio.
          </ParamRow>
          <ParamRow name="blade_height_outlet" type="float [m]" required>
            Exit passage height. Together with the radius, sets the exit flow
            area.
          </ParamRow>
          <ParamRow name="blade_count" type="int" required>
            Number of blades. More blades guide the flow better (higher slip
            factor) but add blockage and friction.
          </ParamRow>
          <ParamRow name="beta_2_metal_rad" type="float [rad]" required>
            Blade exit metal angle — backsweep trades a little work input for
            a wider stable range.
          </ParamRow>
          <ParamRow name="tip_clearance" type="float [m]" required>
            The running gap between blade and shroud. Small numbers matter
            enormously here; the loss models penalize it explicitly.
          </ParamRow>
        </ParamTable>
        <p>
          The radial turbine&apos;s{" "}
          <code className="font-mono text-[13px]">RadialTurbineGeometry</code>{" "}
          is analogous: rotor inlet radius, hub and tip exducer radii, blade
          heights, blade count, metal angles, tip clearance, and a design
          swirl ratio.
        </p>
      </Section>

      <Section id="losses" title="Loss models — every one cited">
        <p>
          A mean-line solver is only as honest as its loss accounting. Cascade
          enforces this structurally: every loss model class carries a
          published citation string, and a CI gate (
          <code className="font-mono text-[13px]">make check-citations</code>)
          instantiates each model and cross-checks its citation against a
          registry. A loss model without a citation fails the build.
        </p>
        <div className="overflow-x-auto scrollbar-subtle">
          <table className="w-full min-w-[520px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-border-subtle text-left">
                <th className="py-2 pr-4 text-xs font-medium uppercase tracking-wide text-text-muted">Component</th>
                <th className="py-2 pr-4 text-xs font-medium uppercase tracking-wide text-text-muted">Model</th>
                <th className="py-2 text-xs font-medium uppercase tracking-wide text-text-muted">Published source</th>
              </tr>
            </thead>
            <tbody className="text-text-subtle">
              <tr className="border-b border-border-subtle/60">
                <td className="py-2 pr-4">Radial turbine</td>
                <td className="py-2 pr-4 font-mono text-xs">WhitfieldBainesRadial</td>
                <td className="py-2">Whitfield &amp; Baines 1990; Glassman 1976 (NASA TN D-8164) tip clearance; Daily &amp; Nece 1960 disc friction</td>
              </tr>
              <tr className="border-b border-border-subtle/60">
                <td className="py-2 pr-4">Centrifugal compressor</td>
                <td className="py-2 pr-4 font-mono text-xs">AungierCentrifugal</td>
                <td className="py-2">Aungier 2000</td>
              </tr>
              <tr>
                <td className="py-2 pr-4">Slip factor</td>
                <td className="py-2 pr-4 font-mono text-xs">WiesnerSlip · StanitzSlip · StodolaSlip</td>
                <td className="py-2">Wiesner 1967 / Stanitz / Stodola</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p>
          You can also ship your own correlation — with a citation, which is
          mandatory — as a{" "}
          <Link href="/docs/plugins" className="font-medium text-brand-text hover:underline">
            plugin
          </Link>
          , and select it per project in the Flow path page&apos;s loss-model
          picker.
        </p>
      </Section>

      <Section id="scripting" title="Solving a machine from Python">
        <CodeBlock
          lang="python"
          title="centrifugal_compressor.py"
          code={`import math
from cascade.meanline import (
    CentrifugalCompressorMeanline,
    CentrifugalCompressorGeometry,
    AungierCentrifugal,
)
from cascade.units import Port, Q, Composition

inlet = Port(
    pressure_total=Q(101.325, "kPa"),
    temperature_total=Q(288.15, "K"),
    mass_flow=Q(0.31, "kg/s"),
    composition=Composition.air(),
)
geom = CentrifugalCompressorGeometry(
    inducer_hub_radius=0.008,        # all lengths in metres
    inducer_tip_radius=0.030,
    impeller_outlet_radius=0.055,
    blade_height_outlet=0.0045,
    blade_count=15,
    beta_2_metal_rad=math.pi / 6,    # 30° backsweep
    tip_clearance=0.00015,
)

solver = CentrifugalCompressorMeanline()
result = solver.solve(
    inlet=inlet,
    rpm=Q(70_000, "rpm"),
    geometry=geom,
    loss_model=AungierCentrifugal(),
)
print(f"π_tt = {result.pressure_ratio:.3f}")
print(f"η_tt = {result.efficiency_total_to_total:.4f}")`}
        />
        <p>
          The radial turbine works the same way:{" "}
          <code className="font-mono text-[13px]">
            RadialTurbineMeanline().solve(inlet, rpm, geometry, loss_model=WhitfieldBainesRadial())
          </code>
          . Results include the full loss breakdown — where every point of
          missing efficiency went — alongside the velocity triangles, so the
          Analysis page can show you incidence, passage, clearance, and
          windage losses separately.
        </p>
      </Section>

      <Section id="refusals" title="Validity, not extrapolation">
        <p>
          Loss correlations are curve fits to published rigs. Outside the
          fitted regime they aren&apos;t “less accurate” — they&apos;re
          fiction. So the solvers enforce a validity envelope:
        </p>
        <ul className="ml-5 list-disc space-y-2">
          <li>
            Relative Mach number beyond the correlated range raises{" "}
            <code className="font-mono text-[13px]">RegimeOutOfValidity</code>{" "}
            instead of returning a number.
          </li>
          <li>
            A continuity iteration that won&apos;t settle raises a convergence
            error rather than reporting the last iterate as truth.
          </li>
          <li>
            In design exploration and performance maps, these surface as
            explicit per-candidate / per-point status codes rather than
            exceptions.
          </li>
        </ul>
      </Section>

      <Section id="validation" title="How good is it? Read the fine print">
        <p>
          The compressor reproduces Eckardt Rotor A (case CC-1) within the
          ±0.10 gate — <em>with</em> the documented calibration{" "}
          <code className="font-mono text-[13px]">wiesner_calibration_scale=1.05</code>{" "}
          (<code className="font-mono text-[13px]">KG-ML-02</code>); the
          default Wiesner slip gives π_tt ≈ 1.78 vs the published 1.94. The
          radial turbine hits NASA TN D-7508 within 2.3 points on a ±5 point
          gate — wide because the geometry is an approximate reconstruction;
          digitizing the exact NASA deck is what tightens it (
          <code className="font-mono text-[13px]">KG-ML-04</code>).
        </p>
        <Callout kind="warning" title="This fine print is the product">
          Most tools publish the headline and bury the calibration. Cascade
          publishes both, because a number you can audit is worth more than a
          number that flatters. Full caveats live in the{" "}
          <Link href="/docs/validation" className="font-medium text-brand-text hover:underline">
            validation report
          </Link>
          .
        </Callout>
      </Section>
    </DocPage>
  );
}
