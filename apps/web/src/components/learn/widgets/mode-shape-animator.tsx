"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Plot, defaultPlotLayout } from "@/components/plot/plotly-host";
import { WidgetFrame } from "./widget-frame";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { useTheme } from "next-themes";
import type { Data, Layout } from "plotly.js";
import { cn } from "@/lib/utils";

type ModeIdx = 1 | 2 | 3;

const CRITICAL_SPEEDS = [3000, 12000, 27000]; // rpm
const RPM_MIN = 0;
const RPM_MAX = 35000;
const MODE_LABELS: Record<ModeIdx, string> = {
  1: "Mode 1 — bending",
  2: "Mode 2 — S-shape",
  3: "Mode 3 — W-shape",
};

const AMPLITUDE = 16; // SVG pixels of vertical deflection at peak

/**
 * Animated rotor mode-shape illustration + Bode response plot.
 *
 * Chapter 8 widget implementation:
 *   y(x, t) = A · sin(n·π·x/L) · sin(2π·t)
 * Animated via requestAnimationFrame at 1 Hz.
 *
 * The Bode plot synthesises a 2-DOF response that picks up the three
 * critical speeds; the user drags a vertical RPM cursor to see magnitude
 * and phase at that operating speed.
 */
export function ModeShapeAnimator() {
  const [mode, setMode] = useState<ModeIdx>(1);
  const [rpm, setRpm] = useState(15000);
  const svgPathRef = useRef<SVGPathElement | null>(null);
  const tStartRef = useRef<number | null>(null);
  const { resolvedTheme } = useTheme();
  const theme = resolvedTheme === "dark" ? "dark" : "light";

  // Animation loop: redraw the rotor centreline path every frame.
  useEffect(() => {
    let raf = 0;
    const tick = (now: number) => {
      if (tStartRef.current === null) tStartRef.current = now;
      const t = (now - tStartRef.current) / 1000; // seconds
      const path = svgPathRef.current;
      if (path) {
        path.setAttribute("d", buildModeShapePath(mode, t));
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [mode]);

  // Bode magnitude + phase across RPM.
  const bode = useMemo(() => {
    const rpms: number[] = [];
    const mags: number[] = [];
    const phases: number[] = [];
    for (let r = 0; r <= RPM_MAX; r += 100) {
      const omega = (r / 60) * 2 * Math.PI;
      // Sum 3 weakly-damped modes; each peak at its critical speed.
      let realSum = 0;
      let imagSum = 0;
      for (let i = 0; i < 3; i++) {
        const omegaN = (CRITICAL_SPEEDS[i] / 60) * 2 * Math.PI;
        const zeta = 0.04 + 0.02 * i; // a bit more damping at higher modes
        const beta = omega / omegaN;
        const denomR = 1 - beta * beta;
        const denomI = 2 * zeta * beta;
        const norm = denomR * denomR + denomI * denomI;
        // Per-mode magnitude with unit forcing amplitude.
        const realM = denomR / norm;
        const imagM = -denomI / norm;
        realSum += realM;
        imagSum += imagM;
      }
      const mag = Math.sqrt(realSum * realSum + imagSum * imagSum);
      const phase = (Math.atan2(imagSum, realSum) * 180) / Math.PI;
      rpms.push(r);
      mags.push(mag);
      phases.push(phase);
    }
    return { rpms, mags, phases };
  }, []);

  const cursorIdx = useMemo(() => {
    const idx = Math.round((rpm - RPM_MIN) / 100);
    return Math.max(0, Math.min(bode.rpms.length - 1, idx));
  }, [rpm, bode.rpms.length]);
  const cursorMag = bode.mags[cursorIdx];
  const cursorPhase = bode.phases[cursorIdx];

  const layout: Partial<Layout> = useMemo(() => {
    const base = defaultPlotLayout(theme);
    return {
      ...base,
      xaxis: {
        ...base.xaxis,
        title: { text: "Speed, rpm", standoff: 6 },
        range: [RPM_MIN, RPM_MAX],
      },
      yaxis: {
        ...base.yaxis,
        title: { text: "Response magnitude", standoff: 6 },
        type: "log",
      },
      margin: { l: 60, r: 16, t: 16, b: 48 },
      shapes: [
        ...CRITICAL_SPEEDS.map((crit) => ({
          type: "line" as const,
          x0: crit,
          x1: crit,
          y0: 0,
          y1: 1,
          yref: "paper" as const,
          line: { color: "rgba(181, 52, 46, 0.4)", width: 1, dash: "dot" as const },
        })),
        {
          type: "line",
          x0: rpm,
          x1: rpm,
          y0: 0,
          y1: 1,
          yref: "paper",
          line: { color: "rgb(45, 110, 120)", width: 2 },
        },
      ],
      annotations: CRITICAL_SPEEDS.map((crit, i) => ({
        x: crit,
        y: 1,
        yref: "paper",
        text: `crit ${i + 1}`,
        showarrow: false,
        font: { size: 9, color: "rgba(181, 52, 46, 0.7)" },
        yshift: 8,
      })),
      showlegend: false,
    };
  }, [theme, rpm]);

  const traces: Data[] = useMemo(() => {
    return [
      {
        x: bode.rpms,
        y: bode.mags,
        mode: "lines",
        type: "scatter",
        line: { color: "rgb(31, 78, 121)", width: 2 },
        name: "|H(ω)|",
        hovertemplate: "rpm=%{x}<br>|H|=%{y:.2f}<extra></extra>",
      },
    ];
  }, [bode]);

  return (
    <WidgetFrame
      label="Rotor mode-shape animator"
      caption="1D rotor, two bearings at L/4 and 3L/4"
      onReset={() => {
        setMode(1);
        setRpm(15000);
      }}
      bodyHeight="540px"
    >
      <div className="grid h-full grid-cols-1 gap-3 p-3 lg:grid-cols-[1fr_220px]">
        <div className="flex min-h-0 flex-col gap-3">
          <div className="flex-1 min-h-0 rounded-sm border border-border-subtle bg-background">
            <RotorSvg pathRef={svgPathRef} />
          </div>
          <div className="flex-1 min-h-0 rounded-sm border border-border-subtle bg-background">
            <Plot
              data={traces}
              layout={layout}
              config={{ displayModeBar: false, responsive: true }}
            />
          </div>
        </div>
        <div className="flex flex-col gap-3 overflow-y-auto pr-1 scrollbar-subtle">
          <div className="flex flex-col gap-1.5">
            <Label className="text-sm">Mode</Label>
            <div className="flex flex-col gap-1">
              {([1, 2, 3] as const).map((n) => (
                <Button
                  key={n}
                  variant={mode === n ? "default" : "outline"}
                  size="sm"
                  onClick={() => setMode(n)}
                  className="justify-start"
                >
                  {MODE_LABELS[n]}
                </Button>
              ))}
            </div>
          </div>
          <div className="h-px bg-border-subtle" />
          <div className="flex flex-col gap-1.5">
            <div className="flex items-baseline justify-between">
              <Label className="text-sm">Speed</Label>
              <span className="font-mono text-xs tabular-nums text-text-muted">
                {rpm.toLocaleString()} rpm
              </span>
            </div>
            <Slider
              min={RPM_MIN}
              max={RPM_MAX}
              step={100}
              value={[rpm]}
              onValueChange={(v) => setRpm(v[0])}
            />
          </div>
          <Readout
            label="|H(ω)|"
            value={cursorMag.toFixed(2)}
            unit=""
            tone={cursorMag > 8 ? "warning" : "neutral"}
          />
          <Readout
            label="Phase"
            value={cursorPhase.toFixed(0)}
            unit="°"
          />
          <div className="rounded-sm border border-border-subtle bg-surface-computed px-2 py-1.5 text-xs text-text-muted">
            <div className="font-medium text-text">Critical speeds</div>
            <ul className="mt-1 flex flex-col gap-0.5">
              {CRITICAL_SPEEDS.map((c, i) => (
                <li key={i} className="font-mono tabular-nums">
                  N{i + 1} = {c.toLocaleString()} rpm
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </WidgetFrame>
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
  tone?: "neutral" | "warning";
}) {
  return (
    <div className="flex items-baseline justify-between gap-2 rounded-sm border border-border-subtle bg-surface-computed px-2 py-1.5">
      <span className="text-xs text-text-muted">{label}</span>
      <span
        className={cn(
          "font-mono text-md tabular-nums",
          tone === "warning" ? "text-semantic-warning-text" : "text-text",
        )}
      >
        {value}
        {unit && <span className="ml-1 text-xs text-text-muted">{unit}</span>}
      </span>
    </div>
  );
}

interface RotorViewport {
  /** Drawing width in SVG units. */
  width: number;
  /** Drawing height in SVG units. */
  height: number;
  /** Left padding. */
  pad: number;
  /** Effective rotor length (within the padded box). */
  L: number;
  /** Y-center of the rotor in SVG units. */
  yMid: number;
}

const VIEW: RotorViewport = {
  width: 600,
  height: 180,
  pad: 24,
  L: 600 - 48,
  yMid: 90,
};

function buildModeShapePath(mode: ModeIdx, tSeconds: number): string {
  const steps = 60;
  const { L, pad, yMid } = VIEW;
  // Sin(2πt) ⇒ one full oscillation per second, which "calm motion" still
  // permits since it's the data, not chrome.
  const tFactor = Math.sin(2 * Math.PI * tSeconds);
  let d = "";
  for (let i = 0; i <= steps; i++) {
    const xFrac = i / steps;
    const x = pad + xFrac * L;
    const phi = Math.PI * mode * xFrac;
    const y = yMid + AMPLITUDE * Math.sin(phi) * tFactor;
    d += i === 0 ? `M ${x.toFixed(2)} ${y.toFixed(2)}` : ` L ${x.toFixed(2)} ${y.toFixed(2)}`;
  }
  return d;
}

function RotorSvg({
  pathRef,
}: {
  pathRef: React.RefObject<SVGPathElement | null>;
}) {
  const { width, height, pad, L, yMid } = VIEW;
  const bearing1X = pad + L * 0.25;
  const bearing2X = pad + L * 0.75;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      xmlns="http://www.w3.org/2000/svg"
      preserveAspectRatio="xMidYMid meet"
      className="h-full w-full"
    >
      {/* Reference centreline */}
      <line
        x1={pad}
        y1={yMid}
        x2={width - pad}
        y2={yMid}
        stroke="rgb(193 197 203 / 0.4)"
        strokeDasharray="2 4"
      />
      {/* Bearings as triangles below the rotor */}
      {[bearing1X, bearing2X].map((bx, i) => (
        <g key={i}>
          <polygon
            points={`${bx - 8},${yMid + 36} ${bx + 8},${yMid + 36} ${bx},${yMid + 18}`}
            fill="rgb(74 79 88)"
            stroke="rgb(122 128 138)"
          />
          <line
            x1={bx - 12}
            y1={yMid + 36}
            x2={bx + 12}
            y2={yMid + 36}
            stroke="rgb(74 79 88)"
            strokeWidth={2}
          />
          {/* hatching under the bearing */}
          {[-6, -2, 2, 6].map((dx) => (
            <line
              key={dx}
              x1={bx + dx}
              y1={yMid + 36}
              x2={bx + dx + 3}
              y2={yMid + 44}
              stroke="rgb(122 128 138)"
              strokeWidth={1}
            />
          ))}
        </g>
      ))}

      {/* The rotor itself — a thick path that is re-set every frame */}
      <path
        ref={pathRef}
        d={buildModeShapePath(1, 0)}
        fill="none"
        stroke="rgb(31, 85, 94)"
        strokeWidth={6}
        strokeLinecap="round"
      />

      {/* End discs */}
      <circle cx={pad} cy={yMid} r={4} fill="rgb(31, 85, 94)" />
      <circle cx={width - pad} cy={yMid} r={4} fill="rgb(31, 85, 94)" />
    </svg>
  );
}
