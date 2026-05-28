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
import { SpecificSpeedExplorer } from "@/components/learn/widgets";
import { TurboVsJet } from "@/components/learn/svg/turbo-vs-jet";
import { getChapter, getChapterNeighbors } from "@/lib/learn/chapters";

const SLUG = "4-radial-vs-axial";

export default function Chapter4() {
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
        Same job, very different shapes. A turbocharger compressor has one
        impeller about the size of your palm; a Boeing 787 engine has
        twelve compressor stages stacked along a 4-meter shaft. Both push
        air for combustion. Why so different?
      </Lead>

      <figure className="-mx-2 my-2 rounded-md border border-border-subtle bg-surface-raised p-4">
        <TurboVsJet className="w-full text-text" />
        <figcaption className="mt-2 px-2 text-xs text-text-muted">
          Two compressors that do the same thing &mdash; squeeze air for
          combustion &mdash; built for radically different boundary
          conditions. Left: a single-stage centrifugal compressor. Right: a
          multi-stage axial compressor. The choice between them is set by
          one dimensionless number.
        </figcaption>
      </figure>

      <Section id="one-number" title="One number decides">
        <p>
          There&rsquo;s a single dimensionless group that tells you which
          geometry family will be most efficient for a given duty: the{" "}
          <em>specific speed</em>, written <Inline>{`n_s`}</Inline>. It
          combines the design pressure rise (or head), the design volume
          flow, and the design rotor speed into one number:
        </p>
        <Math>{`n_s = \\frac{\\omega \\sqrt{\\dot Q}}{(\\Delta h_s)^{3/4}}`}</Math>
        <p>
          where <Inline>{`\\omega`}</Inline> is the angular speed in rad/s,{" "}
          <Inline>{`\\dot Q`}</Inline> is the volumetric flow in m<sup>3</sup>/s,
          and <Inline>{`\\Delta h_s`}</Inline> is the isentropic specific work
          in J/kg. The grouping is dimensionless when expressed this way (the
          &ldquo;rad-based&rdquo; convention); other texts use other
          conventions, so always check.<sup>1</sup>
        </p>
        <p>
          What this number says: at low specific speed (small flow per unit
          of work) you want a <em>radial</em> machine. At high specific speed
          (lots of flow per unit of work) you want an <em>axial</em>{" "}
          machine. In between, mixed-flow machines compete. This rule has
          been good empirical guidance since Otto Cordier wrote it down in
          1953 and Otto Balje refined it in 1981, and it still drives the
          first-cut architecture decision for every modern turbomachine
          design office.<sup>2</sup>
        </p>
        <p>
          Why? Because peak efficiency depends on how cleanly the flow stays
          attached to the blades, how well the velocity triangles match the
          blade angles, and how much rotor diameter you need to deliver the
          required head at the available shaft speed. Those three
          constraints all scale with the same combination of flow, head, and
          speed &mdash; which is exactly <Inline>{`n_s`}</Inline>.
        </p>
      </Section>

      <Section id="cordier" title="The Cordier diagram">
        <p>
          Plot <Inline>{`n_s`}</Inline> against the dimensionless{" "}
          <em>specific diameter</em>
        </p>
        <Math>{`d_s = \\frac{D \\,(\\Delta h_s)^{1/4}}{\\sqrt{\\dot Q}}`}</Math>
        <p>
          for every well-designed turbomachine ever measured, and the points
          cluster along a single curve in log-log space. That curve is the
          Cordier line. It traces the locus of <em>highest efficiency</em>{" "}
          across machine families: pick your <Inline>{`n_s`}</Inline>, and
          the Cordier curve tells you the diameter at which the most
          efficient machine for that duty sits.
        </p>
        <p>
          The diagram isn&rsquo;t magic. It&rsquo;s a regression line through
          decades of empirical data, and individual machines scatter above
          and below it by a few percent on efficiency. But the rough
          mapping holds reliably:
        </p>
        <ul className="ml-6 list-disc space-y-2 text-text">
          <li>
            <Inline>{`n_s < 0.3`}</Inline> &mdash; partial-admission axial,
            or piston / positive-displacement. Below specific speed of
            roughly 0.3, no continuous-flow machine is competitive with a
            piston pump.
          </li>
          <li>
            <Inline>{`n_s \\approx 0.3{-}1.0`}</Inline> &mdash; radial /
            centrifugal. Modest flow, high pressure per stage. A
            turbocharger compressor lives here; a radial-inflow turbine
            lives here.
          </li>
          <li>
            <Inline>{`n_s \\approx 1.0{-}2.5`}</Inline> &mdash; mixed-flow or
            single-stage axial. Transitional region where shape is fluid.
          </li>
          <li>
            <Inline>{`n_s > 2.5`}</Inline> &mdash; axial. Large flow, modest
            pressure per stage; stack many stages if you need a high
            pressure ratio overall.
          </li>
        </ul>
        <Citation
          source="Cordier 1953"
          page='&ldquo;Ähnlichkeitsbedingungen für Strömungsmaschinen&rdquo;, BWK 5(10), 337–340.'
        />
      </Section>

      <Section id="why-each-shape" title="Why each shape wins where it does">
        <p>
          Strip the math away and the geometric argument is simple.
        </p>
        <p>
          A <em>radial</em> machine works the air twice: once as it
          accelerates outward against the centrifugal field (which acts as
          a free pressure rise &mdash; the fluid does negative work on
          itself going up a centrifugal &ldquo;hill&rdquo;), and a second
          time as it diffuses in the volute or downstream stator. The
          radius change <Inline>{`r_2/r_1`}</Inline> typically ranges from
          1.5 to 3.0, and the work per kilogram scales like{" "}
          <Inline>{`U_2^2`}</Inline>, which can be big &mdash; an aggressive
          centrifugal impeller spinning at 100,000&nbsp;rpm with a 30&nbsp;mm
          tip radius reaches{" "}
          <Inline>{`U_2 = 315`}</Inline>&nbsp;m/s and delivers ~50&nbsp;kJ/kg
          of work in a single pass.
        </p>
        <p>
          The catch: the same large work per pass means high velocities in
          the impeller passage, which means tip Mach numbers that creep
          toward unity, which means shock-related losses. At larger flow
          rates the radius would have to grow to absorb the mass flow at a
          reasonable velocity, and rotor stresses rise as the cube of
          radius. So radial maxes out somewhere between 30 and 250&nbsp;kW
          per single stage in practice; beyond that the geometry runs out
          of room.<sup>3</sup>
        </p>
        <p>
          An <em>axial</em> machine works the air a little, over and over.
          Each axial stage typically yields a pressure ratio of 1.1 to 1.5,
          modest by radial standards, but axial stages stack: a modern
          high-pressure compressor on a turbofan engine has 9 to 12 stages
          delivering an overall pressure ratio of 25 to 40. The flow is
          parallel to the shaft, so frontal area per kilogram of throughput
          is small, and the engine looks long and thin &mdash; ideal for
          mounting under an aircraft wing.<sup>4</sup>
        </p>
        <p>
          The catch in axial-land: building twelve stages is twelve times
          the manufacturing precision of building one. Each blade is a
          different aerofoil. Tip clearances on a 3-meter rotor are
          maintained to a few thousandths of an inch. The development cost
          alone runs to a billion-plus dollars for a modern commercial
          engine. So axial machines win in markets where you can amortize
          that cost across thousands of units (aero engines) or where the
          flow rate is so high you have no choice (industrial gas turbines
          above 5&nbsp;MW).
        </p>
      </Section>

      <Section id="real-machines" title="Real machines, on the Cordier line">
        <RealExample title="A spectrum of specific speeds">
          <ul className="ml-4 list-disc space-y-2">
            <li>
              <strong>Garrett T04 turbocharger compressor</strong> &mdash;{" "}
              <Inline>{`n_s \\approx 0.7`}</Inline>. Single-stage centrifugal,
              wheel diameter 60&nbsp;mm, pressure ratio 2.5, runs at
              130,000&nbsp;rpm. Cordier predicts the diameter we use almost
              exactly.
            </li>
            <li>
              <strong>Capstone C30 microturbine compressor</strong> &mdash;{" "}
              <Inline>{`n_s \\approx 0.9`}</Inline>. Single-stage
              centrifugal, 96&nbsp;mm tip diameter, pressure ratio 3.6 at
              96,000&nbsp;rpm.<sup>5</sup> Same family as the turbo.
            </li>
            <li>
              <strong>Honeywell HGT3576 turbocharger</strong> &mdash;{" "}
              <Inline>{`n_s \\approx 1.1`}</Inline>. The largest commercial
              automotive turbo, used on heavy-duty diesel. Crossing into
              mixed-flow territory.
            </li>
            <li>
              <strong>GE LM2500 industrial gas turbine</strong> &mdash;{" "}
              <Inline>{`n_s \\approx 2`}</Inline> per stage. Sixteen-stage
              axial compressor delivering an overall pressure ratio of 18.
              22&nbsp;MW shaft power.<sup>6</sup>
            </li>
            <li>
              <strong>Pratt &amp; Whitney PW1100G high-pressure
              compressor</strong> &mdash; <Inline>{`n_s \\approx 2.3`}</Inline>{" "}
              per stage. Eight-stage axial compressor delivering pressure
              ratio of 10.5 at the rated point, 42.7&nbsp;kg/s mass flow.<sup>7</sup>
            </li>
            <li>
              <strong>GE Haliade-X 12&nbsp;MW wind turbine</strong> &mdash;{" "}
              <Inline>{`n_s \\approx 5`}</Inline>. Three-blade horizontal-
              axis rotor, 220-meter diameter. Massive flow at extremely low
              head &mdash; the opposite extreme from a turbocharger.<sup>8</sup>
            </li>
          </ul>
        </RealExample>

        <Callout kind="note" title="The same fluid, different geometries">
          <p>
            Air doesn&rsquo;t care which shape we feed it through. The
            geometry choice is about what serves <em>us</em>, the
            designers, given the constraints: cost, volume, weight, shaft
            stress, manufacturing investment. Cordier&rsquo;s curve
            captures the unstoppable physics; the choice of where to sit
            on it is yours.
          </p>
        </Callout>
      </Section>

      <Section id="try-it" title="Slide along the diagram">
        <p>
          Drag the specific-speed slider below. The impeller cross-section
          morphs between the three reference shapes, and the dot on the
          Cordier diagram moves to your operating point. The plotted
          reference machines (turbocharger, Capstone, LM2500, wind turbine)
          give you visual anchors for which shape belongs where.
        </p>
        <SpecificSpeedExplorer />
        <p>
          What does this mean for a real design? Imagine you are sizing a
          microturbine compressor at 30&nbsp;kW, 4:1 pressure ratio, with a
          design rotor speed of 96,000&nbsp;rpm. Convert to{" "}
          <Inline>{`n_s`}</Inline>: you land at about 0.9. The slider says
          you want a radial machine, and the Cordier curve predicts the
          tip diameter you should be designing toward. That&rsquo;s the
          first thing Cascade&rsquo;s flow-path page shows you when you
          start a new project &mdash; the specific-speed sanity check.
        </p>
      </Section>

      <Section id="the-other-axis" title="Specific diameter and the design ceiling">
        <p>
          The other axis of the Cordier diagram &mdash; specific diameter{" "}
          <Inline>{`d_s`}</Inline> &mdash; is just as informative.
          Once you have committed to a specific speed, the curve tells you
          the most efficient diameter. Go too small, and the blade
          velocities are subsonic but tip clearances eat your efficiency.
          Go too big, and the blade tip Mach number creeps too high and
          shock losses appear.
        </p>
        <p>
          The fact that <em>both</em> coordinates of the diagram are
          dimensionless is what makes it useful across machine families.
          A water pump, a gas-turbine compressor, and a hydraulic turbine
          all sit on the same curve when expressed in{" "}
          <Inline>{`n_s, d_s`}</Inline> space, even though one is 1&nbsp;m
          across and another is 1&nbsp;cm. The fluid changes; the curve
          doesn&rsquo;t.
        </p>
      </Section>

      <TryItCard
        href="/projects/microturbine-30kw/flowpath"
        title="Pick a geometry"
        body="Open the Flow Path page on the 30 kW microturbine starter. The first chart you see is the same Cordier diagram you just drove, with the current design point and the alternates you might consider."
      />

      <section className="mt-6 flex flex-col gap-2 border-t border-border-subtle pt-4 text-xs text-text-muted">
        <h2 className="text-xs font-medium uppercase tracking-wide text-text-muted">
          Sources
        </h2>
        <ol className="flex flex-col gap-1">
          <li>
            <span className="font-mono text-brand-text">[1]</span> Balje, O. E.,{" "}
            <em>Turbomachines: A Guide to Design, Selection, and Theory</em>,
            John Wiley &amp; Sons, 1981. Tables II/III give the canonical
            <Inline>{`n_s, d_s`}</Inline> mapping for radial, mixed, and axial
            machines.
          </li>
          <li>
            <span className="font-mono text-brand-text">[2]</span> Cordier,
            O., &ldquo;&Auml;hnlichkeitsbedingungen f&uuml;r
            Str&ouml;mungsmaschinen,&rdquo; BWK 5(10), 337&ndash;340 (1953).
            The original specific-speed&ndash;specific-diameter mapping.
          </li>
          <li>
            <span className="font-mono text-brand-text">[3]</span> Japikse,
            D. and Baines, N. C., <em>Introduction to Turbomachinery</em>,
            Concepts ETI 1994. §3.5 has the radial-compressor sizing limits.
          </li>
          <li>
            <span className="font-mono text-brand-text">[4]</span> Cumpsty,
            N. A., <em>Compressor Aerodynamics</em>, 2nd ed., Krieger 2004.
            Ch. 1 lays out the why-axial-stacks logic.
          </li>
          <li>
            <span className="font-mono text-brand-text">[5]</span> Capstone
            Turbine Corporation, <em>C30 Microturbine Aerodynamic Data
            Sheet</em>, 2004. Compressor tip diameter 96 mm at 96,000 rpm.
          </li>
          <li>
            <span className="font-mono text-brand-text">[6]</span> GE
            Aerospace, <em>LM2500 Industrial Gas Turbine Product Brochure</em>,
            2023. Sixteen-stage compressor, OPR 18:1, ISO power 22 MW.
          </li>
          <li>
            <span className="font-mono text-brand-text">[7]</span> Pratt
            &amp; Whitney, PW1100G technical specifications (FAA Type
            Certificate Data Sheet E00081EN). 8-stage HPC at 10.5 PR.
          </li>
          <li>
            <span className="font-mono text-brand-text">[8]</span> GE
            Renewable Energy, <em>Haliade-X Offshore Wind Turbine Brochure</em>,
            2023. 12 MW at 200 m hub height, 220 m rotor diameter.
          </li>
        </ol>
      </section>

      <NextChapter
        prevHref={prev ? `/learn/${prev.slug}` : undefined}
        prevTitle={prev?.title}
        nextHref={next ? `/learn/${next.slug}` : undefined}
        nextTitle={next?.title}
      />
    </Chapter>
  );
}
