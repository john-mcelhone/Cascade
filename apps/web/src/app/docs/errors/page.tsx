import type { Metadata } from "next";
import Link from "next/link";
import { CodeBlock, DocPage, ParamRow, ParamTable } from "@/components/docs";
import { Callout, Section } from "@/components/learn/content";

export const metadata: Metadata = { title: "Failures & status codes" };

export default function ErrorsPage() {
  return (
    <DocPage slug="errors">
      <Section id="philosophy" title="It refuses rather than guesses">
        <p>
          Most engineering tools have two failure modes: crash, or — worse —
          return a plausible-looking wrong number. Cascade adds a third,
          deliberate one: <strong>refusal</strong>. When inputs are invalid,
          a regime is outside a model’s published validity, or an iteration
          honestly didn’t converge, you get a structured explanation of what
          happened and what to do — never a silent zero-efficiency “success”,
          never a bare <code className="font-mono text-[13px]">-1</code>.
        </p>
        <p>The failure surface is part of the spec (SPEC_SHEET §13). It has three layers:</p>
        <ul className="ml-5 list-disc space-y-2">
          <li>
            <strong>Python exceptions</strong> — typed, at the point of the
            problem.
          </li>
          <li>
            <strong>Status codes</strong> — per candidate and per map point,
            where one bad point shouldn’t kill a thousand good ones.
          </li>
          <li>
            <strong>The failure envelope</strong> — structured job results
            over the API, with plain-English explanations.
          </li>
        </ul>
      </Section>

      <Section id="exceptions" title="Python exceptions">
        <ParamTable>
          <ParamRow name="RegimeOutOfValidity" type="cascade.meanline / cycle / thermo">
            The request is outside a model’s published validity: relative
            Mach beyond the loss correlation’s range, combustor exit above
            2100 K, pressure ratio above 60, fluid temperature outside
            200–6000 K. The model has nothing honest to say there.
          </ParamRow>
          <ParamRow name="MeanlineConvergenceError" type="cascade.meanline">
            The continuity iteration would not settle. The last iterate is
            not reported as truth.
          </ParamRow>
          <ParamRow name="TypeError / ValueError" type="cascade.units">
            Wrong dimension, bare float where a Quantity belongs, NaN/±Inf,
            or non-physical magnitudes — refused at construction. See{" "}
            <Link href="/docs/units" className="font-medium text-brand-text hover:underline">
              Units &amp; quantities
            </Link>
            .
          </ParamRow>
          <ParamRow name="ValueError (IMPLAUSIBLE_BEARING_STIFFNESS)" type="cascade.rotor">
            Bearing stiffness above 10¹⁰ N/m — historically always a unit
            mistake, so it’s treated as one.
          </ParamRow>
        </ParamTable>
      </Section>

      <Section id="envelope" title="The failure envelope (API jobs)">
        <p>
          When a job ends in refusal, the job record carries{" "}
          <code className="font-mono text-[13px]">{`status: "failed"`}</code>,{" "}
          <code className="font-mono text-[13px]">error: null</code>, and a{" "}
          <code className="font-mono text-[13px]">failure</code> object in the
          result — that exact combination is the refusal signature:
        </p>
        <CodeBlock
          lang="json"
          title="a refused cycle solve"
          code={`{
  "id": "8f3a…",
  "kind": "cycle",
  "status": "failed",
  "error": null,
  "result": {
    "failure": {
      "kind": "design",
      "title": "Combustor outlet temperature infeasible",
      "plain_english": "The burner outlet temperature (2150 K) exceeds the uncooled-material limit (2100 K). Cooled-turbine modeling is not yet shipped (KG-004). Lower the burner outlet temperature.",
      "suggestions": [
        "Reduce the Burner outlet temperature (TIT) parameter",
        "Track KG-004 for cooled-row modeling"
      ],
      "details": "T_burner_outlet > T_material_limit"
    }
  }
}`}
        />
        <ParamTable title="failure object">
          <ParamRow name="kind" type='"design" | "bug"'>
            <code className="font-mono text-[13px]">design</code> means the
            configuration needs your attention — invalid inputs, incomplete
            topology, a mid-solve refusal.{" "}
            <code className="font-mono text-[13px]">bug</code> means Cascade
            hit an unexpected exception.
          </ParamRow>
          <ParamRow name="title / plain_english" type="string">
            A one-line headline and a paragraph a human can act on — written
            for the person at the screen, not the developer who wrote the
            check.
          </ParamRow>
          <ParamRow name="suggestions" type="string[]">
            Concrete next moves, in order of likelihood.
          </ParamRow>
          <ParamRow name="details" type="string">
            The technical condition that tripped, for the curious.
          </ParamRow>
          <ParamRow name="bug_log" type="string (kind=bug only)">
            The traceback, pre-packaged for a bug report.
          </ParamRow>
        </ParamTable>
        <Callout kind="note" title="Three terminal shapes, at a glance">
          <span className="font-mono text-[13px]">status=done</span> — solved
          (check <span className="font-mono text-[13px]">converged</span>;
          honest non-convergence is{" "}
          <span className="font-mono text-[13px]">done</span> +{" "}
          <span className="font-mono text-[13px]">converged: false</span> with
          an envelope).{" "}
          <span className="font-mono text-[13px]">status=failed, error=null</span>{" "}
          — refusal, read the envelope.{" "}
          <span className="font-mono text-[13px]">status=failed, error set</span>{" "}
          — a crash; please file it.
        </Callout>
      </Section>

      <Section id="status-codes" title="Per-point and per-candidate status codes">
        <p>
          Bulk operations don’t throw — they annotate. Every performance-map
          point carries exactly one of eight codes (
          <code className="font-mono text-[13px]">CONVERGED</code>,{" "}
          <code className="font-mono text-[13px]">CHOKED</code>,{" "}
          <code className="font-mono text-[13px]">STALL_SURGE</code>,{" "}
          <code className="font-mono text-[13px]">NON_CONVERGED</code>,{" "}
          <code className="font-mono text-[13px]">INVALID_GEOMETRY</code>,{" "}
          <code className="font-mono text-[13px]">REGIME_OUT_OF_VALIDITY</code>,{" "}
          <code className="font-mono text-[13px]">TIMEOUT</code>,{" "}
          <code className="font-mono text-[13px]">INFEASIBLE_BC</code>) — the{" "}
          <Link href="/docs/performance-maps" className="font-medium text-brand-text hover:underline">
            performance maps guide
          </Link>{" "}
          has an interactive explorer for all eight. Exploration candidates
          carry their own set (
          <code className="font-mono text-[13px]">VALID</code>,{" "}
          <code className="font-mono text-[13px]">MANUFACTURABILITY_FAILED</code>,
          and the shared validity/geometry/convergence codes) — see{" "}
          <Link href="/docs/exploration" className="font-medium text-brand-text hover:underline">
            Design exploration
          </Link>
          .
        </p>
      </Section>

      <Section id="http" title="Plain HTTP errors">
        <p>
          Request-level problems (before any solver runs) use ordinary HTTP
          semantics with a{" "}
          <code className="font-mono text-[13px]">detail</code> body: 404 for
          a missing project or candidate, 422 for an invalid payload (e.g.
          a <code className="font-mono text-[13px]">null</code> component
          parameter — the TOML store has no null), 409 for cancelling a job
          that already finished.
        </p>
      </Section>

      <Section id="handling" title="Handling failures in your own code">
        <CodeBlock
          lang="python"
          title="robust_sweep.py"
          code={`from cascade.meanline import RegimeOutOfValidity, MeanlineConvergenceError

results = []
for geom in geometries:
    try:
        r = solver.solve(inlet=inlet, rpm=rpm, geometry=geom,
                         loss_model=AungierCentrifugal())
        results.append(("OK", geom, r))
    except RegimeOutOfValidity as e:
        results.append(("OUT_OF_VALIDITY", geom, str(e)))
    except MeanlineConvergenceError as e:
        results.append(("NON_CONVERGED", geom, str(e)))
# Report all three buckets. The refused fraction of a sweep is data,
# not noise — it's the shape of the validity region.`}
        />
      </Section>
    </DocPage>
  );
}
