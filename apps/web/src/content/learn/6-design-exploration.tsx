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
import { DesignSpaceMini } from "@/components/learn/widgets";
import { DesignSpaceScatter } from "@/components/learn/svg/design-space-scatter";
import { getChapter, getChapterNeighbors } from "@/lib/learn/chapters";

const SLUG = "6-design-exploration";

export default function Chapter6() {
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
        How do you find the best impeller? You don&rsquo;t pick one — you
        generate two thousand, then let the constraints draw the line that
        separates the survivors from the rest.
      </Lead>

      <figure className="-mx-2 my-2">
        <DesignSpaceScatter />
        <figcaption className="mt-2 px-2 text-xs text-text-muted">
          512 Sobol&rsquo; samples filling a two-dimensional design space.
          Green points are feasible (constraint-satisfied); slate ones are
          infeasible; the dashed line is the Pareto front between the two
          objectives.
        </figcaption>
      </figure>

      <Section id="the-design-space" title="The design space">
        <p>
          A radial turbomachinery designer has between five and fifteen free
          parameters per stage. Blade count. Hub-to-tip ratio. Inlet blade
          angle. Outlet blade angle. Rotor outlet radius. Splitter
          fraction. Tip clearance. RPM. The list goes on.
          <Citation
            source="Whitfield & Baines 1990"
            page="§ 6 (design parameter inventory)"
          />
        </p>
        <p>
          Each parameter spans a range. Five parameters with ten meaningful
          values each gives a 10&#x2075; = 100,000-point design space.
          Fifteen parameters and the space is bigger than the number of
          atoms in a litre of air. You cannot enumerate it. You cannot
          search it exhaustively. You have to sample.
        </p>
      </Section>

      <Section id="sampling-strategies" title="Sampling strategies">
        <p>
          There are four ways to put&nbsp;<Inline>n</Inline>&nbsp;points in
          a&nbsp;<Inline>d</Inline>-dimensional unit cube. Each one comes
          with a different trade-off.
        </p>
        <dl className="grid grid-cols-1 gap-3 rounded-md border border-border-subtle bg-surface-subtle/40 p-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="font-medium text-text">Full factorial</dt>
            <dd className="text-text-muted">
              Every combination of every parameter. Cost grows
              exponentially with dimension. Tractable to about three or
              four parameters; impossible beyond that. Used in elementary
              physics labs; not used by modern turbomachinery designers.
            </dd>
          </div>
          <div>
            <dt className="font-medium text-text">Monte Carlo (random)</dt>
            <dd className="text-text-muted">
              Uniform random points. Cheap to generate, but clumpy: large
              empty regions and dense clusters appear by chance. Convergence
              of a mean estimator is{" "}
              <Inline>O(n^{`{-1/2}`})</Inline> regardless of dimension.
            </dd>
          </div>
          <div>
            <dt className="font-medium text-text">Latin Hypercube (LHS)</dt>
            <dd className="text-text-muted">
              Stratified random: every marginal projection has exactly one
              point in each of <Inline>n</Inline> equal bins. Much better
              than plain Monte Carlo for low <Inline>d</Inline>; gets
              worse than Sobol&rsquo; for <Inline>d</Inline> above ~6.
              <Citation source="McKay et al. 1979" page="Technometrics 21" />
            </dd>
          </div>
          <div>
            <dt className="font-medium text-text">Sobol&rsquo; (LDS)</dt>
            <dd className="text-text-muted">
              A deterministic low-discrepancy sequence with{" "}
              <Inline>O((\log n)^d / n)</Inline> star discrepancy — close
              to the theoretical best. Extensible: appending more samples
              never invalidates the earlier set.
              <Citation source="Sobol' 1967" page="USSR Comp Math 7(4)" />
            </dd>
          </div>
        </dl>

        <Callout kind="note" title="Why Sobol' wins for our problem">
          <p>
            Three reasons. First, the Koksma&ndash;Hlawka bound: for a
            function of bounded variation,
          </p>
          <Math>
            {`\\left| \\frac{1}{n} \\sum_{i=1}^{n} f(\\mathbf{x}^{(i)}) - \\int_{[0,1]^d} f \\right| \\le V_{HK}(f) \\, D_n^*`}
          </Math>
          <p>
            where{" "}
            <Inline>D_n^*</Inline> is the star discrepancy of the point set.
            Low-discrepancy sequences minimize <Inline>D_n^*</Inline>.
          </p>
          <p>
            Second, Sobol&rsquo; is <em>extensible</em>: 1,024 samples is
            the first 1,024 points of 2,048 samples. The 8,192-sample
            superset reuses everything you&rsquo;ve already evaluated.
            LHS and full-factorial do not have this property.
          </p>
          <p>
            Third, Sobol&rsquo; is deterministic. Given a seed and a
            dimension, the sequence is identical on every machine. The
            design exploration in your project file is reproducible by
            anyone who opens it five years from now.
          </p>
        </Callout>
      </Section>

      <Section id="constraints" title="Constraints, not garbage">
        <p>
          Not every sample is a feasible machine. Some violate aerodynamic
          constraints (max relative Mach above sonic with no shock model).
          Some violate structural constraints (tip speed above what the
          material can hold). Some violate cost constraints (blade count
          above what the manufacturer can mill). Some are silly geometry
          (hub radius greater than outlet radius).
        </p>
        <p>
          The instinct from optimization-textbook reading is to throw
          these away. In an exploration, that&rsquo;s the wrong move. An
          infeasible candidate tells you something:{" "}
          <em>your constraint is binding there.</em> If you sketch the
          infeasibles next to the feasibles, you can see the constraint
          boundary as a line on the scatter, which is exactly what the
          designer needs to think about.
        </p>
        <p>
          So in Cascade, infeasible candidates are surfaced, not deleted.
          They render in a muted grey with the violated constraint as a
          hover label. Feasible candidates render in the chart palette
          coloured by their objective. The eye picks the front out
          instantly.
        </p>
      </Section>

      <DesignSpaceMini />

      <Section id="pareto-fronts" title="Pareto fronts">
        <p>
          A real designer rarely optimizes one number. The microturbine
          team wants high efficiency <em>and</em> low weight{" "}
          <em>and</em> low cost <em>and</em> long bearing life. These
          objectives are in tension; you can&rsquo;t maximize all of them
          at once.
        </p>
        <p>
          The Pareto-optimal set is the set of designs where no other
          design beats them on every objective at once. Formally, a
          candidate <Inline>x_1</Inline> Pareto-dominates{" "}
          <Inline>x_2</Inline> if every objective of{" "}
          <Inline>x_1</Inline> is at least as good as the corresponding
          objective of <Inline>x_2</Inline>, and at least one is strictly
          better. The non-dominated candidates form the{" "}
          <em>Pareto front</em> &mdash; a curve in 2D, a surface in 3D, a
          manifold in higher dimensions.
        </p>
        <Math>
          {`\\mathcal{P} = \\{ x \\in X : \\nexists\\, x' \\in X \\text{ s.t. } f(x') \\prec f(x) \\}`}
        </Math>
        <p>
          The front isn&rsquo;t a single answer; it&rsquo;s a menu. The
          designer reads the front, picks a region of the trade-off they
          can live with (say, &ldquo;efficiency above 86% and weight
          below 5 kg&rdquo;), and selects a candidate from that region.
          The choice involves engineering judgment, not just numerics.
          That&rsquo;s the right place for human input.
        </p>
        <Callout kind="note" title="NSGA-II vs Sobol">
          NSGA-II is a genetic algorithm that <em>converges to</em> the
          Pareto front by evolving a population over generations.
          Sobol&rsquo; doesn&rsquo;t converge to anything — it{" "}
          <em>fills</em> the design space and lets you see the front
          emerge. Cascade runs both. The first pass is Sobol&rsquo;
          (fast, broad, no preconceptions). When the designer has a sense
          of where the front lives, NSGA-II refines it.
          <Citation source="Deb et al. 2002" page="IEEE TEC 6(2)" />
        </Callout>
      </Section>

      <Section id="real-examples" title="In practice">
        <RealExample
          title="NASA E³ — Energy Efficient Engine program"
          source="NASA CR-168219 (1985)"
        >
          The E³ HPC was specified to deliver 23:1 overall pressure ratio
          in ten stages with an isentropic efficiency above 85%. The
          design team at GE generated tens of thousands of candidate stage
          configurations across a parameter sweep on stage loading,
          reaction, and stage count, then ran each through the in-house
          mean-line and 2D throughflow codes. The final design was not
          one engineer&rsquo;s favourite; it was the consensus pick from
          the Pareto-optimal region of the multi-objective scatter, with
          engine-cycle compatibility, off-design margin, and
          manufacturability as the binding constraints.
        </RealExample>

        <RealExample
          title="Capstone Turbine Corporation — C30 / C65 / C200 microturbines"
          source="Capstone product datasheets; SAE 2003-01-0080"
        >
          Capstone iterated the C30 (30 kW) and C65 (65 kW) single-stage
          radial compressor / radial turbine through hundreds of
          candidate geometries before settling on the production wheels.
          The published efficiency target (η<sub>e</sub> ≈ 26% for the
          C30) is the design-point efficiency of the chosen candidate;
          the rest of the exploration lives in the lab notebooks.
          Cascade&rsquo;s CYC-3 validation case reproduces that
          design-point cycle within 0.09 percentage points.
        </RealExample>
      </Section>

      <Section id="the-numbers" title="The numbers, honestly">
        <p>
          Legacy tools called this an{" "}
          <em>inverse solver</em> and pitched it as a different kind of
          math. It isn&rsquo;t. The math is a forward solver swept over a
          sampled parameter space. Each candidate runs the same mean-line
          solver you&rsquo;d run by hand &mdash; just two thousand times
          in parallel.
          Sometimes the technique is called &ldquo;DoE&rdquo;
          (Design of Experiments) and sometimes &ldquo;design
          exploration&rdquo; &mdash; the latter is the more
          accurate name when the goal is to map a feasibility
          space rather than to fit a response surface to noise.
          Cascade calls it design exploration.
        </p>
        <p>
          On a 2026-class laptop with eight worker threads, Cascade runs
          2,000 Sobol&rsquo; candidates through the radial-inflow
          mean-line in about nine seconds, of which roughly 30% will be
          feasible against typical constraints. That&rsquo;s the same
          headline number legacy tools demo: about 600 surviving designs
          per ten seconds of wall-clock.
        </p>
        <p>
          The difference is what you do with them. The Cascade scatter is
          colored by a perceptually-uniform ramp (viridis), every
          infeasible candidate carries its violated-constraint label, and
          the picked candidate&rsquo;s geometry is round-tripped through
          STEP export in a click. Legacy tools&rsquo; scatter uses a
          ten-bin rainbow ramp, deletes infeasibles silently, and exports
          to a binary file format only their own desktop apps can read.
        </p>
      </Section>

      <TryItCard
        href="/projects/microturbine-30kw/flowpath"
        title="Run a real design exploration."
        body="Open the Flow Path PD page on the Microturbine 30 kW project. Set parameter ranges in the left pane and Cascade will generate, filter, and rank candidates as it goes."
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
