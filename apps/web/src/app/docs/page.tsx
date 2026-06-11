import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  Boxes,
  CircleGauge,
  Cog,
  Compass,
  FileCode2,
  FlaskConical,
  GitBranch,
  Layers,
  Map as MapIcon,
  Rocket,
  Ruler,
  ShieldCheck,
  SlidersHorizontal,
  Terminal,
  Wrench,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { CodeBlock } from "@/components/docs";
import { DOC_GROUPS, docHref } from "@/lib/docs/manifest";

const PAGE_ICON: Record<string, LucideIcon> = {
  "": BookOpen,
  installation: Rocket,
  quickstart: Zap,
  projects: GitBranch,
  cycle: Layers,
  meanline: Cog,
  exploration: Compass,
  "performance-maps": MapIcon,
  "rotor-dynamics": CircleGauge,
  optimization: SlidersHorizontal,
  "python-api": FileCode2,
  cli: Terminal,
  "rest-api": Boxes,
  units: Ruler,
  errors: ShieldCheck,
  export: Boxes,
  plugins: Wrench,
  materials: FlaskConical,
  validation: ShieldCheck,
  "known-gaps": ShieldCheck,
  contributing: GitBranch,
};

/**
 * Docs landing page. A short orientation, the three-command quickstart,
 * and every page from the manifest grouped the same way as the sidebar —
 * so the landing page can never drift out of sync with navigation.
 */
export default function DocsOverviewPage() {
  return (
    <div className="flex w-full justify-center px-6">
      <div className="flex w-full max-w-4xl flex-col gap-10 py-8 lg:py-12">
        <header className="flex flex-col gap-3">
          <span className="text-xs font-medium uppercase tracking-wide text-text-muted">
            Documentation
          </span>
          <h1 className="max-w-2xl font-display text-2xl font-medium leading-tight text-text">
            Everything Cascade computes, documented the way it actually runs.
          </h1>
          <p className="max-w-2xl text-lg leading-relaxed text-text-muted">
            Cycle design, mean-line machines, design exploration, performance
            maps, and rotor dynamics — in the browser, from one git-diffable
            project. These pages mirror the shipping code: every loss model is
            cited, every solver is validated in public, and every gap has a
            stable ID.
          </p>
        </header>

        <section className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-lg font-medium text-text">
              Up and running in three commands
            </h2>
            <Link
              href="/docs/quickstart"
              className="inline-flex items-center gap-1 text-sm font-medium text-brand-text hover:underline"
            >
              Full quickstart
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          <CodeBlock
            lang="bash"
            title="terminal"
            code={`make setup   # one-time: install Python deps in .venv
make run     # start API (:8000) + web (:3000) in the background
# then open http://localhost:3000/projects/microturbine-30kw/cycle`}
          />
          <p className="text-sm text-text-muted">
            The seeded <span className="font-medium text-text">Microturbine 30 kW</span>{" "}
            project is a recuperated Brayton matched to the published Capstone
            C30 spec — a real machine, not a toy.
          </p>
        </section>

        {DOC_GROUPS.map((group) => (
          <section key={group.label} className="flex flex-col gap-3">
            <h2 className="text-xs font-medium uppercase tracking-wide text-text-muted">
              {group.label}
            </h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {group.pages
                .filter((p) => p.slug !== "")
                .map((page) => {
                  const Icon = PAGE_ICON[page.slug] ?? BookOpen;
                  return (
                    <Link key={page.slug} href={docHref(page.slug)} className="group block">
                      <div className="flex h-full items-start gap-3 rounded-md border border-border-subtle bg-surface-raised p-4 transition-colors duration-fast hover:border-border-default">
                        <div className="rounded-sm border border-border-subtle bg-surface-subtle/60 p-2">
                          <Icon className="h-4 w-4 text-text-muted transition-colors duration-fast group-hover:text-brand" />
                        </div>
                        <div className="flex-1">
                          <h3 className="text-md font-medium text-text">
                            {page.title}
                          </h3>
                          <p className="mt-1 text-sm leading-relaxed text-text-muted">
                            {page.description}
                          </p>
                        </div>
                      </div>
                    </Link>
                  );
                })}
            </div>
          </section>
        ))}

        <section className="flex items-start gap-3 rounded-md border border-border-subtle bg-surface-subtle/40 p-4">
          <BookOpen className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" />
          <div className="text-sm leading-relaxed text-text-muted">
            New to turbomachinery? The{" "}
            <Link href="/learn" className="font-medium text-brand-text hover:underline">
              Learn section
            </Link>{" "}
            teaches the theory from first principles — what a turbine is, why
            velocity triangles matter, how to read a Campbell diagram — with
            interactive widgets. These docs assume you want to <em>use</em>{" "}
            Cascade; Learn explains <em>why</em> it works.
          </div>
        </section>
      </div>
    </div>
  );
}
