import {
  Chapter,
  Section,
  Lead,
  Callout,
  TryItCard,
  RealExample,
  Citation,
  Inline,
  Math,
  NextChapter,
} from "@/components/learn/content";
import { MapExplorer } from "@/components/learn/widgets";
import { CompressorMap } from "@/components/learn/svg/compressor-map";
import { getChapter, getChapterNeighbors } from "@/lib/learn/chapters";

const SLUG = "7-performance-maps";

export default function Chapter7() {
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
      <Lead>
        A compressor doesn&rsquo;t have one operating point. It has a
        banana-shaped neighborhood of them, bounded on the left by surge
        and on the right by choke. Knowing where you sit inside that
        banana is most of what off-design analysis is.
      </Lead>

      <figure className="-mx-2 my-2">
        <CompressorMap />
        <figcaption className="mt-2 px-2 text-xs text-text-muted">
          The classic centrifugal compressor map. Six speedlines (60% &rarr;
          105% of design corrected speed), surge line on the left,
          choke line on the right, two efficiency islands centred on the
          design point.
        </figcaption>
      </figure>

      <Section id="why-a-map" title="Why a map instead of a point">
        <p>
          Engines never run only at design. Aircraft engines climb,
          cruise, descend. Power-plant gas turbines load and unload with
          grid demand. Microturbines on a generator chase the load. A
          turbocharger sweeps the entire range of an engine&rsquo;s RPM
          band thirty times an hour.
        </p>
        <p>
          For each operating condition, the compressor sees a different
          back pressure and a different inlet condition. Its real
          behaviour is the locus of all those points &mdash; pressure
          ratio versus mass flow at every speed the rotor might turn.
          That locus is the <em>performance map</em>.
        </p>
      </Section>

      <Section id="corrected-quantities" title="Corrected mass flow, corrected speed">
        <p>
          On a hot day the compressor sees less-dense inlet air. At
          altitude, less pressure. The same physical machine&rsquo;s map
          shifts. To get one map that covers all inlet conditions, we use
          the dimensionless corrected quantities:
        </p>
        <Math>
          {`\\dot{m}_{\\text{corr}} = \\dot{m} \\cdot \\frac{\\sqrt{\\theta}}{\\delta}, \\qquad N_{\\text{corr}} = \\frac{N}{\\sqrt{\\theta}}`}
        </Math>
        <p>
          where <Inline>\theta = T_{`{t,in}`} / T_{`{ref}`}</Inline> and{" "}
          <Inline>\delta = p_{`{t,in}`} / p_{`{ref}`}</Inline> are inlet
          temperature and pressure normalized to standard reference
          conditions (288.15 K, 101.325 kPa for the air-breathing
          standard).
          <Citation
            source="Walsh & Fletcher 2004"
            page="Gas Turbine Performance, § 6.3"
          />
        </p>
        <p>
          With these, one map covers every ambient condition. A user reads
          the chart with corrected quantities; the solver converts back to
          physical quantities for the cycle.
        </p>
      </Section>

      <Section id="surge" title="Surge: the left boundary">
        <p>
          Push the back pressure higher than the compressor can sustain
          at a given speed and the flow can no longer climb the pressure
          gradient. The boundary layer separates. Flow reverses,
          momentarily, through the impeller. The compressor unloads,
          recovers, hits the boundary again. The cycle repeats at a few
          to a few dozen hertz and the whole machine shakes.
          <Citation
            source="Greitzer 1976"
            page="J Eng Power 98(2)"
            body="The canonical theoretical treatment of compression-system surge dynamics. The Greitzer B-parameter predicts whether a given system is prone to mild surge or violent deep-surge cycles."
          />
        </p>
        <p>
          On the map, the surge boundary is the locus where the
          speedline&rsquo;s slope{" "}
          <Inline>{`\\partial \\pi / \\partial \\dot{m}`}</Inline>{" "}
          reaches zero or goes positive. Operating to the left of that
          line is forbidden. Cascade detects it on every speedline by
          fitting a cubic spline and flagging the apex.
        </p>
        <Callout kind="warning" title="Anti-surge protection">
          On industrial machines &mdash; centrifugal natural-gas
          compressors, refinery process compressors &mdash; the surge
          line is guarded by an <em>anti-surge valve</em> that recycles
          discharge gas back to inlet whenever the operating point gets
          within ~10% of the line. The valve is open in startup,
          shutdown, and any time the demand drops faster than the rotor
          can spool down. The cost: efficiency loss when recirculating.
          The benefit: the compressor doesn&rsquo;t destroy itself.
        </Callout>
      </Section>

      <Section id="choke" title="Choke: the right boundary">
        <p>
          At the other extreme, push the back pressure low (open the
          throttle) and mass flow climbs &mdash; until something in the
          flow path hits Mach 1. The throat saturates. No matter how
          much further you open the valve, mass flow stops increasing:
        </p>
        <Math>
          {`\\dot{m}_{\\text{choke}} = \\rho^* \\cdot a^* \\cdot A^*`}
        </Math>
        <p>
          where the asterisk denotes sonic conditions at the throat. The
          speedline turns vertical on the map &mdash; same{" "}
          <Inline>{`\\dot{m}`}</Inline>, any <Inline>{`\\pi`}</Inline> below the
          choke-line value gives no extra flow.
          <Citation source="Cumpsty 2004" page="Compressor Aerodynamics, § 9.5" />
        </p>
        <p>
          Choke is less violent than surge &mdash; the machine isn&rsquo;t
          destroying itself, it just isn&rsquo;t doing more work. But for
          an engine designer, hitting choke means the compressor
          can&rsquo;t deliver more air to the combustor, and the cycle
          output saturates.
        </p>
      </Section>

      <MapExplorer />

      <Section id="convergence-codes" title="The eight Cascade convergence codes">
        <p>
          When you run a map, most points converge. Some don&rsquo;t.
          Cascade reports{" "}
          <em>why</em> a point failed using a discrete code, never the
          ambiguous &ldquo;-1&rdquo; that some legacy tools return.
        </p>
        <ul className="grid grid-cols-1 gap-2 rounded-md border border-border-subtle bg-surface-subtle/40 p-4 text-sm sm:grid-cols-2">
          {CODES.map((c) => (
            <li key={c.code} className="flex flex-col gap-0.5">
              <span className="font-mono text-xs text-text">{c.code}</span>
              <span className="text-text-muted">{c.meaning}</span>
            </li>
          ))}
        </ul>
        <Callout kind="note" title="Why eight codes, not one">
          A blanket &ldquo;-1&rdquo; tells you the solver gave up. It
          doesn&rsquo;t tell you whether you ran past surge, past choke,
          past validity, into invalid geometry, or just hit the wall
          clock. Each of those has a different remedy: tighten the
          speedline range, switch on the shock loss model, fix the
          geometry, or extend the timeout. The eight-code legend is a
          differentiator Cascade keeps over its predecessor.
          <Citation
            source="SPEC_SHEET.md"
            page="§ 13 (refusal behavior)"
            body="Legacy tools return code = -1 ambiguously across all map-grid failures. Cascade's eight explicit codes resolve that ambiguity."
          />
        </Callout>
      </Section>

      <Section id="reading-a-real-map" title="Reading a real map">
        <RealExample
          title="GE LM2500 industrial gas turbine"
          source="GE Power Systems datasheet GER-3695E"
        >
          The LM2500 is a derivative of the TF39 high-bypass turbofan
          (which powered the C-5 Galaxy). Its compressor map, published
          in the GE GER-3695E datasheet, shows a 17-stage axial
          compressor running 18:1 overall pressure ratio at 3,600 rpm
          shaft speed. The map runs from 60% to 105% corrected speed.
          The design point sits at the centre of the upper-η-island
          (~85% polytropic) with about 18% margin to surge at design
          speed and 12% margin to choke. The cruise operating envelope
          is the rectangle on the map that doesn&rsquo;t intersect any
          forbidden region.
        </RealExample>
      </Section>

      <Section id="surge-margin" title="Surge margin">
        <p>
          The surge margin is the design-point&rsquo;s distance from the
          surge line, expressed as a percentage of pressure ratio:
        </p>
        <Math>
          {`SM = \\frac{\\pi_{\\text{surge}} - \\pi_{\\text{design}}}{\\pi_{\\text{design}}} \\times 100\\%`}
        </Math>
        <p>
          Industry practice (per API 617, § 2.6.1.2 and GE&rsquo;s
          internal design manuals) is to target SM ≥ 20% for an
          industrial machine and SM ≥ 25% for an aero engine where
          inlet distortion eats margin. Below 15% the operating point is
          considered &ldquo;hot&rdquo; and additional controls are
          required.
        </p>
        <Callout kind="example" title="A concrete number">
          For our Capstone-C30-scale microturbine compressor running
          PR = 4.0 at design, a 20% margin means surge must not occur
          above PR ≈ 4.8 at the design corrected speed. Cascade flags any
          design that fails this gate in the candidate table with a
          margin-violated badge before the user ever opens the map.
        </Callout>
      </Section>

      <TryItCard
        href="/projects/microturbine-30kw/map"
        title="Generate a real performance map."
        body="Open the Map page on the Microturbine 30 kW project. Set the speed range and grid density; Cascade will run the speedlines in parallel and draw the surge and choke lines on top."
      />

      <NextChapter
        prevHref={prev ? `/learn/${prev.slug}` : undefined}
        prevTitle={prev?.title}
        nextHref={next ? `/learn/${next.slug}` : undefined}
        nextTitle={next?.title}
      />
    </Chapter>
  );
}

const CODES = [
  { code: "CONVERGED", meaning: "Solver reached its tolerance. Use the result." },
  {
    code: "CHOKED",
    meaning: "Mach = 1 at the throat. Mass flow saturated; no more can pass.",
  },
  {
    code: "STALL_SURGE",
    meaning: "Speedline turned over. Operating point is past surge.",
  },
  {
    code: "NON_CONVERGED",
    meaning: "Inner Newton ran out of iterations without meeting tolerance.",
  },
  {
    code: "INVALID_GEOMETRY",
    meaning: "Geometry violates a hard rule (e.g. hub > shroud, negative area).",
  },
  {
    code: "REGIME_OUT_OF_VALIDITY",
    meaning:
      "Input is outside the loss-model's validated regime (e.g. M_rel > 2.5).",
  },
  {
    code: "TIMEOUT",
    meaning: "Solver exceeded the wall-clock limit per point.",
  },
  {
    code: "INFEASIBLE_BC",
    meaning:
      "The boundary condition itself is unphysical (e.g. cold-side T_in > hot-side T_in).",
  },
];
