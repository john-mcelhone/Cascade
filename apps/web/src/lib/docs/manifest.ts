/**
 * Canonical manifest for the /docs section. The sidebar, the docs landing
 * page, and every page's prev/next footer derive from this single list so
 * ordering and titles never drift between surfaces.
 */

export interface DocPageMeta {
  /** URL path under /docs ("" is the landing page). */
  slug: string;
  /** Sidebar + header title. */
  title: string;
  /** One-line description for the landing page and prev/next cards. */
  description: string;
}

export interface DocGroup {
  /** Sidebar group heading. */
  label: string;
  pages: DocPageMeta[];
}

export const DOC_GROUPS: DocGroup[] = [
  {
    label: "Get started",
    pages: [
      {
        slug: "",
        title: "Overview",
        description:
          "What Cascade is, what ships today, and where everything lives.",
      },
      {
        slug: "installation",
        title: "Installation",
        description:
          "Requirements, make setup, optional extras, and how to verify the install.",
      },
      {
        slug: "quickstart",
        title: "Quickstart",
        description:
          "Run a cycle, explore a design space, and check a rotor — in about ten minutes.",
      },
      {
        slug: "projects",
        title: "Projects & the .cascade format",
        description:
          "Plain TOML on disk: units, components, edges, and a git-friendly diff story.",
      },
    ],
  },
  {
    label: "Designing machines",
    pages: [
      {
        slug: "cycle",
        title: "Cycle design",
        description:
          "The 0D thermodynamic solver: components, boundary conditions, and result attribution.",
      },
      {
        slug: "meanline",
        title: "Mean-line design",
        description:
          "Radial turbine and centrifugal compressor preliminary design with cited loss models.",
      },
      {
        slug: "exploration",
        title: "Design exploration",
        description:
          "Sobol' sampling, the filter DSL, manufacturability gating, and send-to-cycle.",
      },
      {
        slug: "performance-maps",
        title: "Performance maps",
        description:
          "Speedlines, surge and choke lines, and an explicit status code on every point.",
      },
      {
        slug: "rotor-dynamics",
        title: "Rotor dynamics",
        description:
          "Critical speeds, Campbell, unbalance response, stability — lateral and torsional.",
      },
      {
        slug: "optimization",
        title: "Optimization",
        description:
          "SLSQP, CMA-ES, Powell, and NSGA-II multi-objective on top of any solver.",
      },
    ],
  },
  {
    label: "Reference",
    pages: [
      {
        slug: "python-api",
        title: "Python scripting",
        description:
          "The cascade package is the scripting interface — solve, sweep, and export from code.",
      },
      {
        slug: "cli",
        title: "CLI reference",
        description:
          "cascade demo, validate, sweep, export, and plugin management.",
      },
      {
        slug: "rest-api",
        title: "REST API & jobs",
        description:
          "Every endpoint, the job lifecycle, and live progress over Server-Sent Events.",
      },
      {
        slug: "units",
        title: "Units & quantities",
        description:
          "pint-backed quantities end to end; mismatches are refused, never coerced.",
      },
      {
        slug: "errors",
        title: "Failures & status codes",
        description:
          "The failure envelope, refusal rules, and all eight map point status codes.",
      },
      {
        slug: "export",
        title: "Geometry export",
        description:
          "GLB and STL in the base install; STEP, IGES, and TurboGrid NDF with cascade[cad].",
      },
      {
        slug: "plugins",
        title: "Plugins",
        description:
          "Ship your own loss model — with a citation — and select it per project.",
      },
      {
        slug: "materials",
        title: "Materials database",
        description:
          "Temperature-dependent alloy properties with sources, served over the API.",
      },
    ],
  },
  {
    label: "Trust",
    pages: [
      {
        slug: "validation",
        title: "Validation report",
        description:
          "Pass-gates against published cases — including the fine print.",
      },
      {
        slug: "known-gaps",
        title: "Known gaps",
        description:
          "Every gap has a stable KG-ID. Nothing unshipped is described in the present tense.",
      },
      {
        slug: "contributing",
        title: "Contributing",
        description:
          "The highest-leverage work is validation. Run make ci before opening a PR.",
      },
    ],
  },
];

/** Flat ordered list of every docs page. */
export const DOC_PAGES: DocPageMeta[] = DOC_GROUPS.flatMap((g) => g.pages);

export function getDocPage(slug: string): DocPageMeta | null {
  return DOC_PAGES.find((p) => p.slug === slug) ?? null;
}

/** Previous/next page for footer navigation. */
export function getDocNeighbors(slug: string): {
  prev: DocPageMeta | null;
  next: DocPageMeta | null;
} {
  const idx = DOC_PAGES.findIndex((p) => p.slug === slug);
  if (idx === -1) return { prev: null, next: null };
  return {
    prev: idx > 0 ? DOC_PAGES[idx - 1] : null,
    next: idx < DOC_PAGES.length - 1 ? DOC_PAGES[idx + 1] : null,
  };
}

export function docHref(slug: string): string {
  return slug === "" ? "/docs" : `/docs/${slug}`;
}
