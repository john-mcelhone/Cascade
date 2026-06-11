import type { Metadata } from "next";
import Link from "next/link";
import {
  CodeBlock,
  CodeTabs,
  DocPage,
  StatusCodeExplorer,
} from "@/components/docs";
import { Callout, Section, TryItCard } from "@/components/learn/content";

export const metadata: Metadata = { title: "Performance maps" };

export default function PerformanceMapsPage() {
  return (
    <DocPage slug="performance-maps">
      <Section id="what" title="What a performance map tells you">
        <p>
          The design point is one operating condition. A real machine spends
          its life everywhere else — starting up, part-load, hot days, cold
          days. The performance map is the full picture: pressure ratio and
          efficiency across a grid of shaft speeds and mass flows, bounded by
          the two cliffs every compressor lives between:
        </p>
        <ul className="ml-5 list-disc space-y-2">
          <li>
            <strong>Surge</strong> (left edge) — too little flow for the
            speed; the flow reverses violently. The map’s surge line marks
            where each speedline’s slope turns unstable.
          </li>
          <li>
            <strong>Choke</strong> (right edge) — the flow goes sonic at a
            throat and the machine physically cannot pass more mass.
          </li>
        </ul>
        <p>
          Cascade generates the map by solving the actual mean-line at every
          grid point — the same solver, the same cited loss models, the same
          validity rules as everywhere else.
        </p>
      </Section>

      <Section id="status" title="Every point carries an explicit status">
        <p>
          This is the part legacy tools get wrong: a map cell that didn’t
          converge comes back as <code className="font-mono text-[13px]">-1</code>{" "}
          or a silent gap, and you’re left guessing whether the machine
          choked, the solver diverged, or the input was nonsense. In Cascade,
          the failure surface is part of the spec — every point reports
          exactly one of eight codes:
        </p>
        <StatusCodeExplorer />
      </Section>

      <Section id="generating" title="Generating a map">
        <CodeTabs
          tabs={[
            {
              label: "Python",
              lang: "python",
              code: `import numpy as np
from cascade.perf_map import PerformanceMap, CONVERGED

# The evaluator is any callable: grid coords in, (status, outputs) out.
# In practice you call the mean-line here; this toy parabola shows the shape.
def evaluator(coords):
    m = coords["m_dot"]
    pi = -10 * (m - 0.5) ** 2 + 3
    return CONVERGED, {"pi": pi, "eta": 0.85}

map_obj = PerformanceMap.generate(
    evaluator,
    grid={
        "rpm":   np.array([50_000, 60_000, 70_000]),
        "m_dot": np.linspace(0.2, 1.0, 20),
    },
    parallel=4,                      # points solve independently
)

surge = map_obj.detect_surge_line(
    speed_axis="rpm", flow_axis="m_dot",
    pi_output="pi", pi_design=3.0, m_dot_design=0.6,
)
choke = map_obj.detect_choke_line(
    speed_axis="rpm", flow_axis="m_dot", choke_tolerance=0.01,
)

map_obj.to_csv("map.csv")
map_obj.to_json("map.json")
map_obj.to_hdf5("map.h5")            # requires h5py`,
            },
            {
              label: "HTTP",
              lang: "http",
              code: `POST /api/projects/{project_id}/map
# body: speedline rpms × mass flows → {"job_id": "..."}

GET  /api/jobs/{job_id}/events
# SSE: each solved point arrives as {"point": {...}} with its status;
# the final payload includes surge_line and choke_line arrays.`,
            },
          ]}
        />
        <p>
          In the web app, the Map page streams points into the plot as they
          solve, draws the surge and choke lines when the sweep completes,
          and renders the per-point status as both color and a legend — plus
          a table view when you’d rather read numbers than dots.
        </p>
        <Callout kind="note" title="Known gap, stated up front">
          The map currently computes from the project’s reference geometry.
          A candidate you sent to the cycle does <em>not</em> yet feed the map
          — that’s <code className="font-mono text-[13px]">KG-PLAT-03</code>{" "}
          in the{" "}
          <Link href="/docs/known-gaps" className="font-medium text-brand-text hover:underline">
            gap registry
          </Link>
          .
        </Callout>
        <TryItCard
          href="/projects/microturbine-30kw/map"
          title="Generate the 30 kW machine's map"
          body="Watch the speedlines fill in, then hover points near the edges and read their status codes."
        />
      </Section>

      <Section id="reading" title="Reading the result">
        <p>
          Keep your operating line comfortably to the right of the surge line
          — surge margin is the distance your machine has before transients
          push it over the unstable edge. Points flagged{" "}
          <code className="font-mono text-[13px]">REGIME_OUT_OF_VALIDITY</code>{" "}
          aren’t holes in Cascade; they’re corners of the map where the
          active loss correlation has no published basis, and the honest
          answer is “unknown with this model” rather than a confident-looking
          fabrication.
        </p>
        <CodeBlock
          lang="json"
          title="one map point, as the API returns it"
          code={`{
  "coords":  { "rpm": 60000, "m_dot": 0.31 },
  "outputs": { "pi": 3.92, "eta": 0.842 },
  "status":  "CONVERGED"
}`}
        />
      </Section>
    </DocPage>
  );
}
