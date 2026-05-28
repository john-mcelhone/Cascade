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
import { BraytonExplorer } from "@/components/learn/widgets";
import { JetEngineCutaway } from "@/components/learn/svg/jet-engine-cutaway";
import { getChapter, getChapterNeighbors } from "@/lib/learn/chapters";

const SLUG = "2-brayton-cycle";

export default function Chapter2() {
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
        Compress cold air, heat it, expand it. Take the work the expansion
        produces; spend a small fraction running the compressor; pocket the
        rest. That recipe is the Brayton cycle, and every gas turbine on the
        planet runs some flavor of it.
      </Lead>

      <figure className="-mx-2 my-2 rounded-md border border-border-subtle bg-surface-raised p-4">
        <JetEngineCutaway className="w-full text-text" />
        <figcaption className="mt-2 px-2 text-xs text-text-muted">
          A jet engine in schematic cross-section. Air enters cold at
          station 1, leaves the compressor pressurized at station 2, exits
          the combustor much hotter at station 3, and finally leaves the
          turbine at station 4. Those four numbered points define the
          Brayton cycle.
        </figcaption>
      </figure>

      <Section id="why-this-works" title="Why compress-heat-expand pays out">
        <p>
          Compressing a gas takes work. Expanding a heated gas <em>also</em>{" "}
          takes work — out of the gas. The Brayton cycle&rsquo;s entire
          financial trick is that those two work transactions are not equal:
          you spend a small amount compressing cool air and recover a larger
          amount expanding the same air after you have heated it. The
          difference, paid in shaft power, is what you sell.
        </p>
        <p>
          The reason the books don&rsquo;t balance is the heat addition.
          Compressing 1&nbsp;kg of 288&nbsp;K air to four atmospheres takes
          roughly 130&nbsp;kJ. Heating that 1&nbsp;kg of air from the
          compressor exit temperature up to 1150&nbsp;K in a combustor adds
          another 580&nbsp;kJ. Expanding that hot, pressurized 1&nbsp;kg of
          air back to atmosphere recovers about 280&nbsp;kJ. Subtract the
          compressor cost: 150&nbsp;kJ of net shaft work, for 580&nbsp;kJ of
          fuel — a thermal efficiency of just under 26%. That is the
          ballpark for a small recuperated microturbine; bigger machines do
          better, and we&rsquo;ll see why.<sup>1</sup>
        </p>
        <p>
          The trick works because the {" "}
          <em>work of compression is roughly proportional to the inlet
          temperature</em>, while the {" "}
          <em>work of expansion is roughly proportional to the (higher)
          turbine-inlet temperature</em>. Compress when cold, expand when
          hot, and the math is in your favor. George Brayton patented the
          idea in 1872 for a piston engine; a hundred years later it would
          power every airliner in the sky.<sup>2</sup>
        </p>
      </Section>

      <Section id="the-four-states" title="The four states">
        <p>
          A Brayton cycle is usually drawn on a temperature&ndash;entropy
          (T&ndash;s) diagram with four labelled stations:
        </p>
        <ol className="ml-6 list-decimal space-y-2 text-text">
          <li>
            <strong>Station 1 &mdash; ambient.</strong> Air at the engine
            inlet. For a sea-level test stand this is 288.15&nbsp;K and
            101,325&nbsp;Pa, the International Standard Atmosphere reference
            point.
          </li>
          <li>
            <strong>Station 2 &mdash; compressor exit.</strong> The
            compressor adiabatically raises pressure by a factor of{" "}
            <Inline>{`\\pi_c`}</Inline> (the <em>pressure ratio</em>) and,
            unavoidably, raises the temperature too. In an ideal compressor
            the entropy is unchanged.
          </li>
          <li>
            <strong>Station 3 &mdash; combustor exit, turbine inlet.</strong>{" "}
            Fuel is burned in the combustor at roughly constant pressure;
            temperature climbs to the <em>turbine inlet temperature</em>{" "}
            (TIT), typically 1100&ndash;1900&nbsp;K. Entropy increases
            because heat is added.
          </li>
          <li>
            <strong>Station 4 &mdash; turbine exit, exhaust.</strong> The
            hot gas expands back to atmospheric pressure across the turbine.
            In an ideal turbine the entropy is unchanged again, so station 4
            sits directly below station 3 on the T&ndash;s diagram.
          </li>
        </ol>

        <p>
          Connect the four points and you get a closed loop on the T&ndash;s
          plot: the top edge (3 &rarr; 4) is the turbine, the right edge
          (4 &rarr; 1) is heat rejection to atmosphere, the bottom edge
          (1 &rarr; 2) is the compressor, and the left edge (2 &rarr; 3) is
          the combustor. The area enclosed by the loop is the net work per
          kilogram of working fluid. The wider the loop, the more work; the
          narrower, the less.
          <Citation
            source="Çengel & Boles 2019"
            page="Thermodynamics: An Engineering Approach, 9th ed., Ch. 9 (Brayton cycle)"
          />
        </p>
      </Section>

      <Section id="the-equations" title="The math, in three lines">
        <p>
          For an <em>ideal</em> air-standard Brayton cycle &mdash; constant
          specific heats, adiabatic and reversible compressor and turbine,
          no pressure drops &mdash; the entire cycle thermodynamics can be
          written in three lines. With{" "}
          <Inline>{`\\gamma = c_p / c_v`}</Inline> the heat-capacity ratio
          and <Inline>{`\\pi_c`}</Inline> the compressor pressure ratio:
        </p>

        <Math>{`\\frac{T_2}{T_1} = \\pi_c^{(\\gamma - 1)/\\gamma}`}</Math>
        <Math>{`\\frac{T_3}{T_4} = \\pi_c^{(\\gamma - 1)/\\gamma}`}</Math>
        <Math>{`\\eta_{\\mathrm{th,ideal}} = 1 - \\frac{T_1}{T_2} = 1 - \\pi_c^{-(\\gamma - 1)/\\gamma}`}</Math>

        <p>
          That last line is the whole thermodynamic punchline. An <em>ideal</em>{" "}
          Brayton cycle&rsquo;s thermal efficiency depends only on the
          compressor pressure ratio. Not on turbine inlet temperature, not
          on mass flow, not on the size of the engine. Pressure ratio sets
          how much of the heat input you can convert to work.
          <Citation
            source="Saravanamuttoo et al. 2017"
            page="Gas Turbine Theory, 7th ed., §2.2"
          />
        </p>
        <p>
          Higher <Inline>{`\\pi_c`}</Inline> means higher efficiency, but it
          also means higher compressor work, higher compressor-exit
          temperature, and more stages. Materials and rotor stress put a
          ceiling on how high you can push it; real cycles always trade off
          against those limits. Add a recuperator &mdash; a heat exchanger
          that pre-heats the compressed air with the turbine exhaust &mdash;
          and the formula above no longer applies, because heat input no
          longer starts at <Inline>{`T_2`}</Inline>. Recuperated cycles can
          beat the ideal-Brayton efficiency at any given pressure ratio,
          which is why microturbines like the Capstone C30 are built
          recuperated.
        </p>

        <Callout kind="note" title="Pressure ratio is one knob, TIT is another">
          <p>
            The ideal-cycle formula hides a real-world trade. As you raise{" "}
            <Inline>{`\\pi_c`}</Inline>, the compressor exit temperature
            climbs too. Eventually you run out of useful{" "}
            <em>burner&nbsp;</em>&ldquo;turn-up&rdquo; before you hit the
            material limit on the turbine inlet. Specific work (kJ per
            kilogram of air) peaks at a moderate pressure ratio, falls off
            at extreme pressure ratios, and the optimum shifts with TIT.
            That trade is what the explorer below makes you feel.
          </p>
        </Callout>
      </Section>

      <Section id="the-explorer" title="Drive the cycle">
        <p>
          Drag the pressure ratio and turbine inlet temperature sliders.
          Watch the T&ndash;s diagram redraw. Flip the recuperator on and
          see thermal efficiency jump. Recuperation makes most sense at
          modest pressure ratios &mdash; once the compressor exit is hotter
          than the turbine exit, the recuperator can&rsquo;t add heat to the
          cold side and shuts off, which is the kink you&rsquo;ll see in the
          efficiency curve at high <Inline>{`\\pi_c`}</Inline>.
        </p>
        <BraytonExplorer />
      </Section>

      <Section id="real-machines" title="Real machines, real pressure ratios">
        <p>
          Pressure ratio is the single number that tells you the most about
          a gas-turbine machine&rsquo;s thermodynamic ambition. Here&rsquo;s
          the spread:
        </p>

        <RealExample title="Pressure ratios by class">
          <ul className="ml-4 list-disc space-y-2">
            <li>
              <strong>Turbocharger</strong> &mdash; <Inline>{`\\pi_c \\approx 2{-}3`}</Inline>.
              Modest goal: about double the intake density. No combustor in
              the boost path; the burner is the engine itself, downstream.
              The compressor wheel runs maybe 130,000&nbsp;rpm in a hot-V8
              application.
            </li>
            <li>
              <strong>Microturbine</strong> (Capstone C30, Bowman 80,
              FlexEnergy GT250) &mdash; <Inline>{`\\pi_c \\approx 3.2{-}4.5`}</Inline>.
              Sized for distributed power generation and CHP. Almost always
              recuperated, because a 4-to-1 pressure ratio left to its own
              ideal-Brayton math only manages about 33% efficiency &mdash;
              not competitive with reciprocating engines. Recuperation
              brings them to roughly 26&ndash;30% net electric.<sup>3</sup>
            </li>
            <li>
              <strong>Industrial gas turbine</strong> (GE LM2500, Siemens
              SGT-A35) &mdash; <Inline>{`\\pi_c \\approx 18{-}24`}</Inline>.
              No recuperator (cycle pressure is high enough that
              recuperation no longer helps). Common in power generation,
              naval propulsion, oil-and-gas mechanical drive. Simple-cycle
              efficiency around 35&ndash;38%; combined cycle (Brayton plus a
              steam topping cycle on the exhaust) reaches 60+%.
            </li>
            <li>
              <strong>Modern high-bypass turbofan</strong> (PW1100G, Trent
              XWB, GE9X) &mdash; <Inline>{`\\pi_c \\approx 40{-}50`}</Inline>.
              The compression is split across a fan, low-pressure
              compressor, and high-pressure compressor. Net cycle pressure
              ratio approaches 50:1 in the newest engines, with TIT just
              over 1900&nbsp;K. Thermal efficiency past 50% before propulsive
              losses.<sup>4</sup>
            </li>
            <li>
              <strong>Supercritical-CO<sub>2</sub> recompression cycle</strong>{" "}
              &mdash; <Inline>{`\\pi_c \\approx 2.5{-}3`}</Inline> but at much
              higher absolute pressures. The working fluid is dense and
              compressor work drops, which is the whole appeal of sCO<sub>2</sub>.
              Operates near the CO<sub>2</sub> critical point at 7.4&nbsp;MPa,
              304&nbsp;K. Still a research/demonstration class but climbing.
              <Citation source="Dostal et al. 2004" page="MIT-ANP-TR-100" />
            </li>
          </ul>
        </RealExample>

        <p>
          When someone says &ldquo;a 40:1 cycle,&rdquo; they mean a 40:1
          overall pressure ratio. That number alone tells you the class of
          machine, the cooling regime the hot section needs, the number of
          compressor stages, and ballpark efficiency without anyone having
          to draw a chart.
        </p>
      </Section>

      <Section id="why-ideal-isnt-real" title="Why the ideal cycle is a fiction">
        <p>
          Real Brayton cycles never hit the closed-form efficiency. Every
          line in the cycle has its own villain:
        </p>
        <ul className="ml-6 list-disc space-y-1 text-text">
          <li>
            The compressor and turbine are not isentropic. Real machines
            run at adiabatic efficiencies of 0.80&ndash;0.92 (compressor) and
            0.85&ndash;0.92 (turbine). Each percentage point lost in
            component efficiency costs you about half a percentage point of
            cycle efficiency.
          </li>
          <li>
            The combustor is not isobaric. Real combustors drop 3&ndash;6%
            of total pressure across them; that&rsquo;s real work lost.
          </li>
          <li>
            The recuperator (if any) is not perfectly counterflow. Its
            <em> effectiveness </em><Inline>{`\\varepsilon`}</Inline> &mdash;
            actual heat recovered divided by maximum possible &mdash; is
            typically 0.85&ndash;0.92 in modern primary-surface cores.
            <Citation
              source="McDonald 2003"
              page="ASME GT2003-38570 (Capstone C30 recuperator)"
            />
          </li>
          <li>
            The working fluid is not calorically perfect air. At 1100&nbsp;K
            and 4&nbsp;bar, air&rsquo;s specific heat <Inline>{`c_p`}</Inline> is
            about 1.13&nbsp;kJ/(kg&middot;K), not the 1.005 you might assume from
            room-temperature tables. Real-gas property models matter.
          </li>
          <li>
            Heat is lost to the casing and to the cooling air bled from the
            compressor to keep the turbine blades alive. None of this enters
            the simple textbook formula.
          </li>
        </ul>
        <p>
          Chapter 5 walks through how engineers account for those losses
          quantitatively, with named correlations and citations. For now,
          remember: the ideal cycle tells you the absolute thermodynamic
          ceiling. The real machine sits 5&ndash;15 percentage points below
          it.
        </p>
      </Section>

      <TryItCard
        href="/projects/microturbine-30kw/cycle"
        title="Open the cycle canvas"
        body="The 30 kW microturbine starter has a recuperated Brayton cycle pre-wired with realistic boundary conditions and the Capstone C30 recuperator effectiveness. Run it; see η_e ≈ 26%."
      />

      <section className="mt-6 flex flex-col gap-2 border-t border-border-subtle pt-4 text-xs text-text-muted">
        <h2 className="text-xs font-medium uppercase tracking-wide text-text-muted">
          Sources
        </h2>
        <ol className="flex flex-col gap-1">
          <li>
            <span className="font-mono text-brand-text">[1]</span> McDonald,
            C. F., Rodgers, C., &ldquo;Small recuperated ceramic
            microturbine demonstrator concept,&rdquo; <em>Applied Thermal
            Engineering</em> 28, 2008, pp. 60&ndash;74. Cycle analysis for
            a 30&nbsp;kW recuperated radial machine, the design class of the
            Capstone C30.
          </li>
          <li>
            <span className="font-mono text-brand-text">[2]</span> Brayton,
            G. B., U.S. Patent 125,166 (1872). Originally proposed as a
            piston engine. The continuous-flow version powering modern gas
            turbines was developed in the 1930s&ndash;40s.
          </li>
          <li>
            <span className="font-mono text-brand-text">[3]</span> Capstone
            Turbine Corporation, <em>C30 Microturbine Product Specifications</em>,
            2018. Net electric efficiency 26 ± 2% at ISO conditions; ε_recup
            = 0.88, π_c = 4.0.
          </li>
          <li>
            <span className="font-mono text-brand-text">[4]</span> Pratt &
            Whitney, PW1100G Technical Specifications (FAA Type Certificate
            Data Sheet E00081EN, 2016); GE Aviation, GE9X bench-test
            results, ASME GT2019-91265.
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
