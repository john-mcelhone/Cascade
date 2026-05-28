"use client";

import Link from "next/link";
import { Plus } from "lucide-react";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";
import { useProjects } from "@/lib/api/hooks";
import type { Project } from "@/lib/api/types";
import { fmtNumber } from "@/lib/utils";
import { Folder } from "lucide-react";

export default function ProjectsPage() {
  const { data: projects, isLoading } = useProjects();

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        breadcrumb={[{ label: "Projects" }]}
        title="Projects"
        description="The cascade is where your projects live. Pick one to open the workspace, or start a new one from a template."
        actions={
          <Link href="/projects/new">
            <Button className="gap-2">
              <Plus className="h-4 w-4" />
              New project
            </Button>
          </Link>
        }
      />

      <div className="flex-1 overflow-auto scrollbar-subtle px-5 py-5">
        {isLoading && (
          <p className="text-sm text-text-muted">Loading…</p>
        )}

        {!isLoading && projects && projects.length === 0 && (
          <EmptyState
            Icon={Folder}
            title="No projects yet."
            description="Start with a microturbine template, or import a TOML deck from disk."
            action={
              <Link href="/projects/new">
                <Button>New project</Button>
              </Link>
            }
          />
        )}

        {projects && projects.length > 0 && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {projects.map((p) => (
              <ProjectCard key={p.id} project={p} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ProjectCard({ project }: { project: Project }) {
  const status = project.status;
  const statusVariant =
    status === "converged"
      ? "success"
      : status === "diverged"
        ? "danger"
        : status === "in-progress"
          ? "info"
          : "default";

  return (
    <Link
      href={`/projects/${project.id}`}
      className="group block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus rounded-md"
    >
      <Card className="flex h-full flex-col gap-3 p-4 transition-colors duration-fast group-hover:border-border-default">
        <div className="flex items-start justify-between gap-2">
          <h2 className="text-md font-medium text-text leading-tight">
            {project.name}
          </h2>
          <Badge variant={statusVariant}>{status}</Badge>
        </div>

        <p className="text-sm text-text-muted line-clamp-2">
          {project.description}
        </p>

        <div className="mt-auto flex items-end justify-between gap-3 pt-2">
          <div>
            <div className="text-xs text-text-muted">{project.headline.label}</div>
            <div className="font-mono text-lg font-medium tabular-nums">
              {fmtNumber(project.headline.value, { decimals: 3 })}
              {project.headline.unit && (
                <span className="text-sm text-text-muted ml-1">
                  {project.headline.unit}
                </span>
              )}
            </div>
          </div>
          <Sparkline values={project.sparkline} />
        </div>
      </Card>
    </Link>
  );
}

function Sparkline({ values }: { values: number[] }) {
  if (values.length === 0) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 80;
  const h = 24;
  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * w;
      const y = h - ((v - min) / range) * h;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      role="img"
      aria-label="Recent metric trend"
      className="overflow-visible"
    >
      <polyline
        fill="none"
        stroke="rgb(var(--brand-default))"
        strokeWidth="1.5"
        points={points}
      />
    </svg>
  );
}
