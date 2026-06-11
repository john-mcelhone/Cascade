import type { Metadata } from "next";
import Link from "next/link";
import {
  CodeBlock,
  DocPage,
  Endpoint,
  EndpointList,
  ParamRow,
  ParamTable,
} from "@/components/docs";
import { Callout, Section } from "@/components/learn/content";

export const metadata: Metadata = { title: "REST API & jobs" };

export default function RestApiPage() {
  return (
    <DocPage slug="rest-api">
      <Section id="basics" title="Basics">
        <p>
          The API is a FastAPI server on{" "}
          <code className="font-mono text-[13px]">http://localhost:8000</code>{" "}
          — the same one the web app talks to. It’s single-user and local in
          v0.1 (auth, multi-user storage, and hosted deployment are roadmap
          items —{" "}
          <code className="font-mono text-[13px]">KG-PLAT-01/04</code>).
          Because it’s FastAPI, the interactive OpenAPI browser is free:
        </p>
        <CodeBlock
          lang="bash"
          bare
          code={`$ curl http://localhost:8000/api/health
# {"status": "ok", "cascade_version": "0.1.0", ...}

# Interactive docs: http://localhost:8000/docs (Swagger UI)`}
        />
        <p>
          Errors come back as{" "}
          <code className="font-mono text-[13px]">{`{"detail": ...}`}</code>{" "}
          — a string for simple cases, a structured object (with{" "}
          <code className="font-mono text-[13px]">error_code</code> and
          friends) where the client needs to act on it. Solver-level refusals
          use the richer failure envelope described in{" "}
          <Link href="/docs/errors" className="font-medium text-brand-text hover:underline">
            Failures &amp; status codes
          </Link>
          .
        </p>
      </Section>

      <Section id="jobs" title="The job model">
        <p>
          Anything that solves — cycle, exploration, map, rotor, analysis —
          runs as a <strong>job</strong>. The POST returns immediately with a
          job id; the work runs on a small thread pool (4 workers); you watch
          progress over Server-Sent Events or poll.
        </p>
        <CodeBlock
          lang="bash"
          title="terminal — run a cycle solve and stream progress"
          code={`$ curl -X POST http://localhost:8000/api/projects/microturbine-30kw/cycle/solve
# {"job_id": "8f3a…"}

$ curl -N http://localhost:8000/api/jobs/8f3a…/events
# data: {"progress": 0.2, "message": "Outer iteration 3"}
# data: {"progress": 1.0, "status": "done", "result": {…}, "final": true}`}
        />
        <ParamTable title="Job object">
          <ParamRow name="status" type='"queued" | "running" | "done" | "failed" | "cancelled"'>
            The lifecycle state.{" "}
            <code className="font-mono text-[13px]">done</code> with{" "}
            <code className="font-mono text-[13px]">converged: false</code> in
            the result means the solver finished honestly without an answer.
          </ParamRow>
          <ParamRow name="progress / message" type="0.0–1.0 / string">
            Live progress, also streamed over SSE.
          </ParamRow>
          <ParamRow name="result" type="object | null">
            The solver output on success — or a structured{" "}
            <code className="font-mono text-[13px]">failure</code> envelope on
            refusal.
          </ParamRow>
          <ParamRow name="error" type="string | null">
            Set only for unexpected crashes. The refusal signature is{" "}
            <code className="font-mono text-[13px]">{`status="failed"`}</code> +{" "}
            <code className="font-mono text-[13px]">error=null</code> +{" "}
            <code className="font-mono text-[13px]">result.failure</code>{" "}
            present.
          </ParamRow>
        </ParamTable>
        <EndpointList>
          <Endpoint method="GET" path="/api/jobs" summary="list jobs (filter with ?project_id=)" />
          <Endpoint method="GET" path="/api/jobs/{job_id}" summary="status + result" />
          <Endpoint method="GET" path="/api/jobs/{job_id}/events" summary="SSE stream; pings every 15 s" />
          <Endpoint method="DELETE" path="/api/jobs/{job_id}" summary="cancel; 409 if already finished" />
        </EndpointList>
        <Callout kind="note" title="Jobs are in-memory; projects are on disk">
          Restarting the API forgets job history but never touches projects —
          those are TOML files. Re-run the solve; the inputs were never at
          risk.
        </Callout>
      </Section>

      <Section id="projects" title="Projects & components">
        <EndpointList>
          <Endpoint method="GET" path="/api/projects" summary="all projects" />
          <Endpoint method="POST" path="/api/projects" summary="create from template: microturbine | sco2 | aero | blank" />
          <Endpoint method="GET" path="/api/projects/{id}" summary="components, edges, BCs, settings" />
          <Endpoint method="PATCH" path="/api/projects/{id}" summary="rename, settings, boundary conditions" />
          <Endpoint method="DELETE" path="/api/projects/{id}" />
          <Endpoint method="GET" path="/api/projects/{id}/components" summary="components + edges" />
          <Endpoint method="POST" path="/api/projects/{id}/components" summary="add a component" />
          <Endpoint method="PATCH" path="/api/projects/{id}/components/{cid}" summary="edit params — persists to TOML immediately" />
          <Endpoint method="DELETE" path="/api/projects/{id}/components/{cid}" summary="delete + cascade-delete its edges" />
          <Endpoint method="DELETE" path="/api/projects/{id}/components/{cid}/geometry" summary="detach handoff geometry" />
        </EndpointList>
        <p>
          Two behaviors worth knowing: editing an <strong>Inlet</strong>{" "}
          component mirrors onto the project’s boundary conditions, and a
          parameter set to <code className="font-mono text-[13px]">null</code>{" "}
          is rejected with 422 (the TOML store has no null — remove the key
          instead).
        </p>
      </Section>

      <Section id="solvers" title="Solver endpoints">
        <EndpointList>
          <Endpoint method="POST" path="/api/projects/{id}/cycle/solve" summary="0D cycle solve → job" />
          <Endpoint method="POST" path="/api/projects/{id}/explore" summary="Sobol' exploration → job; candidates stream over SSE" />
          <Endpoint method="POST" path="/api/projects/{id}/map" summary="performance map sweep → job; points stream over SSE" />
          <Endpoint method="POST" path="/api/projects/{id}/rotor" summary="rotor dynamics analyses → job" />
          <Endpoint method="POST" path="/api/projects/{id}/analysis" summary="cycle sensitivity (tornado / one-at-a-time) → job" />
          <Endpoint method="GET" path="/api/projects/{id}/rotor/report.pdf" summary="API 684-style PDF of the latest rotor run" />
        </EndpointList>
      </Section>

      <Section id="candidates" title="Candidates (exploration results)">
        <EndpointList>
          <Endpoint method="GET" path="/api/projects/{id}/candidates" summary="all candidates across jobs" />
          <Endpoint method="GET" path="/api/projects/{id}/candidates/{cid}" />
          <Endpoint method="GET" path="/api/projects/{id}/candidates/{cid}/geometry" summary="merged geometry + meridional polylines" />
          <Endpoint method="GET" path="/api/projects/{id}/candidates/{cid}/manufacturability" summary="per-rule pass/violation report" />
          <Endpoint method="POST" path="/api/projects/{id}/candidates/{cid}/send-to-cycle" summary="write geometry + rpm onto the cycle compressor" />
          <Endpoint method="POST" path="/api/projects/{id}/candidates/{cid}/pin" summary="snapshot into project settings" />
        </EndpointList>
        <p>
          Export endpoints for candidates (GLB, STL, STEP, IGES, TurboGrid
          NDF, fluid-volume STEP) are covered in{" "}
          <Link href="/docs/export" className="font-medium text-brand-text hover:underline">
            Geometry export
          </Link>
          .
        </p>
      </Section>

      <Section id="supporting" title="Supporting resources">
        <EndpointList>
          <Endpoint method="GET" path="/api/loss-models" summary="built-in cited models" />
          <Endpoint method="GET" path="/api/projects/{id}/loss-models" summary="project-scoped plugin models" />
          <Endpoint method="POST" path="/api/projects/{id}/loss-models/upload" summary="upload a plugin (multipart)" />
          <Endpoint method="POST" path="/api/projects/{id}/loss-models/{name}/select" summary="activate for this project" />
          <Endpoint method="GET" path="/api/projects/{id}/manufacturability" summary="rule report (?candidate_id= optional)" />
          <Endpoint method="PUT" path="/api/projects/{id}/manufacturability/overrides" summary="per-project rule overrides" />
          <Endpoint method="GET" path="/api/materials" summary="alloy database (?family= filter)" />
          <Endpoint method="GET" path="/api/materials/{name}" summary="full temperature-dependent property tables" />
          <Endpoint method="GET" path="/api/bearings/presets" summary="foil-bearing coefficient presets" />
          <Endpoint method="GET" path="/api/validation/cases" summary="the validation report, structured" />
          <Endpoint method="GET" path="/api/health" summary="service + version" />
          <Endpoint method="GET" path="/api/health/cad" summary="is the optional CAD stack available?" />
        </EndpointList>
      </Section>

      <Section id="sse-detail" title="SSE details">
        <ul className="ml-5 list-disc space-y-2">
          <li>
            Each event’s <code className="font-mono text-[13px]">data</code>{" "}
            is JSON:{" "}
            <code className="font-mono text-[13px]">{`{progress, message, status?, result?, final?}`}</code>
            . The terminal event has{" "}
            <code className="font-mono text-[13px]">final: true</code> and
            closes the stream.
          </li>
          <li>
            Exploration and map jobs put streaming payloads in the event data
            — e.g. each solved map point arrives as{" "}
            <code className="font-mono text-[13px]">{`{"point": {…}}`}</code>.
          </li>
          <li>
            A ping every 15 seconds keeps proxies from killing idle
            connections.
          </li>
          <li>
            Numbers are sanitized to JSON-safe values — NaN and ±Inf
            serialize as <code className="font-mono text-[13px]">null</code>,
            never as invalid JSON.
          </li>
        </ul>
      </Section>
    </DocPage>
  );
}
