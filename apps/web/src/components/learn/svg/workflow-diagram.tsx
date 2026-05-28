"use client";

import { cn } from "@/lib/utils";

interface Node {
  label: string;
  sub: string;
}

const NODES: Node[] = [
  { label: "Cycle", sub: "Brayton" },
  { label: "Flow Path", sub: "PD" },
  { label: "Analysis", sub: "meanline" },
  { label: "Map", sub: "off-design" },
  { label: "Rotor", sub: "lateral" },
];

interface Edge {
  /** A short hand-off label rendered above the arrow. */
  label: string;
}

const EDGES: Edge[] = [
  { label: "Port (T_t, P_t, ṁ)" },
  { label: "geometry" },
  { label: "loss-tuned η" },
  { label: "rotor shape" },
];

/**
 * The five-step workflow diagram for Chapter 9.
 *
 * Cycle → Flow Path → Analysis → Map → Rotor, with the artifact passed
 * between each pair labeled above the arrow.
 */
export function WorkflowDiagram({
  className,
  width = 720,
  height = 220,
}: {
  className?: string;
  width?: number;
  height?: number;
}) {
  const nodeW = 110;
  const nodeH = 64;
  const gap = (width - NODES.length * nodeW - 32) / (NODES.length - 1);
  const startX = 16;
  const y = height / 2 - nodeH / 2;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="Cascade workflow: cycle, flow path, analysis, map, rotor"
      className={cn("w-full text-text", className)}
    >
      {/* Edges first so nodes draw over them */}
      {EDGES.map((edge, i) => {
        const x1 = startX + (i + 1) * nodeW + i * gap;
        const x2 = x1 + gap;
        const yMid = height / 2;
        return (
          <g key={i}>
            {/* arrow line */}
            <line
              x1={x1}
              y1={yMid}
              x2={x2 - 8}
              y2={yMid}
              stroke="currentColor"
              strokeOpacity={0.45}
              strokeWidth={1.5}
            />
            {/* arrowhead */}
            <polygon
              points={`${x2},${yMid} ${x2 - 8},${yMid - 4} ${x2 - 8},${yMid + 4}`}
              fill="currentColor"
              opacity={0.6}
            />
            {/* edge label */}
            <text
              x={(x1 + x2) / 2}
              y={yMid - 10}
              textAnchor="middle"
              fontSize={9}
              fill="currentColor"
              opacity={0.65}
            >
              {edge.label}
            </text>
          </g>
        );
      })}

      {/* Nodes */}
      {NODES.map((n, i) => {
        const x = startX + i * (nodeW + gap);
        return (
          <g key={i}>
            <rect
              x={x}
              y={y}
              width={nodeW}
              height={nodeH}
              rx={6}
              fill="rgb(var(--surface-raised))"
              stroke="currentColor"
              strokeOpacity={0.35}
              strokeWidth={1.2}
            />
            {/* Step circle */}
            <circle
              cx={x + 14}
              cy={y + 14}
              r={9}
              fill="rgb(var(--brand-default))"
            />
            <text
              x={x + 14}
              y={y + 18}
              textAnchor="middle"
              fontSize={10}
              fontWeight={600}
              fill="rgb(var(--text-inverse))"
            >
              {i + 1}
            </text>
            <text
              x={x + nodeW / 2}
              y={y + 36}
              textAnchor="middle"
              fontSize={13}
              fontWeight={500}
              fill="currentColor"
            >
              {n.label}
            </text>
            <text
              x={x + nodeW / 2}
              y={y + 52}
              textAnchor="middle"
              fontSize={10}
              fill="currentColor"
              opacity={0.6}
            >
              {n.sub}
            </text>
          </g>
        );
      })}

      {/* Output dock — STEP export */}
      <g transform={`translate(${width - 16} ${height - 18})`}>
        <text
          textAnchor="end"
          fontSize={10}
          fill="currentColor"
          opacity={0.55}
        >
          STEP export · hand-off to CFD
        </text>
      </g>

      {/* Time annotation */}
      <text
        x={width / 2}
        y={height - 8}
        textAnchor="middle"
        fontSize={10}
        fill="currentColor"
        opacity={0.55}
      >
        end-to-end: one afternoon on a laptop
      </text>
    </svg>
  );
}
