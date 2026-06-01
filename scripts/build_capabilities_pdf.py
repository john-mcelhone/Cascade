#!/usr/bin/env python3
"""Render the Cascade capabilities report to a designed PDF via WeasyPrint."""
from __future__ import annotations

from pathlib import Path

from weasyprint import HTML

OUT = Path(__file__).resolve().parent.parent / "CAPABILITIES_REPORT.pdf"

HTML_DOC = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  @page {
    size: A4;
    margin: 13mm 13mm 9mm 13mm;
    @bottom-left {
      content: "Cascade v0.1.0 — Software Capabilities Report";
      font-family: 'Helvetica Neue', Arial, sans-serif;
      font-size: 7.5pt; color: #8a94a6;
    }
    @bottom-right {
      content: "Page " counter(page) " of " counter(pages);
      font-family: 'Helvetica Neue', Arial, sans-serif;
      font-size: 7.5pt; color: #8a94a6;
    }
  }
  * { box-sizing: border-box; }
  body {
    font-family: 'Helvetica Neue', 'Segoe UI', Arial, sans-serif;
    color: #1f2733; font-size: 8.4pt; line-height: 1.42; margin: 0;
  }
  /* ---- Masthead ---- */
  .masthead {
    display: flex; align-items: center; justify-content: space-between;
    background: linear-gradient(110deg, #0b3d63 0%, #11628f 55%, #1893b8 100%);
    color: #fff; border-radius: 9px; padding: 11px 18px; margin-bottom: 10px;
  }
  .brand { display: flex; align-items: center; gap: 13px; }
  .glyph {
    width: 40px; height: 40px; border-radius: 9px; flex: none;
    background: rgba(255,255,255,0.14);
    display: flex; align-items: center; justify-content: center;
  }
  .glyph svg { display: block; }
  .brand h1 { font-size: 19pt; margin: 0; letter-spacing: 0.3px; font-weight: 700; }
  .brand .tag { font-size: 8.2pt; opacity: 0.9; margin-top: 2px; font-weight: 400; }
  .meta { text-align: right; font-size: 7.4pt; line-height: 1.6; opacity: 0.95; }
  .meta b { font-weight: 600; }
  .pill {
    display: inline-block; background: rgba(255,255,255,0.18);
    border-radius: 20px; padding: 1px 8px; font-size: 7pt; margin-top: 3px;
  }
  /* ---- Layout ---- */
  .lead {
    font-size: 8.6pt; color: #2c3848; margin: 0 0 8px 0;
    padding-left: 9px; border-left: 3px solid #1893b8;
  }
  .cols { column-count: 2; column-gap: 13px; }
  h2 {
    font-size: 8.8pt; text-transform: uppercase; letter-spacing: 0.6px;
    color: #0b3d63; margin: 0 0 5px 0; padding-bottom: 3px;
    border-bottom: 1.5px solid #d7e1ea; break-after: avoid;
  }
  h2 .ic { color: #1893b8; margin-right: 5px; font-weight: 700; }
  section { break-inside: avoid; margin-bottom: 9px; }
  table { width: 100%; border-collapse: collapse; font-size: 7.7pt; }
  td { padding: 2.6px 5px; vertical-align: top; border-bottom: 0.5px solid #e7edf2; }
  tr td:first-child { font-weight: 600; color: #0b3d63; white-space: nowrap; width: 30%; }
  .full td:first-child { white-space: normal; width: 28%; }
  ul { margin: 0; padding-left: 14px; }
  li { margin-bottom: 2.5px; }
  code {
    font-family: 'SF Mono', 'Consolas', monospace; font-size: 7pt;
    background: #eef3f7; color: #0b3d63; padding: 0 3px; border-radius: 3px;
  }
  .ok { color: #1a7f4b; font-weight: 700; }
  /* ---- Stat band ---- */
  .stats { display: flex; gap: 8px; margin: 0 0 9px 0; }
  .stat {
    flex: 1; background: #f4f8fb; border: 1px solid #e0e9f0;
    border-radius: 7px; padding: 7px 9px; text-align: center;
  }
  .stat .n { font-size: 13pt; font-weight: 700; color: #11628f; line-height: 1; }
  .stat .l { font-size: 6.6pt; text-transform: uppercase; letter-spacing: 0.4px;
             color: #69788a; margin-top: 3px; }
  /* ---- Scope box ---- */
  .scope { background: #fcf8f0; border: 1px solid #ecd9b0; border-radius: 7px;
           padding: 8px 11px; break-inside: avoid; }
  .scope h2 { border-color: #ecd9b0; color: #8a5a06; }
  .scope h2 .ic { color: #c9881a; }
  .scope b { color: #8a5a06; }
  .badge { display:inline-block; font-size:6.6pt; font-weight:700; padding:0 5px;
           border-radius:3px; margin-right:3px; vertical-align: middle; }
  .b-no { background:#fae3e0; color:#a3372a; }
  .b-next { background:#e6eef6; color:#1c5c8c; }
  .b-perm { background:#ece7f2; color:#5a4a85; }
  /* ---- Workflow strip ---- */
  .flow { display: flex; align-items: stretch; gap: 0; margin-top: 4px; }
  .step { flex: 1; background: #f4f8fb; border: 1px solid #e0e9f0;
          padding: 5px 6px; font-size: 6.9pt; position: relative; }
  .step:not(:last-child) { margin-right: 9px; }
  .step:not(:last-child):after {
    content: "›"; position: absolute; right: -7px; top: 50%;
    transform: translateY(-50%); color: #1893b8; font-weight: 700; font-size: 10pt;
  }
  .step b { display: block; color: #0b3d63; font-size: 7pt; margin-bottom: 1px; }
  .step .t { color: #1a7f4b; font-weight: 600; }
  footer { margin-top: 7px; font-size: 6.7pt; color: #9aa6b4;
           border-top: 0.5px solid #e0e7ee; padding-top: 4px; }
</style>
</head>
<body>

  <div class="masthead">
    <div class="brand">
      <div class="glyph">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
          <path d="M3 7c3.5 0 3.5 4 7 4s3.5-4 7-4 3.5 4 4 4" stroke="#fff" stroke-width="1.7" stroke-linecap="round"/>
          <path d="M3 12c3.5 0 3.5 4 7 4s3.5-4 7-4 3.5 4 4 4" stroke="#bfe6f2" stroke-width="1.7" stroke-linecap="round"/>
          <path d="M3 17c3.5 0 3.5 4 7 4" stroke="#7fcbe3" stroke-width="1.7" stroke-linecap="round"/>
        </svg>
      </div>
      <div>
        <h1>Cascade</h1>
        <div class="tag">The web-native turbomachinery design environment</div>
      </div>
    </div>
    <div class="meta">
      <div>Software Capabilities Report</div>
      <div><b>Version</b> 0.1.0 · pre-release</div>
      <div><b>Date</b> 2026-06-01</div>
      <div class="pill">AGPL-3.0 core · MIT SDK</div>
    </div>
  </div>

  <p class="lead">
    Cascade is a browser-based turbomachinery design environment for small engineering teams. It carries a design
    from thermodynamic cycle, through preliminary mean-line aero of the rotating machine, into geometry and rotor
    dynamics — with no install. Its philosophy is <b>transparency</b> (every loss model carries a published citation),
    <b>reproducibility</b> (units-aware, git-diffable TOML projects), and <b>validation</b> (a public suite against
    canonical published cases instead of marketing accuracy claims).
  </p>

  <div class="stats">
    <div class="stat"><div class="n">1,115</div><div class="l">Tests passing</div></div>
    <div class="stat"><div class="n">130</div><div class="l">Validation pass-gates</div></div>
    <div class="stat"><div class="n">&lt;200 ms</div><div class="l">Cycle solve</div></div>
    <div class="stat"><div class="n">~30 s</div><div class="l">2,000 candidates</div></div>
    <div class="stat"><div class="n">Py 3.12</div><div class="l">Numerical core</div></div>
  </div>

  <div class="cols">

    <section>
      <h2><span class="ic">▍</span>Core Capabilities (v1)</h2>
      <table class="full">
        <tr><td>0D cycle</td><td>Brayton variants — simple, recuperated, reheat, intercooled. Real-gas EOS (NASA polynomials + CoolProp; REFPROP optional). Solves &eta;<sub>thermal</sub> in &lt;200&nbsp;ms.</td></tr>
        <tr><td>Mean-line design</td><td>Radial inflow turbine &amp; centrifugal compressor with citable loss models (Whitfield&ndash;Baines, Aungier, Wiesner slip).</td></tr>
        <tr><td>Exploration</td><td>Sobol&rsquo; sampling of 100s&ndash;1000s of candidate geometries; interactive filter-and-pick with live 3D preview.</td></tr>
        <tr><td>Performance maps</td><td>Full-factorial grids with explicit per-point convergence codes (surge / choke / non-converged).</td></tr>
        <tr><td>Rotor dynamics</td><td>Timoshenko beam-FEM with gyroscopics: critical-speed map, unbalance response (Bode + amplification + separation margin), Campbell, stability.</td></tr>
        <tr><td>Bearings</td><td>Plain-journal solver (Reynolds + Christopherson PSOR); tabulated K&ndash;C input for any bearing type.</td></tr>
        <tr><td>Geometry</td><td>Parametric impeller / turbine / volute / rotor; optional STEP &amp; IGES export (OpenCASCADE).</td></tr>
        <tr><td>Optimization</td><td>SLSQP, NSGA-II, CMA-ES, Powell (BOBYQA API) — single &amp; multi-objective.</td></tr>
        <tr><td>Materials &amp; mfg.</td><td>Materials database/registry; rule-based manufacturability checks and reports.</td></tr>
        <tr><td>Interfaces</td><td>Python SDK + <code>cascade</code> CLI at parity with the web UI; sandboxed plugin / adapter system.</td></tr>
      </table>
    </section>

    <section>
      <h2><span class="ic">▍</span>Architecture &amp; Stack</h2>
      <table>
        <tr><td>Core</td><td>Python 3.12 · numpy · scipy · Pint (units) · Pydantic · CoolProp</td></tr>
        <tr><td>API</td><td>FastAPI + Uvicorn · SQLAlchemy 2 (async) + Alembic · Celery + Redis · ReportLab · auto OpenAPI</td></tr>
        <tr><td>Frontend</td><td>Next.js 15 / React 19 App Router · Plotly · react-three-fiber (WebGL 3D)</td></tr>
        <tr><td>Data</td><td>PostgreSQL 16 + pgvector</td></tr>
        <tr><td>Project format</td><td>.cascade directory of units-aware TOML; async collab via git branch + diff + PR</td></tr>
        <tr><td>Deploy</td><td>Fly.io</td></tr>
        <tr><td>Quality</td><td>pytest + hypothesis · ruff · mypy (strict)</td></tr>
      </table>
    </section>

    <section>
      <h2><span class="ic">▍</span>Validation Status</h2>
      <ul>
        <li><b>CYC-1</b> simple Brayton: &eta;<sub>th</sub> 44.80% vs textbook 44.79% (&plusmn;0.01&nbsp;pt) <span class="ok">&#10003;</span></li>
        <li><b>CYC-2</b> recuperated Brayton: &eta;<sub>th</sub> 54.91% <span class="ok">&#10003;</span></li>
        <li><b>CYC-3</b> Capstone C30: &eta;<sub>e</sub> 26.09% vs 26% <span class="ok">&#10003;</span></li>
        <li><b>CC-1</b> Eckardt Rotor A (calibrated): &pi;<sub>tt</sub> within &plusmn;0.10 <span class="ok">&#10003;</span></li>
        <li><b>RIT-1</b> NASA TN D-7508: &eta;<sub>ts</sub> 0.817 vs ~0.84 (&plusmn;5&nbsp;pt) <span class="ok">&#10003;</span></li>
        <li>All implemented pass-gates pass within published tolerances; subset runs in &asymp;14&nbsp;s.</li>
      </ul>
    </section>

    <section class="scope">
      <h2><span class="ic">▍</span>Honest Scope Boundaries</h2>
      <p style="margin:0 0 5px 0;"><span class="badge b-no">NOT IN v1</span> 1D thermal-fluid network solver (<code>cascade.network</code>) and the <b>axial turbine / compressor mean-line solver</b> are specified but not yet built. Several validation cases (CYC-4/5/6/7, RIT-3/4, CC-3/4/5, AXT, TFN) are characterization-only or untested.</p>
      <p style="margin:0 0 5px 0;"><span class="badge b-next">v1.1</span> Real-time co-edit (Yjs/Hocuspocus), multi-stage radial, multi-spool / cooled-turbine matching, tilt-pad / thrust / foil bearings, 2D streamline-curvature throughflow, Bayesian optimization, visual node-graph editor.</p>
      <p style="margin:0;"><span class="badge b-perm">ADAPTER-ONLY</span> RANS CFD (OpenFOAM stub) and full 3D FEA (CalculiX adapter; v1 ships 2D-axisymmetric disc stress).</p>
    </section>

  </div>

  <section style="break-inside:avoid;">
    <h2><span class="ic">▍</span>Hero Workflow</h2>
    <div class="flow">
      <div class="step"><b>Cycle</b>Recuperated Brayton microturbine <span class="t">&lt;200 ms</span></div>
      <div class="step"><b>Design</b>Radial turbine, cycle exit as BC</div>
      <div class="step"><b>Explore</b>2,000 Sobol candidates <span class="t">~30 s</span></div>
      <div class="step"><b>Map</b>Surge / choke lines <span class="t">~60 s</span></div>
      <div class="step"><b>Rotor dyn.</b>Bode + crit-speed + margin <span class="t">~5 s</span></div>
    </div>
  </section>

  <footer>
    Sources: README.md, SPEC_SHEET.md, VALIDATION_REPORT.md, KNOWN_GAPS.md, pyproject.toml &amp; source inspection &mdash; capabilities reflect actual v1 implementation status, not headline spec claims.
  </footer>

</body>
</html>
"""

HTML(string=HTML_DOC).write_pdf(OUT)
print(f"wrote {OUT}")
