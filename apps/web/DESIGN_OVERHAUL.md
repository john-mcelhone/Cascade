# Cascade — v0.4 "Workbench"

v0.3 made Cascade look like an instrument; v0.4 makes it *lay out* like one.
The reference is Blender: a deep, complicated tool that stays legible
because every pixel has a job and the chrome never competes with the work.

## Layout

- **Workspaces, not pages.** A project's stages — Overview, Cycle, Flow
  path, Analysis, Map, Rotor, Runs, Settings — are tabs in the 44 px top
  bar, like Blender's workspace tabs. A project switcher sits beside them.
  Outside a project the same slot holds Projects / Learn / Docs / Changelog.
- **No navigation sidebar.** The 224 px left rail duplicated the tabs and
  breadcrumbs; it is gone, and the width goes to editors. Learn, Docs and
  What's new live in a help menu and the ⌘K palette.
- **One-row workspace header.** `PageHeader` is a 44 px toolbar: title,
  one-line description, actions. Breadcrumbs render only for levels below a
  workspace (Flow path › Candidate). The experience dial drives the
  description: wrapped in Guided, inline + truncated in Standard, hidden in
  Expert.
- **Status bar.** 24 px: solver state and job progress on the left, live
  API connectivity and build on the right. The UTC clock and fake identity
  are gone.
- **Panels.** `components/ui/panel.tsx` gives editors a consistent header
  strip (title, meta, tools) and optional disclosure, like a properties
  editor section. `PropertyRow` renders label/value lists.

## Visual language

- **Graphite / paper.** Neutral greys with a whisper of cool replace the
  blue-black console. Color is for data, selection (cyan), live state
  (amber) and status (green/red) only.
- **Quiet type.** `.micro-label` is sentence case at 11 px; the ~60
  hand-rolled `uppercase tracking-wide` labels in workspace components were
  converted. Docs, Learn and the landing page keep their editorial styling.
- **Controls.** Recessed input fields (hairline edge, brand focus ring),
  segmented tabs, raised secondary buttons, a visible switch track.
  Corners soften to 4 px on controls and 6–8 px on panels.

## Fixes found along the way

- `border-border-default` was used across the app but never defined, so
  those borders fell back to Tailwind's light grey — the harsh white
  outlines on dark inputs. The token now exists, and bare `border` picks up
  the theme hairline.
- The rotor sketch referenced `--semantic-warning-default` (undefined), so
  unselected bearings drew black.
- `scale-in` animated `transform`, overriding dialogs' centering translate;
  it now animates the independent `scale` property.
- React Flow's controls/minimap were light-only; they are retinted per
  theme (outside `@layer`, since Tailwind purges layered rules for runtime
  class names).

---

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
- **Landing page** — the hero is fronted by an **ASCII rotor mural**: a
  large, faint radial-inflow wheel — five log-spiral blades at constant
  spatial thickness on a canvas character grid — turning very slowly
  behind the headline. No interactivity, by design; it honors
  `prefers-reduced-motion` (static frame), pauses off-screen, ~15 fps,
  theme-aware via tokens. In front: a Fraunces display headline with
  italic cyan accent and a hairline-segmented **spec readout** strip
  (`<200 ms`, `2 000+`, `100 %`, `AGPL-3.0`); audience panels with
  terminal header strips; a numbered `01/04` pipeline; dense mono footer.
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
