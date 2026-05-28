"use client";

import * as React from "react";
import dynamic from "next/dynamic";
import type { Layout, PlotData } from "plotly.js-dist-min";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useCycleUiStore } from "./store";
import type { CycleStatePoint } from "@/lib/api/types";

// Stable module-level reference. CRITICAL: must NOT be inline as `?? []` in
// the Zustand selector below — see scatter-utils.ts for the same lesson:
// `useSyncExternalStore` re-runs the selector on every render to verify the
// snapshot, and a fresh `[]` each call is "different" by `Object.is`, which
// schedules an endless cascade of renders → "Maximum update depth exceeded".
const EMPTY_STATES: ReadonlyArray<CycleStatePoint> = Object.freeze([]);

/**
 * Plotly's bundled React wrapper imports the full `plotly.js`. We only
 * ship `plotly.js-dist-min`, so we hand-build the wrapper via its
 * factory. Dynamic import keeps the ~3 MB bundle off the server.
 */
const Plot = dynamic(
  async () => {
    const Plotly = await import("plotly.js-dist-min");
    const createPlotlyComponent = (
      await import("react-plotly.js/factory")
    ).default;
    return createPlotlyComponent(Plotly);
  },
  { ssr: false, loading: () => <DiagramSkeleton /> },
);

interface HsDiagramProps {
  /** Forces light or dark axis colors. */
  dark?: boolean;
  className?: string;
}

/**
 * Collapsible bottom drawer rendering the cycle states on a T-s
 * diagram. Lines connect adjacent states by index; markers carry the
 * stage label (1, 2, 3, …).
 *
 * Legacy desktop tools' system-simulation views do not show a live T-s
 * view on the canvas. Showing it here is a deliberate differentiator.
 */
export function HsDiagram({ dark, className }: HsDiagramProps) {
  const open = useCycleUiStore((s) => s.hsDrawerOpen);
  const setOpen = useCycleUiStore((s) => s.setHsDrawerOpen);
  const states = useCycleUiStore(
    (s) => s.run.result?.states ?? EMPTY_STATES,
  );

  const data = React.useMemo<Partial<PlotData>[]>(() => {
    if (states.length === 0) return [];
    const s = states.map((p) => p.entropy);
    const T = states.map((p) => p.temperature);
    const labels = states.map((p) => p.label);
    const hover = states.map(
      (p) =>
        `<b>${p.label}</b><br>T = ${p.temperature.toFixed(0)} K` +
        `<br>s = ${p.entropy.toFixed(2)} kJ/(kg·K)` +
        (p.pressure ? `<br>Pt = ${p.pressure.toFixed(1)} kPa` : ""),
    );
    return [
      {
        type: "scatter",
        // Plotly accepts compound mode strings at runtime.
        mode: "lines+markers+text" as PlotData["mode"],
        x: s,
        y: T,
        text: labels,
        textposition: "top right",
        textfont: { family: "JetBrains Mono, ui-monospace", size: 11 },
        marker: { size: 8, color: "rgb(45, 110, 120)" },
        line: { color: "rgb(63, 139, 150)", width: 2 },
        hovertemplate: "%{customdata}<extra></extra>",
        customdata: hover,
        name: "Cycle",
      },
    ];
  }, [states]);

  const layout = React.useMemo<Partial<Layout>>(
    () => ({
      autosize: true,
      margin: { l: 48, r: 12, t: 8, b: 36 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: {
        family: "Inter, system-ui",
        size: 11,
        color: dark ? "rgb(238, 239, 241)" : "rgb(26, 28, 33)",
      },
      xaxis: {
        title: { text: "s [kJ/(kg·K)]", standoff: 8 },
        gridcolor: dark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)",
        zerolinecolor: dark ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.15)",
      },
      yaxis: {
        title: { text: "T [K]", standoff: 8 },
        gridcolor: dark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)",
        zerolinecolor: dark ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.15)",
      },
      showlegend: false,
      hoverlabel: {
        bgcolor: dark ? "rgb(44, 48, 56)" : "rgb(255, 255, 255)",
        bordercolor: dark ? "rgb(74, 79, 88)" : "rgb(220, 222, 226)",
        font: { family: "JetBrains Mono, ui-monospace", size: 11 },
      },
    }),
    [dark],
  );

  return (
    <div
      className={cn(
        "border-t border-border-subtle bg-surface",
        className,
      )}
    >
      <div className="flex items-center justify-between px-3 py-1.5">
        <button
          type="button"
          className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-text-muted hover:text-text"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
        >
          {open ? (
            <ChevronDown className="h-3 w-3" />
          ) : (
            <ChevronUp className="h-3 w-3" />
          )}
          T - s diagram
          {states.length === 0 && (
            <span className="ml-1 text-[11px] normal-case tracking-normal text-text-muted">
              (no states yet — run the cycle)
            </span>
          )}
        </button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setOpen(!open)}
          className="text-xs"
        >
          {open ? "Hide" : "Show"}
        </Button>
      </div>
      {open && (
        <div className="h-[240px] w-full px-2 pb-2">
          {states.length === 0 ? (
            <DiagramSkeleton />
          ) : (
            <Plot
              data={data}
              layout={layout}
              config={{
                responsive: true,
                displaylogo: false,
                displayModeBar: false,
              }}
              style={{ width: "100%", height: "100%" }}
              useResizeHandler
            />
          )}
        </div>
      )}
    </div>
  );
}

function DiagramSkeleton() {
  return (
    <div className="flex h-full items-center justify-center text-xs text-text-muted">
      Loading T - s diagram…
    </div>
  );
}
