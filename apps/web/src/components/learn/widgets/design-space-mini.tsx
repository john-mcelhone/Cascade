"use client";

import { useEffect, useMemo, useState } from "react";
import { Plot } from "@/components/plot/plotly-host";
import { WidgetFrame } from "./widget-frame";
import { cn } from "@/lib/utils";

const SAMPLE_OPTIONS = [32, 64, 128, 256, 512, 1024, 2048];

interface Candidate {
  /** Sobol index. */
  i: number;
  /** Rotor outlet radius, m. */
  outletRadius: number;
  /** Total-to-total efficiency, dimensionless. */
  effTT: number;
  /** Maximum relative Mach number anywhere on the rotor. */
  maxMrel: number;
  /** Blade count. */
  bladeCount: number;
  /** Tip speed, m/s. */
  tipSpeed: number;
  /** Specific speed, dimensionless. */
  nS: number;
}

/**
 * DesignSpaceMini — a smaller, embedded version of the Flow Path scatter.
 *
 * Self-contained: a deterministic 2D Sobol-like sequence over four
 * parameters, scored by a smooth synthetic fitness function. The user
 * slides `n_samples` and the scatter fills; they slide a `max_M_rel`
 * threshold and infeasible points grey out; they click a point and a
 * wireframe impeller preview appears below.
 */
export function DesignSpaceMini({ className }: { className?: string }) {
  const [nSamples, setNSamples] = useState(256);
  const [maxMrelThreshold, setMaxMrelThreshold] = useState(1.2);
  const [picked, setPicked] = useState<Candidate | null>(null);

  // Generate the entire candidate set deterministically.
  const candidates = useMemo(() => {
    return generateCandidates(2048);
  }, []);

  const visible = useMemo(() => candidates.slice(0, nSamples), [candidates, nSamples]);

  // Feasible / infeasible split — feasibility is `maxMrel < threshold`.
  const feasible = visible.filter((c) => c.maxMrel < maxMrelThreshold);
  const infeasible = visible.filter((c) => c.maxMrel >= maxMrelThreshold);

  // Default-pick the best feasible candidate at first render.
  useEffect(() => {
    if (picked === null && feasible.length > 0) {
      const best = feasible.reduce((a, b) => (b.effTT > a.effTT ? b : a));
      setPicked(best);
    }
  }, [feasible, picked]);

  // Re-pick if the current pick falls out of the visible set.
  useEffect(() => {
    if (picked && !visible.find((c) => c.i === picked.i)) {
      const next = feasible.length > 0 ? feasible[0] : visible[0] ?? null;
      setPicked(next);
    }
  }, [visible, feasible, picked]);

  return (
    <WidgetFrame
      label="DesignSpaceMini"
      caption="Sobol' sampling · synthetic fitness"
      openHref="/projects/microturbine-30kw/flowpath"
      onReset={() => {
        setNSamples(256);
        setMaxMrelThreshold(1.2);
        setPicked(null);
      }}
      bodyHeight="520px"
      className={className}
    >
      <div className="flex h-full flex-col gap-3 p-3">
        {/* Controls */}
        <div className="flex flex-col gap-2 text-xs">
          <div className="flex items-center gap-3">
            <label className="w-28 shrink-0 font-medium text-text" htmlFor="ds-mini-n">
              n_samples
            </label>
            <input
              id="ds-mini-n"
              type="range"
              min={0}
              max={SAMPLE_OPTIONS.length - 1}
              step={1}
              value={SAMPLE_OPTIONS.indexOf(nSamples)}
              onChange={(e) =>
                setNSamples(SAMPLE_OPTIONS[Number(e.target.value)])
              }
              className="flex-1 accent-[rgb(var(--brand-default))]"
            />
            <span className="w-16 text-right font-mono tabular-nums text-text">
              {nSamples}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <label className="w-28 shrink-0 font-medium text-text" htmlFor="ds-mini-m">
              max_M_rel ≤
            </label>
            <input
              id="ds-mini-m"
              type="range"
              min={1.0}
              max={2.0}
              step={0.05}
              value={maxMrelThreshold}
              onChange={(e) => setMaxMrelThreshold(Number(e.target.value))}
              className="flex-1 accent-[rgb(var(--brand-default))]"
            />
            <span className="w-16 text-right font-mono tabular-nums text-text">
              {maxMrelThreshold.toFixed(2)}
            </span>
          </div>
          <div className="flex justify-between font-mono text-[10px] text-text-muted tabular-nums">
            <span>
              feasible: {feasible.length} / {visible.length}
              <span className="ml-1 opacity-50">
                ({((feasible.length / Math.max(1, visible.length)) * 100).toFixed(0)}%)
              </span>
            </span>
            {picked && <span>#{picked.i} picked</span>}
          </div>
        </div>

        {/* Scatter */}
        <div className="min-h-[180px] flex-1">
          <Plot
            data={[
              {
                type: "scattergl",
                mode: "markers",
                x: infeasible.map((c) => c.outletRadius * 1000),
                y: infeasible.map((c) => c.effTT),
                marker: {
                  size: 5,
                  color: "rgb(var(--chart-8))",
                  opacity: 0.3,
                  line: { width: 0 },
                },
                customdata: infeasible.map((c) => [c.i, c.maxMrel.toFixed(2)]),
                hovertemplate:
                  "<b>#%{customdata[0]}</b><br>r₂ = %{x:.2f} mm<br>η_tt = %{y:.3f}<br>max M_rel = %{customdata[1]}<extra>infeasible</extra>",
                name: "infeasible",
                showlegend: false,
              },
              {
                type: "scattergl",
                mode: "markers",
                x: feasible.map((c) => c.outletRadius * 1000),
                y: feasible.map((c) => c.effTT),
                marker: {
                  size: 6,
                  color: feasible.map((c) => c.maxMrel),
                  colorscale: VIRIDIS,
                  cmin: 0.6,
                  cmax: maxMrelThreshold,
                  colorbar: {
                    title: { text: "M_rel", font: { size: 10 } },
                    thickness: 8,
                    len: 0.7,
                    tickfont: { size: 9 },
                  },
                  line: { width: 0 },
                },
                customdata: feasible.map((c) => [c.i, c.maxMrel.toFixed(2)]),
                hovertemplate:
                  "<b>#%{customdata[0]}</b><br>r₂ = %{x:.2f} mm<br>η_tt = %{y:.3f}<br>max M_rel = %{customdata[1]}<extra>feasible</extra>",
                name: "feasible",
                showlegend: false,
              },
              ...(picked
                ? [
                    {
                      type: "scattergl" as const,
                      mode: "markers" as const,
                      x: [picked.outletRadius * 1000],
                      y: [picked.effTT],
                      marker: {
                        size: 14,
                        color: "rgba(0,0,0,0)",
                        line: {
                          color: "rgb(var(--brand-default))",
                          width: 2,
                        },
                      },
                      hoverinfo: "skip" as const,
                      showlegend: false,
                    },
                  ]
                : []),
            ]}
            layout={{
              autosize: true,
              margin: { l: 50, r: 30, t: 8, b: 40 },
              dragmode: "pan",
              hovermode: "closest",
              xaxis: {
                title: { text: "rotor outlet radius r₂ (mm)", font: { size: 10 } },
                tickfont: { size: 9 },
                showgrid: true,
                gridcolor: "rgba(125,125,125,0.12)",
                zeroline: false,
              },
              yaxis: {
                title: { text: "η_tt", font: { size: 10 } },
                tickfont: { size: 9 },
                showgrid: true,
                gridcolor: "rgba(125,125,125,0.12)",
                zeroline: false,
              },
              paper_bgcolor: "transparent",
              plot_bgcolor: "transparent",
              font: { family: "var(--font-sans), Inter, sans-serif" },
            }}
            config={{
              displaylogo: false,
              responsive: true,
              modeBarButtonsToRemove: [
                "lasso2d",
                "select2d",
                "autoScale2d",
                "toggleSpikelines",
              ],
            }}
            style={{ width: "100%", height: "100%" }}
            useResizeHandler
            onClick={(ev) => {
              if (!ev || !ev.points || ev.points.length === 0) return;
              const pt = ev.points[0];
              const data = pt.customdata as unknown as
                | [number, string]
                | undefined;
              if (!data) return;
              const cand = visible.find((c) => c.i === data[0]);
              if (cand) setPicked(cand);
            }}
          />
        </div>

        {/* Picked-candidate inspector */}
        {picked && (
          <div className="flex items-stretch gap-3 rounded-md border border-border-subtle bg-surface-subtle/60 p-3">
            <ImpellerWireframe
              outletRadius={picked.outletRadius}
              bladeCount={picked.bladeCount}
              tipSpeed={picked.tipSpeed}
            />
            <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs leading-tight">
              <dt className="text-text-muted">candidate</dt>
              <dd className="font-mono tabular-nums text-text">#{picked.i}</dd>
              <dt className="text-text-muted">r₂</dt>
              <dd className="font-mono tabular-nums text-text">
                {(picked.outletRadius * 1000).toFixed(2)} mm
              </dd>
              <dt className="text-text-muted">η_tt</dt>
              <dd className="font-mono tabular-nums text-text">
                {picked.effTT.toFixed(4)}
              </dd>
              <dt className="text-text-muted">max M_rel</dt>
              <dd className="font-mono tabular-nums text-text">
                {picked.maxMrel.toFixed(3)}
              </dd>
              <dt className="text-text-muted">Z_blade</dt>
              <dd className="font-mono tabular-nums text-text">{picked.bladeCount}</dd>
              <dt className="text-text-muted">U_tip</dt>
              <dd className="font-mono tabular-nums text-text">
                {picked.tipSpeed.toFixed(0)} m/s
              </dd>
              <dt className="text-text-muted">n_s</dt>
              <dd className="font-mono tabular-nums text-text">
                {picked.nS.toFixed(2)}
              </dd>
            </dl>
          </div>
        )}
      </div>
    </WidgetFrame>
  );
}

/* ----------------------------- helpers ----------------------------- */

function generateCandidates(n: number): Candidate[] {
  const out: Candidate[] = [];
  for (let i = 1; i <= n; i++) {
    const u1 = vdc(i, 2);
    const u2 = vdc(i, 3);
    const u3 = vdc(i, 5);
    const u4 = vdc(i, 7);

    // Parameter ranges (rough microturbine scale):
    const outletRadius = 0.018 + u1 * 0.022; // 18 → 40 mm
    const ratio = 1.6 + u2 * 1.2; // inlet / outlet radius
    const bladeCount = 8 + Math.floor(u3 * 12); // 8..19
    const rpm = 70000 + u4 * 50000; // 70k..120k rpm
    const tipSpeed = (rpm * 2 * Math.PI) / 60 * (outletRadius * ratio);

    // Synthetic efficiency: peaks at moderate radius, falls off with high Mach.
    const baseEff = 0.86 - 0.18 * Math.pow(outletRadius * 1000 - 27, 2) / 144;
    const bladeCountBonus = 0.018 * Math.exp(-Math.pow(bladeCount - 13, 2) / 16);
    const ratioBonus = 0.012 * Math.exp(-Math.pow(ratio - 2.2, 2) / 0.4);
    // Speed-of-sound at design inlet ~340 m/s
    const maxMrel = tipSpeed / 290 + 0.05 * u3 - 0.05;
    const machPenalty = Math.max(0, (maxMrel - 1.0) * 0.04);
    const effTT = Math.max(
      0.55,
      Math.min(0.92, baseEff + bladeCountBonus + ratioBonus - machPenalty),
    );

    const nS =
      ((rpm * 2 * Math.PI) / 60) *
      Math.sqrt(0.31 / 1.2) / Math.pow(28000, 0.75);

    out.push({
      i,
      outletRadius,
      effTT,
      maxMrel,
      bladeCount,
      tipSpeed,
      nS,
    });
  }
  return out;
}

// Van der Corput sequence in base b — the building block of Halton / Sobol.
function vdc(n: number, base: number): number {
  let q = 0;
  let bk = 1 / base;
  while (n > 0) {
    q += (n % base) * bk;
    n = Math.floor(n / base);
    bk /= base;
  }
  return q;
}

// Cascade-ish viridis sampled to ~10 stops.
const VIRIDIS: [number, string][] = [
  [0, "#440154"],
  [0.11, "#482878"],
  [0.22, "#3e4989"],
  [0.33, "#31688e"],
  [0.44, "#26828e"],
  [0.55, "#1f9e89"],
  [0.66, "#35b779"],
  [0.77, "#6ece58"],
  [0.88, "#b5de2b"],
  [1.0, "#fde725"],
];

function ImpellerWireframe({
  outletRadius,
  bladeCount,
}: {
  outletRadius: number;
  bladeCount: number;
  tipSpeed: number;
}) {
  // SVG end-view of an impeller — a circle with `bladeCount` curved blades.
  const size = 96;
  const cx = size / 2;
  const cy = size / 2;
  const rOuter = (size / 2) * 0.85;
  const rInner = rOuter * 0.35;

  // Each blade is drawn as a B-spline-like curve from inner radius outward.
  const blades = [];
  for (let k = 0; k < bladeCount; k++) {
    const theta0 = (k / bladeCount) * 2 * Math.PI;
    const parts = [];
    const N = 8;
    for (let i = 0; i <= N; i++) {
      const t = i / N;
      const r = rInner + (rOuter - rInner) * t;
      // back-sweep: outlet blade angle ~35°
      const sweep = 0.6 * t;
      const theta = theta0 + sweep;
      const x = cx + r * Math.cos(theta);
      const y = cy + r * Math.sin(theta);
      parts.push(`${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`);
    }
    blades.push(parts.join(" "));
  }

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={`Wireframe impeller, ${bladeCount} blades, outlet radius ${(outletRadius * 1000).toFixed(0)} mm`}
      className={cn("h-24 w-24 shrink-0 text-text")}
    >
      <circle
        cx={cx}
        cy={cy}
        r={rOuter}
        fill="none"
        stroke="currentColor"
        strokeOpacity={0.4}
        strokeWidth={0.6}
      />
      <circle
        cx={cx}
        cy={cy}
        r={rInner}
        fill="none"
        stroke="currentColor"
        strokeOpacity={0.4}
        strokeWidth={0.6}
      />
      {blades.map((d, k) => (
        <path
          key={k}
          d={d}
          fill="none"
          stroke="rgb(var(--brand-default))"
          strokeWidth={1}
          strokeLinecap="round"
        />
      ))}
      <circle cx={cx} cy={cy} r={2} fill="currentColor" opacity={0.4} />
    </svg>
  );
}
