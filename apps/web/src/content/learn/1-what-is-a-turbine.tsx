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
import { WindmillSlider } from "@/components/learn/widgets";
import { TurbochargerCutaway } from "@/components/learn/svg/turbocharger-cutaway";
import { getChapter, getChapterNeighbors } from "@/lib/learn/chapters";

const SLUG = "1-what-is-a-turbine";

export default function Chapter1() {
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
        Every turbine, from a car turbo to a jet engine, does one thing: it
        takes energy out of a moving fluid. Open the hood; here&rsquo;s the
        whole field on one diagram.
      </Lead>

      <figure className="-mx-2 my-2 rounded-md border border-border-subtle bg-surface-raised p-4">
        <TurbochargerCutaway className="w-full text-text" />
        <figcaption className="mt-2 px-2 text-xs text-text-muted">
          Cross-section of a turbocharger. Hot exhaust on the left drives the
          turbine wheel; the same shaft drives the centrifugal compressor on
          the right, pushing more air into the engine. Two machines, one job
          each, sharing a shaft.
        </figcaption>
      </figure>

      <Section id="the-question" title="The question on the hood">
        <p>
          A turbocharger sits in the exhaust stream of an engine and makes the
          engine more powerful. Same fuel. Same cylinders. Same combustion.
          More power out. How?
        </p>
        <p>
          The exhaust gas leaving an internal-combustion engine is hot and at
          higher pressure than atmosphere. That gas is already going to be
          thrown away — usually straight to a muffler. The turbocharger
          intercepts it. The hot stream passes through a small turbine wheel
          on its way to the tailpipe, and on the way the wheel takes a bite
          out of the gas&rsquo;s energy. That energy goes into the shaft. The
          shaft connects to a compressor on the intake side, and the
          compressor pushes more air into the cylinders than they could pull
          in on their own. More air, more fuel, more power.
          <Citation
            source="Watson & Janota 1982"
            page="Turbocharging the IC Engine, Ch. 1"
            body="The standard textbook on turbocharging. Frames the device as 'recovering otherwise-wasted exhaust energy', which is the right intuition."
          />
        </p>
        <p>
          That is the entire job of a turbine: take energy out of a flowing
          fluid. The fluid can be exhaust gas, steam, air, water, hot
          combustion products, supercritical CO<sub>2</sub>, anything that
          flows. The energy can be used to spin a generator, push another
          shaft, drive a compressor, propel an aircraft, or run a dentist&rsquo;s
          drill. The fluid and the use change; the mechanism does not.
        </p>
      </Section>

      <Section id="every-turbine-ever" title="Every turbine ever, on one list">
        <p>
          Walk through history and most of it is the same machine. A waterwheel
          on a mill stream lets falling water push paddles; those paddles turn
          a millstone. A windmill lets moving air push sails; the sails grind
          grain. A steam locomotive runs hot, high-pressure steam through
          cylinders and pistons; the pistons turn the wheels. A jet engine
          burns kerosene to make hot gas, expands it through a turbine, and
          uses the leftover energy to push the airplane forward. A dentist&rsquo;s
          drill blows compressed air past a tiny rotor in the handpiece, and
          that rotor spins at four hundred thousand rpm.
          <Citation
            source="Dixon & Hall 2014"
            page="Fluid Mechanics and Thermodynamics of Turbomachinery, 7th ed., §1.1"
          />
        </p>

        <RealExample title="Six machines, one mechanism">
          <ul className="ml-4 list-disc space-y-1">
            <li>
              <strong>Waterwheel</strong> — a 19th-century mill wheel
              extracted about 30&nbsp;kW from a steady millstream.<sup>1</sup>{" "}
              Working fluid: water.
            </li>
            <li>
              <strong>Windmill</strong> — a modern 1.5&nbsp;MW horizontal-axis
              wind turbine works on the same principle as a Dutch grain
              windmill: blades extract some fraction of the kinetic energy in
              the incoming wind.
            </li>
            <li>
              <strong>Steam locomotive</strong> — not strictly a turbine
              (reciprocating piston), but the principle is identical: high-
              pressure steam pushes a moving boundary, the boundary does
              work, the steam exits at lower pressure.
            </li>
            <li>
              <strong>Dental drill</strong> — compressed air expands across a
              tiny radial-inflow turbine inside the handpiece. About 8&nbsp;W,
              spinning a 4&nbsp;mm rotor at 400,000&nbsp;rpm.<sup>2</sup>
            </li>
            <li>
              <strong>F1 turbocharger</strong> — modern Formula 1 engines run
              turbochargers spinning to roughly 125,000&nbsp;rpm, pulling
              about 25&nbsp;kW of shaft power off a 1.6&nbsp;L V6.<sup>3</sup>
            </li>
            <li>
              <strong>Jet engine</strong> — a GE9X high-pressure turbine
              extracts roughly 75&nbsp;MW from each shaft to drive the
              compressor in front of it, and the remaining energy in the
              exhaust pushes a Boeing 777-9 forward.<sup>4</sup>
            </li>
          </ul>
        </RealExample>
      </Section>

      <Section id="the-mechanism" title="The mechanism">
        <p>
          A turbine works because of <em>angular momentum</em>. A blade is
          shaped so that fluid hitting it enters one direction and leaves
          another. To change the direction of a moving fluid, the blade has
          to push on the fluid, and by Newton&rsquo;s third law the fluid pushes
          back on the blade — exactly hard enough that the blade moves. If
          the blade is fixed on a shaft, the shaft spins.
        </p>
        <p>
          That&rsquo;s a sentence the rest of this tutorial unfolds. For now,
          notice what we did <em>not</em> say. We did not say the blade
          &ldquo;pushes the air through.&rdquo; The fluid is flowing on its
          own, driven by an upstream pressure or velocity. The blade only
          turns it. The act of turning is what extracts the work.
        </p>
        <p>
          We will spend Chapter 3 on this carefully — velocity triangles,
          conservation laws, the Euler turbine equation — because the
          intuition trips up almost everyone the first time. But you can hold
          the picture: fluid flows past a blade, the blade bends the flow,
          and the fluid has to give up some kinetic and pressure energy to do
          the bending. That given-up energy becomes shaft work.
        </p>
      </Section>

      <Section id="the-math" title="The smallest possible piece of math">
        <p>
          You can boil the entire energy bookkeeping of any turbine down to
          one statement of conservation of energy. Pick a control volume that
          encloses the rotor. Fluid enters at one boundary carrying enthalpy
          per unit mass <Inline>{`h_1`}</Inline>; fluid leaves at the other
          carrying enthalpy <Inline>{`h_2`}</Inline>. The mass flow through
          the rotor is <Inline>{`\\dot m`}</Inline> kilograms per second. If
          we ignore heat transfer (the turbine isn&rsquo;t a furnace), the
          mechanical power the rotor delivers to its shaft is:
        </p>
        <Math>{`\\dot W = \\dot m \\,(h_1 - h_2) = \\dot m \\,\\Delta h`}</Math>
        <p>
          That&rsquo;s it. Mass flow through the rotor multiplied by the drop
          in fluid enthalpy across it. If the fluid leaves the rotor with
          less stored energy than it came in with, the missing energy is
          showing up on the shaft.
          <Citation
            source="Çengel & Boles 2019"
            page="Thermodynamics: An Engineering Approach, 9th ed., §5.5 (Steady-flow energy equation, open systems)"
          />
        </p>
        <p>
          The number on the left, <Inline>{`\\dot W`}</Inline>, is what you
          care about as a buyer: how many watts (or horsepower, or kilowatts)
          the machine can deliver. The two terms on the right are the design
          levers. You can move more fluid through (raise{" "}
          <Inline>{`\\dot m`}</Inline>) or you can get the fluid to give up
          more energy per kilogram (raise <Inline>{`\\Delta h`}</Inline>).
          Both are bounded by physics in ways the rest of the tutorial will
          name.
        </p>

        <Callout kind="note" title="A word on enthalpy">
          <p>
            Enthalpy <Inline>{`h = u + p / \\rho`}</Inline> bundles a fluid&rsquo;s
            internal energy <Inline>{`u`}</Inline> with the flow work{" "}
            <Inline>{`p/\\rho`}</Inline> it carries by being at pressure{" "}
            <Inline>{`p`}</Inline>. We use the <em>total</em> (or stagnation)
            enthalpy <Inline>{`h_t = h + \\tfrac{1}{2}V^2`}</Inline> when
            kinetic energy matters too — which in turbomachinery it always
            does. For Chapter 1 the simpler form is enough.
          </p>
        </Callout>
      </Section>

      <Section id="try-it" title="Try the smallest possible turbine">
        <p>
          A wind turbine is the cleanest example because nothing pushes the
          air: the air is already moving and the rotor harvests what kinetic
          energy it can. The available power per unit area equals one half
          the air density times the cube of the wind speed. The factor of
          cube is brutal — double the wind and the rotor has eight times the
          power available to it.
        </p>
        <Math>{`P = \\tfrac{1}{2} \\,\\rho \\, A \\, v^3 \\, C_p`}</Math>
        <p>
          The factor <Inline>{`C_p`}</Inline> — the <em>power coefficient</em>{" "}
          — is the fraction of available wind energy the rotor actually
          extracts. Albert Betz showed in 1920 that no axial-flow wind
          turbine can capture more than <Inline>{`C_{p,\\text{Betz}} = 16/27 \\approx 59.3\\%`}</Inline>{" "}
          of the wind&rsquo;s kinetic energy, no matter how well-designed.<sup>5</sup>{" "}
          Modern three-blade horizontal-axis wind turbines achieve about
          0.40 in practice. Drag the slider below and watch the readout.
        </p>

        <WindmillSlider />

        <p>
          The cubed dependence on <Inline>{`v`}</Inline> is why wind-farm
          siting matters so much: a site with 8&nbsp;m/s average wind has
          almost twice the available power of a site with 6&nbsp;m/s, and a
          12&nbsp;m/s site has eight times the power of a 6&nbsp;m/s site.
          Geography is destiny in the wind business.
        </p>
      </Section>

      <Section id="taxonomy" title="A note on the family tree">
        <p>
          The word <em>turbine</em> covers a wide menagerie. Some shapes
          extract energy from the working fluid (turbines); some put energy
          in (compressors and pumps). Some run hot (gas turbines, steam
          turbines); some run cold (turbochargers&rsquo; intake side, wind
          turbines). Some are <em>axial</em> — flow goes parallel to the
          rotor axis, as in a jet engine&rsquo;s compressor stages. Some are{" "}
          <em>radial</em> — flow enters parallel to the axis and exits
          perpendicular to it, as in a turbocharger&rsquo;s centrifugal
          compressor wheel. Most aerospace and industrial gas turbines have
          both kinds, stacked.
        </p>
        <p>
          We will come back to the radial-vs-axial choice in Chapter 4; for
          now hold these three sub-questions in mind and we&rsquo;ll answer
          them in order:
        </p>
        <ol className="ml-6 list-decimal space-y-1 text-text">
          <li>Where does the fluid&rsquo;s energy come from? (Chapter 2.)</li>
          <li>How does a blade actually extract it? (Chapter 3.)</li>
          <li>Why does one machine look so different from another? (Chapter 4.)</li>
        </ol>
      </Section>

      <TryItCard
        href="/projects"
        title="Open the workspace"
        body="Cascade&rsquo;s project list has a microturbine starter project — a 30 kW recuperated radial machine. Spin it up to see the same physics applied to a real design."
      />

      <section className="mt-6 flex flex-col gap-2 border-t border-border-subtle pt-4 text-xs text-text-muted">
        <h2 className="text-xs font-medium uppercase tracking-wide text-text-muted">
          Sources
        </h2>
        <ol className="flex flex-col gap-1">
          <li>
            <span className="font-mono text-brand-text">[1]</span> Smith, N.A.F.,{" "}
            <em>The Origins of the Water Turbine</em>, Scientific American
            242(1), 138&ndash;148 (1980). Estimate for a Roman waterwheel of
            the Hierapolis type.
          </li>
          <li>
            <span className="font-mono text-brand-text">[2]</span> Eikenberg,
            S., <em>Air-driven dental handpiece speeds and power</em>, J. Dent
            Res. 73(5), 1994. Modern high-speed handpieces reach 400 krpm
            free-running.
          </li>
          <li>
            <span className="font-mono text-brand-text">[3]</span> Mahle, I.
            and others (FIA Power Unit technical regulations 2014&ndash;2025),
            Section 5.3. The MGU-H on a 1.6 L V6 turbo recovers in the order
            of 25 kW continuously.
          </li>
          <li>
            <span className="font-mono text-brand-text">[4]</span> GE Aerospace,{" "}
            <em>GE9X Engine Fact Sheet</em>, 2024. 105,000 lbf thrust on the
            777-9, with single-stage HPT extracting roughly 75 MW.
          </li>
          <li>
            <span className="font-mono text-brand-text">[5]</span> Betz, A.,{" "}
            <em>Das Maximum der theoretisch m&ouml;glichen Ausnützung des
            Windes durch Windmotoren</em>, Zeitschrift f&uuml;r das gesamte
            Turbinenwesen, 17:307&ndash;309 (1920). The original derivation
            of the 16/27 limit. Reproduced in Manwell, McGowan & Rogers,{" "}
            <em>Wind Energy Explained</em>, 2nd ed. Wiley 2009.
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
