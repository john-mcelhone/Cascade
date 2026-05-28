"use client";

import { useMemo } from "react";
import type { RotorSection, RotorShape } from "@/lib/api/types";

/** One row of the tabulated K/C-vs-RPM editor (ADAPT-024). */
export interface BearingTableRow {
  rpm: number;
  K_yy: number;
  K_zz: number;
  K_yz: number;
  K_zy: number;
  C_yy: number;
  C_zz: number;
  C_yz: number;
  C_zy: number;
}

export interface BearingDef {
  /** Stable identifier in the parent rotor model. */
  id: string;
  /** Axial position along the shaft (rotor-shape units, usually mm). */
  axialPosition: number;
  /** Direct + cross-coupled radial stiffness [N/m] -- API 684 §2.3. */
  K_yy: number;
  K_zz: number;
  K_yz: number;
  K_zy: number;
  /** Direct + cross-coupled radial damping [N·s/m]. */
  C_yy: number;
  C_zz: number;
  C_yz: number;
  C_zy: number;
  /** Optional tabulated K/C vs RPM (variable-speed analysis). */
  table?: BearingTableRow[];
  label?: string;
  /**
   * Legacy isotropic mirrors of K_yy / C_yy. Kept for backward compatibility
   * with code that hasn't migrated to the anisotropic shape. Always reflects
   * the average of the direct terms.
   */
  stiffness: number;
  damping: number;
}

interface RotorSketchProps {
  shape: RotorShape;
  /** Discrete bearings hovering above the rotor shape's `bearing` sections. */
  bearings: BearingDef[];
  /** ID of the currently selected bearing (highlighted in brand colour). */
  selectedBearingId?: string;
  onSelectBearing?: (id: string) => void;
}

/**
 * Side-view rotor sketch. Shafts as rectangles, disks as taller rectangles,
 * bearings as triangular supports. Clicking a bearing fires onSelectBearing
 * so the parent can pop the K-C editor.
 */
export function RotorSketch({
  shape,
  bearings,
  selectedBearingId,
  onSelectBearing,
}: RotorSketchProps) {
  const W = 760;
  const H = 160;
  const padX = 40;
  const total = shape.totalLength || 1;
  const scale = (W - padX * 2) / total;
  const cy = H / 2;

  const sectionEls = useMemo(
    () =>
      shape.sections.map((s, i) => (
        <SectionShape key={i} section={s} cy={cy} scale={scale} offset={padX} />
      )),
    [shape.sections, cy, scale],
  );

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full"
      role="img"
      aria-label="Rotor side view"
    >
      {/* Centreline */}
      <line
        x1={padX - 6}
        y1={cy}
        x2={W - padX + 6}
        y2={cy}
        stroke="rgb(var(--border-default))"
        strokeDasharray="2 3"
        strokeWidth={0.8}
      />
      {sectionEls}
      {bearings.map((b) => {
        const cx = padX + b.axialPosition * scale;
        const isSelected = b.id === selectedBearingId;
        const fill = isSelected
          ? "rgb(var(--brand-default))"
          : "rgb(var(--semantic-warning-default))";
        return (
          <g
            key={b.id}
            style={{ cursor: onSelectBearing ? "pointer" : "default" }}
            onClick={() => onSelectBearing?.(b.id)}
          >
            <polygon
              points={`${cx - 9},${cy + 28} ${cx + 9},${cy + 28} ${cx},${cy + 14}`}
              fill={fill}
              stroke={isSelected ? "rgb(var(--brand-default))" : "none"}
              strokeWidth={isSelected ? 2 : 0}
            />
            <polygon
              points={`${cx - 9},${cy - 28} ${cx + 9},${cy - 28} ${cx},${cy - 14}`}
              fill={fill}
              stroke={isSelected ? "rgb(var(--brand-default))" : "none"}
              strokeWidth={isSelected ? 2 : 0}
            />
            <line
              x1={cx}
              y1={cy + 14}
              x2={cx}
              y2={cy - 14}
              stroke={fill}
              strokeWidth={2}
            />
            {b.label && (
              <text
                x={cx}
                y={cy + 44}
                fontSize={9}
                textAnchor="middle"
                fill="rgb(var(--text-muted))"
              >
                {b.label}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

function SectionShape({
  section: s,
  cy,
  scale,
  offset,
}: {
  section: RotorSection;
  cy: number;
  scale: number;
  offset: number;
}) {
  const x = offset + s.axialStart * scale;
  const w = (s.axialEnd - s.axialStart) * scale;
  const r = Math.max(2, s.radius * 1.6);
  if (s.kind === "bearing") {
    // Bearing sections are drawn by the parent on top; here we still draw a
    // small shaft segment underneath so the rotor outline stays continuous.
    return (
      <rect
        x={x}
        y={cy - 6}
        width={w}
        height={12}
        fill="rgb(var(--border-strong))"
        opacity={0.7}
      />
    );
  }
  const fill =
    s.kind === "disk"
      ? "rgb(var(--brand-default))"
      : "rgb(var(--border-strong))";
  return (
    <g>
      <rect
        x={x}
        y={cy - r}
        width={w}
        height={r * 2}
        fill={fill}
        opacity={s.kind === "disk" ? 0.85 : 0.95}
        rx={1}
      />
      {s.label && (
        <text
          x={x + w / 2}
          y={cy - r - 6}
          fontSize={9}
          textAnchor="middle"
          fill="rgb(var(--text-muted))"
        >
          {s.label}
        </text>
      )}
    </g>
  );
}

/** Build an initial set of bearings from a RotorShape's `bearing` sections. */
export function bearingsFromShape(shape: RotorShape): BearingDef[] {
  const out: BearingDef[] = [];
  let idx = 1;
  for (const s of shape.sections) {
    if (s.kind !== "bearing") continue;
    out.push(
      defaultBearing({
        id: `B${idx}`,
        axialPosition: (s.axialStart + s.axialEnd) / 2,
        label: s.label ?? `B${idx}`,
      }),
    );
    idx += 1;
  }
  return out;
}

/**
 * Build a `BearingDef` with seeded API 684 K/C defaults. Used by
 * `bearingsFromShape` and by the bearing editor's "reset" affordance.
 *
 * The defaults are conservative isotropic plain-journal-style values
 * (K = 5e7 N/m, C = 1e3 N·s/m, zero cross-coupling). The legacy
 * `stiffness` / `damping` mirrors track the K_yy / C_yy direct terms.
 */
export function defaultBearing(
  overrides: Partial<BearingDef> & {
    id: string;
    axialPosition: number;
  },
): BearingDef {
  const K_default = 5e7;
  const C_default = 1e3;
  return {
    id: overrides.id,
    axialPosition: overrides.axialPosition,
    label: overrides.label,
    K_yy: overrides.K_yy ?? K_default,
    K_zz: overrides.K_zz ?? K_default,
    K_yz: overrides.K_yz ?? 0,
    K_zy: overrides.K_zy ?? 0,
    C_yy: overrides.C_yy ?? C_default,
    C_zz: overrides.C_zz ?? C_default,
    C_yz: overrides.C_yz ?? 0,
    C_zy: overrides.C_zy ?? 0,
    table: overrides.table,
    stiffness: overrides.stiffness ?? overrides.K_yy ?? K_default,
    damping: overrides.damping ?? overrides.C_yy ?? C_default,
  };
}
