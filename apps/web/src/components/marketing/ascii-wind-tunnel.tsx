"use client";

import { useEffect, useRef } from "react";

/**
 * AsciiWindTunnel — an interactive ASCII flow-field for the landing hero.
 *
 * The math is real: 2-D incompressible potential flow — uniform stream +
 * doublet (a solid cylinder) + vortex (circulation, while the pointer is
 * held). The cursor is the cylinder: streamlines bend around it, the flow
 * accelerates at its shoulders (those cells go brand-cyan), and holding
 * the pointer spins up circulation so the field swirls. With no pointer,
 * the body drifts on a slow Lissajous path so the page is alive on load.
 *
 * Rendering is a character grid on <canvas> (the DOM can't animate ~3 000
 * glyphs): glyph from local flow angle, brightness from streamfunction
 * bands (streamlines) × a phase moving along the velocity potential
 * (dashes that travel with the flow). Honors prefers-reduced-motion by
 * drawing a single static frame. Pure decoration: aria-hidden,
 * pointer-events none, listeners on window.
 */
export function AsciiWindTunnel({ className }: { className?: string }) {
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

    // ── Grid + physics constants ──────────────────────────────────────
    const CW = 14; // cell width  (px)
    const CH = 18; // cell height (px)
    const U = 1; // free-stream speed (normalized)
    const R = 88; // cylinder radius (px)
    const K_PSI = (2 * Math.PI) / 30; // streamline band spacing
    const K_PHI = (2 * Math.PI) / 36; // dash wavelength along flow
    const OMEGA = (2 * Math.PI) / 1.8; // dash speed (rad/s)
    const GAMMA_MAX = 2.4 * U * R; // held-pointer circulation

    let w = 0;
    let h = 0;
    let cols = 0;
    let rows = 0;
    let dpr = 1;

    // Pointer / autonomous body state
    let px: number | null = null;
    let py: number | null = null;
    let held = false;
    let cx = 0;
    let cy = 0;
    let gamma = 0;

    // ── Theme-aware color LUTs (quantized alpha → fillStyle strings) ──
    const LEVELS = 14;
    let lutDim: string[] = [];
    let lutMid: string[] = [];
    let lutHot: string[] = [];
    let lutSpin: string[] = [];

    function readTheme() {
      const cs = getComputedStyle(document.documentElement);
      const dim = cs.getPropertyValue("--border-strong").trim() || "96 112 136";
      const mid = cs.getPropertyValue("--text-muted").trim() || "148 158 174";
      const hot = cs.getPropertyValue("--brand-default").trim() || "78 199 216";
      const spin =
        cs.getPropertyValue("--accent-default").trim() || "245 166 35";
      const build = (t: string) =>
        Array.from({ length: LEVELS + 1 }, (_, i) =>
          `rgb(${t} / ${(i / LEVELS).toFixed(3)})`,
        );
      lutDim = build(dim);
      lutMid = build(mid);
      lutHot = build(hot);
      lutSpin = build(spin);
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
      h = rect.height;
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      canvas!.width = Math.round(w * dpr);
      canvas!.height = Math.round(h * dpr);
      canvas!.style.width = `${w}px`;
      canvas!.style.height = `${h}px`;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      // Canvas font strings can't resolve var(); name the face directly.
      ctx!.font = '11px "JetBrains Mono", ui-monospace, monospace';
      ctx!.textAlign = "center";
      ctx!.textBaseline = "middle";
      cols = Math.ceil(w / CW);
      rows = Math.ceil(h / CH);
      if (cx === 0 && cy === 0) {
        cx = w * 0.62;
        cy = h * 0.5;
      }
    }
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(wrap);

    function onMove(e: PointerEvent) {
      const rect = wrap!.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const inside = x >= 0 && x <= rect.width && y >= 0 && y <= rect.height;
      px = inside ? x : null;
      py = inside ? y : null;
      if (!inside) held = false;
    }
    function onDown(e: PointerEvent) {
      onMove(e);
      if (px !== null) held = true;
    }
    function onUp() {
      held = false;
    }
    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("pointerdown", onDown, { passive: true });
    window.addEventListener("pointerup", onUp, { passive: true });

    // Pause when the hero is off-screen.
    let visible = true;
    const io = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
      },
      { threshold: 0 },
    );
    io.observe(wrap);

    // ── Frame ─────────────────────────────────────────────────────────
    function frame(tMs: number) {
      const t = tMs / 1000;

      // Body target: pointer if present, else a slow Lissajous drift.
      const tx = px ?? w * (0.6 + 0.18 * Math.sin(t * 0.13));
      const ty = py ?? h * (0.5 + 0.26 * Math.sin(t * 0.077 + 1.7));
      cx += (tx - cx) * 0.07;
      cy += (ty - cy) * 0.07;
      gamma += ((held ? GAMMA_MAX : 0) - gamma) * 0.05;

      ctx!.clearRect(0, 0, w, h);

      const R2 = R * R;
      const gOver2pi = gamma / (2 * Math.PI);

      for (let j = 0; j < rows; j++) {
        const y = j * CH + CH / 2;
        for (let i = 0; i < cols; i++) {
          const x = i * CW + CW / 2;
          const dx = x - cx;
          const dy = y - cy;
          const r2 = dx * dx + dy * dy;

          if (r2 < R2 * 0.92) {
            // Inside the body — a faint solid.
            ctx!.fillStyle = lutDim[2];
            ctx!.fillText("·", x, y);
            continue;
          }

          // Potential flow: uniform + doublet + vortex.
          const f = R2 / r2;
          let u = U * (1 - (f * (dx * dx - dy * dy)) / r2);
          let v = U * ((-f * 2 * dx * dy) / r2);
          u += (gOver2pi * dy) / r2;
          v += (-gOver2pi * dx) / r2;

          // Streamfunction (bands = streamlines) + gentle far-field waviness.
          const psi =
            U * dy * (1 - f) +
            gOver2pi * 0.5 * Math.log(r2) +
            6 * Math.sin(x * 0.008 + t * 0.6);
          // Velocity potential (phase travels along the flow).
          const phi = U * dx * (1 + f);

          const band = 0.5 + 0.5 * Math.cos(psi * K_PSI);
          const bandSharp = band * band;
          if (bandSharp < 0.05) {
            // Air between streamlines — a faint dot-matrix fabric.
            if (((i + j) & 1) === 0) {
              ctx!.fillStyle = lutDim[1];
              ctx!.fillText("·", x, y);
            }
            continue;
          }

          const dash = 0.5 + 0.5 * Math.cos(phi * K_PHI - OMEGA * t);
          const s = Math.hypot(u, v) / U;

          // Proximity glow — the flow brightens around the body, so the
          // pointer feels like a light source in the tunnel.
          const prox = Math.exp(-Math.max(0, Math.sqrt(r2) - R) / 150);

          let alpha =
            (0.16 +
              0.84 *
                bandSharp *
                (0.4 + 0.6 * dash) *
                (0.5 + 0.5 * Math.min(s, 1.5))) *
            (1 + 0.7 * prox);
          if (alpha > 0.95) alpha = 0.95;
          const level = Math.round(alpha * LEVELS);
          if (level <= 0) continue;

          // Glyph from flow angle; speed picks the color tier.
          const ang = Math.atan2(v, u);
          const a8 = Math.abs(ang);
          const glyph =
            a8 < 0.39 || a8 > Math.PI - 0.39
              ? "-"
              : a8 > 1.18 && a8 < 1.96
                ? "|"
                : ang > 0 === a8 < Math.PI / 2
                  ? "\\"
                  : "/";

          // Where circulation dominates the local velocity, the wake goes
          // instrument-amber — holding the pointer visibly "spins up".
          const vt = Math.abs(gOver2pi) / Math.sqrt(r2);
          ctx!.fillStyle =
            vt / (vt + U) > 0.42
              ? lutSpin[level]
              : s > 1.05
                ? lutHot[level]
                : s > 0.5
                  ? lutMid[level]
                  : lutDim[level];
          ctx!.fillText(glyph, x, y);
        }
      }
    }

    let raf = 0;
    let last = 0;
    function loop(tMs: number) {
      raf = requestAnimationFrame(loop);
      if (!visible) return;
      // ~30 fps is plenty for character art and kind to laptops.
      if (tMs - last < 33) return;
      last = tMs;
      frame(tMs);
    }

    if (reduceMotion) {
      frame(0); // single static frame
    } else {
      raf = requestAnimationFrame(loop);
    }

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      themeWatch.disconnect();
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("pointerup", onUp);
    };
  }, []);

  return (
    <div
      ref={wrapRef}
      aria-hidden
      className={className}
      style={{ pointerEvents: "none" }}
    >
      <canvas ref={canvasRef} className="block h-full w-full" />
    </div>
  );
}
