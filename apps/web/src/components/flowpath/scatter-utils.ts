"use client";

import { useMemo } from "react";
import { useFlowPathStore } from "@/lib/flowpath/store";

export interface ScatterAxis {
  key: string;
  label: string;
  unit: string;
  kind: "param" | "objective";
}

const OBJECTIVE_AXES: ScatterAxis[] = [
  { key: "eta_tt", label: "η_tt", unit: "", kind: "objective" },
  { key: "eta_ts", label: "η_ts", unit: "", kind: "objective" },
  { key: "power", label: "Power", unit: "kW", kind: "objective" },
  { key: "mass", label: "Mass", unit: "kg", kind: "objective" },
  { key: "M_rel", label: "M_rel", unit: "", kind: "objective" },
];

/**
 * Build the axis dropdown list for the scatter from:
 *  - The server's objective keys (always present; see `_synthetic_evaluator`).
 *  - The geometry parameters configured for this project.
 *
 * The axes are mapped to backend names (mm → m, etc.) so they line up
 * with `ServerCandidate.params`.
 */
export function useFlowPathParameterAxes(projectId: string): ScatterAxis[] {
  // CRITICAL: do NOT use `?? []` here — that returns a brand-new array each
  // call, and Zustand's `useSyncExternalStore` re-runs the selector on every
  // render to verify the snapshot. A new reference each call means React
  // treats the snapshot as "changed" forever → infinite render loop →
  // "Maximum update depth exceeded". Call the store's pure `getParameters`
  // helper, which returns either the seeded entry or the stable module-level
  // `DEFAULT_PARAMETERS` reference.
  const params = useFlowPathStore((s) => s.getParameters(projectId));
  return useMemo(() => {
    const paramAxes: ScatterAxis[] = params
      .filter((p) => p.kind === "geometry")
      .map((p) => ({
        key: backendName(p.id),
        label: p.symbol,
        unit: p.unit,
        kind: "param" as const,
      }));
    return [...OBJECTIVE_AXES, ...paramAxes];
  }, [params]);
}

function backendName(uiId: string): string {
  // Currently 1:1 — the backend sampler uses the same parameter ids.
  return uiId;
}
