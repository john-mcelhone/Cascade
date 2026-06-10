"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useUIStore } from "@/lib/stores/ui-store";
import { useMounted } from "@/lib/hooks/use-mounted";
import { fmtNumber } from "@/lib/utils";

/**
 * Bottom bar — a 28 px status ticker, segmented by hairlines.
 * Left: solver LED + state; running jobs show iteration, residual, progress,
 * cancel. Right: build, UTC clock, identity — all in mono.
 */
export function BottomBar() {
  const job = useUIStore((s) => s.job);
  const resetJob = useUIStore((s) => s.resetJob);

  const isRunning = job.status === "running";

  return (
    <footer className="flex h-bottombar shrink-0 items-stretch border-t border-border-subtle bg-surface text-xs">
      {/* Solver segment */}
      <div className="flex items-center gap-2 border-r border-border-subtle px-3">
        <span
          className={
            isRunning
              ? "led led-pulse bg-accent"
              : "led bg-border-strong"
          }
          aria-hidden
        />
        <span className="micro-label !text-text-subtle">
          {isRunning ? "Solver running" : "Solver idle"}
        </span>
      </div>

      {isRunning && (
        <div className="flex items-center gap-3 border-r border-border-subtle px-3">
          <span className="font-medium text-text">{job.label}</span>
          {job.detail && <span className="text-text-muted">{job.detail}</span>}
          {job.iteration > 0 && (
            <span className="font-mono text-text-muted">
              iter {job.iteration}
            </span>
          )}
          {job.residual !== null && (
            <span className="font-mono text-text-muted">
              res {fmtNumber(job.residual, { sigFigs: 3 })}
            </span>
          )}
          <div className="h-1 w-32 overflow-hidden rounded-full bg-surface-subtle">
            <div
              className="h-full bg-accent transition-[width] duration-base ease-out"
              style={{ width: `${Math.round((job.progress || 0) * 100)}%` }}
            />
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={resetJob}
            className="h-5 px-1.5 text-text-muted hover:text-semantic-danger"
            aria-label="Cancel job"
          >
            <X className="h-3 w-3" />
            Cancel
          </Button>
        </div>
      )}

      <div className="ml-auto flex items-stretch">
        <span className="flex items-center border-l border-border-subtle px-3 font-mono text-text-muted">
          v0.1.0
        </span>
        <UtcClock />
        <span className="flex items-center border-l border-border-subtle px-3 font-mono text-text-muted">
          user@local
        </span>
      </div>
    </footer>
  );
}

/** Live UTC readout — instrument chrome; renders a placeholder until mounted
 *  so SSR markup matches. */
function UtcClock() {
  const mounted = useMounted();
  const [now, setNow] = useState("");

  useEffect(() => {
    if (!mounted) return;
    const tick = () =>
      setNow(new Date().toISOString().slice(11, 19));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [mounted]);

  return (
    <span className="hidden items-center gap-1.5 border-l border-border-subtle px-3 font-mono text-text-muted sm:flex">
      <span data-numeric>{mounted && now ? now : "--:--:--"}</span>
      <span className="text-[10px] text-text-disabled">UTC</span>
    </span>
  );
}
