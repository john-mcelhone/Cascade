# Cascade — Design, UI & UX Overhaul (v0.3 "Console")

A collaboration brief, executed: a product designer and an interaction designer
sit down with Cascade and ask one question — *what should a professional
engineering instrument look like in a browser, and how does the same surface
still welcome someone who has never sized a turbine?* This overhaul is the
answer.

## The design language: instrument-grade density

The previous pass (v0.2) borrowed from consumer software — aurora washes,
glass blur, gradient buttons, big radii. Cascade's users stare at residuals,
Campbell diagrams, and candidate sweeps for hours; the new language borrows
instead from the professional-terminal lineage (trading floors, flight decks,
mission control) without falling into the monospace-everywhere cliché:

- **Dark-first.** The default theme is *Console* — a deep blue-black
  (`#0A0D12`) with three layered panel values. Light mode remains as
  *Blueprint*, a crisp cool-paper companion for daylight and print.
- **Hairlines, not shadows.** Depth comes from layered surface values and
  1 px borders. Elevation shadows are shallow and crisp; nothing blurs,
  nothing glows.
- **Machined corners.** Radii top out at 6 px; working surfaces sit at 2 px.
- **Two accents with strict jobs.** Cyan is the *working* accent —
  interactive, selected, primary. Amber is the *live* accent — running jobs,
  the solver LED, attention. Green/red stay strictly semantic
  (converged/failed), so a glance at any screen reads truthfully.
- **Type with a division of labor.** Inter carries prose and controls; mono
  is reserved for data — values, IDs, timestamps, keyboard hints. The
  signature element is the **micro-label**: 10 px uppercase letterspaced
  caps on every panel header, section eyebrow, and status segment.

## The chrome, redesigned

- **Top bar (40 px)** — a command bar: the mark, a console-style locator
  path (`CASCADE / PROJECTS / MICROTURBINE 30 KW`), a real ⌘K command field,
  the experience dial, theme, account.
- **Left rail (224 px)** — grouped under `WORKSPACE` and `MODULES`
  micro-labels; each project module carries a two-digit mono index (`01`–`07`)
  and a full-height cyan rail when active.
- **Bottom bar (28 px)** — a true status ticker, segmented by hairlines:
  solver LED (grey idle / pulsing amber running) with iteration, residual,
  and progress in mono; build, live UTC clock, and identity on the right.
- **Command palette** — a terminal prompt: `›` caret, mono input, selection
  rail matching the left-rail active state, kbd-hint footer.
- **Page headers** — dense instrument strips: locator breadcrumb, title,
  one-line description, actions.

## Surfaces redesigned

- **Logo** — the three stepping blades now sit in a machined square frame,
  flat brand cyan, paired with an uppercase letterspaced wordmark.
- **Landing page** — the hero is a live **ASCII wind tunnel**: real 2-D
  potential flow (uniform stream + doublet + vortex) rendered as a canvas
  character grid. The cursor is a body in the flow — streamlines bend
  around it, cells go brand-cyan where the flow accelerates at its
  shoulders, and holding the pointer spins up circulation that turns the
  wake instrument-amber. Honors `prefers-reduced-motion` (single static
  frame), pauses off-screen, ~30 fps capped, theme-aware via tokens.
  Beside it: a Fraunces display headline with italic cyan accent, a
  boot-screen **solver console** topped by a live **spinning ASCII
  radial-inflow rotor** (seven log-spiral blades on a canvas character
  grid; hover to spool it up) over a short session log with a blinking
  cursor, and a hairline-segmented **spec readout** strip (`<200 ms`, `2 000+`, `100 %`, `AGPL-3.0`); audience
  panels with terminal header strips; a numbered `01/04` pipeline; dense
  mono footer.
- **Projects** — cards became instrument panels: a header strip with the
  mono project ID and an uppercase status chip, then name, description, and
  a cyan mono metric readout with sparkline.
- **Project home / New project** — module tiles with mono indices; flat
  selection states (cyan fill + check) instead of gradient lifts.
- **Primitives** — buttons are flat illuminated keys (solid cyan primary,
  inverse text); badges are square uppercase status chips; active tabs get a
  2 px brand underline; dialogs sharpen to 3 px radii over a plain scrim.
- **Charts** — the 12-color categorical palette now has a dark-tuned
  variant, brightened for the console background.

## What was deliberately kept

The UX systems from earlier passes survive unchanged — this was a reskin of
the product's expression, not its behavior:

- The **Experience dial** (Guided / Standard / Expert) and everything it
  drives: welcome banner, coach marks (now styled as advisory panels with a
  2 px cyan rail), `useCoaching()`.
- The yellow **input-cell convention** (`surface-input`), retuned for dark.
- The WCAG-tuned semantic structure of the token system: every variable name
  in `globals.css` is preserved, so all module surfaces (cycle, flow path,
  map, rotor) inherit the new language without per-file rework.
- All routing, stores, solver hooks, and keyboard behavior.

`tokens.json` holds the v0.1 semantic baseline; `globals.css` is canonical
for the v0.3 visual language.

## Self-assessment

Reviewed across both themes and all three experience levels, with a green
production build (25/25 routes) and screenshot passes over landing, projects,
project home, map, and rotor:

| Dimension | Notes |
| --- | --- |
| Visual identity | Distinctive, professional, era-appropriate without pastiche; no glass, no gradients, no full-mono cosplay. |
| Density | Chrome shrank (44→40 / 32→28 / 240→224 px) while gaining information: ticker segments, UTC clock, module indices. |
| Beginner path | Guided mode, welcome banner, and coach marks intact and restyled to match. |
| Honest gaps | The deep solver canvases inherit the language via tokens rather than bespoke layouts; a screenshot-regression loop is still manual. |
