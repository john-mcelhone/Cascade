"use client";

import { use, useCallback, useMemo, useState } from "react";
import { Download, Loader2, Play, Square } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/page-header";
import { RightRail } from "@/components/shell/right-rail";
import { Button } from "@/components/ui/button";
import { CodeLegend } from "@/components/map/code-legend";
import {
  GridSetup,
  defaultGridConfig,
  expandGrid,
  type GridConfig,
} from "@/components/map/grid-setup";
import { MapPlot } from "@/components/map/map-plot";
import { MapTable } from "@/components/map/map-table";
import { adaptMapResult, ApiError, getApiClient } from "@/lib/api/client";
import { useProject, useProjectDisplayName } from "@/lib/api/hooks";
import { useJobStream, jobEventsPath } from "@/lib/api/sse";
import type { MapPoint, MapResultBackend } from "@/lib/api/types";

interface PageProps {
  params: Promise<{ id: string }>;
}

type RunState =
  | { kind: "idle" }
  | { kind: "running"; jobId: string; progress: number; message: string }
  | { kind: "done"; jobId: string }
  | { kind: "failed"; jobId?: string; error: string };

/**
 * Performance map page. Three panes:
 *  - Left: grid configuration (mass_flow, rpm, tip_clearance) + objective.
 *  - Centre: speedline plot + sortable results table.
 *  - Right rail: code legend + run controls.
 *
 * Submits a `POST /api/projects/:id/map` job and consumes SSE progress
 * events. Final results are unpacked from the job's `result` payload (the
 * backend stamps the map output there on completion).
 */
export default function MapPage({ params }: PageProps) {
  const { id } = use(params);
  const { data: project } = useProject(id);
  const projectName = useProjectDisplayName(id);

  const [grid, setGrid] = useState<GridConfig>(defaultGridConfig);
  const [run, setRun] = useState<RunState>({ kind: "idle" });
  const [points, setPoints] = useState<MapPoint[]>([]);

  const onRun = useCallback(async () => {
    const api = getApiClient();
    const { rpms, massFlows } = expandGrid(grid);
    if (rpms.length === 0 || massFlows.length === 0) {
      toast.error("Grid is empty.", {
        description: "Set min/max/points for mass_flow and rpm.",
      });
      return;
    }
    setPoints([]);
    try {
      const accepted = await api.runMap(id, {
        speedline_rpms: rpms,
        mass_flows: massFlows,
        parallelism: 1,
      });
      setRun({
        kind: "running",
        jobId: accepted.job_id,
        progress: 0,
        message: "Queued.",
      });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : String(err);
      setRun({ kind: "failed", error: msg });
      toast.error("Failed to submit map.", { description: msg });
    }
  }, [grid, id]);

  const onCancel = useCallback(async () => {
    if (run.kind !== "running") return;
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/jobs/${run.jobId}`,
        { method: "DELETE", credentials: "include" },
      );
      if (!res.ok && res.status !== 204) {
        toast.error("Could not cancel job.");
      }
    } catch {
      toast.error("Could not reach backend to cancel.");
    }
  }, [run]);

  const sseEnabled = run.kind === "running";
  const ssePath = useMemo(
    () => (sseEnabled ? jobEventsPath(run.jobId) : undefined),
    [sseEnabled, run],
  );

  useJobStream(ssePath, {
    enabled: sseEnabled,
    onEvent: (ev) => {
      setRun((prev) =>
        prev.kind === "running"
          ? {
              ...prev,
              progress: ev.progress ?? prev.progress,
              message: ev.message ?? prev.message,
            }
          : prev,
      );
      // Per-point streaming arrives in event.data.point.
      const data = ev.data as { point?: { coords?: { rpm?: number; m_dot?: number }; outputs?: { pi?: number; eta?: number }; status?: string } } | undefined;
      if (data && data.point) {
        const single = adaptMapResult({
          axes: { rpm: [], m_dot: [] },
          points: [
            data.point as unknown as MapResultBackend["points"][0],
          ],
          surge_line: [],
          choke_line: [],
        });
        if (single.points[0]) {
          setPoints((curr) => [...curr, single.points[0]]);
        }
      }
    },
    onFinal: (ev) => {
      if (ev.status === "failed" || ev.status === "cancelled") {
        setRun({
          kind: "failed",
          jobId: ev.job_id,
          error: ev.error ?? ev.message ?? "Run failed.",
        });
        toast.error("Map run failed.", {
          description: ev.error ?? ev.message ?? "Solver did not complete.",
        });
        return;
      }
      const result = ev.result as MapResultBackend | undefined;
      if (result) {
        const adapted = adaptMapResult(result);
        setPoints(adapted.points);
      }
      setRun({ kind: "done", jobId: ev.job_id });
      toast.success("Map complete.", {
        description: `${points.length || result?.points?.length || 0} grid points returned.`,
      });
    },
    onError: () => {
      // SSE re-establishes itself; nothing to do.
    },
  });

  const running = run.kind === "running";

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        breadcrumb={[
          { label: "Projects", href: "/projects" },
          { label: projectName, href: `/projects/${id}` },
          { label: "Map" },
        ]}
        title="Performance map"
        description="Mass flow × rpm. Surge line in danger; choke line in info. Every point carries an explicit status code — no ambiguous −1s."
        actions={
          <>
            <Button
              variant="outline"
              className="gap-2"
              disabled={points.length === 0}
              onClick={() => exportCsv(points)}
            >
              <Download className="h-3 w-3" /> Export CSV
            </Button>
            {running ? (
              <Button
                variant="outline"
                className="gap-2"
                onClick={onCancel}
              >
                <Square className="h-3 w-3" /> Cancel
              </Button>
            ) : (
              <Button className="gap-2" onClick={onRun}>
                <Play className="h-3 w-3" /> Run map
              </Button>
            )}
          </>
        }
      />

      <div className="flex flex-1 overflow-hidden">
        {/* Left: grid setup */}
        <div className="w-[320px] shrink-0 overflow-auto scrollbar-subtle border-r border-border-subtle bg-surface-subtle/30 px-3 py-3">
          <GridSetup config={grid} onConfigChange={setGrid} />
        </div>

        {/* Centre: plot + table */}
        <div className="flex-1 overflow-auto scrollbar-subtle p-5">
          <div className="mb-4 h-[420px] rounded-md border border-border-subtle bg-surface-subtle/30">
            <MapPlot
              points={points}
              objective={grid.objective}
              running={running}
            />
          </div>
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
            Grid points · {points.length}
          </h3>
          <MapTable points={points} />
        </div>

        {/* Right rail */}
        <RightRail width={300}>
          <div className="flex flex-col gap-5 p-4">
            <section>
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
                Run controls
              </h3>
              <RunControlsPanel
                run={run}
                onRun={onRun}
                onCancel={onCancel}
                grid={grid}
              />
            </section>
            <section>
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
                Codes
              </h3>
              <CodeLegend />
            </section>
          </div>
        </RightRail>
      </div>
    </div>
  );
}

function RunControlsPanel({
  run,
  onRun,
  onCancel,
  grid,
}: {
  run: RunState;
  onRun: () => void;
  onCancel: () => void;
  grid: GridConfig;
}) {
  const { rpms, massFlows } = expandGrid(grid);
  const total = rpms.length * massFlows.length;

  return (
    <div className="flex flex-col gap-3 text-sm">
      <div className="rounded-md border border-border-subtle bg-surface px-3 py-2 text-xs">
        <div className="flex justify-between">
          <span className="text-text-muted">Speedlines</span>
          <span className="tabular-nums">{rpms.length}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-muted">ṁ points</span>
          <span className="tabular-nums">{massFlows.length}</span>
        </div>
        <div className="mt-1 flex justify-between border-t border-border-subtle/60 pt-1">
          <span className="text-text-muted">Total grid</span>
          <span className="tabular-nums">{total}</span>
        </div>
      </div>
      {run.kind === "running" && (
        <div className="rounded-md border border-border-subtle bg-surface px-3 py-2 text-xs">
          <div className="mb-1 flex items-center gap-2">
            <Loader2 className="h-3 w-3 animate-spin" />
            <span>{run.message}</span>
          </div>
          <div className="h-1 overflow-hidden rounded-full bg-surface-subtle">
            <div
              className="h-full bg-brand"
              style={{ width: `${Math.min(100, run.progress * 100)}%` }}
            />
          </div>
        </div>
      )}
      {run.kind === "done" && (
        <p className="text-xs text-text-muted">Last run completed.</p>
      )}
      {run.kind === "failed" && (
        <p className="text-xs text-semantic-danger-text">{run.error}</p>
      )}
      <div className="flex gap-2">
        {run.kind === "running" ? (
          <Button variant="outline" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        ) : (
          <Button size="sm" className="gap-2" onClick={onRun}>
            <Play className="h-3 w-3" /> Run map
          </Button>
        )}
      </div>
    </div>
  );
}

function exportCsv(points: MapPoint[]) {
  if (points.length === 0) return;
  const header = "rpm,mass_flow_kg_s,pi_tt,eta_tt,status";
  const rows = points.map(
    (p) =>
      `${p.rpm},${p.massFlow.toFixed(6)},${p.pi_tt.toFixed(6)},${p.eta_tt.toFixed(6)},${p.status}`,
  );
  const blob = new Blob([[header, ...rows].join("\n")], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `map-${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
