"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";

/**
 * The classic banana-shaped compressor map.
 *
 *   y-axis: pressure ratio π
 *   x-axis: corrected mass flow ṁ √θ / δ
 *   speedlines: 5 of them, increasing from 60% N_corr (bottom) to 100% (top)
 *   surge line: connects the leftmost (highest-π) point of each speedline
 *   choke line: vertical-ish line on the right at increasing ṁ
 *   efficiency islands: two nested closed contours around 80% / 75% η
 *   design point: filled diamond at one of the higher-speed lines
 */
export function CompressorMap({
  className,
  width = 520,
  height = 360,
  markDesignPoint = true,
}: {
  className?: string;
  width?: number;
  height?: number;
  markDesignPoint?: boolean;
}) {
  const padL = 44;
  const padR = 18;
  const padT = 20;
  const padB = 36;
  const w = width - padL - padR;
  const h = height - padT - padB;

  const speedFractions = [0.6, 0.7, 0.8, 0.9, 1.0, 1.05];

  // Generate speedlines as cubic curves.
  // For fraction n (where n=1.0 is design), we sweep ṁ from a left-surge
  // boundary to a right-choke boundary; π peaks somewhere in the middle.
  const speedlines = useMemo(
    () => speedFractions.map((n) => makeSpeedline(n, w, h)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [w, h],
  );

  // Surge line: connect the highest-π point of each speedline.
  const surgePoints = speedlines.map((sl) => sl.surge);
  const surgePath = `M ${surgePoints
    .map((p) => `${(padL + p.x).toFixed(1)} ${(padT + p.y).toFixed(1)}`)
    .join(" L ")}`;

  // Choke line: connect the rightmost point of each speedline.
  const chokePoints = speedlines.map((sl) => sl.choke);
  const chokePath = `M ${chokePoints
    .map((p) => `${(padL + p.x).toFixed(1)} ${(padT + p.y).toFixed(1)}`)
    .join(" L ")}`;

  // Efficiency islands — two concentric ellipses in the middle-upper region.
  const eta75 = { cx: 0.58 * w, cy: 0.48 * h, rx: 0.24 * w, ry: 0.22 * h };
  const eta80 = { cx: 0.55 * w, cy: 0.43 * h, rx: 0.13 * w, ry: 0.12 * h };

  // Design point — on the 100% speedline near the high-η island center.
  const dp = speedlines[4].sample(0.55);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="Centrifugal compressor performance map"
      className={cn("w-full text-text", className)}
    >
      {/* Frame */}
      <rect
        x={padL}
        y={padT}
        width={w}
        height={h}
        fill="none"
        stroke="currentColor"
        strokeOpacity={0.25}
      />

      {/* Grid */}
      {Array.from({ length: 5 }, (_, i) => (
        <line
          key={`gx${i}`}
          x1={padL + (i + 1) * (w / 6)}
          x2={padL + (i + 1) * (w / 6)}
          y1={padT}
          y2={padT + h}
          stroke="currentColor"
          strokeOpacity={0.06}
        />
      ))}
      {Array.from({ length: 4 }, (_, i) => (
        <line
          key={`gy${i}`}
          y1={padT + (i + 1) * (h / 5)}
          y2={padT + (i + 1) * (h / 5)}
          x1={padL}
          x2={padL + w}
          stroke="currentColor"
          strokeOpacity={0.06}
        />
      ))}

      {/* Efficiency islands */}
      <ellipse
        cx={padL + eta75.cx}
        cy={padT + eta75.cy}
        rx={eta75.rx}
        ry={eta75.ry}
        fill="none"
        stroke="rgb(var(--chart-3))"
        strokeOpacity={0.5}
        strokeDasharray="3 3"
        strokeWidth={1}
      />
      <ellipse
        cx={padL + eta80.cx}
        cy={padT + eta80.cy}
        rx={eta80.rx}
        ry={eta80.ry}
        fill="none"
        stroke="rgb(var(--chart-3))"
        strokeOpacity={0.7}
        strokeWidth={1.2}
      />
      <text
        x={padL + eta80.cx}
        y={padT + eta80.cy + 3}
        textAnchor="middle"
        fontSize={10}
        fill="rgb(var(--chart-3))"
      >
        η = 0.80
      </text>

      {/* Speedlines */}
      {speedlines.map((sl, i) => (
        <g key={i}>
          <path
            d={sl.path(padL, padT)}
            fill="none"
            stroke="currentColor"
            strokeWidth={1.2}
            strokeOpacity={0.85}
          />
          <text
            x={padL + sl.choke.x + 4}
            y={padT + sl.choke.y + 3}
            fontSize={9}
            fill="currentColor"
            opacity={0.65}
          >
            {Math.round(speedFractions[i] * 100)}%
          </text>
        </g>
      ))}

      {/* Surge line */}
      <path
        d={surgePath}
        fill="none"
        stroke="rgb(var(--chart-10))"
        strokeWidth={1.6}
      />
      <text
        x={padL + surgePoints[surgePoints.length - 1].x - 4}
        y={padT + surgePoints[surgePoints.length - 1].y - 4}
        fontSize={10}
        fontWeight={500}
        fill="rgb(var(--chart-10))"
        textAnchor="end"
      >
        surge
      </text>

      {/* Choke line */}
      <path
        d={chokePath}
        fill="none"
        stroke="rgb(var(--chart-2))"
        strokeWidth={1.6}
        strokeDasharray="4 3"
      />
      <text
        x={padL + chokePoints[chokePoints.length - 1].x + 4}
        y={padT + chokePoints[chokePoints.length - 1].y - 4}
        fontSize={10}
        fontWeight={500}
        fill="rgb(var(--chart-2))"
      >
        choke
      </text>

      {/* Design point */}
      {markDesignPoint && (
        <g transform={`translate(${padL + dp.x} ${padT + dp.y})`}>
          <polygon
            points="0,-5 5,0 0,5 -5,0"
            fill="rgb(var(--brand-default))"
            stroke="rgb(var(--background))"
            strokeWidth={1.5}
          />
          <text
            x={8}
            y={4}
            fontSize={10}
            fontWeight={500}
            fill="rgb(var(--brand-default))"
          >
            design point
          </text>
        </g>
      )}

      {/* Axis labels */}
      <text
        x={padL + w / 2}
        y={height - 6}
        textAnchor="middle"
        fontSize={11}
        fill="currentColor"
        opacity={0.75}
      >
        corrected mass flow  ṁ √θ / δ
      </text>
      <text
        x={12}
        y={padT + h / 2}
        textAnchor="middle"
        transform={`rotate(-90 12 ${padT + h / 2})`}
        fontSize={11}
        fill="currentColor"
        opacity={0.75}
      >
        pressure ratio  π
      </text>
    </svg>
  );
}

interface Speedline {
  surge: { x: number; y: number };
  choke: { x: number; y: number };
  /** sample at parameter t in [0, 1] from surge → choke */
  sample: (t: number) => { x: number; y: number };
  /** SVG path translated by (px, py) */
  path: (px: number, py: number) => string;
}

function makeSpeedline(n: number, w: number, h: number): Speedline {
  // n is speed fraction (0.6 → 1.05).
  // For higher n, the speedline shifts up and right and steepens at the
  // choke side. The peak π (surge) sits at the left.
  // We model it as a parametric curve with t in [0, 1]:
  //   x(t) = ax + bx * t + cx * t^2
  //   y(t) = ay - by * t - cy * t^2 + dy * sin(pi * t * 0.7)
  // tuned to look like a real compressor map.

  const minX = 0.05 + 0.18 * (n - 0.6); // left-most x (surge x)
  const maxX = 0.6 + 0.32 * (n - 0.6); // right-most x (choke x)
  const peakY = 0.16 + 0.65 * (1.05 - n); // surge π (smaller=higher π)
  const chokeY = peakY + 0.18 + 0.15 * (1 - n); // choke π lower than surge

  const sample = (t: number) => {
    const tt = Math.max(0, Math.min(1, t));
    // ease the x so we have more samples near the middle
    const xt = minX + (maxX - minX) * smoothstep(tt);
    // y curve: starts at peakY, dips toward chokeY with a gentle hump
    const yt =
      peakY +
      (chokeY - peakY) * Math.pow(tt, 1.5) -
      0.04 * Math.sin(Math.PI * tt);
    return { x: xt * w, y: yt * h };
  };

  const surge = sample(0);
  const choke = sample(1);

  const path = (px: number, py: number) => {
    const N = 32;
    const parts: string[] = [];
    for (let i = 0; i <= N; i++) {
      const t = i / N;
      const { x, y } = sample(t);
      parts.push(`${i === 0 ? "M" : "L"} ${(px + x).toFixed(1)} ${(py + y).toFixed(1)}`);
    }
    return parts.join(" ");
  };

  return { surge, choke, sample, path };
}

function smoothstep(t: number): number {
  return t * t * (3 - 2 * t);
}
