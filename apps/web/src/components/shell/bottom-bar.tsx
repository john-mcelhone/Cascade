"use client";

import { CircleDot, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useUIStore } from "@/lib/stores/ui-store";
import { fmtNumber } from "@/lib/utils";

/**
 * Bottom bar — 32 px tall.
 * Idle: a single subtle "Solver idle" indicator.
 * Running: label, iteration, residual, progress, cancel.
 */
export function BottomBar() {
  const job = useUIStore((s) => s.job);
  const resetJob = useUIStore((s) => s.resetJob);

  const isRunning = job.status === "running";

  return (
    <footer className="flex h-bottombar shrink-0 items-center gap-3 border-t border-border-subtle bg-surface px-3 text-xs">
      <div className="flex items-center gap-2 text-text-muted">
        {isRunning ? (
          <>
            <Loader2 className="h-3 w-3 animate-spin text-brand" />
            <span className="font-medium text-text">{job.label}</span>
            {job.detail && (
              <span className="text-text-muted">· {job.detail}</span>
            )}
            {job.residual !== null && (
              <span className="font-mono">
                · residual {fmtNumber(job.residual, { sigFigs: 3 })}
              </span>
            )}
            {job.iteration > 0 && (
              <span className="font-mono">· iter {job.iteration}</span>
            )}
          </>
        ) : (
          <>
            <CircleDot className="h-3 w-3 text-text-muted/70" />
            <span>Solver idle</span>
          </>
        )}
      </div>

      {isRunning && (
        <>
          <div className="ml-2 h-1.5 w-40 overflow-hidden rounded-full bg-surface-subtle">
            <div
              className="h-full bg-brand transition-[width] duration-base ease-out"
              style={{ width: `${Math.round((job.progress || 0) * 100)}%` }}
            />
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={resetJob}
            className="h-6 px-2 text-text-muted hover:text-semantic-danger"
            aria-label="Cancel job"
          >
            <X className="h-3 w-3" />
            Cancel
          </Button>
        </>
      )}

      <div className="ml-auto flex items-center gap-3 text-text-muted">
        <span>Cascade v0.1.0</span>
        <span aria-hidden>·</span>
        <span className="font-mono">user@local</span>
      </div>
    </footer>
  );
}
