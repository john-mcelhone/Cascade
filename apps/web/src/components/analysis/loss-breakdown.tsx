"use client";

import { useMemo } from "react";
import { useTheme } from "next-themes";
import type { Data, Layout } from "plotly.js";
import { Plot, defaultPlotLayout } from "@/components/plot/plotly-host";
import type { LossComponent } from "@/lib/api/types";

interface LossBreakdownProps {
  components: LossComponent[];
  /** Optional click handler — bar click pops a citation card upstream. */
  onSelectComponent?: (name: string) => void;
}

/** Horizontal bar chart of Δh contribution per loss bucket. */
export function LossBreakdown({
  components,
  onSelectComponent,
}: LossBreakdownProps) {
  const theme = useTheme().resolvedTheme === "dark" ? "dark" : "light";

  const { data, layout } = useMemo(() => {
    if (components.length === 0) {
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
            },
          ],
        } as Partial<Layout>,
      };
    }
    const sorted = [...components].sort(
      (a, b) => b.delta_h_J_per_kg - a.delta_h_J_per_kg,
    );
    const colors = sorted.map((c) => colourFor(c.name));
    return {
      data: [
        {
          type: "bar",
          orientation: "h",
          x: sorted.map((c) => c.delta_h_J_per_kg / 1000),
          y: sorted.map((c) => c.name),
          marker: { color: colors },
          hovertemplate: "%{y}: %{x:.2f} kJ/kg<extra></extra>",
        } as Data,
      ],
      layout: {
        ...defaultPlotLayout(theme),
        xaxis: {
          ...defaultPlotLayout(theme).xaxis,
          title: { text: "Δh [kJ/kg]" },
        },
        yaxis: {
          ...defaultPlotLayout(theme).yaxis,
          automargin: true,
        },
        bargap: 0.25,
      } satisfies Partial<Layout>,
    };
  }, [components, theme]);

  return (
    <Plot
      data={data}
      layout={layout}
      onClick={(e) => {
        const point = e.points?.[0];
        if (point && typeof point.y === "string") {
          onSelectComponent?.(point.y);
        }
      }}
    />
  );
}

function colourFor(name: string): string {
  const palette = [
    "rgb(99, 102, 241)",
    "rgb(244, 114, 182)",
    "rgb(34, 197, 94)",
    "rgb(250, 204, 21)",
    "rgb(20, 184, 166)",
    "rgb(248, 113, 113)",
    "rgb(125, 211, 252)",
  ];
  // Hash name to a colour index so each bucket stays the same colour across
  // runs without us having to maintain a mapping table.
  let h = 0;
  for (let i = 0; i < name.length; i++) {
    h = (h * 31 + name.charCodeAt(i)) % palette.length;
  }
  return palette[h];
}
