import type { Metadata } from "next";
import {
  CodeBlock,
  CodeTabs,
  DocPage,
  FilterPlayground,
  ParamRow,
  ParamTable,
} from "@/components/docs";
import { Callout, Section, TryItCard } from "@/components/learn/content";

export const metadata: Metadata = { title: "Design exploration" };

export default function ExplorationPage() {
  return (
    <DocPage slug="exploration">
      <Section id="idea" title="The idea: don't guess one design, map the space">
        <p>
          Classical preliminary design iterates one geometry by hand. Cascade
          inverts that: generate hundreds to thousands of candidate geometries
          that span the parameter space, solve the real mean-line for every
          one, and let the trade-offs emerge as a picture. The best design is
          rarely the one you’d have guessed — it’s the one sitting on the
          edge of the cloud, just inside the rules of what your shop can
          machine.
        </p>
      </Section>

      <Section id="sobol" title="Sobol' sampling, deterministic by seed">
        <p>
          Candidates come from a Sobol’ low-discrepancy sequence — it covers
          the parameter space far more evenly than random sampling, with no
          clumps and no holes. And it’s deterministic: the same seed produces
          the same candidates, on your machine or a colleague’s, today or in
          a year. An exploration is a reproducible experiment, not a dice
          roll.
        </p>
        <CodeTabs
          tabs={[
            {
              label: "Python",
              lang: "python",
              code: `from cascade.explore import SobolSampler, ParameterRange

ranges = {
    "rotor_outlet_radius": ParameterRange(min=0.01, max=0.05,
                                          unit="m", scale="linear"),
    "blade_count":         ParameterRange(min=10, max=18,
                                          unit="dimensionless", scale="linear"),
    "tip_clearance":       ParameterRange(min=1e-4, max=5e-4,
                                          unit="m", scale="log"),
}
sampler = SobolSampler(parameter_ranges=ranges, n_samples=256, seed=42)
candidates = sampler.generate()       # list of {name: Quantity} dicts

print(len(candidates))                # 256
print(sampler.discrepancy())          # L2-star discrepancy of the sample`,
            },
            {
              label: "HTTP",
              lang: "http",
              code: `POST /api/projects/{project_id}/explore
# body: parameter ranges + n_samples + seed → {"job_id": "..."}

GET  /api/jobs/{job_id}/events
# SSE stream — candidates arrive live as they solve

GET  /api/projects/{project_id}/candidates
GET  /api/projects/{project_id}/candidates/{candidate_id}`,
            },
          ]}
        />
        <p>
          Note the <code className="font-mono text-[13px]">scale</code> field:
          tip clearance spans half a decade, so it samples on a log scale —
          linear sampling would waste most points at the large end.
        </p>
      </Section>

      <Section id="filter" title="The filter DSL">
        <p>
          With a few thousand points on screen, you narrow by typing a filter.
          The grammar is deliberately tiny — terms joined by{" "}
          <code className="font-mono text-[13px]">AND</code>, each term{" "}
          <code className="font-mono text-[13px]">field op number</code> with
          operators <code className="font-mono text-[13px]">&gt; &gt;= &lt; &lt;= =</code>.
          No OR, no nesting, nothing to memorize. Try it — this playground
          runs the exact parser the Flow path page uses:
        </p>
        <FilterPlayground />
        <p>
          Fields are whatever the exploration produced: objectives like{" "}
          <code className="font-mono text-[13px]">eta_tt</code> and{" "}
          <code className="font-mono text-[13px]">M_rel</code>, and parameters
          like <code className="font-mono text-[13px]">blade_count</code>. An
          unknown field is a parse error, not a silent zero matches.
        </p>
      </Section>

      <Section id="manufacturability" title="The manufacturability gate">
        <p>
          A high-efficiency impeller you can’t machine is a graph point, not
          a design. Every candidate runs through cited 5-axis machining
          rules:
        </p>
        <ul className="ml-5 list-disc space-y-2">
          <li>
            <strong>Cutter access</strong> — can a tool physically reach the
            passage?
          </li>
          <li>
            <strong>Splitter passage</strong> — is the gap between blades wide
            enough to cut?
          </li>
          <li>
            <strong>Edge thickness</strong> — are leading/trailing edges above
            the minimum machinable thickness?
          </li>
          <li>
            <strong>Wrap angle</strong> — does the blade twist stay within
            what 5-axis kinematics can follow?
          </li>
        </ul>
        <p>
          Only candidates that pass are promoted to{" "}
          <code className="font-mono text-[13px]">VALID</code>. The rest stay
          on the plot, greyed out <em>at their real solved performance</em>,
          with the violated rules named — so you can see exactly what
          performance the machining constraint is costing you.
        </p>
        <Callout kind="tryit" title="Better-equipped shop?">
          Rules have per-project overrides:{" "}
          <code className="font-mono text-[13px]">
            PUT /api/projects/{"{id}"}/manufacturability/overrides
          </code>{" "}
          (or the UI panel) loosens individual limits — e.g. a smaller minimum
          edge thickness if your cell can hold it. Overrides live in the
          project file, so they’re versioned and reviewable like everything
          else.
        </Callout>
      </Section>

      <Section id="statuses" title="Candidate status codes">
        <ParamTable title="CandidateStatus">
          <ParamRow name="VALID" type="promoted">
            Solved, in-regime, and passes every manufacturability rule.
          </ParamRow>
          <ParamRow name="MANUFACTURABILITY_FAILED" type="greyed">
            Solved fine — a standard machining cell can’t produce it. The
            report names the violated rules.
          </ParamRow>
          <ParamRow name="REGIME_OUT_OF_VALIDITY" type="greyed">
            The point fell outside the active loss model’s published validity
            envelope. Cascade refuses to extrapolate.
          </ParamRow>
          <ParamRow name="INVALID_GEOMETRY" type="greyed">
            The sampled parameters describe an impossible shape (e.g. hub
            larger than tip).
          </ParamRow>
          <ParamRow name="NON_CONVERGED" type="greyed">
            The mean-line iteration didn’t settle for this geometry.
          </ParamRow>
        </ParamTable>
      </Section>

      <Section id="handoff" title="Closing the loop: send to cycle">
        <p>
          Pick a candidate and press <strong>Send to cycle</strong>. Its
          geometry and design rpm land on the cycle’s compressor component;
          flip that component to <em>Live mean-line</em> and the next cycle
          run uses the geometry’s solved efficiency instead of your assumed
          constant. Optionally, the handoff can also align the cycle’s
          pressure ratio and mass flow to the candidate’s, keeping the two
          views consistent.
        </p>
        <CodeBlock
          lang="http"
          bare
          code={`POST /api/projects/{id}/candidates/{cid}/send-to-cycle
POST /api/projects/{id}/candidates/{cid}/pin       # snapshot a keeper
GET  /api/projects/{id}/candidates/{cid}/geometry  # merged geometry + meridional view
GET  /api/projects/{id}/candidates/{cid}/manufacturability`}
        />
        <p>
          Pinning snapshots a candidate into the project settings — useful
          for keeping shortlist finalists around across explorations.
        </p>
        <TryItCard
          href="/projects/microturbine-30kw/flowpath"
          title="Run an exploration on the 30 kW machine"
          body="Filter to eta_tt > 0.85 AND M_rel < 1.2, click the survivors, send the best one to the cycle."
        />
      </Section>
    </DocPage>
  );
}
