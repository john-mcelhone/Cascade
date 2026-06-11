import type { Metadata } from "next";
import Link from "next/link";
import { CodeTabs, DocPage, ParamRow, ParamTable } from "@/components/docs";
import { Callout, Section, TryItCard } from "@/components/learn/content";

export const metadata: Metadata = { title: "Cycle design" };

export default function CyclePage() {
  return (
    <DocPage slug="cycle">
      <Section id="what" title="What the cycle solver does">
        <p>
          The cycle solver answers the first question of any engine project:{" "}
          <em>
            if I compress this much, burn to this temperature, and expand
            through this turbine, what do I get?
          </em>{" "}
          It’s a 0D thermodynamic balance — no geometry yet, just states and
          energy — solved with a real-gas equation of state (NASA
          9-coefficient polynomials, plus CoolProp for pure fluids like
          supercritical CO₂).
        </p>
        <p>Three cycle architectures ship in v0.1.0:</p>
        <ul className="ml-5 list-disc space-y-2">
          <li>
            <strong>Simple Brayton</strong> — inlet → compressor → burner →
            turbine → exhaust.
          </li>
          <li>
            <strong>Recuperated Brayton</strong> — adds a recuperator that
            preheats compressor-exit air with turbine exhaust, the standard
            microturbine layout.
          </li>
          <li>
            <strong>Multi-shaft Brayton</strong> — several compressors and
            turbines on separate shafts, matched by per-shaft power balance.
            (Map-based multi-spool matching is deferred —{" "}
            <code className="font-mono text-[13px]">KG-003</code>.)
          </li>
        </ul>
      </Section>

      <Section id="canvas" title="Working on the canvas">
        <p>
          In the web app, a cycle is a graph: drag components from the
          palette, wire outlets to inlets, and edit parameters in the
          properties panel. Inputs follow a color convention — yellow fields
          are yours to set, computed values render on a neutral surface. Every
          quantity input understands units: type{" "}
          <code className="font-mono text-[13px]">14.7 psi</code> into a
          pressure field and it lands as the exact pascal equivalent.
        </p>
        <ParamTable title="Component catalog">
          <ParamRow name="Inlet / Outlet" type="boundary">
            Set total pressure, total temperature, mass flow, and gas
            composition. Editing the Inlet mirrors onto the project’s
            boundary conditions.
          </ParamRow>
          <ParamRow name="Compressor" type="turbomachine">
            <code className="font-mono text-[13px]">pressure_ratio</code> and{" "}
            <code className="font-mono text-[13px]">efficiency_isentropic</code>,
            plus an efficiency mode: a constant you assert, or{" "}
            <em>live mean-line</em> computed from attached geometry.
          </ParamRow>
          <ParamRow name="Turbine" type="turbomachine">
            Same shape as the compressor: pressure ratio, isentropic
            efficiency, optional live mean-line mode.
          </ParamRow>
          <ParamRow name="Burner" type="heat addition">
            Pinned by <em>outlet temperature</em> (set TIT, solver finds fuel
            flow) or by <em>fuel mass flow</em> (set fuel, solver finds TIT).
            Models combustion with a real fuel: LHV, C/H atom counts, molar
            mass, combustion efficiency, and pressure drop. An{" "}
            <code className="font-mono text-[13px]">air_standard</code> flag
            skips composition change for textbook comparisons.
          </ParamRow>
          <ParamRow name="Recuperator" type="heat exchanger">
            Effectiveness ε plus cold- and hot-side pressure-drop fractions.
            ε above 0.98 is refused as physically implausible.
          </ParamRow>
          <ParamRow name="Intercooler / Mixer / Splitter / ConstantPressureLoss / Shaft" type="plumbing">
            Intercooling between compression stages, flow merging and
            splitting, duct losses, and shaft membership for multi-shaft
            machines.
          </ParamRow>
        </ParamTable>
        <TryItCard
          href="/projects/microturbine-30kw/cycle"
          title="Open the seeded recuperated Brayton"
          body="A real machine — the Capstone C30 layout — ready to run and modify."
        />
      </Section>

      <Section id="attribution" title="Result attribution: where every number came from">
        <p>
          When a run finishes, the result panel doesn’t just report η_thermal
          — it reports <em>provenance</em>. For each turbomachine, the panel
          states whether its efficiency was an assumed constant or solved live
          from mean-line geometry, and which geometry. This matters because
          the difference between “I assumed 80%” and “the mean-line says
          78.3%” is exactly the credibility gap that burns preliminary
          designs.
        </p>
        <p>
          To go live: send a candidate from{" "}
          <Link href="/docs/exploration" className="font-medium text-brand-text hover:underline">
            design exploration
          </Link>{" "}
          to the cycle, then flip the compressor’s efficiency mode to{" "}
          <em>Live mean-line</em>. The next solve runs the actual mean-line
          inside the cycle iteration.
        </p>
      </Section>

      <Section id="scripting" title="Scripting a cycle solve">
        <CodeTabs
          tabs={[
            {
              label: "Python",
              lang: "python",
              code: `from cascade.cycle import (
    solve_simple_brayton, SimpleBraytonSpec,
    Compressor, Burner, Turbine, NasaFluid,
)
from cascade.units import Port, Q, Composition

inlet = Port(
    pressure_total=Q(101.325, "kPa"),
    temperature_total=Q(288.15, "K"),
    mass_flow=Q(1.0, "kg/s"),
    composition=Composition.air(),
)
spec = SimpleBraytonSpec(
    inlet_port=inlet,
    compressor=Compressor(name="C", pressure_ratio=4.0,
                          efficiency_isentropic=0.80),
    burner=Burner(
        name="B",
        outlet_temperature=Q(1200, "K"),
        pressure_drop_fraction=0.04,
        combustion_efficiency=0.995,
        fuel_lhv=Q(50e6, "J/kg"),       # methane
        fuel_carbon_atoms=1,
        fuel_hydrogen_atoms=4,
        fuel_molar_mass=Q(16.0425, "g/mol"),
    ),
    turbine=Turbine(name="T", pressure_ratio=3.0,
                    efficiency_isentropic=0.85),
)

result = solve_simple_brayton(spec, NasaFluid())
print(f"η_th  = {result.thermal_efficiency * 100:.2f}%")
print(f"net   = {result.net_shaft_work.to('kW')}")
print(f"fuel  = {result.fuel_mass_flow.to('g/s')}")
print(f"converged in {result.outer_iterations} outer iterations")`,
            },
            {
              label: "HTTP",
              lang: "http",
              code: `POST /api/projects/microturbine-30kw/cycle/solve
# → 200 {"job_id": "..."}  — the solve runs as a job

GET  /api/jobs/{job_id}            # poll status + result
GET  /api/jobs/{job_id}/events     # or stream progress over SSE`,
            },
          ]}
        />
        <p>
          The <code className="font-mono text-[13px]">CycleResult</code>{" "}
          carries the full picture, not just a headline:
        </p>
        <ParamTable title="CycleResult">
          <ParamRow name="ports" type="Dict[str, Port]">
            The outlet thermodynamic state of every component, by name —
            total pressure, total temperature, mass flow, composition.
          </ParamRow>
          <ParamRow name="thermal_efficiency / electrical_efficiency" type="float">
            Net shaft work over heat input; and after mechanical + generator
            losses.
          </ParamRow>
          <ParamRow name="net_shaft_work / electrical_output / specific_work" type="Quantity">
            Power numbers as typed quantities, convertible to any compatible
            unit.
          </ParamRow>
          <ParamRow name="fuel_mass_flow / heat_input" type="Quantity">
            What the burner consumed to hit the pinned condition.
          </ParamRow>
          <ParamRow name="converged / outer_iterations / residual_norm" type="bool / int / float">
            The convergence record. A non-converged result says so — it never
            masquerades as an answer.
          </ParamRow>
          <ParamRow name="component_efficiencies" type="Dict[str, float]">
            The efficiency each component actually used in the final solve —
            the data behind the attribution panel.
          </ParamRow>
        </ParamTable>
      </Section>

      <Section id="refusals" title="What the solver refuses">
        <p>
          The cycle solver enforces its validity region instead of
          extrapolating quietly:
        </p>
        <ul className="ml-5 list-disc space-y-2">
          <li>
            <strong>Combustor exit above 2100 K</strong> — refused. That’s the
            uncooled material limit, and cooled-row modeling isn’t shipped (
            <code className="font-mono text-[13px]">KG-004</code>).
          </li>
          <li>
            <strong>Pressure ratio above 60</strong> on any single component —
            refused as outside the validity regime.
          </li>
          <li>
            <strong>Recuperator effectiveness above 0.98</strong> — refused as
            physically implausible.
          </li>
          <li>
            <strong>Incomplete topology</strong> — a cycle missing a
            component never returns a silent zero-efficiency “success”; the
            job fails with a plain-English explanation and a structured
            failure envelope.
          </li>
        </ul>
        <Callout kind="note">
          Refusals arrive as structured data, not stack traces — see{" "}
          <Link href="/docs/errors" className="font-medium text-brand-text hover:underline">
            Failures &amp; status codes
          </Link>{" "}
          for the envelope format and how to handle it.
        </Callout>
      </Section>

      <Section id="validation" title="How good is it?">
        <p>
          Validated in public: the simple Brayton reproduces Çengel &amp;
          Boles Example 9-5 to 0.01 percentage points (case CYC-1), and the
          recuperated cycle hits the published Capstone C30 electrical
          efficiency within 0.09 points against a ±1.5 point gate (CYC-3).
          The receipts are in the{" "}
          <Link href="/docs/validation" className="font-medium text-brand-text hover:underline">
            validation report
          </Link>
          .
        </p>
      </Section>
    </DocPage>
  );
}
