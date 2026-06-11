import type { Metadata } from "next";
import Link from "next/link";
import { CodeBlock, DocPage } from "@/components/docs";
import { Callout, Section, TryItCard } from "@/components/learn/content";

export const metadata: Metadata = { title: "Quickstart" };

function Step({
  n,
  title,
  children,
}: {
  n: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-3">
      <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-brand/40 bg-brand-surface font-mono text-xs font-semibold text-brand-text">
        {n}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-2 pb-2">
        <h3 className="text-md font-medium leading-snug text-text">{title}</h3>
        <div className="flex flex-col gap-2 text-md leading-relaxed text-text">
          {children}
        </div>
      </div>
    </div>
  );
}

export default function QuickstartPage() {
  return (
    <DocPage
      slug="quickstart"
      lead="A guided pass through the whole workflow on the seeded Microturbine 30 kW project: solve the cycle, explore a design space, hand a candidate back to the cycle, generate a map, and check the rotor. About ten minutes."
    >
      <Section id="before" title="Before you start">
        <p>
          You need Cascade running locally (see{" "}
          <Link href="/docs/installation" className="font-medium text-brand-text hover:underline">
            Installation
          </Link>
          ):
        </p>
        <CodeBlock lang="bash" title="terminal" code={`make setup && make run`} />
        <p>
          Everything below happens in the browser against your local API — no
          desktop install, no license server. The{" "}
          <strong>Microturbine 30 kW</strong> project we’ll use is a
          recuperated Brayton cycle matched to the published Capstone C30
          spec: pressure ratio 4.0, turbine inlet around 811 K, recuperator
          effectiveness 0.86, targeting about 28 kW net electrical.
        </p>
      </Section>

      <Section id="cycle" title="Step 1 — Run the cycle">
        <Step n={1} title="Open the cycle canvas">
          <p>
            The canvas shows the machine as connected components: inlet →
            compressor → recuperator (cold side) → burner → turbine →
            recuperator (hot side) → exhaust. Click any component to see its
            parameters in the properties panel — every quantity carries its
            unit.
          </p>
        </Step>
        <Step n={2} title="Press Run cycle">
          <p>
            The 0D thermodynamic solver runs with a real-gas equation of state
            and reports per-component states in the result panel: pressures,
            temperatures, work, and the headline thermal and electrical
            efficiencies.
          </p>
          <Callout kind="note" title="Where did that number come from?">
            The result panel includes an <em>attribution</em>: for every
            efficiency in the solve, it says whether the number was an assumed
            constant or computed live from mean-line geometry. No silent
            assumptions.
          </Callout>
        </Step>
        <TryItCard
          href="/projects/microturbine-30kw/cycle"
          title="Open the Microturbine 30 kW cycle"
          body="Run it, then try raising the compressor pressure ratio and watch η_thermal respond."
        />
      </Section>

      <Section id="explore" title="Step 2 — Explore the design space">
        <Step n={3} title="Switch to Flow path and press Explore design space">
          <p>
            The boundary conditions are already staged from the cycle. Cascade
            draws Sobol&apos; samples over the impeller parameter space —
            deterministic by seed, so a colleague running the same exploration
            gets the same candidates — and solves the real mean-line for each
            one. Candidates stream into the scatter live.
          </p>
        </Step>
        <Step n={4} title="Filter with the DSL">
          <p>Type a filter above the scatter to narrow thousands of points:</p>
          <CodeBlock lang="filter" bare code={`eta_tt > 0.85 AND M_rel < 1.2`} />
          <p>
            Click any point: that impeller&apos;s geometry, manufacturability
            checks, and 3D view load in about two hundred milliseconds.
          </p>
          <Callout kind="warning" title="Greyed-out points are real solutions">
            Every candidate is gated through cited 5-axis manufacturability
            rules (cutter access, splitter passage, edge thickness, wrap
            angle). Designs a standard machining cell can&apos;t produce plot
            greyed-out at their <em>real solved performance</em>, with the
            violated rules named — they aren&apos;t hidden, because the honest
            picture includes what you can&apos;t build.
          </Callout>
        </Step>
        <TryItCard
          href="/projects/microturbine-30kw/flowpath"
          title="Explore the design space"
          body="Run an exploration, type the filter above, and click the best surviving point."
        />
      </Section>

      <Section id="handoff" title="Step 3 — Send a candidate to the cycle">
        <Step n={5} title="Pick a candidate and press Send to cycle">
          <p>
            The candidate&apos;s geometry lands on the cycle&apos;s compressor
            component. Back on the cycle canvas, flip that compressor from{" "}
            <em>constant efficiency</em> to <em>Live mean-line</em>: the next
            run solves with the geometry&apos;s actual mean-line efficiency
            instead of the assumed constant — and the attribution in the
            result panel shows exactly which numbers changed and why.
          </p>
        </Step>
        <p>
          This is the loop that matters: cycle assumptions → real geometry →
          cycle truth. The gap between the assumed and the live efficiency is
          the honest cost (or win) of your chosen impeller.
        </p>
      </Section>

      <Section id="map" title="Step 4 — Generate a performance map">
        <Step n={6} title="Open Map and run the generator">
          <p>
            Cascade sweeps a grid of speeds and mass flows, solving the
            mean-line at every point, then detects the surge and choke lines.
            Every point carries one of eight explicit status codes —{" "}
            <code className="font-mono text-[13px]">CONVERGED</code>,{" "}
            <code className="font-mono text-[13px]">CHOKED</code>,{" "}
            <code className="font-mono text-[13px]">STALL_SURGE</code>, and
            five more — never an ambiguous{" "}
            <code className="font-mono text-[13px]">-1</code>.
          </p>
          <Callout kind="note">
            The map currently computes from reference geometry — a sent
            candidate does not yet feed the map. That&apos;s gap{" "}
            <code className="font-mono text-[13px]">KG-PLAT-03</code> in the
            public gap registry, not an undocumented surprise.
          </Callout>
        </Step>
        <TryItCard
          href="/projects/microturbine-30kw/map"
          title="Generate the performance map"
          body="Watch points stream in with status codes, then inspect the surge and choke lines."
        />
      </Section>

      <Section id="rotor" title="Step 5 — Check the rotor">
        <Step n={7} title="Open Rotor and run the analyses">
          <p>
            Sketch the shaft as sections and lumped disks, place the bearings,
            and run: critical-speed map, Campbell diagram, unbalance response
            (Bode plot, amplification factor, separation margin), and
            stability — lateral <em>and</em> torsional, from a Timoshenko
            beam-FEM with gyroscopic coupling.
          </p>
        </Step>
        <TryItCard
          href="/projects/microturbine-30kw/rotor"
          title="Run the rotor analyses"
          body="Find the first critical speed and check the separation margin against the operating speed."
        />
      </Section>

      <Section id="next" title="Where to go next">
        <ul className="ml-5 list-disc space-y-2">
          <li>
            <Link href="/docs/projects" className="font-medium text-brand-text hover:underline">
              Projects
            </Link>{" "}
            — what just got written to disk, and how to put it in git.
          </li>
          <li>
            <Link href="/docs/python-api" className="font-medium text-brand-text hover:underline">
              Python scripting
            </Link>{" "}
            — everything you just clicked, scriptable.
          </li>
          <li>
            <Link href="/learn" className="font-medium text-brand-text hover:underline">
              Learn
            </Link>{" "}
            — the theory behind each step, from first principles.
          </li>
        </ul>
      </Section>
    </DocPage>
  );
}
