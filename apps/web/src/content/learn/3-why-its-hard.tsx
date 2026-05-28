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
import { VelocityTriangleExplorer } from "@/components/learn/widgets";
import { getChapter, getChapterNeighbors } from "@/lib/learn/chapters";

const SLUG = "3-why-its-hard";

export default function Chapter3() {
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
        The blade doesn&rsquo;t push the air. The air pushes the blade.
        That sentence is correct, useful, and reverses the intuition of
        almost everyone who hasn&rsquo;t taken fluid mechanics. Here&rsquo;s
        why.
      </Lead>

      <Section id="reference-frames" title="Two reference frames">
        <p>
          The hardest part of turbomachinery is not the math. It&rsquo;s
          getting your head around two simultaneous reference frames. The
          fluid lives in the laboratory frame; the blade lives on a
          spinning rotor. What looks like a steady streamline to someone
          watching from outside the engine is an unsteady, looping thing
          from the rotor&rsquo;s point of view, and vice versa.
        </p>
        <p>
          The convention every textbook uses, and the convention Cascade
          uses, is to keep three velocities labelled at every station of
          interest:
        </p>
        <ul className="ml-6 list-disc space-y-2 text-text">
          <li>
            <strong>V</strong> &mdash; the <em>absolute</em> velocity. What
            a stationary observer in the lab frame sees the fluid doing.
          </li>
          <li>
            <strong>U</strong> &mdash; the <em>blade speed</em>. The
            tangential velocity of the rotor at the local radius:{" "}
            <Inline>{`U = \\omega r`}</Inline>. If the rotor spins at{" "}
            <Inline>{`\\omega = 1000\\,\\text{rad/s}`}</Inline> and the
            radius is 0.10&nbsp;m, then{" "}
            <Inline>{`U = 100\\,\\text{m/s}`}</Inline>.
          </li>
          <li>
            <strong>W</strong> &mdash; the <em>relative</em> velocity. What
            the fluid is doing as seen by an observer riding on the blade.
            By the rules of changing reference frame,{" "}
            <Inline>{`\\mathbf W = \\mathbf V - \\mathbf U`}</Inline>.
          </li>
        </ul>
        <p>
          The three vectors at a station form a <em>velocity triangle</em>.
          That triangle is the central object in turbomachinery
          aerodynamics. If you know the velocity triangles at the inlet and
          exit of a rotor, you know what work the rotor extracted from (or
          delivered to) the fluid. Everything else is bookkeeping.
        </p>
      </Section>

      <Section id="why-blades-bend-flow" title="Why a blade is shaped the way it is">
        <p>
          A blade is shaped so the flow approaches it at a friendly angle
          and leaves it at a different angle. The blade does no work just
          by being there; the work happens because the blade <em>changes
          the direction</em> of the relative velocity W as the fluid
          traverses the rotor passage.
        </p>
        <p>
          When the relative velocity changes direction, the fluid&rsquo;s
          angular momentum about the rotor axis changes. Conservation of
          angular momentum is the master ledger here: whatever angular
          momentum the fluid loses, the rotor gains, and that gain is
          torque on the shaft. Multiply torque by rotational speed{" "}
          <Inline>{`\\omega`}</Inline> and you have shaft power.
        </p>
        <p>
          Notice what we did <em>not</em> say. We did not say the blade
          extracts work by &ldquo;catching&rdquo; the fluid like a sail
          catches wind. Sails work by drag (the fluid pushes them along its
          own direction of motion); turbine blades work by lift (the fluid
          deflects, and the reaction force has a useful tangential
          component). This is why a Pelton waterwheel is not a turbine in
          the modern aerodynamic sense, and a wind turbine is.<sup>1</sup>
        </p>
      </Section>

      <Section id="the-euler-equation" title="The Euler turbomachinery equation">
        <p>
          Leonhard Euler wrote the equation that links velocity triangles
          to shaft work in 1754. It is the most important single equation
          in turbomachinery and falls out of one application of conservation
          of angular momentum on a rotating control volume.<sup>2</sup>
        </p>
        <p>
          Pick a control volume that wraps the rotor blades. Fluid enters
          at station 1 with absolute velocity{" "}
          <Inline>{`\\mathbf V_1`}</Inline> and leaves at station 2 with
          <Inline>{` \\mathbf V_2`}</Inline>. Decompose each absolute
          velocity into a meridional component (in the rotor&rsquo;s
          plane, the &ldquo;flow-through&rdquo; component) and a tangential
          component <Inline>{`V_\\theta`}</Inline> (in the direction of the
          blade&rsquo;s motion). The rotor radius at station 1 is{" "}
          <Inline>{`r_1`}</Inline> and at station 2 is{" "}
          <Inline>{`r_2`}</Inline>. Apply angular-momentum balance to the
          control volume:
        </p>

        <Math>{`\\Delta h_0 = U_1 V_{\\theta,1} - U_2 V_{\\theta,2}`}</Math>

        <p>
          That&rsquo;s the Euler turbomachinery equation. The change in
          stagnation enthalpy across the rotor (left-hand side) equals the
          difference between the entry and exit values of the product
          &ldquo;blade speed times tangential velocity component&rdquo;.
          For a turbine, <Inline>{`V_{\\theta,1}`}</Inline> is large
          (highly swirled flow from the upstream stator) and{" "}
          <Inline>{`V_{\\theta,2}`}</Inline> is small (we have removed
          most of the swirl in passing through the rotor), so the
          right-hand side is large and positive: work is extracted.
        </p>
        <p>
          For an axial stage where the radius is constant across the rotor
          (<Inline>{`r_1 = r_2 = r_m`}</Inline>, so{" "}
          <Inline>{`U_1 = U_2 = U`}</Inline>), the form simplifies to:
        </p>

        <Math>{`\\Delta h_0 = U \\,(V_{\\theta,1} - V_{\\theta,2}) = U \\,\\Delta V_\\theta`}</Math>

        <p>
          This is the version you&rsquo;ll see most often in aero
          textbooks. The work per unit mass equals blade speed times the
          tangential velocity change. Two factors: the velocity{" "}
          <Inline>{`U`}</Inline> the blade is moving at, and how much
          tangential motion you can yank out of the flow.
          <Citation
            source="Dixon & Hall 2014"
            page="Fluid Mechanics and Thermodynamics of Turbomachinery, 7th ed., §1.6 (Euler equation)"
          />
        </p>

        <Callout kind="note" title="One sign convention to rule them all">
          <p>
            Different textbooks pick different signs and different angle
            references. Cascade uses the convention &ldquo;angles measured
            from the axial direction, work positive when extracted from
            the fluid by the rotor.&rdquo; Legacy tools use
            &ldquo;angles from tangential&rdquo; in some screens. Both are
            mathematically equivalent &mdash; the conversion is{" "}
            <Inline>{`\\alpha_\\text{axial} = 90^\\circ - \\alpha_\\text{tangential}`}</Inline>.
            Cascade stores both and lets you toggle in the UI.
          </p>
        </Callout>
      </Section>

      <Section id="reaction-degree" title="How the work is split: reaction degree">
        <p>
          A stage with a stator and a rotor has two places to extract work:
          across the stator vanes (where the fluid accelerates and the
          static pressure drops, but no rotor moves) and across the rotor
          blades (where the fluid does work on the rotor). The fraction of
          the stage&rsquo;s static enthalpy drop that happens in the rotor
          is called the <em>degree of reaction</em>:
        </p>
        <Math>{`R = \\frac{h_1 - h_2}{h_0 - h_2}`}</Math>
        <p>
          where station 0 is the stator inlet, 1 is the stator exit (rotor
          inlet) and 2 is the rotor exit. <Inline>{`R`}</Inline> usually
          sits between 0 and 1, with two named limits:
        </p>
        <ul className="ml-6 list-disc space-y-2 text-text">
          <li>
            <strong>Impulse stage, R = 0.</strong> All the static enthalpy
            drop is in the stator. The rotor sees no pressure change &mdash;
            only a deflection of the high-velocity stream. The classic
            example is a Pelton waterwheel: water jets out of a stationary
            nozzle and lands on cup-shaped buckets that simply turn the jet
            around. The buckets see no pressure difference between front and
            back faces; the only force on the bucket is the momentum change
            of the deflected water.<sup>3</sup>
          </li>
          <li>
            <strong>50% reaction, R = 0.5.</strong> The work is split
            equally between stator and rotor. Most modern aero turbines and
            steam turbines design around this point because the velocity
            triangles become symmetric and the blade loading is balanced.
            Parsons turbines from 1880s steam-engine days were the first
            50% reaction machines; the modern descendants run in every
            commercial jet engine.<sup>4</sup>
          </li>
        </ul>
      </Section>

      <Section id="rothalpy" title="A small invariant that does heavy lifting">
        <p>
          Stagnation enthalpy isn&rsquo;t conserved through a rotor &mdash;
          that&rsquo;s the whole point, the rotor extracts work, so{" "}
          <Inline>{`h_{0,1} \\neq h_{0,2}`}</Inline>. But in the rotating
          frame, a quantity called <em>rothalpy</em> <em>is</em> conserved
          along a streamline, even across the rotor:
        </p>
        <Math>{`I = h + \\tfrac{1}{2}W^2 - \\tfrac{1}{2}U^2`}</Math>
        <p>
          Across an adiabatic rotor row, with no body forces other than the
          rotor itself, <Inline>{`I_1 = I_2`}</Inline>. Rothalpy is the
          analog of stagnation enthalpy when you live on the rotor. It is
          the most useful single conservation law in radial turbomachinery
          analysis, because it links the relative velocity{" "}
          <Inline>{`W`}</Inline>, the static enthalpy{" "}
          <Inline>{`h`}</Inline>, and the local blade speed{" "}
          <Inline>{`U`}</Inline> in a single algebraic constraint at every
          station.
          <Citation
            source="Whitfield & Baines 1990"
            page="Design of Radial Turbomachines, §2.5"
          />
        </p>
        <p>
          Cascade&rsquo;s meanline solver checks rothalpy invariance every
          time it converges a radial-inflow turbine; a violation greater
          than 10<sup>&minus;6</sup> means a bug in the loss accounting or
          a real-gas property table that doesn&rsquo;t close. It&rsquo;s a
          free correctness check, so we keep it on by default.
        </p>
      </Section>

      <Section id="try-the-triangles" title="Try the triangles">
        <p>
          The velocity triangle is the single most useful diagram in
          turbomachinery; drag the sliders and watch them redraw. The
          chapter&rsquo;s sliders are dimensionless: blade speed{" "}
          <Inline>{`U/C_m`}</Inline>, inlet blade angle{" "}
          <Inline>{`\\beta_1`}</Inline>, exit blade angle{" "}
          <Inline>{`\\beta_2`}</Inline>. Watch what happens to the Euler
          work and the reaction degree as you change each one.
        </p>
        <VelocityTriangleExplorer />
        <p>
          The widget refuses to draw unphysical regions (negative reaction
          for a turbine, blade angles past mechanical limits) and flags
          them in plain language &mdash; the same regime-check we run on
          every mean-line iteration in the product. Crank the blade speed
          up to 3 and notice how the work scales: doubling{" "}
          <Inline>{`U`}</Inline> roughly quadruples the work, because the
          Euler equation goes as <Inline>{`U \\cdot \\Delta V_\\theta`}</Inline>{" "}
          and <Inline>{`\\Delta V_\\theta`}</Inline> itself scales with{" "}
          <Inline>{`U`}</Inline> for a fixed-geometry stage.
        </p>
      </Section>

      <Section id="real-world-examples" title="Two real-world extremes">
        <RealExample title="Pelton wheel — pure impulse (R = 0)">
          <p>
            A Pelton wheel sits at the bottom of a high-head water column.
            A stationary nozzle squirts a jet of water across atmospheric
            pressure into the open air, where bucket-shaped blades catch
            the jet and turn it around 165&nbsp;degrees before letting it
            fall away. The water enters and leaves the rotor at the same
            (atmospheric) pressure, so the rotor sees zero static enthalpy
            change &mdash; pure impulse. Modern Pelton wheels deliver up to
            70&nbsp;MW per wheel at 90+% peak efficiency.<sup>5</sup>
          </p>
          <p>
            All the work comes from <Inline>{`U \\cdot \\Delta V_\\theta`}</Inline>:
            U at the bucket pitch radius is roughly half the jet velocity
            (the &ldquo;<Inline>{`U/V_\\text{jet} = 0.46`}</Inline>&rdquo; rule for
            optimal Pelton design), and{" "}
            <Inline>{`\\Delta V_\\theta`}</Inline> equals nearly twice
            <Inline>{` V_\\text{jet}`}</Inline> because the bucket turns
            the jet all the way around. Simple, robust, and exactly the
            same Euler equation as a jet engine.
          </p>
        </RealExample>

        <RealExample title="Aero gas-turbine HPT — 50% reaction">
          <p>
            The high-pressure turbine of a Pratt &amp; Whitney PW1100G runs
            at about <Inline>{`U \\approx 380`}</Inline>&nbsp;m/s at the
            blade midspan, with combustor exit temperature near 1900&nbsp;K
            and a pressure ratio across the single stage of about 4. The
            reaction degree is close to 0.5 at midspan, drifting toward
            higher reaction at the tip (where U is higher) and lower
            reaction at the hub. Real aero turbines vary R radially by
            design &mdash; the &ldquo;free-vortex&rdquo; design rule sets
            <Inline>{` r V_\\theta = \\text{const}`}</Inline> across the
            span, which guarantees radial pressure equilibrium but means R
            varies with radius.<sup>6</sup>
          </p>
        </RealExample>
      </Section>

      <TryItCard
        href="/projects/microturbine-30kw/analysis"
        title="See real velocity triangles"
        body="The Analysis page on the 30 kW microturbine project shows the actual converged velocity triangles at rotor inlet and exit, with U, V, W, alpha, beta tabulated and the loss breakdown next to them."
      />

      <section className="mt-6 flex flex-col gap-2 border-t border-border-subtle pt-4 text-xs text-text-muted">
        <h2 className="text-xs font-medium uppercase tracking-wide text-text-muted">
          Sources
        </h2>
        <ol className="flex flex-col gap-1">
          <li>
            <span className="font-mono text-brand-text">[1]</span> Wood, D. H.,{" "}
            <em>Small Wind Turbines: Analysis, Design, and Application</em>,
            Springer 2011. The Pelton-vs-modern-aero distinction is in §2.3.
          </li>
          <li>
            <span className="font-mono text-brand-text">[2]</span> Euler, L.,{" "}
            <em>Th&eacute;orie plus compl&egrave;te des machines qui sont
            mises en mouvement par la r&eacute;action de l&rsquo;eau</em>,
            Acad&eacute;mie Royale des Sciences (Berlin) 1754. The original
            derivation, in French, of the angular-momentum balance for a
            water-wheel.
          </li>
          <li>
            <span className="font-mono text-brand-text">[3]</span> Brekke, H.,{" "}
            <em>Pelton Turbines</em>, in J. P. Tullis (ed.) Hydraulics of
            Pipelines, Wiley 1989, Ch. 7. The classic exposition of the
            Pelton triangle.
          </li>
          <li>
            <span className="font-mono text-brand-text">[4]</span> Parsons,
            C. A., Patent GB 6735 of 1884. The first reaction turbine; a
            7.5&nbsp;kW prototype was demonstrated in 1885.
          </li>
          <li>
            <span className="font-mono text-brand-text">[5]</span> Audel,
            T., and Voith Hydro AG, <em>Bieudron Power Plant: 423 MW Pelton
            Turbine Design</em>, Hydro Review 18(5), 1999. Each Bieudron
            unit reaches 95.5% efficiency at 423&nbsp;MW shaft.
          </li>
          <li>
            <span className="font-mono text-brand-text">[6]</span> Dixon &
            Hall 2014, <em>op. cit.</em>, §4.4 (Free-vortex twist law for
            axial turbines). Cohen, Rogers, Saravanamuttoo, <em>Gas Turbine
            Theory</em>, 7th ed. Pearson 2017, Ch. 7.
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
