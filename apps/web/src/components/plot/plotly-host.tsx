"use client";

import dynamic from "next/dynamic";
import type { ComponentType } from "react";
import type { Config, Data, Layout, PlotMouseEvent } from "plotly.js";

/**
 * Shared dynamic Plotly mount. Pages should import `Plot` and pass `data` /
 * `layout` directly. The factory pattern below is the same one Flow Path
 * uses (lazy-loads plotly.js-dist-min on the client only) so we don't ship
 * the 4 MB bundle to SSR.
 */
export interface PlotProps {
  data: Data[];
  layout: Partial<Layout>;
  config?: Partial<Config>;
  style?: React.CSSProperties;
  className?: string;
  onClick?: (e: PlotMouseEvent) => void;
  useResizeHandler?: boolean;
}

const PlotInner: ComponentType<PlotProps> = dynamic(
  async () => {
    const factory = (await import("react-plotly.js/factory")).default;
    const plotly = await import("plotly.js-dist-min");
    // factory expects a Plotly object; the dist-min default export *is* it.
    // Cast through `any` because the dist-min module has no .d.ts shipped.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const lib = (plotly as any).default ?? plotly;
    return factory(lib) as unknown as ComponentType<PlotProps>;
  },
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full w-full items-center justify-center rounded-md border border-border-subtle bg-surface-subtle/30 text-xs text-text-muted">
        Loading plot…
      </div>
    ),
  },
);

export function Plot(props: PlotProps) {
  return (
    <PlotInner
      useResizeHandler
      style={{ width: "100%", height: "100%", ...props.style }}
      {...props}
    />
  );
}

/** Common Plotly layout defaults that match the design system. */
export function defaultPlotLayout(theme: "light" | "dark"): Partial<Layout> {
  const isDark = theme === "dark";
  return {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    margin: { l: 56, r: 16, t: 24, b: 44 },
    font: {
      family:
        "var(--font-sans), Inter, system-ui, -apple-system, BlinkMacSystemFont",
      color: isDark ? "rgb(220, 222, 226)" : "rgb(28, 32, 42)",
      size: 11,
    },
    xaxis: {
      gridcolor: isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)",
      zerolinecolor: isDark ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.12)",
      linecolor: isDark ? "rgba(255,255,255,0.18)" : "rgba(0,0,0,0.18)",
      tickfont: { size: 10 },
    },
    yaxis: {
      gridcolor: isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)",
      zerolinecolor: isDark ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.12)",
      linecolor: isDark ? "rgba(255,255,255,0.18)" : "rgba(0,0,0,0.18)",
      tickfont: { size: 10 },
    },
    legend: {
      bgcolor: "rgba(0,0,0,0)",
      font: { size: 10 },
    },
    hovermode: "closest",
  };
}
