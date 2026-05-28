"use client";

import { useMemo } from "react";
import { useTheme } from "next-themes";
import type { Data, Layout } from "plotly.js";
import { Plot, defaultPlotLayout } from "@/components/plot/plotly-host";
import type { RotorMode } from "@/lib/api/types";
import { linspace, MODE_COLOURS } from "./critical-speed-map";

interface BodePlotProps {
  modes: RotorMode[];
  speedRangeRpm: [number, number];
}

/**
 * Unbalance-response Bode plot. Magnitude is a sum of Lorentzians centred on
 * each mode's frequency, weighted by 1 / damping_ratio. The phase trace
 * shows the canonical −180° step at each resonance.
 */
export function BodePlot({ modes, speedRangeRpm }: BodePlotProps) {
  const theme = useTheme().resolvedTheme === "dark" ? "dark" : "light";

  const { data, layout } = useMemo(() => {
    const rpms = linspace(speedRangeRpm[0], speedRangeRpm[1], 240);
    const f_excite = rpms.map((rpm) => rpm / 60);

    const mag = f_excite.map((f) => {
      let acc = 0;
      for (const m of modes) {
        const zeta = Math.max(0.005, m.damping_ratio);
        const r = f / m.frequency_hz;
        const denom = Math.sqrt(
          Math.pow(1 - r * r, 2) + Math.pow(2 * zeta * r, 2),
        );
        acc += r * r / denom; // unbalance response form
      }
      return acc;
    });

    const phase = f_excite.map((f) => {
      let acc = 0;
      for (const m of modes) {
        const zeta = Math.max(0.005, m.damping_ratio);
        const r = f / m.frequency_hz;
        const ph = Math.atan2(-2 * zeta * r, 1 - r * r);
        acc += ph;
      }
      return (acc * 180) / Math.PI;
    });

    const traces: Data[] = [
      {
        type: "scatter",
        mode: "lines",
        name: "|H(jω)|",
        x: rpms,
        y: mag,
        yaxis: "y",
        line: { color: MODE_COLOURS[0], width: 1.4 },
      },
      {
        type: "scatter",
        mode: "lines",
        name: "∠H(jω)",
        x: rpms,
        y: phase,
        yaxis: "y2",
        line: { color: MODE_COLOURS[2], width: 1.4 },
      },
    ];
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
          title: { text: "Magnitude" },
          domain: [0.5, 1],
        },
        yaxis2: {
          ...defaultPlotLayout(theme).yaxis,
          title: { text: "Phase [deg]" },
          domain: [0, 0.45],
          anchor: "x",
        },
        grid: { rows: 2, columns: 1, pattern: "independent" },
        showlegend: false,
      } satisfies Partial<Layout>,
    };
  }, [modes, speedRangeRpm, theme]);

  return <Plot data={data} layout={layout} />;
}
