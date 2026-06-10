"use client";

import { useEffect, useRef } from "react";

/**
 * AsciiTurbine — an animated ASCII radial-inflow rotor, face-on.
 *
 * Nine log-spiral blades sweep between hub and shroud on a canvas
 * character grid: glyph weight from blade intensity (· : + = * # % @),
 * brand-cyan blades over a faint dot fabric, a shroud ring, and a hub.
 * The wheel idles at a slow visual rpm and spins up while hovered.
 * Honors prefers-reduced-motion (static frame), pauses off-screen,
 * theme-aware via tokens. Pure decoration: aria-hidden.
 */
export function AsciiTurbine({
  className,
  height = 224,
}: {
  className?: string;
  height?: number;
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

    const CW = 6; // cell width
    const CH = 8; // cell height
    const BLADES = 7;
    const CURVE = 0.9; // log-spiral blade curvature (~70° wrap hub→tip)

    let w = 0;
    const h = height;
    let dpr = 1;
    let hovered = false;

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
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas!.width = Math.round(w * dpr);
      canvas!.height = Math.round(h * dpr);
      canvas!.style.width = `${w}px`;
      canvas!.style.height = `${h}px`;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx!.font = '8px "JetBrains Mono", ui-monospace, monospace';
      ctx!.textAlign = "center";
      ctx!.textBaseline = "middle";
    }
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(wrap);

    const onEnter = () => {
      hovered = true;
    };
    const onLeave = () => {
      hovered = false;
    };
    wrap.addEventListener("pointerenter", onEnter);
    wrap.addEventListener("pointerleave", onLeave);

    let visible = true;
    const io = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
      },
      { threshold: 0 },
    );
    io.observe(wrap);

    let spin = 0; // accumulated rotor angle
    let omega = 0.7; // current angular velocity (rad/s, visual)
    let lastT = 0;

    function frame(tMs: number) {
      const t = tMs / 1000;
      const dt = Math.min(t - lastT || 0.033, 0.1);
      lastT = t;

      // Idle slowly; spool up under the pointer.
      const target = hovered ? 2.6 : 0.4;
      omega += (target - omega) * 0.04;
      spin += omega * dt;

      ctx!.clearRect(0, 0, w, h);

      const cx = w / 2;
      const cy = h / 2;
      const rTip = Math.min(w, h) / 2 - 10;
      const rHub = Math.max(16, rTip * 0.22);
      const cols = Math.ceil(w / CW);
      const rows = Math.ceil(h / CH);

      for (let j = 0; j < rows; j++) {
        const y = j * CH + CH / 2;
        for (let i = 0; i < cols; i++) {
          const x = i * CW + CW / 2;
          const dx = x - cx;
          const dy = y - cy;
          const r = Math.hypot(dx, dy);

          if (r > rTip + 6) continue;

          // Shroud ring — a solid circular casing.
          if (Math.abs(r - rTip) < 4.5) {
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

          // Log-spiral blade field, rotating at omega.
          const theta = Math.atan2(dy, dx);
          const phase =
            BLADES * (theta - spin + CURVE * Math.log(r / rHub));
          const b = Math.cos(phase);

          // Flow passage between blades stays empty — contrast is clarity.
          if (b < 0.2) continue;

          // Shade by position within the blade so each arm renders as a
          // solid ribbon: bright leading edge, solid core, soft trail.
          const p = (b - 0.2) / 0.8;
          const glyph = p > 0.72 ? "@" : p > 0.4 ? "#" : p > 0.18 ? "=" : ":";
          const level = Math.min(LEVELS, 7 + Math.round(p * 7));
          ctx!.fillStyle = lutHot[level];
          ctx!.fillText(glyph, x, y);
        }
      }
    }

    let raf = 0;
    let last = 0;
    function loop(tMs: number) {
      raf = requestAnimationFrame(loop);
      if (!visible) return;
      if (tMs - last < 33) return; // ~30 fps
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
      wrap.removeEventListener("pointerenter", onEnter);
      wrap.removeEventListener("pointerleave", onLeave);
    };
  }, [height]);

  return (
    <div ref={wrapRef} aria-hidden className={className}>
      <canvas ref={canvasRef} className="block w-full" style={{ height }} />
    </div>
  );
}
