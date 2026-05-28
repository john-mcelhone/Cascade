"use client";

import { useMemo, useState } from "react";
import { useTheme } from "next-themes";
import type { Data } from "plotly.js";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { Plot, defaultPlotLayout } from "@/components/plot/plotly-host";
import { WidgetFrame } from "./widget-frame";

/**
 * Chapter 4 — SpecificSpeedExplorer.
 *
 * Slide n_s from 0.2 → 5.0 on a logarithmic scale. The impeller cross
 * section morphs between three reference shapes:
 *   - n_s ≈ 0.3  → narrow radial (centrifugal compressor / RIT)
 *   - n_s ≈ 1.0  → mixed-flow
 *   - n_s ≈ 3.0  → axial, swept-back blades
 *
 * Below the impeller, a Plotly scatter of the Cordier line (the
 * dimensionless n_s · d_s pair that traces the efficiency optimum across
 * machine families — Cordier 1953). The user's operating point is shown
 * on the line so they can see which geometry family their machine belongs
 * to.
 *
 * The morph uses three SVG path strings and opacity blending — the cheap
 * trick is fine for a teaching widget and gracefully degrades without
 * shape-tween libraries.
 */

const N_S_MIN = 0.2;
const N_S_MAX = 5.0;
const DEFAULT_NS = 1.0;

// Lookup table for the Cordier "best η" line — n_s vs d_s (rad-based,
// dimensionless). Numbers drawn from Balje 1981 Tables II/III and
// Korpela 2011 §1.10; this is the canonical efficiency-optimum band.
const CORDIER_POINTS: Array<{ ns: number; ds: number }> = [
  { ns: 0.15, ds: 12.0 },
  { ns: 0.25, ds: 7.5 },
  { ns: 0.4, ds: 5.0 },
  { ns: 0.6, ds: 3.8 },
  { ns: 0.8, ds: 3.0 },
  { ns: 1.0, ds: 2.5 },
  { ns: 1.5, ds: 2.0 },
  { ns: 2.0, ds: 1.7 },
  { ns: 3.0, ds: 1.4 },
  { ns: 4.0, ds: 1.25 },
  { ns: 5.0, ds: 1.15 },
];

// Family labels along the n_s axis.
const FAMILY_BANDS = [
  { ns: 0.5, label: "Radial / centrifugal", color: "rgb(var(--chart-1))" },
  { ns: 1.5, label: "Mixed-flow", color: "rgb(var(--chart-4))" },
  { ns: 3.5, label: "Axial", color: "rgb(var(--chart-3))" },
];

// Reference machines, with their ballpark n_s on the rad-based scale.
const REFERENCE_MACHINES: Array<{ ns: number; label: string }> = [
  { ns: 0.7, label: "Turbocharger" },
  { ns: 0.9, label: "Capstone C30" },
  { ns: 2.0, label: "LM2500 (per stage)" },
  { ns: 4.5, label: "Wind turbine" },
];

export function SpecificSpeedExplorer() {
  const [ns, setNs] = useState(DEFAULT_NS);
  const { resolvedTheme } = useTheme();
  const theme = resolvedTheme === "dark" ? "dark" : "light";

  // Family weights — each shape's contribution to the morph.
  const weights = useMemo(() => weightsFor(ns), [ns]);
  const ds = useMemo(() => interpDs(ns), [ns]);
  const cordierDs = useMemo(() => interpCordierDs(ns), [ns]);

  const traces: Data[] = useMemo(() => {
    const baseColor =
      theme === "dark" ? "rgb(159, 207, 214)" : "rgb(31, 85, 94)";
    const muted =
      theme === "dark" ? "rgb(122, 128, 138)" : "rgb(122, 128, 138)";
    const cordier: Data = {
      x: CORDIER_POINTS.map((p) => p.ns),
      y: CORDIER_POINTS.map((p) => p.ds),
      mode: "lines",
      type: "scatter",
      line: { color: baseColor, width: 2 },
      name: "Cordier optimum",
      hovertemplate: "n_s = %{x:.2f}<br>d_s = %{y:.2f}<extra></extra>",
    };
    const refs: Data = {
      x: REFERENCE_MACHINES.map((r) => r.ns),
      y: REFERENCE_MACHINES.map((r) => interpCordierDs(r.ns)),
      // Plotly's "scatter" trace accepts "markers+text" at runtime but the
      // upstream typings narrow the union; safe cast.
      mode: "markers+text" as never,
      type: "scatter",
      marker: { color: muted, size: 7, symbol: "diamond" },
      text: REFERENCE_MACHINES.map((r) => r.label),
      textposition: "top right",
      textfont: { size: 10, color: muted },
      name: "Reference machines",
      hoverinfo: "skip",
    };
    const op: Data = {
      x: [ns],
      y: [cordierDs],
      mode: "markers",
      type: "scatter",
      marker: {
        color: "rgb(var(--brand-default))",
        size: 12,
        line: { color: "rgb(var(--text-inverse))", width: 1.5 },
      },
      name: "Your design",
      hovertemplate: "n_s = %{x:.2f}<br>d_s = %{y:.2f}<extra>Design point</extra>",
    };
    return [cordier, refs, op];
  }, [ns, cordierDs, theme]);

  const layout = useMemo(
    () => ({
      ...defaultPlotLayout(theme),
      xaxis: {
        ...defaultPlotLayout(theme).xaxis,
        type: "log" as const,
        title: { text: "Specific speed n_s (rad-based)", standoff: 6 },
        range: [Math.log10(0.15), Math.log10(6)],
      },
      yaxis: {
        ...defaultPlotLayout(theme).yaxis,
        type: "log" as const,
        title: { text: "Specific diameter d_s", standoff: 6 },
        range: [Math.log10(1), Math.log10(15)],
      },
      showlegend: false,
      margin: { l: 60, r: 16, t: 14, b: 50 },
    }),
    [theme],
  );

  return (
    <WidgetFrame
      label="Specific-speed explorer"
      caption="Cordier diagram, rad-based n_s"
      onReset={() => setNs(DEFAULT_NS)}
      bodyHeight="560px"
    >
      <div className="grid h-full grid-cols-1 gap-3 p-3 lg:grid-cols-[280px_1fr]">
        <div className="flex flex-col gap-3 overflow-y-auto pr-1 scrollbar-subtle">
          <div className="flex flex-col gap-1.5">
            <div className="flex items-baseline justify-between gap-2">
              <Label className="text-sm">Specific speed (n_s)</Label>
              <span className="font-mono text-xs tabular-nums text-text-muted">
                {ns.toFixed(2)}
              </span>
            </div>
            <Slider
              min={Math.log(N_S_MIN)}
              max={Math.log(N_S_MAX)}
              step={0.01}
              value={[Math.log(ns)]}
              onValueChange={(v) => setNs(Math.exp(v[0]))}
            />
            <div className="flex justify-between text-[10px] font-mono text-text-muted">
              <span>0.2</span>
              <span>1.0</span>
              <span>5.0</span>
            </div>
          </div>

          <div className="rounded-sm border border-border-subtle bg-background p-3">
            <div className="mb-2 text-[10px] uppercase tracking-wide text-text-muted">
              Impeller cross-section
            </div>
            <ImpellerMorph weights={weights} />
          </div>

          <FamilyBanner ns={ns} />

          <div className="h-px bg-border-subtle" />

          <Readout label="n_s" value={ns.toFixed(2)} unit="rad" />
          <Readout label="d_s (Cordier)" value={cordierDs.toFixed(2)} unit="" />
          <Readout
            label="d/D₀ ratio"
            value={ds.toFixed(2)}
            unit=""
          />
        </div>

        <div className="min-h-0 rounded-sm border border-border-subtle bg-background p-1">
          <Plot
            data={traces}
            layout={layout}
            config={{ displayModeBar: false, responsive: true }}
          />
        </div>
      </div>
    </WidgetFrame>
  );
}

/** Compute morph weights for the three reference shapes. */
function weightsFor(ns: number): {
  radial: number;
  mixed: number;
  axial: number;
} {
  // Soft transitions between three "anchor" points.
  const t = (x: number, a: number, b: number) =>
    Math.max(0, Math.min(1, (x - a) / (b - a)));
  // 0.2 → 0.6: pure radial
  // 0.6 → 1.4: blend to mixed-flow
  // 1.4 → 2.6: blend to axial
  // 2.6 → 5.0: pure axial
  const radial = 1 - t(ns, 0.6, 1.4);
  const axial = t(ns, 1.4, 2.6);
  const mixed = 1 - radial - axial;
  return { radial, mixed: Math.max(0, mixed), axial };
}

/** A purely-illustrative d_s curve used for the impeller width hint. */
function interpDs(ns: number): number {
  return Math.max(0.5, 2.5 - 0.4 * Math.log(ns));
}

function interpCordierDs(ns: number): number {
  // Linear interpolation on log-log over the table above.
  if (ns <= CORDIER_POINTS[0].ns) return CORDIER_POINTS[0].ds;
  if (ns >= CORDIER_POINTS[CORDIER_POINTS.length - 1].ns)
    return CORDIER_POINTS[CORDIER_POINTS.length - 1].ds;
  for (let i = 1; i < CORDIER_POINTS.length; i++) {
    const a = CORDIER_POINTS[i - 1];
    const b = CORDIER_POINTS[i];
    if (ns <= b.ns) {
      const t = (Math.log(ns) - Math.log(a.ns)) / (Math.log(b.ns) - Math.log(a.ns));
      return Math.exp(
        Math.log(a.ds) + t * (Math.log(b.ds) - Math.log(a.ds)),
      );
    }
  }
  return 1;
}

function ImpellerMorph({
  weights,
}: {
  weights: { radial: number; mixed: number; axial: number };
}) {
  return (
    <svg
      viewBox="0 0 240 160"
      className="w-full"
      role="img"
      aria-label="Impeller cross-section that morphs from radial to mixed-flow to axial as the specific-speed slider moves."
    >
      {/* Reference axis */}
      <line
        x1="20"
        y1="80"
        x2="220"
        y2="80"
        stroke="currentColor"
        strokeWidth="0.8"
        strokeDasharray="3 3"
        opacity="0.5"
      />

      {/* Radial impeller — backward-swept, large diameter, narrow channel */}
      <g style={{ opacity: weights.radial }}>
        <ellipse
          cx="120"
          cy="80"
          rx="55"
          ry="55"
          fill="rgb(var(--surface-subtle))"
          stroke="currentColor"
          strokeWidth="1.4"
        />
        {Array.from({ length: 8 }).map((_, i) => {
          const a = (i / 8) * 2 * Math.PI;
          const x1 = 120 + 12 * Math.cos(a);
          const y1 = 80 + 12 * Math.sin(a);
          const x2 = 120 + 52 * Math.cos(a - 0.45);
          const y2 = 80 + 52 * Math.sin(a - 0.45);
          return (
            <line
              key={`r-${i}`}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke="currentColor"
              strokeWidth="1.2"
            />
          );
        })}
        <circle cx="120" cy="80" r="10" fill="currentColor" />
      </g>

      {/* Mixed-flow — intermediate cone */}
      <g style={{ opacity: weights.mixed }}>
        <path
          d="M 70 30 L 170 50 L 200 110 L 90 130 Z"
          fill="rgb(var(--surface-subtle))"
          stroke="currentColor"
          strokeWidth="1.4"
        />
        {Array.from({ length: 6 }).map((_, i) => (
          <line
            key={`m-${i}`}
            x1={80 + i * 20}
            y1="35"
            x2={100 + i * 18}
            y2="125"
            stroke="currentColor"
            strokeWidth="1.2"
          />
        ))}
      </g>

      {/* Axial — long, narrow, swept-back blades */}
      <g style={{ opacity: weights.axial }}>
        <rect
          x="40"
          y="58"
          width="160"
          height="44"
          rx="3"
          fill="rgb(var(--surface-subtle))"
          stroke="currentColor"
          strokeWidth="1.4"
        />
        {Array.from({ length: 7 }).map((_, i) => (
          <g key={`a-${i}`}>
            <line
              x1={50 + i * 22}
              y1="60"
              x2={62 + i * 22}
              y2="100"
              stroke="currentColor"
              strokeWidth="1.4"
            />
          </g>
        ))}
        <line
          x1="20"
          y1="80"
          x2="40"
          y2="80"
          stroke="currentColor"
          strokeWidth="1.4"
        />
        <line
          x1="200"
          y1="80"
          x2="220"
          y2="80"
          stroke="currentColor"
          strokeWidth="1.4"
        />
      </g>

      {/* axis label */}
      <text
        x="120"
        y="152"
        textAnchor="middle"
        fontSize="9"
        fontFamily="var(--font-mono)"
        fill="rgb(var(--text-muted))"
      >
        rotation axis →
      </text>
    </svg>
  );
}

function FamilyBanner({ ns }: { ns: number }) {
  const family =
    ns < 1.0 ? FAMILY_BANDS[0] : ns < 2.2 ? FAMILY_BANDS[1] : FAMILY_BANDS[2];
  return (
    <div className="rounded-sm border border-border-subtle bg-surface-subtle/40 px-2 py-1.5 text-xs text-text-muted">
      <div className="text-[10px] uppercase tracking-wide">Geometry family</div>
      <div
        className="mt-0.5 text-sm font-medium"
        style={{ color: family.color }}
      >
        {family.label}
      </div>
    </div>
  );
}

function Readout({
  label,
  value,
  unit,
}: {
  label: string;
  value: string;
  unit: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2 rounded-sm border border-border-subtle bg-surface-computed px-2 py-1.5">
      <span className="text-xs text-text-muted">{label}</span>
      <span className="font-mono text-md tabular-nums text-text">
        {value}
        {unit && <span className="ml-1 text-xs text-text-muted">{unit}</span>}
      </span>
    </div>
  );
}
