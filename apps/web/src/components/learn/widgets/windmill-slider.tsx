"use client";

import { useMemo, useState } from "react";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { WidgetFrame } from "./widget-frame";

/**
 * Chapter 1 — WindmillSlider.
 *
 * A toy windmill that spins faster as wind speed rises. The readout uses
 * the kinetic-energy expression for a turbine,
 *
 *     P = ½ · ρ · A · v³ · Cp,
 *
 * with rotor swept area A = 1 m², air density ρ = 1.225 kg/m³, and a
 * power coefficient Cp = 0.4 (Betz limit Cp,Betz = 16/27 ≈ 0.593 is
 * the *theoretical* maximum — see Betz 1920; real horizontal-axis wind
 * turbines hit 0.35–0.45 in practice).
 *
 * The animation is pure CSS: the SVG rotates at a rate set by an
 * `animation-duration` CSS variable, which we derive from wind speed.
 */

const AIR_DENSITY = 1.225; // kg/m³ at sea level, 15 °C
const SWEPT_AREA = 1; // m² — toy windmill
const CP = 0.4; // realistic horizontal-axis Cp
const CP_BETZ = 16 / 27;

const DEFAULT_WIND = 6; // m/s — average residential wind speed

export function WindmillSlider() {
  const [wind, setWind] = useState(DEFAULT_WIND);

  // Mechanical power available, in watts.
  const powerW = useMemo(
    () => 0.5 * AIR_DENSITY * SWEPT_AREA * Math.pow(wind, 3) * CP,
    [wind],
  );
  // Power at the Betz limit, for comparison.
  const powerBetzW = useMemo(
    () => 0.5 * AIR_DENSITY * SWEPT_AREA * Math.pow(wind, 3) * CP_BETZ,
    [wind],
  );

  // Rotation period in seconds — wind speed → blade tip speed.
  // We pick TSR (tip-speed ratio) ≈ 6 for a 1 m radius rotor, so
  // ω = TSR · v / r. The visual period is 2π/ω, clamped to [0.4, 8] s
  // so animation never freezes or becomes seizure-inducing.
  const periodS = useMemo(() => {
    if (wind < 0.05) return 8;
    const tipSpeedRatio = 6;
    const radius = 1;
    const omega = (tipSpeedRatio * wind) / radius;
    const p = (2 * Math.PI) / omega;
    return Math.max(0.4, Math.min(8, p));
  }, [wind]);

  return (
    <WidgetFrame
      label="Windmill slider"
      caption="kinetic-energy turbine, A = 1 m²"
      onReset={() => setWind(DEFAULT_WIND)}
      bodyHeight="420px"
    >
      <div className="grid h-full grid-cols-1 gap-4 p-4 lg:grid-cols-[1fr_240px]">
        <div className="flex min-h-0 items-center justify-center rounded-sm border border-border-subtle bg-background">
          <WindmillSVG periodS={periodS} />
        </div>
        <div className="flex flex-col gap-3 overflow-y-auto pr-1 scrollbar-subtle">
          <div className="flex flex-col gap-1.5">
            <div className="flex items-baseline justify-between gap-2">
              <Label className="text-sm">Wind speed (v)</Label>
              <span className="font-mono text-xs tabular-nums text-text-muted">
                {wind.toFixed(1)} m/s
              </span>
            </div>
            <Slider
              min={0}
              max={20}
              step={0.1}
              value={[wind]}
              onValueChange={(v) => setWind(v[0])}
            />
            <div className="flex justify-between text-[10px] font-mono text-text-muted">
              <span>0</span>
              <span>10</span>
              <span>20 m/s</span>
            </div>
          </div>

          <div className="h-px bg-border-subtle" />

          <Readout
            label="P_extracted"
            value={powerW < 1 ? powerW.toFixed(2) : powerW.toFixed(1)}
            unit="W"
            tone="brand"
          />
          <Readout
            label="P at Betz limit"
            value={powerBetzW < 1 ? powerBetzW.toFixed(2) : powerBetzW.toFixed(1)}
            unit="W"
          />
          <Readout
            label="C_p (this rotor)"
            value={CP.toFixed(2)}
            unit=""
          />
          <Readout
            label="C_p,Betz (max)"
            value={CP_BETZ.toFixed(3)}
            unit=""
          />

          <p className="rounded-sm border border-semantic-info-border bg-semantic-info-surface px-2 py-2 text-xs leading-relaxed text-semantic-info-text">
            <strong className="font-medium">Betz limit:</strong> no axial-flow
            wind turbine can extract more than 59.3% of the wind&rsquo;s
            kinetic energy (Betz, 1920). Real machines reach 0.35–0.45.
          </p>
        </div>
      </div>
    </WidgetFrame>
  );
}

function WindmillSVG({ periodS }: { periodS: number }) {
  return (
    <svg
      viewBox="0 0 320 320"
      className="h-full w-full"
      role="img"
      aria-label="A schematic windmill. Increase wind speed to see it spin faster."
    >
      {/* Sky / ground reference line */}
      <line
        x1="0"
        y1="280"
        x2="320"
        y2="280"
        stroke="currentColor"
        strokeWidth="0.8"
        strokeDasharray="3 4"
        opacity="0.5"
      />

      {/* Tower */}
      <path
        d="M 152 140 L 160 280 L 168 140 Z"
        fill="rgb(var(--surface-subtle))"
        stroke="currentColor"
        strokeWidth="1.4"
      />

      {/* Nacelle */}
      <rect
        x="142"
        y="120"
        width="36"
        height="24"
        rx="3"
        fill="rgb(var(--surface-subtle))"
        stroke="currentColor"
        strokeWidth="1.4"
      />

      {/* Rotor — animated */}
      <g
        style={{
          transformOrigin: "160px 132px",
          animation: `learn-spin ${periodS}s linear infinite`,
        }}
      >
        {/* Three-blade rotor */}
        {[0, 120, 240].map((deg) => (
          <g key={deg} transform={`rotate(${deg} 160 132)`}>
            <path
              d="M 160 132 Q 168 90 162 38 Q 158 50 155 100 Q 155 122 160 132 Z"
              fill="rgb(var(--brand-default))"
              stroke="rgb(var(--brand-default))"
              strokeWidth="1.4"
              opacity="0.9"
            />
          </g>
        ))}
        {/* hub */}
        <circle
          cx="160"
          cy="132"
          r="6"
          fill="currentColor"
        />
      </g>

      {/* Wind direction indicator */}
      <g
        stroke="rgb(var(--info-default))"
        strokeWidth="1.4"
        fill="rgb(var(--info-default))"
        opacity="0.7"
      >
        <line x1="20" y1="60" x2="60" y2="60" />
        <polyline points="54 54, 60 60, 54 66" fill="none" />
        <line x1="20" y1="100" x2="50" y2="100" />
        <polyline points="44 94, 50 100, 44 106" fill="none" />
        <line x1="20" y1="180" x2="70" y2="180" />
        <polyline points="64 174, 70 180, 64 186" fill="none" />
      </g>
      <text
        x="20"
        y="50"
        fontFamily="var(--font-mono)"
        fontSize="10"
        fill="rgb(var(--info-text))"
      >
        wind
      </text>

      {/* CSS keyframe — scoped to this widget */}
      <style>{`
        @keyframes learn-spin {
          0%   { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @media (prefers-reduced-motion: reduce) {
          g[style*="learn-spin"] {
            animation: none !important;
          }
        }
      `}</style>
    </svg>
  );
}

function Readout({
  label,
  value,
  unit,
  tone,
}: {
  label: string;
  value: string;
  unit: string;
  tone?: "brand";
}) {
  return (
    <div className="flex items-baseline justify-between gap-2 rounded-sm border border-border-subtle bg-surface-computed px-2 py-1.5">
      <span className="text-xs text-text-muted">{label}</span>
      <span
        className={
          "font-mono text-md tabular-nums " +
          (tone === "brand" ? "text-brand-text" : "text-text")
        }
      >
        {value}
        {unit && <span className="ml-1 text-xs text-text-muted">{unit}</span>}
      </span>
    </div>
  );
}
