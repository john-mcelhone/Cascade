import {
  Chapter,
  Section,
  Lead,
  Callout,
  TryItCard,
  Citation,
  Inline,
  Math,
  NextChapter,
} from "@/components/learn/content";
import { LossBreakdownExplorer } from "@/components/learn/widgets";
import { LossMechanisms } from "@/components/learn/svg/loss-mechanisms";
import { getChapter, getChapterNeighbors } from "@/lib/learn/chapters";

const SLUG = "5-loss-models";

export default function Chapter5() {
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
        Eta equals zero point eight seven is excellent. Where do the
        missing thirteen percentage points go? Entropy. There are nine
        named places they hide, and the literature has named all of them.
      </Lead>

      <figure className="-mx-2 my-2 rounded-md border border-border-subtle bg-surface-raised p-4">
        <LossMechanisms className="w-full text-text" />
        <figcaption className="mt-2 px-2 text-xs text-text-muted">
          A schematic turbomachinery stage with each of the nine canonical
          loss mechanisms numbered. The literature has a correlation for
          each one; every modern design tool sums them.
        </figcaption>
      </figure>

      <Section id="why-the-budget-matters" title="Why the loss budget matters">
        <p>
          A stage thermal efficiency of 0.87 means the rotor produces 87
          out of every 100 joules of isentropic work the cycle would
          theoretically allow. Thirteen joules go missing each time. They
          don&rsquo;t disappear; they show up as entropy generation,
          carried out the exit station as extra heat in the working fluid
          or as friction warming the disc face. From the cycle&rsquo;s
          point of view, that&rsquo;s 13% of the rotor&rsquo;s potential
          work permanently gone, and you cannot recover it downstream.
        </p>
        <p>
          Predicting the missing thirteen percentage points within ±1 point
          is the difference between a competitive design and an
          embarrassing one. It is also the most genuinely empirical part
          of turbomachinery design: the loss correlations are fits to
          experimental data, and the fit quality bounds your prediction
          quality. The names you&rsquo;ll see &mdash; Soderberg, Ainley-
          Mathieson, Dunham-Came, Kacker-Okapuu, Whitfield-Baines, Aungier,
          Koch-Smith &mdash; are the people who, between 1949 and 2005,
          wrote down the algebraic formulas that every modern mean-line
          solver uses.
          <Citation
            source="Aungier 2000"
            page="Centrifugal Compressors: A Strategy for Aerodynamic Design and Analysis, Ch. 6 (loss-model survey)"
          />
        </p>
      </Section>

      <Section id="nine-mechanisms" title="The nine mechanisms">
        <p>
          Modern mean-line solvers decompose stage loss into a sum of named
          buckets. There is no single canonical list &mdash; different
          authors group differently &mdash; but most modern packages converge
          on nine. Each one has a clear physical mechanism, a measurable
          driver, and a fitted correlation in a published paper.
        </p>

        <Section id="incidence-loss" title="1. Incidence loss">
          <p>
            When the flow doesn&rsquo;t arrive at the leading edge at the
            blade&rsquo;s design angle, the boundary layer trips, separates,
            and recovers downstream &mdash; spending entropy along the way.
            Incidence loss is zero at the design angle and rises roughly
            quadratically with the deviation. It dominates at off-design
            operation, which is why a compressor map looks &ldquo;banana
            shaped&rdquo; (Chapter 7) instead of square.
          </p>
          <p>
            For axial turbines, Kacker-Okapuu fits the incidence penalty as
            a chart-based correction; Aungier&rsquo;s 2006 turbine book
            replaces the chart with a computer-friendly algebraic form.<sup>1</sup>{" "}
            For radial turbines, Whitfield &amp; Baines use{" "}
            <Inline>{`\\Delta h_\\text{inc} = \\tfrac{1}{2} W_1^2 \\sin^n(\\beta_{1,\\text{flow}} - \\beta_{1,\\text{blade}})`}</Inline>{" "}
            with empirical <Inline>{`n \\approx 2`}</Inline>.<sup>2</sup>
          </p>
        </Section>

        <Section id="profile-loss" title="2. Profile loss (skin friction)">
          <p>
            Friction on the blade surface. The boundary layer on each
            blade is thin (laminar near the leading edge, transitions to
            turbulent somewhere on the suction side) but it&rsquo;s
            unavoidable, and it scales with the wetted area, the relative
            velocity squared, and a skin-friction coefficient.
          </p>
          <p>
            Ainley &amp; Mathieson&rsquo;s 1951 charts give the profile-loss
            coefficient <Inline>{`Y_p`}</Inline> as a function of inlet
            and exit blade angles for axial turbines.<sup>3</sup>{" "}
            Kacker-Okapuu&rsquo;s 1982 update scales those charts for the
            higher Mach numbers and modern profile shapes used in the
            1980s onward.<sup>4</sup> For centrifugal compressors,
            Aungier&rsquo;s 2000 book gives an explicit form{" "}
            <Inline>{`\\Delta h_\\text{sf} = 4 c_f L/D_\\text{hyd} \\cdot \\tfrac{1}{2} \\bar W^2`}</Inline>{" "}
            with skin-friction coefficient <Inline>{`c_f`}</Inline> from the
            Conrad-Raghuram diffuser correlation.<sup>5</sup>
          </p>
        </Section>

        <Section id="secondary-loss" title="3. Secondary flow loss">
          <p>
            At the hub and the shroud, the blade meets a solid endwall.
            The boundary layer there is far thicker than on the blade
            itself, and the blade-to-blade pressure gradient kicks the
            low-momentum endwall fluid into the corner. The result is a
            pair of counter-rotating passage vortices that swirl through
            the rotor passage and spend entropy. This is the dominant
            non-friction loss in modern designs, often the single largest
            bucket after profile loss.
          </p>
          <p>
            Ainley-Mathieson and Dunham-Came correlate it to a dimensionless
            blade-loading parameter; modern designs use the Kacker-Okapuu
            (1982) form{" "}
            <Inline>{`Y_s = 1.2 Y_{s,\\text{AMDC}} K_s`}</Inline> with a
            Reynolds-number scaling.
          </p>
        </Section>

        <Section id="tip-clearance-loss" title="4. Tip clearance loss">
          <p>
            A blade that isn&rsquo;t shrouded must have a gap at its tip,
            because the rotating tip cannot touch the stationary casing
            (rubbing makes sparks, removes material, and destroys both
            parts). Across that gap, the pressure difference between the
            blade&rsquo;s pressure and suction surfaces drives a leakage
            jet that bypasses the rotor&rsquo;s useful work and creates a
            tip-clearance vortex.
          </p>
          <p>
            For axial turbines, Kacker-Okapuu give{" "}
            <Inline>{`Y_{tc} = 0.5 \\cdot (\\varepsilon/h) \\cdot C_L^2 \\cdot (\\cos^2 \\alpha_2)/(\\cos^2 \\alpha_m)`}</Inline>,
            with shrouded-vs-unshrouded scaling factors.<sup>4</sup> For
            radial machines, Whitfield-Baines decompose the gap into axial
            and radial components and apply a multi-term expression. Tip
            clearance is the loss that scales fastest with engine size: a
            0.3&nbsp;mm clearance is 0.5% of blade height on a big engine
            but 5% on a 60&nbsp;mm turbocharger wheel, and the loss penalty
            scales linearly with that ratio.
          </p>
        </Section>

        <Section id="trailing-edge-loss" title="5. Trailing-edge wake loss">
          <p>
            The trailing edge has finite thickness; the two boundary
            layers from the pressure and suction surfaces leave the blade
            with a velocity defect (the &ldquo;wake&rdquo;). That wake
            mixes out downstream of the rotor, and the mixing destroys
            kinetic energy that should have been doing useful work.
            Trailing-edge loss is small (typically 1% of the total) but
            stubbornly difficult to eliminate &mdash; you cannot make a
            blade arbitrarily thin without making it structurally
            insufficient or buckle-prone.
          </p>
          <p>
            Kacker-Okapuu use their chart-based{" "}
            <Inline>{`Y_{TE}`}</Inline> coefficient that depends on TE
            thickness ratio and exit Mach number.
          </p>
        </Section>

        <Section id="disc-friction" title="6. Disc friction (windage)">
          <p>
            The back face of the rotor disc spins, and the fluid in the
            cavity between the disc and the static casing drags on it.
            That drag costs torque, and the torque cost is windage. For an
            axial turbine the disc-cavity Reynolds number is high and the
            friction coefficient is small, so disc friction is typically
            under 0.5% of stage work. For a small high-speed radial machine
            &mdash; like a turbocharger or microturbine wheel &mdash; disc
            friction can swell to 1&ndash;3% because the wheel-tip speed is
            high and the rotor diameter is small.<sup>6</sup>
          </p>
          <p>
            Daily &amp; Nece&rsquo;s 1960 paper gives the canonical{" "}
            <Inline>{`K_\\text{df}`}</Inline> chart as a function of
            disc-cavity Reynolds number; modern packages still use it.
          </p>
        </Section>

        <Section id="recirculation" title="7. Recirculation loss">
          <p>
            At high blade loadings (Lieblein&rsquo;s diffusion factor above
            DF&nbsp;&approx;&nbsp;2 in a centrifugal compressor, or comparable
            criteria in radial turbines), the flow in the impeller passage
            stops following the blade and instead detaches, recirculates,
            and re-entrains downstream. That recirculation is pure entropy
            generation. The Coppage 1956 paper at WADC fit a sinh-cubed
            form to it:
          </p>
          <Math>{`\\Delta h_\\text{rec} = 8 \\times 10^{-5} \\, \\sinh(3.5 \\alpha_2^{\\prime 3}) \\, \\mathrm{DF}^2 \\, U_2^2`}</Math>
          <p>
            which is bizarre on first sight but fits the data. Active only
            at high loading; harmless below DF&nbsp;=&nbsp;1.5.<sup>7</sup>
          </p>
        </Section>

        <Section id="mixing-loss" title="8. Mixing loss">
          <p>
            Downstream of the rotor, jets and wakes mix with each other
            and with any leakage flow from the seals. The mixing creates
            entropy. For a centrifugal compressor with a vaneless diffuser,
            mixing between the impeller&rsquo;s jet and wake regions is a
            named loss bucket, treated separately from the trailing-edge
            wake (which is the local wake at the blade itself). Aungier
            §6.9 gives an explicit form.<sup>5</sup>
          </p>
        </Section>

        <Section id="shock-loss" title="9. Shock loss">
          <p>
            If any part of the flow inside the rotor passes supersonic
            speeds, a shock wave forms, and the shock generates entropy
            irreversibly. Shock loss is identically zero below transonic
            Mach numbers; above <Inline>{`M_\\text{rel} \\approx 0.9`}</Inline>{" "}
            it grows rapidly and dominates above unity.
          </p>
          <p>
            Modern transonic axial compressor rotors (NASA Rotor 67, NASA
            Stage 37) routinely run relative Mach 1.0&ndash;1.6 at the
            blade tip in normal operation. Kacker-Okapuu&rsquo;s 1982
            shock-loss model handled this approximately; Moustapha et al.
            corrected the formula in Appendix A of their 2003 book, and
            most modern packages use the corrected version.<sup>8</sup>
          </p>
        </Section>
      </Section>

      <Section id="try-it" title="Drive the loss budget">
        <p>
          Pick one of three reference loss models below. Each has plausible
          defaults that reproduce a stage efficiency near 0.85. Tweak the
          scale factor on each bucket and watch the net efficiency move.
          Click the label on any bucket to see the citation and the
          equation Cascade uses internally.
        </p>
        <LossBreakdownExplorer />
        <p>
          What you should notice: a 10% scale-factor change on profile
          loss moves total efficiency by about 0.4 percentage points; on
          tip clearance, about 0.25; on incidence, 0.15. The big buckets
          are profile and secondary; if your real machine measures
          efficiency 2 percentage points below prediction, those are the
          first places to look.
        </p>
      </Section>

      <Section id="cascade-opinion" title="The Cascade opinion: cite, calibrate, contribute">
        <p>
          A loss model is a fitted curve from a finite experimental
          database. Outside that database&rsquo;s calibration range, the
          model is extrapolating, with potentially large error. Inside the
          range, the model carries the database&rsquo;s own measurement
          uncertainty &mdash; typically ±0.5 to ±1.5 percentage points on
          η.<sup>9</sup> An honest design tool tells you:
        </p>
        <ol className="ml-6 list-decimal space-y-1 text-text">
          <li>Which correlation it used.</li>
          <li>Where the correlation was calibrated (Mach range, Reynolds range, blade-aspect-ratio range).</li>
          <li>Whether your design lies inside or outside that range.</li>
          <li>The full algebraic form and the page in the source paper.</li>
        </ol>
        <p>
          Cascade ships a CLI that lets you audit the loss model chosen for
          your current run. Run it from the project root; the output is
          machine-readable JSON and human-readable text.
        </p>
        <pre className="overflow-x-auto rounded-md border border-border-subtle bg-surface-subtle/40 px-4 py-3 text-xs font-mono text-text">
{`$ cascade citations --component compressor
compressor.loss_model:
  family: aungier_2000
  buckets:
    incidence:       Aungier 2000, Eq. 6.41
    profile:         Aungier 2000, Eq. 6.42 (skin friction)
    blade_loading:   Aungier 2000, Eq. 6.43
    clearance:       Aungier 2000, Eq. 6.45
    recirculation:   Coppage 1956 (WADC TR-55-257)
    disc_friction:   Daily & Nece 1960
    mixing:          Aungier 2000, §6.9
  calibration_range:
    M_inlet:  0.40 .. 1.20   [your design: 0.85  ✓]
    M_tip:    0.80 .. 1.40   [your design: 1.05  ✓]
    Re_blade: 1e5 .. 5e6     [your design: 8e5   ✓]
    backsweep: 0° .. 50°     [your design: 35°   ✓]
  citation_url: doi.org/10.1115/1.802767`}
        </pre>
        <p>
          The opacity of competing tools is real and worth naming.
          Legacy tools ship loss models under opaque proprietary
          loss-model names whose internals are not public.
          A user cannot tell what equation is being summed, what database
          it was calibrated on, or whether the design sits inside the
          calibration range. Cascade&rsquo;s opposite stance &mdash; that
          every loss model is a citation, an equation, a calibration
          scale, and runnable Python source &mdash; is the central
          differentiator. You can read it. You can change it. You can
          contribute back.
        </p>

        <Callout kind="note" title="When the model is wrong">
          <p>
            All models are wrong. Some are useful. When your test data
            says the machine runs three points lower than the model
            predicts, the right response is not to call the model
            &ldquo;wrong&rdquo; &mdash; it&rsquo;s to ask which bucket the
            extra entropy is in and recalibrate <em>that</em> bucket&rsquo;s
            scale factor against your own data. Cascade keeps the
            calibration history with the project; legacy tools store the
            scale factor as an unlabelled number in a binary file.
          </p>
        </Callout>
      </Section>

      <TryItCard
        href="/projects/microturbine-30kw/analysis"
        title="Inspect the loss breakdown"
        body="Open the Analysis page on the 30 kW microturbine starter and click any bar in the loss breakdown chart. The popover shows the citation, the equation, and the calibration range — every time."
      />

      <section className="mt-6 flex flex-col gap-2 border-t border-border-subtle pt-4 text-xs text-text-muted">
        <h2 className="text-xs font-medium uppercase tracking-wide text-text-muted">
          Sources
        </h2>
        <ol className="flex flex-col gap-1">
          <li>
            <span className="font-mono text-brand-text">[1]</span> Aungier,
            R. H., <em>Turbine Aerodynamics: Axial-Flow and Radial-Inflow
            Turbine Design and Analysis</em>, ASME Press 2006, Ch. 6.
          </li>
          <li>
            <span className="font-mono text-brand-text">[2]</span>{" "}
            Whitfield, A. &amp; Baines, N. C., <em>Design of Radial
            Turbomachines</em>, Longman 1990, Ch. 6.
          </li>
          <li>
            <span className="font-mono text-brand-text">[3]</span> Ainley,
            D. G. &amp; Mathieson, G. C. R., <em>A Method of Performance
            Estimation for Axial-Flow Turbines</em>, ARC R&amp;M 2974, 1951.
          </li>
          <li>
            <span className="font-mono text-brand-text">[4]</span> Kacker,
            S. C. &amp; Okapuu, U., <em>A Mean Line Prediction Method for
            Axial Flow Turbine Efficiency</em>, ASME J. Eng. Power 104,
            111&ndash;119 (Jan 1982).
          </li>
          <li>
            <span className="font-mono text-brand-text">[5]</span> Aungier,
            R. H., <em>Centrifugal Compressors: A Strategy for Aerodynamic
            Design and Analysis</em>, ASME Press 2000, Eqs. 6.41&ndash;6.45.
          </li>
          <li>
            <span className="font-mono text-brand-text">[6]</span> Daily,
            J. W. &amp; Nece, R. E., <em>Chamber Dimension Effects on
            Induced Flow and Frictional Resistance of Enclosed Rotating
            Disks</em>, ASME J. Basic Eng. 82, 217&ndash;232 (1960).
          </li>
          <li>
            <span className="font-mono text-brand-text">[7]</span> Coppage,
            J. E. et al., <em>Study of Supersonic Radial Compressors for
            Refrigeration and Pressurization Systems</em>, WADC Technical
            Report 55-257, 1956.
          </li>
          <li>
            <span className="font-mono text-brand-text">[8]</span>{" "}
            Moustapha, H., Zelesky, M. F., Baines, N. C., Japikse, D.,{" "}
            <em>Axial and Radial Turbomachinery Design</em>, Concepts NREC
            2003, Appendix A (revised Kacker-Okapuu shock term).
          </li>
          <li>
            <span className="font-mono text-brand-text">[9]</span>{" "}
            Cumpsty, N. A., <em>Compressor Aerodynamics</em>, 2nd ed.,
            Krieger 2004, §6.6 on the credibility limits of mean-line
            correlations.
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
