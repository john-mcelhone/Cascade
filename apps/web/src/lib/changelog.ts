/**
 * Product changelog — newest first.
 *
 * Every shipped update gets an entry here; the /changelog page renders
 * this list as a timeline. Append new entries at the TOP. Dates are
 * ISO `yyyy-mm-dd` and rendered in UTC so the display never drifts
 * with the viewer's timezone.
 */

export type ChangeCategory =
  | "release"
  | "feature"
  | "fix"
  | "design"
  | "docs";

export interface ChangelogEntry {
  /** ISO date (yyyy-mm-dd) the change landed. */
  date: string;
  title: string;
  category: ChangeCategory;
  /** One-paragraph summary shown under the title. */
  summary: string;
  /** Optional itemized details, rendered as a compact list. */
  details?: string[];
  /** GitHub pull-request number, linked when present. */
  pr?: number;
}

export const CATEGORY_LABEL: Record<ChangeCategory, string> = {
  release: "Release",
  feature: "Feature",
  fix: "Fix",
  design: "Design",
  docs: "Docs",
};

export const CHANGELOG: ChangelogEntry[] = [
  {
    date: "2026-06-10",
    title: "Manufacturable impeller geometry",
    category: "fix",
    pr: 6,
    summary:
      "The 3D mesh generator now produces wheels that match industry practice and what a 5-axis cell can actually cut. Blade camber, flow-path contours, splitter accounting, and exports were all overhauled.",
    details: [
      "Blade camber integrates per spanwise streamline with the leading-edge metal angle twisted hub-to-shroud (tan β₁ ∝ r). Hub wrap drops from ~185° to ~83° on the reference wheel.",
      "Hub and shroud contours are tangency-correct quarter-ellipses — axial at the inducer, radial at the exit — replacing the rippled interpolating splines.",
      "Blade count is honored as the total budget: with splitters on, Z/2 full blades + Z/2 splitters at half pitch, matching the mean-line correlations.",
      "The cosmetic shroud cup no longer renders by default; STL and STEP exports are watertight.",
      "TurboGrid .curve, NDF, and fluid-volume exports share the generator's curves and metal angles, so what you export is what you see.",
    ],
  },
  {
    date: "2026-06-10",
    title: "3D viewer reliability fixes",
    category: "fix",
    summary:
      "Candidate GLB and STL endpoints were rebuilt around the normative geometry merge, so the mesh you preview is the exact machine behind a candidate's mean-line numbers.",
    details: [
      "Explore and manufacturability routers aligned with the candidate geometry merge.",
      "Regression coverage added for candidate-geometry wiring and explore manufacturability.",
    ],
  },
  {
    date: "2026-06-09",
    title: "README rebuilt around verified claims",
    category: "docs",
    pr: 5,
    summary:
      "Documentation overhaul: the README is rebuilt around live screenshots and claims verified against the shipped code. Stale research notes and the competitive-landscape material were removed.",
  },
  {
    date: "2026-06-09",
    title: "Small gas turbine release",
    category: "feature",
    pr: 4,
    summary:
      "The end-to-end small-gas-turbine workflow: design a flow path, hand the picked candidate to the cycle, and burn fuel the way the test cell does.",
    details: [
      "Burner fuel-mass-flow mode wired end to end — specify fuel flow or turbine inlet temperature.",
      "Candidate detail pages and the flow-path → cycle geometry handoff.",
      "Live mean-line attribution on the cycle page; invalid geometry is refused with structured errors instead of silently substituted.",
      "Refused jobs end as failed with the failure envelope intact.",
      "Web unit tests, typecheck, and the production build added to the CI gate.",
    ],
  },
  {
    date: "2026-06-01",
    title: "Design, UI & UX overhaul",
    category: "design",
    pr: 2,
    summary:
      "A new visual system across the whole app — refreshed shell and navigation, theme tokens, and adaptive experience levels that scale the interface from first-time learner to practicing engineer.",
  },
  {
    date: "2026-06-01",
    title: "Independent physics verification suite",
    category: "fix",
    pr: 1,
    summary:
      "A standalone verification suite now cross-checks the solvers against physics that cannot be argued with, and it caught real bugs on arrival.",
    details: [
      "Radial-turbine polytropic efficiency corrected.",
      "Unsafe slip-factor extrapolation guarded.",
      "Real-combustion conservation checks added to cycle verification.",
    ],
  },
  {
    date: "2026-05-27",
    title: "Cascade v0.1.0",
    category: "release",
    summary:
      "Initial release of the web-native turbomachinery design environment: mean-line solvers for centrifugal compressors and radial-inflow turbines, a Brayton cycle solver, Sobol design-space exploration, rotor dynamics, manufacturability rules, 3D geometry with GLB/STL/STEP exports, and this web app.",
  },
];
