"use client";

import * as React from "react";
import { Play } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getApiClient } from "@/lib/api/client";
import { useCycleUiStore } from "./store";

interface RunButtonProps {
  projectId: string;
  className?: string;
}

/**
 * Top-right Run button. While running, becomes a progress ring that
 * doubles as a cancel affordance. Pipes SSE events into the cycle store
 * so the bottom result panel and h-s diagram populate.
 */
export function RunButton({ projectId, className }: RunButtonProps) {
  const status = useCycleUiStore((s) => s.run.status);
  const progress = useCycleUiStore((s) => s.run.progress);
  const detail = useCycleUiStore((s) => s.run.detail);
  const hasUnsavedEdits = useCycleUiStore((s) => s.hasUnsavedEdits);
  const startRun = useCycleUiStore((s) => s.startRun);
  const pushRunEvent = useCycleUiStore((s) => s.pushRunEvent);
  const finishRun = useCycleUiStore((s) => s.finishRun);
  const resetRun = useCycleUiStore((s) => s.resetRun);

  const cancelRef = React.useRef(false);

  const onClick = async () => {
    if (status === "running") {
      cancelRef.current = true;
      resetRun();
      toast.message("Run cancelled.");
      return;
    }
    // B21: refuse to run while the Properties Panel form has unsaved
    // edits. The solver reads from the backend, so silently running over
    // un-flushed UI state was the #1 source of "I edited PR but the
    // result didn't change" confusion.
    if (hasUnsavedEdits) {
      toast.warning("Save your changes first", {
        description:
          "The cycle solver runs against the saved backend values, not your pending edits. Click Save in the Properties Panel, then Run again.",
      });
      return;
    }
    cancelRef.current = false;
    const api = getApiClient();
    try {
      const { jobId } = await api.solveCycle(projectId);
      startRun(jobId);
      const stream = api.streamJob(jobId);
      for await (const ev of stream) {
        if (cancelRef.current) break;
        pushRunEvent({
          progress: ev.progress,
          iteration: ev.iteration,
          residual: ev.residual,
          detail: ev.detail,
        });
        if (ev.done) {
          // Job contract: a refusal (no result produced — incomplete
          // topology, mid-solve refusal, classified bug) arrives as status
          // `failed` WITH a structured `result.failure` envelope; a
          // non-converged run arrives as `done` with `converged: false`
          // and its own envelope; an unexpected crash arrives as `failed`
          // with no envelope. We branch on the failure envelope first so
          // the FailurePanel renders for both refusals and non-convergence.
          const failure = ev.result?.failure;
          if (ev.status === "succeeded" && !failure) {
            finishRun("succeeded", ev.result);
            toast.success("Cycle converged.", {
              description: ev.result
                ? `η_th = ${ev.result.thermalEfficiency.toFixed(3)}`
                : undefined,
            });
          } else if (failure) {
            // Always stash the result so the FailurePanel can render the
            // friendly explanation + suggestions. The toast is just a
            // short cue pointing at the panel.
            finishRun("failed", ev.result);
            if (failure.kind === "bug") {
              toast.error("Software bug — see the result panel.", {
                description:
                  "Cascade hit an internal error. The result panel has the traceback and a copy button.",
              });
            } else {
              toast.warning("Cycle didn't solve — see the result panel.", {
                description: failure.title,
              });
            }
          } else {
            // Last-resort path: SSE said failed but no structured failure
            // came back. Keep the legacy toast so we don't lose the cue.
            finishRun("failed");
            toast.error("Cycle diverged.", {
              description: ev.detail ?? "Solver did not converge.",
            });
          }
        }
      }
    } catch (err) {
      finishRun("failed");
      toast.error("Run failed.", {
        description: (err as Error).message,
      });
    }
  };

  const isRunning = status === "running";

  return (
    <Button
      onClick={onClick}
      className={cn("gap-2", className)}
      variant={isRunning ? "subtle" : "default"}
      aria-label={isRunning ? "Cancel run" : "Run cycle"}
    >
      {isRunning ? (
        <ProgressRing value={progress} />
      ) : (
        <Play className="h-3.5 w-3.5" />
      )}
      <span>{isRunning ? "Cancel" : "Run cycle"}</span>
      {isRunning && detail && (
        <span className="ml-1 font-mono text-[11px] text-text-muted">
          {detail}
        </span>
      )}
    </Button>
  );
}

function ProgressRing({ value }: { value: number }) {
  const r = 6;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - Math.max(0, Math.min(value, 1)));
  return (
    <svg
      width={16}
      height={16}
      viewBox="0 0 16 16"
      className="text-text-inverse"
      aria-hidden="true"
    >
      <circle
        cx={8}
        cy={8}
        r={r}
        fill="none"
        stroke="currentColor"
        strokeOpacity={0.25}
        strokeWidth={2}
      />
      <circle
        cx={8}
        cy={8}
        r={r}
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeDasharray={c}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform="rotate(-90 8 8)"
      />
    </svg>
  );
}
