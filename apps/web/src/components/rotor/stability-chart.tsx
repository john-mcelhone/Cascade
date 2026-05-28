"use client";

import { useMemo } from "react";
import { useTheme } from "next-themes";
import type { Data, Layout } from "plotly.js";
import { Plot, defaultPlotLayout } from "@/components/plot/plotly-host";
import type { RotorMode } from "@/lib/api/types";
import { linspace, MODE_COLOURS } from "./critical-speed-map";

interface StabilityChartProps {
  modes: RotorMode[];
  speedRangeRpm: [number, number];
}

/**
 * Log-decrement vs RPM. δ = 2π · ζ / sqrt(1 − ζ²). Negative δ means an
 * unstable mode — the page hatches that region for the user.
 */
export function StabilityChart({ modes, speedRangeRpm }: StabilityChartProps) {
  const theme = useTheme().resolvedTheme === "dark" ? "dark" : "light";

  const { data, layout } = useMemo(() => {
    const rpms = linspace(speedRangeRpm[0], speedRangeRpm[1], 30);
    const traces: Data[] = modes.map((m, i) => {
      const colour = MODE_COLOURS[i % MODE_COLOURS.length];
      // Synthetic: damping ratio falls slightly with rpm (gyroscopic flutter).
      const ys = rpms.map((rpm) => {
        const drift = 0.0008 * (rpm / 1000);
        const zeta = Math.max(0.005, m.damping_ratio - drift);
        return (2 * Math.PI * zeta) / Math.sqrt(Math.max(1e-6, 1 - zeta * zeta));
      });
      return {
        type: "scatter",
        mode: "lines+markers",
        name: `Mode ${i + 1}`,
        x: rpms,
        y: ys,
        line: { color: colour, width: 1.4 },
        marker: { size: 4, color: colour },
      };
    });
    traces.push({
      type: "scatter",
      mode: "lines",
      name: "Stable threshold",
      x: [rpms[0], rpms[rpms.length - 1]],
      y: [0, 0],
      line: {
        color: "rgb(239, 68, 68)",
        width: 0.8,
        dash: "dash",
      },
      showlegend: false,
      hoverinfo: "skip",
    });
    return {
      data: traces,
      layout: {
        ...defaultPlotLayout(theme),
        xaxis: {
          ...defaultPlotLayout(theme).xaxis,
          title: { text: "Shaft speed [rpm]" },
        },
        yaxis: {
          ...defaultPlotLayout(theme).yaxis,
          title: { text: "Log decrement δ" },
        },
        showlegend: true,
        legend: {
          ...(defaultPlotLayout(theme).legend ?? {}),
          orientation: "h",
          y: -0.18,
        },
      } satisfies Partial<Layout>,
    };
  }, [modes, speedRangeRpm, theme]);

  return <Plot data={data} layout={layout} />;
}
