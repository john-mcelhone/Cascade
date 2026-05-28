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
import { ModeShapeAnimator } from "@/components/learn/widgets";
import { ModeShapesDiagram } from "@/components/learn/svg/mode-shapes-diagram";
import { getChapter, getChapterNeighbors } from "@/lib/learn/chapters";

const SLUG = "8-rotor-dynamics";

export default function Chapter8() {
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
        Your impeller spins at 60,000 rpm. The shaft is a beam with mass
        and stiffness, which means it has natural frequencies. What
        happens when the rotor speed crosses one of them?
      </Lead>

      <Section id="the-shaft-as-a-beam" title="The shaft is a beam">
        <p>
          A turbomachinery rotor is not a rigid body. It is a long
          flexible steel shaft, sometimes a metre long in industrial
          machines, with one or several heavy disks attached. When it
          spins, the disks have polar mass moments of inertia that
          couple lateral and rotational degrees of freedom &mdash; the
          gyroscopic effect. When you push on the shaft, it bends.
          Bend it dynamically, and it has natural frequencies in the
          same way a guitar string does.
          <Citation
            source="API 684"
            page="2nd ed., 2010 — Rotordynamic tutorial"
            body="The industry-standard rotor-dynamic vocabulary. Cascade's separation-margin and amplification-factor definitions follow this verbatim."
          />
        </p>
        <p>
          The classical model is a Timoshenko beam discretized into
          finite elements, augmented with the gyroscopic{" "}
          <Inline>G</Inline> matrix and the bearing K-C coefficients.
          The equation of motion is:
        </p>
        <Math>
          {`M \\ddot{q} + (C + \\Omega G) \\dot{q} + K q = F(t)`}
        </Math>
        <p>
          where <Inline>q</Inline> is the lateral DOF vector,{" "}
          <Inline>\Omega</Inline> is the spin rate, and{" "}
          <Inline>F(t)</Inline> is the residual unbalance forcing at
          frequency <Inline>\Omega</Inline>. The dependence of the
          system matrices on <Inline>\Omega</Inline> is the whole
          difficulty of rotor dynamics &mdash; the natural frequencies
          themselves shift with spin.
        </p>
      </Section>

      <Section id="critical-speeds" title="Critical speeds">
        <p>
          A critical speed is a rotor speed at which the spin frequency
          equals one of the rotor&rsquo;s damped natural frequencies.
          At that speed, the 1&times; unbalance forcing resonates with
          the natural mode. Amplitude spikes; bearing reaction loads
          spike; if damping is low, things break.
        </p>
        <p>
          Every rotor has a sequence of critical speeds &mdash;
          <Inline>N_{`{c1}`}</Inline>, <Inline>N_{`{c2}`}</Inline>,
          <Inline>N_{`{c3}`}</Inline>, ... &mdash; corresponding to its
          mode shapes. The microturbine in our example project has its
          first lateral critical at about 9,000 rpm and the second
          near 24,000 rpm. Design speed is 60,000 rpm, comfortably above
          both.
        </p>
      </Section>

      <Section id="mode-shapes" title="Mode shapes">
        <p>
          A mode shape is the deflection pattern the rotor takes at one
          of its natural frequencies. They are the eigenvectors of the
          modal problem; the critical speeds are the imaginary parts of
          the corresponding eigenvalues.
        </p>
        <p>
          For a typical two-bearing rotor with disks distributed along
          its length, the first few mode shapes look like this:
        </p>
        <figure className="-mx-2 my-2">
          <ModeShapesDiagram />
          <figcaption className="mt-2 px-2 text-xs text-text-muted">
            The first three lateral mode shapes. The shaft (brand-coloured
            curve) deflects between two bearing supports (triangles);
            nodes (small open circles) sit at zero crossings in modes 2
            and 3.
          </figcaption>
        </figure>
        <p>
          Mode 1 is &ldquo;bending&rdquo; — the shaft bows out between
          the bearings. Mode 2 is &ldquo;S-shape&rdquo; with one node
          between the bearings. Mode 3 is &ldquo;W-shape&rdquo; with two
          nodes. Each higher mode adds an extra node and lives at a
          higher frequency.
        </p>
        <p>
          The physical position of the disks matters: a heavy impeller
          near a node line participates weakly in that mode; one at an
          antinode participates strongly. This is why placing impellers
          matters at the structural-design stage, not just the
          aerodynamic stage.
        </p>
      </Section>

      <ModeShapeAnimator />

      <Section id="bearings" title="Bearings — the only damping you get">
        <p>
          A turbomachinery rotor in vacuum has essentially zero damping.
          What little exists is from internal material hysteresis and is
          irrelevant for design. All of the practical damping comes from
          the bearings.
        </p>
        <p>
          Each bearing is modelled as a 2&times;2 stiffness matrix and a
          2&times;2 damping matrix in the lateral plane:
        </p>
        <Math>
          {`\\mathbf{K}_b = \\begin{bmatrix} K_{yy} & K_{yz} \\\\ K_{zy} & K_{zz} \\end{bmatrix}, \\quad \\mathbf{C}_b = \\begin{bmatrix} C_{yy} & C_{yz} \\\\ C_{zy} & C_{zz} \\end{bmatrix}`}
        </Math>
        <p>
          Plain-journal bearings are non-linear; the K-C coefficients
          depend on operating speed and load. Tabulated K-C at a grid of
          (rpm, load) is the standard exchange format. For other bearing
          types &mdash; tilting-pad, rolling-element, foil &mdash; the
          vendor publishes K-C tables at the rotor designer&rsquo;s
          request.
          <Citation
            source="Childs 1993"
            page="Turbomachinery Rotordynamics, § 4"
          />
        </p>
        <Callout kind="warning" title="Implausible bearing stiffness — a real bug">
          <p>
            Legacy tools once displayed a
            bearing stiffness of{" "}
            <Inline>K_{`{zz}`} = 3.8 \\times 10^{`{14}`}</Inline> N/m
            in its rotor-dynamics analysis window. That number is six
            orders of magnitude larger than any physical bearing
            (canonical range:{" "}
            <Inline>10^7 - 10^9</Inline> N/m). It is almost certainly a
            unit-display bug that the host application did not catch.
          </p>
          <p>
            Cascade refuses any <Inline>K_{`{xx}`}</Inline> above{" "}
            <Inline>10^{`{10}`}</Inline> N/m with an explicit{" "}
            <code className="rounded-sm bg-surface-subtle px-1 font-mono">
              IMPLAUSIBLE_BEARING_STIFFNESS
            </code>{" "}
            error, asking the user to double-check the units in their
            bearing supplier&rsquo;s datasheet (N/m vs lb/in is a common
            source).
          </p>
        </Callout>
      </Section>

      <Section id="campbell" title="The Campbell diagram">
        <p>
          The Campbell diagram plots mode frequency on the y-axis vs
          rotor speed on the x-axis. The natural-frequency lines (one
          per mode) curve gently &mdash; rising with{" "}
          <Inline>\Omega</Inline> for forward-whirl modes, falling for
          backward-whirl modes &mdash; due to gyroscopic stiffening.
        </p>
        <p>
          Overlaid on the Campbell diagram are the <em>engine-order</em>
          (EO) lines: 1&times; (synchronous unbalance), 2&times; (oval
          ovalization), 3&times;, ..., and at high orders the{" "}
          <em>nozzle passing frequency</em> (NPF) and{" "}
          <em>blade passing frequency</em> (BPF). Wherever an EO line
          crosses a mode line, that mode is excited at the corresponding
          RPM. The designer&rsquo;s job is to keep operating speeds away
          from those crossings.
        </p>
      </Section>

      <Section id="api-684-margins" title="API 684 separation margins">
        <p>
          Industry standard API 684 (§&nbsp;2.7) specifies how much
          margin the operating speed must keep from the nearest critical
          speed. For maximum continuous operating speed{" "}
          <Inline>N_{`{mc}`}</Inline>:
        </p>
        <Math>
          {`SM_{\\uparrow} = \\frac{N_{c,\\text{above}} - N_{mc}}{N_{mc}} \\times 100\\% \\ge 16\\%`}
        </Math>
        <Math>
          {`SM_{\\downarrow} = \\frac{N_{mn} - N_{c,\\text{below}}}{N_{c,\\text{below}}} \\times 100\\% \\ge 26\\%`}
        </Math>
        <p>
          The asymmetric thresholds (26% below, 16% above) reflect that
          crossing a critical on spool-up is unavoidable, but the
          operating envelope above the last crossed critical must keep
          extra clearance to the next one. Both numbers relax as a
          function of the amplification factor <Inline>Q</Inline> when
          damping is high.
          <Citation source="API 617" page="8th ed., § 2.6.2.10" />
        </p>
      </Section>

      <Section id="stability" title="Stability and log decrement">
        <p>
          Beyond the synchronous unbalance response, the rotor can
          self-excite. Cross-coupling stiffness from journal bearings,
          labyrinth seals, or aerodynamic forces (Alford&rsquo;s force in
          turbines) can drive a subsynchronous instability where the
          rotor whirls at one of its natural frequencies regardless of
          spin speed. The classical mechanism is{" "}
          <em>oil whirl / oil whip</em> in plain bearings.
        </p>
        <p>
          The stability metric is the logarithmic decrement{" "}
          <Inline>\delta</Inline>, the negative of the eigenvalue real
          part divided by the imaginary part:
        </p>
        <Math>
          {`\\delta = -\\frac{2\\pi \\,\\text{Re}(\\lambda)}{\\text{Im}(\\lambda)}`}
        </Math>
        <p>
          API 684 requires <Inline>\delta \\ge 0.1</Inline> at Level I
          (no applied cross-coupling) and{" "}
          <Inline>\delta \\ge 0</Inline> at Level II (with
          aerodynamic + seal cross-coupling per the Wachel and Kirk
          correlations). Negative <Inline>\delta</Inline> means the
          system grows energy each cycle &mdash; unstable, catastrophic
          if not arrested.
        </p>
      </Section>

      <Section id="real-cases" title="Real cases">
        <RealExample
          title="GE J47 — early jet engine rotor-dynamic failures"
          source="NACA RM E51E22 (1951)"
        >
          The J47, one of America&rsquo;s first production jet engines,
          had a notorious early-life rotor-dynamic issue at thrust
          settings near 7,500 rpm &mdash; close to the second lateral
          critical. Fleet-wide blade liberations were eventually traced
          to insufficient damping at that crossing combined with
          residual unbalance from rough production tolerances. The fix
          was a redesigned damper bearing and tighter balance limits;
          the analytical methods that exposed the problem became the
          template for what is now API 684.
        </RealExample>

        <RealExample
          title="Turbocharger oil whirl"
          source="Garrett / Honeywell Turbo Technologies tech bulletins"
        >
          Aftermarket performance turbochargers running plain journal
          bearings at high speed are famous for sub-synchronous whirl
          tones, often audible as a low warble at part-throttle. The
          mechanism is bearing cross-coupling driving the rotor to
          orbit at about half the spin rate. Production turbochargers
          mitigate it with semi-floating ring bearings or, in
          high-output applications, with ball bearings.
        </RealExample>
      </Section>

      <TryItCard
        href="/projects/microturbine-30kw/rotor"
        title="Run a critical-speed map."
        body="Open the Rotor page on the Microturbine 30 kW project. Cascade will sweep bearing stiffness over its range and plot the resulting critical-speed loci; you confirm the design speed sits in a stable, well-separated band."
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
