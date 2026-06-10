"use client";

import { use } from "react";
import Link from "next/link";
import {
  Network,
  Wind,
  Activity,
  Grid3x3,
  Cog,
  ListOrdered,
  Settings,
  ArrowUpRight,
} from "lucide-react";
import { PageHeader } from "@/components/shell/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CoachMark } from "@/components/coach/coach-mark";
import { useProject, useProjectDisplayName, useRuns } from "@/lib/api/hooks";
import type { RunRecord } from "@/lib/api/types";
import { fmtNumber } from "@/lib/utils";

interface PageProps {
  params: Promise<{ id: string }>;
}

const MODULE_CARDS = [
  {
    key: "cycle",
    label: "Cycle",
    href: (id: string) => `/projects/${id}/cycle`,
    blurb: "Drag components, connect flows, run the converged cycle.",
    Icon: Network,
  },
  {
    key: "flowpath",
    label: "Flow path",
    href: (id: string) => `/projects/${id}/flowpath`,
    blurb: "Preliminary design + design exploration with the 3D viewer.",
    Icon: Wind,
  },
  {
    key: "analysis",
    label: "Analysis",
    href: (id: string) => `/projects/${id}/analysis`,
    blurb: "1D / 2D streamline analysis with loss-model picker.",
    Icon: Activity,
  },
  {
    key: "map",
    label: "Map",
    href: (id: string) => `/projects/${id}/map`,
    blurb: "Performance map sweep across mass flow and rpm.",
    Icon: Grid3x3,
  },
  {
    key: "rotor",
    label: "Rotor",
    href: (id: string) => `/projects/${id}/rotor`,
    blurb: "Rotor-dynamics, mode shapes, Campbell and Bode.",
    Icon: Cog,
  },
  {
    key: "runs",
    label: "Runs",
    href: (id: string) => `/projects/${id}/runs`,
    blurb: "Job history with the residual log and timing.",
    Icon: ListOrdered,
  },
  {
    key: "settings",
    label: "Settings",
    href: (id: string) => `/projects/${id}/settings`,
    blurb: "Working fluid, units, members, deck export.",
    Icon: Settings,
  },
];

export default function ProjectOverviewPage({ params }: PageProps) {
  const { id } = use(params);
  const { data: project, isLoading } = useProject(id);
  const projectName = useProjectDisplayName(id);
  const { data: runs = [] } = useRuns(id);

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        breadcrumb={[
          { label: "Projects", href: "/projects" },
          { label: projectName },
        ]}
        title={project?.name ?? "Project"}
        description={project?.description}
        actions={
          project && (
            <div className="flex items-center gap-2">
              <Badge variant="default">{project.workingFluid}</Badge>
              <Badge
                variant={
                  project.status === "converged"
                    ? "success"
                    : project.status === "diverged"
                      ? "danger"
                      : "info"
                }
              >
                {project.status}
              </Badge>
            </div>
          )
        }
      />

      <div className="flex-1 overflow-auto scrollbar-subtle px-5 py-5">
        {isLoading && <p className="text-sm text-text-muted">Loading…</p>}

        {project && (
          <div className="flex flex-col gap-5">
            <CoachMark id="project-overview" title="This is your project home.">
              Each module below is a stage of the design. A typical flow runs
              left-to-right: start in <strong>Cycle</strong>, then{" "}
              <strong>Flow path</strong>, and finish in <strong>Rotor</strong>.
              You can jump anywhere — and press{" "}
              <kbd className="rounded border border-border-subtle bg-surface px-1 font-mono text-[10px]">
                ⌘K
              </kbd>{" "}
              to go straight to a tool.
            </CoachMark>

            <section>
              <h2 className="micro-label mb-2.5">Modules</h2>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                {MODULE_CARDS.map((m, i) => (
                  <Link
                    key={m.key}
                    href={m.href(id)}
                    className="group block rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
                  >
                    <Card className="flex h-full items-start gap-3 p-3.5 transition-colors duration-fast group-hover:border-border-strong">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-sm border border-brand/40 bg-brand-surface text-brand">
                        <m.Icon className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <h3 className="text-md font-semibold tracking-tight text-text group-hover:text-brand-text">
                            {m.label}
                          </h3>
                          <span className="flex items-center gap-1.5">
                            <span
                              aria-hidden
                              className="font-mono text-[10px] text-text-disabled"
                            >
                              {String(i + 1).padStart(2, "0")}
                            </span>
                            <ArrowUpRight className="h-4 w-4 -translate-x-1 text-brand opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100" />
                          </span>
                        </div>
                        <p className="mt-1 text-sm leading-relaxed text-text-muted">
                          {m.blurb}
                        </p>
                      </div>
                    </Card>
                  </Link>
                ))}
              </div>
            </section>

            <section>
              <div className="mb-2.5 flex items-end justify-between">
                <h2 className="micro-label">Recent runs</h2>
                <Link
                  href={`/projects/${id}/runs`}
                  className="text-sm text-brand-text hover:underline underline-offset-4"
                >
                  View all
                </Link>
              </div>
              <Card className="overflow-hidden">
                {runs.length === 0 ? (
                  <div className="p-4 text-sm text-text-muted">
                    No runs yet. Open a module and run something to see it
                    here.
                  </div>
                ) : (
                  <ul className="divide-y divide-border-subtle">
                    {runs.slice(0, 5).map((r) => (
                      <RunRow key={r.id} run={r} />
                    ))}
                  </ul>
                )}
              </Card>
            </section>

            <section>
              <h2 className="micro-label mb-2.5">Quick actions</h2>
              <div className="flex flex-wrap gap-2">
                <Link href={`/projects/${id}/cycle`}>
                  <Button>Run cycle</Button>
                </Link>
                <Link href={`/projects/${id}/flowpath`}>
                  <Button variant="outline">Explore design space</Button>
                </Link>
                <Link href={`/projects/${id}/map`}>
                  <Button variant="outline">Build performance map</Button>
                </Link>
              </div>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}

function RunRow({ run }: { run: RunRecord }) {
  const statusVariant =
    run.status === "succeeded"
      ? "success"
      : run.status === "failed"
        ? "danger"
        : run.status === "cancelled"
          ? "warning"
          : "info";
  const dt = new Date(run.startedAt);
  return (
    <li className="flex items-center gap-3 px-4 py-2 text-sm">
      <Badge variant={statusVariant}>{run.status}</Badge>
      <span className="font-mono text-xs text-text-muted">{run.id}</span>
      <span className="font-medium">{run.kind}</span>
      <span className="text-text-muted flex-1 truncate">
        {run.summary ?? "—"}
      </span>
      {typeof run.durationMs === "number" && (
        <span className="font-mono text-xs text-text-muted">
          {fmtNumber(run.durationMs)} ms
        </span>
      )}
      <span className="font-mono text-xs text-text-muted">
        {dt.toISOString().slice(0, 16).replace("T", " ")}
      </span>
    </li>
  );
}
