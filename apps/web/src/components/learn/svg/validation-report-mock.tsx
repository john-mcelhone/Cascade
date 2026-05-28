"use client";

import { cn } from "@/lib/utils";

/**
 * A pseudo-screenshot of the public validation page, drawn entirely in SVG
 * so it renders correctly in dark mode and at any resolution. Used as the
 * hero figure for Chapter 10.
 */
export function ValidationReportMock({
  className,
  width = 560,
  height = 340,
}: {
  className?: string;
  width?: number;
  height?: number;
}) {
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="Mockup of the Cascade public validation report page"
      className={cn("w-full text-text", className)}
    >
      {/* Window chrome */}
      <rect
        x={4}
        y={4}
        width={width - 8}
        height={height - 8}
        rx={6}
        fill="rgb(var(--surface-raised))"
        stroke="currentColor"
        strokeOpacity={0.25}
      />
      <rect
        x={4}
        y={4}
        width={width - 8}
        height={28}
        rx={6}
        fill="rgb(var(--surface-subtle))"
      />
      {/* macOS-style window dots */}
      <circle cx={18} cy={18} r={4} fill="#e0e0e0" opacity={0.45} />
      <circle cx={32} cy={18} r={4} fill="#e0e0e0" opacity={0.45} />
      <circle cx={46} cy={18} r={4} fill="#e0e0e0" opacity={0.45} />
      <text
        x={width / 2}
        y={22}
        textAnchor="middle"
        fontSize={10}
        fontFamily="var(--font-mono), monospace"
        fill="currentColor"
        opacity={0.55}
      >
        cascade.dev/docs/validation
      </text>

      {/* Title */}
      <text
        x={20}
        y={56}
        fontSize={14}
        fontWeight={600}
        fill="currentColor"
      >
        Validation Report — v0.1.0
      </text>
      <text x={20} y={72} fontSize={10} fill="currentColor" opacity={0.6}>
        171 tests passing · 45 pass-gates · 13.2 s on every commit
      </text>

      {/* Headline pills */}
      <Pill x={20} y={84} label="all pass" color="success" />
      <Pill x={88} y={84} label="auto-generated" color="info" />
      <Pill x={188} y={84} label="reproducible" color="info" />

      {/* Table-like rows */}
      <g transform="translate(20 116)">
        {/* Header */}
        <text x={0} y={0} fontSize={9} fill="currentColor" opacity={0.6}>
          CASE
        </text>
        <text x={140} y={0} fontSize={9} fill="currentColor" opacity={0.6}>
          SOURCE
        </text>
        <text x={310} y={0} fontSize={9} fill="currentColor" opacity={0.6}>
          MEASURED
        </text>
        <text x={420} y={0} fontSize={9} fill="currentColor" opacity={0.6}>
          TOL
        </text>
        <text x={470} y={0} fontSize={9} fill="currentColor" opacity={0.6}>
          STATUS
        </text>
        <line
          x1={0}
          y1={6}
          x2={width - 40}
          y2={6}
          stroke="currentColor"
          strokeOpacity={0.2}
        />

        <Row
          y={22}
          id="CYC-3"
          src="Capstone C30 spec"
          val="η_e = 26.09%"
          tol="±1.5 pt"
          status="pass"
        />
        <Row
          y={42}
          id="CC-2"
          src="Eckardt 1976 Rotor O"
          val="π_tt = 2.08"
          tol="±1.5 pt"
          status="pass"
        />
        <Row
          y={62}
          id="RD-3"
          src="NASA TM-102368"
          val="N_c1 = 8,924 rpm"
          tol="±5%"
          status="pass"
        />
        <Row
          y={82}
          id="CYC-1"
          src="Çengel & Boles Ex. 9-5"
          val="η_th = 44.80%"
          tol="±0.1 pt"
          status="pass"
        />
        <Row
          y={102}
          id="AXT-3"
          src="NASA Stage 37"
          val="π = 2.04"
          tol="±3%"
          status="pass"
        />
        <Row
          y={122}
          id="OPT-1"
          src="Branin function"
          val="< 100 evals"
          tol="–"
          status="pass"
        />
        <Row
          y={142}
          id="RIT-1"
          src="NASA TN D-7508"
          val="η_ts = 0.817"
          tol="±2 pt"
          status="char"
        />
        <Row
          y={162}
          id="CYC-7"
          src="NPSS / PW1100G"
          val="(cooled deferred)"
          tol="–"
          status="info"
        />
      </g>

      {/* Citation tag bottom-right */}
      <g transform={`translate(${width - 156} ${height - 36})`}>
        <rect
          width={140}
          height={24}
          rx={4}
          fill="currentColor"
          opacity={0.06}
        />
        <text
          x={70}
          y={16}
          textAnchor="middle"
          fontSize={9}
          fontFamily="var(--font-mono), monospace"
          fill="currentColor"
          opacity={0.75}
        >
          make validation
        </text>
      </g>
    </svg>
  );
}

function Pill({
  x,
  y,
  label,
  color,
}: {
  x: number;
  y: number;
  label: string;
  color: "success" | "info" | "warning";
}) {
  const w = label.length * 5.5 + 12;
  const surfaceVar = `--${color}-surface`;
  const textVar = `--${color}-text`;
  return (
    <g transform={`translate(${x} ${y})`}>
      <rect
        width={w}
        height={16}
        rx={3}
        fill={`rgb(var(${surfaceVar}))`}
        stroke={`rgb(var(--${color}-border))`}
        strokeOpacity={0.7}
      />
      <text
        x={w / 2}
        y={11}
        textAnchor="middle"
        fontSize={9}
        fontWeight={500}
        fill={`rgb(var(${textVar}))`}
      >
        {label}
      </text>
    </g>
  );
}

function Row({
  y,
  id,
  src,
  val,
  tol,
  status,
}: {
  y: number;
  id: string;
  src: string;
  val: string;
  tol: string;
  status: "pass" | "char" | "info";
}) {
  return (
    <g transform={`translate(0 ${y})`}>
      <text
        x={0}
        y={0}
        fontSize={10}
        fontFamily="var(--font-mono), monospace"
        fill="currentColor"
      >
        {id}
      </text>
      <text x={140} y={0} fontSize={10} fill="currentColor" opacity={0.85}>
        {src}
      </text>
      <text
        x={310}
        y={0}
        fontSize={10}
        fontFamily="var(--font-mono), monospace"
        fill="currentColor"
      >
        {val}
      </text>
      <text
        x={420}
        y={0}
        fontSize={10}
        fontFamily="var(--font-mono), monospace"
        fill="currentColor"
        opacity={0.75}
      >
        {tol}
      </text>
      <g transform="translate(470 -10)">
        {status === "pass" && (
          <Pill x={0} y={0} label="pass" color="success" />
        )}
        {status === "char" && (
          <Pill x={0} y={0} label="char" color="warning" />
        )}
        {status === "info" && (
          <Pill x={0} y={0} label="info" color="info" />
        )}
      </g>
    </g>
  );
}
