"use client";

import { useMemo, useState } from "react";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Plot, defaultPlotLayout } from "@/components/plot/plotly-host";
import { WidgetFrame } from "./widget-frame";
import { useTheme } from "next-themes";
import type { Data } from "plotly.js";
import { cn } from "@/lib/utils";

// Air at moderate temperature; the chapter uses a closed-form Brayton with
// constant cp / gamma. We hold component isentropic efficiencies fixed at
// modestly realistic values so the default operating point lands in the
// same band as a real microturbine (η_th ≈ 26% at PR=4, TIT=1150 K, the
// Capstone C30 case) rather than the ideal 33%.
const GAMMA = 1.4;
const CP_AIR = 1004; // J/(kg·K)
const T_AMBIENT = 288; // K — ISA sea level
const P_AMBIENT = 101_325; // Pa — ISA sea level
const RECUP_EFFECTIVENESS = 0.85;
// Fixed component isentropic efficiencies. Keeping these constant makes
// the cycle "ideal-ish" — still closed-form, still purely pedagogical, but
// the numbers match what an engineer would see on a real machine.
const ETA_C = 0.86; // compressor isentropic efficiency
const ETA_T = 0.90; // turbine isentropic efficiency

interface CycleState {
  pr: number; // pressure ratio
  tit: number; // turbine inlet temperature, K
  recuperator: boolean;
}

const DEFAULT_STATE: CycleState = {
  pr: 4,
  tit: 1150,
  recuperator: false,
};

interface CycleResult {
  /** State points (1 = inlet, 2 = compressor exit, 3 = burner exit, 4 = turbine exit). */
  T: number[];
  s: number[];
  /** With recuperator: post-recuperator burner inlet + post-recuperator exhaust. */
  TRecuperated?: number;
  TRecupExhaust?: number;
  etaTh: number;
  wNet: number;
  wCompressor: number;
  wTurbine: number;
}

/**
 * Ideal Brayton cycle, constant cp/gamma.
 *
 * Stations:
 *   1 — compressor inlet
 *   2 — compressor exit
 *   3 — burner exit / turbine inlet
 *   4 — turbine exit
 *
 * With recuperator (ε = 0.85), state 2 gets pre-heated by station 4 before
 * entering the burner, so less fuel is needed for the same TIT, raising
 * thermal efficiency.
 */
function computeCycle({ pr, tit, recuperator }: CycleState): CycleResult {
  const expK = (GAMMA - 1) / GAMMA;
  const T1 = T_AMBIENT;
  const T3 = tit;

  // Isentropic exit temperatures; then deflate by component efficiencies.
  const T2s = T1 * Math.pow(pr, expK);
  const T4s = T3 * Math.pow(1 / pr, expK);
  const T2 = T1 + (T2s - T1) / ETA_C; // actual compressor exit (warmer)
  const T4 = T3 - (T3 - T4s) * ETA_T; // actual turbine exit (warmer than s)

  const wCompressor = CP_AIR * (T2 - T1);
  const wTurbine = CP_AIR * (T3 - T4);
  const wNet = wTurbine - wCompressor;

  // Heat addition: without recuperator, from T2 -> T3.
  // With recuperator, the cold side enters at T2', heated by hot side from T4.
  // T2' = T2 + ε·(T4 − T2). The hot side leaves at T5 = T4 − ε·(T4 − T2).
  let qIn = CP_AIR * (T3 - T2);
  let TRecuperated: number | undefined;
  let TRecupExhaust: number | undefined;
  if (recuperator && T4 > T2) {
    TRecuperated = T2 + RECUP_EFFECTIVENESS * (T4 - T2);
    TRecupExhaust = T4 - RECUP_EFFECTIVENESS * (T4 - T2);
    qIn = CP_AIR * (T3 - TRecuperated);
  }
  const etaTh = wNet / qIn;

  // Entropy (relative): s = cp · ln(T/T1) − R · ln(p/p1). With R = cp(γ-1)/γ.
  const R = CP_AIR * expK;
  const s = (T: number, p: number) =>
    CP_AIR * Math.log(T / T1) - R * Math.log(p / P_AMBIENT);

  const p1 = P_AMBIENT;
  const p2 = P_AMBIENT * pr;
  const p3 = p2;
  const p4 = p1;

  return {
    T: [T1, T2, T3, T4],
    s: [s(T1, p1), s(T2, p2), s(T3, p3), s(T4, p4)],
    TRecuperated,
    TRecupExhaust,
    etaTh,
    wNet,
    wCompressor,
    wTurbine,
  };
}

export function BraytonExplorer() {
  const [state, setState] = useState<CycleState>(DEFAULT_STATE);
  const { resolvedTheme } = useTheme();
  const theme = resolvedTheme === "dark" ? "dark" : "light";

  const result = useMemo(() => computeCycle(state), [state]);

  // Build the T-s trace: 1 → 2 → 3 → 4 → 1. If recuperator on, add a
  // dashed overlay showing the cold side heating up and hot side cooling.
  const traces: Data[] = useMemo(() => {
    const baseColor =
      theme === "dark" ? "rgb(159, 207, 214)" : "rgb(31, 85, 94)";
    const recupColor =
      theme === "dark" ? "rgb(213, 143, 31)" : "rgb(180, 113, 0)";
    const xs = [...result.s, result.s[0]];
    const ys = [...result.T, result.T[0]];

    const main: Data = {
      x: xs,
      y: ys,
      mode: "lines+markers",
      type: "scatter",
      line: { color: baseColor, width: 2 },
      marker: { color: baseColor, size: 8 },
      text: ["1", "2", "3", "4", ""],
      hovertemplate:
        "Station %{text}<br>T = %{y:.0f} K<br>s = %{x:.0f} J/(kg·K)<extra></extra>",
      name: "Cycle",
    };
    const labels: Data = {
      x: result.s,
      y: result.T,
      mode: "text",
      type: "scatter",
      text: ["1", "2", "3", "4"],
      textposition: "top right",
      textfont: { color: baseColor, size: 11 },
      hoverinfo: "skip",
      showlegend: false,
    };

    const out: Data[] = [main, labels];
    if (
      state.recuperator &&
      result.TRecuperated !== undefined &&
      result.TRecupExhaust !== undefined
    ) {
      // Overlay the recuperator exchange. Station 2 -> 2' (cold side heated)
      // and station 4 -> 5 (hot side cooled) — both at constant pressure.
      const recup: Data = {
        x: [result.s[1], result.s[1] + 200, result.s[3], result.s[3] - 200],
        y: [
          result.T[1],
          result.TRecuperated,
          result.T[3],
          result.TRecupExhaust,
        ],
        mode: "lines",
        type: "scatter",
        line: { color: recupColor, width: 2, dash: "dot" },
        name: `Recuperator ε=${RECUP_EFFECTIVENESS}`,
        hoverinfo: "skip",
        showlegend: true,
      };
      out.push(recup);
    }
    return out;
  }, [result, theme, state.recuperator]);

  const layout = useMemo(
    () => ({
      ...defaultPlotLayout(theme),
      xaxis: {
        ...defaultPlotLayout(theme).xaxis,
        title: { text: "Entropy s, J/(kg·K)", standoff: 6 },
      },
      yaxis: {
        ...defaultPlotLayout(theme).yaxis,
        title: { text: "Temperature T, K", standoff: 6 },
      },
      showlegend: state.recuperator,
      margin: { l: 60, r: 16, t: 16, b: 48 },
    }),
    [theme, state.recuperator],
  );

  return (
    <WidgetFrame
      label="Brayton cycle explorer"
      caption="T–s diagram, ideal cycle"
      onReset={() => setState(DEFAULT_STATE)}
      bodyHeight="500px"
    >
      <div className="grid h-full grid-cols-1 gap-3 p-3 lg:grid-cols-[1fr_220px]">
        <div className="min-h-0 rounded-sm border border-border-subtle bg-background">
          <Plot
            data={traces}
            layout={layout}
            config={{ displayModeBar: false, responsive: true }}
          />
        </div>
        <div className="flex flex-col gap-3 overflow-y-auto pr-1 scrollbar-subtle">
          <ControlRow
            label="Pressure ratio (PR)"
            value={state.pr.toFixed(1)}
          >
            <Slider
              min={Math.log(1.1)}
              max={Math.log(30)}
              step={0.01}
              value={[Math.log(state.pr)]}
              onValueChange={(v) =>
                setState((s) => ({ ...s, pr: Math.exp(v[0]) }))
              }
            />
          </ControlRow>
          <ControlRow
            label="Turbine inlet (TIT)"
            value={`${state.tit.toFixed(0)} K`}
          >
            <Slider
              min={900}
              max={1900}
              step={10}
              value={[state.tit]}
              onValueChange={(v) =>
                setState((s) => ({ ...s, tit: v[0] }))
              }
            />
          </ControlRow>
          <div className="flex items-center justify-between gap-2">
            <Label htmlFor="brayton-recup" className="text-sm">
              Recuperator
            </Label>
            <Switch
              id="brayton-recup"
              checked={state.recuperator}
              onCheckedChange={(v) =>
                setState((s) => ({ ...s, recuperator: v }))
              }
            />
          </div>
          <div className="h-px bg-border-subtle" />
          <Readout
            label="η_th"
            value={(result.etaTh * 100).toFixed(1)}
            unit="%"
            tone={result.etaTh > 0.35 ? "good" : "neutral"}
          />
          <Readout
            label="Specific work"
            value={(result.wNet / 1000).toFixed(1)}
            unit="kJ/kg"
          />
          <Readout
            label="W_compressor"
            value={(result.wCompressor / 1000).toFixed(1)}
            unit="kJ/kg"
          />
          <Readout
            label="W_turbine"
            value={(result.wTurbine / 1000).toFixed(1)}
            unit="kJ/kg"
          />
        </div>
      </div>
    </WidgetFrame>
  );
}

function ControlRow({
  label,
  value,
  children,
}: {
  label: string;
  value: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <Label className="text-sm">{label}</Label>
        <span className="font-mono text-xs tabular-nums text-text-muted">
          {value}
        </span>
      </div>
      {children}
    </div>
  );
}

function Readout({
  label,
  value,
  unit,
  tone = "neutral",
}: {
  label: string;
  value: string;
  unit: string;
  tone?: "neutral" | "good";
}) {
  return (
    <div className="flex items-baseline justify-between gap-2 rounded-sm border border-border-subtle bg-surface-computed px-2 py-1.5">
      <span className="text-xs text-text-muted">{label}</span>
      <span
        className={cn(
          "font-mono text-md tabular-nums",
          tone === "good" ? "text-semantic-success-text" : "text-text",
        )}
      >
        {value}
        <span className="ml-1 text-xs text-text-muted">{unit}</span>
      </span>
    </div>
  );
}
