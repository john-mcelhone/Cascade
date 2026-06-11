"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Interactive reference for the eight performance-map point status codes
 * (SPEC_SHEET §13). Click a code to read what it means, what the solver
 * observed, and what to do about it. The list mirrors
 * `cascade.perf_map` — these are the exact strings the API returns.
 */

type Tone = "success" | "warning" | "danger" | "info";

interface StatusInfo {
  code: string;
  tone: Tone;
  meaning: string;
  detected: string;
  action: string;
}

const STATUS_CODES: StatusInfo[] = [
  {
    code: "CONVERGED",
    tone: "success",
    meaning: "The solver found a solution and every output is in physical range.",
    detected:
      "The residual dropped below tolerance within the iteration budget, and outputs passed the plausibility checks.",
    action: "Nothing — this is the good one. The point's outputs are trustworthy.",
  },
  {
    code: "CHOKED",
    tone: "warning",
    meaning: "The flow reached sonic conditions at a throat — the machine cannot pass more mass flow.",
    detected: "Throat Mach number reached 1, or mass flow saturated as back-pressure dropped.",
    action:
      "Expected at the right edge of every speedline. If your operating point lands here, you need a bigger throat or less flow.",
  },
  {
    code: "STALL_SURGE",
    tone: "warning",
    meaning: "The point sits on the unstable side of the map, where the speedline slope turns positive.",
    detected:
      "A positive-slope speedline segment, or the mean-line solver raised an explicit stall flag.",
    action:
      "Expected at the left edge of every speedline. Keep your operating line to the right of the surge line with margin.",
  },
  {
    code: "NON_CONVERGED",
    tone: "danger",
    meaning: "The solver ran out of iterations with the residual still above tolerance.",
    detected: "Iteration limit hit; the answer never settled.",
    action:
      "Treat the outputs as unusable. Often a sign the point is near a physical boundary — refine the grid around it.",
  },
  {
    code: "INVALID_GEOMETRY",
    tone: "danger",
    meaning: "The geometry itself is impossible — before any flow physics ran.",
    detected:
      "A geometric constraint failed, e.g. hub radius exceeding tip radius, or non-positive blade height.",
    action: "Fix the geometry. The solver refuses to evaluate impossible shapes.",
  },
  {
    code: "REGIME_OUT_OF_VALIDITY",
    tone: "danger",
    meaning:
      "The point falls outside the published validity envelope of the active loss model.",
    detected:
      "A validity check on the loss correlation failed — for example, relative Mach beyond the correlated range.",
    action:
      "Cascade refuses to extrapolate a correlation past its published range. Use a loss model that covers the regime, or accept that the corner of the map is unknowable with this model.",
  },
  {
    code: "TIMEOUT",
    tone: "danger",
    meaning: "The per-point wall-clock budget ran out.",
    detected: "The point's evaluation exceeded its time limit and was cancelled.",
    action:
      "Re-run with a smaller grid or looser tolerance. Frequent timeouts on a region usually mean the physics there is genuinely stiff.",
  },
  {
    code: "INFEASIBLE_BC",
    tone: "danger",
    meaning: "The boundary conditions contradict each other — no flow could satisfy them.",
    detected: "A consistency check failed, e.g. outlet pressure above inlet pressure for a turbine.",
    action: "Fix the boundary conditions; the point was never evaluated.",
  },
];

const TONE_CHIP: Record<Tone, string> = {
  success:
    "border-semantic-success-border bg-semantic-success-surface text-semantic-success-text",
  warning:
    "border-semantic-warning-border bg-semantic-warning-surface text-semantic-warning-text",
  danger:
    "border-semantic-danger-border bg-semantic-danger-surface text-semantic-danger-text",
  info: "border-semantic-info-border bg-semantic-info-surface text-semantic-info-text",
};

export function StatusCodeExplorer({ className }: { className?: string }) {
  const [selected, setSelected] = useState(0);
  const info = STATUS_CODES[selected];

  return (
    <figure
      className={cn(
        "w-full overflow-hidden rounded-md border border-border-subtle bg-surface-raised",
        className,
      )}
    >
      <header className="flex items-baseline gap-2 border-b border-border-subtle bg-surface-subtle/60 px-3 py-2">
        <span className="text-xs font-medium uppercase tracking-wide text-text-muted">
          Explorer
        </span>
        <span className="text-sm font-medium text-text">
          The eight map point status codes
        </span>
      </header>

      <div className="flex flex-col gap-3 p-3">
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Status codes">
          {STATUS_CODES.map((s, i) => (
            <button
              key={s.code}
              role="tab"
              aria-selected={i === selected}
              onClick={() => setSelected(i)}
              className={cn(
                "rounded-sm border px-2 py-1 font-mono text-[11px] font-medium transition-all duration-fast",
                TONE_CHIP[s.tone],
                i === selected
                  ? "ring-1 ring-border-focus"
                  : "opacity-60 hover:opacity-100",
              )}
            >
              {s.code}
            </button>
          ))}
        </div>

        <div className="flex flex-col gap-2.5 rounded-sm border border-border-subtle bg-surface px-3.5 py-3">
          <p className="text-sm font-medium text-text">{info.meaning}</p>
          <div className="grid gap-2.5 sm:grid-cols-2">
            <div>
              <div className="text-[11px] font-medium uppercase tracking-wide text-text-muted">
                How it’s detected
              </div>
              <p className="mt-0.5 text-sm leading-relaxed text-text-subtle">
                {info.detected}
              </p>
            </div>
            <div>
              <div className="text-[11px] font-medium uppercase tracking-wide text-text-muted">
                What to do
              </div>
              <p className="mt-0.5 text-sm leading-relaxed text-text-subtle">
                {info.action}
              </p>
            </div>
          </div>
        </div>

        <p className="text-xs text-text-muted">
          Legacy tools return <code className="font-mono">-1</code> and let you
          wonder. Every Cascade map point carries exactly one of these codes —
          the failure surface is part of the spec (SPEC_SHEET §13).
        </p>
      </div>
    </figure>
  );
}
