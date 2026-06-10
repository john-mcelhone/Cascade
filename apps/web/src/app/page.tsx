import Link from "next/link";
import {
  ArrowRight,
  GraduationCap,
  Github,
  Network,
  Wind,
  Grid3x3,
  Cog,
  GitBranch,
  ShieldCheck,
  Sigma,
} from "lucide-react";
import { Logo, CascadeMark } from "@/components/shell/logo";
import { Button } from "@/components/ui/button";

/**
 * Cascade landing page. The front door for both audiences: a curious newcomer
 * who has never sized a turbine, and a veteran who wants to be running a sweep
 * in four minutes. The hero speaks to both; the "two ways in" band routes them.
 */
export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-text">
      <header className="glass sticky top-0 z-40 flex h-topbar items-center justify-between border-b border-border-subtle px-5">
        <Logo />
        <nav className="flex items-center gap-1 text-sm text-text-muted">
          <Link
            href="/learn"
            className="hidden rounded-md px-2.5 py-1.5 transition-colors hover:bg-surface-subtle hover:text-text sm:block"
          >
            Learn
          </Link>
          <Link
            href="/docs"
            className="hidden rounded-md px-2.5 py-1.5 transition-colors hover:bg-surface-subtle hover:text-text sm:block"
          >
            Docs
          </Link>
          <Link
            href="/docs/validation"
            className="hidden rounded-md px-2.5 py-1.5 transition-colors hover:bg-surface-subtle hover:text-text md:block"
          >
            Validation
          </Link>
          <Link href="/projects" className="ml-1">
            <Button size="sm" className="h-8 gap-1.5 px-3">
              Open workspace
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </nav>
      </header>

      <main className="flex flex-1 flex-col">
        {/* ───────────────────────── Hero ───────────────────────── */}
        <section className="relative overflow-hidden border-b border-border-subtle">
          <div
            aria-hidden
            className="aurora aurora-animated pointer-events-none absolute inset-0 -z-10"
          />
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_1px_1px,rgb(var(--border-subtle)/0.5)_1px,transparent_0)] [background-size:24px_24px] [mask-image:radial-gradient(ellipse_at_top,black,transparent_75%)]"
          />

          <div className="mx-auto flex w-full max-w-5xl flex-col items-center gap-6 px-5 py-20 text-center sm:py-28">
            <span className="animate-fade-in-up inline-flex items-center gap-2 rounded-full border border-border-subtle bg-surface-raised/70 px-3 py-1 text-xs font-medium text-text-muted shadow-z1 backdrop-blur">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-brand" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-brand" />
              </span>
              Web-native turbomachinery design — no install
            </span>

            <h1
              className="animate-fade-in-up max-w-3xl text-3xl font-semibold leading-[1.05] tracking-tight sm:text-4xl"
              style={{ animationDelay: "60ms" }}
            >
              Turbomachinery design,
              <br className="hidden sm:block" />{" "}
              <span className="text-brand-gradient">in the open.</span>
            </h1>

            <p
              className="animate-fade-in-up max-w-2xl text-md leading-relaxed text-text-muted sm:text-lg"
              style={{ animationDelay: "120ms" }}
            >
              Build a cycle. Run a meanline. Sweep ten thousand candidate
              geometries against your constraints. Pick one. Ship it — every loss
              model cited, every project a folder of text files, every run
              reproducible.
            </p>

            <div
              className="animate-fade-in-up flex flex-wrap items-center justify-center gap-3 pt-2"
              style={{ animationDelay: "180ms" }}
            >
              <Link href="/projects">
                <Button size="xl" className="gap-2">
                  Open the workspace
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <Link href="/learn">
                <Button size="xl" variant="outline" className="gap-2">
                  <GraduationCap className="h-4 w-4" />
                  Start with Learn
                </Button>
              </Link>
            </div>

            <p
              className="animate-fade-in-up text-sm text-text-muted"
              style={{ animationDelay: "240ms" }}
            >
              Sign in with your work email — first radial-turbine sweep in about
              four minutes.
            </p>
          </div>
        </section>

        {/* ─────────────────── Two ways in (audiences) ─────────────────── */}
        <section className="mx-auto w-full max-w-5xl px-5 py-14">
          <div className="mb-8 text-center">
            <h2 className="text-xl font-semibold tracking-tight">
              Two ways in.
            </h2>
            <p className="mt-2 text-md text-text-muted">
              Cascade meets you where you are — and grows as you do.
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <AudienceCard
              eyebrow="New to turbines"
              title="Learn the principles, hands-on."
              body="Ten short illustrated chapters take you from your first Brayton cycle to rotor dynamics, with interactive widgets you can poke at. Switch the app to Guided mode and it coaches you through every step."
              cta="Open the Learn track"
              href="/learn"
              Icon={GraduationCap}
            />
            <AudienceCard
              eyebrow="Seasoned engineer"
              title="Skip the tour. Start sweeping."
              body="Jump straight into the workspace with a microturbine, sCO₂, or radial-turbine template pre-loaded. Switch to Expert mode for maximum density, keyboard-first, every control on screen at once."
              cta="Open the workspace"
              href="/projects"
              Icon={Wind}
              primary
            />
          </div>
        </section>

        {/* ─────────────────────── Why Cascade ─────────────────────── */}
        <section className="border-y border-border-subtle bg-surface-subtle/40">
          <div className="mx-auto w-full max-w-5xl px-5 py-14">
            <div className="grid gap-4 sm:grid-cols-3">
              <ReasonCard
                Icon={Sigma}
                title="You can see the math."
                body="Every loss correlation is a citation, an equation, a calibration scale, and the Python source. Aungier 2000, profile loss, Eq. 6.42 — with the DOI."
              />
              <ReasonCard
                Icon={GitBranch}
                title="Your project lives in git."
                body="A Cascade project is a folder of TOML files, scripts, and a lockfile. Diff it. Code-review it. Bisect a regression."
              />
              <ReasonCard
                Icon={ShieldCheck}
                title="Trust is published."
                body="Every solver ships with a public validation suite. We tell you what we get wrong and by how much."
              />
            </div>
          </div>
        </section>

        {/* ───────────────────── Workflow strip ───────────────────── */}
        <section className="mx-auto w-full max-w-5xl px-5 py-14">
          <div className="mb-8 text-center">
            <h2 className="text-xl font-semibold tracking-tight">
              The whole hero workflow, in one browser tab.
            </h2>
            <p className="mt-2 text-md text-text-muted">
              The path legacy desktop tools take a week to wire up.
            </p>
          </div>
          <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <WorkflowStep
              n={1}
              Icon={Network}
              title="Cycle"
              body="Drag components, connect flows, converge a recuperated Brayton in under 200 ms."
            />
            <WorkflowStep
              n={2}
              Icon={Wind}
              title="Flow path"
              body="Drop into preliminary design with the cycle's exit conditions pre-loaded."
            />
            <WorkflowStep
              n={3}
              Icon={Grid3x3}
              title="Explore + Map"
              body="Sweep 2,000 candidates, then build a performance map with explicit surge & choke."
            />
            <WorkflowStep
              n={4}
              Icon={Cog}
              title="Rotor"
              body="Import the impeller as a lumped disk and run lateral: Bode, Campbell, margins."
            />
          </ol>
        </section>

        <footer className="mt-auto border-t border-border-subtle">
          <div className="mx-auto flex w-full max-w-5xl flex-col items-center justify-between gap-3 px-5 py-6 text-sm text-text-muted sm:flex-row">
            <div className="flex items-center gap-2">
              <CascadeMark />
              <span>© 2026 American Turbines</span>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-4">
              <Link href="/docs" className="hover:text-text">
                Docs
              </Link>
              <Link href="/docs/validation" className="hover:text-text">
                Validation
              </Link>
              <Link href="/changelog" className="hover:text-text">
                Changelog
              </Link>
              <Link href="/terms" className="hover:text-text">
                Terms
              </Link>
              <Link href="/privacy" className="hover:text-text">
                Privacy
              </Link>
              <a
                href="mailto:services@americanturbines.com"
                className="hover:text-text"
              >
                Services
              </a>
              <a
                href="https://github.com/americanturbines/cascade"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 hover:text-text"
              >
                <Github className="h-3.5 w-3.5" />
                Source
              </a>
            </div>
          </div>
        </footer>
      </main>
    </div>
  );
}

function AudienceCard({
  eyebrow,
  title,
  body,
  cta,
  href,
  Icon,
  primary = false,
}: {
  eyebrow: string;
  title: string;
  body: string;
  cta: string;
  href: string;
  Icon: typeof Wind;
  primary?: boolean;
}) {
  return (
    <Link href={href} className="group block focus-visible:outline-none">
      <div
        className={`relative flex h-full flex-col gap-3 overflow-hidden rounded-xl border p-6 shadow-z1 transition-all duration-medium ease-out group-hover:-translate-y-0.5 group-hover:shadow-z3 group-focus-visible:ring-2 group-focus-visible:ring-border-focus ${
          primary
            ? "border-brand/30 bg-brand-surface/40"
            : "border-border-subtle bg-surface-raised"
        }`}
      >
        <div className="flex items-center justify-between">
          <span
            className={`flex h-10 w-10 items-center justify-center rounded-lg ${
              primary
                ? "bg-brand-gradient text-text-inverse shadow-z1"
                : "border border-border-subtle bg-surface-subtle text-text-subtle"
            }`}
          >
            <Icon className="h-5 w-5" />
          </span>
          <span className="text-xs font-medium uppercase tracking-wide text-text-muted">
            {eyebrow}
          </span>
        </div>
        <h3 className="text-lg font-semibold tracking-tight">{title}</h3>
        <p className="text-sm leading-relaxed text-text-muted">{body}</p>
        <span className="mt-auto inline-flex items-center gap-1.5 pt-2 text-sm font-medium text-brand-text">
          {cta}
          <ArrowRight className="h-4 w-4 transition-transform duration-base group-hover:translate-x-0.5" />
        </span>
      </div>
    </Link>
  );
}

function ReasonCard({
  Icon,
  title,
  body,
}: {
  Icon: typeof Sigma;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-xl border border-border-subtle bg-surface-raised p-5 shadow-z1">
      <span className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-brand-surface text-brand">
        <Icon className="h-4 w-4" />
      </span>
      <h3 className="text-md font-semibold tracking-tight">{title}</h3>
      <p className="mt-1.5 text-sm leading-relaxed text-text-muted">{body}</p>
    </div>
  );
}

function WorkflowStep({
  n,
  Icon,
  title,
  body,
}: {
  n: number;
  Icon: typeof Network;
  title: string;
  body: string;
}) {
  return (
    <li className="relative flex flex-col gap-2 rounded-xl border border-border-subtle bg-surface-raised p-4 shadow-z1">
      <div className="flex items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-md bg-surface-subtle text-text-subtle">
          <Icon className="h-4 w-4" />
        </span>
        <span className="font-mono text-xs text-text-muted">
          {String(n).padStart(2, "0")}
        </span>
      </div>
      <h3 className="text-md font-semibold tracking-tight">{title}</h3>
      <p className="text-sm leading-relaxed text-text-muted">{body}</p>
    </li>
  );
}
