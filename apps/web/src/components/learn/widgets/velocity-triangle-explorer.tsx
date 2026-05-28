"use client";

import { useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { WidgetFrame } from "./widget-frame";
import { cn } from "@/lib/utils";

interface TriangleState {
  uOverCm: number;
  beta1: number; // degrees, relative inlet blade angle (from axial)
  beta2: number; // degrees, relative exit blade angle
}

const DEFAULT_STATE: TriangleState = {
  uOverCm: 1.0,
  beta1: 30,
  beta2: -40,
};

const DEG = Math.PI / 180;

interface ComputedTriangle {
  /** Meridional component (axial component normalized). */
  cm: number;
  /** Blade speed. */
  u: number;
  /** Relative angle from axial (radians). */
  beta: number;
  /** Tangential velocity (absolute frame). */
  vTheta: number;
  /** Absolute V magnitude. */
  V: number;
  /** Relative W magnitude. */
  W: number;
}

function triangle(uOverCm: number, betaDeg: number): ComputedTriangle {
  const cm = 1;
  const u = uOverCm * cm;
  const beta = betaDeg * DEG;
  // The blade-relative tangential component is cm·tan(β); add the wheel
  // speed to recover the absolute tangential velocity.
  const wTheta = cm * Math.tan(beta);
  const vTheta = u + wTheta;
  const V = Math.sqrt(cm * cm + vTheta * vTheta);
  const W = Math.sqrt(cm * cm + wTheta * wTheta);
  return { cm, u, beta, vTheta, V, W };
}

interface TriangleResult {
  inlet: ComputedTriangle;
  exit: ComputedTriangle;
  /** Euler specific work, Δh₀ = U · ΔV_θ (assumes constant radius). */
  deltaH0: number;
  /** Approximate reaction degree, ideal axial stage. */
  reaction: number;
}

function computeStage(state: TriangleState): TriangleResult {
  const inlet = triangle(state.uOverCm, state.beta1);
  const exit = triangle(state.uOverCm, state.beta2);
  const deltaH0 = inlet.u * (inlet.vTheta - exit.vTheta);
  // Static enthalpy drop in rotor ≈ ½(W2² − W1²) + ½(U1² − U2²); we assume
  // U1 = U2 (constant radius). Reaction = static drop in rotor / total drop.
  const dhRotor = 0.5 * (exit.W * exit.W - inlet.W * inlet.W);
  const dhStage = inlet.u * (inlet.vTheta - exit.vTheta);
  // Avoid division by zero when no work.
  const reaction = Math.abs(dhStage) < 1e-6 ? 0 : dhRotor / dhStage;
  return { inlet, exit, deltaH0, reaction };
}

export function VelocityTriangleExplorer() {
  const [state, setState] = useState<TriangleState>(DEFAULT_STATE);
  const result = useMemo(() => computeStage(state), [state]);

  const warnings: string[] = [];
  if (result.reaction < 0)
    warnings.push("Negative reaction — the rotor is accelerating relative flow, not decelerating it. Unphysical for a turbine.");
  if (Math.abs(state.beta1) > 75 || Math.abs(state.beta2) > 75)
    warnings.push("Blade angle exceeds 75°. Real rotors stall and accumulate severe loss in this range.");

  return (
    <WidgetFrame
      label="Velocity triangles"
      caption="Inlet and exit, axial stage at constant radius"
      onReset={() => setState(DEFAULT_STATE)}
      bodyHeight="540px"
    >
      <div className="grid h-full grid-cols-1 gap-3 p-3 lg:grid-cols-[1fr_220px]">
        <div className="flex min-h-0 flex-col gap-3">
          <div className="grid flex-1 min-h-0 grid-cols-2 gap-3">
            <TriangleSvg title="Inlet" t={result.inlet} />
            <TriangleSvg title="Exit" t={result.exit} />
          </div>
          {warnings.length > 0 && (
            <div className="flex flex-col gap-1.5 rounded-md border border-semantic-warning-border bg-semantic-warning-surface px-3 py-2 text-xs text-semantic-warning-text">
              {warnings.map((w, i) => (
                <div key={i} className="flex items-start gap-1.5">
                  <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                  <span>{w}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="flex flex-col gap-3 overflow-y-auto pr-1 scrollbar-subtle">
          <ControlRow
            label="U / Cm"
            value={state.uOverCm.toFixed(2)}
          >
            <Slider
              min={0.5}
              max={3.0}
              step={0.05}
              value={[state.uOverCm]}
              onValueChange={(v) =>
                setState((s) => ({ ...s, uOverCm: v[0] }))
              }
            />
          </ControlRow>
          <ControlRow label="β₁ (inlet)" value={`${state.beta1}°`}>
            <Slider
              min={-60}
              max={60}
              step={1}
              value={[state.beta1]}
              onValueChange={(v) =>
                setState((s) => ({ ...s, beta1: Math.round(v[0]) }))
              }
            />
          </ControlRow>
          <ControlRow label="β₂ (exit)" value={`${state.beta2}°`}>
            <Slider
              min={-60}
              max={60}
              step={1}
              value={[state.beta2]}
              onValueChange={(v) =>
                setState((s) => ({ ...s, beta2: Math.round(v[0]) }))
              }
            />
          </ControlRow>
          <div className="h-px bg-border-subtle" />
          <Readout
            label="Δh₀ / Cm²"
            value={result.deltaH0.toFixed(2)}
            unit=""
          />
          <Readout
            label="Reaction R"
            value={result.reaction.toFixed(2)}
            unit=""
            tone={result.reaction < 0 ? "warning" : "neutral"}
          />
          <Readout
            label="V₁ / Cm"
            value={result.inlet.V.toFixed(2)}
            unit=""
          />
          <Readout
            label="W₁ / Cm"
            value={result.inlet.W.toFixed(2)}
            unit=""
          />
        </div>
      </div>
    </WidgetFrame>
  );
}

interface ArrowSpec {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color: string;
  label: string;
  /** Side of the line on which to draw the label ("left" = above, "right" = below). */
  side?: "above" | "below";
}

/**
 * Draws the velocity triangle for one station inside an SVG. The drawing
 * convention is engineering-standard: the wheel speed U points downstream
 * (here, to the right along x); the meridional (axial) component points
 * up; the relative W = V − U closes the triangle.
 */
function TriangleSvg({ title, t }: { title: string; t: ComputedTriangle }) {
  const PAD = 24;
  const W = 220;
  const H = 200;
  // Choose a scale that fits all arrows: longest magnitude is V or W or U.
  const maxMag = Math.max(t.V, t.W, t.u, 1.5);
  const scale = (Math.min(W, H) - PAD * 2) / (maxMag * 1.1);

  // Origin: bottom-left of the working area.
  const ox = PAD;
  const oy = H - PAD;
  // U: along +x from origin to (u*scale, 0)
  const uEnd: [number, number] = [ox + t.u * scale, oy];
  // V: from origin up and to the right by (vTheta*scale, -cm*scale)
  const vEnd: [number, number] = [
    ox + t.vTheta * scale,
    oy - t.cm * scale,
  ];
  // W: from U-end to V-end (closing the triangle)
  const wStart = uEnd;
  const wEnd = vEnd;

  const colors = {
    u: "var(--brand-text-color, currentColor)",
  };

  const arrows: ArrowSpec[] = [
    {
      x1: ox,
      y1: oy,
      x2: uEnd[0],
      y2: uEnd[1],
      color: "var(--vt-u)",
      label: "U",
      side: "below",
    },
    {
      x1: ox,
      y1: oy,
      x2: vEnd[0],
      y2: vEnd[1],
      color: "var(--vt-v)",
      label: "V",
      side: "above",
    },
    {
      x1: wStart[0],
      y1: wStart[1],
      x2: wEnd[0],
      y2: wEnd[1],
      color: "var(--vt-w)",
      label: "W",
      side: "above",
    },
  ];
  // ignore unused
  void colors;

  return (
    <div className="flex h-full flex-col gap-1 rounded-sm border border-border-subtle bg-background p-2">
      <div className="flex items-baseline justify-between text-xs">
        <span className="font-medium text-text">{title}</span>
        <span className="font-mono text-text-muted tabular-nums">
          V={t.V.toFixed(2)} · W={t.W.toFixed(2)}
        </span>
      </div>
      <div className="relative flex-1 min-h-0">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          xmlns="http://www.w3.org/2000/svg"
          preserveAspectRatio="xMidYMid meet"
          className="h-full w-full"
          style={{
            // CSS vars used by the arrows so they re-color on theme swap
            // without needing the JS-side useTheme hook.
            ["--vt-u" as never]: "rgb(31, 78, 121)",
            ["--vt-v" as never]: "rgb(46, 135, 84)",
            ["--vt-w" as never]: "rgb(194, 91, 31)",
          }}
        >
          <defs>
            <marker
              id="arrowhead-u"
              markerWidth="6"
              markerHeight="6"
              refX="5"
              refY="3"
              orient="auto"
            >
              <polygon points="0 0, 6 3, 0 6" fill="var(--vt-u)" />
            </marker>
            <marker
              id="arrowhead-v"
              markerWidth="6"
              markerHeight="6"
              refX="5"
              refY="3"
              orient="auto"
            >
              <polygon points="0 0, 6 3, 0 6" fill="var(--vt-v)" />
            </marker>
            <marker
              id="arrowhead-w"
              markerWidth="6"
              markerHeight="6"
              refX="5"
              refY="3"
              orient="auto"
            >
              <polygon points="0 0, 6 3, 0 6" fill="var(--vt-w)" />
            </marker>
          </defs>
          {/* Reference grid: a faint axial axis */}
          <line
            x1={ox}
            y1={oy}
            x2={ox}
            y2={PAD}
            stroke="rgb(193 197 203 / 0.4)"
            strokeDasharray="2 3"
          />
          <line
            x1={ox}
            y1={oy}
            x2={W - PAD}
            y2={oy}
            stroke="rgb(193 197 203 / 0.4)"
            strokeDasharray="2 3"
          />
          {arrows.map((a, i) => (
            <g key={i}>
              <line
                x1={a.x1}
                y1={a.y1}
                x2={a.x2}
                y2={a.y2}
                stroke={a.color}
                strokeWidth={2}
                markerEnd={`url(#arrowhead-${a.label.toLowerCase()})`}
              />
              <text
                x={(a.x1 + a.x2) / 2}
                y={(a.y1 + a.y2) / 2 + (a.side === "below" ? 14 : -6)}
                fill={a.color}
                fontFamily="var(--font-mono)"
                fontSize="12"
                textAnchor="middle"
              >
                {a.label}
              </text>
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
}

function ControlRow({
  label,
  value,
  children,
}: {
  label: string;
  value: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <Label className="text-sm">{label}</Label>
        <span className="font-mono text-xs tabular-nums text-text-muted">
          {value}
        </span>
      </div>
      {children}
    </div>
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
