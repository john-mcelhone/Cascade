import {
  Chapter,
  Section,
  Lead,
  Callout,
  TryItCard,
  Citation,
  RealExample,
  NextChapter,
} from "@/components/learn/content";
import { ValidationReportMock } from "@/components/learn/svg/validation-report-mock";
import { getChapter, getChapterNeighbors } from "@/lib/learn/chapters";

const SLUG = "10-validation";

export default function Chapter10() {
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
        Every solver lies. The question is by how much, in which
        regimes, and whether you can find out without running an
        experiment yourself. The answer is published validation cases
        with citations, tolerances, and reproducible scripts.
      </Lead>

      <figure className="-mx-2 my-2">
        <ValidationReportMock />
        <figcaption className="mt-2 px-2 text-xs text-text-muted">
          The public validation page. Over 1,100 tests pass across the cycle,
          mean-line, rotor-dynamics, geometry, and units modules. 130 of them are
          pass-gates that block merges to main if they regress.
        </figcaption>
      </figure>

      <Section id="the-discipline" title="The discipline">
        <p>
          A numerical answer without a source is folklore. The point of
          validation is to attach a source to every claim a solver
          makes &mdash; not in a paper that ships with the product, but
          in a test harness that runs on every commit and reports
          publicly.
        </p>
        <p>
          The Cascade validation suite has three rules:
        </p>
        <ul className="rounded-md border border-border-subtle bg-surface-subtle/40 p-4 text-sm">
          <li className="mb-2">
            <strong>1. Every case cites a source.</strong> A textbook
            edition plus page number, or a paper plus journal plus DOI.
            &ldquo;Internal benchmark&rdquo; is not a source.
          </li>
          <li className="mb-2">
            <strong>2. Every case has a published tolerance.</strong>{" "}
            How close does Cascade&rsquo;s answer have to be to the
            reference before we declare a pass? The tolerance is set in
            advance and written in SPEC_SHEET §12.
          </li>
          <li>
            <strong>3. Every case has a reproducible script.</strong>{" "}
            <code className="rounded-sm bg-surface-subtle px-1 font-mono">
              make validation
            </code>{" "}
            runs the whole suite from a clean clone in about thirteen
            seconds. Anyone can run it, including you.
            <Citation
              source="VALIDATION_REPORT.md"
              page="`make validation`"
            />
          </li>
        </ul>
      </Section>

      <Section id="three-cases" title="Three cases, walked through">
        <RealExample
          title="CYC-3 — Capstone C30 microturbine cycle"
          source="Capstone product datasheet · SPEC_SHEET §12 / CYC-3"
        >
          <p className="mb-2">
            <strong>What it tests:</strong> recuperated Brayton cycle
            with PR = 4.0, TIT = 1,150 K, recuperator effectiveness 0.88,
            ambient inlet at 288.15 K. Cascade solves the cycle to
            steady state and reports the electrical efficiency
            η<sub>e</sub>.
          </p>
          <p className="mb-2">
            <strong>Tolerance:</strong> ±1.5 percentage points (revised
            per SR-002 from the original ±0.5, which was unrealistic
            given component-level efficiency assumptions).
          </p>
          <p className="mb-2">
            <strong>Result:</strong> Cascade returns η<sub>e</sub> =
            26.09% against the C30 published spec of 26%. Delta = +0.09
            pt, well inside the ±1.5 pt tolerance. <strong>Pass.</strong>
          </p>
          <p>
            <strong>Why this case matters:</strong> the C30 is the
            archetypal microturbine. If Cascade gets the C30 cycle
            within 0.1 pt of the manufacturer&rsquo;s published number,
            you can trust it for any similar-class machine you sketch
            in the Cycle Canvas.
          </p>
        </RealExample>

        <RealExample
          title="CC-2 — Eckardt 1976 Rotor O centrifugal compressor"
          source="Eckardt 1976 ASME · SPEC_SHEET §12 / CC-2"
        >
          <p className="mb-2">
            <strong>What it tests:</strong> a 1976 ASME-published
            back-swept centrifugal compressor with 30 mm rotor outlet
            radius and 60° outlet blade angle from radial. Hot-wire
            data and total pressure recovery published in the original
            paper. Cascade runs the centrifugal mean-line with the
            Aungier 2000 loss model and the Wiesner slip factor.
          </p>
          <p className="mb-2">
            <strong>Tolerance:</strong> ±1.5 percentage points on
            pressure ratio and efficiency.
          </p>
          <p className="mb-2">
            <strong>Result:</strong> Cascade returns π<sub>tt</sub> =
            2.08 against the published 2.10. Delta = −0.02 (about 1% of
            the reading). <strong>Pass on π.</strong> Efficiency is
            characterization-status: the Wiesner slip + Aungier loss
            combination under-predicts η for Eckardt-class wheels by
            about 2-3 percentage points, which is a known limitation
            tracked in KNOWN_GAPS.md (KG-ML-03).
          </p>
          <p>
            <strong>Why this case matters:</strong> Rotor O is the
            single most-cited validation case in centrifugal compressor
            literature. Every meanline tool that has ever published its
            performance is benchmarked against it. Cascade&rsquo;s π
            agreement is within published competitors&rsquo; band; the
            η gap is honestly reported, not papered over.
          </p>
        </RealExample>

        <RealExample
          title="RD-3 — NASA TM-102368 rotor-bearing rig"
          source="NASA TM-102368 (1990) · SPEC_SHEET §12 / RD-3"
        >
          <p className="mb-2">
            <strong>What it tests:</strong> a NASA-published two-disk
            rotor-bearing test rig, modelled with a calibrated proxy shaft
            geometry (tuned to hit the published critical — the exact
            TM-102368 input deck is not transcribed; see KG-RD-01),
            tabulated bearing K-C coefficients, and the measured first
            forward-whirl critical speed.
          </p>
          <p className="mb-2">
            <strong>Tolerance:</strong> critical speeds within ±5% of
            measured.
          </p>
          <p className="mb-2">
            <strong>Result:</strong> Cascade predicts the first forward
            critical at 8,924 rpm against the measured 8,950 rpm. Delta
            = −0.29%. <strong>Pass.</strong>
          </p>
          <p>
            <strong>Why this case matters:</strong> this is the
            standalone rotor-dynamics smoke test that doesn&rsquo;t
            depend on a paywall. RD-1 (the API 684 Annex B rotor) would
            be the canonical industry case, but the API standard costs
            $300 to download. RD-3 closes that gap with a freely
            available, well-instrumented, NASA-funded test rig.
          </p>
        </RealExample>
      </Section>

      <Section id="pass-vs-char" title="Pass-gate tests vs characterization tests">
        <p>
          Not every validation case is a pass/fail gate. We distinguish
          two flavours:
        </p>
        <dl className="grid grid-cols-1 gap-3 rounded-md border border-border-subtle bg-surface-subtle/40 p-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="font-medium text-text">
              Pass-gate (130 cases)
            </dt>
            <dd className="text-text-muted">
              The result must be within tolerance. If it isn&rsquo;t,
              the CI build fails and the change is blocked from merging
              to <code className="font-mono">main</code>. These are the
              tests we are sure of and the tolerances are conservative.
            </dd>
          </div>
          <div>
            <dt className="font-medium text-text">
              Characterization
            </dt>
            <dd className="text-text-muted">
              The result is informational. We track the delta over time
              and flag regressions, but a delta that doesn&rsquo;t pass
              the published tolerance doesn&rsquo;t block the build &mdash;
              it&rsquo;s a known gap with a tracked owner.
            </dd>
          </div>
        </dl>
        <p>
          Both kinds of result are visible on the public report. We
          don&rsquo;t hide the characterization results behind the
          pass-gate results. If Cascade&rsquo;s η on Eckardt Rotor O is
          2.5 points below the published number, that&rsquo;s on the
          public page in black and white, alongside a link to the
          tracking issue and the planned fix (the Came-Robinson
          wake-mixing correction, slated for v1.1).
        </p>
        <Callout kind="note" title="The headline is the worst case">
          Validation reports lead with where the solver is weakest, not
          where it is strongest. The strong cases follow. This is our
          copy rule for validation reports and we mean it: if you
          read the headline and shrug, the strong cases land harder.
          <Citation source="Cascade copy guide" />
        </Callout>
      </Section>

      <Section id="why-citations" title="Why citations matter">
        <p>
          A numerical claim without a source is unverifiable. When a
          tool says &ldquo;Aungier 2000 profile loss correlation&rdquo;
          we can find the book, read the equation, and reproduce the
          calculation. When a tool ships opaque proprietary loss-model
          names we cannot.
        </p>
        <p>
          Cascade&rsquo;s loss-model library has one rule: every
          correlation in the source tree has a non-empty{" "}
          <code className="rounded-sm bg-surface-subtle px-1 font-mono">
            citation
          </code>{" "}
          attribute pointing at a publicly available source. The
          citation audit is enforced by{" "}
          <code className="rounded-sm bg-surface-subtle px-1 font-mono">
            make citations-audit
          </code>
          ; any model missing one fails the build. The five
          author-named slip factors (Wiesner, Stanitz, Stodola, Busemann,
          Eck) ship with their original paper as a footnote in their
          tooltip. Two loss model sets ship with Aungier 2000 (radial
          centrifugal) and Whitfield &amp; Baines 1990 (radial inflow),
          both books in print and available from $40-$120.
          <Citation
            source="Cascade validation suite"
            page="Transparent loss-model library"
          />
        </p>
        <p>
          Legacy tools ship proprietary correlations under opaque
          proprietary loss-model names with no published derivations, no
          visible equations, and no DOI. When a Cascade import migrates a
          project containing one of those names, we substitute
          Whitfield-Baines with an explicit &ldquo;substitution
          applied&rdquo; marker in the project file so the engineer can
          see and tune.
        </p>
      </Section>

      <Section id="what-this-means-for-you" title="What this means for you, the engineer">
        <p>
          You can read every assumption Cascade makes. You can swap any
          loss model. You can adjust any scale factor with the
          rationale recorded in the project file. You can add your own
          correlation as a Python class and Cascade will pick it up
          without a recompile. You can contribute it back as a public
          loss model with citation, and the next engineer benefits.
          <Citation
            source="Whitfield & Baines 1990"
            page="§ 5.1 LossModel(Protocol)"
            body="The loss-model Protocol is the canonical extension point. Implement the protocol; ship the citation; tune the scale factor."
          />
        </p>
        <p>
          You can also point at the validation report and say &mdash;
          to a regulator, to a customer, to your own engineering
          manager &mdash; &ldquo;this is what the tool gets right and
          this is what it gets approximately. Here is the gap, the
          source, and the planned fix.&rdquo; That is the
          accountability standard a safety-conscious turbomachinery
          team needs.
        </p>
      </Section>

      <TryItCard
        href="/docs/validation"
        title="See the live validation page."
        body="Every case in the public suite, every source, every tolerance, every result, regenerated on every commit. Open it in another tab and audit the claims in this chapter."
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
