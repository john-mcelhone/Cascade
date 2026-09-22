"use client";

import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useUIStore } from "@/lib/stores/ui-store";
import { getApiClient } from "@/lib/api/client";
import { cn, fmtNumber } from "@/lib/utils";

/**
 * Status bar — 24 px, like a desktop app's. Left: solver state, and while a
 * job runs its iteration, residual, progress and a cancel. Right: whether
 * the API is reachable, and the build.
 */
export function BottomBar() {
  const job = useUIStore((s) => s.job);
  const resetJob = useUIStore((s) => s.resetJob);
  const isRunning = job.status === "running";

  return (
    <footer className="flex h-bottombar shrink-0 items-center gap-4 border-t border-border-subtle bg-surface px-3 text-[11px] text-text-muted">
      <span className="flex items-center gap-1.5">
        <span
          aria-hidden
          className={cn(
            "led",
            isRunning ? "led-pulse bg-accent" : "bg-border-strong",
          )}
        />
        <span className={isRunning ? "text-text" : undefined}>
          {isRunning ? job.label || "Solver running" : "Ready"}
        </span>
      </span>

      {isRunning && (
        <span className="flex min-w-0 items-center gap-3">
          {job.detail && <span className="truncate">{job.detail}</span>}
          {job.iteration > 0 && (
            <span className="font-mono">iter {job.iteration}</span>
          )}
          {job.residual !== null && (
            <span className="font-mono">
              res {fmtNumber(job.residual, { sigFigs: 3 })}
            </span>
          )}
          <span className="h-1 w-28 overflow-hidden rounded-full bg-border-subtle">
            <span
              className="block h-full bg-accent transition-[width] duration-base ease-out"
              style={{ width: `${Math.round((job.progress || 0) * 100)}%` }}
            />
          </span>
          <button
            type="button"
            onClick={resetJob}
            aria-label="Cancel job"
            className="flex items-center gap-1 rounded-sm px-1 hover:text-semantic-danger"
          >
            <X className="h-3 w-3" />
            Cancel
          </button>
        </span>
      )}

      <span className="ml-auto flex items-center gap-4">
        <ApiStatus />
        <span className="font-mono">v0.1.0</span>
      </span>
    </footer>
  );
}

/** Polls /api/health so a dead backend is visible at a glance, not only
 *  as a one-off toast. */
function ApiStatus() {
  const { data, isError, isPending } = useQuery({
    queryKey: ["health"],
    queryFn: () => getApiClient().health(),
    refetchInterval: 15_000,
    retry: false,
  });

  const state = isPending
    ? "checking"
    : isError || !data
      ? "offline"
      : "online";
  return (
    <span
      className="flex items-center gap-1.5"
      title={
        state === "offline"
          ? "Start the API with `make api` (port 8000)"
          : undefined
      }
    >
      <span
        aria-hidden
        className={cn(
          "led",
          state === "online" && "bg-semantic-success",
          state === "offline" && "bg-semantic-danger",
          state === "checking" && "bg-border-strong",
        )}
      />
      {state === "online"
        ? "API connected"
        : state === "offline"
          ? "API offline"
          : "Connecting…"}
    </span>
  );
}
