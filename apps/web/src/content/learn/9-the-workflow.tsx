import {
  Chapter,
  Section,
  Lead,
  Callout,
  TryItCard,
  Citation,
  Inline,
  NextChapter,
} from "@/components/learn/content";
import { WorkflowDiagram } from "@/components/learn/svg/workflow-diagram";
import { getChapter, getChapterNeighbors } from "@/lib/learn/chapters";

const SLUG = "9-the-workflow";

export default function Chapter9() {
  const meta = getChapter(SLUG)!;
  const { prev, next } = getChapterNeighbors(SLUG);

  return (
    <Chapter
      slug={meta.slug}
      number={meta.number}
      title={meta.title}
      subtitle={meta.subtitle}
      difficulty={meta.difficulty}
      readMinutes={meta.readMinutes}
    >
      <Callout kind="warning" title="Preview-only">
        <p>
          Some steps in this workflow use placeholder outputs in v1.0.
        </p>
        <p className="mt-2">
          The Analysis page (velocity triangles, η<sub>ts</sub>) and the
          Rotor Dynamics page (mode shapes, Campbell diagram,
          critical-speed map) currently render placeholder data. Real
          solver outputs will replace them in v1.0.1 — tracked as ADAPT-020
          through ADAPT-025.
        </p>
        <p className="mt-2">
          The Flow Path PD page (centrifugal compressor + radial turbine
          + design scatter), the Cycle Canvas, and the Performance Map
          are fully live.
        </p>
      </Callout>

      <Lead>
        You are an engineer at a six-person microturbine startup with
        $30M in seed funding. You have eighteen months to demonstrate a
        30 kW recuperated machine that hits 26% electrical efficiency.
        You have no historical database. Here&rsquo;s how you&rsquo;d
        use Cascade to get there.
      </Lead>

      <figure className="-mx-2 my-2">
        <WorkflowDiagram />
        <figcaption className="mt-2 px-2 text-xs text-text-muted">
          The five stages, in order, with the artifact handed off
          between each pair. In legacy tools the same five stages
          live in five separate desktop applications connected by
          manual file save/load.
        </figcaption>
      </figure>

      <Section id="step-1-cycle" title="Step 1 — Sketch the cycle">
        <p>
          You start in the Cycle Canvas. Drag a compressor, a
          recuperator, a combustor, a turbine, and a generator onto the
          canvas. Connect them. Cascade applies the obvious
          recuperated-Brayton topology and snaps the connections.
        </p>
        <p>
          You set the design boundary conditions: ambient air at 288.15 K
          and 101.325 kPa, design mass flow 0.31 kg/s, combustor exit
          temperature 1,150 K, compressor pressure ratio 4.0, recuperator
          effectiveness 0.88. You hit Run.
        </p>
        <p>
          Cascade solves the cycle in 18 ms (real number: see the
          performance targets in SPEC_SHEET §14). The result: thermal
          efficiency η<sub>e</sub> = 26.1%, specific work 96.4 kJ/kg,
          shaft power 29.9 kW. It matches the Capstone C30
          datasheet&rsquo;s published 26% to within 0.1 percentage point.
          <Citation
            source="VALIDATION_REPORT.md"
            page="CYC-3"
            body="CYC-3 is the pass-gate test for the C30 microturbine cycle; the live result is 26.09% vs published 26%, within the ±1.5 pt tolerance."
          />
        </p>
        <Callout kind="example" title="Time spent">
          About four minutes of canvas work, then a sub-second solver
          run. Faster than it took you to read this paragraph, probably.
        </Callout>
        <TryItCard
          href="/projects/microturbine-30kw/cycle"
          title="Sketch a recuperated Brayton cycle."
          body="The Cycle page lets you build one in about four minutes from a fresh template."
        />
      </Section>

      <Section id="step-2-flow-path" title="Step 2 — Pick boundary conditions, explore">
        <p>
          You move to the Flow Path PD page. Cascade carries the cycle&rsquo;s
          design-point boundary conditions over automatically: total
          pressure, total temperature, and mass flow at compressor
          inlet and outlet are pre-filled.
        </p>
        <p>
          You set parameter ranges on the seven free design variables:
          RPM (60-100 krpm), rotor outlet radius (20-35 mm), inlet-to-outlet
          radius ratio (1.6-2.8), hub-to-shroud ratio at outlet (0.32-0.50),
          blade count (8-19), inlet blade angle (40-55°), and outlet blade
          angle (-30 to -15° back-sweep). You set constraints: maximum
          relative Mach less than 1.1 (so the subsonic mean-line is
          valid), tip speed less than 480 m/s (Inconel 718 material
          limit), outlet hub radius greater than 4 mm
          (manufacturability).
        </p>
        <p>
          You hit Run with <Inline>n = 2{`{,}`}000</Inline> Sobol&rsquo;
          samples. Nine seconds later (eight worker threads on your
          laptop), you have 1,997 candidates evaluated. 612 pass every
          constraint; the rest are flagged as infeasible with their
          violated constraint listed in a hover label. The Pareto front
          on (η<sub>tt</sub>, weight) is drawn automatically.
        </p>
        <p>
          You filter by η<sub>tt</sub> &gt; 0.86 and tip speed &lt;
          440 m/s. Twelve candidates survive. You scroll through them in
          the table; the geometry preview rotates as you click each row.
          You pick candidate #1,847.
        </p>
        <TryItCard
          href="/projects/microturbine-30kw/flowpath"
          title="Run the same exploration."
          body="The Flow Path PD page exposes every parameter you just configured. Cascade's defaults match this chapter exactly."
        />
      </Section>

      <Section id="step-3-analysis" title="Step 3 — Drop into Analysis">
        <p>
          The candidate you picked is now the design point for the
          Analysis page. You re-run the mean-line at design with the
          full loss breakdown surfaced. Cascade tells you where the
          missing efficiency goes:
        </p>
        <ul className="rounded-md border border-border-subtle bg-surface-subtle/40 p-4 text-sm">
          <li>incidence: 0.4 percentage points</li>
          <li>profile: 2.1 percentage points</li>
          <li>secondary: 1.6 percentage points</li>
          <li>tip clearance: 1.9 percentage points</li>
          <li>disc friction: 0.7 percentage points</li>
          <li>trailing edge: 0.4 percentage points</li>
          <li>shock: 0.2 percentage points</li>
        </ul>
        <p>
          Total loss: 7.3 points. η<sub>tt</sub> = 1.0 − 0.073 = 0.927;
          η<sub>ts</sub> after exit-kinetic-energy debit settles to 0.864.
        </p>
        <p>
          You happen to have rig data from a previous wheel of similar
          specific speed. The measured tip-clearance loss in that test
          was 15% higher than Cascade predicts. You open the loss-model
          card for tip clearance, adjust its scale factor from 1.00 to
          1.15, and re-run. New design-point η<sub>tt</sub>: 0.913. The
          scale-factor change is logged in the project file with the
          rationale (&ldquo;from test data, internal report #RT-2025-04&rdquo;).
          <Citation
            source="Cascade copy guide"
            body="Cascade's loss-model scale factors are exposed and the rationale is recorded in the project file. Legacy tools' loss-model selectors are opaque, with opaque proprietary loss-model names and no citation in the UI."
          />
        </p>
        <TryItCard
          href="/projects/microturbine-30kw/analysis"
          title="Inspect the loss breakdown."
          body="Open the Analysis page on the project; each loss bar opens a citation card with the source paper and scale factors."
        />
      </Section>

      <Section id="step-4-map" title="Step 4 — Generate the map">
        <p>
          You switch to the Map page. Cascade auto-generates a map grid:
          five corrected-speed lines (60% → 110%), eleven mass-flow
          points per speedline. The full 55-point grid takes about 45
          seconds on your laptop.
        </p>
        <p>
          The map draws with the surge line on the left, choke line on
          the right, η islands shaded, and the design point marked. You
          read off the surge margin at design speed: 22%. Just above the
          20% target.
        </p>
        <p>
          One point on the 70% speedline returned{" "}
          <code className="rounded-sm bg-surface-subtle px-1 font-mono">
            REGIME_OUT_OF_VALIDITY
          </code>
          : the meanline ran but the relative Mach at the rotor inlet
          climbed past 1.15, outside the subsonic correlation&rsquo;s
          validated regime. You flag it as a known limitation and move
          on; the design point is comfortably inside the validity
          envelope.
        </p>
        <Callout kind="note" title="The bright red point">
          The old tool would have flagged that one bad grid point with
          a blanket{" "}
          <code className="rounded-sm bg-surface-subtle px-1 font-mono">
            code = -1
          </code>
          . You wouldn&rsquo;t know whether it was a surge, a choke, a
          regime violation, or a numerical hiccup. Cascade tells you
          exactly which assumption the point violated, which is what
          you need to decide whether the failure is real or fixable.
        </Callout>
        <TryItCard
          href="/projects/microturbine-30kw/map"
          title="Sweep the same compressor map."
          body="The Map page runs the speedlines in parallel; you'll see the surge and choke boundaries drawn live."
        />
      </Section>

      <Section id="step-5-rotor" title="Step 5 — Rotor dynamics">
        <p>
          You move to the Rotor page. The shaft geometry has been
          inherited automatically from the mean-line output via the
          <code className="rounded-sm bg-surface-subtle px-1 font-mono">
            RotorShape
          </code>{" "}
          handoff (SPEC_SHEET §3.5). The two impellers (compressor on
          the cold end, turbine on the hot end) are lumped as disks at
          their centroids; the generator rotor is a third lumped disk
          near the cold end.
        </p>
        <p>
          You upload two K-C tables for the foil bearings &mdash; the
          bearing supplier sent them as CSV. Cascade validates the
          dimensions and refuses anything outside 10<sup>7</sup>-10<sup>10</sup> N/m.
          The tables pass; they discretize across 8 speeds from 20k to
          120k rpm.
        </p>
        <p>
          You run a critical-speed map. Cascade sweeps bearing stiffness
          across a logarithmic range and traces the first three lateral
          critical-speed loci. The design speed (60,000 rpm) sits at
          2.4&times; the first critical and 0.43&times; the second &mdash;
          plenty of API 684 separation margin on both sides.
        </p>
        <p>
          You run an unbalance response at API 617 grade G2.5 residual
          unbalance. The bode plot peaks at 9.2 krpm (first critical)
          at 27 µm peak-to-peak, well under the 53 µm API 617 limit for
          this size class.
        </p>
        <TryItCard
          href="/projects/microturbine-30kw/rotor"
          title="Confirm the critical-speed margins."
          body="The Rotor page renders the Campbell diagram, critical-speed map, and unbalance response. Each result has a green/amber/red badge against the API 684 criterion."
        />
      </Section>

      <Section id="step-6-export" title="Step 6 — STEP export, hand-off">
        <p>
          You export the wheel geometry as a STEP file (AP242). Cascade
          generates the full B-spline mean-line, hub/shroud curves, and
          blade surfaces with the configured thickness distribution.
          The STEP file is 1.4 MB.
        </p>
        <p className="text-sm text-text-muted">
          <strong>Dependency note:</strong> GLB and STL geometry exports
          are available in every Cascade install. STEP and IGES require
          the{" "}
          <code className="rounded-sm bg-surface-subtle px-1 font-mono">
            cascade[cad]
          </code>{" "}
          optional extra (
          <code className="rounded-sm bg-surface-subtle px-1 font-mono">
            pip install cascade[cad]
          </code>{" "}
          or{" "}
          <code className="rounded-sm bg-surface-subtle px-1 font-mono">
            conda install -c conda-forge pythonocc-core
          </code>
          ). The STEP/IGES buttons in the UI are greyed out with an
          install hint when the dependency is absent.
        </p>
        <p>
          You send it to your CFD contractor for a full-3D RANS
          confirmation run. They open it in StarCCM+ (or Fluent, or
          OpenFOAM &mdash; STEP is interchange-neutral) and report back
          in a week: their 3D η<sub>tt</sub> is 0.908, 0.5 percentage
          points below the mean-line prediction. You note the offset,
          tune the secondary-loss scale factor to match, and lock in
          the design.
        </p>
      </Section>

      <Section id="what-this-proves" title="What this proves">
        <p>
          You did the whole thing in an afternoon, in one browser tab,
          on a laptop. No file-format conversions. No re-entering
          boundary conditions across applications. No alt-tabbing
          between five different desktop programs.
        </p>
        <p>
          In legacy tools, the same workflow spans five
          separate desktop applications: one for the cycle, one for the
          flow path, a visual node-graph editor for analysis, one for the
          map, and a rotordynamics module for the rotor work. Each writes
          a proprietary binary file the others can&rsquo;t read directly.
          State synchronization between them is manual: you save in one,
          open in the next, re-enter or re-import the boundary conditions,
          and hope you didn&rsquo;t mistype a unit conversion.
        </p>
        <p>
          Cascade is one product, one tab, one project file. The
          boundary conditions flow between stages by typed{" "}
          <code className="rounded-sm bg-surface-subtle px-1 font-mono">
            Port
          </code>{" "}
          handoffs (SPEC_SHEET §3.1). The project file is text. Diff it
          in git. Co-edit it with a colleague. Roll back to last
          Tuesday&rsquo;s state in one click.
        </p>
      </Section>

      <NextChapter
        prevHref={prev ? `/learn/${prev.slug}` : undefined}
        prevTitle={prev?.title}
        nextHref={next ? `/learn/${next.slug}` : undefined}
        nextTitle={next?.title}
      />
    </Chapter>
  );
}
