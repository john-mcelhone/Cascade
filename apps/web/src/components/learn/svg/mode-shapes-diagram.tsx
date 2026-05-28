"use client";

import { cn } from "@/lib/utils";

/**
 * Three lateral rotor mode shapes drawn side-by-side: first-bending (U-shape),
 * second (S-shape), third (W-shape). Bearings shown as triangular supports;
 * the shaft is a horizontal line with two impeller disks lumped on it.
 */
export function ModeShapesDiagram({
  className,
  width = 540,
  height = 280,
}: {
  className?: string;
  width?: number;
  height?: number;
}) {
  const cellW = width / 3;
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="First three rotor lateral mode shapes"
      className={cn("w-full text-text", className)}
    >
      {[0, 1, 2].map((i) => (
        <g key={i} transform={`translate(${i * cellW} 0)`}>
          <ModeCell mode={i + 1} width={cellW} height={height} />
        </g>
      ))}
    </svg>
  );
}

function ModeCell({
  mode,
  width,
  height,
}: {
  mode: number;
  width: number;
  height: number;
}) {
  const padX = 18;
  const midY = height * 0.5;
  const left = padX;
  const right = width - padX;
  const span = right - left;

  // Bearings at 18% and 82% along the shaft
  const b1x = left + 0.18 * span;
  const b2x = left + 0.82 * span;
  // Impeller disks at ~28% and ~70%
  const d1x = left + 0.32 * span;
  const d2x = left + 0.68 * span;

  // Mode shape sampling: f(t) where t is normalized along the rotor
  // Use simply-supported beam mode shapes scaled to fit:
  //   mode 1: sin(pi t)
  //   mode 2: sin(2 pi t)
  //   mode 3: sin(3 pi t)
  // Amplitude tapers to zero at bearings.
  const amp = 28;
  const N = 64;
  const pts: Array<{ x: number; y: number }> = [];
  // Anchor the curve so it passes through bearing supports
  const supportFrac1 = (b1x - left) / span;
  const supportFrac2 = (b2x - left) / span;
  for (let i = 0; i <= N; i++) {
    const t = i / N;
    // Confine the curve between supports — use shifted/scaled mode shape
    const tInner = Math.max(0, Math.min(1, (t - supportFrac1) / (supportFrac2 - supportFrac1)));
    const yShape = Math.sin(mode * Math.PI * tInner);
    const x = left + t * span;
    const y = midY - yShape * amp;
    pts.push({ x, y });
  }
  const undeflected = `M ${left} ${midY} L ${right} ${midY}`;
  const deflected = `M ${pts[0].x} ${pts[0].y} ` +
    pts.slice(1).map((p) => `L ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");

  // Critical-speed labels by mode
  const critRPM = mode === 1 ? "≈ 9,000 rpm" : mode === 2 ? "≈ 24,000 rpm" : "≈ 47,000 rpm";

  return (
    <g>
      {/* Title */}
      <text
        x={width / 2}
        y={26}
        textAnchor="middle"
        fontSize={12}
        fontWeight={500}
        fill="currentColor"
      >
        Mode {mode}
      </text>
      <text
        x={width / 2}
        y={42}
        textAnchor="middle"
        fontSize={10}
        fill="currentColor"
        opacity={0.65}
      >
        {critRPM}
      </text>

      {/* Undeflected shaft (dashed) */}
      <path
        d={undeflected}
        stroke="currentColor"
        strokeOpacity={0.3}
        strokeWidth={1}
        strokeDasharray="3 3"
        fill="none"
      />
      {/* Deflected shape */}
      <path
        d={deflected}
        stroke="rgb(var(--brand-default))"
        strokeWidth={2.5}
        strokeLinecap="round"
        fill="none"
      />

      {/* Impeller disks */}
      {[d1x, d2x].map((dx, i) => {
        const tDisk = (dx - left) / span;
        const tInner = Math.max(0, Math.min(1, (tDisk - supportFrac1) / (supportFrac2 - supportFrac1)));
        const yShape = Math.sin(mode * Math.PI * tInner);
        const dy = midY - yShape * amp;
        return (
          <g key={i}>
            {/* dashed ghost of disk at undeflected position */}
            <rect
              x={dx - 4}
              y={midY - 14}
              width={8}
              height={28}
              fill="currentColor"
              opacity={0.08}
              rx={2}
            />
            <rect
              x={dx - 4}
              y={dy - 14}
              width={8}
              height={28}
              fill="currentColor"
              opacity={0.7}
              rx={2}
            />
          </g>
        );
      })}

      {/* Bearings as triangles below shaft */}
      {[b1x, b2x].map((bx, i) => (
        <g key={i}>
          <polygon
            points={`${bx - 7},${midY + 18} ${bx + 7},${midY + 18} ${bx},${midY + 4}`}
            fill="currentColor"
            opacity={0.35}
            stroke="currentColor"
            strokeWidth={1}
          />
          {/* hatched ground */}
          {[-8, -3, 2, 7].map((dx, j) => (
            <line
              key={j}
              x1={bx + dx - 3}
              y1={midY + 25}
              x2={bx + dx + 1}
              y2={midY + 19}
              stroke="currentColor"
              strokeOpacity={0.3}
              strokeWidth={1}
            />
          ))}
          <line
            x1={bx - 10}
            y1={midY + 18}
            x2={bx + 10}
            y2={midY + 18}
            stroke="currentColor"
            strokeOpacity={0.35}
            strokeWidth={1}
          />
        </g>
      ))}

      {/* Node labels (for mode > 1 we have nodes) */}
      {mode > 1 && (() => {
        const nodes = [];
        for (let k = 1; k < mode; k++) {
          const tInner = k / mode;
          const tFull = supportFrac1 + tInner * (supportFrac2 - supportFrac1);
          const nx = left + tFull * span;
          nodes.push(
            <circle
              key={k}
              cx={nx}
              cy={midY}
              r={3}
              fill="rgb(var(--background))"
              stroke="rgb(var(--chart-10))"
              strokeWidth={1.5}
            />,
          );
        }
        return nodes;
      })()}
    </g>
  );
}
