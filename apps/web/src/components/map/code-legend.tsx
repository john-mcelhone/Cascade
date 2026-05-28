"use client";

import { Badge } from "@/components/ui/badge";
import type { MapPoint } from "@/lib/api/types";

const CODES: Array<{
  status: MapPoint["status"];
  label: string;
  description: string;
  variant: "success" | "danger" | "info" | "warning";
}> = [
  {
    status: "ok",
    label: "ok",
    description: "Converged inside regime",
    variant: "success",
  },
  {
    status: "surge",
    label: "surge",
    description: "Below the stable mass-flow line",
    variant: "danger",
  },
  {
    status: "choke",
    label: "choke",
    description: "Above the choke mass-flow line",
    variant: "info",
  },
  {
    status: "diverged",
    label: "diverged",
    description: "Solver did not converge — no shrug, an explicit failure",
    variant: "warning",
  },
];

/**
 * Right-rail legend for the per-point status codes. Mirrors the colours used
 * in the map plot and table so the user can trace a chip to a marker.
 */
export function CodeLegend() {
  return (
    <ul className="flex flex-col gap-2">
      {CODES.map((c) => (
        <li key={c.label} className="flex items-start gap-2">
          <Badge variant={c.variant} className="shrink-0">
            {c.label}
          </Badge>
          <span className="text-xs text-text-muted">{c.description}</span>
        </li>
      ))}
    </ul>
  );
}
