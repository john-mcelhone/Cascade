"use client";

import { useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Animated Sobol' scatter — fills the unit square progressively from
 * 32 → 512 points over a few seconds. Useful as a hero for Chapter 6.
 *
 * The sequence is a deterministic 2D Sobol'-like construction (Van der
 * Corput in base 2 / base 3) — *not* the true Joe–Kuo direction numbers,
 * but mathematically reasonable and visually balanced for the page.
 */
export function DesignSpaceScatter({
  className,
  width = 480,
  height = 280,
  maxPoints = 512,
}: {
  className?: string;
  width?: number;
  height?: number;
  maxPoints?: number;
}) {
  // Pre-compute the entire low-discrepancy sequence so animation is just
  // an index over it.
  const points = useMemo(() => {
    const out: Array<{ x: number; y: number; tier: number }> = [];
    for (let i = 1; i <= maxPoints; i++) {
      out.push({ x: vdc(i, 2), y: vdc(i, 3), tier: tierForIndex(i) });
    }
    return out;
  }, [maxPoints]);

  const [visible, setVisible] = useState(0);

  useEffect(() => {
    let raf = 0;
    let start: number | null = null;
    const duration = 3200; // ms to fill all points
    const tick = (t: number) => {
      if (start === null) start = t;
      const elapsed = t - start;
      const frac = Math.min(1, elapsed / duration);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - frac, 3);
      setVisible(Math.floor(eased * maxPoints));
      if (elapsed < duration) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [maxPoints]);

  // pareto-like envelope: roughly the upper-right quarter-circle of unit sq
  const pareto = useMemo(() => {
    const segs: string[] = [];
    const N = 40;
    for (let i = 0; i <= N; i++) {
      const t = i / N;
      // efficiency-vs-mass tradeoff: y = sqrt(1 - (x-0.2)^2 * 1.6) clamped
      const x = 0.1 + 0.8 * t;
      const r = (x - 0.2) * 1.4;
      const y = Math.sqrt(Math.max(0, 1 - r * r));
      const px = 8 + x * (width - 16);
      const py = height - 8 - y * (height - 16);
      segs.push(`${i === 0 ? "M" : "L"} ${px.toFixed(1)} ${py.toFixed(1)}`);
    }
    return segs.join(" ");
  }, [width, height]);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="Design space scatter filling with Sobol' samples"
      className={cn("w-full text-text", className)}
    >
      {/* Frame */}
      <rect
        x={4}
        y={4}
        width={width - 8}
        height={height - 8}
        fill="none"
        stroke="currentColor"
        strokeOpacity={0.15}
        rx={4}
      />

      {/* Axes labels */}
      <text
        x={width / 2}
        y={height - 2}
        textAnchor="middle"
        fontSize={9}
        fill="currentColor"
        opacity={0.55}
      >
        rotor outlet radius →
      </text>
      <text
        x={8}
        y={height / 2}
        transform={`rotate(-90 8 ${height / 2})`}
        textAnchor="middle"
        fontSize={9}
        fill="currentColor"
        opacity={0.55}
      >
        η_tt →
      </text>

      {/* Pareto front line, faintly */}
      <path
        d={pareto}
        fill="none"
        stroke="currentColor"
        strokeOpacity={visible > 200 ? 0.55 : 0}
        strokeWidth={1.2}
        strokeDasharray="3 3"
        style={{ transition: "stroke-opacity 600ms ease-out" }}
      />
      {visible > 240 && (
        <text
          x={width - 22}
          y={28}
          textAnchor="end"
          fontSize={9}
          fill="currentColor"
          opacity={0.7}
        >
          Pareto front
        </text>
      )}

      {/* Points */}
      {points.slice(0, visible).map((p, i) => {
        const x = 8 + p.x * (width - 16);
        const y = height - 8 - p.y * (height - 16);
        const colorVar = colorForPoint(p);
        return (
          <circle
            key={i}
            cx={x}
            cy={y}
            r={1.6}
            fill={`rgb(var(--${colorVar}))`}
            opacity={0.85}
          />
        );
      })}

      {/* Sample-count badge */}
      <g transform={`translate(${width - 78} 10)`}>
        <rect
          width={70}
          height={18}
          rx={3}
          fill="currentColor"
          opacity={0.07}
        />
        <text
          x={6}
          y={12}
          fontSize={10}
          fontFamily="var(--font-mono), monospace"
          fill="currentColor"
        >
          n = {visible}
        </text>
      </g>
    </svg>
  );
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

// Three coloring tiers: feasible (green), edge (amber), infeasible (slate)
function tierForIndex(i: number): number {
  // Hash-ish; gives ~70% feasible, 20% edge, 10% infeasible
  const h = (i * 2654435761) % 100;
  if (h < 70) return 0;
  if (h < 90) return 1;
  return 2;
}

function colorForPoint(p: { tier: number; x: number; y: number }): string {
  // Penalize points in the lower-left as infeasible too
  if (p.x < 0.18 || p.y < 0.18) return "chart-8";
  if (p.tier === 0) return "chart-3";
  if (p.tier === 1) return "chart-5";
  return "chart-8";
}
