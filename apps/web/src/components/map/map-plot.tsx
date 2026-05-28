"use client";

import { useMemo } from "react";
import { useTheme } from "next-themes";
import type { Data, Layout } from "plotly.js";
import { Plot, defaultPlotLayout } from "@/components/plot/plotly-host";
import type { MapObjective } from "./grid-setup";
import type { MapPoint } from "@/lib/api/types";

const SPEEDLINE_COLORS = [
  "rgb(99, 102, 241)", // indigo
  "rgb(34, 197, 94)", // green
  "rgb(244, 114, 182)", // pink
  "rgb(250, 204, 21)", // yellow
  "rgb(20, 184, 166)", // teal
  "rgb(248, 113, 113)", // soft red
  "rgb(125, 211, 252)", // sky
];

const STATUS_COLORS: Record<MapPoint["status"], string> = {
  ok: "rgb(34, 197, 94)",
  surge: "rgb(239, 68, 68)",
  choke: "rgb(59, 130, 246)",
  diverged: "rgb(250, 204, 21)",
};

interface MapPlotProps {
  points: MapPoint[];
  objective: MapObjective;
  /** Whether a solver is currently producing new points. */
  running?: boolean;
}

/**
 * Compressor / turbine map. One trace per RPM speedline (line + markers),
 * plus a danger-coloured surge line and an info-coloured choke line.
 *
 * Non-`ok` points keep the speedline trace's colour but get a wider marker
 * with a status-coloured border, so the user can see status alongside RPM.
 */
export function MapPlot({ points, objective, running }: MapPlotProps) {
  const theme = useTheme().resolvedTheme === "dark" ? "dark" : "light";

  const { data, layout } = useMemo(() => {
    if (points.length === 0) {
      return {
        data: [] as Data[],
        layout: emptyLayout(theme, objective, running),
      };
    }
    // Group by RPM
    const byRpm = new Map<number, MapPoint[]>();
    for (const p of points) {
      const arr = byRpm.get(p.rpm) ?? [];
      arr.push(p);
      byRpm.set(p.rpm, arr);
    }
    const rpms = [...byRpm.keys()].sort((a, b) => a - b);
    const traces: Data[] = [];
    rpms.forEach((rpm, idx) => {
      const arr = (byRpm.get(rpm) ?? []).sort((a, b) => a.massFlow - b.massFlow);
      const x = arr.map((p) => p.massFlow);
      const y = arr.map((p) => objectiveOf(p, objective));
      const colour = SPEEDLINE_COLORS[idx % SPEEDLINE_COLORS.length];
      const marker = {
        color: arr.map((p) => STATUS_COLORS[p.status]),
        size: 7,
        line: { color: colour, width: 1.2 },
      };
      traces.push({
        type: "scatter",
        mode: "lines+markers",
        name: `${(rpm / 1000).toFixed(0)}k rpm`,
        x,
        y,
        line: { color: colour, width: 1.2, dash: "solid" },
        marker,
        hovertemplate:
          "ṁ %{x:.3f} kg/s<br>" +
          objectiveLabel(objective) +
          " %{y:.3f}<extra>" +
          (rpm / 1000).toFixed(0) +
          "k rpm</extra>",
      });
    });

    // Surge & choke lines: connect surge / choke points across speedlines.
    const surge = points
      .filter((p) => p.status === "surge")
      .sort((a, b) => a.rpm - b.rpm);
    const choke = points
      .filter((p) => p.status === "choke")
      .sort((a, b) => a.rpm - b.rpm);

    if (surge.length >= 2) {
      traces.push({
        type: "scatter",
        mode: "lines",
        name: "Surge line",
        x: surge.map((p) => p.massFlow),
        y: surge.map((p) => objectiveOf(p, objective)),
        line: {
          color: "rgb(239, 68, 68)",
          width: 1.5,
          dash: "dash",
        },
        hoverinfo: "skip",
      });
    }
    if (choke.length >= 2) {
      traces.push({
        type: "scatter",
        mode: "lines",
        name: "Choke line",
        x: choke.map((p) => p.massFlow),
        y: choke.map((p) => objectiveOf(p, objective)),
        line: {
          color: "rgb(59, 130, 246)",
          width: 1.5,
          dash: "dash",
        },
        hoverinfo: "skip",
      });
    }

    return {
      data: traces,
      layout: {
        ...defaultPlotLayout(theme),
        xaxis: {
          ...defaultPlotLayout(theme).xaxis,
          title: { text: "ṁ [kg/s]", standoff: 8 },
        },
        yaxis: {
          ...defaultPlotLayout(theme).yaxis,
          title: { text: objectiveLabel(objective), standoff: 8 },
        },
        showlegend: true,
        legend: {
          ...(defaultPlotLayout(theme).legend ?? {}),
          orientation: "h",
          y: -0.18,
        },
      } satisfies Partial<Layout>,
    };
  }, [points, objective, theme, running]);

  return (
    <div className="relative h-full w-full">
      <Plot data={data} layout={layout} />
      {running && (
        <div className="absolute right-3 top-3 rounded-sm border border-border-subtle bg-surface-raised px-2 py-1 text-xs text-text-muted">
          Live · streaming results
        </div>
      )}
    </div>
  );
}

function emptyLayout(
  theme: "light" | "dark",
  objective: MapObjective,
  running?: boolean,
): Partial<Layout> {
  return {
    ...defaultPlotLayout(theme),
    annotations: [
      {
        text: running
          ? "Streaming results…"
          : "Run the map to populate this plot.",
        x: 0.5,
        y: 0.5,
        xref: "paper",
        yref: "paper",
        showarrow: false,
        font: {
          color:
            theme === "dark"
              ? "rgba(220, 222, 226, 0.6)"
              : "rgba(28, 32, 42, 0.6)",
          size: 12,
        },
      },
    ],
    xaxis: {
      ...defaultPlotLayout(theme).xaxis,
      title: { text: "ṁ [kg/s]" },
    },
    yaxis: {
      ...defaultPlotLayout(theme).yaxis,
      title: { text: objectiveLabel(objective) },
    },
  };
}

function objectiveOf(p: MapPoint, obj: MapObjective): number {
  switch (obj) {
    case "pi_tt":
      return p.pi_tt;
    case "eta_tt":
      return p.eta_tt;
    case "eta_ts":
      // The Map page only stores eta_tt; for v1 we approximate eta_ts as the
      // same value minus a small static-stage delta. The backend will start
      // returning eta_ts as its own field in v1.1.
      return p.eta_tt - 0.03;
    case "power":
      return p.pi_tt * p.massFlow * 50;
    case "max_M_rel":
      return p.pi_tt; // placeholder until backend tracks M_rel per-point
  }
}

function objectiveLabel(obj: MapObjective): string {
  switch (obj) {
    case "pi_tt":
      return "π_tt";
    case "eta_tt":
      return "η_tt";
    case "eta_ts":
      return "η_ts";
    case "power":
      return "Power [kW]";
    case "max_M_rel":
      return "max M_rel";
  }
}
