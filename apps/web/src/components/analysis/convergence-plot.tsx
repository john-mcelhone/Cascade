"use client";

import { useMemo } from "react";
import { useTheme } from "next-themes";
import type { Data, Layout } from "plotly.js";
import { Plot, defaultPlotLayout } from "@/components/plot/plotly-host";
import type { ConvergenceStep } from "@/lib/api/types";

interface ConvergencePlotProps {
  history: ConvergenceStep[];
}

/** Residual vs iteration on a semilog y. */
export function ConvergencePlot({ history }: ConvergencePlotProps) {
  const theme = useTheme().resolvedTheme === "dark" ? "dark" : "light";

  const { data, layout } = useMemo(() => {
    const xs = history.map((s) => s.iter);
    const ys = history.map((s) => Math.max(s.residual, 1e-12));
    return {
      data: [
        {
          type: "scatter",
          mode: "lines+markers",
          x: xs,
          y: ys,
          name: "‖residual‖",
          line: { color: "rgb(99, 102, 241)", width: 1.6 },
          marker: { size: 4 },
        } as Data,
      ],
      layout: {
        ...defaultPlotLayout(theme),
        xaxis: {
          ...defaultPlotLayout(theme).xaxis,
          title: { text: "Iteration" },
        },
        yaxis: {
          ...defaultPlotLayout(theme).yaxis,
          title: { text: "Residual" },
          type: "log",
        },
      } satisfies Partial<Layout>,
    };
  }, [history, theme]);

  if (history.length === 0) {
    return (
      <div className="flex h-full w-full items-center justify-center text-xs text-text-muted">
        Run analysis to see the residual history.
      </div>
    );
  }
  return <Plot data={data} layout={layout} />;
}
