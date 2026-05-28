"use client";

/**
 * Velocity-triangle SVG widget (ADAPT-021).
 *
 * Renders the rotor inlet (1) and rotor exit (2) velocity triangles from
 * the real mean-line solver result. The vectors are pinned to the
 * meridional/tangential frame: tangential is +x, meridional is +y (up).
 *
 *  - U (blade speed) is purely tangential.
 *  - V (absolute) is decomposed into (V_meridional, V_theta).
 *  - W = V − U  →  same meridional, tangential = V_theta − U.
 *
 * The geometry is scaled per-panel so the dominant vector always fills the
 * SVG viewport, regardless of whether U or W is the larger vector. When a
 * `design` triangle is also passed it is rendered in a dimmed colour so
 * the user can compare the active operating point to the original design.
 */

import type { VelocityTriangleBackend } from "@/lib/api/types";

export interface VelocityTriangle {
  /** Blade speed [m/s]. */
  U: number;
  /** Absolute velocity [m/s]. */
  V: number;
  /** Absolute flow angle from meridional [deg]. */
  alpha: number;
  /** Relative flow angle from meridional [deg]. */
  beta: number;
}

interface VelocityTrianglesProps {
  /** Backend triangle for the *active* operating point at the rotor inlet. */
  inlet?: VelocityTriangleBackend | VelocityTriangle;
  /** Backend triangle for the *active* operating point at the rotor exit. */
  exit?: VelocityTriangleBackend | VelocityTriangle;
  /** Optional design-point triangles to overlay (dimmed). */
  designInlet?: VelocityTriangleBackend | VelocityTriangle;
  designExit?: VelocityTriangleBackend | VelocityTriangle;
}

/** Internal shape we render — combines the backend wire format and the
 * legacy {U, V, alpha, beta} shape so both consumers keep compiling. */
interface NormalizedTriangle {
  U: number;
  V_meridional: number;
  V_theta: number;
  W_meridional: number;
  W_theta: number;
  V: number;
  W: number;
  alpha_flow_deg: number;
  beta_flow_deg: number;
}

function normalize(
  t: VelocityTriangleBackend | VelocityTriangle | undefined,
): NormalizedTriangle | undefined {
  if (!t) return undefined;
  // Backend shape — already has all the pieces we need.
  if ("V_meridional" in t) {
    return {
      U: t.U,
      V_meridional: t.V_meridional,
      V_theta: t.V_theta,
      W_meridional: t.W_meridional,
      W_theta: t.W_theta,
      V: t.V,
      W: t.W,
      alpha_flow_deg: t.alpha_flow_deg,
      beta_flow_deg: t.beta_flow_deg,
    };
  }
  // Legacy {U, V, alpha, beta} shape used by `defaultInletTriangle()` /
  // `defaultExitTriangle()` callers. We derive components from α (angle of
  // V from meridional) and β (angle of W from meridional).
  const alphaRad = (t.alpha * Math.PI) / 180;
  const V_meridional = t.V * Math.cos(alphaRad);
  const V_theta = t.V * Math.sin(alphaRad);
  const W_theta = V_theta - t.U;
  const W_meridional = V_meridional;
  const W = Math.sqrt(W_meridional * W_meridional + W_theta * W_theta);
  return {
    U: t.U,
    V_meridional,
    V_theta,
    W_meridional,
    W_theta,
    V: t.V,
    W,
    alpha_flow_deg: t.alpha,
    beta_flow_deg: t.beta,
  };
}

export function VelocityTriangles({
  inlet,
  exit,
  designInlet,
  designExit,
}: VelocityTrianglesProps) {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <TrianglePanel
        title="Rotor inlet (1)"
        tri={normalize(inlet)}
        designTri={normalize(designInlet)}
      />
      <TrianglePanel
        title="Rotor exit (2)"
        tri={normalize(exit)}
        designTri={normalize(designExit)}
      />
    </div>
  );
}

function TrianglePanel({
  title,
  tri,
  designTri,
}: {
  title: string;
  tri: NormalizedTriangle | undefined;
  designTri?: NormalizedTriangle;
}) {
  return (
    <div className="rounded-md border border-border-subtle bg-surface px-3 py-3">
      <div className="mb-2 flex items-baseline justify-between">
        <h4 className="text-xs font-medium uppercase tracking-wide text-text-muted">
          {title}
        </h4>
        {tri ? (
          <span className="text-xs text-text-muted">
            α {tri.alpha_flow_deg.toFixed(0)}° · β{" "}
            {tri.beta_flow_deg.toFixed(0)}°
          </span>
        ) : null}
      </div>
      <svg viewBox="0 0 300 180" className="w-full">
        {tri ? (
          <>
            {designTri && designTri !== tri ? (
              <Triangle tri={designTri} dim />
            ) : null}
            <Triangle tri={tri} />
          </>
        ) : (
          <Empty />
        )}
      </svg>
      {tri ? (
        <ul className="mt-2 grid grid-cols-3 gap-1 text-xs">
          <Kv k="U" v={tri.U.toFixed(0) + " m/s"} />
          <Kv k="V" v={tri.V.toFixed(0) + " m/s"} />
          <Kv k="W" v={tri.W.toFixed(0) + " m/s"} />
        </ul>
      ) : null}
    </div>
  );
}

function Empty() {
  return (
    <g>
      <text
        x="150"
        y="90"
        textAnchor="middle"
        fontSize={11}
        fill="rgb(var(--text-muted))"
      >
        Run analysis to populate.
      </text>
    </g>
  );
}

/** Convert mean-line scalars into a triangle of canvas pixels.
 *
 * Frame: origin at the bottom-left, +x = tangential, +y = meridional (up).
 * We render `U` (blade speed) purely tangential, `V` from the origin to
 * (V_θ, V_m), and `W = V − U` from the U-tip to the V-tip.
 */
function Triangle({
  tri,
  dim = false,
}: {
  tri: NormalizedTriangle;
  dim?: boolean;
}) {
  const W = 280;
  const H = 160;
  const padX = 16;
  const padY = 14;
  const cx = padX;
  const cy = H - padY;

  // Scale by the largest absolute vector component so the picture fills
  // the SVG. We use |U|, |V|, |W| — and also |V_theta|, |V_meridional|
  // separately so a triangle dominated by tangential motion (U ≫ V_m)
  // still uses the vertical space.
  const maxX = Math.max(Math.abs(tri.U), Math.abs(tri.V_theta), 1);
  const maxY = Math.max(
    Math.abs(tri.V_meridional),
    Math.abs(tri.W_meridional),
    1,
  );
  const kx = (W - 2 * padX) / maxX;
  const ky = (H - 2 * padY) / maxY;
  const k = Math.min(kx, ky);

  // Anchor points
  const u_x = cx + tri.U * k;
  const u_y = cy;
  const v_x = cx + tri.V_theta * k;
  const v_y = cy - tri.V_meridional * k;
  // W vector: starts at U-tip, ends at V-tip
  const wTailX = u_x;
  const wTailY = u_y;
  const wHeadX = v_x;
  const wHeadY = v_y;

  const cU = dim ? "rgba(99, 102, 241, 0.35)" : "rgb(99, 102, 241)";
  const cV = dim ? "rgba(34, 197, 94, 0.35)" : "rgb(34, 197, 94)";
  const cW = dim ? "rgba(244, 114, 182, 0.35)" : "rgb(244, 114, 182)";

  return (
    <g>
      {!dim && (
        <>
          {/* meridional axis */}
          <line
            x1={cx}
            y1={cy}
            x2={cx}
            y2={padY}
            stroke="rgb(var(--border-default))"
            strokeDasharray="2 3"
          />
          {/* tangential axis */}
          <line
            x1={cx}
            y1={cy}
            x2={W - padX}
            y2={cy}
            stroke="rgb(var(--border-default))"
            strokeDasharray="2 3"
          />
          <text
            x={W - padX + 2}
            y={cy + 4}
            fontSize={9}
            fill="rgb(var(--text-muted))"
          >
            tangential
          </text>
          <text x={cx - 2} y={padY - 2} fontSize={9} fill="rgb(var(--text-muted))">
            meridional
          </text>
          {/* α arc — V from meridional axis */}
          <AngleArc
            cx={cx}
            cy={cy}
            radius={28}
            startAngleRad={-Math.PI / 2}
            endAngleRad={
              -Math.PI / 2 + (tri.alpha_flow_deg * Math.PI) / 180
            }
            color={cV}
            label={`α=${tri.alpha_flow_deg.toFixed(0)}°`}
          />
          {/* β arc — W from meridional axis. Sign matters: W_theta can be
              negative (turbine exit) so we cap to ±90° visually. */}
          <AngleArc
            cx={wTailX}
            cy={wTailY}
            radius={28}
            startAngleRad={-Math.PI / 2}
            endAngleRad={
              -Math.PI / 2 +
              (Math.sign(tri.W_theta) *
                Math.min(Math.abs(tri.beta_flow_deg), 89) *
                Math.PI) /
                180
            }
            color={cW}
            label={`β=${tri.beta_flow_deg.toFixed(0)}°`}
          />
        </>
      )}
      <Arrow x1={cx} y1={cy} x2={u_x} y2={u_y} color={cU} label="U" />
      <Arrow x1={cx} y1={cy} x2={v_x} y2={v_y} color={cV} label="V" />
      <Arrow
        x1={wTailX}
        y1={wTailY}
        x2={wHeadX}
        y2={wHeadY}
        color={cW}
        label="W"
      />
    </g>
  );
}

function AngleArc({
  cx,
  cy,
  radius,
  startAngleRad,
  endAngleRad,
  color,
  label,
}: {
  cx: number;
  cy: number;
  radius: number;
  startAngleRad: number;
  endAngleRad: number;
  color: string;
  label: string;
}) {
  const sx = cx + radius * Math.cos(startAngleRad);
  const sy = cy + radius * Math.sin(startAngleRad);
  const ex = cx + radius * Math.cos(endAngleRad);
  const ey = cy + radius * Math.sin(endAngleRad);
  const large = Math.abs(endAngleRad - startAngleRad) > Math.PI ? 1 : 0;
  const sweep = endAngleRad > startAngleRad ? 1 : 0;
  const midA = (startAngleRad + endAngleRad) / 2;
  const lx = cx + (radius + 9) * Math.cos(midA);
  const ly = cy + (radius + 9) * Math.sin(midA);
  return (
    <g>
      <path
        d={`M ${sx} ${sy} A ${radius} ${radius} 0 ${large} ${sweep} ${ex} ${ey}`}
        fill="none"
        stroke={color}
        strokeWidth={0.8}
        opacity={0.6}
      />
      <text
        x={lx}
        y={ly}
        fontSize={8}
        fill={color}
        textAnchor="middle"
        dominantBaseline="middle"
      >
        {label}
      </text>
    </g>
  );
}

function Arrow({
  x1,
  y1,
  x2,
  y2,
  color,
  label,
}: {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color: string;
  label: string;
}) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.max(1e-6, Math.sqrt(dx * dx + dy * dy));
  const ux = dx / len;
  const uy = dy / len;
  const headSize = 6;
  const headLeftX = x2 - headSize * (ux + 0.5 * uy);
  const headLeftY = y2 - headSize * (uy - 0.5 * ux);
  const headRightX = x2 - headSize * (ux - 0.5 * uy);
  const headRightY = y2 - headSize * (uy + 0.5 * ux);
  return (
    <g>
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={1.6} />
      <polygon
        points={`${x2},${y2} ${headLeftX},${headLeftY} ${headRightX},${headRightY}`}
        fill={color}
      />
      <text
        x={(x1 + x2) / 2 + 4}
        y={(y1 + y2) / 2 - 4}
        fontSize={10}
        fill={color}
        fontFamily="var(--font-mono)"
      >
        {label}
      </text>
    </g>
  );
}

function Kv({ k, v }: { k: string; v: string }) {
  return (
    <li className="rounded-sm border border-border-subtle bg-surface-subtle px-1.5 py-1">
      <div className="text-[10px] uppercase tracking-wide text-text-muted">
        {k}
      </div>
      <div className="font-mono tabular-nums">{v}</div>
    </li>
  );
}

/* ---------------------------------------------------------------------------
 * Legacy fallbacks — kept for page.tsx callsites that still pre-populate the
 * widget before the user clicks "Run analysis".
 * ------------------------------------------------------------------------- */

export function defaultInletTriangle(): VelocityTriangle {
  return { U: 320, V: 280, alpha: 75, beta: 32 };
}
export function defaultExitTriangle(): VelocityTriangle {
  return { U: 120, V: 90, alpha: 30, beta: 62 };
}
