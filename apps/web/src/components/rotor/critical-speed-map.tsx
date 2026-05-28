"use client";

import { useMemo } from "react";
import { useTheme } from "next-themes";
import type { Data, Layout } from "plotly.js";
import { Plot, defaultPlotLayout } from "@/components/plot/plotly-host";
import type { RotorCriticalSpeedMapPayload, RotorMode } from "@/lib/api/types";

interface CriticalSpeedMapProps {
  /** Real backend critical-speed-map payload (preferred). */
  csm?: RotorCriticalSpeedMapPayload;
  /** Legacy `modes` array used when no payload is present. */
  modes?: RotorMode[];
  /** Bearing stiffness sweep range [N/m] — defaults to four decades around 1e7. */
  stiffnessRange?: [number, number];
}

/**
 * Critical-speed map (ADAPT-013).
 *
 * When the backend supplies a swept-stiffness payload we plot each of the
 * first ~6 modes as a real polyline f(K), with a vertical reference line
 * at the user's chosen operating K. Otherwise we fall back to the
 * closed-form Lorentzian asymptote so the panel never goes blank.
 */
export function CriticalSpeedMap({
  csm,
  modes,
  stiffnessRange = [1e5, 1e9],
}: CriticalSpeedMapProps) {
  const theme = useTheme().resolvedTheme === "dark" ? "dark" : "light";

  const { data, layout } = useMemo(() => {
    const traces: Data[] = [];

    if (csm && csm.modes.length > 0) {
      csm.modes.forEach((m, i) => {
        const colour = MODE_COLOURS[i % MODE_COLOURS.length];
        traces.push({
          type: "scatter",
          mode: "lines+markers",
          name: `Mode ${m.mode_id + 1}`,
          x: csm.stiffness_n_per_m,
          y: m.frequencies_hz_at_stiffness.map((v) => (v == null ? null : v)),
          line: { color: colour, width: 1.6 },
          marker: { size: 3, color: colour },
          connectgaps: false,
        });
      });
      if (csm.operating_K_n_per_m && csm.operating_K_n_per_m > 0) {
        // Compute y-range from the data so the vertical line spans the plot.
        const ys = csm.modes
          .flatMap((m) => m.frequencies_hz_at_stiffness)
          .filter((v): v is number => v != null && Number.isFinite(v));
        const yLo = ys.length ? Math.min(...ys) * 0.95 : 0;
        const yHi = ys.length ? Math.max(...ys) * 1.05 : 1;
        traces.push({
          type: "scatter",
          mode: "lines",
          name: `Operating K (${csm.operating_K_n_per_m.toExponential(2)} N/m)`,
          x: [csm.operating_K_n_per_m, csm.operating_K_n_per_m],
          y: [yLo, yHi],
          line: { color: "rgb(var(--brand-default))", width: 1.2, dash: "dash" },
          hoverinfo: "skip",
        });
      }
    } else if (modes && modes.length) {
      const ks = logspace(stiffnessRange[0], stiffnessRange[1], 40);
      modes.forEach((m, i) => {
        const f_modal = m.frequency_hz;
        const f_rigid = f_modal * 0.15 * (1 + i * 0.15);
        const k_corner = 5e6 * (i + 1);
        const ys = ks.map((K) => {
          const ratio = K / k_corner;
          return f_rigid + (f_modal - f_rigid) * (ratio / (1 + ratio));
        });
        traces.push({
          type: "scatter",
          mode: "lines",
          name: `Mode ${i + 1} · ${m.shape_name}`,
          x: ks,
          y: ys,
          line: { color: MODE_COLOURS[i % MODE_COLOURS.length], width: 1.5 },
        });
      });
    }

    return {
      data: traces,
      layout: {
        ...defaultPlotLayout(theme),
        xaxis: {
          ...defaultPlotLayout(theme).xaxis,
          type: "log",
          title: { text: "Bearing stiffness K [N/m]" },
        },
        yaxis: {
          ...defaultPlotLayout(theme).yaxis,
          title: { text: "Natural frequency [Hz]" },
        },
        showlegend: true,
        legend: {
          ...(defaultPlotLayout(theme).legend ?? {}),
          orientation: "v",
        },
      } satisfies Partial<Layout>,
    };
  }, [csm, modes, stiffnessRange, theme]);

  return <Plot data={data} layout={layout} />;
}

export const MODE_COLOURS = [
  "rgb(99, 102, 241)",
  "rgb(34, 197, 94)",
  "rgb(244, 114, 182)",
  "rgb(250, 204, 21)",
  "rgb(20, 184, 166)",
  "rgb(248, 113, 113)",
];

export function logspace(lo: number, hi: number, n: number): number[] {
  const logLo = Math.log10(lo);
  const logHi = Math.log10(hi);
  return Array.from({ length: n }, (_, i) =>
    Math.pow(10, logLo + ((logHi - logLo) * i) / (n - 1)),
  );
}

export function linspace(lo: number, hi: number, n: number): number[] {
  return Array.from({ length: n }, (_, i) => lo + ((hi - lo) * i) / (n - 1));
}
