"use client";

import { useMemo } from "react";
import { useTheme } from "next-themes";
import type { Data, Layout } from "plotly.js";
import { Plot, defaultPlotLayout } from "@/components/plot/plotly-host";
import type { HsState } from "@/lib/api/types";

interface HsDiagramProps {
  states: HsState[];
}

/**
 * Mean-line h-s diagram (enthalpy vs entropy). Stations are plotted in
 * order with text labels and connected by lines so the user sees the path
 * the gas takes through the machine.
 *
 * Note the backend ships h in J/kg and s in J/(kg·K); we display the same
 * units, scaled to kJ for legibility.
 */
export function HsDiagram({ states }: HsDiagramProps) {
  const theme = useTheme().resolvedTheme === "dark" ? "dark" : "light";

  const { data, layout } = useMemo(() => {
    if (states.length === 0) {
      return {
        data: [] as Data[],
        layout: {
          ...defaultPlotLayout(theme),
          annotations: [
            {
              text: "Run analysis to populate.",
              x: 0.5,
              y: 0.5,
              xref: "paper",
              yref: "paper",
              showarrow: false,
              font: { size: 12 },
            },
          ],
          xaxis: {
            ...defaultPlotLayout(theme).xaxis,
            title: { text: "s [J/(kg·K)]" },
          },
          yaxis: {
            ...defaultPlotLayout(theme).yaxis,
            title: { text: "h [kJ/kg]" },
          },
        } satisfies Partial<Layout>,
      };
    }
    const xs = states.map((s) => s.s_J_per_kgK);
    const ys = states.map((s) => s.h_J_per_kg / 1000);
    const labels = states.map((s) => s.label);
    return {
      data: [
        {
          type: "scatter",
          mode: "lines+markers+text",
          x: xs,
          y: ys,
          text: labels,
          textposition: "top right",
          marker: { size: 7, color: "rgb(99, 102, 241)" },
          line: { color: "rgb(99, 102, 241)", width: 1.6 },
          name: "Mean-line stations",
          hovertemplate:
            "Station %{text}<br>s = %{x:.1f} J/(kg·K)<br>h = %{y:.1f} kJ/kg<extra></extra>",
        } as unknown as Data,
      ],
      layout: {
        ...defaultPlotLayout(theme),
        xaxis: {
          ...defaultPlotLayout(theme).xaxis,
          title: { text: "Entropy s [J/(kg·K)]" },
        },
        yaxis: {
          ...defaultPlotLayout(theme).yaxis,
          title: { text: "Enthalpy h [kJ/kg]" },
        },
      } satisfies Partial<Layout>,
    };
  }, [states, theme]);

  return <Plot data={data} layout={layout} />;
}
