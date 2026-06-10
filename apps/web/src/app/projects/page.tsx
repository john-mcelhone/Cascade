"use client";

import Link from "next/link";
import { Plus } from "lucide-react";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";
import { WelcomeBanner } from "@/components/onboarding/welcome-banner";
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
        <WelcomeBanner />

        {isLoading && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <ProjectCardSkeleton key={i} />
            ))}
          </div>
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
      className="group block rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
    >
      <Card className="flex h-full flex-col overflow-hidden transition-colors duration-fast group-hover:border-border-strong">
        {/* Panel header strip — mono ID + status chip */}
        <div className="flex items-center justify-between gap-2 border-b border-border-subtle bg-surface-subtle px-3 py-1.5">
          <span className="truncate font-mono text-[10px] text-text-muted">
            {project.id}
          </span>
          <Badge variant={statusVariant}>{status}</Badge>
        </div>

        <div className="flex flex-1 flex-col gap-2 p-3">
          <h2 className="text-md font-semibold leading-tight tracking-tight text-text group-hover:text-brand-text">
            {project.name}
          </h2>
          <p className="line-clamp-2 text-sm leading-relaxed text-text-muted">
            {project.description}
          </p>

          <div className="mt-auto flex items-end justify-between gap-3 border-t border-border-subtle pt-2.5">
            <div>
              <div className="micro-label">{project.headline.label}</div>
              <div className="font-mono text-lg font-medium tabular-nums text-brand-text">
                {fmtNumber(project.headline.value, { decimals: 3 })}
                {project.headline.unit && (
                  <span className="ml-1 text-sm text-text-muted">
                    {project.headline.unit}
                  </span>
                )}
              </div>
            </div>
            <Sparkline values={project.sparkline} />
          </div>
        </div>
      </Card>
    </Link>
  );
}

function ProjectCardSkeleton() {
  return (
    <Card className="flex h-full flex-col gap-3 p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="h-4 w-32 animate-pulse rounded bg-surface-subtle" />
        <div className="h-4 w-16 animate-pulse rounded bg-surface-subtle" />
      </div>
      <div className="space-y-1.5">
        <div className="h-3 w-full animate-pulse rounded bg-surface-subtle" />
        <div className="h-3 w-3/4 animate-pulse rounded bg-surface-subtle" />
      </div>
      <div className="mt-auto flex items-end justify-between border-t border-border-subtle pt-3">
        <div className="h-7 w-24 animate-pulse rounded bg-surface-subtle" />
        <div className="h-6 w-20 animate-pulse rounded bg-surface-subtle" />
      </div>
    </Card>
  );
}

function Sparkline({ values }: { values: number[] }) {
  if (values.length === 0) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 88;
  const h = 26;
  const coords = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - ((v - min) / range) * (h - 3) - 1.5;
    return [x, y] as const;
  });
  const line = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `0,${h} ${line} ${w},${h}`;
  const [lastX, lastY] = coords[coords.length - 1];
  const gradId = `spark-${Math.round(min)}-${Math.round(max)}-${values.length}`;

  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      role="img"
      aria-label="Recent metric trend"
      className="overflow-visible"
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgb(var(--brand-default))" stopOpacity="0.22" />
          <stop offset="100%" stopColor="rgb(var(--brand-default))" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={area} fill={`url(#${gradId})`} />
      <polyline
        fill="none"
        stroke="rgb(var(--brand-default))"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={line}
      />
      <circle cx={lastX} cy={lastY} r="2" fill="rgb(var(--brand-default))" />
    </svg>
  );
}
