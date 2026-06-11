"use client";

import { useEffect, useRef } from "react";

/**
 * AsciiTurbine — an animated ASCII radial-inflow rotor, face-on.
 *
 * Seven log-spiral blades sweep between hub and shroud on a canvas
 * character grid, each arm shaded as a solid ribbon (bright leading edge
 * → core → trail) in brand cyan. Built as background art: chunky cells,
 * no interactivity, and a very slow constant spin (set `speed` in rad/s).
 * Dim it with a wrapper opacity. Honors prefers-reduced-motion (static
 * frame), pauses off-screen, theme-aware via tokens. Pure decoration.
 */
export function AsciiTurbine({
  className,
  height = 720,
  speed = 0.08,
}: {
  className?: string;
  height?: number;
  speed?: number;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    if (!wrap || !canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduceMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    const CW = 8; // cell width
    const CH = 11; // cell height
    const BLADES = 5;
    const CURVE = 0.9; // log-spiral blade curvature (~70° wrap hub→tip)
    const TH = 13; // blade half-thickness (px), constant along the arm
    const TAU = Math.PI * 2;
    const GRAD = Math.sqrt(1 + CURVE * CURVE);

    let w = 0;
    const h = height;
    let dpr = 1;

    const LEVELS = 14;
    let lutDim: string[] = [];
    let lutMid: string[] = [];
    let lutHot: string[] = [];

    function readTheme() {
      const cs = getComputedStyle(document.documentElement);
      const dim = cs.getPropertyValue("--border-strong").trim() || "96 112 136";
      const mid = cs.getPropertyValue("--text-muted").trim() || "148 158 174";
      const hot = cs.getPropertyValue("--brand-default").trim() || "78 199 216";
      const build = (t: string) =>
        Array.from({ length: LEVELS + 1 }, (_, i) =>
          `rgb(${t} / ${(i / LEVELS).toFixed(3)})`,
        );
      lutDim = build(dim);
      lutMid = build(mid);
      lutHot = build(hot);
    }
    readTheme();
    const themeWatch = new MutationObserver(readTheme);
    themeWatch.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    function resize() {
      const rect = wrap!.getBoundingClientRect();
      w = rect.width;
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      canvas!.width = Math.round(w * dpr);
      canvas!.height = Math.round(h * dpr);
      canvas!.style.width = `${w}px`;
      canvas!.style.height = `${h}px`;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx!.font = '9px "JetBrains Mono", ui-monospace, monospace';
      ctx!.textAlign = "center";
      ctx!.textBaseline = "middle";
    }
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(wrap);

    let visible = true;
    const io = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
      },
      { threshold: 0 },
    );
    io.observe(wrap);

    function frame(tMs: number) {
      const spin = (tMs / 1000) * speed;

      ctx!.clearRect(0, 0, w, h);

      const cx = w / 2;
      const cy = h / 2;
      const rTip = Math.min(w, h) / 2 - 12;
      const rHub = Math.max(20, rTip * 0.22);
      const cols = Math.ceil(w / CW);
      const rows = Math.ceil(h / CH);

      for (let j = 0; j < rows; j++) {
        const y = j * CH + CH / 2;
        for (let i = 0; i < cols; i++) {
          const x = i * CW + CW / 2;
          const dx = x - cx;
          const dy = y - cy;
          const r = Math.hypot(dx, dy);

          if (r > rTip + 8) continue;

          // Shroud ring — a solid circular casing.
          if (Math.abs(r - rTip) < 6) {
            ctx!.fillStyle = lutMid[6];
            ctx!.fillText("o", x, y);
            continue;
          }
          // Hub.
          if (r < rHub) {
            ctx!.fillStyle = r < rHub * 0.45 ? lutMid[8] : lutDim[6];
            ctx!.fillText(r < rHub * 0.45 ? "+" : "#", x, y);
            continue;
          }
          if (r > rTip) continue;

          // Log-spiral blade field, rotating slowly. Arms are drawn at a
          // constant spatial thickness (signed distance to the blade
          // centerline) so they read as clean ribbons at mural scale.
          const theta = Math.atan2(dy, dx);
          const phase = BLADES * (theta - spin + CURVE * Math.log(r / rHub));
          const m = ((phase % TAU) + TAU) % TAU;
          const sgn = m < Math.PI ? m : m - TAU;
          const dist = (Math.abs(sgn) / BLADES) * (r / GRAD);

          // Taper thickness toward the root so the passages stay open.
          const th = TH * Math.min(1, (r - rHub) / (rHub * 0.9) + 0.25);
          if (dist > th) continue;

          // Bright leading edge along one side of each arm.
          const edge = sgn > 0 && dist > th * 0.55;
          ctx!.fillStyle = lutHot[edge ? 13 : 8];
          ctx!.fillText(edge ? "@" : "#", x, y);
        }
      }
    }

    let raf = 0;
    let last = 0;
    function loop(tMs: number) {
      raf = requestAnimationFrame(loop);
      if (!visible) return;
      // A slow wheel doesn't need fast frames.
      if (tMs - last < 66) return; // ~15 fps
      last = tMs;
      frame(tMs);
    }

    if (reduceMotion) {
      frame(0);
    } else {
      raf = requestAnimationFrame(loop);
    }

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      themeWatch.disconnect();
    };
  }, [height, speed]);

  return (
    <div ref={wrapRef} aria-hidden className={className}>
      <canvas ref={canvasRef} className="block w-full" style={{ height }} />
    </div>
  );
}
