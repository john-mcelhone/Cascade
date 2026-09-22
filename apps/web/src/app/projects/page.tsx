"use client";

import Link from "next/link";
import { Plus } from "lucide-react";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { WelcomeBanner } from "@/components/onboarding/welcome-banner";
import { useProjects } from "@/lib/api/hooks";
import type { Project } from "@/lib/api/types";
import { fluidLabel, fmtNumber } from "@/lib/utils";
import { useMounted } from "@/lib/hooks/use-mounted";
import { Folder } from "lucide-react";

export default function ProjectsPage() {
  // Gate data on mount so SSR markup matches the first client render (the
  // top bar's project switcher shares this query and may resolve it first).
  const mounted = useMounted();
  const { data, isLoading: loading } = useProjects();
  const projects = mounted ? data : undefined;
  const isLoading = !mounted || loading;

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Projects"
        description="Pick a project to open its workspaces, or start a new one from a template."
        actions={
          <Button asChild>
            <Link href="/projects/new">
              <Plus className="h-3.5 w-3.5" />
              New project
            </Link>
          </Button>
        }
      />

      <div className="flex-1 overflow-auto scrollbar-subtle">
        <div className="mx-auto w-full max-w-[1400px] p-4 lg:p-5">
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
              <NewProjectCard />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ProjectCard({ project }: { project: Project }) {
  const status = project.status;
  const led =
    status === "converged"
      ? "bg-semantic-success"
      : status === "diverged"
        ? "bg-semantic-danger"
        : status === "in-progress"
          ? "bg-accent"
          : "bg-border-strong";

  return (
    <Link
      href={`/projects/${project.id}`}
      className="group block rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
    >
      <Card className="flex h-full flex-col transition-[border-color,background-color] duration-fast group-hover:border-border-strong">
        <div className="flex flex-1 flex-col gap-1.5 p-4">
          <div className="flex items-center gap-2">
            <h2 className="min-w-0 flex-1 truncate text-[15px] font-semibold tracking-tight text-text">
              {project.name}
            </h2>
            <span className="flex shrink-0 items-center gap-1.5 text-xs capitalize text-text-muted">
              <span className={`led ${led}`} aria-hidden />
              {status}
            </span>
          </div>
          <p className="line-clamp-2 text-sm leading-relaxed text-text-muted">
            {project.description}
          </p>
        </div>

        <div className="flex items-end justify-between gap-3 border-t border-border-subtle px-4 py-3">
          <div className="min-w-0">
            <div className="text-xs text-text-muted">
              {project.headline.label || "No headline yet"}
            </div>
            <div className="mt-0.5 font-mono text-lg font-medium leading-tight tabular-nums text-text">
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
        <div className="flex items-center gap-2 rounded-b-md border-t border-border-subtle bg-surface-subtle px-4 py-2 text-xs text-text-muted">
          <span>{fluidLabel(project.workingFluid)}</span>
          <span className="text-text-disabled">·</span>
          <span className="truncate font-mono text-[11px]">{project.id}</span>
        </div>
      </Card>
    </Link>
  );
}

function NewProjectCard() {
  return (
    <Link
      href="/projects/new"
      className="group flex min-h-[180px] flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border-default text-text-muted transition-colors hover:border-brand/60 hover:bg-brand-surface/30 hover:text-brand-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-full bg-border-subtle transition-colors group-hover:bg-brand group-hover:text-text-inverse">
        <Plus className="h-4 w-4" />
      </span>
      <span className="text-sm font-medium">New project</span>
      <span className="text-xs text-text-muted">From a template or blank</span>
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
  if (values.length < 2) return null;
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
  const line = coords
    .map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");
  const [lastX, lastY] = coords[coords.length - 1];

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
        strokeLinecap="round"
        strokeLinejoin="round"
        points={line}
      />
      <circle cx={lastX} cy={lastY} r="2" fill="rgb(var(--brand-default))" />
    </svg>
  );
}
