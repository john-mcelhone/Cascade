"use client";

import { use } from "react";
import Link from "next/link";
import {
  Network,
  Wind,
  Activity,
  Grid3x3,
  Cog,
  ArrowRight,
  Play,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { PageHeader } from "@/components/shell/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel, PropertyRow } from "@/components/ui/panel";
import { CoachMark } from "@/components/coach/coach-mark";
import { useProject, useRuns } from "@/lib/api/hooks";
import { useMounted } from "@/lib/hooks/use-mounted";
import type { RunRecord } from "@/lib/api/types";
import { cn, fluidLabel, fmtNumber } from "@/lib/utils";

interface PageProps {
  params: Promise<{ id: string }>;
}

interface Stage {
  segment: string;
  label: string;
  blurb: string;
  Icon: LucideIcon;
  /** Run kinds that count as this stage having been exercised. */
  runKinds: RunRecord["kind"][];
}

/** The design pipeline, in the order a machine is actually designed. */
const STAGES: Stage[] = [
  {
    segment: "cycle",
    label: "Cycle",
    blurb: "Lay out the thermodynamic cycle and solve for thermal efficiency.",
    Icon: Network,
    runKinds: ["cycle"],
  },
  {
    segment: "flowpath",
    label: "Flow path",
    blurb:
      "Explore thousands of impeller geometries; pick one that can be made.",
    Icon: Wind,
    runKinds: ["explore"],
  },
  {
    segment: "analysis",
    label: "Analysis",
    blurb: "Mean-line losses, velocity triangles and the h–s path of a design.",
    Icon: Activity,
    runKinds: ["analysis"],
  },
  {
    segment: "map",
    label: "Map",
    blurb: "Sweep speed and flow for the performance map, surge and choke.",
    Icon: Grid3x3,
    runKinds: ["map"],
  },
  {
    segment: "rotor",
    label: "Rotor",
    blurb: "Critical speeds, Campbell, unbalance response and stability.",
    Icon: Cog,
    runKinds: ["rotor"],
  },
];

const RUN_KIND_LABEL: Record<RunRecord["kind"], string> = {
  cycle: "Cycle",
  explore: "Exploration",
  analysis: "Analysis",
  map: "Map",
  rotor: "Rotor",
};

export default function ProjectOverviewPage({ params }: PageProps) {
  const { id } = use(params);
  // Gate data on mount: the top bar shares this query, and can resolve it
  // before this segment hydrates — which would mismatch the SSR markup.
  const mounted = useMounted();
  const { data: projectData } = useProject(id);
  const { data: runsData } = useRuns(id);
  const project = mounted ? projectData : undefined;
  const runs = (mounted && runsData) || [];

  const lastRunFor = (kinds: RunRecord["kind"][]) =>
    runs
      .filter((r) => kinds.includes(r.kind))
      .sort((a, b) => b.startedAt.localeCompare(a.startedAt))[0];

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Overview"
        description="Each stage of the design is its own workspace. Work left to right, or jump straight to the one you need."
        actions={
          <Button asChild>
            <Link href={`/projects/${id}/cycle`}>
              <Play className="h-3.5 w-3.5" />
              Open cycle
            </Link>
          </Button>
        }
      />

      <div className="flex-1 overflow-auto scrollbar-subtle">
        {!project && (
          <p className="p-5 text-sm text-text-muted">Loading project…</p>
        )}

        {project && (
          <div className="mx-auto grid max-w-[1400px] gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_320px] lg:p-5">
            <div className="flex min-w-0 flex-col gap-4">
              <CoachMark
                id="project-overview"
                title="This is your project home."
              >
                A machine is designed in stages, left to right: start in{" "}
                <strong>Cycle</strong>, pick a geometry in{" "}
                <strong>Flow path</strong>, and finish in <strong>Rotor</strong>
                . The tabs along the top bar switch stages; press{" "}
                <span className="kbd">⌘K</span> to jump anywhere.
              </CoachMark>

              {/* Hero — name and description, set once, large. */}
              <div className="px-1 pt-1">
                <h2 className="text-xl font-semibold tracking-tight text-text">
                  {project.name}
                </h2>
                <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-text-muted">
                  {project.description}
                </p>
              </div>

              <Panel title="Design pipeline" meta="5 stages">
                {/* Hairline grid: 1px gaps over the border colour. */}
                <ol className="grid grid-cols-1 gap-px bg-border-subtle sm:grid-cols-2 xl:grid-cols-5">
                  {STAGES.map((s, i) => {
                    const last = lastRunFor(s.runKinds);
                    return (
                      <li
                        key={s.segment}
                        className="bg-surface last:sm:col-span-2 last:xl:col-span-1"
                      >
                        <Link
                          href={`/projects/${id}/${s.segment}`}
                          className="group flex h-full flex-col gap-3 p-4 transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-border-focus"
                        >
                          <div className="flex items-center gap-2.5">
                            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-brand-surface text-brand">
                              <s.Icon className="h-4 w-4" />
                            </span>
                            <span className="font-mono text-xs text-text-disabled">
                              {i + 1}
                            </span>
                            <ArrowRight className="ml-auto h-4 w-4 -translate-x-1 text-text-disabled opacity-0 transition-all group-hover:translate-x-0 group-hover:text-brand group-hover:opacity-100" />
                          </div>
                          <div>
                            <h3 className="text-sm font-semibold text-text">
                              {s.label}
                            </h3>
                            <p className="mt-1 text-xs leading-relaxed text-text-muted">
                              {s.blurb}
                            </p>
                          </div>
                          <StageStatus run={last} />
                        </Link>
                      </li>
                    );
                  })}
                </ol>
              </Panel>

              <Panel
                title="Recent runs"
                meta={runs.length > 0 ? `${runs.length} total` : undefined}
                actions={
                  runs.length > 0 && (
                    <Button asChild variant="ghost" size="sm">
                      <Link href={`/projects/${id}/runs`}>View all</Link>
                    </Button>
                  )
                }
              >
                {runs.length === 0 ? (
                  <div className="flex flex-col items-start gap-1 px-4 py-6">
                    <p className="text-sm text-text">No runs yet.</p>
                    <p className="text-xs text-text-muted">
                      Solve a cycle, explore a design space or run a map, and
                      every job lands here with its timing and outcome.
                    </p>
                  </div>
                ) : (
                  <ul className="divide-y divide-border-subtle">
                    {runs.slice(0, 6).map((r) => (
                      <RunRow key={r.id} run={r} />
                    ))}
                  </ul>
                )}
              </Panel>
            </div>

            {/* Inspector column */}
            <div className="flex min-w-0 flex-col gap-4">
              <Panel title={project.headline.label || "Headline"} meta="latest">
                <div className="flex items-end justify-between gap-3 px-3 py-3">
                  <div className="font-mono text-2xl font-medium tabular-nums leading-none text-text">
                    {fmtNumber(project.headline.value, { decimals: 3 })}
                    {project.headline.unit && (
                      <span className="ml-1 text-sm text-text-muted">
                        {project.headline.unit}
                      </span>
                    )}
                  </div>
                  <Sparkline values={project.sparkline} />
                </div>
              </Panel>

              <Panel title="Properties" bodyClassName="py-1.5">
                <PropertyRow label="Status">
                  <Badge variant={statusVariant(project.status)}>
                    {project.status}
                  </Badge>
                </PropertyRow>
                <PropertyRow label="Working fluid">
                  <span>{fluidLabel(project.workingFluid)}</span>
                </PropertyRow>
                <PropertyRow label="Template">{project.template}</PropertyRow>
                <PropertyRow label="Updated">
                  {fmtDate(project.updatedAt)}
                </PropertyRow>
                <PropertyRow label="Created">
                  {fmtDate(project.createdAt)}
                </PropertyRow>
                <PropertyRow label="ID" mono>
                  {project.id}
                </PropertyRow>
                <div className="px-3 pb-1.5 pt-2">
                  <Button
                    asChild
                    variant="outline"
                    size="sm"
                    className="w-full"
                  >
                    <Link href={`/projects/${id}/settings`}>
                      Project settings
                    </Link>
                  </Button>
                </div>
              </Panel>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StageStatus({ run }: { run?: RunRecord }) {
  if (!run) {
    return (
      <span className="mt-auto flex items-center gap-1.5 text-xs text-text-disabled">
        <span className="led bg-border-default" />
        Not run yet
      </span>
    );
  }
  const tone =
    run.status === "succeeded"
      ? "bg-semantic-success"
      : run.status === "failed"
        ? "bg-semantic-danger"
        : run.status === "running" || run.status === "queued"
          ? "bg-accent led-pulse"
          : "bg-semantic-warning";
  return (
    <span className="mt-auto flex items-center gap-1.5 text-xs text-text-muted">
      <span className={cn("led", tone)} />
      <span className="capitalize">{run.status}</span>
      <span className="text-text-disabled">· {timeAgo(run.startedAt)}</span>
    </span>
  );
}

function RunRow({ run }: { run: RunRecord }) {
  return (
    <li className="flex items-center gap-3 px-3 py-2 text-sm">
      <Badge
        variant={runVariant(run.status)}
        className="w-[72px] justify-center"
      >
        {run.status}
      </Badge>
      <span className="w-24 shrink-0 font-medium text-text">
        {RUN_KIND_LABEL[run.kind]}
      </span>
      <span className="min-w-0 flex-1 truncate text-text-muted">
        {run.summary ?? "—"}
      </span>
      {typeof run.durationMs === "number" && (
        <span className="hidden font-mono text-xs text-text-muted sm:inline">
          {fmtNumber(run.durationMs)} ms
        </span>
      )}
      <span className="w-20 shrink-0 text-right text-xs text-text-muted">
        {timeAgo(run.startedAt)}
      </span>
    </li>
  );
}

function statusVariant(s: string) {
  return s === "converged"
    ? "success"
    : s === "diverged"
      ? "danger"
      : s === "in-progress"
        ? "info"
        : "default";
}

function runVariant(s: RunRecord["status"]) {
  return s === "succeeded"
    ? "success"
    : s === "failed"
      ? "danger"
      : s === "cancelled"
        ? "warning"
        : "info";
}

function fmtDate(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function timeAgo(iso: string) {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "—";
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 96;
  const h = 28;
  const pts = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * w;
      const y = h - ((v - min) / range) * (h - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      aria-hidden
      className="overflow-visible"
    >
      <polyline
        fill="none"
        stroke="rgb(var(--brand-default))"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={pts}
      />
    </svg>
  );
}
