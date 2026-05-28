"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTheme } from "next-themes";
import { Pause, Play } from "lucide-react";
import type { Data, Layout } from "plotly.js";
import { Plot, defaultPlotLayout } from "@/components/plot/plotly-host";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import type { RotorMode, RotorModeShapeNode, RotorShape } from "@/lib/api/types";
import { MODE_COLOURS } from "./critical-speed-map";

interface ModeShapesProps {
  modes: RotorMode[];
  shape: RotorShape;
}

/** Visual angular frequency for the animation — target ~1.5 Hz orbit. */
const VISUAL_OMEGA_DEFAULT = 2 * Math.PI * 1.5;

/**
 * Compute animated y/z at a given time `t` [seconds].
 *
 * The full orbit rotation formula (API 684 whirl convention):
 *   forward  whirl: y_anim =  y·cos(ωt) - z·sin(ωt)
 *                  z_anim =  y·sin(ωt) + z·cos(ωt)
 *   backward whirl: z_anim negated ⇒ opposite rotation direction
 *   (planar / unknown): treat same as forward)
 *
 * At t=0 both formulas return the original (y, z), preserving the static view.
 */
function animateNode(
  node: RotorModeShapeNode,
  t: number,
  omega: number,
  whirl: RotorMode["whirl"],
): { y: number; z: number } {
  const c = Math.cos(omega * t);
  const s = Math.sin(omega * t);
  const dir = whirl === "backward" ? -1 : 1;
  return {
    y: node.y * c - dir * node.z * s,
    z: dir * node.y * s + node.z * c,
  };
}

// ---------------------------------------------------------------------------
// Animated SVG renderer — direct DOM mutation, no React re-render per frame.
// ---------------------------------------------------------------------------

interface AnimatedModeShapeProps {
  nodes: RotorModeShapeNode[];
  whirl: RotorMode["whirl"];
  omega: number;
  colour: string;
}

/**
 * SVG panel that animates the mode shape using requestAnimationFrame.
 * Uses a ref-based path mutation approach (same pattern as ModeShapeAnimator
 * in the learn curriculum) to avoid React re-renders at 60 FPS.
 */
function AnimatedModeShape({
  nodes,
  whirl,
  omega,
  colour,
}: AnimatedModeShapeProps) {
  const yPathRef = useRef<SVGPathElement | null>(null);
  const zPathRef = useRef<SVGPathElement | null>(null);
  const tStartRef = useRef<number | null>(null);
  const rafRef = useRef<number>(0);

  // Cache node arrays in refs so the RAF closure sees the latest values
  // without being re-registered on every prop change.
  const nodesRef = useRef(nodes);
  const whirlRef = useRef(whirl);
  const omegaRef = useRef(omega);
  useEffect(() => { nodesRef.current = nodes; }, [nodes]);
  useEffect(() => { whirlRef.current = whirl; }, [whirl]);
  useEffect(() => { omegaRef.current = omega; }, [omega]);

  // SVG viewport parameters.
  const W = 600;
  const H = 160;
  const PAD_X = 24;
  const PAD_Y = 24;
  const plotW = W - 2 * PAD_X;
  const plotH = H - 2 * PAD_Y;
  const yMid = PAD_Y + plotH / 2;

  const buildPaths = useCallback(
    (t: number): { yD: string; zD: string } => {
      const ns = nodesRef.current;
      if (ns.length === 0) return { yD: "", zD: "" };
      // Map axial positions to SVG x-coordinates.
      const xMin = ns[0].axial_position_m;
      const xMax = ns[ns.length - 1].axial_position_m;
      const xRange = xMax - xMin || 1;
      // Scale: half-height for amplitude (max normalised displacement = 1).
      const scale = (plotH / 2) * 0.8;
      let yD = "";
      let zD = "";
      for (let i = 0; i < ns.length; i++) {
        const n = ns[i];
        const animated = animateNode(n, t, omegaRef.current, whirlRef.current);
        const svgX = PAD_X + ((n.axial_position_m - xMin) / xRange) * plotW;
        const svgY = yMid - animated.y * scale;
        const svgZ = yMid - animated.z * scale;
        const cmd = i === 0 ? "M" : "L";
        yD += `${cmd} ${svgX.toFixed(1)} ${svgY.toFixed(1)} `;
        zD += `${cmd} ${svgX.toFixed(1)} ${svgZ.toFixed(1)} `;
      }
      return { yD, zD };
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  useEffect(() => {
    tStartRef.current = null;
    const tick = (now: number) => {
      if (tStartRef.current === null) tStartRef.current = now;
      const t = (now - tStartRef.current) / 1000;
      const { yD, zD } = buildPaths(t);
      yPathRef.current?.setAttribute("d", yD);
      zPathRef.current?.setAttribute("d", zD);
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [buildPaths]);

  // Initial static render at t=0.
  const { yD: initY, zD: initZ } = useMemo(() => buildPaths(0), [buildPaths]);

  const xMin = nodes[0]?.axial_position_m ?? 0;
  const xMax = nodes[nodes.length - 1]?.axial_position_m ?? 1;

  // Axis tick marks for x (every ~25% of rotor length).
  const tickXs = [0, 0.25, 0.5, 0.75, 1.0].map((f) => ({
    svgX: PAD_X + f * plotW,
    label: `${((xMin + f * (xMax - xMin)) * 1000).toFixed(0)}`,
  }));

  const dirLabel = whirl === "backward" ? "backward whirl" : whirl === "forward" ? "forward whirl" : whirl ?? "";

  return (
    <svg
      viewBox={`0 0 ${W} ${H + 28}`}
      xmlns="http://www.w3.org/2000/svg"
      preserveAspectRatio="xMidYMid meet"
      className="h-full w-full"
      role="img"
      aria-label={`Animated mode shape — ${dirLabel}`}
    >
      {/* Grid lines */}
      <line
        x1={PAD_X} y1={yMid} x2={W - PAD_X} y2={yMid}
        stroke="currentColor" strokeOpacity={0.15} strokeDasharray="3 5" strokeWidth={1}
        className="text-text-muted"
      />
      {tickXs.map(({ svgX }) => (
        <line
          key={svgX}
          x1={svgX} y1={PAD_Y} x2={svgX} y2={H - PAD_Y}
          stroke="currentColor" strokeOpacity={0.08} strokeWidth={1}
          className="text-text-muted"
        />
      ))}
      {/* ±1 reference lines */}
      {[-1, 1].map((sign) => (
        <line
          key={sign}
          x1={PAD_X} y1={yMid - sign * (plotH / 2) * 0.8}
          x2={W - PAD_X} y2={yMid - sign * (plotH / 2) * 0.8}
          stroke="currentColor" strokeOpacity={0.07} strokeWidth={1}
          className="text-text-muted"
        />
      ))}
      {/* X axis labels */}
      {tickXs.map(({ svgX, label }) => (
        <text
          key={svgX}
          x={svgX} y={H + 14}
          textAnchor="middle"
          fontSize={10}
          fill="currentColor" fillOpacity={0.45}
          className="text-text-muted"
        >
          {label}
        </text>
      ))}
      <text x={W / 2} y={H + 26} textAnchor="middle" fontSize={9} fill="currentColor" fillOpacity={0.35} className="text-text-muted">
        Axial position [mm]
      </text>
      {/* Animated traces */}
      <path
        ref={yPathRef}
        d={initY}
        fill="none"
        stroke={colour}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        ref={zPathRef}
        d={initZ}
        fill="none"
        stroke={colour}
        strokeWidth={1.4}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray="4 3"
      />
      {/* Legend */}
      <line x1={PAD_X} y1={8} x2={PAD_X + 16} y2={8} stroke={colour} strokeWidth={2} />
      <text x={PAD_X + 20} y={11} fontSize={9} fill="currentColor" fillOpacity={0.55} className="text-text-muted">y (radial 1)</text>
      <line x1={PAD_X + 80} y1={8} x2={PAD_X + 96} y2={8} stroke={colour} strokeWidth={1.4} strokeDasharray="4 3" />
      <text x={PAD_X + 100} y={11} fontSize={9} fill="currentColor" fillOpacity={0.55} className="text-text-muted">z (radial 2)</text>
    </svg>
  );
}

/**
 * Mode shapes from the real eigensolver (ADAPT-005). Each mode renders the
 * y- and z-displacement traces of its eigenvector projected onto the rotor
 * axial stations. A picker on the right switches between modes; the page
 * defaults to mode 1.
 *
 * The eigenvector data ships in `mode.mode_shape` as
 * `[{ axial_position_m, y, z }, ...]` already normalised to unit max
 * amplitude. The plot's x-axis is in mm to match the rotor sketch.
 *
 * W-28: play/pause button animates the mode shape as a rotating orbit.
 * Animation is paused by default and respects `prefers-reduced-motion`.
 */
export function ModeShapes({ modes, shape }: ModeShapesProps) {
  const theme = useTheme().resolvedTheme === "dark" ? "dark" : "light";
  const [selected, setSelected] = useState<number>(0);

  // W-28 animation state. Default paused; honour prefers-reduced-motion.
  const prefersReducedMotion =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const [playing, setPlaying] = useState(false);
  // Speed multiplier: 0.25 – 4×, step 0.25. Stored as index into slider.
  const [speedMult, setSpeedMult] = useState(1.0);

  const validIdx = Math.min(selected, Math.max(modes.length - 1, 0));
  const mode = modes[validIdx];

  const { data, layout, summary, fallback } = useMemo(() => {
    if (!mode) {
      return {
        data: [] as Data[],
        layout: defaultPlotLayout(theme),
        summary: null,
        fallback: false,
      };
    }

    // Prefer the real eigenvector if the backend supplied it. Otherwise
    // fall back to a `sin(n·π·x/L)` placeholder so the page still has
    // *something* to show.
    let xsMm: number[];
    let ys: number[];
    let zs: number[];
    let fallback = false;
    if (mode.mode_shape && mode.mode_shape.length > 1) {
      xsMm = mode.mode_shape.map((n) => n.axial_position_m * 1000);
      ys = mode.mode_shape.map((n) => n.y);
      zs = mode.mode_shape.map((n) => n.z);
    } else {
      const L = shape.totalLength || 1;
      const n = validIdx + 1;
      const N = 60;
      xsMm = Array.from({ length: N }, (_, i) => (L * i) / (N - 1));
      ys = xsMm.map((x) => Math.sin((n * Math.PI * x) / L));
      zs = ys.map(() => 0);
      fallback = true;
    }

    const colour = MODE_COLOURS[validIdx % MODE_COLOURS.length];
    const traces: Data[] = [
      {
        type: "scatter",
        mode: "lines",
        name: "y (radial 1)",
        x: xsMm,
        y: ys,
        line: { color: colour, width: 2 },
      },
      {
        type: "scatter",
        mode: "lines",
        name: "z (radial 2)",
        x: xsMm,
        y: zs,
        line: { color: colour, width: 1.4, dash: "dot" },
      },
      {
        type: "scatter",
        mode: "lines",
        name: "centreline",
        x: [xsMm[0], xsMm[xsMm.length - 1]],
        y: [0, 0],
        line: { color: "rgb(var(--text-muted))", width: 0.6, dash: "dash" },
        hoverinfo: "skip",
        showlegend: false,
      },
    ];

    const summary = {
      freqHz: mode.frequency_hz,
      freqRpm: mode.frequency_rpm,
      whirl: mode.whirl,
      damping: mode.damping_ratio,
      logDec: mode.log_decrement,
    };

    return {
      data: traces,
      layout: {
        ...defaultPlotLayout(theme),
        xaxis: {
          ...defaultPlotLayout(theme).xaxis,
          title: { text: "Axial position [mm]" },
        },
        yaxis: {
          ...defaultPlotLayout(theme).yaxis,
          title: { text: "Normalised displacement" },
          zeroline: true,
        },
        showlegend: true,
        legend: {
          ...(defaultPlotLayout(theme).legend ?? {}),
          orientation: "h",
          y: -0.18,
        },
      } satisfies Partial<Layout>,
      summary,
      fallback,
    };
  }, [mode, shape, theme, validIdx]);

  if (!mode) {
    return (
      <div className="flex h-full w-full items-center justify-center text-xs text-text-muted">
        No modes available — run the lateral analysis first.
      </div>
    );
  }

  // Animated nodes: only available when real eigenvector data is present.
  const animNodes = !fallback && mode.mode_shape && mode.mode_shape.length > 1
    ? mode.mode_shape
    : null;
  const canAnimate = animNodes !== null && !prefersReducedMotion;
  // Visual omega: base freq × speed multiplier, clamped to 0.25–4 Hz visually.
  const visualOmega = VISUAL_OMEGA_DEFAULT * speedMult;
  const colour = MODE_COLOURS[validIdx % MODE_COLOURS.length];

  return (
    <div className="flex h-full flex-col">
      {/* Toolbar row */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-2 pt-1">
        <div className="flex items-center gap-2">
          <label className="text-[10px] uppercase tracking-wide text-text-muted">
            Mode
          </label>
          <select
            className="h-7 rounded-sm border border-border-default bg-surface-input px-2 text-xs tabular-nums focus:outline-none focus:ring-2 focus:ring-border-focus"
            value={validIdx}
            onChange={(e) => {
              setSelected(Number(e.target.value));
              setPlaying(false);
            }}
            data-input="true"
          >
            {modes.map((m, i) => (
              <option key={i} value={i}>
                {i + 1} · {m.shape_name} · {m.frequency_hz.toFixed(1)} Hz
                {m.whirl && m.whirl !== "planar" ? ` · ${m.whirl}` : ""}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-3">
          {/* Speed multiplier slider — only show when animation is available */}
          {canAnimate && playing && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] uppercase tracking-wide text-text-muted">
                Speed
              </span>
              <Slider
                className="w-24"
                min={0.25}
                max={4}
                step={0.25}
                value={[speedMult]}
                onValueChange={(v) => setSpeedMult(v[0])}
                aria-label="Animation speed multiplier"
              />
              <span className="w-7 text-[11px] tabular-nums text-text-muted">
                {speedMult.toFixed(2)}×
              </span>
            </div>
          )}

          {/* Play / Pause button (W-28 AC1) */}
          {canAnimate && (
            <Button
              variant="outline"
              size="sm"
              className="h-7 gap-1.5 px-2 text-xs"
              onClick={() => setPlaying((p) => !p)}
              aria-label={playing ? "Pause mode-shape animation" : "Play mode-shape animation"}
            >
              {playing ? (
                <>
                  <Pause className="h-3 w-3" aria-hidden="true" />
                  Pause
                </>
              ) : (
                <>
                  <Play className="h-3 w-3" aria-hidden="true" />
                  Animate
                </>
              )}
            </Button>
          )}

          {/* Mode metadata chips */}
          {summary && (
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-[11px] text-text-muted">
              <span>
                <span className="text-text-muted/70">freq</span>{" "}
                <span className="font-mono tabular-nums text-text">
                  {summary.freqHz.toFixed(2)} Hz
                </span>
              </span>
              {summary.freqRpm !== undefined && (
                <span>
                  <span className="text-text-muted/70">≡</span>{" "}
                  <span className="font-mono tabular-nums text-text">
                    {summary.freqRpm.toLocaleString(undefined, {
                      maximumFractionDigits: 0,
                    })}{" "}
                    rpm
                  </span>
                </span>
              )}
              <span>
                <span className="text-text-muted/70">ζ</span>{" "}
                <span className="font-mono tabular-nums text-text">
                  {summary.damping.toExponential(2)}
                </span>
              </span>
              {summary.logDec !== undefined && summary.logDec !== null && (
                <span>
                  <span className="text-text-muted/70">δ</span>{" "}
                  <span className="font-mono tabular-nums text-text">
                    {summary.logDec.toFixed(3)}
                  </span>
                </span>
              )}
              {summary.whirl && (
                <span className="rounded-sm border border-border-subtle bg-surface-subtle px-1.5 py-0.5 text-[10px] uppercase tracking-wide">
                  {summary.whirl}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {fallback && (
        <div className="px-2 pb-1 pt-1 text-[10px] text-semantic-warning-text">
          Eigenvector not returned by solver — showing sin(n·π·x/L) placeholder.
        </div>
      )}

      {/* Plot area: animated SVG when playing, static Plotly when paused (W-28 AC2, AC3) */}
      <div className="flex-1 min-h-0">
        {canAnimate && playing && animNodes ? (
          <AnimatedModeShape
            key={validIdx}
            nodes={animNodes}
            whirl={mode.whirl}
            omega={visualOmega}
            colour={colour}
          />
        ) : (
          <Plot data={data} layout={layout} />
        )}
      </div>
    </div>
  );
}
