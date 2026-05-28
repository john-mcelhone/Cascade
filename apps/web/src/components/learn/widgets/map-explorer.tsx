"use client";

import { useMemo, useState } from "react";
import { Plot, defaultPlotLayout } from "@/components/plot/plotly-host";
import { WidgetFrame } from "./widget-frame";
import { useTheme } from "next-themes";
import type { Data, PlotMouseEvent } from "plotly.js";

const SPEED_FRACTIONS = [0.6, 0.8, 1.0, 1.1, 1.2];

type StatusCode =
  | "CONVERGED"
  | "CHOKED"
  | "STALL_SURGE"
  | "NON_CONVERGED";

interface MapPoint {
  mdot: number;
  piTotal: number;
  speedFrac: number;
  status: StatusCode;
}

interface MapData {
  points: MapPoint[];
  surgeLine: { mdot: number[]; piTotal: number[] };
  chokeLine: { mdot: number[]; piTotal: number[] };
}

/**
 * Synthetic 5-speed centrifugal-compressor map. The math is intentionally
 * impressionistic — it just has to look like a real map (banana-shape per
 * speed, surge on the left, choke on the right).
 */
function makeSyntheticMap(): MapData {
  const points: MapPoint[] = [];
  // Surge tracking (peak π per speed) + choke tracking (right-most point).
  const surgeXs: number[] = [];
  const surgeYs: number[] = [];
  const chokeXs: number[] = [];
  const chokeYs: number[] = [];

  for (const frac of SPEED_FRACTIONS) {
    // Centre the speedline on a mass flow that scales roughly with speed.
    const mdotCenter = 0.8 + 0.7 * frac;
    const mdotMin = mdotCenter * 0.55;
    const mdotMax = mdotCenter * 1.25;
    const piPeak = 1.0 + 3.0 * frac * frac; // characteristic peak

    // Sample 11 points across the speedline.
    let surge: MapPoint | null = null;
    let choke: MapPoint | null = null;
    const speedPts: MapPoint[] = [];
    for (let i = 0; i < 11; i++) {
      const t = i / 10;
      const mdot = mdotMin + t * (mdotMax - mdotMin);
      // Parabolic dome: pi = piPeak - k*(mdot - mPeak)^2, with the peak
      // sitting at the centre of the speedline.
      const mPeak = (mdotMin + mdotMax) / 2 - 0.06;
      const k = 1.5 / ((mdotMax - mdotMin) * (mdotMax - mdotMin));
      let pi = piPeak - k * (mdot - mPeak) * (mdot - mPeak);

      // Force a steep "knee" near choke (right edge): the rightmost two
      // points fall off fast.
      const chokeDepth = Math.max(0, (mdot - mdotMax * 0.92) / 0.1);
      pi = pi - chokeDepth * 0.4;

      let status: StatusCode = "CONVERGED";
      if (i === 0) status = "STALL_SURGE";
      if (i >= 9) status = "CHOKED";
      if (i === 5 && frac === 1.1) status = "NON_CONVERGED";

      const pt: MapPoint = { mdot, piTotal: pi, speedFrac: frac, status };
      points.push(pt);
      speedPts.push(pt);
    }

    // Surge: highest π on this speedline.
    surge = speedPts.reduce((a, b) => (a.piTotal > b.piTotal ? a : b));
    surgeXs.push(surge.mdot);
    surgeYs.push(surge.piTotal);

    // Choke: rightmost CONVERGED-or-CHOKED point.
    choke = speedPts
      .filter((p) => p.status !== "NON_CONVERGED")
      .reduce((a, b) => (a.mdot > b.mdot ? a : b));
    chokeXs.push(choke.mdot);
    chokeYs.push(choke.piTotal);
  }

  return {
    points,
    surgeLine: { mdot: surgeXs, piTotal: surgeYs },
    chokeLine: { mdot: chokeXs, piTotal: chokeYs },
  };
}

// Viridis-ish ramp for speed lines (5 stops).
const VIRIDIS_5 = [
  "#440154",
  "#3B528B",
  "#21918C",
  "#5DC863",
  "#FDE725",
];

const STATUS_MARKER: Record<
  StatusCode,
  { color: string; symbol: string; label: string }
> = {
  CONVERGED: { color: "rgb(46, 135, 84)", symbol: "circle", label: "Converged" },
  CHOKED: { color: "rgb(42, 93, 170)", symbol: "diamond", label: "Choked" },
  STALL_SURGE: {
    color: "rgb(181, 52, 46)",
    symbol: "x",
    label: "Stall / surge",
  },
  NON_CONVERGED: {
    color: "rgb(122, 128, 138)",
    symbol: "square-open",
    label: "Non-converged",
  },
};

export function MapExplorer() {
  const data = useMemo(() => makeSyntheticMap(), []);
  const { resolvedTheme } = useTheme();
  const theme = resolvedTheme === "dark" ? "dark" : "light";
  const [hovered, setHovered] = useState<MapPoint | null>(null);

  const traces: Data[] = useMemo(() => {
    // Group converged points by speed for the speedlines.
    const lines: Data[] = SPEED_FRACTIONS.map((frac, i) => {
      const pts = data.points.filter(
        (p) => p.speedFrac === frac && p.status !== "NON_CONVERGED",
      );
      return {
        x: pts.map((p) => p.mdot),
        y: pts.map((p) => p.piTotal),
        mode: "lines",
        type: "scatter",
        line: { color: VIRIDIS_5[i], width: 2 },
        name: `${Math.round(frac * 100)}% N`,
        hoverinfo: "skip",
        showlegend: true,
      };
    });

    // Per-status point overlays so the legend explains the markers.
    const statusGroups: Data[] = (
      ["CONVERGED", "CHOKED", "STALL_SURGE", "NON_CONVERGED"] as StatusCode[]
    ).map((code) => {
      const pts = data.points.filter((p) => p.status === code);
      const marker = STATUS_MARKER[code];
      return {
        x: pts.map((p) => p.mdot),
        y: pts.map((p) => p.piTotal),
        mode: "markers",
        type: "scatter",
        marker: {
          color: marker.color,
          size: 8,
          symbol: marker.symbol,
          line: { color: marker.color, width: 1.5 },
        },
        name: marker.label,
        text: pts.map(
          (p) =>
            `${marker.label}<br>π_tt = ${p.piTotal.toFixed(2)}<br>ṁ_corr = ${p.mdot.toFixed(2)}<br>${Math.round(p.speedFrac * 100)}% N`,
        ),
        hovertemplate: "%{text}<extra></extra>",
      };
    });

    const surge: Data = {
      x: data.surgeLine.mdot,
      y: data.surgeLine.piTotal,
      mode: "lines",
      type: "scatter",
      line: { color: "rgb(181, 52, 46)", width: 2, dash: "dash" },
      name: "Surge line",
      hoverinfo: "skip",
    };

    const choke: Data = {
      x: data.chokeLine.mdot,
      y: data.chokeLine.piTotal,
      mode: "lines",
      type: "scatter",
      line: { color: "rgb(42, 93, 170)", width: 2, dash: "dash" },
      name: "Choke line",
      hoverinfo: "skip",
    };

    return [...lines, surge, choke, ...statusGroups];
  }, [data]);

  const layout = useMemo<Partial<import("plotly.js").Layout>>(() => {
    const base = defaultPlotLayout(theme);
    return {
      ...base,
      xaxis: {
        ...base.xaxis,
        title: { text: "Corrected mass flow, kg/s", standoff: 6 },
      },
      yaxis: {
        ...base.yaxis,
        title: { text: "Total-to-total pressure ratio π_tt", standoff: 6 },
      },
      legend: { ...base.legend, orientation: "v" as const, x: 1.02, y: 1 },
      margin: { l: 60, r: 110, t: 16, b: 48 },
    };
  }, [theme]);

  const handleClick = (e: PlotMouseEvent) => {
    const p = e.points[0];
    if (!p) return;
    const mdot = p.x as number;
    const piTotal = p.y as number;
    const match = data.points.find(
      (q) =>
        Math.abs(q.mdot - mdot) < 1e-6 && Math.abs(q.piTotal - piTotal) < 1e-6,
    );
    setHovered(match ?? null);
  };

  return (
    <WidgetFrame
      label="Performance map demo"
      caption="Synthetic 5-speed centrifugal compressor"
      onReset={() => setHovered(null)}
      bodyHeight="500px"
    >
      <div className="flex h-full flex-col p-3">
        <div className="min-h-0 flex-1 rounded-sm border border-border-subtle bg-background">
          <Plot
            data={traces}
            layout={layout}
            config={{ displayModeBar: false, responsive: true }}
            onClick={handleClick}
          />
        </div>
        <div className="mt-2 flex h-12 items-center gap-3 rounded-sm border border-border-subtle bg-surface-computed px-3 text-xs text-text-muted">
          {hovered ? (
            <>
              <span className="font-medium text-text">
                {STATUS_MARKER[hovered.status].label}
              </span>
              <span className="font-mono tabular-nums">
                π_tt = {hovered.piTotal.toFixed(2)}
              </span>
              <span className="font-mono tabular-nums">
                ṁ_corr = {hovered.mdot.toFixed(2)} kg/s
              </span>
              <span className="font-mono tabular-nums">
                N = {Math.round(hovered.speedFrac * 100)}%
              </span>
            </>
          ) : (
            <span>Click a point to see its status code and operating values.</span>
          )}
        </div>
      </div>
    </WidgetFrame>
  );
}
