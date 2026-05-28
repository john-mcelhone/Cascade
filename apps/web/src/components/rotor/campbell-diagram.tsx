"use client";

import { useMemo } from "react";
import { useTheme } from "next-themes";
import type { Data, Layout } from "plotly.js";
import { Plot, defaultPlotLayout } from "@/components/plot/plotly-host";
import type { RotorCampbellPayload, RotorMode } from "@/lib/api/types";
import { MODE_COLOURS, linspace } from "./critical-speed-map";

interface CampbellDiagramProps {
  /** Real backend Campbell payload (preferred). */
  campbell?: RotorCampbellPayload;
  /** Legacy `modes` array used when the backend hasn't sent the sweep. */
  modes: RotorMode[];
  speedRangeRpm: [number, number];
}

/**
 * Campbell diagram (ADAPT-013).
 *
 * When the backend supplies the swept-eigenvalue payload (the real path),
 * each mode is drawn as a real polyline of damped frequency vs spin
 * speed. Forward-whirl modes are solid, backward-whirl modes are dashed.
 * The 1× synchronous excitation is red; 2× is orange. Critical-speed
 * crossings reported by the solver are marked with a black diamond.
 *
 * When no Campbell payload is present we fall back to the closed-form
 * shift used in the original placeholder so the UI never goes blank.
 */
export function CampbellDiagram({
  campbell,
  modes,
  speedRangeRpm,
}: CampbellDiagramProps) {
  const theme = useTheme().resolvedTheme === "dark" ? "dark" : "light";

  const { data, layout } = useMemo(() => {
    const traces: Data[] = [];

    if (campbell && campbell.modes.length > 0) {
      const rpms = campbell.speeds_rpm;
      campbell.modes.forEach((m, i) => {
        const colour = MODE_COLOURS[i % MODE_COLOURS.length];
        const isBwd = m.whirl_classification === "backward";
        traces.push({
          type: "scatter",
          mode: "lines+markers",
          name: `Mode ${i + 1} (${m.whirl_classification})`,
          x: rpms,
          y: m.frequencies_hz_at_speed.map((v) => (v == null ? null : v)),
          line: {
            color: colour,
            width: 1.6,
            dash: isBwd ? "dash" : "solid",
          },
          marker: { size: 3, color: colour },
          connectgaps: false,
        });
      });

      // 1×, 2× excitation lines.
      const eoStyles: Array<{ eo: number; colour: string; name: string }> = [
        { eo: 1, colour: "rgb(239, 68, 68)", name: "1× synchronous" },
        { eo: 2, colour: "rgb(249, 115, 22)", name: "2× harmonic" },
      ];
      for (const { eo, colour, name } of eoStyles) {
        traces.push({
          type: "scatter",
          mode: "lines",
          name,
          x: rpms,
          y: rpms.map((rpm) => (eo * rpm) / 60),
          line: { color: colour, width: 1.0, dash: "dot" },
          hoverinfo: "skip",
        });
      }

      // Critical-speed crossing markers.
      if (campbell.critical_intersections.length) {
        const xs: number[] = [];
        const ys: number[] = [];
        const txt: string[] = [];
        for (const ix of campbell.critical_intersections) {
          const f = (ix.engine_order * ix.rpm) / 60;
          xs.push(ix.rpm);
          ys.push(f);
          txt.push(
            `Crit @ ${ix.rpm.toFixed(0)} rpm (mode ${ix.mode_id + 1}, ${ix.engine_order}×)`,
          );
        }
        traces.push({
          type: "scatter",
          mode: "markers",
          name: "Critical-speed crossings",
          x: xs,
          y: ys,
          marker: {
            symbol: "diamond",
            size: 10,
            color: "rgba(0,0,0,0)",
            line: { color: "rgb(var(--text-default))", width: 1.5 },
          },
          text: txt,
          hovertemplate: "%{text}<extra></extra>",
        });
      }
    } else {
      // Fallback: ω_n shift placeholder.
      const rpms = linspace(speedRangeRpm[0], speedRangeRpm[1], 40);
      modes.forEach((m, i) => {
        const colour = MODE_COLOURS[i % MODE_COLOURS.length];
        const fwd = rpms.map(
          (rpm) => m.frequency_hz * (1 + 0.002 * (rpm / 1000)),
        );
        const bwd = rpms.map(
          (rpm) => m.frequency_hz * (1 - 0.002 * (rpm / 1000)),
        );
        traces.push({
          type: "scatter",
          mode: "lines",
          name: `Mode ${i + 1} (fwd)`,
          x: rpms,
          y: fwd,
          line: { color: colour, width: 1.4 },
        });
        traces.push({
          type: "scatter",
          mode: "lines",
          name: `Mode ${i + 1} (bwd)`,
          x: rpms,
          y: bwd,
          line: { color: colour, width: 1.4, dash: "dash" },
          showlegend: false,
        });
      });
      for (let k = 1; k <= 2; k++) {
        traces.push({
          type: "scatter",
          mode: "lines",
          name: `${k}× excitation`,
          x: rpms,
          y: rpms.map((rpm) => (k * rpm) / 60),
          line: {
            color: k === 1 ? "rgb(239, 68, 68)" : "rgb(249, 115, 22)",
            width: 0.8,
            dash: "dash",
          },
          hoverinfo: "skip",
        });
      }
    }

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
          title: { text: "Damped natural frequency [Hz]" },
        },
        showlegend: true,
        legend: {
          ...(defaultPlotLayout(theme).legend ?? {}),
          orientation: "h",
          y: -0.18,
        },
      } satisfies Partial<Layout>,
    };
  }, [campbell, modes, speedRangeRpm, theme]);

  return <Plot data={data} layout={layout} />;
}
