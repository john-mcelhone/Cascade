"use client";

import { useMemo } from "react";
import type { MergedGeometry } from "@/lib/api/flowpath";
import { fmtNumber } from "@/lib/utils";

/**
 * 2D meridional (r–z) flow-path view.
 *
 * Renders the hub and shroud contours from the merged geometry — the SAME
 * B-spline curves the mesh generator and the vendor exports sample — with
 * the dimensions engineers judge a flow path by: r1_hub / r1_tip at the
 * eye, r2 and b2 at the exit. Equal-aspect axes (z horizontal, r vertical);
 * upper half only, per meridional-drawing convention.
 */
export function MeridionalView({ merged }: { merged: MergedGeometry }) {
  const hub = merged.meridional?.hub ?? [];
  const shroud = merged.meridional?.shroud ?? [];
  const gp = merged.geometry_params;

  const view = useMemo(() => {
    if (hub.length < 2 || shroud.length < 2) return null;

    const all = [...hub, ...shroud];
    const zMin = Math.min(...all.map((p) => p[0]));
    const zMax = Math.max(...all.map((p) => p[0]));
    const rMax = Math.max(...all.map((p) => p[1]));
    if (zMax - zMin <= 0 || rMax <= 0) return null;

    // Drawing box: leave gutters for the centerline (below r=0) and the
    // dimension labels (right + left).
    const W = 420;
    const H = 300;
    const PAD = { left: 56, right: 64, top: 20, bottom: 34 };
    const innerW = W - PAD.left - PAD.right;
    const innerH = H - PAD.top - PAD.bottom;
    // Equal aspect: one scale for both axes.
    const scale = Math.min(innerW / (zMax - zMin), innerH / rMax);

    const x = (z: number) => PAD.left + (z - zMin) * scale;
    const y = (r: number) => H - PAD.bottom - r * scale;
    const path = (pts: [number, number][]) =>
      pts
        .map((p, i) => `${i === 0 ? "M" : "L"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`)
        .join(" ");

    return { W, H, x, y, path, zMin, zMax, rMax };
  }, [hub, shroud]);

  if (!view) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-text-muted">
        Meridional contour unavailable for this candidate.
      </div>
    );
  }

  const { W, H, x, y, path } = view;
  const hubEnd = hub[hub.length - 1];
  const r2 = gp.impeller_outlet_radius;
  const b2 = gp.blade_height_outlet;
  const r1Hub = gp.inducer_hub_radius;
  const r1Tip = gp.inducer_tip_radius;

  return (
    <div className="flex h-full flex-col items-center justify-center overflow-auto p-3">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="max-h-full w-full"
        role="img"
        aria-label={`Meridional flow path: exit radius ${fmtNumber(r2 * 1000, { decimals: 1 })} millimetres, exit blade height ${fmtNumber(b2 * 1000, { decimals: 2 })} millimetres.`}
      >
        {/* Axis of rotation (centerline, dash-dot per drawing convention) */}
        <line
          x1={x(view.zMin) - 24}
          y1={y(0)}
          x2={x(view.zMax) + 36}
          y2={y(0)}
          className="stroke-text-muted"
          strokeWidth={0.75}
          strokeDasharray="10 3 2 3"
        />
        <text
          x={x(view.zMin) - 24}
          y={y(0) + 12}
          className="fill-text-muted text-[9px]"
        >
          axis (z)
        </text>

        {/* Hub + shroud contours */}
        <path d={path(hub)} className="stroke-text" strokeWidth={1.6} fill="none" />
        <path d={path(shroud)} className="stroke-text" strokeWidth={1.6} fill="none" />
        <text
          x={x(hub[Math.floor(hub.length * 0.45)][0]) + 4}
          y={y(hub[Math.floor(hub.length * 0.45)][1]) + 12}
          className="fill-text-muted text-[9px]"
        >
          hub
        </text>
        <text
          x={x(shroud[Math.floor(shroud.length * 0.45)][0]) - 4}
          y={y(shroud[Math.floor(shroud.length * 0.45)][1]) - 6}
          className="fill-text-muted text-[9px]"
          textAnchor="end"
        >
          shroud
        </text>

        {/* Eye radii (z = 0 end) */}
        <DimLine
          x1={x(hub[0][0])}
          y1={y(0)}
          x2={x(hub[0][0])}
          y2={y(r1Hub)}
          label={`r₁h ${fmtNumber(r1Hub * 1000, { decimals: 1 })}`}
          labelX={x(hub[0][0]) - 6}
          labelY={y(r1Hub / 2)}
          anchor="end"
        />
        <DimLine
          x1={x(shroud[0][0]) - 26}
          y1={y(0)}
          x2={x(shroud[0][0]) - 26}
          y2={y(r1Tip)}
          label={`r₁t ${fmtNumber(r1Tip * 1000, { decimals: 1 })}`}
          labelX={x(shroud[0][0]) - 32}
          labelY={y(r1Tip / 2)}
          anchor="end"
        />

        {/* Exit radius r2 (vertical, outside the trailing edge) */}
        <DimLine
          x1={x(hubEnd[0]) + 26}
          y1={y(0)}
          x2={x(hubEnd[0]) + 26}
          y2={y(r2)}
          label={`r₂ ${fmtNumber(r2 * 1000, { decimals: 1 })}`}
          labelX={x(hubEnd[0]) + 32}
          labelY={y(r2 / 2)}
          anchor="start"
        />

        {/* Exit passage height b2 (axial bracket at the trailing edge). The
            meshed shroud sits a further tip-clearance beyond the b2 tick —
            the bracket is drawn at exactly b2 so the label matches it. */}
        <DimLine
          x1={x(hubEnd[0] - b2)}
          y1={y(r2) - 12}
          x2={x(hubEnd[0])}
          y2={y(r2) - 12}
          label={`b₂ ${fmtNumber(b2 * 1000, { decimals: 2 })}`}
          labelX={(x(hubEnd[0] - b2) + x(hubEnd[0])) / 2}
          labelY={y(r2) - 18}
          anchor="middle"
        />
      </svg>
      <p className="mt-1 text-center text-[10px] text-text-muted">
        Hub/shroud contour as meshed — the same curves the exports use.
        Dimensions in mm.
      </p>
    </div>
  );
}

/** Thin dimension line with end ticks and a label. */
function DimLine({
  x1,
  y1,
  x2,
  y2,
  label,
  labelX,
  labelY,
  anchor,
}: {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  label: string;
  labelX: number;
  labelY: number;
  anchor: "start" | "middle" | "end";
}) {
  const vertical = Math.abs(x2 - x1) < 0.5;
  const tick = 3;
  return (
    <g className="stroke-brand-text" strokeWidth={0.75}>
      <line x1={x1} y1={y1} x2={x2} y2={y2} />
      {vertical ? (
        <>
          <line x1={x1 - tick} y1={y1} x2={x1 + tick} y2={y1} />
          <line x1={x2 - tick} y1={y2} x2={x2 + tick} y2={y2} />
        </>
      ) : (
        <>
          <line x1={x1} y1={y1 - tick} x2={x1} y2={y1 + tick} />
          <line x1={x2} y1={y2 - tick} x2={x2} y2={y2 + tick} />
        </>
      )}
      <text
        x={labelX}
        y={labelY}
        textAnchor={anchor}
        className="fill-brand-text text-[9px]"
        stroke="none"
      >
        {label}
      </text>
    </g>
  );
}
