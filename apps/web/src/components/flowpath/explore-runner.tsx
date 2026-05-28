"use client";

import { useCallback, useEffect, useRef } from "react";
import { Play, Square } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useUIStore } from "@/lib/stores/ui-store";
import { useFlowPathStore } from "@/lib/flowpath/store";
import {
  BACKEND_PARAMETER_MAP,
  type ParameterDef,
} from "@/lib/flowpath/parameters";
import {
  cancelJob,
  postExplore,
  type ExploreRequestBody,
  type ServerJobEvent,
} from "@/lib/api/flowpath";
import { useEventStream, useJobPolling, jobEventsUrl } from "@/lib/api/sse";

interface ExploreRunnerProps {
  projectId: string;
}

/**
 * "Explore design space" primary button + SSE plumbing.
 *
 * On click:
 *  1. Builds an `ExploreRequest` from the parameter table (only
 *     non-frozen geometry rows contribute a sweep range).
 *  2. POSTs `/api/projects/:id/explore`.
 *  3. Opens `EventSource` on `/api/jobs/:job_id/events`.
 *  4. Appends each `candidates_batch` chunk to the Zustand store, which
 *     in turn re-renders the scatter and parallel coordinates.
 *  5. Mirrors job progress into the global `useUIStore.job` so the
 *     bottom bar shows the bar + cancel button.
 *
 * If `EventSource` is unavailable, `useJobPolling` falls back to 500 ms
 * polling on `/api/jobs/:id` — progress still flows but candidates only
 * appear on the terminal `done` event (server cache).
 */
export function ExploreRunner({ projectId }: ExploreRunnerProps) {
  const parameters = useFlowPathStore((s) => s.getParameters(projectId));
  const jobId = useFlowPathStore((s) => s.jobId);
  const jobStatus = useFlowPathStore((s) => s.jobStatus);
  const setJob = useFlowPathStore((s) => s.setJob);
  const appendCandidates = useFlowPathStore((s) => s.appendCandidates);
  const resetCandidates = useFlowPathStore((s) => s.resetCandidates);
  const setPicked = useFlowPathStore((s) => s.setPicked);
  const setGlobalJob = useUIStore((s) => s.setJob);
  const resetGlobalJob = useUIStore((s) => s.resetJob);

  const isRunning = jobStatus === "running";
  const sseUrl = jobId ? jobEventsUrl(jobId) : null;

  // Used to seed the picked candidate with the first batch we receive.
  const autoPickedRef = useRef(false);

  const onEvent = useCallback(
    (ev: ServerJobEvent) => {
      // Defensively coerce — when polling we synthesise events without `data`.
      setJob({
        progress: ev.progress,
        message: ev.message,
        status:
          ev.status === "done"
            ? "done"
            : ev.status === "failed"
              ? "failed"
              : ev.status === "cancelled"
                ? "cancelled"
                : "running",
      });
      setGlobalJob({
        id: ev.job_id,
        label: "Explore design space",
        status:
          ev.status === "done"
            ? "succeeded"
            : ev.status === "failed"
              ? "failed"
              : ev.status === "cancelled"
                ? "cancelled"
                : "running",
        progress: ev.progress,
        detail: ev.message,
        residual: null,
        iteration:
          (ev.data?.n_done as number | undefined) ?? 0,
      });

      const batch = ev.data?.candidates_batch;
      if (batch && Array.isArray(batch)) {
        appendCandidates(batch);
        if (!autoPickedRef.current && batch.length > 0) {
          autoPickedRef.current = true;
          setPicked(batch[0].id);
        }
      }

      if (ev.status === "done") {
        toast.success(
          ev.message || "Exploration complete — picked best candidate.",
        );
      } else if (ev.status === "failed") {
        toast.error(ev.message || "Exploration failed.");
      }
    },
    [appendCandidates, setGlobalJob, setJob, setPicked],
  );

  useEventStream(sseUrl, onEvent, {
    onError: () => {
      // EventSource will reconnect — no toast here unless we hit a
      // hard timeout, which is handled by the global job state.
    },
  });

  // SSE may never connect (test env, ad-blocker, missing API server).
  // The polling hook is a no-op until `jobId` is set, and once set it
  // ticks every 500 ms until the job reaches a terminal state. Both
  // streams write to the same callback so we just dedupe by `n_done`.
  useJobPolling(jobId, onEvent, 500);

  // Reset auto-pick when a new job starts.
  useEffect(() => {
    if (!jobId) autoPickedRef.current = false;
  }, [jobId]);

  const onStart = useCallback(async () => {
    autoPickedRef.current = false;
    resetCandidates();
    setJob({ jobId: null, progress: 0, status: "running", message: "Starting exploration…" });
    setGlobalJob({
      label: "Explore design space",
      status: "running",
      progress: 0,
      residual: null,
      iteration: 0,
      detail: "Submitting job…",
    });

    const body = buildExploreRequest(parameters);
    try {
      const resp = await postExplore(projectId, body);
      setJob({ jobId: resp.job_id, status: "running" });
      setGlobalJob({ id: resp.job_id, status: "running" });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(`Couldn't start exploration: ${msg}`);
      setJob({ jobId: null, status: "failed", message: msg });
      resetGlobalJob();
    }
  }, [parameters, projectId, resetCandidates, setJob, setGlobalJob, resetGlobalJob]);

  const onCancel = useCallback(async () => {
    if (!jobId) return;
    await cancelJob(jobId);
    setJob({ status: "cancelled", message: "Cancelled." });
    setGlobalJob({ status: "cancelled" });
    toast.message("Exploration cancelled.");
  }, [jobId, setJob, setGlobalJob]);

  if (isRunning) {
    return (
      <Button
        variant="outline"
        onClick={onCancel}
        className="gap-1"
        aria-label="Cancel running exploration"
      >
        <Square className="h-3 w-3" /> Cancel
      </Button>
    );
  }
  return (
    <Button
      onClick={onStart}
      className="gap-1"
      aria-label="Explore design space"
    >
      <Play className="h-3 w-3" /> Explore design space
    </Button>
  );
}

function buildExploreRequest(parameters: ParameterDef[]): ExploreRequestBody {
  const n = parameters.find((p) => p.id === "n_samples")?.value ?? 800;
  const seed = parameters.find((p) => p.id === "seed")?.value ?? 2026;
  const parallel = parameters.find((p) => p.id === "parallelism")?.value ?? 4;

  const ranges: ExploreRequestBody["parameter_ranges"] = {};
  for (const p of parameters) {
    if (p.kind !== "geometry") continue;
    if (p.frozen) continue;
    if (p.min == null || p.max == null) continue;
    const mapping = BACKEND_PARAMETER_MAP[p.id];
    if (!mapping) continue;
    const lo = mapping.toBackend(p.min);
    const hi = mapping.toBackend(p.max);
    ranges[mapping.name] = {
      min: Math.min(lo, hi),
      max: Math.max(lo, hi),
      unit: p.id === "blade_count" ? "dimensionless" : "m",
      scale: p.id === "tip_clearance" ? "log" : "linear",
    };
  }

  return {
    n_samples: Math.max(16, Math.round(n)),
    seed: Math.round(seed),
    parallelism: Math.max(1, Math.round(parallel)),
    parameter_ranges: ranges,
    primary_objective: "eta_tt",
    minimize_primary: false,
  };
}
