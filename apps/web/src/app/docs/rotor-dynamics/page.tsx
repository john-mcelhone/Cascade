import type { Metadata } from "next";
import Link from "next/link";
import { CodeBlock, CodeTabs, DocPage, ParamRow, ParamTable } from "@/components/docs";
import { Callout, Section, TryItCard } from "@/components/learn/content";

export const metadata: Metadata = { title: "Rotor dynamics" };

export default function RotorDynamicsPage() {
  return (
    <DocPage slug="rotor-dynamics">
      <Section id="why" title="The question rotor dynamics answers">
        <p>
          A microturbine shaft spins at 70,000+ rpm. Somewhere in its speed
          range sit <em>critical speeds</em> — shaft bending resonances where
          tiny residual unbalance gets amplified into large vibration. Rotor
          dynamics answers the questions that decide whether your machine
          survives its first run-up: where are the criticals, how violently
          does the rotor respond crossing them, and is the operating speed
          far enough away?
        </p>
        <p>
          Cascade models the rotor as a <strong>Timoshenko beam
          finite-element model with gyroscopic coupling</strong> — shear
          deformation included (it matters for short, stubby turbomachine
          shafts), and the speed-dependent gyroscopic stiffening that splits
          modes into forward and backward whirl. Both <strong>lateral</strong>{" "}
          (bending) and <strong>torsional</strong> (twisting) analyses ship.
        </p>
      </Section>

      <Section id="model" title="Describing the rotor">
        <p>
          A rotor is a stack of cylindrical sections plus lumped disks
          (impellers, generator magnets) at axial stations, supported on
          bearings:
        </p>
        <CodeBlock
          lang="python"
          title="rotor_model.py"
          code={`from cascade.rotor import build_rotor_model, LinearBearing, run_lateral_analysis
from cascade.units import Q, RotorShape, RotorSection, LumpedDisk

shape = RotorShape(
    sections=[
        RotorSection(
            diameter_outer=Q(20, "mm"),
            diameter_inner=Q(0, "mm"),       # solid shaft
            length=Q(400, "mm"),
            density=Q(7800, "kg/m^3"),
            axial_position=Q(0, "mm"),
            material="STEEL_AISI4340",
        ),
    ],
    disks=[
        LumpedDisk(                          # e.g. the impeller
            mass=Q(2.5, "kg"),
            inertia_polar=Q(2.5e-3, "kg*m^2"),
            inertia_diametrical=Q(1.25e-3, "kg*m^2"),
            axial_position=Q(200, "mm"),
        ),
    ],
)

bearings = [
    LinearBearing(
        name="bearing_1", axial_position=Q(0, "m"),
        stiffness_y=Q(1e6, "N/m"), stiffness_z=Q(1e6, "N/m"),
        damping_y=Q(100, "N*s/m"), damping_z=Q(100, "N*s/m"),
    ),
    LinearBearing(
        name="bearing_2", axial_position=Q(0.4, "m"),
        stiffness_y=Q(1e6, "N/m"), stiffness_z=Q(1e6, "N/m"),
        damping_y=Q(100, "N*s/m"), damping_z=Q(100, "N*s/m"),
    ),
]

model = build_rotor_model(shape, bearings)
modes = run_lateral_analysis(model, rpm=50_000, n_modes=6)
for m in modes:
    print(f"f = {m.damped_freq_hz:8.2f} Hz   ζ = {m.damping_ratio:.4f}")`}
        />
        <p>
          In the web app, the Rotor page gives you the same model as a visual
          sketch — sections, disks, and bearing markers on the actual shaft —
          with the analyses one click away.
        </p>
      </Section>

      <Section id="bearings" title="Bearings">
        <ParamTable title="Bearing models">
          <ParamRow name="LinearBearing" type="direct coefficients">
            You supply stiffness and damping per direction. The fastest way
            to model a known support, or a vendor-quoted coefficient set.
          </ParamRow>
          <ParamRow name="PlainJournalBearing" type="solved from geometry">
            A native plain-journal solver: finite-bearing Reynolds equation
            via Christopherson 1941 PSOR, the Ocvirk 1952 short-bearing
            closed form, and the full 2×2 stiffness/damping matrices per Lund
            &amp; Thomsen 1978. Give it diameter, width, clearance, and oil
            viscosity; it gives you the coefficients.
          </ParamRow>
          <ParamRow name="TabulatedBearing" type="your data">
            Tilt-pad, thrust, and foil bearings don’t have native solvers yet
            (<code className="font-mono text-[13px]">KG-007/008/009</code>) —
            they accept tabulated speed-dependent coefficients from vendor
            data or test. Foil-bearing presets ship at{" "}
            <code className="font-mono text-[13px]">GET /api/bearings/presets</code>.
          </ParamRow>
        </ParamTable>
        <Callout kind="warning" title="The 10¹⁰ N/m guard">
          Bearing stiffness above 10¹⁰ N/m is refused with{" "}
          <code className="font-mono text-[13px]">IMPLAUSIBLE_BEARING_STIFFNESS</code>.
          This guard exists because of a real bug observed in legacy tools: a
          unit-display error that fed K<sub>zz</sub> = 3.8×10¹⁴ N/m into an
          analysis, which then happily reported nonsense criticals. Cascade
          assumes a number that stiff is a units mistake, because it always
          has been.
        </Callout>
      </Section>

      <Section id="analyses" title="The five analyses">
        <ParamTable>
          <ParamRow name="run_lateral_analysis" type="(model, rpm, n_modes)">
            Damped complex modes at one speed: frequencies, damping ratios,
            and mode shapes in both lateral planes.
          </ParamRow>
          <ParamRow name="run_critical_speed_map" type="(rotor, rpm_range, bearing_speed_fractions)">
            Critical speeds versus bearing stiffness — the classic map for
            choosing how stiff your supports should be. Sweeps bearing
            stiffness multipliers (e.g. 0.5×, 1×, 2×).
          </ParamRow>
          <ParamRow name="run_unbalance_response" type="(rotor, unbalance_magnitude, rpm_range)">
            Forced response to a specified unbalance (e.g.{" "}
            <code className="font-mono text-[13px]">{`Q(10, "g*mm")`}</code>):
            Bode plot of amplitude and phase through the speed range,
            amplification factor at each critical, and the separation margin
            between criticals and operating speed — the quantities an API 684
            review asks for.
          </ParamRow>
          <ParamRow name="run_campbell" type="(rotor, rpm_range, n_rpm_points)">
            Natural frequencies versus speed with the synchronous (1×)
            excitation line — where it crosses a forward-whirl branch, that’s
            a critical.
          </ParamRow>
          <ParamRow name="run_stability / run_torsional_analysis" type="(rotor, rpm_range) / (model, rpm)">
            Log-decrement screening per mode across the speed range
            (negative log-dec means self-excited vibration), and the
            torsional natural frequencies for drivetrain integration.
          </ParamRow>
        </ParamTable>
        <CodeTabs
          tabs={[
            {
              label: "Python",
              lang: "python",
              code: `from cascade.rotor import (
    run_critical_speed_map, run_unbalance_response, run_campbell, run_stability,
)

cs_map = run_critical_speed_map(
    rotor=model, rpm_range=(1_000, 100_000),
    bearing_speed_fractions=[0.5, 1.0, 2.0],
)
response = run_unbalance_response(
    rotor=model,
    unbalance_magnitude=Q(10, "g*mm"),
    rpm_range=(1_000, 80_000), n_points=100,
)
print(response.amplification_factor, response.separation_margin)

campbell  = run_campbell(rotor=model, rpm_range=(1_000, 100_000), n_rpm_points=50)
stability = run_stability(rotor=model, rpm_range=(1_000, 100_000), n_rpm_points=50)`,
            },
            {
              label: "HTTP",
              lang: "http",
              code: `POST /api/projects/{project_id}/rotor
# body: sections, disks, bearings, analyses → {"job_id": "..."}

GET  /api/projects/{project_id}/rotor/report.pdf
# API 684-style PDF report of the latest analysis`,
            },
          ]}
        />
        <TryItCard
          href="/projects/microturbine-30kw/rotor"
          title="Run the rotor analyses"
          body="Sketch the shaft, run the critical-speed map, and check the separation margin."
        />
      </Section>

      <Section id="validation" title="How good is it?">
        <p>
          The beam-FEM reproduces the NASA TM-102368 rotor-bearing rig’s
          first forward critical within 0.3% against a ±5% gate (case RD-3,
          using a calibrated proxy shaft with the real NASA bearing
          coefficients —{" "}
          <code className="font-mono text-[13px]">KG-RD-01</code>), and
          matches Friswell 2010 closed-form beam modes within ±1% (RD-4).
          RD-4 and the Jeffcott case verify the discretization and
          eigensolver — not real-machine fidelity; the{" "}
          <Link href="/docs/validation" className="font-medium text-brand-text hover:underline">
            validation report
          </Link>{" "}
          spells out which claim is which.
        </p>
        <Callout kind="note" title="Scope boundary">
          The rotor model is linear: linearized bearing coefficients, no
          nonlinear transient orbits. That covers the API 684 preliminary
          screening workflow; full nonlinear response is out of v1 scope by
          design.
        </Callout>
      </Section>
    </DocPage>
  );
}
