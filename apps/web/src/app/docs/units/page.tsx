import type { Metadata } from "next";
import Link from "next/link";
import { CodeBlock, DocPage, ParamRow, ParamTable } from "@/components/docs";
import { Callout, Section } from "@/components/learn/content";

export const metadata: Metadata = { title: "Units & quantities" };

export default function UnitsPage() {
  return (
    <DocPage slug="units">
      <Section id="rule" title="The rule: numbers carry units, or they don't enter">
        <p>
          Every physical value in Cascade — in Python, in the API, in the
          TOML files, in the UI — is a typed quantity: a magnitude{" "}
          <em>and</em> a unit, backed by{" "}
          <a
            href="https://pint.readthedocs.io"
            target="_blank"
            rel="noreferrer"
            className="font-medium text-brand-text hover:underline"
          >
            pint
          </a>
          . When dimensions don’t match, Cascade refuses at the boundary —
          it never coerces, never assumes, never multiplies by a hopeful
          constant.
        </p>
        <CodeBlock
          lang="python"
          title="quantities.py"
          code={`from cascade import Q

p = Q(14.7, "psi")
print(p.to("kPa"))          # 101.35253... kilopascal
print(p.to("Pa").magnitude) # 101352.93...

# Arithmetic keeps dimensions honest:
mdot = Q(0.31, "kg/s")
w    = Q(120, "kJ/kg")
print((mdot * w).to("kW"))  # 37.2 kilowatt`}
        />
        <p>
          The round trip is exact: the NIST SP 811 psi ↔ Pa conversion
          round-trips to 1 part in 10¹² (validation case UNIT-1). That’s not
          a marketing line — it’s a pass-gate in the test suite.
        </p>
      </Section>

      <Section id="refusal" title="What refusal looks like">
        <p>
          The <code className="font-mono text-[13px]">Port</code> type — the
          thermodynamic state at every component boundary — validates its
          fields on construction:
        </p>
        <CodeBlock
          lang="python"
          title="refusals.py"
          code={`from cascade import Q, Port, Composition

# Wrong dimension: temperature given in metres → TypeError
Port(
    pressure_total=Q(101.325, "kPa"),
    temperature_total=Q(288.15, "m"),     # ✗ refused
    mass_flow=Q(0.31, "kg/s"),
    composition=Composition.air(),
)

# Bare float instead of a Quantity → TypeError
Port(pressure_total=101325.0, ...)        # ✗ refused

# Non-physical magnitude → ValueError
Port(pressure_total=Q(float("nan"), "Pa"), ...)   # ✗ refused
Port(temperature_total=Q(-40, "K"), ...)          # ✗ refused`}
        />
        <Callout kind="warning" title="Why so strict?">
          Unit errors are the classic silent killer of engineering software —
          they don’t crash, they just produce confidently wrong answers. The
          rotor module’s 10¹⁰ N/m bearing-stiffness guard exists because a
          real unit-display bug in a legacy tool fed K<sub>zz</sub> =
          3.8×10¹⁴ N/m into an analysis. Strictness at the boundary is
          cheaper than archaeology after the design review.
        </Callout>
      </Section>

      <Section id="surfaces" title="Units across every surface">
        <ParamTable>
          <ParamRow name="Python" type="pint Quantity">
            <code className="font-mono text-[13px]">{`Q(value, "unit")`}</code>;
            convert with{" "}
            <code className="font-mono text-[13px]">{`.to("other_unit")`}</code>;
            SI canonical storage internally. One global registry (
            <code className="font-mono text-[13px]">cascade.units.ureg</code>)
            so quantities from different modules always compare.
          </ParamRow>
          <ParamRow name="TOML project files" type='{ value, unit }'>
            <code className="font-mono text-[13px]">
              pressure_total = {`{ value = 101.325, unit = "kPa" }`}
            </code>{" "}
            — self-describing on disk. Dimensionless ratios are plain floats.
            See{" "}
            <Link href="/docs/projects" className="font-medium text-brand-text hover:underline">
              Projects
            </Link>
            .
          </ParamRow>
          <ParamRow name="Web UI" type="unit-aware inputs">
            Quantity fields parse units as you type —{" "}
            <code className="font-mono text-[13px]">14.7 psi</code> into a
            pressure field stores the exact pascal equivalent and displays in
            your preferred unit. A value with the wrong dimension is rejected
            in the field, before it ever reaches a solver.
          </ParamRow>
          <ParamRow name="REST API" type="explicit units in payloads">
            Quantities travel as value + unit pairs, same as the TOML. The
            API never guesses what a bare number means.
          </ParamRow>
        </ParamTable>
      </Section>

      <Section id="conventions" title="Conventions worth knowing">
        <ul className="ml-5 list-disc space-y-2">
          <li>
            <strong>Total (stagnation) state by default.</strong> Ports carry{" "}
            <code className="font-mono text-[13px]">pressure_total</code> and{" "}
            <code className="font-mono text-[13px]">temperature_total</code>;
            static quantities are always named explicitly (e.g.{" "}
            <code className="font-mono text-[13px]">p_out_static</code> on
            the turbine solver).
          </li>
          <li>
            <strong>SI internally, anything compatible at the edges.</strong>{" "}
            Solvers compute in SI; you write and read whatever pint can
            convert — psi, bar, krpm, g/mm.
          </li>
          <li>
            <strong>Angles are radians in code</strong> — geometry fields
            like{" "}
            <code className="font-mono text-[13px]">beta_2_metal_rad</code>{" "}
            carry the unit in their name; the UI displays degrees.
          </li>
          <li>
            <strong>Mass flow is signed.</strong> Direction is part of the
            value, which keeps splitters and mixers honest.
          </li>
        </ul>
      </Section>
    </DocPage>
  );
}
